"""Split discipline: closed over leakage, priority-ordered, and never random.

Defends spec Section 17.7: splits MUST prevent leakage by grouping on the named
dimensions, and a random sentence split is nonconforming for semantic-detector
evaluation.

Also defends the two leakage findings that shape the grouping: documents may
be byte-identical across repositories, so repository is not a sufficient key;
and a group formed at a high priority is never divided to improve a
lower-priority distribution target.
"""

from __future__ import annotations

import datetime as dt

import pytest

from ats.context import Context
from ats.corpus import records as rec
from ats.corpus import split
from ats.errors import UsageError

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)

POLICY = {
    "policy_id": "unit-test",
    "seed": "ats-1.0.0-draft.1",
    "partitions": [
        {
            "name": "training",
            "kind": "training",
            "target_fraction": 0.6,
            "disjoint_on": ["source_document", "source_mutation_pair"],
        },
        {
            "name": "development",
            "kind": "development",
            "target_fraction": 0.2,
            "disjoint_on": ["source_document", "source_mutation_pair"],
        },
        {
            "name": "evaluation",
            "kind": "in_domain_evaluation",
            "target_fraction": 0.2,
            "disjoint_on": ["source_document", "source_mutation_pair", "near_duplicate_cluster"],
        },
    ],
}

#: The eight dimensions spec 17.7 enumerates, in this repository's spelling.
SPEC_17_7 = (
    "source_document",
    "repository",
    "author",
    "source_model_family",
    "template",
    "mutation_family",
    "domain",
    "near_duplicate_cluster",
)


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


def _example(ctx: Context, name: str, **overrides) -> dict:
    fields = {
        "text": f"Example {name}.",
        "profile": "SPECIFY",
        "rule_id": "ATS-DEON-001",
        "label": "conforming",
        "rationale": f"Fixture example {name}.",
        "protected_impact": ["P0"],
        "provenance": "human_authored_fixture",
        "synthetic": False,
        "split_group": name,
        "repository_group": "unit-repo",
    }
    fields.update(overrides)
    example = rec.text_example(**fields)
    ctx.schemas.validate_document(example)
    return example


def _artifact(ctx: Context, repository: str, path: str, *, content: str, **overrides) -> dict:
    """A real ``SourceArtifactV1``: the carrier of content_hash across repositories."""
    digest = split.sha256_hex(content.encode("utf-8"))
    fields = {
        "repository": repository,
        "repository_group": repository,
        "path": path,
        "revision": "0" * 40,
        "content_sha256": digest,
        "normalized_sha256": digest,
        "media_type": "text/markdown",
        "review_state": "unknown",
        "use_authority": "internal_training_permitted",
        "handling_policy": "internal",
        "ingested_at": ctx.timestamp(),
    }
    fields.update(overrides)
    artifact = rec.source_artifact(**fields)
    ctx.schemas.validate_document(artifact)
    return artifact


def _checks(result: dict, dimension: str, kind: str) -> dict:
    return next(
        c for c in result["leakage_checks"] if c["dimension"] == dimension and c["kind"] == kind
    )


def test_the_dimensions_are_the_schema_s(ctx: Context) -> None:
    """Spec 17.7 names the leakage dimensions; the schema enumerates them."""
    schema = ctx.schemas.schema("ats_corpus_split_v1.schema.json")
    assert list(schema["$defs"]["dimension"]["enum"]) == list(split.DIMENSIONS)
    assert len(split.DIMENSIONS) == 14
    assert set(SPEC_17_7) <= set(split.DIMENSIONS)
    # Every dimension has exactly one role and exactly one priority: an
    # unranked dimension has no defined behaviour under the priority order.
    assert set(split.CLOSURE_DIMENSIONS) | set(split.CONSTRAINT_DIMENSIONS) == set(
        split.DIMENSIONS
    )
    assert not set(split.CLOSURE_DIMENSIONS) & set(split.CONSTRAINT_DIMENSIONS)
    assert set(split.PRIORITY) == set(split.DIMENSIONS)
    assert set(split.TIER) == set(split.DIMENSIONS)


def test_the_priority_order_is_the_declared_one() -> None:
    """The order is the contract: closure above every placement constraint."""
    assert [t[0] for t in split.CLOSURE_TIERS + split.CONSTRAINT_TIERS] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert [t[1] for t in split.CLOSURE_TIERS + split.CONSTRAINT_TIERS] == [
        "lineage_integrity",
        "exact_content_integrity",
        "near_duplicate_integrity",
        "project_disjointness",
        "template_disjointness",
        "author_disjointness",
        "domain_balance",
        "residual_disjointness",
    ]
    assert max(split.PRIORITY[d] for d in split.CLOSURE_DIMENSIONS) < min(
        split.PRIORITY[d] for d in split.CONSTRAINT_DIMENSIONS
    )


def test_a_random_split_is_refused(ctx: Context) -> None:
    """Spec 17.7: a random sentence split is nonconforming."""
    examples = [_example(ctx, "a")]
    with pytest.raises(UsageError, match="random sentence split"):
        split.generate_split(ctx, examples, {**POLICY, "grouping_dimensions": []})


def test_assignment_without_a_grouping_key_is_refused() -> None:
    """The assignment function itself will not place an ungrouped example."""
    with pytest.raises(UsageError, match="no grouping key"):
        split.assign("seed", "", POLICY["partitions"])


def test_an_example_missing_a_required_dimension_is_unassignable(ctx: Context) -> None:
    """Spec 17.7: an ungroupable example is recorded, never dropped into training."""
    grouped = _example(ctx, "grouped")
    ungrouped = _example(ctx, "ungrouped", repository_group=None)
    result = split.generate_split(
        ctx,
        [grouped, ungrouped],
        {**POLICY, "grouping_dimensions": ["repository", "source_mutation_pair"]},
    )
    assert ungrouped["example_id"] not in result["assignments"]
    assert result["unassignable"] == [
        {"example_id": ungrouped["example_id"], "missing_dimensions": ["repository"]}
    ]
    assert grouped["example_id"] in result["assignments"]


def test_assignment_is_a_pure_function_of_seed_and_key() -> None:
    """Spec 16.2 and 17.7: no RNG state, so no dependence on iteration order."""
    partitions = POLICY["partitions"]
    first = split.assign("seed-a", "group-1", partitions)
    assert first == split.assign("seed-a", "group-1", partitions)
    assert first in {p["name"] for p in partitions}
    # A different seed is a different draw; the same seed never is.
    draws = {split.assign(f"seed-{i}", "group-1", partitions) for i in range(24)}
    assert len(draws) > 1


def test_insertion_order_does_not_change_assignments(ctx: Context) -> None:
    """Inserting an example never reshuffles the rest."""
    examples = [_example(ctx, name) for name in ("a", "b", "c", "d")]
    forward = split.generate_split(ctx, examples, POLICY)
    reversed_ = split.generate_split(ctx, list(reversed(examples)), POLICY)
    assert forward["assignments"] == reversed_["assignments"]

    extra = examples + [_example(ctx, "e")]
    grown = split.generate_split(ctx, extra, POLICY)
    for example in examples:
        assert grown["assignments"][example["example_id"]] == forward["assignments"][
            example["example_id"]
        ]


def test_a_mutation_and_its_source_share_a_group(ctx: Context) -> None:
    """Spec 17.7: a mutation stays in the same split group as its source."""
    source = _example(ctx, "source")
    mutant = _example(
        ctx,
        "source",
        text="Mutated example.",
        label="violation",
        rationale="A mutation of the source.",
        synthetic=True,
        provenance="synthetic_mutation",
        mutation_operator="ATS-MUT-NEGATION-FLIP",
        extensions={rec.EXT_SOURCE_EXAMPLE_ID: source["example_id"]},
    )
    result = split.generate_split(ctx, [source, mutant, _example(ctx, "other")], POLICY)
    group = next(
        g for g in result["groups"] if source["example_id"] in g["example_ids"]
    )
    assert mutant["example_id"] in group["example_ids"]
    assert split.pair_is_grouped(result, source["example_id"], mutant["example_id"])


def test_a_chain_of_mutations_stays_in_one_group(ctx: Context) -> None:
    """Lineage integrity is priority 1, and a chain shares no single pair value.

    A mutant of a mutant points at its parent while the parent points at the
    original, so joining on the shared pair value alone would leave the
    grandchild in its own group — an evaluation example whose answer is a diff
    away from a training example.
    """
    source = _example(ctx, "source")
    first = _example(
        ctx,
        "first",
        text="Once mutated.",
        label="violation",
        rationale="First mutation.",
        synthetic=True,
        provenance="synthetic_mutation",
        mutation_operator="ATS-MUT-NEGATION-FLIP",
        extensions={rec.EXT_SOURCE_EXAMPLE_ID: source["example_id"]},
    )
    second = _example(
        ctx,
        "second",
        text="Twice mutated.",
        label="violation",
        rationale="Mutation of the mutation.",
        synthetic=True,
        provenance="synthetic_mutation",
        mutation_operator="ATS-MUT-SCOPE-DROP",
        extensions={rec.EXT_SOURCE_EXAMPLE_ID: first["example_id"]},
    )
    result = split.generate_split(ctx, [source, first, second], POLICY)
    assert len(result["groups"]) == 1
    assert result["groups"][0]["example_ids"] == sorted(
        [source["example_id"], first["example_id"], second["example_id"]]
    )
    assert result["groups"][0]["closure_priority"] == 1


def test_an_explicit_derivation_joins_examples(ctx: Context) -> None:
    """A declared derivation is a leakage edge even with no mutation operator."""
    parent = _example(ctx, "parent")
    child = _example(
        ctx, "child", extensions={split.EXT_DERIVED_FROM: parent["example_id"]}
    )
    stranger = _example(ctx, "stranger")
    result = split.generate_split(ctx, [parent, child, stranger], POLICY)
    assert result["assignments"][parent["example_id"]] == result["assignments"][
        child["example_id"]
    ]
    group = next(g for g in result["groups"] if parent["example_id"] in g["example_ids"])
    assert group["example_ids"] == sorted([parent["example_id"], child["example_id"]])
    assert "explicit_derivation" in group["closure_dimensions"]
    assert stranger["example_id"] not in group["example_ids"]


def test_a_shared_source_document_joins_examples(ctx: Context) -> None:
    """Two spans of one document cannot be split across partitions."""
    artifact = "ats-artifact-sha256:" + "a" * 64
    left = _example(ctx, "left", source_artifact=artifact)
    right = _example(ctx, "right", source_artifact=artifact)
    apart = _example(ctx, "apart", source_artifact="ats-artifact-sha256:" + "b" * 64)
    result = split.generate_split(
        ctx,
        [left, right, apart],
        {**POLICY, "grouping_dimensions": ["source_document", "repository", "source_mutation_pair"]},
    )
    assert result["assignments"][left["example_id"]] == result["assignments"][
        right["example_id"]
    ]
    groups = {g["group_key"]: set(g["example_ids"]) for g in result["groups"]}
    assert any(
        {left["example_id"], right["example_id"]} == members for members in groups.values()
    )
    assert {apart["example_id"]} in list(groups.values())


def test_a_near_duplicate_joins_examples(ctx: Context) -> None:
    """Spec 17.7 names near-duplicate cluster as a grouping dimension."""
    cluster = "nearduplicate-abc"
    left = _example(ctx, "left", extensions={rec.EXT_NEAR_DUPLICATE_CLUSTER: cluster})
    right = _example(ctx, "right", extensions={rec.EXT_NEAR_DUPLICATE_CLUSTER: cluster})
    result = split.generate_split(ctx, [left, right], POLICY)
    assert len(result["groups"]) == 1
    assert result["assignments"][left["example_id"]] == result["assignments"][
        right["example_id"]
    ]


def test_the_same_content_hash_joins_two_repositories(ctx: Context) -> None:
    """Identical content joins across repository labels without using repository alone.

    The examples are caller-supplied synthetic artifacts; no checked-in corpus
    history is required.
    """
    text = "# Contributing\n\nEvery change MUST carry a receipt.\n"
    left_artifact = _artifact(ctx, "repo-alpha", "CLAUDE.md", content=text)
    right_artifact = _artifact(ctx, "repo-beta", "CLAUDE.md", content=text)
    other_artifact = _artifact(ctx, "repo-alpha", "README.md", content="# Something else\n")
    assert left_artifact["artifact_id"] != right_artifact["artifact_id"]
    assert left_artifact["content_sha256"] == right_artifact["content_sha256"]

    left = _example(
        ctx, "left", repository_group="repo-alpha", source_artifact=left_artifact["artifact_id"]
    )
    right = _example(
        ctx,
        "right",
        repository_group="repo-beta",
        source_artifact=right_artifact["artifact_id"],
    )
    other = _example(
        ctx, "other", repository_group="repo-alpha", source_artifact=other_artifact["artifact_id"]
    )
    result = split.generate_split(
        ctx,
        [left, right, other],
        {**POLICY, "grouping_dimensions": ["source_document", "repository"]},
        artifacts=[left_artifact, right_artifact, other_artifact],
    )
    group = next(g for g in result["groups"] if left["example_id"] in g["example_ids"])
    assert right["example_id"] in group["example_ids"]
    assert result["assignments"][left["example_id"]] == result["assignments"][
        right["example_id"]
    ]
    assert group["closure_priority"] == 2
    assert "content_hash" in group["closure_dimensions"]
    # The group spans two repositories, which is the whole point: repository is
    # recorded, and did not divide the group.
    assert group["dimension_values"]["repository"] == "repo-alpha,repo-beta"
    assert other["example_id"] not in group["example_ids"]


def test_a_transitive_chain_of_clusters_joins_three_examples(ctx: Context) -> None:
    """Closure is transitive: A~B by near duplicate, B~C by copied template.

    A and C share no value at all. A per-example key, or one union pass per
    dimension without transitivity, would put them in different groups and leak
    B's text into both sides.
    """
    a = _example(ctx, "a", extensions={rec.EXT_NEAR_DUPLICATE_CLUSTER: "nd-1"})
    b = _example(
        ctx,
        "b",
        extensions={
            rec.EXT_NEAR_DUPLICATE_CLUSTER: "nd-1",
            rec.EXT_COPIED_TEXT_CLUSTER: "copy-9",
        },
    )
    c = _example(ctx, "c", extensions={rec.EXT_COPIED_TEXT_CLUSTER: "copy-9"})
    far = _example(ctx, "far")
    result = split.generate_split(ctx, [a, b, c, far], POLICY)
    group = next(g for g in result["groups"] if a["example_id"] in g["example_ids"])
    assert group["example_ids"] == sorted(
        [a["example_id"], b["example_id"], c["example_id"]]
    )
    assert len({result["assignments"][e["example_id"]] for e in (a, b, c)}) == 1
    assert sorted(group["closure_dimensions"]) == ["copied_text_cluster", "near_duplicate_cluster"]
    assert far["example_id"] not in group["example_ids"]


def test_repository_constrains_placement_but_never_divides_a_group(ctx: Context) -> None:
    """Joining on repository would collapse a one-repository corpus into one group."""
    assert "repository" not in split.CLOSURE_DIMENSIONS
    assert "repository" in split.CONSTRAINT_DIMENSIONS
    examples = [_example(ctx, name) for name in ("a", "b", "c", "d", "e", "f")]
    result = split.generate_split(ctx, examples, POLICY)
    assert len(result["groups"]) == len(examples)
    assert len(set(result["assignments"].values())) > 1


def test_a_declared_constraint_co_places_groups_without_dividing_them(ctx: Context) -> None:
    """Project disjointness is enforced by co-placement, not by grouping."""
    left = [_example(ctx, f"l{i}", repository_group="repo-left") for i in range(3)]
    right = [_example(ctx, f"r{i}", repository_group="repo-right") for i in range(3)]
    policy = {
        **POLICY,
        "partitions": [
            {"name": "training", "kind": "training", "target_fraction": 0.5},
            {
                "name": "evaluation",
                "kind": "project_disjoint_evaluation",
                "target_fraction": 0.5,
                "disjoint_on": ["repository"],
            },
        ],
    }
    result = split.generate_split(ctx, left + right, policy)
    # Every group stays a single example: a constraint co-places, it never joins.
    assert len(result["groups"]) == 6
    for side in (left, right):
        assert len({result["assignments"][e["example_id"]] for e in side}) == 1
    check = _checks(result, "repository", "disjointness")
    assert check["status"] == "PASS"
    assert check["priority"] == 4
    # The co-placement is auditable: each block's lowest-keyed group is placed
    # on its own key and the other four record whose key they inherited.
    assert sum(1 for g in result["groups"] if "placement_block" in g) == 4


def test_a_constraint_that_would_collapse_the_split_is_reported_unmet(ctx: Context) -> None:
    """A single-repository corpus cannot be project-disjoint, and says so."""
    examples = [_example(ctx, name) for name in ("a", "b", "c", "d")]
    policy = {
        **POLICY,
        "partitions": [
            {"name": "training", "kind": "training", "target_fraction": 0.5},
            {
                "name": "evaluation",
                "kind": "project_disjoint_evaluation",
                "target_fraction": 0.5,
                "disjoint_on": ["repository"],
            },
        ],
    }
    result = split.generate_split(ctx, examples, policy)
    check = _checks(result, "repository", "disjointness")
    assert check["status"] == "UNMET"
    assert "would collapse" in check["detail"]
    # The split is still a split: the target was reported unmet rather than met
    # by emptying a partition.
    assert len(set(result["assignments"].values())) > 1
    assert not any("placement_block" in g for g in result["groups"])


def test_a_domain_balance_target_blocked_by_an_exact_content_group_is_unmet(
    ctx: Context,
) -> None:
    """Priority 2 beats priority 7: the group holds and the target is reported unmet.

    ``quantitative-finance`` exists only inside one exact-content group, so no
    placement of that group can give any partition a proportional share of the
    domain. The only way to hit the target is to divide the group, which would
    put the same bytes on both sides of the split.
    """
    text = "# Sizing\n\nPositions MUST be capped at 2% of book.\n"
    left_artifact = _artifact(ctx, "repo-quant-a", "SIZING.md", content=text, domain="quant")
    right_artifact = _artifact(ctx, "repo-quant-b", "SIZING.md", content=text, domain="quant")
    left = _example(
        ctx,
        "qf-left",
        repository_group="repo-quant-a",
        domain="quantitative-finance",
        source_artifact=left_artifact["artifact_id"],
    )
    right = _example(
        ctx,
        "qf-right",
        repository_group="repo-quant-b",
        domain="quantitative-finance",
        source_artifact=right_artifact["artifact_id"],
    )
    others = [
        _example(ctx, f"ai{i}", domain="agent-infrastructure") for i in range(6)
    ]
    policy = {
        **POLICY,
        "balance_on": ["domain"],
        "balance_tolerance": 0.1,
    }
    result = split.generate_split(
        ctx,
        [left, right, *others],
        policy,
        artifacts=[left_artifact, right_artifact],
    )
    assert result["policy"]["balance_on"] == ["domain"]

    # The higher-priority group held.
    group = next(g for g in result["groups"] if left["example_id"] in g["example_ids"])
    assert right["example_id"] in group["example_ids"]
    assert group["closure_priority"] == 2
    assert result["assignments"][left["example_id"]] == result["assignments"][
        right["example_id"]
    ]

    check = _checks(result, "domain", "balance")
    assert check["status"] == "UNMET"
    assert check["priority"] == 7
    assert check["blocked_by"] == [
        {"dimension": "content_hash", "priority": 2, "group_key": group["group_key"]}
    ]
    # The report names what protects the group, not only a bare rank.
    assert "priority 2 (exact_content_integrity)" in check["detail"]
    assert "MUST NOT be broken" in check["detail"]
    # And the target is not silently reported as met somewhere else.
    assert not any(
        c["kind"] == "balance" and c["status"] == "PASS" for c in result["leakage_checks"]
    )


def test_a_met_balance_target_passes(ctx: Context) -> None:
    """The UNMET path is a finding, not the only outcome the code can produce."""
    examples = [_example(ctx, name, domain="prose") for name in ("a", "b", "c", "d")]
    policy = {
        **POLICY,
        "partitions": [{"name": "training", "kind": "training", "target_fraction": 1.0}],
        "balance_on": ["domain"],
    }
    result = split.generate_split(ctx, examples, policy)
    check = _checks(result, "domain", "balance")
    assert check["status"] == "PASS"
    assert "within" in check["detail"]


def test_an_undeclared_balance_target_produces_no_balance_claim(ctx: Context) -> None:
    """An undeclared target is not a target, and is not reported either way."""
    examples = [_example(ctx, name, domain="prose") for name in ("a", "b")]
    result = split.generate_split(ctx, examples, POLICY)
    assert not any(c["kind"] == "balance" for c in result["leakage_checks"])
    assert "balance_on" not in result["policy"]


def test_a_balance_target_over_an_uncarried_dimension_is_unavailable(ctx: Context) -> None:
    """Spec 20.6 and ADR-0002: an unmeasurable target is unavailable, not met."""
    examples = [_example(ctx, name) for name in ("a", "b")]
    result = split.generate_split(ctx, examples, {**POLICY, "balance_on": ["domain"]})
    check = _checks(result, "domain", "balance")
    assert check["status"] == "UNAVAILABLE"
    assert "cannot be measured" in check["detail"]


def test_an_unknown_balance_dimension_is_refused(ctx: Context) -> None:
    with pytest.raises(UsageError, match="unknown balance dimensions"):
        split.generate_split(ctx, [_example(ctx, "a")], {**POLICY, "balance_on": ["sentence"]})


def test_a_partially_carried_dimension_is_unavailable_not_pass(ctx: Context) -> None:
    """A check that could not run over the whole corpus must not read as a pass."""
    cluster = "nd-partial"
    carried = [
        _example(ctx, name, extensions={rec.EXT_NEAR_DUPLICATE_CLUSTER: cluster})
        for name in ("a", "b")
    ]
    bare = _example(ctx, "c")
    result = split.generate_split(ctx, [*carried, bare], POLICY)
    check = _checks(result, "near_duplicate_cluster", "closure")
    assert check["status"] == "UNAVAILABLE"
    assert "1 of 3 assigned example(s)" in check["detail"]


def test_a_leakage_check_is_emitted_for_every_dimension(ctx: Context) -> None:
    """A dimension nobody checked must not read as a dimension that passed."""
    result = split.generate_split(ctx, [_example(ctx, n) for n in ("a", "b")], POLICY)
    checks = {c["dimension"]: c for c in result["leakage_checks"]}
    assert set(checks) == set(split.DIMENSIONS)
    for check in checks.values():
        assert check["status"] in {"PASS", "FAIL", "UNAVAILABLE", "NOT_APPLICABLE", "UNMET"}
        assert check["detail"]
        assert check["priority"] == split.PRIORITY[check["dimension"]]
        assert check["kind"] in {"closure", "disjointness", "balance"}
    # repository is carried by every example but declared disjoint by none.
    assert checks["repository"]["status"] == "NOT_APPLICABLE"
    assert "no partition declares" in checks["repository"]["detail"]
    # author is carried by nobody.
    assert checks["author"]["status"] == "UNAVAILABLE"
    # source_mutation_pair is always checked.
    assert checks["source_mutation_pair"]["status"] == "PASS"


def test_the_always_checked_dimensions_cannot_be_waived(ctx: Context) -> None:
    """Leakage on a closure dimension is not something a policy may authorise."""
    assert split.ALWAYS_CHECKED == split.CLOSURE_DIMENSIONS
    assert {"source_document", "source_mutation_pair", "content_hash"} <= set(
        split.ALWAYS_CHECKED
    )
    policy = {
        **POLICY,
        "partitions": [
            {"name": "all", "kind": "training", "target_fraction": 1.0},
        ],
    }
    result = split.generate_split(ctx, [_example(ctx, "a")], policy)
    checks = {c["dimension"]: c["status"] for c in result["leakage_checks"]}
    assert checks["source_mutation_pair"] == "PASS"


def test_an_artifact_supplies_only_what_the_example_lacks(ctx: Context) -> None:
    """The example is the record being split; the artifact fills the gaps.

    Author provenance is available for every document in the corpus but only as
    an artifact field. The withheld artifact below still carries the author
    string beside the state, which the schema permits: spec Section 17.4 and
    SP-20 make an availability state other than ``present`` not an author, so
    the recorded string MUST NOT be read as one.
    """
    withheld = _artifact(
        ctx,
        "repo-alpha",
        "DESIGN.md",
        content="# Design\n",
        domain="agent-infrastructure",
        template_family="template-7",
        author_provenance={"availability": "withheld", "author": "recorded@example.com"},
    )
    named = _artifact(
        ctx,
        "repo-alpha",
        "OTHER.md",
        content="# Other\n",
        author_provenance={"availability": "present", "author": "someone@example.com"},
    )
    example = _example(ctx, "a", source_artifact=withheld["artifact_id"], domain="prose")
    values = split.dimension_values(example, artifact=withheld)
    # The example's own domain wins over the artifact's.
    assert values["domain"] == "prose"
    assert values["template"] == "template-7"
    assert values["content_hash"] == withheld["content_sha256"]
    assert "author" not in values
    assert split.dimension_values(example, artifact=named)["author"] == "someone@example.com"


def test_the_split_record_validates(ctx: Context) -> None:
    result = split.generate_split(ctx, [_example(ctx, n) for n in ("a", "b", "c")], POLICY)
    assert ctx.schemas.validate_document(result) == "ats_corpus_split_v1.schema.json"
    assert result["split_id"].startswith("ats-split-sha256:")
    ok, detail = rec.verify_record(result)
    assert ok, detail
    assert len(result["corpus_sha256"]) == 64
    assert result["grouping_dimensions"] == list(split.DEFAULT_GROUPING_DIMENSIONS)


def test_an_unknown_grouping_dimension_is_refused(ctx: Context) -> None:
    with pytest.raises(UsageError, match="unknown grouping dimensions"):
        split.generate_split(
            ctx, [_example(ctx, "a")], {**POLICY, "grouping_dimensions": ["sentence"]}
        )


def test_a_corpus_where_nothing_is_groupable_is_refused(ctx: Context) -> None:
    """Assigning ungroupable examples anyway would be the random split under a new name."""
    ungrouped = _example(ctx, "x", repository_group=None)
    with pytest.raises(UsageError, match="random sentence split"):
        split.generate_split(ctx, [ungrouped], POLICY)

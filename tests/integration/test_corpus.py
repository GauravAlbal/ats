"""The corpus pipeline end to end, against a real Git repository.

inventory -> context bundle -> mine -> mutate -> annotate -> adjudicate ->
split -> stats, with no mocks anywhere: the sample repository is created by
``git init`` and real commits, and every emitted record is validated against its
schema before it is used by the next stage.

Defends spec Sections 17.4 through 17.9 as a chain rather than as isolated
units, plus Section 5.5 (an unsupported capability is reported, not emulated).
"""

from __future__ import annotations

import datetime as dt
import json
import sys

import pytest

from ats.context import Context
from ats.corpus import adjudicate, annotate, inventory, mine, mutate, split, stats
from ats.corpus import context as ctxmod
from ats.corpus import records as rec
from ats.errors import UnsupportedCapabilityError, UsageError
from ats.spec_package import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
from generate_corpus_fixtures import build_sample_repo  # noqa: E402

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)

SPLIT_POLICY = {
    "policy_id": "ats-corpus-v0",
    "seed": "ats-1.0.0-draft.1",
    # Spec 17.7: for a mined corpus the source document is a required grouping key.
    "grouping_dimensions": ["source_document", "repository", "source_mutation_pair"],
    "partitions": [
        {
            "name": "training",
            "kind": "training",
            "target_fraction": 0.6,
            "disjoint_on": ["source_document", "source_mutation_pair", "near_duplicate_cluster"],
        },
        {
            "name": "development",
            "kind": "development",
            "target_fraction": 0.2,
            "disjoint_on": ["source_document", "source_mutation_pair", "near_duplicate_cluster"],
        },
        {
            "name": "evaluation",
            "kind": "project_disjoint_evaluation",
            "target_fraction": 0.2,
            "disjoint_on": [
                "source_document",
                "source_mutation_pair",
                "near_duplicate_cluster",
                "template",
            ],
        },
    ],
}


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    """A real Git repository: git init plus three real commits, no mock."""
    return build_sample_repo(tmp_path_factory.mktemp("git") / "sample-repo")


@pytest.fixture(scope="module")
def pipeline(ctx: Context, repo, tmp_path_factory):
    """Run the whole chain once and hand every stage's output to the tests."""
    store = tmp_path_factory.mktemp("corpus")

    # 1. Inventory the repository at its exact revision.
    inv = inventory.build_inventory(ctx, repo)
    artifacts = {a["artifact_id"]: a for a in inv["artifacts"]}
    texts = {a: inventory.artifact_text(repo, artifacts[a]) for a in artifacts}

    # 2. Mine candidates. No candidate carries a label.
    mined = mine.mine_candidates(ctx, inv)

    # 3. Build a context bundle for each distinct candidate span.
    bundles: dict[str, dict] = {}
    examples: list[dict] = []
    labels = {
        "deontic-noncanonical": ("ATS-DEON-001", "violation"),
        "wep-canonical-phrase": ("ATS-EPI-002", "conforming"),
        "relative-time-expression": ("ATS-TIME-002", "violation"),
        "deontic-surface": ("ATS-DEON-001", "conforming"),
    }
    for candidate in mined["candidates"]:
        curated = labels.get(candidate["signal"]["signal_id"])
        if curated is None:
            continue
        artifact = artifacts[candidate["artifact_id"]]
        bundle = ctxmod.build_context_bundle(
            ctx,
            artifact=artifact,
            text=texts[candidate["artifact_id"]],
            span=candidate["span"],
            repo_path=repo,
            profile_hint=(candidate["profile_hypotheses"] or [None])[0],
        )
        rule_id, label = curated
        example = rec.text_example(
            text=bundle["span_text"],
            context=bundle["containing_block"]["text"],
            source_artifact=artifact["artifact_id"],
            source_span=candidate["span"],
            repository_group=artifact["repository_group"],
            domain=artifact.get("domain"),
            profile=bundle["profile_hypothesis"]["profile"],
            rule_id=rule_id,
            label=label,
            rationale=f"Curated label for a mined {candidate['signal']['signal_id']} candidate.",
            protected_impact=["P0"],
            provenance="human_authored_fixture",
            use_authority=artifact["use_authority"],
            synthetic=False,
            split_group=f"{artifact['repository_group']}:{artifact['path']}",
            extensions={
                rec.EXT_CONTEXT_BUNDLE_ID: bundle["bundle_id"],
                rec.EXT_TEMPLATE_FAMILY: artifact.get("template_family"),
                rec.EXT_NEAR_DUPLICATE_CLUSTER: artifact.get("near_duplicate_cluster"),
            },
        )
        bundles[example["example_id"]] = bundle
        examples.append(example)

    # 4. Mutate the curated IR source, producing paired synthetic examples.
    ir = json.loads(
        (REPO_ROOT / "fixtures/mutations/sources/assess_mutation_source.json").read_text(
            encoding="utf-8"
        )
    )
    mutation_source = rec.text_example(
        text=ir["sections"][0]["claims"][0]["proposition"],
        profile="ASSESS",
        rule_id="ATS-EPI-001",
        label="conforming",
        rationale="Hand-authored mutation source.",
        protected_impact=["P0"],
        provenance="human_authored_fixture",
        synthetic=False,
        split_group="mutation-source-assess",
        repository_group="ats-seed",
        domain="acceptance-kernel",
        source_artifact="fixtures/mutations/sources/assess_mutation_source.json",
        extensions={rec.EXT_TEXT_IR: ir},
    )
    mutations, refused = mutate.apply_all(ctx, mutation_source)
    mutants = [m["mutant"] for m in mutations]

    # 5. Store everything append-only.
    examples_path = store / "examples.jsonl"
    rec.append_records(ctx, examples_path, examples + [mutation_source] + mutants)
    rec.append_records(ctx, store / "context_bundles.jsonl", list(bundles.values()))

    # 6. Two independent annotators, blind to each other.
    judgments: list[dict] = []
    for annotator in ("human:annotator-a", "human:annotator-b"):
        queue = annotate.build_queue(
            ctx, examples, annotator, bundles=bundles, existing_judgments=judgments
        )
        assert queue["blind"] is True
        for item in queue["items"]:
            example = next(e for e in examples if e["example_id"] == item["example_id"])
            disputed = item["rule_id"] == "ATS-TIME-002" and annotator.endswith("-b")
            judgments.append(
                annotate.submit_judgment(
                    ctx,
                    item=item,
                    annotator_id=annotator,
                    label="ambiguous" if disputed else example["label"],
                    rationale=(
                        "The rule text does not say whether a note anchors relative time."
                        if disputed
                        else example["rationale"]
                    ),
                    evidence_spans=[example["source_span"]]
                    if example["label"] == "violation" and not disputed
                    else [],
                    protected_impact=example["protected_impact"],
                    ambiguity_category="standard_ambiguity" if disputed else "none",
                )
            )
    judgments_path = store / "judgments.jsonl"
    rec.append_records(ctx, judgments_path, judgments)

    # 7. Adjudicate.
    adjudications = adjudicate.adjudicate_file(ctx, judgments_path, "human:adjudicator")
    rec.append_records(ctx, store / "adjudications.jsonl", adjudications)

    # 8. Split, then 9. report.
    all_examples = examples + [mutation_source] + mutants
    assignment = split.generate_split(ctx, all_examples, SPLIT_POLICY)
    report = stats.corpus_stats(ctx, store)

    return {
        "store": store,
        "inventory": inv,
        "mined": mined,
        "bundles": bundles,
        "examples": examples,
        "mutation_source": mutation_source,
        "mutations": mutations,
        "refused": refused,
        "judgments": judgments,
        "adjudications": adjudications,
        "split": assignment,
        "stats": report,
    }


def test_the_chain_produced_something_at_every_stage(pipeline) -> None:
    assert pipeline["inventory"]["artifacts"]
    assert pipeline["mined"]["candidates"]
    assert pipeline["bundles"]
    assert pipeline["examples"]
    assert pipeline["mutations"]
    assert pipeline["judgments"]
    assert pipeline["adjudications"]
    assert pipeline["split"]["groups"]


def test_every_emitted_record_validates_against_its_schema(ctx: Context, pipeline) -> None:
    """No stage hands the next one an object that could not be stored."""
    expected = {
        "ats.source_artifact.v1": "ats_source_artifact_v1.schema.json",
        "ats.context_bundle.v1": "ats_context_bundle_v1.schema.json",
        "ats.text_example.v1": "ats_text_example_v1.schema.json",
        "ats.judgment.v1": "ats_judgment_v1.schema.json",
        "ats.corpus_adjudication.v1": "ats_corpus_adjudication_v1.schema.json",
        "ats.corpus_split.v1": "ats_corpus_split_v1.schema.json",
    }
    records = (
        pipeline["inventory"]["artifacts"]
        + list(pipeline["bundles"].values())
        + pipeline["examples"]
        + [m["mutant"] for m in pipeline["mutations"]]
        + pipeline["judgments"]
        + pipeline["adjudications"]
        + [pipeline["split"]]
    )
    seen: set[str] = set()
    for record in records:
        schema_version = record["schema_version"]
        seen.add(schema_version)
        assert ctx.schemas.validate_document(record) == expected[schema_version]
        ok, detail = rec.verify_record(record)
        assert ok, detail
    assert seen == set(expected)


def test_the_stored_corpus_validates(ctx: Context, pipeline) -> None:
    report = rec.validate_records(ctx, pipeline["store"])
    assert report["problems"] == []
    assert report["records_checked"] == sum(report["by_schema"].values())


def test_the_store_is_append_only(ctx: Context, pipeline) -> None:
    """Spec 17.9: retained disagreement needs a store that cannot be rewritten."""
    with pytest.raises(UsageError, match="append-only"):
        rec.append_records(
            ctx, pipeline["store"] / "judgments.jsonl", [pipeline["judgments"][0]]
        )


def test_a_mutation_and_its_source_share_a_split_group(pipeline) -> None:
    """Spec 17.7: a mutation MUST stay in the same split group as its source."""
    assignment = pipeline["split"]
    source_id = pipeline["mutation_source"]["example_id"]
    assert pipeline["mutations"]
    group = next(g for g in assignment["groups"] if source_id in g["example_ids"])
    for mutation in pipeline["mutations"]:
        mutant_id = mutation["mutant"]["example_id"]
        assert mutant_id in group["example_ids"]
        assert split.pair_is_grouped(assignment, source_id, mutant_id)
        assert mutation["mutant"]["split_group"] == pipeline["mutation_source"]["split_group"]


def test_a_random_sentence_split_is_refused(ctx: Context, pipeline) -> None:
    """Spec 17.7: a random sentence split is nonconforming for semantic evaluation."""
    with pytest.raises(UsageError, match="random sentence split"):
        split.generate_split(
            ctx,
            pipeline["examples"],
            {**SPLIT_POLICY, "grouping_dimensions": []},
        )
    with pytest.raises(UsageError, match="no grouping key"):
        split.assign(SPLIT_POLICY["seed"], "", SPLIT_POLICY["partitions"])


def test_the_split_records_a_leakage_check_per_dimension(pipeline) -> None:
    checks = {c["dimension"]: c for c in pipeline["split"]["leakage_checks"]}
    assert set(checks) == set(split.DIMENSIONS)
    assert checks["source_document"]["status"] == "PASS"
    assert checks["source_mutation_pair"]["status"] == "PASS"
    assert all(c["status"] != "PASS" or c["detail"] for c in checks.values())


def test_a_needs_rule_revision_adjudication_is_not_gold_eligible(pipeline) -> None:
    """Spec 17.9: the case cannot be gold under a rule definition that cannot decide it."""
    revisions = [
        a for a in pipeline["adjudications"] if a["final_state"] == "needs_rule_revision"
    ]
    assert revisions, "the pipeline seeded a standard-ambiguity disagreement"
    for adjudication in revisions:
        assert adjudication["gold_eligible"] is False
        assert adjudication["required_rule_amendment"]
        assert adjudication["disagreement_category"] == "standard_defect"
        assert len(adjudication["judgments"]) >= 2


def test_an_unsupported_operator_raises_rather_than_degrading(ctx: Context, pipeline) -> None:
    """Spec 5.5: an unsupported capability is reported, never emulated by generation."""
    with pytest.raises(UnsupportedCapabilityError) as excinfo:
        mutate.apply_operator(
            ctx, pipeline["mutation_source"], "ATS-MUT-ANTECEDENT-AMBIGUATE"
        )
    assert excinfo.value.exit_code == 3
    refusals = {r["operator_id"]: r for r in pipeline["refused"]}
    assert refusals["ATS-MUT-ANTECEDENT-AMBIGUATE"]["reason"] == "unsupported"
    # Nothing was produced in its place.
    assert all(
        m["operator_id"] != "ATS-MUT-ANTECEDENT-AMBIGUATE" for m in pipeline["mutations"]
    )


def test_mining_never_labelled_anything(pipeline) -> None:
    """Spec 17.4: mining produces candidates; a person produces labels."""
    for candidate in pipeline["mined"]["candidates"]:
        assert candidate["label"] is None
        assert candidate["candidate_only"] is True
    # An accepted document in the repository produced no conforming label.
    accepted = [c for c in pipeline["mined"]["candidates"] if c["review_state"] == "accepted"]
    assert accepted
    assert all(c["label"] is None for c in accepted)


def test_context_bundles_carry_the_containing_block_and_revision(pipeline) -> None:
    """Spec 17.4: complete local context, the source revision, and an honest rating.

    A bundle rated below ``complete`` must be able to say which dimension it is
    missing. A rating with nothing behind it would let a fragment read as a
    whole document.
    """
    revisions = {a["revision"] for a in pipeline["inventory"]["artifacts"]}
    ratings = set()
    for bundle in pipeline["bundles"].values():
        assert bundle["source_revision"] in revisions
        assert bundle["span_text"] in bundle["containing_block"]["text"]
        assert bundle["diff"]["availability"] == "present"
        rating = bundle["context_completeness"]
        ratings.add(rating)
        assert rating in ("complete", "partial", "insufficient")
        if rating == "complete":
            continue
        searched = ("present", "not_found", "not_applicable")
        gaps = [
            field
            for field in ("preceding_context", "following_context", "diff", "review_comment",
                          "later_edit", "policy_context")
            if bundle[field]["availability"] not in searched
        ]
        assert gaps or bundle["profile_hypothesis"]["basis"] == "unknown"
    # The plain-text note declares no profile, so at least one bundle is honest
    # about being short of complete.
    assert ratings != {"complete"}


def test_the_report_separates_synthetic_from_natural(pipeline) -> None:
    """Spec 17.5: the two are never conflated as independent evidence."""
    report = pipeline["stats"]
    counts = report["synthetic_vs_natural"]
    assert counts["natural"] == len(pipeline["examples"]) + 1
    assert counts["synthetic"] == len(pipeline["mutations"])
    assert "17.5" in counts["note"]
    assert '"total"' not in json.dumps(report)


def test_the_report_counts_gold_eligibility_and_agreement(pipeline) -> None:
    report = pipeline["stats"]
    assert report["records"]["adjudications"] == len(pipeline["adjudications"])
    assert report["gold_eligible"]["eligible"] + report["gold_eligible"]["not_eligible"] == len(
        pipeline["adjudications"]
    )
    assert report["agreement"]["example_rule_pairs_with_two_independent_judgments"] > 0
    assert "needs_rule_revision" in report["gold_eligible"]["blocked_by_final_state"]


def test_the_pipeline_is_reproducible(ctx: Context, tmp_path, pipeline) -> None:
    """Spec 16.2: replaying the same plan at a different path yields identical records.

    The destination directory differs; the repository *name* does not, because
    the name is part of the artifact's content address while the absolute path
    deliberately is not.
    """
    second = build_sample_repo(tmp_path / "elsewhere" / "sample-repo")
    assert str(second) != pipeline["inventory"]["repository"]
    inv = inventory.build_inventory(ctx, second)
    assert [a["artifact_id"] for a in inv["artifacts"]] == [
        a["artifact_id"] for a in pipeline["inventory"]["artifacts"]
    ]
    mined = mine.mine_candidates(ctx, inv)
    assert [c["candidate_id"] for c in mined["candidates"]] == [
        c["candidate_id"] for c in pipeline["mined"]["candidates"]
    ]

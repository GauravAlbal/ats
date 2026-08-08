"""The sampling frame: what it draws, withholds, and refuses.

Defends the properties a governed annotation round is worthless without:

* only an authorised repository contributes a bundle (spec Sections 16.9, 17.13);
* the draw is a pure function of supplied inputs and the seed;
* one selection per leakage component, so exact-content grouping holds by
  construction;
* a miner prediction never reaches a blind annotator;
* a stratum that cannot be filled and a constraint the corpus cannot meet are
  reported as such, never quietly relaxed (ADR-0002, Section 17.5).

Synthetic repository fixtures exercise the draw end to end at a scale a test
can fill. Their honesty is asserted directly from generated inputs.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ats.canonical import verify_seal
from ats.context import Context
from ats.corpus import frame as fr
from ats.corpus import inventory as inv
from ats.corpus import mine
from ats.corpus.context import Block
from ats.errors import UsageError

NOW = dt.datetime(2026, 8, 3, tzinfo=dt.UTC)


#: Five authorised synthetic repositories and one that declares nothing. Five
#: because the repository share cap is a fraction of the target: a two-repository
#: fixture cannot fill any frame, so a cap that binds needs somewhere to spill.
AUTHORISED = ("alpha", "bravo", "charlie", "delta", "echo")
UNDECLARED = "zulu"

#: A scaled-down copy of :data:`ats.corpus.frame.STRATA`. Same mechanisms, same
#: order, targets a fixture can actually supply.
SMALL_STRATA = (
    fr.Stratum("surface_cue_hard_negative", 4, "cue in an exempting configuration"),
    fr.Stratum("revision_derived_candidate", 2, "a revision moved the text on a force axis"),
    fr.Stratum("low_signal_random_control", 4, "documents no signal pointed at"),
    fr.Stratum("zero_candidate_rule_probe", 4, "a rule with no candidates, probed"),
    fr.Stratum("natural_rule_candidate", 6, "a declared vocabulary matched"),
)
SMALL_TARGET = sum(s.target for s in SMALL_STRATA)

#: Byte-identical in two repositories, so the leakage closure has a
#: cross-repository content match to catch -- the exact case
#: STAGE_1_CENSUS_REPORT.md section 4 found in the real corpus and warned that
#: repository grouping alone would miss.
SHARED = (
    "# Shared note\n\n"
    "The same bytes appear in two repositories, so a split keyed on repository "
    "alone would place them on opposite sides.\n"
)

DENSE = (
    "# Dense\n\n"
    + " ".join(
        [
            "The scheduler admits a submission once its receipt verifies against the "
            "resolved snapshot, and it records the resolution alongside the admission "
            "so a later reader can reconstruct which snapshot was in force.",
            "A retry re-reads the snapshot rather than reusing the cached copy, because "
            "a snapshot that changed between the two reads would make the second "
            "admission a decision about a document nobody adjudicated.",
            "That behaviour is robust under concurrent submission and it is the reason "
            "the admission path holds no lock across the verification boundary.",
            "The queue drains in arrival order and the drain is observable through the "
            "same receipt the admission wrote, so an operator reading the log sees the "
            "sequence the scheduler actually took.",
        ]
    )
    + "\n"
)


def _git(repo: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2026-01-02T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-01-02T00:00:00+00:00",
        "PATH": "/usr/bin:/bin",
        "HOME": str(repo),
    }
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True
    ).stdout


def _documents(name: str, *, revised: bool) -> dict[str, str]:
    """One repository's documents, one per pool the frame draws from.

    Paths carry the repository name. ``inventory.near_duplicate_clusters`` keys a
    cluster on the lexicographically smallest *path* in it, so two repositories
    holding the same path are handed the same cluster identifier and the leakage
    closure joins them -- which would collapse this fixture into a handful of
    components and leave every stratum starved. The one document that is meant
    to be joined across repositories is joined on its bytes instead, which is
    the mechanism the closure is supposed to be tested on.
    """
    return {
        f"docs/{name}-cues.md": (
            f"# {name} cues\n\n"
            "The retention path is significant and the operator currently reviews it "
            f"{'twice' if revised else 'once'} per release.\n"
        ),
        f"docs/{name}-quoted.md": (
            f"# {name} quoted\n\n"
            "The prior specification said:\n\n"
            "> The exporter currently emits a significant summary for every receipt.\n\n"
            "That sentence is quoted, not asserted.\n"
        ),
        f"docs/{name}-anchored.md": (
            f"# {name} anchored\n\n"
            "As of 2026-03-14 the resolver currently reads the pinned snapshot and "
            "nothing else.\n"
        ),
        f"docs/{name}-dense.md": f"# {name}\n\n" + DENSE.split("\n\n", 1)[1],
        f"docs/{name}-plain.md": (
            f"# {name} pipeline\n\n"
            "The pipeline writes each record to disk. A reader opens the file and "
            "iterates the rows in the order they were written. Nothing in this "
            "document states a requirement or an estimate.\n"
        ),
        f"docs/{name}-force.md": (
            f"# {name} force\n\n"
            "The exporter "
            + ("MUST" if revised else "MAY")
            + " retry the upload after a transport failure.\n"
        ),
        f"docs/{name}-probe.md": (
            f"# {name} probe\n\n"
            "The API contract accepts at least three receipts per batch. This is "
            "checked by the verifier before admission. Every worker MUST record the "
            "batch identifier.\n\n"
            "## Glossary\n\n"
            "Receipt: the record a verifier writes.\n"
        ),
        f"notes/{name}-shared.md": SHARED,
    }


def _overlay(repository: str, revision: str) -> dict[str, Any]:
    """An owner declaration permitting annotation and mining, deferring training."""
    return {
        "schema_version": "ats.corpus_authority.v1",
        "principal": {"id": "https://example.invalid/fixture-owner", "kind": "person"},
        "authority_basis": {
            "kind": "owner_declared",
            "statement": "The principal authored every commit in this synthetic fixture.",
        },
        "repository": {
            "name": repository,
            "origin": None,
            "root_commit": "f" * 64,
            "effective_from_revision": revision,
            "declaration_location": "pilot_overlay",
        },
        "uses": {
            "inventory": "allow",
            "candidate_mining": "allow",
            "human_annotation": "allow",
            "deterministic_mutation": "allow",
            "evaluation": "allow",
            "model_training": "defer",
            "model_distillation": "defer",
            "external_model_submission": "deny",
            "publication": "deny",
            "cross_repository_derivatives": "allow_private",
        },
        "content": {"exclude": ["generated/*"]},
        "issued_at": "2026-01-01T00:00:00+00:00",
        "review_after": "2027-01-01T00:00:00+00:00",
        "superseded_by": None,
        "handling": {
            "classification": "private",
            "store_source_text": True,
            "store_context_bundles": True,
            "store_derived_features": True,
            "retain_deleted_revisions": True,
            "export_raw_text": False,
        },
        "provenance": {
            "authorship": "unknown_unless_explicit",
            "model_authorship_inference": "prohibited",
        },
        "notes": "Synthetic fixture repository.",
    }


@pytest.fixture(scope="module")
def now_ctx() -> Context:
    return Context.load(now=NOW)


@pytest.fixture(scope="module")
def corpus(now_ctx: Context, tmp_path_factory) -> dict[str, Any]:
    """Six synthetic repositories, five of them declared, inventoried and mined.

    The fixture asserts every pool it means to exercise is non-empty. A pool
    that silently emptied would leave the strata tests passing on nothing, which
    is the failure mode a sampling test is most exposed to.
    """
    root = tmp_path_factory.mktemp("frame-corpus")
    overlay_dir = root / "authority"
    overlay_dir.mkdir()

    rows: list[dict[str, Any]] = []
    for name in (*AUTHORISED, UNDECLARED):
        repo = root / name
        repo.mkdir()
        _git(repo, "init", "--quiet")
        for revised in (False, True):
            for relative, content in _documents(name, revised=revised).items():
                target = repo / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            _git(repo, "add", "--all")
            _git(repo, "commit", "--quiet", "-m", f"pass {int(revised)}")
        revision = _git(repo, "rev-parse", "HEAD").strip()
        if name in AUTHORISED:
            (overlay_dir / f"{name}.json").write_text(
                json.dumps(_overlay(name, revision), indent=2) + "\n", encoding="utf-8"
            )

    for name in (*AUTHORISED, UNDECLARED):
        repo = root / name
        inventory = inv.build_inventory(now_ctx, repo, authority_overlay=overlay_dir)
        # No digest argument: the inventory records the declaration it was
        # resolved under and the mining result reads it from there, so nothing
        # here hashes the overlay a second time. A cache that cannot name its
        # declaration is refused by the frame, which is the point.
        rows.append(
            {
                "repository": name,
                "family": f"{name}-family",
                "domain": "synthetic" if name in AUTHORISED[:3] else "synthetic-other",
                "revision": inventory["revision"],
                "inventory": inventory,
                "mined": mine.mine_candidates(now_ctx, inventory),
            }
        )

    return {"root": root, "overlay": overlay_dir, "rows": rows}


def _build(corpus: dict[str, Any], ctx: Context, *, seed: int = 7, **kwargs: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "repositories": corpus["rows"],
        "seed": seed,
        "target_size": SMALL_TARGET,
        "double_annotation_target": 8,
        "authority_overlay": corpus["overlay"],
        "strata": SMALL_STRATA,
        "corpus_review_states": {"unknown": 96},
        "unauthorised_profiles": {"x-reply-harness": {"SPECIFY": 2}},
    }
    defaults.update(kwargs)
    return fr.build_sampling_frame(ctx, **defaults)


@pytest.fixture(scope="module")
def drawn(corpus: dict[str, Any], now_ctx: Context) -> dict[str, Any]:
    return _build(corpus, now_ctx)




# -- the synthetic draw ------------------------------------------------------


def test_every_pool_the_frame_claims_to_draw_from_is_populated(
    corpus: dict[str, Any], now_ctx: Context
) -> None:
    """A vacuous pool would make every stratum assertion below pass on nothing."""
    authority = fr.resolve_annotation_authority(corpus["rows"], corpus["overlay"])
    # The digest travels with the source exactly as ``build_sampling_frame``
    # sends it: ``build_pools`` refuses a cache it cannot check against a live
    # declaration, and a test that withheld it would be testing the refusal.
    digests = {
        str(entry["repository"]): entry.get("declaration_sha256")
        for entry in authority["authorised"]
    }
    sources = [
        {
            **row,
            "declaration": authority["declarations"][row["repository"]],
            "declaration_sha256": digests.get(row["repository"]),
        }
        for row in corpus["rows"]
        if row["repository"] in authority["declarations"]
    ]
    assert len(sources) == len(AUTHORISED)
    pools, _, _, _ = fr.build_pools(now_ctx, sources)
    for stratum in SMALL_STRATA:
        assert len(pools[stratum.name]) >= stratum.target, stratum.name
    lanes = {p.lane for p in pools["surface_cue_hard_negative"]}
    assert lanes == {name for name, _ in fr.HARD_NEGATIVE_CLASSES}


def test_the_same_seed_reproduces_the_frame_byte_for_byte(
    corpus: dict[str, Any], now_ctx: Context, drawn: dict[str, Any]
) -> None:
    """Section 16.2: identical canonical inputs, identical result."""
    assert now_ctx.schemas.validate_document(drawn) == fr.SCHEMA_ID
    ok, declared, recomputed = verify_seal(drawn)
    assert ok, f"{declared} != {recomputed}"
    again = _build(corpus, now_ctx)
    assert json.dumps(again, sort_keys=True) == json.dumps(drawn, sort_keys=True)
    assert again["record_sha256"] == drawn["record_sha256"]
    assert again["frame_id"] == drawn["frame_id"]


def test_a_different_seed_is_a_different_draw(
    corpus: dict[str, Any], now_ctx: Context, drawn: dict[str, Any]
) -> None:
    """The seed has to do work, or recording it in policy.seed is decoration."""
    other = _build(corpus, now_ctx, seed=99)
    assert other["policy"]["seed"] == 99
    assert {row["bundle_id"] for row in other["selection"]} != {
        row["bundle_id"] for row in drawn["selection"]
    }
    assert other["record_sha256"] != drawn["record_sha256"]
    # A different draw over the same corpus is still the same corpus.
    assert other["corpus_sha256"] == drawn["corpus_sha256"]


def test_an_undeclared_repository_contributes_no_selection(drawn: dict[str, Any]) -> None:
    """Sections 16.9, 17.13: inventorying a document is not authority to annotate it.

    The undeclared repository is supplied with its full inventory and mining
    result, so exclusion has to come from the authority resolution rather than
    from the caller happening not to pass it.
    """
    assert {row["repository"] for row in drawn["selection"]} <= set(AUTHORISED)
    excluded = {row["repository"]: row["reason"] for row in drawn["authority"]["excluded_repositories"]}
    assert UNDECLARED in excluded
    assert "not permitted" in excluded[UNDECLARED]
    assert all(row["repository"] != UNDECLARED for row in drawn["selection"])


def test_every_authorised_repository_declares_the_required_uses(
    corpus: dict[str, Any], drawn: dict[str, Any]
) -> None:
    """The frame's own authority block has to match what the overlays say."""
    from ats.corpus.authority import AuthorityDeclaration

    for entry in drawn["authority"]["authorised_repositories"]:
        overlay = Path(corpus["overlay"]) / f"{entry['repository']}.json"
        declaration = AuthorityDeclaration.from_dict(
            json.loads(overlay.read_text()),
            repository=entry["repository"],
            location="pilot_overlay",
        )
        for use in fr.REQUIRED_USES:
            assert declaration.resolve(use).permitted, (entry["repository"], use)
        assert entry["declaration_location"] == "pilot_overlay"
        assert entry["declaration_sha256"]


def test_one_selection_per_leakage_component(drawn: dict[str, Any]) -> None:
    """Section 17.7: two members of one component can never be split, so only one is drawn."""
    groups = [row["split_group"] for row in drawn["selection"]]
    assert len(groups) == len(set(groups))
    hashes = [row["content_sha256"] for row in drawn["selection"]]
    assert len(hashes) == len(set(hashes))


def test_a_document_shared_by_two_repositories_is_one_component(
    corpus: dict[str, Any], now_ctx: Context
) -> None:
    """Repository is not a sufficient grouping key, and the closure knows it."""
    authority = fr.resolve_annotation_authority(corpus["rows"], corpus["overlay"])
    artifacts = [
        artifact
        for row in corpus["rows"]
        if row["repository"] in authority["declarations"]
        for artifact in row["inventory"]["artifacts"]
    ]
    domains = {row["repository"]: row["domain"] for row in corpus["rows"]}
    groups = fr.leakage_groups(now_ctx, artifacts, domains)
    shared = [a for a in artifacts if a["path"].endswith("-shared.md")]
    assert len(shared) == len(AUTHORISED)
    assert len({groups[a["artifact_id"]] for a in shared}) == 1


def test_a_stratum_that_cannot_be_filled_records_a_shortfall_reason(
    corpus: dict[str, Any], now_ctx: Context
) -> None:
    """ADR-0002 for sampling: an unfillable stratum says why, it does not look complete."""
    greedy = (
        fr.Stratum("surface_cue_hard_negative", 4, "cue in an exempting configuration"),
        fr.Stratum("revision_derived_candidate", 12, "a revision moved the text"),
        fr.Stratum("low_signal_random_control", 4, "documents no signal pointed at"),
        fr.Stratum("zero_candidate_rule_probe", 4, "a rule with no candidates, probed"),
        fr.Stratum("natural_rule_candidate", 6, "a declared vocabulary matched"),
    )
    result = _build(
        corpus,
        now_ctx,
        strata=greedy,
        target_size=sum(s.target for s in greedy),
        double_annotation_target=8,
    )
    short = next(r for r in result["strata"] if r["stratum"] == "revision_derived_candidate")
    assert short["selected"] < short["target"]
    assert "shortfall_reason" in short
    assert str(short["selected"]) in short["shortfall_reason"]
    # A short stratum is never topped up from another mechanism.
    assert all(
        row["candidate_source"].startswith(fr.REVISION_BASIS)
        for row in result["selection"]
        if row["stratum"] == "revision_derived_candidate"
    )
    filled = next(r for r in result["strata"] if r["stratum"] == "natural_rule_candidate")
    assert filled["selected"] == filled["target"]
    assert "shortfall_reason" not in filled


def test_the_repository_share_cap_binds_when_one_repository_could_fill_the_frame(
    corpus: dict[str, Any], now_ctx: Context
) -> None:
    """A cap applied afterwards is a cap that has already been exceeded.

    The lane-fair draw spreads across repositories on its own, so a balanced
    corpus never reaches the cap and so cannot test it. The pool here is one
    repository with more admissible components than the cap allows, which is the
    only shape where the cap is the thing doing the work.
    """
    pool = [
        fr.Pick(
            stratum="natural_rule_candidate",
            repository="alpha",
            artifact_id=f"ats-artifact-sha256:{index:064d}",
            span=(0, 10),
            candidate_source="signal:vague-evaluative-term",
            rule_ids=("ATS-SCOPE-001",),
            constraint_relevant=False,
            lane="vague-evaluative-term",
        )
        for index in range(30)
    ]
    groups = {pick.artifact_id: f"group-{index}" for index, pick in enumerate(pool)}
    strata = (fr.Stratum("natural_rule_candidate", 30, "one repository only"),)
    picks, report = fr.select(11, 30, {"natural_rule_candidate": pool}, groups, strata=strata)
    cap = int(30 * fr.MAX_REPOSITORY_SHARE)
    assert 0 < cap < 30
    assert len(picks) == cap
    assert "share cap" in report["natural_rule_candidate"]["shortfall_reason"]

    # And the whole-frame draw respects it too.
    result = _build(corpus, now_ctx)
    counts: dict[str, int] = {}
    for row in result["selection"]:
        counts[row["repository"]] = counts.get(row["repository"], 0) + 1
    assert counts, "the draw selected nothing"
    assert max(counts.values()) <= int(result["policy"]["target_size"] * fr.MAX_REPOSITORY_SHARE)


def test_a_corpus_with_no_declared_profile_reports_the_one_remaining_unsatisfiable(
    drawn: dict[str, Any],
) -> None:
    """The honest failure is computed, not transcribed from an artifact.

    The synthetic corpus declares no profile and carries only ``unknown`` review
    states, exactly as this synthetic fixture does. The profile constraint
    therefore has to come out unmet and unsatisfiable here as well. The review
    state row must not: its expectation was withdrawn, so it reports the
    measurement it made and records who withdrew what.
    """
    rows = {row["constraint"]: row for row in drawn["constraints"]}
    profile = rows["profile_hypothesis_coverage"]
    assert profile["satisfied"] is False
    assert profile["unsatisfiable"] is True
    assert profile["detail"]

    review = rows["review_state_coverage"]
    assert review["satisfied"] is True
    assert "unsatisfiable" not in review, "a withdrawn expectation cannot also be unsatisfiable"
    withdrawn = review["expectation_withdrawn"]
    assert {"expectation", "withdrawn_by", "reason", "reference"} <= set(withdrawn)
    assert "Caller policy" in withdrawn["withdrawn_by"]
    assert "ats.corpus.acceptance" in withdrawn["reference"]
    # Withdrawn, not hidden: the measurement that made it a finding is still here.
    assert "unknown=96" in review["observed"]
    assert "acceptance evidence remains separate" in review["detail"]

    assert {row["review_state"] for row in drawn["selection"]} == {"unknown"}
    assert not {p for row in drawn["selection"] for p in row["profile_hypotheses"]}
    # Every other constraint is met by this draw, so a blanket false would show.
    met = {row["constraint"] for row in drawn["constraints"] if row["satisfied"]}
    assert "exact_content_uniqueness" in met
    assert "repository_coverage" in met


def test_probe_and_control_selections_carry_no_detector_flag(drawn: dict[str, Any]) -> None:
    """No detector flagged them, so candidate_rule_ids is empty rather than borrowed."""
    for row in drawn["selection"]:
        if row["stratum"] in ("zero_candidate_rule_probe", "low_signal_random_control"):
            assert row["candidate_rule_ids"] == []
        if row["stratum"] == "zero_candidate_rule_probe":
            rule_id = row["candidate_source"].split(":")[1]
            assert rule_id in {p.rule_id for p in fr.PROBES}


def test_double_annotation_leads_the_array_and_spans_the_strata(drawn: dict[str, Any]) -> None:
    """The subset has to be spread, or per-mechanism agreement is unmeasurable."""
    selection = drawn["selection"]
    target = drawn["policy"]["double_annotation_target"]
    assert [row["double_annotated"] for row in selection[:target]] == [True] * target
    assert not any(row["double_annotated"] for row in selection[target:])
    marked = selection[:target]
    assert len({row["stratum"] for row in marked}) == len(SMALL_STRATA)
    assert len({row["repository"] for row in marked}) >= 4


def test_a_frame_whose_strata_do_not_add_up_is_refused(
    corpus: dict[str, Any], now_ctx: Context
) -> None:
    """An unaccounted-for remainder is a draw nobody described."""
    with pytest.raises(UsageError, match="do not add up|unaccounted"):
        _build(corpus, now_ctx, target_size=SMALL_TARGET + 1)


def test_an_authorised_repository_supplied_without_an_inventory_is_refused(
    corpus: dict[str, Any], now_ctx: Context
) -> None:
    """Silently omitting it would misreport the corpus the frame drew from."""
    rows = [
        {k: v for k, v in row.items() if k != "mined"}
        if row["repository"] == AUTHORISED[0]
        else row
        for row in corpus["rows"]
    ]
    with pytest.raises(UsageError, match="supplied no inventory or mining result"):
        _build(corpus, now_ctx, repositories=rows)


def test_a_mining_result_built_against_a_different_inventory_is_refused(
    corpus: dict[str, Any], now_ctx: Context
) -> None:
    """A candidate that addresses no inventoried artifact is a stale input, not an exclusion.

    ``artifact_id`` is a content address over the whole artifact record,
    including the authority resolution the inventory attaches, so
    re-inventorying against a changed authority overlay re-addresses every
    document and orphans a cached candidate set. Skipping the orphans quietly
    produced a frame that looked plausible, was 48 bundles short, breached the
    concentration cap it declares, and said nothing about why. A governed path
    exclusion still skips silently, because that exclusion is counted
    elsewhere -- the two cases have to stay distinguishable.
    """
    target = AUTHORISED[0]
    orphan = "ats-artifact-sha256:" + "f" * 64

    def orphaned(key: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in corpus["rows"]:
            if row["repository"] != target:
                rows.append(row)
                continue
            mined = json.loads(json.dumps(row["mined"]))
            assert mined[key], f"fixture supplied no {key} to orphan"
            mined[key][0]["artifact_id"] = orphan
            rows.append({**row, "mined": mined})
        return rows

    with pytest.raises(UsageError, match="not in the inventory being drawn from"):
        _build(corpus, now_ctx, repositories=orphaned("candidates"))
    with pytest.raises(UsageError, match="revision_candidates entry"):
        _build(corpus, now_ctx, repositories=orphaned("revision_candidates"))


def test_a_mining_cache_is_refused_at_load_before_a_candidate_is_read(
    corpus: dict[str, Any], now_ctx: Context
) -> None:
    """The diagnosis belongs at the cache, not at the 669th unresolvable candidate.

    ``_require_addressable`` is the backstop and reports one orphaned span;
    ``mine.require_inventory_binding`` runs before any candidate is read and
    names which input moved. Both are needed: a cache can carry a valid binding
    and still hold one bad row, and a cache can be wholly stale.
    """
    target = AUTHORISED[0]
    rows: list[dict[str, Any]] = []
    for row in corpus["rows"]:
        if row["repository"] != target:
            rows.append(row)
            continue
        mined = {k: v for k, v in row["mined"].items() if k != mine.INVENTORY_BINDING}
        rows.append({**row, "mined": mined})
    with pytest.raises(UsageError, match="records no inventory_binding"):
        _build(corpus, now_ctx, repositories=rows)

    # A binding for a different inventory is refused with the cause named.
    rows = []
    for row in corpus["rows"]:
        if row["repository"] != target:
            rows.append(row)
            continue
        mined = dict(row["mined"])
        mined[mine.INVENTORY_BINDING] = {
            **mined[mine.INVENTORY_BINDING],
            "inventory_sha256": "0" * 64,
        }
        rows.append({**row, "mined": mined})
    with pytest.raises(UsageError, match="built over a different inventory"):
        _build(corpus, now_ctx, repositories=rows)


def test_a_path_excluded_document_is_skipped_without_a_refusal(
    corpus: dict[str, Any], now_ctx: Context, drawn: dict[str, Any]
) -> None:
    """The governed case must stay quiet, or every declaration exclude glob would raise."""
    authority = fr.resolve_annotation_authority(
        corpus["rows"], corpus["overlay"], now=now_ctx.timestamp()
    )
    declaration = authority["declarations"][AUTHORISED[0]]
    assert declaration.exclude, "fixture declaration excludes nothing"
    assert not fr.path_permitted(declaration, "generated/report.md")
    assert fr.path_permitted(declaration, "docs/anything.md")
    # The draw that produced `drawn` ran over these same declarations and did not raise.
    assert drawn["selection"]


# -- blinding ---------------------------------------------------------------


def test_the_withheld_set_is_derived_from_the_schema_not_enumerated(
    now_ctx: Context, drawn: dict[str, Any]
) -> None:
    """Subtraction, so a field added to the schema is withheld until admitted."""
    _, schema = now_ctx.schemas.schema_for_version(fr.SCHEMA_VERSION)
    declared = set(schema["properties"]["selection"]["items"]["properties"])
    withheld = set(drawn["blinding"]["withheld_from_annotator"])
    assert withheld == declared - set(fr.ANNOTATOR_VISIBLE_FIELDS)
    assert withheld and not withheld & set(fr.ANNOTATOR_VISIBLE_FIELDS)
    # The mining prediction and the sampling mechanism are both on the list.
    assert {"stratum", "candidate_source", "candidate_rule_ids"} <= withheld


def test_the_annotator_view_cannot_carry_a_withheld_field(drawn: dict[str, Any]) -> None:
    """Sections 13.2, 16.5: a candidate is not a finding, and showing one anchors the judgment."""
    view = fr.annotator_view(drawn)
    withheld = drawn["blinding"]["withheld_from_annotator"]
    assert view["items"] and len(view["items"]) == len(drawn["selection"])
    for item in view["items"]:
        for field in withheld:
            assert field not in item
        assert set(item) <= set(fr.ANNOTATOR_VISIBLE_FIELDS)
    # No withheld *value* survives either: a stratum name or a candidate source
    # leaking through some other key would blind nothing.
    serialised = json.dumps(view["items"])
    for row in drawn["selection"]:
        assert row["stratum"] not in serialised
        assert row["candidate_source"] not in serialised
    # The design record goes too: the stratum table names the mechanisms.
    assert "strata" not in view
    assert "constraints" not in view


def test_a_selection_field_outside_the_allow_list_never_reaches_the_view(
    drawn: dict[str, Any],
) -> None:
    """The projection is an allow-list, so an unknown field is absent by construction."""
    poisoned = {
        **drawn,
        "selection": [
            {**row, "miner_prediction": "likely_violation"} for row in drawn["selection"]
        ],
    }
    view = fr.annotator_view(poisoned)
    assert "likely_violation" not in json.dumps(view)
    assert all("miner_prediction" not in item for item in view["items"])


def test_a_field_both_withheld_and_visible_is_refused(drawn: dict[str, Any]) -> None:
    """Resolving the contradiction silently would decide which of the two is the mistake."""
    contradictory = {
        **drawn,
        "blinding": {
            **drawn["blinding"],
            "withheld_from_annotator": [*drawn["blinding"]["withheld_from_annotator"], "repository"],
        },
    }
    with pytest.raises(UsageError, match="both withheld and allow-listed"):
        fr.annotator_view(contradictory)


def test_an_allow_list_naming_an_undeclared_field_is_refused(
    now_ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale allow-list would silently shrink the withheld set."""
    monkeypatch.setattr(
        fr, "ANNOTATOR_VISIBLE_FIELDS", (*fr.ANNOTATOR_VISIBLE_FIELDS, "not_a_schema_field")
    )
    with pytest.raises(UsageError, match="the schema does not declare"):
        fr.withheld_fields(now_ctx)


# -- mechanism classification ----------------------------------------------


def _block(text: str, kind: str = "paragraph") -> Block:
    return Block(kind=kind, start_line=1, end_line=1, start=0, end=len(text), text=text)


def test_long_dense_prose_needs_both_length_and_sentences() -> None:
    """One very long sentence is not the false-positive pressure this lane selects."""
    one_sentence = _block("word " * 200)
    assert len(one_sentence.text) >= fr.LONG_PROSE_CHARS
    assert not fr.long_dense_prose(one_sentence)
    three_short = _block("One. Two. Three.")
    assert not fr.long_dense_prose(three_short)
    assert fr.long_dense_prose(_block(("A sentence of some length here. " * 30)))
    assert not fr.long_dense_prose(_block("A sentence. " * 100, kind="code_block"))


def test_quoted_material_outranks_the_other_configurations() -> None:
    """Section 5.6 is the strongest claim available, and the rarest configuration."""
    quoted = {
        "block": {"kind": "block_quote"},
        "signal": {"signal_id": "relative-time-expression"},
    }
    long_anchored = _block("As of 2026-03-14, currently. " * 40, kind="block_quote")
    assert fr.hard_negative_class(quoted, long_anchored) == "HN-6_quoted_material"
    plain = {"block": {"kind": "paragraph"}, "signal": {"signal_id": "relative-time-expression"}}
    assert fr.hard_negative_class(plain, _block("currently, as of 2026-03-14.")) == (
        "HN-9_anchored_relative_time"
    )
    assert fr.hard_negative_class(plain, _block("currently, with no anchor at all.")) is None


def test_a_probe_with_no_surface_returns_nothing_rather_than_the_opening_block(
    now_ctx: Context,
) -> None:
    """A silent fallback would report probe coverage for a surface the document lacks."""
    from ats.corpus.context import document_blocks

    text = "# Title\n\nnothing here matches a probe surface at all.\n"
    blocks = document_blocks(text, media_type="text/markdown")
    artifact: dict[str, Any] = {"extensions": {}}
    for basis in ("glossary_shaped_heading", "revision_predecessor_available"):
        probe = next(p for p in fr.PROBES if p.basis == basis)
        assert probe_none(now_ctx, probe, artifact, text, blocks)
    contrary = next(p for p in fr.PROBES if p.basis == "contrary_evidence_language")
    assert probe_none(now_ctx, contrary, artifact, text, blocks)


def probe_none(ctx: Context, probe: fr.Probe, artifact: dict, text: str, blocks) -> bool:
    return fr.probe_span(ctx, probe, artifact=artifact, text=text, blocks=blocks) is None


def test_an_unimplemented_probe_basis_raises_rather_than_selecting_nothing(
    now_ctx: Context,
) -> None:
    """A basis with no implementation is a probe nobody wrote, not a probe that found nothing."""
    from ats.corpus.context import document_blocks

    text = "# Title\n\nSome prose.\n"
    with pytest.raises(UsageError, match="has no implementation"):
        fr.probe_span(
            now_ctx,
            fr.Probe("ATS-TERM-001", "not_a_basis", "fixture"),
            artifact={},
            text=text,
            blocks=document_blocks(text, media_type="text/markdown"),
        )

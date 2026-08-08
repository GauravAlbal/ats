"""Deterministic candidate extraction, and the three inferences it refuses.

Defends spec Section 17.4 (never infer conformance from merge, violation from
deletion, or quality from a later edit), Section 13.2 (applicability belongs to
a detector, not a phrase match), and the term-list discipline: every vocabulary
comes from the force lexicon, a list enumerated verbatim in the specification,
or the artifact's own glossary.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Final

import pytest

from ats.context import Context
from ats.corpus import inventory as inv
from ats.corpus import mine
from ats.corpus.authority import AuthorityDeclaration
from ats.errors import UsageError
from ats.spec_package import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
from generate_corpus_fixtures import build_sample_repo  # noqa: E402

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


@pytest.fixture(scope="module")
def mined(ctx: Context, tmp_path_factory):
    repo = build_sample_repo(tmp_path_factory.mktemp("git") / "sample-repo")
    inventory = inv.build_inventory(ctx, repo)
    return mine.mine_candidates(ctx, inventory)


def test_no_candidate_carries_a_label(mined) -> None:
    """Spec 13.2, 16.5: a matched phrase is a candidate, never a finding or a label."""
    assert mined["candidates"]
    for candidate in mined["candidates"]:
        assert candidate["label"] is None
        assert candidate["candidate_only"] is True
        assert "does not establish" in candidate["note"]
        assert candidate["requires_context_bundle"] is True


def test_every_candidate_names_its_triggering_signal(mined) -> None:
    """A candidate an annotator cannot trace back to a vocabulary is unreviewable."""
    for candidate in mined["candidates"]:
        signal = candidate["signal"]
        assert signal["signal_id"]
        assert signal["rule_ids"]
        assert signal["vocabulary_source"]
        assert signal["spec_ref"].startswith("ATS-1 ")
        assert candidate["matched_phrase"]


def test_signal_vocabularies_have_only_three_permitted_origins(ctx: Context, mined) -> None:
    """A detector may match the lexicon, a spec-enumerated list, or the IR glossary."""
    permitted = {"lexicon", "spec_enumeration", "artifact_glossary"}
    origins = {s["origin"] for s in mined["signals_available"]}
    assert origins <= permitted
    assert origins & {"lexicon", "spec_enumeration"} == {"lexicon", "spec_enumeration"}


def test_spec_lists_are_the_repository_s_single_copy(ctx: Context) -> None:
    """Sections 10.11, 10.20, and 10.21 are declared once and reused, never restated."""
    from ats.output.render_checks import EMPTY_INTENSIFIERS, VAGUE_EVALUATIVE
    from ats.rules.deterministic.time_rules import RELATIVE_TIME_TERMS

    signals = {s.signal_id: s for s in mine.build_signals(ctx)}
    assert signals["relative-time-expression"].phrases == tuple(RELATIVE_TIME_TERMS)
    assert signals["empty-intensifier"].phrases == tuple(EMPTY_INTENSIFIERS)
    assert signals["vague-evaluative-term"].phrases == tuple(VAGUE_EVALUATIVE)
    # The Section 10.11 list, quoted from the specification.
    assert set(RELATIVE_TIME_TERMS) == {
        "today",
        "currently",
        "recently",
        "soon",
        "later",
        "next",
        "the latest",
    }


def test_lexicon_signals_come_from_the_lexicon(ctx: Context) -> None:
    """The force lexicon is the only source of WEP, deontic, and confidence vocabulary."""
    signals = {s.signal_id: s for s in mine.build_signals(ctx)}
    assert set(signals["wep-canonical-phrase"].phrases) == set(ctx.lexicon.wep_phrases)
    assert set(signals["wep-noncanonical-alias"].phrases) == set(ctx.lexicon.wep_aliases)
    assert set(signals["deontic-noncanonical"].phrases) == set(ctx.lexicon.deontic_noncanonical)
    assert set(signals["assessment-confidence-level"].phrases) == set(ctx.lexicon.confidence_levels)


def test_glossary_signals_come_from_the_declared_glossary(ctx: Context) -> None:
    """Spec 10.2: a deprecated alias is whatever the artifact's glossary declares."""
    glossary = [
        {
            "concept_id": "acceptance-kernel",
            "canonical_term": "acceptance kernel",
            "definition": "The closed state-transition component.",
            "scope": "Arq",
            "deprecated_aliases": ["gate engine"],
        }
    ]
    signals = {s.signal_id: s for s in mine.build_signals(ctx, glossary=glossary)}
    alias = signals["glossary-deprecated-alias"]
    assert alias.phrases == ("gate engine",)
    assert alias.origin == "artifact_glossary"
    # Without a glossary the signal does not exist; it is never invented.
    assert "glossary-deprecated-alias" not in {s.signal_id for s in mine.build_signals(ctx)}


def test_deontic_surfaces_match_case_sensitively(ctx: Context) -> None:
    """Spec 1.3: the keywords are normative only in uppercase."""
    signal = {s.signal_id: s for s in mine.build_signals(ctx)}["deontic-surface"]
    assert mine.find_matches("The verifier MUST reject the receipt.", signal)
    assert not mine.find_matches("The verifier must eventually get around to it.", signal)


def test_code_blocks_do_not_generate_candidates(mined) -> None:
    """Spec 5.6: code and quoted material may be exempt, so a cue there is not a candidate."""
    assert all(c["block"]["kind"] != "code_block" for c in mined["candidates"])


def test_merge_is_never_conformance(mined) -> None:
    """Spec 17.4 refusal one."""
    label, reason = mine.conformance_from_review_state("accepted")
    assert label is None
    assert "17.4" in reason
    accepted = [c for c in mined["candidates"] if c["review_state"] == "accepted"]
    assert accepted, "the fixture repository declares an accepted document"
    for candidate in accepted:
        assert candidate["label"] is None
        assert "nothing to do with ATS-1 conformance" in candidate["review_state_note"]


def test_deletion_is_never_a_violation() -> None:
    """Spec 17.4 refusal two."""
    label, reason = mine.violation_from_deletion("The qualification that was removed.")
    assert label is None
    assert "Deletion records that an edit happened" in reason


def test_a_later_edit_is_never_a_quality_verdict(mined) -> None:
    """Spec 17.4 refusal three."""
    label, reason = mine.quality_from_later_edit({"availability": "present"})
    assert label is None
    assert "not treated as a verdict" in reason
    for candidate in mined["candidates"]:
        assert "not treated as a verdict" in candidate["later_edit_note"]


def test_every_candidate_carries_all_three_refusals(mined) -> None:
    """An annotator reading one candidate sees every inference the pipeline declined."""
    for candidate in mined["candidates"]:
        assert [r["refusal_id"] for r in candidate["refusals"]] == list(mine.REFUSAL_IDS)
    assert len(mine.MINING_REFUSALS) == 3


def test_mining_is_deterministic(ctx: Context, mined, tmp_path) -> None:
    """Spec 16.2: identical canonical inputs produce identical results."""
    repo = build_sample_repo(tmp_path / "again")
    again = mine.mine_candidates(ctx, inv.build_inventory(ctx, repo))
    assert [c["matched_phrase"] for c in again["candidates"]] == [
        c["matched_phrase"] for c in mined["candidates"]
    ]
    assert [c["span"] for c in again["candidates"]] == [c["span"] for c in mined["candidates"]]


def test_signals_used_is_a_subset_of_signals_available(mined) -> None:
    """The report distinguishes what fired from what was searched for."""
    used = {s["signal_id"] for s in mined["signals_used"]}
    available = {s["signal_id"] for s in mined["signals_available"]}
    assert used
    assert used < available
    assert used == {c["signal"]["signal_id"] for c in mined["candidates"]}


# -- cache binding ----------------------------------------------------------
#
# A mining result is expensive, so it gets cached. Every candidate addresses its
# artifact by ``artifact_id``, and ``records.address`` hashes the whole artifact
# record -- extensions, including the authority block -- so editing an authority
# overlay re-addresses every document it covers and orphans the cache. That
# happened: a draw silently discarded 668 candidates, three whole repositories,
# and reported a smaller corpus instead of an error.
#
# The overlay edit is the hard half. A repository revision that moves is visible
# in ``revision``; an overlay edit moves no source byte and no revision, so the
# only thing that can betray it is the declaration digest recorded beside the
# artifacts. These tests hold the three answers that digest can give apart.

#: The repository name every fixture below builds under, so a refusal can be
#: checked for naming the repository it is refusing.
SAMPLE_REPO: Final[str] = "sample-repo"


def _overlay(repository: str, revision: str) -> dict[str, Any]:
    """An operator overlay authorising mining of one synthetic repository.

    Written out here rather than shared with ``test_corpus_frame.py``: the point
    of these tests is what happens when the overlay *bytes* change, so the bytes
    have to be under the test's control rather than imported from a fixture
    another module is free to reshape.
    """
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


def _write_overlay(directory: Path, repository: str, data: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{repository}.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def _digest(overlay: Path, repository: str) -> str:
    """The live declaration digest, read the one way the pipeline reads it."""
    declaration = AuthorityDeclaration.from_file(
        overlay, repository=repository, location="pilot_overlay"
    )
    assert declaration.source_sha256 is not None
    return declaration.source_sha256


@pytest.fixture(scope="module")
def bound(ctx: Context, tmp_path_factory):
    """An inventory and the mining result built over exactly it.

    Paired deliberately. The module's ``mined`` fixture cannot serve here: an
    artifact record carries its repository name, so an inventory built at a
    different temporary path is a genuinely different inventory and the binding
    would report drift that is real rather than the drift under test.
    """
    repo = build_sample_repo(tmp_path_factory.mktemp("bound") / SAMPLE_REPO)
    inventory = inv.build_inventory(ctx, repo)
    return {"inventory": inventory, "mined": mine.mine_candidates(ctx, inventory)}


@pytest.fixture(scope="module")
def declared(ctx: Context, tmp_path_factory):
    """The same pairing, under an authority overlay that actually declares something.

    ``bound`` covers a repository nobody has declared anything about, where the
    honest digest is no digest. This one covers the case the pilot is in, and it
    is the only one where a declaration change is observable at all.
    """
    root = tmp_path_factory.mktemp("declared")
    repo = build_sample_repo(root / SAMPLE_REPO)
    # The sample repository ships the pre-authority ``.ats/corpus.json``, which
    # declares a repository group and no per-use authority. A repository's own
    # declaration outranks an operator overlay by design, so leaving it in place
    # would leave this fixture undeclared and silently identical to ``bound``.
    (repo / ".ats" / "corpus.json").unlink()
    overlay_dir = root / "authority"
    overlay = _write_overlay(
        overlay_dir, repo.name, _overlay(repo.name, inv.head_revision(repo))
    )
    inventory = inv.build_inventory(ctx, repo, authority_overlay=overlay_dir)
    return {
        "root": root,
        "overlay": overlay,
        "inventory": inventory,
        "mined": mine.mine_candidates(ctx, inventory),
        "digest": _digest(overlay, repo.name),
    }


def test_a_mining_result_records_the_inventory_it_was_built_over(bound) -> None:
    """A cache that cannot say what it was built over cannot be trusted later."""
    inventory = bound["inventory"]
    binding = bound["mined"][mine.INVENTORY_BINDING]
    assert binding["revision"] == inventory["revision"]
    assert binding["artifact_count"] == len(inventory["artifacts"])
    assert binding["inventory_sha256"]
    # Nothing declares this repository, so there are no declaration bytes to
    # hash. That is recorded as an absence with a reason, never guessed at, and
    # it is still not a state a cache can be read as fresh in.
    assert inventory[inv.AUTHORITY_DECLARATION]["availability"] == "not_found"
    assert binding["declaration_sha256"] is None


def test_a_mining_result_read_against_a_rebuilt_inventory_is_refused(bound) -> None:
    """Re-addressed artifacts mean no candidate resolves, so the read has to stop."""
    inventory = bound["inventory"]
    rebuilt = {
        **inventory,
        "artifacts": [
            {**artifact, "artifact_id": "ats-artifact-sha256:" + "0" * 64}
            if index == 0
            else artifact
            for index, artifact in enumerate(inventory["artifacts"])
        ],
    }
    with pytest.raises(UsageError, match="built over a different inventory"):
        mine.require_inventory_binding(
            bound["mined"], rebuilt, where=SAMPLE_REPO, declaration_sha256=None
        )


def test_a_mining_result_with_no_binding_is_refused(bound) -> None:
    """ADR-0002: a cache whose provenance is unstated is unverified, not verified."""
    legacy = {k: v for k, v in bound["mined"].items() if k != mine.INVENTORY_BINDING}
    with pytest.raises(UsageError, match="records no inventory_binding"):
        mine.require_inventory_binding(
            legacy, bound["inventory"], where=SAMPLE_REPO, declaration_sha256=None
        )


# -- the declaration a cache was built under ---------------------------------


def test_the_declaration_digest_reaches_the_cache_from_the_one_computation(
    declared,
) -> None:
    """The digest is read where the declaration is read, not recomputed downstream.

    Both halves matter. Equality with ``AuthorityDeclaration.from_file`` is the
    contract -- that is the single implementation, and the sampling frame's
    authority rows carry its output -- and equality with a plain sha256 of the
    file proves nothing normalises the bytes on the way, which is what would
    silently re-address a frozen frame.
    """
    binding = declared["mined"][mine.INVENTORY_BINDING]
    assert declared["inventory"][inv.AUTHORITY_DECLARATION] == {
        "availability": "present",
        "location": "pilot_overlay",
        "sha256": declared["digest"],
    }
    assert binding["declaration_sha256"] == declared["digest"]
    assert (
        binding["declaration_sha256"]
        == hashlib.sha256(declared["overlay"].read_bytes()).hexdigest()
    )


def test_a_cache_read_under_the_same_declaration_is_accepted(declared) -> None:
    """The governed case has to stay quiet, or the refusals below prove nothing."""
    mine.require_inventory_binding(
        declared["mined"],
        declared["inventory"],
        where=SAMPLE_REPO,
        declaration_sha256=declared["digest"],
    )


def test_a_cache_built_under_a_different_declaration_is_refused(declared) -> None:
    """The incident, reproduced: the overlay moved and the artifacts did not.

    The inventory is the one the cache was mined over, unchanged, so the
    artifact digest agrees and every earlier guard passes. Only the declaration
    differs, and that alone has to stop the read -- an overlay edit changes what
    was in scope, and re-addresses every document it covers, without moving a
    source byte or a revision.
    """
    edited = _overlay(SAMPLE_REPO, declared["inventory"]["revision"])
    edited["content"]["exclude"] = ["generated/*", "docs/*"]
    path = _write_overlay(declared["root"] / "authority-edited", SAMPLE_REPO, edited)
    live = _digest(path, SAMPLE_REPO)
    assert live != declared["digest"]

    with pytest.raises(UsageError) as raised:
        mine.require_inventory_binding(
            declared["mined"],
            declared["inventory"],
            where=SAMPLE_REPO,
            declaration_sha256=live,
        )
    message = str(raised.value)
    assert SAMPLE_REPO in message
    assert "different authority declaration" in message
    assert declared["digest"][:12] in message and live[:12] in message
    assert f"Re-mine {SAMPLE_REPO}" in message


def test_a_legacy_cache_with_no_recorded_declaration_is_not_read_as_fresh(
    declared,
) -> None:
    """Absence of the field is not evidence the declaration has not moved.

    A cache written before the field existed is exactly as likely to be stale as
    one written under a declaration that has since changed; the difference is
    only that it cannot say. Refusing is the safer answer and costs a re-mine,
    which is what the pilot pays anyway once a frame is found defective.
    """
    binding = {
        key: value
        for key, value in declared["mined"][mine.INVENTORY_BINDING].items()
        if key != "declaration_sha256"
    }
    legacy = {**declared["mined"], mine.INVENTORY_BINDING: binding}

    with pytest.raises(UsageError) as raised:
        mine.require_inventory_binding(
            legacy,
            declared["inventory"],
            where=SAMPLE_REPO,
            declaration_sha256=declared["digest"],
        )
    message = str(raised.value)
    assert SAMPLE_REPO in message
    assert "unknown is not fresh" in message
    assert f"Re-mine {SAMPLE_REPO}" in message
    # Unknown is not mismatch. A reader that cannot tell them apart cannot tell
    # "the overlay moved" from "nobody recorded which overlay this was".
    assert "different authority declaration" not in message


def test_a_reader_that_cannot_state_a_live_declaration_is_refused(declared) -> None:
    """A skipped check reads exactly like a passed one, so it is not offered."""
    with pytest.raises(UsageError, match="unknown is not fresh"):
        mine.require_inventory_binding(
            declared["mined"],
            declared["inventory"],
            where=SAMPLE_REPO,
            declaration_sha256=None,
        )


def test_the_three_declaration_states_stay_three(declared) -> None:
    """Match, mismatch and cannot-determine are separate answers (ADR-0002)."""
    other = "b" * 64
    digest = declared["digest"]
    assert mine.declaration_state(digest, digest)[0] == mine.DECLARATION_MATCH
    assert mine.declaration_state(digest, other)[0] == mine.DECLARATION_MISMATCH
    # Three ways to reach unknown, none of which is either of the above: the
    # cache cannot say, the reader cannot say, and neither can.
    assert mine.declaration_state(None, other)[0] == mine.DECLARATION_UNKNOWN
    assert mine.declaration_state(digest, None)[0] == mine.DECLARATION_UNKNOWN
    assert mine.declaration_state(None, None)[0] == mine.DECLARATION_UNKNOWN
    assert (
        len({mine.DECLARATION_MATCH, mine.DECLARATION_MISMATCH, mine.DECLARATION_UNKNOWN})
        == 3
    )
    # Each unknown says which side could not answer; a single reason for all
    # three would leave an operator unable to act on any of them.
    reasons = {
        mine.declaration_state(None, other)[1],
        mine.declaration_state(digest, None)[1],
        mine.declaration_state(None, None)[1],
    }
    assert len(reasons) == 3


def test_mining_refuses_a_declaration_that_contradicts_the_inventory(
    ctx: Context, declared
) -> None:
    """Two candidate digests, one of which did not address these artifacts.

    The supplied argument exists for inventories written before they recorded
    the field. Letting it override an inventory that *did* record one would let
    a caller stamp a freshness claim onto candidates extracted under a different
    declaration, which is worse than recording nothing.
    """
    with pytest.raises(UsageError, match="the inventory it is mining was built under"):
        mine.mine_candidates(ctx, declared["inventory"], declaration_sha256="a" * 64)


def test_a_supplied_declaration_is_recorded_when_the_inventory_predates_the_field(
    ctx: Context, declared
) -> None:
    """A supplied declaration is recorded when an inventory predates the field."""
    legacy_inventory = {
        key: value
        for key, value in declared["inventory"].items()
        if key != inv.AUTHORITY_DECLARATION
    }
    result = mine.mine_candidates(
        ctx, legacy_inventory, declaration_sha256=declared["digest"]
    )
    assert result[mine.INVENTORY_BINDING]["declaration_sha256"] == declared["digest"]
    mine.require_inventory_binding(
        result,
        legacy_inventory,
        where=SAMPLE_REPO,
        declaration_sha256=declared["digest"],
    )
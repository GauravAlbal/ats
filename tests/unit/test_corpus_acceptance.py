"""Acceptance is a decision an authority made, never something Git computed.

The census answer for the whole corpus is ``unknown``, and the value of that
answer depends entirely on it being unreachable by accident. These tests are
therefore mostly about what does *not* happen: a merge does not accept, a
deletion does not reject, a revert does not adjudicate, and a state cannot be
represented at all without the artifact that decided it.

The promotion path is exercised too, on synthetic authoritative artifacts,
because a refusal that also refuses real evidence is a bug rather than a
principle.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import Any

import pytest

from ats.context import Context
from ats.corpus import acceptance as acc
from ats.corpus import authorship as auth
from ats.corpus import inventory as inv
from ats.errors import UsageError
from ats.output.receipt import SELF_IDENTITIES
from ats.spec_package import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
from generate_corpus_fixtures import _git as write_git  # noqa: E402
from generate_corpus_fixtures import build_sample_repo  # noqa: E402

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)

#: The independently redistributable synthetic fixture used by public tests.
OVERLAY = REPO_ROOT / "corpus" / "authority"
REAL_REPOSITORY = "sample-repo"

PROSE = """# Seating policy

Guests MUST be seated at the table named on their invitation. A guest who
arrives without an invitation SHOULD be seated at the overflow table, and the
coordinator MUST be told before the meal service begins.
"""

REVISED_PROSE = """# Seating policy

Guests MUST be seated at the table named on their invitation. A guest who
arrives without an invitation MUST be seated at the overflow table, and the
coordinator MUST be told before the meal service begins.
"""

#: The default branch's competing edit to the same sentence, so the merge below
#: has to resolve a conflict and therefore appears in the path's own history.
HEAD_TABLE_PROSE = """# Seating policy

Guests MUST be seated at the table named on their invitation. A guest who
arrives without an invitation SHOULD be seated at the head table, and the
coordinator MUST be told before the meal service begins.
"""

#: What the merge commit itself wrote: neither parent's text.
RESOLVED_PROSE = """# Seating policy

Guests MUST be seated at the table named on their invitation. A guest who
arrives without an invitation MUST be seated at the head table, and the
coordinator MUST be told before the meal service begins.
"""


def _receipt(**overrides: Any) -> dict[str, Any]:
    """A synthetic authoritative artifact: complete, citable, externally owned."""
    record = {
        acc.STATE_KEY: "accepted",
        acc.LOCATOR_KEY: "arq://receipt/7f3c",
        acc.AUTHORITY_KEY: "Reviewer One <one@ats.invalid>",
        "detail": "adjudicated against ATS-1 1.0.0-draft.1",
        "decided_at": "2026-01-20T12:00:00+00:00",
    }
    record.update(overrides)
    return record


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


@pytest.fixture(scope="module")
def real_inventory(ctx: Context, tmp_path_factory):
    """The inventory of the independently redistributable synthetic fixture."""
    repo = build_sample_repo(
        tmp_path_factory.mktemp("git") / REAL_REPOSITORY,
        include_review_evidence=False,
    )
    return inv.build_inventory(ctx, repo, authority_overlay=OVERLAY)


@pytest.fixture(scope="module")
def merge_inventory(ctx: Context, tmp_path_factory):
    """A real repository whose current content was written by a merge commit."""
    repo = tmp_path_factory.mktemp("git") / "merge-repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    write_git(repo, "init", "--quiet")
    (docs / "seating.md").write_text(PROSE, encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "-m", "Add the seating policy\n")
    default = write_git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()

    write_git(repo, "checkout", "--quiet", "-b", "revise")
    (docs / "seating.md").write_text(REVISED_PROSE, encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(
        repo,
        "commit",
        "--quiet",
        "-m",
        "Tighten the overflow obligation\n\nReviewed-by: Reviewer One <one@ats.invalid>\n",
    )

    write_git(repo, "checkout", "--quiet", default)
    (docs / "seating.md").write_text(HEAD_TABLE_PROSE, encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "-m", "Send uninvited guests to the head table\n")
    with pytest.raises(RuntimeError, match="git merge"):
        write_git(repo, "merge", "--no-ff", "revise", "-m", "Merge branch 'revise'\n")
    assert (repo / ".git" / "MERGE_HEAD").is_file()
    (docs / "seating.md").write_text(RESOLVED_PROSE, encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(
        repo,
        "commit",
        "--quiet",
        "-m",
        "Merge branch 'revise'\n\nReviewed-by: Reviewer One <one@ats.invalid>\n",
    )
    return inv.build_inventory(ctx, repo)

@pytest.fixture(scope="module")
def revert_inventory(ctx: Context, tmp_path_factory):
    """A real repository carrying Git's own ``This reverts commit`` marker."""
    repo = tmp_path_factory.mktemp("git") / "revert-repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    write_git(repo, "init", "--quiet")
    (docs / "seating.md").write_text(PROSE, encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "-m", "Add the seating policy\n")
    (docs / "seating.md").write_text(REVISED_PROSE, encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "-m", "Tighten the overflow obligation\n")
    write_git(repo, "revert", "--quiet", "--no-edit", "HEAD")
    return inv.build_inventory(ctx, repo)


@pytest.fixture(scope="module")
def declared_inventory(ctx: Context, tmp_path_factory):
    """The sample fixture repository, whose copy declares ``ATS-Review-State``."""
    return inv.build_inventory(
        ctx, build_sample_repo(tmp_path_factory.mktemp("git") / "sample-repo")
    )


def _by_path(inventory) -> dict[str, dict]:
    return {a["path"]: a for a in inventory["artifacts"]}


def _binding(**overrides: Any) -> auth.ProspectiveBinding:
    fields: dict[str, Any] = {
        "producing_skill": "ats-output-authoring",
        "model": {"name": "fixture-writer", "version": "1.0.0"},
        "prompt_identity": "prompt:sha256:2b1f",
        "source_ir": "ir:sha256:9ac4",
        "human_edits": auth.BINDING_NO_HUMAN_EDITS,
        "adjudicator": auth.BINDING_PENDING_ADJUDICATION,
        "acceptance_receipt": auth.BINDING_PENDING_ACCEPTANCE,
    }
    fields.update(overrides)
    return auth.ProspectiveBinding(**fields)


# -- the default -------------------------------------------------------------


def test_unknown_is_the_default_with_nothing_supplied() -> None:
    """Absence of an authoritative artifact is unknown, not implicit acceptance."""
    reading = acc.read_acceptance(locator="git:abc")
    assert reading.state == acc.UNDETERMINED
    assert reading.as_record()["acceptance_evidence"] == []
    assert not reading.decided


def test_every_evidence_kind_is_named_in_the_search_even_when_it_answers_nothing() -> None:
    """ADR-0002: an unavailable answer names what was consulted, never a bare null."""
    joined = " | ".join(acc.read_acceptance(locator="git:abc").searched)
    for label in ("arq receipts", "decision records", "review dispositions", "review state"):
        assert label in joined, label
    for signal in acc.TOPOLOGICAL_SIGNALS:
        assert signal in joined, signal


def test_a_state_off_unknown_cannot_be_constructed_without_evidence() -> None:
    """The invariant is structural: an unevidenced decision must not be representable."""
    for state in sorted(acc.DECLARABLE_STATES):
        with pytest.raises(UsageError, match="no evidence"):
            acc.Acceptance(state=state, evidence=(), searched=("looked everywhere",))


def test_a_reading_must_say_what_it_searched() -> None:
    """A bare result cannot distinguish 'searched and not found' from 'never looked'."""
    with pytest.raises(UsageError, match="what it looked for"):
        acc.Acceptance(state=acc.UNDETERMINED, evidence=(), searched=())


def test_uncited_evidence_is_refused() -> None:
    """A decision nobody can check is an assertion, not evidence."""
    with pytest.raises(UsageError, match="locator"):
        acc.AcceptanceEvidence(
            kind="arq_receipt", state="accepted", locator="", authority="a human", detail="x"
        )


def test_evidence_with_no_deciding_authority_is_refused() -> None:
    """Acceptance is somebody's decision; a disposition nobody owns is an opinion."""
    with pytest.raises(UsageError, match="no deciding authority"):
        acc.AcceptanceEvidence(
            kind="arq_receipt", state="accepted", locator="arq://r/1", authority="  ", detail="x"
        )


@pytest.mark.parametrize("identity", sorted(i for i in SELF_IDENTITIES if i))
def test_this_implementation_cannot_be_its_own_acceptance_authority(identity: str) -> None:
    """Spec 13.7: a component must not adjudicate its own findings."""
    with pytest.raises(UsageError, match="must be external"):
        acc.AcceptanceEvidence(
            kind="arq_receipt",
            state="accepted",
            locator="arq://r/1",
            authority=identity,
            detail="x",
        )


def test_rejected_is_a_decision_and_unknown_is_its_absence() -> None:
    """The two must stay distinct: a refusal somebody made, and nobody having ruled."""
    rejected = acc.read_acceptance(
        locator="git:abc", decision_records=[_receipt(acceptance_state="rejected")]
    )
    silent = acc.read_acceptance(locator="git:abc")
    assert rejected.state == "rejected" and rejected.decided
    assert silent.state == acc.UNDETERMINED and not silent.decided
    assert rejected.state != silent.state


# -- over a real authorised repository ---------------------------------------


def test_every_document_in_a_real_authorised_repository_is_unknown(real_inventory) -> None:
    """Observation K, recomputed rather than transcribed from the census report."""
    artifacts = real_inventory["artifacts"]
    assert artifacts, "the authorised repository yielded no documents to check"
    for artifact in artifacts:
        reading = acc.artifact_acceptance(artifact)
        record = reading.as_record()
        assert record["acceptance_state"] == "unknown", artifact["path"]
        assert record["acceptance_evidence"] == [], artifact["path"]
        assert record["searched"], artifact["path"]
        # The searched list has to name what was looked for, not merely exist.
        joined = " | ".join(record["searched"])
        assert "arq receipts" in joined and "decision records" in joined
        assert "review dispositions" in joined and "review state declarations" in joined


def test_synthetic_fixture_carries_public_redistribution_authority(real_inventory) -> None:
    """The checked-in fixture must not inherit an internal or unknown default."""
    for artifact in real_inventory["artifacts"]:
        assert artifact["use_authority"] == "external_training_permitted"
        assert artifact["handling_policy"] == "public"

def test_a_real_repository_reports_its_topology_and_promotes_on_none_of_it(
    real_inventory,
) -> None:
    """Presence at the pinned revision is observed, cited, and refused as evidence."""
    observed = [
        signal
        for artifact in real_inventory["artifacts"]
        for signal in acc.artifact_acceptance(artifact).topology
    ]
    assert observed, "no topological signal was observed at all, so nothing was refused"
    for signal in observed:
        assert signal["establishes_acceptance"] is False
        assert signal["why_not"]
        assert signal["signal"] in acc.TOPOLOGICAL_SIGNALS


# -- topology cannot promote --------------------------------------------------


def test_merge_topology_alone_cannot_promote_the_state(merge_inventory) -> None:
    """Reviewed on a branch, merged with a merge commit, untouched since: still unknown."""
    artifact = _by_path(merge_inventory)["docs/seating.md"]
    history = artifact["extensions"]["x-ats-repo-git"]["history"]
    # The fixture must actually carry the topology, or this asserts nothing.
    assert any("Merge branch" in c["subject"] for c in history["commits"])
    assert artifact["acceptance_evidence"]["availability"] == "present"
    assert artifact["acceptance_evidence"]["reviewers"]

    reading = acc.artifact_acceptance(artifact)
    assert reading.state == acc.UNDETERMINED
    assert reading.as_record()["acceptance_evidence"] == []
    reviewed = [s for s in reading.topology if s["signal"] == "reviewed_by_trailer"]
    assert reviewed and "does not record what they decided" in reviewed[0]["why_not"]


def test_a_reviewed_by_trailer_says_somebody_looked_not_what_they_decided(
    merge_inventory,
) -> None:
    """The inventory collected the reviewer; acceptance still needs the decision."""
    reading = acc.artifact_acceptance(_by_path(merge_inventory)["docs/seating.md"])
    assert reading.state == acc.UNDETERMINED
    assert any("review state declarations" in note for note in reading.searched)


def test_deletion_alone_cannot_mark_rejection() -> None:
    """Text is deleted because it moved or lost its subject; that is not a refusal."""
    reading = acc.read_acceptance(
        locator="git:abc", topology={"deletion": "removed in 4f21ab", "merge_topology": True}
    )
    assert reading.state == acc.UNDETERMINED
    assert reading.state != "rejected"
    deletion = [s for s in reading.topology if s["signal"] == "deletion"]
    assert deletion and "not a rejection" in deletion[0]["why_not"]


def test_a_revert_is_detected_from_git_and_is_not_an_acceptance_state(
    revert_inventory,
) -> None:
    """A revert stays detected -- it is a topological fact -- and stays out of the state."""
    artifact = _by_path(revert_inventory)["docs/seating.md"]
    # Detection is preserved: the inventory still reads Git's own revert line.
    assert artifact["review_state"] == "reverted"
    assert "revert" in artifact["extensions"]["x-ats-repo-git"]["review_state_basis"]

    reading = acc.artifact_acceptance(artifact)
    assert reading.state == acc.UNDETERMINED
    assert reading.as_record()["acceptance_evidence"] == []
    marker = [s for s in reading.topology if s["signal"] == "revert_marker"]
    assert marker and "not a reviewer's judgment" in marker[0]["why_not"]


@pytest.mark.parametrize("signal", acc.TOPOLOGICAL_SIGNALS)
def test_no_named_topological_signal_moves_the_state(signal: str) -> None:
    """Each one is present, observed, cited, and refused. Named so it is testable."""
    reading = acc.read_acceptance(locator="git:abc", topology={signal: "observed"})
    assert reading.state == acc.UNDETERMINED
    assert [s["signal"] for s in reading.topology] == [signal]
    assert reading.topology[0]["establishes_acceptance"] is False


def test_every_topological_signal_at_once_still_promotes_nothing() -> None:
    """The heuristics do not become evidence by being numerous."""
    reading = acc.read_acceptance(
        locator="git:abc", topology={s: "observed" for s in acc.TOPOLOGICAL_SIGNALS}
    )
    assert reading.state == acc.UNDETERMINED
    assert len(reading.topology) == len(acc.TOPOLOGICAL_SIGNALS)


def test_an_unenumerated_topological_signal_is_refused() -> None:
    """A signal with no written-down refusal is one nobody has thought about."""
    with pytest.raises(UsageError, match="named topological signal"):
        acc.read_acceptance(locator="git:abc", topology={"ci_passed": True})


def test_a_candidate_receipt_is_named_as_not_an_acceptance() -> None:
    """Spec 14.11: this pipeline's own receipt is deliberately short of acceptance."""
    assert "13.7" in acc.TOPOLOGY_REFUSALS["candidate_receipt"]
    reading = acc.read_acceptance(locator="git:abc", topology={"candidate_receipt": "cr:1"})
    assert reading.state == acc.UNDETERMINED


# -- an authoritative artifact promotes --------------------------------------


@pytest.mark.parametrize(
    "kwarg,kind",
    [
        ("arq_receipts", "arq_receipt"),
        ("decision_records", "decision_record"),
        ("review_dispositions", "review_disposition"),
        ("review_state_declarations", "review_state_declaration"),
    ],
)
def test_each_authoritative_artifact_promotes_and_is_recorded(kwarg: str, kind: str) -> None:
    """All four kinds are equally admissible; each records where to check it."""
    reading = acc.read_acceptance(locator="git:abc", **{kwarg: [_receipt()]})
    assert reading.state == "accepted"
    assert reading.decided
    evidence = reading.as_record()["acceptance_evidence"]
    assert len(evidence) == 1
    assert evidence[0] == {
        "kind": kind,
        "acceptance_state": "accepted",
        "locator": "arq://receipt/7f3c",
        "authority": "Reviewer One <one@ats.invalid>",
        "detail": "adjudicated against ATS-1 1.0.0-draft.1",
        "decided_at": "2026-01-20T12:00:00+00:00",
    }


@pytest.mark.parametrize("state", sorted(acc.DECLARABLE_STATES))
def test_an_authoritative_artifact_can_assert_any_declarable_state(state: str) -> None:
    reading = acc.read_acceptance(
        locator="git:abc", arq_receipts=[_receipt(acceptance_state=state)]
    )
    assert reading.state == state


def test_a_declaration_without_a_locator_is_refused() -> None:
    """An uncitable decision must fail loudly rather than move the state quietly."""
    with pytest.raises(UsageError, match="uncitable"):
        acc.read_acceptance(locator="git:abc", arq_receipts=[_receipt(locator="")])


def test_a_declaration_without_an_authority_is_refused() -> None:
    with pytest.raises(UsageError, match="no deciding authority"):
        acc.read_acceptance(locator="git:abc", arq_receipts=[_receipt(authority="")])


def test_a_state_outside_the_vocabulary_is_refused() -> None:
    """A producer writing 'merged' gets an error, not an unknown that looks like absence."""
    with pytest.raises(UsageError, match="merged"):
        acc.read_acceptance(locator="git:abc", arq_receipts=[_receipt(acceptance_state="merged")])


def test_an_artifact_declaring_unknown_contributes_no_evidence() -> None:
    """Declaring 'unknown' is declining to decide, and is recorded as such."""
    reading = acc.read_acceptance(
        locator="git:abc", arq_receipts=[_receipt(acceptance_state="unknown")]
    )
    assert reading.state == acc.UNDETERMINED
    assert not reading.evidence
    assert any("1 searched, none declares" in note for note in reading.searched)


def test_a_declared_review_state_trailer_promotes_and_cites_the_committer(
    declared_inventory,
) -> None:
    """Somebody wrote ATS-Review-State on purpose; that is a declaration, not topology."""
    reading = acc.artifact_acceptance(_by_path(declared_inventory)["docs/requirements-copy.md"])
    assert reading.state == "accepted"
    assert [e.kind for e in reading.evidence] == ["review_state_declaration"]
    assert "trailer" in reading.evidence[0].detail
    assert reading.evidence[0].authority


def test_a_sibling_document_without_the_trailer_stays_unknown(declared_inventory) -> None:
    """A declaration is about the commit that carries it, never about the repository."""
    assert acc.artifact_acceptance(_by_path(declared_inventory)["docs/requirements.md"]).state == (
        acc.UNDETERMINED
    )


# -- folding several dispositions --------------------------------------------


def test_combine_never_invents_a_state() -> None:
    assert acc.combine([]) == acc.UNDETERMINED
    assert acc.combine(["unknown"]) == acc.UNDETERMINED
    assert acc.combine(["accepted"]) == "accepted"
    assert acc.combine(["rejected"]) == "rejected"


def test_supersession_wins_over_the_acceptance_it_supersedes() -> None:
    """That is what supersession means; reporting 'accepted' would be a stale answer."""
    assert acc.combine(["accepted", "superseded"]) == "superseded"


def test_two_authorities_deciding_differently_stay_unresolved() -> None:
    """Section 17.9 retains disagreement; folding it to either answer would delete it."""
    reading = acc.read_acceptance(
        locator="git:abc",
        arq_receipts=[_receipt()],
        decision_records=[_receipt(acceptance_state="rejected", locator="adr://12")],
    )
    assert reading.state == acc.UNDETERMINED
    assert reading.decided, "the disagreement is retained even though no state stands"
    assert {e.state for e in reading.evidence} == {"accepted", "rejected"}


# -- the prospective bridge ---------------------------------------------------


def test_a_produced_artifact_awaiting_adjudication_is_unknown() -> None:
    """Producing something is not accepting it, whoever produced it."""
    reading = acc.producer_binding_acceptance(_binding(), locator="artifact:1")
    assert reading.state == acc.UNDETERMINED
    assert reading.as_record()["acceptance_evidence"] == []
    assert any("adjudicator=" in note for note in reading.searched)


def test_a_bound_receipt_and_adjudicator_promote_the_produced_artifact() -> None:
    """The two directions meet through a written record, never through a default."""
    binding = _binding(
        adjudicator="Reviewer One <one@ats.invalid>", acceptance_receipt="arq://receipt/aa11"
    )
    reading = acc.producer_binding_acceptance(binding, locator="artifact:1")
    assert reading.state == "accepted"
    evidence = reading.as_record()["acceptance_evidence"][0]
    assert evidence["kind"] == "arq_receipt"
    assert evidence["locator"] == "arq://receipt/aa11"
    assert evidence["authority"] == "Reviewer One <one@ats.invalid>"


def test_an_adjudicated_but_unaccepted_binding_stays_unknown() -> None:
    """An adjudicator who has not ruled yet has not accepted anything."""
    binding = _binding(adjudicator="Reviewer One <one@ats.invalid>")
    assert acc.producer_binding_acceptance(binding, locator="artifact:1").state == (
        acc.UNDETERMINED
    )


def test_the_producer_cannot_bind_itself_as_the_accepting_authority() -> None:
    """Spec 13.7 again, at the point the producer writes the binding."""
    with pytest.raises(UsageError, match="must be external"):
        _binding(adjudicator="ats", acceptance_receipt="arq://receipt/aa11")

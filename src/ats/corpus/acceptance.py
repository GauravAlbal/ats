"""Acceptance of a corpus document: a decision an authority made, never a topology.

Git is an excellent witness and a hopeless adjudicator. It can establish that a
document was present at a revision, that a later commit modified or deleted it,
that one commit is an ancestor of another, and that a merge joined two lines of
history. Every one of those is a fact about a graph. Not one of them is a
decision anybody made about the text.

The public implementation does not infer acceptance from repository topology.
Callers supply acceptance evidence explicitly; absent evidence remains
``unknown`` and is reported as searched or unavailable rather than promoted.
Git can witness presence, deletion, ancestry, and merge structure, but none of
those facts is an authority decision about the text.

So acceptance here has four values — ``accepted``, ``rejected``, ``superseded``,
``unknown`` — and ``unknown`` is both the default and the only value reachable
without an authoritative artifact. ``rejected`` is a refusal an authority made;
``unknown`` is the absence of a sufficient authority decision, and the two are
kept apart for the same reason ``deny`` and ``unknown`` are kept apart in
:mod:`ats.corpus.authority`. :class:`Acceptance` enforces this structurally: a
non-``unknown`` state with no evidence cannot be constructed at all. That is the
same invariant, in the same shape, that :class:`ats.corpus.authorship.Authorship`
enforces for authorship; it is deliberately not a second mechanism.

The signals in :data:`TOPOLOGICAL_SIGNALS` are the ones Git *can* answer and that
a plausible implementation would promote on. They are read — presence, deletion,
merge structure and the rest are real context an annotator needs — and recorded
on :attr:`Acceptance.topology`, structurally apart from
:attr:`Acceptance.evidence`, where they cannot move the state. ``reverted`` is
the sharpest case: Git's own ``This reverts commit`` line makes it detectable,
one document in the census carries it, and it stays detected. A revert says a
change was undone. It does not say a reviewer rejected the prose, and this module
will not convert the one into the other.

Section 14.11 puts final authority for semantic acceptance with an authorised
human or an explicitly governed external acceptance system, and Section 13.7
forbids a component from adjudicating its own findings. Both apply here:
:data:`EVIDENCE_KINDS` admits only artifacts an external authority produced, and
an evidence record whose deciding authority names this implementation is refused
outright, reusing :data:`ats.output.receipt.SELF_IDENTITIES` rather than
restating the list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence

from ..errors import UsageError
from ..output.receipt import SELF_IDENTITIES
from .authorship import ProspectiveBinding

#: The acceptance vocabulary. ``rejected`` and ``unknown`` are distinct states,
#: not two shades of "not accepted": the first is a decision an authority made
#: against the text, the second is the absence of any sufficient decision. Spec
#: Section 17.4 keeps ``superseded`` apart from ``rejected`` too — superseded
#: text was accepted and later replaced; rejected text never cleared review.
ACCEPTANCE_STATES: Final[tuple[str, ...]] = ("accepted", "rejected", "superseded", "unknown")

#: The default, and the only state reachable without an authoritative artifact.
UNDETERMINED: Final[str] = "unknown"

#: States an authoritative artifact may assert. ``unknown`` is absent
#: deliberately: an artifact declaring ``unknown`` has decided nothing, and is
#: recorded as searched-and-undetermined rather than as evidence.
DECLARABLE_STATES: Final[frozenset[str]] = frozenset({"accepted", "rejected", "superseded"})

#: The artifact kinds that may move acceptance off ``unknown``. Each is a record
#: an identified authority deliberately produced to state a disposition; none of
#: them can be reconstructed from repository history.
#:
#: ``arq_receipt``
#:     A conformance receipt from the Arq adjudication path the pipeline ends in
#:     (``NORTH_STAR.md``, "human or Arq adjudication"). A *candidate* receipt is
#:     not one of these — see :data:`TOPOLOGICAL_SIGNALS`.
#: ``decision_record``
#:     An explicit decision record — an ADR, a governance minute, a signed
#:     approval — that names the document and states what was decided.
#: ``review_disposition``
#:     A structured review outcome from a review system: an approval, a change
#:     request, a rejection, carrying the reviewer and the decision.
#: ``review_state_declaration``
#:     The ``ATS-Review-State`` declaration :mod:`ats.corpus.inventory` already
#:     reads out of a commit trailer or a git note. It is admitted because
#:     somebody wrote it on purpose, and for no other reason: it is a declaration
#:     that happens to live in Git, not something Git computed. Observation K
#:     calls this the producer-side mechanism — something producers must adopt,
#:     not something miners can extract.
EVIDENCE_KINDS: Final[tuple[str, ...]] = (
    "arq_receipt",
    "decision_record",
    "review_disposition",
    "review_state_declaration",
)

#: Facts Git or the producing system can establish that MUST NOT move acceptance
#: off ``unknown``, named so the prohibition can be tested rather than assumed.
#: Every one of them is routinely read as acceptance by somebody and establishes
#: it for nobody. They are observed and reported: suppressing them would lose
#: context Section 17.4 says to retain, and promoting on them would invent
#: decisions.
TOPOLOGICAL_SIGNALS: Final[tuple[str, ...]] = (
    "merge_topology",
    "default_branch_presence",
    "survival_duration",
    "deletion",
    "revert_marker",
    "later_edit_absence",
    "reviewed_by_trailer",
    "candidate_receipt",
)

#: Why each topological signal is not acceptance, so the refusal travels with the
#: observation instead of living only in this module's docstring.
TOPOLOGY_REFUSALS: Final[Mapping[str, str]] = {
    "merge_topology": (
        "a merge joined two lines of history; repositories merge text to unblock work, to keep "
        "a branch alive, and by automation, none of which is a decision about the prose "
        "(spec 17.4)"
    ),
    "default_branch_presence": (
        "the document exists at the pinned revision; being committed on a default branch is not "
        "acceptance (spec 17.4)"
    ),
    "survival_duration": (
        "the text has gone unedited for a long time; nobody deciding is not somebody accepting"
    ),
    "deletion": (
        "the document was deleted; text is deleted because it became redundant, moved, or lost "
        "its subject, so a deletion is not a rejection (ATS_CORPUS_PROTOCOL_V0 CP-38.2)"
    ),
    "revert_marker": (
        "git's 'This reverts commit' line says a change was undone; undoing a change is a "
        "topological fact, not a reviewer's judgment about the prose"
    ),
    "later_edit_absence": (
        "no later commit touches the path; the absence of a subsequent edit is the absence of "
        "evidence, not evidence of approval (ADR-0002)"
    ),
    "reviewed_by_trailer": (
        "a Reviewed-By trailer records that somebody looked; it does not record what they "
        "decided, and acceptance needs the decision"
    ),
    "candidate_receipt": (
        "this pipeline emits a candidate receipt, which spec 14.11 explicitly leaves short of "
        "acceptance; a component accepting its own output is what spec 13.7 forbids"
    ),
}

#: The keys an authoritative artifact must carry for this module to read a
#: disposition out of it. A record missing any of them is not a decision: an
#: uncitable disposition cannot be checked, and a disposition with no deciding
#: authority is an opinion.
STATE_KEY: Final[str] = "acceptance_state"
LOCATOR_KEY: Final[str] = "locator"
AUTHORITY_KEY: Final[str] = "authority"

#: Stated once so it is quotable: what promotes, and what never does.
ACCEPTANCE_POLICY: Final[str] = (
    "acceptance is a decision an external authority recorded in an authoritative artifact; "
    "repository topology establishes presence, deletion, ancestry, and merge structure, and "
    "establishes acceptance of nothing"
)


def _check_authority(authority: str, *, where: str) -> str:
    """An acceptance authority must exist and must not be this implementation.

    Spec Section 13.7 forbids a component from becoming the authoritative
    adjudicator for its own finding, and Section 14.11 puts semantic acceptance
    with an authorised human or a governed external system.
    :data:`ats.output.receipt.SELF_IDENTITIES` already names the identities that
    mean "us"; reusing it keeps one list rather than two that drift apart.
    """
    named = authority.strip()
    if not named:
        raise UsageError(
            f"{where} names no deciding authority; a disposition nobody owns is an opinion and "
            f"cannot move acceptance off {UNDETERMINED!r}"
        )
    if named.casefold() in SELF_IDENTITIES:
        raise UsageError(
            f"{where} names {authority!r} as the deciding authority, which is this "
            "implementation; acceptance authority must be external (spec 13.7, 14.11)"
        )
    return named


@dataclass(frozen=True, slots=True)
class AcceptanceEvidence:
    """One authoritative artifact recording a disposition, and where to check it."""

    kind: str
    state: str
    locator: str
    authority: str
    detail: str
    decided_at: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in EVIDENCE_KINDS:
            raise UsageError(
                f"{self.kind!r} is not an acceptance evidence kind; expected one of "
                f"{', '.join(EVIDENCE_KINDS)}"
            )
        if self.state not in DECLARABLE_STATES:
            raise UsageError(
                f"acceptance evidence declares {self.state!r}; an authoritative artifact must "
                f"assert one of {', '.join(sorted(DECLARABLE_STATES))}"
            )
        if not self.locator:
            raise UsageError(
                "acceptance evidence carries no locator; an uncitable decision is not evidence "
                f"and cannot move acceptance off {UNDETERMINED!r}"
            )
        _check_authority(self.authority, where=f"the {self.kind} at {self.locator}")

    def as_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "kind": self.kind,
            "acceptance_state": self.state,
            "locator": self.locator,
            "authority": self.authority,
            "detail": self.detail,
        }
        if self.decided_at:
            record["decided_at"] = self.decided_at
        return record


@dataclass(frozen=True, slots=True)
class Acceptance:
    """An acceptance reading: the state, its evidence, what was searched, what Git said.

    ``topology`` is a peer field rather than a source, and that placement is the
    design: the merge structure, the revert marker and the deletion are all
    reported, and none of them reaches :attr:`state`. The invariants live in
    ``__post_init__`` rather than in prose, because "a decision must be impossible
    to invent by accident" is only true if the accident raises.
    """

    state: str
    evidence: tuple[AcceptanceEvidence, ...]
    searched: tuple[str, ...]
    topology: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.state not in ACCEPTANCE_STATES:
            raise UsageError(
                f"{self.state!r} is not an acceptance state; expected one of "
                f"{', '.join(ACCEPTANCE_STATES)}"
            )
        if self.state != UNDETERMINED and not self.evidence:
            raise UsageError(
                f"acceptance {self.state!r} was asserted with no evidence; only "
                f"{UNDETERMINED!r} is reachable without an authoritative artifact. "
                f"{ACCEPTANCE_POLICY}"
            )
        if not self.searched:
            raise UsageError(
                "an acceptance reading must record what it looked for; a bare result gives a "
                "reader no way to tell 'searched and not found' from 'never searched'"
            )

    @property
    def decided(self) -> bool:
        """Whether any authority recorded a disposition for this document."""
        return bool(self.evidence)

    def as_record(self) -> dict[str, Any]:
        """The serialisable form, carrying both lists a reader is entitled to."""
        return {
            "acceptance_state": self.state,
            "acceptance_evidence": [e.as_record() for e in self.evidence],
            "searched": list(self.searched),
            "topology_observed": [dict(t) for t in self.topology],
            "policy": ACCEPTANCE_POLICY,
        }


def combine(states: Sequence[str]) -> str:
    """Fold declared dispositions into one.

    Supersession wins over the acceptance it supersedes, because that is what
    supersession means. Any other disagreement is not folded: two authorities
    deciding differently about the same document is a fact the corpus keeps, and
    collapsing it to either one would delete the disagreement Section 17.9
    requires be retained. It reports ``unknown`` — no single sufficient decision
    stands — with both artifacts still in the evidence list, which is why
    :attr:`Acceptance.decided` is a separate question from the state.
    """
    declared = {s for s in states if s in DECLARABLE_STATES}
    if not declared:
        return UNDETERMINED
    if declared <= {"accepted", "superseded"} and "superseded" in declared:
        return "superseded"
    if len(declared) == 1:
        return next(iter(declared))
    return UNDETERMINED


# -- retrospective: what an authority recorded about an existing document ----


def declared_evidence(
    records: Sequence[Mapping[str, Any]], *, kind: str, label: str
) -> tuple[list[AcceptanceEvidence], str]:
    """Dispositions declared by authoritative artifacts of one kind.

    Each record must carry an explicit ``acceptance_state``, a ``locator``, and an
    ``authority``. A record carrying no state is not a disposition, and the search
    note says so. A record declaring a state this vocabulary does not have raises:
    a producer writing ``acceptance_state: merged`` deserves an error rather than
    an ``unknown`` indistinguishable from an honest absence.
    """
    if kind not in EVIDENCE_KINDS:
        raise UsageError(f"{kind!r} is not an acceptance evidence kind")
    found: list[AcceptanceEvidence] = []
    for index, record in enumerate(records):
        raw = record.get(STATE_KEY)
        if raw is None:
            continue
        state = str(raw).strip().lower()
        if state == UNDETERMINED:
            continue
        if state not in DECLARABLE_STATES:
            raise UsageError(
                f"{label} record {index} declares {STATE_KEY}={raw!r}; expected one of "
                f"{', '.join(sorted(DECLARABLE_STATES))} or {UNDETERMINED!r}"
            )
        locator = str(record.get(LOCATOR_KEY) or "")
        if not locator:
            raise UsageError(
                f"{label} record {index} declares {STATE_KEY}={state!r} with no {LOCATOR_KEY!r}; "
                f"an uncitable decision cannot move acceptance off {UNDETERMINED!r}"
            )
        authority = _check_authority(
            str(record.get(AUTHORITY_KEY) or ""), where=f"{label} record {index} at {locator}"
        )
        decided_at = record.get("decided_at")
        found.append(
            AcceptanceEvidence(
                kind=kind,
                state=state,
                locator=locator,
                authority=authority,
                detail=str(
                    record.get("detail") or f"{authority} recorded {state} in {label} {locator}"
                ),
                decided_at=str(decided_at) if decided_at else None,
            )
        )
    if not records:
        return found, f"{label}: none supplied"
    if not found:
        return found, f"{label}: {len(records)} searched, none declares {STATE_KEY}"
    return found, f"{label}: {len(found)} of {len(records)} declare {STATE_KEY}"


def topology_observations(
    signals: Mapping[str, Any], *, locator: str
) -> tuple[list[dict[str, Any]], str]:
    """Record the Git facts that were observed, each with why it does not promote.

    ``signals`` maps a name from :data:`TOPOLOGICAL_SIGNALS` to whatever the
    caller observed — a boolean, a sha, a count. A name outside the enumeration
    raises rather than being recorded quietly: an unenumerated signal is one whose
    refusal nobody has written down, and silence is how a signal gets promoted.
    """
    observed: list[dict[str, Any]] = []
    for name in sorted(signals):
        if name not in TOPOLOGY_REFUSALS:
            raise UsageError(
                f"{name!r} is not a named topological signal; expected one of "
                f"{', '.join(TOPOLOGICAL_SIGNALS)}"
            )
        value = signals[name]
        if value is None or value is False or value == "":
            continue
        observed.append(
            {
                "signal": name,
                "observed": value if isinstance(value, (str, int)) else str(value),
                "locator": locator,
                "establishes_acceptance": False,
                "why_not": TOPOLOGY_REFUSALS[name],
            }
        )
    summary = (
        ", ".join(f"{o['signal']}={o['observed']}" for o in observed)
        if observed
        else "no named signal observed"
    )
    return observed, (
        f"repository topology of {locator}: {summary}; none of "
        f"{', '.join(TOPOLOGICAL_SIGNALS)} may promote acceptance"
    )


def read_acceptance(
    *,
    locator: str,
    arq_receipts: Sequence[Mapping[str, Any]] = (),
    decision_records: Sequence[Mapping[str, Any]] = (),
    review_dispositions: Sequence[Mapping[str, Any]] = (),
    review_state_declarations: Sequence[Mapping[str, Any]] = (),
    topology: Mapping[str, Any] | None = None,
) -> Acceptance:
    """Read the acceptance an authority already recorded. Nothing is derived.

    Every one of the four evidence kinds is searched and reported, whether or not
    it answers, so ``unknown`` arrives with the list of places that were looked at
    instead of a bare null (ADR-0002). Topology is observed alongside and reported
    as topology; there is no branch in this function by which it reaches the state.
    """
    evidence: list[AcceptanceEvidence] = []
    searched: list[str] = []

    for records, kind, label in (
        (arq_receipts, "arq_receipt", "arq receipts"),
        (decision_records, "decision_record", "decision records"),
        (review_dispositions, "review_disposition", "review dispositions"),
        (review_state_declarations, "review_state_declaration", "review state declarations"),
    ):
        found, note = declared_evidence(records, kind=kind, label=label)
        searched.append(note)
        evidence.extend(found)

    observed, note = topology_observations(topology or {}, locator=locator)
    searched.append(note)
    searched.append("not promoted, by policy: " + ", ".join(TOPOLOGICAL_SIGNALS))

    return Acceptance(
        state=combine([e.state for e in evidence]),
        evidence=tuple(evidence),
        searched=tuple(searched),
        topology=tuple(observed),
    )


def _locator(artifact: Mapping[str, Any]) -> str:
    return (
        f"{artifact.get('repository', '?')}@{artifact.get('revision', '?')}"
        f":{artifact.get('path', '?')}"
    )


def _declaration_from_artifact(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The ``ATS-Review-State`` declaration the inventory already resolved, if any.

    ``review_state`` on a ``SourceArtifactV1`` is a mixed field: the inventory
    fills it from an explicit trailer or note *and* from Git's revert marker
    (``ats.corpus.inventory._review_state``). Only the first is a declaration, and
    ``review_state_basis`` is what tells them apart, so the basis is read rather
    than trusted from the value. ``reverted`` never reaches here — it is not in
    :data:`DECLARABLE_STATES` — and is routed to topology instead.
    """
    state = str(artifact.get("review_state") or UNDETERMINED).strip().lower()
    if state not in DECLARABLE_STATES:
        return []
    git = (artifact.get("extensions") or {}).get("x-ats-repo-git") or {}
    basis = str(git.get("review_state_basis") or "")
    if "declared by" not in basis:
        return []
    provenance = artifact.get("author_provenance") or {}
    return [
        {
            STATE_KEY: state,
            LOCATOR_KEY: _locator(artifact),
            AUTHORITY_KEY: str(provenance.get("author") or ""),
            "detail": basis,
            "decided_at": provenance.get("authored_at"),
        }
    ]


def artifact_acceptance(
    artifact: Mapping[str, Any],
    *,
    arq_receipts: Sequence[Mapping[str, Any]] = (),
    decision_records: Sequence[Mapping[str, Any]] = (),
    review_dispositions: Sequence[Mapping[str, Any]] = (),
) -> Acceptance:
    """The acceptance reading for one inventoried ``SourceArtifactV1``.

    The topology this artifact carries is handed to the reader *as* topology: the
    revert marker, the fact that the document is present at the pinned revision,
    the absence of any later edit, and any ``Reviewed-By`` trailer the inventory
    collected. External authoritative artifacts are supplied by the caller,
    because by construction none of them lives in the repository being mined —
    which is why every document of every authorised repository reads ``unknown``.
    """
    git = (artifact.get("extensions") or {}).get("x-ats-repo-git") or {}
    basis = str(git.get("review_state_basis") or "")
    later = (git.get("later_edits") or {}).get("availability")
    evidence_object = artifact.get("acceptance_evidence") or {}

    topology: dict[str, Any] = {
        "default_branch_presence": f"present at {str(artifact.get('revision', ''))[:12]}",
        "revert_marker": (
            basis if artifact.get("review_state") == "reverted" and "revert" in basis else False
        ),
        "later_edit_absence": later == "not_found",
        "reviewed_by_trailer": bool(evidence_object.get("reviewers")),
    }
    return read_acceptance(
        locator=_locator(artifact),
        arq_receipts=arq_receipts,
        decision_records=decision_records,
        review_dispositions=review_dispositions,
        review_state_declarations=_declaration_from_artifact(artifact),
        topology=topology,
    )


# -- prospective: what this system binds to an artifact it produces ----------


def producer_binding_acceptance(binding: ProspectiveBinding, *, locator: str) -> Acceptance:
    """Acceptance for an artifact this system produced, read off its own binding.

    The forward half of the authorship policy binds an ``acceptance_receipt`` and
    an ``adjudicator`` (:class:`ats.corpus.authorship.ProspectiveBinding`). When
    both are bound the receipt is an ``arq_receipt`` and promotes; while either is
    pending the artifact is ``unknown``, because a produced artifact awaiting
    adjudication is not an accepted one. This is the only place the two directions
    meet, and they meet through a written record rather than a default: the
    binding had to name a real receipt and a real external adjudicator, and
    :func:`_check_authority` refuses the latter if it names this implementation.
    """
    receipts: list[Mapping[str, Any]] = []
    if binding.adjudicated and binding.accepted:
        receipts.append(
            {
                STATE_KEY: "accepted",
                LOCATOR_KEY: binding.acceptance_receipt,
                AUTHORITY_KEY: binding.adjudicator,
                "detail": (
                    f"{binding.adjudicator} accepted the artifact produced by "
                    f"{binding.producing_skill}; receipt {binding.acceptance_receipt}"
                ),
            }
        )
    reading = read_acceptance(locator=locator, arq_receipts=receipts, topology={})
    return Acceptance(
        state=reading.state,
        evidence=reading.evidence,
        searched=(
            f"producer binding for {locator}: adjudicator={binding.adjudicator!r}, "
            f"acceptance_receipt={binding.acceptance_receipt!r}",
            *reading.searched,
        ),
        topology=reading.topology,
    )

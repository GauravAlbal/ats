"""Deterministic candidate extraction from inventoried source documents.

A candidate is a span whose surface carries a signal one of the thirty rules
cares about. It is **not** a finding and it is **not** a label. Spec Section
13.2 reserves applicability to a detector, and Section 17.9 reserves labels to
adjudicated judgments; a phrase match establishes only that a human or detector
should look.

Every signal comes from one of three places, and each candidate records which:

* ``lexicons/ats_force_lexicon_v1.yaml`` — the only source of WEP terms and
  aliases, non-probability terms, confidence levels, evidential and causal
  vocabularies, and deontic surfaces;
* a list enumerated verbatim in ``ATS-1_SPEC.md`` — Sections 10.11, 10.20, and
  10.21. These are reused from the modules that already declare them, so the
  repository holds exactly one copy of each specification list;
* the declared glossary of the artifact under inspection.

Section 17.4 also names three inferences the pipeline refuses to make. They are
implemented as functions that return no label, in :data:`MINING_REFUSALS`.

A second basis reads the *history* rather than the surface. Where a revision
moved a span on an axis Section 11.3.1 protects — deontic force, likelihood,
quantifier scope, temporal order — the change itself is the reason to look.
Reconstructed history is trustworthy enough to establish that the text moved;
it is not trustworthy enough to say what the movement means, so every such
candidate records ``normative_interpretation`` as
:data:`NORMATIVE_INTERPRETATION` and there is no code path that records
anything else. Its vocabulary obeys the same three-source rule, plus the enums
the normative schemas declare (ADR-0006).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

from ..canonical import content_hash, sha256_hex
from ..errors import UsageError
from ..output.render_checks import EMPTY_INTENSIFIERS, VAGUE_EVALUATIVE
from ..rules.deterministic.time_rules import RELATIVE_TIME_TERMS
from . import inventory as inv
from . import records as rec

#: The sentence every candidate carries. Spec Sections 13.2 and 16.5: the
#: presence of a cue is not the presence of a violation, and the absence of a
#: cue is not conformance.
CANDIDATE_ONLY_NOTE: Final[str] = (
    "A matched phrase generates a candidate for review only. It does not establish that the "
    "rule applies, that the artifact violates it, or that the artifact conforms. Only an "
    "adjudicated judgment under the named rule can decide that (spec 13.2, 16.5, 17.9)."
)

#: Section 17.4 refuses to read a label out of repository workflow state.
@dataclass(frozen=True, slots=True)
class Refusal:
    refusal_id: str
    question: str
    answer: str
    spec_ref: str


MINING_REFUSALS: Final[tuple[Refusal, ...]] = (
    Refusal(
        refusal_id="no-conformance-from-merge",
        question="Does a merged or accepted commit show the text conforms?",
        answer=(
            "No. Acceptance outcomes are preserved as a separate dimension, not converted into "
            "a conformance label. A repository merges text for many reasons that have nothing "
            "to do with ATS-1 conformance."
        ),
        spec_ref="ATS-1 17.4",
    ),
    Refusal(
        refusal_id="no-violation-from-deletion",
        question="Does deleted text show the deleted text violated a rule?",
        answer=(
            "No. Deletion records that an edit happened. Scope changes, duplication, and "
            "reorganisation delete conforming text just as readily as nonconforming text."
        ),
        spec_ref="ATS-1 17.4",
    ),
    Refusal(
        refusal_id="no-quality-from-later-edit",
        question="Does a later edit show the earlier text was of lower quality?",
        answer=(
            "No. A subsequent edit is retained as context so an annotator can see it, not "
            "treated as a verdict on the version it replaced."
        ),
        spec_ref="ATS-1 17.4",
    ),
)

REFUSAL_IDS: Final[tuple[str, ...]] = tuple(r.refusal_id for r in MINING_REFUSALS)


def conformance_from_review_state(review_state: str) -> tuple[None, str]:
    """Never returns a label. Merge state is context, not conformance evidence."""
    refusal = MINING_REFUSALS[0]
    return None, f"{refusal.answer} (review_state={review_state!r}, {refusal.spec_ref})"


def violation_from_deletion(deleted_text: str) -> tuple[None, str]:
    """Never returns a label. Deleted text is not thereby a violation."""
    refusal = MINING_REFUSALS[1]
    return None, f"{refusal.answer} ({len(deleted_text)} characters deleted, {refusal.spec_ref})"


def quality_from_later_edit(later_edit: Mapping[str, Any]) -> tuple[None, str]:
    """Never returns a label. A later edit is context, not a quality judgment."""
    refusal = MINING_REFUSALS[2]
    return None, (
        f"{refusal.answer} (later_edit availability="
        f"{later_edit.get('availability', 'not_searched')!r}, {refusal.spec_ref})"
    )


# -- signals ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Signal:
    """One vocabulary a candidate can be triggered by."""

    signal_id: str
    phrases: tuple[str, ...]
    rule_ids: tuple[str, ...]
    vocabulary_source: str
    spec_ref: str
    #: ``lexicon``, ``spec_enumeration``, or ``artifact_glossary``.
    origin: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "rule_ids": list(self.rule_ids),
            "vocabulary_source": self.vocabulary_source,
            "spec_ref": self.spec_ref,
            "origin": self.origin,
            "phrase_count": len(self.phrases),
        }


def build_signals(ctx: Any, *, glossary: Sequence[Mapping[str, Any]] = ()) -> list[Signal]:
    """Assemble the signal set from the lexicon, the spec lists, and the glossary."""
    lexicon = ctx.lexicon
    signals: list[Signal] = [
        Signal(
            signal_id="wep-noncanonical-alias",
            phrases=tuple(sorted(lexicon.wep_aliases)),
            rule_ids=("ATS-EPI-003",),
            vocabulary_source="likelihood.terms[].input_aliases in ats_force_lexicon_v1.yaml",
            spec_ref="ATS-1 8.3",
            origin="lexicon",
        ),
        Signal(
            signal_id="wep-canonical-phrase",
            phrases=tuple(sorted(lexicon.wep_phrases)),
            rule_ids=("ATS-EPI-001", "ATS-EPI-002"),
            vocabulary_source="likelihood.terms[].phrase in ats_force_lexicon_v1.yaml",
            spec_ref="ATS-1 8.2, 8.4",
            origin="lexicon",
        ),
        Signal(
            signal_id="non-probability-term",
            phrases=tuple(lexicon.non_probability_terms),
            rule_ids=("ATS-EPI-007",),
            vocabulary_source="likelihood.non_probability_terms in ats_force_lexicon_v1.yaml",
            spec_ref="ATS-1 8.7",
            origin="lexicon",
        ),
        Signal(
            signal_id="assessment-confidence-level",
            phrases=tuple(lexicon.confidence_levels),
            rule_ids=("ATS-EPI-004", "ATS-EPI-005"),
            vocabulary_source="assessment_confidence.terms[].id in ats_force_lexicon_v1.yaml",
            spec_ref="ATS-1 8.8, 8.11",
            origin="lexicon",
        ),
        Signal(
            signal_id="evidential-force",
            phrases=tuple(
                t["phrase"] for t in lexicon.document["evidential_force"]["terms"]
            ),
            rule_ids=("ATS-EVID-001", "ATS-EVID-002"),
            vocabulary_source="evidential_force.terms[].phrase in ats_force_lexicon_v1.yaml",
            spec_ref="ATS-1 8.12, 8.13",
            origin="lexicon",
        ),
        Signal(
            signal_id="causal-untyped-candidate",
            phrases=tuple(lexicon.causal_untyped_candidates),
            rule_ids=("ATS-EVID-002",),
            vocabulary_source="causal_force.untyped_candidates in ats_force_lexicon_v1.yaml",
            spec_ref="ATS-1 8.14, 8.15",
            origin="lexicon",
        ),
        Signal(
            signal_id="deontic-surface",
            phrases=tuple(sorted(set(lexicon.deontic_surfaces.values()))),
            rule_ids=("ATS-DEON-001", "ATS-DEON-002", "ATS-DEON-003"),
            vocabulary_source="deontic_force.terms[].surface in ats_force_lexicon_v1.yaml",
            spec_ref="ATS-1 8.16",
            origin="lexicon",
        ),
        Signal(
            signal_id="deontic-noncanonical",
            phrases=tuple(lexicon.deontic_noncanonical),
            rule_ids=("ATS-DEON-001",),
            vocabulary_source="deontic_force.noncanonical in ats_force_lexicon_v1.yaml",
            spec_ref="ATS-1 8.17",
            origin="lexicon",
        ),
        Signal(
            signal_id="relative-time-expression",
            phrases=tuple(RELATIVE_TIME_TERMS),
            rule_ids=("ATS-TIME-002",),
            vocabulary_source="the relative expressions enumerated verbatim in ATS-1 10.11",
            spec_ref="ATS-1 10.11",
            origin="spec_enumeration",
        ),
        Signal(
            signal_id="empty-intensifier",
            phrases=tuple(EMPTY_INTENSIFIERS),
            rule_ids=("ATS-DISC-003",),
            vocabulary_source="the intensifiers enumerated verbatim in ATS-1 10.20",
            spec_ref="ATS-1 10.20",
            origin="spec_enumeration",
        ),
        Signal(
            signal_id="vague-evaluative-term",
            phrases=tuple(VAGUE_EVALUATIVE),
            rule_ids=("ATS-SCOPE-001", "ATS-NUM-001"),
            vocabulary_source="the vague evaluative terms enumerated verbatim in ATS-1 10.21",
            spec_ref="ATS-1 10.21",
            origin="spec_enumeration",
        ),
    ]

    deprecated: list[str] = []
    for entry in glossary:
        deprecated.extend(entry.get("deprecated_aliases", ()))
    if deprecated:
        signals.append(
            Signal(
                signal_id="glossary-deprecated-alias",
                phrases=tuple(sorted(set(deprecated))),
                rule_ids=("ATS-TERM-001",),
                vocabulary_source="deprecated_aliases declared by the artifact's own glossary",
                spec_ref="ATS-1 10.2, 10.3",
                origin="artifact_glossary",
            )
        )

    for signal in signals:
        unknown = [r for r in signal.rule_ids if r not in ctx.registry]
        if unknown:
            raise UsageError(f"signal {signal.signal_id} names unknown rules: {unknown}")
    return signals


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(r"(?<!\w)" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"(?!\w)")


def match_phrases(text: str, phrases: Sequence[str]) -> list[tuple[int, int, str]]:
    """``(start, end, matched_text)`` for every phrase of ``phrases`` in ``text``.

    Carries no vocabulary of its own (ADR-0006): the caller supplies the term
    list, and this function only decides how a term is matched.
    """
    out: list[tuple[int, int, str]] = []
    lowered = text.lower()
    for phrase in phrases:
        if not phrase.strip():
            continue
        # Deontic surfaces are uppercase keywords; matching them case-folded
        # would flag ordinary uses of "may" and "can" as normative force.
        subject, needle = (
            (text, phrase) if phrase.isupper() else (lowered, phrase.lower().replace("_", " "))
        )
        for match in _phrase_pattern(needle).finditer(subject):
            out.append((match.start(), match.end(), text[match.start() : match.end()]))
    return sorted(set(out))


def find_matches(text: str, signal: Signal) -> list[tuple[int, int, str]]:
    """``(start, end, matched_text)`` for every phrase of ``signal`` in ``text``."""
    return match_phrases(text, signal.phrases)


# -- revision-derived candidates --------------------------------------------
#
# History reconstruction is trustworthy enough to say *that* a revision moved
# the text on an axis ATS-1 protects. It is not trustworthy enough to say
# anything normative about the move, and this section is written so that it
# structurally cannot.

#: The corpus use a revision-derived candidate consumes. One of the uses
#: ``ats.corpus.authority.USES`` enumerates; mining a repository that has not
#: authorised it is not a smaller kind of mining, it is mining without
#: permission.
AUTHORITY_USE: Final[str] = "candidate_mining"

#: The basis discriminator a revision-derived candidate carries.
REVISION_BASIS: Final[str] = "revision_force_delta"

#: The only value a revision candidate may record for its normative
#: interpretation, and the reason it is the only one.
#:
#: A force delta establishes that the text moved on an axis Section 11.3.1
#: protects. It does **not** establish that the earlier version violated a rule
#: (Section 17.4 refusal two), that the later version conforms (refusal one),
#: or that the edit was an improvement (refusal three). Only an adjudicated
#: judgment under a named rule can decide any of those (Sections 13.2, 16.5,
#: 17.9), and no part of this pipeline produces one. Every construction site
#: reads this constant, so there is exactly one value the field can hold.
NORMATIVE_INTERPRETATION: Final[str] = "unresolved"

#: Where the basis travels when a candidate becomes a stored corpus record.
EXT_CANDIDATE_BASIS: Final[str] = f"{rec.EXT_PREFIX}candidate-basis"

REVISION_BASIS_NOTE: Final[str] = (
    "A revision moved this span on an axis ATS-1 protects, which is why the span is worth "
    "reviewing. It is not evidence that the earlier text violated a rule, that the later text "
    "conforms, or that the edit improved the document. The normative reading of the change is "
    "unresolved, and only an adjudicated judgment under a named rule can resolve it "
    "(spec 11.3.1, 13.2, 17.4, 17.9)."
)

#: The ordering and timing boundary words Section 9.3.7 names verbatim when it
#: requires a material timing requirement to state an observable boundary:
#: "before or after a named event; within a duration; ...; until a condition".
#: The section's remaining items -- "at a frequency", "for a duration", "in a
#: specified sequence" -- name a boundary *kind* rather than a surface word, so
#: they contribute no phrase. That gap is recorded here rather than filled by
#: inventing synonyms (ADR-0006).
TIMING_BOUNDARY_TERMS: Final[tuple[str, ...]] = ("after", "before", "until", "within")


@dataclass(frozen=True, slots=True)
class ForceAxis:
    """One axis a revision can move text along, and the vocabulary that shows it."""

    #: ``deontic_force``, ``likelihood``, ``quantifier_scope``, or
    #: ``temporal_order``. Section 11.5 names the corresponding semantic delta
    #: classes ``deontic_force_changed``, ``likelihood_changed``,
    #: ``quantifier_changed``, and ``scope_changed``.
    axis: str
    phrases: tuple[str, ...]
    vocabulary_source: str
    spec_ref: str
    #: ``lexicon``, ``spec_enumeration``, or ``normative_schema_enum``.
    origin: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "vocabulary_source": self.vocabulary_source,
            "spec_ref": self.spec_ref,
            "origin": self.origin,
            "phrase_count": len(self.phrases),
        }


def build_force_axes(ctx: Any) -> list[ForceAxis]:
    """Assemble the four axes from the lexicon, Section 9.3.7, and the schemas.

    ADR-0006 binds a term list to the force lexicon, a list enumerated verbatim
    in the specification, or an enum a normative schema declares. Nothing here
    is assembled by this implementation.
    """
    lexicon = ctx.lexicon

    # A collision rule names a lowercase surface Section 8.17 calls ambiguous.
    # Only the ones colliding with a canonical deontic keyword are deontic
    # surfaces, and the membership test is the lexicon's own deontic term ids:
    # "will" and "confidence" collide elsewhere and are excluded by that test
    # rather than by a judgment made here.
    deontic_collisions = sorted(
        str(rule["surface"])
        for rule in lexicon.collision_rules
        if str(rule.get("surface", "")).upper() in lexicon.deontic_surfaces
    )
    quantifier_kinds = ctx.schemas.schema("ats_common_v1.schema.json")["$defs"]["quantifier"][
        "properties"
    ]["kind"]["enum"]

    axes = [
        ForceAxis(
            axis="deontic_force",
            phrases=tuple(
                sorted(
                    set(lexicon.deontic_surfaces.values())
                    | set(lexicon.deontic_noncanonical)
                    | set(deontic_collisions)
                )
            ),
            vocabulary_source=(
                "deontic_force.terms[].surface, deontic_force.noncanonical, and the "
                "collision_rules surfaces colliding with a deontic keyword in "
                "ats_force_lexicon_v1.yaml"
            ),
            spec_ref="ATS-1 8.16, 8.17",
            origin="lexicon",
        ),
        ForceAxis(
            axis="likelihood",
            phrases=tuple(
                sorted(
                    set(lexicon.wep_phrases)
                    | set(lexicon.wep_aliases)
                    | set(lexicon.non_probability_terms)
                )
            ),
            vocabulary_source=(
                "likelihood.terms[].phrase, likelihood.terms[].input_aliases, and "
                "likelihood.non_probability_terms in ats_force_lexicon_v1.yaml"
            ),
            spec_ref="ATS-1 8.2, 8.3, 8.7",
            origin="lexicon",
        ),
        ForceAxis(
            axis="quantifier_scope",
            phrases=tuple(sorted(quantifier_kinds)),
            vocabulary_source="quantifier kinds enumerated in ats_common_v1#/$defs/quantifier",
            spec_ref="ATS-1 7.7",
            origin="normative_schema_enum",
        ),
        ForceAxis(
            axis="temporal_order",
            phrases=TIMING_BOUNDARY_TERMS,
            vocabulary_source="the timing boundary words enumerated verbatim in ATS-1 9.3.7",
            spec_ref="ATS-1 9.3.7",
            origin="spec_enumeration",
        ),
    ]
    empty = [a.axis for a in axes if not a.phrases]
    if empty:
        raise UsageError(
            f"force axes {empty} resolved to no vocabulary; an axis that matches nothing would "
            "report 'no delta' for every revision, which is a pass read out of an absent check"
        )
    return axes


@dataclass(frozen=True, slots=True)
class RevisionDelta:
    """One region of one revision pair that moved on one axis."""

    axis: ForceAxis
    before_start: int
    before_end: int
    after_start: int
    after_end: int
    before_terms: tuple[str, ...]
    after_terms: tuple[str, ...]
    #: The axis matches inside the after region, at absolute offsets into the
    #: after text, so a caller can point a reviewer at the changed words.
    after_matches: tuple[tuple[int, int, str], ...]


def _line_starts(lines: Sequence[str]) -> list[int]:
    """Character offset of each line, plus the end offset. Length ``len+1``."""
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    return offsets


def _collapsed(text: str) -> str:
    """``text`` with every whitespace run collapsed, for cosmetic comparison."""
    return " ".join(text.split())


def revision_deltas(
    before_text: str, after_text: str, axes: Sequence[ForceAxis]
) -> tuple[list[RevisionDelta], dict[str, int]]:
    """Axis movements between two revisions of one document, and what was skipped.

    Only a region where one run of lines *replaced* another is examined. A pure
    insertion states force no earlier version stated, and a pure deletion
    leaves nothing at the pinned revision for a reviewer to look at -- neither
    is a movement of an existing statement, and Section 17.4 refusal two
    forbids reading a violation out of a deletion in any case. Both are counted
    in the returned tally rather than dropped silently.

    A region whose whitespace-collapsed text is unchanged is a reflow or a
    whitespace edit and yields nothing.
    """
    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    before_offsets = _line_starts(before_lines)
    after_offsets = _line_starts(after_lines)
    # autojunk would treat a line repeated across 1% of a large document as
    # noise and silently move the region boundaries, which is a different diff
    # on the same inputs once a file grows past the heuristic's threshold.
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)

    deltas: list[RevisionDelta] = []
    tally = {"replaced_regions": 0, "inserted_regions": 0, "deleted_regions": 0, "cosmetic": 0}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            tally["inserted_regions"] += 1
            continue
        if tag == "delete":
            tally["deleted_regions"] += 1
            continue
        if tag != "replace":
            continue
        tally["replaced_regions"] += 1
        b0, b1 = before_offsets[i1], before_offsets[i2]
        a0, a1 = after_offsets[j1], after_offsets[j2]
        before_region, after_region = before_text[b0:b1], after_text[a0:a1]
        if _collapsed(before_region) == _collapsed(after_region):
            tally["cosmetic"] += 1
            continue
        for axis in axes:
            before_hits = match_phrases(before_region, axis.phrases)
            after_hits = match_phrases(after_region, axis.phrases)
            before_terms = tuple(sorted(h[2] for h in before_hits))
            after_terms = tuple(sorted(h[2] for h in after_hits))
            if before_terms == after_terms:
                continue
            deltas.append(
                RevisionDelta(
                    axis=axis,
                    before_start=b0,
                    before_end=b1,
                    after_start=a0,
                    after_end=a1,
                    before_terms=before_terms,
                    after_terms=after_terms,
                    after_matches=tuple((a0 + s, a0 + e, t) for s, e, t in after_hits),
                )
            )
    return deltas, tally


def candidate_mining_permitted(artifact: Mapping[str, Any]) -> tuple[bool, str]:
    """Whether ``candidate_mining`` resolved permitted for this exact artifact.

    Read from the resolution ``build_inventory`` already recorded rather than
    resolved again: a second resolution path is a second place the answer can
    differ. An artifact carrying no resolution is not thereby authorised --
    an absent declaration resolves ``unknown``, and ADR-0002 forbids reading a
    pass out of a check that did not run.
    """
    git = (artifact.get("extensions") or {}).get(f"{rec.EXT_PREFIX}git") or {}
    block = git.get("authority")
    if not isinstance(block, Mapping):
        return False, (
            "the inventory recorded no authority resolution for this artifact, so "
            f"{AUTHORITY_USE} is unknown; an unknown use is not an authorised one"
        )
    value = (block.get("uses") or {}).get(AUTHORITY_USE, "unknown")
    if AUTHORITY_USE in (block.get("permitted") or ()):
        location = block.get("declaration_location") or "unrecorded"
        return True, f"{AUTHORITY_USE} resolved {value!r} from the {location} declaration"
    basis = (block.get("blocked_basis") or {}).get(AUTHORITY_USE) or ["unrecorded"]
    return False, f"{AUTHORITY_USE} resolved {value!r}; basis: {', '.join(basis)}"


def _revision_span(
    delta: RevisionDelta, blocks: Sequence[tuple[int, int, int, str]]
) -> tuple[int, int, tuple[int, int, int, str]] | None:
    """``(start, end, block)`` in the after text, or ``None`` when unreviewable.

    The candidate points at the changed words inside one block, not at the
    whole diff region: a context bundle carries the complete containing block
    and cannot be built for a span straddling two. Section 5.6 exempts code and
    quoted material from surface rules, so a delta inside a code block is not
    even a candidate.
    """
    anchor = delta.after_matches[0][0] if delta.after_matches else delta.after_start
    block = next((b for b in blocks if b[0] <= anchor < b[1]), None)
    if block is None or block[3] == "code_block":
        return None
    if delta.after_matches:
        inside = [m for m in delta.after_matches if block[0] <= m[0] and m[1] <= block[1]]
        if not inside:
            return None
        start, end = inside[0][0], max(m[1] for m in inside)
    else:
        # Every axis term was removed. There are no changed words left to point
        # at, so the reviewable span is what replaced them, clipped to the block.
        start, end = delta.after_start, min(delta.after_end, block[1])
    return (start, end, block) if start < end else None


def build_revision_candidate(
    artifact: Mapping[str, Any],
    delta: RevisionDelta,
    *,
    before_revision: str,
    span: tuple[int, int],
    block: tuple[int, int, int, str],
    heading_path: Sequence[str],
    review_state_note: str,
    later_edit_note: str,
    authority_basis: str,
) -> dict[str, Any]:
    """The one place a ``revision_force_delta`` candidate is constructed.

    ``normative_interpretation`` is :data:`NORMATIVE_INTERPRETATION` here and
    nowhere else, so the field has exactly one reachable value.
    """
    start, end = span
    after_revision = artifact["revision"]
    candidate_id = "ats-candidate-sha256:" + sha256_hex(
        "|".join(
            (
                artifact["artifact_id"],
                REVISION_BASIS,
                delta.axis.axis,
                before_revision,
                str(delta.before_start),
                str(delta.before_end),
                str(delta.after_start),
                str(delta.after_end),
            )
        ).encode("utf-8")
    )
    return {
        "candidate_id": candidate_id,
        "artifact_id": artifact["artifact_id"],
        "repository_group": artifact["repository_group"],
        "path": artifact["path"],
        "revision": after_revision,
        "span": {
            "kind": "character",
            "start": start,
            "end": end,
            "source_sha256": artifact["content_sha256"],
        },
        "block": {"kind": block[3], "start_line": block[2]},
        "heading_path": list(heading_path),
        "profile_hypotheses": list(artifact.get("profile_hypotheses") or ()),
        "candidate_only": True,
        "note": CANDIDATE_ONLY_NOTE,
        "label": None,
        "requires_context_bundle": True,
        "refusals": [
            {"refusal_id": r.refusal_id, "answer": r.answer, "spec_ref": r.spec_ref}
            for r in MINING_REFUSALS
        ],
        "review_state": artifact.get("review_state", "unknown"),
        "review_state_note": review_state_note,
        "later_edit_note": later_edit_note,
        "authority_basis": authority_basis,
        "candidate_basis": {
            "type": REVISION_BASIS,
            "before_revision": before_revision,
            "after_revision": after_revision,
            "before_span": {
                "kind": "character",
                "start": delta.before_start,
                "end": delta.before_end,
                "revision": before_revision,
            },
            "after_span": {
                "kind": "character",
                "start": delta.after_start,
                "end": delta.after_end,
                "revision": after_revision,
                "source_sha256": artifact["content_sha256"],
            },
            "changed_axis": delta.axis.axis,
            "normative_interpretation": NORMATIVE_INTERPRETATION,
            "normative_interpretation_note": REVISION_BASIS_NOTE,
            "before_terms": list(delta.before_terms),
            "after_terms": list(delta.after_terms),
            "vocabulary_source": delta.axis.vocabulary_source,
            "spec_ref": delta.axis.spec_ref,
        },
    }


def attach_candidate_basis(
    record: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    """Carry a candidate's basis onto a stored corpus record, re-addressed.

    A judgment reached without the basis is a judgment about a span rather than
    about the change that raised it, and the refusals only bind where the
    annotator can read them. The basis therefore rides in the record's own
    ``extensions`` under the Section 19.5 namespace instead of being dropped
    when a candidate becomes a context bundle or a text example.
    """
    basis = candidate.get("candidate_basis")
    if not isinstance(basis, Mapping) or not basis:
        raise UsageError(
            f"candidate {candidate.get('candidate_id', '<unidentified>')!r} carries no "
            "candidate_basis; there is nothing to attach"
        )
    extensions = dict(record.get("extensions") or {})
    extensions[EXT_CANDIDATE_BASIS] = dict(basis)
    return rec.address({**record, "extensions": extensions})


# -- mining -----------------------------------------------------------------


def _block_index(text: str, media_type: str) -> list[tuple[int, int, int, str]]:
    """``(start, end, start_line, kind)`` for each block, for span attribution."""
    from .context import document_blocks

    return [(b.start, b.end, b.start_line, b.kind) for b in document_blocks(text, media_type=media_type)]


# -- cache binding ----------------------------------------------------------
#
# A mining result is expensive and therefore gets cached, and a cache is only
# safe if it can say what it was built over. Everything below exists because it
# could not.

#: Where a mining result records the inventory it was built over.
INVENTORY_BINDING: Final[str] = "inventory_binding"

#: The three conclusions a declaration check can reach. Three rather than two,
#: because "verified equal", "verified different" and "cannot be determined"
#: are separate answers and ADR-0002 forbids reporting the third as either of
#: the first two. A cache that cannot say which declaration it was built under
#: is not thereby fresh.
DECLARATION_MATCH: Final[str] = "match"
DECLARATION_MISMATCH: Final[str] = "mismatch"
DECLARATION_UNKNOWN: Final[str] = "unknown"


def declaration_sha256_of(inventory: Mapping[str, Any]) -> str | None:
    """The authority declaration digest an inventory recorded, if it recorded one.

    ``None`` covers two situations the inventory itself keeps apart -- a
    repository nothing declares (``availability: not_found``) and an inventory
    built before :data:`ats.corpus.inventory.AUTHORITY_DECLARATION` existed (no
    block at all). Both are ``unknown`` to a staleness check and neither is a
    digest, so they collapse here and nowhere earlier.
    """
    block = inventory.get(inv.AUTHORITY_DECLARATION)
    if not isinstance(block, Mapping):
        return None
    recorded = block.get("sha256")
    return str(recorded) if recorded else None


def declaration_state(recorded: str | None, live: str | None) -> tuple[str, str]:
    """Compare the declaration a cache was built under with the live one.

    Returns one of :data:`DECLARATION_MATCH`, :data:`DECLARATION_MISMATCH` or
    :data:`DECLARATION_UNKNOWN`, and the sentence that says why. Only the first
    is evidence of freshness: an unknown is the absence of the comparison, not
    a quiet pass, and the caller that treats it as one has re-created the
    failure this module exists to remove.
    """
    if recorded is None and live is None:
        return DECLARATION_UNKNOWN, (
            "neither the cache nor the reader states an authority declaration, so there is "
            "nothing to compare"
        )
    if recorded is None:
        return DECLARATION_UNKNOWN, (
            f"the cache records no declaration digest and is being read under "
            f"{str(live)[:12]}, so it predates the field or was mined without one"
        )
    if live is None:
        return DECLARATION_UNKNOWN, (
            f"the cache was built under {recorded[:12]} but the reader states no live "
            "declaration, so whether that one is still in force is unestablished"
        )
    if recorded == live:
        return DECLARATION_MATCH, f"both name declaration {recorded[:12]}"
    return DECLARATION_MISMATCH, (
        f"the cache was built under {recorded[:12]} and is being read under {live[:12]}"
    )


def _declaration_under(
    inventory: Mapping[str, Any], supplied: str | None
) -> str | None:
    """The declaration digest a mining run should record, from two possible sources.

    The inventory is the authority: it was resolved under that declaration and
    every artifact address in it was computed from the result. ``supplied``
    exists for the one case the inventory cannot answer -- a cached inventory
    written before it recorded the field -- and a ``supplied`` value that
    contradicts the inventory is refused. Preferring either one silently would
    stamp a digest onto candidates that were extracted under the other, which
    is worse than no digest: it would make a stale cache assert freshness.
    """
    recorded = declaration_sha256_of(inventory)
    if supplied is None:
        return recorded
    if recorded is not None and recorded != supplied:
        raise UsageError(
            f"mining {inventory.get('repository')} was asked to record authority "
            f"declaration {supplied[:12]}, but the inventory it is mining was built under "
            f"{recorded[:12]}. These artifacts were addressed under the inventory's "
            "declaration, so recording the supplied one would make the cache claim a scope "
            "it does not have; re-inventory the repository under the declaration you mean."
        )
    return supplied


def inventory_binding(
    inventory: Mapping[str, Any], *, declaration_sha256: str | None = None
) -> dict[str, Any]:
    """What a mining result was built over, in a form a later reader can check.

    ``inventory_sha256`` digests the ``(artifact_id, content_sha256)`` pairs and
    nothing else, because those are the two facts a candidate keys on: it
    addresses its artifact by ``artifact_id`` and cuts its span from the bytes
    ``content_sha256`` pins. A digest over the whole inventory would also move
    for changes no candidate depends on, and would report staleness that is not
    there.

    ``declaration_sha256`` is the authority declaration the inventory was
    resolved under. It defaults to the digest the inventory itself recorded, so
    the value reaches the cache without anyone hashing an overlay a second time
    (:meth:`ats.corpus.authority.AuthorityDeclaration.from_file` is the one
    place that hash is computed). It is recorded separately from
    ``inventory_sha256`` rather than folded into it so a mismatch can say
    *which* input moved: an overlay edit and a new repository revision both
    re-address every document, and they call for different responses.

    The coupling this exists to make visible: ``records.address`` hashes the
    whole artifact record with only the identifier removed, extensions
    included, so the authority block ``build_inventory`` attaches sits inside
    ``artifact_id`` by construction. Editing an overlay therefore re-addresses
    every document it covers, and every cached candidate pointing at the old
    address silently stops resolving.
    """
    artifacts = list(inventory.get("artifacts", ()))
    return {
        "revision": str(inventory.get("revision", "")),
        "artifact_count": len(artifacts),
        "inventory_sha256": content_hash(
            {
                "artifacts": sorted(
                    [str(a["artifact_id"]), str(a["content_sha256"])] for a in artifacts
                )
            },
            exclude=set(),
        ),
        "declaration_sha256": declaration_sha256,
    }


def require_inventory_binding(
    mined: Mapping[str, Any],
    inventory: Mapping[str, Any],
    *,
    where: str,
    declaration_sha256: str | None,
) -> None:
    """Refuse a mining result that was not built over ``inventory``.

    Called by every consumer that reads a *stored* mining result, so the error
    arrives when the cache is loaded rather than as a pile of unresolvable
    candidates later. A consumer that skips an unresolvable candidate instead
    converts "I could not resolve this" into "there was nothing here", which is
    passing by absence (ADR-0002) at whatever scale the drift reached -- 668
    candidates and a third of the corpus, the one time it happened.

    An absent binding refuses too. A result mined before this field existed
    cannot state what it was built over, and treating "cannot verify" as
    "verified" is the failure this function exists to remove.

    ``declaration_sha256`` has no default. It is the caller's statement of
    which authority declaration is live *now*, and a caller that cannot make
    that statement passes ``None`` and is refused, because the alternative --
    silently skipping the comparison -- is a check whose absence reads exactly
    like a pass. Every repository that clears
    :func:`ats.corpus.frame.resolve_annotation_authority` has a digest to pass;
    one that does not was never authorised to be mined.
    """
    recorded = mined.get(INVENTORY_BINDING)
    expected = inventory_binding(inventory, declaration_sha256=declaration_sha256)
    if not isinstance(recorded, Mapping):
        raise UsageError(
            f"the mining result for {where} records no {INVENTORY_BINDING}, so it cannot say "
            "which inventory it was built over; re-mine it rather than trusting a cache whose "
            "provenance is unstated"
        )
    if recorded.get("inventory_sha256") != expected["inventory_sha256"]:
        moved = (
            "the repository revision moved"
            if recorded.get("revision") != expected["revision"]
            else "the artifact records were rebuilt at the same revision, which an authority "
            "overlay edit alone is enough to do"
        )
        raise UsageError(
            f"the mining result for {where} was built over a different inventory "
            f"({recorded.get('artifact_count')} artifacts at "
            f"{str(recorded.get('revision'))[:12]}, digest "
            f"{str(recorded.get('inventory_sha256'))[:12]}) than the one supplied "
            f"({expected['artifact_count']} artifacts at {expected['revision'][:12]}, digest "
            f"{expected['inventory_sha256'][:12]}): {moved}. Every candidate addresses its "
            "artifact by artifact_id, and artifact_id is a content address over the artifact "
            "record, so none of these candidates resolves. Re-mine."
        )
    state, reason = declaration_state(
        recorded.get("declaration_sha256"), declaration_sha256
    )
    if state == DECLARATION_MISMATCH:
        raise UsageError(
            f"the mining result for {where} was built under a different authority "
            f"declaration: {reason}. The artifact identities happen to agree, but the "
            "declaration that scoped the mining does not, so what was in scope when these "
            f"candidates were extracted is not what is in scope now. Re-mine {where}."
        )
    if state == DECLARATION_UNKNOWN:
        raise UsageError(
            f"the mining result for {where} cannot be checked against a live authority "
            f"declaration: {reason}. That is unknown, and unknown is not fresh -- the "
            "declaration's bytes sit inside every artifact_id built under it, so an overlay "
            "edit re-addresses every document without moving one and a cache that cannot "
            f"name its declaration cannot rule that out (ADR-0002). Re-mine {where} so the "
            "cache states what it was built under."
        )


def mine_candidates(
    ctx: Any,
    inventory: Mapping[str, Any],
    *,
    repo_path: str | None = None,
    declaration_sha256: str | None = None,
) -> dict[str, Any]:
    """Extract review candidates from every artifact in ``inventory``.

    Two bases produce candidates, and they are kept apart because they are
    entitled to different things:

    ``candidates``
        A span whose *surface* carries a signal one of the thirty rules cares
        about. Each names the signal that triggered it, the rules that signal
        is relevant to, and the vocabulary the phrase came from.
    ``revision_candidates``
        A span a revision *moved* on a protected force axis, carrying a
        ``candidate_basis`` of type :data:`REVISION_BASIS`. These are produced
        only for artifacts whose repository authorised :data:`AUTHORITY_USE`.

    No candidate of either basis carries a label: ``label`` is always ``None``
    and ``refusals`` names the three inferences Section 17.4 forbids.

    The result opens with :data:`INVENTORY_BINDING`, naming the inventory it was
    built over and the authority declaration that scoped it. Every candidate
    addresses its artifact by ``artifact_id``, which is a content address over
    the artifact record, so a result read against a rebuilt inventory resolves
    nothing.

    ``declaration_sha256`` defaults to the digest ``inventory`` recorded, which
    is where it should come from: the inventory was resolved under that
    declaration and the artifacts carry it inside their addresses. A caller may
    pass one only when the inventory is silent -- a cache built before
    :data:`ats.corpus.inventory.AUTHORITY_DECLARATION` existed -- and passing
    one that contradicts the inventory is refused rather than preferred, since
    exactly one of the two can be describing the artifacts in hand.
    """
    declaration_sha256 = _declaration_under(inventory, declaration_sha256)
    repository = repo_path or inventory.get("repository")
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    signals = build_signals(ctx)
    signals_by_id = {s.signal_id: s for s in signals}
    axes = build_force_axes(ctx)
    pending: list[dict[str, Any]] = []

    for artifact in inventory.get("artifacts", ()):
        try:
            text = inv.artifact_text(repository, artifact) if repository else None
        except UsageError as exc:
            skipped.append({"path": artifact["path"], "reason": "unreadable", "detail": str(exc)})
            continue
        if text is None:
            skipped.append(
                {
                    "path": artifact["path"],
                    "reason": "no_repository",
                    "detail": "candidate spans are cut from the exact bytes at the pinned "
                    "revision, so mining without the repository is refused",
                }
            )
            continue

        media_type = artifact.get("media_type", "text/markdown")
        blocks = _block_index(text, media_type)
        later_edit = (
            (artifact.get("extensions") or {})
            .get(f"{rec.EXT_PREFIX}git", {})
            .get("later_edits", {"availability": "not_searched"})
        )

        _, merge_reason = conformance_from_review_state(artifact.get("review_state", "unknown"))
        _, edit_reason = quality_from_later_edit(later_edit)

        permitted, authority_basis = candidate_mining_permitted(artifact)
        previous = (
            (artifact.get("extensions") or {})
            .get(f"{rec.EXT_PREFIX}git", {})
            .get("previous_edit", {"availability": "not_searched"})
        )
        if not permitted:
            skipped.append(
                {
                    "path": artifact["path"],
                    "reason": "revision_basis_unauthorised",
                    "detail": authority_basis,
                }
            )
        elif previous.get("availability") != "present":
            skipped.append(
                {
                    "path": artifact["path"],
                    "reason": "revision_basis_no_previous_edit",
                    "detail": previous.get(
                        "detail", "the inventory recorded no earlier revision of this path"
                    ),
                }
            )
        else:
            pending.append(
                {
                    "artifact": artifact,
                    "text": text,
                    "blocks": blocks,
                    "before_revision": previous["sha"],
                    "review_state_note": merge_reason,
                    "later_edit_note": edit_reason,
                    "authority_basis": authority_basis,
                }
            )

        for signal in signals:
            for start, end, matched in find_matches(text, signal):
                block = next(
                    ((bs, be, line, kind) for bs, be, line, kind in blocks if bs <= start < be),
                    None,
                )
                if block is None:
                    continue
                if block[3] == "code_block":
                    # Spec 5.6: quoted source text, code, and logs may be
                    # exempt from surface rules, so a cue inside them is not
                    # even a candidate.
                    continue
                candidate_id = "ats-candidate-sha256:" + sha256_hex(
                    f"{artifact['artifact_id']}|{signal.signal_id}|{start}|{end}".encode("utf-8")
                )
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "artifact_id": artifact["artifact_id"],
                        "repository_group": artifact["repository_group"],
                        "path": artifact["path"],
                        "revision": artifact["revision"],
                        "span": {
                            "kind": "character",
                            "start": start,
                            "end": end,
                            "source_sha256": artifact["content_sha256"],
                        },
                        "matched_phrase": matched,
                        "signal": signal.to_dict(),
                        "block": {"kind": block[3], "start_line": block[2]},
                        "heading_path": _heading_path_for(artifact, text, block[2]),
                        "profile_hypotheses": list(artifact.get("profile_hypotheses") or ()),
                        "candidate_only": True,
                        "note": CANDIDATE_ONLY_NOTE,
                        "label": None,
                        "requires_context_bundle": True,
                        "refusals": [
                            {"refusal_id": r.refusal_id, "answer": r.answer, "spec_ref": r.spec_ref}
                            for r in MINING_REFUSALS
                        ],
                        "review_state": artifact.get("review_state", "unknown"),
                        "review_state_note": merge_reason,
                        "later_edit_note": edit_reason,
                    }
                )

    revision_candidates, revision_skipped, scan = _mine_revisions(repository, pending, axes)
    skipped.extend(revision_skipped)

    candidates.sort(key=lambda c: (c["path"], c["span"]["start"], c["signal"]["signal_id"]))
    revision_candidates.sort(
        key=lambda c: (c["path"], c["span"]["start"], c["candidate_basis"]["changed_axis"])
    )
    used = sorted({c["signal"]["signal_id"] for c in candidates})
    axes_used = sorted({c["candidate_basis"]["changed_axis"] for c in revision_candidates})
    axes_by_name = {a.axis: a for a in axes}
    return {
        INVENTORY_BINDING: inventory_binding(
            inventory, declaration_sha256=declaration_sha256
        ),
        "candidates": candidates,
        "signals_used": [signals_by_id[s].to_dict() for s in used],
        "signals_available": [s.to_dict() for s in signals],
        "revision_candidates": revision_candidates,
        "axes_used": [axes_by_name[a].to_dict() for a in axes_used],
        "axes_available": [a.to_dict() for a in axes],
        "revision_scan": scan,
        "refusals": [
            {
                "refusal_id": r.refusal_id,
                "question": r.question,
                "answer": r.answer,
                "spec_ref": r.spec_ref,
            }
            for r in MINING_REFUSALS
        ],
        "skipped": skipped,
    }


def _mine_revisions(
    repository: str | None,
    pending: Sequence[Mapping[str, Any]],
    axes: Sequence[ForceAxis],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, int]]:
    """Build revision candidates for the artifacts that cleared the authority gate.

    The earlier revision of each document is read in one ``git`` call per
    distinct revision rather than one per document, because a single commit
    usually touches several of them.
    """
    out: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    scan: dict[str, int] = {
        "documents_scanned": 0,
        "replaced_regions": 0,
        "inserted_regions": 0,
        "deleted_regions": 0,
        "cosmetic": 0,
    }
    if not pending or repository is None:
        return out, skipped, scan

    repo = Path(repository)
    by_revision: dict[str, list[str]] = {}
    for item in pending:
        by_revision.setdefault(item["before_revision"], []).append(item["artifact"]["path"])
    blobs: dict[str, dict[str, bytes]] = {}
    for revision, paths in sorted(by_revision.items()):
        try:
            blobs[revision] = inv.blob_batch(repo, revision, sorted(paths))
        except inv.GitUnavailable as exc:
            blobs[revision] = {}
            skipped.append(
                {
                    "path": ", ".join(sorted(paths)),
                    "reason": "revision_basis_git_unavailable",
                    "detail": f"the earlier revision {revision[:12]} is unreadable: {exc}",
                }
            )

    for item in pending:
        artifact = item["artifact"]
        path = artifact["path"]
        raw = blobs.get(item["before_revision"], {}).get(path)
        if raw is None:
            skipped.append(
                {
                    "path": path,
                    "reason": "revision_basis_before_blob_missing",
                    "detail": f"{path} has no blob at {item['before_revision'][:12]}",
                }
            )
            continue
        try:
            before_text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            skipped.append(
                {
                    "path": path,
                    "reason": "revision_basis_before_not_utf8",
                    "detail": str(exc),
                }
            )
            continue

        scan["documents_scanned"] += 1
        deltas, tally = revision_deltas(before_text, item["text"], axes)
        for key, value in tally.items():
            scan[key] += value
        for delta in deltas:
            located = _revision_span(delta, item["blocks"])
            if located is None:
                skipped.append(
                    {
                        "path": path,
                        "reason": "revision_basis_unreviewable_span",
                        "detail": f"the {delta.axis.axis} delta at [{delta.after_start},"
                        f"{delta.after_end}) is in exempt or unblocked content, so it carries "
                        "no span an annotator can be shown (spec 5.6, 17.4)",
                    }
                )
                continue
            start, end, block = located
            out.append(
                build_revision_candidate(
                    artifact,
                    delta,
                    before_revision=item["before_revision"],
                    span=(start, end),
                    block=block,
                    heading_path=_heading_path_for(artifact, item["text"], block[2]),
                    review_state_note=item["review_state_note"],
                    later_edit_note=item["later_edit_note"],
                    authority_basis=item["authority_basis"],
                )
            )
    return out, skipped, scan


def _heading_path_for(artifact: Mapping[str, Any], text: str, start_line: int) -> list[str]:
    """The heading stack over a candidate, for documents that have headings."""
    from .context import heading_path_at

    if not artifact.get("heading_paths"):
        return []
    return heading_path_at(text, start_line)


def candidate_spans(candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The distinct ``(artifact, span)`` pairs a candidate set points at."""
    seen: dict[tuple[str, int, int], dict[str, Any]] = {}
    for candidate in candidates:
        span = candidate["span"]
        key = (candidate["artifact_id"], span["start"], span["end"])
        seen.setdefault(key, {"artifact_id": candidate["artifact_id"], "span": span})
    return [seen[k] for k in sorted(seen)]

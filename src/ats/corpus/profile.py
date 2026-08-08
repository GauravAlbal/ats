"""Profile as a corpus-layer hypothesis, never as an inferred fact.

Profile resolution is a corpus-layer annotation question, not an inferred
fact. A corpus that cannot supply a profile has exactly two options — guess
one, or make it an annotation target. This module implements the second, and
the shape of the record is what enforces it:

* A record is scoped to one **section**, never to a whole document. Section 9.4
  permits an artifact to compose profiles at section level, so a document-wide
  answer would erase a distinction the standard makes.
* Every candidate carries the evidence that raised it, and the only admissible
  evidence is structural or lexical and read out of the scope's own text. A
  filename, a directory, a repository, and a sibling document's convention are
  excluded: none of them is a statement about what reader job the prose does.
  ``SPECIFICATION.md`` is a naming habit, not a declaration.
* Absent evidence produces no candidate. It does not produce a default profile,
  and it does not produce "no profile" either (Section 5.4).
* Two or more candidates for one scope is the normal case for a mixed artifact
  and is represented as such. Nothing here ranks them: ordering candidates by
  cue count would reintroduce the guess the object exists to avoid.
* ``decision.state`` leaves this module as ``REVIEW_REQUIRED`` on every record.
  Section 13.7 forbids a component from adjudicating its own output and
  Section 14.11 places semantic acceptance with an authorized human.

No vocabulary is declared here. The imported force lexicon supplies the
likelihood, assessment-confidence, deontic, and evidential terms, and
``ats_common_v1.schema.json`` supplies the core profile identifiers, the
extension-namespace pattern, the claim-role enum, and the requirement-slot
names. :func:`check_vocabulary_currency` fails loudly if a mapping here ever
names something the normative package no longer defines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

from ..errors import UsageError
from . import inventory as inv
from . import records as rec
from .authority import AuthorityDeclaration
from .mine import Refusal

SCHEMA_VERSION: Final[str] = "ats.profile_hypothesis.v1"

GENERATOR_ID: Final[str] = "ats.corpus.profile/build_profile_hypotheses"

#: The corpus use this generator performs. It reads source text and derives
#: candidates from it, which is mining; producing an annotation target is not
#: itself annotation.
AUTHORITY_USE: Final[str] = "candidate_mining"

#: The normative schema that defines every identifier vocabulary this module
#: reads. Nothing below restates its contents.
COMMON_SCHEMA_ID: Final[str] = "ats_common_v1.schema.json"

#: Block kinds whose contents raise no candidate. Spec Section 5.6 exempts
#: quoted source text, code, and logs from surface rules, so a deontic keyword
#: inside a fenced example is a quotation of a keyword, not an obligation.
EXEMPT_BLOCK_KINDS: Final[frozenset[str]] = frozenset({"code_block"})


# -- refusals ---------------------------------------------------------------
#
# Reuses :class:`ats.corpus.mine.Refusal` rather than declaring a second shape
# for the same idea, so a reviewer reads mining refusals and profile refusals in
# one format.

PROFILE_REFUSALS: Final[tuple[Refusal, ...]] = (
    Refusal(
        refusal_id="no-profile-from-filename",
        question="Does a file called SPECIFICATION.md, or a path under specs/, make its "
        "content SPECIFY?",
        answer=(
            "No. A filename, a directory, and a repository are naming conventions their "
            "authors chose for other reasons. Section 3.2 defines a profile by the reader "
            "job the prose performs, and no evidence for that job lives outside the prose."
        ),
        spec_ref="ATS-1 3.2, 9.4",
    ),
    Refusal(
        refusal_id="no-profile-from-absence",
        question="Does a section with no matched cue have no profile?",
        answer=(
            "No. It has no evidence. Section 5.4 forbids reading the absence of a signal as "
            "a determination, so a scope with nothing found emits no candidate rather than a "
            "candidate saying none."
        ),
        spec_ref="ATS-1 5.4, 16.5",
    ),
    Refusal(
        refusal_id="no-resolution-from-generator",
        question="May the generator pick the profile when the evidence points one way?",
        answer=(
            "No. Every generated record stays REVIEW_REQUIRED. Section 13.7 forbids a "
            "component from becoming the authoritative adjudicator for its own output, and "
            "Section 14.11 places semantic acceptance with an authorized human."
        ),
        spec_ref="ATS-1 13.7, 14.11",
    ),
    Refusal(
        refusal_id="no-conformance-claim-for-namespaced-profile",
        question="May an extension-namespaced profile carry an ATS-1 conformance claim?",
        answer=(
            "No. Section 3.3 permits experimenting with a reserved profile under an extension "
            "namespace but forbids claiming core ATS-1 profile conformance for it, and "
            "Section 9.5 requires the identifier be preserved and reported as unsupported "
            "rather than mapped to ASSESS or SPECIFY by similarity."
        ),
        spec_ref="ATS-1 3.3, 9.5",
    ),
)

REFUSAL_IDS: Final[tuple[str, ...]] = tuple(r.refusal_id for r in PROFILE_REFUSALS)


def _refusal_records() -> list[dict[str, str]]:
    return [
        {
            "refusal_id": r.refusal_id,
            "question": r.question,
            "answer": r.answer,
            "spec_ref": r.spec_ref,
        }
        for r in PROFILE_REFUSALS
    ]


# -- profile identifiers, read from the normative schema ---------------------


def _profile_def(ctx: Any) -> Mapping[str, Any]:
    return ctx.schemas.schema(COMMON_SCHEMA_ID)["$defs"]["profile"]


def core_profiles(ctx: Any) -> tuple[str, ...]:
    """The core ATS-1 profile identifiers, read from the normative schema.

    Read rather than restated, so an edition that adds or removes a core profile
    changes this implementation's behaviour without an edit here.
    """
    for branch in _profile_def(ctx)["oneOf"]:
        if "enum" in branch:
            return tuple(branch["enum"])
    raise UsageError(
        f"{COMMON_SCHEMA_ID} #/$defs/profile declares no enum branch, so the core profile "
        "identifiers cannot be read from the normative package"
    )


def extension_profile_pattern(ctx: Any) -> re.Pattern[str]:
    """The normative extension-namespace pattern for a profile identifier."""
    for branch in _profile_def(ctx)["oneOf"]:
        if "pattern" in branch:
            return re.compile(branch["pattern"])
    raise UsageError(
        f"{COMMON_SCHEMA_ID} #/$defs/profile declares no pattern branch, so an extension "
        "profile cannot be recognised"
    )


def is_extension_profile(ctx: Any, profile: str) -> bool:
    """Whether ``profile`` is namespaced as an extension, e.g. ``X-ARQ-EXPLAIN``."""
    return extension_profile_pattern(ctx).search(profile) is not None


def may_carry_conformance_claim(ctx: Any, profile: str) -> bool:
    """Whether ``profile`` may carry a core ATS-1 conformance claim.

    True only for a core identifier the normative package enumerates. False for
    every extension-namespaced profile, because Section 3.3 permits
    experimenting with a reserved profile under a namespace and in the same
    sentence forbids claiming core ATS-1 profile conformance for it. Also false
    for a bare reserved name such as ``EXPLAIN``: Section 3.3 requires the
    namespace, so the unnamespaced form is not a recordable profile at all.
    """
    return profile in core_profiles(ctx)


def is_recordable_profile(ctx: Any, profile: str) -> bool:
    """Whether ``profile`` may appear in a hypothesis at all.

    A core identifier or an extension-namespaced one. This mirrors the normative
    ``profile`` definition, so a value refused here is a value the schema would
    also refuse; the check exists so the refusal happens before the record is
    built rather than as a validation failure afterwards.
    """
    return may_carry_conformance_claim(ctx, profile) or is_extension_profile(ctx, profile)


# -- evidence vocabularies ---------------------------------------------------

#: Claim roles the standard ties to one profile, with the section that ties
#: them. A role the spec uses in both profiles is deliberately absent:
#: "appears in both" is not evidence for either, and a candidate raised from it
#: would be noise a reviewer has to clear. ``definition``, ``boundary``, and
#: ``exception`` are absent for that reason specifically — Section 9.1
#: obligations 4 and 6 make terms, boundaries, and exceptions obligations of
#: *all* stable profiles, so the role alone discriminates nothing. Section 9.2.2
#: separately makes "material boundaries" an ASSESS **document-level slot**,
#: which is a claim about a section's structure rather than about one claim's
#: role; that reading is carried by :data:`ASSESS_DOCUMENT_SLOTS` and applies to
#: headings only.
ROLE_PROFILE: Final[dict[str, tuple[str, str]]] = {
    "observation": ("ASSESS", "ATS-1 9.2.5"),
    "inference": ("ASSESS", "ATS-1 9.2.5"),
    "judgment": ("ASSESS", "ATS-1 9.2.4"),
    "forecast": ("ASSESS", "ATS-1 9.2.4"),
    "recommendation": ("ASSESS", "ATS-1 9.2.2"),
    "assumption": ("ASSESS", "ATS-1 9.2.2"),
    "requirement": ("SPECIFY", "ATS-1 9.3.2"),
}

#: Requirement slots that carry no profile signal on their own. ``rationale``
#: is explicitly non-normative and stored separately (Section 9.3.2), and
#: ``indivisible_actions_justification`` is a justification about a requirement
#: rather than a slot of one.
UNINFORMATIVE_REQUIREMENT_SLOTS: Final[frozenset[str]] = frozenset(
    {"rationale", "indivisible_actions_justification"}
)

#: How many distinct requirement-slot labels a scope must show before the slot
#: shape counts as evidence. One label proves nothing — "Scope:" and
#: "Condition:" head paragraphs in every kind of document. Section 9.3.2
#: describes a requirement *object* with several slots, so the object's shape,
#: not any single slot name, is what is being recognised.
REQUIREMENT_SLOT_QUORUM: Final[int] = 2

#: Section 9.2.2's required document-level ASSESS slots, enumerated verbatim
#: from ``ATS-1_SPEC.md``. The spec states them as prose rather than as a
#: machine-readable enum, so they are transcribed here once and cited, in the
#: same way ``ats.corpus.mine`` reuses the Section 10.11, 10.20, and 10.21
#: lists. They exist so that a heading such as "Contrary evidence" is
#: recognised as ASSESS structure, and so that a slot both profiles name is
#: recognised as evidence for neither.
ASSESS_DOCUMENT_SLOTS: Final[tuple[str, ...]] = (
    "analytic question",
    "decision context",
    "key judgment",
    "scope",
    "time horizon",
    "evidence base",
    "assumption",
    "boundary",
    "contrary evidence",
    "update indicator",
    "recommendation",
)


def claim_roles(ctx: Any) -> tuple[str, ...]:
    """The normative claim-role enum."""
    defs = ctx.schemas.schema(COMMON_SCHEMA_ID)["$defs"]
    return tuple(defs["claim"]["properties"]["role"]["enum"])


def requirement_slot_names(ctx: Any) -> tuple[str, ...]:
    """The normative requirement-slot names, minus the ones that signal nothing."""
    defs = ctx.schemas.schema(COMMON_SCHEMA_ID)["$defs"]
    return tuple(
        name
        for name in defs["requirement_slots"]["properties"]
        if name not in UNINFORMATIVE_REQUIREMENT_SLOTS
    )


def check_vocabulary_currency(ctx: Any) -> None:
    """Fail loudly if a mapping here names a role the normative package dropped.

    :data:`ROLE_PROFILE` is the one place this module writes normative
    identifiers down, and it does so only to attach a profile and a spec citation
    to each. That is a mapping, not a second definition — but it can still go
    stale, and a stale mapping would quietly stop producing evidence instead of
    failing.
    """
    unknown = sorted(set(ROLE_PROFILE) - set(claim_roles(ctx)))
    if unknown:
        raise UsageError(
            f"ROLE_PROFILE maps {', '.join(unknown)}, which the normative claim-role enum in "
            f"{COMMON_SCHEMA_ID} does not define"
        )


def _label(name: str) -> str:
    """A slot or role identifier as it appears in prose: ``acceptance criterion``."""
    return name.replace("_", " ")


#: Irregular plural surfaces a heading may use, keyed by the singular ending.
#: Everything else takes a plain ``s``. This is surface morphology over an
#: imported term list, not a term list.
_PLURAL_ENDINGS: Final[tuple[tuple[str, str], ...]] = (
    ("criterion", "criteria"),
    ("y", "ies"),
)


def _surface_forms(label: str) -> tuple[str, ...]:
    """The label and its plural, for heading matching.

    Headings pluralize: "## Assumptions", "## Boundaries", "## Acceptance
    criteria". No term is introduced that the normative vocabulary does not
    already contain — only its plural surface.
    """
    if label.endswith("s"):
        return (label,)
    for singular, plural in _PLURAL_ENDINGS:
        if not label.endswith(singular):
            continue
        stem = label[: -len(singular)]
        # `y` pluralizes to `ies` only after a consonant; `day` is `days`.
        if singular == "y" and (not stem or stem[-1] in "aeiou"):
            break
        return (label, stem + plural)
    return (label, label + "s")


def _phrase(phrase: str) -> str:
    """A whitespace-tolerant regex body for a multi-word phrase."""
    return r"\s+".join(re.escape(word) for word in phrase.split())


def _word_pattern(phrases: Iterable[str], *, flags: int = 0) -> re.Pattern[str] | None:
    """One alternation over ``phrases``, longest first so a prefix never wins."""
    ordered = sorted({p for p in phrases if p}, key=lambda p: (-len(p), p))
    if not ordered:
        return None
    body = "|".join(_phrase(p) for p in ordered)
    return re.compile(rf"(?<!\w)(?:{body})(?!\w)", flags)


def _label_pattern(labels: Iterable[str]) -> re.Pattern[str] | None:
    """A line-leading ``Label:`` form, optionally bulleted or emphasised.

    Section 9.2.5 shows exactly this shape for the observation / inference /
    judgment / recommendation chain, and Section 9.3.2's slots are written the
    same way in practice. Requiring the label *position* is what separates a
    structural observation from a bag of words: the bare noun "scope" says
    nothing, whereas a line beginning ``Scope:`` says the author is filling a
    slot.
    """
    ordered = sorted({label for label in labels if label}, key=lambda p: (-len(p), p))
    if not ordered:
        return None
    body = "|".join(_phrase(label) for label in ordered)
    return re.compile(
        rf"^[ \t]*(?:[-*+][ \t]+|\d+\.[ \t]+)?(?:\*\*|__|`)?[ \t]*({body})[ \t]*"
        rf"(?:\*\*|__|`)?[ \t]*:",
        re.IGNORECASE,
    )


# -- scopes -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Scope:
    """One section of one document, in line coordinates.

    ``lines`` holds only the lines a candidate may be raised from: exempt blocks
    and blank lines are dropped, so nothing downstream has to remember to skip
    them, and every retained line keeps its 1-based source number.
    """

    heading_path: tuple[str, ...]
    start_line: int
    end_line: int
    lines: tuple[tuple[int, str], ...]

    @property
    def text(self) -> str:
        return "\n".join(line for _number, line in self.lines)


def _heading_index(text: str, media_type: str) -> list[tuple[int, str, int]]:
    """``(level, title, line)`` per heading, or empty for a document without them."""
    if media_type != "text/markdown":
        return []
    from ..errors import ParseError
    from ..output.parse import headings as _headings
    from ..output.parse import parse_markdown

    try:
        parsed = parse_markdown(text)
    except ParseError as exc:
        raise UsageError(f"source document cannot be parsed: {exc}") from exc
    return _headings(parsed)


def sections(text: str, *, media_type: str = "text/markdown") -> list[Scope]:
    """Split a document into scopes a hypothesis may attach to.

    A scope is a heading and everything under it up to the next heading at the
    same or a shallower level, plus the preamble before the first heading. A
    document with no headings is one scope; it is not thereby exempt from
    review.
    """
    from .context import document_blocks

    exempt: set[int] = set()
    for block in document_blocks(text, media_type=media_type):
        if block.kind in EXEMPT_BLOCK_KINDS:
            exempt.update(range(block.start_line, block.end_line + 1))

    raw = text.split("\n")
    total = len(raw)
    heads = _heading_index(text, media_type)

    def cut(start: int, end: int, path: tuple[str, ...]) -> Scope | None:
        lines = tuple(
            (n, raw[n - 1])
            for n in range(start, min(end, total) + 1)
            if n not in exempt and raw[n - 1].strip()
        )
        return Scope(path, start, end, lines) if lines else None

    if not heads:
        scope = cut(1, total, ())
        return [scope] if scope else []

    out: list[Scope] = []
    first_heading_line = heads[0][2]
    if first_heading_line > 1:
        preamble = cut(1, first_heading_line - 1, ())
        if preamble:
            out.append(preamble)

    stack: list[tuple[int, str]] = []
    for index, (level, title, line) in enumerate(heads):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        end = heads[index + 1][2] - 1 if index + 1 < len(heads) else total
        scope = cut(line, end, tuple(t for _lvl, t in stack))
        if scope:
            out.append(scope)
    return out


# -- evidence ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Evidence:
    """One observation, and the profile it is evidence for."""

    profile: str
    kind: str
    detail: str
    spec_ref: str
    vocabulary_source: str
    occurrences: int
    first_line: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "detail": self.detail,
            "spec_ref": self.spec_ref,
            "vocabulary_source": self.vocabulary_source,
            "occurrences": self.occurrences,
            "first_line": self.first_line,
        }


def _tally(scope: Scope, pattern: re.Pattern[str], *, group: int = 0) -> list[tuple[str, int, int]]:
    """``(surface, occurrences, first_line)`` per distinct surface in ``scope``.

    Surfaces are folded case-insensitively only when the pattern is. A
    case-sensitive pattern keeps ``MUST`` and ``must`` apart, which Section 1.3
    requires: the keywords are normative only in uppercase.

    Returned in document order. :func:`scope_evidence` is the single place the
    emitted order is decided, so a second sort here would be an untestable
    duplicate of that rule rather than a second guarantee.
    """
    fold = bool(pattern.flags & re.IGNORECASE)
    counts: dict[str, int] = {}
    first: dict[str, int] = {}
    for number, line in scope.lines:
        for match in pattern.finditer(line):
            surface = match.group(group)
            key = surface.lower() if fold else surface
            counts[key] = counts.get(key, 0) + 1
            first.setdefault(key, number)
    return [(surface, count, first[surface]) for surface, count in counts.items()]


def _declared_markers(ctx: Any, scope: Scope) -> list[Evidence]:
    """An explicit ``<!-- ats:profile X -->`` declaration inside the scope.

    A declaration is the strongest evidence available and still does not resolve
    the record: a marker written before this corpus existed is a claim by an
    author, not an adjudication.
    """
    out: list[Evidence] = []
    seen: set[str] = set()
    for number, line in scope.lines:
        match = inv.PROFILE_MARKER.match(line.strip())
        if match is None:
            continue
        profile = match.group(1).upper()
        if profile in seen or not is_recordable_profile(ctx, profile):
            continue
        seen.add(profile)
        out.append(
            Evidence(
                profile=profile,
                kind="declared_profile_marker",
                detail=line.strip(),
                spec_ref="ATS-1 9.4",
                vocabulary_source="explicit ats:profile declaration in the document",
                occurrences=1,
                first_line=number,
            )
        )
    return out


def _deontic_evidence(ctx: Any, scope: Scope) -> list[Evidence]:
    """Canonical and noncanonical deontic surfaces, matched case-sensitively."""
    surfaces = [s for s in ctx.lexicon.deontic_surfaces.values() if "<" not in s]
    surfaces.extend(ctx.lexicon.deontic_noncanonical)
    pattern = _word_pattern(surfaces)
    if pattern is None:
        return []
    return [
        Evidence(
            profile="SPECIFY",
            kind="deontic_surface",
            detail=surface,
            spec_ref="ATS-1 9.3.2",
            vocabulary_source="ats_force_lexicon_v1.yaml#/deontic_force",
            occurrences=count,
            first_line=line,
        )
        for surface, count, line in _tally(scope, pattern)
    ]


def _requirement_slot_evidence(ctx: Any, scope: Scope) -> list[Evidence]:
    """Requirement-slot labels, once enough of them appear to be an object."""
    pattern = _label_pattern(_label(name) for name in requirement_slot_names(ctx))
    if pattern is None:
        return []
    found = _tally(scope, pattern, group=1)
    if len(found) < REQUIREMENT_SLOT_QUORUM:
        return []
    return [
        Evidence(
            profile="SPECIFY",
            kind="requirement_slot_label",
            detail=surface,
            spec_ref="ATS-1 9.3.2",
            vocabulary_source=f"{COMMON_SCHEMA_ID}#/$defs/requirement_slots",
            occurrences=count,
            first_line=line,
        )
        for surface, count, line in found
    ]


def _role_label_evidence(ctx: Any, scope: Scope) -> list[Evidence]:
    """Claim-role labels in the ``Judgment:`` form Section 9.2.5 shows."""
    check_vocabulary_currency(ctx)
    by_label = {_label(role): role for role in ROLE_PROFILE}
    pattern = _label_pattern(by_label)
    if pattern is None:
        return []
    out: list[Evidence] = []
    for surface, count, line in _tally(scope, pattern, group=1):
        role = by_label.get(surface.lower())
        if role is None:
            continue
        profile, spec_ref = ROLE_PROFILE[role]
        out.append(
            Evidence(
                profile=profile,
                kind="claim_role_label",
                detail=surface,
                spec_ref=spec_ref,
                vocabulary_source=f"{COMMON_SCHEMA_ID}#/$defs/claim/properties/role",
                occurrences=count,
                first_line=line,
            )
        )
    return out


def heading_vocabulary(ctx: Any) -> dict[str, tuple[str, str, str, str]]:
    """``surface form -> (profile, spec_ref, vocabulary_source, term)`` for headings.

    Three normative sources contribute: the claim-role enum, the requirement
    slots of Section 9.3.2, and the ASSESS document-level slots of Section
    9.2.2. A form claimed by more than one profile is then **dropped**, on the
    same principle that keeps a profile-neutral claim role out of
    :data:`ROLE_PROFILE`: "both profiles name it" is not evidence for either.
    That is what removes "Scope", which Section 9.2.2 and Section 9.3.2 both
    name.

    A heading is one term, so it can never show the multi-slot requirement
    *object* shape that :data:`REQUIREMENT_SLOT_QUORUM` looks for in body text.
    Dropping neutral forms is what keeps a single heading term from asserting
    more than one term can.
    """
    claimed: dict[str, set[str]] = {}
    entries: dict[str, tuple[str, str, str, str]] = {}

    def offer(form: str, profile: str, spec_ref: str, source: str, term: str) -> None:
        claimed.setdefault(form, set()).add(profile)
        entries.setdefault(form, (profile, spec_ref, source, term))

    for role, (profile, spec_ref) in ROLE_PROFILE.items():
        for form in _surface_forms(_label(role)):
            offer(form, profile, spec_ref, f"{COMMON_SCHEMA_ID}#/$defs/claim/properties/role", role)
    for name in requirement_slot_names(ctx):
        for form in _surface_forms(_label(name)):
            offer(
                form,
                "SPECIFY",
                "ATS-1 9.3.2",
                f"{COMMON_SCHEMA_ID}#/$defs/requirement_slots",
                name,
            )
    for slot in ASSESS_DOCUMENT_SLOTS:
        for form in _surface_forms(slot):
            offer(
                form,
                "ASSESS",
                "ATS-1 9.2.2",
                "ATS-1_SPEC.md Section 9.2.2 document-level slot list",
                slot,
            )

    return {form: entry for form, entry in entries.items() if len(claimed[form]) == 1}


def _heading_evidence(ctx: Any, scope: Scope) -> list[Evidence]:
    """A heading naming a slot or role that belongs to exactly one profile.

    Only the scope's own innermost heading is read. An ancestor heading governs a
    larger region and its evidence belongs to that region's own scope, which is
    generated separately; crediting it here would smear one section's structure
    across all of its siblings.
    """
    if not scope.heading_path:
        return []
    heading = scope.heading_path[-1]

    by_form = heading_vocabulary(ctx)
    pattern = _word_pattern(by_form, flags=re.IGNORECASE)
    if pattern is None:
        return []
    out: list[Evidence] = []
    seen: set[str] = set()
    for match in pattern.finditer(heading):
        form = match.group(0).lower()
        if form in seen:
            continue
        seen.add(form)
        profile, spec_ref, source, term = by_form[form]
        out.append(
            Evidence(
                profile=profile,
                kind="heading_role_term",
                detail=f"{heading} ({term})",
                spec_ref=spec_ref,
                vocabulary_source=source,
                occurrences=1,
                first_line=scope.start_line,
            )
        )
    return out


def _likelihood_evidence(ctx: Any, scope: Scope) -> list[Evidence]:
    """Words of estimative probability. Section 9.2.4 makes likelihood an ASSESS slot."""
    phrases = list(ctx.lexicon.wep_phrases) + list(ctx.lexicon.wep_aliases)
    pattern = _word_pattern(phrases, flags=re.IGNORECASE)
    if pattern is None:
        return []
    return [
        Evidence(
            profile="ASSESS",
            kind="likelihood_term",
            detail=surface,
            spec_ref="ATS-1 9.2.4",
            vocabulary_source="ats_force_lexicon_v1.yaml#/likelihood",
            occurrences=count,
            first_line=line,
        )
        for surface, count, line in _tally(scope, pattern)
    ]


def _confidence_evidence(ctx: Any, scope: Scope) -> list[Evidence]:
    """An assessment-confidence level attached to the word ``confidence``.

    The levels come from the lexicon and the slot name from the normative
    ``assessment_confidence`` definition. Only the adjacency of the two belongs
    to this module: a bare ``high`` is not evidence of anything, whereas a
    lexicon level sitting against the slot name is the surface Section 9.2.4
    asks for.
    """
    levels = "|".join(re.escape(level) for level in ctx.lexicon.confidence_levels)
    if not levels:
        return []
    pattern = re.compile(
        rf"(?<!\w)(?:(?:{levels})\s+confidence|confidence\s*(?:is|:|=)\s*(?:{levels}))(?!\w)",
        re.IGNORECASE,
    )
    return [
        Evidence(
            profile="ASSESS",
            kind="assessment_confidence_term",
            detail=surface,
            spec_ref="ATS-1 9.2.4",
            vocabulary_source=(
                "ats_force_lexicon_v1.yaml#/assessment_confidence with the slot name from "
                f"{COMMON_SCHEMA_ID}#/$defs/assessment_confidence"
            ),
            occurrences=count,
            first_line=line,
        )
        for surface, count, line in _tally(scope, pattern)
    ]


def _evidential_evidence(ctx: Any, scope: Scope) -> list[Evidence]:
    """Graded evidence-to-claim language. Section 9.2.6 is an ASSESS obligation."""
    phrases = [
        term["phrase"]
        for term in ctx.lexicon.document["evidential_force"]["terms"]
        if term.get("phrase")
    ]
    pattern = _word_pattern(phrases, flags=re.IGNORECASE)
    if pattern is None:
        return []
    return [
        Evidence(
            profile="ASSESS",
            kind="evidential_force_term",
            detail=surface,
            spec_ref="ATS-1 9.2.6",
            vocabulary_source="ats_force_lexicon_v1.yaml#/evidential_force",
            occurrences=count,
            first_line=line,
        )
        for surface, count, line in _tally(scope, pattern)
    ]


#: Every matcher, in the order their evidence is collected. Causal force is
#: deliberately absent: Section 8.1 makes it one of five force axes that both
#: profiles carry, so a causal verb discriminates nothing.
MATCHERS: Final[tuple[Any, ...]] = (
    _declared_markers,
    _deontic_evidence,
    _requirement_slot_evidence,
    _role_label_evidence,
    _heading_evidence,
    _likelihood_evidence,
    _confidence_evidence,
    _evidential_evidence,
)

#: Every vocabulary a candidate may be raised from, recorded on each record. A
#: term outside these is not evidence.
EVIDENCE_SOURCES: Final[tuple[str, ...]] = (
    "ats_force_lexicon_v1.yaml#/likelihood",
    "ats_force_lexicon_v1.yaml#/assessment_confidence",
    "ats_force_lexicon_v1.yaml#/evidential_force",
    "ats_force_lexicon_v1.yaml#/deontic_force",
    f"{COMMON_SCHEMA_ID}#/$defs/claim/properties/role",
    f"{COMMON_SCHEMA_ID}#/$defs/requirement_slots",
    "ATS-1_SPEC.md Section 9.2.2 document-level slot list",
    "explicit ats:profile declaration in the document",
)


def scope_evidence(ctx: Any, scope: Scope) -> list[Evidence]:
    """Every admissible observation in one scope, deterministically ordered."""
    found: list[Evidence] = []
    for matcher in MATCHERS:
        found.extend(matcher(ctx, scope))
    found.sort(key=lambda e: (e.profile, e.kind, e.detail, e.first_line))
    return found


def candidate_profiles(ctx: Any, scope: Scope) -> list[dict[str, Any]]:
    """The candidate-profile entries for one scope.

    Every evidence-backed profile is emitted with status ``hypothesis``. None is
    promoted over another: this module has no authority to rank, and counting
    cues is not a ranking anyone could defend. An empty list means nothing
    admissible was found, which :func:`build_profile_hypotheses` reports as an
    examined scope without evidence rather than as an absent profile.
    """
    grouped: dict[str, list[Evidence]] = {}
    for evidence in scope_evidence(ctx, scope):
        grouped.setdefault(evidence.profile, []).append(evidence)
    return [
        {
            "profile": profile,
            "basis": [e.to_dict() for e in grouped[profile]],
            "status": "hypothesis",
            "conformance_claim_permitted": may_carry_conformance_claim(ctx, profile),
        }
        for profile in sorted(grouped)
    ]


# -- records ----------------------------------------------------------------


def profile_hypothesis(
    ctx: Any,
    *,
    source_artifact_id: str,
    path: str,
    revision: str,
    scope: Scope,
    candidates: Sequence[Mapping[str, Any]],
    repository_group: str | None = None,
    context_bundle_id: str | None = None,
    source_sha256: str | None = None,
    authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one content-addressed ``ProfileHypothesisV1``.

    ``decision`` is fixed at ``REVIEW_REQUIRED`` and takes no parameter. There is
    deliberately no way to ask this constructor for a resolved record: a caller
    that wants one has to write the annotator identity, timestamp, and rationale
    itself, which is the point (Section 13.7).
    """
    scope_block: dict[str, Any] = {
        "heading_path": list(scope.heading_path),
        "start_line": scope.start_line,
        "end_line": scope.end_line,
    }
    if source_sha256 is not None:
        scope_block["source_sha256"] = source_sha256

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_artifact_id": source_artifact_id,
        "path": path,
        "revision": revision,
        "repository_group": repository_group,
        "context_bundle_id": context_bundle_id,
        "scope": scope_block,
        "candidate_profiles": [dict(c) for c in candidates],
        "decision": {"state": "REVIEW_REQUIRED"},
        "authority": dict(authority) if authority is not None else None,
        "generator": {
            "generator_id": GENERATOR_ID,
            "spec_version": ctx.spec_version,
            "lexicon_version": ctx.lexicon.version,
            "evidence_sources": list(EVIDENCE_SOURCES),
            "refusals": _refusal_records(),
        },
    }
    return rec.address(record)


def document_hypotheses(
    ctx: Any,
    text: str,
    *,
    source_artifact_id: str,
    path: str,
    revision: str,
    media_type: str = "text/markdown",
    repository_group: str | None = None,
    source_sha256: str | None = None,
    authority: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """``(records, scopes_examined)`` for one document's text.

    A scope with no admissible evidence yields no record. The examined count is
    returned beside the records so a caller can report how much of the document
    produced nothing, rather than letting the silence disappear.
    """
    scopes = sections(text, media_type=media_type)
    out: list[dict[str, Any]] = []
    for scope in scopes:
        candidates = candidate_profiles(ctx, scope)
        if not candidates:
            continue
        out.append(
            profile_hypothesis(
                ctx,
                source_artifact_id=source_artifact_id,
                path=path,
                revision=revision,
                scope=scope,
                candidates=candidates,
                repository_group=repository_group,
                source_sha256=source_sha256,
                authority=authority,
            )
        )
    return out, len(scopes)


def build_profile_hypotheses(
    ctx: Any,
    inventory: Mapping[str, Any],
    *,
    repo_path: str | Path | None = None,
    authority_overlay: str | Path | None = "corpus/authority",
) -> dict[str, Any]:
    """Generate profile hypotheses for every artifact in ``inventory``.

    Returns ``{"hypotheses", "scopes_examined", "scopes_with_evidence",
    "scopes_without_evidence", "skipped", "refusals"}``. Authority is resolved
    per path for :data:`AUTHORITY_USE`, and an unpermitted path is skipped with
    the resolution's own basis attached rather than mined under a default.
    """
    repository = repo_path or inventory.get("repository")
    if not repository:
        raise UsageError(
            "profile hypotheses are cut from the exact bytes at the pinned revision, so "
            "generating without the repository is refused"
        )
    declaration = AuthorityDeclaration.load(
        Path(repository),
        overlay_dir=Path(authority_overlay) if authority_overlay else None,
    )

    hypotheses: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    examined = 0

    for artifact in inventory.get("artifacts", ()):
        path = artifact["path"]
        resolution = declaration.resolve(AUTHORITY_USE, path)
        if not resolution.permitted:
            skipped.append(
                {
                    "path": path,
                    "reason": "authority",
                    "detail": f"{AUTHORITY_USE} resolved to {resolution.value}",
                    "basis": list(resolution.basis),
                }
            )
            continue
        try:
            text = inv.artifact_text(repository, artifact)
            records, scopes = document_hypotheses(
                ctx,
                text,
                source_artifact_id=artifact["artifact_id"],
                path=path,
                revision=artifact["revision"],
                media_type=artifact.get("media_type", "text/markdown"),
                repository_group=artifact.get("repository_group"),
                source_sha256=artifact.get("content_sha256"),
                authority=resolution.to_dict(),
            )
        except UsageError as exc:
            skipped.append({"path": path, "reason": "unreadable", "detail": str(exc)})
            continue
        examined += scopes
        hypotheses.extend(records)

    hypotheses.sort(key=lambda h: (h["path"], h["scope"]["start_line"], h["hypothesis_id"]))
    return {
        "hypotheses": hypotheses,
        "scopes_examined": examined,
        "scopes_with_evidence": len(hypotheses),
        "scopes_without_evidence": examined - len(hypotheses),
        "skipped": skipped,
        "refusals": _refusal_records(),
    }

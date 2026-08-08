"""A sampling frame over caller-supplied context bundles.

The frame answers which spans an annotation round may adjudicate, with
selection balanced on how a span was surfaced rather than on its expected
label. It keeps source grouping and authority checks structural.

**Balancing is on mechanism, never on expected outcome.** Every stratum here
names how a span was *surfaced*: a declared vocabulary matched it, a revision
moved it on a protected axis, a rule that never receives a candidate was
probed for, or nothing at all pointed at it. No stratum names a presumed
conformance verdict, because a frame balanced by expected label decides the
question the annotation exists to answer (spec Sections 17.5, 17.8). The
stratum ``surface_cue_hard_negative`` is the sharp case: it selects a cue in a
*configuration* ATS-1 exempts or that `ATS_CORPUS_PROTOCOL_V0.md` CP-42 names
as false-positive pressure, and it does **not** assert that the span conforms.
An annotator may well find a violation in it, and that outcome is a result
rather than a defect of the frame.

**The random control is load-bearing.** ``low_signal_random_control`` draws
from authorised documents that produced no candidate at all (CP-37). Without
it there is no denominator: candidate density cannot be read as enrichment
relative to ordinary prose if ordinary prose was never sampled.

**A miner prediction never reaches a blind annotator.** The annotator-facing
projection is an allow-list (:data:`ANNOTATOR_VISIBLE_FIELDS`), and
``blinding.withheld_from_annotator`` is *derived* by subtracting that list from
the schema's own selection properties. A field added to the schema is withheld
until somebody deliberately admits it, so the withholding cannot rot into a
stale deny-list.

Two governance properties are structural rather than checked afterwards. Only
repositories whose overlay resolves ``human_annotation`` and
``candidate_mining`` permitted contribute a pool at all, so an unauthorised
repository cannot appear in a selection by any path (Sections 16.9, 17.13).
And a constraint the corpus cannot meet is recorded with ``satisfied: false``
and ``unsatisfiable: true`` rather than quietly relaxed or forced — ADR-0002
applied to sampling: a stratum or constraint that cannot be evaluated is
reported unavailable, never satisfied.

Determinism is a property the frame is disputable through: selection is a pure
function of the pinned corpus and ``policy.seed``, so a rebuilt frame is
byte-identical and a different seed is a visibly different draw.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Mapping, MutableSequence, Sequence

from ..canonical import content_hash, seal, sha256_hex
from ..errors import UsageError
from ..rules.deterministic.quantity import BOUNDARY_TERMS

# Imported rather than restated. The acronym shape is a detector's own
# vocabulary and the leakage closure is a splitter's own algorithm; a second
# spelling of either is a second answer that can drift from the first, which is
# exactly what these probes and this frame are supposed to be traceable to.
from ..rules.deterministic.terminology import _ACRONYM as ACRONYM_SHAPE
from . import inventory as inv
from . import split as sp
from .authority import AuthorityDeclaration, require_provenance
from .context import Block, build_context_bundle, document_blocks
from .mine import REVISION_BASIS, require_inventory_binding

SCHEMA_ID: Final[str] = "ats_sampling_frame_v1.schema.json"
SCHEMA_VERSION: Final[str] = "ats.sampling_frame.v1"

#: The ``ats-`` prefix a frame identifier carries. :func:`ats.corpus.records.address`
#: is the repository's content-addressing convention, and it is deliberately not
#: reused here: ``RECORD_IDENTITY`` enumerates the five normative corpus record
#: types plus the splits and hypotheses derived from them, and a sampling frame
#: is a governance artifact rather than a corpus record. Adding it there would
#: widen what ``records.validate_records`` claims to police.
ID_PREFIX: Final[str] = "ats-frame-sha256"

#: The uses every selected bundle had to have been authorised for. Annotating a
#: span is a use in its own right, and inventorying a document is not authority
#: to put it in front of a person (Section 16.9). ``candidate_mining`` is
#: required alongside it because every stratum here is built from mined spans.
REQUIRED_USES: Final[tuple[str, ...]] = ("human_annotation", "candidate_mining")


@dataclass(frozen=True, slots=True)
class Stratum:
    """One sampling mechanism, its target, and why the round needs it."""

    name: str
    target: int
    rationale: str


#: The five strata, in the order they are drawn. Scarce pools draw first,
#: because every selection consumes a whole leakage component (see
#: :func:`leakage_groups`): letting the 7,500-span natural pool draw first would
#: spend the components the 29-span quoted-material pool needs.
STRATA: Final[tuple[Stratum, ...]] = (
    Stratum(
        name="surface_cue_hard_negative",
        target=60,
        rationale=(
            "A declared cue in a configuration that ATS-1 exempts or that CP-42 names as "
            "false-positive pressure: quoted material (CP-42 HN-6, ATS-1 5.6), a relative-time "
            "expression with an absolute anchor in its own block (HN-9, ATS-1 10.11), and a cue "
            "inside a long dense prose paragraph (HN-1, ATS-1 10.13/10.14 impose no global "
            "sentence-length limit). The stratum names the configuration, not a label: whether "
            "the span conforms is the annotator's judgment, and a violation found here is a "
            "result rather than a defect. Three of the twelve CP-42 classes are reachable from "
            "this miner and corpus; the other nine are recorded as unreachable in "
            "SAMPLING_FRAME.md rather than approximated by inventing a cue."
        ),
    ),
    Stratum(
        name="revision_derived_candidate",
        target=30,
        rationale=(
            "A span a revision moved on one of the four force axes Section 11.3.1 protects, "
            "carrying ats.corpus.mine's revision_force_delta basis. The basis establishes that "
            "the text moved; it establishes nothing normative, and its "
            "normative_interpretation is 'unresolved' at every construction site. Selected so "
            "the round can ask whether an edit that changed force also changed conformance -- "
            "a question no single-revision stratum can pose."
        ),
    ),
    Stratum(
        name="low_signal_random_control",
        target=30,
        rationale=(
            "Caller-supplied documents that produced no candidate from any configured "
            "signal, sampled at a seed-chosen prose block. This is the denominator, "
            "not filler: candidate density means nothing as enrichment unless prose "
            "the miner ignored is adjudicated on the same protocol. A frame without "
            "this stratum can report precision within the cue but cannot estimate "
            "what it missed."
        ),
    ),
    Stratum(
        name="zero_candidate_rule_probe",
        target=30,
        rationale=(
            "Documents that a caller identifies as plausibly relevant to a rule with "
            "zero candidates, sampled at a surface block. A probe carries no "
            "candidate_rule_ids because no detector flagged it; the rule travels in "
            "candidate_source. Rules requiring a source/output pair remain unavailable "
            "when the caller supplies no such related artifacts. That gap is stated "
            "rather than papered over."
        ),
    ),
    Stratum(
        name="natural_rule_candidate",
        target=150,
        rationale=(
            "A span whose surface carries one of the eleven declared vocabularies "
            "ats.corpus.mine.build_signals assembles from the force lexicon and the lists "
            "Section 9.3.7/10.11/10.20/10.21 enumerate verbatim. The largest stratum because it "
            "is the one the deterministic layer will actually be measured against; it is also "
            "the most biased, which is why the four other strata exist."
        ),
    ),
)

STRATUM_NAMES: Final[tuple[str, ...]] = tuple(s.name for s in STRATA)

#: Selection fields an annotator may see. This is an allow-list, and
#: :func:`withheld_fields` derives the withheld set by subtracting it from the
#: schema's own selection properties, so a field added to the schema is withheld
#: by default. A deny-list would silently admit it.
#:
#: ``review_state`` is visible on purpose. Section 17.4 keeps merge state as
#: retained *context* and forbids reading conformance out of it, and the
#: refusal travels with the candidate; hiding the context would not strengthen
#: the refusal, it would remove information the annotator needs to judge a
#: reverted document at all.
ANNOTATOR_VISIBLE_FIELDS: Final[tuple[str, ...]] = (
    "bundle_id",
    "source_artifact_id",
    "repository",
    "document_family",
    "domain",
    "split_group",
    "content_sha256",
    "near_duplicate_cluster",
    "template_family",
    "review_state",
    "profile_hypotheses",
)

#: Why the withheld fields are withheld. Each names a prediction or a design
#: fact about the draw, and every one of them would anchor the judgment it is
#: supposed to be tested against (Sections 13.2, 16.5, 17.8).
BLINDING_RATIONALE: Final[str] = (
    "A candidate is a vocabulary match, not a finding, and a stratum is a sampling mechanism, "
    "not a label. Showing an annotator that a span was drawn as a hard negative, or which rules "
    "a detector flagged, or that a second annotator will see the same span, replaces an "
    "independent judgment with agreement to a machine's guess -- and the resulting agreement "
    "figure would then measure the anchoring rather than the rule. The annotator-facing view is "
    "built by allow-list projection, so these fields are absent by construction rather than "
    "stripped afterwards."
)

#: The annotator-facing projection's own schema version. It is not a normative
#: ATS schema and says so: the view is a derived, lossy read of the frame.
VIEW_SCHEMA_VERSION: Final[str] = "x-ats-repo.sampling_frame_annotator_view.v0"

# -- hard-negative configurations -------------------------------------------
#
# Each class below is a CP-42 row that this miner and this corpus can actually
# produce. A class whose cue the miner never nominates (CP-42 HN-7's lowercase
# `should`, for instance: `deontic-surface` draws its phrases from the lexicon's
# canonical uppercase surfaces, so a lowercase deontic never becomes a
# candidate) is absent from this tuple rather than approximated, because
# approximating it means inventing a vocabulary RULE_COVERAGE.md forbids adding.

#: The smallest paragraph, in characters, that counts as long dense prose, and
#: the fewest sentence-terminated segments it must contain. Repository policy,
#: not an ATS-1 threshold: Section 10.13 imposes no global sentence-word limit
#: and Section 10.14 governs dependency depth instead, so there is no normative
#: number to quote here. The pair is declared so the frame can be disputed on
#: it.
LONG_PROSE_CHARS: Final[int] = 600
LONG_PROSE_SENTENCES: Final[int] = 3

#: An absolute date or year that can anchor a relative-time expression, so
#: Section 10.11's "resolution MAY come from an anchor in context" is observably
#: available in the span's own block.
_ANCHOR = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b|\bQ[1-4]\s*(?:19|20)\d{2}\b|\b(?:19|20)\d{2}\b")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def long_dense_prose(block: Block) -> bool:
    """Whether ``block`` is a long, multi-sentence prose paragraph.

    Length and sentence count are observable; coherence and technical validity
    are not, and this function does not claim them. It selects the false-
    positive *pressure* -- a cue buried in dense prose that a length- or
    reference-sensitive detector is most likely to misfire on -- and leaves the
    verdict to the annotator.
    """
    if block.kind != "paragraph" or len(block.text) < LONG_PROSE_CHARS:
        return False
    sentences = [s for s in _SENTENCE_SPLIT.split(block.text) if s.strip()]
    return len(sentences) >= LONG_PROSE_SENTENCES


def hard_negative_class(candidate: Mapping[str, Any], block: Block) -> str | None:
    """The CP-42 class ``candidate`` sits in, or ``None``.

    Precedence runs scarcest first. Quoted material is the strongest claim
    available -- Section 5.6 exempts quoted source text from surface rules
    outright -- and it is also the rarest configuration in this corpus, so a
    span that is both quoted and long is recorded as quoted.
    """
    if candidate["block"]["kind"] == "block_quote":
        return "HN-6_quoted_material"
    if candidate["signal"]["signal_id"] == "relative-time-expression" and _ANCHOR.search(block.text):
        return "HN-9_anchored_relative_time"
    if long_dense_prose(block):
        return "HN-1_long_dense_prose"
    return None


#: The CP-42 classes this frame can build, scarcest first, with the ATS-1
#: section that makes the cue non-forceful in that configuration.
HARD_NEGATIVE_CLASSES: Final[tuple[tuple[str, str], ...]] = (
    ("HN-6_quoted_material", "ATS-1 5.6: quoted source text MAY be exempt from surface rules"),
    ("HN-9_anchored_relative_time", "ATS-1 10.11: resolution MAY come from an anchor in context"),
    (
        "HN-1_long_dense_prose",
        "ATS-1 10.13/10.14: no global sentence-word limit; dependency depth is what is governed",
    ),
)

# -- zero-candidate rule probes ---------------------------------------------

#: The probe vocabularies are kept beside the frame logic so callers can
#: explain which surfaces a zero-candidate probe exercises.
#:
#: These are **not** rule vocabularies and they nominate no candidate. A phrase
#: probe can show a construct is present; it cannot show a rule is violated
#: (RULE_COVERAGE.md, "Method, and what it can and cannot show"). They select
#: which document to put in front of an annotator, and nothing else. Two
#: vocabularies are imported from the detectors instead of restated --
#: :data:`ats.rules.deterministic.quantity.BOUNDARY_TERMS` and terminology's
#: acronym shape -- so those have one spelling in the repository.
FORECAST_CUES: Final[tuple[str, ...]] = ("probabl", "likely", "unlikely", "forecast")
RESOLUTION_HORIZON_CUES: Final[tuple[str, ...]] = (
    "resolution date",
    "resolves on",
    "resolves by",
    "time horizon",
    "resolution_source",
)
REVISION_LANGUAGE: Final[tuple[str, ...]] = (
    "would change",
    "would revise",
    "would invalidate",
    "invalidated if",
    "invalidated by",
    "falsif",
    "revisit if",
    "kill criteria",
    "reversal indicator",
)
CONTRARY_EVIDENCE_LANGUAGE: Final[tuple[str, ...]] = (
    "contrary evidence",
    "counterexample",
    "alternative explanation",
    "competing hypothes",
    "steelman",
    "disconfirm",
)
_GLOSSARY_HEADING = re.compile(r"glossar|definitions|terminology", re.IGNORECASE)
_SENTENCE_INITIAL_PRONOUN = re.compile(
    r"(?:\A|(?<=[.!?]\s)|(?<=\n))(This|That|These|Those|It|They)\b"
)
_BOUNDARY_TERM = re.compile(
    "|".join(r"(?<!\w)" + re.escape(t) + r"(?!\w)" for t in BOUNDARY_TERMS), re.IGNORECASE
)
#: Paragraphs a document needs before "one conceptual move per paragraph" has
#: anything to be judged over. RULE_COVERAGE.md counts 172 paragraphs in the
#: densest authorised document; twenty is a floor, declared as policy.
MANY_PARAGRAPHS: Final[int] = 20


@dataclass(frozen=True, slots=True)
class Probe:
    """A zero-candidate rule and the surface that makes a document worth reading.

    ``basis`` names what was looked for, and ``evidence`` cites where
    RULE_COVERAGE.md reports how many authorised documents carry it, so a probe
    is traceable to the measurement that motivated it rather than to a hunch.
    """

    rule_id: str
    basis: str
    evidence: str


#: Probeable zero-candidate rules and the deterministic surface that can place a
#: caller-supplied artifact into a review stratum. These rationales describe
#: instrument mechanics only; they contain no claims about an omitted corpus.
PROBES: Final[tuple[Probe, ...]] = (
    Probe(
        "ATS-TERM-001",
        "glossary_shaped_heading",
        "a glossary-shaped heading is only a review cue; canonical_term still requires "
        "caller-supplied vocabulary context (context_unavailable)",
    ),
    Probe(
        "ATS-TERM-002",
        "revision_predecessor_available",
        "the construct is recoverable only when the caller supplies a declared predecessor "
        "revision (no_deterministic_surface_signal)",
    ),
    Probe(
        "ATS-TERM-003",
        "acronym_shape_present",
        "an acronym-shaped token is not rule-specific and no deterministic signal names the "
        "intended terminology relation (miner_lacks_cue)",
    ),
    Probe(
        "ATS-REF-001",
        "sentence_initial_pronoun",
        "a sentence-initial pronoun is a review cue, but this implementation has no syntactic "
        "resolver for its referent (no_deterministic_surface_signal)",
    ),
    Probe(
        "ATS-NUM-002",
        "boundary_comparator_present",
        "a boundary comparator is not rule-specific and no deterministic signal establishes "
        "the required quantitative relation (miner_lacks_cue)",
    ),
    Probe(
        "ATS-TIME-001",
        "forecast_cue_without_horizon",
        "a forecast cue can nominate a review span, but absence of a resolution horizon is not "
        "proved by that cue alone (no_deterministic_surface_signal)",
    ),
    Probe(
        "ATS-EPI-006",
        "revision_or_reversal_language",
        "revision language can nominate a review span; the violating absence remains "
        "unmeasurable from prose alone (no_deterministic_surface_signal)",
    ),
    Probe(
        "ATS-EVID-003",
        "contrary_evidence_language",
        "contrary-evidence language can nominate a review span, but the required treatment "
        "cannot be inferred from lexical presence or absence alone "
        "(no_deterministic_surface_signal)",
    ),
    Probe(
        "ATS-DISC-001",
        "leading_prose_block",
        "no deterministic surface separates leading with the answer from leading with "
        "background (no_deterministic_surface_signal)",
    ),
    Probe(
        "ATS-DISC-002",
        "many_paragraph_document",
        "TextIR models sections and claims rather than paragraph discourse structure "
        "(no_deterministic_surface_signal)",
    ),
    Probe(
        "ATS-REQ-001",
        "canonical_uppercase_deontic",
        "canonical deontic prose can nominate a review span, but profile applicability is "
        "caller-supplied (corpus_lacks_profile)",
    ),
    Probe(
        "ATS-REQ-002",
        "canonical_uppercase_deontic",
        "as ATS-REQ-001: deontic prose is only a cue and profile applicability is "
        "caller-supplied (corpus_lacks_profile)",
    ),
    Probe(
        "ATS-REQ-003",
        "canonical_uppercase_deontic",
        "as ATS-REQ-001: deontic prose is only a cue and profile applicability is "
        "caller-supplied (corpus_lacks_profile)",
    ),
)

#: Rules that require a declared transformation pair rather than a lexical
#: probe. Callers must supply such a pair or use authored fixtures; the
#: instrument never manufactures one to fill a stratum.
UNPROBEABLE_RULES: Final[tuple[tuple[str, str], ...]] = (
    (
        "ATS-PRES-001",
        "requires source and output IR, a retention contract, authorisations, and a declared "
        "transformation relation; without that pair, use an authored fixture rather than an "
        "inferred sample",
    ),
    (
        "ATS-PRES-002",
        "as ATS-PRES-001: requires a declared transformation pair and cannot be probed from "
        "an unrelated document",
    ),
)


def _uppercase_deontic(ctx: Any) -> re.Pattern[str]:
    """The canonical deontic surfaces, from the lexicon rather than restated."""
    surfaces = sorted(
        {s for s in ctx.lexicon.deontic_surfaces.values() if s.isupper() and "<" not in s},
        key=len,
        reverse=True,
    )
    return re.compile("|".join(r"(?<!\w)" + re.escape(s) + r"(?!\w)" for s in surfaces))


def probe_span(
    ctx: Any,
    probe: Probe,
    *,
    artifact: Mapping[str, Any],
    text: str,
    blocks: Sequence[Block],
) -> tuple[int, int] | None:
    """The span a probe points at, or ``None`` when the document has no surface.

    A probe that finds nothing returns ``None`` rather than falling back to the
    document's opening: a probe with a silent fallback would report coverage for
    a rule whose surface the document never carried (ADR-0002).
    """
    prose = [b for b in blocks if b.kind != "code_block"]
    if not prose:
        return None

    if probe.basis == "leading_prose_block":
        first = next((b for b in prose if b.kind == "paragraph"), prose[0])
        return (first.start, first.end)
    if probe.basis == "many_paragraph_document":
        paragraphs = [b for b in prose if b.kind == "paragraph"]
        if len(paragraphs) < MANY_PARAGRAPHS:
            return None
        widest = max(paragraphs, key=lambda b: (len(b.text), -b.start))
        return (widest.start, widest.end)
    if probe.basis == "revision_predecessor_available":
        git = (artifact.get("extensions") or {}).get("x-ats-repo-git") or {}
        if (git.get("previous_edit") or {}).get("availability") != "present":
            return None
        first = next((b for b in prose if b.kind == "paragraph"), prose[0])
        return (first.start, first.end)
    if probe.basis == "glossary_shaped_heading":
        for block in prose:
            if block.kind == "heading" and _GLOSSARY_HEADING.search(block.text):
                return (block.start, block.end)
        return None

    lowered = text.lower()
    if probe.basis == "forecast_cue_without_horizon":
        if any(h in lowered for h in RESOLUTION_HORIZON_CUES):
            return None
        return _first_in_prose(prose, tuple(FORECAST_CUES))
    if probe.basis == "revision_or_reversal_language":
        return _first_in_prose(prose, REVISION_LANGUAGE)
    if probe.basis == "contrary_evidence_language":
        return _first_in_prose(prose, CONTRARY_EVIDENCE_LANGUAGE)
    if probe.basis == "acronym_shape_present":
        return _first_match_in_prose(prose, ACRONYM_SHAPE)
    if probe.basis == "boundary_comparator_present":
        return _first_match_in_prose(prose, _BOUNDARY_TERM)
    if probe.basis == "sentence_initial_pronoun":
        return _first_match_in_prose(prose, _SENTENCE_INITIAL_PRONOUN)
    if probe.basis == "canonical_uppercase_deontic":
        return _first_match_in_prose(prose, _uppercase_deontic(ctx))
    raise UsageError(f"probe basis {probe.basis!r} has no implementation")


def _first_in_prose(prose: Sequence[Block], needles: Sequence[str]) -> tuple[int, int] | None:
    """The earliest case-insensitive substring hit, in the earliest prose block."""
    for block in prose:
        lowered = block.text.lower()
        hits = [(lowered.find(n), n) for n in needles if n in lowered]
        if hits:
            offset, needle = min(hits)
            return (block.start + offset, block.start + offset + len(needle))
    return None


def _first_match_in_prose(
    prose: Sequence[Block], pattern: re.Pattern[str]
) -> tuple[int, int] | None:
    """The earliest regex match, in the earliest prose block."""
    for block in prose:
        match = pattern.search(block.text)
        if match:
            return (block.start + match.start(), block.start + match.end())
    return None


# -- authority --------------------------------------------------------------


def resolve_annotation_authority(
    repositories: Sequence[Mapping[str, Any]],
    overlay_dir: str | Path,
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Which repositories may contribute a bundle, resolved per use.

    Resolution is per repository *and* per artifact path: an overlay excludes
    ``generated/*`` and similar trees, and a document outside the declared
    include set resolves ``unknown`` even though its repository is declared.
    Both answers are needed, so this returns the declaration itself alongside
    the verdict.

    A repository whose declaration does not permit **every** use in
    :data:`REQUIRED_USES` contributes nothing. ``defer`` is not a smaller
    ``allow``: it is an explicit refusal to decide, and every one of these six
    overlays defers ``model_training`` -- which is why this frame authorises an
    annotation round and not a training corpus.

    Every authorised row carries the declaration's provenance, not just its
    permission. All six of these declarations are operator overlays, and a
    frame that recorded only "authorised" would read as though six repository
    owners had declared in place. None has: the permission is the operator's
    account of its own material from outside the repository, and it expires.

    ``now`` is the clock ``review_after`` is checked against. Without it a
    lapsed overlay would keep authorising selections, which is the failure
    ``review_after`` exists to prevent; the frame builder passes the run clock.
    """
    overlay = Path(overlay_dir)
    authorised: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    declarations: dict[str, AuthorityDeclaration] = {}
    for row in repositories:
        name = str(row["repository"])
        candidate = overlay / f"{name}.json"
        if candidate.is_file():
            # ``from_file`` reads the overlay once and records the digest of
            # those exact bytes, so the permission this row reports and the
            # declaration digest it carries cannot describe two different
            # revisions of the file.
            declaration = AuthorityDeclaration.from_file(
                candidate, repository=name, location="pilot_overlay"
            )
            declaration_sha256 = declaration.source_sha256
        else:
            declaration = AuthorityDeclaration.undeclared(name)
            declaration_sha256 = None
        blocked = [
            f"{use}={declaration.resolve(use, now=now).value}"
            for use in REQUIRED_USES
            if not declaration.resolve(use, now=now).permitted
        ]
        if blocked:
            excluded.append(
                {
                    "repository": name,
                    "reason": (
                        f"required use(s) not permitted: {', '.join(blocked)}; an unknown or "
                        "deferred use is not an authorised one"
                    ),
                }
            )
            continue
        declarations[name] = declaration
        entry: dict[str, Any] = {
            "repository": name,
            "revision": str(row["revision"]),
            **declaration.provenance(now),
        }
        require_provenance(entry, where=f"the sampling frame's authority row for {name}")
        if declaration_sha256:
            entry["declaration_sha256"] = declaration_sha256
        authorised.append(entry)
    return {
        "authorised": sorted(authorised, key=lambda e: e["repository"]),
        "excluded": sorted(excluded, key=lambda e: e["repository"]),
        "declarations": declarations,
    }


def path_permitted(declaration: AuthorityDeclaration, path: str) -> bool:
    """Whether every required use resolves permitted for this exact path.

    No clock: :func:`resolve_annotation_authority` has already checked the
    declaration's review date at the repository level, and a lapsed
    declaration contributes no repository here to have paths in.
    """
    return all(declaration.resolve(use, path).permitted for use in REQUIRED_USES)


# -- leakage closure --------------------------------------------------------


def leakage_groups(
    ctx: Any, artifacts: Sequence[Mapping[str, Any]], domains: Mapping[str, str]
) -> dict[str, str]:
    """``artifact_id -> split group key``, from :mod:`ats.corpus.split`'s closure.

    The closure is not reimplemented. One pseudo-example per document is fed to
    :func:`ats.corpus.split.generate_split`, which joins documents that share a
    source identity, an exact or normalised content hash, or a near-duplicate
    cluster into one component (``CLOSURE_TIERS`` priorities 1--3). The frame
    then admits at most one selection per component, so the exact-content
    constraint holds by construction rather than by a second check: two members
    of one component cannot be separated by a later split because the frame
    never selects two.

    The partition names in the policy are incidental. The frame reads group
    identity only and does not fix the eventual split; a real split runs over
    the annotated examples, not over this frame.
    """
    examples = [
        {
            "example_id": artifact["artifact_id"],
            "source_artifact": artifact["artifact_id"],
            "repository_group": artifact["repository_group"],
            "domain": domains.get(str(artifact["repository"]), ""),
            "synthetic": False,
        }
        for artifact in artifacts
    ]
    policy = {
        "policy_id": "caller-frame-leakage-closure",
        "seed": "caller-frame",
        "grouping_dimensions": ["repository", "source_document", "source_mutation_pair"],
        "partitions": [
            {
                "name": "training",
                "kind": "training",
                "target_fraction": 0.5,
                "disjoint_on": ["source_document", "content_hash", "normalized_content_hash"],
            },
            {
                "name": "development",
                "kind": "development",
                "target_fraction": 0.5,
                "disjoint_on": ["source_document", "content_hash", "normalized_content_hash"],
            },
        ],
    }
    result = sp.generate_split(ctx, examples, policy, artifacts=artifacts)
    groups: dict[str, str] = {}
    for group in result["groups"]:
        for example_id in group["example_ids"]:
            groups[example_id] = group["group_key"]
    unassignable = [row["example_id"] for row in result.get("unassignable", ())]
    if unassignable:
        raise UsageError(
            f"{len(unassignable)} authorised documents carry no leakage group "
            f"(first: {unassignable[0]}); selecting them would place ungrouped bundles in a "
            "frame that promises one selection per component"
        )
    return groups


# -- pools ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Pick:
    """One admissible span, before selection decides whether to take it."""

    stratum: str
    repository: str
    artifact_id: str
    span: tuple[int, int]
    candidate_source: str
    rule_ids: tuple[str, ...]
    #: Sort ahead of its peers because a declared distribution constraint names
    #: this document. Never a conformance expectation -- see :func:`_priority`.
    constraint_relevant: bool
    #: Round-robin sub-key, so a stratum drawn from several mechanisms spreads
    #: over them instead of exhausting the largest first.
    lane: str


def _priority(artifact: Mapping[str, Any]) -> bool:
    """Whether a declared distribution constraint names this document.
    a declared profile hypothesis and a review state other than ``unknown``.
    A document carrying either sorts to the front of its lane so a bounded draw
    does not miss it by chance.

    This is a preference on *recorded provenance*, disclosed in the frame, and
    it is not a preference on an expected label: neither field says anything
    about conformance, and Section 17.4 forbids reading a label out of review
    state at all.
    """
    return bool(artifact.get("profile_hypotheses")) or artifact.get("review_state") != "unknown"


def build_pools(
    ctx: Any, sources: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, list[Pick]], dict[str, Mapping[str, Any]], dict[str, str], dict[str, Any]]:
    """Every admissible span, by stratum, plus the artifact and text indexes.

    ``sources`` is one entry per authorised repository, carrying its inventory,
    its cached mining result, its family, and its domain. Documents whose own
    path does not clear :data:`REQUIRED_USES` are dropped here, so a repository
    declaration's ``exclude`` globs are honoured at the document level and not
    only at the repository level.
    """
    pools: dict[str, list[Pick]] = {s.name: [] for s in STRATA}
    artifacts: dict[str, Mapping[str, Any]] = {}
    texts: dict[str, str] = {}
    blocks_by_artifact: dict[str, list[Block]] = {}
    dropped: list[dict[str, str]] = []

    for source in sources:
        repository = str(source["repository"])
        declaration: AuthorityDeclaration = source["declaration"]
        inventory = source["inventory"]
        mined = source["mined"]
        repo_path = inventory["repository"]

        # Before a single candidate is read. A stored mining result that was
        # built over a different inventory resolves nothing, and the per-
        # candidate refusal below is the backstop rather than the diagnosis:
        # this one names which input moved.
        require_inventory_binding(
            mined,
            inventory,
            where=repository,
            declaration_sha256=source.get("declaration_sha256"),
        )

        admitted: dict[str, Mapping[str, Any]] = {}
        for artifact in inventory["artifacts"]:
            if not path_permitted(declaration, str(artifact["path"])):
                dropped.append(
                    {
                        "repository": repository,
                        "path": str(artifact["path"]),
                        "reason": "the declaration does not permit the required uses for this path",
                    }
                )
                continue
            admitted[artifact["artifact_id"]] = artifact
            artifacts[artifact["artifact_id"]] = artifact

        # Every artifact the inventory holds, admitted or not. A candidate whose
        # artifact_id is in here but not in ``admitted`` was excluded by the
        # declaration and is skipped; one that is in neither means the mining
        # result and the inventory disagree about what the corpus *is*, which is
        # a stale input and not an exclusion. Telling them apart is the whole
        # point: an artifact_id is a content address over the artifact record,
        # so re-inventorying against a changed authority overlay re-addresses
        # every document and silently orphans a cached candidate set.
        inventoried = {str(a["artifact_id"]) for a in inventory["artifacts"]}

        for artifact_id, artifact in admitted.items():
            text = inv.artifact_text(repo_path, artifact)
            texts[artifact_id] = text
            blocks_by_artifact[artifact_id] = document_blocks(
                text, media_type=artifact.get("media_type", "text/markdown")
            )

        with_candidates: set[str] = set()
        for candidate in mined["candidates"]:
            artifact_id = candidate["artifact_id"]
            artifact = admitted.get(artifact_id)
            if artifact is None:
                _require_addressable(repository, artifact_id, inventoried, "candidates")
                continue
            with_candidates.add(artifact_id)
            block = _containing(blocks_by_artifact[artifact_id], candidate["span"]["start"])
            if block is None:
                continue
            span = (candidate["span"]["start"], candidate["span"]["end"])
            rule_ids = tuple(candidate["signal"]["rule_ids"])
            signal_id = candidate["signal"]["signal_id"]
            pools["natural_rule_candidate"].append(
                Pick(
                    stratum="natural_rule_candidate",
                    repository=repository,
                    artifact_id=artifact_id,
                    span=span,
                    candidate_source=f"signal:{signal_id}",
                    rule_ids=rule_ids,
                    constraint_relevant=_priority(artifact),
                    lane=signal_id,
                )
            )
            hard_negative = hard_negative_class(candidate, block)
            if hard_negative:
                pools["surface_cue_hard_negative"].append(
                    Pick(
                        stratum="surface_cue_hard_negative",
                        repository=repository,
                        artifact_id=artifact_id,
                        span=span,
                        candidate_source=f"hard_negative_configuration:{hard_negative}",
                        rule_ids=rule_ids,
                        constraint_relevant=_priority(artifact),
                        lane=hard_negative,
                    )
                )

        for candidate in mined["revision_candidates"]:
            artifact_id = candidate["artifact_id"]
            artifact = admitted.get(artifact_id)
            if artifact is None:
                _require_addressable(repository, artifact_id, inventoried, "revision_candidates")
                continue
            axis = candidate["candidate_basis"]["changed_axis"]
            pools["revision_derived_candidate"].append(
                Pick(
                    stratum="revision_derived_candidate",
                    repository=repository,
                    artifact_id=artifact_id,
                    span=(candidate["span"]["start"], candidate["span"]["end"]),
                    candidate_source=f"{REVISION_BASIS}:{axis}",
                    rule_ids=(),
                    constraint_relevant=_priority(artifact),
                    lane=axis,
                )
            )

        for artifact_id, artifact in admitted.items():
            if artifact_id in with_candidates:
                continue
            prose = [b for b in blocks_by_artifact[artifact_id] if b.kind != "code_block"]
            if not prose:
                continue
            # A control must be ordinary prose. Always taking the first block
            # would sample abstracts and summaries systematically, which is a
            # cue of its own.
            index = int(sha256_hex(f"control|{artifact_id}".encode("utf-8")), 16) % len(prose)
            block = prose[index]
            pools["low_signal_random_control"].append(
                Pick(
                    stratum="low_signal_random_control",
                    repository=repository,
                    artifact_id=artifact_id,
                    span=(block.start, block.end),
                    candidate_source="no_signal_document:seeded_prose_block",
                    rule_ids=(),
                    constraint_relevant=_priority(artifact),
                    lane="no_signal",
                )
            )

        for probe in PROBES:
            for artifact_id, artifact in admitted.items():
                span = probe_span(
                    ctx,
                    probe,
                    artifact=artifact,
                    text=texts[artifact_id],
                    blocks=blocks_by_artifact[artifact_id],
                )
                if span is None:
                    continue
                pools["zero_candidate_rule_probe"].append(
                    Pick(
                        stratum="zero_candidate_rule_probe",
                        repository=repository,
                        artifact_id=artifact_id,
                        span=span,
                        candidate_source=(
                            f"zero_candidate_probe:{probe.rule_id}:{probe.basis}"
                        ),
                        rule_ids=(),
                        constraint_relevant=_priority(artifact),
                        lane=probe.rule_id,
                    )
                )

    return (
        pools,
        artifacts,
        texts,
        {"blocks": blocks_by_artifact, "dropped": dropped},
    )


def _require_addressable(
    repository: str, artifact_id: str, inventoried: frozenset[str] | set[str], where: str
) -> None:
    """Refuse a mined candidate that points at no artifact in the inventory.

    A candidate whose artifact the declaration excluded is a governed exclusion
    and is skipped quietly -- the exclusion is already counted. A candidate
    whose ``artifact_id`` is not in the inventory *at all* is a different
    animal: the mining result was produced against a different inventory than
    the one being drawn from, so the two disagree about what the corpus
    contains.

    This has to be loud. ``artifact_id`` is a content address over the whole
    artifact record, including the authority resolution ``build_inventory``
    attaches, so re-inventorying against a changed authority overlay
    re-addresses every document and orphans a cached candidate set. Skipping
    those quietly produced a frame that looked plausible and was 48 bundles
    short with a breached concentration cap, and nothing in the artifact said
    why -- exactly the shape ADR-0002 exists to prevent, one level up from a
    rule result.
    """
    if artifact_id in inventoried:
        return
    raise UsageError(
        f"a mined {where} entry for {repository} names artifact {artifact_id}, which is not in "
        f"the inventory being drawn from. The mining result was built against a different "
        f"inventory -- an artifact_id is a content address over the artifact record, so "
        f"re-inventorying against a changed authority overlay re-addresses every document. "
        f"Re-mine ({repository}) rather than drawing from a cache that describes a corpus this "
        "frame is not sampling."
    )


def _containing(blocks: Sequence[Block], start: int) -> Block | None:
    return next((b for b in blocks if b.start <= start < b.end), None)


#: The largest share of the frame one repository may hold. Repository policy,
#: declared so the frame can be disputed on it: a single repository past a third
#: of the frame would make every per-rule figure a statement about that
#: repository's house style (Section 17.7 treats repository as a leakage
#: dimension for the same reason).
MAX_REPOSITORY_SHARE: Final[float] = 0.30

#: How much of one rule's selections a single near-duplicate cluster may hold.
#: Also repository policy. A cluster past a third of a rule's evidence means the
#: rule was measured on one document written several times.
MAX_CLUSTER_SHARE_PER_RULE: Final[float] = 0.34

#: How many selections must sit in long, dense prose before the frame exerts
#: false-positive pressure. A tenth of the frame: enough that a length- or
#: reference-sensitive detector misfiring on dense prose shows up as a pattern
#: rather than as one span.
MIN_LONG_PROSE_SELECTIONS: Final[int] = 30

# -- selection --------------------------------------------------------------


def _shuffle_key(seed: int, stratum: str, pick: Pick) -> str:
    """A seed-dependent order over one lane, stable for a fixed corpus.

    Hashing the seed together with the span's identity makes the draw a pure
    function of ``(corpus, seed)``: the same seed reproduces the frame byte for
    byte, and a different seed is a different draw rather than a reordering of
    the same one.
    """
    return sha256_hex(
        f"{seed}|{stratum}|{pick.artifact_id}|{pick.span[0]}|{pick.span[1]}|"
        f"{pick.candidate_source}".encode("utf-8")
    )


def select(
    seed: int,
    target_size: int,
    pools: Mapping[str, Sequence[Pick]],
    groups: Mapping[str, str],
    *,
    strata: Sequence[Stratum] = STRATA,
) -> tuple[list[Pick], dict[str, dict[str, Any]]]:
    """Draw the frame, and report what each stratum could and could not fill.

    Three admission rules, all enforced during the draw rather than repaired
    afterwards:

    1. **One selection per leakage component.** A component already represented
       is closed, which is how "no exact-content group appears more than once"
       holds -- and it also stops a near-duplicate cluster from carrying a
       stratum.
    2. **No repository above :data:`MAX_REPOSITORY_SHARE` of the frame.** A
       hard cap, checked against ``target_size`` rather than the running total,
       so the limit does not depend on draw order.
    3. **Lane-fair round-robin.** Lanes are the mechanisms inside a stratum --
       a signal, a hard-negative class, a probed rule, a force axis. The visit
       order is built so that every lane is offered a slot before any lane is
       offered a second one, and each lane's repositories rotate underneath it.
       Visiting ``(lane, repository)`` pairs in a flat seeded shuffle instead
       looked equivalent and was not: with 78 pairs feeding a 30-bundle
       stratum, the draw ended inside the first pass and three of the thirteen
       probed rules received nothing. Lane fairness is what makes the probe
       stratum cover every probeable rule, and repository rotation is what
       makes the repository and family coverage constraints hold by
       construction rather than by luck.

    A stratum that runs out of admissible picks records a ``shortfall_reason``
    naming which resource ran out. It never borrows from another stratum,
    because a stratum silently topped up from a different mechanism is no
    longer the mechanism it claims to be.
    """
    cap = int(target_size * MAX_REPOSITORY_SHARE)
    taken: list[Pick] = []
    used_groups: set[str] = set()
    per_repository: dict[str, int] = {}
    report: dict[str, dict[str, Any]] = {}

    for stratum in strata:
        pool = list(pools.get(stratum.name, ()))
        queues: dict[tuple[str, str], list[Pick]] = {}
        for pick in pool:
            queues.setdefault((pick.lane, pick.repository), []).append(pick)
        for key in queues:
            queues[key].sort(
                key=lambda p: (
                    0 if p.constraint_relevant else 1,
                    _shuffle_key(seed, stratum.name, p),
                    p.artifact_id,
                    p.span,
                )
            )

        lanes = sorted(
            {lane for lane, _ in queues},
            key=lambda lane: (sha256_hex(f"{seed}|{stratum.name}|{lane}".encode()), lane),
        )
        repositories_of: dict[str, list[str]] = {
            lane: sorted(
                (repository for lane_, repository in queues if lane_ == lane),
                key=lambda repository: (
                    sha256_hex(f"{seed}|{stratum.name}|{lane}|{repository}".encode()),
                    repository,
                ),
            )
            for lane in lanes
        }
        # Depth-major: every lane appears at depth 0 before any lane appears at
        # depth 1, so one pass over ``order`` offers each mechanism one slot.
        order = [
            (lane, repositories_of[lane][depth])
            for depth in range(max((len(r) for r in repositories_of.values()), default=0))
            for lane in lanes
            if depth < len(repositories_of[lane])
        ]

        selected = 0
        blocked_by_cap = 0
        exhausted = False
        while selected < stratum.target:
            progress = False
            for key in order:
                if selected >= stratum.target:
                    break
                queue = queues[key]
                while queue:
                    pick = queue.pop(0)
                    group = groups.get(pick.artifact_id)
                    if group is None or group in used_groups:
                        continue
                    if per_repository.get(pick.repository, 0) >= cap:
                        blocked_by_cap += 1
                        continue
                    used_groups.add(group)
                    per_repository[pick.repository] = per_repository.get(pick.repository, 0) + 1
                    taken.append(pick)
                    selected += 1
                    progress = True
                    break
            if not progress:
                exhausted = True
                break

        entry: dict[str, Any] = {"selected": selected, "pool": len(pool)}
        if selected < stratum.target:
            reasons = [
                f"the pool offered {len(pool)} admissible spans over "
                f"{len({p.artifact_id for p in pool})} documents"
            ]
            if exhausted:
                reasons.append(
                    "every remaining span belongs to a leakage component already represented, "
                    "and the frame admits one selection per component so a near-duplicate "
                    "cannot be counted twice"
                )
            if blocked_by_cap:
                reasons.append(
                    f"{blocked_by_cap} span(s) were refused because their repository had "
                    f"reached the {int(MAX_REPOSITORY_SHARE * 100)}% share cap"
                )
            entry["shortfall_reason"] = (
                f"selected {selected} of {stratum.target}: " + "; ".join(reasons)
            )
        report[stratum.name] = entry

    return taken, report



def assign_double_annotation(
    selections: Sequence[Mapping[str, Any]],
    target: int,
    *,
    stratum_order: Sequence[str] = STRATUM_NAMES,
) -> list[dict[str, Any]]:
    """Mark ``target`` selections for a second independent judgment, and order them first.

    The subset is drawn by round-robin over ``(stratum, repository)`` buckets,
    visited stratum-interleaved: every stratum is offered a slot before any
    stratum is offered a second one, and its repositories rotate underneath.
    Sorting the buckets and walking them in order looked equivalent and was not
    -- ``(stratum, repository)`` sorts stratum-major, so a target smaller than
    the bucket count consumed the alphabetically first stratum entirely and
    reached only some of the mechanisms.

    Equal-per-bucket rather than proportional is deliberate: agreement is read
    per mechanism (Section 17.10 forbids folding hard negatives into a pooled
    score), and a 30-selection stratum needs a high double-annotation share
    before its agreement figure says anything at all. The consequence -- the
    small strata are more heavily double-annotated than the large one -- is the
    intended trade.

    Marked selections are placed first, so ``double_annotated`` on the leading
    ``target`` rows is a property of the array and not a claim about it.
    """
    buckets: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in selections:
        buckets.setdefault((row["stratum"], row["repository"]), []).append(row)
    for key in buckets:
        buckets[key].sort(key=lambda r: r["bundle_id"])
    repositories_of: dict[str, list[str]] = {}
    for stratum, repository in sorted(buckets):
        repositories_of.setdefault(stratum, []).append(repository)
    present = [name for name in stratum_order if name in repositories_of]
    order = [
        (stratum, repositories_of[stratum][depth])
        for depth in range(max((len(r) for r in repositories_of.values()), default=0))
        for stratum in present
        if depth < len(repositories_of[stratum])
    ]

    chosen: list[Mapping[str, Any]] = []
    while len(chosen) < target:
        progress = False
        for key in order:
            if len(chosen) >= target:
                break
            if buckets[key]:
                chosen.append(buckets[key].pop(0))
                progress = True
        if not progress:
            break

    chosen_ids = {row["bundle_id"] for row in chosen}
    marked = [{**row, "double_annotated": True} for row in chosen]
    rest = [
        {**row, "double_annotated": False}
        for row in selections
        if row["bundle_id"] not in chosen_ids
    ]
    order_of = {name: position for position, name in enumerate(stratum_order)}

    def sort_key(row: Mapping[str, Any]) -> tuple[int, str, str]:
        return (order_of[row["stratum"]], row["repository"], row["bundle_id"])

    return sorted(marked, key=sort_key) + sorted(rest, key=sort_key)


# -- constraints ------------------------------------------------------------


def authorised_profile_counts(artifacts: Any) -> dict[str, int]:
    """Declared profile hypotheses per profile, over the admitted documents.

    Only *declared* hypotheses are counted. A document that declares nothing is
    counted under ``<none declared>`` rather than under the ASSESS default its
    bundle will report, because the default is what the pipeline falls back to
    and not something the document said (ADR-0002).
    """
    counts: dict[str, int] = {}
    for artifact in artifacts:
        declared = list(artifact.get("profile_hypotheses") or ())
        if not declared:
            counts["<none declared>"] = counts.get("<none declared>", 0) + 1
        for profile in declared:
            counts[profile] = counts.get(profile, 0) + 1
    return counts



def evaluate_constraints(
    selections: Sequence[Mapping[str, Any]],
    *,
    long_prose: Mapping[str, bool],
    authorised_repositories: Sequence[Mapping[str, Any]],
    authorised_documents: int,
    path_excluded_documents: Sequence[Mapping[str, str]],
    corpus_review_states: Mapping[str, int],
    corpus_profiles: Mapping[str, int],
    unauthorised_profiles: Mapping[str, Mapping[str, int]],
) -> list[dict[str, Any]]:
    """Every declared distribution constraint, met or not.

    One is unsatisfiable from this corpus and is recorded as such. Marking it
    ``satisfied: false, unsatisfiable: true`` with the measured counts is the
    whole point: a constraint quietly dropped from the list would read as a
    constraint nobody needed, and a constraint reported satisfied on a
    redefinition of its terms would be worse.

    ``review_state_coverage`` is the one row that is no longer a constraint. It
    carries ``expectation_withdrawn`` in place of ``unsatisfiable``, because the
    two claims differ: ``unsatisfiable`` says *this corpus* cannot meet a
    standing requirement, and there is no longer a requirement to meet. Its
    measurement is kept in full and its ``satisfied`` recomputes from the draw
    rather than being asserted -- dropping the row would hide the finding, and
    leaving it permanently red would teach a reader to ignore a red.
    """
    repositories = sorted({row["repository"] for row in selections})
    families = sorted({row.get("document_family", "") for row in selections} - {""})
    total = len(selections)

    per_repository: dict[str, int] = {}
    for row in selections:
        per_repository[row["repository"]] = per_repository.get(row["repository"], 0) + 1
    worst_repo, worst_share = ("", 0.0)
    for name, count in sorted(per_repository.items()):
        share = count / total if total else 0.0
        if share > worst_share:
            worst_repo, worst_share = name, share

    groups: dict[str, int] = {}
    for row in selections:
        groups[row["split_group"]] = groups.get(row["split_group"], 0) + 1
    repeated = sorted(g for g, n in groups.items() if n > 1)

    per_rule_cluster: dict[str, dict[str, int]] = {}
    for row in selections:
        cluster = row.get("near_duplicate_cluster")
        if not cluster:
            continue
        for rule_id in row.get("candidate_rule_ids", ()):
            per_rule_cluster.setdefault(rule_id, {})
            per_rule_cluster[rule_id][cluster] = per_rule_cluster[rule_id].get(cluster, 0) + 1
    dominated: list[str] = []
    for rule_id, clusters in sorted(per_rule_cluster.items()):
        rule_total = sum(clusters.values())
        for cluster, count in sorted(clusters.items()):
            if rule_total >= 3 and count / rule_total > MAX_CLUSTER_SHARE_PER_RULE:
                dominated.append(f"{rule_id}: {cluster} holds {count}/{rule_total}")

    declared_profiles = sorted(
        {p for row in selections for p in row.get("profile_hypotheses", ())}
    )
    selected_states = sorted({row.get("review_state", "unknown") for row in selections})
    long_count = sum(1 for row in selections if long_prose.get(row["bundle_id"], False))

    review_summary = ", ".join(f"{k}={v}" for k, v in sorted(corpus_review_states.items()))
    profile_summary = ", ".join(f"{k}={v}" for k, v in sorted(corpus_profiles.items())) or "none"
    # Where the missing profile actually lives, kept apart from the rest. A
    # single summary of every unauthorised declaration read as though all of
    # them declared SPECIFY, which is not what the census measured.
    specify_locations = sorted(
        repo for repo, counts in unauthorised_profiles.items() if counts.get("SPECIFY")
    )
    unauthorised_summary = "; ".join(
        f"{repo}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        for repo, counts in sorted(unauthorised_profiles.items())
        if repo not in specify_locations
    )

    return [
        {
            "constraint": "repository_coverage",
            "target": "at least 5 repositories",
            "observed": f"{len(repositories)}: {', '.join(repositories)}",
            "satisfied": len(repositories) >= 5,
            "detail": (
                f"{len(authorised_repositories)} repositories cleared "
                f"{' and '.join(REQUIRED_USES)}, and {authorised_documents} of their documents "
                f"cleared it at their own path; {len(path_excluded_documents)} were refused by a "
                "declaration's exclude globs, which RULE_COVERAGE.md had to record as "
                "path_scoping: not_applied because a per-repository census cannot subtract them. "
                "The draw round-robins over repositories inside every stratum, so coverage is a "
                "property of the draw rather than a filter applied after it."
            ),
        },
        {
            "constraint": "document_family_coverage",
            "target": "at least 4 document families",
            "observed": f"{len(families)}: {', '.join(families)}",
            "satisfied": len(families) >= 4,
            "detail": (
                "Each authorised repository contributes a declared family, so family coverage "
                "tracks repository coverage only when that declaration is one-to-one. It is "
                "reported because a rule concentrated in one family is a real risk elsewhere."
            ),
        },
        {
            "constraint": "repository_concentration",
            "target": f"no repository above {int(MAX_REPOSITORY_SHARE * 100)}% of the frame",
            "observed": (
                f"largest is {worst_repo} at {per_repository.get(worst_repo, 0)}/{total} "
                f"({worst_share:.1%})"
            ),
            "satisfied": worst_share <= MAX_REPOSITORY_SHARE,
            "detail": (
                "The cap exists because a handful of repositories hold most of the "
                "candidates, and an uncapped draw would be a statement about their house "
                "style. It is enforced during the draw against the target size, so it does "
                "not depend on draw order -- but the share reported here is measured "
                "against the frame that actually exists. When a stratum under-fills, the "
                "same per-repository ceiling becomes a larger fraction of a smaller frame, "
                "and this check then fails on the realised distribution even though the "
                "draw honoured the cap it was given. The failure is left standing: "
                "discarding selections to recover the ratio would shrink a sample to "
                "improve a statistic, which is the trade the priority order forbids."
            ),
        },
        {
            "constraint": "exact_content_uniqueness",
            "target": "no exact-content group appears more than once",
            "observed": (
                f"{len(groups)} distinct leakage components over {total} selections"
                + (f"; repeated: {', '.join(repeated)}" if repeated else "")
            ),
            "satisfied": not repeated,
            "detail": (
                "The group is ats.corpus.split's leakage-closure component, which joins "
                "documents sharing a source identity, an exact or normalised content hash, or a "
                "near-duplicate cluster. The frame admits one selection per component, so this "
                "holds by construction: three content hashes appear in more than one repository "
                "in this corpus (STAGE_1_CENSUS_REPORT.md 4), and repository grouping alone "
                "would not have caught them."
            ),
        },
        {
            "constraint": "near_duplicate_rule_concentration",
            "target": (
                f"no near-duplicate cluster above {int(MAX_CLUSTER_SHARE_PER_RULE * 100)}% of "
                "any single rule's selections"
            ),
            "observed": (
                f"{len(per_rule_cluster)} rules carry flagged candidates; "
                + ("no cluster dominates" if not dominated else "; ".join(dominated))
            ),
            "satisfied": not dominated,
            "detail": (
                "Scoped to candidate_rule_ids, which are detector flags. Probe and control "
                "selections carry none by design -- no detector flagged them -- so they cannot "
                "and do not contribute to a per-rule concentration. Rules with fewer than three "
                "selections are not assessed, because one of two is not domination."
            ),
        },
        {
            "constraint": "profile_hypothesis_coverage",
            "target": "both ASSESS and SPECIFY profile hypotheses present",
            "observed": (
                f"declared hypotheses among selections: {', '.join(declared_profiles) or 'none'}"
            ),
            "satisfied": {"ASSESS", "SPECIFY"} <= set(declared_profiles),
            "unsatisfiable": True,
            "detail": (
                f"Unsatisfiable from the supplied corpus. Declared profile hypotheses across "
                f"the {authorised_documents} authorised documents: {profile_summary}. The "
                f"supplied profiles include {', '.join(specify_locations) or 'no SPECIFY declaration'}, "
                "Every bundle whose document declares nothing reports profile ASSESS with basis "
                "'unknown' (ats.corpus.context._profile_hypothesis); that default is a "
                "placeholder, not a hypothesis. The annotation round must supply SPECIFY "
                "through profile_hint when the corpus needs it; this frame cannot infer one."
            ),
        },
        {
            "constraint": "review_state_coverage",
            "target": (
                "observation: which review states the corpus supplied, reported for every "
                "selection; no acceptance state is a required stratum"
            ),
            "observed": (
                f"among selections: {', '.join(selected_states)}; census-wide: {review_summary}"
            ),
            "satisfied": (
                bool(selections)
                and bool(corpus_review_states)
                and all(row.get("review_state") for row in selections)
            ),
            "expectation_withdrawn": {
                "expectation": (
                    "accepted, superseded, reverted, and unresolved artifacts present as "
                    "required strata of the annotation frame"
                ),
                "withdrawn_by": (
                    "Caller policy: include accepted, superseded, or reverted strata only "
                    "when independently supplied evidence authorises them"
                ),
                "reason": (
                    "Acceptance is a decision an external authority records, not a property "
                    "version control stores. Git establishes presence, deletion, ancestry, and "
                    "merge topology, and none of those is a decision about the text. No "
                    "repository-derived corpus can supply an acceptance stratum without "
                    "explicit evidence; the expectation is withdrawn rather than carried as "
                    "a permanent failure. Documents remain acceptance_state: unknown until "
                    "an authority record says otherwise."
                ),
                "reference": "ats.corpus.acceptance",
            },
            "detail": (
                f"Measurement retained, expectation withdrawn. The caller supplied "
                f"review-state summary is {review_summary}; acceptance evidence remains "
                "separate from repository topology. A document is not promoted by "
                "being present, merged, deleted, or reverted. Acceptance promotion "
                "requires an explicit authoritative receipt, decision record, structured "
                "review disposition, or declared ATS-Review-State."
            ),
        },
        {
            "constraint": "false_positive_pressure",
            "target": (
                f"at least {MIN_LONG_PROSE_SELECTIONS} selections in long, dense prose "
                f"(a paragraph of at least {LONG_PROSE_CHARS} characters over at least "
                f"{LONG_PROSE_SENTENCES} sentences)"
            ),
            "observed": f"{long_count}/{total} selections",
            "satisfied": long_count >= MIN_LONG_PROSE_SELECTIONS,
            "detail": (
                "Length and sentence count are observable; 'technically valid' is not, and the "
                "frame does not claim it. Caller-supplied technical documentation provides "
                "the material for the CP-42 HN-1 lane, so a detector that misfires on dense "
                "prose has somewhere to show it. A frame of short cue-bearing fragments would "
                "report precision no reviewer could trust."
            ),
        },
    ]


# -- blinding ---------------------------------------------------------------


def withheld_fields(ctx: Any) -> tuple[str, ...]:
    """Selection fields withheld from an annotator, derived from the schema.

    Subtraction, not enumeration: the withheld set is every property the
    schema declares on a selection minus :data:`ANNOTATOR_VISIBLE_FIELDS`. A
    field added to the schema is therefore withheld until somebody adds it to
    the allow-list, which is the direction a blinding mechanism has to fail in.
    """
    _, schema = ctx.schemas.schema_for_version(SCHEMA_VERSION)
    declared = schema["properties"]["selection"]["items"]["properties"]
    missing = [f for f in ANNOTATOR_VISIBLE_FIELDS if f not in declared]
    if missing:
        raise UsageError(
            f"the annotator allow-list names selection fields the schema does not declare: "
            f"{missing}; the withheld set is derived by subtraction, so a stale allow-list "
            "would silently shrink it"
        )
    return tuple(f for f in declared if f not in ANNOTATOR_VISIBLE_FIELDS)


def annotator_view(frame: Mapping[str, Any]) -> dict[str, Any]:
    """The frame as a blind annotator sees it: work items, and nothing else.

    Built by projecting each selection onto
    :data:`ANNOTATOR_VISIBLE_FIELDS`. Nothing is deleted, so there is no field
    a future selection key can slip through: a key absent from the allow-list
    is absent from the output whatever the frame carries. The frame's design
    record -- policy, strata with their rationales, constraints -- is dropped
    whole, because the stratum table names the mechanisms and would give the
    hard-negative lane away even with the per-row ``stratum`` removed.
    """
    withheld = list(frame["blinding"]["withheld_from_annotator"])
    leaked = [f for f in withheld if f in ANNOTATOR_VISIBLE_FIELDS]
    if leaked:
        raise UsageError(
            f"fields {leaked} are both withheld and allow-listed; the projection cannot honour "
            "both, and resolving it silently would decide which of the two is a mistake"
        )
    return {
        "schema_version": VIEW_SCHEMA_VERSION,
        "frame_id": frame["frame_id"],
        "generated_at": frame["generated_at"],
        "withheld_from_annotator": withheld,
        "blinding_rationale": frame["blinding"].get("rationale", ""),
        "items": [
            {f: row[f] for f in ANNOTATOR_VISIBLE_FIELDS if f in row}
            for row in frame["selection"]
        ],
    }


# -- frame ------------------------------------------------------------------


def build_sampling_frame(
    ctx: Any,
    *,
    repositories: Sequence[Mapping[str, Any]],
    seed: int,
    target_size: int = 300,
    double_annotation_target: int = 120,
    authority_overlay: str | Path = "corpus/authority",
    strata: Sequence[Stratum] = STRATA,
    corpus_review_states: Mapping[str, int],
    unauthorised_profiles: Mapping[str, Mapping[str, int]],
    bundle_sink: MutableSequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a sampling frame over a caller-supplied corpus.

    ``repositories`` is one entry per supplied repository, carrying
    ``repository``, ``family``, ``domain``, and ``revision``, plus an
    ``inventory`` and a ``mined`` result for entries a caller expects to be
    authorised. Authority is resolved before any pool is built, so an
    unauthorised repository cannot contribute a selection; a row that clears
    authority without carrying its inventory is refused rather than skipped.

    ``corpus_review_states`` and ``unauthorised_profiles`` are caller-supplied
    measurements the constraint details cite. They are passed in rather than
    recomputed because the counts that make a constraint unsatisfiable describe
    the complete input corpus; the authorised subset's profile counts are
    derived here from the documents actually selected.
    ``strata`` defaults to :data:`STRATA`. It remains a parameter so the same
    code path can be exercised at a scale a caller's corpus can fill: a draw
    that only ever runs at one fixed size is a draw whose shortfall and cap
    behaviour nobody checks.
    """
    if target_size < 1:
        raise UsageError(f"target_size must be at least 1; got {target_size}")
    if not 0 <= double_annotation_target <= target_size:
        raise UsageError(
            f"double_annotation_target {double_annotation_target} is not within "
            f"[0, target_size={target_size}]"
        )
    declared_total = sum(s.target for s in strata)
    if declared_total != target_size:
        raise UsageError(
            f"the {len(strata)} strata target {declared_total} bundles but target_size is "
            f"{target_size}; a frame whose strata do not add up to its target has an "
            "unaccounted-for remainder"
        )

    # The run clock, so an overlay past its review date stops authorising a
    # selection instead of quietly granting for as long as the file exists.
    authority = resolve_annotation_authority(
        repositories, authority_overlay, now=ctx.timestamp()
    )
    declarations = authority["declarations"]
    # ``declaration_sha256`` travels with the source so the mining cache can be
    # checked against the declaration it was scoped by, not only against the
    # artifact identities.
    digests = {
        str(entry["repository"]): entry.get("declaration_sha256")
        for entry in authority["authorised"]
    }
    sources = [
        {
            **row,
            "declaration": declarations[str(row["repository"])],
            "declaration_sha256": digests.get(str(row["repository"])),
        }
        for row in repositories
        if str(row["repository"]) in declarations
    ]
    missing = sorted(
        str(row["repository"])
        for row in sources
        if not row.get("inventory") or not row.get("mined")
    )
    if missing:
        raise UsageError(
            f"repositories {missing} resolved authorised but were supplied no inventory or "
            "mining result; a frame that quietly omits an authorised repository misreports the "
            "corpus it drew from"
        )
    if not sources:
        raise UsageError(
            "no repository permits both "
            f"{' and '.join(REQUIRED_USES)}; a frame drawn anyway would be a governance failure"
        )

    pools, artifacts, texts, index = build_pools(ctx, sources)
    families = {str(row["repository"]): str(row["family"]) for row in sources}
    domains = {str(row["repository"]): str(row["domain"]) for row in sources}
    repo_paths = {str(row["repository"]): row["inventory"]["repository"] for row in sources}

    groups = leakage_groups(ctx, sorted(artifacts.values(), key=lambda a: a["artifact_id"]), domains)
    picks, stratum_report = select(seed, target_size, pools, groups, strata=strata)

    blocks: Mapping[str, list[Block]] = index["blocks"]
    rows: list[dict[str, Any]] = []
    long_prose: dict[str, bool] = {}
    for pick in picks:
        artifact = artifacts[pick.artifact_id]
        repository = str(artifact["repository"])
        bundle = build_context_bundle(
            ctx,
            artifact=artifact,
            text=texts[pick.artifact_id],
            span={
                "kind": "character",
                "start": pick.span[0],
                "end": pick.span[1],
                "source_sha256": artifact["content_sha256"],
            },
            repo_path=repo_paths[repository],
        )
        if bundle_sink is not None:
            # The frame records a bundle_id but not the span it was built from,
            # so a bundle discarded here cannot be reconstructed afterwards.
            # Annotation needs the bundle itself, and rebuilding it by
            # re-selecting would be a second selection path that could drift
            # from this one.
            bundle_sink.append(bundle)
        row: dict[str, Any] = {
            "bundle_id": bundle["bundle_id"],
            "source_artifact_id": artifact["artifact_id"],
            "repository": repository,
            "document_family": families[repository],
            "domain": domains[repository],
            "stratum": pick.stratum,
            "candidate_source": pick.candidate_source,
            "candidate_rule_ids": list(pick.rule_ids),
            "profile_hypotheses": list(artifact.get("profile_hypotheses") or ()),
            "split_group": groups[pick.artifact_id],
            "content_sha256": artifact["content_sha256"],
            "review_state": str(artifact.get("review_state", "unknown")),
        }
        if artifact.get("near_duplicate_cluster"):
            row["near_duplicate_cluster"] = str(artifact["near_duplicate_cluster"])
        if artifact.get("template_family"):
            row["template_family"] = str(artifact["template_family"])
        block = _containing(blocks[pick.artifact_id], pick.span[0])
        long_prose[bundle["bundle_id"]] = bool(block and long_dense_prose(block))
        rows.append(row)

    selection = assign_double_annotation(
        rows, double_annotation_target, stratum_order=[s.name for s in strata]
    )

    stratum_rows = []
    for stratum in strata:
        entry = stratum_report[stratum.name]
        stratum_row: dict[str, Any] = {
            "stratum": stratum.name,
            "target": stratum.target,
            "selected": entry["selected"],
            "rationale": stratum.rationale,
        }
        if "shortfall_reason" in entry:
            stratum_row["shortfall_reason"] = entry["shortfall_reason"]
        stratum_rows.append(stratum_row)

    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": ctx.timestamp(),
        "corpus_sha256": content_hash(
            {
                "artifacts": sorted(
                    [a["artifact_id"], a["content_sha256"], a["revision"]]
                    for a in artifacts.values()
                )
            },
            exclude=set(),
        ),
        "policy": {
            "seed": seed,
            "target_size": target_size,
            "double_annotation_target": double_annotation_target,
        },
        "authority": {
            "authorised_repositories": authority["authorised"],
            "required_uses": list(REQUIRED_USES),
            "excluded_repositories": authority["excluded"],
        },
        "strata": stratum_rows,
        "selection": selection,
        "constraints": evaluate_constraints(
            selection,
            long_prose=long_prose,
            authorised_repositories=authority["authorised"],
            authorised_documents=len(artifacts),
            path_excluded_documents=index["dropped"],
            corpus_review_states=corpus_review_states,
            corpus_profiles=authorised_profile_counts(artifacts.values()),
            unauthorised_profiles=unauthorised_profiles,
        ),
        "blinding": {
            "withheld_from_annotator": list(withheld_fields(ctx)),
            "rationale": BLINDING_RATIONALE,
        },
    }
    digest = content_hash(body, exclude=set())
    body["frame_id"] = f"{ID_PREFIX}:{digest}"
    frame = seal(body)
    ctx.schemas.validate_document(frame)
    return frame

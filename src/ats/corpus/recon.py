"""SPECIFY profile reconnaissance: why an authorised corpus declares no SPECIFY.

The report explains why a caller-supplied corpus may declare no SPECIFY. It
keeps that outcome explicit rather than forcing sections into SPECIFY, which
leaves the question open. Four explanations survive that refusal and this
module is built to return any of them, including the one that says the
standard is wrong:

``true_corpus_absence``
    The repositories genuinely contain few ATS-style obligations.
``candidate_mining_deficiency``
    Requirement-bearing text exists but the production miner does not surface it.
``context_bundle_deficiency``
    The obligations depend on enclosing sections the bundles omit.
``profile_boundary_defect``
    Real technical specifications do not fit ATS-1's SPECIFY definition cleanly.

Three properties make the answer worth reading.

**The selector is deliberately broader than the miner and never changes it.**
``ats.corpus.mine`` matches the lexicon's canonical *uppercase* deontic
surfaces; this module matches them case-insensitively and adds six further
requirement-shape signals. Broadening here is safe because nothing downstream
raises a finding from it: the study asks whether requirement-bearing text
exists, and answering "no" with a narrow instrument would answer a different
question. The miner is untouched, so if the verdict is that it is deficient,
that is a finding rather than a change already made.

**A signal ATS-1 enumerates no vocabulary for says so.** ADR-0006 permits a
term list only from the force lexicon, a list enumerated verbatim in the spec,
or an enum declared in a normative schema. Two of the seven signals -- an
explicit actor and an enumerated obligation -- have no such list anywhere, so
they declare ``no_declared_vocabulary``, carry zero phrases, and are observed
structurally instead. Inventing a plausible word list for them would make the
count look better and the finding worthless.

**The classifier never sees why a bundle was selected.**
:func:`blind_recon_item` is an allow-list over the bundle, built by naming what
is included rather than by deleting what is not, in the same shape as
:func:`ats.corpus.round.blind_item`. The fired signals are the study's own
prediction about the text; handing them to the annotator would anchor the
judgment the study is trying to measure (spec Sections 13.2, 16.5, 17.8).

Both annotators are LLM passes. Agreement between them measures whether the
rubric and the bundles produce a stable classification -- instrument
reproducibility. It is **not** human inter-rater reliability, and
:data:`INSTRUMENT_CAVEAT` travels into every report so nothing downstream can
describe it as such.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

from ..canonical import content_hash, seal, sha256_hex
from ..errors import UsageError

# Imported rather than restated, so the repository has one spelling of each.
# ``BOUNDARY_TERMS`` is the ATS-NUM-002 detector's own comparator vocabulary and
# ``CONCEALING_ACTORS`` is the ATS-REQ-001 detector's, both quoted from the spec
# in their own modules; ``_word_pattern`` and ``_surface_forms`` are the profile
# hypothesiser's surface morphology over an imported term list, not a term list.
from ..rules.deterministic.quantity import BOUNDARY_TERMS
from ..rules.deterministic.requirements import CONCEALING_ACTORS
from . import frame as fr
from . import inventory as inv
from .context import Block, build_context_bundle, document_blocks
from .mine import Refusal
from .profile import EXEMPT_BLOCK_KINDS, _surface_forms, _word_pattern

SCHEMA_ID: Final[str] = "ats_profile_reconnaissance_v1.schema.json"
SCHEMA_VERSION: Final[str] = "ats.profile_reconnaissance.v1"
ID_PREFIX: Final[str] = "ats-recon-sha256"

GENERATOR_ID: Final[str] = "ats.corpus.recon/build_profile_reconnaissance"

#: The normative schema every slot vocabulary below is read from.
COMMON_SCHEMA_ID: Final[str] = "ats_common_v1.schema.json"

#: What the study asks. Recorded on the report so a reader does not have to
#: infer the question from the answer.
STUDY_QUESTION: Final[str] = (
    "Given caller-supplied context bundles, does the profile reconnaissance "
    "surface requirement-bearing structure, or do the bundles lack the "
    "enclosing sections the obligations depend on?"
)

#: The four rival explanations, fixed before any bundle was drawn. A study that
#: can only return one of its hypotheses has not tested them.
EXPLANATIONS: Final[tuple[tuple[str, str], ...]] = (
    (
        "true_corpus_absence",
        "The supplied repositories genuinely contain little requirement-bearing text, so "
        "no miner and no bundle shape would have found SPECIFY sections to declare.",
    ),
    (
        "candidate_mining_deficiency",
        "Requirement-bearing text is present and broad signals surface it, but the "
        "production candidate miner and profile hypothesiser do not, so the corpus reports "
        "an absence that is an instrument gap.",
    ),
    (
        "context_bundle_deficiency",
        "The obligations are only recognisable from an enclosing section the context bundle "
        "omits, so a classifier reading a bundle cannot see what a reader of the document "
        "would.",
    ),
    (
        "profile_boundary_defect",
        "The text is genuine specification prose and still does not sit inside ATS-1's "
        "SPECIFY definition, so the boundary drawn by Section 9.3 -- not this corpus and not "
        "this implementation -- is what produces the zero.",
    ),
)

EXPLANATION_IDS: Final[tuple[str, ...]] = tuple(e for e, _ in EXPLANATIONS)

#: Bound into every report. Two model passes are a measurement of the
#: instrument, and the distinction is exactly the one a reader will otherwise
#: get wrong.
INSTRUMENT_CAVEAT: Final[str] = (
    "Both annotators are LLM passes (kind: llm). The agreement reported here measures "
    "whether the rubric and the context bundles produce a stable classification -- "
    "instrument reproducibility. It is NOT human inter-rater reliability, and no downstream "
    "artifact may describe it as such."
)

RELATIONSHIP_TO_FRAME: Final[str] = (
    "This study may be run beside a caller-supplied sampling frame and contributes "
    "nothing to it. It selects its own bundles with its own broader signals, produces "
    "no label against any ATS-1 rule, and leaves frame constraints standing."
)

#: What this study declines to conclude, in the same shape as the mining and
#: profile refusals so a reader sees the boundaries without reading the code.
RECON_REFUSALS: Final[tuple[Refusal, ...]] = (
    Refusal(
        refusal_id="no-profile-inferred-from-signals",
        question="Does a fired signal make the section a SPECIFY section?",
        answer=(
            "No. A signal selects text for someone to read. Only the classification passes "
            "produce a profile judgment, and the signals are withheld from them precisely so "
            "the two cannot be confused."
        ),
        spec_ref="ATS-1 13.2, 16.5",
    ),
    Refusal(
        refusal_id="no-vocabulary-invented-for-an-unenumerated-signal",
        question="May a signal ATS-1 enumerates no words for be given a plausible word list?",
        answer=(
            "No. It declares no_declared_vocabulary, carries zero phrases, and is observed "
            "structurally or not at all. A count raised by an invented list would measure "
            "this implementation's taste, not the corpus."
        ),
        spec_ref="ADR-0006",
    ),
    Refusal(
        refusal_id="no-human-agreement-claim",
        question="Is the agreement figure inter-rater reliability?",
        answer=(
            "No. Both annotators are LLM passes. The figure is instrument reproducibility, "
            "and reporting it as human agreement would claim evidence nobody collected."
        ),
        spec_ref="ATS-1 17.9",
    ),
    Refusal(
        refusal_id="no-verdict-to-have-one",
        question="Must the study name one of the four explanations?",
        answer=(
            "No. A criterion is evaluated per explanation against a threshold declared "
            "before the passes ran. When none or several are supported the verdict is "
            "undecided and the separating experiment is named."
        ),
        spec_ref="ADR-0002",
    ),
)


def _refusal_records() -> list[dict[str, str]]:
    return [
        {
            "refusal_id": r.refusal_id,
            "statement": f"{r.question} {r.answer}",
            "spec_ref": r.spec_ref,
        }
        for r in RECON_REFUSALS
    ]


# -- signals ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReconSignal:
    """One requirement-shape signal, and where its vocabulary came from.

    ``origin`` is the audit trail ADR-0006 requires. ``no_declared_vocabulary``
    is a first-class value rather than an omission: it states that ATS-1
    enumerates nothing for this signal, which is a finding about the standard's
    machine-readable surface and not a gap in this module.
    """

    signal_id: str
    description: str
    spec_ref: str
    vocabulary_source: str
    origin: str
    detection: str
    phrases: tuple[str, ...] = ()
    #: Words a reader might expect and that this signal deliberately does not
    #: carry, because no ATS-1 list names them.
    not_matched: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.origin == "no_declared_vocabulary" and self.phrases:
            raise UsageError(
                f"signal {self.signal_id} declares no_declared_vocabulary and still carries "
                f"{len(self.phrases)} phrase(s); a word list under that label is exactly the "
                "invention ADR-0006 forbids"
            )
        if self.detection == "phrase" and not self.phrases:
            raise UsageError(
                f"signal {self.signal_id} detects by phrase and carries none; it would fire "
                "on nothing while reporting itself as wired"
            )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "signal_id": self.signal_id,
            "description": self.description,
            "spec_ref": self.spec_ref,
            "vocabulary_source": self.vocabulary_source,
            "origin": self.origin,
            "detection": self.detection,
            "phrase_count": len(self.phrases),
        }
        if self.phrases:
            out["phrases"] = list(self.phrases)
        if self.not_matched:
            out["not_matched"] = list(self.not_matched)
        return out


#: The conditional and temporal openers ATS-1 Section 9.3.5's recommended forms
#: and Section 9.3.6's examples use verbatim: "When <trigger>", "While
#: <condition>", "If <undesired event>", "Within <duration> after <trigger>",
#: and "only when <permission boundary>". Transcribed with the section recorded,
#: in the same way ``mine.RELATIVE_TIME_TERMS`` transcribes Section 10.11.
CONDITION_TRIGGER_OPENERS: Final[tuple[str, ...]] = ("if", "only when", "when", "while")

#: Exception markers ATS-1 does **not** enumerate. Section 9.3.2 declares an
#: ``exceptions`` slot and gives no surface vocabulary for it, so these are
#: recorded as unmatched rather than added. A selector that matched them would
#: cite 9.3.2 for words 9.3.2 does not contain. "except when" is deliberately
#: absent from this list: it contains the enumerated opener "when" and does
#: fire, so listing it as unmatched would be a false claim about the selector.
CONDITION_TRIGGER_UNMATCHED: Final[tuple[str, ...]] = (
    "unless",
    "provided that",
    "in the event that",
)

#: A bare numeral is a threshold surface with no enumerated vocabulary: Sections
#: 9.3.8 and 10.10 name comparator and inclusivity *words*, which is what
#: ``BOUNDARY_TERMS`` holds. Matching digits would widen the signal past the
#: list it cites.
THRESHOLD_UNMATCHED: Final[tuple[str, ...]] = ("bare numerals", "bare units", "percentages")

#: How many words a subject noun phrase may hold before it stops being one.
#: Section 9.3.5's canonical order puts the actor immediately left of the
#: deontic; a twenty-word left context is a clause, not an actor. Repository
#: policy, declared so the structural observation can be disputed.
ACTOR_PREFIX_MAX_WORDS: Final[int] = 8

#: How many sibling lines of one list must carry a modality before the list is
#: an enumeration of obligations rather than a list that happens to contain one.
#: Mirrors ``profile.REQUIREMENT_SLOT_QUORUM``: the shape, not any single line,
#: is what is being recognised.
ENUMERATED_OBLIGATION_QUORUM: Final[int] = 2


def _deontic_phrases(ctx: Any) -> tuple[str, ...]:
    """Every deontic surface, canonical and noncanonical, from the lexicon."""
    lexicon = ctx.lexicon
    return tuple(
        sorted(set(lexicon.deontic_surfaces.values()) | set(lexicon.deontic_noncanonical))
    )


def _prohibition_permission_phrases(ctx: Any) -> tuple[str, ...]:
    """The prohibiting and permitting deontic surfaces, derived from the lexicon.

    Membership is decided by the lexicon's own term ids -- ``*_NOT`` prohibits,
    ``MAY`` permits -- rather than by a judgment made here, so a lexicon that
    adds a prohibition moves this signal without a code edit (Section 19.3).
    """
    lexicon = ctx.lexicon
    surfaces = {
        surface
        for term_id, surface in lexicon.deontic_surfaces.items()
        if term_id.endswith("_NOT") or term_id == "MAY"
    }
    surfaces |= {s for s in lexicon.deontic_noncanonical if "NOT" in s.upper().split()}
    return tuple(sorted(surfaces))


def _acceptance_phrases(ctx: Any) -> tuple[str, ...]:
    """The ``acceptance_criterion`` slot surface, read from the normative schema."""
    slots = ctx.schemas.schema(COMMON_SCHEMA_ID)["$defs"]["requirement_slots"]["properties"]
    if "acceptance_criterion" not in slots:
        raise UsageError(
            "ats_common_v1#/$defs/requirement_slots no longer declares acceptance_criterion; "
            "this signal cites a slot the normative package dropped"
        )
    return _surface_forms("acceptance criterion")


def build_recon_signals(ctx: Any) -> tuple[ReconSignal, ...]:
    """The seven requirement-shape signals, with provenance on each.

    Deliberately broader than :func:`ats.corpus.mine.build_signals`: the
    modality signal matches case-insensitively where the miner matches the
    canonical uppercase surfaces only, and six of the seven have no counterpart
    in the miner at all. The breadth is the instrument -- a narrow selector that
    found nothing would not distinguish "the corpus has no obligations" from
    "the selector cannot see them".
    """
    deontic = _deontic_phrases(ctx)
    return (
        ReconSignal(
            signal_id="normative-modality",
            description=(
                "A deontic surface: MUST, MUST NOT, SHOULD, SHOULD NOT, MAY, CAN, CANNOT, "
                "SHALL, SHALL NOT, matched case-insensitively."
            ),
            spec_ref="ATS-1 8.16, 8.17, 9.3.2",
            vocabulary_source=(
                "deontic_force.terms[].surface and deontic_force.noncanonical in "
                "ats_force_lexicon_v1.yaml, matched case-insensitively -- deliberately "
                "broader than ats.corpus.mine's case-sensitive canonical match, which "
                "SAMPLING_FRAME.md records as never nominating a lowercase deontic"
            ),
            origin="lexicon",
            detection="phrase",
            phrases=deontic,
            not_matched=("IS REQUIRED BY <source> (a template with a placeholder)",),
        ),
        ReconSignal(
            signal_id="explicit-actor",
            description=(
                "A named party immediately left of a deontic surface, in Section 9.3.5's "
                "canonical order, that is not one of the concealing forms Section 9.3.4 "
                "names nonconforming."
            ),
            spec_ref="ATS-1 9.3.4, 9.3.5",
            vocabulary_source=(
                "no_declared_vocabulary: ATS-1 enumerates no actor vocabulary. It enumerates "
                "only the concealing forms (9.3.4, 21.4), imported here as "
                "ats.rules.deterministic.requirements.CONCEALING_ACTORS, so an actor is "
                "observed structurally as a short non-concealing subject phrase preceding "
                "the deontic rather than matched against a word list"
            ),
            origin="no_declared_vocabulary",
            detection="structural",
        ),
        ReconSignal(
            signal_id="condition-or-trigger",
            description=(
                "A conditional or event opener: if, when, while, only when -- Section "
                "9.3.6's event/state distinction rendered in Section 9.3.5's forms."
            ),
            spec_ref="ATS-1 9.3.5, 9.3.6",
            vocabulary_source=(
                "the openers used verbatim by the recommended forms enumerated in ATS-1 "
                "9.3.5 and the examples in 9.3.6"
            ),
            origin="spec_enumeration",
            detection="phrase",
            phrases=CONDITION_TRIGGER_OPENERS,
            not_matched=CONDITION_TRIGGER_UNMATCHED,
        ),
        ReconSignal(
            signal_id="threshold",
            description="A comparative or inclusivity bound on a quantity.",
            spec_ref="ATS-1 9.3.8, 10.10",
            vocabulary_source=(
                "ats.rules.deterministic.quantity.BOUNDARY_TERMS, the comparator words "
                "enumerated in ATS-1 9.3.8 and 10.10, imported from the ATS-NUM-002 "
                "detector rather than restated"
            ),
            origin="detector_vocabulary",
            detection="phrase",
            phrases=tuple(sorted(BOUNDARY_TERMS)),
            not_matched=THRESHOLD_UNMATCHED,
        ),
        ReconSignal(
            signal_id="acceptance-criterion",
            description="The observable-evidence slot Section 9.3.2 requires, named in prose.",
            spec_ref="ATS-1 9.3.2",
            vocabulary_source=(
                "the acceptance_criterion slot declared in "
                "ats_common_v1#/$defs/requirement_slots, with its plural surface"
            ),
            origin="normative_schema_enum",
            detection="phrase",
            phrases=_acceptance_phrases(ctx),
        ),
        ReconSignal(
            signal_id="prohibition-or-permission",
            description="A prohibiting or permitting deontic surface, matched case-insensitively.",
            spec_ref="ATS-1 8.16, 9.3.2",
            vocabulary_source=(
                "deontic_force surfaces whose lexicon term id ends in _NOT or is MAY, plus "
                "the noncanonical negated surfaces, in ats_force_lexicon_v1.yaml"
            ),
            origin="lexicon",
            detection="phrase",
            phrases=_prohibition_permission_phrases(ctx),
        ),
        ReconSignal(
            signal_id="enumerated-obligation",
            description=(
                f"A list whose items carry a modality on at least "
                f"{ENUMERATED_OBLIGATION_QUORUM} lines: several required behaviours "
                "enumerated together."
            ),
            spec_ref="ATS-1 9.3.3",
            vocabulary_source=(
                "no_declared_vocabulary: ATS-1 enumerates no list vocabulary. The shape is "
                "observed structurally over the block model -- a list block whose sibling "
                f"lines carry the normative-modality vocabulary on at least "
                f"{ENUMERATED_OBLIGATION_QUORUM} of them"
            ),
            origin="no_declared_vocabulary",
            detection="structural",
        ),
    )


@dataclass(frozen=True, slots=True)
class _Matchers:
    """Compiled patterns for one signal set, built once per corpus."""

    modality: re.Pattern[str]
    by_signal: Mapping[str, re.Pattern[str]]


def compile_matchers(signals: Sequence[ReconSignal]) -> _Matchers:
    """Compile every phrase signal, case-insensitively.

    Case-insensitivity is the deliberate widening. ADR-0006 keeps
    ``contains_exact`` case-sensitive because Section 1.3 makes the deontic
    keywords normative only in uppercase; that is right for a *detector*, whose
    output is a finding. Nothing here raises a finding, and the question is
    whether obligation-shaped prose exists at all.
    """
    by_signal: dict[str, re.Pattern[str]] = {}
    for signal in signals:
        if signal.detection != "phrase":
            continue
        pattern = _word_pattern(signal.phrases, flags=re.IGNORECASE)
        if pattern is None:  # pragma: no cover - ReconSignal refuses this at construction
            raise UsageError(f"signal {signal.signal_id} compiled to no pattern")
        by_signal[signal.signal_id] = pattern
    if "normative-modality" not in by_signal:
        raise UsageError(
            "the modality signal is missing; the structural signals are defined over it and "
            "would silently never fire"
        )
    return _Matchers(modality=by_signal["normative-modality"], by_signal=by_signal)


def _has_explicit_actor(matchers: _Matchers, sentence: str) -> bool:
    """Whether a non-concealing subject phrase sits immediately left of a modality.

    Section 9.3.5 puts optional scope, trigger, and condition before the actor
    and separates them with punctuation, so the actor is the last comma- or
    semicolon-delimited segment of the left context. Section 9.3.4 names the
    forms that conceal it; those are imported, and everything else short enough
    to be a subject noun phrase counts.
    """
    for match in matchers.modality.finditer(sentence):
        prefix = sentence[: match.start()]
        segment = re.split(r"[,;:]", prefix)[-1].strip()
        if not segment:
            continue
        words = segment.split()
        if not 1 <= len(words) <= ACTOR_PREFIX_MAX_WORDS:
            continue
        if not any(word[:1].isalpha() for word in words):
            continue
        head = segment.casefold().strip(" \t\"'`*_()[]")
        if head in CONCEALING_ACTORS or head.removeprefix("the ").strip() in CONCEALING_ACTORS:
            continue
        return True
    return False


def _is_enumerated_obligation(matchers: _Matchers, block: Block, block_text: str) -> bool:
    """Whether ``block`` is a list enumerating several required behaviours."""
    if block.kind not in ("list", "list_item"):
        return False
    lines = [line for line in block_text.split("\n") if line.strip()]
    carrying = sum(1 for line in lines if matchers.modality.search(line))
    return carrying >= ENUMERATED_OBLIGATION_QUORUM


def fired_signals(
    matchers: _Matchers, *, sentence: str, block: Block, block_text: str
) -> tuple[str, ...]:
    """Every signal that fires on one span, in a deterministic order."""
    fired: list[str] = []
    for signal_id, pattern in sorted(matchers.by_signal.items()):
        if pattern.search(sentence):
            fired.append(signal_id)
    if _has_explicit_actor(matchers, sentence):
        fired.append("explicit-actor")
    if _is_enumerated_obligation(matchers, block, block_text):
        fired.append("enumerated-obligation")
    return tuple(sorted(fired))


# -- candidate spans ---------------------------------------------------------

#: The shortest and longest span the selector will put in front of a
#: classifier. Below the floor a "sentence" is a fragment a heading split off;
#: above the ceiling it is an unsegmented block, and the classifier would be
#: judging a page. Mechanical bounds on the segmentation, declared rather than
#: buried.
MIN_SPAN_CHARS: Final[int] = 40
MAX_SPAN_CHARS: Final[int] = 700

#: How many distinct signals a span must carry to be admissible. One opener is
#: not a requirement shape -- "if" appears in every kind of prose -- and the
#: study is about requirement-*shaped* text, not about any single cue. The pool
#: at every signal count is reported, so the floor can be argued with.
MIN_SIGNALS_TO_ADMIT: Final[int] = 2

#: At or above this many signals a span is treated as strongly requirement
#: shaped, which is the population explanation 4 is tested over: "annotators
#: consistently say mixed or reserved_profile on genuine specification prose"
#: needs a declared definition of genuine specification prose.
SPECIFICATION_SHAPE_SIGNALS: Final[int] = 4

#: Sentence segmentation. Imported from the frame so the two governance
#: artifacts agree about what a sentence is.
_SENTENCE_SPLIT: Final[re.Pattern[str]] = fr._SENTENCE_SPLIT


@dataclass(frozen=True, slots=True)
class Candidate:
    """One admissible span, before selection decides whether to take it."""

    repository: str
    artifact_id: str
    span: tuple[int, int]
    signals: tuple[str, ...]
    block_kind: str

    @property
    def signal_count(self) -> int:
        return len(self.signals)


def _sentence_spans(text: str, block: Block) -> list[tuple[int, int]]:
    """Absolute character spans of the sentences inside ``block``.

    Segmentation runs over ``text[block.start:block.end]`` rather than over
    ``block.text``: the parser's block text is normalised, and a span built from
    normalised offsets would not index the document the bundle pins by hash.
    """
    raw = text[block.start : block.end]
    spans: list[tuple[int, int]] = []
    cursor = 0
    for piece in _SENTENCE_SPLIT.split(raw):
        start = raw.find(piece, cursor)
        if start < 0:  # pragma: no cover - split pieces are substrings by construction
            continue
        end = start + len(piece)
        cursor = end
        stripped = piece.strip()
        if not stripped:
            continue
        lead = len(piece) - len(piece.lstrip())
        trail = len(piece) - len(piece.rstrip())
        spans.append((block.start + start + lead, block.start + end - trail))
    return spans


def build_recon_pool(
    ctx: Any, sources: Sequence[Mapping[str, Any]]
) -> tuple[list[Candidate], dict[str, Mapping[str, Any]], dict[str, str], dict[str, Any]]:
    """Every admissible span across the authorised corpus, plus the indexes.

    ``sources`` is one entry per repository that already cleared
    :data:`ats.corpus.frame.REQUIRED_USES`, carrying its ``inventory`` and its
    resolved ``declaration``. Path-level authority is re-resolved per document
    with :func:`ats.corpus.frame.path_permitted`, so a declaration's ``exclude``
    globs are honoured at the document level and not only at the repository
    level. No mining result is read: the whole point is a selector independent
    of the miner.
    """
    signals = build_recon_signals(ctx)
    matchers = compile_matchers(signals)

    candidates: list[Candidate] = []
    artifacts: dict[str, Mapping[str, Any]] = {}
    texts: dict[str, str] = {}
    blocks_by_artifact: dict[str, list[Block]] = {}
    dropped: list[dict[str, str]] = []
    documents_with_signal: dict[str, set[str]] = {s.signal_id: set() for s in signals}
    spans_with_signal: dict[str, int] = {s.signal_id: 0 for s in signals}

    for source in sources:
        repository = str(source["repository"])
        declaration = source["declaration"]
        inventory = source["inventory"]
        repo_path = inventory["repository"]

        for artifact in inventory["artifacts"]:
            path = str(artifact["path"])
            if not fr.path_permitted(declaration, path):
                dropped.append(
                    {
                        "repository": repository,
                        "path": path,
                        "reason": "the declaration does not permit the required uses for this path",
                    }
                )
                continue
            artifact_id = str(artifact["artifact_id"])
            artifacts[artifact_id] = artifact
            text = inv.artifact_text(repo_path, artifact)
            texts[artifact_id] = text
            blocks = document_blocks(
                text, media_type=artifact.get("media_type", "text/markdown")
            )
            blocks_by_artifact[artifact_id] = blocks

            for block in blocks:
                # Section 5.6 exempts quoted source text, code, and logs from
                # surface rules: a deontic keyword inside a fenced example is a
                # quotation of a keyword, not an obligation.
                if block.kind in EXEMPT_BLOCK_KINDS:
                    continue
                block_text = text[block.start : block.end]
                for start, end in _sentence_spans(text, block):
                    if not MIN_SPAN_CHARS <= end - start <= MAX_SPAN_CHARS:
                        continue
                    fired = fired_signals(
                        matchers,
                        sentence=text[start:end],
                        block=block,
                        block_text=block_text,
                    )
                    if not fired:
                        continue
                    for signal_id in fired:
                        spans_with_signal[signal_id] += 1
                        documents_with_signal[signal_id].add(artifact_id)
                    if len(fired) < MIN_SIGNALS_TO_ADMIT:
                        continue
                    candidates.append(
                        Candidate(
                            repository=repository,
                            artifact_id=artifact_id,
                            span=(start, end),
                            signals=fired,
                            block_kind=block.kind,
                        )
                    )

    index = {
        "blocks": blocks_by_artifact,
        "dropped": dropped,
        "signals": signals,
        "spans_with_signal": spans_with_signal,
        "documents_with_signal": {k: len(v) for k, v in documents_with_signal.items()},
    }
    return candidates, artifacts, texts, index


# -- selection ---------------------------------------------------------------


def _order_key(seed: int, candidate: Candidate) -> tuple[int, str]:
    """Most requirement-shaped first, ties broken by a seeded per-span digest.

    Ranking on signal breadth is the declared selector: the study is looking for
    requirement-*shaped* text, and a pool ordered by document order would draw
    whatever sits at the top of the largest file. The tie-break is a pure
    function of the seed and the span's own identity, so adding a document
    cannot reorder the rest.
    """
    digest = sha256_hex(
        f"{seed}\x1f{candidate.artifact_id}\x1f{candidate.span[0]}\x1f{candidate.span[1]}".encode(
            "utf-8"
        )
    )
    return (-candidate.signal_count, digest)


def select_recon_bundles(
    seed: int,
    target: int,
    candidates: Sequence[Candidate],
    groups: Mapping[str, str],
    *,
    max_repository_share: float = fr.MAX_REPOSITORY_SHARE,
) -> tuple[list[Candidate], dict[str, Any]]:
    """Draw the study's bundles, round-robin over repositories.

    Three rules, all of them the frame's and none of them re-derived:
    at most one selection per leakage component (:func:`ats.corpus.frame.leakage_groups`),
    at most :data:`ats.corpus.frame.MAX_REPOSITORY_SHARE` of the target from any
    one repository, and a round-robin over repositories so no repository can
    dominate merely by being large. A shortfall is reported with the pool it
    exhausted rather than repaired by lifting a cap.
    """
    if target < 1:
        raise UsageError(f"target must be at least 1; got {target}")
    cap = max(1, math.ceil(target * max_repository_share))

    by_repository: dict[str, list[Candidate]] = {}
    for candidate in sorted(candidates, key=lambda c: _order_key(seed, c)):
        by_repository.setdefault(candidate.repository, []).append(candidate)

    cursors = {name: 0 for name in by_repository}
    counts = {name: 0 for name in by_repository}
    used_groups: set[str] = set()
    taken: list[Candidate] = []
    used_documents: set[str] = set()

    order = sorted(by_repository)
    progress = True
    while len(taken) < target and progress:
        progress = False
        for repository in order:
            if len(taken) >= target:
                break
            if counts[repository] >= cap:
                continue
            pool = by_repository[repository]
            index = cursors[repository]
            while index < len(pool):
                candidate = pool[index]
                index += 1
                group = groups.get(candidate.artifact_id)
                if group is None:
                    raise UsageError(
                        f"{candidate.artifact_id} carries no leakage group; selecting it would "
                        "place an ungrouped bundle in a study that promises one per component"
                    )
                if group in used_groups:
                    continue
                used_groups.add(group)
                used_documents.add(candidate.artifact_id)
                counts[repository] += 1
                taken.append(candidate)
                progress = True
                break
            cursors[repository] = index

    report: dict[str, Any] = {
        "target": target,
        "selected": len(taken),
        "repository_cap": cap,
        "per_repository": dict(sorted(counts.items())),
        "components_consumed": len(used_groups),
        "documents": len(used_documents),
    }
    if len(taken) < target:
        report["shortfall_reason"] = (
            f"selected {len(taken)} of {target}: every remaining admissible span belongs to a "
            f"leakage component already represented, or to a repository already at its cap of "
            f"{cap}"
        )
    return taken, report


# -- blinding ----------------------------------------------------------------

#: What a classifier sees for one bundle. An allow-list, in the same shape as
#: :func:`ats.corpus.round.blind_item`: a denylist silently admits any field
#: added later, and the field that must never travel -- the signals that
#: surfaced the span -- is precisely the study's own prediction about the text.
CLASSIFIER_VISIBLE_FIELDS: Final[tuple[str, ...]] = (
    "bundle_id",
    "span_text",
    "heading_path",
    "containing_block_text",
    "preceding_context",
    "following_context",
    "local_definitions",
    "glossary_entries",
    "context_completeness",
)

#: Why the rest is withheld.
BLINDING_RATIONALE: Final[str] = (
    "The fired signals are this study's prediction about the text, and the study measures "
    "whether an independent reader agrees. A classifier told that a modality, an actor, a "
    "trigger, and an acceptance criterion were all detected has been handed the shape of "
    "SPECIFY and asked whether it sees SPECIFY (spec Sections 13.2, 16.5, 17.8)."
)

#: Bundle fields the projection renames rather than withholds. ``containing_block``
#: travels as ``containing_block_text``; listing it as withheld would report a
#: blinding this study does not perform.
_PROJECTED_ALIASES: Final[frozenset[str]] = frozenset({"containing_block"})


def withheld_from_classifier(ctx: Any) -> tuple[str, ...]:
    """Every field the classifier does not see, derived from the two schemas.

    Derived rather than enumerated, for the same reason
    :func:`ats.corpus.frame.withheld_fields` is: a property added to the context
    bundle or to this report's selection row is withheld until somebody
    deliberately adds it to :data:`CLASSIFIER_VISIBLE_FIELDS`. A hand-written
    list would silently admit it.
    """
    bundle = set(ctx.schemas.schema("ats_context_bundle_v1.schema.json")["properties"])
    selection = set(
        ctx.schemas.schema(SCHEMA_ID)["properties"]["selection"]["items"]["properties"]
    )
    return tuple(
        sorted((bundle | selection) - set(CLASSIFIER_VISIBLE_FIELDS) - _PROJECTED_ALIASES)
    )


def blind_recon_item(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """What a classifier sees for one bundle, and nothing else.

    Built by naming what is included. The selection row -- with its
    ``signals_fired``, its repository, and its split group -- is never passed
    here at all, so there is no field on it that a future edit could leak.
    """
    block = bundle.get("containing_block") or {}
    return {
        "bundle_id": bundle["bundle_id"],
        "span_text": bundle["span_text"],
        "heading_path": list(bundle.get("heading_path", ())),
        "containing_block_text": block.get("text", "") if isinstance(block, Mapping) else "",
        "preceding_context": bundle.get("preceding_context"),
        "following_context": bundle.get("following_context"),
        "local_definitions": list(bundle.get("local_definitions", ())),
        "glossary_entries": list(bundle.get("glossary_entries", ())),
        "context_completeness": bundle.get("context_completeness"),
    }


# -- classification vocabulary -----------------------------------------------

#: The six admissible classifications. ``insufficient_context`` is a real
#: answer, not a failure to produce one (ADR-0002), and it is the answer that
#: makes explanation 3 detectable at all.
CLASSES: Final[tuple[str, ...]] = (
    "SPECIFY",
    "ASSESS",
    "mixed",
    "reserved_profile",
    "not_applicable",
    "insufficient_context",
)


def load_classifications(
    path: str | Path, annotator_id: str, *, bundle_ids: Iterable[str] | None = None
) -> tuple[list[dict[str, Any]], int]:
    """Read one pass's raw judgments, refusing anything outside :data:`CLASSES`.

    Returns ``(rows, refused)``. A classification outside the vocabulary is
    dropped and counted rather than repaired into the nearest legal value:
    repairing it would invent an opinion nobody held, and counting it lets the
    pass report how many judgments it failed to obtain instead of silently
    shrinking.
    """
    source = Path(path)
    if not source.is_file():
        raise UsageError(
            f"no judgments at {source}; a pass with no judgments is not a pass with no "
            "disagreements"
        )
    admissible = set(bundle_ids) if bundle_ids is not None else None
    rows: list[dict[str, Any]] = []
    refused = 0
    seen: set[str] = set()
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        bundle_id = str(raw.get("bundle_id", ""))
        answer = raw.get("answer")
        if not isinstance(answer, Mapping) or answer.get("classification") not in CLASSES:
            refused += 1
            continue
        if admissible is not None and bundle_id not in admissible:
            refused += 1
            continue
        if bundle_id in seen:
            refused += 1
            continue
        seen.add(bundle_id)
        rows.append(
            {
                "bundle_id": bundle_id,
                "annotator_id": annotator_id,
                "classification": str(answer["classification"]),
                "rationale": str(answer.get("rationale") or "").strip()[:600],
                "persuasive_signals": [
                    str(s)[:200] for s in (answer.get("persuasive_signals") or []) if str(s).strip()
                ],
                "requested_additional_context": [
                    str(s)[:200]
                    for s in (answer.get("requested_additional_context") or [])
                    if str(s).strip()
                ],
                "evidence_offsets": [
                    [int(pair[0]), int(pair[1])]
                    for pair in (answer.get("evidence_offsets") or [])
                    if isinstance(pair, (list, tuple))
                    and len(pair) == 2
                    and _is_span(pair)
                ],
            }
        )
    rows.sort(key=lambda row: row["bundle_id"])
    return rows, refused


def _is_span(pair: Sequence[Any]) -> bool:
    try:
        start, end = int(pair[0]), int(pair[1])
    except (TypeError, ValueError):
        return False
    return 0 <= start < end


# -- agreement ---------------------------------------------------------------


def agreement_between(
    rows: Sequence[Mapping[str, Any]],
    annotators: Sequence[str],
    signals_by_bundle: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """Per-class agreement between two passes, with every disagreement kept.

    Reported per class rather than pooled. A single number hides which class the
    instrument is unstable on, and the class this study turns on -- SPECIFY --
    is the rare one, so a pooled figure dominated by ASSESS would say nothing
    about it. The per-class figure is ``both / either``: of the bundles either
    pass put in the class, the share both did. Zero over zero is ``null``, not
    agreement.
    """
    if len(annotators) != 2:
        raise UsageError(
            f"agreement is measured between exactly two passes; got {len(annotators)}"
        )
    first, second = annotators
    by_annotator: dict[str, dict[str, str]] = {first: {}, second: {}}
    rationale: dict[tuple[str, str], str] = {}
    for row in rows:
        annotator = str(row["annotator_id"])
        if annotator not in by_annotator:
            raise UsageError(
                f"judgment from unregistered annotator {annotator!r}; every classification "
                "must name a pass the report declares"
            )
        by_annotator[annotator][str(row["bundle_id"])] = str(row["classification"])
        rationale[(annotator, str(row["bundle_id"]))] = str(row.get("rationale", ""))

    shared = sorted(set(by_annotator[first]) & set(by_annotator[second]))
    agreed = sum(1 for b in shared if by_annotator[first][b] == by_annotator[second][b])

    per_class: list[dict[str, Any]] = []
    for label in CLASSES:
        a_set = {b for b in shared if by_annotator[first][b] == label}
        b_set = {b for b in shared if by_annotator[second][b] == label}
        both = len(a_set & b_set)
        either = len(a_set | b_set)
        per_class.append(
            {
                "classification": label,
                "by_annotator": [
                    {"annotator_id": first, "count": len(a_set)},
                    {"annotator_id": second, "count": len(b_set)},
                ],
                "both": both,
                "either": either,
                "agreement": (both / either) if either else None,
            }
        )

    disagreements = [
        {
            "bundle_id": bundle_id,
            "labels": [
                {
                    "annotator_id": annotator,
                    "classification": by_annotator[annotator][bundle_id],
                    "rationale": rationale.get((annotator, bundle_id), ""),
                }
                for annotator in (first, second)
            ],
            "signals_fired": list(signals_by_bundle.get(bundle_id, ())),
        }
        for bundle_id in shared
        if by_annotator[first][bundle_id] != by_annotator[second][bundle_id]
    ]

    return {
        "compared": len(shared),
        "agreed": agreed,
        "observed_agreement": (agreed / len(shared)) if shared else 0.0,
        "per_class": per_class,
        "disagreements": disagreements,
        "caveat": INSTRUMENT_CAVEAT,
    }


# -- verdict -----------------------------------------------------------------

#: The share of classified bundles at which a class is a finding rather than a
#: handful. Repository policy, declared here -- before any pass ran -- so a
#: criterion cannot be tuned to the answer it produced.
MATERIAL_SHARE: Final[float] = 0.25

#: The share below which a class is negligible.
NEGLIGIBLE_SHARE: Final[float] = 0.10

#: The share of one population that makes a reading predominant rather than
#: present.
PREDOMINANCE_SHARE: Final[float] = 0.60

#: The share of the bundle target the selector must reach before a shortfall
#: stops being a scarcity finding about the corpus.
MINIMUM_SELECTOR_YIELD: Final[float] = 0.75


def _share(numerator: int, denominator: int) -> float:
    return (numerator / denominator) if denominator else 0.0


def evaluate_explanations(counts: Mapping[str, int]) -> list[dict[str, Any]]:
    """Test each explanation independently against its declared threshold.

    Independently, not in priority order. An ordered cascade would let the first
    test that happens to pass suppress a second reading the evidence supports
    equally well, which is how a study picks an answer to have picked one. The
    cost is that several criteria can hold at once; that is reported as
    ``undecided`` by :func:`decide`, which is the honest outcome.
    """
    n = counts["compared"]
    strong = counts["strongly_shaped_compared"]
    specify_either = counts["specify_either"]

    criteria: list[dict[str, Any]] = []

    absence_agreed = counts["specify_both"] + counts["mixed_both"]
    yield_short = _share(counts["selected"], counts["target"]) < MINIMUM_SELECTOR_YIELD
    criteria.append(
        {
            "explanation_id": "true_corpus_absence",
            "supported": _share(absence_agreed, n) <= NEGLIGIBLE_SHARE or yield_short,
            "test": (
                f"agreed SPECIFY or mixed at or below {NEGLIGIBLE_SHARE:.0%} of compared "
                f"bundles, or the selector filled under {MINIMUM_SELECTOR_YIELD:.0%} of its "
                "target from the authorised corpus"
            ),
            "observed": (
                f"{absence_agreed}/{n} agreed SPECIFY-or-mixed ({_share(absence_agreed, n):.1%}); "
                f"selector filled {counts['selected']}/{counts['target']} "
                f"({_share(counts['selected'], counts['target']):.0%}) from "
                f"{counts['admissible_spans']} admissible spans in "
                f"{counts['admissible_documents']} documents"
            ),
            "limb": "classification" if _share(absence_agreed, n) <= NEGLIGIBLE_SHARE else "yield",
        }
    )

    criteria.append(
        {
            "explanation_id": "candidate_mining_deficiency",
            "supported": (
                _share(counts["specify_both"] + counts["mixed_both"], n) >= MATERIAL_SHARE
                and counts["corpus_declared_specify"] == 0
            ),
            "test": (
                f"both passes agree SPECIFY or mixed on at least {MATERIAL_SHARE:.0%} of "
                "compared bundles while the production path declares zero SPECIFY over the "
                "same authorised corpus"
            ),
            "observed": (
                f"{counts['specify_both']} agreed SPECIFY and {counts['mixed_both']} agreed "
                f"mixed of {n} compared "
                f"({_share(counts['specify_both'] + counts['mixed_both'], n):.1%}); the "
                f"authorised corpus declares {counts['corpus_declared_specify']} SPECIFY "
                "hypotheses"
            ),
        }
    )

    context_linked = counts["specify_with_context_request"]
    criteria.append(
        {
            "explanation_id": "context_bundle_deficiency",
            "supported": (
                (specify_either > 0 and _share(context_linked, specify_either) >= PREDOMINANCE_SHARE)
                or _share(counts["insufficient_both"], n) >= MATERIAL_SHARE
            ),
            "test": (
                f"at least {PREDOMINANCE_SHARE:.0%} of the bundles any pass called SPECIFY "
                "carry a request from that same pass for enclosing context, or both passes "
                f"agree insufficient_context on at least {MATERIAL_SHARE:.0%} of compared "
                "bundles"
            ),
            "observed": (
                f"{context_linked}/{specify_either} SPECIFY judgments also requested context "
                f"({_share(context_linked, specify_either):.1%}); "
                f"{counts['insufficient_both']}/{n} agreed insufficient_context "
                f"({_share(counts['insufficient_both'], n):.1%})"
            ),
            "limb": "specify_context_linked"
            if specify_either > 0 and _share(context_linked, specify_either) >= PREDOMINANCE_SHARE
            else "insufficient_context",
        }
    )

    boundary = counts["mixed_both_strong"] + counts["reserved_both_strong"]
    criteria.append(
        {
            "explanation_id": "profile_boundary_defect",
            "supported": (
                _share(boundary, strong) >= MATERIAL_SHARE and boundary > counts["specify_both_strong"]
            ),
            "test": (
                f"among bundles carrying at least {SPECIFICATION_SHAPE_SIGNALS} signals -- the "
                "declared definition of genuine specification prose -- both passes agree "
                f"mixed or reserved_profile on at least {MATERIAL_SHARE:.0%} of them, and "
                "more often than they agree SPECIFY"
            ),
            "observed": (
                f"{boundary}/{strong} strongly shaped bundles agreed mixed-or-reserved "
                f"({_share(boundary, strong):.1%}) against {counts['specify_both_strong']} "
                "agreed SPECIFY"
            ),
        }
    )
    return criteria


#: What would separate two readings the counts cannot. Keyed by the pair, so an
#: undecided verdict names an experiment rather than shrugging.
SEPARATORS: Final[dict[tuple[str, str], str]] = {
    ("candidate_mining_deficiency", "context_bundle_deficiency"): (
        "Rebuild the SPECIFY-classified bundles with their complete enclosing section and "
        "re-run both passes. If SPECIFY survives without a context request, the obligations "
        "were visible in the bundle and the miner is what missed them."
    ),
    ("candidate_mining_deficiency", "profile_boundary_defect"): (
        "Read the mixed rationales against Section 9.4. Composition at section level is "
        "something ATS-1 explicitly permits, so a mixed section the standard accommodates is "
        "a miner gap; a mixed verdict whose rationale says neither profile fits is a boundary "
        "defect."
    ),
    ("context_bundle_deficiency", "profile_boundary_defect"): (
        "Re-run the strongly shaped bundles with their enclosing section. A boundary defect "
        "survives more context; a bundle deficiency does not."
    ),
    ("true_corpus_absence", "candidate_mining_deficiency"): (
        "Widen the selector to single-signal spans and re-draw. If the pool grows and the "
        "classifications do not, the corpus is thin; if both grow, the selector was the bound."
    ),
    ("true_corpus_absence", "context_bundle_deficiency"): (
        "Draw document-level bundles rather than span-level ones. Absence survives the change; "
        "a bundle deficiency does not."
    ),
    ("true_corpus_absence", "profile_boundary_defect"): (
        "Classify the authored SPECIFY fixtures in corpus/seeds/ on the same rubric. If the "
        "instrument places known SPECIFY prose correctly, the corpus is thin rather than the "
        "boundary being wrong."
    ),
}

UNDECIDED_NOTHING_SUPPORTED: Final[str] = (
    "No criterion reached its declared threshold. The counts are consistent with more than "
    "one explanation and decisive for none, and naming one anyway would be choosing an answer "
    "to have chosen it."
)


def decide(criteria: Sequence[Mapping[str, Any]]) -> tuple[str, str, list[str]]:
    """``(explanation, statement, what_would_resolve)`` from the evaluated criteria."""
    supported = [str(c["explanation_id"]) for c in criteria if c["supported"]]
    statements = dict(EXPLANATIONS)
    if len(supported) == 1:
        winner = supported[0]
        unsupported = [e for e in EXPLANATION_IDS if e != winner]
        return (
            winner,
            statements[winner],
            [
                f"What would overturn this verdict in favour of {other}: "
                + _separator(winner, other)
                for other in unsupported
            ],
        )
    if not supported:
        return "undecided", UNDECIDED_NOTHING_SUPPORTED, [
            "Draw a larger sample: at 40 bundles a class has to reach roughly a quarter of "
            "the draw before it clears the material threshold, so a real but modest effect "
            "cannot show.",
            "Classify the authored fixtures in corpus/seeds/ on the same rubric to establish "
            "whether the instrument places known SPECIFY prose at all.",
        ]
    pairs = [
        _separator(a, b)
        for i, a in enumerate(supported)
        for b in supported[i + 1 :]
    ]
    return (
        "undecided",
        "The evidence supports "
        + ", ".join(supported)
        + " at their declared thresholds and does not separate them. Naming one would be a "
        "choice, not a finding.",
        pairs,
    )


def _separator(first: str, second: str) -> str:
    key = (first, second) if (first, second) in SEPARATORS else (second, first)
    return SEPARATORS.get(
        key,
        f"No separating experiment is declared for {first} against {second}; one must be "
        "designed before either is acted on.",
    )


def tally(
    classifications: Sequence[Mapping[str, Any]],
    annotators: Sequence[str],
    selection: Sequence[Mapping[str, Any]],
    *,
    target: int,
    admissible_spans: int,
    admissible_documents: int,
    corpus_declared_specify: int,
) -> dict[str, int]:
    """Every count the verdict criteria cite, derived once so they cannot drift."""
    first, second = annotators
    labels: dict[str, dict[str, str]] = {first: {}, second: {}}
    asked: dict[str, set[str]] = {first: set(), second: set()}
    for row in classifications:
        annotator = str(row["annotator_id"])
        bundle_id = str(row["bundle_id"])
        labels[annotator][bundle_id] = str(row["classification"])
        if row.get("requested_additional_context"):
            asked[annotator].add(bundle_id)

    shared = set(labels[first]) & set(labels[second])
    strong = {
        str(row["bundle_id"])
        for row in selection
        if int(row["signal_count"]) >= SPECIFICATION_SHAPE_SIGNALS
    }

    def both(label: str, population: set[str] | None = None) -> int:
        pool = shared if population is None else shared & population
        return sum(1 for b in pool if labels[first][b] == label == labels[second][b])

    def either(label: str) -> int:
        return sum(
            1 for b in shared if label in (labels[first][b], labels[second][b])
        )

    specify_with_context_request = sum(
        1
        for b in shared
        if any(
            labels[annotator][b] == "SPECIFY" and b in asked[annotator]
            for annotator in (first, second)
        )
    )

    return {
        "target": target,
        "selected": len(selection),
        "admissible_spans": admissible_spans,
        "admissible_documents": admissible_documents,
        "compared": len(shared),
        "strongly_shaped_selected": len(strong),
        "strongly_shaped_compared": len(shared & strong),
        "corpus_declared_specify": corpus_declared_specify,
        "specify_both": both("SPECIFY"),
        "specify_either": either("SPECIFY"),
        "specify_both_strong": both("SPECIFY", strong),
        "mixed_both": both("mixed"),
        "mixed_either": either("mixed"),
        "mixed_both_strong": both("mixed", strong),
        "reserved_both": both("reserved_profile"),
        "reserved_either": either("reserved_profile"),
        "reserved_both_strong": both("reserved_profile", strong),
        "assess_both": both("ASSESS"),
        "not_applicable_both": both("not_applicable"),
        "insufficient_both": both("insufficient_context"),
        "insufficient_either": either("insufficient_context"),
        "specify_with_context_request": specify_with_context_request,
    }


# -- report ------------------------------------------------------------------

#: The context dimensions :func:`ats.corpus.context.build_context_bundle` rates.
#: Named here rather than discovered from the bundle, so a dimension added to
#: the bundle schema and not to this study shows up as a missing column instead
#: of quietly widening a denominator.
CONTEXT_DIMENSIONS: Final[tuple[str, ...]] = (
    "preceding_context",
    "following_context",
    "diff",
    "review_comment",
    "later_edit",
    "policy_context",
)


class _ContextTally:
    """How much context the drawn bundles carried, counted per dimension.

    ``context_completeness`` is one word over six dimensions and an unknown
    profile basis degrades it on its own, so ``insufficient`` on every bundle
    reads as "the enclosing prose was withheld" when it may mean nothing of the
    kind. Keeping the per-dimension tally is what lets the narrative tell those
    two apart: whether the classifier's requests for enclosing context are
    requests for something the bundle actually omitted is the whole of the
    ``context_bundle_deficiency`` reading.
    """

    __slots__ = ("completeness", "profile_basis", "dimensions")

    def __init__(self) -> None:
        self.completeness: dict[str, int] = {}
        self.profile_basis: dict[str, int] = {}
        self.dimensions: dict[str, dict[str, int]] = {d: {} for d in CONTEXT_DIMENSIONS}

    @staticmethod
    def _bump(counter: dict[str, int], key: str) -> None:
        counter[key] = counter.get(key, 0) + 1

    def add(self, bundle: Mapping[str, Any]) -> None:
        self._bump(self.completeness, str(bundle["context_completeness"]))
        basis = (bundle.get("profile_hypothesis") or {}).get("basis")
        self._bump(self.profile_basis, "absent" if basis is None else str(basis))
        for dimension in CONTEXT_DIMENSIONS:
            block = bundle.get(dimension) or {}
            availability = block.get("availability")
            self._bump(
                self.dimensions[dimension],
                "absent" if availability is None else str(availability),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "completeness": dict(sorted(self.completeness.items())),
            "profile_basis": dict(sorted(self.profile_basis.items())),
            "dimension_availability": {
                dimension: dict(sorted(statuses.items()))
                for dimension, statuses in self.dimensions.items()
            },
        }



def draw_recon_bundles(
    ctx: Any,
    *,
    repositories: Sequence[Mapping[str, Any]],
    seed: int,
    target_bundles: int = 40,
    authority_overlay: str | Path = "corpus/authority",
    bundle_sink: Any = None,
) -> dict[str, Any]:
    """Resolve authority, build the pool, draw the bundles, and build them.

    Split out from :func:`build_profile_reconnaissance` because the bundles have
    to exist before the classification passes can run, and the report has to be
    built from the same draw afterwards. One function, called twice, is what
    stops the two from diverging: a second selection path could reorder the
    draw and leave judgments bound to bundles the report does not contain.

    ``repositories`` is one row per census repository carrying ``repository``,
    ``family``, ``domain``, ``revision`` and, for the ones expected to be
    authorised, an ``inventory``. Authority is resolved before any span is read,
    so there is no code path on which an unauthorised repository contributes a
    bundle.
    """
    authority = fr.resolve_annotation_authority(
        repositories, authority_overlay, now=ctx.timestamp()
    )
    declarations = authority["declarations"]
    sources = [
        {**row, "declaration": declarations[str(row["repository"])]}
        for row in repositories
        if str(row["repository"]) in declarations
    ]
    missing = sorted(str(row["repository"]) for row in sources if not row.get("inventory"))
    if missing:
        raise UsageError(
            f"repositories {missing} resolved authorised but were supplied no inventory; a "
            "study that quietly omits an authorised repository misreports the corpus it read"
        )
    if not sources:
        raise UsageError(
            f"no repository permits both {' and '.join(fr.REQUIRED_USES)}; a reconnaissance "
            "drawn anyway would be a governance failure"
        )

    candidates, artifacts, texts, index = build_recon_pool(ctx, sources)
    families = {str(row["repository"]): str(row["family"]) for row in sources}
    domains = {str(row["repository"]): str(row["domain"]) for row in sources}
    repo_paths = {str(row["repository"]): row["inventory"]["repository"] for row in sources}

    groups = fr.leakage_groups(
        ctx, sorted(artifacts.values(), key=lambda a: a["artifact_id"]), domains
    )
    picks, draw = select_recon_bundles(seed, target_bundles, candidates, groups)

    selection: list[dict[str, Any]] = []
    context_tally = _ContextTally()
    for pick in sorted(picks, key=lambda c: (c.artifact_id, c.span)):
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
        context_tally.add(bundle)
        if bundle_sink is not None:
            # The report records a bundle_id but not the span behind it, so a
            # bundle discarded here could not be rebuilt. The classifier reads
            # the caller-supplied bundle locally; export policy may withhold raw
            # source text from generated reports.
            bundle_sink.append(bundle)
        row: dict[str, Any] = {
            "bundle_id": bundle["bundle_id"],
            "source_artifact_id": str(artifact["artifact_id"]),
            "repository": repository,
            "document_family": families[repository],
            "domain": domains[repository],
            "split_group": groups[pick.artifact_id],
            "content_sha256": str(artifact["content_sha256"]),
            "heading_path": list(bundle.get("heading_path", ())),
            "signals_fired": list(pick.signals),
            "signal_count": pick.signal_count,
            "block_kind": pick.block_kind,
            "context_completeness": str(bundle["context_completeness"]),
        }
        declared = list(artifact.get("profile_hypotheses") or ())
        if declared:
            row["declared_profile_hypotheses"] = declared
        selection.append(row)
    selection.sort(key=lambda row: row["bundle_id"])

    return {
        "authority": authority,
        "artifacts": artifacts,
        "candidates": candidates,
        "index": index,
        "draw": draw,
        "selection": selection,
        "bundle_context": context_tally.to_dict(),
        # Declared hypotheses over the documents actually admitted here, so the
        # verdict's "the production path declares zero SPECIFY" limb is measured
        # against this corpus rather than quoted from another report.
        "declared_profiles": fr.authorised_profile_counts(artifacts.values()),
    }


def build_profile_reconnaissance(
    ctx: Any,
    *,
    repositories: Sequence[Mapping[str, Any]],
    seed: int,
    target_bundles: int = 40,
    authority_overlay: str | Path = "corpus/authority",
    annotators: Sequence[Any],
    judgment_paths: Mapping[str, str | Path],
    corpus_declared_specify: int | None = None,
    bundle_sink: Any = None,
) -> dict[str, Any]:
    """The reconnaissance report over the authorised caller-supplied corpus.

    ``annotators`` are :class:`ats.corpus.round.Annotator` records and
    ``judgment_paths`` maps each annotator id to its raw judgment file. Each
    pass is frozen by the content hash of its judgments with
    :func:`ats.corpus.round.freeze_pass` before agreement is computed, so a
    disagreement cannot be resolved by revising an earlier answer.

    ``corpus_declared_specify`` defaults to the count the draw measures over the
    documents it admitted. It is injectable so a test can exercise the verdict
    limb that reads it without building a corpus that declares one.
    """
    from .round import Annotator, freeze_pass  # keeps this module import-light

    if len(annotators) != 2:
        raise UsageError(
            "the study runs exactly two independent passes; one judgment is not an agreement "
            "measurement (spec 17.9)"
        )
    for annotator in annotators:
        if not isinstance(annotator, Annotator):
            raise UsageError(f"expected an ats.corpus.round.Annotator, got {type(annotator)!r}")

    drawn = draw_recon_bundles(
        ctx,
        repositories=repositories,
        seed=seed,
        target_bundles=target_bundles,
        authority_overlay=authority_overlay,
        bundle_sink=bundle_sink,
    )
    authority = drawn["authority"]
    artifacts = drawn["artifacts"]
    candidates = drawn["candidates"]
    index = drawn["index"]
    draw = drawn["draw"]
    selection = drawn["selection"]
    if corpus_declared_specify is None:
        corpus_declared_specify = int(drawn["declared_profiles"].get("SPECIFY", 0))

    bundle_ids = {row["bundle_id"] for row in selection}
    signals_by_bundle = {row["bundle_id"]: row["signals_fired"] for row in selection}

    classifications: list[dict[str, Any]] = []
    passes: list[dict[str, Any]] = []
    for annotator in annotators:
        path = judgment_paths[annotator.annotator_id]
        frozen = freeze_pass(annotator.annotator_id, path)
        rows, refused = load_classifications(
            path, annotator.annotator_id, bundle_ids=bundle_ids
        )
        classifications.extend(rows)
        if refused:
            frozen["refused"] = refused
        passes.append(frozen)
    classifications.sort(key=lambda row: (row["bundle_id"], row["annotator_id"]))

    annotator_ids = [a.annotator_id for a in annotators]
    agreement = agreement_between(classifications, annotator_ids, signals_by_bundle)
    counts = tally(
        classifications,
        annotator_ids,
        selection,
        target=target_bundles,
        admissible_spans=len(candidates),
        admissible_documents=len({c.artifact_id for c in candidates}),
        corpus_declared_specify=corpus_declared_specify,
    )
    counts["repository_cap"] = int(draw["repository_cap"])
    counts["components_consumed"] = int(draw["components_consumed"])
    criteria = evaluate_explanations(counts)
    explanation, statement, resolve = decide(criteria)
    if "shortfall_reason" in draw:
        resolve = [draw["shortfall_reason"], *resolve]

    signal_defs: Sequence[ReconSignal] = index["signals"]
    bundles_with_signal: dict[str, int] = {s.signal_id: 0 for s in signal_defs}
    for row in selection:
        for signal_id in row["signals_fired"]:
            bundles_with_signal[signal_id] += 1

    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": ctx.timestamp(),
        "study": {
            "question": STUDY_QUESTION,
            "explanations": [
                {"explanation_id": eid, "statement": text} for eid, text in EXPLANATIONS
            ],
            "instrument": INSTRUMENT_CAVEAT,
            "relationship_to_frame": RELATIONSHIP_TO_FRAME,
        },
        "policy": {
            "seed": seed,
            "target_bundles": target_bundles,
            "max_repository_share": fr.MAX_REPOSITORY_SHARE,
            "one_bundle_per_leakage_component": True,
            "selector": (
                "broad requirement shape: seven signals, admitted at "
                f"{MIN_SIGNALS_TO_ADMIT} or more per span, ranked by signal breadth, "
                "round-robin over repositories"
            ),
            "decision_thresholds": {
                "material_share": MATERIAL_SHARE,
                "negligible_share": NEGLIGIBLE_SHARE,
                "predominance_share": PREDOMINANCE_SHARE,
                "specification_shape_signals": SPECIFICATION_SHAPE_SIGNALS,
                "minimum_selector_yield": MINIMUM_SELECTOR_YIELD,
            },
        },
        "corpus": {
            "corpus_sha256": content_hash(
                {
                    "artifacts": sorted(
                        [a["artifact_id"], a["content_sha256"], a["revision"]]
                        for a in artifacts.values()
                    )
                },
                exclude=set(),
            ),
            "authorised_documents": len(artifacts),
            "path_excluded_documents": len(index["dropped"]),
            "required_uses": list(fr.REQUIRED_USES),
            "authorised_repositories": [
                {
                    **entry,
                    "documents": sum(
                        1
                        for a in artifacts.values()
                        if str(a["repository"]) == entry["repository"]
                    ),
                    "selections": sum(
                        1 for row in selection if row["repository"] == entry["repository"]
                    ),
                }
                for entry in authority["authorised"]
            ],
            "excluded_repositories": authority["excluded"],
        },
        "signals": [
            {
                **signal.to_dict(),
                "spans_fired": int(index["spans_with_signal"][signal.signal_id]),
                "documents_fired": int(index["documents_with_signal"][signal.signal_id]),
                "bundles_fired": bundles_with_signal[signal.signal_id],
            }
            for signal in signal_defs
        ],
        "selection": selection,
        "bundle_context": drawn["bundle_context"],
        "blinding": {
            "visible_to_classifier": list(CLASSIFIER_VISIBLE_FIELDS),
            "withheld_from_classifier": list(withheld_from_classifier(ctx)),
            "rationale": BLINDING_RATIONALE,
        },
        "annotators": [a.to_dict() for a in annotators],
        "passes": passes,
        "classifications": classifications,
        "agreement": agreement,
        "verdict": {
            "explanation": explanation,
            "statement": statement,
            "criteria": criteria,
            "counts": counts,
            "what_would_resolve": resolve,
        },
        "refusals": _refusal_records(),
    }
    body["report_id"] = f"{ID_PREFIX}:{content_hash(body, exclude=set())}"
    report = seal(body)
    ctx.schemas.validate_document(report)
    return report


# -- narrative ---------------------------------------------------------------

#: Where a caller may write a rendered account.
NARRATIVE_PATH: Final[str] = "PROFILE_RECON.md"

#: Why this document is generated when a caller requests it: a figure retyped
#: into prose can drift from the artifact silently.
GENERATED_NARRATIVE_RATIONALE: Final[str] = (
    "Generated from the caller-supplied profile reconnaissance artifact. Every "
    "figure is read from the committed JSON rather than retyped into prose, and "
    "a check fails if the two drift apart."
)


def _pct(numerator: int, denominator: int) -> str:
    """A share, or an explicit statement that there is nothing to take a share of.

    ADR-0002 in one line: an empty denominator is not zero percent. Printing
    ``0.0%`` for "no such bundle was drawn" is the substitution the whole
    repository is built to refuse.
    """
    if denominator <= 0:
        return f"{numerator}/{denominator} (no denominator)"
    return f"{numerator}/{denominator} ({numerator / denominator:.1%})"


def _table(header: Sequence[str], align: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(align) + "|",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def _distribution(rows: Sequence[Mapping[str, Any]], key: str) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row[key])
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items())


def _inline(values: Iterable[tuple[str, int]]) -> str:
    return ", ".join(f"`{name}` {count}" for name, count in values)


def _conjoin(names: Sequence[str]) -> str:
    """``a``, ``a and b``, ``a, b and c`` -- a list a person reads as a sentence."""
    quoted = [f"`{name}`" for name in names]
    if len(quoted) < 2:
        return "".join(quoted)
    return ", ".join(quoted[:-1]) + " and " + quoted[-1]


def blinding_holds(report: Mapping[str, Any]) -> tuple[bool, str]:
    """Whether the selector's own prediction stayed out of the classifier's view.

    Returns the finding and the sentence that states it, rather than asserting
    the blinding: a document that claims a blinding it cannot demonstrate is the
    failure this check exists to catch, so the negative case has to be
    renderable.
    """
    visible = set(report["blinding"]["visible_to_classifier"])
    withheld = set(report["blinding"]["withheld_from_classifier"])
    predictive = ("signals_fired", "signal_count")
    leaked = sorted(field for field in predictive if field in visible)
    unaccounted = sorted(
        field for field in predictive if field not in visible and field not in withheld
    )
    if leaked:
        return False, (
            "**The blinding does not hold.** "
            + ", ".join(f"`{field}`" for field in leaked)
            + " appears in the visible set, so the classifier was shown the shape this study "
            "predicted before it was asked whether it saw that shape. Every classification "
            "below is anchored and the agreement figure measures the anchor."
        )
    if unaccounted:
        return False, (
            "**The blinding cannot be confirmed.** "
            + ", ".join(f"`{field}`" for field in unaccounted)
            + " appears in neither the visible nor the withheld set, so the report does not "
            "say what happened to it. An unstated field is not a withheld one."
        )
    return True, (
        "**The blinding holds.** `signals_fired` and `signal_count` are both in the withheld "
        "set and in neither case in the visible set, so no classifier was told which signals "
        "surfaced the span it was reading."
    )


def _identity_block(report: Mapping[str, Any]) -> list[str]:
    return [
        "```",
        f"report_id      {report['report_id']}",
        f"report_sha256  {report['report_sha256']}",
        f"corpus_sha256  {report['corpus']['corpus_sha256']}",
        f"policy.seed    {report['policy']['seed']}",
        f"generated_at   {report['generated_at']}",
        "```",
    ]


def _selection_section(report: Mapping[str, Any]) -> list[str]:
    corpus = report["corpus"]
    policy = report["policy"]
    selection = report["selection"]
    signals = report["signals"]
    repositories = corpus["authorised_repositories"]
    excluded = corpus["excluded_repositories"]

    out = [
        "## What was selected, and by which signals",
        "",
        f"{len(selection)} bundles were drawn against a target of {policy['target_bundles']}, "
        f"from {corpus['authorised_documents']} documents in {len(repositories)} authorised "
        f"repositories. {corpus['path_excluded_documents']} further documents were dropped "
        "because the repository's own declaration excludes their path, and "
        f"{len(excluded)} census repositories contributed nothing at all: none of them "
        f"permits both {' and '.join(f'`{use}`' for use in corpus['required_uses'])}, and an "
        "unknown or deferred use is not an authorised one.",
        "",
        f"The selector is `{policy['selector']}`, with no repository past "
        f"{policy['max_repository_share']:.0%} of the target and at most one bundle per "
        "leakage component. It is deliberately broader than the production candidate miner "
        "and changes nothing in it: a study that asked whether requirement-bearing text "
        "exists, using the instrument suspected of missing it, would answer a different "
        "question.",
        "",
        *_table(
            ["repository", "revision", "documents", "bundles"],
            ["---", "---", "---:", "---:"],
            [
                [
                    f"`{entry['repository']}`",
                    f"`{str(entry['revision'])[:12]}`",
                    str(entry["documents"]),
                    str(entry["selections"]),
                ]
                for entry in repositories
            ],
        ),
        "",
        "### The signals",
        "",
        f"{len(signals)} signals, each carrying the source of its vocabulary. `spans` counts "
        "admissible spans in the pool the signal fired on, `documents` the documents behind "
        "them, and `bundles` how many of the drawn bundles carry it.",
        "",
        *_table(
            ["signal", "vocabulary", "spans", "documents", "bundles"],
            ["---", "---", "---:", "---:", "---:"],
            [
                [
                    f"`{signal['signal_id']}`",
                    f"`{signal['origin']}`"
                    + (
                        f", {signal['phrase_count']} phrases"
                        if signal.get("phrase_count")
                        else ""
                    ),
                    str(signal["spans_fired"]),
                    str(signal["documents_fired"]),
                    str(signal["bundles_fired"]),
                ]
                for signal in signals
            ],
        ),
        "",
    ]

    unenumerated = [s for s in signals if s["origin"] == "no_declared_vocabulary"]
    if unenumerated:
        out += [
            "Of those, "
            + _conjoin([str(s["signal_id"]) for s in unenumerated])
            + (" carries" if len(unenumerated) == 1 else " carry")
            + " no word list, because ATS-1 enumerates none for "
            + ("it" if len(unenumerated) == 1 else "them")
            + ". They are observed structurally or not at all. A plausible invented "
            "vocabulary would raise the count and make the finding worthless (ADR-0006).",
            "",
        ]

    by_count = _distribution(selection, "signal_count")
    strong = report["verdict"]["counts"]["strongly_shaped_selected"]
    threshold = policy["decision_thresholds"]["specification_shape_signals"]
    out += [
        "### The shape of the draw",
        "",
        f"Signals per bundle: {_inline(by_count)}. Block kind: "
        f"{_inline(_distribution(selection, 'block_kind'))}. Document family: "
        f"{_inline(_distribution(selection, 'document_family'))}.",
        "",
    ]
    if strong == len(selection):
        out += [
            f"Every one of the {len(selection)} bundles carries at least {threshold} signals, "
            "which is this study's declared definition of genuine specification prose. That "
            "is a consequence of ranking the pool by signal breadth and taking from the top, "
            "and it has a cost stated in the limits below: the draw contains no weakly shaped "
            "bundles to contrast the strongly shaped ones against.",
            "",
        ]
    else:
        out += [
            f"{_pct(strong, len(selection))} of the bundles carry at least {threshold} "
            "signals, which is this study's declared definition of genuine specification "
            "prose and the population the `profile_boundary_defect` criterion is tested over.",
            "",
        ]
    return out


def _context_section(report: Mapping[str, Any]) -> list[str]:
    context = report["bundle_context"]
    selection = report["selection"]
    availability = context["dimension_availability"]
    searched = ("present", "not_found", "not_applicable")

    present = {
        dimension: statuses
        for dimension, statuses in availability.items()
        if all(status in searched for status in statuses)
    }
    unsearched = {
        dimension: statuses
        for dimension, statuses in availability.items()
        if any(status not in searched for status in statuses)
    }
    out = [
        "### What `context_completeness` does and does not say",
        "",
        f"Completeness over the draw: {_inline(sorted(context['completeness'].items()))}. "
        "Read alone that number invites a conclusion it does not support, so the "
        "per-dimension tally is recorded beside it.",
        "",
        *_table(
            ["dimension", "availability over the draw"],
            ["---", "---"],
            [
                [f"`{dimension}`", _inline(sorted(statuses.items()))]
                for dimension, statuses in availability.items()
            ],
        ),
        "",
    ]
    if present and unsearched:
        out += [
            "The dimensions searched in every bundle are "
            + _conjoin(list(present))
            + "; the ones that were not are "
            + _conjoin(list(unsearched))
            + ". The rating degrades on any unsearched dimension and on an unknown profile "
            "basis alike, so `insufficient` here is not a claim that the enclosing prose was "
            "withheld. Where `preceding_context` and `following_context` are present, the "
            "surrounding section was in front of the classifier, and a request for more of it "
            "is a request for more than the bundle format carries rather than for something "
            "the bundle dropped.",
            "",
        ]
    basis = context["profile_basis"]
    if basis.get("unknown"):
        out += [
            "`profile_hypothesis.basis` is `unknown` on "
            f"{_pct(basis['unknown'], len(selection))} of the bundles. That is the same zero "
            "this study is about, arriving one layer down: the bundle builder degrades its "
            "own completeness rating because the corpus declares no profile for the "
            "document, which is the fact under investigation rather than an independent "
            "observation about context.",
            "",
        ]
    return out


def _passes_section(report: Mapping[str, Any]) -> list[str]:
    annotators = report["annotators"]
    passes = {row["annotator_id"]: row for row in report["passes"]}
    agreement = report["agreement"]
    models = [a["model"] for a in annotators]
    prompts = {a["prompt_sha256"] for a in annotators}

    return [
        "## What the two passes said",
        "",
        f"{len(annotators)} passes, "
        + (
            "different models"
            if len(set(models)) == len(models)
            else "the same model more than once"
        )
        + ", "
        + ("one shared prompt" if len(prompts) == 1 else f"{len(prompts)} distinct prompts")
        + ", neither seeing the other's output. Each pass is frozen by the content hash of "
        "its judgment file before any agreement is computed, so a disagreement cannot be "
        "resolved by revising an earlier answer.",
        "",
        *_table(
            ["pass", "kind", "model", "judgments", "state", "judgments_sha256"],
            ["---", "---", "---", "---:", "---", "---"],
            [
                [
                    f"`{a['annotator_id']}`",
                    f"`{a['kind']}`",
                    f"`{a['model']}`",
                    str(passes[a["annotator_id"]]["judgment_count"]),
                    f"`{passes[a['annotator_id']]['state']}`",
                    f"`{passes[a['annotator_id']]['judgments_sha256'][:16]}`",
                ]
                for a in annotators
            ],
        ),
        "",
        *_table(
            [
                "classification",
                *(f"`{a['annotator_id']}`" for a in annotators),
                "both",
                "either",
                "agreement",
            ],
            ["---", *("---:" for _ in annotators), "---:", "---:", "---:"],
            [
                [
                    f"`{row['classification']}`",
                    *(str(entry["count"]) for entry in row["by_annotator"]),
                    str(row["both"]),
                    str(row["either"]),
                    "not defined" if row["agreement"] is None else f"{row['agreement']:.3f}",
                ]
                for row in agreement["per_class"]
            ],
        ),
        "",
        "`agreement` is the per-class Jaccard ratio, `both` over `either`. A class neither "
        "pass ever used has no denominator and reports `not defined` rather than a "
        "manufactured zero.",
        "",
    ]


def _agreement_section(report: Mapping[str, Any]) -> list[str]:
    agreement = report["agreement"]
    return [
        "## Agreement between the passes",
        "",
        "**These are instrument-reproducibility numbers, not inter-rater reliability.** Both "
        "annotators are LLM passes — different models, one shared prompt, no shared state, "
        "neither seeing the other's output. Agreement here says how repeatably the instrument "
        "returns the same answer on the same unit. It says nothing about whether the answers "
        "are right: two passes can agree perfectly and be wrong together in the same way, and "
        "no agreement statistic detects that.",
        "",
        f"The two passes agreed on {_pct(agreement['agreed'], agreement['compared'])} of the "
        f"bundles both classified. {len(agreement['disagreements'])} disagreements are kept "
        "in the report with both rationales and the signals that surfaced the span, because a "
        "disagreement nobody can inspect is a number rather than evidence.",
        "",
    ]


def _context_request_section(report: Mapping[str, Any]) -> list[str]:
    counts = report["verdict"]["counts"]
    linked = counts["specify_with_context_request"]
    specify_either = counts["specify_either"]
    predominance = report["policy"]["decision_thresholds"]["predominance_share"]
    out = [
        "### SPECIFY, and a request for more context in the same breath",
        "",
        f"{_pct(linked, specify_either)} of the bundles a pass called SPECIFY carry a request "
        "from that same pass for the enclosing section. A classifier that names a profile and "
        "simultaneously asks for more of the document is reporting something specific: on "
        "those bundles it is the boundary of the bundle, not the content of the corpus, that "
        "limits the judgment.",
        "",
    ]
    if specify_either <= 0:
        out += [
            "No pass called any bundle SPECIFY, so there is nothing here to read either way.",
            "",
        ]
        return out
    out += [
        "That is evidence bearing on `context_bundle_deficiency`, and it sits below the "
        f"{predominance:.0%} declared before the passes ran, so the criterion does not fire. "
        f"It is also the thinnest population in the study: n = {specify_either}. It cannot "
        "settle the question against `candidate_mining_deficiency` on its own, and it is not "
        "asked to — those two readings are separated by an experiment named below, not by "
        "this ratio. What it does establish is that the context reading is alive rather than "
        "excluded, which is why the verdict is stated together with what would overturn it.",
        "",
    ]
    return out


def _verdict_section(report: Mapping[str, Any]) -> list[str]:
    verdict = report["verdict"]
    statements = {
        row["explanation_id"]: row["statement"] for row in report["study"]["explanations"]
    }
    criteria = verdict["criteria"]
    supported = [c for c in criteria if c["supported"]]
    chosen = verdict["explanation"]

    out = [
        "## The verdict",
        "",
        f"**`{chosen}`.** {verdict['statement']}",
        "",
        "Each criterion was evaluated independently against a threshold declared before the "
        "passes ran, not in priority order. An ordered cascade lets the first test that "
        "happens to pass suppress a reading the evidence supports equally well, which is how "
        "a study picks an answer to have picked one.",
        "",
        *_table(
            ["explanation", "supported", "test", "observed"],
            ["---", "---", "---", "---"],
            [
                [
                    f"`{c['explanation_id']}`",
                    "**yes**" if c["supported"] else "no",
                    c["test"],
                    c["observed"],
                ]
                for c in criteria
            ],
        ),
        "",
    ]

    if chosen == "undecided":
        if supported:
            out += [
                "### Why no single explanation",
                "",
                "The evidence reached the declared threshold for "
                + ", ".join(f"`{c['explanation_id']}`" for c in supported)
                + " and does not separate them. Naming one would be a choice rather than a "
                "finding, so none is named. `undecided` here is a result: the study ran, the "
                "thresholds held, and the data is consistent with more than one account.",
                "",
            ]
        else:
            out += [
                "### Why no explanation at all",
                "",
                "No criterion reached its declared threshold. The counts are consistent with "
                "more than one explanation and decisive for none. Lowering a threshold until "
                "one fired would be tuning the instrument to the answer.",
                "",
            ]
    else:
        out += ["### Why not each of the others", ""]
        for criterion in criteria:
            other = criterion["explanation_id"]
            if other == chosen:
                continue
            out += [
                f"**Not `{other}`.** {statements[other]} That reading would have been selected "
                f"by this evidence: {criterion['test']}. What was observed instead: "
                f"{criterion['observed']}.",
                "",
            ]
        out += [
            f"**Not `undecided`.** Exactly one criterion of {len(criteria)} reached its "
            "declared threshold. `undecided` is returned when none does or when several do; "
            "it is a legitimate result of this study rather than a failure to produce one, "
            "and it is not the result here.",
            "",
        ]

    out += [
        "### What would change the verdict",
        "",
        *(f"- {line}" for line in verdict["what_would_resolve"]),
        "",
    ]
    return out


def _limits_section(report: Mapping[str, Any]) -> list[str]:
    counts = report["verdict"]["counts"]
    thresholds = report["policy"]["decision_thresholds"]
    compared = counts["compared"]
    material = thresholds["material_share"]
    needed = math.ceil(material * compared) if compared else 0
    out = [
        "## Limits",
        "",
        f"**n = {counts['selected']} bundles, {compared} of them classified by both passes.** "
        "That is a reconnaissance, not a measurement of the corpus. At this size a class has "
        f"to reach {needed} bundles to clear the {material:.0%} material threshold, so a real "
        "but modest effect cannot show at all, and a difference of two or three bundles moves "
        "a share by more than the gap between two of the thresholds. Every proportion in this "
        "report should be read as a direction, not as a magnitude.",
        "",
        "**Two model passes, so instrument reproducibility rather than inter-rater "
        "reliability.** Nothing here establishes that either pass is correct. The two could "
        "agree on every bundle and be wrong together in the same way, and no agreement "
        "statistic in this report would detect it.",
        f"{counts['strongly_shaped_selected']} of {counts['selected']} bundles carry at least "
        f"{thresholds['specification_shape_signals']} signals",
    ]
    if counts["strongly_shaped_selected"] == counts["selected"]:
        out[-1] += (
            " — all of them. The `profile_boundary_defect` criterion was therefore evaluated "
            "over the whole draw rather than over a strongly shaped subset of it, and the "
            "study holds no weakly shaped bundles to contrast against. A boundary defect that "
            "shows up only as a *difference* between strong and weak prose is invisible to "
            "this draw."
        )
    else:
        out[-1] += (
            ", so the strongly shaped population the `profile_boundary_defect` criterion is "
            "tested over is a subset of the draw and smaller than the headline n."
        )
    out += [
        "",
        "**What this study does not establish.** It does not show that any bundle it called "
        "SPECIFY would be labelled SPECIFY by a human annotator; no human read them. It does "
        "not measure the production miner — it measures a different, broader selector beside "
        "it and infers a gap from the difference. It does not evaluate any ATS-1 rule, "
        "produce any label, or alter the sampling frame. And it does not license a change to "
        "the miner: the finding is a finding, and acting on it is a separate decision with "
        "its own evidence.",
        "",
        "**One defect this is not.** The miner deficiency named above, if it is the right "
        "reading, is a question about what the miner looks for: text this study surfaced and "
        "the production path did not. It is a different thing from the mining-cache "
        "staleness that invalidated an earlier draw of the sampling frame, which was "
        "an addressing bug between an inventory and the cache beside it. Repairing that "
        "addressing says nothing about this verdict, and this verdict is not evidence for "
        "that repair. The two share a subsystem and nothing else.",
    ]
    return out


def render_report_markdown(report: Mapping[str, Any]) -> str:
    """The prose account of one reconnaissance report, derived from the report.

    A pure function of the sealed JSON. Nothing is transcribed: every count,
    share and identifier below is read out of ``report``, so the document cannot
    drift from the artifact it describes without ``--check`` noticing.
    """
    study = report["study"]
    blinding = report["blinding"]
    _, blinding_statement = blinding_holds(report)

    lines = [
        "# ATS-1 profile reconnaissance",
        "",
        "Why an authorised corpus of "
        f"{report['corpus']['authorised_documents']} documents declares zero SPECIFY "
        "sections. A bounded diagnostic that runs beside a caller-supplied sampling "
        "frame and contributes nothing to it: no label, no rule verdict, no conformance "
        "claim.",
        "",
        GENERATED_NARRATIVE_RATIONALE,
        "",
        *_identity_block(report),
        "",
        "## The question",
        "",
        study["question"],
        "",
        "Four explanations were fixed before any bundle was drawn, including the one that "
        "says the standard is wrong. A study that can only return the answer it was built to "
        "find has not tested anything.",
        "",
        *_table(
            ["explanation", "statement"],
            ["---", "---"],
            [
                [f"`{row['explanation_id']}`", row["statement"]]
                for row in study["explanations"]
            ],
        ),
        "",
        study["relationship_to_frame"],
        "",
        *_selection_section(report),
        *_context_section(report),
        "## The blinding",
        "",
        blinding["rationale"],
        "",
        blinding_statement,
        "",
        "The visible set is an allow-list rather than a denylist, so a field added to the "
        "bundle schema later is withheld until somebody deliberately admits it. "
        f"{len(blinding['visible_to_classifier'])} fields travelled to the classifier and "
        f"{len(blinding['withheld_from_classifier'])} did not.",
        "",
        "Visible: " + ", ".join(f"`{f}`" for f in blinding["visible_to_classifier"]) + ".",
        "",
        "Withheld: " + ", ".join(f"`{f}`" for f in blinding["withheld_from_classifier"]) + ".",
        "",
        *_passes_section(report),
        *_agreement_section(report),
        *_context_request_section(report),
        *_verdict_section(report),
        *_limits_section(report),
        "## What this study refused to do",
        "",
    ]
    for refusal in report["refusals"]:
        ref = refusal.get("spec_ref")
        lines += [
            f"**`{refusal['refusal_id']}`**"
            + (f" ({ref})" if ref else "")
            + f" — {refusal['statement']}",
            "",
        ]
    return "\n".join(lines).rstrip("\n") + "\n"

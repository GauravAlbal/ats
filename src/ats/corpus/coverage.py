"""Per-rule mining coverage, with a mechanism attached to every zero.

The report is evaluated over a caller-supplied corpus and never treats a
historical corpus size or count as a public baseline. The bare count is not
actionable, because a zero is ambiguous between at least six mechanisms, and
they call for opposite responses: a rule with no deterministic surface needs
annotated context bundles, a rule the miner simply has no cue for needs three
lines in :func:`ats.corpus.mine.build_signals`, and a genuinely rare rule needs
nothing at all. Spec Section 18.5 requires the blockers to be reported rather
than a score that can hide one; this module reports the blocker per rule.

**Candidate counts are diagnostic, never a target.** No cue may be broadened,
loosened, or invented to raise a count. A rule whose construct genuinely does
not occur in this corpus MUST stay at zero and be classified ``naturally_rare``,
because a keyword net wide enough to guarantee coverage would manufacture the
prevalence evidence Section 17.5 forbids and would report matches that are not
candidates for the rule at all (Section 13.2, 16.5).

**A zero is not a verdict on a rule, in either direction.**
A rule with zero natural candidates can still be valid: a protected rule may
simply have no artifact pair that could exercise it. A rule with many
candidates can still be useless, because a cue is not a finding (Section 13.2)
and a large match count says nothing about whether the rule they were nominated
for earns its place in the standard. Candidate count
measures the mining surface, never rule quality, and MUST never be read, ranked,
or reported as one.

**A reason is not a disposition.** :func:`suspected_reason_for_zero` is
a hypothesis about the *mechanism* that produced a count; :data:`DISPOSITIONS`
is what should be *done* about the rule. They are separate closed
vocabularies and neither is derived from the other: knowing that a zero came
from a missing parser does not establish whether the rule should be kept,
re-bounded, or dropped, and only an annotated example can. Every rule starts
at ``insufficient_evidence`` -- the honest state before caller-supplied
annotation results -- and ``naturally_rare`` appearing in both vocabularies
is a coincidence of English, not an identity.

Four consequences shape the code:

- Every signal, profile, and context fact is *derived* from something the
  repository already holds -- the rule registry, the generated capability
  declaration, and the miner's own signal set. Nothing here encodes an opinion
  about which rules "should" be detectable, and an input or vocabulary this
  module cannot classify raises rather than falling into a default bucket.
- Natural and synthetic counts are never summed (Section 17.5), and an example
  store that was not searched reports ``None`` rather than ``0``: nothing was
  inspected, so nothing was found to be absent.
- The census is read, not recomputed. Its bytes are content-addressed into the
  report, so a report cannot silently describe a different corpus than the one
  it names.
- A disposition is *recorded*, never derived. It is read from an operator ledger
  of annotated evidence, and a ledger entry naming no evidence is refused rather
  than taken at face value: an untested claim about a rule is
  ``insufficient_evidence`` by definition, and no ledger is the same state for
  every rule at once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

from ..canonical import load_json, seal, sha256_hex
from ..errors import UsageError
from ..policy import STABLE_PROFILES
from . import mine
from . import records as rec
from .authority import AuthorityDeclaration

SCHEMA_ID: Final[str] = "ats_rule_coverage_report_v1.schema.json"
SCHEMA_VERSION: Final[str] = "ats.rule_coverage_report.v1"

#: The use these counts are resolved for. Inventorying a document is not
#: authority to extract candidates from it (spec Section 16.9, 17.13).
MINING_USE: Final[str] = "candidate_mining"

#: The provenance every declaration in this report must have come from. The
#: report carries one ``basis`` value for the whole authority block, so mixing
#: provenances would make that value false for some of its rows -- and an
#: overlay reported as repository-owned authority is exactly the confusion the
#: marker exists to prevent.
_REPORT_BASIS: Final[str] = "pilot_overlay"

#: The rule that governs how the report may be acted on. It is written into the
#: document because a coverage table invites exactly the response it forbids.
MINING_CONSTRAINT: Final[str] = (
    "Candidate counts are diagnostic, not a performance target. No vocabulary may be "
    "broadened to raise a count: a rule whose construct does not occur in this corpus "
    "stays at zero and is classified naturally_rare. A wider keyword net would "
    "manufacture prevalence evidence that spec Section 17.5 forbids and would report "
    "matches that are not candidates for the rule (Section 13.2, 16.5). Candidate count "
    "is not a quality measure in either direction: a rule with zero candidates can still "
    "be valid, and a rule with many candidates can still be useless, because a cue is not "
    "a finding (Section 13.2) and the absence of a cue is not conformance (Section 16.5). "
    "Rules MUST NOT be ranked, prioritised, or removed by candidate count."
)

#: Why a zero happened. Closed vocabulary: a mechanism outside this list is a
#: mechanism nobody agreed to, so it must be added here deliberately.
ZERO_REASONS: Final[dict[str, str]] = {
    "naturally_rare": (
        "A deterministic cue for the rule is wired into the miner and matched nothing. "
        "The corpus, not the rule or the miner, is thin here. Leave the count at zero."
    ),
    "no_deterministic_surface_signal": (
        "No deterministic vocabulary for the rule can be matched in raw prose, either "
        "because the registry declares no D0 or D1 detector class for it or because "
        "every implemented subcheck reads a TextIR structure the document does not carry."
    ),
    "miner_lacks_cue": (
        "An enumerable vocabulary that is matchable in prose already exists for the "
        "rule, and no mining signal names the rule. The zero measures the miner."
    ),
    "corpus_lacks_profile": (
        "The rule is disabled under the profile the corpus documents resolve to, so no "
        "document can supply an enabled instance regardless of its wording."
    ),
    "over_specified_or_irrelevant": (
        "The construct the rule governs does not occur in this genre of document at "
        "all, so the rule is not merely unsupported here but inapplicable. This value "
        "is never derived: it asserts something about the standard rather than about "
        "the corpus, and requires an operator decision recorded outside this report."
    ),
    "context_unavailable": (
        "The rule needs context the mined corpus did not supply -- a declared glossary, "
        "a revision predecessor, or surrounding documents -- so the zero describes the "
        "mining scope rather than the corpus."
    ),
    "not_applicable_has_candidates": (
        "The rule received candidates. The field is present and non-null so that a "
        "missing explanation can never be read as 'no explanation needed'."
    ),
}

#: What should be *done* about a rule, as distinct from why its count came out
#: the way it did. Closed vocabulary, and deliberately not the reason vocabulary:
#: a mechanism is a hypothesis about the corpus and the miner, while a
#: disposition is a claim about the rule, and only an annotated example can
#: establish one. ``naturally_rare`` appears in both lists and means different
#: things in each -- there it is why nothing matched, here it is the decision to
#: leave the rule alone -- so the two are never assigned from one another.
DISPOSITIONS: Final[dict[str, str]] = {
    "naturally_rare": (
        "Keep the rule and leave the count at zero. Annotated examples confirm the "
        "construct is well formed and simply uncommon in this corpus. Nothing to fix."
    ),
    "profile_absent": (
        "Keep the rule and cover it elsewhere. It is disabled under the profile the "
        "corpus resolves to, so this corpus cannot test it at any sample size; it needs "
        "authored fixtures or annotator-declared profiles, not a change to the rule."
    ),
    "requires_semantic_retrieval": (
        "Keep the rule and route it to semantic review. Annotated examples show the "
        "obligation is decidable by a reader and not by any enumerable vocabulary, so "
        "coverage comes from adjudicated judgments rather than from mining."
    ),
    "requires_unavailable_context": (
        "Keep the rule and supply the context. Annotated examples show the obligation is "
        "decidable once a glossary, revision predecessor, paired artifact, or authored "
        "ledger accompanies the document; the gap is in the mining scope, not the rule."
    ),
    "deterministic_miner_deficient": (
        "Keep the rule and fix this implementation. An enumerated vocabulary the spec "
        "already states would nominate candidates and no signal names the rule. Wire the "
        "vocabulary verbatim and nothing wider."
    ),
    "rule_boundary_defective": (
        "Keep the rule and re-bound it. Annotated examples disagree about what the rule "
        "covers -- annotators split on cases the text should have settled -- so the "
        "boundary, not the corpus and not the miner, is what produced the count."
    ),
    "rule_unnecessary": (
        "Propose dropping the rule. Annotated examples establish that the obligation is "
        "already carried by another rule or governs nothing a reader would call a defect. "
        "This value asserts something about the standard and is never derived: it "
        "requires operator-recorded annotated evidence, and a ratification decision the "
        "implementation trial does not get to make."
    ),
    "Decide nothing yet. No annotated example has tested this rule, so every other "
    "value would be a claim the caller has not earned. This is the state of every rule "
    "until an annotation and adjudication cycle reports, and it is distinct from "
    "naturally_rare: rare is a measured finding, insufficient is the absence of one."
    ),
}

#: The disposition of a rule nothing has tested. Named rather than inlined so the
#: default and the vocabulary cannot drift apart.
UNTESTED_DISPOSITION: Final[str] = "insufficient_evidence"

#: How a deterministic vocabulary relates to raw document prose.
SIGNAL_AVAILABILITY: Final[tuple[str, ...]] = (
    "wired_text_signal",
    "wired_artifact_declared_signal",
    "unwired_text_vocabulary",
    "no_prose_vocabulary",
    "no_vocabulary_declared",
)

#: Whether closing the rule needs a semantic judgment.
SEMANTIC_REQUIREMENT: Final[tuple[str, ...]] = ("required", "supplementary", "not_declared")

#: How the rule depends on profile resolution.
PROFILE_DEPENDENCY: Final[tuple[str, ...]] = (
    "disabled_except_transform",
    "disabled_in_assess",
    "profile_input_required",
    "profile_independent",
)

#: Context classes, least blocking first. The order is the precedence used when
#: a rule requires inputs from several classes: the report names the input that
#: blocks hardest, because that is the one that has to be solved first.
CONTEXT_DEPENDENCY: Final[tuple[str, ...]] = (
    "document_only",
    "artifact_declaration_required",
    "revision_or_neighbour_context_required",
    "authored_ir_required",
    "paired_ir_required",
)

#: Each ``required_inputs`` value in ``ats_rules_v1.yaml``, mapped to the class
#: of context a mined document would have to be accompanied by.
#:
#: ``syntax`` is deliberately ``document_only``: a syntactic parse is derivable
#: from the document's own bytes by a parser this implementation does not have.
#: That is a capability gap, recorded in ``deterministic_signal_available``, and
#: calling it a context gap would send the reader looking for missing data
#: instead of a missing parser.
_INPUT_CONTEXT: Final[dict[str, str]] = {
    "text": "document_only",
    "metadata": "document_only",
    "document_ast": "document_only",
    "force_lexicon": "document_only",
    "syntax": "document_only",
    "profile": "artifact_declaration_required",
    "policy": "artifact_declaration_required",
    "glossary": "artifact_declaration_required",
    "audience": "artifact_declaration_required",
    "source_text": "revision_or_neighbour_context_required",
    "document_context": "revision_or_neighbour_context_required",
    "meaning_ledger": "authored_ir_required",
    "requirement_ir": "authored_ir_required",
    "evidence": "authored_ir_required",
    "source_ir": "paired_ir_required",
    "output_ir": "paired_ir_required",
    "retention_contract": "paired_ir_required",
    "authorizations": "paired_ir_required",
}

#: Every ``vocabulary_source`` in ``capability/ats_rule_capability_v1.json``,
#: classified by where its members can be matched:
#:
#: ``text``
#:     literal strings a reader would find in prose, so a document-text signal
#:     over them is possible.
#: ``ir_structure``
#:     field names or enum values of the TextIR. A document carries the prose,
#:     not the ledger, so these can never produce a prose match.
#: ``artifact_declared``
#:     members the artifact itself must supply, so the vocabulary is empty for a
#:     document that declares nothing.
#: ``none``
#:     the capability declares no vocabulary, which is how an undecidable rule
#:     says it has no surface at all.
#:
#: The keys are matched exactly. The capability document is generated from the
#: detector specs, so a reworded ``vocabulary_source`` will fail this lookup
#: loudly -- which is the intent. A prefix match would keep working while
#: silently classifying a vocabulary nobody re-read.
_VOCABULARY_SURFACE: Final[dict[str, str]] = {
    "none": "none",
    "lexicons/ats_force_lexicon_v1.yaml": "text",
    "lexicons/ats_force_lexicon_v1.yaml deontic_force.terms": "text",
    "lexicons/ats_force_lexicon_v1.yaml deontic_force.terms[].surface": "text",
    "lexicons/ats_force_lexicon_v1.yaml deontic_force.noncanonical": "text",
    "lexicons/ats_force_lexicon_v1.yaml collision_rules": "text",
    "lexicons/ats_force_lexicon_v1.yaml likelihood.terms[].input_aliases": "text",
    "lexicons/ats_force_lexicon_v1.yaml likelihood.non_probability_terms": "text",
    "lexicons/ats_force_lexicon_v1.yaml assessment_confidence.terms": "text",
    "lexicons/ats_force_lexicon_v1.yaml assessment_confidence.basis_dimensions": "ir_structure",
    "claim roles enumerated in ATS-1 7.4": "ir_structure",
    "update_indicator objects and extraction_issues declared in the IR": "ir_structure",
    "relation types enumerated in ats_common_v1#/$defs/relation": "ir_structure",
    "source types enumerated in ats_common_v1#/$defs/source_ref": "ir_structure",
    (
        "relation types in ats_common_v1 plus the contrary_evidence states in "
        "lexicons/ats_force_lexicon_v1.yaml"
    ): "ir_structure",
    "quantifier kinds enumerated in ATS-1 7.7": "ir_structure",
    "requirement slots defined in ats_common_v1#/$defs/requirement_slots": "ir_structure",
    "forecast slots defined in ats_common_v1#/$defs/forecast_slots": "ir_structure",
    "scope fields defined in ats_common_v1#/$defs/scope": "ir_structure",
    "comparator words enumerated in ATS-1 9.3.8 and 10.10": "text",
    "the concealing actor forms quoted from ATS-1 9.3.4 and 21.4": "text",
    "the coordination marker in the nonconforming example at ATS-1 9.3.3": "text",
    "the literal marker Section 9.3.2 requires for an unknown slot": "text",
    (
        "acronym shape `[A-Z][A-Z0-9]{1,}` plus the artifact's glossary "
        "`approved_abbreviations` and `audience.assumed_glossary_refs`"
    ): "text",
    "the artifact's own glossary `deprecated_aliases`": "artifact_declared",
    "the artifact's own glossary": "artifact_declared",
}

#: A term fed to the miner purely to make its glossary-conditional signal
#: appear, so the conditional rule set is read off the miner instead of being
#: restated here.
_GLOSSARY_PROBE_ALIAS: Final[str] = "ats-coverage-glossary-probe"


def vocabulary_surface(source: str) -> str:
    """Where the members of ``source`` can be matched.

    Raises rather than guessing: an unclassified vocabulary would otherwise be
    silently reported as having no prose surface, which is a claim about a rule
    that nobody checked (ADR-0002).
    """
    try:
        return _VOCABULARY_SURFACE[source]
    except KeyError:
        raise UsageError(
            f"vocabulary_source {source!r} is not classified in "
            "ats.corpus.coverage._VOCABULARY_SURFACE; classify it explicitly rather "
            "than letting the rule fall into a default coverage class"
        ) from None


def wired_rules(ctx: Any) -> dict[str, frozenset[str]]:
    """Which rules the miner has a signal for, split by what the signal needs.

    ``unconditional`` signals draw on the force lexicon or a list enumerated in
    the specification, so they apply to every document. ``artifact_declared``
    signals draw on the artifact's own glossary, so they apply only to a
    document that declares one. The split is discovered by asking the miner for
    its signals twice rather than by restating its signal table here.
    """
    unconditional = frozenset(
        rule_id for signal in mine.build_signals(ctx) for rule_id in signal.rule_ids
    )
    probed = mine.build_signals(
        ctx, glossary=[{"deprecated_aliases": [_GLOSSARY_PROBE_ALIAS]}]
    )
    conditional = frozenset(
        rule_id
        for signal in probed
        if signal.origin == "artifact_glossary"
        for rule_id in signal.rule_ids
    )
    return {"unconditional": unconditional, "artifact_declared": conditional - unconditional}


def deterministic_signal(ctx: Any, rule_id: str, wired: Mapping[str, frozenset[str]]) -> str:
    """How a deterministic vocabulary for ``rule_id`` relates to raw prose."""
    if rule_id in wired["unconditional"]:
        return "wired_text_signal"
    if rule_id in wired["artifact_declared"]:
        return "wired_artifact_declared_signal"
    surfaces = {
        vocabulary_surface(str(subcheck["vocabulary_source"]))
        for subcheck in ctx.capability.for_rule(rule_id).subchecks
    }
    if "text" in surfaces:
        return "unwired_text_vocabulary"
    if surfaces - {"none"}:
        return "no_prose_vocabulary"
    return "no_vocabulary_declared"


def semantic_requirement(ctx: Any, rule_id: str) -> str:
    """Whether a semantic judgment is needed to close ``rule_id``.

    Two declarations decide it. The registry's ``detector_classes`` name D3 when
    a semantic critic is part of the rule's detection path (spec Section 12.3),
    and the capability's ``decision_power`` says what silence from the
    deterministic detector establishes: anything short of ``decides`` yields
    REVIEW_REQUIRED rather than PASS, so the deterministic part cannot close the
    rule on its own.
    """
    rule = ctx.registry.get(rule_id)
    if ctx.capability.for_rule(rule_id).decision_power != "decides":
        return "required"
    return "supplementary" if "D3" in rule.detector_classes else "not_declared"


def profile_dependency(ctx: Any, rule_id: str) -> str:
    """How ``rule_id`` depends on profile resolution.

    A rule that is ``disabled`` by default in a profile cannot be mined from a
    corpus whose documents never declare a profile that enables it. This
    function reports that dependency without assuming a prevalence or profile
    distribution for the caller's input.
    """
    rule = ctx.registry.get(rule_id)
    disabled = frozenset(
        profile for profile, state in rule.default_states.items() if state == "disabled"
    )
    if disabled == frozenset({"ASSESS", "SPECIFY"}):
        return "disabled_except_transform"
    if disabled == frozenset({"ASSESS"}):
        return "disabled_in_assess"
    if disabled:
        raise UsageError(
            f"{rule_id} is disabled by default in {sorted(disabled)}, a combination "
            "ats.corpus.coverage.PROFILE_DEPENDENCY has no value for; add one rather "
            "than reporting a weaker dependency"
        )
    return "profile_input_required" if "profile" in rule.required_inputs else "profile_independent"


def context_dependency(ctx: Any, rule_id: str) -> str:
    """The hardest-blocking class of input ``rule_id`` needs beyond the bytes."""
    rule = ctx.registry.get(rule_id)
    worst = "document_only"
    for required in rule.required_inputs:
        try:
            klass = _INPUT_CONTEXT[required]
        except KeyError:
            raise UsageError(
                f"{rule_id} requires input {required!r}, which "
                "ats.corpus.coverage._INPUT_CONTEXT does not classify; a required "
                "input nobody classified cannot be reported as document-only"
            ) from None
        if CONTEXT_DEPENDENCY.index(klass) > CONTEXT_DEPENDENCY.index(worst):
            worst = klass
    return worst


def _no_deterministic_surface_mechanism(ctx: Any, rule_id: str, signal: str) -> str | None:
    """Which of the two no-surface mechanisms applies, or ``None``.

    Kept apart from the reason itself because the two call for different work:
    a rule with no deterministic detector class can never be mined at all, while
    a rule whose vocabulary is a TextIR structure becomes minable the moment an
    annotator authors the ledger.
    """
    rule = ctx.registry.get(rule_id)
    if not {"D0", "D1"} & set(rule.detector_classes):
        return "no_deterministic_detector_class"
    if signal in {"no_prose_vocabulary", "no_vocabulary_declared"}:
        return "vocabulary_not_in_prose"
    return None


def suspected_reason_for_zero(
    ctx: Any,
    rule_id: str,
    *,
    candidate_count: int,
    signal: str,
    profile: str,
    context: str,
) -> str:
    """Why ``rule_id`` received no candidate.

    The order is a precedence, not a search: several mechanisms can be true at
    once, and the report names the one furthest upstream, because that is the one
    whose removal would change the count. A rule disabled by profile stays at
    zero however many cues are wired for it, and a rule with no deterministic
    detector class stays at zero however much context is supplied.

    An unwired prose vocabulary outranks a missing context deliberately.
    Nominating a candidate is a prose operation: it needs a cue in the bytes and
    nothing else, and the meaning ledger, profile, or glossary a rule also
    requires is what *adjudicating* it needs. Reporting a missing ledger for a
    rule whose enumerated comparator words were simply never wired would send
    the reader to author IR when three lines in the miner would produce the
    candidates.
    """
    if candidate_count > 0:
        return "not_applicable_has_candidates"
    if profile in {"disabled_except_transform", "disabled_in_assess"}:
        return "corpus_lacks_profile"
    if _no_deterministic_surface_mechanism(ctx, rule_id, signal) is not None:
        return "no_deterministic_surface_signal"
    if signal == "unwired_text_vocabulary":
        return "miner_lacks_cue"
    if signal == "wired_artifact_declared_signal" or context != "document_only":
        return "context_unavailable"
    return "naturally_rare"


def recommended_action(
    ctx: Any,
    rule_id: str,
    *,
    reason: str,
    signal: str,
    candidate_count: int,
    repository_count: int,
    natural_candidate_count: int,
) -> str:
    """What to do about the count, derived from the mechanism that produced it."""
    rule = ctx.registry.get(rule_id)
    cap = ctx.capability.for_rule(rule_id)
    if reason == "not_applicable_has_candidates":
        return (
            f"Sample from the {natural_candidate_count} authorized candidate(s) of "
            f"{candidate_count} across {repository_count} repositories. No coverage "
            "action is needed; a candidate is not a finding, so the sample still needs "
            "human adjudication (spec Section 13.2)."
        )
    if reason == "corpus_lacks_profile":
        enabling = sorted(
            profile for profile, state in rule.default_states.items() if state != "disabled"
        )
        return (
            f"Do not mine for this rule. It is disabled by default outside "
            f"{', '.join(enabling)}, and a document that declares no profile cannot "
            "resolve to one, so no document can supply an enabled instance whatever its "
            "wording. Cover it from authored fixtures, or from bundles whose profile an "
            "annotator declares; profile remains caller-supplied rather than inferred."
        )
    if reason == "no_deterministic_surface_signal":
        mechanism = _no_deterministic_surface_mechanism(ctx, rule_id, signal)
        if mechanism == "no_deterministic_detector_class":
            return (
                "Do not add a cue. The registry declares detector classes "
                f"{', '.join(rule.detector_classes)} for this rule and no D0 or D1, so a "
                "text match could not be a candidate for it under any vocabulary. Cover "
                "it from human-annotated context bundles and count the agreement rate."
            )
        blocking = ", ".join(cap.blocking_inputs) or "the TextIR structures it reads"
        return (
            "Cover it from context bundles annotated against an authored ledger, not "
            f"from prose mining: every implemented subcheck reads {blocking}, which a "
            "raw document does not carry. The zero is a property of the mining surface, "
            "not of the corpus."
        )
    if reason == "context_unavailable":
        missing = ", ".join(
            required
            for required in rule.required_inputs
            if _INPUT_CONTEXT[required] != "document_only"
        )
        return (
            f"Supply the missing context before reading anything into this zero: the "
            f"rule requires {missing}, and the mined documents supply none of it, so a "
            "wired cue has no vocabulary to match. Re-mine with the context attached, "
            "then re-classify."
        )
    if reason == "miner_lacks_cue":
        sources = sorted(
            {
                str(subcheck["vocabulary_source"])
                for subcheck in cap.subchecks
                if vocabulary_surface(str(subcheck["vocabulary_source"])) == "text"
            }
        )
        return (
            "Wire the vocabulary that already exists into "
            f"ats.corpus.mine.build_signals: {'; '.join(sources)}. The zero measures the "
            "miner, not the corpus. Wire the enumerated vocabulary verbatim and nothing "
            "wider -- a broadened net would report matches that are not candidates for "
            "this rule."
        )
    return (
        "Leave the count at zero. A cue for this rule is wired and matched nothing, so "
        "the corpus is thin here; raising the count would require widening a vocabulary, "
        "which is forbidden. Cover the rule from fixtures and say so when reporting "
        "coverage."
    )


# -- annotation probe evidence ----------------------------------------------


#: The stratum drawn to put a reader in front of material a zero-candidate
#: rule's own surface selected. It is an instrument for turning a zero from
#: something explained into something tested: the miner passed the span over,
#: so whatever the reader says about it is information the candidate count
#: could not carry.
PROBE_STRATUM: Final[str] = "zero_candidate_rule_probe"

#: How the frame writes the probed rule into a probe pick. A probe carries no
#: ``candidate_rule_ids`` -- no detector flagged it, which is the entire point --
#: so the rule it was drawn for travels in ``candidate_source`` as
#: ``zero_candidate_probe:<rule_id>:<basis>``. Parsed here rather than restated,
#: because a second copy of the encoding would drift from ats.corpus.frame.
PROBE_SOURCE_PREFIX: Final[str] = "zero_candidate_probe:"

#: Where an annotator records the profile the document in front of them resolves
#: to. This is a profile observation made by reading, as opposed to one the
#: inventory guessed from a heading path, so it can turn "no document declares
#: a profile" from an absence into a measurement.
DECLARED_PROFILE_EXTENSION: Final[str] = "x-ats-repo-declared-profile"

#: Labels asserting the construct a rule governs is present *and* defective.
#: ``near_miss`` counts: it is a case the rule nearly catches, which still
#: requires the construct to be in the span.
DEFECT_LABELS: Final[frozenset[str]] = frozenset({"violation", "near_miss"})

#: The two blind passes, by the role the round and the agreement report give
#: them. Named once so a third pass cannot be half-added.
PASS_ROLES: Final[tuple[str, ...]] = ("a", "b")

#: Every per-rule observation this module recomputes from the round, and what
#: each one licenses. Closed on purpose: a ledger that may cite a count nobody
#: computes can support any claim at all, so a citation outside this set is
#: refused rather than passed through as free-text evidence.
EVIDENCE_COUNTS: Final[dict[str, str]] = {
    "probe_bundles_in_frame": (
        "Probe picks the sampling frame held for this rule. Zero means the rule was "
        "never probeable, which is a different claim from a probe that found nothing."
    ),
    "probe_bundles_in_round": (
        "Those picks the round actually selected. A rule with picks in the frame and "
        "none in the round was not tested, however large the frame's pool."
    ),
    "rule_directed_judgments": (
        "Judgment records naming this rule, across both passes. This is the count that "
        "says a reader was asked about this rule rather than about something else."
    ),
    "rule_directed_declines": (
        "Decline records naming this rule, across both passes. A decline is a reader "
        "looking at the span and reporting the construct absent -- positive evidence of "
        "absence, which a candidate count can never be."
    ),
    "rule_directed_defect_labels": (
        "Judgments naming this rule labelled violation or near_miss. Any of these on a "
        "span the miner produced no candidate for measures the miner, not the corpus."
    ),
    "probe_bundles_declined_by_both_passes": (
        "Probe bundles for this rule that both passes independently declined. Two "
        "readers finding the construct absent at the rule's own surface, which is the "
        "weakest evidence that still supports a claim about the corpus."
    ),
    "enabling_profile_observations": (
        "Bundle-passes whose reader-recorded profile is one this rule is not disabled "
        "in. Zero over a non-empty set of observations is a measured negative: readers "
        "recorded a profile and never recorded one that would enable the rule."
    ),
    "disabling_profile_observations": (
        "Bundle-passes whose reader-recorded profile leaves this rule disabled. Reported "
        "beside the enabling count so the denominator is visible."
    ),
}


def enabling_profiles(ctx: Any, rule_id: str) -> tuple[str, ...]:
    """Profiles in which ``rule_id`` is not disabled by default.

    Read off the registry's ``default_states`` rather than mapped by hand, so a
    rule whose default state changes cannot leave a stale profile list behind in
    this module.
    """
    states = ctx.registry.get(rule_id).default_states
    return tuple(sorted(profile for profile, state in states.items() if state != "disabled"))


def probe_rule_of(candidate_source: str) -> str | None:
    """The rule a probe pick was drawn for, or ``None`` when it is not a probe.

    ``None`` rather than an exception for a non-probe source: the frame holds
    five strata and only this one encodes a rule in ``candidate_source``. A
    probe source that carries no rule *is* an error, because the rule is the
    only record of what the probe was testing.
    """
    if not candidate_source.startswith(PROBE_SOURCE_PREFIX):
        return None
    rule_id, _, basis = candidate_source[len(PROBE_SOURCE_PREFIX) :].partition(":")
    if not rule_id or not basis:
        raise UsageError(
            f"probe candidate_source {candidate_source!r} does not carry a "
            "<rule_id>:<basis> pair; the rule a probe was drawn for is the only record "
            "of what it was testing and must not be guessed"
        )
    return rule_id


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _evidence_unavailable(path_label: str, availability: str, note: str) -> dict[str, Any]:
    """The metadata block for a round that was not read.

    Every count is ``None`` rather than ``0`` and every list empty, so a reader
    of the report can tell "no pass was asked about this rule" from "no round
    was read at all" (ADR-0002).
    """
    return {
        "path": path_label,
        "availability": availability,
        "round_id": None,
        "frame_id": None,
        "bundles": None,
        "probe_bundles": None,
        "rules_probed": None,
        "judgment_records": None,
        "decline_records": None,
        "sources": [],
        "declared_profile_observations": [],
        "profiles_never_observed": [],
        "note": note,
    }


def load_annotation_evidence(
    ctx: Any,
    *,
    round_path: str | Path | None,
    frame_path: str | Path | None,
    judgment_dir: str | Path | None,
) -> tuple[dict[str, dict[str, int]], dict[str, Any]]:
    """Per-rule observations recomputed from the completed annotation round.

    This is the evidence a disposition may rest on, and it is recomputed on every
    run rather than transcribed into the ledger, so a hand-typed number cannot
    outlive the artifact it claims to describe. The ledger states what it thinks
    it saw and :func:`load_disposition_ledger` refuses it when the two disagree.

    Three joins produce it. The frame says which bundle was drawn to probe which
    rule, because a probe carries no candidate rule of its own -- no detector
    flagged it. The round says which of those picks a pass actually saw. The
    judgment and decline files say what each pass reported, and a decline counts
    as evidence in its own right: an annotator who reads the rule's own surface
    and reports the construct absent has *looked*, which is the one thing an
    absent candidate count can never establish.

    When any input is missing the per-rule mapping is empty and the metadata
    names the missing file. Nothing was read, so nothing was found to be absent,
    and every count is withheld rather than reported as zero (ADR-0002).
    """
    rule_ids = ctx.registry.ids()
    if round_path is None or frame_path is None or judgment_dir is None:
        return {}, _evidence_unavailable(
            "(not searched)",
            "not_searched",
            "No annotation round was named, so no rule was tested against an annotated "
            "example and no observation was computed.",
        )
    round_file, frame_file, judgments = Path(round_path), Path(frame_path), Path(judgment_dir)
    wanted: list[Path] = [round_file, frame_file]
    for role in PASS_ROLES:
        wanted.append(judgments / f"round-{role}.jsonl")
        wanted.append(judgments / f"round-{role}-inapplicable.jsonl")
    absent = [str(candidate) for candidate in wanted if not candidate.is_file()]
    if absent:
        return {}, _evidence_unavailable(
            str(round_path),
            "not_found",
            "The annotation round is incomplete on disk: "
            f"{', '.join(absent)} missing. Every observation is withheld rather than "
            "reported as zero, because nothing was read.",
        )

    frame = load_json(frame_file)
    probed_by_bundle: dict[str, str] = {}
    frame_probes: dict[str, int] = dict.fromkeys(rule_ids, 0)
    for row in frame.get("selection", ()):
        rule_id = probe_rule_of(str(row.get("candidate_source", "")))
        if rule_id is None:
            continue
        if rule_id not in frame_probes:
            raise UsageError(
                f"sampling frame {frame_file} probes {rule_id!r}, which is not in the "
                "rule registry; a probe for an unknown rule tests nothing this report "
                "can attribute"
            )
        probed_by_bundle[str(row["bundle_id"])] = rule_id
        frame_probes[rule_id] += 1

    round_record = load_json(round_file)
    round_probes: dict[str, int] = dict.fromkeys(rule_ids, 0)
    probe_bundles: dict[str, set[str]] = {rule_id: set() for rule_id in rule_ids}
    for row in round_record.get("selection", ()):
        if str(row.get("stratum")) != PROBE_STRATUM:
            continue
        bundle_id = str(row["bundle_id"])
        rule_id = probed_by_bundle.get(bundle_id)
        if rule_id is None:
            raise UsageError(
                f"round {round_file} selects probe bundle {bundle_id}, which the frame "
                f"{frame_file} records no probed rule for; what a probe was testing "
                "cannot be recovered from the round alone"
            )
        round_probes[rule_id] += 1
        probe_bundles[rule_id].add(bundle_id)

    judged: dict[str, int] = dict.fromkeys(rule_ids, 0)
    declined: dict[str, int] = dict.fromkeys(rule_ids, 0)
    defects: dict[str, int] = dict.fromkeys(rule_ids, 0)
    declines_by_role: dict[str, set[tuple[str, str]]] = {role: set() for role in PASS_ROLES}
    profiles: dict[str, int] = {}
    sources: list[dict[str, Any]] = []
    for role in PASS_ROLES:
        judgment_file = judgments / f"round-{role}.jsonl"
        decline_file = judgments / f"round-{role}-inapplicable.jsonl"
        rows = _read_jsonl(judgment_file)
        declines = _read_jsonl(decline_file)
        for row in rows:
            rule_id = str(row["rule_id"])
            if rule_id not in judged:
                raise UsageError(
                    f"{judgment_file} judges {rule_id!r}, which is not in the rule registry"
                )
            judged[rule_id] += 1
            if str(row.get("label")) in DEFECT_LABELS:
                defects[rule_id] += 1
            profile = (row.get("extensions") or {}).get(DECLARED_PROFILE_EXTENSION)
            if profile is not None:
                profiles[str(profile)] = profiles.get(str(profile), 0) + 1
        for row in declines:
            rule_id = str(row["rule_id"])
            if rule_id not in declined:
                raise UsageError(
                    f"{decline_file} declines {rule_id!r}, which is not in the rule registry"
                )
            declined[rule_id] += 1
            declines_by_role[role].add((str(row["example_id"]), rule_id))
        sources.append(
            {
                "role": role,
                "judgments_path": str(judgment_file),
                "judgments": len(rows),
                "judgments_sha256": sha256_hex(judgment_file.read_bytes()),
                "declines_path": str(decline_file),
                "declines": len(declines),
                "declines_sha256": sha256_hex(decline_file.read_bytes()),
            }
        )

    both_declined = declines_by_role[PASS_ROLES[0]] & declines_by_role[PASS_ROLES[1]]
    evidence: dict[str, dict[str, int]] = {}
    for rule_id in rule_ids:
        enabling = frozenset(enabling_profiles(ctx, rule_id))
        evidence[rule_id] = {
            "probe_bundles_in_frame": frame_probes[rule_id],
            "probe_bundles_in_round": round_probes[rule_id],
            "rule_directed_judgments": judged[rule_id],
            "rule_directed_declines": declined[rule_id],
            "rule_directed_defect_labels": defects[rule_id],
            "probe_bundles_declined_by_both_passes": sum(
                1 for bundle_id in probe_bundles[rule_id] if (bundle_id, rule_id) in both_declined
            ),
            "enabling_profile_observations": sum(
                count for profile, count in profiles.items() if profile in enabling
            ),
            "disabling_profile_observations": sum(
                count for profile, count in profiles.items() if profile not in enabling
            ),
        }

    return evidence, {
        "path": str(round_path),
        "availability": "present",
        "round_id": str(round_record["round_id"]),
        "frame_id": str(frame["frame_id"]),
        "bundles": len(round_record.get("selection", ())),
        "probe_bundles": sum(round_probes.values()),
        "rules_probed": sum(1 for rule_id in rule_ids if round_probes[rule_id] > 0),
        "judgment_records": sum(int(source["judgments"]) for source in sources),
        "decline_records": sum(int(source["declines"]) for source in sources),
        "sources": sources,
        "declared_profile_observations": [
            {"profile": profile, "bundle_passes": profiles[profile]} for profile in sorted(profiles)
        ],
        "profiles_never_observed": sorted(STABLE_PROFILES - frozenset(profiles)),
        "note": "Counts are recomputed from these files on every run. A rule no pass was "
        "asked about has zero rule-directed observations, and that is a fact about the "
        "round rather than about the rule.",
    }


# -- disposition ------------------------------------------------------------


#: What is said about a rule nothing has annotated yet. Spelled out rather than
#: left blank because a blank would be read as "no disposition needed", which is
#: the opposite of what an untested rule is in (ADR-0002).
UNTESTED_BASIS: Final[str] = (
    "No annotated example has tested this rule. The value is this report's default, not "
    "a finding: nothing was adjudicated, so nothing about the rule is established."
)


def natural_rarity_obstacle(rule_id: str, observed: Mapping[str, int] | None) -> str | None:
    """Why ``naturally_rare`` is unavailable for ``rule_id``, or ``None``.

    ``naturally_rare`` is the one disposition that asserts something about the
    world rather than about this implementation: the construct the rule governs
    does not occur here. Nothing in a candidate count can support that. A zero
    means the miner nominated nothing, and the miner is exactly the instrument
    whose reach is in question -- reading rarity off it is the absence-as-evidence
    error ADR-0002 exists to prevent, one level up from a rule result.

    So the value is gated on observations only a reader can produce, and the gate
    is a function of recomputed counts rather than of anything the ledger says
    about itself. Four conditions, each disqualifying on its own:

    - No pass declined the rule. A decline is the record of a reader looking at
      the rule's own surface and reporting the construct absent, and it is
      only one kind of evidence of absence.
    - One reader is not two. A single decline on a single probe span is thin for
      a claim about the whole corpus, so both blind passes must have declined
      the same bundle independently.
    - Some pass found the construct present and defective. One violation or
      near_miss refutes "does not occur" outright.

    This is a floor, not an adjudication. It rules out the claim a count alone
    could produce; it cannot choose between two readings a reader supports.
    ``ATS-TERM-002`` clears every condition here and is recorded
    ``requires_unavailable_context``, because its readers declined for want of a
    glossary rather than for want of the construct -- a distinction that lives in
    the rationales and not in any number. Which is why the disposition is
    recorded by a person and only checked here.
    """
    if observed is None:
        return (
            "no observation was recomputed for it, so the claim cannot be checked against "
            "anything"
        )
    if observed.get("rule_directed_declines", 0) <= 0:
        return (
            "no pass declined it as inapplicable, so no reader is on record having looked "
            "at its surface and found the construct absent; an absent candidate count is "
            "the miner's silence, not a reader's"
        )
    if observed.get("probe_bundles_declined_by_both_passes", 0) <= 0:
        return (
            "no probe bundle was declined by both blind passes, so the absence rests on a "
            "single reader of a single span"
        )
    if observed.get("rule_directed_defect_labels", 0) > 0:
        return (
            f"{observed['rule_directed_defect_labels']} judgment(s) labelled it violation "
            "or near_miss, which is the construct occurring"
        )
    return None


def _check_observed_counts(
    ledger_file: Path,
    rule_id: str,
    claimed: Mapping[str, Any],
    recomputed: Mapping[str, int] | None,
) -> dict[str, int]:
    """The recomputed value of every count the ledger cites, or a refusal.

    The ledger writes down what its author believed they saw; this function
    reads the same quantities off the artifacts and refuses the entry when the
    two disagree, naming both numbers. That is the mechanism that keeps the
    ledger from rotting: a judgment file can be re-run and re-frozen without any
    prose in this repository noticing, and a claim whose stated evidence no
    longer matches its source is worse than no claim, because it reads as
    checked.

    The returned mapping holds the *recomputed* values, never the claimed ones,
    so the report cannot publish a number that was only ever typed.
    """
    if not claimed:
        raise UsageError(
            f"disposition ledger {ledger_file} gives {rule_id} a disposition with no "
            "observed_counts; a disposition states what was observed, and an entry that "
            "cites nothing cannot be checked against the round that supposedly tested it"
        )
    if recomputed is None:
        raise UsageError(
            f"disposition ledger {ledger_file} cites observations for {rule_id}, but no "
            "annotation round was read, so nothing can be checked against them; supply "
            "the round or record the rule as untested"
        )
    verified: dict[str, int] = {}
    for name in sorted(claimed):
        if name not in EVIDENCE_COUNTS:
            raise UsageError(
                f"disposition ledger {ledger_file} cites {name!r} for {rule_id}, which is "
                f"not an observation this report computes; the closed set is "
                f"{sorted(EVIDENCE_COUNTS)}"
            )
        stated = int(claimed[name])
        actual = recomputed[name]
        if stated != actual:
            raise UsageError(
                f"disposition ledger {ledger_file} states {name}={stated} for {rule_id}, "
                f"but the annotation round holds {name}={actual}; the ledger's evidence "
                "has gone stale against the artifacts it describes and the disposition "
                "cannot be published until one of them is corrected"
            )
        verified[name] = actual
    return verified


def load_disposition_ledger(
    ctx: Any,
    path: str | Path | None,
    evidence: Mapping[str, Mapping[str, int]] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Operator-recorded dispositions, and a record of what was read to get them.

    A disposition is a claim about a *rule*, and this module can derive nothing
    of the kind: every fact it computes describes the corpus or the miner. So the
    ledger is an input, not an output, and its absence produces
    ``insufficient_evidence`` for every rule rather than a guess per rule.

    Six refusals, each of which would otherwise let an unearned claim through:

    - A rule identifier outside the registry is refused, not dropped. Section
      18.1 makes identifiers immutable, so an unknown one is a mistake, and
      silently ignoring it would silently lose the disposition it carried.
    - A value outside :data:`DISPOSITIONS` is refused. The vocabulary is closed
      so that a reader of the report knows the full set of things it can say.
    - A disposition other than ``insufficient_evidence`` with no ``tested_by``
      entry is refused. That is the whole invariant: a disposition nothing tested
      *is* insufficient evidence, whatever the ledger would prefer to call it.
    - An entry citing no observation, or one this report does not compute, is
      refused: an uncheckable claim is not evidence.
    - An entry whose cited counts disagree with the recomputed ones is refused,
      with both numbers in the message.
    - ``naturally_rare`` is refused unless the recomputed observations earn it
      (:func:`natural_rarity_obstacle`), whatever the entry's prose asserts.

    ``overturned_by`` is required of every entry for the same reason the basis is:
    a claim nobody can say how to falsify is not a finding. Every disposition
    remains one contrary observation away from being wrong.
    """
    rule_ids = ctx.registry.ids()
    if path is None:
        return {}, {
            "path": "(not searched)",
            "availability": "not_searched",
            "dispositions": None,
            "note": "No disposition ledger was named, so every rule carries the "
            f"{UNTESTED_DISPOSITION} default.",
        }
    ledger_file = Path(path)
    if not ledger_file.is_file():
        return {}, {
            "path": str(path),
            "availability": "not_found",
            "dispositions": None,
            "note": "No disposition ledger exists yet. The count is null rather than "
            "zero -- nothing was read, so nothing was found to be absent -- and every "
            f"rule carries the {UNTESTED_DISPOSITION} default until the annotation and "
            "adjudication cycle supplies one.",
        }
    entries: dict[str, dict[str, Any]] = {}
    for row in load_json(ledger_file).get("rule_dispositions", ()):
        rule_id = str(row["rule_id"])
        if rule_id not in rule_ids:
            raise UsageError(
                f"disposition ledger {ledger_file} names {rule_id!r}, which is not in "
                "the rule registry; a disposition for an unknown rule cannot be reported "
                "against any row and must not be dropped silently"
            )
        if rule_id in entries:
            raise UsageError(
                f"disposition ledger {ledger_file} records {rule_id!r} twice; a rule with "
                "two dispositions has none this report could publish"
            )
        value = str(row["disposition"])
        if value not in DISPOSITIONS:
            raise UsageError(
                f"disposition ledger {ledger_file} gives {rule_id} the disposition "
                f"{value!r}, which is not in the closed vocabulary "
                f"{sorted(DISPOSITIONS)}"
            )
        tested_by = [str(source) for source in row.get("tested_by", ())]
        if value != UNTESTED_DISPOSITION and not tested_by:
            raise UsageError(
                f"disposition ledger {ledger_file} gives {rule_id} the disposition "
                f"{value!r} and names nothing that tested it; a disposition no annotated "
                f"example tested is {UNTESTED_DISPOSITION}, and recording it as anything "
                "else would report an untested claim as a finding"
            )
        basis = str(row["basis"])
        if not basis:
            raise UsageError(
                f"disposition ledger {ledger_file} gives {rule_id} a disposition with an "
                "empty basis; the value is a claim about the standard and must say what "
                "it rests on"
            )
        overturned_by = str(row.get("overturned_by", ""))
        if not overturned_by:
            raise UsageError(
                f"disposition ledger {ledger_file} gives {rule_id} a disposition with no "
                "overturned_by; every disposition here rests on a handful of judgments, "
                "so an entry that cannot say what observation would refute it is an "
                "opinion wearing the vocabulary of a measurement"
            )
        recomputed = None if evidence is None else evidence.get(rule_id)
        observed = _check_observed_counts(
            ledger_file, rule_id, row.get("observed_counts") or {}, recomputed
        )
        if value == "naturally_rare":
            obstacle = natural_rarity_obstacle(rule_id, recomputed)
            if obstacle is not None:
                raise UsageError(
                    f"disposition ledger {ledger_file} calls {rule_id} naturally_rare, but "
                    f"{obstacle}. naturally_rare claims the construct does not occur, "
                    "which needs a reader who looked; it is never inferable from a rule "
                    "receiving no candidate"
                )
        entries[rule_id] = {
            "disposition": value,
            "tested_by": tested_by,
            "basis": basis,
            "overturned_by": overturned_by,
            "observed_counts": observed,
        }
    return entries, {
        "path": str(path),
        "availability": "present",
        "dispositions": len(entries),
        "note": "Dispositions are read from this ledger and never derived from a count: "
        "a mechanism explains a number, and only an annotated example can say what to do "
        "about a rule. Every cited observation is recomputed from the annotation round "
        "before the entry is accepted.",
    }


def rule_disposition(
    rule_id: str, ledger: Mapping[str, Mapping[str, Any]]
) -> tuple[str, dict[str, Any]]:
    """What to do about ``rule_id``, and whether anything tested that.

    Deliberately takes no reason, no count, and no signal fact. A caller cannot
    accidentally pass the mechanism in and have it become the disposition,
    because the mechanism is not in the signature: the two vocabularies overlap
    on the token ``naturally_rare`` and conflating them would turn "a wired cue
    matched nothing" into "the rule is fine", which is a different claim
    supported by different evidence.

    ``observed_counts`` and ``overturned_by`` are ``None`` for a rule the ledger
    does not mention, and never ``{}`` or ``""``: an empty object would read as
    "measured, nothing found", which is the opposite of an unexamined rule.
    """
    entry = ledger.get(rule_id)
    if entry is None:
        return UNTESTED_DISPOSITION, {
            "tested_against_annotated_examples": False,
            "tested_by": [],
            "basis": UNTESTED_BASIS,
            "observed_counts": None,
            "overturned_by": None,
        }
    tested_by = [str(source) for source in entry["tested_by"]]
    return str(entry["disposition"]), {
        "tested_against_annotated_examples": bool(tested_by),
        "tested_by": tested_by,
        "basis": str(entry["basis"]),
        "observed_counts": dict(entry["observed_counts"]),
        "overturned_by": str(entry["overturned_by"]),
    }


# -- candidate counts -------------------------------------------------------


def census_rule_counts(
    ctx: Any, census: Mapping[str, Any], authorized: Sequence[str]
) -> dict[str, dict[str, int]]:
    """Per-rule candidate counts read from a caller-supplied census.
    ``rules_touched`` counts candidates *relevant to* a rule, so the per-rule
    figures sum to more than the census's candidate total: one cue can be
    relevant to several rules and is counted once for each. Summing them would
    invent candidates, so no total over rules is produced here.
    """
    permitted = set(authorized)
    counts = {
        rule_id: {
            "candidate_count": 0,
            "repository_count": 0,
            "document_family_count": 0,
            "natural_candidate_count": 0,
        }
        for rule_id in ctx.registry.ids()
    }
    families: dict[str, set[str]] = {rule_id: set() for rule_id in counts}
    repositories: dict[str, set[str]] = {rule_id: set() for rule_id in counts}
    for row in census.get("repositories", ()):
        repository = str(row["repository"])
        family = str(row["family"])
        for rule_id, number in row["candidate_density"]["rules_touched"].items():
            if rule_id not in counts:
                raise UsageError(
                    f"census names candidates for {rule_id!r}, which is not in the rule "
                    "registry; a retired identifier MUST NOT be reused (spec 18.1)"
                )
            counts[rule_id]["candidate_count"] += int(number)
            repositories[rule_id].add(repository)
            families[rule_id].add(family)
            if repository in permitted:
                counts[rule_id]["natural_candidate_count"] += int(number)
    for rule_id, value in counts.items():
        value["repository_count"] = len(repositories[rule_id])
        value["document_family_count"] = len(families[rule_id])
    return counts


def example_store_counts(
    ctx: Any, path: str | Path | None
) -> tuple[dict[str, dict[str, int | None]], dict[str, Any]]:
    """Mutation and hard-negative counts per rule, plus what was searched.

    A store that does not exist yields ``None`` for every count, never ``0``: an
    unsearched location has no absences to report (ADR-0002). Counts are
    reported separately and never added to a natural count, because Section 17.5
    forbids treating a synthetic mutation as evidence of real-world prevalence.
    """
    rule_ids = ctx.registry.ids()
    unsearched: dict[str, dict[str, int | None]] = {
        rule_id: {"mutation_candidate_count": None, "hard_negative_count": None}
        for rule_id in rule_ids
    }
    if path is None:
        return unsearched, {
            "path": "(not searched)",
            "availability": "not_searched",
            "examples": None,
            "note": "No example store was named, so no mutation or hard-negative count "
            "was computed.",
        }
    store = Path(path)
    if not store.exists():
        return unsearched, {
            "path": str(path),
            "availability": "not_found",
            "examples": None,
            "note": "The example store does not exist. The counts are null rather than "
            "zero: nothing was inspected, so nothing was found to be absent.",
        }
    mutations = dict.fromkeys(rule_ids, 0)
    hard_negatives = dict.fromkeys(rule_ids, 0)
    examples = 0
    for record in rec.load_corpus(store).get("ats.text_example.v1", ()):
        rule_id = str(record.get("rule_id", ""))
        if rule_id not in mutations:
            raise UsageError(
                f"example store {store} holds an example for {rule_id!r}, which is not "
                "in the rule registry"
            )
        examples += 1
        if record.get("provenance") == "synthetic_mutation":
            mutations[rule_id] += 1
        if record.get("label") == "hard_negative":
            hard_negatives[rule_id] += 1
    counts: dict[str, dict[str, int | None]] = {
        rule_id: {
            "mutation_candidate_count": mutations[rule_id],
            "hard_negative_count": hard_negatives[rule_id],
        }
        for rule_id in rule_ids
    }
    return counts, {
        "path": str(path),
        "availability": "present",
        "examples": examples,
        "note": "Mutation and hard-negative counts are reported beside the natural "
        "count and never added to it (spec Section 17.5).",
    }


def resolve_mining_authority(
    census: Mapping[str, Any], overlay_dir: str | Path
) -> dict[str, Any]:
    """Which caller-supplied repositories may be mined for candidates.

    Resolution is from the supplied overlay. A repository's own
    ``.ats/corpus.json`` outranks an overlay
    (:meth:`ats.corpus.authority.AuthorityDeclaration.load`); callers that
    need in-place declarations must provide an inventory carrying them.
    """
    overlay = Path(overlay_dir)
    authorized: list[str] = []
    unauthorized: list[str] = []
    for row in census.get("repositories", ()):
        name = str(row["repository"])
        candidate = overlay / f"{name}.json"
        if candidate.is_file():
            declaration = AuthorityDeclaration.from_dict(
                load_json(candidate), repository=name, location="pilot_overlay"
            )
        else:
            declaration = AuthorityDeclaration.undeclared(name)
        # ``basis`` below is a single value for the whole report, so it is
        # checked against every declaration rather than asserted once. A
        # repository-owned declaration reaching this loop would make the
        # report's own provenance marker false, and an overlay reported as
        # repository-owned authority is the confusion the marker exists to
        # prevent -- so it is refused here rather than averaged away.
        if declaration.declared and declaration.declaration_location != _REPORT_BASIS:
            raise UsageError(
                f"the authority for {name} was read from "
                f"{declaration.declaration_location!r}, but this report declares its "
                f"basis as {_REPORT_BASIS!r}; a report carrying one provenance marker "
                "cannot mix declarations that came from different places"
            )
        (authorized if declaration.resolve(MINING_USE).permitted else unauthorized).append(name)
    return {
        "overlay_dir": str(overlay_dir),
        "basis": _REPORT_BASIS,
        "use": MINING_USE,
        "authorized_repositories": sorted(authorized),
        "unauthorized_repositories": sorted(unauthorized),
        "path_scoping": "not_applied",
        "path_scoping_note": (
            "A declaration's path excludes could not be intersected with these counts, "
            "because the census aggregates candidates per repository and not per path. "
            "The authorized figure is therefore an upper bound."
        ),
    }


# -- report -----------------------------------------------------------------


def build_rule_coverage(
    ctx: Any,
    *,
    census_path: str | Path,
    authority_overlay: str | Path = "corpus/authority",
    example_store: str | Path | None = "corpus/seeds",
    disposition_ledger: str | Path | None = None,
    annotation_round: str | Path | None = None,
    sampling_frame: str | Path | None = None,
    judgment_dir: str | Path | None = None,
) -> dict[str, Any]:
    """The per-rule coverage report over one caller-supplied corpus.

    Every rule in the registry gets exactly one row, whether or not the input
    mentions it: a rule absent from the table is a rule whose coverage nobody
    reported, which is the failure mode this report exists to prevent.

    Every row also carries a ``disposition`` -- what to do about the rule --
    kept strictly apart from ``suspected_reason_for_zero``, which is only a
    hypothesis about the mechanism behind a count. The disposition is read
    from ``disposition_ledger`` and is never inferred from a count in either
    direction: a zero does not condemn a rule and a large count does not
    defend one. With no ledger every rule reports ``insufficient_evidence``;
    once supplied, the ledger's evidence is recomputed from the input round on
    every run and an entry that no longer matches its own source is refused.
    """
    census_file = Path(census_path)
    if not census_file.is_file():
        raise UsageError(
            f"no census at {census_file}; the report reads a census rather than "
            "recomputing one, so it cannot proceed without it"
        )
    census = load_json(census_file)
    authority = resolve_mining_authority(census, authority_overlay)
    counts = census_rule_counts(ctx, census, authority["authorized_repositories"])
    example_counts, store = example_store_counts(ctx, example_store)
    evidence, evidence_meta = load_annotation_evidence(
        ctx,
        round_path=annotation_round,
        frame_path=sampling_frame,
        judgment_dir=judgment_dir,
    )
    ledger, ledger_meta = load_disposition_ledger(ctx, disposition_ledger, evidence)
    wired = wired_rules(ctx)

    rules: list[dict[str, Any]] = []
    reason_counts: dict[str, int] = {}
    disposition_counts: dict[str, int] = {}
    zero_dispositions: dict[str, int] = {}
    for rule_id in ctx.registry.ids():
        signal = deterministic_signal(ctx, rule_id, wired)
        profile = profile_dependency(ctx, rule_id)
        context = context_dependency(ctx, rule_id)
        candidate_count = counts[rule_id]["candidate_count"]
        reason = suspected_reason_for_zero(
            ctx,
            rule_id,
            candidate_count=candidate_count,
            signal=signal,
            profile=profile,
            context=context,
        )
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        disposition, disposition_evidence = rule_disposition(rule_id, ledger)
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
        if candidate_count == 0:
            zero_dispositions[disposition] = zero_dispositions.get(disposition, 0) + 1
        rules.append(
            {
                "rule_id": rule_id,
                "candidate_count": candidate_count,
                "repository_count": counts[rule_id]["repository_count"],
                "document_family_count": counts[rule_id]["document_family_count"],
                "natural_candidate_count": counts[rule_id]["natural_candidate_count"],
                "mutation_candidate_count": example_counts[rule_id]["mutation_candidate_count"],
                "hard_negative_count": example_counts[rule_id]["hard_negative_count"],
                "deterministic_signal_available": signal,
                "semantic_signal_required": semantic_requirement(ctx, rule_id),
                "profile_dependency": profile,
                "context_dependency": context,
                "suspected_reason_for_zero": reason,
                "recommended_action": recommended_action(
                    ctx,
                    rule_id,
                    reason=reason,
                    signal=signal,
                    candidate_count=candidate_count,
                    repository_count=counts[rule_id]["repository_count"],
                    natural_candidate_count=counts[rule_id]["natural_candidate_count"],
                ),
                "disposition": disposition,
                "disposition_evidence": disposition_evidence,
            }
        )

    with_candidates = sum(1 for row in rules if row["candidate_count"] > 0)
    report = {
        "schema_version": SCHEMA_VERSION,
        "report_sha256": "",
        "generated_at": ctx.timestamp(),
        "spec_version": ctx.spec_version,
        "implementation": ctx.implementation,
        "mining_constraint": MINING_CONSTRAINT,
        "census": {
            "path": str(census_path),
            "census_sha256": sha256_hex(census_file.read_bytes()),
            "documents": int(census["totals"]["documents"]),
            "repositories": int(census["totals"]["repositories"]),
            "document_families": len(
                {str(row["family"]) for row in census.get("repositories", ())}
            ),
            "candidates": int(census["totals"]["candidates"]),
        },
        "authority": authority,
        "example_store": store,
        "annotation_evidence": evidence_meta,
        "disposition_ledger": ledger_meta,
        "zero_reason_vocabulary": [
            {"reason": reason, "meaning": meaning} for reason, meaning in ZERO_REASONS.items()
        ],
        "disposition_vocabulary": [
            {"disposition": value, "meaning": meaning} for value, meaning in DISPOSITIONS.items()
        ],
        "observation_vocabulary": [
            {"observation": name, "meaning": meaning}
            for name, meaning in EVIDENCE_COUNTS.items()
        ],
        "rules": rules,
        "totals": {
            "rules": len(rules),
            "rules_with_candidates": with_candidates,
            "rules_without_candidates": len(rules) - with_candidates,
            "reason_counts": dict(sorted(reason_counts.items())),
            "disposition_counts": dict(sorted(disposition_counts.items())),
            "rules_with_tested_disposition": sum(
                1
                for row in rules
                if row["disposition_evidence"]["tested_against_annotated_examples"]
            ),
            "zero_candidate_disposition_counts": dict(sorted(zero_dispositions.items())),
        },
    }
    sealed = seal(report)
    ctx.schemas.validate_document(sealed)
    return sealed

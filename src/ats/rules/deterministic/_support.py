"""Shared plumbing for the deterministic IR detectors.

Each detector is declared once, as a :class:`DetectorSpec`. The same declaration
drives three things that would otherwise drift apart (constitution #5):

* what the detector is allowed to conclude at runtime;
* the per-rule capability document under ``capability/``;
* the ``authority`` recorded on every finding it emits.

A detector body never constructs a :class:`~ats.rules.results.RuleResult`
directly. It returns findings and subcheck records; :func:`run_detector` applies
the policy state, the missing-input rules, and
:func:`~ats.rules.results.decide`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Final, Mapping, Sequence

from ...ir.model import IrEvaluation
from ...rules.results import DecisionPower, Detector, Finding, RuleResult, decide
from . import register

#: Inputs the TextIR surface genuinely supplies.
#:
#: ``meaning_ledger`` is the TextIR itself (spec Section 4.14). ``text`` is the
#: claim and evidence propositions the IR carries. Everything absent from this
#: set is a real gap, not an inconvenience.
IR_SURFACE_INPUTS: Final[frozenset[str]] = frozenset(
    {
        "text",
        "profile",
        "glossary",
        "audience",
        "meaning_ledger",
        "force_lexicon",
        "policy",
        "metadata",
        "evidence",
        "requirement_ir",
        # Draft.2 inputs the TextIR document itself carries: the document is the
        # IR, and the optional stable-coordinates block and basis policy live
        # inside it (spec 7.17, 7.5).
        "ir_document",
        "stable_coordinates",
        "basis_policy",
    }
)

#: A substitution the IR surface may declare for an input it does not have.
#: Anything not listed here is blocking.
IR_SECTION_ORDER_SUBSTITUTION: Final[dict[str, str]] = {
    "input": "document_ast",
    "substituted_by": "TextIR section and claim ordering",
    "spec_ref": "ATS-1 7.3",
    "justification": (
        "Section 7.3 gives every section an identifier and an ordered claim list, so "
        "'first use in a section' and 'appears before' are decidable over the IR itself. "
        "This substitution covers ordering only; it does not supply paragraph or block "
        "structure, which the IR does not represent."
    ),
}

#: ``syntax`` stands in for the structured requirement slots when a subcheck
#: reads the slot rather than the sentence.
IR_REQUIREMENT_SLOT_SUBSTITUTION: Final[dict[str, str]] = {
    "input": "syntax",
    "substituted_by": "the requirement object's structured action slot",
    "spec_ref": "ATS-1 9.3.2, 9.3.3",
    "justification": (
        "Section 9.3.2 requires the action to be a slot in its own right, so counting the "
        "behaviours a requirement coordinates reads that slot, not a parse of the surrounding "
        "sentence. The substitution covers the slot only: two obligations expressed across "
        "separate sentences of the proposition remain undetectable, which the rule's known "
        "limits record."
    ),
}


@dataclass(frozen=True, slots=True)
class SubcheckSpec:
    """One named thing a detector actually inspects."""

    subcheck_id: str
    decides: bool
    spec_ref: str
    description: str
    vocabulary_source: str = "none"

    def to_capability(self) -> dict[str, Any]:
        return {
            "subcheck_id": self.subcheck_id,
            "decides": self.decides,
            "spec_ref": self.spec_ref,
            "vocabulary_source": self.vocabulary_source,
            "description": self.description,
        }


#: A detector body: given the evaluation and its detector identity, return the
#: findings it observed and the subcheck records describing what it inspected.
DetectorBody = Callable[[IrEvaluation, Detector], tuple[list[Finding], list[dict[str, Any]]]]


@dataclass(frozen=True, slots=True)
class DetectorSpec:
    rule_id: str
    detector_class: str
    power: DecisionPower
    subchecks: tuple[SubcheckSpec, ...]
    unavailable_conditions: tuple[str, ...]
    known_limits: tuple[str, ...]
    body: DetectorBody | None = None
    substitutions: tuple[Mapping[str, Any], ...] = ()
    #: Opt-in discipline (ADR-0002, review finding F1): when set, a clean run
    #: whose every subcheck is NOT_APPLICABLE reports NOT_APPLICABLE instead of
    #: PASS — the rule inspected nothing, so no exact comparison ran. The 30
    #: carried draft.1 rules keep the historical vacuous-PASS behavior; the
    #: coordinate rules opt in because a renderer could otherwise drop every
    #: coordinate with nothing failing.
    vacuous_pass: bool = False

    @property
    def detector_name(self) -> str:
        return f"ats-ir-{self.rule_id.lower()}"

    @property
    def implemented(self) -> bool:
        return self.power is not DecisionPower.UNDECIDABLE

    @property
    def authority(self) -> str:
        """Authority is capped by the detector class the registry allows.

        A rule whose registry record lists only D3 and D4 has no declared class
        describing a deterministic structural detector. Rather than claim a
        class the registry does not list, such a detector reports D3, and
        Section 12.3 caps D3 output at ``proposal_only``. Its findings are then
        surfaced for adjudication instead of deciding the rule.
        """
        from ...rules.registry import DETECTOR_CLASS_MAX_AUTHORITY

        if self.power is DecisionPower.UNDECIDABLE:
            return "none"
        return DETECTOR_CLASS_MAX_AUTHORITY[self.detector_class]

    def available_inputs(self, required: Sequence[str]) -> tuple[str, ...]:
        return tuple(i for i in required if i in IR_SURFACE_INPUTS)

    def missing_inputs(self, required: Sequence[str]) -> tuple[str, ...]:
        return tuple(i for i in required if i not in IR_SURFACE_INPUTS)

    def blocking_inputs(self, required: Sequence[str]) -> tuple[str, ...]:
        substituted = {s["input"] for s in self.substitutions}
        return tuple(i for i in self.missing_inputs(required) if i not in substituted)


#: rule_id -> spec, populated by :func:`detector`.
SPECS: dict[str, DetectorSpec] = {}


def detector(spec: DetectorSpec) -> Callable[[DetectorBody], DetectorBody]:
    """Declare and register a detector from its spec."""

    def wrap(body: DetectorBody) -> DetectorBody:
        bound = replace(spec, body=body)
        SPECS[spec.rule_id] = bound

        @register(spec.rule_id)
        def _run(ev: IrEvaluation) -> RuleResult:
            return run_detector(ev, bound)

        _run.__name__ = f"detect_{spec.rule_id.replace('-', '_').lower()}"
        _run.__doc__ = body.__doc__
        return body

    return wrap


def undecidable(spec: DetectorSpec) -> DetectorSpec:
    """Register a rule this surface cannot decide at all."""
    SPECS[spec.rule_id] = spec

    @register(spec.rule_id)
    def _run(ev: IrEvaluation) -> RuleResult:
        return run_detector(ev, spec)

    _run.__name__ = f"detect_{spec.rule_id.replace('-', '_').lower()}"
    return spec


def run_with_optional_inputs(
    ev: IrEvaluation,
    spec: DetectorSpec,
    body: DetectorBody,
    *,
    supplied: Callable[[Any], bool],
    missing: tuple[str, ...],
) -> RuleResult:
    """Run a detector whose transformation inputs MAY arrive in ``extensions``.

    :func:`run_detector` treats every required input as either present or absent
    for all evaluations, which fits the draft.1 rules. A draft.2 TRANSFORM
    detector can instead receive its source side through document extensions
    (the ``extensions.source_basis`` ledger for ATS-BASIS-002, the
    ``extensions.output_trace`` for ATS-PRES-003): when the substitution is
    present the body runs and decides; when it is absent the rule reports
    UNAVAILABLE naming the genuinely missing inputs, never PASS (ADR-0002).
    """
    rule = ev.ctx.registry.get(spec.rule_id)
    state = ev.state_for(spec.rule_id)
    det = ev.ctx.detector(
        spec.detector_name,
        detector_class=spec.detector_class if spec.detector_class != "none" else "D0",
        authority=spec.authority if spec.authority != "none" else "candidate_only",
        basis_anchor="ats-ir-rule",
    )

    if state.state == "disabled":
        return decide(
            rule_id=spec.rule_id,
            rule_version=rule.rule_version,
            profile=state.profile,
            effective_state=state.state,
            decision_power=spec.power,
            detector=det,
            reason=(
                f"rule state is disabled for profile {state.profile} under the resolved policy "
                f"(default {state.default_state}, layer {state.layer})"
            ),
        )

    if not supplied(ev.ir):
        return decide(
            rule_id=spec.rule_id,
            rule_version=rule.rule_version,
            profile=state.profile,
            effective_state=state.state,
            decision_power=DecisionPower.UNDECIDABLE,
            detector=det,
            missing_inputs=missing,
            reason=(
                f"the TextIR surface cannot supply {', '.join(missing)}; "
                f"{spec.unavailable_conditions[0] if spec.unavailable_conditions else 'no decision procedure applies'}"
            ),
            subchecks=[
                {
                    "subcheck_id": sc.subcheck_id,
                    "status": "UNAVAILABLE",
                    "spec_ref": sc.spec_ref,
                    "detail": sc.description,
                }
                for sc in spec.subchecks
            ],
        )

    findings, subchecks = body(ev, det)
    return decide(
        rule_id=spec.rule_id,
        rule_version=rule.rule_version,
        profile=state.profile,
        effective_state=state.state,
        decision_power=spec.power,
        detector=det,
        findings=findings,
        subchecks=subchecks,
    )


def run_detector(ev: IrEvaluation, spec: DetectorSpec) -> RuleResult:
    """Apply policy state, input availability, and the decision rules."""
    rule = ev.ctx.registry.get(spec.rule_id)
    state = ev.state_for(spec.rule_id)
    det = ev.ctx.detector(
        spec.detector_name,
        detector_class=spec.detector_class if spec.detector_class != "none" else "D0",
        authority=spec.authority if spec.authority != "none" else "candidate_only",
        basis_anchor="ats-ir-rule",
    )

    if state.state == "disabled":
        return decide(
            rule_id=spec.rule_id,
            rule_version=rule.rule_version,
            profile=state.profile,
            effective_state=state.state,
            decision_power=spec.power,
            detector=det,
            reason=(
                f"rule state is disabled for profile {state.profile} under the resolved policy "
                f"(default {state.default_state}, layer {state.layer})"
            ),
        )

    blocking = spec.blocking_inputs(rule.required_inputs)
    if blocking or spec.body is None:
        return decide(
            rule_id=spec.rule_id,
            rule_version=rule.rule_version,
            profile=state.profile,
            effective_state=state.state,
            decision_power=DecisionPower.UNDECIDABLE,
            detector=det,
            missing_inputs=blocking,
            reason=(
                f"the TextIR surface cannot supply {', '.join(blocking)}; "
                f"{spec.unavailable_conditions[0] if spec.unavailable_conditions else 'no decision procedure applies'}"
            ),
            subchecks=[
                {
                    "subcheck_id": sc.subcheck_id,
                    "status": "UNAVAILABLE",
                    "spec_ref": sc.spec_ref,
                    "detail": sc.description,
                }
                for sc in spec.subchecks
            ],
        )

    findings, subchecks = spec.body(ev, det)
    return decide(
        rule_id=spec.rule_id,
        rule_version=rule.rule_version,
        profile=state.profile,
        effective_state=state.state,
        decision_power=spec.power,
        detector=det,
        findings=findings,
        subchecks=subchecks,
        vacuous_pass=spec.vacuous_pass,
    )


# -- subcheck record helpers ------------------------------------------------


def subcheck(
    spec: SubcheckSpec, *, observed: int, violations: int, unavailable: bool = False
) -> dict[str, Any]:
    """Build the runtime record for one subcheck."""
    if unavailable:
        status = "UNAVAILABLE"
    elif violations:
        status = "FAIL"
    elif observed == 0:
        status = "NOT_APPLICABLE"
    elif spec.decides:
        status = "PASS"
    else:
        status = "REVIEW_REQUIRED"
    return {
        "subcheck_id": spec.subcheck_id,
        "status": status,
        "spec_ref": spec.spec_ref,
        "detail": spec.description,
        "observed": observed,
    }


# -- text helpers -----------------------------------------------------------
#
# Matching is always against a vocabulary that comes from the lexicon, the
# spec, or the artifact's own glossary. These helpers only handle word
# boundaries; they never carry a term list of their own.


def contains_phrase(text: str, phrase: str) -> bool:
    """Case-insensitive whole-word containment of a multi-word phrase."""
    import re

    pattern = r"(?<![\w-])" + re.escape(phrase) + r"(?![\w-])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def find_phrases(text: str, phrases: Sequence[str]) -> list[str]:
    """Every phrase from ``phrases`` present in ``text``, in vocabulary order."""
    return [p for p in phrases if contains_phrase(text, p)]


def contains_exact(text: str, token: str) -> bool:
    """Case-SENSITIVE whole-token containment, for uppercase deontic surfaces."""
    import re

    pattern = r"(?<![\w-])" + re.escape(token) + r"(?![\w-])"
    return re.search(pattern, text) is not None


@dataclass(slots=True)
class Collector:
    """Accumulates findings and keeps per-subcheck violation counts."""

    ev: IrEvaluation
    detector: Detector
    rule_id: str
    findings: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    observed: dict[str, int] = field(default_factory=dict)

    def saw(self, subcheck_id: str, n: int = 1) -> None:
        self.observed[subcheck_id] = self.observed.get(subcheck_id, 0) + n

    def flag(
        self,
        subcheck_id: str,
        *,
        issue_code: str,
        summary: str,
        spans: Sequence[Mapping[str, Any]],
        evidence_spans: Sequence[Mapping[str, Any]] = (),
        interpretations: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        self.counts[subcheck_id] = self.counts.get(subcheck_id, 0) + 1
        self.findings.append(
            self.ev.finding(
                rule_id=self.rule_id,
                issue_code=issue_code,
                summary=summary,
                spans=spans,
                detector=self.detector,
                evidence_spans=evidence_spans,
                interpretations=interpretations,
            )
        )

    def records(self, specs: Sequence[SubcheckSpec]) -> list[dict[str, Any]]:
        return [
            subcheck(
                sc,
                observed=self.observed.get(sc.subcheck_id, 0),
                violations=self.counts.get(sc.subcheck_id, 0),
            )
            for sc in specs
        ]

    def result(self, specs: Sequence[SubcheckSpec]) -> tuple[list[Finding], list[dict[str, Any]]]:
        return self.findings, self.records(specs)

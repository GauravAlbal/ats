"""Rule results, detector identity, and the never-PASS-by-absence discipline.

Spec Section 5.4: a required check that cannot execute is ``UNAVAILABLE``, not
``PASS``. Spec Section 16.5: for a required semantic rule, the absence of a
surfaced finding does not prove the rule passed.

This module encodes that as a small closed vocabulary and a *decision power*
declaration per detector. A detector may only return ``PASS`` when it declares
:data:`DecisionPower.DECIDES`, meaning it implements a complete decision
procedure for the rule over the inputs it received. A detector that can
recognise violations but cannot certify their absence declares
:data:`DecisionPower.DETECTS_VIOLATIONS` and returns ``REVIEW_REQUIRED``
instead of ``PASS`` when it finds nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final, Iterable, Mapping, Sequence

#: Result vocabulary required of every active rule by the v0 milestone.
#:
#: This is an implementation-level vocabulary and is deliberately distinct from
#: the normative ``conformance_status`` enum (which uses INSUFFICIENT_EVIDENCE
#: for the forecast-calibration dimension). :func:`to_conformance_status` maps
#: between them at the one place the two meet.
RESULT_STATUSES: Final[tuple[str, ...]] = (
    "PASS",
    "FAIL",
    "UNAVAILABLE",
    "NOT_APPLICABLE",
    "REVIEW_REQUIRED",
)


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class DecisionPower(StrEnum):
    """What a detector is entitled to conclude.

    ``DECIDES``
        Implements a complete decision procedure for the rule over the IR or
        output objects supplied. May return PASS or FAIL.
    ``DETECTS_VIOLATIONS``
        Recognises a defined subset of violations. May return FAIL; when it
        finds nothing it MUST return REVIEW_REQUIRED, never PASS.
    ``UNDECIDABLE``
        Cannot decide the rule from the available inputs at all. Returns
        UNAVAILABLE with the missing inputs named.
    """

    DECIDES = "decides"
    DETECTS_VIOLATIONS = "detects_violations"
    UNDECIDABLE = "undecidable"


@dataclass(frozen=True, slots=True)
class Detector:
    """An ``ats_common_v1#/$defs/detector`` value, as produced by this package."""

    name: str
    version: str
    detector_class: str
    authority: str
    authority_basis_ref: str | None = None
    detector_status: str = "deterministic"
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "class": self.detector_class,
            "authority": self.authority,
            "detector_status": self.detector_status,
        }
        if self.authority_basis_ref:
            out["authority_basis_ref"] = self.authority_basis_ref
        if self.run_id:
            out["run_id"] = self.run_id
        return out


@dataclass(frozen=True, slots=True)
class Finding:
    """An ``ats.finding.v1`` document under construction.

    Spec Section 13.1 lists the required content; :meth:`to_dict` emits exactly
    that shape so the finding validates against the normative schema.
    """

    finding_id: str
    artifact_id: str
    policy_snapshot_id: str
    rule_id: str
    rule_version: str
    profile: str
    spans: tuple[Mapping[str, Any], ...]
    issue_code: str
    summary: str
    severity: str
    detector: Detector
    applicability: str
    protected_impact: tuple[str, ...]
    state: str = "proposed"
    evidence_spans: tuple[Mapping[str, Any], ...] = ()
    interpretations: tuple[Mapping[str, Any], ...] = ()
    proposed_repairs: tuple[Mapping[str, Any], ...] = ()
    abstention_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": "ats.finding.v1",
            "finding_id": self.finding_id,
            "artifact_id": self.artifact_id,
            "policy_snapshot_id": self.policy_snapshot_id,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "profile": self.profile,
            "spans": [dict(s) for s in self.spans],
            "issue_code": self.issue_code,
            "summary": self.summary,
            "severity": self.severity,
            "detector": self.detector.to_dict(),
            "applicability": self.applicability,
            "protected_impact": list(self.protected_impact),
            "state": self.state,
        }
        if self.evidence_spans:
            out["evidence_spans"] = [dict(s) for s in self.evidence_spans]
        if self.interpretations:
            out["interpretations"] = [dict(i) for i in self.interpretations]
        if self.proposed_repairs:
            out["proposed_repairs"] = [dict(r) for r in self.proposed_repairs]
        if self.abstention_reason is not None:
            out["abstention_reason"] = self.abstention_reason
        return out


@dataclass(frozen=True, slots=True)
class RuleResult:
    """The explicit result of one rule under one resolved state.

    Every active rule receives one of these. There is no "no news is good news"
    path: :meth:`decide` is the only constructor used by detectors, and it
    refuses to emit PASS unless the detector declared a complete decision
    procedure.
    """

    rule_id: str
    rule_version: str
    profile: str
    effective_state: str
    status: Status
    decision_power: DecisionPower
    detector: Detector
    findings: tuple[Finding, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    reason: str = ""
    subchecks: tuple[Mapping[str, Any], ...] = ()

    @property
    def blocks_conformance(self) -> bool:
        """True when this result prevents its conformance dimension passing.

        Spec Section 5.4: FAIL or UNAVAILABLE on a required check blocks the
        dimension. REVIEW_REQUIRED blocks too, because an undispositioned
        surfaced obligation is not a pass (Section 15.3).
        """
        if self.effective_state != "required":
            return False
        return self.status in (Status.FAIL, Status.UNAVAILABLE, Status.REVIEW_REQUIRED)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": "ats.rule_result.v1",
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "profile": self.profile,
            "effective_state": self.effective_state,
            "status": str(self.status),
            "decision_power": str(self.decision_power),
            "detector": self.detector.to_dict(),
            "finding_ids": [f.finding_id for f in self.findings],
        }
        if self.missing_inputs:
            out["missing_inputs"] = list(self.missing_inputs)
        if self.reason:
            out["reason"] = self.reason
        if self.subchecks:
            out["subchecks"] = [dict(s) for s in self.subchecks]
        return out


def decide(
    *,
    rule_id: str,
    rule_version: str,
    profile: str,
    effective_state: str,
    decision_power: DecisionPower,
    detector: Detector,
    findings: Sequence[Finding] = (),
    missing_inputs: Iterable[str] = (),
    reason: str = "",
    subchecks: Sequence[Mapping[str, Any]] = (),
    vacuous_pass: bool = False,
) -> RuleResult:
    """Construct a :class:`RuleResult` under the never-PASS-by-absence rule.

    The status is derived, never supplied by the caller. Two independent gates
    apply, matching the spec's own statement that rule state and detector
    authority are orthogonal (Section 12.3):

    * *Decision power* gates PASS. Only a complete decision procedure may
      conclude conformance from the absence of a finding (Sections 5.4, 16.5).
    * *Detector authority* gates FAIL. ``candidate_only`` output can route work
      but cannot establish applicability, and ``proposal_only`` output can
      create a finding for adjudication but cannot independently establish PASS
      or FAIL (Section 12.3). Findings from such a detector are surfaced as
      REVIEW_REQUIRED with the findings attached, never as a decided failure.
    """
    findings = tuple(findings)
    missing = tuple(missing_inputs)
    decides_outcomes = detector.authority == "conformance_evidence"

    if effective_state == "disabled":
        status = Status.NOT_APPLICABLE
        reason = reason or "rule state is disabled under the resolved policy"
    elif missing:
        status = Status.UNAVAILABLE
        reason = reason or f"required inputs unavailable: {', '.join(missing)}"
    elif decision_power is DecisionPower.UNDECIDABLE:
        status = Status.UNAVAILABLE
        reason = reason or "no deterministic decision procedure is implemented for this rule"
    elif findings and decides_outcomes:
        status = Status.FAIL
    elif findings:
        status = Status.REVIEW_REQUIRED
        reason = reason or (
            f"{len(findings)} finding(s) raised by a {detector.authority} detector "
            f"(class {detector.detector_class}); such output can be adjudicated but cannot "
            "independently establish PASS or FAIL (spec 12.3)"
        )
    elif decision_power is DecisionPower.DECIDES and decides_outcomes:
        if vacuous_pass and subchecks and all(
            s.get("status") == "NOT_APPLICABLE" for s in subchecks
        ):
            # Opt-in discipline (ADR-0002; review F1): the rule inspected no
            # object, so no exact comparison ran. NOT_APPLICABLE never blocks,
            # so a document that simply never declares coordinates is not
            # penalized — but the rule does not claim a decided PASS either.
            status = Status.NOT_APPLICABLE
            reason = reason or (
                "every subcheck was NOT_APPLICABLE; the rule inspected no object, "
                "so no exact comparison ran"
            )
        else:
            status = Status.PASS
    elif decision_power is DecisionPower.DECIDES:
        status = Status.REVIEW_REQUIRED
        reason = reason or (
            f"a complete decision procedure ran and found nothing, but a {detector.authority} "
            "detector may not contribute a conformance decision (spec 12.3)"
        )
    else:
        status = Status.REVIEW_REQUIRED
        reason = reason or (
            "the implemented detector recognises a subset of violations and found none; "
            "absence of a deterministic violation does not establish conformance"
        )

    return RuleResult(
        rule_id=rule_id,
        rule_version=rule_version,
        profile=profile,
        effective_state=effective_state,
        status=status,
        decision_power=decision_power,
        detector=detector,
        findings=findings,
        missing_inputs=missing,
        reason=reason,
        subchecks=tuple(subchecks),
    )


def not_applicable(
    *,
    rule_id: str,
    rule_version: str,
    profile: str,
    effective_state: str,
    detector: Detector,
    reason: str,
) -> RuleResult:
    """A rule that does not apply to the artifact under evaluation."""
    return RuleResult(
        rule_id=rule_id,
        rule_version=rule_version,
        profile=profile,
        effective_state=effective_state,
        status=Status.NOT_APPLICABLE,
        decision_power=DecisionPower.DECIDES,
        detector=detector,
        reason=reason,
    )


@dataclass(frozen=True, slots=True)
class CheckResult:
    """A structural check that is not one of the thirty ATS rules.

    Profile completeness and IR/output structural integrity operate *in
    addition* to the rule catalog (spec Section 12.8), so they carry their own
    identifiers rather than being smuggled into a rule's result.
    """

    check_id: str
    title: str
    status: Status
    detail: str = ""
    spec_ref: str = ""
    findings: tuple[Finding, ...] = ()
    required: bool = True

    @property
    def blocks_conformance(self) -> bool:
        if not self.required:
            return False
        return self.status in (Status.FAIL, Status.UNAVAILABLE, Status.REVIEW_REQUIRED)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "check_id": self.check_id,
            "title": self.title,
            "status": str(self.status),
            "required": self.required,
        }
        if self.detail:
            out["detail"] = self.detail
        if self.spec_ref:
            out["spec_ref"] = self.spec_ref
        if self.findings:
            out["finding_ids"] = [f.finding_id for f in self.findings]
        return out


def to_conformance_status(status: Status) -> str:
    """Map an implementation result onto the normative ``conformance_status`` enum.

    ``REVIEW_REQUIRED`` maps to ``UNAVAILABLE`` rather than to ``PASS``: the
    check ran, but this implementation cannot supply conformance evidence for
    it, which is exactly what Section 5.4 calls unavailable.
    """
    if status is Status.REVIEW_REQUIRED:
        return "UNAVAILABLE"
    return str(status)


@dataclass(slots=True)
class ResultSet:
    """All rule results and structural checks for one artifact evaluation."""

    rule_results: list[RuleResult] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)

    def all_findings(self) -> list[Finding]:
        out: list[Finding] = []
        for r in self.rule_results:
            out.extend(r.findings)
        for c in self.checks:
            out.extend(c.findings)
        return out

    def counts(self) -> dict[str, int]:
        counts = dict.fromkeys(RESULT_STATUSES, 0)
        for r in self.rule_results:
            counts[str(r.status)] += 1
        return counts

    def required_blockers(self) -> list[RuleResult | CheckResult]:
        blockers: list[RuleResult | CheckResult] = [
            r for r in self.rule_results if r.blocks_conformance
        ]
        blockers.extend(c for c in self.checks if c.blocks_conformance)
        return blockers

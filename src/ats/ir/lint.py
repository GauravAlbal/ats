"""``ats ir lint`` — the deterministic IR linter.

Stage order follows spec Section 14.1 as far as the IR surface reaches: policy
resolution, profile resolution, meaning-ledger validation, deterministic checks,
conformance evaluation, receipt-shaped report emission. Stages this surface
skips are named in the conformance rationale rather than passed over.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..canonical import seal
from ..context import Context
from ..errors import SchemaValidationError
from ..policy import PolicySnapshot
from ..rules.deterministic import load_detectors
from ..rules.results import (
    CheckResult,
    Finding,
    RESULT_STATUSES,
    ResultSet,
    RuleResult,
    Status,
    to_conformance_status,
)
from .checks import run_structural_checks
from .model import IrDocument, IrEvaluation
from .validate import IR_SCHEMA_ID, validate_ir

REPORT_SCHEMA_ID = "ats_ir_lint_report_v1.schema.json"

#: Checks whose failure blocks the mechanical dimension specifically
#: (spec Section 15.1: required deterministic checks, parser capability,
#: glossary and policy resolution, deterministic replay).
MECHANICAL_CHECKS = frozenset(
    {
        "IR-SCHEMA",
        "IR-POLICY-IDENTITY",
        "IR-POLICY-CURRENTNESS",
        "IR-SOURCE-HASH",
        "IR-ID-UNIQUE",
        "IR-REFS",
        "IR-SECTION-PROFILE",
        "IR-GLOSSARY-REFS",
        "IR-LIKELIHOOD-VOCAB",
        "IR-FIRST-USE-RANGE",
        "IR-CONFIDENCE-BASIS",
        "IR-DEONTIC-VALIDITY",
        "IR-EXTRACTION-STATUS",
        "IR-POLICY-EXCEPTIONS",
        "IR-CANONICAL",
    }
)


def lint_ir(
    ctx: Context,
    ir_document: Mapping[str, Any],
    policy_document: Mapping[str, Any],
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Lint one TextIR document and return a sealed report."""
    violations = validate_ir(ctx, ir_document)
    if violations:
        # A document that does not validate cannot be indexed, so the report is
        # the schema failure itself rather than a partially evaluated artifact.
        raise SchemaValidationError(IR_SCHEMA_ID, violations)

    policy = ctx.policy(policy_document)
    ir = IrDocument.from_document(ir_document)
    states, conflicts = policy.resolve_all(
        ir.profiles or policy.profiles, now=ctx.now, artifact_id=ir.artifact_id
    )
    evaluation = IrEvaluation(ctx=ctx, ir=ir, policy=policy, states=states)

    results = ResultSet()
    results.checks.extend(
        run_structural_checks(
            ctx,
            ir,
            policy,
            schema_violations=violations,
            source_path=Path(source_path) if source_path else None,
        )
    )

    detectors = load_detectors(ctx.registry.ids())
    for rule_id in ctx.registry.ids():
        detector = detectors.get(rule_id)
        if detector is None:
            results.rule_results.append(_unimplemented(ctx, evaluation, rule_id))
            continue
        results.rule_results.append(detector(evaluation))

    return _build_report(ctx, ir, policy, states, conflicts, results, source_path)


def _unimplemented(ctx: Context, ev: IrEvaluation, rule_id: str) -> RuleResult:
    """A rule with no registered detector reports UNAVAILABLE, never a pass."""
    from ..rules.results import DecisionPower, decide

    rule = ctx.registry.get(rule_id)
    state = ev.state_for(rule_id)
    return decide(
        rule_id=rule_id,
        rule_version=rule.rule_version,
        profile=state.profile,
        effective_state=state.state,
        decision_power=DecisionPower.UNDECIDABLE,
        detector=ctx.detector(
            f"ats-ir-{rule_id.lower()}", detector_class="D0", authority="candidate_only"
        ),
        missing_inputs=tuple(rule.required_inputs),
        reason="no detector is registered for this rule in this build",
    )


def _build_report(
    ctx: Context,
    ir: IrDocument,
    policy: PolicySnapshot,
    states: Mapping[str, Any],
    conflicts: list,
    results: ResultSet,
    source_path: str | Path | None,
) -> dict[str, Any]:
    findings: list[Finding] = results.all_findings()
    by_status = dict.fromkeys(RESULT_STATUSES, 0)
    for result in results.rule_results:
        by_status[str(result.status)] += 1

    required = [r for r in results.rule_results if r.effective_state == "required"]
    advisory_findings = sum(
        len(r.findings) for r in results.rule_results if r.effective_state == "advisory"
    )

    conformance, rationale = compute_conformance(ir, policy, results)

    report: dict[str, Any] = {
        "schema_version": "ats.ir_lint_report.v1",
        "report_id": f"irlint:{ir.artifact_id}:{ir.ir_sha256[:16]}",
        "artifact_id": ir.artifact_id,
        "ir_sha256": ir.ir_sha256,
        "source_content_sha256": ir.source["content_sha256"],
        "spec_version": ctx.spec_version,
        "policy_snapshot_id": policy.snapshot_id,
        "policy_sha256": policy.declared_sha256,
        "profiles": list(ir.profiles or policy.profiles),
        "implementation": {**ctx.implementation, "schema_set_sha256": ctx.schema_set_sha256},
        "structural_checks": [c.to_dict() for c in results.checks],
        "rule_results": [r.to_dict() for r in results.rule_results],
        "findings": [f.to_dict() for f in findings],
        "summary": {
            "rules_total": len(results.rule_results),
            "by_status": by_status,
            "required_failed": sum(1 for r in required if r.status is Status.FAIL),
            "required_unavailable": sum(1 for r in required if r.status is Status.UNAVAILABLE),
            "required_review_required": sum(
                1 for r in required if r.status is Status.REVIEW_REQUIRED
            ),
            "advisory_findings": advisory_findings,
        },
        "conformance": conformance,
        "conformance_rationale": rationale,
        "created_at": ctx.timestamp(),
    }

    unsupported = [p for p in ir.profiles if p not in ("ASSESS", "SPECIFY", "TRANSFORM")]
    if unsupported:
        report["unsupported_profiles"] = sorted(set(unsupported))
    if conflicts:
        report["policy_conflicts"] = [
            {
                "rule_id": c.rule_id,
                "profiles": list(c.profiles),
                "states": list(c.states),
                "detail": c.detail,
            }
            for c in conflicts
        ]
    ignored = PolicySnapshot.ignored_directives(states)
    if ignored:
        report["ignored_policy_directives"] = [d.to_dict() for d in ignored]

    sealed = seal(report)
    ctx.schemas.validate(sealed, REPORT_SCHEMA_ID)
    return sealed


def compute_conformance(
    ir: IrDocument, policy: PolicySnapshot, results: ResultSet
) -> tuple[dict[str, str], dict[str, str]]:
    """The five-dimension vector and why each dimension holds its status.

    Nothing here averages or compensates (spec Sections 5.2 and 15.6). Each
    dimension is computed from its own evidence and reports the first reason it
    is not PASS.
    """
    checks = {c.check_id: c for c in results.checks}
    rules = {r.rule_id: r for r in results.rule_results}

    # -- mechanical --------------------------------------------------------
    mech_failed = [
        c for cid, c in checks.items() if cid in MECHANICAL_CHECKS and c.status is Status.FAIL
    ]
    mech_unavailable = [
        c
        for cid, c in checks.items()
        if cid in MECHANICAL_CHECKS and c.status is Status.UNAVAILABLE
    ]
    required_d01 = [
        r
        for r in results.rule_results
        if r.effective_state == "required"
        and r.detector.detector_class in ("D0", "D1")
        and r.detector.authority == "conformance_evidence"
    ]
    rule_failed = [r for r in required_d01 if r.status is Status.FAIL]
    rule_unavailable = [r for r in required_d01 if r.status is Status.UNAVAILABLE]

    if mech_failed or rule_failed:
        mechanical = "FAIL"
        mech_why = (
            "required deterministic evidence failed: "
            + ", ".join(
                [c.check_id for c in mech_failed] + [r.rule_id for r in rule_failed]
            )
        )
    elif mech_unavailable or rule_unavailable:
        mechanical = "UNAVAILABLE"
        mech_why = (
            "a required deterministic check could not execute, which is UNAVAILABLE and not "
            "PASS (spec 5.4): "
            + ", ".join(
                [c.check_id for c in mech_unavailable] + [r.rule_id for r in rule_unavailable]
            )
        )
    else:
        mechanical = "PASS"
        mech_why = (
            f"every required deterministic check executed and passed "
            f"({len(required_d01)} conformance-evidence rule(s), "
            f"{len(MECHANICAL_CHECKS)} structural check(s)); canonical replay reproduces the "
            "content address"
        )

    # -- profile -----------------------------------------------------------
    profile_check = checks.get("IR-PROFILE-SLOTS")
    if profile_check is None:  # pragma: no cover - always present
        profile, prof_why = "UNAVAILABLE", "the profile validator did not run"
    else:
        profile = to_conformance_status(profile_check.status)
        prof_why = profile_check.detail or "profile completeness evaluated"
        if profile_check.status is Status.PASS:
            prof_why = (
                "every required semantic slot for the active profile is resolved: "
                + profile_check.detail
            )

    # -- semantic review ---------------------------------------------------
    surfaced = [
        r
        for r in results.rule_results
        if r.status in (Status.FAIL, Status.REVIEW_REQUIRED) and r.effective_state != "disabled"
    ]
    semantic = "UNAVAILABLE"
    semantic_why = (
        f"{len(surfaced)} rule result(s) require disposition and this implementation holds no "
        "disposition authority. Section 15.3 requires every surfaced finding to be dispositioned "
        "by an authorized human, an authoritative structured source, or a detector validated as "
        "conformance_evidence, and Section 14.11 assigns final semantic acceptance to an external "
        "authority. semantic_review is therefore never PASS in this implementation."
    )

    # -- preservation ------------------------------------------------------
    transform_active = any(
        rules[rid].effective_state != "disabled"
        for rid in ("ATS-PRES-001", "ATS-PRES-002")
        if rid in rules
    )
    if not transform_active:
        preservation = "NOT_APPLICABLE"
        pres_why = (
            "no TRANSFORM profile is active and both preservation rules resolve to disabled, so "
            "this artifact is not a transformation output (spec 15.4)"
        )
    else:
        preservation = "UNAVAILABLE"
        pres_why = (
            "ATS-PRES-001 and ATS-PRES-002 are active but their source IR, output IR, retention "
            "contract, and authorization inputs were not supplied. Section 6.4 makes both rules "
            "unwaivable, so preservation MUST NOT be reported as PASS while they are unavailable."
        )

    # -- forecast calibration ---------------------------------------------
    forecasts = [c for c in ir.all_claims() if c.role == "forecast"]
    resolved = [
        c
        for c in forecasts
        if (c.forecast or {}).get("outcome_status") in ("resolved_true", "resolved_false")
    ]
    forecast = "INSUFFICIENT_EVIDENCE"
    forecast_why = (
        f"{len(forecasts)} forecast claim(s), {len(resolved)} resolved. Section 15.5 requires a "
        "declared cohort, a scoring rule, reliability analysis, uncertainty estimates, and a "
        "pre-declared minimum evidence threshold. None is implemented, so the honest result is "
        "INSUFFICIENT_EVIDENCE rather than a calibration claim."
    )

    return (
        {
            "mechanical": mechanical,
            "profile": profile,
            "semantic_review": semantic,
            "preservation": preservation,
            "forecast_calibration": forecast,
        },
        {
            "mechanical": mech_why,
            "profile": prof_why,
            "semantic_review": semantic_why,
            "preservation": pres_why,
            "forecast_calibration": forecast_why,
        },
    )

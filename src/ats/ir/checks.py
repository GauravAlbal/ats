"""The twenty-seven structural checks over a TextIR document and its policy.

These sit alongside the thirty rules (spec Section 12.8). Each has a stable
identifier, a spec reference, and one of the five result statuses. A check that
cannot run says so; none of them reports PASS because nothing was inspected.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ..canonical import canonical_bytes, content_hash, sha256_hex
from ..capability import CapabilityDeclaration
from ..context import Context
from ..errors import UsageError
from ..hashes import bind_file
from ..policy import PolicySnapshot, STABLE_PROFILES
from ..rules.registry import ForceLexicon
from ..rules.results import CheckResult, Status
from .model import IrDocument
from .profile import evaluate_profiles
from .references import (
    iter_reference_problems,
    unresolved_concept_refs,
    unresolved_glossary_refs,
)


def _check(
    check_id: str,
    title: str,
    spec_ref: str,
    *,
    ok: bool | None,
    ok_detail: str,
    fail_detail: str,
    unavailable_detail: str = "",
    required: bool = True,
) -> CheckResult:
    """Small constructor: ``None`` means the check could not run."""
    if ok is None:
        status, detail = Status.UNAVAILABLE, unavailable_detail
    elif ok:
        status, detail = Status.PASS, ok_detail
    else:
        status, detail = Status.FAIL, fail_detail
    return CheckResult(
        check_id=check_id, title=title, status=status, detail=detail, spec_ref=spec_ref,
        required=required,
    )


def run_structural_checks(
    ctx: Context,
    ir: IrDocument,
    policy: PolicySnapshot,
    *,
    schema_violations: list,
    source_path: Path | None = None,
) -> list[CheckResult]:
    """Every structural check, in a stable order."""
    lex = ctx.lexicon
    checks: list[CheckResult] = [
        _ir_schema(schema_violations),
        _ir_policy_identity(ir, policy),
        _ir_policy_currentness(ctx, policy),
        _ir_source_hash(ir, source_path),
        _ir_id_unique(ir),
        _ir_refs(ir),
        _ir_section_profile(ir, policy),
        evaluate_profiles(ir)[0],
        _ir_claim_role_fields(ir),
        _ir_evidence_endpoints(ir),
        _ir_glossary_refs(ir, policy),
        _ir_likelihood_vocab(ir, lex),
        _ir_first_use_range(ir, lex),
        _ir_likelihood_confidence_sep(ir),
        _ir_confidence_basis(ir, lex),
        _ir_update_indicators(ir),
        _ir_deontic_validity(ir, lex),
        _ir_requirement_slots(ir),
        _ir_one_obligation(ir),
        _ir_quant_units(ir),
        _ir_polarity_quantifier(ir),
        _ir_p0_p1_declarations(ir, ctx),
        _ir_extraction_status(ir),
        _ir_policy_exceptions(policy, ctx.now),
        _ir_capability(ctx.capability, policy, ir),
        _ir_canonical(ir),
        _ir_basis_schema(ir),
    ]
    return checks


# -- individual checks ------------------------------------------------------


def _ir_schema(violations: list) -> CheckResult:
    return _check(
        "IR-SCHEMA",
        "TextIR conforms to ats_text_ir_v1.schema.json",
        "ATS-1 19.4, Appendix C",
        ok=not violations,
        ok_detail="the document validates against the normative TextIR schema",
        fail_detail="; ".join(f"{v.pointer or '/'}: {v.message}" for v in violations[:6]),
    )


def _ir_policy_identity(ir: IrDocument, policy: PolicySnapshot) -> CheckResult:
    computed = policy.computed_sha256()
    problems: list[str] = []
    if ir.policy_snapshot_id != policy.snapshot_id:
        problems.append(
            f"the IR binds policy_snapshot_id {ir.policy_snapshot_id!r} but the supplied "
            f"snapshot is {policy.snapshot_id!r}"
        )
    if computed != policy.declared_sha256:
        problems.append(
            f"snapshot_sha256 {policy.declared_sha256} does not match the canonical bytes "
            f"({computed})"
        )
    return _check(
        "IR-POLICY-IDENTITY",
        "The bound policy snapshot is the one supplied, and its content address holds",
        "ATS-1 6.6, 14.13",
        ok=not problems,
        ok_detail=f"policy {policy.snapshot_id!r} binds at {computed}",
        fail_detail="; ".join(problems),
    )


def _ir_policy_currentness(ctx: Context, policy: PolicySnapshot) -> CheckResult:
    problems: list[str] = []
    if policy.spec_version != ctx.spec_version:
        problems.append(
            f"policy targets spec {policy.spec_version!r}, imported package is "
            f"{ctx.spec_version!r}"
        )
    expired = [d for d in policy.exception_diagnostics(ctx.now) if d.status == "expired"]
    if expired:
        problems.append(
            f"{len(expired)} expired exception(s) remain in the snapshot: "
            + ", ".join(d.exception_id for d in expired)
        )
    if policy.fallback_policy != "fail_closed":
        problems.append(
            f"fallback_policy is {policy.fallback_policy!r}; this implementation declares no "
            "authorized fallback component, so a non-fail-closed policy cannot be honoured "
            "(spec 14.12)"
        )
    return _check(
        "IR-POLICY-CURRENTNESS",
        "Policy currentness inputs hold for the artifact scope",
        "ATS-1 14.3, 14.12, 15.8",
        ok=not problems,
        ok_detail=(
            f"policy targets the imported spec version, no exception has expired, and the "
            f"fallback policy is fail_closed"
        ),
        fail_detail="; ".join(problems),
    )


def _ir_source_hash(ir: IrDocument, source_path: Path | None) -> CheckResult:
    """Verify that the declared hashes bind the actual input bytes.

    Without the source file this is UNAVAILABLE, unconditionally. Appendix C
    requires a normalization step to *retain* a separate normalized hash rather
    than replace the source hash; it does not require the two digests to
    differ. For a source that is already NFC, LF-terminated, and free of
    trailing horizontal whitespace, :func:`ats.hashes.normalize_text` is a
    no-op and the two digests are legitimately equal. Treating that equality as
    a defect would manufacture a decided failure out of missing input, which is
    the inverse of Sections 5.4 and 20.6.
    """
    source = ir.source
    content = source.get("content_sha256", "")
    normalized = source.get("normalized_sha256")
    if source_path is None:
        return CheckResult(
            "IR-SOURCE-HASH",
            "Source and normalized hashes bind the exact input bytes",
            Status.UNAVAILABLE,
            f"content_sha256 {content[:16]}… is well formed, but no source file was supplied, "
            "so the binding to actual bytes is unverified (spec 14.2). Re-run with the source "
            "to decide this check.",
            "ATS-1 14.2, Appendix C",
        )
    binding = bind_file(source_path)
    problems: list[str] = []
    if binding.content_sha256 != content:
        problems.append(
            f"{source_path} hashes to {binding.content_sha256}, the IR declares {content}"
        )
    if normalized and binding.normalized_sha256 != normalized:
        problems.append(
            f"normalized bytes hash to {binding.normalized_sha256}, the IR declares {normalized}"
        )
    detail = f"{source_path.name} matches the declared content hash"
    if normalized:
        detail += (
            " and normalized hash"
            + (
                " (identical, because normalization is a no-op for this source)"
                if normalized == content
                else ""
            )
        )
    else:
        detail += "; the IR declares no normalized hash, so no normalization is claimed"
    return _check(
        "IR-SOURCE-HASH",
        "Source and normalized hashes bind the exact input bytes",
        "ATS-1 14.2, Appendix C",
        ok=not problems,
        ok_detail=detail,
        fail_detail="; ".join(problems),
    )


def _ir_id_unique(ir: IrDocument) -> CheckResult:
    duplicates = ir.duplicate_ids()
    return _check(
        "IR-ID-UNIQUE",
        "Every identifier is used once",
        "ATS-1 7.3, 9.3.18, 7.17",
        ok=not duplicates,
        ok_detail=(
            f"{len(ir.object_ids)} object identifiers are distinct and every declared "
            "stable coordinate and requirement/decision/acceptance-criterion id is used once"
        ),
        fail_detail="; ".join(f"{k} at {', '.join(v)}" for k, v in duplicates[:6]),
    )


def _ir_refs(ir: IrDocument) -> CheckResult:
    problems = list(iter_reference_problems(ir))
    return _check(
        "IR-REFS",
        "Every internal reference resolves to an object of the right kind",
        "ATS-1 7.9, 7.11, 7.13, 7.14, 7.17",
        ok=not problems,
        ok_detail=(
            "all claim, evidence, relation, indicator, dependency-target, and "
            "acceptance-criterion references resolve"
        ),
        fail_detail="; ".join(f"{p.pointer}: {p.detail}" for p in problems[:6]),
    )


def _ir_section_profile(ir: IrDocument, policy: PolicySnapshot) -> CheckResult:
    problems: list[str] = []
    unsupported: list[str] = []
    for section in ir.sections:
        if not section.profiles:
            problems.append(f"{section.section_id}: no profile (spec 6.5)")
            continue
        for profile in section.profiles:
            if profile not in STABLE_PROFILES:
                unsupported.append(f"{section.section_id}:{profile}")
            elif profile not in policy.profiles:
                problems.append(
                    f"{section.section_id}: profile {profile} is not among the policy's "
                    f"declared profiles {list(policy.profiles)}"
                )
    if problems:
        return CheckResult(
            "IR-SECTION-PROFILE",
            "Every section resolves to a declared content profile",
            Status.FAIL,
            "; ".join(problems[:6]),
            "ATS-1 6.5, 9.4, 9.5",
        )
    if unsupported:
        return CheckResult(
            "IR-SECTION-PROFILE",
            "Every section resolves to a declared content profile",
            Status.UNAVAILABLE,
            f"reserved or extension profiles present and preserved, not coerced: "
            f"{', '.join(sorted(set(unsupported)))} (spec 9.5)",
            "ATS-1 6.5, 9.4, 9.5",
        )
    return CheckResult(
        "IR-SECTION-PROFILE",
        "Every section resolves to a declared content profile",
        Status.PASS,
        f"{len(ir.sections)} section(s) resolve to profiles the policy declares",
        "ATS-1 6.5, 9.4, 9.5",
    )


#: Force fields each claim role may carry (spec Section 7.4 role meanings plus
#: Sections 9.2.5 and 9.2.10 on role transitions).
ROLE_FORBIDDEN_FORCE: dict[str, tuple[str, ...]] = {
    "definition": ("likelihood", "assessment_confidence", "evidential", "causal"),
    "observation": ("likelihood", "assessment_confidence"),
    "sourced_report": ("likelihood", "assessment_confidence"),
    "assumption": ("evidential",),
    "recommendation": ("evidential", "causal"),
    "requirement": ("likelihood",),
    "exception": ("likelihood",),
    "boundary": ("likelihood",),
}


def _ir_claim_role_fields(ir: IrDocument) -> CheckResult:
    problems: list[str] = []
    for claim in ir.all_claims():
        forbidden = ROLE_FORBIDDEN_FORCE.get(claim.role, ())
        for field in forbidden:
            if claim.force.get(field) is not None:
                problems.append(
                    f"{claim.pointer}: role {claim.role!r} carries force.{field}"
                )
        if claim.role == "requirement" and claim.requirement is None:
            problems.append(f"{claim.pointer}: role 'requirement' without a requirement object")
        if claim.role == "forecast" and claim.forecast is None:
            problems.append(f"{claim.pointer}: role 'forecast' without a forecast object")
        if claim.requirement is not None and claim.role != "requirement":
            problems.append(
                f"{claim.pointer}: a requirement object on role {claim.role!r} hides a normative "
                "obligation behind a non-normative role (spec 7.4)"
            )
    return _check(
        "IR-CLAIM-ROLE-FIELDS",
        "Claim roles carry only the fields their role admits",
        "ATS-1 7.4, 7.5, 9.2.5, 9.2.10",
        ok=not problems,
        ok_detail=f"{len(ir.claims)} claim(s) carry force fields compatible with their role",
        fail_detail="; ".join(problems[:6]),
    )


def _ir_evidence_endpoints(ir: IrDocument) -> CheckResult:
    problems: list[str] = []
    for section in ir.sections:
        for ev in section.evidence:
            source = ev.source
            availability = ev.availability
            if availability == "present":
                if not (source.get("locator") or source.get("content_sha256")):
                    problems.append(
                        f"{ev.pointer}: availability 'present' with neither locator nor "
                        "content hash, so the evidence cannot be retrieved (spec 9.2.6)"
                    )
            if source.get("availability") != availability:
                problems.append(
                    f"{ev.pointer}: evidence availability {availability!r} disagrees with its "
                    f"source availability {source.get('availability')!r}"
                )
            if availability == "not_searched" and not source.get("search_scope"):
                problems.append(
                    f"{ev.pointer}: 'not_searched' without a declared search scope leaves the "
                    "search state unbounded (spec 9.2.7)"
                )
    return _check(
        "IR-EVIDENCE-ENDPOINTS",
        "Evidence objects are retrievable or carry an exact availability state",
        "ATS-1 7.9, 7.10, 9.2.6, 9.2.7",
        ok=not problems,
        ok_detail=f"{len(ir.evidence)} evidence object(s) carry coherent availability",
        fail_detail="; ".join(problems[:6]),
    )


def _ir_glossary_refs(ir: IrDocument, policy: PolicySnapshot) -> CheckResult:
    unresolved = unresolved_glossary_refs(ir, policy.raw.get("glossary_refs", ()))
    malformed = unresolved_concept_refs(ir)
    problems = [f"{ptr}: term base {ref!r} is not declared by the policy" for ref, ptr in unresolved]
    problems += [f"{ptr}: glossary entry {cid!r} is incomplete" for cid, ptr in malformed]
    return _check(
        "IR-GLOSSARY-REFS",
        "Glossary and assumed term-base references resolve",
        "ATS-1 7.2, 10.3",
        ok=not problems,
        ok_detail=f"{len(ir.glossary)} glossary entr(ies) and every assumed term base resolve",
        fail_detail="; ".join(problems[:6]),
    )


def _ir_likelihood_vocab(ir: IrDocument, lex: ForceLexicon) -> CheckResult:
    problems: list[str] = []
    seen = 0
    for claim in ir.all_claims():
        likelihood = claim.likelihood
        if likelihood is None:
            continue
        seen += 1
        kind = likelihood.get("kind")
        if kind != "wep":
            continue
        term = likelihood.get("term")
        if term not in lex.wep_terms:
            problems.append(f"{claim.pointer}: {term!r} is not a canonical WEP term")
            continue
        lower, upper, _ = lex.interval_for(term)
        if likelihood.get("lower") != lower or likelihood.get("upper") != upper:
            problems.append(
                f"{claim.pointer}: term {term!r} declares "
                f"[{likelihood.get('lower')}, {likelihood.get('upper')}], lexicon says "
                f"[{lower}, {upper}]"
            )
    if seen == 0:
        return CheckResult(
            "IR-LIKELIHOOD-VOCAB",
            "WEP terms and intervals match the active lexicon",
            Status.NOT_APPLICABLE,
            "no claim declares a likelihood",
            "ATS-1 8.2, 19.3",
        )
    return _check(
        "IR-LIKELIHOOD-VOCAB",
        "WEP terms and intervals match the active lexicon",
        "ATS-1 8.2, 19.3",
        ok=not problems,
        ok_detail=f"{seen} likelihood object(s) match lexicon {lex.version}",
        fail_detail="; ".join(problems[:6]),
    )


def _ir_first_use_range(ir: IrDocument, lex: ForceLexicon) -> CheckResult:
    if not lex.first_use_must_show_range:
        return CheckResult(
            "IR-FIRST-USE-RANGE",
            "First material WEP use declares its display range",
            Status.NOT_APPLICABLE,
            "the active lexicon does not require a first-use range",
            "ATS-1 8.4",
        )
    problems: list[str] = []
    seen = 0
    for section in ir.sections:
        first = next(
            (
                c
                for c in section.claims
                if c.material and c.likelihood and c.likelihood.get("kind") == "wep"
            ),
            None,
        )
        if first is None:
            continue
        seen += 1
        likelihood = first.likelihood or {}
        if not likelihood.get("range_shown_inline"):
            problems.append(
                f"{first.pointer}: first material WEP use in section "
                f"{section.section_id!r} does not show its range inline"
            )
        elif "display" not in likelihood:
            problems.append(
                f"{first.pointer}: range_shown_inline is true but no display string records "
                "what was shown"
            )
    if seen == 0:
        return CheckResult(
            "IR-FIRST-USE-RANGE",
            "First material WEP use declares its display range",
            Status.NOT_APPLICABLE,
            "no section contains a material WEP use",
            "ATS-1 8.4",
        )
    return _check(
        "IR-FIRST-USE-RANGE",
        "First material WEP use declares its display range",
        "ATS-1 8.4",
        ok=not problems,
        ok_detail=f"{seen} section(s) declare an inline range at first material WEP use",
        fail_detail="; ".join(problems[:6]),
    )


def _ir_likelihood_confidence_sep(ir: IrDocument) -> CheckResult:
    """Section 8.11: distinct fields, and neither substituting for the other."""
    problems: list[str] = []
    for claim in ir.all_claims():
        force = claim.force
        if "likelihood" in force and "assessment_confidence" in force:
            likelihood = force["likelihood"]
            confidence = force["assessment_confidence"]
            if likelihood.get("display") and likelihood["display"] == confidence.get("level"):
                problems.append(
                    f"{claim.pointer}: the likelihood display and the confidence level are the "
                    "same string, so the two axes are not distinguishable"
                )
    return _check(
        "IR-LIKELIHOOD-CONFIDENCE-SEP",
        "Likelihood and assessment confidence occupy distinct fields",
        "ATS-1 8.11, 4.8",
        ok=not problems,
        ok_detail="the schema keeps the two axes in separate fields and no claim collapses them",
        fail_detail="; ".join(problems[:6]),
    )


def _ir_confidence_basis(ir: IrDocument, lex: ForceLexicon) -> CheckResult:
    dimensions = tuple(lex.basis_dimensions)
    problems: list[str] = []
    seen = 0
    for claim in ir.all_claims():
        confidence = claim.assessment_confidence
        if confidence is None:
            continue
        seen += 1
        if confidence.get("level") not in lex.confidence_levels:
            problems.append(
                f"{claim.pointer}: confidence level {confidence.get('level')!r} is not one of "
                f"{', '.join(lex.confidence_levels)}"
            )
        basis = confidence.get("basis", {})
        for dimension in dimensions:
            value = basis.get(dimension)
            allowed = lex.basis_dimensions[dimension]
            if value is None:
                problems.append(f"{claim.pointer}: basis dimension {dimension!r} is absent")
            elif value not in allowed:
                problems.append(
                    f"{claim.pointer}: basis {dimension}={value!r} is not one of "
                    f"{', '.join(allowed)}"
                )
    if seen == 0:
        return CheckResult(
            "IR-CONFIDENCE-BASIS",
            "Confidence-basis structure matches the lexicon dimensions",
            Status.NOT_APPLICABLE,
            "no claim declares an assessment confidence",
            "ATS-1 8.8, 8.9",
        )
    return _check(
        "IR-CONFIDENCE-BASIS",
        "Confidence-basis structure matches the lexicon dimensions",
        "ATS-1 8.8, 8.9",
        ok=not problems,
        ok_detail=f"{seen} confidence label(s) carry all {len(dimensions)} basis dimensions",
        fail_detail="; ".join(problems[:6]),
    )


#: Update-indicator effects the semantic model recognises (Section 7.14).
INDICATOR_EFFECTS = (
    "increase_likelihood",
    "decrease_likelihood",
    "increase_confidence",
    "decrease_confidence",
    "reverse",
    "withdraw",
    "supersede",
)


def _ir_update_indicators(ir: IrDocument) -> CheckResult:
    problems: list[str] = []
    for indicator in sorted(ir.indicators.values(), key=lambda i: i.indicator_id):
        if not indicator.target_claim_refs:
            problems.append(f"{indicator.pointer}: indicator targets no claim")
        if not indicator.text.strip():
            problems.append(f"{indicator.pointer}: indicator text is blank")
        effect = indicator.effect
        if effect is not None and effect not in INDICATOR_EFFECTS:
            problems.append(
                f"{indicator.pointer}: effect {effect!r} is not one of {', '.join(INDICATOR_EFFECTS)}"
            )
    reversals = [
        r for r in ir.relations.values() if r.type in ("updates", "reverses")
    ]
    for relation in reversals:
        if not relation.basis_refs and not relation.notes:
            problems.append(
                f"{relation.pointer}: a {relation.type!r} relation records neither a basis nor a "
                "note, so what changed is unrecoverable (spec 7.14)"
            )
    if not ir.indicators and not reversals:
        return CheckResult(
            "IR-UPDATE-INDICATORS",
            "Update and reversal indicators are well formed",
            Status.NOT_APPLICABLE,
            "the artifact declares no update indicator and no update or reversal relation",
            "ATS-1 7.14",
        )
    return _check(
        "IR-UPDATE-INDICATORS",
        "Update and reversal indicators are well formed",
        "ATS-1 7.14",
        ok=not problems,
        ok_detail=f"{len(ir.indicators)} indicator(s) and {len(reversals)} update relation(s) are well formed",
        fail_detail="; ".join(problems[:6]),
    )


def _ir_deontic_validity(ir: IrDocument, lex: ForceLexicon) -> CheckResult:
    valid = set(lex.deontic_surfaces)
    problems: list[str] = []
    seen = 0
    for claim in ir.all_claims():
        deontic = claim.deontic
        if deontic is not None:
            seen += 1
            if deontic not in valid:
                problems.append(f"{claim.pointer}: deontic {deontic!r} is outside the lexicon")
        requirement = claim.requirement
        if requirement is not None:
            seen += 1
            rd = requirement.get("deontic")
            if rd not in valid:
                problems.append(
                    f"{claim.pointer}: requirement deontic {rd!r} is outside the lexicon"
                )
            elif deontic is not None and rd != deontic:
                problems.append(
                    f"{claim.pointer}: force.deontic {deontic!r} disagrees with "
                    f"requirement.deontic {rd!r}"
                )
    if seen == 0:
        return CheckResult(
            "IR-DEONTIC-VALIDITY",
            "Deontic force values come from the closed lexicon",
            Status.NOT_APPLICABLE,
            "the artifact declares no deontic force",
            "ATS-1 8.16",
        )
    return _check(
        "IR-DEONTIC-VALIDITY",
        "Deontic force values come from the closed lexicon",
        "ATS-1 8.16",
        ok=not problems,
        ok_detail=f"{seen} deontic declaration(s) are canonical and internally consistent",
        fail_detail="; ".join(problems[:6]),
    )


def _ir_requirement_slots(ir: IrDocument) -> CheckResult:
    from .profile import specify_requirement_slots

    gaps = []
    count = 0
    for claim in ir.all_claims():
        if claim.role != "requirement":
            continue
        count += 1
        gaps.extend(specify_requirement_slots(claim))
    if count == 0:
        return CheckResult(
            "IR-REQUIREMENT-SLOTS",
            "Requirement slots are explicit or referenced",
            Status.NOT_APPLICABLE,
            "the artifact declares no requirement",
            "ATS-1 9.3.2, 9.3.7, 9.3.9",
        )
    return _check(
        "IR-REQUIREMENT-SLOTS",
        "Requirement slots are explicit or referenced",
        "ATS-1 9.3.2, 9.3.7, 9.3.9",
        ok=not gaps,
        ok_detail=f"{count} requirement(s) resolve every applicable slot",
        fail_detail="; ".join(f"{g.pointer}: {g.detail}" for g in gaps[:6]),
    )


def _ir_one_obligation(ir: IrDocument) -> CheckResult:
    from ..rules.deterministic.requirements import COORDINATION_MARKERS

    problems: list[str] = []
    count = 0
    for claim in ir.all_claims():
        requirement = claim.requirement
        if requirement is None:
            continue
        count += 1
        action = f" {requirement.get('action', '')} ".casefold()
        if any(m in action for m in COORDINATION_MARKERS) and not str(
            requirement.get("indivisible_actions_justification", "")
        ).strip():
            problems.append(
                f"{claim.pointer}: action {requirement.get('action')!r} coordinates more than one "
                "behaviour with no indivisibility justification"
            )
    if count == 0:
        return CheckResult(
            "IR-ONE-OBLIGATION",
            "Each requirement object carries one obligation",
            Status.NOT_APPLICABLE,
            "the artifact declares no requirement",
            "ATS-1 9.3.3",
        )
    if problems:
        return CheckResult(
            "IR-ONE-OBLIGATION",
            "Each requirement object carries one obligation",
            Status.FAIL,
            "; ".join(problems[:6]),
            "ATS-1 9.3.3",
        )
    return CheckResult(
        "IR-ONE-OBLIGATION",
        "Each requirement object carries one obligation",
        Status.REVIEW_REQUIRED,
        f"{count} requirement action slot(s) show no coordinating connective. Whether two "
        "obligations are expressed without one is a semantic judgement this check cannot make.",
        "ATS-1 9.3.3",
    )


def _ir_quant_units(ir: IrDocument) -> CheckResult:
    """Material numbers written into prose but never represented as a quantifier.

    ATS-NUM-001 decides the quantifier objects that exist. This check reports
    the representation gap the rule cannot see: a proposition stating a number
    with no quantifier object behind it.
    """
    import re

    number = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?\s*%?")
    unrepresented: list[str] = []
    represented = 0
    for claim in ir.all_claims():
        if not claim.material:
            continue
        hits = number.findall(claim.proposition)
        if not hits:
            continue
        if claim.quantifier is not None:
            represented += 1
            continue
        # A likelihood display legitimately carries the probability numbers.
        display = (claim.likelihood or {}).get("display", "")
        residual = claim.proposition.replace(display, "") if display else claim.proposition
        if not number.findall(residual):
            continue
        unrepresented.append(f"{claim.pointer}: states a number with no quantifier object")
    if not unrepresented and represented == 0:
        return CheckResult(
            "IR-QUANT-UNITS",
            "Material numbers are represented as quantifier objects",
            Status.NOT_APPLICABLE,
            "no material claim states a number outside a likelihood display",
            "ATS-1 7.7, 10.9",
        )
    if unrepresented:
        return CheckResult(
            "IR-QUANT-UNITS",
            "Material numbers are represented as quantifier objects",
            Status.REVIEW_REQUIRED,
            "; ".join(unrepresented[:6])
            + ". A number in prose without a quantifier object cannot be checked for units by "
            "ATS-NUM-001, so its dimension is unverified rather than absent.",
            "ATS-1 7.7, 10.9",
        )
    return CheckResult(
        "IR-QUANT-UNITS",
        "Material numbers are represented as quantifier objects",
        Status.PASS,
        f"{represented} material claim(s) stating a number carry a quantifier object",
        "ATS-1 7.7, 10.9",
    )


def _ir_polarity_quantifier(ir: IrDocument) -> CheckResult:
    """Section 7.5 fields whose absence changes how a claim reads."""
    problems: list[str] = []
    for claim in ir.all_claims():
        if not claim.material:
            continue
        if claim.polarity not in ("positive", "negative"):
            problems.append(f"{claim.pointer}: polarity {claim.polarity!r} is not recognised")
        if claim.role in ("judgment", "forecast", "requirement"):
            scope = claim.scope
            if not scope:
                problems.append(
                    f"{claim.pointer}: a material {claim.role} declares no scope, which reads as "
                    "universal scope (spec 7.6)"
                )
            elif not any(
                scope.get(f) for f in ("population", "system", "environment", "condition")
            ) and not scope.get("unknown_fields"):
                problems.append(
                    f"{claim.pointer}: scope names no population, system, environment, or "
                    "condition and declares no unknown fields (spec 7.6)"
                )
        if claim.role == "sourced_report" and not claim.refs("source_refs"):
            problems.append(
                f"{claim.pointer}: a sourced report cites no source, so attribution is lost "
                "(spec 7.4, 11.3.1)"
            )
        if claim.deontic == "REQUIRED_BY" and not claim.force.get("external_authority"):
            problems.append(f"{claim.pointer}: REQUIRED_BY with no external authority (spec 9.3.15)")
    return _check(
        "IR-POLARITY-QUANTIFIER",
        "Polarity, scope, attribution, and authority fields are represented",
        "ATS-1 7.5, 7.6, 7.8, 9.3.15",
        ok=not problems,
        ok_detail="every material claim declares polarity, scope, attribution, and authority",
        fail_detail="; ".join(problems[:6]),
    )


def _ir_p0_p1_declarations(ir: IrDocument, ctx: Context) -> CheckResult:
    """P0 and P1 exposure the artifact declares, and whether it hangs together.

    Spec Section 7.15: authors and authoritative upstream systems MAY mark
    claims and relations as material, and materiality is what makes a field P0
    or a relation P1 (Sections 11.3.1 and 11.3.2). ``materiality_rationale`` is
    optional in the schema, so its absence is not a defect and is not reported
    as one.

    What is checked is coherence: a relation declared material whose endpoints
    are both immaterial would protect a relation between unprotected objects,
    which no transformation consumer could act on.
    """
    material_claims = list(ir.material_claims())
    material_relations = [r for r in ir.relations.values() if r.material]
    problems: list[str] = []
    for relation in sorted(material_relations, key=lambda r: r.relation_id):
        endpoints = []
        for oid in (relation.source_id, relation.target_id):
            obj = ir.claims.get(oid)
            if obj is not None:
                endpoints.append(obj.material)
            elif oid in ir.evidence:
                endpoints.append(True)  # evidence is protected by attribution
        if endpoints and not any(endpoints):
            problems.append(
                f"{relation.pointer}: relation {relation.relation_id!r} is material but neither "
                f"{relation.source_id!r} nor {relation.target_id!r} is, so a P1 relation would "
                "protect a link between unprotected objects"
            )
    detail = (
        f"P0 exposure: {len(material_claims)} material claim(s); "
        f"P1 exposure: {len(material_relations)} material relation(s); "
        f"{sum(1 for c in material_claims if c.data.get('materiality_rationale'))} carry an "
        "optional materiality rationale"
    )
    return _check(
        "IR-P0-P1-DECLARATIONS",
        "Protected-impact exposure is declared coherently",
        "ATS-1 7.15, 11.3.1, 11.3.2",
        ok=not problems,
        ok_detail=detail,
        fail_detail="; ".join(problems[:6]),
    )


def _ir_extraction_status(ir: IrDocument) -> CheckResult:
    status = ir.extraction_status
    issues = list(ir.extraction_issues)
    ambiguous = [c for c in ir.all_claims() if c.status == "ambiguous"]
    problems: list[str] = []

    if status == "complete" and issues:
        problems.append(
            f"extraction_status is 'complete' but {len(issues)} extraction issue(s) are recorded"
        )
    if status in ("partial", "ambiguous", "unavailable") and not issues:
        problems.append(
            f"extraction_status is {status!r} but no extraction issue records what is missing "
            "or unresolved (spec 7.16)"
        )
    if ambiguous and status == "complete":
        problems.append(
            f"{len(ambiguous)} claim(s) have status 'ambiguous' while extraction_status is "
            "'complete'"
        )
    for claim in ambiguous:
        readings = list(claim.interpretations)
        if len(set(readings)) != len(readings):
            problems.append(
                f"{claim.pointer}: candidate interpretations repeat, so they are not materially "
                "distinct (spec 7.5, 13.4)"
            )
    for issue in issues:
        if issue.get("status") == "ambiguous" and not issue.get("candidate_interpretations"):
            problems.append(
                f"extraction issue {issue.get('issue_id')!r} is ambiguous but enumerates no "
                "candidate interpretations (spec 13.4)"
            )
    return _check(
        "IR-EXTRACTION-STATUS",
        "Extraction status, issues, and ambiguous claims agree",
        "ATS-1 7.5, 7.16, 13.4",
        ok=not problems,
        ok_detail=f"extraction_status {status!r} is coherent with {len(issues)} recorded issue(s)",
        fail_detail="; ".join(problems[:6]),
    )


def _ir_policy_exceptions(policy: PolicySnapshot, now: _dt.datetime) -> CheckResult:
    diagnostics = policy.exception_diagnostics(now)
    if not diagnostics:
        return CheckResult(
            "IR-POLICY-EXCEPTIONS",
            "Policy exceptions are valid, scoped, and unexpired",
            Status.NOT_APPLICABLE,
            "the policy snapshot declares no exception",
            "ATS-1 6.3, 6.4",
        )
    bad = [d for d in diagnostics if d.status != "active"]
    return _check(
        "IR-POLICY-EXCEPTIONS",
        "Policy exceptions are valid, scoped, and unexpired",
        "ATS-1 6.3, 6.4",
        ok=not bad,
        ok_detail=f"{len(diagnostics)} exception(s) are in force with an exact scope",
        fail_detail="; ".join(f"{d.exception_id}: {d.status} — {d.detail}" for d in bad[:6]),
    )


def _ir_capability(
    capability: CapabilityDeclaration, policy: PolicySnapshot, ir: IrDocument
) -> CheckResult:
    """Spec 5.5: unsupported rules MUST be reported as UNAVAILABLE when required."""
    undecidable = sorted(
        rid for rid, cap in capability.rules.items() if cap.decision_power == "undecidable"
    )
    partial = sorted(
        rid for rid, cap in capability.rules.items() if cap.decision_power == "detects_violations"
    )
    detail = (
        f"{len(undecidable)} rule(s) undecidable on the TextIR surface "
        f"({', '.join(undecidable)}); {len(partial)} rule(s) recognise only a subset of "
        f"violations ({', '.join(partial)}). Both are reported per rule rather than absorbed."
    )
    return CheckResult(
        "IR-CAPABILITY",
        "Unsupported and partially supported capabilities are declared",
        Status.PASS,
        detail,
        "ATS-1 5.5, 14.12, 16.1",
    )


def _ir_canonical(ir: IrDocument) -> CheckResult:
    """JCS round-trip stability and content-address reproducibility."""
    import json

    first = canonical_bytes(ir.raw)
    reparsed = json.loads(first.decode("utf-8"))
    second = canonical_bytes(reparsed)
    digest = sha256_hex(first)
    problems: list[str] = []
    if first != second:
        problems.append("canonical serialization is not stable across a parse round trip")
    if digest != ir.ir_sha256:
        problems.append(
            f"the indexed view reports {ir.ir_sha256} but the canonical bytes hash to {digest}"
        )
    return _check(
        "IR-CANONICAL",
        "Canonical serialization is stable and reproduces the content address",
        "ATS-1 Appendix C, 16.2",
        ok=not problems,
        ok_detail=f"{len(first)} canonical byte(s) hash to {digest}",
        fail_detail="; ".join(problems),
    )


def _ir_basis_schema(ir: IrDocument) -> CheckResult:
    """Draft.2 D-F: the basis policy's presence obligation (spec 7.5, 4.25).

    The schema enforces that a declared ``semantic_basis`` uses one of the five
    defined values; this check enforces the policy-level obligation: when
    ``basis_policy.declared`` is true, every material claim, and every
    requirement object on a material claim, must carry ``semantic_basis``.
    ``declared: false`` is an explicit policy choice and passes with a note;
    an absent policy makes the check NOT_APPLICABLE. Not required: it does not
    gate the mechanical dimension (the spec makes basis declaration a SHOULD;
    the policy obligation is what this check enforces).
    """
    policy = ir.basis_policy
    if policy is None:
        return CheckResult(
            "IR-BASIS-SCHEMA",
            "Material semantic values declare a source basis under the basis policy",
            Status.NOT_APPLICABLE,
            "the document declares no basis_policy, so no basis-declaration obligation is "
            "in force (draft.2 D-F, spec 7.5)",
            "ATS-1 4.25, 7.5",
            required=False,
        )
    if not policy.get("declared"):
        return CheckResult(
            "IR-BASIS-SCHEMA",
            "Material semantic values declare a source basis under the basis policy",
            Status.PASS,
            f"basis_policy.declared is false (default_basis {policy.get('default_basis')!r}), "
            "so basis declaration is explicitly optional and none is enforced",
            "ATS-1 4.25, 7.5",
            required=False,
        )
    problems: list[str] = []
    for claim in ir.material_claims():
        if claim.data.get("semantic_basis") is None:
            problems.append(
                f"{claim.pointer}: material {claim.role} claim {claim.claim_id!r} carries no "
                "semantic_basis although basis_policy.declared is true (spec 7.5)"
            )
        requirement = claim.requirement
        if requirement is not None and requirement.get("semantic_basis") is None:
            problems.append(
                f"{claim.pointer}: requirement {requirement.get('requirement_id')!r} on a "
                "material claim carries no semantic_basis although basis_policy.declared is "
                "true (spec 7.5)"
            )
    return _check(
        "IR-BASIS-SCHEMA",
        "Material semantic values declare a source basis under the basis policy",
        "ATS-1 4.25, 7.5",
        ok=not problems,
        ok_detail=(
            f"basis_policy.declared is true and every material claim and requirement carries "
            "a semantic_basis"
        ),
        fail_detail="; ".join(problems[:6]),
        required=False,
    )

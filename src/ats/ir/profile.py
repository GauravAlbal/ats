"""Profile completeness.

Spec Section 12.8: the profile validators operate *in addition* to the thirty
text rules. An artifact can pass every local rule and still fail profile
completeness because a required section-level semantic slot is absent. These
checks therefore carry their own identifiers and never borrow a rule's result.

Section 9.2.13 and Section 9.3.20 give the PASS conditions. Section 9.2.13 also
fixes the failure semantics: an unresolved missing material slot produces
``profile: FAIL``, while a detector incapable of evaluating a required slot
produces ``profile: UNAVAILABLE``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from ..rules.results import CheckResult, Status
from .model import ClaimView, IrDocument, SectionView

#: Roles that carry a material assessment obligation under ASSESS (Section 9.2.4).
ASSESSMENT_ROLES = ("judgment", "forecast")

#: Availability states that count as an exact typed answer rather than silence
#: (Section 9.1 obligation 9 and Section 9.2.13 second bullet).
TYPED_ABSENCE = ("not_found", "not_searched", "unavailable", "not_applicable", "withheld")


@dataclass(frozen=True, slots=True)
class SlotGap:
    section_id: str
    claim_id: str | None
    slot: str
    pointer: str
    detail: str


def _has(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


# -- ASSESS -----------------------------------------------------------------


def assess_document_slots(ir: IrDocument, section: SectionView) -> list[SlotGap]:
    """Section 9.2.2 document-level slots, evaluated per ASSESS section."""
    gaps: list[SlotGap] = []
    roles = {claim.role for claim in section.claims if claim.material}

    required_roles = {
        "open_question": "the analytic question or decision context",
        "judgment": "one or more key judgments",
        "assumption": "material assumptions",
        "boundary": "material boundaries",
    }
    # A forecast is a judgment subprofile (Section 9.2.11), so it satisfies the
    # key-judgment slot.
    if "forecast" in roles:
        roles.add("judgment")
    for role, description in required_roles.items():
        if role not in roles:
            gaps.append(
                SlotGap(
                    section.section_id,
                    None,
                    role,
                    section.pointer + "/claims",
                    f"no material claim with role {role!r} supplies {description} (spec 9.2.2)",
                )
            )

    if not section.evidence:
        gaps.append(
            SlotGap(
                section.section_id,
                None,
                "evidence_base",
                section.pointer + "/evidence",
                "the evidence base is absent and no availability state stands in its place "
                "(spec 9.2.2, 9.2.6)",
            )
        )

    if not section.update_indicators:
        gaps.append(
            SlotGap(
                section.section_id,
                None,
                "update_indicators",
                section.pointer + "/update_indicators",
                "no update indicator exists for any material judgment (spec 9.2.2)",
            )
        )

    judgments = [c for c in section.claims if c.material and c.role in ASSESSMENT_ROLES]
    recommendations = [c for c in section.claims if c.material and c.role == "recommendation"]
    if judgments and not recommendations:
        # Section 9.2.2 requires a separation between judgments and
        # recommendations. With no recommendation present the separation holds
        # vacuously; this is not a gap.
        pass
    return gaps


def assess_assessment_object(claim: ClaimView, ir: IrDocument) -> list[SlotGap]:
    """Section 9.2.4 slots for one material judgment or forecast."""
    gaps: list[SlotGap] = []

    def gap(slot: str, pointer: str, detail: str) -> None:
        gaps.append(SlotGap(claim.section_id, claim.claim_id, slot, pointer, detail))

    if not _has(claim.proposition):
        gap("proposition", claim.field_pointer("proposition"), "the proposition is empty")
    if not _has(claim.scope):
        gap(
            "scope",
            claim.field_pointer("scope"),
            "no scope is declared, so the claim reads as universally applicable (spec 7.6)",
        )
    likelihood = claim.likelihood
    if likelihood is None:
        # Section 9.2.4: a non-probabilistic judgment MAY omit a WEP but MUST
        # state the basis that makes likelihood inapplicable.
        confidence = claim.assessment_confidence or {}
        rationale = confidence.get("basis", {}).get("rationale", "")
        if not _has(rationale):
            gap(
                "likelihood",
                claim.field_pointer("force"),
                "no likelihood is declared and no confidence-basis rationale states why "
                "likelihood is inapplicable (spec 9.2.4)",
            )
    if claim.assessment_confidence is None:
        gap(
            "assessment_confidence",
            claim.field_pointer("force"),
            "no assessment confidence is declared (spec 9.2.4)",
        )
    else:
        basis = claim.assessment_confidence.get("basis")
        if not _has(basis):
            gap(
                "confidence_basis",
                claim.field_pointer("force", "assessment_confidence"),
                "the confidence label carries no basis object (spec 8.9)",
            )
    supporting = [
        r for r in ir.relations_targeting(claim.claim_id) if r.source_id in ir.evidence
    ]
    if not supporting:
        gap(
            "supporting_evidence",
            claim.field_pointer("source_refs"),
            "no evidence object is related to this claim (spec 9.2.4, 9.2.6)",
        )
    if not claim.refs("assumption_refs"):
        gap(
            "assumptions",
            claim.field_pointer("assumption_refs"),
            "no assumption is attached; a material assumption that bridges an evidence gap "
            "MUST be explicit (spec 9.2.9)",
        )
    if not claim.refs("boundary_refs"):
        gap(
            "boundaries",
            claim.field_pointer("boundary_refs"),
            "no boundary is attached, so nothing limits the claim's generality (spec 9.2.4)",
        )
    if not ir.indicators_targeting(claim.claim_id):
        gap(
            "update_indicators",
            claim.pointer,
            "no update indicator targets this claim (spec 9.2.4)",
        )
    return gaps


# -- SPECIFY ----------------------------------------------------------------

#: Section 9.3.2 slots that every material requirement MUST carry.
SPECIFY_MANDATORY_SLOTS = ("actor", "deontic", "action", "object", "source_authority")


def specify_requirement_slots(claim: ClaimView) -> list[SlotGap]:
    """Section 9.3.2 and 9.3.20 slots for one material requirement."""
    gaps: list[SlotGap] = []
    requirement = claim.requirement
    ptr = claim.field_pointer("requirement")
    if requirement is None:
        return [
            SlotGap(
                claim.section_id,
                claim.claim_id,
                "requirement",
                ptr,
                "a claim with role 'requirement' carries no requirement object (spec 9.3.2)",
            )
        ]

    def gap(slot: str, detail: str) -> None:
        gaps.append(SlotGap(claim.section_id, claim.claim_id, slot, f"{ptr}/{slot}", detail))

    for slot in SPECIFY_MANDATORY_SLOTS:
        if not _has(requirement.get(slot)):
            gap(slot, f"the {slot} slot is absent or blank (spec 9.3.2)")

    if not _has(requirement.get("requirement_id")):
        gap("requirement_id", "the requirement has no stable identifier (spec 9.3.20)")

    if requirement.get("deontic") in ("MUST", "MUST_NOT") and not _has(
        requirement.get("acceptance_criterion")
    ):
        gap(
            "acceptance_criterion",
            "a MUST or MUST NOT requirement has no verifiable acceptance criterion; "
            "Section 9.3.10 forbids reporting profile: PASS in this case",
        )

    if _has(requirement.get("rationale")) and not _has(requirement.get("action")):
        gap("action", "a rationale is present but the normative action slot is empty (spec 9.3.16)")
    return gaps


def specify_set_level(ir: IrDocument) -> list[SlotGap]:
    """Section 9.3.18: requirement identifiers unique within an authority domain."""
    gaps: list[SlotGap] = []
    seen: dict[tuple[str, str], list[str]] = {}
    for claim in ir.all_claims():
        requirement = claim.requirement
        if requirement is None:
            continue
        key = (requirement.get("source_authority", ""), requirement.get("requirement_id", ""))
        seen.setdefault(key, []).append(claim.claim_id)
    for (authority, rid), claim_ids in sorted(seen.items()):
        if len(claim_ids) > 1:
            gaps.append(
                SlotGap(
                    "",
                    claim_ids[0],
                    "requirement_id",
                    "/sections",
                    f"requirement identifier {rid!r} is reused within authority domain "
                    f"{authority!r} by claims {', '.join(claim_ids)}; identifiers MUST be unique "
                    "and MUST NOT be reused for a materially different obligation (spec 9.3.18)",
                )
            )
    return gaps


# -- assembly ---------------------------------------------------------------

#: Profiles this implementation evaluates for completeness. A section carrying
#: any other profile yields UNAVAILABLE rather than being coerced (spec 9.5).
EVALUABLE_PROFILES = ("ASSESS", "SPECIFY")


def evaluate_profiles(ir: IrDocument) -> tuple[CheckResult, list[SlotGap]]:
    """Run profile completeness across every section, returning IR-PROFILE-SLOTS."""
    gaps: list[SlotGap] = []
    unevaluable: list[str] = []
    evaluated = 0

    for section in ir.sections:
        for profile in section.profiles:
            if profile not in EVALUABLE_PROFILES:
                unevaluable.append(f"{section.section_id}:{profile}")
                continue
            evaluated += 1
            if profile == "ASSESS":
                gaps.extend(assess_document_slots(ir, section))
                for claim in section.claims:
                    if claim.material and claim.role in ASSESSMENT_ROLES:
                        gaps.extend(assess_assessment_object(claim, ir))
            else:
                for claim in section.claims:
                    if claim.material and claim.role == "requirement":
                        gaps.extend(specify_requirement_slots(claim))
    gaps.extend(specify_set_level(ir))

    if evaluated == 0:
        status = Status.UNAVAILABLE
        detail = (
            "no section resolves to a profile this implementation evaluates; profiles "
            f"{', '.join(sorted(set(unevaluable))) or 'none'} are preserved but unsupported "
            "(spec 9.5)"
        )
    elif gaps:
        status = Status.FAIL
        detail = (
            f"{len(gaps)} unresolved material slot(s): "
            + "; ".join(
                f"{g.section_id or '<artifact>'}"
                f"{'/' + g.claim_id if g.claim_id else ''}.{g.slot}"
                for g in gaps[:8]
            )
            + (" …" if len(gaps) > 8 else "")
        )
    elif unevaluable:
        status = Status.UNAVAILABLE
        detail = (
            "every evaluated section is complete, but "
            f"{', '.join(sorted(set(unevaluable)))} could not be evaluated, so profile "
            "completeness for the artifact as a whole is unavailable (spec 9.2.13)"
        )
    else:
        status = Status.PASS
        detail = f"every material slot required by {evaluated} profiled section(s) is resolved"

    return (
        CheckResult(
            check_id="IR-PROFILE-SLOTS",
            title="Profile-required semantic slots are resolved",
            status=status,
            detail=detail,
            spec_ref="ATS-1 9.1, 9.2.2, 9.2.4, 9.2.13, 9.3.2, 9.3.20, 12.8",
        ),
        gaps,
    )

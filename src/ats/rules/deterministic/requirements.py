"""Requirements rules: ATS-REQ-001, ATS-REQ-002, ATS-REQ-003."""

from __future__ import annotations

from typing import Any

from ...ir.model import IrEvaluation
from ...rules.results import DecisionPower, Detector, Finding
from ._support import (
    IR_REQUIREMENT_SLOT_SUBSTITUTION,
    Collector,
    DetectorSpec,
    SubcheckSpec,
    detector,
)

#: Actor forms ATS-1 Section 9.3.4 itself names nonconforming. "It MUST be
#: rejected before acceptance." is the spec's own nonconforming example, and
#: Section 21.4 names "the system" as failing ATS-REQ-001. Nothing here is
#: invented: each entry is quoted from a nonconforming example in the spec.
CONCEALING_ACTORS = (
    "it",
    "this",
    "that",
    "they",
    "the system",
    "system",
)

#: Phrases Section 9.3.9 names as not being acceptance criteria.
VACUOUS_ACCEPTANCE = ("works correctly", "is robust")

#: The literal marker Section 9.3.2 requires for an applicable-but-unknown slot.
UNKNOWN_MARKER = "unknown"

#: Coordination markers used by Section 9.3.3's own nonconforming example,
#: "The verifier MUST reject stale receipts and record an audit event."
COORDINATION_MARKERS = (" and then ", " and ")


REQ001 = SubcheckSpec(
    subcheck_id="actor-concealed",
    decides=True,
    spec_ref="ATS-1 9.3.4",
    vocabulary_source="the concealing actor forms quoted from ATS-1 9.3.4 and 21.4",
    description=(
        "A requirement's actor slot holds a pronoun or an unresolved generic that conceals which "
        "component is responsible."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-REQ-001",
        detector_class="D1",
        power=DecisionPower.DECIDES,
        subchecks=(REQ001,),
        unavailable_conditions=(
            "An artifact with no requirement objects presents no actor slot to check.",
        ),
        known_limits=(
            "The schema already requires a non-empty actor, so what remains is a concealing "
            "actor. Section 9.3.4 permits an actor inherited from a mechanically unambiguous "
            "requirement block; the TextIR has no block-inheritance construct, so every "
            "requirement must name its own actor here.",
        ),
    )
)
def req_001(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Every material requirement MUST identify the responsible actor explicitly."""
    c = Collector(ev, det, "ATS-REQ-001")
    for claim in ev.ir.all_claims():
        requirement = claim.requirement
        if requirement is None:
            continue
        c.saw(REQ001.subcheck_id)
        actor = str(requirement.get("actor", "")).strip().casefold()
        normalised = actor.removeprefix("the ").strip()
        if actor in CONCEALING_ACTORS or normalised in CONCEALING_ACTORS:
            c.flag(
                REQ001.subcheck_id,
                issue_code="actor-concealed",
                summary=(
                    f"Requirement {requirement['requirement_id']} names its actor as "
                    f"{requirement['actor']!r}, which does not identify the responsible "
                    "component. Responsibility and authority cannot be verified when the actor is "
                    "hidden behind a pronoun or a generic."
                ),
                spans=[
                    {
                        "kind": "json_pointer",
                        "locator": claim.field_pointer("requirement", "actor"),
                    }
                ],
            )
    return c.result((REQ001,))


# -- ATS-REQ-002 ------------------------------------------------------------

REQ002 = SubcheckSpec(
    subcheck_id="coordinated-actions-without-indivisibility",
    decides=False,
    spec_ref="ATS-1 9.3.3",
    vocabulary_source="the coordination marker in the nonconforming example at ATS-1 9.3.3",
    description=(
        "A requirement's action slot coordinates two behaviours and declares no indivisibility "
        "justification."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-REQ-002",
        detector_class="D1",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(REQ002,),
        substitutions=(IR_REQUIREMENT_SLOT_SUBSTITUTION,),
        unavailable_conditions=(
            "An artifact with no requirement objects presents no obligation to count.",
        ),
        known_limits=(
            "Coordination is recognised only in the action slot and only through the connective "
            "the spec's own nonconforming example uses. Two obligations expressed without a "
            "connective are not detected, so a clean run is REVIEW_REQUIRED.",
            "A coordinated action that is genuinely one indivisible behaviour is a hard negative; "
            "declaring `indivisible_actions_justification` suppresses the finding, which is the "
            "path Section 9.3.3 provides.",
        ),
    )
)
def req_002(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Every material requirement MUST contain one obligation."""
    c = Collector(ev, det, "ATS-REQ-002")
    for claim in ev.ir.all_claims():
        requirement = claim.requirement
        if requirement is None:
            continue
        c.saw(REQ002.subcheck_id)
        action = f" {requirement.get('action', '')} ".casefold()
        if not any(marker in action for marker in COORDINATION_MARKERS):
            continue
        if str(requirement.get("indivisible_actions_justification", "")).strip():
            continue
        c.flag(
            REQ002.subcheck_id,
            issue_code="coordinated-actions-without-indivisibility",
            summary=(
                f"Requirement {requirement['requirement_id']} states the action "
                f"{requirement['action']!r}, which coordinates more than one behaviour, and "
                "declares no indivisibility justification. Independently satisfying one action "
                "would not satisfy the other, so the obligations must be decomposed or their "
                "indivisibility documented."
            ),
            spans=[
                {"kind": "json_pointer", "locator": claim.field_pointer("requirement", "action")}
            ],
        )
    return c.result((REQ002,))


# -- ATS-REQ-003 ------------------------------------------------------------

REQ003_ACCEPTANCE = SubcheckSpec(
    subcheck_id="must-without-acceptance-criterion",
    decides=True,
    spec_ref="ATS-1 9.3.9, 9.3.10",
    vocabulary_source="requirement slots defined in ats_common_v1#/$defs/requirement_slots",
    description=(
        "A MUST or MUST NOT requirement carries no acceptance criterion, or carries one of the "
        "forms Section 9.3.9 names as not being an acceptance criterion."
    ),
)
REQ003_UNKNOWN = SubcheckSpec(
    subcheck_id="applicable-slot-marked-unknown",
    decides=True,
    spec_ref="ATS-1 9.3.2",
    vocabulary_source="the literal marker Section 9.3.2 requires for an unknown slot",
    description=(
        "A requirement slot is marked unknown. Section 9.3.2 requires the marking and makes it "
        "prevent profile conformance."
    ),
)
REQ003_AUTHORITY = SubcheckSpec(
    subcheck_id="requirement-without-source-authority",
    decides=True,
    spec_ref="ATS-1 9.3.15",
    vocabulary_source="requirement slots defined in ats_common_v1#/$defs/requirement_slots",
    description="A requirement's source authority is blank, so the obligation's origin is unstated.",
)

SLOT_NAMES = (
    "actor",
    "action",
    "object",
    "scope",
    "trigger",
    "condition",
    "timing",
    "acceptance_criterion",
    "source_authority",
)


@detector(
    DetectorSpec(
        rule_id="ATS-REQ-003",
        detector_class="D1",
        power=DecisionPower.DECIDES,
        subchecks=(REQ003_ACCEPTANCE, REQ003_UNKNOWN, REQ003_AUTHORITY),
        unavailable_conditions=(
            "An artifact with no requirement objects presents no slots to resolve.",
        ),
        known_limits=(
            "Section 9.3.2 permits omitting a slot that is not applicable, so an absent optional "
            "slot is not a violation. What is decided here is that an applicable slot marked "
            "unknown is reported, that MUST and MUST NOT carry a non-vacuous acceptance "
            "criterion, and that source authority is stated.",
            "Whether a present acceptance criterion is genuinely verifiable is a semantic "
            "judgement left to review; only the forms Section 9.3.9 explicitly rejects are "
            "detected mechanically.",
        ),
    )
)
def req_003(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Every applicable requirement slot MUST be explicit or referenced."""
    c = Collector(ev, det, "ATS-REQ-003")
    for claim in ev.ir.all_claims():
        requirement = claim.requirement
        if requirement is None:
            continue
        rid = requirement["requirement_id"]
        ptr = claim.field_pointer("requirement")

        c.saw(REQ003_UNKNOWN.subcheck_id)
        for slot in SLOT_NAMES:
            value = requirement.get(slot)
            if isinstance(value, str) and value.strip().casefold() == UNKNOWN_MARKER:
                c.flag(
                    REQ003_UNKNOWN.subcheck_id,
                    issue_code="applicable-slot-marked-unknown",
                    summary=(
                        f"Requirement {rid} marks its {slot!r} slot unknown. Section 9.3.2 "
                        "requires the marking and makes an unknown applicable slot prevent "
                        "profile conformance until it is resolved."
                    ),
                    spans=[{"kind": "json_pointer", "locator": f"{ptr}/{slot}"}],
                )

        c.saw(REQ003_AUTHORITY.subcheck_id)
        if not str(requirement.get("source_authority", "")).strip():
            c.flag(
                REQ003_AUTHORITY.subcheck_id,
                issue_code="requirement-without-source-authority",
                summary=(
                    f"Requirement {rid} states no source authority, so a reader cannot tell "
                    "which authority created or imposed the obligation."
                ),
                spans=[{"kind": "json_pointer", "locator": f"{ptr}/source_authority"}],
            )

        if requirement.get("deontic") not in ("MUST", "MUST_NOT"):
            continue
        c.saw(REQ003_ACCEPTANCE.subcheck_id)
        criterion = str(requirement.get("acceptance_criterion", "")).strip()
        if not criterion:
            c.flag(
                REQ003_ACCEPTANCE.subcheck_id,
                issue_code="must-without-acceptance-criterion",
                summary=(
                    f"Requirement {rid} states {requirement['deontic']} but carries no acceptance "
                    "criterion. Section 9.3.9 requires one, and Section 9.3.10 forbids reporting "
                    "profile conformance without it."
                ),
                spans=[{"kind": "json_pointer", "locator": f"{ptr}/acceptance_criterion"}],
            )
            continue
        folded = criterion.casefold()
        vacuous = [p for p in VACUOUS_ACCEPTANCE if p in folded]
        if vacuous and len(folded) <= len(vacuous[0]) + 8:
            c.flag(
                REQ003_ACCEPTANCE.subcheck_id,
                issue_code="vacuous-acceptance-criterion",
                summary=(
                    f"Requirement {rid} offers {criterion!r} as its acceptance criterion. Section "
                    "9.3.9 names this form as not being an acceptance criterion because it "
                    "identifies no observable evidence."
                ),
                spans=[{"kind": "json_pointer", "locator": f"{ptr}/acceptance_criterion"}],
            )
    return c.result((REQ003_ACCEPTANCE, REQ003_UNKNOWN, REQ003_AUTHORITY))

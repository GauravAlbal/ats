"""Local semantic closure rule: ATS-CLOSE-001.

Spec Section 4.24 (draft.2 amendment D-D) defines local semantic closure: a
unit is locally closed when its operative meaning can be recovered from the
unit plus explicitly declared dependencies, without undeclared document-wide
inference. Section 7.18 carries the extractable-unit fields.

The presence mechanics are decided exactly: a requirement slot in a SPECIFY
section must carry an actor (or a declared inheritance marker), a deontic, an
action, and an object, and every acceptance-criterion and dependency reference
must resolve. Whether the recovered meaning is genuinely sufficient for action
is a semantic judgement, so a clean run is REVIEW_REQUIRED, never PASS
(detects_violations power; known_limits records the boundary).
"""

from __future__ import annotations

from typing import Any, Mapping

from ...ir.model import IrEvaluation
from ...rules.results import DecisionPower, Detector, Finding
from ._support import Collector, DetectorSpec, SubcheckSpec, detector

CLOSE_ACTOR = SubcheckSpec(
    subcheck_id="requirement-slot-missing-actor",
    decides=True,
    spec_ref="ATS-1 4.24, 7.18",
    vocabulary_source="none",
    description=(
        "A requirement slot declares no actor and no inherited-scope marker, so the "
        "unit's operative meaning depends on undeclared document-wide inference."
    ),
)
CLOSE_DEONTIC = SubcheckSpec(
    subcheck_id="requirement-slot-missing-deontic",
    decides=True,
    spec_ref="ATS-1 4.24, 7.18",
    vocabulary_source="none",
    description="A requirement slot declares no deontic modality.",
)
CLOSE_ACTION = SubcheckSpec(
    subcheck_id="requirement-slot-missing-action",
    decides=True,
    spec_ref="ATS-1 4.24, 7.18",
    vocabulary_source="none",
    description="A requirement slot declares no action.",
)
CLOSE_OBJECT = SubcheckSpec(
    subcheck_id="requirement-slot-missing-object",
    decides=True,
    spec_ref="ATS-1 4.24, 7.18",
    vocabulary_source="none",
    description="A requirement slot declares no object.",
)
CLOSE_ACCEPTANCE = SubcheckSpec(
    subcheck_id="acceptance-criterion-ref-unresolved",
    decides=True,
    spec_ref="ATS-1 4.24, 7.18",
    vocabulary_source="none",
    description=(
        "A requirement's acceptance_criterion_id resolves to no declared acceptance "
        "criterion."
    ),
)
CLOSE_DEPENDENCY = SubcheckSpec(
    subcheck_id="dependency-target-unresolved",
    decides=True,
    spec_ref="ATS-1 4.24, 7.18",
    vocabulary_source="none",
    description=(
        "A relation's dependency_target resolves to no declared object, so the unit's "
        "declared dependencies are incomplete."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-CLOSE-001",
        detector_class="D1",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(
            CLOSE_ACTOR,
            CLOSE_DEONTIC,
            CLOSE_ACTION,
            CLOSE_OBJECT,
            CLOSE_ACCEPTANCE,
            CLOSE_DEPENDENCY,
        ),
        unavailable_conditions=(
            "A document with no extractable normative unit declares no unit whose local "
            "closure can be checked.",
        ),
        known_limits=(
            "Presence mechanics only: actor, deontic, action, and object presence plus "
            "acceptance-criterion and dependency reference resolution are decided "
            "mechanically. Whether the recovered meaning is genuinely sufficient for "
            "action is a semantic judgement, so a clean run is REVIEW_REQUIRED, not PASS.",
            "The schema requires the requirement slot fields, so a blank after stripping "
            "is the mechanically expressible form of a missing slot value; the deontic "
            "subcheck is defensive for documents whose slot is absent. An actor declared "
            "by an enclosing scope (spec 4.24) or an inherited-actor marker satisfies the "
            "actor slot.",
        ),
    )
)
def close_001(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """An extractable normative unit MUST be locally closed."""
    c = Collector(ev, det, "ATS-CLOSE-001")
    declared = {entry["id"] for entry in ev.ir.stable_coordinates}
    claim_ids = set(ev.ir.claims)
    resolvable = declared | claim_ids

    for section in ev.ir.sections:
        if "SPECIFY" not in section.profiles:
            continue
        section_actor = _enclosing_scope_actor(section.data)
        for claim in section.claims:
            requirement = claim.requirement
            if requirement is None:
                continue
            rid = requirement["requirement_id"]
            req_ptr = claim.field_pointer("requirement")

            # -- slot presence ----------------------------------------------
            c.saw(CLOSE_ACTOR.subcheck_id)
            actor = str(requirement.get("actor", "")).strip()
            claim_extensions = claim.data.get("extensions")
            inherited = (
                claim_extensions.get("inherited_actor")
                if isinstance(claim_extensions, Mapping)
                else None
            )
            if not actor and not inherited and not section_actor:
                c.flag(
                    CLOSE_ACTOR.subcheck_id,
                    issue_code="requirement-slot-missing-actor",
                    summary=(
                        f"Requirement {rid} declares no actor and no inherited-scope "
                        "marker, so its operative meaning depends on undeclared "
                        "document-wide inference. The unit is not locally closed."
                    ),
                    spans=[{"kind": "json_pointer", "locator": f"{req_ptr}/actor"}],
                )

            c.saw(CLOSE_DEONTIC.subcheck_id)
            if not requirement.get("deontic"):
                c.flag(
                    CLOSE_DEONTIC.subcheck_id,
                    issue_code="requirement-slot-missing-deontic",
                    summary=(
                        f"Requirement {rid} declares no deontic modality, so a reader "
                        "cannot recover whether the obligation is a MUST, SHOULD, or MAY."
                    ),
                    spans=[{"kind": "json_pointer", "locator": f"{req_ptr}/deontic"}],
                )

            c.saw(CLOSE_ACTION.subcheck_id)
            if not str(requirement.get("action", "")).strip():
                c.flag(
                    CLOSE_ACTION.subcheck_id,
                    issue_code="requirement-slot-missing-action",
                    summary=(
                        f"Requirement {rid} declares no action, so the behaviour it "
                        "obliges cannot be recovered from the unit."
                    ),
                    spans=[{"kind": "json_pointer", "locator": f"{req_ptr}/action"}],
                )

            c.saw(CLOSE_OBJECT.subcheck_id)
            if not str(requirement.get("object", "")).strip():
                c.flag(
                    CLOSE_OBJECT.subcheck_id,
                    issue_code="requirement-slot-missing-object",
                    summary=(
                        f"Requirement {rid} declares no object, so the thing the action "
                        "applies to cannot be recovered from the unit."
                    ),
                    spans=[{"kind": "json_pointer", "locator": f"{req_ptr}/object"}],
                )

            # -- reference resolution ----------------------------------------
            ac_id = requirement.get("acceptance_criterion_id")
            if ac_id:
                c.saw(CLOSE_ACCEPTANCE.subcheck_id)
                if ac_id not in resolvable:
                    c.flag(
                        CLOSE_ACCEPTANCE.subcheck_id,
                        issue_code="acceptance-criterion-ref-unresolved",
                        summary=(
                            f"Requirement {rid} references acceptance criterion {ac_id!r}, "
                            "which resolves to no declared acceptance criterion, so the "
                            "unit's acceptance precondition is undeclared."
                        ),
                        spans=[
                            {
                                "kind": "json_pointer",
                                "locator": f"{req_ptr}/acceptance_criterion_id",
                            }
                        ],
                    )

    for relation in ev.ir.relations.values():
        dep = relation.data.get("dependency_target")
        if not dep:
            continue
        c.saw(CLOSE_DEPENDENCY.subcheck_id)
        if dep in resolvable:
            continue
        c.flag(
            CLOSE_DEPENDENCY.subcheck_id,
            issue_code="dependency-target-unresolved",
            summary=(
                f"Relation {relation.relation_id} declares dependency_target {dep!r}, "
                "which resolves to no declared object, so the unit's declared "
                "dependencies are incomplete."
            ),
            spans=[
                {
                    "kind": "json_pointer",
                    "locator": relation.pointer + "/dependency_target",
                }
            ],
        )

    return c.result(
        (CLOSE_ACTOR, CLOSE_DEONTIC, CLOSE_ACTION, CLOSE_OBJECT, CLOSE_ACCEPTANCE, CLOSE_DEPENDENCY)
    )


def _enclosing_scope_actor(section: Mapping[str, Any]) -> str | None:
    """The actor a section's declared enclosing scope supplies (spec 4.24)."""
    extensions = section.get("extensions")
    if not isinstance(extensions, Mapping):
        return None
    scope = extensions.get("enclosing_scope")
    if not isinstance(scope, Mapping):
        return None
    if scope.get("declared") is not True:
        return None
    actor = str(scope.get("actor", "")).strip()
    return actor or None

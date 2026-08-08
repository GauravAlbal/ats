"""Deontics rules: ATS-DEON-001, ATS-DEON-002, ATS-DEON-003.

The deontic vocabulary, its surface forms, the noncanonical set, and the
collision rules all come from ``lexicons/ats_force_lexicon_v1.yaml``.
"""

from __future__ import annotations

from typing import Any

from ...ir.model import IrEvaluation
from ...rules.results import DecisionPower, Detector, Finding
from ._support import (
    Collector,
    DetectorSpec,
    SubcheckSpec,
    contains_exact,
    detector,
)

LEXICON_SOURCE = "lexicons/ats_force_lexicon_v1.yaml"

# -- ATS-DEON-001 -----------------------------------------------------------

DEON001_MISSING = SubcheckSpec(
    subcheck_id="requirement-without-deontic-force",
    decides=True,
    spec_ref="ATS-1 8.16, 9.3.2",
    vocabulary_source=f"{LEXICON_SOURCE} deontic_force.terms",
    description="A claim with role `requirement` declares no deontic force field.",
)
DEON001_SURFACE = SubcheckSpec(
    subcheck_id="deontic-surface-absent-from-proposition",
    decides=True,
    spec_ref="ATS-1 8.16, 1.3",
    vocabulary_source=f"{LEXICON_SOURCE} deontic_force.terms[].surface",
    description=(
        "A requirement declares a deontic force whose uppercase surface form does not appear in "
        "its proposition, so the obligation strength is not carried by the normative text."
    ),
)
DEON001_NONCANONICAL = SubcheckSpec(
    subcheck_id="noncanonical-modal-in-material-claim",
    decides=True,
    spec_ref="ATS-1 8.16",
    vocabulary_source=f"{LEXICON_SOURCE} deontic_force.noncanonical",
    description=(
        "A material claim uses a modal the lexicon marks noncanonical (SHALL, SHALL NOT), which "
        "carries hidden normative meaning."
    ),
)
DEON001_AUTHORITY = SubcheckSpec(
    subcheck_id="required-by-without-authority",
    decides=True,
    spec_ref="ATS-1 9.3.15",
    vocabulary_source=f"{LEXICON_SOURCE} deontic_force.terms",
    description=(
        "A claim whose deontic force is REQUIRED_BY names no external authority, so an obligation "
        "imposed elsewhere reads as if it originated locally."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-DEON-001",
        detector_class="D0",
        power=DecisionPower.DECIDES,
        subchecks=(DEON001_MISSING, DEON001_SURFACE, DEON001_NONCANONICAL, DEON001_AUTHORITY),
        unavailable_conditions=(
            "An artifact with no requirement claims and no material propositions presents no "
            "normative statement to check.",
        ),
        known_limits=(
            "Section 1.3 makes the deontic keywords normative only in uppercase, so a lowercase "
            "'must' in ordinary prose is correctly not flagged here. Whether a lowercase modal is "
            "smuggling normative force is a semantic question ATS-DEON-003 addresses for `should`.",
        ),
    )
)
def deon_001(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Normative statements MUST use ATS-1 deontic terms with their defined force."""
    c = Collector(ev, det, "ATS-DEON-001")
    surfaces = ev.ctx.lexicon.deontic_surfaces
    noncanonical = ev.ctx.lexicon.deontic_noncanonical

    for claim in ev.ir.all_claims():
        if claim.material:
            c.saw(DEON001_NONCANONICAL.subcheck_id)
            for modal in noncanonical:
                if contains_exact(claim.proposition, modal):
                    c.flag(
                        DEON001_NONCANONICAL.subcheck_id,
                        issue_code="noncanonical-modal",
                        summary=(
                            f"Claim {claim.claim_id} uses {modal!r}, which the ATS-1 lexicon marks "
                            "noncanonical. Requirements become unverifiable when obligation "
                            "strength is encoded through a modal outside the closed vocabulary."
                        ),
                        spans=[claim.span()],
                    )

        deontic = claim.deontic
        if deontic == "REQUIRED_BY":
            c.saw(DEON001_AUTHORITY.subcheck_id)
            if not str(claim.force.get("external_authority", "")).strip():
                c.flag(
                    DEON001_AUTHORITY.subcheck_id,
                    issue_code="required-by-without-authority",
                    summary=(
                        f"Claim {claim.claim_id} declares REQUIRED_BY force but names no external "
                        "authority, so an externally imposed obligation reads as locally created."
                    ),
                    spans=[{"kind": "json_pointer", "locator": claim.field_pointer("force")}],
                )

        if claim.role != "requirement":
            continue
        c.saw(DEON001_MISSING.subcheck_id)
        if deontic is None:
            c.flag(
                DEON001_MISSING.subcheck_id,
                issue_code="requirement-without-deontic-force",
                summary=(
                    f"Claim {claim.claim_id} has role `requirement` but declares no "
                    "`force.deontic`, so its obligation strength is unrepresented."
                ),
                spans=[{"kind": "json_pointer", "locator": claim.field_pointer("force")}],
            )
            continue
        c.saw(DEON001_SURFACE.subcheck_id)
        surface = surfaces.get(deontic, deontic)
        if deontic == "REQUIRED_BY":
            continue
        if not contains_exact(claim.proposition, surface):
            c.flag(
                DEON001_SURFACE.subcheck_id,
                issue_code="deontic-surface-absent",
                summary=(
                    f"Requirement {claim.claim_id} declares deontic force {deontic!r} but the "
                    f"uppercase surface {surface!r} does not appear in its proposition. Section "
                    "1.3 makes the keyword normative only in uppercase, so the represented force "
                    "and the stated text disagree."
                ),
                spans=[claim.span()],
            )
    return c.result(
        (DEON001_MISSING, DEON001_SURFACE, DEON001_NONCANONICAL, DEON001_AUTHORITY)
    )


# -- ATS-DEON-002 -----------------------------------------------------------

DEON002_LIKELIHOOD = SubcheckSpec(
    subcheck_id="may-carrying-probability",
    decides=False,
    spec_ref="ATS-1 8.17 force-collision-may",
    vocabulary_source=f"{LEXICON_SOURCE} collision_rules",
    description="A claim with MAY force also carries a likelihood, collapsing permission into probability.",
)
DEON002_ROLE = SubcheckSpec(
    subcheck_id="may-on-non-normative-role",
    decides=False,
    spec_ref="ATS-1 8.17, 9.3.12, 9.3.13",
    vocabulary_source=f"{LEXICON_SOURCE} collision_rules",
    description=(
        "A claim with MAY force has a role that is not a requirement, so the statement grants no "
        "identifiable permission to an identifiable actor."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-DEON-002",
        detector_class="D0",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(DEON002_LIKELIHOOD, DEON002_ROLE),
        unavailable_conditions=("An artifact with no MAY force presents no permission to check.",),
        known_limits=(
            "The collision between permission, capability, and probability is visible here only "
            "when the IR represents both forces. A prose `may` that never became a typed force is "
            "invisible to this surface, so a clean run is REVIEW_REQUIRED.",
        ),
    )
)
def deon_002(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """MAY MUST express permission, not probability or capability."""
    c = Collector(ev, det, "ATS-DEON-002")
    for claim in ev.ir.all_claims():
        if claim.deontic != "MAY":
            continue
        c.saw(DEON002_LIKELIHOOD.subcheck_id)
        c.saw(DEON002_ROLE.subcheck_id)
        if claim.likelihood is not None and claim.likelihood.get("kind") != "not_applicable":
            c.flag(
                DEON002_LIKELIHOOD.subcheck_id,
                issue_code="may-carrying-probability",
                summary=(
                    f"Claim {claim.claim_id} declares MAY permission and also a likelihood. "
                    "Permission and probability lead to different system behaviour and authority, "
                    "so one statement cannot carry both."
                ),
                spans=[{"kind": "json_pointer", "locator": claim.field_pointer("force")}],
                interpretations=[
                    {
                        "interpretation_id": f"{claim.claim_id}-permission",
                        "reading": "The actor is permitted to perform the action.",
                        "material_difference": "An implementer may implement the action.",
                    },
                    {
                        "interpretation_id": f"{claim.claim_id}-probability",
                        "reading": "The action might occur with the stated probability.",
                        "material_difference": "No permission is granted; a forecast is made.",
                    },
                ],
            )
        if claim.role not in ("requirement", "exception"):
            c.flag(
                DEON002_ROLE.subcheck_id,
                issue_code="may-on-non-normative-role",
                summary=(
                    f"Claim {claim.claim_id} carries MAY permission on role {claim.role!r}. "
                    "Section 9.3.12 requires a MAY statement to identify the permitted actor, "
                    "action, and boundary, which only a requirement object represents."
                ),
                spans=[{"kind": "json_pointer", "locator": claim.field_pointer("force")}],
            )
    return c.result((DEON002_LIKELIHOOD, DEON002_ROLE))


# -- ATS-DEON-003 -----------------------------------------------------------

DEON003 = SubcheckSpec(
    subcheck_id="should-without-override-path",
    decides=True,
    spec_ref="ATS-1 9.3.11",
    vocabulary_source=f"{LEXICON_SOURCE} deontic_force.terms",
    description=(
        "A SHOULD or SHOULD NOT requirement identifies neither an exception nor a rationale "
        "linking to an override policy."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-DEON-003",
        detector_class="D0",
        power=DecisionPower.DECIDES,
        subchecks=(DEON003,),
        unavailable_conditions=(
            "An artifact with no SHOULD or SHOULD NOT requirement presents no defeasible "
            "recommendation to check.",
        ),
        known_limits=(
            "Section 9.3.11 also forbids using SHOULD merely because the author is uncertain "
            "whether the requirement matters. That is a semantic judgement about intent and is "
            "not decided here; this subcheck decides only the override-path obligation.",
        ),
    )
)
def deon_003(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """SHOULD MUST express defeasible recommendation with a stated override path."""
    c = Collector(ev, det, "ATS-DEON-003")
    for claim in ev.ir.all_claims():
        requirement = claim.requirement
        if requirement is None:
            continue
        # The subcheck inspects every requirement: a non-SHOULD requirement is
        # an inspected, passed comparison, not an uninspected one (ADR-0002).
        c.saw(DEON003.subcheck_id)
        if requirement.get("deontic") not in ("SHOULD", "SHOULD_NOT"):
            continue
        has_exception = bool([e for e in requirement.get("exceptions", ()) if str(e).strip()])
        has_rationale = bool(str(requirement.get("rationale", "")).strip())
        if has_exception or has_rationale:
            continue
        c.flag(
            DEON003.subcheck_id,
            issue_code="should-without-override-path",
            summary=(
                f"Requirement {requirement['requirement_id']} states "
                f"{requirement['deontic']} but lists no exception and gives no rationale. A "
                "defeasible recommendation MUST identify why exceptions may be valid or link to "
                "an override policy, otherwise an implementer cannot record a justified "
                "deviation."
            ),
            spans=[{"kind": "json_pointer", "locator": claim.field_pointer("requirement")}],
        )
    return c.result((DEON003,))

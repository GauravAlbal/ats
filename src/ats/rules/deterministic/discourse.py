"""Discourse rules: ATS-DISC-001, ATS-DISC-002, ATS-DISC-003.

All three are SHOULD rules and therefore advisory by default in every stable
profile. Two of the three depend on document structure the TextIR does not
represent, and say so rather than inventing a proxy.
"""

from __future__ import annotations

from typing import Any

from ...ir.model import IrEvaluation
from ...rules.results import DecisionPower, Detector, Finding
from ._support import (
    IR_SECTION_ORDER_SUBSTITUTION,
    Collector,
    DetectorSpec,
    SubcheckSpec,
    detector,
    undecidable,
)

#: Roles Section 10.16 calls load-bearing: the key answer, judgment,
#: requirement, or change.
LOAD_BEARING_ROLES = ("judgment", "requirement", "forecast")

#: Roles that can legitimately precede a load-bearing statement because they
#: frame it rather than delay it (Section 9.2.3 permits a short framing
#: statement; Section 7.4 defines the roles).
FRAMING_ROLES = ("definition", "open_question", "boundary")

DISC001 = SubcheckSpec(
    subcheck_id="load-bearing-statement-not-first",
    decides=False,
    spec_ref="ATS-1 10.16, 9.2.3",
    vocabulary_source="claim roles enumerated in ATS-1 7.4",
    description=(
        "A section's first material claim is neither load-bearing nor a permitted framing role, "
        "so background precedes the operative statement."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-DISC-001",
        detector_class="D1",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(DISC001,),
        substitutions=(IR_SECTION_ORDER_SUBSTITUTION,),
        unavailable_conditions=(
            "A section with no load-bearing material claim has no operative statement to place.",
        ),
        known_limits=(
            "Section 10.16 qualifies the obligation with 'background that does not alter its "
            "interpretation'. Whether the preceding material actually alters interpretation is a "
            "semantic judgement, so a clean ordering is REVIEW_REQUIRED, not PASS.",
            "Claim order in the IR is the authored order. It is not evidence about where a "
            "renderer will place the statement; the output linter checks the rendered order.",
        ),
    )
)
def disc_001(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """The load-bearing judgment, requirement, or answer SHOULD precede background."""
    c = Collector(ev, det, "ATS-DISC-001")
    for section in ev.ir.sections:
        material = section.material_claims()
        if not material:
            continue
        load_bearing = [claim for claim in material if claim.role in LOAD_BEARING_ROLES]
        if not load_bearing:
            continue
        c.saw(DISC001.subcheck_id)
        first = material[0]
        if first.role in LOAD_BEARING_ROLES or first.role in FRAMING_ROLES:
            continue
        target = load_bearing[0]
        c.flag(
            DISC001.subcheck_id,
            issue_code="load-bearing-statement-not-first",
            summary=(
                f"Section {section.section_id!r} opens with material claim {first.claim_id} of "
                f"role {first.role!r}, while its load-bearing {target.role} {target.claim_id} "
                f"appears at position {material.index(target) + 1}. A reader traverses setup "
                "before reaching the operative claim."
            ),
            spans=[first.span()],
            evidence_spans=[target.span()],
        )
    return c.result((DISC001,))


undecidable(
    DetectorSpec(
        rule_id="ATS-DISC-002",
        detector_class="none",
        power=DecisionPower.UNDECIDABLE,
        subchecks=(
            SubcheckSpec(
                subcheck_id="one-conceptual-move-per-paragraph",
                decides=False,
                spec_ref="ATS-1 10.15",
                description=(
                    "Counting the conceptual moves in a paragraph requires the paragraph, which "
                    "the TextIR does not represent."
                ),
            ),
        ),
        unavailable_conditions=(
            "The TextIR models sections and claims, not paragraphs. Section 10.15's unit of "
            "analysis does not exist on this surface, and a claim is not a paragraph.",
        ),
        known_limits=(
            "Section 10.15 explicitly prefers conceptual moves over sentence or topic counts, so "
            "substituting a claim count would be the arbitrary proxy the rule exists to reject.",
        ),
    )
)

undecidable(
    DetectorSpec(
        rule_id="ATS-DISC-003",
        detector_class="none",
        power=DecisionPower.UNDECIDABLE,
        subchecks=(
            SubcheckSpec(
                subcheck_id="restatement-adds-function",
                decides=False,
                spec_ref="ATS-1 10.19",
                description=(
                    "Deciding whether a restatement adds scope, evidence, mechanism, implication, "
                    "contrast, action, or retrieval value requires the surrounding document "
                    "context."
                ),
            ),
        ),
        unavailable_conditions=(
            "`document_context` is not supplied to `ats ir lint`, and two claims with similar "
            "propositions may be a legitimate functional repetition rather than a restatement.",
        ),
        known_limits=(
            "String similarity between propositions would flag exactly the functional repetition "
            "Section 10.19 permits, so no proxy is implemented.",
        ),
    )
)

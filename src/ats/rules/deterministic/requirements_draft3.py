"""Draft.3 requirement rule: ATS-REQ-004 behavioral acceptance criteria.

The deterministic surface intentionally decides only objective pathologies. It
never certifies that an acceptance criterion is fully load-bearing or perfectly
scope-equivalent to its requirement; a clean run therefore remains
REVIEW_REQUIRED and semantic review stays external.
"""
from __future__ import annotations

import re
from typing import Any

from ...ir.model import IrEvaluation
from ...rules.results import DecisionPower, Detector, Finding
from ._support import Collector, DetectorSpec, SubcheckSpec, detector

# Deliberately narrow: only criteria whose whole proposition is a named test,
# command, or bare pass/result assertion are classified as evidence substituted
# for behavior. Embedded evidence references inside a behavioral AC are allowed.
TEST_SHAPED_AC = re.compile(
    r"^\s*(?:(?:test|spec)[A-Za-z0-9_.:/-]+|"
    r"(?:pytest|go\s+test|cargo\s+test|npm\s+test|make\s+test)(?:\s+[^.;]+)?)"
    r"\s+(?:passes?|succeeds?|is\s+green)(?:\.|$)",
    re.IGNORECASE,
)

# Uppercase ATS deontics inside the AC are independently normative. A canonical
# AC may describe required behavior, but it must not create an obligation of its
# own; hidden normative content belongs in the REQ.
HIDDEN_DEONTIC = re.compile(r"\bMUST(?:\s+NOT)?\b")

REQ004_TEST_SHAPED = SubcheckSpec(
    subcheck_id="evidence-substituted-for-behavior",
    decides=False,
    spec_ref="ATS-1 9.3.9 (D-G)",
    vocabulary_source="the evidence-instrument examples named by ATS-1 9.3.9 (D-G)",
    description=(
        "A canonical acceptance criterion consists only of a test/command result rather than "
        "an observable behavioral proposition."
    ),
)

REQ004_HIDDEN_OBLIGATION = SubcheckSpec(
    subcheck_id="acceptance-criterion-hidden-obligation",
    decides=False,
    spec_ref="ATS-1 9.3.9 (D-G scope-fidelity rule)",
    vocabulary_source="the ATS-1 uppercase deontic vocabulary",
    description=(
        "An acceptance criterion contains an uppercase ATS deontic, indicating normative "
        "behavior that belongs in the requirement rather than being introduced by the AC."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-REQ-004",
        detector_class="D1",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(REQ004_TEST_SHAPED, REQ004_HIDDEN_OBLIGATION),
        unavailable_conditions=(
            "An artifact with no MUST/MUST NOT requirement acceptance criteria presents nothing to inspect.",
        ),
        known_limits=(
            "A clean deterministic run does not establish that an AC is load-bearing; constructing a materially broken implementation that still satisfies the AC is a semantic review task.",
            "The detector does not infer scope equivalence or hidden obligations expressed without an uppercase ATS deontic.",
            "Evidence references embedded inside an otherwise behavioral acceptance criterion are not treated as evidence substitution.",
        ),
    )
)
def req_004(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Surface objective ATS-REQ-004 violations without claiming semantic sufficiency."""
    c = Collector(ev, det, "ATS-REQ-004")
    for claim in ev.ir.all_claims():
        requirement = claim.requirement
        if requirement is None or requirement.get("deontic") not in ("MUST", "MUST_NOT"):
            continue
        criterion = str(requirement.get("acceptance_criterion", "")).strip()
        if not criterion:
            # ATS-REQ-003 owns absence; avoid duplicate findings here.
            continue
        ptr = claim.field_pointer("requirement", "acceptance_criterion")
        rid = requirement["requirement_id"]

        c.saw(REQ004_TEST_SHAPED.subcheck_id)
        if TEST_SHAPED_AC.match(criterion):
            c.flag(
                REQ004_TEST_SHAPED.subcheck_id,
                issue_code="evidence-substituted-for-behavior",
                summary=(
                    f"Requirement {rid} uses {criterion!r} as its acceptance criterion. "
                    "That is an evidence/test result, not the behavioral proposition the "
                    "requirement asks a verifier to adjudicate."
                ),
                spans=[{"kind": "json_pointer", "locator": ptr}],
            )

        c.saw(REQ004_HIDDEN_OBLIGATION.subcheck_id)
        if HIDDEN_DEONTIC.search(criterion):
            c.flag(
                REQ004_HIDDEN_OBLIGATION.subcheck_id,
                issue_code="acceptance-criterion-hidden-obligation",
                summary=(
                    f"Requirement {rid}'s acceptance criterion contains an uppercase ATS "
                    "deontic. An AC must not introduce or strengthen a normative obligation; "
                    "move that behavior into the requirement or decompose the requirement."
                ),
                spans=[{"kind": "json_pointer", "locator": ptr}],
            )

    return c.result((REQ004_TEST_SHAPED, REQ004_HIDDEN_OBLIGATION))

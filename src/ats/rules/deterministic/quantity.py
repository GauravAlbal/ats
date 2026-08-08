"""Quantity rules: ATS-NUM-001, ATS-NUM-002."""

from __future__ import annotations

from typing import Any

from ...ir.model import IrEvaluation
from ...rules.results import DecisionPower, Detector, Finding
from ._support import Collector, DetectorSpec, SubcheckSpec, contains_phrase, detector

#: Quantifier kinds that carry a magnitude and therefore need a dimension
#: (spec Section 7.7 lists the kinds; Section 10.9 imposes the obligation).
MAGNITUDE_KINDS = ("exact_count", "minimum", "maximum", "range", "proportion")

NUM001_UNIT = SubcheckSpec(
    subcheck_id="magnitude-without-unit",
    decides=True,
    spec_ref="ATS-1 10.9",
    vocabulary_source="quantifier kinds enumerated in ATS-1 7.7",
    description=(
        "A material claim carrying a magnitude quantifier declares neither a unit nor an "
        "explicit dimensionless status."
    ),
)
NUM001_DENOM = SubcheckSpec(
    subcheck_id="proportion-without-denominator",
    decides=True,
    spec_ref="ATS-1 10.9",
    vocabulary_source="quantifier kinds enumerated in ATS-1 7.7",
    description="A material proportion declares no denominator, so its count basis is unknown.",
)


def _declares_dimensionless(claim) -> bool:
    """The artifact says the quantity is dimensionless, rather than omitting the unit.

    Spec Section 7.6: an unknown scope field MUST be represented as unknown; it
    MUST NOT be omitted in a way that implies something it does not say. The
    two honest forms are a declared ``unit`` of ``dimensionless`` or a
    ``scope.unknown_fields`` entry naming the unit.
    """
    quantifier = claim.quantifier or {}
    if quantifier.get("unit", "").strip().casefold() == "dimensionless":
        return True
    unknown = claim.scope.get("unknown_fields", ())
    return any(field in ("unit", "quantifier.unit", "dimension") for field in unknown)


@detector(
    DetectorSpec(
        rule_id="ATS-NUM-001",
        detector_class="D0",
        power=DecisionPower.DECIDES,
        subchecks=(NUM001_UNIT, NUM001_DENOM),
        unavailable_conditions=(
            "None on this surface: every quantifier the IR carries is inspectable, and a claim "
            "with no quantifier object states no material number to check.",
        ),
        known_limits=(
            "A material number written into a proposition string but never represented as a "
            "quantifier object is invisible here. Structural check IR-QUANT-UNITS reports that "
            "representation gap separately so it is not silently absorbed into this PASS.",
        ),
    )
)
def num_001(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """A material number MUST include its unit, dimension, denominator, or dimensionless status."""
    c = Collector(ev, det, "ATS-NUM-001")
    for claim in ev.ir.material_claims():
        quantifier = claim.quantifier
        if not quantifier or quantifier.get("kind") not in MAGNITUDE_KINDS:
            continue
        kind = quantifier["kind"]
        c.saw(NUM001_UNIT.subcheck_id)
        if not quantifier.get("unit") and not _declares_dimensionless(claim):
            c.flag(
                NUM001_UNIT.subcheck_id,
                issue_code="magnitude-without-unit",
                summary=(
                    f"Claim {claim.claim_id} carries a {kind!r} quantifier with no unit and no "
                    "declared dimensionless status, so the number cannot be interpreted or "
                    "verified. Declare `quantifier.unit`, or record the unit as unknown in "
                    "`scope.unknown_fields`."
                ),
                spans=[{"kind": "json_pointer", "locator": claim.field_pointer("quantifier")}],
            )
        if kind == "proportion":
            c.saw(NUM001_DENOM.subcheck_id)
            if quantifier.get("denominator") in (None, 0):
                c.flag(
                    NUM001_DENOM.subcheck_id,
                    issue_code="proportion-without-denominator",
                    summary=(
                        f"Claim {claim.claim_id} states a proportion whose denominator is absent "
                        "or zero, so the count basis of the proportion is unrecoverable."
                    ),
                    spans=[
                        {
                            "kind": "json_pointer",
                            "locator": claim.field_pointer("quantifier", "denominator"),
                        }
                    ],
                )
    return c.result((NUM001_UNIT, NUM001_DENOM))


# -- ATS-NUM-002 ------------------------------------------------------------

NUM002_ORDER = SubcheckSpec(
    subcheck_id="range-bounds-inverted",
    decides=True,
    spec_ref="ATS-1 10.10",
    vocabulary_source="quantifier kinds enumerated in ATS-1 7.7",
    description="A range quantifier's lower bound exceeds its upper bound.",
)
NUM002_BOUNDARY = SubcheckSpec(
    subcheck_id="threshold-without-boundary-semantics",
    decides=False,
    spec_ref="ATS-1 10.10, 9.3.8",
    vocabulary_source="comparator words enumerated in ATS-1 9.3.8 and 10.10",
    description=(
        "A material threshold on a requirement declares no comparator or inclusivity anywhere in "
        "its constraints, action, or condition slots."
    ),
)

#: Boundary vocabulary enumerated by ATS-1 Sections 9.3.8 and 10.10. Not an
#: invented list: these are the comparator and inclusivity words the spec uses
#: when it states what a threshold must identify.
BOUNDARY_TERMS = (
    "at least",
    "at most",
    "greater than",
    "less than",
    "no more than",
    "no fewer than",
    "inclusive",
    "exclusive",
    "or more",
    "or fewer",
    "up to and including",
)


@detector(
    DetectorSpec(
        rule_id="ATS-NUM-002",
        detector_class="D0",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(NUM002_ORDER, NUM002_BOUNDARY),
        unavailable_conditions=(
            "A claim with no range or threshold quantifier states no boundary to check.",
        ),
        known_limits=(
            "Inverted bounds are decidable; whether ordinary language leaves a boundary ambiguous "
            "is not. A run with no inverted bound and no missing comparator is REVIEW_REQUIRED.",
            "Comparator detection reads the requirement's own slots. A comparator expressed only "
            "in surrounding prose is not visible to the IR surface.",
        ),
    )
)
def num_002(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """A material range or threshold MUST define comparator and boundary semantics."""
    c = Collector(ev, det, "ATS-NUM-002")
    for claim in ev.ir.material_claims():
        quantifier = claim.quantifier
        if not quantifier:
            continue
        kind = quantifier.get("kind")
        if kind == "range":
            c.saw(NUM002_ORDER.subcheck_id)
            lower, upper = quantifier.get("lower"), quantifier.get("upper")
            if lower is not None and upper is not None and lower > upper:
                c.flag(
                    NUM002_ORDER.subcheck_id,
                    issue_code="range-bounds-inverted",
                    summary=(
                        f"Claim {claim.claim_id} declares a range whose lower bound {lower} "
                        f"exceeds its upper bound {upper}; no value satisfies it."
                    ),
                    spans=[{"kind": "json_pointer", "locator": claim.field_pointer("quantifier")}],
                )
        if kind in ("range", "minimum", "maximum"):
            c.saw(NUM002_BOUNDARY.subcheck_id)
            requirement = claim.requirement
            if requirement is None:
                continue
            haystack = " ".join(
                [
                    *requirement.get("constraints", ()),
                    requirement.get("action", ""),
                    requirement.get("condition", "") or "",
                    requirement.get("acceptance_criterion", "") or "",
                ]
            )
            if not any(contains_phrase(haystack, term) for term in BOUNDARY_TERMS):
                c.flag(
                    NUM002_BOUNDARY.subcheck_id,
                    issue_code="threshold-without-boundary-semantics",
                    summary=(
                        f"Requirement {requirement['requirement_id']} states a {kind!r} threshold "
                        "but none of its constraint, action, condition, or acceptance-criterion "
                        "slots identifies a comparator or inclusivity, so the boundary case is "
                        "undetermined."
                    ),
                    spans=[
                        {"kind": "json_pointer", "locator": claim.field_pointer("requirement")}
                    ],
                    interpretations=[
                        {
                            "interpretation_id": f"{claim.claim_id}-inclusive",
                            "reading": "The stated bound is included in the acceptable set.",
                            "material_difference": "A value exactly at the bound is accepted.",
                        },
                        {
                            "interpretation_id": f"{claim.claim_id}-exclusive",
                            "reading": "The stated bound is excluded from the acceptable set.",
                            "material_difference": "A value exactly at the bound is rejected.",
                        },
                    ],
                )
    return c.result((NUM002_ORDER, NUM002_BOUNDARY))

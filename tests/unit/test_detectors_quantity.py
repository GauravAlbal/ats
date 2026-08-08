"""Quantity detectors: ATS-NUM-001 and ATS-NUM-002.

Section 10.9 requires a material number to carry its unit, dimension,
denominator, or an explicit dimensionless status. Section 10.10 and Section
9.3.8 require a range or threshold to define comparator and boundary semantics.
"""

from __future__ import annotations

import pytest

from ats.rules.results import Status

CLEAN_STATUS = {"ATS-NUM-001": Status.PASS, "ATS-NUM-002": Status.REVIEW_REQUIRED}


@pytest.mark.parametrize("rule_id", ["ATS-NUM-001", "ATS-NUM-002"])
@pytest.mark.parametrize(
    ("ir_name", "policy_name"),
    [("assess_conforming", "assess"), ("specify_conforming", "specify")],
)
def test_conforming_artifacts_state_no_unquantified_number(
    evaluate_ir, rule_id, ir_name, policy_name
) -> None:
    """Spec 21.1 and 21.3: neither conforming example carries a bare magnitude."""
    result = evaluate_ir(ir_name, policy_name)[rule_id]
    assert result.findings == ()
    assert result.status is CLEAN_STATUS[rule_id]
    assert result.effective_state == "required"


# -- ATS-NUM-001 ------------------------------------------------------------


def test_num_001_fails_on_a_magnitude_with_no_unit(evaluate_ir, issue_codes) -> None:
    """Spec 10.9: a number with no dimension cannot be interpreted or verified."""
    result = evaluate_ir("quantifier_without_unit", "specify")["ATS-NUM-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["magnitude-without-unit"]
    assert str(result.decision_power) == "decides"
    assert result.detector.authority == "conformance_evidence"


def test_num_001_accepts_a_declared_unit(mutated_ir, evaluate_document) -> None:
    """Spec 10.9 is satisfied by the unit itself."""
    document = mutated_ir("quantifier_without_unit")
    document["sections"][0]["claims"][0]["quantifier"]["unit"] = "milliseconds"
    result = evaluate_document(document, "specify")["ATS-NUM-001"]
    assert result.findings == ()
    assert result.status is Status.PASS


def test_num_001_accepts_an_explicit_dimensionless_status(
    mutated_ir, evaluate_document
) -> None:
    """Spec 10.9 permits declaring the quantity dimensionless rather than omitting a unit."""
    document = mutated_ir("quantifier_without_unit")
    document["sections"][0]["claims"][0]["quantifier"]["unit"] = "dimensionless"
    result = evaluate_document(document, "specify")["ATS-NUM-001"]
    assert result.findings == ()
    assert result.status is Status.PASS


def test_num_001_accepts_a_unit_declared_unknown_in_scope(
    mutated_ir, evaluate_document
) -> None:
    """Spec 7.6: an unknown field is represented as unknown, not omitted."""
    document = mutated_ir("quantifier_without_unit")
    claim = document["sections"][0]["claims"][0]
    claim["scope"]["unknown_fields"] = ["unit"]
    result = evaluate_document(document, "specify")["ATS-NUM-001"]
    assert result.findings == ()
    assert result.status is Status.PASS


def test_num_001_fails_on_a_proportion_with_no_denominator(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 10.9: a proportion without its count basis is unrecoverable."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][0]["quantifier"] = {
        "kind": "proportion",
        "value": 0.3,
        "unit": "dimensionless",
    }
    result = evaluate_document(document, "assess")["ATS-NUM-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["proportion-without-denominator"]


def test_num_001_ignores_a_quantifier_kind_that_carries_no_magnitude(
    mutated_ir, evaluate_document
) -> None:
    """Spec 7.7: only the magnitude kinds carry a dimension obligation."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][0]["quantifier"] = {"kind": "unspecified"}
    result = evaluate_document(document, "assess")["ATS-NUM-001"]
    assert result.findings == ()
    assert result.status is Status.PASS


# -- ATS-NUM-002 ------------------------------------------------------------


def test_num_002_fails_on_a_threshold_with_no_comparator(
    evaluate_ir, issue_codes
) -> None:
    """Spec 10.10 and 9.3.8: a threshold must determine its boundary case."""
    result = evaluate_ir("quantifier_without_unit", "specify")["ATS-NUM-002"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["threshold-without-boundary-semantics"]
    assert str(result.decision_power) == "detects_violations"
    finding = result.findings[0]
    assert [i["interpretation_id"].rsplit("-", 1)[-1] for i in finding.interpretations] == [
        "inclusive",
        "exclusive",
    ]


def test_num_002_is_satisfied_by_a_comparator_in_a_requirement_slot(
    mutated_ir, evaluate_document
) -> None:
    """Spec 9.3.8: the comparator may live in any of the requirement's own slots."""
    document = mutated_ir("quantifier_without_unit")
    requirement = document["sections"][0]["claims"][0]["requirement"]
    requirement["constraints"] = ["at most 500 milliseconds, inclusive"]
    document["sections"][0]["claims"][0]["quantifier"]["unit"] = "milliseconds"
    result = evaluate_document(document, "specify")["ATS-NUM-002"]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED


def test_num_002_fails_on_an_inverted_range(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 10.10: a range whose lower bound exceeds its upper bound admits no value."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][0]["quantifier"] = {
        "kind": "range",
        "lower": 10,
        "upper": 2,
        "unit": "defects",
    }
    result = evaluate_document(document, "assess")["ATS-NUM-002"]
    assert result.status is Status.FAIL
    # The claim carries no requirement object, so only the ordering subcheck
    # applies; the boundary subcheck reads requirement slots that do not exist.
    assert issue_codes(result) == ["range-bounds-inverted"]


def test_num_002_accepts_a_well_ordered_range(mutated_ir, evaluate_document) -> None:
    """Spec 10.10: a correctly ordered range raises nothing."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][0]["quantifier"] = {
        "kind": "range",
        "lower": 2,
        "upper": 10,
        "unit": "defects",
    }
    result = evaluate_document(document, "assess")["ATS-NUM-002"]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED

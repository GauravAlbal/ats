"""Time detectors: ATS-TIME-001 and ATS-TIME-002.

Section 9.2.11 makes a forecast scorable only when it declares a resolvable
outcome and a resolution source; Section 9.2.4 requires a probabilistic
judgment to carry a horizon; Section 10.11 enumerates the relative-time
expressions that must resolve to an absolute anchor.
"""

from __future__ import annotations

import pytest

from ats.rules.deterministic.time_rules import ANCHOR_FIELDS, RELATIVE_TIME_TERMS
from ats.rules.results import Status


def test_relative_time_vocabulary_is_the_list_section_10_11_enumerates() -> None:
    """Spec 10.11 names exactly these expressions; nothing is invented."""
    assert RELATIVE_TIME_TERMS == (
        "today",
        "currently",
        "recently",
        "soon",
        "later",
        "next",
        "the latest",
    )
    assert "time_horizon" in ANCHOR_FIELDS and "version" in ANCHOR_FIELDS


@pytest.mark.parametrize("rule_id", ["ATS-TIME-001", "ATS-TIME-002"])
@pytest.mark.parametrize(
    ("ir_name", "policy_name"),
    [("assess_conforming", "assess"), ("specify_conforming", "specify")],
)
def test_conforming_artifacts_are_temporally_anchored(
    evaluate_ir, rule_id, ir_name, policy_name
) -> None:
    """Spec 21.1 and 21.3: both conforming examples anchor what they assert."""
    result = evaluate_ir(ir_name, policy_name)[rule_id]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED


# -- ATS-TIME-001 -----------------------------------------------------------


def test_time_001_fails_on_a_forecast_with_no_resolution(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 9.2.11: an unresolvable forecast can never be scored."""
    document = mutated_ir("assess_conforming")
    claim = document["sections"][0]["claims"][0]
    claim["role"] = "forecast"
    claim["forecast"] = {"forecast_id": "f1"}

    result = evaluate_document(document, "assess")["ATS-TIME-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["forecast-without-resolution"]
    summary = result.findings[0].summary
    for slot in ("outcome_definition", "resolution", "resolution_source"):
        assert slot in summary


def test_time_001_accepts_a_fully_declared_forecast(
    mutated_ir, evaluate_document
) -> None:
    """Spec 9.2.11: outcome, resolution, and source together make it scorable."""
    document = mutated_ir("assess_conforming")
    claim = document["sections"][0]["claims"][0]
    claim["role"] = "forecast"
    claim["forecast"] = {
        "forecast_id": "f1",
        "outcome_definition": "Invalid-state defects per release fall below the current median.",
        "resolution": "2027-02-01",
        "resolution_source": "Arq acceptance defect ledger",
    }
    result = evaluate_document(document, "assess")["ATS-TIME-001"]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED


def test_time_001_fails_on_a_probabilistic_judgment_with_no_horizon(
    evaluate_ir, issue_codes
) -> None:
    """Spec 9.2.4: a probability without a horizon is not a stable proposition."""
    result = evaluate_ir("unanchored_relative_time", "assess")["ATS-TIME-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["probabilistic-judgment-without-horizon"]
    assert str(result.decision_power) == "detects_violations"


# -- ATS-TIME-002 -----------------------------------------------------------


def test_time_002_fails_on_an_unanchored_relative_expression(
    evaluate_ir, issue_codes
) -> None:
    """Spec 10.11: 'soon' changes meaning as time passes unless it is anchored."""
    result = evaluate_ir("unanchored_relative_time", "assess")["ATS-TIME-002"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["unanchored-relative-time"]
    assert "'soon'" in result.findings[0].summary
    assert str(result.decision_power) == "detects_violations"


@pytest.mark.parametrize("anchor", ["time_horizon", "version", "evidence_window"])
def test_time_002_is_satisfied_by_any_declared_anchor(
    mutated_ir, evaluate_document, anchor
) -> None:
    """Spec 10.11: a date, version, or evidence window resolves the expression."""
    document = mutated_ir("unanchored_relative_time")
    document["sections"][0]["claims"][0]["scope"][anchor] = "2026-Q4"
    result = evaluate_document(document, "assess")["ATS-TIME-002"]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED


def test_time_002_matches_whole_words_only(mutated_ir, evaluate_document) -> None:
    """Spec 10.11 enumerates expressions, not substrings: 'current' is not 'currently'."""
    document = mutated_ir("assess_conforming")
    claim = document["sections"][0]["claims"][1]
    claim["proposition"] = "The current transition model remains the subject of this assessment."
    result = evaluate_document(document, "assess")["ATS-TIME-002"]
    assert result.findings == ()

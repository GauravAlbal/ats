"""Epistemics detectors: ATS-EPI-001 through ATS-EPI-007.

Section 8 defines calibrated force. The conforming ASSESS artifact of Section
21.1 must raise nothing; each violation fixture perturbs one field and must
raise exactly the rule that field belongs to.
"""

from __future__ import annotations

import pytest

from ats.rules.results import Status

EPISTEMIC_RULES = (
    "ATS-EPI-001",
    "ATS-EPI-002",
    "ATS-EPI-003",
    "ATS-EPI-004",
    "ATS-EPI-005",
    "ATS-EPI-006",
    "ATS-EPI-007",
)

#: Status each epistemics rule reports on a conforming ASSESS artifact.
#: PASS where the rule has a complete decision procedure whose class may carry
#: conformance evidence (spec 12.3), REVIEW_REQUIRED otherwise (spec 16.5).
CLEAN_ASSESS_STATUS = {
    "ATS-EPI-001": Status.PASS,
    "ATS-EPI-002": Status.PASS,
    "ATS-EPI-003": Status.PASS,
    "ATS-EPI-004": Status.REVIEW_REQUIRED,
    "ATS-EPI-005": Status.PASS,
    "ATS-EPI-006": Status.REVIEW_REQUIRED,
    "ATS-EPI-007": Status.PASS,
}


@pytest.mark.parametrize("rule_id", EPISTEMIC_RULES)
def test_conforming_assess_raises_no_epistemic_finding(evaluate_ir, rule_id) -> None:
    """Spec 21.1 and 16.4: the spec's own conforming example must raise nothing."""
    result = evaluate_ir("assess_conforming", "assess")[rule_id]
    assert result.findings == ()
    assert result.status is CLEAN_ASSESS_STATUS[rule_id]
    assert result.effective_state == "required"


@pytest.mark.parametrize("rule_id", EPISTEMIC_RULES)
def test_conforming_specify_raises_no_epistemic_finding(evaluate_ir, rule_id) -> None:
    """Spec 21.3: a conforming SPECIFY artifact states no miscalibrated force."""
    result = evaluate_ir("specify_conforming", "specify")[rule_id]
    assert result.findings == ()
    assert result.effective_state == "advisory"


# -- ATS-EPI-001 ------------------------------------------------------------


def test_epi_001_fails_when_the_declared_interval_is_not_the_lexicon_interval(
    ctx, evaluate_ir, issue_codes
) -> None:
    """Spec 8.2: a WEP term's numeric range is fixed by the active lexicon."""
    lower, upper, _ = ctx.lexicon.interval_for("likely")
    assert (lower, upper) == (0.55, 0.8), "the fixture perturbs exactly this bound"

    result = evaluate_ir("wep_interval_mismatch", "assess")["ATS-EPI-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["wep-interval-mismatch"]
    assert str(result.decision_power) == "decides"
    assert result.detector.authority == "conformance_evidence"


def test_epi_001_fails_on_a_term_outside_the_canonical_row(
    ctx, mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 8.2: the likelihood vocabulary is closed."""
    document = mutated_ir("assess_conforming")
    likelihood = document["sections"][0]["claims"][0]["force"]["likelihood"]
    likelihood["term"] = "fairly likely"
    assert "fairly likely" not in ctx.lexicon.wep_terms

    result = evaluate_document(document, "assess")["ATS-EPI-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["wep-term-not-canonical"]


def test_epi_001_fails_on_a_point_probability_with_no_rationale(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 8.5: greater precision than the WEP row requires a stated basis."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][0]["force"]["likelihood"] = {
        "kind": "point",
        "value": 0.62,
        "display": "62%",
    }
    result = evaluate_document(document, "assess")["ATS-EPI-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["point-probability-unjustified"]


# -- ATS-EPI-002 ------------------------------------------------------------


def test_epi_002_fails_when_first_material_use_hides_the_range(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 8.4: the first material use of a WEP term must show its numeric range."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][0]["force"]["likelihood"]["range_shown_inline"] = False

    result = evaluate_document(document, "assess")["ATS-EPI-002"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["first-use-range-not-shown"]


def test_epi_002_fails_when_the_display_omits_the_lexicon_range(
    ctx, mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 8.4: the shown range must be the lexicon's range for that term."""
    document = mutated_ir("assess_conforming")
    likelihood = document["sections"][0]["claims"][0]["force"]["likelihood"]
    likelihood["display"] = "likely (50-90%)"
    assert ctx.lexicon.display_range("likely") == "55–80%"

    result = evaluate_document(document, "assess")["ATS-EPI-002"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["first-use-display-missing-range"]


def test_epi_002_passes_when_no_material_wep_use_exists(evaluate_ir) -> None:
    """Spec 8.4 applies only to a first material use; absence is not a violation."""
    result = evaluate_ir("possibility_term_only", "assess")["ATS-EPI-002"]
    assert result.status is Status.PASS
    assert result.findings == ()


# -- ATS-EPI-003 ------------------------------------------------------------


def test_epi_003_fails_on_a_noncanonical_probability_synonym(
    ctx, evaluate_ir, issue_codes
) -> None:
    """Spec 8.3: output must use the canonical phrase, not an input alias."""
    assert ctx.lexicon.wep_aliases["probable"] == "likely"

    result = evaluate_ir("noncanonical_wep_synonym", "assess")["ATS-EPI-003"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["noncanonical-wep-synonym"]
    assert str(result.decision_power) == "decides"
    assert "probable" in result.findings[0].summary


# -- ATS-EPI-004 ------------------------------------------------------------


def test_epi_004_fails_when_a_confidence_word_is_shown_as_the_probability(
    ctx, mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 8.11: likelihood and assessment confidence are separate axes."""
    assert "high" in ctx.lexicon.confidence_levels
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][0]["force"]["likelihood"]["display"] = (
        "high confidence (55–80%)"
    )

    result = evaluate_document(document, "assess")["ATS-EPI-004"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["confidence-word-inside-likelihood"]
    assert str(result.decision_power) == "detects_violations"


def test_epi_004_fails_when_confidence_substitutes_for_a_missing_likelihood(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 8.11: a confidence label may not stand in for an event probability."""
    document = mutated_ir("assess_conforming")
    claim = document["sections"][0]["claims"][0]
    del claim["force"]["likelihood"]
    claim["proposition"] = "A Rust migration is probable to reduce invalid-state defects."

    result = evaluate_document(document, "assess")["ATS-EPI-004"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["confidence-substituted-for-likelihood"]
    # Section 13.4: the two readings must be enumerated and materially distinct.
    interpretations = result.findings[0].interpretations
    assert len(interpretations) == 2
    assert len({i["reading"] for i in interpretations}) == 2


# -- ATS-EPI-005 ------------------------------------------------------------


def test_epi_005_fails_on_a_blank_confidence_basis_rationale(
    evaluate_ir, issue_codes
) -> None:
    """Spec 8.9: a confidence label carries an inspectable basis and rationale."""
    result = evaluate_ir("blank_confidence_basis", "assess")["ATS-EPI-005"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["confidence-basis-rationale-blank"]
    assert str(result.decision_power) == "decides"


def test_epi_005_fails_when_every_basis_dimension_is_unknown(
    ctx, mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 8.9 and 8.10: a label resting on nothing inspectable is unsupported authority."""
    document = mutated_ir("assess_conforming")
    confidence = document["sections"][0]["claims"][0]["force"]["assessment_confidence"]
    for dimension, allowed in ctx.lexicon.basis_dimensions.items():
        if "unknown" in allowed:
            confidence["basis"][dimension] = "unknown"
    unknown_capable = [
        d for d, allowed in ctx.lexicon.basis_dimensions.items() if "unknown" in allowed
    ]
    for dimension in ctx.lexicon.basis_dimensions:
        if dimension not in unknown_capable:
            confidence["basis"].pop(dimension, None)

    result = evaluate_document(document, "assess")["ATS-EPI-005"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["confidence-basis-wholly-unknown"]


# -- ATS-EPI-006 ------------------------------------------------------------


def test_epi_006_surfaces_a_material_judgment_with_no_update_indicator(
    evaluate_ir, issue_codes
) -> None:
    """Spec 7.14 and 9.2.4: a material assessment must be operationally revisable.

    The registry lists only D3 and D4 for this rule, so Section 12.3 caps its
    output at ``proposal_only``: the finding is surfaced for adjudication and
    the rule reports REVIEW_REQUIRED rather than a decided FAIL.
    """
    result = evaluate_ir("no_update_indicator", "assess")["ATS-EPI-006"]
    assert result.status is Status.REVIEW_REQUIRED
    assert issue_codes(result) == ["no-update-indicator"]
    assert result.detector.detector_class == "D3"
    assert result.detector.authority == "proposal_only"
    assert result.detector.authority_basis_ref is None


def test_epi_006_accepts_an_extraction_issue_naming_the_claim(
    mutated_ir, evaluate_document
) -> None:
    """Spec 7.16: an artifact may state that an indicator is unavailable."""
    document = mutated_ir("no_update_indicator")
    document["extraction_status"] = "partial"
    document["extraction_issues"] = [
        {
            "issue_id": "no-indicator-in-source",
            "status": "partial",
            "description": "The source states no observable that would revise the judgment.",
            "affected_fields": ["sections/0/claims/c1/update_indicators"],
        }
    ]
    result = evaluate_document(document, "assess")["ATS-EPI-006"]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED


# -- ATS-EPI-007 ------------------------------------------------------------


def test_epi_007_fails_when_a_possibility_term_is_the_only_likelihood(
    ctx, evaluate_ir, issue_codes
) -> None:
    """Spec 8.7: 'possible', 'plausible', 'might', 'could' are not probabilities."""
    assert "might" in ctx.lexicon.non_probability_terms

    result = evaluate_ir("possibility_term_only", "assess")["ATS-EPI-007"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["possibility-term-as-only-likelihood"]
    assert str(result.decision_power) == "decides"
    assert "might" in result.findings[0].summary


def test_epi_007_accepts_a_possibility_term_beside_a_calibrated_likelihood(
    mutated_ir, evaluate_document
) -> None:
    """Spec 8.7 fires only when no calibrated likelihood is supplied."""
    document = mutated_ir("assess_conforming")
    claim = document["sections"][0]["claims"][0]
    claim["proposition"] = (
        "A Rust migration is likely (55–80%) to reduce invalid-state defects; it is possible "
        "that iteration speed falls."
    )
    result = evaluate_document(document, "assess")["ATS-EPI-007"]
    assert result.findings == ()
    assert result.status is Status.PASS

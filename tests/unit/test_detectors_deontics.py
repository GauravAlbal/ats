"""Deontics detectors: ATS-DEON-001, ATS-DEON-002, ATS-DEON-003.

Section 8.16 closes the deontic vocabulary, Section 1.3 makes the keywords
normative only in uppercase, Section 8.17 states the MAY collision rule, and
Section 9.3.11 requires a SHOULD to carry an override path.
"""

from __future__ import annotations

import pytest

from ats.rules.results import Status

DEONTIC_RULES = ("ATS-DEON-001", "ATS-DEON-002", "ATS-DEON-003")

CLEAN_STATUS = {
    "ATS-DEON-001": Status.PASS,
    "ATS-DEON-002": Status.REVIEW_REQUIRED,
    "ATS-DEON-003": Status.PASS,
}


@pytest.mark.parametrize("rule_id", DEONTIC_RULES)
@pytest.mark.parametrize(
    ("ir_name", "policy_name", "state"),
    [
        ("assess_conforming", "assess", "advisory"),
        ("specify_conforming", "specify", "required"),
    ],
)
def test_conforming_artifacts_raise_no_deontic_finding(
    evaluate_ir, rule_id, ir_name, policy_name, state
) -> None:
    """Spec 21.1 and 21.3: neither conforming example miscarries obligation strength."""
    result = evaluate_ir(ir_name, policy_name)[rule_id]
    assert result.findings == ()
    assert result.status is CLEAN_STATUS[rule_id]
    assert result.effective_state == state


# -- ATS-DEON-001 -----------------------------------------------------------


def test_deon_001_fails_on_a_noncanonical_modal_and_an_absent_surface(
    ctx, evaluate_ir, issue_codes
) -> None:
    """Spec 8.16 and 1.3: SHALL is outside the vocabulary, and MUST must appear."""
    assert ctx.lexicon.deontic_noncanonical == ("SHALL", "SHALL NOT")
    assert ctx.lexicon.deontic_surfaces["MUST"] == "MUST"

    result = evaluate_ir("noncanonical_modal", "specify")["ATS-DEON-001"]
    assert result.status is Status.FAIL
    # The requirement still declares MUST force while its proposition says
    # SHALL, so the represented force and the normative text disagree.
    assert issue_codes(result) == ["deontic-surface-absent", "noncanonical-modal"]
    assert str(result.decision_power) == "decides"
    assert result.detector.authority == "conformance_evidence"
    assert result.detector.authority_basis_ref == "docs/AUTHORITY_MODEL.md#ats-ir-rule"


def test_deon_001_fails_when_a_requirement_declares_no_deontic_force(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 9.3.2: obligation strength is a represented slot, not an inference."""
    document = mutated_ir("specify_conforming")
    claim = document["sections"][0]["claims"][0]
    claim["force"] = {}

    result = evaluate_document(document, "specify")["ATS-DEON-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["requirement-without-deontic-force"]


def test_deon_001_fails_on_required_by_without_an_external_authority(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 9.3.15: an externally imposed obligation must name its source."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][0]["force"]["deontic"] = "REQUIRED_BY"

    result = evaluate_document(document, "assess")["ATS-DEON-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["required-by-without-authority"]


def test_deon_001_ignores_a_lowercase_modal(mutated_ir, evaluate_document) -> None:
    """Spec 1.3: the keywords are normative only in uppercase."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][1]["proposition"] = (
        "The transition model shall remain stable, though this sentence states no obligation."
    )
    result = evaluate_document(document, "assess")["ATS-DEON-001"]
    assert result.findings == ()
    assert result.status is Status.PASS


# -- ATS-DEON-002 -----------------------------------------------------------


def test_deon_002_fails_when_may_carries_probability_on_a_non_normative_role(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 8.17 and 9.3.12: permission is not probability, and MAY needs an actor."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][0]["force"]["deontic"] = "MAY"

    result = evaluate_document(document, "assess")["ATS-DEON-002"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["may-carrying-probability", "may-on-non-normative-role"]
    assert str(result.decision_power) == "detects_violations"
    # Section 13.4: the collision is reported with both readings enumerated.
    collision = next(f for f in result.findings if f.issue_code == "may-carrying-probability")
    assert len(collision.interpretations) == 2


def test_deon_002_accepts_may_on_a_requirement_without_a_likelihood(
    mutated_ir, evaluate_document
) -> None:
    """Spec 9.3.12: a requirement object identifies actor, action, and boundary."""
    document = mutated_ir("specify_conforming")
    claim = document["sections"][0]["claims"][0]
    claim["force"]["deontic"] = "MAY"
    claim["requirement"]["deontic"] = "MAY"
    claim["proposition"] = claim["proposition"].replace("MUST", "MAY")

    result = evaluate_document(document, "specify")["ATS-DEON-002"]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED


# -- ATS-DEON-003 -----------------------------------------------------------


def test_deon_003_fails_on_a_should_with_no_override_path(evaluate_ir, issue_codes) -> None:
    """Spec 9.3.11: a defeasible recommendation must state how it may be overridden."""
    result = evaluate_ir("should_without_override", "specify")["ATS-DEON-003"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["should-without-override-path"]
    assert str(result.decision_power) == "decides"


def test_deon_003_accepts_a_should_carrying_a_rationale(
    mutated_ir, evaluate_document
) -> None:
    """Spec 9.3.11: either an exception or a rationale supplies the override path."""
    document = mutated_ir("should_without_override")
    requirement = document["sections"][0]["claims"][0]["requirement"]
    requirement["rationale"] = (
        "A verifier operating under an explicitly waived policy generation may accept the "
        "receipt, which is the documented override."
    )
    result = evaluate_document(document, "specify")["ATS-DEON-003"]
    assert result.findings == ()
    assert result.status is Status.PASS


def test_deon_001_still_passes_on_the_should_fixture(evaluate_ir) -> None:
    """The violation twin differs in one rule only: the SHOULD surface is present."""
    result = evaluate_ir("should_without_override", "specify")["ATS-DEON-001"]
    assert result.findings == ()
    assert result.status is Status.PASS

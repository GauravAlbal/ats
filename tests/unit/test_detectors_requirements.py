"""Requirements detectors: ATS-REQ-001, ATS-REQ-002, ATS-REQ-003.

Section 9.3.4 requires an explicit actor, Section 9.3.3 one obligation per
requirement, and Sections 9.3.2, 9.3.9, 9.3.10, and 9.3.15 require the
applicable slots to be resolved. All three are disabled under ASSESS
(Section 6.1 default states) and required under SPECIFY.
"""

from __future__ import annotations

import pytest

from ats.rules.results import Status

REQUIREMENT_RULES = ("ATS-REQ-001", "ATS-REQ-002", "ATS-REQ-003")

CLEAN_SPECIFY_STATUS = {
    "ATS-REQ-001": Status.PASS,
    "ATS-REQ-002": Status.REVIEW_REQUIRED,
    "ATS-REQ-003": Status.PASS,
}


@pytest.mark.parametrize("rule_id", REQUIREMENT_RULES)
def test_requirement_rules_do_not_run_under_assess(evaluate_ir, rule_id) -> None:
    """Spec 6.1: the requirement rules are disabled in the ASSESS profile."""
    result = evaluate_ir("assess_conforming", "assess")[rule_id]
    assert result.effective_state == "disabled"
    assert result.status is Status.NOT_APPLICABLE
    assert result.findings == ()


@pytest.mark.parametrize("rule_id", REQUIREMENT_RULES)
def test_conforming_specify_raises_no_requirement_finding(evaluate_ir, rule_id) -> None:
    """Spec 21.3: the conforming SPECIFY example resolves every applicable slot."""
    result = evaluate_ir("specify_conforming", "specify")[rule_id]
    assert result.findings == ()
    assert result.status is CLEAN_SPECIFY_STATUS[rule_id]
    assert result.effective_state == "required"


# -- ATS-REQ-001 ------------------------------------------------------------


def test_req_001_fails_on_a_concealing_actor(evaluate_ir, issue_codes) -> None:
    """Spec 9.3.4 and 21.4: 'the system' does not identify the responsible component."""
    result = evaluate_ir("concealed_actor", "specify")["ATS-REQ-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["actor-concealed"]
    assert str(result.decision_power) == "decides"
    assert "the system" in result.findings[0].summary


@pytest.mark.parametrize("actor", ["it", "This", "  they  ", "the system", "System"])
def test_req_001_rejects_every_concealing_form_the_spec_names(
    mutated_ir, evaluate_document, issue_codes, actor
) -> None:
    """Spec 9.3.4: the nonconforming forms are quoted from the specification."""
    document = mutated_ir("specify_conforming")
    document["sections"][0]["claims"][0]["requirement"]["actor"] = actor
    result = evaluate_document(document, "specify")["ATS-REQ-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["actor-concealed"]


def test_req_001_accepts_a_named_component(mutated_ir, evaluate_document) -> None:
    """Spec 9.3.4: a named component satisfies the rule."""
    document = mutated_ir("concealed_actor")
    document["sections"][0]["claims"][0]["requirement"]["actor"] = "acceptance verifier"
    result = evaluate_document(document, "specify")["ATS-REQ-001"]
    assert result.findings == ()
    assert result.status is Status.PASS


# -- ATS-REQ-002 ------------------------------------------------------------


def test_req_002_fails_on_coordinated_actions_without_a_justification(
    evaluate_ir, issue_codes
) -> None:
    """Spec 9.3.3: 'reject and record an audit event' is two obligations."""
    result = evaluate_ir("two_obligations", "specify")["ATS-REQ-002"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["coordinated-actions-without-indivisibility"]
    assert str(result.decision_power) == "detects_violations"


def test_req_002_is_suppressed_by_a_declared_indivisibility(
    mutated_ir, evaluate_document
) -> None:
    """Spec 9.3.3 provides exactly this escape for a genuinely atomic action."""
    document = mutated_ir("two_obligations")
    document["sections"][0]["claims"][0]["requirement"][
        "indivisible_actions_justification"
    ] = "The rejection and its audit record are committed in one transaction."
    result = evaluate_document(document, "specify")["ATS-REQ-002"]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED


def test_req_002_reads_the_action_slot_through_a_declared_substitution(ctx) -> None:
    """Spec 5.5: `syntax` is unavailable, so the substitution must be declared."""
    cap = ctx.capability.rules["ATS-REQ-002"]
    assert "syntax" in cap.required_inputs
    assert "syntax" in cap.missing_inputs
    assert cap.blocking_inputs == ()
    substitution = next(s for s in cap.input_substitutions if s["input"] == "syntax")
    assert substitution["spec_ref"].startswith("ATS-1 9.3")
    assert substitution["justification"].strip()


# -- ATS-REQ-003 ------------------------------------------------------------


def test_req_003_fails_when_a_must_carries_no_acceptance_criterion(
    evaluate_ir, issue_codes
) -> None:
    """Spec 9.3.9 and 9.3.10: a MUST needs a verifiable acceptance criterion."""
    result = evaluate_ir("missing_acceptance_criterion", "specify")["ATS-REQ-003"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["must-without-acceptance-criterion"]
    assert str(result.decision_power) == "decides"


@pytest.mark.parametrize("criterion", ["works correctly", "is robust"])
def test_req_003_rejects_the_vacuous_forms_the_spec_names(
    mutated_ir, evaluate_document, issue_codes, criterion
) -> None:
    """Spec 9.3.9 names these forms as not being acceptance criteria."""
    document = mutated_ir("specify_conforming")
    document["sections"][0]["claims"][0]["requirement"]["acceptance_criterion"] = criterion
    result = evaluate_document(document, "specify")["ATS-REQ-003"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["vacuous-acceptance-criterion"]


def test_req_003_fails_on_an_applicable_slot_marked_unknown(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 9.3.2: an unknown applicable slot prevents profile conformance."""
    document = mutated_ir("specify_conforming")
    document["sections"][0]["claims"][0]["requirement"]["timing"] = "unknown"
    result = evaluate_document(document, "specify")["ATS-REQ-003"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["applicable-slot-marked-unknown"]


def test_req_003_fails_when_the_source_authority_is_blank(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 9.3.15: the obligation's origin must be stated."""
    document = mutated_ir("specify_conforming")
    document["sections"][0]["claims"][0]["requirement"]["source_authority"] = "   "
    result = evaluate_document(document, "specify")["ATS-REQ-003"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["requirement-without-source-authority"]


def test_req_003_does_not_require_an_acceptance_criterion_for_a_should(
    evaluate_ir
) -> None:
    """Spec 9.3.9 attaches the obligation to MUST and MUST NOT."""
    result = evaluate_ir("should_without_override", "specify")["ATS-REQ-003"]
    assert result.findings == ()
    assert result.status is Status.PASS

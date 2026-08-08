"""Reference and scope detectors: ATS-REF-001 and ATS-SCOPE-001.

Section 10.6 requires a referring expression to have one plausible antecedent
and Section 7.6 requires an unambiguous scope. Both decisions need the parsed
sentence syntax, which ``ats ir lint`` does not receive, so both rules report
UNAVAILABLE and name ``syntax`` rather than approximating from the IR.
"""

from __future__ import annotations

import pytest

from ats.rules.results import Status

REFERENCE_RULES = ("ATS-REF-001", "ATS-SCOPE-001")


@pytest.mark.parametrize("rule_id", REFERENCE_RULES)
@pytest.mark.parametrize(
    ("ir_name", "policy_name", "state"),
    [
        ("assess_conforming", "assess", "advisory"),
        ("specify_conforming", "specify", "required"),
    ],
)
def test_syntax_dependent_rules_are_unavailable_on_the_ir_surface(
    ctx, evaluate_ir, rule_id, ir_name, policy_name, state
) -> None:
    """Spec 5.4 and 5.5: a rule that cannot run says so, and says what it lacks."""
    result = evaluate_ir(ir_name, policy_name)[rule_id]
    assert result.effective_state == state
    assert result.status is Status.UNAVAILABLE
    assert result.findings == ()
    assert "syntax" in result.missing_inputs
    assert set(result.missing_inputs) <= set(ctx.registry.get(rule_id).required_inputs)
    assert str(result.decision_power) == "undecidable"
    assert result.reason.strip()


@pytest.mark.parametrize("rule_id", REFERENCE_RULES)
def test_an_unavailable_required_rule_blocks_its_conformance_dimension(
    evaluate_ir, rule_id
) -> None:
    """Spec 5.4: UNAVAILABLE on a required check blocks, it does not pass."""
    result = evaluate_ir("specify_conforming", "specify")[rule_id]
    assert result.effective_state == "required"
    assert result.blocks_conformance is True


@pytest.mark.parametrize("rule_id", REFERENCE_RULES)
def test_the_capability_publishes_the_same_gap(ctx, rule_id) -> None:
    """Spec 16.1: the declaration must describe the same unavailability."""
    cap = ctx.capability.rules[rule_id]
    assert cap.decision_power == "undecidable"
    assert cap.implemented is False
    assert "syntax" in cap.blocking_inputs
    assert cap.detector_class == "none"
    assert cap.authority == "none"
    assert cap.unavailable_conditions, "spec 5.5 requires the condition to be stated"


@pytest.mark.parametrize("rule_id", REFERENCE_RULES)
def test_unavailable_rules_still_report_their_named_subchecks(evaluate_ir, rule_id) -> None:
    """Spec 12.10: an abstention still explains which check did not run."""
    result = evaluate_ir("assess_conforming", "assess")[rule_id]
    assert result.subchecks
    assert {record["status"] for record in result.subchecks} == {"UNAVAILABLE"}
    for record in result.subchecks:
        assert record["spec_ref"].startswith("ATS-1 ")
        assert record["detail"].strip()

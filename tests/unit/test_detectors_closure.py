"""Local semantic closure detector: ATS-CLOSE-001.

Draft.2 amendment D-D (spec 4.24, 7.18). The slot-presence and reference
mechanics are decided; whether the recovered meaning is genuinely sufficient
for action is a semantic judgement, so a clean run is REVIEW_REQUIRED, never
PASS (detects_violations power).
"""

from __future__ import annotations

import pytest

from ats.rules.results import Status

DRAFT2_POLICY = "draft2"


def _result(evaluate_ir_d2, ir_name):
    return evaluate_ir_d2(ir_name, DRAFT2_POLICY)["ATS-CLOSE-001"]


def test_close_001_a_closed_unit_reports_review_required(evaluate_ir_d2) -> None:
    """Spec 4.24: presence mechanics pass; semantic sufficiency stays under review."""
    result = _result(evaluate_ir_d2, "ats-close-001-closed")
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED
    assert str(result.decision_power) == "detects_violations"
    assert result.effective_state == "required"


def test_close_001_flags_a_missing_actor(evaluate_ir_d2, issue_codes) -> None:
    """Spec 7.18: a SPECIFY requirement without an actor is not locally closed."""
    result = _result(evaluate_ir_d2, "ats-close-001-missing-actor")
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["requirement-slot-missing-actor"]
    assert str(result.decision_power) == "detects_violations"


def test_close_001_a_non_extractable_document_is_a_hard_negative(
    evaluate_ir_d2,
) -> None:
    """No extractable normative unit means no closure to check."""
    result = _result(evaluate_ir_d2, "ats-close-001-non-extractable")
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED
    assert {record["status"] for record in result.subchecks} == {"NOT_APPLICABLE"}


def test_close_001_an_inherited_actor_satisfies_the_actor_slot(evaluate_ir_d2) -> None:
    """Spec 4.24: an explicitly declared enclosing scope MAY provide the actor."""
    result = _result(evaluate_ir_d2, "ats-close-001-inherited-actor")
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED


def test_close_001_flags_a_missing_object(mutated_ir, evaluate_document_d2, issue_codes) -> None:
    """Spec 7.18: the object of the action is required for local closure."""
    document = mutated_ir("ats-close-001-closed")
    document["sections"][0]["claims"][0]["requirement"]["object"] = " "
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-CLOSE-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["requirement-slot-missing-object"]


def test_close_001_flags_an_unresolved_acceptance_criterion_reference(
    mutated_ir, evaluate_document_d2, issue_codes
) -> None:
    """Spec 7.18: the acceptance criterion must resolve against declared coordinates."""
    document = mutated_ir("ats-close-001-closed")
    document["sections"][0]["claims"][0]["requirement"]["acceptance_criterion_id"] = "AC-NOPE"
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-CLOSE-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["acceptance-criterion-ref-unresolved"]


def test_close_001_flags_an_unresolved_dependency_target(
    mutated_ir, evaluate_document_d2, issue_codes
) -> None:
    """Spec 7.18: a dependency target that resolves to nothing breaks closure."""
    document = mutated_ir("ats-close-001-closed")
    document["sections"][0]["relations"].append(
        {
            "relation_id": "REL-CLOSE-1",
            "source_id": "REQ-C1-1",
            "type": "depends_on",
            "target_id": "REQ-NOPE",
            "material": True,
            "dependency_target": "REQ-NOPE",
        }
    )
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-CLOSE-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["dependency-target-unresolved"]

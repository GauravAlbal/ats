"""Stable semantic coordinate detectors: ATS-COORD-001, ATS-COORD-002.

Draft.2 amendments D-C protect the eight coordinate kinds (spec 4.23, 7.17).
ATS-COORD-001 preserves the declared coordinate set, ATS-COORD-002 guards
coordinate integrity. Both are exact set/reference checks, so both decide:
PASS or FAIL, never a review placeholder. The draft.2 fixtures live in
fixtures/ir/{conforming,violation,hard_negative,exception} and are evaluated
under the draft.2 policy snapshot with the 36-rule registry.
"""

from __future__ import annotations

import pytest

from ats.rules.results import Status

DRAFT2_POLICY = "draft2"


def _result(evaluate_ir_d2, ir_name, rule_id):
    return evaluate_ir_d2(ir_name, DRAFT2_POLICY)[rule_id]


# -- ATS-COORD-001 ----------------------------------------------------------


def test_coord_001_passes_when_every_use_is_declared_and_every_declaration_resolves(
    evaluate_ir_d2,
) -> None:
    """Spec 7.17: the declared coordinates are used and resolve to real objects."""
    result = _result(evaluate_ir_d2, "ats-coord-001-declared", "ATS-COORD-001")
    assert result.status is Status.PASS
    assert result.findings == ()
    assert str(result.decision_power) == "decides"
    assert result.effective_state == "required"
    statuses = {record["subcheck_id"]: record["status"] for record in result.subchecks}
    assert statuses == {
        "coordinate-used-but-undeclared": "PASS",
        "declared-coordinate-unresolved": "PASS",
    }


def test_coord_001_flags_undeclared_use_and_unresolved_declarations(
    evaluate_ir_d2, issue_codes
) -> None:
    """Spec 7.17: a used-but-undeclared or declared-but-unresolved coordinate is a violation."""
    result = _result(evaluate_ir_d2, "ats-coord-001-undeclared-use", "ATS-COORD-001")
    assert result.status is Status.FAIL
    assert issue_codes(result) == [
        "coordinate-used-but-undeclared",
        "declared-coordinate-unresolved",
    ]
    assert str(result.decision_power) == "decides"


def test_coord_001_no_block_is_not_an_exact_comparison_that_ran(
    evaluate_ir_d2,
) -> None:
    """Spec 7.17: the block is optional, but a rule that inspected nothing
    must not report PASS (ADR-0002). All-NOT_APPLICABLE subchecks degrade to
    NOT_APPLICABLE."""
    result = _result(evaluate_ir_d2, "ats-coord-001-no-block", "ATS-COORD-001")
    assert result.status is Status.NOT_APPLICABLE
    assert result.findings == ()
    for record in result.subchecks:
        assert record["status"] == "NOT_APPLICABLE"
        assert "no stable_coordinates block" in record["detail"]


def test_coord_001_removing_the_block_never_passes_by_absence(
    mutated_ir, evaluate_document_d2
) -> None:
    """ADR-0002: a document that uses coordinate ids but declares no block is
    NOT_APPLICABLE (the rule inspected nothing), never PASS — a renderer could
    otherwise drop every coordinate with nothing failing."""
    document = mutated_ir("ats-coord-001-declared")
    document.pop("stable_coordinates")
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-COORD-001"]
    assert result.status is Status.NOT_APPLICABLE
    assert result.findings == ()


def test_coord_001_externally_scoped_coordinates_may_resolve_out_of_ir(
    mutated_ir, evaluate_document_d2
) -> None:
    """Spec 4.23: protocol/work-item/authority/dependency coordinates name
    objects outside this IR; declaring one is not an unresolved-coordinate
    violation (mirrors the package validator's kind split)."""
    document = mutated_ir("ats-coord-001-declared")
    document["stable_coordinates"].append(
        {
            "kind": "protocol_id",
            "id": "RPL-PROV-001",
            "source_pointer": "#/stable_coordinates/9",
        }
    )
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-COORD-001"]
    assert result.status is Status.PASS
    assert result.findings == ()


def test_coord_001_document_scoped_coordinate_without_an_object_is_a_violation(
    mutated_ir, evaluate_document_d2, issue_codes
) -> None:
    """Spec 7.17: a document-scoped coordinate that names nothing cannot join
    anything. (work_item_id is externally scoped and exempt; requirement_id is
    not.)"""
    document = mutated_ir("ats-coord-001-declared")
    document["stable_coordinates"].append(
        {
            "kind": "requirement_id",
            "id": "REQ-000-NO-SUCH",
            "source_pointer": "#/stable_coordinates/9",
        }
    )
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-COORD-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["declared-coordinate-unresolved"]


def test_coord_001_an_unwaivable_rule_still_fires_under_a_declared_exception(
    evaluate_ir_d2, issue_codes
) -> None:
    """Spec 6.4: the policy exception declares the deviation but cannot waive the rule."""
    result = _result(evaluate_ir_d2, "ats-coord-001-policy-exception", "ATS-COORD-001")
    assert result.effective_state == "required"
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["coordinate-used-but-undeclared"]


# -- ATS-COORD-002 ----------------------------------------------------------


def test_coord_002_passes_when_ids_are_unique_and_references_resolve(
    evaluate_ir_d2,
) -> None:
    """Spec 7.17: unique declared ids and resolving dependency/AC references."""
    result = _result(evaluate_ir_d2, "ats-coord-002-unique", "ATS-COORD-002")
    assert result.status is Status.PASS
    assert result.findings == ()
    assert str(result.decision_power) == "decides"


def test_coord_002_flags_a_duplicate_declared_coordinate(evaluate_ir_d2, issue_codes) -> None:
    """Spec 7.17: the same id declared twice breaks coordinate integrity."""
    result = _result(evaluate_ir_d2, "ats-coord-002-duplicate", "ATS-COORD-002")
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["duplicate-coordinate-id"]
    assert str(result.decision_power) == "decides"


def test_coord_002_no_block_and_no_references_is_not_an_inspected_pass(
    evaluate_ir_d2,
) -> None:
    """ADR-0002: with no block and no coordinate references, the integrity
    checks inspected nothing and must not report a decided PASS."""
    result = _result(evaluate_ir_d2, "ats-coord-002-unique-ids", "ATS-COORD-002")
    assert result.status is Status.NOT_APPLICABLE
    assert result.findings == ()


def test_coord_002_a_duplicate_still_fires_under_a_declared_exception(
    evaluate_ir_d2, issue_codes
) -> None:
    """Spec 6.4: an unwaivable integrity rule keeps firing under a declared exception."""
    result = _result(evaluate_ir_d2, "ats-coord-002-dup-under-exception", "ATS-COORD-002")
    assert result.effective_state == "required"
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["duplicate-coordinate-id"]


def test_coord_002_flags_a_dangling_dependency_target(
    mutated_ir, evaluate_document_d2, issue_codes
) -> None:
    """Spec 7.17: a dependency_target that resolves to nothing is a violation."""
    document = mutated_ir("ats-coord-002-unique")
    document["sections"][0]["relations"][0]["dependency_target"] = "REQ-NO-SUCH"
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-COORD-002"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["dependency-target-unresolved"]


def test_coord_002_flags_a_dangling_acceptance_criterion_without_a_block(
    mutated_ir, evaluate_document_d2, issue_codes
) -> None:
    """Spec 7.17: without a block, an AC ref must still resolve to a claim id."""
    document = mutated_ir("ats-coord-001-no-block")
    document["sections"][0]["claims"][0]["requirement"]["acceptance_criterion_id"] = "AC-NO-SUCH"
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-COORD-002"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["acceptance-criterion-ref-unresolved"]


def test_coord_002_an_undeclared_but_real_target_is_still_a_violation(
    mutated_ir, evaluate_document_d2, issue_codes
) -> None:
    """Spec 7.17: with a block, a ref must resolve to a DECLARED coordinate."""
    document = mutated_ir("ats-coord-002-unique")
    document["stable_coordinates"] = [
        e for e in document["stable_coordinates"] if e["id"] != "REQ-C002-2"
    ]
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-COORD-002"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["dependency-target-unresolved"]

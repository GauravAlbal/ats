"""Semantic basis detectors: ATS-BASIS-001, ATS-BASIS-002.

Draft.2 amendment D-F (spec 4.25, 7.19). ATS-BASIS-001 is a review_required
D3 rule: it recognises material claims without a declared basis but cannot
decide that a missing basis is immaterial, so a clean run is REVIEW_REQUIRED.
ATS-BASIS-002 is a block rule: over an IR that carries an
``extensions.source_basis`` ledger it decides whether any EXPLICIT claim
promoted INFERRED or UNAVAILABLE source material; without that ledger the
required transformation inputs are missing and it reports UNAVAILABLE naming
them, never PASS (ADR-0002).
"""

from __future__ import annotations

import pytest

from ats.rules.results import Status

DRAFT2_POLICY = "draft2"


def _result(evaluate_ir_d2, ir_name, rule_id):
    return evaluate_ir_d2(ir_name, DRAFT2_POLICY)[rule_id]


# -- ATS-BASIS-001 ----------------------------------------------------------


def test_basis_001_declared_bases_leave_a_clean_run_review_required(
    evaluate_ir_d2,
) -> None:
    """Spec 4.25: every material claim declares a basis; D3 cannot conclude from silence."""
    result = _result(evaluate_ir_d2, "ats-basis-001-declared", "ATS-BASIS-001")
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED
    assert str(result.decision_power) == "detects_violations"
    assert result.effective_state == "required"


def test_basis_001_flags_a_material_claim_without_a_basis(
    evaluate_ir_d2, issue_codes
) -> None:
    """Spec 7.19: a material claim with no semantic_basis under a declared policy."""
    result = _result(evaluate_ir_d2, "ats-basis-001-missing-basis", "ATS-BASIS-001")
    assert result.findings
    assert issue_codes(result) == ["material-claim-without-basis"]
    assert result.status is Status.REVIEW_REQUIRED  # D3 output is proposal_only


def test_basis_001_no_material_claims_is_a_hard_negative(evaluate_ir_d2) -> None:
    """A document with no material claim declares no material value to check."""
    result = _result(evaluate_ir_d2, "ats-basis-001-no-material-claims", "ATS-BASIS-001")
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED
    assert {record["status"] for record in result.subchecks} == {"NOT_APPLICABLE"}


def test_basis_001_still_flags_when_the_policy_does_not_require_declaration(
    mutated_ir, evaluate_document_d2, issue_codes
) -> None:
    """Spec 7.19: declared=false lowers the emphasis, not the presence check."""
    document = mutated_ir("ats-basis-001-missing-basis")
    document["basis_policy"]["declared"] = False
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-BASIS-001"]
    assert result.findings
    assert issue_codes(result) == ["material-claim-without-basis"]


def test_basis_001_a_requirement_slot_basis_satisfies_the_unit(
    mutated_ir, evaluate_document_d2
) -> None:
    """Spec 7.19: a basis declared on the requirement slot covers the material claim."""
    document = mutated_ir("ats-basis-001-missing-basis")
    document["sections"][0]["claims"][1]["semantic_basis"] = {
        "basis": "AUTHOR_JUDGMENT",
        "rationale": "The recommendation is new authoring under granted authority.",
    }
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-BASIS-001"]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED


def test_basis_001_the_exception_declares_the_deviation_but_the_finding_stands(
    evaluate_ir_d2, issue_codes
) -> None:
    """The IR-level policy exception documents the gap; the D3 finding still surfaces."""
    result = _result(evaluate_ir_d2, "ats-basis-001-exception", "ATS-BASIS-001")
    assert result.findings
    assert issue_codes(result) == ["material-claim-without-basis"]
    assert result.status is Status.REVIEW_REQUIRED


# -- ATS-BASIS-002 ----------------------------------------------------------


def test_basis_002_is_unavailable_without_the_source_basis_ledger(
    evaluate_ir_d2,
) -> None:
    """Spec 5.4 and ADR-0002: no source side, no comparison, UNAVAILABLE naming inputs."""
    result = _result(evaluate_ir_d2, "ats-coord-001-declared", "ATS-BASIS-002")
    assert result.effective_state == "required"
    assert result.status is Status.UNAVAILABLE
    assert result.findings == ()
    assert tuple(result.missing_inputs) == ("source_ir", "output_ir")
    assert str(result.decision_power) == "undecidable"
    assert result.blocks_conformance is True


def test_basis_002_passes_when_inferred_stays_inferred(evaluate_ir_d2) -> None:
    """Spec 4.25: an INFERRED claim whose source basis is INFERRED is not a promotion."""
    result = _result(evaluate_ir_d2, "ats-basis-002-inferred-stays-inferred", "ATS-BASIS-002")
    assert result.status is Status.PASS
    assert result.findings == ()
    assert str(result.decision_power) == "decides"


def test_basis_002_flags_a_silent_promotion_to_explicit(
    evaluate_ir_d2, issue_codes
) -> None:
    """D-F: EXPLICIT output over INFERRED source material is a silent promotion."""
    result = _result(evaluate_ir_d2, "ats-basis-002-promoted", "ATS-BASIS-002")
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["inferred-source-promoted-to-explicit"]
    assert str(result.decision_power) == "decides"


def test_basis_002_genuinely_explicit_source_material_passes(evaluate_ir_d2) -> None:
    """Hard negative: EXPLICIT output over EXPLICIT source material is allowed."""
    result = _result(evaluate_ir_d2, "ats-basis-002-genuinely-explicit", "ATS-BASIS-002")
    assert result.status is Status.PASS
    assert result.findings == ()


def test_basis_002_a_requirement_slot_promotion_is_detected(
    mutated_ir, evaluate_document_d2, issue_codes
) -> None:
    """D-F: the schema permits basis at either level; a requirement-slot
    EXPLICIT over an INFERRED source is the same silent promotion (F3)."""
    document = mutated_ir("ats-basis-002-promoted")
    claim = document["sections"][0]["claims"][0]
    claim["requirement"] = {
        "requirement_id": "REQ-B2-1",
        "actor": "Sear",
        "deontic": "MUST",
        "action": "preserve",
        "object": "accepted messages",
        "source_authority": "tribunal",
        "semantic_basis": claim.pop("semantic_basis"),
    }
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-BASIS-002"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["inferred-source-promoted-to-explicit"]


def test_basis_002_an_authorized_change_suppresses_the_finding(evaluate_ir_d2) -> None:
    """Spec 11.4: an authorized semantic change declares the promotion explicitly."""
    result = _result(evaluate_ir_d2, "ats-basis-002-authorized-change", "ATS-BASIS-002")
    assert result.status is Status.PASS
    assert result.findings == ()


def test_basis_002_a_document_level_ledger_is_read_too(
    mutated_ir, evaluate_document_d2, issue_codes
) -> None:
    """The ledger may sit at document level rather than per claim."""
    document = mutated_ir("ats-basis-002-inferred-stays-inferred")
    claim = document["sections"][0]["claims"][0]
    claim.pop("extensions")
    claim["semantic_basis"]["basis"] = "EXPLICIT"
    document["extensions"] = {"source_basis": {"EV-B2-1": "INFERRED"}}
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-BASIS-002"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["inferred-source-promoted-to-explicit"]


def test_basis_002_unavailable_basis_values_are_promotions_too(
    mutated_ir, evaluate_document_d2, issue_codes
) -> None:
    """D-F: UNAVAILABLE source material must not become EXPLICIT either."""
    document = mutated_ir("ats-basis-002-inferred-stays-inferred")
    claim = document["sections"][0]["claims"][0]
    claim["extensions"]["source_basis"]["EV-B2-1"] = "UNAVAILABLE"
    claim["semantic_basis"]["basis"] = "EXPLICIT"
    result = evaluate_document_d2(document, DRAFT2_POLICY)["ATS-BASIS-002"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["inferred-source-promoted-to-explicit"]

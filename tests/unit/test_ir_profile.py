"""Profile completeness.

Section 12.8 puts the profile validators alongside the thirty rules rather than
inside them. Section 9.2.13 fixes the failure semantics: an unresolved material
slot is FAIL, and a slot this implementation cannot evaluate is UNAVAILABLE.
Section 9.3.20 does the same for SPECIFY.
"""

from __future__ import annotations

import copy

import pytest

from ats.ir.model import IrDocument
from ats.ir.profile import (
    EVALUABLE_PROFILES,
    SPECIFY_MANDATORY_SLOTS,
    assess_assessment_object,
    assess_document_slots,
    evaluate_profiles,
    specify_requirement_slots,
    specify_set_level,
)
from ats.rules.results import Status


def check_for(document):
    return evaluate_profiles(IrDocument.from_document(document))


@pytest.mark.parametrize("name", ["assess_conforming", "specify_conforming"])
def test_conforming_artifacts_resolve_every_material_slot(load_ir, name) -> None:
    """Spec 9.2.13 and 9.3.20: the conforming examples are profile complete."""
    check, gaps = check_for(load_ir(name))
    assert gaps == []
    assert check.check_id == "IR-PROFILE-SLOTS"
    assert check.status is Status.PASS
    assert check.required is True
    assert "9.2.13" in check.spec_ref


def test_a_missing_document_level_slot_fails(load_ir) -> None:
    """Spec 9.2.2: an ASSESS section must carry an update indicator."""
    check, gaps = check_for(load_ir("no_update_indicator"))
    assert check.status is Status.FAIL
    assert {gap.slot for gap in gaps} >= {"update_indicators"}
    assert "update_indicators" in check.detail


@pytest.mark.parametrize(
    "role", ["open_question", "judgment", "assumption", "boundary"]
)
def test_every_required_assess_role_is_a_document_level_slot(load_ir, role) -> None:
    """Spec 9.2.2 enumerates the document-level slots an ASSESS section carries."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    section = document["sections"][0]
    section["claims"] = [c for c in section["claims"] if c["role"] != role]
    ir = IrDocument.from_document(document)
    gaps = assess_document_slots(ir, ir.sections[0])
    assert role in {gap.slot for gap in gaps}


def test_a_forecast_satisfies_the_key_judgment_slot(load_ir) -> None:
    """Spec 9.2.11: a forecast is a judgment subprofile."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    claim = document["sections"][0]["claims"][0]
    claim["role"] = "forecast"
    claim["forecast"] = {
        "forecast_id": "f1",
        "outcome_definition": "Invalid-state defects fall below the current median.",
        "resolution": "2027-02-01",
        "resolution_source": "Arq acceptance defect ledger",
    }
    ir = IrDocument.from_document(document)
    gaps = assess_document_slots(ir, ir.sections[0])
    assert "judgment" not in {gap.slot for gap in gaps}


def test_an_assessment_object_must_carry_its_section_9_2_4_slots(load_ir) -> None:
    """Spec 9.2.4: a material judgment carries scope, confidence, evidence, and boundaries."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    claim = document["sections"][0]["claims"][0]
    claim.pop("scope", None)
    claim["force"].pop("assessment_confidence", None)
    claim["force"].pop("likelihood", None)

    ir = IrDocument.from_document(document)
    gaps = assess_assessment_object(ir.claims["c1"], ir)
    slots = {gap.slot for gap in gaps}
    assert {"scope", "assessment_confidence", "likelihood"} <= slots


def test_a_non_probabilistic_judgment_may_omit_a_likelihood_with_a_stated_basis(
    load_ir,
) -> None:
    """Spec 9.2.4: the basis that makes likelihood inapplicable must be stated."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    claim = document["sections"][0]["claims"][0]
    del claim["force"]["likelihood"]

    ir = IrDocument.from_document(document)
    gaps = assess_assessment_object(ir.claims["c1"], ir)
    assert "likelihood" not in {gap.slot for gap in gaps}


def test_a_missing_acceptance_criterion_is_a_specify_slot_gap(load_ir) -> None:
    """Spec 9.3.10 forbids reporting profile PASS without a MUST's acceptance criterion."""
    check, gaps = check_for(load_ir("missing_acceptance_criterion"))
    assert check.status is Status.FAIL
    assert {gap.slot for gap in gaps} == {"acceptance_criterion"}
    assert "9.3.10" in gaps[0].detail


@pytest.mark.parametrize("slot", SPECIFY_MANDATORY_SLOTS)
def test_every_mandatory_specify_slot_is_checked(load_ir, slot) -> None:
    """Spec 9.3.2 enumerates the slots every material requirement carries."""
    document = copy.deepcopy(load_ir("specify_conforming"))
    document["sections"][0]["claims"][0]["requirement"][slot] = "  "
    ir = IrDocument.from_document(document)
    gaps = specify_requirement_slots(ir.claims["REQ-POLICY-017"])
    assert slot in {gap.slot for gap in gaps}


def test_a_requirement_role_without_a_requirement_object_is_a_gap(load_ir) -> None:
    """Spec 9.3.2: the requirement object is the represented obligation."""
    document = copy.deepcopy(load_ir("specify_conforming"))
    del document["sections"][0]["claims"][0]["requirement"]
    ir = IrDocument.from_document(document)
    (gap,) = specify_requirement_slots(ir.claims["REQ-POLICY-017"])
    assert gap.slot == "requirement"


def test_a_reused_requirement_identifier_is_reported(load_ir) -> None:
    """Spec 9.3.18: identifiers are unique within an authority domain."""
    document = copy.deepcopy(load_ir("specify_conforming"))
    section = document["sections"][0]
    clone = copy.deepcopy(section["claims"][0])
    clone["claim_id"] = "REQ-POLICY-017-B"
    clone["proposition"] = (
        "When the executor replays an acceptance receipt, the verifier MUST reject it."
    )
    section["claims"].append(clone)

    ir = IrDocument.from_document(document)
    (gap,) = specify_set_level(ir)
    assert gap.slot == "requirement_id"
    assert "REQ-POLICY-017" in gap.detail
    assert "9.3.18" in gap.detail


def test_a_profile_this_implementation_cannot_evaluate_is_unavailable(load_ir) -> None:
    """Spec 9.5: a reserved profile is preserved, not coerced onto a stable one."""
    assert EVALUABLE_PROFILES == ("ASSESS", "SPECIFY")
    check, gaps = check_for(load_ir("reserved_profile"))
    assert check.status is Status.UNAVAILABLE
    assert gaps == []
    assert "X-ARQ-EXPLAIN-1" in check.detail
    assert "9.5" in check.detail


def test_a_complete_artifact_carrying_an_unevaluable_profile_is_unavailable(
    load_ir,
) -> None:
    """Spec 9.2.13: completeness for the artifact as a whole is unavailable."""
    check, gaps = check_for(load_ir("assess_transform_output"))
    assert gaps == []
    assert check.status is Status.UNAVAILABLE
    assert "TRANSFORM" in check.detail


def test_a_composed_artifact_is_evaluated_under_each_profile(load_ir) -> None:
    """Spec 6.5 and 9.4: composition accumulates obligations, it does not choose."""
    check, gaps = check_for(load_ir("composed_profiles"))
    assert gaps == []
    assert check.status is Status.PASS
    assert "2 profiled section(s)" in check.detail

"""Preservation detectors: ATS-PRES-001, ATS-PRES-002, ATS-PRES-003.

Section 11.3.1 and Section 11.3.2 define the P0 and P1 preservation classes,
and both draft.1 rules require a source IR, an output IR, a retention contract,
and an authorization set. The v0 IR surface supplies none of those, so under
TRANSFORM both report UNAVAILABLE. Section 6.4 makes both unwaivable, which is
why they may never be quietly downgraded to a pass.

ATS-PRES-003 (draft.2 D-B) protects the P1 relation set under compression: when
the artifact carries the output trace in ``extensions.output_trace`` the
realization of every protected relation is decided over the trace's
``p1_relations``; without a trace it reports UNAVAILABLE naming ``trace``.
"""

from __future__ import annotations

import pytest

from ats.rules.results import Status

PRESERVATION_RULES = ("ATS-PRES-001", "ATS-PRES-002")

#: The four inputs Section 11.3 requires and the TextIR surface cannot supply.
REQUIRED_TRANSFORM_INPUTS = (
    "source_ir",
    "output_ir",
    "retention_contract",
    "authorizations",
)


@pytest.mark.parametrize("rule_id", PRESERVATION_RULES)
def test_preservation_rules_are_unwaivable_in_the_registry(ctx, rule_id) -> None:
    """Spec 6.4: a preservation claim MUST NOT be waived by policy."""
    rule = ctx.registry.get(rule_id)
    assert rule.waivable is False
    assert tuple(rule.required_inputs) == REQUIRED_TRANSFORM_INPUTS
    assert rule.default_states == {
        "ASSESS": "disabled",
        "SPECIFY": "disabled",
        "TRANSFORM": "required",
    }


@pytest.mark.parametrize("rule_id", PRESERVATION_RULES)
@pytest.mark.parametrize(
    ("ir_name", "policy_name"),
    [("assess_conforming", "assess"), ("specify_conforming", "specify")],
)
def test_preservation_does_not_apply_to_a_non_transformed_artifact(
    evaluate_ir, rule_id, ir_name, policy_name
) -> None:
    """Spec 15.4: an artifact that is not a transformation output is NOT_APPLICABLE."""
    result = evaluate_ir(ir_name, policy_name)[rule_id]
    assert result.effective_state == "disabled"
    assert result.status is Status.NOT_APPLICABLE
    assert result.findings == ()
    assert result.subchecks == ()


@pytest.mark.parametrize("rule_id", PRESERVATION_RULES)
def test_preservation_is_unavailable_when_transform_is_active(
    ctx, evaluate_ir, rule_id
) -> None:
    """Spec 5.4 and 6.4: active, unwaivable, and unevaluable is UNAVAILABLE, not PASS."""
    result = evaluate_ir("assess_transform_output", "assess_transform")[rule_id]
    assert result.effective_state == "required"
    assert result.status is Status.UNAVAILABLE
    assert result.findings == ()
    assert tuple(result.missing_inputs) == REQUIRED_TRANSFORM_INPUTS
    assert str(result.decision_power) == "undecidable"
    assert result.blocks_conformance is True
    # Spec 16.1: the same gap is published rather than discovered at runtime.
    assert tuple(ctx.capability.rules[rule_id].blocking_inputs) == REQUIRED_TRANSFORM_INPUTS
    assert ctx.capability.rules[rule_id].implemented is False


@pytest.mark.parametrize("rule_id", PRESERVATION_RULES)
def test_preservation_subchecks_report_unavailable_individually(
    evaluate_ir, rule_id
) -> None:
    """Spec 5.4: each named subcheck reports its own unavailability."""
    result = evaluate_ir("assess_transform_output", "assess_transform")[rule_id]
    assert result.subchecks
    assert {record["status"] for record in result.subchecks} == {"UNAVAILABLE"}
    for record in result.subchecks:
        assert record["spec_ref"].startswith("ATS-1 11.3")


def test_the_capability_declares_only_declared_rendering_preservation(ctx) -> None:
    """Spec 16.1: what is implemented is P0/P1 declaration checking, not a transform proof."""
    projection = ctx.capability.to_normative(
        spec_version=ctx.spec_version, schema_versions=sorted(ctx.schemas.documents)
    )
    assert projection["preservation_methods"] == [
        "p0_exact_declared_rendering",
        "p1_declared_representation",
    ]
    assert any("TRANSFORM preservation" in limit for limit in projection["known_limitations"])


# -- ATS-PRES-003 ------------------------------------------------------------


def test_pres_003_is_unavailable_without_an_output_trace(evaluate_ir_d2) -> None:
    """Spec 5.4 and ADR-0002: no trace, no realization check, UNAVAILABLE naming trace."""
    result = evaluate_ir_d2("ats-coord-001-declared", "draft2")["ATS-PRES-003"]
    assert result.effective_state == "required"
    assert result.status is Status.UNAVAILABLE
    assert result.findings == ()
    assert tuple(result.missing_inputs) == ("trace",)
    assert str(result.decision_power) == "undecidable"
    assert result.blocks_conformance is True


def test_pres_003_passes_when_every_protected_relation_is_realized(evaluate_ir_d2) -> None:
    """Spec 11.3.2: a protected relation realized in the trace's p1_relations is preserved."""
    result = evaluate_ir_d2("ats-pres-003-realized", "draft2")["ATS-PRES-003"]
    assert result.status is Status.PASS
    assert result.findings == ()
    assert str(result.decision_power) == "decides"


def test_pres_003_flags_a_dropped_protected_relation(evaluate_ir_d2, issue_codes) -> None:
    """D-B: a relation absent from the trace's p1_relations was removed or made implicit."""
    result = evaluate_ir_d2("ats-pres-003-dropped", "draft2")["ATS-PRES-003"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["protected-relation-dropped"]
    assert "REL-P3-4" in result.findings[0].summary
    assert str(result.decision_power) == "decides"


def test_pres_003_no_protected_relations_is_a_hard_negative(evaluate_ir_d2) -> None:
    """A document with no protected relation has nothing the trace must realize."""
    result = evaluate_ir_d2("ats-pres-003-no-protected-relations", "draft2")["ATS-PRES-003"]
    assert result.status is Status.PASS
    assert result.findings == ()
    assert {record["status"] for record in result.subchecks} == {"NOT_APPLICABLE"}


def test_pres_003_an_authorized_semantic_change_suppresses_the_finding(evaluate_ir_d2) -> None:
    """Spec 11.4: an authorized semantic change classifies the drop separately."""
    result = evaluate_ir_d2(
        "ats-pres-003-authorized-semantic-change", "draft2"
    )["ATS-PRES-003"]
    assert result.status is Status.PASS
    assert result.findings == ()


def test_pres_003_a_dropped_relation_still_fails_without_an_authorization(
    mutated_ir, evaluate_document_d2, issue_codes
) -> None:
    """Spec 11.4: dropping requires the authorization object, not just a note."""
    document = mutated_ir("ats-pres-003-authorized-semantic-change")
    document["extensions"].pop("authorized_semantic_change")
    result = evaluate_document_d2(document, "draft2")["ATS-PRES-003"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["protected-relation-dropped"]


def test_pres_003_an_authorization_for_another_relation_does_not_cover_the_drop(
    mutated_ir, evaluate_document_d2, issue_codes
) -> None:
    """Spec 11.4: the authorization must name the exact source object."""
    document = mutated_ir("ats-pres-003-authorized-semantic-change")
    document["extensions"]["authorized_semantic_change"]["changed_relation"] = "REL-OTHER"
    result = evaluate_document_d2(document, "draft2")["ATS-PRES-003"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["protected-relation-dropped"]

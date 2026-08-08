"""Evidence detectors: ATS-EVID-001, ATS-EVID-002, ATS-EVID-003.

Section 9.2.5 separates observation, inference, and judgment; Section 9.2.10
separates recommendation from evidence; Sections 8.13 and 8.15 require a basis
behind asserted evidential or causal force; Sections 9.2.7 and 9.2.8 require an
exact contrary-evidence position.

ATS-EVID-002 and ATS-EVID-003 list only D3 and D4 in the registry, so Section
12.3 caps their output at ``proposal_only``: their findings are surfaced for
adjudication and the rule reports REVIEW_REQUIRED, never a decided FAIL.
"""

from __future__ import annotations

import pytest

from ats.rules.results import Status


@pytest.mark.parametrize("rule_id", ["ATS-EVID-001", "ATS-EVID-002", "ATS-EVID-003"])
@pytest.mark.parametrize(
    ("ir_name", "policy_name"),
    [("assess_conforming", "assess"), ("specify_conforming", "specify")],
)
def test_conforming_artifacts_raise_no_evidence_finding(
    evaluate_ir, rule_id, ir_name, policy_name
) -> None:
    """Spec 21.1 and 21.3: both conforming examples separate their epistemic roles."""
    result = evaluate_ir(ir_name, policy_name)[rule_id]
    assert result.findings == ()


def test_evid_001_passes_on_the_conforming_assess_artifact(evaluate_ir) -> None:
    """Spec 9.2.5: role and force compatibility is fully decidable from the IR."""
    result = evaluate_ir("assess_conforming", "assess")["ATS-EVID-001"]
    assert result.status is Status.PASS
    assert str(result.decision_power) == "decides"


@pytest.mark.parametrize("rule_id", ["ATS-EVID-002", "ATS-EVID-003"])
def test_proposal_only_evidence_rules_never_pass(evaluate_ir, rule_id) -> None:
    """Spec 12.3: a D3 detector may not contribute a conformance decision."""
    result = evaluate_ir("assess_conforming", "assess")[rule_id]
    assert result.status is Status.REVIEW_REQUIRED
    assert result.detector.detector_class == "D3"
    assert result.detector.authority == "proposal_only"
    assert result.detector.authority_basis_ref is None


# -- ATS-EVID-001 -----------------------------------------------------------


def test_evid_001_fails_when_an_observation_carries_assessment_force(
    evaluate_ir, issue_codes
) -> None:
    """Spec 9.2.5: assessment machinery on an observation hides the transition."""
    result = evaluate_ir("observation_with_confidence", "assess")["ATS-EVID-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["observation-carrying-assessment-force"]
    summary = result.findings[0].summary
    assert "likelihood" in summary and "assessment_confidence" in summary


def test_evid_001_fails_when_a_recommendation_carries_evidential_force(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 9.2.10: advice is not an observed consequence of the evidence."""
    document = mutated_ir("assess_conforming")
    recommendation = next(
        c for c in document["sections"][0]["claims"] if c["role"] == "recommendation"
    )
    recommendation["force"] = {"evidential": "observed"}

    result = evaluate_document(document, "assess")["ATS-EVID-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["recommendation-carrying-evidential-force"]


def test_evid_001_fails_when_an_assumption_carries_evidential_force(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 9.2.9 and 9.2.13: an assumption must not be presented as established."""
    document = mutated_ir("assess_conforming")
    assumption = next(
        c for c in document["sections"][0]["claims"] if c["role"] == "assumption"
    )
    assumption["force"] = {"evidential": "observed"}

    result = evaluate_document(document, "assess")["ATS-EVID-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["assumption-presented-as-established"]


# -- ATS-EVID-002 -----------------------------------------------------------


def test_evid_002_surfaces_a_supporting_relation_with_no_basis(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 8.13 and 8.15: asserted support must have something behind it."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["relations"].append(
        {
            "relation_id": "rel-unbased",
            "type": "supports",
            "source_id": "a1",
            "target_id": "c1",
            "material": True,
        }
    )
    result = evaluate_document(document, "assess")["ATS-EVID-002"]
    assert result.status is Status.REVIEW_REQUIRED
    assert issue_codes(result) == ["discriminating-relation-without-basis"]


def test_evid_002_surfaces_an_unresolvable_basis_reference(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 8.15: a basis that cannot be inspected is not a basis."""
    document = mutated_ir("assess_conforming")
    relation = next(r for r in document["sections"][0]["relations"] if r["type"] == "supports")
    relation["basis_refs"] = ["e-does-not-exist"]

    result = evaluate_document(document, "assess")["ATS-EVID-002"]
    assert issue_codes(result) == ["basis-reference-unresolved"]
    assert result.status is Status.REVIEW_REQUIRED


def test_evid_002_surfaces_model_output_standing_as_independent_evidence(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 9.2.6: a model's analysis is an inference, not another evidence line."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["evidence"][0]["source"]["source_type"] = "model_output"

    result = evaluate_document(document, "assess")["ATS-EVID-002"]
    assert issue_codes(result) == ["model-output-as-independent-evidence"]
    finding = result.findings[0]
    assert finding.evidence_spans, "spec 13.3 requires the evidence span"


def test_evid_002_ignores_a_non_discriminating_relation(
    mutated_ir, evaluate_document
) -> None:
    """Spec 8.13 attaches the obligation to relations that assert support or cause."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["relations"].append(
        {
            "relation_id": "rel-qualifies",
            "type": "qualifies",
            "source_id": "b1",
            "target_id": "c1",
            "material": True,
        }
    )
    result = evaluate_document(document, "assess")["ATS-EVID-002"]
    assert result.findings == ()


# -- ATS-EVID-003 -----------------------------------------------------------


def test_evid_003_surfaces_a_judgment_with_no_contrary_evidence_position(
    ctx, mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 9.2.7: a reader must tell a bounded search from no search."""
    document = mutated_ir("assess_conforming")
    basis = document["sections"][0]["claims"][0]["force"]["assessment_confidence"]["basis"]
    del basis["contrary_evidence"]

    result = evaluate_document(document, "assess")["ATS-EVID-003"]
    assert result.status is Status.REVIEW_REQUIRED
    assert issue_codes(result) == ["judgment-without-contrary-evidence-state"]
    for state in ("addressed", "none_found", "not_searched", "not_applicable"):
        assert state in result.findings[0].summary


def test_evid_003_is_satisfied_by_a_contrary_relation(
    mutated_ir, evaluate_document
) -> None:
    """Spec 9.2.8: a live alternative or contradiction against the claim suffices."""
    document = mutated_ir("assess_conforming")
    basis = document["sections"][0]["claims"][0]["force"]["assessment_confidence"]["basis"]
    del basis["contrary_evidence"]
    document["sections"][0]["relations"].append(
        {
            "relation_id": "rel-contra",
            "type": "contradicts",
            "source_id": "e3",
            "target_id": "c1",
            "material": True,
        }
    )
    result = evaluate_document(document, "assess")["ATS-EVID-003"]
    assert result.findings == ()


@pytest.mark.parametrize(
    "state", ["addressed", "none_found", "not_searched", "not_applicable"]
)
def test_evid_003_accepts_every_exact_contrary_state(
    mutated_ir, evaluate_document, state
) -> None:
    """Spec 9.2.7 enumerates exactly these positions."""
    document = mutated_ir("assess_conforming")
    basis = document["sections"][0]["claims"][0]["force"]["assessment_confidence"]["basis"]
    basis["contrary_evidence"] = state
    result = evaluate_document(document, "assess")["ATS-EVID-003"]
    assert result.findings == ()

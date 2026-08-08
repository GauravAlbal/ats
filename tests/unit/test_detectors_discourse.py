"""Discourse detectors: ATS-DISC-001, ATS-DISC-002, ATS-DISC-003.

Section 10.16 puts the load-bearing statement first. Sections 10.15 and 10.19
operate on paragraphs and on surrounding document context, neither of which the
TextIR represents, so those two rules report UNAVAILABLE and name what they
lack rather than substituting a proxy.
"""

from __future__ import annotations

import pytest

from ats.rules.results import Status


def test_conforming_assess_opens_with_its_key_judgment(evaluate_ir) -> None:
    """Spec 9.2.3 and 10.16: the operative claim precedes its background."""
    result = evaluate_ir("assess_conforming", "assess")["ATS-DISC-001"]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED
    assert result.effective_state == "advisory", "spec 10.16 is a SHOULD"


def test_conforming_specify_opens_with_its_requirement(evaluate_ir) -> None:
    """Spec 10.16: a requirement is a load-bearing statement."""
    result = evaluate_ir("specify_conforming", "specify")["ATS-DISC-001"]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED


def test_disc_001_fails_when_background_precedes_the_judgment(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 10.16: a reader must not traverse setup before the operative claim."""
    document = mutated_ir("assess_conforming")
    claims = document["sections"][0]["claims"]
    judgment = claims.pop(0)
    assert judgment["role"] == "judgment"
    claims.insert(2, judgment)
    assert claims[0]["role"] == "assumption"

    result = evaluate_document(document, "assess")["ATS-DISC-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["load-bearing-statement-not-first"]
    assert str(result.decision_power) == "detects_violations"
    finding = result.findings[0]
    assert "assumption" in finding.summary
    assert finding.evidence_spans, "spec 13.3: the displaced judgment is cited"


def test_disc_001_permits_a_framing_role_before_the_judgment(
    mutated_ir, evaluate_document
) -> None:
    """Spec 9.2.3 permits a short framing statement ahead of the key judgment."""
    document = mutated_ir("assess_conforming")
    claims = document["sections"][0]["claims"]
    question = claims.pop(3)
    assert question["role"] == "open_question"
    claims.insert(0, question)

    result = evaluate_document(document, "assess")["ATS-DISC-001"]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED


def test_disc_001_reads_ordering_through_a_declared_substitution(ctx) -> None:
    """Spec 5.5: `document_ast` is absent, so the IR ordering must be declared."""
    cap = ctx.capability.rules["ATS-DISC-001"]
    assert "document_ast" in cap.missing_inputs
    assert cap.blocking_inputs == ()
    substitution = next(s for s in cap.input_substitutions if s["input"] == "document_ast")
    assert substitution["spec_ref"] == "ATS-1 7.3"


@pytest.mark.parametrize(
    ("rule_id", "missing"),
    [("ATS-DISC-002", "document_ast"), ("ATS-DISC-003", "document_context")],
)
def test_structure_dependent_discourse_rules_are_unavailable(
    ctx, evaluate_ir, rule_id, missing
) -> None:
    """Spec 10.15 and 10.19: the unit of analysis does not exist on this surface."""
    result = evaluate_ir("assess_conforming", "assess")[rule_id]
    assert result.status is Status.UNAVAILABLE
    assert missing in result.missing_inputs
    assert missing in ctx.registry.get(rule_id).required_inputs
    assert result.findings == ()
    assert str(result.decision_power) == "undecidable"
    assert result.reason.strip()
    # Spec 16.1: the same gap is published in the capability declaration.
    assert missing in ctx.capability.rules[rule_id].blocking_inputs

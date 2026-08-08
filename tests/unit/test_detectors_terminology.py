"""Terminology detectors: ATS-TERM-001, ATS-TERM-002, ATS-TERM-003.

Section 10.2 requires one canonical term per concept within a scope, Section
10.4 governs substituted technical terms, and Section 10.5 requires an acronym
to be expanded at its first material use unless policy permits it.
"""

from __future__ import annotations

import pytest

from ats.rules.results import Status

CLEAN_ASSESS_STATUS = {
    "ATS-TERM-001": Status.REVIEW_REQUIRED,
    "ATS-TERM-002": Status.UNAVAILABLE,
    "ATS-TERM-003": Status.REVIEW_REQUIRED,
}


@pytest.mark.parametrize("rule_id", ["ATS-TERM-001", "ATS-TERM-002", "ATS-TERM-003"])
@pytest.mark.parametrize(
    ("ir_name", "policy_name"),
    [("assess_conforming", "assess"), ("specify_conforming", "specify")],
)
def test_conforming_artifacts_raise_no_terminology_finding(
    evaluate_ir, rule_id, ir_name, policy_name
) -> None:
    """Spec 21.1 and 21.3: both conforming examples use one canonical term throughout."""
    result = evaluate_ir(ir_name, policy_name)[rule_id]
    assert result.findings == ()
    assert result.status is CLEAN_ASSESS_STATUS[rule_id]


# -- ATS-TERM-001 -----------------------------------------------------------


def test_term_001_fails_when_a_material_claim_uses_a_deprecated_alias(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 10.2 and 10.3: the vocabulary comes from the artifact's own glossary."""
    document = mutated_ir("assess_conforming")
    document["glossary"][0]["deprecated_aliases"] = ["acceptance core"]
    document["sections"][0]["claims"][1]["proposition"] = (
        "The acceptance core will remain substantially stable during the migration."
    )

    result = evaluate_document(document, "assess")["ATS-TERM-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["deprecated-alias-used"]
    assert str(result.decision_power) == "detects_violations"
    finding = result.findings[0]
    assert "acceptance core" in finding.summary
    assert "acceptance kernel" in finding.summary
    # Section 13.3: the glossary entry that grounds the finding is cited.
    assert finding.evidence_spans[0]["locator"] == "/glossary"


def test_term_001_fails_when_two_concepts_claim_one_canonical_term(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 10.2: one term cannot denote several concepts within one scope."""
    document = mutated_ir("assess_conforming")
    duplicate = dict(document["glossary"][0])
    duplicate["concept_id"] = "acceptance-kernel-alias"
    duplicate["definition"] = "A second concept claiming the same canonical term."
    document["glossary"].append(duplicate)

    result = evaluate_document(document, "assess")["ATS-TERM-001"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["canonical-term-collision"]


def test_term_001_ignores_an_alias_that_appears_in_no_material_claim(
    mutated_ir, evaluate_document
) -> None:
    """Spec 10.2 governs the text, not the glossary's own alias list."""
    document = mutated_ir("assess_conforming")
    document["glossary"][0]["deprecated_aliases"] = ["acceptance core"]
    result = evaluate_document(document, "assess")["ATS-TERM-001"]
    assert result.findings == ()


# -- ATS-TERM-002 -----------------------------------------------------------


def test_term_002_is_unavailable_because_the_source_text_is_absent(
    ctx, evaluate_ir
) -> None:
    """Spec 10.4: deciding substitution requires the text the output came from."""
    result = evaluate_ir("assess_conforming", "assess")["ATS-TERM-002"]
    assert result.status is Status.UNAVAILABLE
    assert result.missing_inputs == ("source_text",)
    assert "source_text" in ctx.registry.get("ATS-TERM-002").required_inputs
    assert result.findings == ()
    assert str(result.decision_power) == "undecidable"
    assert result.detector.authority != "conformance_evidence"


# -- ATS-TERM-003 -----------------------------------------------------------


def test_term_003_fails_on_an_unexpanded_acronym_at_first_material_use(
    mutated_ir, evaluate_document, issue_codes
) -> None:
    """Spec 10.5: an acronym must be expanded in place or permitted by policy."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][1]["proposition"] = (
        "The migration keeps the existing FFI boundary unchanged."
    )
    result = evaluate_document(document, "assess")["ATS-TERM-003"]
    assert result.status is Status.FAIL
    assert issue_codes(result) == ["acronym-not-expanded"]
    assert "FFI" in result.findings[0].summary


def test_term_003_accepts_an_in_place_expansion(mutated_ir, evaluate_document) -> None:
    """Spec 10.5: `Expansion (ACR)` is the canonical in-place form."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][1]["proposition"] = (
        "The migration keeps the existing foreign function interface (FFI) boundary unchanged."
    )
    result = evaluate_document(document, "assess")["ATS-TERM-003"]
    assert result.findings == ()
    assert result.status is Status.REVIEW_REQUIRED


def test_term_003_accepts_an_approved_abbreviation(mutated_ir, evaluate_document) -> None:
    """Spec 10.5: the glossary may declare the abbreviation as approved."""
    document = mutated_ir("assess_conforming")
    document["glossary"][0]["approved_abbreviations"] = ["FFI"]
    document["sections"][0]["claims"][1]["proposition"] = (
        "The migration keeps the existing FFI boundary unchanged."
    )
    result = evaluate_document(document, "assess")["ATS-TERM-003"]
    assert result.findings == ()


def test_term_003_does_not_treat_the_deontic_vocabulary_as_an_acronym(
    ctx, evaluate_ir
) -> None:
    """Spec 1.3 and 8.16: MUST is an ATS-1 keyword, not an audience acronym."""
    assert "MUST" in ctx.lexicon.deontic_surfaces.values()
    result = evaluate_ir("specify_conforming", "specify")["ATS-TERM-003"]
    assert result.findings == ()


def test_term_003_reports_only_the_first_material_use(
    mutated_ir, evaluate_document
) -> None:
    """Spec 10.5 attaches the obligation to the first material use, not to every use."""
    document = mutated_ir("assess_conforming")
    document["sections"][0]["claims"][1]["proposition"] = "The FFI boundary is unchanged."
    document["sections"][0]["claims"][2]["proposition"] = "The FFI boundary is out of scope."
    result = evaluate_document(document, "assess")["ATS-TERM-003"]
    assert len(result.findings) == 1


def test_term_003_does_not_flag_the_deontic_negative_marker(
    mutated_ir, evaluate_document_d2
) -> None:
    """Regression: 'NOT' inside a canonical surface such as 'MUST NOT' is
    closed deontic vocabulary, not an unexpanded audience acronym. Without the
    fix the mechanical dimension hard-FAILs on the word NOT."""
    document = mutated_ir("ats-coord-001-declared")
    claim = document["sections"][0]["claims"][0]
    claim["proposition"] = (
        "The gateway MUST NOT delete messages with an outstanding delivery attempt."
    )
    claim["force"] = {"deontic": "MUST_NOT"}
    result = evaluate_document_d2(document, "draft2")["ATS-TERM-003"]
    assert result.findings == ()

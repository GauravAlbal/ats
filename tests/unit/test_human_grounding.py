"""Human-grounding minimization (draft.2 contract D-I).

The draft.2 model treats human grounding as exceptional: nonessential
unknowns stay unknown, an ambiguity that blocks action surfaces as a
REVIEW_REQUIRED signal instead of a silent answer, explicit author intent
resolves the ambiguity, and absence is never converted into an answer
(ADR-0002: no PASS-by-absence). These tests drive small synthetic IR
documents through the full 36-rule draft.2 detector registry and the
planning projection, and assert that behaviour on the authority, basis, and
modality axes.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ats.planning import project_from_ir
from ats.rules.results import Status

DRAFT2_POLICY = "draft2"

#: The content hash of the synthetic source artifact the projection binds.
SHA = "9" * 64


def _ir(artifact_id: str, section: dict[str, Any]) -> dict[str, Any]:
    """A minimal schema-valid draft.2 TextIR document around one section."""
    return {
        "schema_version": "ats.text_ir.v1",
        "artifact_id": artifact_id,
        "source": {
            "content_sha256": SHA,
            "normalized_sha256": SHA,
            "media_type": "text/plain",
            "locator": f"{artifact_id}.txt",
        },
        "policy_snapshot_id": "policy-fixture-draft2",
        "language": "en",
        "audience": {"expertise": "expert"},
        "sections": [section],
        "extraction_status": "complete",
    }


def _requirement_claim(
    claim_id: str,
    *,
    proposition: str,
    actor: str,
    deontic: str,
    action: str,
    object_: str,
    authority: str = "acceptance kernel",
    **extra: Any,
) -> dict[str, Any]:
    """One locally closed requirement claim; ``extra`` merges over it."""
    claim: dict[str, Any] = {
        "claim_id": claim_id,
        "role": "requirement",
        "proposition": proposition,
        "material": True,
        "polarity": "positive",
        "status": "asserted",
        "requirement": {
            "requirement_id": claim_id,
            "actor": actor,
            "deontic": deontic,
            "action": action,
            "object": object_,
            "source_authority": authority,
        },
    }
    claim.update(extra)
    return claim


# -- §35.7: missing nonessential precedence ---------------------------------


def test_missing_precedence_does_not_block_or_invent(
    ctx_d2, evaluate_document_d2, load_policy
) -> None:
    """§35.7: UNAVAILABLE authority basis with no precedence raises no question.

    The authority axis must neither block the artifact nor invent a hierarchy:
    BASIS-001 is advisory-level (review_required class, advisory SPECIFY state,
    never FAIL), and the planning projection omits ``precedence`` rather than
    strengthening UNAVAILABLE source material into an explicit answer.
    """
    document = _ir(
        "hg-precedence-unavailable",
        {
            "section_id": "s1",
            "heading": "hg-precedence-unavailable",
            "profiles": ["SPECIFY"],
            "claims": [
                _requirement_claim(
                    "REQ-HG-1",
                    proposition="The verifier MUST reject a stale receipt before settlement.",
                    actor="verifier",
                    deontic="MUST",
                    action="reject",
                    object_="a stale receipt",
                    semantic_basis={
                        "basis": "UNAVAILABLE",
                        "rationale": "No authoritative source states the authority hierarchy.",
                    },
                )
            ],
            "evidence": [],
            "relations": [],
            "update_indicators": [],
        },
    )

    # BASIS-001 is advisory on the SPECIFY axis, not a block.
    rule = ctx_d2.registry.get("ATS-BASIS-001")
    assert rule.raw["operational_class"] == "review_required"
    assert rule.default_states["SPECIFY"] == "advisory"

    results = evaluate_document_d2(document, DRAFT2_POLICY)
    basis = results["ATS-BASIS-001"]
    assert basis.findings == ()  # the basis is declared: nothing to flag
    assert basis.status is not Status.FAIL
    assert basis.status is Status.REVIEW_REQUIRED  # D3 cannot conclude from silence
    assert basis.blocks_conformance is False  # advisory axis never blocks

    # The projection omits precedence rather than inventing an authority order.
    projection = project_from_ir(ctx_d2, document, load_policy(DRAFT2_POLICY), artifact_sha256=SHA)
    assert projection["authority"] == [
        {"source_id": "REQ-HG-1", "authority": "acceptance kernel"}
    ]
    assert all("precedence" not in record for record in projection["authority"])


# -- §35.7: missing nonessential confidence stays UNAVAILABLE ----------------


def test_unavailable_confidence_stays_unavailable(ctx_d2, evaluate_document_d2) -> None:
    """§35.7: a claim with basis UNAVAILABLE keeps it through the detector path.

    ATS-BASIS-002 only blocks silent promotion of INFERRED/UNAVAILABLE source
    material into an EXPLICIT source-authoritative fact; a claim that declares
    UNAVAILABLE stays UNAVAILABLE (decided PASS, zero findings) and the IR is
    never rewritten to a stronger value.
    """
    document = _ir(
        "hg-confidence-unavailable",
        {
            "section_id": "s1",
            "heading": "hg-confidence-unavailable",
            "profiles": ["TRANSFORM"],
            "claims": [
                {
                    "claim_id": "OUT-HG-1",
                    "role": "judgment",
                    "proposition": (
                        "The acceptance kernel is likely to reject stale-policy transitions (55-80%)."
                    ),
                    "material": True,
                    "polarity": "positive",
                    "status": "asserted",
                    "semantic_basis": {
                        "basis": "UNAVAILABLE",
                        "rationale": "The source records no confidence for the band.",
                    },
                    "source_refs": ["EV-HG-1"],
                    "extensions": {"source_basis": {"EV-HG-1": "UNAVAILABLE"}},
                }
            ],
            "evidence": [
                {
                    "evidence_id": "EV-HG-1",
                    "proposition": "Audit entries show rejections clustering around stale-policy transitions.",
                    "source": {
                        "source_id": "src-EV-HG-1",
                        "source_type": "synthetic_fixture",
                        "availability": "present",
                        "locator": "EV-HG-1.txt",
                    },
                    "availability": "present",
                }
            ],
            "relations": [],
            "update_indicators": [],
        },
    )

    results = evaluate_document_d2(document, DRAFT2_POLICY)
    basis002 = results["ATS-BASIS-002"]
    assert basis002.status is Status.PASS  # decided: no promotion
    assert basis002.findings == ()
    assert str(basis002.decision_power) == "decides"

    # The basis value is never promoted or rewritten by the detector path.
    claim = document["sections"][0]["claims"][0]
    assert claim["semantic_basis"]["basis"] == "UNAVAILABLE"
    assert claim["extensions"]["source_basis"]["EV-HG-1"] == "UNAVAILABLE"


# -- §35.7: action-blocking ambiguous modality -------------------------------


def test_action_blocking_ambiguous_modality_is_never_a_silent_pass(
    evaluate_document_d2,
) -> None:
    """§35.7: force ambiguity (absent deontic, alternatives recorded) -> review.

    A material requirement in a SPECIFY unit whose represented modality is
    absent or ambiguous must not resolve silently: ATS-DEON-001 raises a
    requirement-without-deontic-force finding, and ATS-CLOSE-001's closure
    check reports REVIEW_REQUIRED on the unit — never a silent PASS.
    """
    document = _ir(
        "hg-force-ambiguity",
        {
            "section_id": "s1",
            "heading": "hg-force-ambiguity",
            "profiles": ["SPECIFY"],
            "claims": [
                _requirement_claim(
                    "REQ-HG-2",
                    proposition="The adjudicator SHOULD confirm a quorum first.",
                    actor="adjudicator",
                    deontic="SHOULD",
                    action="confirm",
                    object_="a quorum",
                    authority="adjudication charter",
                    # The represented modality is absent; the ambiguity is
                    # recorded, not resolved: two live candidate forces.
                    force={},
                    extensions={"requirement_force": {"alternatives": ["SHOULD", "MUST"]}},
                )
            ],
            "evidence": [],
            "relations": [],
            "update_indicators": [],
        },
    )

    results = evaluate_document_d2(document, DRAFT2_POLICY)

    # ATS-DEON-001: obligation strength is a represented slot, not an inference.
    deon = results["ATS-DEON-001"]
    assert deon.status is not Status.PASS
    assert {f.issue_code for f in deon.findings} == {"requirement-without-deontic-force"}

    # ATS-CLOSE-001: the slot fields are present, but closure cannot conclude
    # from a clean run — REVIEW_REQUIRED, never PASS (detects_violations power).
    # (The presence subchecks may PASS individually: they are exact mechanical
    # checks. The rule-level conclusion is what never reports PASS.)
    close = results["ATS-CLOSE-001"]
    assert close.status is Status.REVIEW_REQUIRED
    assert close.findings == ()


def test_explicit_author_intent_resolves_the_ambiguity(evaluate_document_d2) -> None:
    """§35.7: the same unit with EXPLICIT basis + declared deontic resolves.

    Explicit author intent — a declared deontic force whose surface appears in
    the proposition, and a semantic_basis of EXPLICIT — leaves no finding on
    the modality or basis axis: ATS-DEON-001 decides PASS and BASIS-001 and
    ATS-CLOSE-001 raise nothing.
    """
    document = _ir(
        "hg-force-explicit",
        {
            "section_id": "s1",
            "heading": "hg-force-explicit",
            "profiles": ["SPECIFY"],
            "claims": [
                _requirement_claim(
                    "REQ-HG-3",
                    proposition="The adjudicator MUST confirm a quorum first.",
                    actor="adjudicator",
                    deontic="MUST",
                    action="confirm",
                    object_="a quorum",
                    authority="adjudication charter",
                    force={"deontic": "MUST"},
                    semantic_basis={
                        "basis": "EXPLICIT",
                        "rationale": "The charter states the obligation directly.",
                    },
                )
            ],
            "evidence": [],
            "relations": [],
            "update_indicators": [],
        },
    )

    results = evaluate_document_d2(document, DRAFT2_POLICY)

    deon = results["ATS-DEON-001"]
    assert deon.status is Status.PASS  # declared canonical force, surface present
    assert deon.findings == ()

    basis = results["ATS-BASIS-001"]
    assert basis.findings == ()

    close = results["ATS-CLOSE-001"]
    assert close.findings == ()


# -- §35.7: absence is never converted into an answer ------------------------


def test_absence_is_never_silently_converted_to_an_answer(evaluate_document_d2) -> None:
    """§35.7: no basis and no materiality -> no claim anywhere, never a PASS.

    A non-material claim declares no basis; nothing may promote it. BASIS-001
    must report REVIEW_REQUIRED with a NOT_APPLICABLE material-claim subcheck
    (never PASS by absence), BASIS-002 stays UNAVAILABLE without a source
    ledger, and the IR is not rewritten to carry an EXPLICIT value.
    """
    document = _ir(
        "hg-absence",
        {
            "section_id": "s1",
            "heading": "hg-absence",
            "profiles": ["ASSESS"],
            "claims": [
                {
                    "claim_id": "OBS-HG-1",
                    "role": "observation",
                    "proposition": "The audit log records transitions.",
                    "material": False,  # non-material: no material value to declare
                    "polarity": "positive",
                    "status": "asserted",
                }
            ],
            "evidence": [],
            "relations": [],
            "update_indicators": [],
        },
    )

    assert "EXPLICIT" not in json.dumps(document)

    results = evaluate_document_d2(document, DRAFT2_POLICY)

    basis001 = results["ATS-BASIS-001"]
    assert basis001.findings == ()
    assert basis001.status is Status.REVIEW_REQUIRED  # never PASS by absence
    assert {record["status"] for record in basis001.subchecks} == {"NOT_APPLICABLE"}

    basis002 = results["ATS-BASIS-002"]
    assert basis002.status is Status.UNAVAILABLE  # no source side, no comparison
    assert tuple(basis002.missing_inputs) == ("source_ir", "output_ir")

    # No detector anywhere fabricated an explicit claim or a promotion finding.
    assert "EXPLICIT" not in json.dumps(document)
    for rule_id, result in results.items():
        issue_codes = {f.issue_code for f in result.findings}
        assert "inferred-source-promoted-to-explicit" not in issue_codes, rule_id

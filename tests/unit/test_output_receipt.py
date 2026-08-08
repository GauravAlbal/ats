"""Candidate receipts and receipt verification.

Section 14.11 assigns final semantic acceptance to an authorized human or a
governed external system, and Section 13.7 forbids a component from adjudicating
its own finding. Section 16.12 requires a receipt to be re-checkable against the
artifacts it binds, and Section 15.8 makes a claim stale when the policy moves.
"""

from __future__ import annotations

import copy

import pytest

from ats.canonical import seal, sha256_hex, verify_seal
from ats.errors import UsageError
from ats.ir.model import IrDocument
from ats.output.receipt import SELF_IDENTITIES, build_candidate_receipt, verify_receipt

ADJUDICATOR = "arq-acceptance-authority"


@pytest.fixture(scope="module")
def bundle(load_bundle):
    return load_bundle("assess-bundle")


@pytest.fixture(scope="module")
def ir(load_ir):
    return IrDocument.from_document(load_ir("assess_conforming"))


@pytest.fixture(scope="module")
def policy(ctx, load_policy):
    return ctx.policy(load_policy("assess"))


# -- build_candidate_receipt ------------------------------------------------


def test_a_candidate_receipt_is_sealed_valid_and_bound(
    ctx, ir, policy, bundle, assert_valid
) -> None:
    """Spec 14.13 and Appendix C: the receipt binds the artifacts and addresses itself."""
    output_sha = sha256_hex(bundle["output_path"].read_bytes())
    receipt = build_candidate_receipt(
        ctx,
        ir=ir,
        policy=policy,
        output_sha256=output_sha,
        lint_report=bundle["lint"],
        adjudicator=ADJUDICATOR,
    )
    assert_valid(receipt, "ats_acceptance_receipt_v1.schema.json")
    ok, declared, recomputed = verify_seal(receipt)
    assert ok and declared == recomputed

    assert receipt["standard"] == "ATS-1"
    assert receipt["spec_version"] == ctx.spec_version
    assert receipt["source_sha256"] == ir.source["content_sha256"]
    assert receipt["output_sha256"] == output_sha
    assert receipt["policy_snapshot_id"] == policy.snapshot_id
    assert receipt["policy_snapshot_sha256"] == policy.declared_sha256
    assert receipt["adjudicator"] == ADJUDICATOR
    assert receipt["created_at"] == ctx.timestamp()
    assert receipt["conformance"] == bundle["lint"]["conformance"]


def test_a_candidate_receipt_records_undispositioned_work_as_unresolved(
    ctx, ir, policy, bundle
) -> None:
    """Spec 15.3: a surfaced finding is unresolved until an authority disposes of it."""
    receipt = build_candidate_receipt(
        ctx,
        ir=ir,
        policy=policy,
        output_sha256=None,
        lint_report=bundle["lint"],
        adjudicator=ADJUDICATOR,
    )
    review_required = bundle["lint"]["summary"]["by_status"]["REVIEW_REQUIRED"]
    semantic = receipt["semantic_summary"]
    assert semantic["proposed"] == review_required
    assert semantic["unresolved"] == review_required
    assert semantic["accepted"] == 0
    assert semantic["rejected"] == 0
    assert semantic["waived"] == 0
    assert "output_sha256" not in receipt


@pytest.mark.parametrize("adjudicator", sorted(SELF_IDENTITIES) + ["  ATS  ", "Self"])
def test_the_implementation_refuses_to_name_itself_as_adjudicator(
    ctx, ir, policy, bundle, adjudicator
) -> None:
    """Spec 13.7 and 14.11: acceptance authority must be external."""
    with pytest.raises(UsageError, match="adjudicating its own findings"):
        build_candidate_receipt(
            ctx,
            ir=ir,
            policy=policy,
            output_sha256=None,
            lint_report=bundle["lint"],
            adjudicator=adjudicator,
        )


def test_optional_reference_lists_are_carried_through(ctx, ir, policy, bundle) -> None:
    """Spec 13.6 and 14.13: the receipt records what it supersedes and cites."""
    receipt = build_candidate_receipt(
        ctx,
        ir=ir,
        policy=policy,
        output_sha256=None,
        lint_report=bundle["lint"],
        adjudicator=ADJUDICATOR,
        finding_refs=["f-1"],
        adjudication_refs=["adj-1"],
        supersedes=["candidate:old"],
    )
    assert receipt["finding_refs"] == ["f-1"]
    assert receipt["adjudication_refs"] == ["adj-1"]
    assert receipt["supersedes"] == ["candidate:old"]


# -- verify_receipt ---------------------------------------------------------


def test_verify_receipt_passes_on_the_conforming_bundle(
    ctx, bundle, load_ir, policy
) -> None:
    """Spec 16.12: a receipt must be reproducible from the artifacts it binds."""
    result = verify_receipt(
        ctx,
        bundle["receipt"],
        ir_document=load_ir("assess_conforming"),
        output_sha256=sha256_hex(bundle["output_path"].read_bytes()),
        policy=policy,
    )
    assert result["status"] == "PASS"
    assert result["declared_sha256"] == result["recomputed_sha256"]
    assert result["unreplayable"] == []


def test_verify_receipt_detects_a_tampered_self_hash(ctx, bundle) -> None:
    """Appendix C: the receipt's own address must recompute from its bytes."""
    tampered = {**copy.deepcopy(bundle["receipt"]), "adjudicator": "someone-else"}
    result = verify_receipt(ctx, tampered)
    assert result["status"] == "FAIL"
    assert "does not match its canonical bytes" in result["detail"]
    assert result["declared_sha256"] != result["recomputed_sha256"]


def test_verify_receipt_detects_a_stale_policy_hash(ctx, bundle, load_policy) -> None:
    """Spec 15.8: a receipt bound to a superseded policy MUST be re-evaluated."""
    receipt = seal({**copy.deepcopy(bundle["receipt"]), "policy_snapshot_sha256": "0" * 64})
    result = verify_receipt(ctx, receipt, policy_document=load_policy("assess"))
    assert result["status"] == "FAIL"
    assert "Section 15.8" in result["detail"]


def test_verify_receipt_detects_a_policy_identity_change(
    ctx, bundle, load_policy
) -> None:
    """Spec 6.6: the snapshot identity is part of what the receipt binds."""
    result = verify_receipt(
        ctx, bundle["receipt"], policy_document=load_policy("specify")
    )
    assert result["status"] == "FAIL"
    assert "policy-fixture-specify" in result["detail"]


def test_verify_receipt_detects_a_mismatched_source_hash(
    ctx, bundle, load_ir
) -> None:
    """Spec 14.2: the receipt is a claim about specific source bytes."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["source"]["content_sha256"] = "a" * 64
    result = verify_receipt(ctx, bundle["receipt"], ir_document=document)
    assert result["status"] == "FAIL"
    assert "receipt binds source" in result["detail"]


def test_verify_receipt_detects_a_mismatched_output_hash(ctx, bundle) -> None:
    """Spec 14.13: the receipt names the rendering it was issued for."""
    result = verify_receipt(ctx, bundle["receipt"], output_sha256="b" * 64)
    assert result["status"] == "FAIL"
    assert "the document hashes to" in result["detail"]


def test_verify_receipt_detects_a_spec_version_change(ctx, bundle) -> None:
    """Spec 19.1: conformance is claimed against one specification version."""
    receipt = seal({**copy.deepcopy(bundle["receipt"]), "spec_version": "1.0.0-draft.0"})
    result = verify_receipt(ctx, receipt)
    assert result["status"] == "FAIL"
    assert "1.0.0-draft.0" in result["detail"]


def test_verify_receipt_rejects_a_self_naming_adjudicator(ctx, bundle) -> None:
    """Spec 13.7: a component cannot be the authority for its own finding."""
    receipt = seal({**copy.deepcopy(bundle["receipt"]), "adjudicator": "ats-output-linter"})
    result = verify_receipt(ctx, receipt)
    assert result["status"] == "FAIL"
    assert "acceptance authority must be external" in result["detail"]


def test_verify_receipt_reports_an_unreplayable_semantic_pass(ctx, bundle) -> None:
    """Spec 16.12: a dimension this implementation cannot reproduce is UNAVAILABLE."""
    receipt = copy.deepcopy(bundle["receipt"])
    receipt["conformance"]["semantic_review"] = "PASS"
    result = verify_receipt(ctx, seal(receipt))
    assert result["status"] == "UNAVAILABLE"
    assert result["unreplayable"]
    assert "historical evidence only" in result["unreplayable"][0]


def test_verify_receipt_reports_an_unreplayable_preservation_pass(ctx, bundle) -> None:
    """Spec 15.4: no source-to-output comparison is reproducible from these artifacts."""
    receipt = copy.deepcopy(bundle["receipt"])
    receipt["conformance"]["preservation"] = "PASS"
    result = verify_receipt(ctx, seal(receipt))
    assert result["status"] == "UNAVAILABLE"
    assert any("preservation" in reason for reason in result["unreplayable"])


def test_verify_receipt_rejects_a_schema_invalid_receipt(ctx, bundle) -> None:
    """Spec 19.4: a receipt that is not a valid object is not evaluated further."""
    broken = copy.deepcopy(bundle["receipt"])
    del broken["conformance"]
    result = verify_receipt(ctx, broken)
    assert result["status"] == "FAIL"
    assert "conformance" in result["detail"]

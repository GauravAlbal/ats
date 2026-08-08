"""Draft.2 output lint checks: OUT-COORD-PRESERVED and OUT-BASIS-NOT-STRENGTHENED.

Both checks are structural OUT-* checks gated into the mechanical dimension
only when the IR declares the surfaces they protect (draft.2 D-C/D-F): a
``stable_coordinates`` block and ``semantic_basis`` declarations respectively.
The gating runs through the check's ``required`` flag (GATED_MECHANICAL_CHECKS)
because ``MECHANICAL_CHECKS`` itself stays a static frozenset for draft.1
parity. These tests drive the full ``lint_output`` seam against a draft.2
context, so report-schema validity and conformance gating are exercised too.
"""

from __future__ import annotations

import copy
import datetime as _dt

import pytest

from ats.canonical import content_hash
from ats.context import Context
from ats.ir.model import IrDocument
from ats.output.lint import lint_output
from ats.output.parse import parse_markdown
from ats.output.trace import build_trace

FIXED_NOW = _dt.datetime(2026, 8, 3, tzinfo=_dt.UTC)

COORD = "OUT-COORD-PRESERVED"
BASIS = "OUT-BASIS-NOT-STRENGTHENED"

_SOURCE = {
    "content_sha256": "1" * 64,
    "media_type": "text/plain",
    "locator": "draft2-outlint.txt",
}


@pytest.fixture(scope="module")
def ctx_d2() -> Context:
    """The draft.2 evaluation context (36 rules), on the fixed evaluation clock."""
    return Context.load(spec_version="1.0.0-draft.2", now=FIXED_NOW)


@pytest.fixture(scope="module")
def draft2_policy(ctx_d2, load_policy):
    """A policy fixture rebound to the draft.2 edition, hash recomputed."""

    def _load(name: str) -> dict:
        document = copy.deepcopy(load_policy(name))
        document["spec_version"] = "1.0.0-draft.2"
        document["snapshot_sha256"] = content_hash(
            document, exclude={"snapshot_sha256"}
        )
        return document

    return _load


def _ir_document(claims, *, coordinates=(), basis_policy=None, profiles=("TRANSFORM",)):
    """A schema-valid draft.2 TextIR with the given claims and optional blocks."""
    document = {
        "schema_version": "ats.text_ir.v1",
        "artifact_id": "draft2-outlint",
        "source": dict(_SOURCE),
        "policy_snapshot_id": "policy-fixture-assess-transform",
        "language": "en",
        "audience": {"audience_id": "draft2-outlint", "expertise": "expert"},
        "sections": [
            {
                "section_id": "s1",
                "heading": "draft.2 output lint",
                "profiles": list(profiles),
                "claims": list(claims),
                "evidence": [],
                "relations": [],
                "update_indicators": [],
            }
        ],
        "extraction_status": "complete",
    }
    if coordinates:
        document["stable_coordinates"] = [dict(c) for c in coordinates]
    if basis_policy:
        document["basis_policy"] = dict(basis_policy)
    return document


def _lint(ctx, policy_document, ir_document, text, block_metadata, tmp_path):
    """Run the full output lint seam; returns ``check_id -> check`` plus the report."""
    ir = IrDocument.from_document(ir_document)
    parsed = parse_markdown(text)
    trace_document = build_trace(
        ctx,
        ir=ir,
        parsed=parsed,
        output_bytes=text.encode("utf-8"),
        policy_snapshot_id=policy_document["snapshot_id"],
        policy_sha256=policy_document["snapshot_sha256"],
        block_metadata=block_metadata,
        renderer={"name": "draft2-outlint-test", "version": "0"},
    )
    target = tmp_path / "document.md"
    target.write_text(text, encoding="utf-8")
    report = lint_output(
        ctx,
        output_path=target,
        trace_document=trace_document,
        ir_document=ir_document,
        policy_document=policy_document,
    )
    return {c["check_id"]: c for c in report["checks"]}, report


def _block(display_role="requirement", *, material=True, claim_ids=(), requirement_ids=(), coordinates=()):
    return {
        "display_role": display_role,
        "section_id": "s1",
        "material": material,
        "claim_ids": list(claim_ids),
        "requirement_ids": list(requirement_ids),
        **({"coordinates": list(coordinates)} if coordinates else {}),
    }


def _requirement_claim(claim_id, *, deontic="MUST", proposition=None, basis=None):
    claim = {
        "claim_id": claim_id,
        "role": "requirement",
        "proposition": proposition or f"The verifier {deontic} reject the receipt.",
        "material": True,
        "polarity": "positive",
        "status": "asserted",
        "requirement": {
            "requirement_id": claim_id,
            "actor": "verifier",
            "deontic": deontic,
            "action": "reject",
            "object": "the receipt",
            "source_authority": "acceptance kernel",
        },
    }
    if basis:
        claim["semantic_basis"] = {"basis": basis}
    return claim


def _plain_claim(claim_id, proposition, *, basis=None, likelihood=None):
    claim = {
        "claim_id": claim_id,
        "role": "judgment",
        "proposition": proposition,
        "material": True,
        "polarity": "positive",
        "status": "asserted",
    }
    if basis:
        claim["semantic_basis"] = {"basis": basis}
    if likelihood:
        claim["force"] = {"likelihood": likelihood}
    return claim


def _coordinate(kind, cid, pointer="#/sections/0/claims/0"):
    return {"kind": kind, "id": cid, "source_pointer": pointer}


# -- OUT-COORD-PRESERVED -----------------------------------------------------


def test_out_coord_preserved_fails_when_a_coordinate_is_dropped(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.17: a declared coordinate must appear in at least one block's references."""
    ir_document = _ir_document(
        [_plain_claim("c1", "The kernel stays stable.")],
        coordinates=[_coordinate("work_item_id", "WI-42")],
    )
    text = "<!-- ats:block b1 -->\nThe kernel stays stable.\n"
    checks, _ = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(display_role="key_judgment", claim_ids=["c1"])},
        tmp_path,
    )
    check = checks[COORD]
    assert check["status"] == "FAIL"
    assert "WI-42" in check["detail"]
    assert "dropped" in check["detail"]
    assert check["required"] is True


def test_out_coord_preserved_fails_when_a_coordinate_is_altered(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.17: a block referencing id X whose text renders X' is altered."""
    ir_document = _ir_document(
        [_plain_claim("c1", "The kernel stays stable.")],
        coordinates=[_coordinate("work_item_id", "WI-42")],
    )
    text = "<!-- ats:block b1 -->\nThe kernel tracks WI-43 for the migration.\n"
    checks, _ = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(display_role="key_judgment", claim_ids=["c1"], coordinates=["WI-42"])},
        tmp_path,
    )
    check = checks[COORD]
    assert check["status"] == "FAIL"
    assert "WI-42" in check["detail"]
    assert "does not contain the exact id string" in check["detail"]


def test_out_coord_preserved_passes_when_the_coordinate_renders_exactly(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.17: referenced and byte-identical in the block body is preserved."""
    ir_document = _ir_document(
        [_plain_claim("c1", "The kernel tracks WI-42.")],
        coordinates=[_coordinate("work_item_id", "WI-42")],
    )
    text = "<!-- ats:block b1 -->\nThe kernel tracks WI-42 for the migration.\n"
    checks, _ = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(display_role="key_judgment", claim_ids=["c1"], coordinates=["WI-42"])},
        tmp_path,
    )
    assert checks[COORD]["status"] == "PASS"


def test_out_coord_preserved_passes_via_claim_ids_when_coordinate_equals_claim_id(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.17: a coordinate that is also a claim id survives via claim_ids."""
    ir_document = _ir_document(
        [_requirement_claim("REQ-1", proposition="The verifier MUST reject the receipt. REQ-1")],
        coordinates=[_coordinate("requirement_id", "REQ-1")],
    )
    text = "<!-- ats:block b1 -->\nThe verifier MUST reject the receipt. REQ-1\n"
    checks, _ = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(requirement_ids=["REQ-1"])},
        tmp_path,
    )
    assert checks[COORD]["status"] == "PASS"


def test_out_coord_preserved_is_not_applicable_without_a_block(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.17: no stable_coordinates block means no coordinate to preserve."""
    ir_document = _ir_document([_plain_claim("c1", "The kernel stays stable.")])
    text = "<!-- ats:block b1 -->\nThe kernel stays stable.\n"
    checks, report = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(display_role="key_judgment", claim_ids=["c1"])},
        tmp_path,
    )
    check = checks[COORD]
    assert check["status"] == "NOT_APPLICABLE"
    assert check["required"] is False
    # Absence of the block must not gate the mechanical dimension.
    assert report["conformance"]["mechanical"] == "PASS"


def test_out_coord_preserved_failure_gates_mechanical(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 15.1: a declared coordinate that is dropped blocks the dimension."""
    ir_document = _ir_document(
        [_plain_claim("c1", "The kernel stays stable.")],
        coordinates=[_coordinate("work_item_id", "WI-42")],
    )
    text = "<!-- ats:block b1 -->\nThe kernel stays stable.\n"
    checks, report = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(display_role="key_judgment", claim_ids=["c1"])},
        tmp_path,
    )
    assert checks[COORD]["status"] == "FAIL"
    assert report["conformance"]["mechanical"] == "FAIL"
    assert COORD in report["conformance_rationale"]["mechanical"]


# -- OUT-BASIS-NOT-STRENGTHENED ----------------------------------------------


def test_out_basis_fails_when_should_is_rendered_as_must(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.19: SHOULD -> MUST is a decided strengthening (directive 35.4)."""
    ir_document = _ir_document(
        [_requirement_claim("REQ-1", deontic="SHOULD", basis="INFERRED")]
    )
    text = "<!-- ats:block b1 -->\nThe verifier MUST reject the receipt. REQ-1\n"
    checks, _ = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(requirement_ids=["REQ-1"])},
        tmp_path,
    )
    check = checks[BASIS]
    assert check["status"] == "FAIL"
    assert "SHOULD" in check["detail"]
    assert "MUST" in check["detail"]


def test_out_basis_fails_when_may_is_rendered_as_must(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.19: MAY -> MUST is a decided strengthening (directive 35.4)."""
    ir_document = _ir_document(
        [_requirement_claim("REQ-1", deontic="MAY", basis="INFERRED")]
    )
    text = "<!-- ats:block b1 -->\nThe verifier MUST reject the receipt. REQ-1\n"
    checks, _ = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(requirement_ids=["REQ-1"])},
        tmp_path,
    )
    check = checks[BASIS]
    assert check["status"] == "FAIL"
    assert "MAY" in check["detail"]


def test_out_basis_fails_on_wep_band_mutation(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.19: a band rendered with a different canonical phrase is decided."""
    likelihood = {
        "kind": "wep",
        "term": "likely",
        "display": "likely (55\u201380%)",
        "lower": 0.55,
        "upper": 0.8,
        "range_shown_inline": True,
    }
    ir_document = _ir_document(
        [
            _plain_claim(
                "c1",
                "The migration is likely to reduce defects.",
                basis="INFERRED",
                likelihood=likelihood,
            )
        ]
    )
    text = "<!-- ats:block b1 -->\nThe migration is very likely to reduce defects.\n"
    checks, _ = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(display_role="key_judgment", claim_ids=["c1"])},
        tmp_path,
    )
    check = checks[BASIS]
    assert check["status"] == "FAIL"
    assert "likely" in check["detail"]
    assert "very likely" in check["detail"]


def test_out_basis_fails_on_wep_band_numeric_bounds_mutation(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.19: a numeric probability range with different bounds is decided."""
    likelihood = {
        "kind": "wep",
        "term": "likely",
        "display": "likely (55\u201380%)",
        "lower": 0.55,
        "upper": 0.8,
        "range_shown_inline": True,
    }
    ir_document = _ir_document(
        [
            _plain_claim(
                "c1",
                "The migration is likely to reduce defects.",
                basis="INFERRED",
                likelihood=likelihood,
            )
        ]
    )
    text = "<!-- ats:block b1 -->\nThe migration is likely (80\u201395%) to reduce defects.\n"
    checks, _ = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(display_role="key_judgment", claim_ids=["c1"])},
        tmp_path,
    )
    check = checks[BASIS]
    assert check["status"] == "FAIL"
    assert "different bounds" in check["detail"]


def test_out_basis_fails_when_unknown_is_rendered_as_known(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.19: a claim with basis UNAVAILABLE rendered as settled is decided."""
    ir_document = _ir_document(
        [_plain_claim("c1", "The kernel may reject stale receipts.", basis="UNAVAILABLE")]
    )
    text = "<!-- ats:block b1 -->\nThe kernel MUST reject stale receipts.\n"
    checks, _ = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(display_role="key_judgment", claim_ids=["c1"])},
        tmp_path,
    )
    check = checks[BASIS]
    assert check["status"] == "FAIL"
    assert "UNAVAILABLE" in check["detail"]
    assert "settled" in check["detail"]


def test_out_basis_passes_when_the_declared_force_is_preserved(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.19: rendering the claim's own force with an EXPLICIT basis passes."""
    ir_document = _ir_document(
        [_requirement_claim("REQ-1", deontic="MUST", basis="EXPLICIT")]
    )
    text = "<!-- ats:block b1 -->\nThe verifier MUST reject the receipt. REQ-1\n"
    checks, _ = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(requirement_ids=["REQ-1"])},
        tmp_path,
    )
    check = checks[BASIS]
    assert check["status"] == "PASS"


def test_out_basis_reports_review_required_for_an_unsupported_suspicious_strengthening(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.19 / ADR-0002: MAY -> SHOULD is suspicious, not decidable, never PASS."""
    ir_document = _ir_document(
        [_requirement_claim("REQ-1", deontic="MAY", basis="INFERRED")]
    )
    text = "<!-- ats:block b1 -->\nThe verifier SHOULD reject the receipt. REQ-1\n"
    checks, _ = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(requirement_ids=["REQ-1"])},
        tmp_path,
    )
    check = checks[BASIS]
    assert check["status"] == "REVIEW_REQUIRED"
    assert "SHOULD" in check["detail"]


def test_out_basis_is_not_applicable_without_basis_declarations(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 7.5: no semantic_basis declaration means no constraint to enforce."""
    ir_document = _ir_document([_requirement_claim("REQ-1", deontic="MUST")])
    text = "<!-- ats:block b1 -->\nThe verifier MUST reject the receipt. REQ-1\n"
    checks, report = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(requirement_ids=["REQ-1"])},
        tmp_path,
    )
    check = checks[BASIS]
    assert check["status"] == "NOT_APPLICABLE"
    assert check["required"] is False
    assert report["conformance"]["mechanical"] == "PASS"


def test_out_basis_is_not_applicable_outside_transform(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 15.4: without TRANSFORM the rendering is not a transformation output."""
    ir_document = _ir_document(
        [_requirement_claim("REQ-1", deontic="SHOULD", basis="INFERRED")],
        profiles=("ASSESS",),
    )
    text = "<!-- ats:block b1 -->\nThe verifier MUST reject the receipt. REQ-1\n"
    checks, _ = _lint(
        ctx_d2,
        draft2_policy("assess"),
        ir_document,
        text,
        {"b1": _block(requirement_ids=["REQ-1"])},
        tmp_path,
    )
    check = checks[BASIS]
    assert check["status"] == "NOT_APPLICABLE"
    assert "TRANSFORM" in check["detail"]


def test_out_basis_failure_gates_mechanical(
    ctx_d2, draft2_policy, tmp_path
) -> None:
    """Spec 15.1: a decided basis strengthening blocks the mechanical dimension."""
    ir_document = _ir_document(
        [_requirement_claim("REQ-1", deontic="SHOULD", basis="INFERRED")]
    )
    text = "<!-- ats:block b1 -->\nThe verifier MUST reject the receipt. REQ-1\n"
    checks, report = _lint(
        ctx_d2,
        draft2_policy("assess_transform"),
        ir_document,
        text,
        {"b1": _block(requirement_ids=["REQ-1"])},
        tmp_path,
    )
    assert checks[BASIS]["status"] == "FAIL"
    assert report["conformance"]["mechanical"] == "FAIL"
    assert BASIS in report["conformance_rationale"]["mechanical"]

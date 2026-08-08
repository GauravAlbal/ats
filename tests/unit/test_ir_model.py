"""Indexed views over a validated TextIR document.

Section 7.1 through 7.16 define the semantic model. These views are read-only
projections of a validated document, so what is asserted here is that every
object is reachable by identity and by a deterministic JSON Pointer (Section
13.1 requires a locatable span) and that the content address is reproducible
(Appendix C).
"""

from __future__ import annotations

import json

import pytest

from ats.canonical import canonical_bytes, sha256_hex
from ats.errors import UsageError
from ats.ir.model import (
    IrDocument,
    IrEvaluation,
    json_pointer_span,
    pointer,
)


def test_pointer_applies_rfc6901_escaping() -> None:
    """RFC 6901 via Appendix C: `~` becomes `~0` and `/` becomes `~1`."""
    assert pointer("sections", 0, "claims", 1) == "/sections/0/claims/1"
    assert pointer("a/b") == "/a~1b"
    assert pointer("a~b") == "/a~0b"
    assert pointer("a~/b") == "/a~0~1b"


def test_json_pointer_span_is_a_locatable_span() -> None:
    """Spec 13.1: a finding must name where in the artifact it applies."""
    assert json_pointer_span("/sections/0") == {
        "kind": "json_pointer",
        "locator": "/sections/0",
    }


def test_from_document_refuses_a_foreign_schema_version(load_ir) -> None:
    """Spec 19.4: an unknown major schema version MUST be rejected."""
    document = {**load_ir("assess_conforming"), "schema_version": "ats.text_ir.v2"}
    with pytest.raises(UsageError, match="ats.text_ir.v1"):
        IrDocument.from_document(document)


def test_every_object_is_indexed_by_its_identifier(load_ir) -> None:
    """Spec 7.3: sections carry ordered, identified objects."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    section = ir.sections[0]

    assert set(ir.claims) == {"c1", "a1", "b1", "alt1", "r1"}
    assert set(ir.evidence) == {"e1", "e2", "e3"}
    assert set(ir.relations) == {"rel1", "rel2", "rel3", "rel4", "rel5", "rel6"}
    assert set(ir.indicators) == {"u1"}
    assert ir.object_ids["c1"] == "claim"
    assert ir.object_ids["e1"] == "evidence"
    assert ir.object_ids["rel1"] == "relation"
    assert ir.object_ids["u1"] == "update_indicator"

    assert ir.section_for(section.section_id) is section
    with pytest.raises(UsageError, match="no section"):
        ir.section_for("no-such-section")


def test_pointers_address_the_object_they_describe(load_ir) -> None:
    """Spec 13.1 and 14.4: localization must survive into the finding."""
    document = load_ir("assess_conforming")
    ir = IrDocument.from_document(document)
    claim = ir.claims["c1"]

    assert claim.pointer == "/sections/0/claims/0"
    assert claim.field_pointer("force", "likelihood") == (
        "/sections/0/claims/0/force/likelihood"
    )
    assert document["sections"][0]["claims"][0] is claim.data
    assert ir.evidence["e1"].pointer == "/sections/0/evidence/0"
    assert ir.indicators["u1"].pointer == "/sections/0/update_indicators/0"


def test_a_claim_prefers_its_declared_source_span(load_ir) -> None:
    """Spec 14.2 and 14.4: a declared source span localizes into the original text."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    claim = ir.claims["c1"]
    declared = claim.data.get("span")
    if declared:
        assert claim.span() == dict(declared)
    else:
        assert claim.span() == json_pointer_span(claim.pointer)


def test_profiles_are_collected_in_document_order_without_duplicates(load_ir) -> None:
    """Spec 6.5 and 9.4: an artifact's profiles are the union of its sections'."""
    assert IrDocument.from_document(load_ir("assess_conforming")).profiles == ("ASSESS",)
    assert IrDocument.from_document(load_ir("composed_profiles")).profiles == (
        "ASSESS",
        "SPECIFY",
    )
    assert IrDocument.from_document(load_ir("assess_transform_output")).profiles == (
        "ASSESS",
        "TRANSFORM",
    )


def test_duplicate_identifiers_are_reported_not_raised(load_ir) -> None:
    """Spec 7.3: a reused identifier is a linter finding, not a load failure."""
    ir = IrDocument.from_document(load_ir("duplicate_ids"))
    duplicates = ir.duplicate_ids()
    assert [identifier for identifier, _ in duplicates] == ["a1"]
    (_, pointers) = duplicates[0]
    assert len(pointers) == 2
    assert pointers == sorted(pointers, key=lambda p: int(p.rsplit("/", 1)[-1]))

    assert IrDocument.from_document(load_ir("assess_conforming")).duplicate_ids() == []


def test_relation_and_indicator_lookups_are_directional(load_ir) -> None:
    """Spec 7.11 and 7.14: a relation has a direction and an indicator has a target."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    targeting = {r.relation_id for r in ir.relations_targeting("c1")}
    assert "rel1" in targeting
    assert {r.relation_id for r in ir.relations_from("e1")} == {"rel1"}
    assert {u.indicator_id for u in ir.indicators_targeting("c1")} == {"u1"}
    assert ir.indicators_targeting("b1") == ()


def test_material_claims_are_the_subset_the_artifact_marks_material(load_ir) -> None:
    """Spec 4.5 and 7.15: materiality is declared, never inferred."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    assert {c.claim_id for c in ir.material_claims()} == {
        c.claim_id for c in ir.all_claims() if c.data["material"]
    }
    assert ir.sections[0].material_claims() == tuple(
        c for c in ir.sections[0].claims if c.material
    )
    assert {c.claim_id for c in ir.sections[0].claims_with_role("judgment")} == {"c1"}


def test_ir_sha256_is_the_canonical_content_address(load_ir) -> None:
    """Appendix C: the content address is SHA-256 over the JCS bytes."""
    document = load_ir("assess_conforming")
    ir = IrDocument.from_document(document)
    assert ir.ir_sha256 == sha256_hex(canonical_bytes(document))
    # Stable across a parse round trip (spec 16.2).
    reparsed = json.loads(canonical_bytes(document).decode("utf-8"))
    assert IrDocument.from_document(reparsed).ir_sha256 == ir.ir_sha256


def test_finding_identity_is_a_function_of_the_inputs_only(ctx, load_ir, load_policy) -> None:
    """Spec 16.2: identical canonical inputs produce identical finding identities."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    policy = ctx.policy(load_policy("assess"))
    states, _ = policy.resolve_all(ir.profiles, now=ctx.now, artifact_id=ir.artifact_id)

    first = IrEvaluation(ctx=ctx, ir=ir, policy=policy, states=states)
    second = IrEvaluation(ctx=ctx, ir=ir, policy=policy, states=states)
    ids = [first.finding_id("ATS-EPI-001", "wep-interval-mismatch") for _ in range(3)]
    assert ids == [
        f"{ir.artifact_id}:ATS-EPI-001:wep-interval-mismatch:{n:03d}" for n in range(3)
    ]
    assert second.finding_id("ATS-EPI-001", "wep-interval-mismatch") == ids[0]
    # A different issue code has its own ordinal sequence.
    assert second.finding_id("ATS-EPI-001", "wep-term-not-canonical").endswith(":000")


def test_a_finding_inherits_severity_and_impact_from_the_registry(
    ctx, load_ir, load_policy
) -> None:
    """Spec 12.2 and 13.1: severity and protected impact are rule properties."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    policy = ctx.policy(load_policy("assess"))
    states, _ = policy.resolve_all(ir.profiles, now=ctx.now, artifact_id=ir.artifact_id)
    evaluation = IrEvaluation(ctx=ctx, ir=ir, policy=policy, states=states)

    detector = ctx.detector(
        "ats-ir-test", detector_class="D0", authority="conformance_evidence"
    )
    finding = evaluation.finding(
        rule_id="ATS-EPI-001",
        issue_code="wep-interval-mismatch",
        summary="test",
        spans=[json_pointer_span("/sections/0")],
        detector=detector,
    )
    rule = ctx.registry.get("ATS-EPI-001")
    assert finding.severity == rule.severity
    assert finding.protected_impact == rule.protected_impact
    assert finding.policy_snapshot_id == policy.snapshot_id
    assert finding.profile == states["ATS-EPI-001"].profile


def test_state_for_refuses_an_unresolved_rule(ctx, load_ir, load_policy) -> None:
    """Spec 6.1: a rule with no resolved state cannot be evaluated silently."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    policy = ctx.policy(load_policy("assess"))
    evaluation = IrEvaluation(ctx=ctx, ir=ir, policy=policy, states={})
    with pytest.raises(UsageError, match="no resolved state"):
        evaluation.state_for("ATS-EPI-001")

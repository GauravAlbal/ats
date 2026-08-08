"""The capability declaration must not overstate what the code does.

Spec Section 5.5 requires a partial implementation to publish what it supports;
Section 16.1 requires the declaration to be machine readable and to record the
detector class and declared authority per rule. Section 12.3 caps what each
detector class may conclude, and Section 5.4 forbids reporting PASS for a check
that cannot execute. Together those make several combinations incoherent, and
this file asserts that none of them appears.
"""

from __future__ import annotations

import pytest

from ats.capability import CapabilityDeclaration
from ats.errors import UnsupportedCapabilityError
from ats.rules.registry import DETECTOR_CLASS_MAX_AUTHORITY

#: The anchor every conformance-evidence detector's authority basis resolves to.
IR_RULE_AUTHORITY_BASIS = "docs/AUTHORITY_MODEL.md#ats-ir-rule"


def test_declaration_is_coherent_with_the_registry(ctx) -> None:
    """Spec 5.5 and 16.1: the declaration is checked, not asserted."""
    assert ctx.capability.coherence_errors() == []
    ctx.capability.require_coherent()


def test_generated_capability_file_is_current(run_tool) -> None:
    """Spec 16.1: the declaration is derived from the detector specs, not hand-maintained."""
    result = run_tool("tools/generate_capability.py", "--check")
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def test_every_registry_rule_has_exactly_one_capability_entry(ctx) -> None:
    """Spec 5.5: an undeclared rule cannot be reported honestly."""
    records = ctx.capability.document["rules"]
    ids = [record["rule_id"] for record in records]
    assert sorted(ids) == list(ctx.registry.ids())
    assert len(ids) == len(set(ids)), "a rule may not be declared twice"
    assert set(ctx.capability.rules) == set(ctx.registry.ids())


def test_an_undeclared_rule_is_reported_as_unsupported(ctx) -> None:
    """Spec 5.5: unsupported rules MUST be reported, never silently skipped."""
    with pytest.raises(UnsupportedCapabilityError):
        ctx.capability.for_rule("ATS-NOT-A-RULE")


def test_conformance_evidence_carries_an_authority_basis(ctx) -> None:
    """Spec 12.3 and 16.1: an authority claim is only as good as its recorded basis."""
    for rule_id, cap in sorted(ctx.capability.rules.items()):
        if not cap.produces_conformance_evidence:
            assert cap.authority != "conformance_evidence", rule_id
            continue
        assert cap.authority == "conformance_evidence", rule_id
        assert cap.authority_basis_ref == IR_RULE_AUTHORITY_BASIS, rule_id


def test_decides_requires_conformance_evidence_authority(ctx) -> None:
    """Spec 5.4 and 12.3: a detector that may never PASS must not claim to decide."""
    for rule_id, cap in sorted(ctx.capability.rules.items()):
        if cap.decision_power == "decides":
            assert cap.authority == "conformance_evidence", rule_id


def test_declared_authority_never_exceeds_its_detector_class_ceiling(ctx) -> None:
    """Spec 12.3: D2 output is candidate_only and D3 output is proposal_only."""
    for rule_id, cap in sorted(ctx.capability.rules.items()):
        if cap.detector_class == "none":
            assert cap.authority == "none", rule_id
            assert cap.decision_power == "undecidable", rule_id
            continue
        ceiling = DETECTOR_CLASS_MAX_AUTHORITY[cap.detector_class]
        if cap.authority == "conformance_evidence":
            assert ceiling == "conformance_evidence", rule_id
        assert cap.detector_class in ctx.registry.get(rule_id).detector_classes, rule_id


def test_undecidable_rules_name_what_they_lack(ctx) -> None:
    """Spec 5.4: UNAVAILABLE must say which input is missing."""
    for rule_id, cap in sorted(ctx.capability.rules.items()):
        if cap.decision_power != "undecidable":
            continue
        assert cap.blocking_inputs, rule_id
        assert set(cap.blocking_inputs) <= set(ctx.registry.get(rule_id).required_inputs), rule_id
        assert cap.implemented is False, rule_id
        assert cap.surfaces == (), rule_id


def test_input_accounting_is_arithmetic_not_narrative(ctx) -> None:
    """Spec 5.5: declared inputs must add up, or the declaration is a story."""
    for rule_id, cap in sorted(ctx.capability.rules.items()):
        required = set(cap.required_inputs)
        assert required == set(ctx.registry.get(rule_id).required_inputs), rule_id
        unsupplied = required - set(cap.available_inputs)
        assert set(cap.missing_inputs) == unsupplied, rule_id
        substituted = {s["input"] for s in cap.input_substitutions}
        assert substituted <= unsupplied, rule_id
        assert set(cap.blocking_inputs) == unsupplied - substituted, rule_id
        if cap.implemented:
            assert cap.blocking_inputs == (), rule_id


def test_every_subcheck_cites_a_spec_section_and_names_its_vocabulary(ctx) -> None:
    """Spec 16.1 and 12.10: a check must say what it reads and where that is normative."""
    for rule_id, cap in sorted(ctx.capability.rules.items()):
        assert cap.subchecks, rule_id
        for record in cap.subchecks:
            assert record["spec_ref"].startswith("ATS-1 "), (rule_id, record["subcheck_id"])
            assert record["description"].strip(), (rule_id, record["subcheck_id"])
            assert "vocabulary_source" in record, (rule_id, record["subcheck_id"])
        if cap.decision_power == "decides":
            assert any(s["decides"] for s in cap.subchecks), rule_id


def test_normative_projection_validates_and_is_derived(ctx, assert_valid) -> None:
    """Spec 16.1: the ``ats.capability.v1`` document is a projection, not a second source."""
    projection = ctx.capability.to_normative(
        spec_version=ctx.spec_version, schema_versions=sorted(ctx.schemas.documents)
    )
    assert_valid(projection, "ats_capability_v1.schema.json")

    assert projection["schema_version"] == "ats.capability.v1"
    assert projection["ats_versions"] == [ctx.spec_version]
    assert [entry["rule_id"] for entry in projection["rules"]] == list(ctx.registry.ids())
    assert projection["deterministic_replay"] is True
    assert projection["known_limitations"], "spec 5.5 requires the limits to be published"

    for entry in projection["rules"]:
        cap = ctx.capability.rules[entry["rule_id"]]
        if cap.detector_class == "none":
            assert entry["detector_classes"] == []
            assert entry["autofix"] == "none"
        else:
            assert entry["detector_classes"] == [cap.detector_class]
            assert entry["authority_by_class"] == {cap.detector_class: cap.authority}
        if cap.authority_basis_ref and entry["detector_classes"]:
            assert entry["authority_basis_refs"] == {
                cap.detector_class: cap.authority_basis_ref
            }


def test_declaration_document_validates_against_its_schema(ctx, assert_valid) -> None:
    """Spec 19.4: the per-rule declaration is itself a schema-governed object."""
    document = ctx.capability.document
    assert_valid(document, "ats_rule_capability_v1.schema.json")
    assert document["ats_version"] == ctx.spec_version
    assert document["implementation_name"] == ctx.implementation["name"]
    assert document["implementation_version"] == ctx.implementation["version"]


def test_a_missing_declaration_is_an_error_not_an_empty_default(ctx, tmp_path) -> None:
    """Spec 5.5: an implementation MUST publish a capability declaration."""
    from ats.errors import UsageError

    declaration = CapabilityDeclaration(ctx.registry, path=tmp_path / "absent.json")
    with pytest.raises(UsageError, match="capability declaration not found"):
        _ = declaration.document

"""TextIR schema validation.

Section 19.4 makes the imported JSON Schemas authoritative and requires an
implementation to reject an unknown major schema version. Section 20.6 requires
honest insufficiency: a document that does not validate is reported as such,
never partially evaluated.
"""

from __future__ import annotations

import pytest

from conftest import INVALID_IR_POLICY, VALID_IR_NAMES

from ats.errors import SchemaValidationError
from ats.ir.model import IrDocument
from ats.ir.validate import IR_SCHEMA_ID, require_valid_ir, validate_ir


@pytest.mark.parametrize("name", VALID_IR_NAMES)
def test_every_conforming_fixture_validates(ctx, load_ir, name) -> None:
    """Spec 19.4: the conforming fixtures are schema-valid TextIR documents."""
    assert validate_ir(ctx, load_ir(name)) == []
    assert isinstance(require_valid_ir(ctx, load_ir(name)), IrDocument)


@pytest.mark.parametrize("name", sorted(INVALID_IR_POLICY))
def test_every_violation_fixture_is_schema_valid(ctx, load_ir, name) -> None:
    """Spec 16.4: a rule fixture must violate its rule, not the schema.

    A fixture that failed validation would stop the pipeline before the rule
    ran, so it would test nothing about the rule it is named for.
    """
    assert validate_ir(ctx, load_ir(name)) == []


def test_a_foreign_major_version_is_rejected_before_any_indexing(ctx, load_ir) -> None:
    """Spec 19.4: an unknown major schema version MUST be rejected."""
    document = {**load_ir("assess_conforming"), "schema_version": "ats.text_ir.v2"}
    violations = validate_ir(ctx, document)
    assert len(violations) == 1
    assert violations[0].pointer == "/schema_version"
    assert violations[0].validator == "const"
    assert "ats.text_ir.v1" in violations[0].message


def test_a_non_object_document_is_rejected(ctx) -> None:
    """Spec 19.4: a TextIR document is a JSON object."""
    for value in ([], "text", 3, None):
        violations = validate_ir(ctx, value)
        assert len(violations) == 1
        assert violations[0].message == "document is not a JSON object"
        assert violations[0].schema_id == IR_SCHEMA_ID


def test_a_missing_required_field_is_located_by_pointer(ctx, load_ir) -> None:
    """Spec 14.4: a failure must identify the affected region."""
    document = {k: v for k, v in load_ir("assess_conforming").items() if k != "artifact_id"}
    violations = validate_ir(ctx, document)
    assert violations
    assert any("artifact_id" in v.message for v in violations)
    assert all(v.schema_id == IR_SCHEMA_ID for v in violations)


def test_a_bad_nested_value_is_located_by_pointer(ctx, load_ir) -> None:
    """Spec 14.4: localization survives into nested objects."""
    import copy

    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["claims"][0]["role"] = "not-a-role"
    violations = validate_ir(ctx, document)
    assert violations
    assert any(v.pointer.startswith("/sections/0/claims/0") for v in violations)


def test_require_valid_ir_raises_with_every_violation(ctx, load_ir) -> None:
    """Spec 20.6: the report is the schema failure, not a partial evaluation."""
    document = {**load_ir("assess_conforming"), "schema_version": "ats.text_ir.v2"}
    with pytest.raises(SchemaValidationError) as excinfo:
        require_valid_ir(ctx, document)
    error = excinfo.value
    assert error.schema_id == IR_SCHEMA_ID
    assert error.violations
    assert error.payload()["error"] == "schema_validation_failed"
    assert error.exit_code == 1


def test_lint_ir_refuses_a_schema_invalid_document(ctx, load_ir, load_policy) -> None:
    """Spec 14.1: schema validation precedes every later stage."""
    from ats.ir.lint import lint_ir

    document = {**load_ir("assess_conforming"), "schema_version": "ats.text_ir.v2"}
    with pytest.raises(SchemaValidationError):
        lint_ir(ctx, document, load_policy("assess"))

"""TextIR schema validation."""

from __future__ import annotations

from typing import Any, Mapping

from ..context import Context
from ..errors import SchemaValidationError, SchemaViolation, UsageError
from .model import IrDocument

IR_SCHEMA_ID = "ats_text_ir_v1.schema.json"


def validate_ir(ctx: Context, document: Any) -> list[SchemaViolation]:
    """Every way ``document`` fails ``ats_text_ir_v1.schema.json``."""
    if not isinstance(document, Mapping):
        return [
            SchemaViolation("", "document is not a JSON object", IR_SCHEMA_ID, "type"),
        ]
    version = document.get("schema_version")
    if version != "ats.text_ir.v1":
        return [
            SchemaViolation(
                "/schema_version",
                f"expected 'ats.text_ir.v1', got {version!r}; an implementation MUST reject an "
                "unknown major schema version (spec 19.4)",
                IR_SCHEMA_ID,
                "const",
            )
        ]
    return ctx.schemas.violations(document, IR_SCHEMA_ID)


def require_valid_ir(ctx: Context, document: Any) -> IrDocument:
    """Validate and index, or raise :class:`~ats.errors.SchemaValidationError`."""
    violations = validate_ir(ctx, document)
    if violations:
        raise SchemaValidationError(IR_SCHEMA_ID, violations)
    if not isinstance(document, Mapping):  # pragma: no cover - guarded above
        raise UsageError("document is not a JSON object")
    return IrDocument.from_document(document)

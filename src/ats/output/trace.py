"""The output trace sidecar: reading, hashing, and building.

The trace maps rendered blocks to the TextIR objects they realize. It is the
only thing that makes a readable Markdown document deterministically traceable,
so its integrity is checked before any surface rule runs: a trace that does not
match the bytes it describes cannot ground a finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..canonical import canonical_bytes, load_json, seal, sha256_hex
from ..context import Context
from ..errors import UsageError
from ..ir.model import IrDocument
from .parse import MarkdownBlock, ParsedDocument

TRACE_SCHEMA_ID = "ats_output_trace_v1.schema.json"

MARKER_SCHEME: dict[str, str] = {
    "kind": "html_comment",
    "pattern": "<!-- ats:block {block_id} -->",
    "end_pattern": "<!-- /ats:block {block_id} -->",
}

#: Object kinds a block may reference, mapped to the trace field carrying them.
REFERENCE_FIELDS: tuple[tuple[str, str], ...] = (
    ("claim_ids", "claim"),
    ("evidence_ids", "evidence"),
    ("relation_ids", "relation"),
    ("requirement_ids", "requirement"),
    ("forecast_ids", "forecast"),
    ("update_indicator_ids", "update_indicator"),
    #: Draft.2 D-C (spec 7.17): stable semantic coordinates the block renders.
    #: Distinct from the object-kind fields above: a coordinate may name an
    #: object declared outside this artifact (a work item, a protocol), so it
    #: is tracked by its own field rather than coerced into an object kind.
    ("coordinates", "coordinate"),
)


def block_text_sha256(block: MarkdownBlock) -> str:
    """SHA-256 over the block body's exact UTF-8 bytes, marker line excluded.

    The marker is metadata the renderer inserts, not content the reader sees, so
    it is outside the hash. One trailing newline is stripped so that a block's
    hash does not change when it becomes the last block in a document.
    """
    return sha256_hex(block.text.rstrip("\n").encode("utf-8"))


@dataclass(frozen=True, slots=True)
class TraceBlock:
    data: Mapping[str, Any]

    @property
    def block_id(self) -> str:
        return self.data["block_id"]

    @property
    def ordinal(self) -> int:
        return self.data["ordinal"]

    @property
    def text_sha256(self) -> str:
        return self.data["text_sha256"]

    @property
    def material(self) -> bool:
        return bool(self.data["material"])

    @property
    def content_class(self) -> str:
        return self.data.get("content_class", "prose")

    @property
    def display_role(self) -> str:
        return self.data["display_role"]

    @property
    def section_id(self) -> str:
        return self.data["section_id"]

    def references(self) -> Iterable[tuple[str, str, str]]:
        """``(field, kind, object_id)`` for every IR object this block claims."""
        for field, kind in REFERENCE_FIELDS:
            for object_id in self.data.get(field, ()):
                yield field, kind, object_id

    @property
    def p0_fields(self) -> Sequence[Mapping[str, Any]]:
        return self.data.get("p0_fields", ())

    @property
    def p1_relations(self) -> Sequence[Mapping[str, Any]]:
        return self.data.get("p1_relations", ())


@dataclass(slots=True)
class OutputTrace:
    raw: Mapping[str, Any]

    @property
    def artifact_id(self) -> str:
        return self.raw["artifact_id"]

    @property
    def ir_sha256(self) -> str:
        return self.raw["ir_sha256"]

    @property
    def output_sha256(self) -> str:
        return self.raw["output_sha256"]

    @property
    def policy_sha256(self) -> str:
        return self.raw["policy_sha256"]

    @property
    def policy_snapshot_id(self) -> str:
        return self.raw["policy_snapshot_id"]

    @property
    def profiles(self) -> tuple[str, ...]:
        return tuple(self.raw["profiles"])

    @property
    def blocks(self) -> tuple[TraceBlock, ...]:
        return tuple(TraceBlock(b) for b in self.raw["blocks"])

    @property
    def unmapped(self) -> Sequence[Mapping[str, Any]]:
        return self.raw.get("unmapped_ir_objects", ())

    def block(self, block_id: str) -> TraceBlock | None:
        for block in self.blocks:
            if block.block_id == block_id:
                return block
        return None

    def declared_object_ids(self) -> set[str]:
        return {oid for block in self.blocks for _, _, oid in block.references()}


def read_trace(ctx: Context, path: str | Path) -> OutputTrace:
    document = load_json(path)
    ctx.schemas.validate(document, TRACE_SCHEMA_ID)
    return OutputTrace(document)


def load_trace(ctx: Context, document: Mapping[str, Any]) -> OutputTrace:
    ctx.schemas.validate(document, TRACE_SCHEMA_ID)
    return OutputTrace(document)


def build_trace(
    ctx: Context,
    *,
    ir: IrDocument,
    parsed: ParsedDocument,
    output_bytes: bytes,
    policy_snapshot_id: str,
    policy_sha256: str,
    block_metadata: Mapping[str, Mapping[str, Any]],
    renderer: Mapping[str, str],
    unmapped: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Assemble a trace from a rendered document and its per-block metadata.

    ``block_metadata`` is keyed by ``block_id`` and supplies everything the
    renderer knows and the parser cannot infer: which IR objects the block
    realizes, its display role, its content class, and the P0 values it prints.
    """
    blocks: list[dict[str, Any]] = []
    ordinal = 0
    for block in parsed.blocks:
        if not block.marker_id:
            continue
        meta = block_metadata.get(block.marker_id)
        if meta is None:
            raise UsageError(
                f"rendered block {block.marker_id!r} has no trace metadata; every marked block "
                "must declare what it realizes"
            )
        entry: dict[str, Any] = {
            "block_id": block.marker_id,
            "marker": f"<!-- ats:block {block.marker_id} -->",
            "ordinal": ordinal,
            "text_sha256": block_text_sha256(block),
            "material": bool(meta.get("material", False)),
            "display_role": meta["display_role"],
            "section_id": meta["section_id"],
            "claim_ids": list(meta.get("claim_ids", ())),
            "evidence_ids": list(meta.get("evidence_ids", ())),
            "relation_ids": list(meta.get("relation_ids", ())),
            "requirement_ids": list(meta.get("requirement_ids", ())),
            "forecast_ids": list(meta.get("forecast_ids", ())),
        }
        for optional in (
            "update_indicator_ids",
            "coordinates",
            "profile",
            "heading_path",
            "p0_fields",
            "p1_relations",
            "content_class",
        ):
            if meta.get(optional):
                entry[optional] = meta[optional]
        blocks.append(entry)
        ordinal += 1

    document: dict[str, Any] = {
        "schema_version": "ats.output_trace.v1",
        "artifact_id": ir.artifact_id,
        "ir_sha256": ir.ir_sha256,
        "output_sha256": sha256_hex(output_bytes),
        "policy_snapshot_id": policy_snapshot_id,
        "policy_sha256": policy_sha256,
        "profiles": list(ir.profiles),
        "renderer": dict(renderer),
        "marker_scheme": dict(MARKER_SCHEME),
        "created_at": ctx.timestamp(),
        "blocks": blocks,
    }
    if unmapped:
        document["unmapped_ir_objects"] = [dict(u) for u in unmapped]
    sealed = seal(document)
    ctx.schemas.validate(sealed, TRACE_SCHEMA_ID)
    return sealed


def ir_value_at(ir: IrDocument, pointer: str) -> Any:
    """Resolve a JSON Pointer into the TextIR document (RFC 6901)."""
    if pointer in ("", "/"):
        return ir.raw
    if not pointer.startswith("/"):
        raise UsageError(f"{pointer!r} is not a JSON Pointer")
    current: Any = ir.raw
    for raw_part in pointer.lstrip("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                raise UsageError(f"{pointer!r} does not resolve in this TextIR") from None
        elif isinstance(current, Mapping):
            if part not in current:
                raise UsageError(f"{pointer!r} does not resolve in this TextIR")
            current = current[part]
        else:
            raise UsageError(f"{pointer!r} does not resolve in this TextIR")
    return current


def canonical_ir_sha256(document: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_bytes(document))

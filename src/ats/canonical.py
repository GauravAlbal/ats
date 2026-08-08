"""Canonical JSON serialization and content addressing.

Appendix C of ATS-1 requires content-addressed objects to:

1. omit the object's own hash field from the hash input;
2. serialize the remaining object with RFC 8785 JCS;
3. hash the canonical bytes with SHA-256;
4. encode the digest as lowercase hexadecimal; and
5. prefix identifiers with the object type when used as human-facing IDs.

Canonicalization is delegated to :mod:`rfc8785` rather than re-implemented here.
A hand-rolled JCS would duplicate a normative encoding, and RFC 8785's ES6
number formatting is exactly the part that silently diverges.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

import rfc8785

from .errors import UsageError

#: Field names that hold an object's own content address, keyed by schema version.
#: Appendix C step 1 requires exactly this field to be omitted from the hash input.
SELF_HASH_FIELDS: Final[dict[str, str]] = {
    "ats.policy_snapshot.v1": "snapshot_sha256",
    "ats.policy_exception.v1": "sha256",
    "ats.acceptance_receipt.v1": "receipt_sha256",
    "ats.output_trace.v1": "trace_sha256",
    "ats.ir_lint_report.v1": "report_sha256",
    "ats.output_lint_report.v1": "report_sha256",
    "ats.source_artifact.v1": "record_sha256",
    "ats.context_bundle.v1": "record_sha256",
    "ats.judgment.v1": "record_sha256",
    "ats.corpus_adjudication.v1": "record_sha256",
    "ats.corpus_split.v1": "record_sha256",
    "ats.profile_hypothesis.v1": "record_sha256",
    "ats.rule_coverage_report.v1": "report_sha256",
    "ats.census_receipt.v1": "receipt_sha256",
    "ats.sampling_frame.v1": "record_sha256",
    "ats.annotation_round.v1": "record_sha256",
    "ats.agreement_report.v1": "report_sha256",
    "ats.profile_reconnaissance.v1": "report_sha256",
    "ats.completion_gate.v1": "record_sha256",
    "ats.adjudication_queue.v1": "record_sha256",
    "ats.operator_adjudication.v1": "record_sha256",
    "ats.instrument_validity.v1": "report_sha256",
    "ats.planning_projection.v1": "projection_id",
}

#: Human-facing identifier prefixes (Appendix C step 5).
ID_PREFIXES: Final[dict[str, str]] = {
    "ats.policy_snapshot.v1": "ats-policy-sha256",
    "ats.policy_exception.v1": "ats-exception-sha256",
    "ats.acceptance_receipt.v1": "ats-receipt-sha256",
    "ats.output_trace.v1": "ats-trace-sha256",
    "ats.ir_lint_report.v1": "ats-irlint-sha256",
    "ats.output_lint_report.v1": "ats-outlint-sha256",
    "ats.planning_projection.v1": "ats-projection-sha256",
}


def canonical_bytes(value: Any) -> bytes:
    """Return the RFC 8785 canonical UTF-8 encoding of ``value``."""
    try:
        return rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, ValueError, TypeError) as exc:
        raise UsageError(f"value is not JCS-serializable: {exc}") from exc


def canonical_text(value: Any) -> str:
    """Return the canonical serialization as text (UTF-8 decoded)."""
    return canonical_bytes(value).decode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Lowercase hexadecimal SHA-256 digest of exact bytes."""
    return hashlib.sha256(data).hexdigest()


def content_hash(obj: dict[str, Any], *, exclude: set[str] | None = None) -> str:
    """Content address of ``obj`` after removing ``exclude`` fields.

    When ``exclude`` is omitted the field is derived from ``schema_version``
    through :data:`SELF_HASH_FIELDS`; an object whose schema declares no self
    hash field is hashed whole.
    """
    if exclude is None:
        self_field = SELF_HASH_FIELDS.get(obj.get("schema_version", ""))
        exclude = {self_field} if self_field else set()
    material = {k: v for k, v in obj.items() if k not in exclude}
    return sha256_hex(canonical_bytes(material))


def seal(obj: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``obj`` with its self-hash field set to its content address.

    Raises :class:`UsageError` when the object's schema declares no self-hash
    field, because sealing an object that has nowhere to record its address
    would silently produce an unaddressed artifact.
    """
    schema_version = obj.get("schema_version")
    field = SELF_HASH_FIELDS.get(schema_version or "")
    if field is None:
        raise UsageError(f"no self-hash field declared for schema_version={schema_version!r}")
    sealed = dict(obj)
    sealed.pop(field, None)
    sealed[field] = content_hash(sealed, exclude={field})
    return sealed


def verify_seal(obj: dict[str, Any]) -> tuple[bool, str, str]:
    """Verify a sealed object.

    Returns ``(ok, declared, recomputed)``.
    """
    schema_version = obj.get("schema_version")
    field = SELF_HASH_FIELDS.get(schema_version or "")
    if field is None:
        raise UsageError(f"no self-hash field declared for schema_version={schema_version!r}")
    declared = obj.get(field, "")
    recomputed = content_hash(obj, exclude={field})
    return declared == recomputed, declared, recomputed


def prefixed_id(obj: dict[str, Any], digest: str) -> str:
    """Human-facing content identifier, e.g. ``ats-policy-sha256:4f23...``."""
    prefix = ID_PREFIXES.get(obj.get("schema_version", ""), "ats-sha256")
    return f"{prefix}:{digest}"


def load_json(path: str | Any) -> Any:
    """Read a JSON document, raising :class:`UsageError` on malformed input."""
    from pathlib import Path

    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise UsageError(f"cannot read {p}: {exc}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UsageError(f"{p} is not valid UTF-8 JSON: {exc}") from exc


def write_json(path: str | Any, obj: Any) -> str:
    """Write ``obj`` as canonical JSON and return the SHA-256 of the written bytes."""
    from pathlib import Path

    p = Path(path)
    data = canonical_bytes(obj)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return sha256_hex(data)

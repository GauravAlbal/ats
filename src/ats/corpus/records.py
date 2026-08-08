"""Typed constructors, content addressing, and append-only storage for corpus records.

Five record types live here:

``ats.source_artifact.v1``
    A repository document pinned to an exact revision (repository-local schema).
``ats.context_bundle.v1``
    The context an annotator needs to adjudicate one span (repository-local).
``ats.text_example.v1``
    **Normative.** ``TextExampleV1`` is defined by the imported package, so this
    module never adds a top-level field to it. Repository-specific data is
    carried inside its ``extensions`` object under the ``x-ats-repo-`` prefix,
    which spec Section 19.5 requires of an extension namespace.
``ats.judgment.v1`` / ``ats.corpus_adjudication.v1``
    One annotator judgment and its resolution (repository-local).

Every record is content-addressed: its identifier is the SHA-256 of its own
canonical serialization with the identifier omitted, so two runs that produce
the same content produce the same identifier and a changed record can never
masquerade as the original.

Storage is append-only JSONL. Spec Section 17.9 requires disagreement to be
*retained*; a corpus store that permits in-place rewriting cannot make that
guarantee, so :func:`append_records` refuses to write a record whose identifier
is already present.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

from ..canonical import canonical_bytes, content_hash, seal, verify_seal
from ..errors import UsageError

#: Extension namespace for repository-specific data on the normative
#: ``TextExampleV1`` record (spec Section 19.5: an extension identifier MUST use
#: a namespace that cannot collide with core ATS identifiers).
EXT_PREFIX: Final[str] = "x-ats-repo-"

#: Where a ``TextExampleV1`` carries its own content address. The normative
#: schema declares no self-hash field and MUST NOT gain one, so the digest is
#: recorded as an extension instead.
EXT_RECORD_SHA256: Final[str] = f"{EXT_PREFIX}record-sha256"

#: Extension keys this repository defines on ``TextExampleV1``.
EXT_TEXT_IR: Final[str] = f"{EXT_PREFIX}text-ir"
EXT_SOURCE_EXAMPLE_ID: Final[str] = f"{EXT_PREFIX}source-example-id"
EXT_MUTATION_FAMILY: Final[str] = f"{EXT_PREFIX}mutation-family"
EXT_CONTEXT_BUNDLE_ID: Final[str] = f"{EXT_PREFIX}context-bundle-id"
EXT_AUTHOR: Final[str] = f"{EXT_PREFIX}author"
EXT_SOURCE_MODEL_FAMILY: Final[str] = f"{EXT_PREFIX}source-model-family"
EXT_TEMPLATE_FAMILY: Final[str] = f"{EXT_PREFIX}template-family"
EXT_NEAR_DUPLICATE_CLUSTER: Final[str] = f"{EXT_PREFIX}near-duplicate-cluster"
EXT_COPIED_TEXT_CLUSTER: Final[str] = f"{EXT_PREFIX}copied-text-cluster"
EXT_COMMON_ANCESTOR: Final[str] = f"{EXT_PREFIX}common-ancestor-document"
EXT_SOURCE_REVISION: Final[str] = f"{EXT_PREFIX}source-revision"
EXT_TARGET_POINTER: Final[str] = f"{EXT_PREFIX}target-pointer"
EXT_CANDIDATE_ONLY: Final[str] = f"{EXT_PREFIX}candidate-only"

#: schema_version -> (identifier field, identifier prefix).
RECORD_IDENTITY: Final[dict[str, tuple[str, str]]] = {
    "ats.source_artifact.v1": ("artifact_id", "ats-artifact-sha256"),
    "ats.context_bundle.v1": ("bundle_id", "ats-bundle-sha256"),
    "ats.text_example.v1": ("example_id", "ats-example-sha256"),
    "ats.judgment.v1": ("judgment_id", "ats-judgment-sha256"),
    "ats.corpus_adjudication.v1": ("adjudication_id", "ats-corpus-adjudication-sha256"),
    "ats.corpus_split.v1": ("split_id", "ats-split-sha256"),
    "ats.profile_hypothesis.v1": ("hypothesis_id", "ats-profile-hypothesis-sha256"),
}

#: The corpus record types :func:`validate_records` recognises.
CORPUS_SCHEMA_VERSIONS: Final[tuple[str, ...]] = tuple(RECORD_IDENTITY)


def identity_field(schema_version: str) -> str:
    """The identifier field name for a corpus record type."""
    try:
        return RECORD_IDENTITY[schema_version][0]
    except KeyError:
        raise UsageError(f"{schema_version!r} is not a corpus record type") from None


def record_id(record: Mapping[str, Any]) -> str:
    """The identifier of a corpus record, by its declared ``schema_version``."""
    schema_version = record.get("schema_version")
    if not isinstance(schema_version, str):
        raise UsageError("record has no schema_version discriminator")
    field = identity_field(schema_version)
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise UsageError(f"record declares {schema_version} but carries no {field}")
    return value


# -- content addressing -----------------------------------------------------


def _drop_empty(record: dict[str, Any]) -> dict[str, Any]:
    """Remove keys whose value is ``None``, so an absent field is truly absent.

    A ``null`` in an emitted record would be a silent omission wearing a value.
    Every optional field this module builds is either present with content or
    not present at all.
    """
    return {k: v for k, v in record.items() if v is not None}


def address(record: Mapping[str, Any]) -> dict[str, Any]:
    """Content-address and seal a corpus record.

    The identifier is the SHA-256 of the record's canonical serialization with
    the identifier and self-hash fields removed, so it is a pure function of
    the record's meaning. Records whose schema declares a ``record_sha256``
    field are then sealed through :func:`ats.canonical.seal`; the normative
    ``TextExampleV1``, which declares none, records its digest under
    :data:`EXT_RECORD_SHA256` instead of gaining a top-level field.
    """
    schema_version = record.get("schema_version")
    if not isinstance(schema_version, str) or schema_version not in RECORD_IDENTITY:
        raise UsageError(f"{schema_version!r} is not a corpus record type")
    id_field, prefix = RECORD_IDENTITY[schema_version]

    body = _drop_empty(dict(record))
    body.pop(id_field, None)
    body.pop("record_sha256", None)
    if schema_version == "ats.text_example.v1":
        extensions = dict(body.get("extensions") or {})
        extensions.pop(EXT_RECORD_SHA256, None)
        if extensions:
            body["extensions"] = extensions
        else:
            body.pop("extensions", None)

    digest = content_hash(body, exclude=set())
    body[id_field] = f"{prefix}:{digest}"

    if schema_version == "ats.text_example.v1":
        extensions = dict(body.get("extensions") or {})
        extensions[EXT_RECORD_SHA256] = digest
        body["extensions"] = extensions
        return body
    return seal(body)


def verify_record(record: Mapping[str, Any]) -> tuple[bool, str]:
    """Verify a record's content address; returns ``(ok, detail)``."""
    schema_version = record.get("schema_version", "")
    if schema_version not in RECORD_IDENTITY:
        return False, f"{schema_version!r} is not a corpus record type"
    id_field, prefix = RECORD_IDENTITY[schema_version]
    declared_id = record.get(id_field, "")

    recomputed = address({k: v for k, v in record.items() if k != id_field})
    if recomputed[id_field] != declared_id:
        return False, f"{id_field} is {declared_id!r}, content addresses to {recomputed[id_field]!r}"

    if schema_version == "ats.text_example.v1":
        declared = (record.get("extensions") or {}).get(EXT_RECORD_SHA256, "")
        expected = declared_id.removeprefix(f"{prefix}:")
        if declared != expected:
            return False, f"{EXT_RECORD_SHA256} is {declared!r}, expected {expected!r}"
        return True, "content address and extension digest agree"

    ok, declared_hash, recomputed_hash = verify_seal(dict(record))
    if not ok:
        return False, f"record_sha256 is {declared_hash!r}, recomputes to {recomputed_hash!r}"
    return True, "content address and seal agree"


# -- constructors -----------------------------------------------------------


def source_artifact(
    *,
    repository: str,
    repository_group: str,
    path: str,
    revision: str,
    content_sha256: str,
    normalized_sha256: str,
    media_type: str,
    review_state: str,
    use_authority: str,
    handling_policy: str,
    ingested_at: str,
    bytes_: int | None = None,
    author_provenance: Mapping[str, Any] | None = None,
    model_provenance: Mapping[str, Any] | None = None,
    acceptance_evidence: Mapping[str, Any] | None = None,
    template_family: str | None = None,
    near_duplicate_cluster: str | None = None,
    domain: str | None = None,
    profile_hypotheses: Sequence[str] | None = None,
    heading_paths: Sequence[Sequence[str]] | None = None,
    extensions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a content-addressed ``SourceArtifactV1``."""
    record: dict[str, Any] = {
        "schema_version": "ats.source_artifact.v1",
        "repository": repository,
        "repository_group": repository_group,
        "path": path,
        "revision": revision,
        "content_sha256": content_sha256,
        "normalized_sha256": normalized_sha256,
        "bytes": bytes_,
        "media_type": media_type,
        "author_provenance": dict(author_provenance) if author_provenance else None,
        "model_provenance": dict(model_provenance) if model_provenance else None,
        "review_state": review_state,
        "acceptance_evidence": dict(acceptance_evidence) if acceptance_evidence else None,
        "use_authority": use_authority,
        "handling_policy": handling_policy,
        "template_family": template_family,
        "near_duplicate_cluster": near_duplicate_cluster,
        "domain": domain,
        "profile_hypotheses": list(profile_hypotheses) if profile_hypotheses else None,
        "heading_paths": [list(p) for p in heading_paths] if heading_paths else None,
        "ingested_at": ingested_at,
        "extensions": dict(extensions) if extensions else None,
    }
    return address(_drop_empty(record))


def context_bundle(
    *,
    source_artifact_id: str,
    source_revision: str,
    source_span: Mapping[str, Any],
    span_text: str,
    containing_block: Mapping[str, Any],
    heading_path: Sequence[str],
    preceding_context: Mapping[str, Any],
    following_context: Mapping[str, Any],
    local_definitions: Sequence[Mapping[str, Any]],
    glossary_entries: Sequence[Mapping[str, Any]],
    profile_hypothesis: Mapping[str, Any],
    policy_context: Mapping[str, Any],
    diff: Mapping[str, Any],
    review_comment: Mapping[str, Any],
    later_edit: Mapping[str, Any],
    reversal: Mapping[str, Any] | None = None,
    context_completeness: str | None = None,
    extensions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a content-addressed ``ContextBundleV1``."""
    record: dict[str, Any] = {
        "schema_version": "ats.context_bundle.v1",
        "source_artifact_id": source_artifact_id,
        "source_revision": source_revision,
        "source_span": dict(source_span),
        "span_text": span_text,
        "containing_block": dict(containing_block),
        "heading_path": list(heading_path),
        "preceding_context": dict(preceding_context),
        "following_context": dict(following_context),
        "local_definitions": [dict(d) for d in local_definitions],
        "glossary_entries": [dict(g) for g in glossary_entries],
        "profile_hypothesis": dict(profile_hypothesis),
        "policy_context": dict(policy_context),
        "diff": dict(diff),
        "review_comment": dict(review_comment),
        "later_edit": dict(later_edit),
        "reversal": dict(reversal) if reversal else None,
        "context_completeness": context_completeness,
        "extensions": dict(extensions) if extensions else None,
    }
    return address(_drop_empty(record))


def text_example(
    *,
    text: str,
    profile: str,
    rule_id: str,
    label: str,
    rationale: str,
    protected_impact: Sequence[str],
    provenance: str,
    synthetic: bool,
    split_group: str,
    context: str | None = None,
    source_artifact: str | None = None,
    source_span: Mapping[str, Any] | None = None,
    repository_group: str | None = None,
    domain: str | None = None,
    adjudicators: Sequence[str] | None = None,
    use_authority: str | None = None,
    mutation_operator: str | None = None,
    related_finding_refs: Sequence[str] | None = None,
    extensions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a content-addressed normative ``TextExampleV1``.

    ``synthetic`` and ``provenance`` MUST agree: spec Section 17.5 requires
    synthetic examples to be tagged so they are never counted as independent
    real-world evidence, and a mutation recorded as natural would defeat that.
    """
    if synthetic and provenance != "synthetic_mutation":
        raise UsageError(
            f"synthetic example declares provenance={provenance!r}; a synthetic mutation MUST "
            "be tagged as such (spec 17.5)"
        )
    if not synthetic and provenance == "synthetic_mutation":
        raise UsageError("provenance=synthetic_mutation requires synthetic=true (spec 17.5)")
    if mutation_operator and not synthetic:
        raise UsageError("mutation_operator is only meaningful on a synthetic example (spec 17.5)")

    record: dict[str, Any] = {
        "schema_version": "ats.text_example.v1",
        "text": text,
        "context": context,
        "source_artifact": source_artifact,
        "source_span": dict(source_span) if source_span else None,
        "repository_group": repository_group,
        "domain": domain,
        "profile": profile,
        "rule_id": rule_id,
        "label": label,
        "rationale": rationale,
        "protected_impact": list(protected_impact),
        "adjudicators": list(adjudicators) if adjudicators else None,
        "provenance": provenance,
        "use_authority": use_authority,
        "synthetic": synthetic,
        "mutation_operator": mutation_operator,
        "split_group": split_group,
        "related_finding_refs": list(related_finding_refs) if related_finding_refs else None,
        "extensions": dict(extensions) if extensions else None,
    }
    return address(_drop_empty(record))


def judgment(
    *,
    example_id: str,
    annotator_id: str,
    rule_id: str,
    rule_version: str,
    profile: str,
    label: str,
    rationale: str,
    evidence_spans: Sequence[Mapping[str, Any]],
    protected_impact: Sequence[str],
    annotation_confidence: str,
    requested_additional_context: Sequence[str],
    ambiguity_category: str,
    timestamp: str,
    tool_version: str,
    context_bundle_id: str | None = None,
    normative_statement_quoted: str | None = None,
    blind: bool | None = None,
    extensions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a content-addressed ``JudgmentV1``."""
    record: dict[str, Any] = {
        "schema_version": "ats.judgment.v1",
        "example_id": example_id,
        "context_bundle_id": context_bundle_id,
        "annotator_id": annotator_id,
        "rule_id": rule_id,
        "rule_version": rule_version,
        "profile": profile,
        "label": label,
        "rationale": rationale,
        "normative_statement_quoted": normative_statement_quoted,
        "evidence_spans": [dict(s) for s in evidence_spans],
        "protected_impact": list(protected_impact),
        "annotation_confidence": annotation_confidence,
        "requested_additional_context": list(requested_additional_context),
        "ambiguity_category": ambiguity_category,
        "blind": blind,
        "timestamp": timestamp,
        "tool_version": tool_version,
        "extensions": dict(extensions) if extensions else None,
    }
    return address(_drop_empty(record))


def adjudication(
    *,
    example_id: str,
    rule_id: str,
    rule_version: str,
    judgments: Sequence[Mapping[str, Any]],
    agreement: str,
    disagreement_category: str,
    final_state: str,
    adjudicator: str,
    rationale: str,
    gold_eligible: bool,
    timestamp: str,
    context_constraint: str | None = None,
    standard_ambiguity_discovered: str | None = None,
    source_ambiguity_discovered: str | None = None,
    policy_mismatch: str | None = None,
    annotation_error: str | None = None,
    required_rule_amendment: str | None = None,
    required_corpus_correction: str | None = None,
    tool_version: str | None = None,
    extensions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a content-addressed ``AdjudicationV1``, retaining judgments verbatim."""
    if len(judgments) < 2:
        raise UsageError(
            "an adjudication resolves at least two independent judgments (spec 17.9); "
            f"got {len(judgments)}"
        )
    record: dict[str, Any] = {
        "schema_version": "ats.corpus_adjudication.v1",
        "example_id": example_id,
        "rule_id": rule_id,
        "rule_version": rule_version,
        "judgment_ids": [record_id(j) for j in judgments],
        "judgments": [dict(j) for j in judgments],
        "agreement": agreement,
        "disagreement_category": disagreement_category,
        "final_state": final_state,
        "context_constraint": context_constraint,
        "adjudicator": adjudicator,
        "rationale": rationale,
        "standard_ambiguity_discovered": standard_ambiguity_discovered,
        "source_ambiguity_discovered": source_ambiguity_discovered,
        "policy_mismatch": policy_mismatch,
        "annotation_error": annotation_error,
        "required_rule_amendment": required_rule_amendment,
        "required_corpus_correction": required_corpus_correction,
        "gold_eligible": gold_eligible,
        "timestamp": timestamp,
        "tool_version": tool_version,
        "extensions": dict(extensions) if extensions else None,
    }
    return address(_drop_empty(record))


# -- append-only JSONL storage ----------------------------------------------


def read_records(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL corpus file. A missing file reads as empty, not as an error."""
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise UsageError(f"{p}:{lineno} is not valid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise UsageError(f"{p}:{lineno} is not a JSON object")
        out.append(record)
    return out


def existing_ids(path: str | Path) -> set[str]:
    """Identifiers already stored in a JSONL corpus file."""
    return {record_id(r) for r in read_records(path)}


def append_records(
    ctx: Any, path: str | Path, records: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Validate and append records to a JSONL file.

    Appending is the only mutation this store supports. A record whose
    identifier is already present is refused with :class:`UsageError`: because
    the identifier is a content address, a repeat identifier means either an
    exact duplicate or an attempt to rewrite history, and spec Section 17.9
    requires the original to be retained either way.
    """
    p = Path(path)
    present = existing_ids(p)
    batch: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        ctx.schemas.validate_document(record)
        ok, detail = verify_record(record)
        if not ok:
            raise UsageError(f"record is not correctly content-addressed: {detail}")
        rid = record_id(record)
        if rid in present or rid in seen:
            raise UsageError(
                f"{rid} is already stored in {p}; the corpus store is append-only and a "
                "record identifier is a content address, so rewriting one is refused (spec 17.9)"
            )
        seen.add(rid)
        batch.append(dict(record))

    if batch:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for record in batch:
                fh.write(canonical_bytes(record).decode("utf-8"))
                fh.write("\n")
    return {"path": str(p), "appended": len(batch), "total": len(present) + len(batch)}


def iter_corpus_files(path: str | Path) -> list[Path]:
    """Resolve a corpus path to the JSONL files under it, in sorted order."""
    p = Path(path)
    if p.is_dir():
        return sorted(p.rglob("*.jsonl"))
    if p.exists():
        return [p]
    raise UsageError(f"no corpus file or directory at {p}")


def load_corpus(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Read every corpus record under ``path``, indexed by ``schema_version``."""
    out: dict[str, list[dict[str, Any]]] = {}
    for file in iter_corpus_files(path):
        for record in read_records(file):
            out.setdefault(str(record.get("schema_version")), []).append(record)
    return out


def validate_records(ctx: Any, path: str | Path) -> dict[str, Any]:
    """Validate every corpus record under ``path``.

    An empty ``problems`` list is the only signal that the store is valid; the
    function reports schema violations, broken content addresses, and duplicate
    identifiers rather than stopping at the first failure.
    """
    from ..errors import SchemaValidationError

    problems: list[dict[str, Any]] = []
    by_schema: dict[str, int] = {}
    checked = 0
    seen: dict[str, str] = {}

    for file in iter_corpus_files(path):
        try:
            records = read_records(file)
        except UsageError as exc:
            problems.append({"file": str(file), "problem": "unreadable", "detail": str(exc)})
            continue
        for index, record in enumerate(records):
            checked += 1
            locator = f"{file}:{index}"
            schema_version = record.get("schema_version")
            if not isinstance(schema_version, str):
                problems.append(
                    {
                        "file": str(file),
                        "locator": locator,
                        "problem": "no_schema_version",
                        "detail": "record carries no schema_version discriminator",
                    }
                )
                continue
            by_schema[schema_version] = by_schema.get(schema_version, 0) + 1
            try:
                ctx.schemas.validate_document(record)
            except (SchemaValidationError, UsageError) as exc:
                problems.append(
                    {
                        "file": str(file),
                        "locator": locator,
                        "problem": "schema_invalid",
                        "detail": str(exc),
                    }
                )
                continue
            if schema_version not in RECORD_IDENTITY:
                continue
            ok, detail = verify_record(record)
            if not ok:
                problems.append(
                    {
                        "file": str(file),
                        "locator": locator,
                        "problem": "content_address_mismatch",
                        "detail": detail,
                    }
                )
                continue
            rid = record_id(record)
            if rid in seen:
                problems.append(
                    {
                        "file": str(file),
                        "locator": locator,
                        "problem": "duplicate_id",
                        "detail": f"{rid} already stored at {seen[rid]}",
                    }
                )
                continue
            seen[rid] = locator

    return {
        "path": str(path),
        "records_checked": checked,
        "by_schema": dict(sorted(by_schema.items())),
        "problems": problems,
    }

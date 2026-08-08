"""Schema registry and validation.

The imported JSON Schemas remain authoritative (spec Section 19.4, Appendix B).
Nothing in this package re-declares a normative object's shape in Python; the
dataclasses elsewhere are typed *views* over validated documents, never a
second definition that can drift.

Repository-local schemas under ``schemas/`` extend the normative set for
objects ATS-1 does not define (output traces, corpus records, lint reports).
They live in a separate directory and use distinct ``schema_version`` values so
a local convenience can never be mistaken for a normative object.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Final

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .canonical import load_json
from .errors import SchemaValidationError, SchemaViolation, UsageError
from .spec_package import REPO_ROOT, SpecPackage

#: Repository-local schema directory (non-normative extensions).
LOCAL_SCHEMA_ROOT: Final[Path] = REPO_ROOT / "schemas"

#: schema_version -> schema $id, for both normative and local objects.
SCHEMA_FOR_VERSION: Final[dict[str, str]] = {
    # normative (imported)
    "ats.text_ir.v1": "ats_text_ir_v1.schema.json",
    "ats.policy_snapshot.v1": "ats_policy_snapshot_v1.schema.json",
    "ats.policy_exception.v1": "ats_policy_exception_v1.schema.json",
    "ats.ruleset.v1": "ats_ruleset_v1.schema.json",
    "ats.force_lexicon.v1": "ats_force_lexicon_v1.schema.json",
    "ats.finding.v1": "ats_finding_v1.schema.json",
    "ats.adjudication.v1": "ats_adjudication_v1.schema.json",
    "ats.retention_contract.v1": "ats_retention_contract_v1.schema.json",
    "ats.preservation_report.v1": "ats_preservation_report_v1.schema.json",
    "ats.acceptance_receipt.v1": "ats_acceptance_receipt_v1.schema.json",
    "ats.text_example.v1": "ats_text_example_v1.schema.json",
    "ats.capability.v1": "ats_capability_v1.schema.json",
    "ats.package_manifest.v1": "ats_package_manifest_v1.schema.json",
    # repository-local extensions
    "ats.import_receipt.v1": "ats_import_receipt_v1.schema.json",
    "ats.output_trace.v1": "ats_output_trace_v1.schema.json",
    "ats.rule_result.v1": "ats_rule_result_v1.schema.json",
    "ats.rule_capability.v1": "ats_rule_capability_v1.schema.json",
    "ats.fleet_policy.v1": "ats_fleet_policy_v1.schema.json",
    "ats.ir_lint_report.v1": "ats_ir_lint_report_v1.schema.json",
    "ats.output_lint_report.v1": "ats_output_lint_report_v1.schema.json",
    "ats.source_artifact.v1": "ats_source_artifact_v1.schema.json",
    "ats.context_bundle.v1": "ats_context_bundle_v1.schema.json",
    "ats.judgment.v1": "ats_judgment_v1.schema.json",
    "ats.corpus_adjudication.v1": "ats_corpus_adjudication_v1.schema.json",
    "ats.mutation_operator.v1": "ats_mutation_operator_v1.schema.json",
    "ats.corpus_split.v1": "ats_corpus_split_v1.schema.json",
    "ats.corpus_authority.v1": "ats_corpus_authority_v1.schema.json",
    "ats.profile_hypothesis.v1": "ats_profile_hypothesis_v1.schema.json",
    "ats.rule_coverage_report.v1": "ats_rule_coverage_report_v1.schema.json",
    "ats.census_receipt.v1": "ats_census_receipt_v1.schema.json",
    "ats.sampling_frame.v1": "ats_sampling_frame_v1.schema.json",
    "ats.annotation_round.v1": "ats_annotation_round_v1.schema.json",
    "ats.agreement_report.v1": "ats_agreement_report_v1.schema.json",
    "ats.profile_reconnaissance.v1": "ats_profile_reconnaissance_v1.schema.json",
    "ats.completion_gate.v1": "ats_completion_gate_v1.schema.json",
    "ats.adjudication_queue.v1": "ats_adjudication_queue_v1.schema.json",
    "ats.operator_adjudication.v1": "ats_operator_adjudication_v1.schema.json",
    "ats.instrument_validity.v1": "ats_instrument_validity_v1.schema.json",
    "ats.planning_projection.v1": "ats_planning_projection_v1.schema.json",
    "ats.skill_pack_manifest.v1": "ats_skill_pack_manifest_v1.schema.json",
}

#: Schema ids sourced from the imported normative package.
NORMATIVE_SCHEMA_IDS: Final[frozenset[str]] = frozenset(
    {
        "ats_common_v1.schema.json",
        "ats_text_ir_v1.schema.json",
        "ats_policy_snapshot_v1.schema.json",
        "ats_policy_exception_v1.schema.json",
        "ats_ruleset_v1.schema.json",
        "ats_force_lexicon_v1.schema.json",
        "ats_finding_v1.schema.json",
        "ats_adjudication_v1.schema.json",
        "ats_retention_contract_v1.schema.json",
        "ats_preservation_report_v1.schema.json",
        "ats_acceptance_receipt_v1.schema.json",
        "ats_text_example_v1.schema.json",
        "ats_capability_v1.schema.json",
        "ats_package_manifest_v1.schema.json",
    }
)


class SchemaSet:
    """Resolved registry over normative and repository-local schemas."""

    def __init__(self, package: SpecPackage, local_root: Path | None = None) -> None:
        self.package = package
        self.local_root = local_root if local_root is not None else LOCAL_SCHEMA_ROOT
        self._validators: dict[str, Draft202012Validator] = {}

    @functools.cached_property
    def documents(self) -> dict[str, dict[str, Any]]:
        docs: dict[str, dict[str, Any]] = {}
        for path in self.package.schema_paths:
            doc = load_json(path)
            docs[doc["$id"]] = doc
        if self.local_root.is_dir():
            for path in sorted(self.local_root.glob("*.schema.json")):
                doc = load_json(path)
                schema_id = doc["$id"]
                if schema_id in NORMATIVE_SCHEMA_IDS:
                    raise UsageError(
                        f"local schema {path} redefines normative schema id {schema_id}; "
                        "a code convenience must not shadow a normative object"
                    )
                docs[schema_id] = doc
        return docs

    @functools.cached_property
    def registry(self) -> Registry:
        resources = [
            (schema_id, Resource.from_contents(doc, default_specification=DRAFT202012))
            for schema_id, doc in self.documents.items()
        ]
        return Registry().with_resources(resources)

    def schema(self, schema_id: str) -> dict[str, Any]:
        try:
            return self.documents[schema_id]
        except KeyError:
            raise UsageError(f"unknown schema id: {schema_id}") from None

    def schema_for_version(self, schema_version: str) -> tuple[str, dict[str, Any]]:
        try:
            schema_id = SCHEMA_FOR_VERSION[schema_version]
        except KeyError:
            raise UsageError(
                f"unknown schema_version {schema_version!r}; "
                "an implementation MUST reject an unknown major schema version (spec 19.4)"
            ) from None
        return schema_id, self.schema(schema_id)

    def _validator(self, schema_id: str) -> Draft202012Validator:
        cached = self._validators.get(schema_id)
        if cached is None:
            cached = Draft202012Validator(self.schema(schema_id), registry=self.registry)
            self._validators[schema_id] = cached
        return cached

    def violations(self, instance: Any, schema_id: str) -> list[SchemaViolation]:
        validator = self._validator(schema_id)
        out: list[SchemaViolation] = []
        for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
            pointer = "/" + "/".join(str(p) for p in err.absolute_path)
            out.append(
                SchemaViolation(
                    pointer=pointer if pointer != "/" else "",
                    message=err.message,
                    schema_id=schema_id,
                    validator=str(err.validator),
                )
            )
        return out

    def validate(self, instance: Any, schema_id: str) -> None:
        violations = self.violations(instance, schema_id)
        if violations:
            raise SchemaValidationError(schema_id, violations)

    def validate_document(self, instance: Any) -> str:
        """Validate a document by its declared ``schema_version``; returns the schema id."""
        if not isinstance(instance, dict) or "schema_version" not in instance:
            raise UsageError("document has no schema_version discriminator")
        schema_id, _ = self.schema_for_version(instance["schema_version"])
        self.validate(instance, schema_id)
        return schema_id

    def check_own_schemas(self) -> list[SchemaViolation]:
        """Validate every registered schema against the Draft 2020-12 metaschema."""
        out: list[SchemaViolation] = []
        for schema_id, doc in sorted(self.documents.items()):
            try:
                Draft202012Validator.check_schema(doc)
            except SchemaError as exc:
                pointer = "/" + "/".join(str(p) for p in exc.absolute_path)
                out.append(
                    SchemaViolation(
                        pointer if pointer != "/" else "",
                        exc.message,
                        schema_id,
                        "metaschema",
                    )
                )
        return out


def load_schema_set(spec_version: str | None = None) -> SchemaSet:
    return SchemaSet(SpecPackage.load(spec_version))

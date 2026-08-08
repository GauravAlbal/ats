# ADR-0003: Repository-local schemas are namespaced and may not shadow a normative schema id

**Status:** Accepted
**Date:** 2026-08-02

## Context

The imported package ships 14 normative schemas. The v0 pipeline needs objects ATS-1 does not
define: an import receipt, an IR lint report, an output lint report, a per-rule capability
declaration richer than `ats.capability.v1`, an output trace sidecar, a rule result, and five
corpus records.

All of these are JSON Schema Draft 2020-12 documents resolved through the same `referencing`
registry, and several of them `$ref` into `ats_common_v1.schema.json`. That shared registry
is exactly where a local convenience could quietly displace a normative object: a local file
whose `$id` is `ats_text_ir_v1.schema.json` would win or lose by directory iteration order,
and every validation in the process would silently start using it.

The consequence would not be a crash. It would be a green build validating against a private
definition of TextIR while every report still says `spec_version: 1.0.0-draft.1`.

## Decision

Three separations, all mechanical.

**Separate directory.** Normative schemas live in `spec/ATS-1/<version>/schemas/`; local ones
live in `schemas/` at the repository root. `SchemaSet` loads the package's first, then the
local root.

**Distinct `schema_version` discriminators.** `SCHEMA_FOR_VERSION` in `ats/schemas.py` maps
every `schema_version` to a schema id, with the two groups commented apart. Normative values
are the `ats.<object>.v1` names Appendix B fixes. Local values use distinct object names that
do not collide: `ats.import_receipt.v1`, `ats.output_trace.v1`, `ats.rule_result.v1`,
`ats.rule_capability.v1`, `ats.ir_lint_report.v1`, `ats.output_lint_report.v1`,
`ats.source_artifact.v1`, `ats.context_bundle.v1`, `ats.judgment.v1`,
`ats.corpus_adjudication.v1`, `ats.mutation_operator.v1`, `ats.corpus_split.v1`.

**A hard refusal on `$id` collision.** `NORMATIVE_SCHEMA_IDS` is a frozenset of the 14
imported ids. When `SchemaSet.documents` loads a local schema whose `$id` is in that set, it
raises:

```python
raise UsageError(
    f"local schema {path} redefines normative schema id {schema_id}; "
    "a code convenience must not shadow a normative object"
)
```

This is a load-time failure of `Context.load()`, not a warning, so no code path can run
against a shadowed registry.

Two naming choices follow from the same principle. `ats.rule_capability.v1` is deliberately
*not* `ats.capability.v1`: it is a richer per-rule document with decision power, subchecks,
vocabulary sources, unavailable conditions, known limits, and input substitutions.
`CapabilityDeclaration.to_normative()` projects it into a real `ats.capability.v1` document
when one is needed — one source, two representations, the projection derived. Likewise
`ats.corpus_adjudication.v1` is not `ats.adjudication.v1`: the normative object dispositions a
*finding on an artifact*, the local one dispositions a *corpus example*, and its schema
description says so.

## Consequences

- A normative object's shape is unambiguous: exactly one schema in the process defines it, and
  it came from the verified package.
- Local schemas may `$ref` into `ats_common_v1.schema.json` freely and reuse `identifier`,
  `sha256`, `timestamp`, `span`, `availability`, `profile`, and `glossary_entry`. They share
  the normative vocabulary without owning it — which is why the corpus records can use the
  same `availability` enum as the IR's typed-absence fields.
- `SchemaSet.check_own_schemas()` validates every registered schema, normative and local,
  against the Draft 2020-12 metaschema, so a malformed local schema fails loudly rather than
  producing confusing validation output.
- `Context.schema_set_sha256` content-addresses the entire set, so a local schema change is
  visible in every IR lint report and can invalidate a prior receipt's replay claim (§15.8).
- Cost: two directories and two vocabularies to keep straight, and a projection function to
  maintain. `to_normative()` is 30 lines that must move when either side moves.

## Alternatives considered

**One `schemas/` directory holding both.** Rejected. It makes the normative/local boundary a
naming convention inside a flat listing, and it puts imported files somewhere they can be
edited.

**Extend normative schemas in place via `allOf` or by adding properties.** Rejected twice
over: it edits the imported package (ADR-0001), and §19.4 permits accepting an unknown
optional field only when the schema permits it and the field does not alter conformance
semantics — most normative schemas here set `additionalProperties: false`.

**Use a URL namespace prefix, e.g. `https://ats.local/schemas/…`.** Considered and not
adopted. It would make collision impossible by construction rather than by check, which is
genuinely stronger. But the imported package uses bare filename `$id`s, so a prefixed local
set would need URI rewriting to `$ref` into `ats_common_v1.schema.json`, adding a resolution
layer to prevent a collision the frozenset already prevents at load time. Revisit if a second
schema source ever appears.

**Put corpus and report objects in the `extensions` field the normative schemas provide.**
Rejected. `extensions` is a typed escape hatch for per-artifact metadata, not a place to host
whole object types; a lint report inside an IR's `extensions` would have no schema of its own
and could not be validated or content-addressed independently.

## References

- ATS-1 §19.4 (schema versioning; reject an unknown major schema version), §19.5 (extension
  identifiers MUST use a non-colliding namespace), Appendix B (canonical object identifiers)
- Constitution #5 (single source of truth with typed references; one concept, one canonical
  encoding, alternates forced through a chokepoint conversion)
- `src/ats/schemas.py` (`SCHEMA_FOR_VERSION`, `NORMATIVE_SCHEMA_IDS`, `SchemaSet.documents`),
  `src/ats/capability.py::to_normative`

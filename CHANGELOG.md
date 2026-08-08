# Changelog

All notable changes to this repository are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow semantic versioning.

Downstream artifacts bind the exact ATS-1 draft version they were evaluated under. A change to
the imported normative package is a separate, receipted import, never an edit in place.

## [0.1.2-skill-pack] — 2026-08-08

Portable standalone recipe lookup repair.

- Public skills now distinguish canonical-source recipe paths from the
  host-local `recipes/` and `references/` paths shipped in generated packs.
- `ats skills verify` checks every manifest-declared recipe target inside every
  generated host rather than accepting a repository-only path.
- An isolated-pack capstone prevents repository files from masking broken
  standalone references.
- This patch changes only the skill-pack surface and packaging; ATS
  implementation `0.5.0` and the draft.2-new/draft.1-legacy version law remain
  unchanged.

## [0.1.1-skill-pack] — 2026-08-07

Public release of the canonical skill surface defined by ADR-0023.

- Four self-contained public skills, deterministic host packaging, and
  draft.2-default/draft.1-historical version semantics define the release
  contract.
- Generated artifacts are regenerated only from the completed canonical source;
  host forms are verified against their manifest and are never hand-maintained.
- The history-free public lineage separates canonical source (P0) from generated
  pack output (P1) and publishes the signed annotated tag
  `v0.1.1-skill-pack` at P1.

## [0.5.0] — 2026-08-07

Operationalization pivot: ATS becomes reusable implementation infrastructure.

Program change: ATS is a controlled technical discourse standard for
transferring operative models between reasoning systems, deployed with
deterministic validation, linting, receipts, policy resolution, and planning
projection.

 

### Added — draft.2 normative package


- The ATS-1 `1.0.0-draft.2` package under `spec/ATS-1/1.0.0-draft.2/`: six
  normative deltas (D-A mission, D-B relation preservation as a rule,
  D-C stable semantic coordinates, D-D local semantic closure, D-E
  intentional redundancy, D-F source semantic basis), each marked inline in
  the spec and classified in `docs/ATS_1_DRAFT_2_MIGRATION.md`. Draft.1 stays
  byte-immutable; its schemas are supersets so draft.1 IRs validate under
  draft.2 without rerendering.
- A 36-rule registry (`ats.ruleset.v2`): 30 carried rules plus ATS-COORD-001/
  002 (coordinates), ATS-BASIS-001/002 (basis), ATS-PRES-003 (protected
  relations), ATS-CLOSE-001 (closure), each with an operational class
  (`block` / `review_required` / `advisory`). ATS-DISC-003 amended to permit
  locality-preserving redundancy.
- Six deterministic detectors over the new rules; structural and output lint
  extended (IR-BASIS-SCHEMA, OUT-COORD-PRESERVED, OUT-BASIS-NOT-STRENGTHENED,
  coordinate-aware IR-ID-UNIQUE/IR-REFS). No PASS-by-absence: transformation
  rules without their inputs report UNAVAILABLE.
- Policy and planning surfaces: `ats policy resolve` (policy contract
  `ats.fleet_policy.v1`, `config/policies/fleet_policy.json`) and
  `ats planning project` (`ats.planning_projection.v1`, deterministic,
  source-pointered, sealed).
- Three capstones (prose→ATS with no invented authority; new architecture
  authoring with AUTHOR_JUDGMENT; planning projection with coordinates
  preserved) and the §35 contract test suites.

### Added — downstream planning boundary

- The sealed planning projection preserves source coordinates and policy
  provenance without becoming an executable task graph.
- Downstream planners consume projections without re-authoring ATS semantics;
  acceptance remains an authorized external decision.


## [0.1.0] — 2026-08-03

First implementation milestone: the deterministic v0 of ATS-1.

### Added — normative package ingestion

- Imported `ATS-1 1.0.0-draft.1` into `spec/ATS-1/1.0.0-draft.1/`, verified against the published
  archive digest `8ccef3df…d37c28`, byte-verified against its own `MANIFEST.json`, and validated
  by the package's own offline validator (14 schemas, 30 rules, 13 examples).
- `spec/ATS-1/receipts/1.0.0-draft.1.json` records the archive hash, manifest hash, package
  version, import timestamp, validator result, and extraction path. It lives beside the version
  directory, never inside it: the upstream validator asserts that the package's files equal its
  manifest exactly, so a receipt written inside would make that validator fail on every run
  after the import.
- `ats spec import` performs a receipted import of a new upstream version.

### Added — core

- RFC 8785 canonical serialization and content addressing (`ats.canonical`), delegated to the
  `rfc8785` library and verified against the package's own example hashes.
- Source binding with separate content and normalized hashes plus a monotone offset map
  (`ats.hashes`).
- A typed error hierarchy with stable machine codes and exit codes (`ats.errors`).
- Immutable access to the imported package with byte-level integrity verification
  (`ats.spec_package`).
- A schema registry over the 14 normative schemas plus 12 repository-local schemas, which are
  namespaced and refuse to shadow a normative schema id (`ats.schemas`).
- Pure policy resolution: the rule-state lattice, layered resolution, scoped exceptions with
  expiry and hash verification, composed-profile resolution with typed conflicts, and a record of
  every refused policy directive (`ats.policy`).

### Added — rules and detectors

- Typed access to the 30-rule registry and the calibrated force lexicon (`ats.rules.registry`).
- The rule-result model with two orthogonal gates: decision power gates `PASS`, detector authority
  gates `FAIL` (`ats.rules.results`). A detector cannot assign itself a status.
- Deterministic detectors for all 30 rules across ten category modules. 11 decide completely,
  12 recognise a defined subset of violations, and 7 report `UNAVAILABLE` naming the input the
  TextIR surface cannot supply.
- `capability/ats_rule_capability_v1.json`, generated from the detector declarations by
  `tools/generate_capability.py`, covering implementation status, detector class, decision power,
  conformance-evidence authority, required and available inputs, declared input substitutions,
  per-subcheck vocabulary provenance, unavailable conditions, and known limits for every rule.

### Added — IR linter

- `ats ir validate`, `ats ir lint`, `ats ir canonicalize`, and `ats ir explain-finding`.
- 26 structural checks spanning schema conformance, policy identity and currentness, source
  hashes, identifier uniqueness, internal references, section and profile composition, profile
  slots, claim-role field compatibility, evidence endpoints, glossary references, likelihood
  vocabulary and interval identity, first-use range metadata, likelihood/confidence separation,
  confidence-basis structure, update indicators, deontic validity, requirement slots, one
  obligation per requirement, quantitative units, polarity and scope fields, protected-impact
  declarations, extraction-status coherence, policy exceptions, capability reporting, and
  canonical serialization.
- ASSESS and SPECIFY profile completeness validators implementing Sections 9.2.13 and 9.3.20.
- A sealed `ats.ir_lint_report.v1` carrying every rule result, every check, the conformance
  vector, and a non-empty rationale for each dimension.

### Added — output linter

- `ats output lint` and `ats output verify-receipt`.
- Markdown parsing through `markdown-it-py`; unsupported constructs are reported rather than
  silently skipped, and a parse failure names the affected region.
- `ats.output_trace.v1`, an invisible HTML-comment source map plus a sidecar mapping rendered
  blocks to IR objects, declared P0 values with JSON Pointers, and declared P1 relations.
- 25 output checks covering bytes and hashes, parsing, marker integrity, trace schema, block
  hashes, IR references, material coverage, unknown references, block ordering, profile-required
  sections, canonical WEP terms, inline probability ranges, deontic keywords, acronym policy,
  units, relative-time anchoring, terminology constraints, heading and list mechanics, exact P0
  rendering, declared P1 relations, policy exceptions, finding dispositions, the conformance
  vector, and receipt integrity.
- Candidate receipts whose acceptance authority is external by construction: the builder refuses
  an adjudicator identity that names this implementation.

### Added — corpus

- Corpus record types, local Git inventory with no network access, context
  bundles, deterministic candidate mining, the public mutation registry, blind
  annotation queues, and adjudication; these mechanics operate on
  caller-supplied or synthetic public fixtures. Omitted non-public evidence is
  not a release input.
- `corpus/operators/ats_mutation_operators_v1.yaml` and the three public protocol documents under
  `protocols/`.

### Added — skills and documentation

- Three repo-local skills: `ats-ir-author`, `ats-assess-output`, `ats-specify-output`.
- `docs/` covering the north star, architecture, authority model, skill contracts, corpus data
  model, package observations, and architecture decision records.

### Known limitations

- `semantic_review` is never reported as `PASS`: this implementation holds no disposition
  authority (Sections 15.3 and 14.11).
- `forecast_calibration` is always `INSUFFICIENT_EVIDENCE`: no resolved-forecast cohort or scoring
  procedure exists (Section 15.5).
- `preservation` is `UNAVAILABLE` whenever TRANSFORM is active, because no v0 command supplies a
  source IR, output IR, retention contract, and authorization set. Section 6.4 makes
  `ATS-PRES-001` and `ATS-PRES-002` unwaivable, so this correctly blocks a preservation claim.
- No D2 rule router, D3 semantic critic, or learned detector of any kind is implemented.
- Rules whose required inputs include `source_text`, `syntax`, `document_ast`, or
  `document_context` cannot be decided from a TextIR alone; each reports `UNAVAILABLE` and names
  the missing input.
- Defects and ambiguities found in `1.0.0-draft.1` are recorded in `docs/PACKAGE_OBSERVATIONS.md`
  as observations against the draft, not as changes to the standard.

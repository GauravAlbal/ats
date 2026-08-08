# ADR-0017: Fleet artifact applicability is policy-based, not filename-based

**Status:** Accepted
**Date:** 2026-08-07

## Context

ATS becomes the default for new durable technical artifacts in the artifact
classes listed by `schemas/ats_fleet_policy_v1.schema.json`, but not the
universal writing voice. Two failure modes bracket the design space. First: a
blanket rule — "all artifacts are ATS" — would force ATS onto exploratory chat,
blog posts, and marketing copy, which is overhead with no recovery value. Second:
a filename heuristic — ".md files in docs/ are ATS" — is both over- and
under-inclusive. Applicability must follow the artifact's intent and the
machine-readable policy contract, not prompt convention.

## Decision

Fleet applicability is defined by the repo-local fleet policy schema
`schemas/ats_fleet_policy_v1.schema.json` (`$id: ats_fleet_policy_v1.schema.json`,
`schema_version: ats.fleet_policy.v1`):

- **Required classes** (twelve): architecture, technical_proposal, rfc,
  implementation_spec, capability_program, implementation_plan, postmortem,
  diagnostic, forensic_analysis, technical_assessment, acceptance_record,
  change_control_record. These are the classes for which ATS is the default
  for new durable artifacts.
- **Default exclusions** (nine): exploratory_chat, scratch_notes,
  brainstorming, blog_posts, marketing_copy, README_marketing,
  ordinary_issue_comments, casual_explanation, social_copy.
- **Enforcement** is graded by the operational class values in the fleet policy
  schema: the deterministic integrity surfaces are required — `ir_schema`,
  `deterministic_ir_lint`, `output_trace`, `deterministic_output_lint`,
  `p0_preservation`, `stable_coordinate_preservation` — while
  `semantic_review` is advisory. Deterministic integrity failures block;
  style advisories never block.
- **Failure policy** is explicit: `unknown_nonblocking` → preserve,
  `inferred_material_semantics` → review_required,
  `deterministic_integrity_failure` → block.
- **Repository overrides** are explicit and receipt-bound: a repo may add or
  remove `required_for` classes and override enforcement, and those
  overrides bind a receipt. Overrides are never implicit per-repo drift.
- **Applicability is intent-based, never filename-only.** Every class entry
  records its `applicability_basis` in the schema; resolution asks what the
  artifact *is*, not what its file is called.
- The policy is content-addressed (`policy_id`), versioned, and
  deterministically resolvable via the CLI: `ats policy resolve
  <artifact-class> [--repo <path>]` emits the resolved policy — membership,
  enforcement, failure policy, and override resolution — for a class.

## Consequences

- Arq consumes one stable contract (`ats policy resolve`) instead of
  re-deriving applicability per repo, which is the no-duplication boundary
  of ADR-0018.
- A repository that wants ATS for an unusual class opts it in explicitly
  with a receipted override; a repository that wants to exempt a class
  documents that exemption the same way. Silent and receipt-free drift is
  impossible by construction.
- Naming games stop mattering: an RFC-shaped artifact in an excluded repo
  is still covered if its intent is an RFC; a chat transcript named like an
  RFC is not covered just because of its filename.
- The rollout stages are a deployment concern outside this policy ADR. The
  `failure_policy` carries the block-vs-advisory split that keeps style findings
  out of acceptance.
- Cost: intent must be declared or discoverable for resolution to be
  sound; the schema's `applicability_basis` field makes that declaration
  part of the policy record rather than an informal assumption.

## Alternatives considered

**Infer applicability from filename or extension.** Rejected explicitly by
`schemas/ats_fleet_policy_v1.schema.json`: applicability is based on artifact
intent and policy, not inferred only from filename. It is both over- and
under-inclusive and would let naming decide conformance.

**Per-repo ad-hoc configuration outside a schema.** Rejected. Without a
schema there is no validation, no content-addressed `policy_id`, no
receipt binding, and no deterministic CLI for Arq to call; overrides would
drift silently.

**Apply ATS to every artifact in the fleet.** Rejected. The policy schema does
not make ATS the universal writing voice; the excluded classes are exactly the
ones where ATS adds cost and no recovery value.

**Let a downstream consumer re-implement applicability logic.** Rejected. That
duplicates the policy in a second place and would drift from the schema; the
consumer resolves the ATS-provided contract instead.

## References

- `schemas/ats_fleet_policy_v1.schema.json`; `src/ats/policy.py`; CLI
  `ats policy resolve`; ATS-1 operational class policy
- ADR-0010 (operationalization pivot)

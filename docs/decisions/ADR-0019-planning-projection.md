# ADR-0019: The ATS planning projection is source-lineaged planning input, not a task graph

**Status:** Accepted
**Date:** 2026-08-07

## Context

Once Arq accepts ATS artifacts as planning input, it needs a stable, deterministic
view of the semantics it can plan against. The naive mapping — one ATS requirement
equals one VX task — is too rigid: implementation reality frequently splits one
obligation into several tasks (for example, `AGK-FENCE-001` → VX-T1/T2/T3) or
folds several coupled requirements into one task. The mapping must be made by the
planner, not frozen by the standard.

But the planner cannot do its job from raw IR either. Raw IR is a full
semantic document; the planner needs the projection — requirements,
decisions, acceptance criteria, proof obligations, dependencies, non-goals,
boundaries, exceptions, update indicators, authority, and the stable
coordinates that tie them together — with source pointers that make the
derivation auditable. And because the projection is the seam where
semantics become workflow, its loss modes are the same as the coordinate
loss modes ADR-0013 exists to prevent: a task derived without its source
obligation is a task that cannot be evidenced, accepted, or postmortemed
against its origin.

## Decision

ATS ships a deterministic **planning projection** — `AtsPlanningProjectionV1`
(delta D-H):

- Schema `schemas/ats_planning_projection_v1.schema.json`
  (`$id: ats_planning_projection_v1.schema.json`,
  `schema_version: ats.planning_projection.v1`). Top-level fields:
  `projection_id`, `artifact_id`, `artifact_sha256`, `ir_sha256`,
  `policy_snapshot_id`, `policy_snapshot_sha256`, `spec_version`,
  `profile`, `stable_coordinates`, `requirements`, `decisions`,
  `acceptance_criteria`, `proof_obligations`, `dependencies`,
  `non_goals`, `boundaries`, `exceptions`, `update_indicators`, and
  `authority`.
- Module `src/ats/planning/project.py` exposes
  `project_from_ir(ctx, ir_document, policy_document, *, artifact_sha256)`
  — a deterministic projection from a validated IR. Every projected
  requirement, decision, and acceptance criterion carries its IR source
  pointer; the projection binds the artifact hash and the policy snapshot
  hash, validates against the schema, and is sealed by content hash.
- CLI: `ats planning project <ir> --policy <policy>
  --artifact-sha256 <sha> [--out <path>]`.
- **The projection is not a task graph.** It is planning input: it
  preserves the semantic units, their coordinates, dependencies, and
  obligations, and it deliberately does not decide task boundaries. The
  downstream planner may derive one→one, one→many, or many→one while
  preserving lineage — that decision belongs to the downstream planner.
- **Lineage is non-negotiable.** Every derived VX task retains
  `source_ats: {artifact_id, artifact_sha256, requirement_ids,
  decision_ids, acceptance_criterion_ids}`. A planner MAY create new
  planning coordinates; it MUST preserve ATS stable coordinates and MUST NOT
  rewrite a source obligation into unrelated task statements with no machine-stable
  join.
- Capstone C exercises the contract end-to-end: accepted spec IR →
  planning projection → mock planner → tasks with `source_ats` lineage,
  covering both one→many and many→one derivation.

## Consequences

- The ATS→planning seam is exact: no fuzzy semantic joins between ATS artifacts,
  Arq plans, VX tasks, tests, and Moat acceptance. The lineage chain — artifact →
  plan → task → implementation → test/evidence → acceptance — is mechanically
  joinable.
- The projection is sealed against both the artifact and the policy
  snapshot, so a change to either invalidates the projection hash
  deterministically; `update_indicators` flags the review surface when the
  source IR shifts.
- The projection is cheap to produce and review because it is a pure
  function of validated IR plus policy; there is no learned step and no
  hidden state.
- Cost: the projection intentionally stops short of task compilation. A planner
  that wants ready-made tasks must do that work itself; ATS will not guess task
  boundaries, because guessing them would make ATS an execution authority
  (ADR-0010, ADR-0018) and would pin a rigid one-to-one mapping.

## Alternatives considered

**One requirement = one task.** Rejected explicitly by the planning projection
contract; it is too rigid and would force false task boundaries onto real
implementations.

**Emit the raw IR as the "projection".** Rejected. Raw IR is not a
stable planning contract — it is the full semantic document with no
planner-shaped surface, no policy binding, and no sealed identity for the
derivation.

**Build the planner into ATS.** Rejected. Planning/decomposition belongs to the
downstream planner; ATS supplying a task graph would duplicate the workflow
engine and re-introduce the boundary violation the decision exists to prevent.

**Emit a task graph anyway, with lineage.** Rejected. ATS artifacts are
privileged planning inputs, not automatically executable task graphs. The
projection preserves the semantic units and their joins; task shape remains the
planner's judgment.

## References

- `schemas/ats_planning_projection_v1.schema.json`;
  `src/ats/planning/project.py`; CLI `ats planning project`;
  `docs/PLANNING_PROJECTION.md`; ATS-1 draft.2 planning/lineage requirements
- ADR-0013 (stable coordinates protected), ADR-0010 (what ATS is not)

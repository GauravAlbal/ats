# Planning Projection

This document specifies the ATS planning projection: the deterministic surface that turns
an accepted ATS TextIR artifact into structured planning input for downstream consumers.
Every claim is checkable against
`schemas/ats_planning_projection_v1.schema.json`, `src/ats/planning/project.py`, and the
test suites in `tests/unit/test_planning_projection.py`.

## Purpose

ATS artifacts are **privileged planning inputs, not automatically executable task graphs**.
An ATS requirement is semantic source material: it states what must hold, who acts, under
what condition, and how acceptance is evidenced. It is not a work item, a sprint unit, or
an implementation recipe. Planning decisions — task boundaries, sequencing, ownership,
effort — belong to the external planner or consumer, not to ATS.

The planning projection is the handoff between those authorities. It extracts, from a
validated IR document, the operative model a planner needs — requirements, decisions,
acceptance criteria, proof obligations, dependencies, non-goals, boundaries, exceptions,
update indicators, and authority — while preserving the **stable semantic coordinates**
(D-C) that make later joins machine-stable. The projection does not decompose anything
into tasks. It makes decomposition cheap and traceable.

The explicit non-goal of the projection is to conflate ATS requirements with downstream
tasks. A one-requirement-to-one-task mapping is rejected as a design rule; the projection
is deliberately mapping-agnostic.

## Position in the pipeline

ATS artifact (accepted, lint-clean, coordinates protected)
        ↓  ats planning project
AtsPlanningProjectionV1 (sealed, deterministic)
        ↓  external planner consumes projection
Planner plan (plan items join on requirement/decision/AC ids)
        ↓
Consumer tasks (each task carries source_ats lineage)
        ↓
implementation → test/evidence (evidence references AC ids)
        ↓
Acceptance system (receipt binds projection + artifact hashes)
```

The projection is one draft.2 operational surface alongside fleet policy resolution
(`ats policy resolve`) and other downstream integrations. Fleet policy decides *whether*
ATS applies; the planning projection decides *what the artifact means for planning*.
This repository ships the projection CLI and documentation; planning and acceptance
systems consume the resulting public schema without requiring ATS to implement them.

## Schema

`schemas/ats_planning_projection_v1.schema.json`, `$id: ats_planning_projection_v1.schema.json`,
`schema_version: ats.planning_projection.v1`. It is a repository-local schema (ADR-0003:
namespaced, never shadowing a normative id). The projection is produced by
`src/ats/planning/project.py::project_from_ir(ctx, ir_document, policy_document, *,
artifact_sha256) -> dict`: deterministic extraction from validated IR, every output unit
carrying its IR `source_pointer`, then validated against the schema and sealed.

### Identity and hashes

| Field | Semantics | Source |
|---|---|---|
| `schema_version` | `ats.planning_projection.v1` (const) | Schema |
| `projection_id` | Content hash of the projection (RFC 8785 identity), written by `seal()` | `ats/canonical.py` |
| `artifact_id` | The IR document's `artifact_id` | IR `artifact_id` |
| `artifact_sha256` | Hash of the source artifact bytes, supplied by the caller | CLI `--artifact-sha256` |
| `ir_sha256` | Content hash of the validated IR document | `ats/canonical.content_hash` on the IR |
| `policy_snapshot_id` | The fleet policy's `policy_id` | Resolved policy document |
| `policy_snapshot_sha256` | Content hash of the canonical policy bytes | `ats/canonical.canonical_bytes` |
| `spec_version` | Standard version the artifact was authored against (`1.0.0-draft.2` under fleet policy) | IR / policy, stamped like receipts (contract §0) |
| `profile` | The IR's declared profile (`ASSESS` / `SPECIFY`) | IR profile declaration |

The projection binds artifact and policy hashes so that replay is unambiguous: a projection
is only valid against one artifact version under one resolved policy. Changing either
invalidates the projection.

### Field groups and their IR feed

Every group below is copied from the validated IR with a `source_pointer` (JSON Pointer into
the TextIR document). The projection never invents a value; it reports what the IR declares,
and a missing value stays missing.

| Group | Shape | IR feed |
|---|---|---|
| `stable_coordinates` | `{kind, id, source_pointer}`; `uniqueItems` on `id` | The document-level `stable_coordinates` block (draft.2, contract §2). `kind` is one of the eight protected kinds: `requirement_id`, `decision_id`, `acceptance_criterion_id`, `work_item_id`, `protocol_id`, `protocol_version`, `dependency_target`, `authority_reference`. Lint (ATS-COORD-001/002) has already verified every declared coordinate resolves and no duplicates exist before the projection runs. |
| `requirements` | `{requirement_id, actor, deontic, action, object, scope?, trigger?, condition?, acceptance_criterion_id?, source_pointer, authority?}` | IR `requirement_slots` on requirement claims. `deontic` enum is verbatim from the IR (`MUST`, `MUST_NOT`, `SHOULD`, `SHOULD_NOT`, `MAY`). `acceptance_criterion_id` comes from the slot's linked criterion coordinate; `authority` from the slot's `source_authority`. |
| `decisions` | `{decision_id, proposition, status?, source_pointer}` | IR decision records (draft.2 `claim.decision_id` on recommendation/judgment claims). `status` copies the claim status (`asserted`, `ambiguous`, `unresolved`, `withdrawn`, `superseded`) so open design questions reach the planner typed, not guessed. |
| `acceptance_criteria` | `{acceptance_criterion_id, criterion, requirement_ids?}` | IR acceptance-criterion objects. `requirement_ids` links the criterion to every requirement that references it, preserving the acceptance dependency (P1 relation, D-B). |
| `proof_obligations` | `{obligation_id, claim_id, requirement_id?}` | Claims that carry verification/evidence obligations, paired with the requirement they ground. The projection names the obligation; whether and how it is discharged is a planning decision. |
| `dependencies` | `{from_requirement_id, to_requirement_id, kind?}` | IR relations of dependency kind (`depends_on`, `condition_for`, `necessary_for`, `sufficient_for`); `kind` preserves the relation type. `dependency_target` refs have been resolved by lint. |
| `non_goals` | `{statement, source_pointer}` | Explicit exclusion declarations in the IR. The projection copies the statement and pointer verbatim; it does not classify prose into non-goals. |
| `boundaries` | `{statement, source_pointer}` | IR claims with role `boundary`. |
| `exceptions` | `{statement, source_pointer}` | IR claims with role `exception` and requirement-level exception slots (`exception_to` relations). |
| `update_indicators` | `{indicator_id, claim_id, kind?, status?, source_pointer}` | IR `update_indicator` records: target claim ref → `claim_id`, `effect` → `kind` (e.g. `increase_likelihood`, `invalidate_assumption`, `reverse_recommendation`), plus indicator state → `status`. These are the artifact's own reversal/update conditions — the planner can wire them to re-evaluation triggers, not just to initial execution. |
| `authority` | `{source_id, authority?, precedence?}` | IR source attribution records. `precedence` is carried only when the IR declares it; an undeclared precedence stays absent — the projection must never invent an authority hierarchy, and ATS-BASIS-002 makes silent promotion a blocking violation. |

The eight protected coordinate kinds are the join surface. Any id the planner sees in
`requirements`, `decisions`, `acceptance_criteria`, `proof_obligations`, `dependencies`, or
`update_indicators` resolves either into `stable_coordinates` or into a planner-created
coordinate explicitly introduced downstream.

## Determinism

The projection is a **pure function of (validated IR, resolved policy, artifact hash)**. It
makes no model calls, reads no clocks, and consults no external state. Replay guarantees:

- **RFC 8785 identity.** `ats/canonical.py` delegates canonical JSON to the `rfc8785`
  library (ADR-0004); `content_hash` removes the object's own self-hash field
  (`SELF_HASH_FIELDS` keyed by `schema_version`), canonicalizes the remainder, and SHA-256s
  it (Appendix C steps 1–4). `projection_id` is that address, written by `seal()` — which
  raises if the schema declared no self-hash field, rather than emitting an unaddressed
  projection.
- **Inputs are pinned.** `artifact_sha256`, `ir_sha256`, and `policy_snapshot_sha256` ride
  on the projection; `project_from_ir` fails rather than projecting against a stale policy
  (`StalePolicyError`, exit 4, consistent with §14.3 currentness discipline).
- **No semantic re-judging.** The projection extracts from a lint-clean, accepted IR. It is
  not a conformance evaluation and adds no findings: the coordinate, basis, and closure
  checks (ATS-COORD-001/002, ATS-BASIS-001/002, ATS-CLOSE-001) ran before acceptance, at
  `ats ir lint` time.
- **No model calls.** If a later version adds any learned extraction, it is a different
  surface with its own identity; the deterministic projection stays the replay-guaranteed
  contract that downstream consumers use.

## Task derivation rules

The projection does not derive tasks, but it defines the rules an external planner or
consumer must obey when it does:

- **Mapping cardinality is free.** One requirement → one task, one requirement → several
  tasks (a requirement decomposes into independently verifiable implementation units), or
  several coupled requirements → one task (a change that must land atomically). The
  projection carries requirements and their dependency edges precisely so the planner can
  make this call per requirement instead of by a global rule.
- **Every derived task carries source lineage.** Each derived task retains
  `source_ats: {artifact_id, artifact_sha256, requirement_ids, decision_ids,
  acceptance_criterion_ids}`. A task with an empty lineage is a planner-created
  coordination task and must be declared as such.
- **Source coordinates are preserved; planning coordinates are additive.** The planner MAY
  create new planning coordinates (`PLAN-T1`, `PLAN-T2`, …) but MUST preserve every ATS
  stable coordinate it consumes. A task that references `AGK-FENCE-001` must keep that id
  verbatim.
- **Rewriting without a join is forbidden.** Splitting a source obligation into task
  statements that no longer carry the source coordinate, with the join left to textual
  similarity or model inference, is a violation — there is no machine-stable join. The
  ATS stable coordinate is that join; dropping it breaks the chain from artifact to
  acceptance.

## CLI

```text
ats planning project <ir> --policy <policy> --artifact-sha256 <sha> [--out <path>]
```

- `<ir>` — a validated TextIR document (draft.2 features make the projection meaningful;
  draft.1 documents project too, but with an empty `stable_coordinates` surface the
  joinable-coordinate guarantee does not hold).
- `--policy` — the resolved fleet policy document; its `policy_id` becomes
  `policy_snapshot_id` and its canonical bytes hash becomes `policy_snapshot_sha256`.
- `--artifact-sha256` — the source artifact's content hash, bound into the projection.
- `--out` — write the sealed projection JSON here; without it, the projection is printed.
- Emits: the validated, sealed `AtsPlanningProjectionV1` object. Exit codes follow the
  `ats.errors` taxonomy (`ats/cli.py`): `2` usage, `1` schema validation / unresolved
  reference, `4` stale or mismatched policy.

The reference planner in `tests/capstone/test_fleet_capstones.py` consumes this output and
demonstrates one→many and many→one derivation with `source_ats` lineage on every task,
proving the round-trip preserves coordinates.

## The chain, hop by hop

| Hop | Join key | What carries it |
|---|---|---|
| ATS artifact → projection | `artifact_id` + `artifact_sha256` + `ir_sha256` | Projection identity block |
| Projection → plan | `requirement_id`, `decision_id`, `acceptance_criterion_id`, `dependency_target` | Plan items reference projection coordinates |
| Plan → derived task | `requirement_ids`/`decision_ids`/`acceptance_criterion_ids` | `source_ats` on every task |
| Derived task → implementation | `work_item_id` (planner-created) → source coordinates | Task → code mapping, reviewable |
| Implementation → test/evidence | `acceptance_criterion_id` | Tests and evidence cite the criteria they discharge |
| Evidence → acceptance system | AC ids + `artifact_sha256` + projection hash | Acceptance receipt binds the artifact version |

Every hop joins on a stable coordinate. Nothing in the chain re-infers the semantic join
from prose; the coordinates do that work, and the projection is where they become
machine-consumable.

## Authority boundaries

- **ATS owns** semantic compilation and conformance evidence: the projection is evidence
  about what the artifact means, sealed and replayable.
- **External planners and consumers own** adoption policy, planning, and task derivation:
  the projection is an input, never an instruction to execute.
- **An acceptance system owns** acceptance: the projection's hashes let a receipt name
  exactly which artifact version and policy produced the planning surface being accepted
  against.
- **Draft.1 stays immutable** (`spec/ATS-1/1.0.0-draft.1/`). The projection is a draft.2-era
  surface built on draft.2 declarations (`stable_coordinates`, `decision_id`,
  `acceptance_criterion_id`, `semantic_basis`); draft.1 artifacts remain lintable and
  receipt-able exactly as before, they just have no coordinate surface to project. See
  [`ATS_1_DRAFT_2_MIGRATION.md`](ATS_1_DRAFT_2_MIGRATION.md).

## Reading order

| Document | Question it answers |
|---|---|
| [`NORTH_STAR.md`](NORTH_STAR.md) | Why coordinates and basis are protected semantics |
| [`AUTHORITY_MODEL.md`](AUTHORITY_MODEL.md) | Who may declare, and who may accept |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | The canonicalization and sealing machinery the projection reuses |
| [`decisions/ADR-0019-planning-projection.md`](decisions/ADR-0019-planning-projection.md) | The public planning-projection decision |
| [`schemas/ats_planning_projection_v1.schema.json`](../schemas/ats_planning_projection_v1.schema.json) | The sealed projection schema |

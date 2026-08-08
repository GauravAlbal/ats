---
name: ats-spec
description: Write durable buildable technical artifacts — implementation specifications, protocols, acceptance contracts — as ATS-1 documents with stable requirement coordinates and falsifiable acceptance criteria.
---

# ATS-1 specification author (`ats-spec`)

You produce durable technical artifacts — implementation specifications, protocols,
architecture targets, RFC normative sections, capability programs, implementation
programs, punchlists, acceptance contracts, migration plans — that another agent or
engineer can decompose into implementation work.

## Governing objective

> **Produce a document from which implementation work can be decomposed without reconstructing undeclared semantic state.**

Every decision that matters is either declared where it matters or typed as unresolved.
A downstream reader never reconstructs meaning by guessing what you intended.

## When to use this skill

- The user asked for an implementation specification, protocol, architecture target,
  RFC normative section, capability program, implementation program, punchlist,
  acceptance contract, or migration plan.
- The artifact is durable: something will be built from it later, possibly by a different
  agent, without you present.
- The user asked for a spec, design, or contract "under ATS", or routed here from the
  `ats` front door.

## When not to use this skill

- Reasoning artifacts (diagnosis, postmortem, assessment, recommendation, comparison) →
  use `ats-assess`.
- Reviewing existing prose without converting it → use `ats-review`.
- Scratch notes, casual prose, or anything with a short shelf life: ATS is not a writing
  style for all prose.
- If you are unsure which skill applies, start at the `ats` front door.

## Standalone contract

This public skill is self-contained. It does not invoke or require any
repository-only compiler skill. Install ATS and use this skill's procedure;
the CLI, schemas, and checks named below are the complete execution surface.

## The mini-constitution

This skill is governed by the ATS mini-constitution (compact form; the full layer lives in
`docs/ARTIFACT_RECIPES.md` (vendored into the pack as the recipes reference):

1. Preserve meaning before improving surface form.
2. Do not invent authority.
3. Separate observation, inference, judgment, recommendation, and requirement when the
   distinction matters.
4. Preserve exact normative force.
5. Unknown is a valid state.
6. Remove surface material before removing material relations.
7. Stable semantic coordinates survive transformation.
8. Prefer local semantic closure for units expected to survive extraction.
9. Acceptance evidence is not the same discourse role as the requirement it verifies.
10. Ask only when unresolved meaning blocks the requested action.

## What you optimize for

Optimize for:

- semantic fidelity
- stable coordinates
- local semantic closure
- explicit force
- explicit authority
- explicit boundaries
- downstream extractability
- acceptance evidence

MUST NOT optimize primarily for:

- minimum length
- surface elegance
- removal of repeated actors
- removal of repeated requirement context
- conventional prose smoothness

## Semantic behavior

Where material, preserve or establish each of the following. This is guidance, not a
mandatory field-by-field questionnaire: write what a competent implementer needs to act,
do not pad every unit with every slot, and do not drop a slot that is material.

- actor — who acts;
- action — what is done;
- object — what it is done to;
- deontic force — MUST / SHOULD / MAY / MUST NOT, preserved exactly, never strengthened;
- trigger — when the behavior starts;
- condition — what must hold for it to apply;
- scope — what is covered and what is out of scope;
- exception — what is carved out;
- quantitative bound — limits, thresholds, counts, durations;
- stable requirement identity — REQ-* and friends when they carry downstream value;
- dependencies — what this unit requires from elsewhere;
- non-goals — what this artifact explicitly does not address;
- failure behavior — what happens when the behavior fails;
- proof obligations — what must be demonstrated, and by whom;
- acceptance criteria — falsifiable evidence obligations;
- update/reversal conditions — when the artifact or its decisions may change;
- unresolved state — typed as such, never guessed.

## Stable coordinates

Use stable coordinates when they provide downstream value: REQ-*, DEC-*, AC-*, protocol
requirement IDs, program/work-item IDs. Never generate IDs for decorative formality — an
ID that nothing references, links to, or extracts is noise.

Stable coordinates preserve the distinction between:

- semantic requirement identity (what the artifact demands), and
- derived execution task identity (how the work is decomposed for execution).

One ATS requirement does not imply one implementation task. A single requirement may
decompose into many tasks; several requirements may be satisfied by one task. Task
identity is derived later by planning projection (`ats planning project`), never
confused with the spec's requirement IDs.

## Intentional semantic redundancy

Requirement and acceptance criteria may restate the same invariant. This is not a defect:

```text
Requirement:
  MailService MUST preserve accepted mail until semantic consumption.

Acceptance:
  after restart, accepted-but-unconsumed mail remains recoverable.
```

The requirement declares the desired invariant; the acceptance converts it into a
falsifiable evidence obligation. Do not "fix" the overlap by deleting either side.

## Local semantic closure

Make each important implementation unit recoverable without undeclared document-wide
inference. A downstream agent should be able to extract the unit and act on it with only
its declared dependencies. Do not over-normalize repetition to save lines.

```text
REQ-X-001

Actor:
  MailService

Requirement:
  MailService MUST preserve accepted mail until semantic consumption.

Condition:
  after a message is accepted

Acceptance:
  after restart, accepted-but-unconsumed mail remains recoverable.

Dependencies:
  persistence layer must survive process restart
```

## Authoring vs transformation

- **New authoring** ("design this", "propose this", "define the implementation contract"):
  you may introduce AUTHOR_JUDGMENT under the granted authoring authority. New decisions
  are not extracted truth; where provenance matters, mark them as such.
- **Transformation** (convert existing prose): transformation never strengthens. Source
  semantics → ATS representation. Do not make the source more authoritative, more
  mandatory, more certain, more causal, more complete, or more settled.

Basis vocabulary at a glance (mechanics live in the internal authoring skill, not here):

- EXPLICIT — stated in the source or in explicit author intent;
- DERIVED — obtained by mechanical derivation;
- INFERRED — model inference; suspicious-but-plausible cases surface as REVIEW_REQUIRED;
- UNAVAILABLE — not recoverable; a valid state;
- AUTHOR_JUDGMENT — a new decision made under granted authoring authority (new authoring only).

## Version behavior

- New durable authoring resolves ATS-1 `1.0.0-draft.2` under the binding policy. The
  policy pins the edition — no `--spec-version` override is needed.
- Legacy / historical material stays `1.0.0-draft.1` unless migration is explicit.
- A draft.2 artifact under a draft.1 policy is a refusal, never a silent downgrade.
- A draft.1 artifact must not silently acquire draft.2 semantics.
- An explicit `--spec-version` always wins.

## Procedure (standalone)

1. Bind the input before drafting. For a transformation, preserve the source
   locator, media type, `content_sha256`, and `normalized_sha256` in the IR's
   `source` object. For new authoring, record the explicit request or granted
   author intent as the source basis; mark newly introduced decisions
   `AUTHOR_JUDGMENT`.
2. Construct one `ats.text_ir.v1` document from the source or intent. Its required
   top-level fields are `schema_version`, `artifact_id`, `source`,
   `policy_snapshot_id`, `language`, `audience`, `sections`, and
   `extraction_status`. Each section carries a `section_id`, `profiles`
   (`SPECIFY`, or a declared composition), `claims`, `evidence`, `relations`,
   and `update_indicators`. Put the material actor, action, object, force,
   conditions, scope, exceptions, dependencies, failure behavior, stable
   coordinates, acceptance criteria, and semantic basis on the relevant claims;
   use `UNAVAILABLE` or an extraction issue instead of guessing.
3. Resolve the policy when the environment has one:
   `ats policy resolve implementation_spec` — the resolved snapshot supplies
   `policy_snapshot_id` and pins the edition.
4. Run the deterministic checks in order:
   - `ats ir lint <ir.json> --policy <policy>` — structural checks and rule
     detectors bound to the policy; continue only when required failures are zero;
   - render the human-readable Markdown document and its trace sidecar from the
     validated IR, preserving stable claim coordinates. Emit the IR lint report,
     output-lint report, and candidate receipt beside those artifacts;
     The four-file bundle is `<document>.md`, `<document>.trace.json`,
     `<document>.lint.json`, and `<document>.receipt.json`; the trace binds
     each marked block to its section, claim, evidence, relation, and stable
     coordinate IDs. For every material requirement, render distinct
     requirement, acceptance-criterion, and authority blocks when applicable.
     Preserve every stable coordinate verbatim, and never render an
     `INFERRED` or `UNAVAILABLE` value as an explicit fact.
     The receipt is a candidate evidence record, not an acceptance claim; final
     semantic acceptance belongs to an authorized human or governed external
     authority, never to the component that produced the bundle.
   - `ats output lint <document> --trace <trace> --ir <ir.json> --policy <policy>`
     — proves the rendered document realizes the declared IR and that trace
     blocks point back to the right claims;
   - `ats output verify-receipt <receipt> --ir <ir.json> --document <document> --policy <policy>`
     — re-checks the candidate receipt against the IR, document, trace bindings,
     and policy.
5. Treat `REVIEW_REQUIRED` honestly: it is a semantic concern the machinery
   cannot decide. Resolve it with better evidence or a typed `UNAVAILABLE`;
   never delete the material or paper over it. Do not report success past an
   unresolved `REVIEW_REQUIRED` unless it is genuinely non-material.
6. Ask a human only when an unresolved semantic distinction blocks the requested
   artifact or action. Routine authoring requires almost no human grounding.
7. Advanced: `ats planning project <ir.json> --policy <policy> --artifact-sha256 <sha>`
   projects an accepted spec into sealed planning input — task identity is derived
   there, distinct from the spec's requirement IDs.

## Examples

### Implementation specification unit

```text
REQ-014  On checkout, the order service MUST persist the order and decrement inventory
         in a single transaction.
Trigger:   POST /checkout with a validated cart.
Condition: account credit limit is not exceeded.
Exception: promotional orders marked no-inventory skip the inventory decrement.
Failure:   a partial failure aborts the transaction; the client receives 503 and may retry.
AC-014    After a successful checkout, order and inventory state are consistent even if
          the process crashes mid-commit.
```

### Protocol fragment

```text
PROTO-3  A replica MUST answer a heartbeat within 1 second of receiving it.
Scope:      intra-cluster links only; client links are out of scope.
PROTO-4  A replica MUST transition to FOLLOWER after 3 consecutive missed heartbeats.
Dependency: clock synchronization within 100 ms.
```

### Acceptance contract

```text
AC-1  On a clean install, `ats spec status` prints the imported edition and exits 0.
AC-2  A draft.2 IR linted under a draft.1 policy exits non-zero with a refusal —
      never a silent downgrade.
```

## Never

- Never collapse semantic identity into task identity.
- Never treat requirement/AC overlap as a defect.
- Never invent authority.
- Never silently strengthen.
- Never decorate with IDs.
- Never claim conformance the checks did not establish.
- Never optimize for prose minimalism.

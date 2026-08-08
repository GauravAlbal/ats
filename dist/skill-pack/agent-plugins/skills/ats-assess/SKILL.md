---
name: ats-assess
description: Author ATS-1 reasoning artifacts — diagnosis, postmortem, technical assessment, architecture comparison, recommendation under uncertainty — preserving evidence, inference, judgment, and force.
---

# ATS-1 assessment author

You turn a reasoning task into an ATS-1 assessment: a durable document whose
observations, inferences, judgments, forecasts, and recommendations are
explicitly separated, whose uncertainty is preserved, and whose force is never
silently strengthened. The reader must be able to tell what happened, what
evidence supports it, why the author believes it, and how confident that belief
is — without reconstructing undeclared reasoning.

## Purpose

`ats-assess` produces reasoning artifacts: technical diagnosis, forensic
investigation, postmortem, design assessment, architecture comparison,
technical recommendation, risk analysis, evaluation result, uncertainty-bearing
judgment. They are consumed by humans and machine readers (planning, review,
acceptance); every material claim carries its discourse role, its basis, and
its force.

## When to use / when not to use

Use `ats-assess` when the deliverable is a conclusion reached under
uncertainty: explaining an incident, investigating a failure, evaluating a
design, comparing architectures, assessing risk, making a recommendation. An
artifact may be pure `ASSESS` or compose `ASSESS + SPECIFY` when a
recommendation carries requirements forward (architecture proposal, RFC); the
`SPECIFY` part belongs to `ats-spec`. Do not use it for durable buildable
artifacts (→ `ats-spec`), value-adding review of existing prose (→
`ats-review`), or scratch/casual prose — ATS is not a universal writing style.

## Standalone contract

This public skill is self-contained. It does not invoke or require any
repository-only compiler skill. Install ATS and use this skill's procedure;
the CLI, schemas, and checks named below are the complete execution surface.

## Mini-constitution

1. Preserve meaning before improving surface form.
2. Do not invent authority.
3. Separate observation, inference, judgment, recommendation, and requirement when the distinction matters.
4. Preserve exact normative force.
5. Unknown is a valid state.
6. Remove surface material before removing material relations.
7. Stable semantic coordinates survive transformation.
8. Prefer local semantic closure for units expected to survive extraction.
9. Acceptance evidence is not the same discourse role as the requirement it verifies.
10. Ask only when unresolved meaning blocks the requested action.

## Version behavior

- New durable authoring resolves ATS-1 `1.0.0-draft.2` under the binding
  policy (which pins the edition; no `--spec-version` override unless the user
  passes one).
- Legacy/historical material (corpus, annotation bench, unlabeled older
  artifacts) is interpreted under `1.0.0-draft.1` unless migration is explicit.
- A draft.2 artifact under a draft.1 policy is a **refusal**, never a silent
  downgrade; a draft.1 artifact must not silently acquire draft.2 semantics.

## Authoring vs transformation

- **Transformation** compiles existing prose into an ATS assessment and adds
  nothing material. The source is the authority; you MUST NOT silently make it
  more authoritative, mandatory, certain, causal, complete, or settled.
- **New authoring** (you are asked to diagnose, assess, recommend) grants
  authority to introduce material judgments, marked `AUTHOR_JUDGMENT` and kept
  distinct from extracted source truth.

### Basis vocabulary at a glance

| basis | meaning |
|---|---|
| `EXPLICIT` | the source or granted intent states it directly |
| `DERIVED` | mechanically derived from stated material (e.g. computed) |
| `INFERRED` | you reasoned to it; it stays an inference, never an observed fact |
| `UNAVAILABLE` | cannot be established from source or intent; a valid value |
| `AUTHOR_JUDGMENT` | intentionally introduced under new-authoring authority |

## Discourse distinctions

Preserve these roles where material; do not force labels where ordinary prose
remains unambiguous; do not collapse materially different roles. An inference
written as an observation hides the reasoning the reader must reconstruct; an
observation reported as an inference fabricates uncertainty:

```text
definition          what a term means in this document
observation         what was seen, measured, or happened
sourced report      what a named source reported
assumption          what is taken as given without proof
inference           what is reasoned from other claims
judgment            the author's weighing of alternatives
forecast            what is predicted to happen
recommendation      what the author advises doing
requirement         what someone must or should do
boundary            what the assessment does and does not cover
exception           a condition under which a claim does not hold
open question       a question the evidence does not settle
insufficiency       a gap where evidence is not enough
```

Never merge two roles to make the document read better.

## Force separation

Five force axes are distinct; one must never stand in for another:

```text
event likelihood      the probability of the event
assessment confidence how robust the judgment is
evidential force      how far the evidence discriminates
causal force          the asserted cause-effect relationship
deontic force         obligation type and strength
```

Four collapses are prohibited:

1. **MUST NOT collapse likelihood into confidence.** "Likely" is about the
   event; "high confidence" is about the judgment. A confident author can still
   report an unlikely event.
2. **MUST NOT collapse supports into establishes.** Evidence that supports a
   claim does not establish it.
3. **MUST NOT collapse correlated with into caused by.** Association is not
   causation; name the causal claim separately, or leave causal force
   unasserted.
4. **MUST NOT collapse recommended into required.** A recommendation carries
   advisory force; a requirement carries obligation. Rewriting "we recommend X"
   as "X must be done" invents authority.

## Unknown state

When evidence cannot establish a material claim, the valid output is
`UNAVAILABLE / insufficient / unresolved`. Never make the assessment more
decisive to feel complete. Contradictory evidence may coexist — record both and
the insufficiency; an insufficient-evidence conclusion is complete, not
defective; an open question is valid output and inventing an answer is
fabrication.

## The diagnostic rule

A diagnostic MUST distinguish **what happened** from **why we believe it
happened**: the event record (observations, observed sequence, measured behavior)
versus the reasoning record (competing explanations, causal assessment, confidence).
Never let a causal assessment absorb the observation it explains; the event record must
survive later changes.

## Machinery

The CLI is the authority for conformance; the skill is not. Run the
deterministic checks before reporting success:

1. **Lint the IR** under the binding policy — proceed only when
   `conformance.mechanical == "PASS"` and `summary.required_failed == 0`:

   ```bash
   ats ir lint path/to/assessment.ir.json --policy path/to/policy.json
   ```

2. **Lint the rendered output** against its trace and IR:

   ```bash
   ats output lint path/to/assessment.md --trace path/to/assessment.trace.json \
     --ir path/to/assessment.ir.json --policy path/to/policy.json
   ```

3. **Verify the receipt** when one is produced:

   ```bash
   ats output verify-receipt path/to/assessment.receipt.json \
     --ir path/to/assessment.ir.json --document path/to/assessment.md \
     --policy path/to/policy.json
   ```

4. **Policy resolution** (fleet environments): `ats policy resolve
   <artifact-class> --repo <repo>` fixes whether ATS applies and which gates
   run. A class outside `required_for` is out of scope — report that, do not
   half-assess. `ats planning project` (advanced) may be offered after
   acceptance when the assessment feeds downstream work; never a
   prerequisite.

### REVIEW_REQUIRED and the human

`REVIEW_REQUIRED` findings are surfaced honestly: report the count and items;
never claim conformance the checks did not establish. A `REVIEW_REQUIRED` item
is not a failure and is not a blocking question — ask a human only when an
unresolved semantic distinction blocks the action (constitution 10).
Resolution order: source/intent → mechanical derivation → author judgment →
typed unknown → continuation → human only if the action requires resolution.

### Recipe guidance

Artifact shapes for diagnostic, postmortem, architecture comparison, RFC, and
risk analysis live in `docs/ARTIFACT_RECIPES.md` (canonical) and
`skills/public/recipes/`. Recipes are authoring guidance, not normative
profiles; exact section names may vary, semantic roles must remain recoverable.

## Examples

### 1. Postmortem

```text
ASSESS
  incident            queue drained, 41,208 messages lost over 09:12-09:41 UTC
  observed sequence   [observation] backpressure rose; worker pool exited;
                      queue file rotated; replay never re-armed
  evidence            logs, queue-file timestamps, rotation config (refs)
  causal factors      [inference] rotation raced the drain; [judgment] likely
                      primary, confidence medium
  confidence          high on sequence, medium on causal role
  detection failures  [observation] no alert fired; [judgment] coverage gap
  corrective actions  [recommendation] re-arm replay on rotation, add alert
  unresolved          whether rotation is the only trigger — UNAVAILABLE
```

What happened (sequence, evidence) stays separate from why we believe it
(causal factors, confidence); the recommendation is advisory unless adopted.

### 2. Diagnostic

```text
ASSESS
  observed behavior    [observation] reads return 404 after deploy 7b3
  expected behavior    [observation] reads return 200 for existing keys
  evidence             [observation] 404 rate tracks the router rollout, not
                       storage errors; key present in store
  competing explanations
                       [inference] route table change dropped the key prefix
                       [inference] store re-index lag — contradicted by data
  causal assessment    [judgment] prefix-loss best explains the pattern
  confidence           medium — high on correlation with rollout, lower on the
                       exact mechanism
  insufficiency        no direct evidence of the prefix write
  recommended action   [recommendation] restore route table, then verify
```

"404s track the rollout" is correlated-with, not caused-by; the causal claim
is a separate judgment with its own confidence.

### 3. Architecture comparison

```text
ASSESS
  boundary             candidates A and B for the ingest path only
  observations         [observation] A holds latency < 200 ms in load tests;
                       B holds < 5 s
  evidence             benchmark runs, configs, hardware (refs)
  assumptions          [assumption] traffic stays within the tested envelope
  inference            A's cost scales with partition count
  judgment             A fits the latency requirement; B fits ops simplicity
  recommendation       choose A if latency binds; choose B otherwise
  open questions       operational cost at 10x volume — UNAVAILABLE
  exceptions           if the team cannot staff streaming ops, B's margin wins
```

## Never

- Never convert an observation into a causal claim.
- Never collapse likelihood into confidence.
- Never turn a recommendation into a requirement.
- Never invent evidence.
- Never make the document more decisive than the evidence.
- Never claim conformance the checks did not establish.

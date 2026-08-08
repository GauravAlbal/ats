# ATS-1 Artifact Recipes

Canonical authoring guidance for the public ATS skills (`ats`, `ats-spec`,
`ats-assess`, `ats-review`). Recipes are **authoring guidance**, not normative
ATS profiles: they compose the stable profiles `ASSESS` and `SPECIFY`.
Exact section names MAY vary; the semantic roles MUST remain recoverable.

## The mini-constitution

The public skills carry this governing layer. Every public skill and every recipe
is consistent with it:

1. **Preserve meaning before improving surface form.**
2. **Do not invent authority.**
3. **Separate observation, inference, judgment, recommendation, and
   requirement when the distinction matters.**
4. **Preserve exact normative force.**
5. **Unknown is a valid state.**
6. **Remove surface material before removing material relations.**
7. **Stable semantic coordinates survive transformation.**
8. **Prefer local semantic closure for units expected to survive extraction.**
9. **Acceptance evidence is not the same discourse role as the requirement it
   verifies.**
10. **Ask only when unresolved meaning blocks the requested action.**

## Version law (applies to every recipe)

- **New durable authoring** resolves ATS-1 `1.0.0-draft.2` under the binding
  policy. The policy document pins the edition; no `--spec-version` override
  is needed.
- **Legacy / historical material** stays `1.0.0-draft.1` unless migration is
  explicit.
- A draft.2 artifact under a draft.1 policy is a **refusal**, never a silent
  downgrade; a draft.1 artifact never acquires draft.2 semantics by being
  reopened.
- An explicit `--spec-version` always wins.

---

## Architecture recipe

Composed `ASSESS + SPECIFY`.

```text
ASSESS
  current state
  evidence
  problem
  constraints
  alternatives
  judgment
  unresolved points

SPECIFY
  target state
  authority boundary
  requirements
  dependencies
  failure behavior
  migration
  acceptance
  update indicators
```

Must keep recoverable: what the current system does (observation) vs what the
target system must do (requirement) vs why this target was chosen (judgment).

## RFC / technical proposal recipe

Composed `ASSESS + SPECIFY`.

```text
ASSESS
  problem
  evidence
  current constraints
  considered alternatives
  decision basis

SPECIFY
  selected target
  scope
  non-goals
  requirements
  compatibility
  migration
  evidence required for acceptance
  reversal/update conditions
```

## Implementation program recipe

Composed `ASSESS + SPECIFY`.

```text
ASSESS
  why program exists
  current evidence
  constraints
  risk

SPECIFY
  destination
  work units
  dependency graph
  invariant set
  acceptance criteria
  stop conditions
  deferred work
```

Programs SHOULD remain shardable. Do not collapse locally closed work units
into one elegant narrative section if doing so damages downstream extraction.

## Diagnostic recipe

`ASSESS`.

```text
ASSESS
  observed behavior
  expected behavior
  evidence
  competing explanations
  causal assessment
  confidence
  insufficiency
  recommended next action
```

A diagnostic MUST distinguish **what happened** from **why we believe it
happened**.

## Postmortem recipe

`ASSESS`.

```text
ASSESS
  incident
  impact
  observed sequence
  evidence
  causal/contributing factors
  confidence
  detection failures
  recovery behavior
  corrective recommendations
  unresolved questions
```

Do not force causal certainty. `UNAVAILABLE` for a causal factor is a valid
conclusion.

---

## Recipe rules that apply to all

- **Stable coordinates when they pay for themselves.** `REQ-*`, `DEC-*`,
  `AC-*`, protocol and program/work-item IDs earn their place when downstream
  systems join on them (planning, tasks, acceptance, receipts). Never generate
  IDs decoratively. One ATS requirement does not imply one implementation task.
- **Local semantic closure.** Units expected to survive extraction — a work
  unit, a requirement block, an acceptance contract — must be operatively
  intelligible from the unit plus its declared dependencies, without
  undeclared document-wide inference. Do not over-normalize repetition; an
  acceptance criterion may restate the requirement it verifies (intentional
  semantic redundancy, constitution #9).
- **Unknown is cheaper than invented authority.** Missing evidence, missing
  precedence, missing measurement → `UNAVAILABLE` / `unresolved`, not a guess.
- **Transformation never strengthens.** Converting existing prose to ATS must
  not make it more authoritative, more mandatory, more certain, more causal,
  more complete, or more settled. Material inferred values stay inferred /
  review-required / unavailable.
- **New authoring may judge.** When the user grants design authority
  ("design this", "propose this", "write an architecture"), the author may
  introduce `AUTHOR_JUDGMENT` decisions — and must distinguish them from
  extracted source truth where provenance matters.

---
name: ats
description: The ATS-1 front door — author, transform, or review durable technical artifacts, routed to the right ATS skill with the correct standard version and deterministic checks.
---

# ATS-1 — Applied Technical Semantics front door

This is the one skill name you need. You start here with any ATS-1 request —
writing a new technical artifact, converting material that already exists, or
reviewing an existing document — and this skill routes you to the correct
public skill, profile, artifact recipe, standard version, and deterministic
checking path.

In this name, “Applied” means semantics applied to practical technical work,
not universal applicability; ATS remains scoped to durable technical artifacts.

ATS-1 is a technical writing standard for durable engineering artifacts whose
operative meaning must survive handoff: architecture, RFCs and technical
proposals, implementation specifications, capability and implementation
programs, implementation plans, diagnostics, postmortems, technical
assessments, and acceptance/change-control records. It is not a universal
writing style.

## Purpose

Handle the whole ATS-1 request surface in one place:

- new technical authoring;
- transformation of existing technical material;
- artifact review;
- profile selection (`ASSESS` / `SPECIFY` / declared composition);
- artifact recipe selection;
- policy/version resolution;
- deterministic checking.

You do not need ATS internals (TextIR, basis records, lint reports, receipts)
to use this skill. Those stay available as machine records; ordinary user
prose is plain language.

## When to use

- The user asks for any durable technical artifact under ATS, in any phrasing:
  "use ATS for…", "write this in ATS", "turn this into an ATS…", "review
  this with ATS".
- The user's request matches an ATS artifact family: architecture, RFC /
  technical proposal, implementation specification, capability program,
  implementation plan, diagnostic, forensic analysis, postmortem, technical
  assessment, acceptance record, change-control record.
- The user is unsure which ATS skill applies. This skill decides.

## When not to use

- Scratch notes, exploratory chat, brainstorming, casual explanation, ordinary
  issue comments, marketing copy, blog posts, README marketing: ATS does not
  apply. Decline politely and do the ordinary thing — do not force ATS onto
  casual prose.
- The user wants only a style pass on an already-settled document: that is
  `ats-review`'s advisory surface at most, never an ATS conformance claim.
- The user asks a question about the ATS standard itself (rule registries,
  profiles, spec editions): answer from the standard, do not route through
  authoring.

## Standalone contract

This public skill is self-contained. It does not invoke or require any
repository-only compiler skill. Install ATS and follow the selected public
skill's procedure; the CLI, schemas, and checks named there are the complete
execution surface.

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

## How to route

### Step 1 — Determine the mode

- **New authoring** — nothing exists yet, or the user grants design authority
  ("design this", "propose this", "write an architecture", "define the
  implementation contract"). You may introduce `AUTHOR_JUDGMENT` decisions
  under that authority, marked as new rather than extracted truth.
- **Transformation** — existing prose is converted to ATS representation.
  Transformation never strengthens: it must not make the source more
  authoritative, more mandatory, more certain, more causal, more complete, or
  more settled. Material inferred values stay inferred / review-required /
  unavailable.
- **Review** — the user hands you an existing document and wants it examined
  for semantic risk. Review is the default operation; transformation happens
  only when explicitly requested after the findings.

### Step 2 — Determine the artifact intent

Classify what the user actually wants produced or examined. The artifact
intent drives the profile, the recipe, and — in fleet environments — the
policy resolution. Apply the policy's `required_for` classification, never a
guess from the filename.

### Step 3 — Resolve whether ATS is appropriate

ATS applies to durable technical artifacts whose operative meaning must
survive handoff. Casual, exploratory, or marketing material is out of scope:
decline politely and proceed with ordinary handling. When a fleet policy is
present, `ats policy resolve` decides applicability for the artifact class and
which enforcement gates apply.

### Step 4 — Select the profile

- `SPECIFY` — the artifact is buildable: requirements, contracts, target
  states, acceptance criteria, protocols.
- `ASSESS` — the artifact is a conclusion reached under uncertainty: diagnosis,
  comparison, postmortem, assessment, recommendation.
- **Declared composition** — `ASSESS + SPECIFY` when one artifact carries both
  (architecture proposal, RFC): the reasoning half and the buildable half stay
  in their own profiles with their own obligations.

### Step 5 — Resolve the standard version (the front-door law)

Two defaults, never collapsed into one:

- **New durable authoring** resolves ATS-1 `1.0.0-draft.2` under the binding
  policy. The policy pins the edition; no `--spec-version` override is needed.
- **Legacy / historical material** stays `1.0.0-draft.1` unless migration is
  explicit.
- An explicit `--spec-version` always wins.
- A draft.2 artifact under a draft.1 policy is a **refusal**, never a silent
  downgrade. A draft.1 artifact must not silently acquire draft.2 semantics.

### Step 6 — Route to the right skill

| mode | artifact intent | public skill | recipe |
|---|---|---|---|
| new / transform | implementation spec, protocol, architecture target, RFC normative section, capability program, implementation program, punchlist, acceptance contract, migration plan | `ats-spec` | implementation program (or RFC for proposals) |
| new / transform | architecture proposal, RFC / technical proposal (ASSESS + SPECIFY) | `ats-spec` (SPECIFY half) + `ats-assess` (ASSESS half) | architecture / RFC |
| new / transform | diagnosis, forensic analysis, postmortem, design assessment, architecture comparison, technical recommendation, risk analysis, evaluation result | `ats-assess` | diagnostic / postmortem |
| new / transform | technical assessment, acceptance record, change-control record | `ats-assess` | postmortem (assessment shape) |
| review | any existing technical prose (ATS or pre-ATS) | `ats-review` | none (findings, not recipes) |
| not ATS | scratch notes, casual prose, marketing, exploratory chat | none | none — decline politely |

`ats-spec` and `ats-assess` are the two authoring surfaces; `ats-review` is the
review surface. The front door never authors directly — it routes. Recipes are
authoring guidance, not normative profiles. In the canonical source, use
`docs/ARTIFACT_RECIPES.md` and `skills/public/recipes/`; in generated
generic/Codex packs, use `recipes/ARTIFACT_RECIPES.md` and `recipes/`; in
generated Claude/Agent Plugins packs, use
`references/ARTIFACT_RECIPES.md` and `references/`. The containing host README
identifies the installed layout.

## Required routing examples

```text
"Use ATS to write an architecture proposal for this change."
→ new authoring · ASSESS + SPECIFY composition · ats-spec + ats-assess,
  architecture recipe · 1.0.0-draft.2

"Use ATS to turn these design notes into an implementation specification."
→ transformation · SPECIFY · ats-spec, implementation program recipe · draft.2,
  source semantics never strengthened

"Review this existing RFC with ATS."
→ review mode · ats-review (BLOCK / REVIEW_REQUIRED / ADVISORY) · no conformance
  claim unless the user requested ATS conformance

"Convert this incident analysis into an ATS postmortem."
→ transformation · ASSESS · ats-assess, postmortem recipe · draft.2,
  what-happened stays separate from why-we-believe-it

"Use ATS for this technical assessment."
→ new authoring · ASSESS · ats-assess · draft.2, uncertainty preserved
  (UNAVAILABLE is valid output)
```

## Required behaviors

1. Determine the mode: new authoring / transformation / review.
2. Determine the artifact intent.
3. Resolve whether ATS is appropriate for it (decline politely for
   non-applicable prose; the fleet policy's `required_for` classification
   decides applicability when one is present).
4. Select `ASSESS`, `SPECIFY`, or a declared composition.
5. Resolve the standard version correctly — the two-default law above.
6. Use draft.2 for new durable authoring.
7. Preserve draft.1 interpretation for historical material unless migration is
   explicit.
8. Route to the selected public skill (`ats-spec`, `ats-assess`, or
   `ats-review`). Each public skill carries its own authoring or review
   procedure; no repository-only compiler skill is invoked or required.
9. Run deterministic validation before reporting success.
10. Surface `REVIEW_REQUIRED` honestly.
11. Ask a human only when an unresolved semantic distinction blocks the
    requested artifact/action.
12. Prefer `UNAVAILABLE` or preserved uncertainty over invented completion.
13. Return a useful human artifact by default.
14. Make IR/trace/receipt paths available without dumping compiler internals
    into ordinary user prose.

## Deterministic machinery

The CLI is the authority for conformance; the skill is not. Run these before
reporting success (the routed skill runs them; this front door holds the same
standard):
```bash
ats policy resolve <artifact-class>   # fleet envs: applicability + version
ats ir lint <artifact>.ir.json --policy <policy>
ats output lint <artifact>.md --trace <artifact>.trace.json \
  --ir <artifact>.ir.json --policy <policy>
ats output verify-receipt <artifact>.receipt.json
```

- `ats policy resolve` — decides applicability and enforcement for the artifact
  class when a fleet policy is present; a class outside `required_for` is out
  of scope: say so, do not half-apply ATS.
- `ats ir lint` — structural checks and rule detectors over the meaning ledger.
- `ats output lint` — proves the rendered document realizes the declared IR.
- `ats output verify-receipt` — re-checks a receipt against its artifacts.
- `ats planning project` — advanced, offered after acceptance when the
  artifact feeds downstream planning. Never a prerequisite.

Do not claim conformance unless these checks establish it. `REVIEW_REQUIRED`
findings are surfaced honestly with their count and items; they are not
failures, and they are not blocking questions.

### Human questions

Ask a human only when an unresolved semantic distinction blocks the requested
artifact or action. Resolution order: explicit source or author intent →
mechanical derivation → authorized author judgment → typed unknown
(`UNAVAILABLE`) → non-blocking continuation → human only if the action
requires resolution. Never ask "what should the authority hierarchy be?"
merely because none exists — record `authority_precedence = UNAVAILABLE`.

## Examples — worked routing outcomes

### 1. New architecture proposal

```text
User:  "Use ATS to write an architecture proposal for this change."
Route: new authoring · ASSESS + SPECIFY · ats-spec + ats-assess ·
       architecture recipe · 1.0.0-draft.2
Outcome:
  - ASSESS half: current state (observation), constraints, alternatives,
    judgment, unresolved points — each role preserved.
  - SPECIFY half: target state, authority boundary, requirements (REQ-*),
    dependencies, failure behavior, migration, acceptance (AC-*).
  - New design decisions marked AUTHOR_JUDGMENT; nothing extracted from the
    request is strengthened. Lints green, receipt verified; the user gets a
    readable proposal plus machine records, no TextIR or basis internals.
```

### 2. Legacy material stays legacy

```text
User:  "Convert this 2024 incident analysis into an ATS postmortem."
Route: transformation · ASSESS · ats-assess · postmortem recipe ·
       1.0.0-draft.1 (historical material; no explicit migration)
Outcome:
  - The source's causal claims remain causal *claims* — no observation is
    upgraded, no recommendation becomes a requirement.
  - A causal factor the source does not establish: UNAVAILABLE, not a guess.
  - Edition reported as draft.1; never silently re-interpreted under draft.2.
```

### 3. Review stays review

```text
User:  "Review this existing RFC with ATS."
Route: review mode · ats-review · no recipe, no version resolved for the
       prose itself
Outcome:
  - Findings: "normative force ambiguous — acts like a requirement without
    establishing MUST vs SHOULD"; "missing actor — the obligation has no
    subject".
  - No rewrite, no quality score, no "nonconforming" verdict unless ATS
    conformance was requested as a gate. Conversion only if the user asks.
```

## Never

- Never force ATS onto casual prose, scratch notes, marketing, or exploratory chat.
- Never collapse the two defaults into one global standard version.
- Never let a draft.2 artifact silently downgrade to draft.1.
- Never dump TextIR, basis records, rule-registry, or receipt-schema internals into ordinary user output.
- Never claim conformance the deterministic checks did not establish.
- Never ask a human for a non-blocking unknown — type it `UNAVAILABLE` and continue.
- Never invent authority, force, evidence, or completion the source does not support.

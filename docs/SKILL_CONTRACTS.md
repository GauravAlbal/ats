# Skill contracts

This document specifies the **contracts** of both skill layers — what each skill consumes, what
it emits, what it must refuse, what it is and is not entitled to decide, and where it hands off.
The skills' own instructions live in `skills/*/SKILL.md`; this document is the interface those
instructions must satisfy.

The current public identity is **ATS-1 — Applied Technical Semantics**.
“Applied” means semantics applied to practical technical work, not universal
applicability; this naming does not alter any skill contract.

## Public layer — the operator skill surface

Four public skills make up the surface an ordinary coding-agent user installs and invokes. They
are the canonical source the generated host packages under `dist/skill-pack/` are derived from
(skill-pack release `0.1.2`, bound to the canonical source by tree hash in
`ats.skill_pack_manifest.v1`). Canonical source comes first: complete the
public skills and recipes, then generate and verify the host forms; generated
output is never hand-maintained. Release `0.1.2` is published under
`v0.1.2-skill-pack`; release `0.1.1` remains available as the previous release.
The internal compiler contracts below are repository-only implementation references; they stay
out of the operator's way and are not callable dependencies of the public pack. Each public
skill's own instructions in `skills/public/*/SKILL.md` are self-contained and satisfy the
operator-facing interface.

| Skill | Path | Job |
|---|---|---|
| ats (front door) | `skills/public/ats/SKILL.md` | any ATS-1 request → mode, profile, recipe, standard version, deterministic checking path |
| ats-spec | `skills/public/ats-spec/SKILL.md` | durable buildable artifact → specification decomposable without reconstructing undeclared semantic state |
| ats-assess | `skills/public/ats-assess/SKILL.md` | reasoning task → assessment preserving discourse roles, force separation, and uncertainty |
| ats-review | `skills/public/ats-review/SKILL.md` | existing technical prose → review findings; conversion only on request |

### Contract summary — `ats` (front door)

**Consumes.** The user's request in any phrasing — "use ATS for…", "write this in ATS", "review
this with ATS" — plus the material to author, transform, or review. It may route to any other
public skill.

**Emits.** A resolved route — mode (new authoring / transformation / review), profile
(`ASSESS` / `SPECIFY` / declared composition), artifact recipe, and standard version — and, by
default, a useful human artifact with the deterministic checks that gate it. IR/trace/receipt
paths stay available without dumping compiler internals into ordinary user prose.

**Decides.** Whether ATS applies at all (scratch and casual prose do not force ATS); artifact
intent; mode; the standard version (draft.2 for new authoring, draft.1 for legacy
interpretation, explicit `--spec-version` wins, a draft.2 artifact never silently downgrades);
which public skill, profile, and recipe to invoke.

**Refuses.** Inventing authority, force, evidence, or completion the source does not support;
asking a human when no unresolved semantic distinction blocks the requested action; claiming
conformance the checks did not establish.

### Contract summary — `ats-spec`

**Consumes.** A durable buildable artifact request: implementation specification, protocol,
architecture target, RFC normative section, capability or implementation program, punchlist,
acceptance contract, migration plan. Composes with `ats-assess` when a recommendation carries
requirements forward (architecture proposal, RFC).

**Emits.** A document from which implementation work can be decomposed without reconstructing
undeclared semantic state: actors, actions, objects, deontic force, triggers, conditions, scope,
exceptions, quantitative bounds, stable coordinates (`REQ-*`/`DEC-*`/`AC-*`/protocol/work-item
IDs where they provide downstream value — never decorative), dependencies, non-goals, failure
behavior, proof obligations, acceptance criteria, update/reversal conditions, and typed
unresolved state.

**Refuses.** Optimizing primarily for minimum length or surface elegance; collapsing requirement
identity into execution-task identity (one requirement does not imply one task); silently
introducing new requirement authority during transformation; strengthening force.

### Contract summary — `ats-assess`

**Consumes.** A reasoning task: diagnosis, forensic investigation, postmortem, design
assessment, architecture comparison, technical recommendation, risk analysis, evaluation
result, uncertainty-bearing judgment.

**Emits.** A reasoning artifact in which discourse roles stay distinct where material
(definition, observation, sourced report, assumption, inference, judgment, forecast,
recommendation, requirement, boundary, exception, open question, insufficiency); force stays
separate (likelihood ≠ confidence, supports ≠ establishes, correlated with ≠ caused by,
recommended ≠ required); and `UNAVAILABLE`/insufficient/unresolved is a valid, complete state.

**Refuses.** Collapsing materially different discourse roles; making the assessment more
decisive to feel complete; inventing basis or confidence.

### Contract summary — `ats-review`

**Consumes.** Arbitrary existing technical prose — RFCs, architecture documents, plans,
postmortems, diagnostics, generated agent specs, or artifacts already in ATS form. The material
does not need to be ATS, and the user does not need ATS internals.

**Emits.** Findings in named families (implicit authority, semantic strengthening, ambiguous
normative force, missing actor, missing scope, missing exception, hidden dependency, untyped
uncertainty, causal overclaim, evidence/claim mismatch, requirement lacking acceptance
evidence, locally incomplete implementation unit, unstable terminology, coordinate loss,
source/provenance ambiguity), presented in three classes: `BLOCK` (deterministic conformance
failure, only when policy makes ATS applicable), `REVIEW_REQUIRED` (semantic concern),
`ADVISORY` (style).

**Decides.** Default is review, not rewrite; conversion may be offered or executed only when
explicitly requested.

**Refuses.** Silent rewrite; rewriting `SHOULD`→`MUST` to look rigorous; inventing a quality
score; calling an arbitrary non-ATS document "nonconforming" unless ATS conformance was
requested; passing material semantic uncertainty.

### The mini-constitution

Every public skill is governed by the ten-law mini-constitution. Each SKILL.md
carries the compact form; the full layer lives in `docs/ARTIFACT_RECIPES.md` (the canonical
recipes reference) and `docs/SKILL_PACK_NORTH_STAR.md` (the program north star; ADR-0023):

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

### Public-vs-internal boundary

Public skills are the operator surface: they follow their standalone source/intent →
TextIR → render → receipt procedure and invoke deterministic machinery through the
CLI (`ats ir lint`, `ats output lint`, `ats output verify-receipt`, `ats policy
resolve`, `ats planning project`). They do not invoke or require a repository-only
compiler skill, and they do not duplicate the 36-rule registry. Internal skills speak
TextIR, basis records, and lint reports; their contracts below are unchanged and
remain independently testable.
One canonical public source feeds OSS users and fleet consumers — host packages
are thin generated adapters of the same bytes, and a forked dialect would be a
defect.

### Version law

New durable authoring resolves draft.2 (fleet policy pins `text_policy.version =
1.0.0-draft.2`); legacy and historical material resolves draft.1 unless migration is explicit;
an explicit `--spec-version` wins; a draft.2 artifact under a draft.1 policy is a refusal,
never a silent downgrade; a draft.1 artifact must not silently acquire draft.2 semantics. The
public skills never collapse the two-default model into one global default (ADR-0020).

### Authority precedence

When layers disagree, precedence runs: **normative package** (`spec/ATS-1/…`, immutable,
sealed by its own manifest) > **public contract** (this document and `skills/public/*/SKILL.md`)
> **recipe** (`docs/ARTIFACT_RECIPES.md`, `skills/public/recipes/` — authoring guidance, not
normative profiles) > **host adapter** (generated `dist/skill-pack/{generic,claude,codex,
agent-plugins}/`). A generated host form that conflicts with the canonical skill is a packaging
defect: the canonical source wins and the pack is regenerated.

## Internal layer — the v0 compiler skills

Three repo-local skills sit at the front of the v0 pipeline. This document specifies their
**contracts** — what each consumes, what it emits, what it must refuse, what it is and is not
entitled to decide, and where it hands off. The skills' own instructions live in
`skills/*/SKILL.md`; this document is the interface those instructions must satisfy.

| Skill | Path | Job |
|---|---|---|
| IR author | `skills/ats-ir-author/SKILL.md` | source or explicit author intent → validated `ats.text_ir.v1` |
| ASSESS output | `skills/ats-assess-output/SKILL.md` | validated ASSESS IR → four-file output bundle |
| SPECIFY output | `skills/ats-specify-output/SKILL.md` | validated SPECIFY IR → four-file output bundle |

The two output skills share one contract; they differ only in the profile whose structural
obligations they must satisfy (§9.2 versus §9.3). They are separate skills because
`PROFILE_REQUIRED_ROLES` in `src/ats/output/lint.py` holds a different required display-role
set for each, and because a single skill covering both would have to choose a profile at
runtime — which is a policy resolution, not a rendering decision.

---

## Contract 1 — `ats-ir-author`

### Consumes

| Input | Required | Notes |
|---|---|---|
| Source material, or explicit structured author intent | Yes | One of the two. There is no third mode: the skill never invents subject matter. |
| Resolved ATS profile | Yes | `ASSESS` or `SPECIFY`. Resolved *before* IR construction, not inferred afterward from what got written. |
| Policy snapshot (`ats.policy_snapshot.v1`) | Yes | Supplies `policy_snapshot_id`, which the IR carries as a required field. |
| Force lexicon and glossary | Yes | The only vocabularies the IR may draw force terms from. |
| Fleet artifact policy (draft.2 D-G) | Yes (draft.2) | Resolved via `ats policy resolve <artifact-class> [--repo <path>]` *before* extraction. Fixes whether the class is `required_for` ATS-1, which enforcement gates apply, and the failure policy. Applicability is by artifact intent/policy, never inferred from filename. |

### Emits

Exactly three things, and no polished prose:

1. an `ats.text_ir.v1` document, canonically serialized;
2. its validation result — the sealed `ats.ir_lint_report.v1` produced by `ats ir lint`; and
3. provenance metadata: source locator, revision, `content_sha256`, `normalized_sha256`.

The IR's required top-level fields are fixed by `ats_text_ir_v1.schema.json`:
`schema_version`, `artifact_id`, `source`, `policy_snapshot_id`, `language`, `audience`,
`sections`, `extraction_status`. `source` itself requires `content_sha256` and `media_type`.

### What the skill may decide

- Which claims, evidence objects, relations, assumptions, boundaries, exceptions, forecasts,
  requirements, and update indicators the source or explicit intent actually supports.
- Which of the thirteen role distinctions each claim takes — observation, sourced report,
  assumption, inference, judgment, forecast, recommendation, requirement, permission,
  capability, exception, boundary, open question.
- How to decompose scope into fields rather than leaving it buried in prose (§7.6).
- Stable identifiers, through a documented deterministic scheme.
- (Draft.2) Which of the five §4.25 `semantic_basis` values a material value carries, and
  which coordinates belong in the document-level `stable_coordinates` block — both chosen
  from the source, never invented.
- (Draft.2) Whether a unit is locally closed: every field a reader needs is present in the
  unit or in a dependency the unit names (§4.24).

### What the skill may NOT decide

- **That an unstated thing is true.** It may never strengthen a claim, invent evidence, infer
  an unstated probability, or manufacture confidence. §11.7 forbids adding a material claim
  absent from the source; §8.6 and §8.9 forbid precision and confidence without a basis.
- **(Draft.2) That an inferred or unavailable value is source truth.** §7.19/`ATS-BASIS-002`
  forbid silently promoting `INFERRED`/`UNAVAILABLE` material to `EXPLICIT` — the permitted
  moves are preserve-as-`INFERRED`, represent-as-unresolved, omit-when-nonessential, propose
  a candidate interpretation, or ask for adjudication. `AUTHOR_JUDGMENT` is the only basis
  for new-authoring content and is never claimed without task-granted authority.
- **Which of several readings the author meant.** Where material ambiguity is unresolved, the
  skill surfaces it — `status: "ambiguous"` on the claim, candidate interpretations
  enumerated, an `extraction_issues` entry recorded — rather than choosing the convenient
  reading (§13.4).
- **Whether the artifact conforms.** That is the linter's output, and only for the dimensions
  the linter can reach.
- **That its own IR is accepted.** Acceptance authority is external (§14.11).

### Hard refusal conditions

The skill fails closed rather than emitting a weaker artifact when:

| Condition | Why | Spec |
|---|---|---|
| The profile cannot be resolved before construction | Every section MUST resolve to at least one content profile | §6.5 |
| Policy currentness cannot be established | The implementation MUST fail closed for required conformance claims; `ctx.policy()` raises `StalePolicyError` when the declared `snapshot_sha256` disagrees with the canonical bytes or the snapshot targets another spec version | §14.3, §6.6 |
| The exact source bytes cannot be bound to a content hash | Binding precedes evaluation | §14.2 |
| A required field is unavailable and no typed absence value exists for it | Typed insufficiency, never an unsupported pass | §20.6 |
| `ats ir lint` reports a `FAIL` on a required deterministic check | The skill runs the linter before returning; it does not return an artifact it knows is failing | §14.6 |
| The requested profile is a reserved profile | Reserved profiles inherit nothing by similarity | §9.5 |

Three coherence rules the IR linter will enforce anyway, so the skill must satisfy them up
front (`_ir_extraction_status`, `ATS-1` §7.16, §13.4):

- `extraction_status: "complete"` with any `extraction_issues` recorded is a `FAIL`;
- `extraction_status` of `partial`, `ambiguous`, or `unavailable` with **no**
  `extraction_issues` is a `FAIL` — the status must say what is missing;
- an `extraction_issues` entry with `status: "ambiguous"` and no
  `candidate_interpretations` is a `FAIL`, and repeated interpretations on an ambiguous claim
  are a `FAIL` because they are not materially distinct.

### Draft.2 obligations (the current public contract)

Five extraction-time obligations sit on top of the steps above, and the deterministic rules
`ATS-COORD-001/002`, `ATS-BASIS-001/002`, `ATS-PRES-003`, and `ATS-CLOSE-001` (§12.7.5)
verify what is mechanically verifiable:

1. **Record `semantic_basis` where material.** A material claim or requirement SHOULD declare
   one of the five §4.25 values verbatim (`EXPLICIT`, `DERIVED`, `INFERRED`, `UNAVAILABLE`,
   `AUTHOR_JUDGMENT`); the enum is schema-enforced, and when `basis_policy.declared` is true
   `IR-BASIS-SCHEMA` requires it on every material claim (`ATS-BASIS-001`).
2. **Preserve stable coordinates exactly.** The eight protected kinds (§4.23) are declared in
   the `stable_coordinates` block and used verbatim wherever the object appears. A
   coordinate MUST survive a transformation even when its proposition is recoverable
   through another coordinate — semantic equivalence does not imply coordinate equivalence
   (`ATS-COORD-001/002`).
3. **Produce locally closed units.** Each extractable normative unit carries its recovery
   fields (identity, actor, modality, action, object, condition/trigger, scope, exception,
   quantitative boundary, dependency, proof obligation, acceptance criterion,
   rationale/evidence reference, where applicable) or names its dependencies. `ATS-CLOSE-001`
   mechanically checks the SPECIFY minima.
4. **Prefer typed insufficiency over invented completion.** Gaps are `UNAVAILABLE`/
   `partial`/`ambiguous` with `extraction_issues` entries (§7.16, §20.6). Only
   action-blocking unresolved semantics are escalated, in ladder order (deterministically
   recover → Tribunal can adjudicate from evidence → record judgment → stay `UNAVAILABLE` →
   continue → human; D-I, ADR-0016).
5. **Never promote inferred material.** No `INFERRED`/`UNAVAILABLE` value is recorded as an
   explicit source-authoritative fact (§7.19, `ATS-BASIS-002`), and no protected relation is
   removed, weakened, strengthened, reversed, or made materially implicit to shorten the
   document (§11.3.2, `ATS-PRES-003`; locality-preserving redundancy is permitted and often
   preferred, §11.3.3 D-E).

Before returning, the skill runs the **twelve-item pivot checklist** in
`skills/ats-ir-author/SKILL.md`: transformation-or-authoring decided under granted authority; profile + fleet artifact
policy resolved before extraction; explicit source semantics preserved; basis recorded
where material; author judgments only under authority; no inferred-as-fact; coordinates
exact; local closure; typed insufficiency; operator asked only for action-blocking
semantics; IR fit for downstream decomposition (`requirement_id`/`decision_id`/
`acceptance_criterion_id`/`dependency_target` resolvable so the planning projection and Arq
can consume without re-authoring); and `ats ir lint` green on `mechanical` and `profile`
with `summary.required_failed == 0` before completion.

### Handoff

`ats ir lint PATH --policy POLICY [--source SOURCE]` →
`ats.ir.lint.lint_ir(ctx, ir_document, policy_document, source_path=...)` → a sealed
`ats.ir_lint_report.v1`. The skill returns that report alongside the IR. Findings it cannot
resolve deterministically go to a human or Arq adjudicator, never back into the IR as an
authorial guess. Draft.2 runs lint explicitly (`--spec-version 1.0.0-draft.2` when the
artifact is draft.2) and resolves the fleet artifact class via `ats policy resolve` before
any extraction.

---

## Contract 2 — `ats-assess-output` and `ats-specify-output`

### Consumes

| Input | Required | Notes |
|---|---|---|
| A schema-valid `ats.text_ir.v1` document | Yes | Validated, not merely well formed. |
| Its resolved policy snapshot | Yes | The trace must bind the same `policy_snapshot_id` and `policy_sha256`. |
| The applicable lexicon and glossary | Yes | Canonical WEP phrases, deontic surfaces, approved abbreviations. |
| Explicit presentation constraints | Optional | Presentation only; never a licence to change meaning. |

### Emits — the four-file output bundle

```text
document.md            readable Markdown with invisible block markers
document.trace.json    ats.output_trace.v1 — the block → IR object map
document.lint.json     ats.output_lint_report.v1 — the deterministic verdict
document.receipt.json  ats.acceptance_receipt.v1 — candidate, adjudicator external
```

They are four files rather than one because they carry four different authorities: the
Markdown is what a reader sees, the trace is what the renderer *declares*, the lint report is
what a deterministic procedure *established*, and the receipt is what an external authority
would be accepting. Collapsing any two of them would let a claim inherit an authority it did
not earn (constitution #2, #6).

**`document.md`.** Each traced block is preceded on its own line by
`<!-- ats:block <block-id> -->`, matching `^<!--\s*ats:block\s+([a-z0-9][a-z0-9-]{0,127})\s*-->$`
in `src/ats/output/parse.py`. An optional closer `<!-- /ats:block <block-id> -->` is
recognised. Markers are metadata, not content: `block_text_sha256` hashes the block body's
exact UTF-8 bytes with the marker line excluded and one trailing newline stripped, so a
block's hash does not change when it becomes the last block in the document. Marker ids must
be unique — `OUT-MARKERS` fails on duplicates, on a marker declared in the trace but absent
from the document, on a marker in the document but absent from the trace, and on any line
containing `ats:block` that does not match the marker grammar.

**`document.trace.json`.** Required top-level fields: `schema_version`, `artifact_id`,
`ir_sha256`, `output_sha256`, `policy_snapshot_id`, `policy_sha256`, `profiles`,
`marker_scheme`, `blocks`. Each block requires `block_id`, `marker`, `ordinal`,
`text_sha256`, `material`, `display_role`, `section_id`, `claim_ids`, `evidence_ids`,
`relation_ids`, `requirement_ids`, `forecast_ids`; and may carry `update_indicator_ids`,
`profile`, `heading_path`, `p0_fields`, `p1_relations`, and `content_class`. Ordinals are
zero-based, dense, and strictly increasing in document order. `unmapped_ir_objects` records
any IR object the renderer deliberately did not realize, with a `reason` from
`not_material | retention_contract_allowed_omission | policy_exception |
profile_not_applicable` and, for anything other than `not_material`, an `authorization_ref`.
The trace is sealed: `trace_sha256` is its own content address with only that field omitted.

**`document.lint.json`.** The sealed `ats.output_lint_report.v1` from the output linter: 27
checks in draft.2 (25 draft.1 checks plus `OUT-COORD-PRESERVED` and
`OUT-BASIS-NOT-STRENGTHENED`, both gated into `mechanical` only when the IR declares the
surfaces they protect), block coverage, per-P0 and per-P1 results, finding dispositions, the
five-dimension conformance vector, and one non-empty rationale string per dimension.

**`document.receipt.json`.** A *candidate* `ats.acceptance_receipt.v1` from
`ats.output.receipt.build_candidate_receipt`, binding source hash, output hash, policy id and
hash, implementation and parser identity, rule-registry and lexicon versions, the
deterministic and semantic summaries, and the conformance vector — plus an externally
supplied `adjudicator`.

### What an output skill may decide

Only P2 (§11.3.3): sentence and paragraph boundaries, heading wording, list versus prose
rendering, approved lexical substitution, deletion of functionless repetition, punctuation,
and local ordering that does not change dependencies — subject to the active surface rules
and to the profile's structural obligations. Draft.2 (D-E) sharpens the repetition clause:
requirements and acceptance criteria MAY intentionally restate overlapping semantics when
the restatement changes the discourse role or improves extraction locality — such
locality-preserving redundancy (adding stable identity, standalone extraction, task or
acceptance-criterion generation, review, receipt linkage, or retrieval locality) is not
functionless repetition and is not a defect (`ATS-DISC-003` amendment).

### What an output skill may NOT decide

- **Anything P0.** Named entities, identifiers, numbers and units, dates and horizons,
  polarity, quantifier kind and value, probability points and bands, confidence level, deontic
  force, authority and source attribution, conditions and exceptions, thresholds, requirement
  identifiers, versions, acceptance criteria — all render exactly (§11.3.1).
- **Anything P1.** Wording may change; type, direction, scope, and force must remain
  recoverable (§11.3.2).
- **What the artifact claims.** It renders only claims, evidence, relations, and force already
  present in the IR. Adding a material claim is a §11.7 violation, and
  `OUT-UNKNOWN-REFS` fails on any block reference to an object absent from the IR.
- **That readable means conformant.** A clean-reading document with a broken trace is a
  failing bundle.
- **That its own semantic output is accepted.** It never declares acceptance.

### Hard refusal conditions

| Condition | Why | Spec |
|---|---|---|
| The IR does not validate | Rendering an invalid ledger produces prose with no ground truth | §19.4 |
| The IR is materially ambiguous and the output would not represent the ambiguity | Silent disambiguation is the failure mode ATS exists to prevent | §13.4, §2.2 |
| A material IR object cannot be mapped to a block and carries no authorized omission | `OUT-MATERIAL-COVERAGE` fails | §11.7, §11.8 |
| An omission claims a reason other than `not_material` with no `authorization_ref` | An intentional P0/P1 change requires an authorization object | §11.4 |
| A P0 value cannot be rendered exactly | `OUT-P0-EXACT` fails | §11.3.1, §11.6 |
| A required surface rule cannot be evaluated because the document did not parse | A parser failure MUST NOT lead to token-only rules plus a full-conformance report | §14.4 |
| The renderer would name itself as adjudicator | `build_candidate_receipt` raises `UsageError` on `SELF_IDENTITIES` | §13.7, §14.11 |
| The profile has no declared structural obligations here | `OUT-PROFILE-SECTIONS` is `UNAVAILABLE`; the skill must not synthesise a structure | §9.5 |

### Draft.2 output obligations (the pivot)

The draft.2 mission (D-A, §2.1) makes **semantic recovery cost** — not word count — the
governing objective of rendered output. Optimize for semantic recovery, local closure,
stable-coordinate retention, human inspectability, and downstream extractability (planning
projection, Arq consumption, task decomposition). A sentence-level readability improvement
MUST NOT justify material semantic loss; brevity is a P2 preference, never a licence to
drop or blur material semantics. Concretely:

- **Stable coordinates render verbatim.** Every `requirement_id`, `decision_id`, and
  `acceptance_criterion_id` declared in the IR's `stable_coordinates` MUST appear exactly in
  the rendered artifact, and the trace MUST reference the coordinate-carrying block.
  `OUT-COORD-PRESERVED` fails on drop or alteration; `ATS-COORD-001/002` guard the ledger
  side.
- **Never render an `INFERRED`/`UNAVAILABLE` value as an explicit fact.** It is rendered as
  unresolved or omitted, never as if the source declared it (§7.19, `ATS-BASIS-002`). For a
  TRANSFORM output, `OUT-BASIS-NOT-STRENGTHENED` mechanically rejects a strengthening marker
  on an inferred/unavailable axis (`SHOULD`→`MUST`, `MAY`→`MUST`, unknown→known, WEP band
  mutation, explicit probability-band change).
- **Produce locally closed blocks.** Each rendered unit's operative meaning is recoverable
  from the unit plus its declared references — where applicable: stable identity, actor,
  modality, action, object, condition/trigger, scope, exception, quantitative boundary,
  dependency, proof obligation, acceptance criterion, and rationale/evidence reference
  (§4.24). An explicit enclosing heading may supply values; the block must not require
  undeclared document-wide inference.
- **The gate and the bundle are unchanged.** The refusal gate — no rendering unless
  `ats ir lint` is mechanically green — and the four-file bundle contract stand as-is; the
  two new checks run inside Step 7's lint.

### Revision discipline

An output skill revises **only** in response to a deterministic finding or an explicitly
accepted finding. It does not preemptively repair proposed findings: §14.9 requires a repair
stage to consume an accepted finding or explicit author instruction, and forbids repairing
every proposed finding preemptively when doing so could alter meaning. This is also
constitution #8 — converge by targeted repair against a mechanical defect signal, not by
re-rolling the prose until it looks better.

### Handoff

```bash
ats output lint document.md \
  --trace document.trace.json \
  --ir source.ir.json \
  --policy policy.json
```

→ `ats.output.lint.lint_output(...)` → sealed `ats.output_lint_report.v1`. With a receipt
supplied, `OUT-RECEIPT` additionally runs `ats.output.receipt.verify_receipt`, and
`ats output verify-receipt RECEIPT` re-checks a receipt against the artifacts it binds.

---

## Shared boundary: what no skill may do

1. **No skill accepts its own output.** §13.7 forbids a component becoming the authoritative
   adjudicator for its own finding; §14.11 assigns final semantic acceptance to an authorized
   human or an explicitly governed external acceptance system. `SELF_IDENTITIES` in
   `src/ats/output/receipt.py` makes the refusal mechanical rather than procedural.
2. **No skill reports a conformance dimension.** The linters compute the vector; a skill
   reports what the linter returned. "Approved output" means an output created through the
   approved ATS workflow and eligible for acceptance — not that the authoring skill holds
   final acceptance authority.
3. **No skill invents a vocabulary.** Force terms come from the lexicon; enumerated term lists
   come verbatim from `ATS-1_SPEC.md`; domain terms come from the artifact's declared glossary
   (ADR-0006).
4. **No skill silently substitutes a weaker component.** §14.12: when a configured detector,
   model, glossary, or evidence provider is unavailable, the unavailable capability is
   reported. `UnsupportedCapabilityError` carries `status: "UNAVAILABLE"` and exits 3.

## Handoff to adjudication

The pipeline terminates at typed findings plus a candidate receipt. Adjudication happens
outside these skills and outside this package.

An `ats.adjudication.v1` record (§13.7) must carry the finding identifier, disposition,
adjudicator identity, rationale, timestamp, the selected interpretation where applicable, the
authorized repair or waiver, evidence references, and the policy snapshot. The dispositions
available are the §13.6 lifecycle states: `proposed`, `accepted`, `rejected`, `waived`,
`deferred`, `resolved`, `unresolved` — with `resolved` requiring a patch or evidence change
*and* successful re-evaluation, so acceptance of a finding is not the same as resolution.

Once an adjudication exists, `OUT-FINDING-DISPOSITIONS` can move off `UNAVAILABLE`: with a
receipt supplied it compares the receipt's `semantic_summary.proposed` against the settled
counts and fails when any surfaced finding remains undispositioned, because §15.3 forbids
semantic-review conformance while one does.

Note the ordering that this makes possible and the one it forbids. A finding may be
*rejected* and semantic review may still pass (§15.3: "A semantic review can pass with
rejected findings"). What it may never do is pass with an undispositioned surfaced finding —
which is the same honesty rule as `decide()`, applied one layer up: silence is not consent.

---

## What changed in the SKILL.md files (draft.2)

The three skill files were updated for the draft.2 pivot. The contracts above are the
interface those changes must satisfy; this is what the files actually say today.

### `skills/ats-ir-author/SKILL.md`

- **Step 2 gained two resolution steps**: (5) determine the task class — transformation vs
  new authoring — where `AUTHOR_JUDGMENT` (§4.25) is the only basis for new-authoring
  content and is never claimed without task-granted authority; and (6) resolve the fleet
  artifact policy for the artifact class via `ats policy resolve` before extracting (D-G).
- **A new "Draft.2 pivot" section** after Step 6 adds the four extraction-time obligations:
  record `semantic_basis` (the five §4.25 values, verbatim table, schema-enforced); preserve
  stable semantic coordinates exactly (the eight protected kinds, `stable_coordinates`
  block, never rename/renumber/re-case an authority-assigned coordinate); produce locally
  closed units (§4.24 recovery fields); and the never-promote rule (`ATS-BASIS-002`), plus
  the D-A/D-E mission note — do not optimize primarily for brevity, locality-preserving
  redundancy is permitted, protected relations (`ATS-PRES-003`) are never compressed away.
- **Step 12 (ambiguity) gained the draft.2 escalation ladder**: prefer typed insufficiency;
  ask the operator only for action-blocking semantics; escalate in ladder order
  (deterministically recover → Tribunal adjudication → record judgment → stay `UNAVAILABLE`
  → continue → human); absence is never silently converted into a value.
- **The lint-reading section** updated the counts: 27 structural `IR-*` checks (26 draft.1 +
  `IR-BASIS-SCHEMA`), 36 rules in draft.2 (§12.7.5) with `REVIEW_REQUIRED` explained as
  honest and expected.
- **A new twelve-item pivot checklist** runs before returning: the twelve binary
  checks listed under Contract 1 above.

### `skills/ats-assess-output/SKILL.md` and `skills/ats-specify-output/SKILL.md`

- **A new "Draft.2 output obligations" section** states the D-A mission (semantic recovery
  cost, not word count, is the governing objective) and four obligations: restatement is
  permitted when it changes role or locality (D-E, `ATS-DISC-003` — locality-preserving
  redundancy is not a defect); stable coordinates render verbatim (`OUT-COORD-PRESERVED`
  fails on drop or alteration); never render an `INFERRED`/`UNAVAILABLE` value as an
  explicit fact (`OUT-BASIS-NOT-STRENGTHENED`); produce locally closed blocks (§4.24). The
  SPECIFY variant adds that for its profile the coordinates are the requirement identifiers,
  their acceptance-criterion identifiers, and `dependency_target` references (§9.3.2).
- **The gate and the four-file bundle contract are unchanged** — the two new checks run
  inside Step 7's lint, gated into `mechanical` only when the IR declares stable coordinates
  or semantic basis.
- **The lint-reading section** updated to 27 `OUT-*` checks (25 draft.1 +
  `OUT-COORD-PRESERVED` + `OUT-BASIS-NOT-STRENGTHENED`).

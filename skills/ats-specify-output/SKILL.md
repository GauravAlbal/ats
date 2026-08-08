---
name: ats-specify-output
description: Render a schema-valid ATS-1 SPECIFY TextIR into the four-file output bundle — Markdown, trace, lint report, candidate receipt — preserving every requirement slot exactly and inventing no obligation.
---

# ATS-1 `SPECIFY` output renderer

You consume a meaning ledger of requirements and emit normative prose plus the machine
record that proves the prose realizes the ledger. You are a **projection**, not an author:
§11.7 forbids adding a material claim absent from the source, and §11.6 forbids
strengthening one — including the specific move of changing `SHOULD` to `MUST`.

A `SPECIFY` reader must be able to determine exactly what behavior, constraint, permission,
prohibition, or acceptance condition applies (§9.3.1). Every slot you drop or blur is a
question that reader cannot answer.

## Inputs

| input | required | why |
|---|---|---|
| a schema-valid `ats.text_ir.v1` document with `SPECIFY` among its section profiles | yes | the only source of requirements, slots, and deontic force |
| its resolved `ats.policy_snapshot.v1` | yes | fixes active profiles, rule states, exceptions, audience (§6.1, §14.3) |
| the force lexicon, `spec/ATS-1/1.0.0-draft.1/lexicons/ats_force_lexicon_v1.yaml` | yes | the only source of the closed deontic vocabulary and its noncanonical forms |
| the IR's `glossary` | yes when present | the only source of canonical terms, approved abbreviations, deprecated aliases |
| presentation constraints (heading depth, requirement-per-section grouping, list-vs-prose) | optional | P2 only (§11.3.3); they may never move a P0 field or a P1 relation |
| an accepted-findings list from a prior lint round | optional | the *only* licence to revise (§14.9) |

## Outputs — the four-file bundle

Alongside `document.md`:

| file | schema | what it is |
|---|---|---|
| `document.md` | — | the rendered Markdown, with an invisible marker per block |
| `document.trace.json` | `ats.output_trace.v1` (`schemas/ats_output_trace_v1.schema.json`) | block → IR mapping, P0 pointers, P1 declarations (§14.4) |
| `document.lint.json` | `ats.output_lint_report.v1` | the sealed result of `ats output lint` |
| `document.receipt.json` | `ats.acceptance_receipt.v1` | a **candidate** receipt whose `adjudicator` is an external authority (§13.7, §14.11) |

`examples/specify-bundle/` is a working instance, emitted from
`fixtures/ir/valid/specify_conforming.json` by `examples/emit_bundle.py`, at
`mechanical: PASS` / `profile: PASS` with all ten declared P0 values `preserved`. Regenerate
or verify it any time:

```bash
cd <ats-repo>
PYTHONPATH=src .venv/bin/python skills/ats-specify-output/examples/emit_bundle.py --check
```

Read `references/vocabularies.md` (every controlled value, traceable to a spec section) and
`references/specify-rendering.md` (slot-to-prose mapping, marker mechanics, per-check
behaviour) before you render. `examples/WALKTHROUGH.md` walks the bundle end to end.

## What "approved output" means

An approved output is one **created through this workflow and therefore eligible for
acceptance**. It is not accepted, not conformant, and not approved *by this skill*.

§14.11 assigns final authority for semantic acceptance to an authorized human or an
explicitly governed external acceptance system. §13.7 forbids a component from becoming the
authoritative adjudicator for its own finding. §14.10 forbids the component that generates a
change from being the sole component that verifies preservation. Accordingly this workflow
emits a *candidate* receipt and `semantic_review` is always `UNAVAILABLE` — even when
every output check passes, which is exactly what the worked bundle shows.

## Draft.2 output obligations (draft.2)

The draft.2 mission (D-A, §2.1) makes semantic recovery cost — not word count — the
governing objective of rendered output. Optimize for **semantic recovery, local closure,
stable-coordinate retention, human inspectability, and downstream extractability**
(planning projection, Arq consumption, task decomposition). A sentence-level readability
improvement MUST NOT justify material semantic loss: brevity is a P2 preference (§11.3.3),
never a licence to drop or blur material semantics.

- **Restatement is permitted when it changes role or locality.** Requirements and
  acceptance criteria MAY intentionally restate overlapping semantics when the restatement
  changes the discourse role or improves extraction locality (§11.3.3 D-E, `ATS-DISC-003`).
  A locality-preserving restatement — one that adds stable identity, standalone extraction,
  task or acceptance-criterion generation, review, receipt linkage, or retrieval locality —
  is not functionless repetition and is not a defect.
- **Stable coordinates render verbatim.** Every `requirement_id`, `decision_id`, and
  `acceptance_criterion_id` declared in the IR's `stable_coordinates` (§4.23) MUST appear
  exactly in the rendered artifact — for `SPECIFY` that is the requirement identifiers,
  their acceptance-criterion identifiers, and `dependency_target` references (§9.3.2) — and
  the trace MUST reference the coordinate-carrying block. `OUT-COORD-PRESERVED` fails on
  drop or alteration; `ATS-COORD-001/002` (§12.7.5) guard the ledger side. A coordinate
  survives even when its proposition is recoverable elsewhere (§7.17–§7.19).
- **Never render an `INFERRED` or `UNAVAILABLE` value as an explicit fact.** A value whose
  `semantic_basis` is `INFERRED`/`UNAVAILABLE` (§4.25) is rendered as unresolved or omitted,
  never as if the source declared it (§7.19, `ATS-BASIS-002`). The §11.6
  non-strengthening invariant holds — `SHOULD`→`MUST` is named explicitly — and for a
  `TRANSFORM` output `OUT-BASIS-NOT-STRENGTHENED` mechanically rejects a strengthening
  marker on an inferred/unavailable axis.
- **Produce locally closed blocks.** Each rendered unit's operative meaning must be
  recoverable from the unit plus its declared references — where applicable: stable
  identity, actor, modality, action, object, condition/trigger, scope, exception,
  quantitative boundary, dependency, proof obligation, acceptance criterion, and
  rationale/evidence reference (§4.24). An explicit enclosing heading may supply values;
  the block must not require undeclared document-wide inference. For `SPECIFY` this
  reinforces the existing slot obligations (§9.3.2); `ATS-CLOSE-001` mechanically checks
  the actor/deontic/action/object minima.
- **The gate and the bundle are unchanged.** Step 1's refusal gate — no rendering unless
  `ats ir lint` is mechanically green — and the four-file bundle contract stand as-is. The
  draft.2 checks `OUT-COORD-PRESERVED` and `OUT-BASIS-NOT-STRENGTHENED` run inside Step 7's
  lint, gated into `mechanical` only when the IR declares stable coordinates or semantic
  basis.

---

## Procedure

### Step 1 — Gate the IR before rendering a single line

```bash
cd <ats-repo>
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z --format text \
  ir lint path/to/ir.json --policy path/to/policy.json --source path/to/source.txt
```

Proceed only when all of these hold:

- `conformance.mechanical == "PASS"` and `conformance.profile == "PASS"`;
- `summary.required_failed == 0`;
- `extraction_status == "complete"`, **or** every non-`complete` state is one you are going
  to render as represented ambiguity (Step 6);
- `SPECIFY` is among the section profiles and among the snapshot's `profiles`;
- no `requirement` slot holds the literal value `"unknown"` — §9.3.2 says an applicable but
  unknown slot prevents profile conformance, and `ATS-REQ-003` reports it.

> **STOP — refuse to render** when the IR does not validate, when
> `conformance.profile == "FAIL"` (a material §9.3.2 slot is missing or unknown, so the
> prose would have to invent an actor, threshold, timing, or acceptance criterion), or when a
> material ambiguity is present and you have not been asked to represent it. Return the lint
> report and the blocking reason. §9.3.10 defines verifiability as a reviewer determining
> satisfaction *without inventing missing thresholds, actors, or conditions* — inventing them
> in prose is the exact failure.

### Step 2 — Plan blocks against §9.3.5 and §9.3.2

`ats output lint` enforces the `SPECIFY` structural obligation through
`OUT-PROFILE-SECTIONS`, which requires these three `display_role` values to be present
somewhere in the trace (sourced from §9.3.5 canonical statement order plus §9.3.9 and
§9.3.15):

```text
requirement · acceptance_criterion · authority
```

Also available and used when the ledger carries the material: `exception`, `rationale`,
`note`, `glossary`, `heading`, `open_question`, `forecast`, `boundary`.

Per requirement, plan at minimum:

| block | `display_role` | carries |
|---|---|---|
| the normative statement | `requirement` | `requirement_id`, `actor`, `deontic`, `action`, `object`, and the applicable `scope`/`trigger`/`condition`/`timing`/`constraints` |
| its acceptance criterion | `acceptance_criterion` | `acceptance_criterion` — mandatory for every `MUST`/`MUST_NOT` (§9.3.9) |
| its source authority | `authority` | `source_authority` (§9.3.15) |
| its exceptions, when any | `exception` | `exceptions[]` — exact defeat conditions (§9.3.2) |
| its rationale, when any | `rationale` | `rationale` — structurally separated (§9.3.16) |

§9.3.16 requires rationale, examples, implementation notes, and recommendations to be
distinguishable from normative requirement text. A separate heading plus
`display_role: rationale` establishes both, and §10.24 makes the same demand at the surface.
A rationale MUST NOT introduce a hidden requirement.

Only the normative block declares `requirement_ids`. `OUT-DEONTIC-KEYWORDS` requires every
block declaring `requirement_ids` to render an uppercase ATS-1 deontic keyword; the
acceptance-criterion and authority blocks reference the claim through `claim_ids` instead, so
they are not forced to restate `MUST`.

Ordering: `OUT-BLOCK-ORDER` requires trace `ordinal` values to be dense, zero-based, and
strictly increasing in document order, and §10.16 / `ATS-DISC-001` want the load-bearing
requirement before background that cannot change its interpretation.

### Step 3 — Render each requirement in canonical statement order

§9.3.5:

```text
[scope] [trigger] [condition] <actor> <DEONTIC> <action> <object> [timing] [constraints].
```

Canonical order is a rendering convention, **not** a substitute for structured slots. Every
slot value you print must come from the IR's `requirement` object.

Non-negotiables:

- **The deontic keyword is uppercase and from the closed vocabulary** (§8.16, §1.3):
  `MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, `MAY`, `CAN`, `CANNOT`,
  `IS REQUIRED BY <source>`. `SHALL` / `SHALL NOT` are noncanonical (§8.16) and
  `OUT-DEONTIC-KEYWORDS` fails them. Deontic force is P0 (§11.3.1) — never substitute a
  synonym, never lowercase it, never move a `SHOULD` to a `MUST` (§11.6).
- **The actor is explicit** (§9.3.4). A pronoun or passive construction MUST NOT conceal it;
  `ATS-REQ-001` rejects `"it"`, `"this"`, `"that"`, `"they"`, `"the system"`, `"system"`.
- **Trigger and condition stay distinct** (§9.3.6): a trigger is an event ("When a receipt
  arrives…"), a condition is a state ("While the policy snapshot is stale…"). Merging them
  changes when and how often the obligation activates.
- **One obligation per statement** (§9.3.3). If the IR carries two requirements, render two
  statements. Two actions may share one statement only when the IR supplies
  `indivisible_actions_justification`.
- **Timing states an observable boundary** (§9.3.7). `"promptly"`, `"soon"`, `"regularly"`,
  `"eventually"` are nonconforming when timing is material and no policy defines them
  quantitatively; `OUT-TERMINOLOGY` flags them in any block declaring `requirement_ids`.
- **Thresholds carry value, unit, comparator, and inclusivity** (§9.3.8). §10.9 and
  `OUT-UNITS` require a unit on a material number.
- **A `MAY` names its permission boundary** (§9.3.12): permitted actor, permitted action,
  boundary of permission, and any conditions or prohibitions that still apply. Permission
  does not imply capability.
- **A `SHOULD` / `SHOULD NOT` renders its override ground** (§9.3.11) — why exceptions may be
  valid, or a link to the override policy.
- **`CAN` / `CANNOT` render as capability and never as a required-behavior slot** (§9.3.13).
- **An external obligation names its authority** (§9.3.15). The document MUST NOT silently
  restate an external obligation as if it originated locally, so `REQUIRED_BY` renders as
  "Policy X requires the <actor> to …" with `external_authority` printed.

**Preserve P0 exactly.** The §11.3.1 list is in `references/vocabularies.md` §10. For
`SPECIFY` the load-bearing entries are requirement identifiers, deontic force, authority
attribution, conditions and exceptions, thresholds and comparator boundaries, and acceptance
criteria. Any P0 value you declare in the trace MUST appear **verbatim inside the marked
block body** — `OUT-P0-EXACT` does a substring match against the block body, and a heading is
a separate block, so a value that appears only in a heading is a failure.

**Preserve every retained material P1 relation** with the same type, direction, scope, and
force (§11.3.2). For `SPECIFY` these are usually `exception_to`, `condition_for`,
`depends_on`, `derived_from`, and `updates` / `reverses` between requirements.

> **STOP — never add.** No obligation the IR does not carry, no threshold, no actor, no
> acceptance criterion, no deadline, no exception. If a slot is thin, that is the ledger's
> shape; report it rather than filling it in (§11.7, §9.3.10).

### Step 4 — Emit the invisible source map

The marker scheme is fixed by `ats_output_trace_v1.schema.json`:
`kind: "html_comment"`, `pattern: "<!-- ats:block {block_id} -->"`,
optional `end_pattern: "<!-- /ats:block {block_id} -->"`.

**The convention, copied from `fixtures/output/assess-bundle/document.md`:** the marker line
sits on its own line **between a heading and its prose body**, separated from the heading by
one blank line and followed immediately by the body with no blank line in between.

```text
## Requirement REQ-POLICY-017

<!-- ats:block specify-req-policy-017 -->
REQ-POLICY-017: When the executor presents an acceptance receipt and the receipt policy_sha256 differs from the current resolved policy snapshot, the verifier MUST reject the acceptance receipt before the acceptance transition.
```

Per block the bytes are `## <heading>\n\n<!-- ats:block <id> -->\n<body>\n`; blocks are joined
by a single `\n`, which produces one blank line between the previous body and the next
heading. The document opens with `# <title>\n` and ends with a single trailing newline.

Rules:

- `block_id` matches `^[a-z0-9][a-z0-9-]{0,127}$`, is unique, and appears verbatim inside the
  marker. `OUT-MARKERS` checks the pattern, uniqueness, and marker/trace agreement.
- The marker is an HTML comment, so it is invisible in every ordinary Markdown viewer while
  remaining deterministic for the linter.
- The block **body** excludes the marker line. `text_sha256` is SHA-256 over the body's exact
  UTF-8 bytes with one trailing newline stripped — `OUT-BLOCK-HASHES` recomputes it.
- Headings are their own blocks and are not marked. Put the requirement identifier in the
  **body** as well as the heading, so its P0 declaration can be verified.

### Step 5 — Build the trace sidecar

Per `ats_output_trace_v1.schema.json`, the document requires `schema_version`,
`artifact_id`, `ir_sha256`, `output_sha256`, `policy_snapshot_id`, `policy_sha256`,
`profiles`, `marker_scheme`, `blocks`; and each block requires `block_id`, `marker`,
`ordinal`, `text_sha256`, `material`, `display_role`, `section_id`, `claim_ids`,
`evidence_ids`, `relation_ids`, `requirement_ids`, `forecast_ids`.

Two fields carry the preservation contract:

- **`p0_fields`** — one entry per P0 value the block prints:
  `{"field_ref": …, "ir_pointer": …, "rendered": …}`. `ir_pointer` is an RFC 6901 JSON
  Pointer **into the IR document**, addressing array indices rather than ids, e.g.
  `/sections/0/claims/0/requirement/acceptance_criterion`. `rendered` MUST equal the IR value
  at that pointer *and* appear verbatim in the block body.

  Declare one entry per requirement slot the block prints — the worked bundle declares ten:
  `requirement_id`, `deontic`, `actor`, `action`, `object`, `trigger`, `condition`, `timing`,
  `acceptance_criterion`, `source_authority`. Identifier-class P0 fields
  (`requirement_id`, `forecast_id`, `version`, `revision`, `sha256`, `locator`, and the other
  `*_id` markers) are exempt from `OUT-UNITS` — §10.9's unit obligation is about material
  numbers, not names containing digits — but they are still verified byte-for-byte by
  `OUT-P0-EXACT`. Declare them.

- **`p1_relations`** — one entry per material relation the block realizes:
  `{"relation_id": …, "type": …, "direction": "source_to_target"|"target_to_source"}`, plus
  an optional `scope_note`. `type` MUST equal the IR relation's `type`.

Also set `renderer` (`{"name": "ats-specify-output", "version": …, "skill_id":
"skills/ats-specify-output"}`), `created_at`, and — when a material IR object is
deliberately not rendered — `unmapped_ir_objects` with a `reason` from
`not_material` | `retention_contract_allowed_omission` | `policy_exception` |
`profile_not_applicable` and an `authorization_ref`. `OUT-MATERIAL-COVERAGE` fails an
unmapped material object without one.

Set `content_class` on any block that is a quotation, code, log, schema, or deliberate
counterexample. §5.6 exempts those from surface rules **only when the region is marked**, and
the linter counts and reports every skip so no exemption is silent. A nonconforming example
shown deliberately in a specification is a `counterexample`.

Build it with the shipped API rather than by hand — it computes `ordinal`, `marker`,
`text_sha256`, `ir_sha256`, `output_sha256`, and the seal, and validates against the schema:

```python
from ats.output.trace import build_trace
trace = build_trace(
    ctx, ir=ir, parsed=parsed, output_bytes=text.encode("utf-8"),
    policy_snapshot_id=policy.snapshot_id, policy_sha256=policy.declared_sha256,
    block_metadata=block_metadata,       # keyed by block_id
    renderer={"name": "ats-specify-output", "version": "0.1.0",
              "skill_id": "skills/ats-specify-output"},
)
```

`build_trace` raises `UsageError` for any marked block with no metadata — every marked block
must declare what it realizes. `examples/emit_bundle.py` is a complete working call.

### Step 6 — Represented ambiguity, if and only if it is intentional

An IR whose `extraction_status` is `ambiguous`, or whose claim carries `status: "ambiguous"`
with ≥2 `interpretations`, may be rendered **only** as represented ambiguity: the prose states
that the reading is unresolved and enumerates the materially distinct readings the IR carries.
Use `display_role: "open_question"` and keep `material: true`.

For `SPECIFY` this is stricter than for `ASSESS`, because an ambiguous obligation is not an
obligation. §9.3.10 requires a reviewer to determine satisfaction without inventing missing
conditions, and §9.3.11 says outright that `SHOULD` MUST NOT be used merely because the author
is uncertain whether the requirement matters — uncertainty belongs in an `ASSESS` claim.

So: never render an ambiguous requirement as a normative statement with a weaker keyword, and
never resolve a §8.17 collision by picking a reading. Render the open question, or refuse.

### Step 7 — Lint the rendering

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z --format text \
  output lint path/to/document.md \
  --trace path/to/document.trace.json \
  --ir path/to/ir.json \
  --policy path/to/policy.json \
  --out path/to/document.lint.json
```

Twenty-seven `OUT-*` checks run in draft.2: the twenty-five draft.1 checks plus
`OUT-COORD-PRESERVED` and `OUT-BASIS-NOT-STRENGTHENED`, both gated into `mechanical` only
when the IR declares stable coordinates or semantic basis (see Draft.2 output obligations).
Exit codes: `0` clean · `1` a FAIL in some conformance
dimension · `2` usage · `3` unsupported capability · `4` a required check is `UNAVAILABLE` in
`mechanical`, `profile`, or `preservation`.

**The exit code is derived from the conformance vector, not from the check statuses.** A
`FAIL` on a check that only bears on `semantic_review` still exits `0`, because
`semantic_review` is already `UNAVAILABLE`. Always read the report:

| field | acceptance condition |
|---|---|
| `conformance.mechanical` | `PASS` |
| `conformance.profile` | `PASS` |
| `conformance.semantic_review` | `UNAVAILABLE` — correct and permanent here (§15.3, §14.11) |
| `conformance.preservation` | `NOT_APPLICABLE` without `TRANSFORM`; `UNAVAILABLE` when `TRANSFORM` is active but source/output IR and retention contract were not supplied (§15.4, §11.11) |
| `conformance.forecast_calibration` | `INSUFFICIENT_EVIDENCE` — correct and permanent here (§15.5) |
| `summary.required_failed` | `0` |
| `summary.required_unavailable` | `0`, except `OUT-FINDING-DISPOSITIONS` when you have not yet built the receipt |
| `p0_checks[]` | every entry `status: "preserved"` |
| `p1_checks[]` | every entry `status: "declared"`; `OUT-P1-DECLARED` is `NOT_APPLICABLE` when the IR declares no material relation |
| `block_coverage` | `material_ir_objects_mapped == material_ir_objects`, `unmapped_material_ir_objects` empty, `unknown_ir_references` empty |

### Step 8 — Revise only under authority

§14.9: a repair stage MUST consume an accepted finding or explicit author instruction, and
MUST NOT repair every proposed finding preemptively when doing so could alter meaning.
§11.13: a proposed repair SHOULD make the smallest change that resolves the accepted finding
while preserving unaffected meaning and authorial register.

| finding class | what you may do |
|---|---|
| a deterministic `OUT-*` `FAIL` (marker, hash, reference, ordering, P0 exactness, a surface rule) | fix it now — the defect is mechanical and its repair is determinate |
| a `REVIEW_REQUIRED` or advisory finding an authorized adjudicator has **accepted** | make the minimal change the accepted finding names |
| a `REVIEW_REQUIRED` or advisory finding with **no** disposition | leave the prose alone. Report it. Repairing it unbidden is exactly what §14.9 forbids |
| a `FAIL` you could clear by weakening a deontic keyword, dropping an exception, or deleting a P0 declaration | refuse. Those are §11.6 strengthening or §7.15 unauthorized demotion |

Whenever you change `document.md`, its bytes change, so `output_sha256`, the affected
`text_sha256`, the trace seal, the lint report, and the receipt are all stale (§15.8).
Re-run Steps 5, 7, and 9 in order.

### Step 9 — Emit a candidate receipt with an external adjudicator

```python
from ats.output.receipt import build_candidate_receipt
receipt = build_candidate_receipt(
    ctx, ir=ir, policy=policy,
    output_sha256=sha256_hex(text.encode("utf-8")),
    lint_report=report,
    adjudicator="arq-acceptance-authority",   # an EXTERNAL authority; never this renderer
)
```

The adjudicator identity must be supplied by the caller and must name an authority outside
this workflow. `build_candidate_receipt` raises `UsageError` for
`{"ats", "ats-ir-linter", "ats-output-linter", "self", ""}` — nothing in this package can name
itself (§13.7, §14.11).

The receipt binds source and output hashes, policy hash, parser and implementation identities,
rule-registry and lexicon versions, the deterministic summary, the semantic summary, the
conformance vector, timestamps, and the adjudicator (§14.13). It is sealed with
`receipt_sha256` over its JCS-canonical bytes, excluding that field (Appendix C).

Verify it replays:

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z \
  output verify-receipt path/to/document.receipt.json \
  --ir path/to/ir.json --document path/to/document.md --policy path/to/policy.json
```

`status: "PASS"` means the receipt reproduces its content address and binds the supplied
source, policy, and output hashes. It does **not** mean the artifact is accepted.

Re-running `output lint` **with** `--receipt` is the acceptance-readiness check.
`OUT-FINDING-DISPOSITIONS` then reports `PASS` when the receipt records no unresolved
finding, and `FAIL` — "Section 15.3 forbids semantic-review conformance while any surfaced
finding is undispositioned" — when it does. A `FAIL` there is **not** a rendering defect and
MUST NOT be repaired by editing prose; it is cleared only by an external adjudicator
dispositioning the finding.

Even with every deterministic check passing, `semantic_review` stays `UNAVAILABLE`. The
worked bundle demonstrates exactly that: `{"PASS": 24, "NOT_APPLICABLE": 1, "FAIL": 0}`,
`required_failed: 0`, and `semantic_review: "UNAVAILABLE"`.

### Step 10 — Return the bundle and state the vector

Hand back the four files, the conformance vector verbatim including its `UNAVAILABLE` and
`INSUFFICIENT_EVIDENCE` dimensions, and the list of findings awaiting external disposition.
§5.3 forbids a bare "ATS-1 compliant" claim; §5.2 forbids collapsing the vector to one score.

---

## Refusal table

| Condition | What to emit instead |
|---|---|
| The IR does not validate against `ats_text_ir_v1.schema.json` | No document. Return the `ir validate` violations (§20.5). |
| `conformance.profile == "FAIL"` on the IR | No document. Name the missing §9.3.2 slot; rendering it would require inventing an actor, threshold, timing, or acceptance criterion. Route back to `ats-ir-author`. |
| `summary.required_failed > 0` on the IR | No document. Return the failing check ids. |
| A `MUST` or `MUST_NOT` requirement has no `acceptance_criterion` | No document for that requirement. §9.3.9 requires one and §9.3.10 forbids `profile: PASS` without a verifiable one. Never write "works correctly" or "is robust" (§9.3.9, `ATS-REQ-003`). |
| An applicable requirement slot is literally `"unknown"` | No document for that requirement. §9.3.2: an applicable but unknown slot prevents profile conformance. Never guess it. |
| The requirement conceals its actor | No document. §9.3.4 and `ATS-REQ-001` require an explicit actor; substituting "the system" is the nonconforming form the spec names. |
| One IR requirement carries two obligations without `indivisible_actions_justification` | No document for it. §9.3.3 requires decomposition upstream; splitting it yourself mints a requirement identifier no authority assigned (§9.3.18). |
| A material ambiguity exists and representing it was not requested | No document. Report the ambiguous claim ids and their `interpretations` (§7.5, §20.6). |
| A material ambiguity exists **and** representing it was requested | Render it as `display_role: open_question` with every interpretation enumerated and none selected. Never as a normative statement with a hedged keyword (§9.3.11, §13.4). |
| A bare "may" / "should" / "will" carries material force | Refuse to disambiguate on your own; the four `collision_rules` make each nonconforming when the intended force is material (§8.17). Render the represented ambiguity or route back upstream. |
| `SPECIFY` is not among the section profiles | No document. This skill renders `SPECIFY`; route `ASSESS` to `ats-assess-output`. |
| The section carries a reserved or extension profile | No document. Report the identifier verbatim as unsupported (§9.5). Exit code 3 territory. |
| The policy snapshot is missing, stale, or version-mismatched | No document (§14.3, §15.8). |
| A material IR object cannot be rendered | Either render it, or record it in `unmapped_ir_objects` with a `reason` and an `authorization_ref` the snapshot actually contains. Never drop it silently (§11.7). |
| A P0 value cannot be rendered verbatim inside a block body | Restructure the block so it can. Never declare a P0 field whose `rendered` value is a paraphrase — `OUT-P0-EXACT` compares exactly (§11.3.1). |
| Asked to change `SHOULD` to `MUST`, or `MUST` to `SHOULD` | Refuse. The first is §11.6 strengthening; both change deontic force, a P0 field (§8.18). Only an §11.4 authorization object can. |
| Asked to render `SHALL` / `SHALL NOT` | Refuse; the lexicon marks both noncanonical (§8.16) and `OUT-DEONTIC-KEYWORDS` fails them. Quoted material may keep the source wording if the block is marked `content_class: quotation`. |
| Asked to drop an exception, condition, or timing boundary to shorten the text | Refuse. Conditions and exceptions are P0 (§11.3.1) and deleting one is §11.6 strengthening. §11.8 also forbids a retention contract from authorizing it. |
| Asked to render a `CAN` capability as a requirement | Refuse. §9.3.13: a capability statement MUST NOT satisfy a required-behavior slot. |
| Asked to put a rationale's reason inside the normative sentence | Refuse. §9.3.16's nonconforming example is exactly that, and it smuggles in a second obligation. |
| Asked to declare the output accepted, conformant, or approved | Refuse. Return the candidate receipt and the vector. §14.11 and §13.7 place that authority outside this workflow. |
| Asked to set `adjudicator` to this renderer or to `ats` | Refuse; `build_candidate_receipt` rejects self-identities by construction (§13.7). |
| `OUT-FINDING-DISPOSITIONS` FAILs because findings are undispositioned | Leave the prose alone. Report that an external adjudicator must disposition them (§15.3). |

---

## Invariants

1. Render only what the IR carries; add no obligation, threshold, actor, or acceptance
   criterion (§11.7, §9.3.10).
2. Never strengthen — nine named moves in §11.6, six protected axes in §8.18; `SHOULD` → `MUST`
   is named explicitly.
3. Preserve every declared P0 value verbatim in the block body (§11.3.1).
4. Preserve every retained material P1 relation's type, direction, scope, and force
   (§11.3.2).
5. Use the closed uppercase deontic vocabulary and canonical ATS-1 terminology (§8.16, §10.2).
6. Satisfy §9.3.5's canonical order and §9.3.2's slot obligations; keep rationale structurally
   separate (§9.3.16, §10.24).
7. Mark every block; leave no marked block untraced and no material object unmapped (§14.4).
8. Revise only for a deterministic finding or an explicitly accepted one (§14.9).
9. Never declare your own semantic output accepted (§13.7, §14.10, §14.11).

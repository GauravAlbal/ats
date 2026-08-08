---
name: ats-assess-output
description: Render a schema-valid ATS-1 ASSESS TextIR into the four-file output bundle — Markdown, trace, lint report, candidate receipt — adding no claim the meaning ledger does not already carry.
---

# ATS-1 `ASSESS` output renderer

You consume a meaning ledger and emit prose plus the machine record that proves the prose
realizes the ledger. You are a **projection**, not an author: §11.7 forbids adding a
material claim absent from the source, and §11.6 forbids strengthening one.

## Inputs

| input | required | why |
|---|---|---|
| a schema-valid `ats.text_ir.v1` document with `ASSESS` among its section profiles | yes | the only source of claims, evidence, relations, and force |
| its resolved `ats.policy_snapshot.v1` | yes | fixes active profiles, rule states, exceptions, audience (§6.1, §14.3) |
| the force lexicon, `spec/ATS-1/1.0.0-draft.1/lexicons/ats_force_lexicon_v1.yaml` | yes | the only source of WEP phrases, display ranges, and force vocabularies |
| the IR's `glossary` | yes when present | the only source of canonical terms, approved abbreviations, deprecated aliases |
| presentation constraints (heading depth, length target, list-vs-prose, audience overrides) | optional | P2 only (§11.3.3); they may never move a P0 field or a P1 relation |
| an accepted-findings list from a prior lint round | optional | the *only* licence to revise (§14.9) |

## Outputs — the four-file bundle

Alongside `document.md`:

| file | schema | what it is |
|---|---|---|
| `document.md` | — | the rendered Markdown, with an invisible marker per block |
| `document.trace.json` | `ats.output_trace.v1` (`schemas/ats_output_trace_v1.schema.json`) | block → IR mapping, P0 pointers, P1 declarations (§14.4) |
| `document.lint.json` | `ats.output_lint_report.v1` | the sealed result of `ats output lint` |
| `document.receipt.json` | `ats.acceptance_receipt.v1` | a **candidate** receipt whose `adjudicator` is an external authority (§13.7, §14.11) |

`fixtures/output/assess-bundle/` is a working instance of exactly this bundle. Copy its
shape. `fixtures/output/assess-broken/` is the same bundle with two deliberate defects and
is the fastest way to see what the linter catches.

Read `references/vocabularies.md` (every controlled value, traceable to a spec section) and
`references/assess-rendering.md` (block roles, marker mechanics, per-check behaviour) before
you render. `examples/WALKTHROUGH.md` walks the fixture bundle end to end.

## What "approved output" means

An approved output is one **created through this workflow and therefore eligible for
acceptance**. It is not accepted, not conformant, and not approved *by this skill*.

§14.11 assigns final authority for semantic acceptance to an authorized human or an
explicitly governed external acceptance system. §13.7 forbids a component from becoming the
authoritative adjudicator for its own finding. §14.10 forbids the component that generates a
change from being the sole component that verifies preservation. Accordingly this workflow
emits a *candidate* receipt, `semantic_review` is always `UNAVAILABLE`, and every P1
declaration returns `REVIEW_REQUIRED` — because declaring that a block realizes a relation
is not the same as establishing that the prose realizes it with the same force and
direction.

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
  exactly in the rendered artifact, and the trace MUST reference the coordinate-carrying
  block. `OUT-COORD-PRESERVED` fails on drop or alteration; `ATS-COORD-001/002` (§12.7.5)
  guard the ledger side. A coordinate survives even when its proposition is recoverable
  elsewhere (§7.17–§7.19).
- **Never render an `INFERRED` or `UNAVAILABLE` value as an explicit fact.** A value whose
  `semantic_basis` is `INFERRED`/`UNAVAILABLE` (§4.25) is rendered as unresolved or omitted,
  never as if the source declared it (§7.19, `ATS-BASIS-002`). The §11.6
  non-strengthening invariant holds — including `SHOULD`→`MUST` — and for a `TRANSFORM`
  output `OUT-BASIS-NOT-STRENGTHENED` mechanically rejects a strengthening marker on an
  inferred/unavailable axis.
- **Produce locally closed blocks.** Each rendered unit's operative meaning must be
  recoverable from the unit plus its declared references — where applicable: stable
  identity, actor, modality, action, object, condition/trigger, scope, exception,
  quantitative boundary, dependency, proof obligation, acceptance criterion, and
  rationale/evidence reference (§4.24). An explicit enclosing heading may supply values;
  the block must not require undeclared document-wide inference.
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
- `ASSESS` is among the section profiles and among the snapshot's `profiles`.

> **STOP — refuse to render** when the IR does not validate, when
> `conformance.profile == "FAIL"` (a material §9.2.4 slot is missing, so the prose would
> have to invent it), or when a material ambiguity is present and you have not been asked
> to represent it in the output. Return the lint report and the blocking reason. §20.5
> requires failing closed when required schemas cannot be validated or material deltas are
> unresolved.

### Step 2 — Plan blocks against the §9.2.12 structure

§9.2.12 gives the canonical `ASSESS` structure, and the renderer "SHOULD support this
structure without requiring every heading when the artifact remains clear":

```text
Question · Key judgment · Likelihood · Confidence and basis · Supporting evidence
· Contrary evidence and alternatives · Assumptions · Boundary · Update indicators
· Recommendation or next discriminating test
```

`ats output lint` enforces the structural obligation through `OUT-PROFILE-SECTIONS`, which
requires these nine `display_role` values to be present somewhere in the trace:

```text
question · key_judgment · confidence · supporting_evidence · contrary_evidence
· assumption · boundary · update_indicator · recommendation
```

`likelihood`, `confidence_basis`, `alternatives`, `forecast`, `rationale`, `note`,
`glossary`, `open_question`, `heading`, `exception` are available in the enum and used when
the ledger carries the material. The fixture bundle folds `likelihood` into the
`key_judgment` block (the WEP renders inline) and `confidence_basis` into the `confidence`
block — permitted, because §9.2.12 does not require every heading.

Order: §9.2.3 and `ATS-DISC-001` want the first material key judgment before extended
background. `OUT-BLOCK-ORDER` requires trace `ordinal` values to be dense, zero-based, and
strictly increasing in document order.

Assign one block per material object or coherent group, and decide up front:
`block_id`, `display_role`, `section_id`, `material`, which IR ids it realizes, which P0
values it prints, which P1 relations it declares.

### Step 3 — Render prose from the ledger and nothing else

Every sentence must be recoverable from a claim's `proposition`, an evidence object's
`proposition`, a relation, an update indicator's `text`, or a glossary definition.

**Canonical force vocabulary is mandatory on output.**

- WEP: §8.3 requires the canonical phrase and forbids emitting `input_aliases` such as
  "probable", "remote", "highly probable", "nearly certain" — `OUT-WEP-CANONICAL` fails on
  any of them. The exceptions §8.3 names are a quote, an explicit domain policy, or a
  recorded input-normalization report.
- First material WEP use in a section renders its display range inline (§8.4):
  `likely (55–80%)`. `OUT-WEP-INLINE-RANGE` fails without it. Take the range from the
  lexicon `display_range`, not from `lower`/`upper` arithmetic.
- Evidential and causal wording uses the lexicon `phrase` values (§8.12, §8.14). Never
  upgrade `suggests` to `supports`, or `associated with` to `causes` — §11.6 names both as
  strengthening.
- Assessment confidence renders as its own labelled statement, separate from likelihood
  (§8.11). Never write "we are highly confident that X is very likely" — that is §8.11's
  nonconforming example verbatim.
- Deontic keywords, if any appear, are the uppercase closed vocabulary; `SHALL` /
  `SHALL NOT` are noncanonical (§8.16) and `OUT-DEONTIC-KEYWORDS` fails them.

**Preserve P0 exactly.** The §11.3.1 list is in `references/vocabularies.md` §10. Any P0
value you declare in the trace MUST appear **verbatim inside the marked block body** —
`OUT-P0-EXACT` does a substring match against the block body, and a heading is a separate
block, so a value that appears only in a heading is a failure.

**Preserve every retained material P1 relation** with the same type, direction, scope, and
force (§11.3.2). Wording may change; the relation may not. `OUT-P1-DECLARED` fails a
material IR relation that no rendered block declares, and fails a block that declares a
type differing from the IR's.

**Surface rules that will be checked** (all deterministic, all sourced from the lexicon or a
list enumerated verbatim in the spec): acronym expansion on first material use (§10.5),
units on material numbers (§10.9), anchored relative time (§10.11), no deprecated glossary
aliases (§10.2), no empty intensifiers (§10.20), no vague evaluative terms without a
comparison or threshold (§10.21), heading nesting and list mechanics (§10.17, §10.18).

> **STOP — never add.** No new claim, no new evidence line, no inferred probability, no
> manufactured confidence, no causal upgrade, no dropped condition or exception, no dropped
> source attribution. If the prose reads thin, that is the ledger's shape; report it rather
> than filling it in (§11.7, §11.6, §20.1).

### Step 4 — Emit the invisible source map

The marker scheme is fixed by `ats_output_trace_v1.schema.json`:
`kind: "html_comment"`, `pattern: "<!-- ats:block {block_id} -->"`,
optional `end_pattern: "<!-- /ats:block {block_id} -->"`.

**The convention, copied from `fixtures/output/assess-bundle/document.md`:** the marker line
sits on its own line **between a heading and its prose body**, separated from the heading by
one blank line and followed immediately by the body with no blank line in between.

```text
## Key judgment

<!-- ats:block assess-key-judgment -->
A Rust migration is likely (55–80%) to reduce invalid-state defects in the acceptance kernel after the transition model is stable.
```

The exact bytes of that region in the fixture are:

```text
## Key judgment\n\n<!-- ats:block assess-key-judgment -->\nA Rust migration is likely (55–80%) …\n
```

so the shape per block is `## <heading>\n\n<!-- ats:block <id> -->\n<body>\n`, and blocks
are joined by a single `\n`, which produces one blank line between the previous body and the
next heading. The document opens with `# <title>\n` and ends with a single trailing newline.

Rules:

- `block_id` matches `^[a-z0-9][a-z0-9-]{0,127}$`, is unique, and appears verbatim inside
  the marker. `OUT-MARKERS` checks the pattern, uniqueness, and marker/trace agreement.
- The marker is an HTML comment, so it is invisible in every ordinary Markdown viewer while
  remaining deterministic for the linter.
- The block **body** excludes the marker line. `text_sha256` is SHA-256 over the body's
  exact UTF-8 bytes with one trailing newline stripped — `OUT-BLOCK-HASHES` recomputes it.
- Headings are their own blocks and are not marked in the fixture. A P0 value must therefore
  live in the body.

### Step 5 — Build the trace sidecar

Per `ats_output_trace_v1.schema.json`, the document requires `schema_version`,
`artifact_id`, `ir_sha256`, `output_sha256`, `policy_snapshot_id`, `policy_sha256`,
`profiles`, `marker_scheme`, `blocks`; and each block requires `block_id`, `marker`,
`ordinal`, `text_sha256`, `material`, `display_role`, `section_id`, `claim_ids`,
`evidence_ids`, `relation_ids`, `requirement_ids`, `forecast_ids`.

Two fields carry the preservation contract:

- **`p0_fields`** — one entry per P0 value the block prints:
  `{"field_ref": …, "ir_pointer": …, "rendered": …}`. `ir_pointer` is an RFC 6901 JSON
  Pointer **into the IR document**, e.g.
  `/sections/0/claims/0/force/likelihood/term`. `rendered` MUST equal the IR value at that
  pointer *and* appear verbatim in the block body.
- **`p1_relations`** — one entry per material relation the block realizes:
  `{"relation_id": …, "type": …, "direction": "source_to_target"|"target_to_source"}`,
  plus an optional `scope_note`. `type` MUST equal the IR relation's `type`.

Also set `renderer` (`{"name": "ats-assess-output", "version": …, "skill_id":
"skills/ats-assess-output"}`), `created_at`, and — when a material IR object is
deliberately not rendered — `unmapped_ir_objects` with a `reason` from
`not_material` | `retention_contract_allowed_omission` | `policy_exception` |
`profile_not_applicable` and an `authorization_ref`. `OUT-MATERIAL-COVERAGE` fails an
unmapped material object without one; `OUT-POLICY-EXCEPTIONS` fails a cited exception the
snapshot does not contain.

Set `content_class` on any block that is a quotation, code, log, schema, or deliberate
counterexample. §5.6 exempts those from surface rules **only when the region is marked**,
and the linter counts and reports every skip so no exemption is silent.

Build it with the shipped API rather than by hand — it computes `ordinal`, `marker`,
`text_sha256`, `ir_sha256`, `output_sha256`, and the seal, and validates against the schema:

```python
from ats.output.trace import build_trace
trace = build_trace(
    ctx, ir=ir, parsed=parsed, output_bytes=text.encode("utf-8"),
    policy_snapshot_id=policy.snapshot_id, policy_sha256=policy.declared_sha256,
    block_metadata=block_metadata,       # keyed by block_id
    renderer={"name": "ats-assess-output", "version": "0.1.0",
              "skill_id": "skills/ats-assess-output"},
)
```

`build_trace` raises `UsageError` for any marked block with no metadata — every marked block
must declare what it realizes.

### Step 6 — Represented ambiguity, if and only if it is intentional

An IR whose `extraction_status` is `ambiguous`, or whose claim carries
`status: "ambiguous"` with ≥2 `interpretations`, may be rendered **only** as represented
ambiguity: the prose states that the reading is unresolved and enumerates the materially
distinct readings the IR carries. Use `display_role: "open_question"` or
`"alternatives"`, and keep `material: true`.

Never collapse the interpretations to one reading, and never smooth the ambiguity into a
hedge. §7.5 and §13.4 require the distinct readings to remain distinguishable; §20.1 names
"binary framing of unresolved tradeoffs" and "clean headings that imply resolution where
evidence is insufficient" as hazards to test for specifically.

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
dimension · `2` usage · `3` unsupported capability · `4` a required check is `UNAVAILABLE`
in `mechanical`, `profile`, or `preservation`.

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
| `p1_checks[]` | every entry `status: "declared"` |
| `block_coverage` | `material_ir_objects_mapped == material_ir_objects`, `unmapped_material_ir_objects` empty, `unknown_ir_references` empty |

`OUT-P1-DECLARED` returning `REVIEW_REQUIRED` is the expected clean result, not a defect:
declaration is not realization, and that judgment is semantic.

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
| a `FAIL` you could clear by deleting a material claim, weakening the policy, or dropping a P0 declaration | refuse. §7.15 forbids demoting an explicitly material item without adjudication |

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
`{"ats", "ats-ir-linter", "ats-output-linter", "self", ""}` — nothing in this package can
name itself (§13.7, §14.11).

The receipt binds source and output hashes, policy hash, parser and implementation
identities, rule-registry and lexicon versions, the deterministic summary, the semantic
summary, the conformance vector, timestamps, and the adjudicator (§14.13). It is sealed with
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

Re-running `output lint` **with** `--receipt` is the acceptance-readiness check, and while
any surfaced finding is undispositioned `OUT-FINDING-DISPOSITIONS` will report `FAIL` with
"Section 15.3 forbids semantic-review conformance while any surfaced finding is
undispositioned". That `FAIL` is **not** a rendering defect and MUST NOT be repaired by
editing prose. It is cleared only by an external adjudicator dispositioning the finding.

### Step 10 — Return the bundle and state the vector

Hand back the four files, the conformance vector verbatim including its `UNAVAILABLE` and
`INSUFFICIENT_EVIDENCE` dimensions, and the list of findings awaiting external disposition.
§5.3 forbids a bare "ATS-1 compliant" claim; §5.2 forbids collapsing the vector to one
score.

---

## Refusal table

| Condition | What to emit instead |
|---|---|
| The IR does not validate against `ats_text_ir_v1.schema.json` | No document. Return the `ir validate` violations (§20.5). |
| `conformance.profile == "FAIL"` on the IR | No document. Name the missing §9.2.4 slot; rendering it would require inventing the slot. Route back to `ats-ir-author`. |
| `summary.required_failed > 0` on the IR | No document. Return the failing check ids. |
| A material ambiguity exists and representing it was not requested | No document. Report the ambiguous claim ids and their `interpretations`; ask whether to represent the ambiguity or resolve it upstream (§7.5, §20.6). |
| A material ambiguity exists **and** representing it was requested | Render it as represented ambiguity: `display_role: open_question` / `alternatives`, every interpretation enumerated, none selected (§13.4). |
| `ASSESS` is not among the section profiles | No document. This skill renders `ASSESS`; route `SPECIFY` to `ats-specify-output`. |
| The section carries a reserved or extension profile | No document. Report the identifier verbatim as unsupported (§9.5). Exit code 3 territory. |
| The policy snapshot is missing, stale, or version-mismatched | No document (§14.3, §15.8). |
| A material IR object cannot be rendered | Either render it, or record it in `unmapped_ir_objects` with a `reason` and an `authorization_ref` the snapshot actually contains. Never drop it silently (§11.7, `OUT-MATERIAL-COVERAGE`). |
| A P0 value cannot be rendered verbatim inside a block body | Restructure the block so it can. Never declare a P0 field whose `rendered` value is a paraphrase — `OUT-P0-EXACT` compares exactly (§11.3.1). |
| A material P1 relation has no natural home in the prose | Give it a block. Never omit the declaration to make `OUT-P1-DECLARED` quiet (§11.3.2). |
| Asked to shorten by dropping a condition, exception, boundary, or contrary-evidence line | Refuse. That is §11.6 strengthening and §11.8's forbidden loss. A deliberately lossy summary needs a `RetentionContractV1` and `TRANSFORM`, which is a different job. |
| Asked to raise a likelihood band, a confidence level, or an evidential/causal term | Refuse, citing §8.18 and §11.6. Only an authorization object under §11.4 can change a P0 field. |
| Asked to use a friendlier synonym for a WEP phrase | Refuse; §8.3 requires the canonical phrase and `OUT-WEP-CANONICAL` fails aliases. Quoted material may keep the source wording if the block is marked `content_class: quotation`. |
| Asked to declare the output accepted, conformant, or approved | Refuse. Return the candidate receipt and the vector. §14.11 and §13.7 place that authority outside this workflow. |
| Asked to set `adjudicator` to this renderer or to `ats` | Refuse; `build_candidate_receipt` rejects self-identities by construction (§13.7). |
| `OUT-FINDING-DISPOSITIONS` FAILs because findings are undispositioned | Leave the prose alone. Report that an external adjudicator must disposition them (§15.3). |

---

## Invariants

1. Render only what the IR carries; add no material claim (§11.7).
2. Never strengthen — nine named moves in §11.6, six protected axes in §8.18.
3. Preserve every declared P0 value verbatim in the block body (§11.3.1).
4. Preserve every retained material P1 relation's type, direction, scope, and force
   (§11.3.2).
5. Use canonical ATS-1 terminology and force vocabulary (§8.3, §8.12, §8.14, §8.16).
6. Satisfy §9.2.12's structural obligations; a heading alone never satisfies an evidence or
   basis obligation (§9.2.2).
7. Mark every block; leave no marked block untraced and no material object unmapped
   (§14.4).
8. Revise only for a deterministic finding or an explicitly accepted one (§14.9).
9. Never declare your own semantic output accepted (§13.7, §14.10, §14.11).

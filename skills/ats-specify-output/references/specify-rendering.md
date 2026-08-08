# `SPECIFY` rendering: slot-to-prose mapping, marker mechanics, and the 25 output checks

Companion to `vocabularies.md` (all controlled values and profile slots). This file covers
the rendering surface: the marker byte convention, the trace's block contract, how §9.3.2
slots become prose, and exactly what each `OUT-*` check does.

Sources: `schemas/ats_output_trace_v1.schema.json`,
`src/ats/output/{parse,trace,render_checks,lint,receipt}.py`,
`fixtures/output/assess-bundle/` (the canonical marker convention),
`../examples/specify-bundle/` (the worked `SPECIFY` instance), and `ATS-1_SPEC.md`.

---

## 1. The marker convention, byte-exact

Taken from `fixtures/output/assess-bundle/document.md`, whose first 260 bytes are, verbatim:

```text
# Acceptance-kernel language assessment\n\n## Question\n\n<!-- ats:block assess-question -->\nShould Arq move the acceptance kernel from Python to Rust after the state model stabilizes?\n\n## Key judgment\n\n<!-- ats:block assess-key-judgment -->\nA Rust migration is li…
```

The shape:

```text
# <document title>
<blank>
## <heading>
<blank>
<!-- ats:block <block-id> -->
<body line(s)>
<blank>
## <next heading>
…
```

Equivalently, each block contributes `## {heading}\n\n<!-- ats:block {id} -->\n{body}\n`, the
title contributes `# {title}\n`, and the parts are joined with a single `\n`. The file ends
with exactly one trailing newline. `../examples/emit_bundle.py` implements exactly this in its
`block()` helper, and `--check` proves the committed bundle reproduces byte-for-byte.

Hard rules:

| rule | source |
|---|---|
| marker sits on its own line, **between the heading and the body**, with a blank line above and none below | `fixtures/output/assess-bundle/document.md` |
| `pattern` is exactly `<!-- ats:block {block_id} -->` | `ats_output_trace_v1.schema.json` `marker_scheme.pattern` (a `const`) |
| optional closer is `<!-- /ats:block {block_id} -->` | `marker_scheme.end_pattern` (a `const`) |
| the parser accepts flexible internal whitespace: `^<!--\s*ats:block\s+([a-z0-9][a-z0-9-]{0,127})\s*-->$` | `src/ats/output/parse.py` `MARKER_OPEN` |
| `block_id` matches `^[a-z0-9][a-z0-9-]{0,127}$` | trace schema `block.block_id.pattern` |
| markers are unique per document | `OUT-MARKERS` |
| the block **body excludes** the marker line; headings are separate, unmarked blocks | `src/ats/output/trace.py` `block_text_sha256` |
| `text_sha256` = SHA-256 over the body's exact UTF-8 bytes with one trailing newline stripped | same |

Because a marker is an HTML comment, it is invisible in every ordinary Markdown viewer while
remaining a deterministic anchor for the linter — which is what §14.4 requires of a source
map.

Because the heading is a separate block, **a P0 value that appears only in a heading is not in
any block body**, and `OUT-P0-EXACT` will fail it. This bites hardest on requirement
identifiers: the worked bundle heads its block `## Requirement REQ-POLICY-017` *and* opens the
body with `REQ-POLICY-017: When the executor …`, so the identifier's P0 declaration verifies.

---

## 2. §9.3.2 slots → prose, block by block

The worked bundle (`../examples/specify-bundle/`) renders one requirement as four blocks:

| ordinal | heading | `block_id` | `display_role` | `material` | declares |
|---|---|---|---|---|---|
| 0 | `Requirement REQ-POLICY-017` | `specify-req-policy-017` | `requirement` | `true` | `claim_ids`, `requirement_ids`, 8 `p0_fields` |
| 1 | `Acceptance criterion` | `specify-acceptance-criterion` | `acceptance_criterion` | `true` | `claim_ids`, 1 `p0_field` |
| 2 | `Source authority` | `specify-authority` | `authority` | `true` | `claim_ids`, 1 `p0_field` |
| 3 | `Rationale (non-normative)` | `specify-rationale` | `rationale` | `false` | nothing |

The normative body, in §9.3.5 canonical order
`[scope] [trigger] [condition] <actor> <DEONTIC> <action> <object> [timing] [constraints]`:

```text
REQ-POLICY-017: When the executor presents an acceptance receipt and the receipt
policy_sha256 differs from the current resolved policy snapshot, the verifier MUST reject
the acceptance receipt before the acceptance transition.
```

Slot by slot:

| slot | IR value | where it lands in the prose |
|---|---|---|
| `requirement_id` | `REQ-POLICY-017` | the body's leading label (and the heading) |
| `trigger` | `executor presents an acceptance receipt` | `When the executor presents an acceptance receipt` |
| `condition` | `receipt policy_sha256 differs from the current resolved policy snapshot` | `and the receipt policy_sha256 differs from the current resolved policy snapshot` |
| `actor` | `verifier` | `the verifier` |
| `deontic` | `MUST` | `MUST`, uppercase, unaltered |
| `action` | `reject` | `reject` |
| `object` | `acceptance receipt` | `the acceptance receipt` |
| `timing` | `before the acceptance transition` | `before the acceptance transition` |
| `acceptance_criterion` | full sentence | its own block, `display_role: acceptance_criterion` |
| `source_authority` | `Arq acceptance-policy kernel` | its own block, `display_role: authority` |
| `rationale` | full sentence | its own block, `display_role: rationale`, `material: false` |
| `exceptions` | `[]` | nothing rendered — the array is empty, and inventing "no exceptions apply" would be adding a claim |

Every one of those ten printed slot values is declared in `p0_fields`, and every one comes
back `status: "preserved"`.

Notice the trigger and condition remain lexically distinct ("When … *and* …") because §9.3.6
forbids treating an event and a state as interchangeable. Notice too that only the normative
block declares `requirement_ids`: `OUT-DEONTIC-KEYWORDS` requires any block declaring them to
render an uppercase deontic keyword, so the acceptance-criterion and authority blocks
reference the claim through `claim_ids` alone.

---

## 3. `display_role` — the full enum

`question` · `key_judgment` · `likelihood` · `confidence` · `confidence_basis` ·
`supporting_evidence` · `contrary_evidence` · `alternatives` · `assumption` · `boundary` ·
`update_indicator` · `recommendation` · `forecast` · `requirement` · `acceptance_criterion` ·
`authority` · `exception` · `rationale` · `note` · `heading` · `glossary` · `open_question`

`OUT-PROFILE-SECTIONS` requires these three for `SPECIFY` (`PROFILE_REQUIRED_ROLES` in
`src/ats/output/lint.py`, sourced from §9.3.5 canonical statement order plus §9.3.9 and
§9.3.15):

```text
requirement · acceptance_criterion · authority
```

Missing any one → `OUT-PROFILE-SECTIONS` `FAIL` → `conformance.profile: FAIL`.

`exception`, `rationale`, `note`, `boundary`, `glossary`, `open_question` are used when the
ledger carries the material. §9.3.16 and §10.24 both require rationale, examples,
implementation notes, and commentary to be structurally distinguishable from normative
requirement text — a separate heading plus `display_role: rationale` and `material: false`
establishes that at both the surface and the trace level.

When an artifact composes profiles (§9.4), `OUT-PROFILE-SECTIONS` evaluates every profile in
the trace's `profiles` array that has declared obligations, so a composed `ASSESS` + `SPECIFY`
document must satisfy the nine `ASSESS` roles *and* these three.

---

## 4. Trace block contract

Required on every block: `block_id`, `marker`, `ordinal`, `text_sha256`, `material`,
`display_role`, `section_id`, `claim_ids`, `evidence_ids`, `relation_ids`, `requirement_ids`,
`forecast_ids`.

Optional: `profile`, `heading_path`, `update_indicator_ids`, `p0_fields`, `p1_relations`,
`content_class`.

`ordinal` is zero-based, dense, and strictly increasing in document order.

### `p0_fields`

```json
{
  "field_ref": "REQ-POLICY-017.requirement.acceptance_criterion",
  "ir_pointer": "/sections/0/claims/0/requirement/acceptance_criterion",
  "rendered": "A stale-policy fixture returns refused_stale_policy, emits no accepted transition, and records both policy hashes."
}
```

All three keys are required, and `additionalProperties: false`. `ir_pointer` is an RFC 6901
JSON Pointer into the **IR document**, addressing array indices rather than ids —
`/sections/0/claims/0/requirement/...` is the first claim of the first section.
`OUT-P0-EXACT` performs two comparisons:

1. `rendered` equals the IR value at `ir_pointer` (numbers stringified, booleans as
   `true`/`false`) — otherwise `status: "changed_unauthorized"`;
2. `rendered` appears as a substring of the declaring block's body — otherwise
   `status: "changed_unauthorized"`.

An unresolvable pointer, or a declaring block absent from the document, gives
`status: "unavailable"`. Declaring no P0 field anywhere gives `REVIEW_REQUIRED`: exact
rendering of protected values is then *undeclared* rather than verified.

Consequence for prose: a P0 slot value must be rendered **verbatim**, not smoothed. The
worked bundle writes `and the receipt policy_sha256 differs from …` rather than
`whose policy_sha256 differs from …`, because the IR's `condition` is
`receipt policy_sha256 differs from the current resolved policy snapshot` and the paraphrase
would not contain it as a substring.

Identifier-class P0 fields — `field_ref` or `ir_pointer` containing `requirement_id`,
`forecast_id`, `claim_id`, `evidence_id`, `relation_id`, `indicator_id`, `artifact_id`,
`section_id`, `concept_id`, `source_id`, `exception_id`, `snapshot_id`, `version`, `revision`,
`sha256`, or `locator` — are exempt from the `OUT-UNITS` check. §11.3.1 still protects them
exactly and `OUT-P0-EXACT` still verifies them byte-for-byte; §10.9's unit obligation applies
to material numbers, not to names containing digits. So `REQ-POLICY-017` is a correct,
encouraged P0 declaration.

### `p1_relations`

```json
{ "relation_id": "rel1", "type": "exception_to", "direction": "source_to_target" }
```

`relation_id`, `type`, `direction` required; `scope_note` optional. `direction` is
`source_to_target` | `target_to_source`. `OUT-P1-DECLARED` fails a material IR relation no
block declares (`status: "missing"`) and fails a declared `type` differing from the IR's
(`status: "direction_changed"`). When every material relation is declared it returns
`REVIEW_REQUIRED`, because declaration is not realization. When the IR declares no material
relation it returns `NOT_APPLICABLE` — which is what the worked bundle shows, since
`specify_conforming.json` has an empty `relations` array.

Typical `SPECIFY` P1 relations: `exception_to` (an exception defeating a requirement),
`condition_for`, `depends_on`, `derived_from` (a requirement adopted from an `ASSESS`
recommendation, §9.4), and `updates` / `reverses` between requirement versions (§9.3.18).

### `unmapped_ir_objects`

```json
{ "object_id": "REQ-POLICY-018", "reason": "profile_not_applicable", "authorization_ref": "…" }
```

`reason` ∈ `not_material` | `retention_contract_allowed_omission` | `policy_exception` |
`profile_not_applicable`. A `policy_exception` reason whose `authorization_ref` is not an
exception in the snapshot fails `OUT-POLICY-EXCEPTIONS`.

### `content_class`

`prose` | `quotation` | `code` | `log` | `schema` | `counterexample` | `table`.

§5.6 exempts `quotation`, `code`, `log`, `schema`, `counterexample` from the surface checks —
**only when marked**. Fenced code and blockquotes are exempt by construction. Every skip is
counted and reported in the check `detail`, so no exemption is silent. `prose` and `table` are
not exempt.

This matters for specifications specifically: §9.3.3, §9.3.4, §9.3.9, and §9.3.16 all show
nonconforming examples. A block that deliberately renders such an example must be
`content_class: "counterexample"`, otherwise its `SHALL`, its "the system", or its "works
correctly" is a real finding.

---

## 5. The 25 output checks

All are `required`.

| check | title | spec ref | what fails it |
|---|---|---|---|
| `OUT-BYTES` | Output and IR hashes match the trace | 14.2, 14.13, App. C | `output_sha256` or `ir_sha256` in the trace disagrees with the real bytes |
| `OUT-MARKDOWN-PARSE` | The document parses with a real Markdown parser | 14.4, 16.3 | commonmark parse failure; §14.4 forbids falling back to token-only rules |
| `OUT-CONSTRUCTS` | Unsupported Markdown constructs are identified | 16.3 | a construct outside the supported set is present and unreported |
| `OUT-MARKERS` | Source-map markers are intact and unique | 14.4 | malformed marker, duplicate `block_id`, or marker/trace disagreement |
| `OUT-TRACE-SCHEMA` | The trace validates and binds the same policy and IR | 6.6, 14.13 | trace schema violation, or `policy_sha256` ≠ the snapshot's `snapshot_sha256` |
| `OUT-BLOCK-HASHES` | Each block's declared hash matches its rendered bytes | 14.2, 16.2 | `text_sha256` ≠ SHA-256 of the body |
| `OUT-IR-REFS` | Every block reference resolves to an IR object of the right kind | 14.4 | `requirement_ids` naming a non-requirement claim, etc. |
| `OUT-MATERIAL-COVERAGE` | Every material IR object is mapped or authorized as omitted | 11.7, 11.8 | a material claim/evidence/relation/indicator neither mapped nor in `unmapped_ir_objects` |
| `OUT-UNKNOWN-REFS` | No block references an object absent from the IR | 11.7 | an id in the trace that the IR does not contain |
| `OUT-BLOCK-ORDER` | Block ordering is dense, ascending, and matches the document | 14.4, 16.2 | non-dense, non-increasing, or document-order mismatch |
| `OUT-PROFILE-SECTIONS` | Profile-required sections are rendered | 9.2.12, 9.3.5 | `requirement`, `acceptance_criterion`, or `authority` absent from the trace |
| `OUT-WEP-CANONICAL` | Canonical WEP phrases only | 8.3 | a lexicon `input_aliases` phrase in unexempt prose |
| `OUT-WEP-INLINE-RANGE` | First material WEP use shows its range | 8.4 | first material WEP use in a section without its `display_range` inline |
| `OUT-DEONTIC-KEYWORDS` | Deontic keywords are canonical and uppercase | 8.16, 1.3 | `SHALL`/`SHALL NOT` rendered; or a block declaring `requirement_ids` renders no uppercase deontic keyword |
| `OUT-ACRONYMS` | Acronyms are expanded or permitted | 10.5 | first rendered use of an acronym neither expanded in place as `Expansion (ACR)` nor in `approved_abbreviations`. Uppercase deontic surfaces and `P0`/`P1`/`P2` are always permitted, and a hyphen-joined token such as `REQ-POLICY-017` is not treated as an acronym |
| `OUT-UNITS` | Rendered P0 numbers carry units | 10.9, 9.3.8 | a declared non-identifier P0 field whose rendered value is a standalone number with no unit, dimension, or `%` |
| `OUT-RELATIVE-TIME` | Relative time is anchored | 10.11 | a §10.11 relative-time term in a block whose claims declare no anchoring scope field |
| `OUT-TERMINOLOGY` | Terminology, intensifier, and timing constraints | 10.2, 10.20, 10.21, 9.3.7 | a glossary `deprecated_aliases` term in any unexempt block; a §10.20 empty intensifier in any unexempt block; a §10.21 vague evaluative term in a block whose trace says `material: true`; a §9.3.7 vague timing term (`promptly`, `soon`, `regularly`, `eventually`) in a block that declares `requirement_ids` |
| `OUT-HEADINGS-LISTS` | Heading and list mechanics | 10.17, 10.18 | heading level skipped, or list mechanics violated |
| `OUT-P0-EXACT` | Declared P0 values render exactly | 11.3.1, 11.6 | see §4 above |
| `OUT-P1-DECLARED` | Material P1 relations are declared by a rendered block | 11.3.2 | see §4 above |
| `OUT-POLICY-EXCEPTIONS` | No unrecorded or invalid policy exception is in play | 6.3 | an expired/mis-scoped exception, or an `authorization_ref` the snapshot lacks |
| `OUT-FINDING-DISPOSITIONS` | Every surfaced finding carries a disposition | 13.6, 15.3 | the receipt records unresolved findings; `UNAVAILABLE` when no receipt was supplied |
| `OUT-CONFORMANCE-VECTOR` | The conformance vector is computed per dimension without aggregation | 5.2, 15.6, 15.7 | an aggregated or averaged vector |
| `OUT-RECEIPT` | The candidate receipt is well formed and binds this bundle | 14.13, 16.12 | receipt seal, hash bindings, or schema violation; `NOT_APPLICABLE` when no receipt was supplied |

Two `SPECIFY`-specific traps worth restating:

- `OUT-TERMINOLOGY`'s vague-timing arm fires **only** on blocks declaring `requirement_ids`.
  That is the §9.3.7 rule: "promptly" in a rationale is a style question, but in a requirement
  it is nonconforming when timing is material.
- `OUT-DEONTIC-KEYWORDS`'s second arm fires **only** on blocks declaring `requirement_ids`.
  Attaching `requirement_ids` to an acceptance-criterion block that never restates the keyword
  therefore turns a clean bundle into a `FAIL`. Use `claim_ids` there.

---

## 6. Reading the report and the exit code

`_exit_for` in `src/ats/cli.py` maps the **conformance vector**, not the check statuses:

```text
any dimension FAIL                                       -> 1
mechanical | profile | preservation is UNAVAILABLE       -> 4
otherwise                                                -> 0
```

Never treat exit `0` as "clean" — read `summary.required_failed`, `p0_checks`, `p1_checks`, and
`block_coverage`.

The worked bundle's result **without** `--receipt`:

```json
{"checks_total": 25,
 "by_status": {"PASS": 22, "FAIL": 0, "UNAVAILABLE": 1, "NOT_APPLICABLE": 2, "REVIEW_REQUIRED": 0},
 "required_failed": 0, "required_unavailable": 1}
```

- the `1` `UNAVAILABLE` is `OUT-FINDING-DISPOSITIONS` (no receipt supplied);
- the `2` `NOT_APPLICABLE` are `OUT-RECEIPT` (no receipt supplied) and `OUT-P1-DECLARED`
  (the IR declares no material relation);
- `report_sha256` is
  `75324aea9a7039f2379dfa42bb43b93b932670a188c8dfdbdadd452e780aadba`.

And **with** `--receipt`:

```json
{"checks_total": 25,
 "by_status": {"PASS": 24, "FAIL": 0, "UNAVAILABLE": 0, "NOT_APPLICABLE": 1, "REVIEW_REQUIRED": 0},
 "required_failed": 0, "required_unavailable": 0}
```

Twenty-four passing, zero failing, zero unavailable — **and `semantic_review` is still
`UNAVAILABLE`**, with the rationale: "Mapping a block to an IR object establishes that the
renderer declared the object, not that the prose realizes it with the same meaning and force.
… This implementation holds neither, so semantic_review is never PASS here."

That is the point. A perfect deterministic result is eligibility, not acceptance.

Other report sections to read: `block_coverage` (`blocks_declared`, `blocks_found`,
`material_ir_objects`, `material_ir_objects_mapped`, `unmapped_material_ir_objects`,
`authorized_omissions`, `unknown_ir_references`), `p0_checks[]`, `p1_checks[]`,
`finding_dispositions`, and `conformance_rationale` — one non-empty string per dimension.

---

## 7. Candidate receipt

`ats.acceptance_receipt.v1`. Built by `ats.output.receipt.build_candidate_receipt`, which
requires the caller to supply `adjudicator` and refuses the self-identities
`{"ats", "ats-ir-linter", "ats-output-linter", "self", ""}` — nothing in the package can name
itself as its own adjudicator (§13.7, §14.11).

The worked bundle's receipt:

```json
{
  "schema_version": "ats.acceptance_receipt.v1",
  "receipt_id": "candidate:fixture-specify-stale-policy:6ec21218ff8acb39",
  "standard": "ATS-1",
  "spec_version": "1.0.0-draft.1",
  "policy_snapshot_id": "policy-fixture-specify",
  "profiles": ["SPECIFY"],
  "deterministic_summary": { "required_passed": 22, "required_failed": 0,
    "required_unavailable": 1, "advisory_findings": 0 },
  "semantic_summary": { "proposed": 0, "accepted": 0, "rejected": 0, "waived": 0,
    "unresolved": 0, "abstained": 1 },
  "conformance": { "mechanical": "PASS", "profile": "PASS",
    "semantic_review": "UNAVAILABLE", "preservation": "NOT_APPLICABLE",
    "forecast_calibration": "INSUFFICIENT_EVIDENCE" },
  "adjudicator": "arq-acceptance-authority",
  "output_sha256": "a69aeffb480a272c28062948c2746d798ffe2264acea498e3c0f95322682d467",
  "receipt_sha256": "22a9e4f0f8ce385caceacd2fc919a29e7c9b070a022b312427672ae648d36072"
}
```

`semantic_summary.abstained: 1` is the honest record that this implementation abstained from
semantic disposition rather than granting itself one. `unresolved: 0` here — because no output
check returned `REVIEW_REQUIRED` — is why re-linting with `--receipt` gives
`OUT-FINDING-DISPOSITIONS: PASS` rather than the `FAIL` the `ASSESS` bundle produces.

`ats output verify-receipt` re-checks the seal and the bindings; `status: "PASS"` means the
receipt reproduces its content address and binds this bundle. It does not mean the artifact is
accepted.

---

## 8. Staleness

§15.8: a conformance claim is stale when any material input changes. Touching `document.md`
changes its bytes, therefore `output_sha256`, the affected `text_sha256`, the trace seal, the
lint report, and the receipt. Regenerate the trace, re-lint, and rebuild the receipt — in that
order — after every prose change. The `parser_version`
(`markdown-it-py/commonmark@<version>`) is recorded in the report and receipt precisely so a
parser upgrade invalidates a prior replay claim.

§9.3.18 adds a `SPECIFY`-specific staleness rule: a changed requirement MUST record one of
compatible clarification, strengthened obligation, weakened obligation, changed scope, changed
acceptance criterion, supersession by another requirement, or withdrawal — and a superseded
requirement MUST retain a link to its successor. That record belongs in the IR, upstream of
rendering; a renderer that silently emits the new wording under the old identifier has
violated it.

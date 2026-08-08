# `ASSESS` rendering: block roles, marker mechanics, and the 25 output checks

Companion to `vocabularies.md` (all controlled values and profile slots). This file covers
the rendering surface: the marker byte convention, the trace's block contract, and exactly
what each `OUT-*` check does.

Sources: `schemas/ats_output_trace_v1.schema.json`,
`src/ats/output/{parse,trace,render_checks,lint,receipt}.py`,
`fixtures/output/assess-bundle/`, and `ATS-1_SPEC.md`.

---

## 1. The marker convention, byte-exact

From `fixtures/output/assess-bundle/document.md`. The first 260 bytes, verbatim:

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

Equivalently, each block contributes `## {heading}\n\n<!-- ats:block {id} -->\n{body}\n`,
the title contributes `# {title}\n`, and the parts are joined with a single `\n`. The file
ends with exactly one trailing newline. The assess-bundle document is 1803 bytes and hashes
to `ec7ea8378f720578538291acb07831ab72ea3c75eb9fdf8d36c39565aac77361`.

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

Because the heading is a separate block, **a P0 value that appears only in a heading is not
in any block body**, and `OUT-P0-EXACT` will fail it. Put P0 values in the body.

---

## 2. Block ids in the fixture bundle

Ten blocks, ordinals `0`–`9`, in document order:

| ordinal | `block_id` | `display_role` | `material` | realizes |
|---|---|---|---|---|
| 0 | `assess-question` | `question` | `false` | — (framing) |
| 1 | `assess-key-judgment` | `key_judgment` | `true` | `c1`; P0 `c1.force.likelihood.term` |
| 2 | `assess-confidence` | `confidence` | `true` | `c1`; P0 `c1.force.assessment_confidence.level` |
| 3 | `assess-evidence-1` | `supporting_evidence` | `true` | `e1`,`e2`; P1 `rel1`,`rel2` (`supports`) |
| 4 | `assess-contrary` | `contrary_evidence` | `true` | `e3`; P1 `rel5` (`qualifies`) |
| 5 | `assess-alternative` | `alternatives` | `true` | `alt1`; P1 `rel6` (`alternative_to`) |
| 6 | `assess-assumption` | `assumption` | `true` | `a1`; P1 `rel3` (`condition_for`) |
| 7 | `assess-boundary` | `boundary` | `true` | `b1`; P0 `b1.proposition`; P1 `rel4` (`qualifies`) |
| 8 | `assess-update-indicator` | `update_indicator` | `true` | `u1` via `update_indicator_ids` |
| 9 | `assess-recommendation` | `recommendation` | `true` | `r1` |

Recommended id form: `<profile>-<display_role slug>` with `-<n>` when the role repeats. The
fixture abbreviates some slugs (`assess-contrary` for `contrary_evidence`,
`assess-alternative` for `alternatives`, `assess-evidence-1` for `supporting_evidence`).
That is permitted — the id is opaque to the linter, which only checks its pattern,
uniqueness, ordering, and marker/trace agreement. `display_role` in the trace is the
authoritative role, so abbreviation loses nothing.

---

## 3. `display_role` — the full enum

`question` · `key_judgment` · `likelihood` · `confidence` · `confidence_basis` ·
`supporting_evidence` · `contrary_evidence` · `alternatives` · `assumption` · `boundary` ·
`update_indicator` · `recommendation` · `forecast` · `requirement` ·
`acceptance_criterion` · `authority` · `exception` · `rationale` · `note` · `heading` ·
`glossary` · `open_question`

`OUT-PROFILE-SECTIONS` requires these nine for `ASSESS` (`PROFILE_REQUIRED_ROLES` in
`src/ats/output/lint.py`, sourced from §9.2.12):

```text
question · key_judgment · confidence · supporting_evidence · contrary_evidence
· assumption · boundary · update_indicator · recommendation
```

Missing any one → `OUT-PROFILE-SECTIONS` `FAIL` → `conformance.profile: FAIL`.

`likelihood` and `confidence_basis` are **not** in the required set: §9.2.12 does not require
every heading, and the fixture renders the WEP inline in the `key_judgment` block and the
basis inline in the `confidence` block. Use the separate roles when the artifact is clearer
with them.

---

## 4. Trace block contract

Required on every block: `block_id`, `marker`, `ordinal`, `text_sha256`, `material`,
`display_role`, `section_id`, `claim_ids`, `evidence_ids`, `relation_ids`,
`requirement_ids`, `forecast_ids`.

Optional: `profile`, `heading_path`, `update_indicator_ids`, `p0_fields`, `p1_relations`,
`content_class`.

`ordinal` is zero-based, dense, and strictly increasing in document order.

### `p0_fields`

```json
{
  "field_ref": "c1.force.likelihood.term",
  "ir_pointer": "/sections/0/claims/0/force/likelihood/term",
  "rendered": "likely"
}
```

All three keys are required, and `additionalProperties: false`. `ir_pointer` is an RFC 6901
JSON Pointer into the **IR document** — array indices, not ids: `/sections/0/claims/2/...`
is `b1`, the third claim of the first section. `OUT-P0-EXACT` performs two comparisons:

1. `rendered` equals the IR value at `ir_pointer` (numbers stringified, booleans as
   `true`/`false`) — otherwise `status: "changed_unauthorized"`;
2. `rendered` appears as a substring of the declaring block's body — otherwise
   `status: "changed_unauthorized"`.

An unresolvable pointer, or a declaring block absent from the document, gives
`status: "unavailable"`. Declaring no P0 field anywhere gives `REVIEW_REQUIRED`: exact
rendering of protected values is then *undeclared* rather than verified.

Identifier-class P0 fields (`requirement_id`, `forecast_id`, `claim_id`, `evidence_id`,
`relation_id`, `indicator_id`, `artifact_id`, `section_id`, `concept_id`, `source_id`,
`exception_id`, `snapshot_id`, `version`, `revision`, `sha256`, `locator`) are exempt from
the `OUT-UNITS` check — §10.9's unit obligation is about material numbers, not names
containing digits — but they are still verified byte-for-byte by `OUT-P0-EXACT`. Declare
them.

### `p1_relations`

```json
{ "relation_id": "rel1", "type": "supports", "direction": "source_to_target" }
```

`relation_id`, `type`, `direction` required; `scope_note` optional. `direction` is
`source_to_target` | `target_to_source`. `OUT-P1-DECLARED` fails a material IR relation no
block declares (`status: "missing"`) and fails a declared `type` differing from the IR's
(`status: "direction_changed"`). When every material relation is declared it returns
`REVIEW_REQUIRED`, because declaration is not realization.

### `unmapped_ir_objects`

```json
{ "object_id": "e4", "reason": "not_material", "authorization_ref": "…" }
```

`reason` ∈ `not_material` | `retention_contract_allowed_omission` | `policy_exception` |
`profile_not_applicable`. A `policy_exception` reason whose `authorization_ref` is not an
exception in the snapshot fails `OUT-POLICY-EXCEPTIONS`.

### `content_class`

`prose` | `quotation` | `code` | `log` | `schema` | `counterexample` | `table`.

§5.6 exempts `quotation`, `code`, `log`, `schema`, `counterexample` from the surface checks
— **only when marked**. Fenced code and blockquotes are exempt by construction. Every skip
is counted and reported in the check `detail`, so no exemption is silent. `prose` and
`table` are not exempt.

---

## 5. The 25 output checks

All are `required`. Ids and titles are read from a real report.

| check | title | spec ref | what fails it |
|---|---|---|---|
| `OUT-BYTES` | Output and IR hashes match the trace | 14.2, 14.13, App. C | `output_sha256` or `ir_sha256` in the trace disagrees with the real bytes |
| `OUT-MARKDOWN-PARSE` | The document parses with a real Markdown parser | 14.4, 16.3 | commonmark parse failure; §14.4 forbids falling back to token-only rules |
| `OUT-CONSTRUCTS` | Unsupported Markdown constructs are identified | 16.3 | a construct outside the supported set is present and unreported |
| `OUT-MARKERS` | Source-map markers are intact and unique | 14.4 | malformed marker, duplicate `block_id`, or marker/trace disagreement |
| `OUT-TRACE-SCHEMA` | The trace validates and binds the same policy and IR | 6.6, 14.13 | trace schema violation, or `policy_sha256` ≠ the snapshot's `snapshot_sha256` |
| `OUT-BLOCK-HASHES` | Each block's declared hash matches its rendered bytes | 14.2, 16.2 | `text_sha256` ≠ SHA-256 of the body |
| `OUT-IR-REFS` | Every block reference resolves to an IR object of the right kind | 14.4 | `claim_ids` naming an evidence object, etc. |
| `OUT-MATERIAL-COVERAGE` | Every material IR object is mapped or authorized as omitted | 11.7, 11.8 | a material claim/evidence/relation/indicator neither mapped nor in `unmapped_ir_objects` |
| `OUT-UNKNOWN-REFS` | No block references an object absent from the IR | 11.7 | an id in the trace that the IR does not contain |
| `OUT-BLOCK-ORDER` | Block ordering is dense, ascending, and matches the document | 14.4, 16.2 | non-dense, non-increasing, or document-order mismatch |
| `OUT-PROFILE-SECTIONS` | Profile-required sections are rendered | 9.2.12, 9.3.5 | a required `display_role` for an active profile is absent |
| `OUT-WEP-CANONICAL` | Canonical WEP phrases only | 8.3 | a lexicon `input_aliases` phrase in unexempt prose |
| `OUT-WEP-INLINE-RANGE` | First material WEP use shows its range | 8.4 | first material WEP use in a section without its `display_range` inline |
| `OUT-DEONTIC-KEYWORDS` | Deontic keywords are canonical and uppercase | 8.16, 1.3 | `SHALL`/`SHALL NOT` rendered; or a block declaring `requirement_ids` renders no uppercase deontic keyword |
| `OUT-ACRONYMS` | Acronyms are expanded or permitted | 10.5 | first rendered use of an acronym neither expanded in place as `Expansion (ACR)` nor in `approved_abbreviations` |
| `OUT-UNITS` | Rendered P0 numbers carry units | 10.9, 9.3.8 | a declared P0 field whose rendered value is a standalone number with no unit, dimension, or `%` |
| `OUT-RELATIVE-TIME` | Relative time is anchored | 10.11 | a §10.11 relative-time term in a block whose claims declare no anchoring scope field |
| `OUT-TERMINOLOGY` | Terminology, intensifier, and timing constraints | 10.2, 10.20, 10.21, 9.3.7 | a glossary `deprecated_aliases` term in any unexempt block; a §10.20 empty intensifier in any unexempt block; a §10.21 vague evaluative term in a block whose trace says `material: true`; a §9.3.7 vague timing term in a block that declares `requirement_ids` |
| `OUT-HEADINGS-LISTS` | Heading and list mechanics | 10.17, 10.18 | heading level skipped, or list mechanics violated |
| `OUT-P0-EXACT` | Declared P0 values render exactly | 11.3.1, 11.6 | see §4 above |
| `OUT-P1-DECLARED` | Material P1 relations are declared by a rendered block | 11.3.2 | see §4 above |
| `OUT-POLICY-EXCEPTIONS` | No unrecorded or invalid policy exception is in play | 6.3 | an expired/mis-scoped exception, or an `authorization_ref` the snapshot lacks |
| `OUT-FINDING-DISPOSITIONS` | Every surfaced finding carries a disposition | 13.6, 15.3 | the receipt records unresolved findings; `UNAVAILABLE` when no receipt was supplied |
| `OUT-CONFORMANCE-VECTOR` | The conformance vector is computed per dimension without aggregation | 5.2, 15.6, 15.7 | an aggregated or averaged vector |
| `OUT-RECEIPT` | The candidate receipt is well formed and binds this bundle | 14.13, 16.12 | receipt seal, hash bindings, or schema violation; `NOT_APPLICABLE` when no receipt was supplied |

---

## 6. Reading the report and the exit code

`_exit_for` in `src/ats/cli.py` maps the **conformance vector**, not the check statuses:

```text
any dimension FAIL                                       -> 1
mechanical | profile | preservation is UNAVAILABLE       -> 4
otherwise                                                -> 0
```

Consequence, verified on the fixture bundle: linting **with** `--receipt` produces
`OUT-FINDING-DISPOSITIONS: FAIL` and `summary.required_failed: 1`, yet still exits `0`,
because that check only bears on `semantic_review`, which is already `UNAVAILABLE`. Never
treat exit `0` as "clean" — read `summary.required_failed`, `p0_checks`, `p1_checks`, and
`block_coverage`.

The clean fixture-bundle result **without** `--receipt`:

```json
{"checks_total": 25,
 "by_status": {"PASS": 22, "FAIL": 0, "UNAVAILABLE": 1, "NOT_APPLICABLE": 1, "REVIEW_REQUIRED": 1},
 "required_failed": 0, "required_unavailable": 1}
```

- the `1` `REVIEW_REQUIRED` is `OUT-P1-DECLARED` — expected and correct;
- the `1` `UNAVAILABLE` is `OUT-FINDING-DISPOSITIONS` (no receipt supplied);
- the `1` `NOT_APPLICABLE` is `OUT-RECEIPT` (no receipt supplied);
- `conformance` is `{mechanical: PASS, profile: PASS, semantic_review: UNAVAILABLE,
  preservation: NOT_APPLICABLE, forecast_calibration: INSUFFICIENT_EVIDENCE}`;
- `report_sha256` is
  `1b420828d3326363fec0e8944c282bd748a6590c88c21945d0fa283e9eafdb0a`, which is byte-identical
  to `fixtures/output/assess-bundle/document.lint.json`.

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

The fixture receipt, in full shape:

```json
{
  "schema_version": "ats.acceptance_receipt.v1",
  "receipt_id": "candidate:fixture-assess-rust-kernel:f0994c8b259133af",
  "standard": "ATS-1",
  "spec_version": "1.0.0-draft.1",
  "source_sha256": "1c4098e4305c49849065f1c430dfdffbbf5df654b20e48377efe7b72cc4aa7d5",
  "policy_snapshot_id": "policy-example-assess",
  "policy_snapshot_sha256": "7d2503c20bd94a1f76770575575f35d757b1ecce42adb5d37c87677cc3d6128c",
  "implementation": { "name": "ats", "version": "0.1.0",
    "rule_registry_version": "1.0.0-draft.1", "lexicon_version": "1.0.0-draft.1",
    "parser_version": "markdown-it-py/commonmark@4.2.0" },
  "profiles": ["ASSESS"],
  "deterministic_summary": { "required_passed": 22, "required_failed": 0,
    "required_unavailable": 1, "advisory_findings": 0 },
  "semantic_summary": { "proposed": 1, "accepted": 0, "rejected": 0, "waived": 0,
    "unresolved": 1, "abstained": 1 },
  "conformance": { "mechanical": "PASS", "profile": "PASS",
    "semantic_review": "UNAVAILABLE", "preservation": "NOT_APPLICABLE",
    "forecast_calibration": "INSUFFICIENT_EVIDENCE" },
  "adjudicator": "arq-acceptance-authority",
  "created_at": "2026-08-03T00:00:00Z",
  "output_sha256": "ec7ea8378f720578538291acb07831ab72ea3c75eb9fdf8d36c39565aac77361",
  "receipt_sha256": "f94012d3465cf71bb4db2d088e0514e39dce89fea2e822fce7184955fc03b120"
}
```

`adjudicator: "arq-acceptance-authority"` is an authority outside this workflow.
`semantic_summary.unresolved: 1` and `abstained: 1` record honestly that a surfaced finding
has no disposition — which is why `semantic_review` is `UNAVAILABLE` and why re-linting with
`--receipt` reports `OUT-FINDING-DISPOSITIONS: FAIL`. That FAIL is cleared by an external
adjudicator, never by editing prose.

`ats output verify-receipt` re-checks the seal and the bindings:

```json
{"status": "PASS", "receipt_id": "candidate:fixture-assess-rust-kernel:f0994c8b259133af",
 "declared_sha256": "f94012d3465cf71bb4db2d088e0514e39dce89fea2e822fce7184955fc03b120",
 "recomputed_sha256": "f94012d3465cf71bb4db2d088e0514e39dce89fea2e822fce7184955fc03b120",
 "detail": "receipt f94012d3465cf71b… reproduces its content address and binds the supplied source, policy, and output hashes",
 "unreplayable": []}
```

`PASS` means the receipt reproduces its content address. It does not mean the artifact is
accepted.

---

## 8. Staleness

§15.8: a conformance claim is stale when any material input changes. Touching
`document.md` changes its bytes, therefore `output_sha256`, the affected `text_sha256`, the
trace seal, the lint report, and the receipt. Regenerate the trace, re-lint, and rebuild the
receipt — in that order — after every prose change. The `parser_version`
(`markdown-it-py/commonmark@<version>`) is recorded in the report and receipt precisely so a
parser upgrade invalidates a prior replay claim.

# Worked `ASSESS` IR → bundle

Input and output are both repository fixtures, so nothing here is invented. Every command
was run from the ATS repository root; the reported results are what it printed.

| role | path |
|---|---|
| IR | `fixtures/ir/valid/assess_conforming.json` (`artifact_id: fixture-assess-rust-kernel`) |
| policy snapshot | `fixtures/policies/assess.json` (`policy-example-assess`, `profiles: ["ASSESS"]`) |
| source (for the IR's hashes) | `fixtures/ir/sources/assess_rust_kernel.txt` |
| bundle | `fixtures/output/assess-bundle/{document.md,document.trace.json,document.lint.json,document.receipt.json}` |
| deliberately broken twin | `fixtures/output/assess-broken/` |

---

## Step 1 — Gate the IR

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z --format text \
  ir lint fixtures/ir/valid/assess_conforming.json \
  --policy fixtures/policies/assess.json \
  --source fixtures/ir/sources/assess_rust_kernel.txt
```

`Mechanical: PASS`, `Profile: PASS`, `required_failed: 0`, `required_unavailable: 0`,
`extraction_status: "complete"`, `ASSESS` in the section profiles and in the snapshot. Gate
open.

## Step 2 — What the ledger contains

| object | role / type | material |
|---|---|---|
| `c1` | `judgment`, WEP `likely` + `moderate` confidence with a nine-dimension basis | yes |
| `a1` | `assumption` | yes |
| `b1` | `boundary`, `polarity: negative` | yes |
| `alt1` | `open_question`, `status: unresolved` | yes |
| `r1` | `recommendation` | yes |
| `e1`,`e2` | evidence, `repository_artifact`, `availability: present` | — |
| `e3` | evidence (contrary), `repository_artifact`, `availability: present` | — |
| `rel1`,`rel2` | `e1`/`e2` `--supports-->` `c1` | yes |
| `rel3` | `a1` `--condition_for-->` `c1` | yes |
| `rel4` | `b1` `--qualifies-->` `c1` | yes |
| `rel5` | `e3` `--qualifies-->` `c1` | yes |
| `rel6` | `alt1` `--alternative_to-->` `r1` | yes |
| `u1` | update indicator, `effect: decrease_likelihood`, targets `c1` | — |

Fourteen material objects. The lint report confirms
`block_coverage.material_ir_objects: 14`, `material_ir_objects_mapped: 14`.

## Step 3 — Block plan against §9.2.12

Ten blocks, one heading each, covering the nine `display_role` values that
`OUT-PROFILE-SECTIONS` requires for `ASSESS` plus `alternatives`:

| ordinal | heading | `block_id` | `display_role` | realizes |
|---|---|---|---|---|
| 0 | Question | `assess-question` | `question` | — (`material: false`) |
| 1 | Key judgment | `assess-key-judgment` | `key_judgment` | `c1` |
| 2 | Confidence | `assess-confidence` | `confidence` | `c1` |
| 3 | Supporting evidence | `assess-evidence-1` | `supporting_evidence` | `e1`,`e2`,`rel1`,`rel2` |
| 4 | Contrary evidence | `assess-contrary` | `contrary_evidence` | `e3`,`rel5` |
| 5 | Live alternatives | `assess-alternative` | `alternatives` | `alt1`,`rel6` |
| 6 | Assumptions | `assess-assumption` | `assumption` | `a1`,`rel3` |
| 7 | Boundary | `assess-boundary` | `boundary` | `b1`,`rel4` |
| 8 | Update indicators | `assess-update-indicator` | `update_indicator` | `u1` |
| 9 | Recommendation | `assess-recommendation` | `recommendation` | `r1` |

The `key_judgment` block absorbs the `likelihood` role (the WEP renders inline) and the
`confidence` block absorbs `confidence_basis` (the basis rationale renders inline). §9.2.12
does not require every heading, and `OUT-PROFILE-SECTIONS` does not require those two roles.

The question block is ordinal 0 and the key judgment is ordinal 1, so the load-bearing
judgment precedes every piece of background (§9.2.3, `ATS-DISC-001`).

## Step 4 — The rendered document, with markers

```markdown
# Acceptance-kernel language assessment

## Question

<!-- ats:block assess-question -->
Should Arq move the acceptance kernel from Python to Rust after the state model stabilizes?

## Key judgment

<!-- ats:block assess-key-judgment -->
A Rust migration is likely (55–80%) to reduce invalid-state defects in the acceptance kernel after the transition model is stable.

## Confidence

<!-- ats:block assess-confidence -->
moderate. The type-system argument is direct, but no controlled migration ablation exists.
```

…continuing through Supporting evidence, Contrary evidence, Live alternatives, Assumptions,
Boundary, Update indicators, and Recommendation. The file is 1803 bytes and hashes to
`ec7ea8378f720578538291acb07831ab72ea3c75eb9fdf8d36c39565aac77361`.

Byte shape of one block, exactly:

```text
## Key judgment\n\n<!-- ats:block assess-key-judgment -->\nA Rust migration is likely (55–80%) …\n
```

Marker on its own line, one blank line above it, **no** blank line between it and the body.
The heading is a separate, unmarked block.

Rendering decisions worth copying:

- `likely (55–80%)` — the canonical lexicon phrase plus the lexicon `display_range`, because
  this is the section's first material WEP use (§8.4). Not "probable", which is an
  `input_aliases` value that `OUT-WEP-CANONICAL` fails (§8.3).
- The confidence block is a **separate labelled statement** starting with the level and
  followed by the basis rationale — §8.11's conforming pattern. The likelihood is nowhere in
  it, and no confidence word appears in the key-judgment block.
- `e1` and `e2` render as a two-item bulleted list; `e3` renders as its own prose block under
  its own "Contrary evidence" heading, so the contrary line is not folded into the judgment
  (§9.2.7).
- `b1` has `polarity: negative`, and the prose keeps the negation:
  "The assessment does **not** apply to the policy-fluid orchestration plane." Polarity is P0
  (§11.3.1).
- The contrary-evidence block adds "as of revision 2026-08-03". The IR evidence proposition
  says "currently", a §10.11 relative-time term; the rendering anchors it so
  `OUT-RELATIVE-TIME` is satisfied.

## Step 5 — Trace metadata, block by block

Trace header:

```json
{
  "schema_version": "ats.output_trace.v1",
  "artifact_id": "fixture-assess-rust-kernel",
  "ir_sha256": "f0994c8b259133af321c9b10e875e7810f3fc8a5c0393c60a342ff56522c03e2",
  "output_sha256": "ec7ea8378f720578538291acb07831ab72ea3c75eb9fdf8d36c39565aac77361",
  "policy_snapshot_id": "policy-example-assess",
  "policy_sha256": "7d2503c20bd94a1f76770575575f35d757b1ecce42adb5d37c87677cc3d6128c",
  "profiles": ["ASSESS"],
  "renderer": { "name": "ats-assess-output", "version": "0.1.0",
                "skill_id": "skills/ats-assess-output" },
  "marker_scheme": { "kind": "html_comment",
                     "pattern": "<!-- ats:block {block_id} -->",
                     "end_pattern": "<!-- /ats:block {block_id} -->" },
  "created_at": "2026-08-03T00:00:00Z",
  "blocks": [ … ],
  "trace_sha256": "bf996156ef4286794062c173593cb01a595d3899ddf78fc8687798bf3b3cd5e4"
}
```

`ir_sha256` is SHA-256 over the IR's JCS-canonical bytes. `policy_sha256` must equal the
snapshot's own `snapshot_sha256` or `OUT-TRACE-SCHEMA` fails.

The judgment block, with its P0 declaration:

```json
{
  "block_id": "assess-key-judgment",
  "marker": "<!-- ats:block assess-key-judgment -->",
  "ordinal": 1,
  "text_sha256": "1a28e5286a57b86d4e041f13b5443198b6b38b89a23a6f36b287267cb0d6f770",
  "material": true,
  "display_role": "key_judgment",
  "section_id": "assessment",
  "claim_ids": ["c1"],
  "evidence_ids": [], "relation_ids": [], "requirement_ids": [], "forecast_ids": [],
  "profile": "ASSESS",
  "p0_fields": [
    { "field_ref": "c1.force.likelihood.term",
      "ir_pointer": "/sections/0/claims/0/force/likelihood/term",
      "rendered": "likely" }
  ]
}
```

`rendered: "likely"` equals the IR value at that pointer **and** appears verbatim in the
block body. Both comparisons are what `OUT-P0-EXACT` performs.

The confidence block declares the other P0 axis:

```json
"p0_fields": [
  { "field_ref": "c1.force.assessment_confidence.level",
    "ir_pointer": "/sections/0/claims/0/force/assessment_confidence/level",
    "rendered": "moderate" }
]
```

Confidence **level** is P0 (§11.3.1); the nine-dimension basis is inspectable evidence for
it and renders as prose.

The evidence block declares two P1 relations and no P0:

```json
{
  "block_id": "assess-evidence-1",
  "ordinal": 3,
  "material": true,
  "display_role": "supporting_evidence",
  "section_id": "assessment",
  "claim_ids": [],
  "evidence_ids": ["e1", "e2"],
  "relation_ids": ["rel1", "rel2"],
  "requirement_ids": [], "forecast_ids": [],
  "profile": "ASSESS",
  "p1_relations": [
    { "relation_id": "rel1", "type": "supports", "direction": "source_to_target" },
    { "relation_id": "rel2", "type": "supports", "direction": "source_to_target" }
  ]
}
```

`type` is `supports`, matching the IR exactly. Declaring `strongly_supports` here would be a
§11.6 strengthening and `OUT-P1-DECLARED` would report `direction_changed`.

The boundary block declares both a P0 field and a P1 relation:

```json
"p0_fields": [
  { "field_ref": "b1.proposition",
    "ir_pointer": "/sections/0/claims/2/proposition",
    "rendered": "The assessment does not apply to the policy-fluid orchestration plane." }
],
"p1_relations": [
  { "relation_id": "rel4", "type": "qualifies", "direction": "source_to_target" }
]
```

The whole proposition is declared P0 because its negation is the load-bearing part. Note the
pointer uses the **array index** `/claims/2`, not the id `b1`.

The update-indicator block uses the optional `update_indicator_ids` field:

```json
"update_indicator_ids": ["u1"]
```

All six material relations are declared across blocks 3–7, and all fourteen material objects
are mapped, so `unmapped_ir_objects` is absent entirely.

Build the trace with the shipped API — it computes `ordinal`, `marker`, `text_sha256`,
`ir_sha256`, `output_sha256`, and the seal, and validates against the schema:

```python
from ats.output.trace import build_trace
trace = build_trace(
    ctx, ir=ir, parsed=parse_markdown(text, locator=str(path)),
    output_bytes=text.encode("utf-8"),
    policy_snapshot_id=policy.snapshot_id,
    policy_sha256=policy.declared_sha256,
    block_metadata=block_metadata,
    renderer={"name": "ats-assess-output", "version": "0.1.0",
              "skill_id": "skills/ats-assess-output"},
)
```

## Step 6 — Lint the rendering

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z --format text \
  output lint fixtures/output/assess-bundle/document.md \
  --trace fixtures/output/assess-bundle/document.trace.json \
  --ir fixtures/ir/valid/assess_conforming.json \
  --policy fixtures/policies/assess.json
```

Observed (exit `0`):

```text
ATS-1 1.0.0-draft.1 / ASSESS
Mechanical: PASS
Profile: PASS
Semantic review: UNAVAILABLE
Preservation: NOT_APPLICABLE
Forecast calibration: INSUFFICIENT_EVIDENCE
Report: ats-sha256:1b420828d3326363fec0e8944c282bd748a6590c88c21945d0fa283e9eafdb0a
Summary: {"by_status": {"FAIL": 0, "NOT_APPLICABLE": 1, "PASS": 22, "REVIEW_REQUIRED": 1,
"UNAVAILABLE": 1}, "checks_total": 25, "required_failed": 0, "required_unavailable": 1}
  [REVIEW_REQUIRED] OUT-P1-DECLARED: 6 material relation(s) are declared by a rendered
    block. Declaration establishes that the block claims the relation, not that the prose
    realizes it with the same force and direction; that remains a semantic judgement.
  [UNAVAILABLE] OUT-FINDING-DISPOSITIONS: no receipt was supplied, so no disposition record
    exists to check (spec 15.3)
  [NOT_APPLICABLE] OUT-RECEIPT: no receipt was supplied to this run
```

That `report_sha256` is byte-identical to `fixtures/output/assess-bundle/document.lint.json`,
so the run is deterministic and replayable (§16.2).

This **is** the clean result. The three non-`PASS` checks are all honest states, not defects:
`OUT-P1-DECLARED` is `REVIEW_REQUIRED` because declaration is not realization, and the other
two are `UNAVAILABLE`/`NOT_APPLICABLE` only because this run had no `--receipt`.

Also worth reading:

```json
"block_coverage": {"blocks_declared": 10, "blocks_found": 10, "material_ir_objects": 14,
                   "material_ir_objects_mapped": 14, "unmapped_material_ir_objects": [],
                   "authorized_omissions": [], "unknown_ir_references": []},
"p0_checks": [{"field_ref": "c1.force.likelihood.term", "block_id": "assess-key-judgment",
               "rendered_value": "likely", "source_value": "likely", "status": "preserved"},
              … 3 total …],
"p1_checks": [{"relation_id": "rel1", "status": "declared",
               "block_ids": ["assess-evidence-1"]}, … 6 total …]
```

All three P0 entries `preserved`, all six P1 entries `declared`.

## Step 7 — The candidate receipt

```python
from ats.output.receipt import build_candidate_receipt
receipt = build_candidate_receipt(
    ctx, ir=ir, policy=policy,
    output_sha256="ec7ea8378f720578538291acb07831ab72ea3c75eb9fdf8d36c39565aac77361",
    lint_report=report,
    adjudicator="arq-acceptance-authority",
)
```

`adjudicator: "arq-acceptance-authority"` names an authority outside this workflow.
`build_candidate_receipt` raises `UsageError` for `ats`, `ats-ir-linter`,
`ats-output-linter`, `self`, or `""` — the renderer cannot name itself (§13.7, §14.11).

The receipt records `semantic_summary: {"proposed": 1, "accepted": 0, "rejected": 0,
"waived": 0, "unresolved": 1, "abstained": 1}` and
`conformance.semantic_review: "UNAVAILABLE"`. That is the bundle stating plainly that a
surfaced finding awaits an external disposition.

Verify the seal:

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli --now 2026-08-03T00:00:00Z \
  output verify-receipt fixtures/output/assess-bundle/document.receipt.json \
  --ir fixtures/ir/valid/assess_conforming.json \
  --document fixtures/output/assess-bundle/document.md \
  --policy fixtures/policies/assess.json
```

Observed:

```json
{"status": "PASS",
 "receipt_id": "candidate:fixture-assess-rust-kernel:f0994c8b259133af",
 "declared_sha256": "f94012d3465cf71bb4db2d088e0514e39dce89fea2e822fce7184955fc03b120",
 "recomputed_sha256": "f94012d3465cf71bb4db2d088e0514e39dce89fea2e822fce7184955fc03b120",
 "detail": "receipt f94012d3465cf71b… reproduces its content address and binds the supplied source, policy, and output hashes",
 "unreplayable": []}
```

`PASS` means the receipt reproduces its content address and binds this bundle. **It does not
mean the artifact is accepted.**

## Step 8 — Acceptance-readiness, and the FAIL you must not repair

Re-lint **with** the receipt:

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z --format text \
  output lint fixtures/output/assess-bundle/document.md \
  --trace fixtures/output/assess-bundle/document.trace.json \
  --ir fixtures/ir/valid/assess_conforming.json \
  --policy fixtures/policies/assess.json \
  --receipt fixtures/output/assess-bundle/document.receipt.json
```

Observed (still exit `0`):

```text
Summary: {"by_status": {"FAIL": 1, "NOT_APPLICABLE": 0, "PASS": 23, "REVIEW_REQUIRED": 1,
"UNAVAILABLE": 0}, "checks_total": 25, "required_failed": 1, "required_unavailable": 0}
  [FAIL] OUT-FINDING-DISPOSITIONS: 1 surfaced finding(s) remain undispositioned; Section
    15.3 forbids semantic-review conformance while any surfaced finding is undispositioned
```

Two lessons:

1. **Exit `0` with a `FAIL` present.** The exit code is derived from the conformance vector,
   and this check only bears on `semantic_review`, which is already `UNAVAILABLE`. Always
   read `summary.required_failed`.
2. **This `FAIL` is not a rendering defect.** Nothing in the prose is wrong. It is the
   standard saying the bundle is *eligible for* acceptance and not yet accepted. It is
   cleared only by an authorized external adjudicator dispositioning the finding — never by
   editing `document.md`, deleting a claim, or weakening the policy (§14.9, §15.3, §14.11).

---

## What the linter catches: the broken twin

`fixtures/output/assess-broken/` differs from the good bundle in exactly two body lines:

```diff
-A Rust migration is likely (55–80%) to reduce invalid-state defects in the acceptance kernel after the transition model is stable.
+A Rust migration is likely to reduce invalid-state defects in the acceptance kernel after the transition model is stable.

-The assessment does not apply to the policy-fluid orchestration plane.
+The assessment also covers the policy-fluid orchestration plane.
```

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z --format text \
  output lint fixtures/output/assess-broken/document.md \
  --trace fixtures/output/assess-broken/document.trace.json \
  --ir fixtures/ir/valid/assess_conforming.json \
  --policy fixtures/policies/assess.json
```

Observed (exit `1`):

```text
Mechanical: FAIL
Profile: PASS
Summary: {"by_status": {"FAIL": 2, "NOT_APPLICABLE": 1, "PASS": 20, "REVIEW_REQUIRED": 1,
"UNAVAILABLE": 1}, "checks_total": 25, "required_failed": 2, "required_unavailable": 1}
  [FAIL] OUT-WEP-INLINE-RANGE: assess-key-judgment: the first material use of 'likely' in
    section 'assessment' does not show its numeric range '55–80%' inline
  [FAIL] OUT-P0-EXACT: the IR value at /sections/0/claims/2/proposition is 'The assessment
    does not apply to the policy-fluid orchestration plane.' but the block declares it
    rendered as 'The assessment also covers the policy-fluid orchestration plane.'
```

The second defect is the one that matters most: the prose silently reversed the boundary's
polarity, which is a §11.3.1 P0 change and a §11.6 strengthening (deleting a boundary makes
the judgment broader). It reads perfectly fluently — which is exactly the hazard §20.1 names
as misleading fluency. Only the trace's P0 declaration makes it mechanically detectable.

Both are deterministic `OUT-*` failures, so both are in scope for immediate repair under
§14.9: restore the inline range and restore the boundary's exact wording. Neither repair
requires an adjudication, because neither involves a judgment about meaning — the IR already
states the correct value.

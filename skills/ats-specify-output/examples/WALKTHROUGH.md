# Worked `SPECIFY` IR → bundle

Input is a repository fixture; output is the bundle in `specify-bundle/`, emitted by
`emit_bundle.py` in this directory. Nothing here is invented — every rendered sentence comes
from a slot of `REQ-POLICY-017`. Every command was run from the ATS repository root and the
reported results are what it printed.

| role | path |
|---|---|
| IR | `fixtures/ir/valid/specify_conforming.json` (`artifact_id: fixture-specify-stale-policy`) |
| policy snapshot | `fixtures/policies/specify.json` (`policy-fixture-specify`, `profiles: ["SPECIFY"]`) |
| source (for the IR's hashes) | `fixtures/ir/sources/specify_stale_policy.txt` |
| bundle | `specify-bundle/{document.md,document.trace.json,document.lint.json,document.receipt.json}` |
| emitter | `emit_bundle.py` |

Regenerate or verify at any time:

```bash
PYTHONPATH=src .venv/bin/python skills/ats-specify-output/examples/emit_bundle.py
PYTHONPATH=src .venv/bin/python skills/ats-specify-output/examples/emit_bundle.py --check
```

`--check` prints `OK 4 file(s) reproduce byte-for-byte` and exits `0`, which is the
determinism claim of §16.2 made testable.

---

## Step 1 — Gate the IR

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z --format text \
  ir lint fixtures/ir/valid/specify_conforming.json \
  --policy fixtures/policies/specify.json \
  --source fixtures/ir/sources/specify_stale_policy.txt
```

Observed (exit `0`): `Mechanical: PASS`, `Profile: PASS`,
`Report: ats-sha256:20d01b42eb3655f39c862c5ea3505b53aa58c4cfdcb449ad507fbcf3f481fd9e`.

`extraction_status: "complete"`, `SPECIFY` in the section profiles and in the snapshot, and no
`requirement` slot holds the literal `"unknown"`. Gate open.

## Step 2 — What the ledger contains

One material claim, `REQ-POLICY-017`, `role: requirement`, with these slots:

| slot | value |
|---|---|
| `requirement_id` | `REQ-POLICY-017` |
| `actor` | `verifier` |
| `deontic` | `MUST` |
| `action` | `reject` |
| `object` | `acceptance receipt` |
| `trigger` | `executor presents an acceptance receipt` |
| `condition` | `receipt policy_sha256 differs from the current resolved policy snapshot` |
| `timing` | `before the acceptance transition` |
| `exceptions` | `[]` |
| `acceptance_criterion` | `A stale-policy fixture returns refused_stale_policy, emits no accepted transition, and records both policy hashes.` |
| `source_authority` | `Arq acceptance-policy kernel` |
| `rationale` | `A receipt proves conformance only under the policy used to evaluate it.` |

Plus `force.deontic: "MUST"` at claim level,
`scope: {"system": "Arq verifier", "authority_domain": "Arq acceptance-policy kernel"}`, and
empty `evidence`, `relations`, `update_indicators` arrays. One glossary entry defines
`policy_sha256`.

The lint report confirms `block_coverage.material_ir_objects: 1`,
`material_ir_objects_mapped: 1`.

## Step 3 — Block plan against §9.3.5 and §9.3.16

Four blocks. The three `display_role` values `OUT-PROFILE-SECTIONS` requires for `SPECIFY`
(`requirement`, `acceptance_criterion`, `authority`) plus a separated rationale:

| ordinal | heading | `block_id` | `display_role` | `material` |
|---|---|---|---|---|
| 0 | Requirement REQ-POLICY-017 | `specify-req-policy-017` | `requirement` | `true` |
| 1 | Acceptance criterion | `specify-acceptance-criterion` | `acceptance_criterion` | `true` |
| 2 | Source authority | `specify-authority` | `authority` | `true` |
| 3 | Rationale (non-normative) | `specify-rationale` | `rationale` | `false` |

The normative statement is ordinal 0, before anything that cannot change its interpretation
(§10.16, `ATS-DISC-001`). The rationale is last, in its own block, with its own heading and
`material: false` — §9.3.16 and §10.24 both require it to be structurally distinguishable from
normative text.

Only block 0 declares `requirement_ids`. Blocks 1 and 2 reference the claim through
`claim_ids`, because `OUT-DEONTIC-KEYWORDS` requires any block declaring `requirement_ids` to
render an uppercase ATS-1 deontic keyword, and neither of those blocks restates `MUST`.

## Step 4 — The rendered document

`specify-bundle/document.md`, in full:

```markdown
# Stale-policy rejection

## Requirement REQ-POLICY-017

<!-- ats:block specify-req-policy-017 -->
REQ-POLICY-017: When the executor presents an acceptance receipt and the receipt policy_sha256 differs from the current resolved policy snapshot, the verifier MUST reject the acceptance receipt before the acceptance transition.

## Acceptance criterion

<!-- ats:block specify-acceptance-criterion -->
A stale-policy fixture returns refused_stale_policy, emits no accepted transition, and records both policy hashes.

## Source authority

<!-- ats:block specify-authority -->
The obligation is imposed by the Arq acceptance-policy kernel.

## Rationale (non-normative)

<!-- ats:block specify-rationale -->
A receipt proves conformance only under the policy used to evaluate it. This paragraph is rationale and creates no obligation.
```

It hashes to `a69aeffb480a272c28062948c2746d798ffe2264acea498e3c0f95322682d467`.

Byte shape of one block, exactly:

```text
## Requirement REQ-POLICY-017\n\n<!-- ats:block specify-req-policy-017 -->\nREQ-POLICY-017: When the executor …\n
```

Marker on its own line, one blank line above it, **no** blank line between it and the body.
The heading is a separate, unmarked block.

### Rendering decisions worth copying

**Canonical statement order, §9.3.5.** The normative sentence follows
`[trigger] [condition] <actor> <DEONTIC> <action> <object> [timing]`:

```text
When the executor presents an acceptance receipt      <- trigger  (an event)
and the receipt policy_sha256 differs from the        <- condition (a state)
    current resolved policy snapshot,
the verifier                                          <- actor
MUST                                                  <- deontic
reject                                                <- action
the acceptance receipt                                <- object
before the acceptance transition.                     <- timing
```

Trigger and condition stay lexically separate because §9.3.6 forbids treating an event and a
state as interchangeable — merging them would change when and how often the obligation
activates.

**The identifier is in the body, not only the heading.** The body opens
`REQ-POLICY-017: When the executor …`. Headings are separate blocks, so a `requirement_id`
declared as a P0 field must appear in the body or `OUT-P0-EXACT` fails it.

**P0 slot values are verbatim, not smoothed.** The IR's `condition` is
`receipt policy_sha256 differs from the current resolved policy snapshot`. The natural English
paraphrase — "an acceptance receipt *whose* policy_sha256 differs from …" — does **not**
contain that string, so `OUT-P0-EXACT` would report `changed_unauthorized`. The rendering
therefore says "*and the receipt* policy_sha256 differs from …". Verbatim P0 sometimes costs a
little fluency; §11.3.1 is not negotiable.

**`exceptions: []` renders as nothing.** The IR's empty array says the source declared no
exception. Writing "No exceptions apply." would be adding a material claim (§11.7); writing
"Exceptions: none" implies a bounded search the ledger never claims.

**The authority block names the imposing authority.** §9.3.15 forbids silently restating an
external obligation as if it originated locally, so `source_authority` is printed rather than
assumed.

**The rationale block says outright that it creates no obligation.** §9.3.16's nonconforming
example is a rationale that smuggles in a second requirement ("… MUST reject stale receipts
because it also needs to log every rejection"). Keeping the reason in its own block, with its
own `display_role`, makes that structurally impossible.

## Step 5 — Trace metadata

Header:

```json
{
  "schema_version": "ats.output_trace.v1",
  "artifact_id": "fixture-specify-stale-policy",
  "ir_sha256": "6ec21218ff8acb3918d6350fbd8fe88a9dfff8627fc27998949ccebc2b93f7f5",
  "output_sha256": "a69aeffb480a272c28062948c2746d798ffe2264acea498e3c0f95322682d467",
  "policy_snapshot_id": "policy-fixture-specify",
  "policy_sha256": "7b30c3e27567413e22ebf983660a1687590b3ceab50ca17ad31f4f9c34766d2f",
  "profiles": ["SPECIFY"],
  "renderer": { "name": "ats-specify-output", "version": "0.1.0",
                "skill_id": "skills/ats-specify-output" },
  "marker_scheme": { "kind": "html_comment",
                     "pattern": "<!-- ats:block {block_id} -->",
                     "end_pattern": "<!-- /ats:block {block_id} -->" },
  "created_at": "2026-08-03T00:00:00Z",
  "blocks": [ … ],
  "trace_sha256": "37268b205708ff7637abf64b21311be24daf465850a951dd9d6a20741e7841b7"
}
```

`ir_sha256` is SHA-256 over the IR's JCS-canonical bytes. `policy_sha256` must equal the
snapshot's own `snapshot_sha256` or `OUT-TRACE-SCHEMA` fails.

The normative block, with all eight of its P0 declarations:

```json
{
  "block_id": "specify-req-policy-017",
  "marker": "<!-- ats:block specify-req-policy-017 -->",
  "ordinal": 0,
  "text_sha256": "0be8bb16d2174e9a68f0bccb4e3cf22a82774ddbe1ffc1be51d339315e4af59f",
  "material": true,
  "display_role": "requirement",
  "section_id": "requirement",
  "claim_ids": ["REQ-POLICY-017"],
  "evidence_ids": [], "relation_ids": [], "forecast_ids": [],
  "requirement_ids": ["REQ-POLICY-017"],
  "profile": "SPECIFY",
  "p0_fields": [
    { "field_ref": "REQ-POLICY-017.requirement.requirement_id",
      "ir_pointer": "/sections/0/claims/0/requirement/requirement_id",
      "rendered": "REQ-POLICY-017" },
    { "field_ref": "REQ-POLICY-017.requirement.deontic",
      "ir_pointer": "/sections/0/claims/0/requirement/deontic",
      "rendered": "MUST" },
    { "field_ref": "REQ-POLICY-017.requirement.actor",
      "ir_pointer": "/sections/0/claims/0/requirement/actor",
      "rendered": "verifier" },
    { "field_ref": "REQ-POLICY-017.requirement.action",
      "ir_pointer": "/sections/0/claims/0/requirement/action",
      "rendered": "reject" },
    { "field_ref": "REQ-POLICY-017.requirement.object",
      "ir_pointer": "/sections/0/claims/0/requirement/object",
      "rendered": "acceptance receipt" },
    { "field_ref": "REQ-POLICY-017.requirement.trigger",
      "ir_pointer": "/sections/0/claims/0/requirement/trigger",
      "rendered": "executor presents an acceptance receipt" },
    { "field_ref": "REQ-POLICY-017.requirement.condition",
      "ir_pointer": "/sections/0/claims/0/requirement/condition",
      "rendered": "receipt policy_sha256 differs from the current resolved policy snapshot" },
    { "field_ref": "REQ-POLICY-017.requirement.timing",
      "ir_pointer": "/sections/0/claims/0/requirement/timing",
      "rendered": "before the acceptance transition" }
  ]
}
```

Then blocks 1 and 2 declare one P0 field each — `acceptance_criterion` and
`source_authority` — and reference the claim through `claim_ids` only. Block 3 declares
nothing and is `material: false`.

Ten declared P0 values in total. `document.lint.json` reports every one
`status: "preserved"`:

```text
REQ-POLICY-017.requirement.requirement_id        preserved
REQ-POLICY-017.requirement.deontic               preserved
REQ-POLICY-017.requirement.actor                 preserved
REQ-POLICY-017.requirement.action                preserved
REQ-POLICY-017.requirement.object                preserved
REQ-POLICY-017.requirement.trigger               preserved
REQ-POLICY-017.requirement.condition             preserved
REQ-POLICY-017.requirement.timing                preserved
REQ-POLICY-017.requirement.acceptance_criterion  preserved
REQ-POLICY-017.requirement.source_authority      preserved
```

`REQ-POLICY-017` is a legitimate P0 declaration even though it ends in digits: identifier-class
P0 fields are exempt from `OUT-UNITS` (§10.9's unit obligation is about material numbers, not
names containing digits) while still being verified byte-for-byte by `OUT-P0-EXACT`.

There are no `p1_relations` anywhere, because `specify_conforming.json` has an empty
`relations` array. `OUT-P1-DECLARED` correctly reports `NOT_APPLICABLE`. Omitting the field is
right here; omitting it when the IR *does* carry a material relation is an
`OUT-P1-DECLARED: FAIL`.

## Step 6 — Lint the rendering

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z --format text \
  output lint skills/ats-specify-output/examples/specify-bundle/document.md \
  --trace skills/ats-specify-output/examples/specify-bundle/document.trace.json \
  --ir fixtures/ir/valid/specify_conforming.json \
  --policy fixtures/policies/specify.json
```

Observed (exit `0`):

```text
ATS-1 1.0.0-draft.1 / SPECIFY
Mechanical: PASS
Profile: PASS
Semantic review: UNAVAILABLE
Preservation: NOT_APPLICABLE
Forecast calibration: INSUFFICIENT_EVIDENCE
Report: ats-sha256:75324aea9a7039f2379dfa42bb43b93b932670a188c8dfdbdadd452e780aadba
Summary: {"by_status": {"FAIL": 0, "NOT_APPLICABLE": 2, "PASS": 22, "REVIEW_REQUIRED": 0,
"UNAVAILABLE": 1}, "checks_total": 25, "required_failed": 0, "required_unavailable": 1}
  [NOT_APPLICABLE] OUT-P1-DECLARED: the IR declares no material relation
  [UNAVAILABLE] OUT-FINDING-DISPOSITIONS: no receipt was supplied, so no disposition record
    exists to check (spec 15.3)
  [NOT_APPLICABLE] OUT-RECEIPT: no receipt was supplied to this run
```

That `report_sha256` is byte-identical to `specify-bundle/document.lint.json`, so the run is
deterministic and replayable (§16.2).

Also worth reading:

```json
"block_coverage": {"blocks_declared": 4, "blocks_found": 4, "material_ir_objects": 1,
                   "material_ir_objects_mapped": 1, "unmapped_material_ir_objects": [],
                   "authorized_omissions": [], "unknown_ir_references": []}
```

## Step 7 — The candidate receipt

```python
from ats.output.receipt import build_candidate_receipt
receipt = build_candidate_receipt(
    ctx, ir=ir, policy=policy,
    output_sha256="a69aeffb480a272c28062948c2746d798ffe2264acea498e3c0f95322682d467",
    lint_report=report,
    adjudicator="arq-acceptance-authority",
)
```

`adjudicator: "arq-acceptance-authority"` names an authority outside this workflow.
`build_candidate_receipt` raises `UsageError` for `ats`, `ats-ir-linter`,
`ats-output-linter`, `self`, or `""` — the renderer cannot name itself (§13.7, §14.11).

The emitted receipt:

```json
{
  "receipt_id": "candidate:fixture-specify-stale-policy:6ec21218ff8acb39",
  "profiles": ["SPECIFY"],
  "deterministic_summary": {"required_passed": 22, "required_failed": 0,
                            "required_unavailable": 1, "advisory_findings": 0},
  "semantic_summary": {"proposed": 0, "accepted": 0, "rejected": 0, "waived": 0,
                       "unresolved": 0, "abstained": 1},
  "conformance": {"mechanical": "PASS", "profile": "PASS",
                  "semantic_review": "UNAVAILABLE", "preservation": "NOT_APPLICABLE",
                  "forecast_calibration": "INSUFFICIENT_EVIDENCE"},
  "adjudicator": "arq-acceptance-authority",
  "output_sha256": "a69aeffb480a272c28062948c2746d798ffe2264acea498e3c0f95322682d467",
  "receipt_sha256": "22a9e4f0f8ce385caceacd2fc919a29e7c9b070a022b312427672ae648d36072"
}
```

`abstained: 1` is the honest record that this implementation abstained from semantic
disposition rather than granting itself one.

Verify the seal:

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli --now 2026-08-03T00:00:00Z \
  output verify-receipt skills/ats-specify-output/examples/specify-bundle/document.receipt.json \
  --ir fixtures/ir/valid/specify_conforming.json \
  --document skills/ats-specify-output/examples/specify-bundle/document.md \
  --policy fixtures/policies/specify.json
```

Observed:

```json
{"status": "PASS",
 "receipt_id": "candidate:fixture-specify-stale-policy:6ec21218ff8acb39",
 "declared_sha256": "22a9e4f0f8ce385caceacd2fc919a29e7c9b070a022b312427672ae648d36072",
 "recomputed_sha256": "22a9e4f0f8ce385caceacd2fc919a29e7c9b070a022b312427672ae648d36072",
 "detail": "receipt 22a9e4f0f8ce385c… reproduces its content address and binds the supplied source, policy, and output hashes",
 "unreplayable": []}
```

`PASS` means the receipt reproduces its content address and binds this bundle. **It does not
mean the artifact is accepted.**

## Step 8 — A perfect deterministic result is still not acceptance

Re-lint **with** the receipt:

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z --format text \
  output lint skills/ats-specify-output/examples/specify-bundle/document.md \
  --trace skills/ats-specify-output/examples/specify-bundle/document.trace.json \
  --ir fixtures/ir/valid/specify_conforming.json \
  --policy fixtures/policies/specify.json \
  --receipt skills/ats-specify-output/examples/specify-bundle/document.receipt.json
```

Observed (exit `0`):

```text
Mechanical: PASS
Profile: PASS
Summary: {"by_status": {"FAIL": 0, "NOT_APPLICABLE": 1, "PASS": 24, "REVIEW_REQUIRED": 0,
"UNAVAILABLE": 0}, "checks_total": 25, "required_failed": 0, "required_unavailable": 0}
  [NOT_APPLICABLE] OUT-P1-DECLARED: the IR declares no material relation
```

Twenty-four checks passing, zero failing, zero unavailable — and the conformance vector is
still:

```json
{"mechanical": "PASS", "profile": "PASS", "semantic_review": "UNAVAILABLE",
 "preservation": "NOT_APPLICABLE", "forecast_calibration": "INSUFFICIENT_EVIDENCE"}
```

with `conformance_rationale.semantic_review`:

> "Mapping a block to an IR object establishes that the renderer declared the object, not that
> the prose realizes it with the same meaning and force. Section 15.3 requires every surfaced
> finding to be dispositioned by an authorized human or a promoted detector, and Section 14.11
> assigns final semantic acceptance to an external authority. This implementation holds
> neither, so semantic_review is never PASS here."

**This is the whole point of the bundle.** A clean deterministic sweep means the output was
created through the approved workflow and is therefore *eligible for* acceptance. It does not
mean it is accepted, conformant, or approved. That call belongs to
`arq-acceptance-authority` — an authority outside this workflow — and no amount of green
checks moves it here.

`OUT-FINDING-DISPOSITIONS` passes on this bundle because no check returned
`REVIEW_REQUIRED`, so the receipt records `unresolved: 0`. The `ASSESS` fixture bundle is the
contrasting case: its `OUT-P1-DECLARED` is `REVIEW_REQUIRED`, the receipt records
`unresolved: 1`, and re-linting with `--receipt` reports
`OUT-FINDING-DISPOSITIONS: FAIL — 1 surfaced finding(s) remain undispositioned`. That `FAIL`
is not a rendering defect and is cleared only by an external adjudicator, never by editing
prose.

---

## What breaking a slot looks like

Three failures observed while building this bundle, each caught deterministically before the
document was ever shown to a reader:

1. **Attaching `requirement_ids` to a non-normative block.** Giving the acceptance-criterion
   block `requirement_ids: ["REQ-POLICY-017"]` produced:

   ```text
   [FAIL] OUT-DEONTIC-KEYWORDS: specify-acceptance-criterion: block declares requirement
     'REQ-POLICY-017' but renders no uppercase ATS-1 deontic keyword, so the obligation
     strength is not normative (spec 1.3)
   ```

   Fix: reference the claim through `claim_ids` there. §1.3 makes the uppercase keyword the
   carrier of normative force, so a block that claims to state a requirement must show it.

2. **A P0 value only in the heading.** Declaring
   `REQ-POLICY-017.requirement.requirement_id` while the identifier appeared only in
   `## Requirement REQ-POLICY-017` produced:

   ```text
   [FAIL] OUT-P0-EXACT: the block does not contain the exact P0 value 'REQ-POLICY-017' it
     declares
   ```

   Fix: repeat the identifier in the body. Headings are separate, unmarked blocks.

3. **A paraphrased condition.** Rendering "an acceptance receipt *whose* policy_sha256
   differs from …" while declaring the IR's `condition` produced the same
   `OUT-P0-EXACT` failure for that field. Fix: render the condition verbatim.

All three are deterministic `OUT-*` failures, so all three are in scope for immediate repair
under §14.9 — the IR already states the correct value, so no judgment about meaning is
involved and no adjudication is required.

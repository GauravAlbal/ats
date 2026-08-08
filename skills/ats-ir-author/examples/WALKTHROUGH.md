# Worked source → TextIR pairs

Both pairs use this repository's own fixtures as input and output, so nothing here is
invented. Every command below was run from the ATS repository root and the reported
results are what it printed.

---

## Pair 1 — `ASSESS`

**Input:** `fixtures/ir/sources/assess_rust_kernel.txt`
**Policy:** `fixtures/policies/assess.json` (`snapshot_id: policy-example-assess`, `profiles: ["ASSESS"]`)
**Output:** `fixtures/ir/valid/assess_conforming.json`

### Step 1 — bind the source

```bash
PYTHONPATH=src .venv/bin/python -c \
  "from ats.hashes import bind_file; b = bind_file('fixtures/ir/sources/assess_rust_kernel.txt'); \
   print(b.content_sha256); print(b.normalized_sha256)"
```

```text
1c4098e4305c49849065f1c430dfdffbbf5df654b20e48377efe7b72cc4aa7d5
1c4098e4305c49849065f1c430dfdffbbf5df654b20e48377efe7b72cc4aa7d5
```

Both hashes are equal because this source needs no normalization. The IR records both
anyway, so "no normalization happened" is stated rather than implied:

```json
"source": {
  "content_sha256": "1c4098e4305c49849065f1c430dfdffbbf5df654b20e48377efe7b72cc4aa7d5",
  "normalized_sha256": "1c4098e4305c49849065f1c430dfdffbbf5df654b20e48377efe7b72cc4aa7d5",
  "media_type": "text/plain",
  "locator": "fixtures/ir/sources/assess_rust_kernel.txt"
}
```

### Step 2 — resolve policy and profile first

The snapshot declares `profiles: ["ASSESS"]`, so the single section gets
`profiles: ["ASSESS"]` and the §9.2.2 / §9.2.4 slot set is the target. Nothing in the IR is
constructed before this is fixed.

### Step 3 — the id assignment under `ATS-ID-1`

One section (`assessment`), so document-wide ordinals are also section ordinals:

| source block | object | id | why that prefix |
|---|---|---|---|
| `Key judgment` | claim, `role: judgment` | `c1` | judgment → `c`, first |
| `Assumptions` | claim, `role: assumption` | `a1` | assumption → `a`, first |
| `Boundary` | claim, `role: boundary` | `b1` | boundary → `b`, first |
| `Contrary evidence and alternatives` (the unresolved alternative) | claim, `role: open_question` | `alt1` | open_question → `alt`, first |
| `Recommendation` | claim, `role: recommendation` | `r1` | recommendation → `r`, first |
| `Supporting evidence` items 1, 2 | evidence | `e1`, `e2` | evidence → `e`, source order |
| `Contrary evidence` | evidence | `e3` | continues the `e` ordinal |
| six typed relations | relation | `rel1`…`rel6` | relation → `rel`, source order |
| `Update indicators` | update indicator | `u1` | indicator → `u`, first |

No collisions, no authority-assigned identifiers, so nothing to resolve.

### Step 4 — the five force axes on `c1`, kept separate

The source sentence is *"A Rust migration is likely (55-80%) to reduce invalid-state
defects … after the transition model is stable."* That single sentence carries two axes,
and they land in two sibling fields:

```json
"force": {
  "likelihood": {
    "kind": "wep",
    "term": "likely",
    "display": "likely (55–80%)",
    "lower": 0.55,
    "upper": 0.8,
    "range_shown_inline": true
  },
  "assessment_confidence": {
    "level": "moderate",
    "basis": {
      "basis_type": "mixed",
      "evidence_quality": "mixed",
      "evidence_coverage": "partial",
      "source_independence": "partially_independent",
      "directness": "mixed",
      "consistency": "convergent",
      "assumption_sensitivity": "moderate",
      "environmental_stability": "mixed",
      "contrary_evidence": "addressed",
      "rationale": "The type-system argument is direct, but no controlled migration ablation exists."
    }
  }
}
```

Points to copy:

- `lower: 0.55` / `upper: 0.8` are the lexicon numbers for `likely`, not a rounding of the
  display range. `ATS-EPI-001` compares them to the lexicon exactly.
- `display` shows the range inline because this is the section's first material WEP use
  (§8.4, `IR-FIRST-USE-RANGE`, `ATS-EPI-002`), and `range_shown_inline: true` declares it.
- `display` contains **no** confidence word. Putting "moderate" in there is exactly what
  `ATS-EPI-004` and `IR-LIKELIHOOD-CONFIDENCE-SEP` fail (§8.11).
- The source's confidence sentence ("Moderate. Rust can encode closed transitions … rather
  than a controlled migration ablation.") supplies the level *and* the `rationale`. The nine
  dimensions are read off what the source actually says about its own basis — nothing was
  manufactured to make `high` defensible.
- Scope is decomposed, not buried in the proposition:
  `{"system": "Arq acceptance kernel", "condition": "after the transition model is stable",
  "time_horizon": "post-stabilization"}`.

### Step 5 — relations carry the structure, not adjectives

```text
rel1: e1  --supports-->      c1
rel2: e2  --supports-->      c1
rel3: a1  --condition_for--> c1
rel4: b1  --qualifies-->     c1
rel5: e3  --qualifies-->     c1
rel6: alt1 --alternative_to--> r1
```

`e3` is the contrary evidence. It is **not** deleted and it is **not** downgraded to a
caveat inside `c1`'s proposition — it is its own evidence object with a `qualifies`
relation, which is what §9.2.7 and `ATS-EVID-003` require. `alt1` is `role: open_question`
with `status: "unresolved"`, because the source states an alternative exists without
resolving it (§9.2.8).

### Step 6 — what was deliberately *not* built

The source says nothing about a resolution date, so there is no `forecast` slot and
`role: forecast` is not used. It states no requirement, so there is no `requirement` slot
and `ATS-REQ-*` report `NOT_APPLICABLE`. It states no external authority, so
`force.deontic` is absent entirely rather than set to a plausible value.

### Step 7 — lint

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z --format text \
  ir lint fixtures/ir/valid/assess_conforming.json \
  --policy fixtures/policies/assess.json \
  --source fixtures/ir/sources/assess_rust_kernel.txt
```

Observed (exit `0`):

```text
ATS-1 1.0.0-draft.1 / ASSESS
Mechanical: PASS
Profile: PASS
Semantic review: UNAVAILABLE
Preservation: NOT_APPLICABLE
Forecast calibration: INSUFFICIENT_EVIDENCE
Report: ats-sha256:d55bdf3c428597c077fe3649aa016eb182213479b60e6dd84e0ed8d825af273c
Summary: {"advisory_findings": 0, "by_status": {"FAIL": 0, "NOT_APPLICABLE": 5, "PASS": 9,
"REVIEW_REQUIRED": 11, "UNAVAILABLE": 5}, "required_failed": 0,
"required_review_required": 7, "required_unavailable": 0, "rules_total": 30}
```

**Read this correctly.** `required_failed: 0` and `required_unavailable: 0` with
`mechanical: PASS` and `profile: PASS` is the clean result. The eleven `REVIEW_REQUIRED`
rules and five `UNAVAILABLE` rules are not defects in the IR:

- `REVIEW_REQUIRED` — e.g. `ATS-EPI-004`, `ATS-EVID-003`, `ATS-TERM-003`. The detector
  recognises a subset of violations and found none. §5.4 and §16.5 forbid turning that
  silence into `PASS`.
- `UNAVAILABLE` — `ATS-REF-001`, `ATS-SCOPE-001`, `ATS-TERM-002`, `ATS-DISC-002`,
  `ATS-DISC-003`. These need `syntax`, `source_text`, `document_ast`, or
  `document_context`, none of which exists on the IR-only surface. Naming the missing input
  is the honest answer (§14.12).
- `semantic_review: UNAVAILABLE` and `forecast_calibration: INSUFFICIENT_EVIDENCE` are
  permanent for this implementation (§15.3, §14.11, §15.5) — not something to fix.

### What a violation looks like

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli --now 2026-08-03T00:00:00Z --format text \
  ir lint fixtures/ir/invalid/wep_interval_mismatch.json --policy fixtures/policies/assess.json
```

exits `1`. Every file in `fixtures/ir/invalid/` violates exactly one named thing, so it is
the fastest way to see which check owns which defect.

---

## Pair 2 — `SPECIFY`

**Input:** `fixtures/ir/sources/specify_stale_policy.txt`
**Policy:** `fixtures/policies/specify.json` (`snapshot_id: policy-fixture-specify`, `profiles: ["SPECIFY"]`)
**Output:** `fixtures/ir/valid/specify_conforming.json`

### The source

```text
Requirement ID: REQ-POLICY-017

Statement
When the executor presents an acceptance receipt whose policy_sha256 differs from the
current resolved policy snapshot, the verifier MUST reject the receipt before the
acceptance transition.

Acceptance criterion
Given a receipt with a stale policy_sha256, the verifier returns refused_stale_policy,
emits no accepted-change transition, and records the current and presented policy hashes
in the rejection receipt.

Authority
Arq acceptance-policy kernel.

Exception
None.
```

### Id assignment

The source authority already assigns `REQ-POLICY-017`. Under `ATS-ID-1` rule 4 the
authority identifier wins: `claim_id == requirement.requirement_id == "REQ-POLICY-017"`.
It is never renamed or normalized — requirement identifiers are P0 (§11.3.1) and §9.3.18
forbids reuse for a materially different obligation.

### Slot decomposition (§9.3.2)

One prose sentence becomes eleven typed slots. Canonical statement order (§9.3.5) is a
*rendering* convention; the slots are the semantics.

| slot | value | from |
|---|---|---|
| `requirement_id` | `REQ-POLICY-017` | `Requirement ID:` line |
| `actor` | `verifier` | "the verifier" — §9.3.4 requires it explicit; `ATS-REQ-001` rejects "the system"/"it" |
| `deontic` | `MUST` | the uppercase keyword in the source |
| `action` | `reject` | the verb |
| `object` | `acceptance receipt` | the thing acted on |
| `trigger` | `executor presents an acceptance receipt` | an **event** (§9.3.6) |
| `condition` | `receipt policy_sha256 differs from the current resolved policy snapshot` | a **state** (§9.3.6) — deliberately not merged with the trigger |
| `timing` | `before the acceptance transition` | observable ordering boundary (§9.3.7) |
| `exceptions` | `[]` | the source says "Exception: None." An empty array states that; omitting the key would leave it unstated |
| `acceptance_criterion` | `A stale-policy fixture returns refused_stale_policy, emits no accepted transition, and records both policy hashes.` | required by §9.3.9 for every `MUST`; `ATS-REQ-003` also rejects "works correctly"/"is robust" |
| `source_authority` | `Arq acceptance-policy kernel` | the `Authority` block (§9.3.15) |
| `rationale` | `A receipt proves conformance only under the policy used to evaluate it.` | non-normative, stored in its own slot (§9.3.16) |

`force.deontic: "MUST"` sits alongside `requirement.deontic: "MUST"`. The claim-level field
is the force axis (§8.16); the requirement-level field is the slot (§9.3.2). Both are
present and they agree — `IR-DEONTIC-VALIDITY` and `ATS-DEON-001` check the pairing, and
`ATS-DEON-001` also requires the surface `MUST` to appear verbatim in the proposition.

Scope is decomposed to
`{"system": "Arq verifier", "authority_domain": "Arq acceptance-policy kernel"}`.

`evidence`, `relations`, and `update_indicators` are present as empty arrays: the source
offers none, and an empty array is a positive statement while a missing key is a schema
failure.

### Lint

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z --format text \
  ir lint fixtures/ir/valid/specify_conforming.json \
  --policy fixtures/policies/specify.json \
  --source fixtures/ir/sources/specify_stale_policy.txt
```

Observed (exit `0`): `Mechanical: PASS`, `Profile: PASS`,
`Report: ats-sha256:20d01b42eb3655f39c862c5ea3505b53aa58c4cfdcb449ad507fbcf3f481fd9e`.

---

## Encoding permission and capability

These are force values, not roles, and they are encoded differently. Both forms below were
compiled against `fixtures/policies/specify.json` and lint at `Mechanical: PASS`,
`Profile: PASS`, `required_failed: 0`.

**Permission — `role: requirement`, `MAY` in both deontic fields.** §9.3.12 requires the
permitted actor, the permitted action, the boundary of permission, and any conditions that
still apply, so the boundary goes in `condition` and `constraints`:

```json
{
  "claim_id": "REQ-VER-009",
  "role": "requirement",
  "proposition": "The verifier MAY reject a receipt whose policy hash is stale, only when the acceptance transition has not started.",
  "material": true,
  "polarity": "positive",
  "status": "asserted",
  "scope": { "system": "Arq verifier", "authority_domain": "Arq acceptance-policy kernel" },
  "force": { "deontic": "MAY" },
  "requirement": {
    "requirement_id": "REQ-VER-009",
    "actor": "verifier",
    "deontic": "MAY",
    "action": "reject",
    "object": "receipt whose policy hash is stale",
    "condition": "the acceptance transition has not started",
    "constraints": ["permission is bounded to the pre-transition window"],
    "source_authority": "Arq acceptance-policy kernel",
    "rationale": "Rejecting after the transition would require a compensating rollback."
  }
}
```

**Capability — `force.deontic: CAN` on a claim that is not a requirement.**
`requirement_slots.deontic` has no `CAN`, and §9.3.13 states a capability statement MUST
NOT satisfy a required-behavior slot, so the role reports the fact instead:

```json
{
  "claim_id": "c1",
  "role": "observation",
  "proposition": "The verifier CAN compute the policy hash in under 500 ms.",
  "material": true,
  "polarity": "positive",
  "status": "asserted",
  "scope": { "system": "Arq verifier", "version": "0.1.0" },
  "quantifier": { "kind": "maximum", "value": 500, "unit": "ms" },
  "force": { "deontic": "CAN" }
}
```

Note `quantifier.unit: "ms"`: §10.9 and `ATS-NUM-001` require a unit on a material number,
and `quantifier.kind: "maximum"` requires `value` per the schema. `role: observation` also
means this claim must carry **no** `likelihood` and no `assessment_confidence` —
`ATS-EVID-001` fails an observation that carries assessment machinery (§7.4, §9.2.5).

---

## Representing what the source did not settle

Two fixtures show the two typed states. Neither invents a value to fill the gap.

### `partial` — `fixtures/ir/valid/assess_partial_extraction.json`

```json
"extraction_status": "partial",
"extraction_issues": [
  {
    "issue_id": "missing-alternatives",
    "status": "partial",
    "description": "The source states that alternatives exist but does not enumerate them, so no alternative claim could be constructed without inventing content.",
    "affected_fields": ["sections/0/claims/c1/alternatives"]
  }
]
```

The alternative claim is simply absent, and the gap is named. §7.16 forbids filling the slot
with a likely value.

### `ambiguous` — `fixtures/ir/valid/assess_represented_ambiguity.json`

```json
"extraction_status": "ambiguous",
"extraction_issues": [
  {
    "issue_id": "scope-of-migration",
    "status": "ambiguous",
    "description": "The source does not resolve whether 'kernel' includes the policy plane.",
    "affected_fields": ["sections/0/claims/c1/scope/system"],
    "candidate_interpretations": [
      "The acceptance kernel only.",
      "The acceptance kernel together with the policy-fluid orchestration plane."
    ]
  }
]
```

and on the claim itself:

```json
"status": "ambiguous",
"interpretations": [
  "The migration covers the acceptance kernel only.",
  "The migration covers the acceptance kernel and the policy-fluid orchestration plane."
]
```

Two materially distinct readings, at the document level and on the claim, agreeing with
each other. The schema enforces `minItems: 2` on `interpretations` whenever
`status == "ambiguous"`; `fixtures/ir/invalid/ambiguous_without_distinct_readings.json` is
the counterexample and exits `1`.

The convenient move — picking "the acceptance kernel only" because it lints cleanly — is
the failure mode §20.1 names as misleading fluency and §20.6 forbids.

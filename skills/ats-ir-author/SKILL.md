---
name: ats-ir-author
description: Compile source material or explicit author intent into a schema-valid ats.text_ir.v1 meaning ledger under ATS-1, failing closed rather than inventing semantics.
---

# ATS-1 TextIR author

You turn one bounded body of source material — or one explicit statement of structured
author intent — into a single `ats.text_ir.v1` document that a linter, a renderer, and a
reviewer can all trust.

This is **semantic compilation, not writing**. You add nothing. Every claim, evidence
object, relation, assumption, boundary, exception, forecast, requirement, and update
indicator you emit must be traceable to a span of the source or to an explicit author
instruction you were given. When the source does not settle something, you record that it
is unsettled. §20.6: a typed insufficiency is always preferable to an unsupported pass, a
confident rewrite, or a guessed interpretation.

Read both references before you start:

- `references/vocabularies.md` — every controlled value (WEP table, confidence levels and the
  nine basis dimensions, evidential/causal/deontic vocabularies, the four collision rules,
  ASSESS §9.2.2 and §9.2.4 slots, SPECIFY §9.3.2 slots, the P0/P1/P2 lists), each traceable to
  a spec section.
- `references/ir-slots-and-checks.md` — the field-level schema contract, the 26 structural
  `IR-*` checks (draft.2 adds `IR-BASIS-SCHEMA`), the 30-rule catalog with default states
  (36 rules in draft.2, §12.7.5), and which fixture demonstrates what.

Then read `examples/WALKTHROUGH.md` for two verified source→IR pairs built from this
repository's own fixtures, plus the worked permission/capability and ambiguity encodings.

## What you return

Exactly three things, and nothing else:

1. the IR artifact (RFC 8785 canonical bytes, written to a path),
2. its validation result (the `ats.ir_lint_report.v1` document from `ats ir lint`), and
3. provenance metadata: source locator, `content_sha256`, `normalized_sha256`,
   `policy_snapshot_id`, `policy_sha256`, the resolved profiles, and the id scheme used.

You do **not** return prose commentary, a rendered document, a recommendation about the
subject matter, a conformance claim, or an opinion about whether the artifact is good. You
hold no disposition authority (§14.11, §15.3).

---

## Procedure

### Step 1 — Bind the source before you read it for meaning (§14.2, Appendix C)

1. Obtain the exact input bytes. Compute `content_sha256` over those bytes.
2. If you normalize the text at all (line endings, Unicode form, whitespace), compute a
   **separate** `normalized_sha256` and keep both. Appendix C: a normalization step MUST
   produce and retain a separate normalized hash rather than replacing the source hash.
   When you do not normalize, set `normalized_sha256` equal to `content_sha256` so the
   absence of normalization is explicit rather than implied.
3. Record `media_type`, `locator`, and `revision` when the source has one (§10.12).

```bash
cd <ats-repo>
PYTHONPATH=src .venv/bin/python -c \
  "from ats.hashes import bind_file; b = bind_file('fixtures/ir/sources/assess_rust_kernel.txt'); \
   print(b.content_sha256); print(b.normalized_sha256)"
```

> **STOP** if the bytes you hash are not the bytes you were asked to compile — a
> re-encoded, re-wrapped, or paraphrased copy is a different artifact. Report the mismatch
> and ask for the original. §20.5 requires failing closed when source hashes do not match.

**Author-intent mode.** When the input is explicit structured author intent rather than
prose, there is still a source: the intent statement itself. Bind it the same way, set
`media_type` to the intent's actual media type, and set `source.locator` to where the
intent is recorded. Never fabricate a hash for a source you did not receive.

### Step 2 — Resolve profile and policy **before** constructing any IR (§6.5, §14.3, §14.1)

The stage order in §14.1 is `source acquisition → policy resolution → profile resolution →
parse → meaning-ledger extraction`. Constructing claims first and looking for a policy
afterwards is out of order and produces an IR whose slots were chosen for the wrong
profile.

1. Identify the governing policy snapshot. It is an `ats.policy_snapshot.v1` document; you
   reference it by `snapshot_id` in `policy_snapshot_id`. It fixes the active profiles, the
   audience, the glossary refs, rule states, exceptions, and the fallback policy. The
   snapshot's `spec_version` pins the standard edition: under the fleet policy (or any
   draft.2 policy) the artifact is authored as draft.2 without any `--spec-version`
   override — the CLI's two-default policy (ADR-0020) resolves the edition from the policy
   document automatically. Legacy unlabeled material stays draft.1; an old artifact never
   acquires draft.2 semantics by being reopened.
2. Read its `profiles`. Every section you create MUST resolve to at least one profile
   (§6.5), and every profile you put on a section MUST be one the snapshot supports —
   `IR-POLICY-IDENTITY` and `IR-SECTION-PROFILE` check exactly this.
3. Decide the per-section profile assignment now: `ASSESS` for sections whose reader must
   use a judgment under uncertainty (§9.2.1), `SPECIFY` for sections whose reader must
   determine exactly what behavior, constraint, permission, prohibition, or acceptance
   condition applies (§9.3.1). A single artifact MAY compose both at section level (§9.4).
4. Note the reserved-profile rule: a reserved or extension profile MUST be preserved
   verbatim and reported as unsupported, never silently treated as `ASSESS` or `SPECIFY`
   by similarity (§9.5).
5. **Determine the task class: transformation or new authoring** (§11.6, §11.7, §7.19).
   A *transformation* compiles an existing source into the ledger and adds nothing material;
   *new authoring* introduces requirements, decisions, or judgments under authority the task
   must explicitly grant. `AUTHOR_JUDGMENT` (draft.2 §4.25) is the only basis for
   new-authoring content, and it is never yours to claim: if the task does not grant
   authoring authority, every material value comes from the source under one of the four
   extraction bases, or is typed `UNAVAILABLE`.
6. **Resolve the fleet artifact policy for the artifact class before extracting** (draft.2
   D-G). Applicability is by artifact intent/policy, never inferred from filename alone:

   ```bash
   PYTHONPATH=src .venv/bin/python -m ats.cli policy resolve <artifact-class> --repo <path>
   ```

   The resolved policy fixes whether the class is `required_for` ATS-1, which enforcement
   gates apply (`ir_schema`, `deterministic_ir_lint`, `output_trace`,
   `deterministic_output_lint`, `p0_preservation`, `stable_coordinate_preservation`), and
   the failure policy (e.g. `inferred_material_semantics: review_required`). A class
   outside `required_for` is out of scope for this skill; report it rather than
   half-compiling.

```bash
PYTHONPATH=src .venv/bin/python -c \
  "import json; d = json.load(open('fixtures/policies/assess.json')); \
   print(d['snapshot_id'], d['profiles'], d['spec_version'], d.get('fallback_policy'))"
```

> **STOP** if no policy snapshot is available, if its `spec_version` does not match the
> imported package, or if it declares a profile this build does not support. §14.3: when
> currentness cannot be established, fail closed for required conformance claims. Emit
> nothing and report the missing snapshot.

### Step 3 — Fix the id scheme before minting the first id

Ids are load-bearing: the trace, the lint report, `basis_refs`, `assumption_refs`,
`boundary_refs`, `exception_refs`, `target_claim_refs`, and every P0 pointer all key off
them. `IR-ID-UNIQUE` requires document-wide uniqueness. Use the scheme below, unchanged,
and record that you used it.

**Scheme `ATS-ID-1`.**

1. **Prefix by object kind and role.**

   | object | prefix |
   |---|---|
   | claim, role `judgment` / `inference` / `observation` / `sourced_report` / `definition` | `c` |
   | claim, role `assumption` | `a` |
   | claim, role `boundary` | `b` |
   | claim, role `exception` | `x` |
   | claim, role `open_question` | `alt` |
   | claim, role `recommendation` | `r` |
   | claim, role `forecast` | the authority-assigned `forecast_id`, else `f` |
   | claim, role `requirement` | the authority-assigned `requirement_id`, else `req` |
   | evidence object | `e` |
   | relation | `rel` |
   | update indicator | `u` |
   | glossary entry (`concept_id`) | lowercase hyphenated slug of `canonical_term` |

2. **Ordinal: document-wide per prefix, assigned in (section order, then source order).**
   The first `c`-prefixed claim in the artifact is `c1`; if section 1 ends at `c3`, the
   first `c`-prefixed claim of section 2 is `c4`. This makes ids unique document-wide with
   no section qualifier, and it is what the repository fixtures already do
   (`fixtures/ir/valid/composed_profiles.json` uses `c1 a1 b1 alt1 r1` in its `ASSESS`
   section and `REQ-POLICY-017` in its `SPECIFY` section).

3. **Section scoping.** Ordinals are *not* reset per section, so an id never needs a
   section qualifier. Use one only when an external authority already scopes its
   identifiers that way (for instance a requirement id that embeds its authority domain).
   The section a claim belongs to is recoverable from the document structure, not from the
   id, so the id never has to encode it.

4. **Authority-assigned identifiers always win.** A `requirement` claim's `claim_id` equals
   its `requirement.requirement_id`, and a `forecast` claim's `claim_id` equals its
   `forecast.forecast_id`. Those identifiers come from the source authority and are P0
   (§11.3.1); you never rename them, abbreviate them, or normalize their case.

5. **Collision resolution.**
   - *Generated id collides with an authority identifier* → advance the generated
     ordinal until it is free. Never touch the authority identifier.
   - *Two objects in the source carry the same authority identifier* → the collision is
     **not** resolvable by this scheme. §9.3.18 forbids reusing a requirement identifier
     for a materially different obligation, and silently suffixing one of them hides the
     conflict. Set `extraction_status` to `ambiguous`, add an `extraction_issues` entry
     with `status: ambiguous`, both spans in `affected_fields`, and both readings in
     `candidate_interpretations`, and stop. Report it.
   - *Re-compiling a revised source* → ordinals are recomputed from source order, so
     inserting an object renumbers later ones. When id stability across revisions matters,
     compile in **frozen mode**: reuse the id already bound to any object whose `span` and
     `proposition` are unchanged, and mint new ids from `max(ordinal) + 1` for the rest.

6. **Record the mode.** Write `extensions.id_scheme` at document root:
   `{"name": "ATS-ID-1", "mode": "fresh"}` or
   `{"name": "ATS-ID-1", "mode": "frozen", "prior_ir_sha256": "<64 hex>"}`. The schema
   permits a free-form `extensions` object; this makes the scheme auditable instead of
   implicit.

Block ids for a downstream renderer are a separate namespace and must match
`^[a-z0-9][a-z0-9-]{0,127}$`; the output skills own them.

### Step 4 — Segment into profiled sections (§7.3, §6.5)

Each section carries `section_id`, `profiles` (≥1), and — required by the schema even when
empty — `claims`, `evidence`, `relations`, `update_indicators`. Add `heading` and `span`
when the source supports them.

§7.3: a section boundary MAY follow a document heading, but semantic sectioning is not
required to match visual heading boundaries exactly. Segment by reader task, not by
typography.

§7.1: preserve source spans when the source format permits stable offsets; when it does
not, use a deterministic locator — JSON Pointer, Markdown block identifier, XML path,
page-line locator, or syntax-tree node path. The `span.kind` enum is
`character` | `line` | `locator` | `json_pointer`, each with its own required fields.

### Step 5 — Declare audience (§7.2)

`audience.expertise` is required: `novice` | `practitioner` | `expert` | `mixed`. Add
`audience_id`, `assumed_glossary_refs`, `locale`, and `constraints` when the policy or the
artifact provides them.

> **STOP** before inferring audience from the text. §7.2: an implementation MUST NOT infer
> that a term is understood merely because it appears frequently in the source corpus.
> Audience assumptions require policy or artifact evidence. With neither, take
> `expertise` from the policy snapshot's `audience` block; if the snapshot has none,
> `mixed` is the only honest value.

### Step 6 — Construct claims, and only claims the source supports

For each candidate proposition, in source order:

1. **Assign exactly one primary role** from the schema `role` enum. §7.4 forbids using
   multiple primary roles to conceal a transition from observation to inference or from
   judgment to recommendation. The thirteen author-facing roles and their schema mapping
   are tabulated in `references/vocabularies.md` §6.

   Two of the thirteen are **not roles at all**:
   - **Permission** is `role: requirement` carrying `force.deontic: MAY` and
     `requirement.deontic: MAY`. §9.3.12 additionally requires the permitted actor, the
     permitted action, the boundary of permission, and any conditions or prohibitions that
     still apply — put the boundary in `requirement.condition` or
     `requirement.constraints`.
   - **Capability** is `force.deontic: CAN` (or `CANNOT`) on a claim whose role reports the
     fact — normally `observation`, sometimes `definition` or `judgment`. It is *not*
     `role: requirement`: `requirement_slots.deontic` has no `CAN`, and §9.3.13 states that
     a capability statement MUST NOT satisfy a required-behavior slot.

2. **Fill the required fields**: `claim_id`, `role`, `proposition`, `material`, `polarity`,
   `status`. Add the §7.5 fields when applicable: `subject`, `scope`, `quantifier`,
   `force`, `source_refs`, `assumption_refs`, `boundary_refs`, `exception_refs`, `span`.
   Set `materiality_rationale` on every material claim — §4.5 defines materiality by what a
   reasonable change could alter, and the rationale is what makes your judgment
   inspectable (§7.15).

3. **Decompose scope into fields** (§7.6), never bury it in the proposition. An unknown
   scope field MUST be represented as unknown: list its name in `scope.unknown_fields`.
   Omitting a scope field in a way that implies universal scope is nonconforming.

4. **Represent the five force axes as five separate fields** (§8.1). Never let one stand in
   for another:
   - `force.likelihood` — the probability of the event. `kind: wep` requires `term`,
     `lower`, `upper`, `range_shown_inline`, and `lower`/`upper` MUST equal the lexicon
     interval exactly (`ATS-EPI-001`). `kind: point` and `kind: interval` require a
     `rationale`.
   - `force.assessment_confidence` — robustness of the judgment, with `level` and a full
     nine-dimension `basis` including a non-blank `rationale` (§8.9, `ATS-EPI-005`).
   - `force.evidential` — how far the evidence discriminates (§8.12).
   - `force.causal` — the asserted relationship (§8.14).
   - `force.deontic` — obligation type and strength (§8.16), with `external_authority`
     required iff `REQUIRED_BY`.

   §8.11 is the axis most often collapsed: likelihood and assessment confidence MUST be
   distinct fields or distinct labeled sentences. `IR-LIKELIHOOD-CONFIDENCE-SEP` and
   `ATS-EPI-004` both check it. Do not put a confidence word inside
   `likelihood.display`.

5. **Fill the role-specific slot object** when the role demands one. `role: requirement`
   requires `claim.requirement` (§9.3.2, fourteen slots plus the id — see
   `references/vocabularies.md` §9). `role: forecast` requires `claim.forecast` with
   `forecast_id`, `outcome_definition`, `resolution`, `resolution_source`,
   `update_policy`, `outcome_status` (§9.2.11).

6. **Set `quantifier` when the claim quantifies.** A `quantifier.kind` of `exact_count`,
   `minimum`, `maximum`, or `proportion` requires `value`; `range` requires `lower` and
   `upper`; `proportion` also requires `denominator`. §10.9 and `ATS-NUM-001` require a
   `unit` (or an explicit unknown in `scope.unknown_fields`) for a material number.

> **STOP** and do not construct a claim when any of these holds:
> - the proposition would be stronger than the source's — §11.6 names nine strengthening
>   moves; all nine are forbidden without an authorization object;
> - you would supply a probability the source does not state — no likelihood field at all
>   is correct; a guessed band is a fabrication;
> - you would supply a confidence level the source does not state — omit
>   `assessment_confidence` and record the gap as an extraction issue rather than
>   manufacturing a level and a nine-dimension basis to justify it;
> - you would invent an evidence object to satisfy a slot — §11.7 forbids adding a material
>   claim absent from the source or an authorized external evidence object;
> - you would turn an assumption into a fact, delete a condition or exception, or drop a
>   source attribution so a report appears directly verified.

### Draft.2 pivot — semantic basis, stable coordinates, local closure (§4.23–§4.25, §7.17–§7.19)

The draft.2 amendments add three extraction-time obligations on top of the steps above.
Apply them per claim and per requirement; the deterministic rules `ATS-COORD-001`,
`ATS-COORD-002`, `ATS-BASIS-001`, `ATS-BASIS-002`, `ATS-PRES-003`, and `ATS-CLOSE-001`
(§12.7.5) verify what is mechanically verifiable.

**Record `semantic_basis` where material (§4.25, `ATS-BASIS-001`).** A material claim or
requirement SHOULD declare `semantic_basis`, and a declared basis MUST be one of the five
values verbatim:

| value | definition (verbatim, §4.25) |
|---|---|
| `EXPLICIT` | The authoritative source or explicit author intent directly states the semantic value. |
| `DERIVED` | The value follows mechanically from explicit structure without substantive interpretive judgment. |
| `INFERRED` | A competent reader/model can reasonably infer the value, but the source does not establish it uniquely or normatively. |
| `UNAVAILABLE` | The value cannot be established from the available source or author intent. |
| `AUTHOR_JUDGMENT` | The ATS authoring process intentionally introduces a new judgment, recommendation, design choice, or requirement under the authority granted for new authoring. Distinct from extracting source truth. |

The enum is schema-enforced — a basis outside the five fails validation. When the document
sets `basis_policy.declared: true`, `IR-BASIS-SCHEMA` requires every material claim to
carry a basis. `AUTHOR_JUDGMENT` requires the task to have granted authoring authority
(Step 2, item 5); without it, use one of the four extraction bases or `UNAVAILABLE`.

**Preserve stable semantic coordinates exactly (§4.23, `ATS-COORD-001/002`).** A stable
semantic coordinate is a machine-stable identifier whose loss can break joins among
specification, planning, task decomposition, acceptance criteria, implementation, tests,
review, receipts, postmortems, and later amendments. The protected kinds are
`requirement_id`, `decision_id`, `acceptance_criterion_id`, `work_item_id`, `protocol_id`,
`protocol_version`, `dependency_target`, and `explicit cross-document authority
reference`. Declare them in the document-level `stable_coordinates` block
(`{kind, id, source_pointer}`) and use them verbatim wherever the object appears. Under a
transformation, a coordinate MUST survive unchanged even when its proposition remains
recoverable through another coordinate (§7.17–§7.19): semantic equivalence does not imply
coordinate equivalence when units have different authority, lifecycle, dependency,
execution, verification, or evidence roles. Never rename, renumber, or re-case an
authority-assigned coordinate, and never mint a `requirement_id`/`decision_id`/
`acceptance_criterion_id` the source did not assign.

**Produce locally closed units (§4.24, `ATS-CLOSE-001`).** A unit is locally closed when
its operative meaning is recoverable from the unit plus explicitly declared dependencies
without requiring undeclared document-wide inference. For each extractable normative unit,
recovery SHOULD include, where applicable: stable identity, actor, modality, action,
object, condition or trigger, scope, exception, quantitative boundary, dependency, proof
obligation, acceptance criterion, and rationale/evidence reference. Explicit enclosing
scope MAY provide values; extraction MUST remain reliable — not every field must appear in
every sentence, but a value a reader needs MUST be present in the unit or in a dependency
the unit names. `ATS-CLOSE-001` mechanically checks the SPECIFY minima (actor,
modality/deontic, action, object, and resolving refs).

**Do not optimize primarily for brevity, elegance, or removal of repetition.** The draft.2
mission (D-A) makes semantic recovery cost — not word count — the governing objective, and
locality-preserving redundancy is permitted and often preferred (§11.3.3 D-E,
`ATS-DISC-003`). Restatement that adds stable identity, standalone extraction, task or
acceptance-criterion generation, review, receipt linkage, or retrieval locality is not
functionless repetition. Protected relations (§11.3.2 P1, `ATS-PRES-003`) must never be
removed, weakened, strengthened, reversed, or made materially implicit to shorten the
document; surface compression is permitted, semantic-relational compression is not.

**Never promote `INFERRED`/`UNAVAILABLE` source material to an explicit
source-authoritative fact (§7.19, `ATS-BASIS-002`).** A transformation MUST NOT silently
convert an inferred or unavailable value into an explicit semantic fact. Material axes
include authority, authority precedence, deontic force, acceptance/settlement state,
likelihood, confidence, quantifier, polarity, causal force, normative dependency, exception
removal, and source attribution. The compiler MAY preserve the value as `INFERRED`,
represent it as unresolved, omit it when nonessential, propose a candidate interpretation,
or ask for adjudication — it MUST NOT pretend the source declared it.

### Step 7 — Construct evidence objects (§7.9, §7.10, §9.2.6)

Required: `evidence_id`, `proposition`, `source`, `availability`. `source` is a
`source_ref` requiring `source_id`, `source_type`, `availability`; when
`source.availability == "present"` the schema additionally requires `locator` **or**
`content_sha256`.

- Use the exact availability state (§7.9). `not_found` asserts that a bounded search was
  performed and MUST carry `search_scope` or a reference to the search receipt. §7.8
  forbids collapsing "no search", "search found none", "evidence unavailable", "evidence
  against", and "evidence for the negation" into one state.
- §7.10 / §9.2.6: a model output without an inspectable basis is `source_type:
  model_output`, never independent evidence. A model's analysis of evidence is an
  `inference` or `judgment` claim, not a second evidence line.
- §10.12: record `observed_at` and `revision` when the claim depends on mutable facts.

### Step 8 — Construct typed relations (§7.11)

§7.11: a material relationship among claims or evidence MUST use a typed relation when a
structured representation is produced. Required: `relation_id`, `source_id`, `type`,
`target_id`, `material`. The nineteen types are listed in `references/vocabularies.md` §7.

- Relations are **directional**. `source_id` is the thing doing the supporting,
  qualifying, or conditioning; `target_id` is the claim affected. Never reverse it (§7.11).
- `basis_refs` is required in practice for the discriminating and causal types
  (`supports`, `strongly_supports`, `causes`, `necessary_for`, `sufficient_for`,
  `contributes_to`, `predicts`) — `ATS-EVID-002` fails a material relation of those types
  with empty `basis_refs`, and §8.15 requires a material causal claim to state or reference
  its basis.
- Every endpoint MUST resolve to a real object in the document: `IR-REFS` and
  `IR-EVIDENCE-ENDPOINTS` check this.
- A material `judgment` needs either a `contradicts` / `alternative_to` /
  `contrasts_with` relation aimed at it, or an explicit
  `assessment_confidence.basis.contrary_evidence` state (§9.2.7, §9.2.8,
  `ATS-EVID-003`).

### Step 9 — Assumptions, boundaries, exceptions (§7.12, §7.13)

- An assumption is `role: assumption`. §7.12 requires what is assumed, why it is needed,
  which claims depend on it, the consequence if false, and an update indicator or test when
  one is available. Encode the dependency as `condition_for` or `depends_on`, and list the
  assumption in the dependent claim's `assumption_refs`. §7.12: an assumption MUST NOT be
  rendered as an observation or established fact.
- A boundary (`role: boundary`) says where a claim stops applying; an exception
  (`role: exception`) says what defeats a claim that otherwise applies (§7.13). Attach with
  `boundary_refs` / `exception_refs` and a `qualifies` / `exception_to` relation.
- §7.13: a generic caveat such as "results may vary" does not satisfy a boundary
  obligation unless it identifies a discriminating condition. If the source only offers a
  generic caveat, that is a missing material slot, not a boundary — record it as an
  extraction issue.

### Step 10 — Update indicators (§7.14)

Required: `indicator_id`, `text`, `target_claim_refs` (≥1). Add `observation_condition` and
`effect` (seven-value enum) when the source supports them.

Every material `judgment` or `forecast` claim must be targeted by at least one update
indicator, or an `extraction_issues` entry must name the missing field as unavailable —
`IR-UPDATE-INDICATORS` and `ATS-EPI-006` both check this, and §9.2.2 lists update
indicators as a required document-level slot.

§7.14: an update indicator SHOULD be operational enough that a reviewer can determine
whether it occurred. "Monitor the situation" is not an update indicator.

### Step 11 — Glossary (§10.3, §10.2)

A `glossary_entry` requires `concept_id`, `canonical_term`, `definition`, `scope`. Add
`approved_abbreviations`, `deprecated_aliases`, `audience`, `external_ids`.

The glossary is the **only** legitimate source of artifact-specific term rules:
`ATS-TERM-001` matches deprecated aliases from it, `ATS-TERM-003` permits acronyms listed
in `approved_abbreviations`, and `IR-GLOSSARY-REFS` resolves references into it. Do not
invent entries to silence a check; add an entry only when the source or the author
actually defines the term.

### Step 12 — Surface ambiguity rather than resolving it conveniently

This is the step that most often gets skipped, and it is the point of the standard.

1. **Material ambiguity in a single claim** → set `claim.status: "ambiguous"` and populate
   `claim.interpretations` with **at least two** materially distinct readings (the schema
   enforces `minItems: 2`; §7.5 requires it, and `ATS-EPI`/`IR-EXTRACTION-STATUS` and the
   `ambiguous_without_distinct_readings` fixture defend it). §13.4 shows the shape: one
   reading per materially distinct force or scope.
2. **An open question the source leaves unresolved** → `role: open_question` with
   `status: "unresolved"`, not a judgment with a hedge.
3. **Document-level extraction state** → `extraction_status` is one of `complete`,
   `partial`, `ambiguous`, `unavailable` (§7.16). Choose it by what actually happened:

   | situation | `extraction_status` | also required |
   |---|---|---|
   | every applicable slot resolved from the source | `complete` | — |
   | a material slot exists in the source but could not be fully extracted | `partial` | an `extraction_issues` entry with `status: partial`, `affected_fields`, and `span` |
   | a material reading could not be settled | `ambiguous` | an `extraction_issues` entry with `status: ambiguous` and `candidate_interpretations` |
   | the source could not be read, or a required input was absent | `unavailable` | an `extraction_issues` entry with `status: unavailable` naming the missing input |

4. §7.16: a partial or ambiguous extraction MUST identify affected spans and fields, and
   **MUST NOT fill missing semantic slots with likely values without marking them as
   inferred candidates.**
5. **Escalate only action-blocking gaps, in ladder order** (draft.2 D-I). Prefer typed
   insufficiency over invented completion: an unresolved semantic that is not
   action-blocking stays recorded as `UNAVAILABLE` and is never guessed. For a genuinely
   action-blocking unresolved semantic, escalate in this order — (a) deterministically
   recover from the source or explicit structure; (b) evidence-based adjudication
   from the available reasoning state, resolving to `AUTHOR_JUDGMENT` or
   `UNAVAILABLE`; (c) remain `UNAVAILABLE` and continue with the typed insufficiency
   recorded. Only a product-authority distinction that no evidence tier can settle reaches
   the human operator. Absence is never silently converted into a value (§7.19).

Worked shapes already in the repository:
`fixtures/ir/valid/assess_partial_extraction.json` (partial, with `affected_fields`) and
`fixtures/ir/valid/assess_represented_ambiguity.json` (ambiguous, with a two-reading
`interpretations` array and matching `candidate_interpretations`).

> **STOP** and choose the typed state whenever you are about to pick "the reading that
> makes the document lint cleanly". A convenient reading that the source does not support
> is the specific failure mode §20.1 calls misleading fluency and §20.6 forbids.

### Step 13 — Serialize canonically (Appendix C)

Serialize with RFC 8785 JCS and hash the canonical bytes with SHA-256, lowercase hex.

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli ir canonicalize path/to/ir.json --out path/to/ir.json
```

`ats ir canonicalize` rewrites the file as canonical bytes and prints the digest;
`IR-CANONICAL` verifies that a replay of the canonicalization reproduces the same content
address. The `ir_sha256` a downstream trace binds is SHA-256 over exactly these bytes.

### Step 14 — Validate, then lint, before returning anything

```bash
cd <ats-repo>

# schema only — fast structural gate
PYTHONPATH=src .venv/bin/python -m ats.cli ir validate path/to/ir.json

# the real gate: 27 structural checks (26 draft.1 + IR-BASIS-SCHEMA) + all 36 rule
# detectors (30 carried + ATS-COORD-001/002, ATS-BASIS-001/002, ATS-PRES-003,
# ATS-CLOSE-001 — §12.7.5), bound to the policy
PYTHONPATH=src .venv/bin/python -m ats.cli \
  --now 2026-08-03T00:00:00Z --format text \
  ir lint path/to/ir.json \
  --policy path/to/policy.json \
  --source path/to/source.txt \
  --out path/to/ir.lint.json
```

- `--source` makes `IR-SOURCE-HASH` compare your declared `content_sha256` and
  `normalized_sha256` against the real file. **Always pass it** when the source is a file;
  without it that check cannot execute.
- `--now` pins evaluation time so exception expiry and the report are reproducible
  (§16.2). Never omit it in a receipted run.
- `--out` writes the sealed `ats.ir_lint_report.v1`, which is the validation result you
  return.

Exit codes: `0` clean · `1` a FAIL in some conformance dimension · `2` usage error ·
`3` unsupported capability · `4` a required check is `UNAVAILABLE` in `mechanical`,
`profile`, or `preservation`.

**The exit code is not the whole answer.** Read the report:

| field | what to do |
|---|---|
| `conformance.mechanical` | must be `PASS`; `FAIL` means a required deterministic check failed |
| `conformance.profile` | must be `PASS`; `FAIL` means a material profile slot is missing (§9.2.13, §9.3.20) |
| `conformance.semantic_review` | always `UNAVAILABLE` here; this is correct, not a defect (§15.3, §14.11) |
| `conformance.forecast_calibration` | always `INSUFFICIENT_EVIDENCE` here (§15.5) |
| `summary.required_failed` | must be `0` |
| `summary.required_unavailable` | must be `0`; each one names an input you did not supply |
| `structural_checks[]` | 27 `IR-*` checks (26 draft.1 + `IR-BASIS-SCHEMA`); read every non-`PASS` detail |
| `rule_results[]` | 36 `ATS-*` rules (30 carried + the six draft.2 rules, §12.7.5); `REVIEW_REQUIRED` is honest and expected — a detector that recognises only a subset of violations never reports `PASS` from absence (§5.4, §16.5) |

Deterministic lint before completion is required by the draft.2 workflow: run
`ats ir lint` with `--source` and `--now`, and treat a non-green
`mechanical`/`profile` run as a non-completion.

Explain any rule you do not recognise:

```bash
PYTHONPATH=src .venv/bin/python -m ats.cli ir explain-finding ATS-EPI-002
PYTHONPATH=src .venv/bin/python -m ats.cli ir explain-finding <finding_id> --report path/to/ir.lint.json
```

> **STOP** and do not return the IR while `conformance.mechanical` or
> `conformance.profile` is `FAIL`, or `summary.required_failed > 0`. Fix the IR — by
> correcting a mis-typed field or by recording an honest typed insufficiency — and lint
> again. Never suppress a check by weakening the policy or deleting a claim you actually
> extracted.

### Step 15 — Return

Hand back the three artifacts named at the top of this file. State the conformance vector
verbatim, including the `UNAVAILABLE` and `INSUFFICIENT_EVIDENCE` dimensions and why they
hold. §5.3 forbids a bare "ATS-1 compliant" claim; §5.2 forbids collapsing the vector into
one score.

### Draft.2 pivot checklist

Before returning, run the twelve-item pivot checklist. Every item is a binary check
against the artifact you built:

1. **Transformation or authoring?** The task class was decided (Step 2, item 5), and
   new-authoring content exists only under authority the task granted.
2. **Profile + artifact policy.** Policy snapshot resolved (§6.5) and fleet artifact class
   resolved via `ats policy resolve` before any extraction (D-G).
3. **Explicit source semantics preserved.** No protected relation dropped, weakened,
   strengthened, reversed, or made materially implicit (§11.3.2, `ATS-PRES-003`).
4. **Basis recorded where material.** Material claims/requirements carry one of the five
   §4.25 values; a declared basis is in the enum (`ATS-BASIS-001`).
5. **Author judgments only under authority.** Every `AUTHOR_JUDGMENT` traces to
   task-granted authoring authority.
6. **No inferred-as-fact.** No `INFERRED`/`UNAVAILABLE` value recorded as explicit source
   truth (§7.19, `ATS-BASIS-002`).
7. **Coordinates exact.** All eight coordinate kinds (§4.23) preserved verbatim, declared
   in `stable_coordinates`, no duplicates, refs resolve (`ATS-COORD-001/002`).
8. **Local closure.** Each extractable unit carries its recovery fields or names its
   dependencies (§4.24, `ATS-CLOSE-001`).
9. **Typed insufficiency.** Gaps are `UNAVAILABLE`/`partial`/`ambiguous` with
   `extraction_issues` entries, never filled with likely values (§7.16, §20.6).
10. **Asked the operator only for action-blocking semantics.** Escalation ladder followed;
    non-blocking unknowns stayed recorded and unresolved (D-I).
11. **IR fit for downstream decomposition.** `requirement_id`/`decision_id`/
    `acceptance_criterion_id`/`dependency_target` coordinates are resolvable so the
    planning projection and downstream planner can consume the IR without
    re-authoring (D-H, D-I).
12. **Lint before completion.** `ats ir lint` ran with `--source` and `--now`; the report
    is green on `mechanical` and `profile`, `summary.required_failed == 0`, and any
    `REVIEW_REQUIRED` findings are understood and reported.

---

## Refusal table

Every row is a hard stop. Emit the right-hand column and nothing more; never substitute a
best-effort IR.

| Condition | What to emit instead |
|---|---|
| No policy snapshot, or it cannot be resolved | No IR. Report the missing snapshot and that §14.3 requires failing closed for required conformance claims. |
| Policy snapshot `spec_version` differs from the imported package | No IR. Report both versions; §15.8 makes the conformance claim stale by construction. |
| Policy declares a profile this build does not support | No IR. Report the profile identifier verbatim (§9.5 forbids treating it as `ASSESS`/`SPECIFY` by similarity). Exit code 3 territory. |
| Source bytes unavailable, or hash mismatch against what you were given | No IR. Report the expected and actual digests (§20.5). |
| Source unreadable or unparseable | IR with `extraction_status: "unavailable"` and an `extraction_issues` entry naming the failed region (§14.4 forbids silently running token-only rules and reporting conformance). |
| A material slot exists in the source but cannot be fully extracted | IR with `extraction_status: "partial"` and an `extraction_issues` entry with `status: partial`, `affected_fields`, and `span`. Never fill the slot with a likely value (§7.16). |
| A material reading cannot be settled from the source | IR with `extraction_status: "ambiguous"`, the claim's `status: "ambiguous"`, and ≥2 entries in `interpretations`; plus an `extraction_issues` entry with `candidate_interpretations` (§7.5, §13.4). |
| The source states a judgment but no probability | Claim with no `likelihood` field. Never infer a band. If the profile requires likelihood because the proposition is probabilistic, that is a `partial` extraction with the field named in `affected_fields` (§9.2.4). |
| The source states a judgment but no confidence | Claim with no `assessment_confidence`. Never manufacture a level or a nine-dimension basis (§8.9). Record the gap. |
| The source asserts causation with no basis | `force.causal` set to the level the source actually supports — `associated_with` or `predicts` if that is all the basis carries — plus a relation whose `basis_refs` name the real basis, or an extraction issue. Never upgrade to `causes` (§8.13, §8.15, §11.6). |
| A required evidence object does not exist | Evidence object with the exact availability state (`not_found` with `search_scope`, `not_searched`, `unavailable`, `withheld`, `not_applicable`) — or no evidence object and a named gap. Never invent one (§11.7, §7.8). |
| A requirement's applicable slot is unknown | `requirement` slot literally marked unknown, which §9.3.2 says prevents profile conformance and `ATS-REQ-003` reports. Never guess an actor, threshold, or acceptance criterion (§9.3.10). |
| Two source objects carry the same authority identifier | `extraction_status: "ambiguous"` with both spans and both readings. Never suffix or rename one (§9.3.18). |
| A capability statement is offered as a requirement | `force.deontic: CAN` on a non-`requirement` claim. §9.3.13: a capability statement MUST NOT satisfy a required-behavior slot. |
| A bare "may" / "should" / "will" / "confidence" carries material force | The disambiguated form the author intended, if the author states it; otherwise `status: "ambiguous"` with one interpretation per collision reading (§8.17 and the four `collision_rules`). |
| The source uses `SHALL` / `SHALL NOT` | Keep the source proposition exact if it is quoted material (`content_class: quotation` downstream); otherwise record it as a deontic ambiguity. Never silently rewrite it to `MUST` — that changes deontic force, a P0 field (§8.16, §8.18). |
| Asked to make the IR "lint clean" by dropping an extracted claim or weakening the policy | Refuse, and say why: §7.15 forbids demoting an explicitly material item without adjudication, and §16.5 forbids treating detector silence as conformance. |
| Asked to declare the artifact conformant or accepted | Refuse. Return the lint report. §14.11 and §15.3 assign semantic acceptance to an authorized human or an explicitly governed external acceptance system; this workflow is not one. |

---

## Invariants

1. Never emit a claim, evidence object, relation, or slot value the source or an explicit
   author instruction does not support (§11.7).
2. Never strengthen (§11.6, nine named moves), never infer an unstated probability, never
   manufacture a confidence level or basis (§8.9).
3. Never collapse two force axes into one field (§8.1, §8.11).
4. Never omit a scope field in a way that implies universal scope (§7.6).
5. Never reverse a relation's direction (§7.11).
6. Never replace the source hash with a normalized hash (Appendix C, §14.2).
7. Never fill a missing slot with a likely value instead of a typed insufficiency
   (§7.16, §20.6).
8. Never claim conformance, acceptance, or a scalar score (§5.2, §5.3, §14.11).

# ATS Mutation Catalog V0

Status: repository protocol, version 0, for ATS-1 `1.0.0-draft.1`.
Machine-readable counterpart: `corpus/operators/ats_mutation_operators_v1.yaml`, validated by
`schemas/ats_mutation_operator_v1.schema.json`.
Registry version documented here: `1.0.0`. `ats_version`: `1.0.0-draft.1`.

## 0. How to read this document

### 0.1 Normative language

ATS-1 §1.3 applies: **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** carry normative
force only in uppercase. `CAN` and `CANNOT` state capability. Obligations are identified `MC-n`;
a retired identifier MUST NOT be reused.

**Reference convention.** `ATS-1 §n`, and a bare `§n` inside a grounding note or parenthetical,
name a section of `ATS-1_SPEC.md`. A reference to a section of this document is always written
`this document §n`. Other protocol documents are referenced by filename.

### 0.2 Authority of an obligation

As in `ATS_CORPUS_PROTOCOL_V0.md` §0.2: each obligation is tagged in this document §5 as **ATS-1 normative**,
**ATS-1 raised** (a §17.5 `SHOULD` raised to a repository `MUST`), **Repo schema**, or
**Repository policy**. An obligation marked **Repository policy** MUST NOT be cited as an ATS-1
conformance requirement.

### 0.3 What a mutation is for

A mutation produces a *paired* example: an unmodified source and a derived example differing in one
intended semantic feature. The pair exists so that a detector's behavior CAN be attributed to that
feature rather than to unrelated surface variation.

**MC-1.** Synthetic mutations MUST change one semantic feature at a time (ATS-1 §17.5, raised).

**MC-2.** Synthetic examples MUST be tagged, and MUST NOT be counted as independent real-world
evidence of rule prevalence or user value (ATS-1 §17.5). A metric described as measuring natural
prevalence, reviewer burden, accepted-finding rate, or downstream value MUST exclude synthetic
examples, or report them as a separate stratum.

**MC-3.** A rule MUST NOT be promoted to `required` based only on synthetic violations
(ATS-1 §12.9).

**MC-4.** Semantic mutations MUST NOT be implemented through uncontrolled model generation in v0. An
operator that cannot be performed safely and deterministically MUST be specified with
`supported: false` and an `unsupported_reason`, rather than implemented through free-form generation.

---

## 1. Operator contract

Every operator record MUST carry the following fields. The list is exactly the `required` array of
`#/$defs/operator` in `schemas/ats_mutation_operator_v1.schema.json`; `additionalProperties` is
`false`, so no other field MAY appear.

| Field | Type / vocabulary | Meaning |
|---|---|---|
| `operator_id` | string, `^ATS-MUT-[A-Z0-9-]+$` | stable operator identity |
| `operator_version` | non-empty string | operator definition version |
| `title` | non-empty string | human-readable name |
| `applicable_profiles` | array ≥ 1, unique, `ats_common_v1#/$defs/profile` | profiles the operator may be applied under |
| `target_rule_ids` | array ≥ 1, unique, `^ATS-[A-Z]+-[0-9]{3}$` | the rules the mutation is built to exercise |
| `preconditions` | array ≥ 1 of non-empty strings | conditions the source must satisfy before application |
| `transformation` | object | the exact edit (see §1.1) |
| `expected_label` | one of the seven ATS-1 §17.3 labels | the label the derived example is expected to receive |
| `expected_protected_impact` | array ≥ 1, unique, over `P0`,`P1`,`P2` | the preservation classes the mutation disturbs |
| `deterministic` | boolean | whether the edit is a pure function of the source and operator parameters |
| `invertible` | boolean | whether the source CAN be recovered from the derived example plus the recorded transformation |
| `required_context` | array of non-empty strings | context an annotator needs in order to adjudicate the derived example |
| `exclusions` | array of non-empty strings | source shapes to which the operator MUST NOT be applied |
| `hard_negative_pair_required` | boolean | whether a matched hard negative MUST accompany the mutation |
| `split_group_policy` | `inherit_source` \| `inherit_source_and_operator` | leakage grouping of the derived example |
| `supported` | boolean | whether v0 implements the operator |

Optional fields: `expected_delta_classes` (unique array over the 21 `semantic_delta` types of
`ats_common_v1#/$defs/semantic_delta`, ATS-1 §11.5); `hard_negative_classes` (array of strings, the
`HN-n` classes of `ATS_CORPUS_PROTOCOL_V0.md` §6); `unsupported_reason` (non-empty string);
`spec_refs` (array ≥ 1 of non-empty strings).

Registry-level required fields: `schema_version` (const `ats.mutation_operator.v1`),
`registry_version`, `ats_version`, `operators` (array ≥ 1).

Schema-enforced conditionals:

- `supported: false` requires `unsupported_reason`.
- `supported: true` requires `deterministic: true`.

**MC-5.** An operator MUST declare all sixteen required fields. A registry entry missing any of them
MUST NOT be loaded.

**MC-6.** `split_group_policy` MUST be `inherit_source` or `inherit_source_and_operator`. Both keep
the derived example in its source's split group; `inherit_source_and_operator` additionally binds the
group to the operator family so that a mutation-disjoint evaluation partition CAN be constructed
(ATS-1 §17.7, `ATS_SPLIT_POLICY_V0.md`).

### 1.1 `transformation`

`transformation` requires `kind` and `description`, and MAY carry `target_pointer`,
`replacement_source`, and `literal`.

`kind` ∈ `ir_field_delete`, `ir_field_replace`, `ir_field_swap`, `ir_relation_reverse`,
`ir_relation_delete`, `ir_claim_role_change`, `ir_claim_merge`, `ir_claim_reorder`,
`ir_claim_insert`, `text_span_delete`, `text_span_replace`.

`replacement_source` ∈ `force_lexicon`, `literal`, `adjacent_band`, `sibling_field`, `none`.

**MC-7.** A replacement value MUST come from a declared `replacement_source`. It MUST NEVER be a
free-form model completion. `force_lexicon` means `lexicons/ats_force_lexicon_v1.yaml` in the
normative package; `literal` means a string quoted in this catalog and in the registry;
`adjacent_band` means the neighbouring WEP interval in the lexicon ordering; `sibling_field` means a
value already present elsewhere in the same source object.

**MC-8.** `target_pointer` MUST be a JSON Pointer template into the `TextIR` object the operator
edits, so the edit site is recoverable from the record alone.

### 1.2 Determinism, IR level, and text realization

**MC-9.** Every supported operator edits the `TextIR` object, not free prose. An operator whose
intended feature cannot be realized in the derived artifact's *text* by a deterministic rule MUST
declare, in `exclusions`, that its output is admissible as a preservation IR pair only, and MUST NOT
be presented as naturally occurring prose. In v0 this applies to `ATS-MUT-NEGATION-FLIP` and
`ATS-MUT-QUANTIFIER-WIDEN`.

**MC-10.** A supported operator MUST be a pure function of (source IR, operator parameters). Applying
it twice to the same source MUST yield byte-identical output under RFC 8785 canonical serialization
(ATS-1 §16.2, Appendix C).

**MC-11.** An operator MUST NOT produce an IR that fails `ats_text_ir_v1.schema.json`. An edit that
would violate the schema — for example deleting `requirement.actor`, whose `minLength` is 1 — MUST be
expressed as a replacement with a spec-quoted literal instead of a deletion.

### 1.3 The five per-mutation obligations

**MC-12.** Each generated mutation MUST:

1. change one intended semantic feature (MC-1);
2. preserve the original example, unmodified and separately stored;
3. record the exact transformation applied, including `operator_id`, `operator_version`, and the
   resolved `target_pointer`;
4. record source and output hashes; and
5. record the expected rule impact (`target_rule_ids`, `expected_label`,
   `expected_protected_impact`).

**MC-13.** In addition, each generated mutation MUST validate against its schema and MUST remain
paired with its source: the derived `TextExampleV1` carries `provenance: synthetic_mutation`,
`synthetic: true`, `mutation_operator` naming the operator, and the same `split_group` as its source
(ATS-1 §17.7).

**MC-14.** A mutation whose `hard_negative_pair_required` is `true` MUST NOT be admitted to
evaluation data without at least one accompanying hard negative from the operator's
`hard_negative_classes`. The pair exists so that a detector cannot score on the mutation by keying on
the surface cue alone (ATS-1 §17.6, §18.4).

---

## 2. Catalog

Twenty-two operators. Each `operator_version` is `1.0.0`. `applicable_profiles` names the profiles in
which the target rules have a non-`disabled` default state.

Legend for the per-operator rows: **Changes** is the semantic feature; **Impact** is
`expected_protected_impact` grounded in ATS-1 §11.3.1 (P0), §11.3.2 (P1), §11.3.3 (P2); **Det.** is
`deterministic`; **Inv.** is `invertible`; **HN pair** is `hard_negative_pair_required`; **Split** is
`split_group_policy`; **v0** is `supported`.

### 2.1 `ATS-MUT-QUAL-DELETE` — Delete a qualification

| Field | Value |
|---|---|
| Title | Delete a qualification relation |
| Profiles | `ASSESS`, `SPECIFY`, `TRANSFORM` |
| Changes | removes the material `qualifies` relation that narrows a claim |
| Target rules | `ATS-PRES-002`, `ATS-EVID-002` |
| Transformation | `ir_relation_delete`, `target_pointer` `/relations/{i}`, `replacement_source` `none` |
| Preconditions | the relation's `type` is `qualifies`; `material` is `true`; both endpoints resolve to stored claims; the qualified claim remains material after deletion |
| Expected label | `violation` |
| Impact | `P1` — qualification is a P1 relation (§11.3.2) |
| Delta classes | `omitted`, `relation_changed` |
| Det. / Inv. | true / true (the deleted relation object is retained in the pair record) |
| Required context | the qualified claim; the qualifying claim; the section heading path |
| Exclusions | MUST NOT delete a `scope` field: removing a scope condition changes a P0 condition, is a different semantic feature, and no v0 operator covers it. MUST NOT be applied when the qualification is restated by another retained relation. |
| HN pair | true — `HN-10` (authorized omission under a retention contract) |
| Split | `inherit_source` |
| v0 | supported |

### 2.2 `ATS-MUT-WEP-BAND-SHIFT` — Move a canonical WEP to an adjacent band

| Field | Value |
|---|---|
| Title | Shift a WEP term to the adjacent band |
| Profiles | `ASSESS`, `TRANSFORM` |
| Changes | replaces `likelihood.term` with the adjacent canonical term in the lexicon ordering, leaving `lower`, `upper`, and `display` at the source band |
| Target rules | `ATS-EPI-001`, `ATS-PRES-001` |
| Transformation | `ir_field_replace`, `target_pointer` `/claims/{i}/force/likelihood/term`, `replacement_source` `adjacent_band` |
| Preconditions | `likelihood.kind` is `wep`; `term` is one of the seven canonical terms; `lower` and `upper` exactly equal the lexicon interval for `term` before the edit; the claim is material |
| Expected label | `violation` |
| Impact | `P0` — probability points and bands are P0 (§11.3.1) |
| Delta classes | `likelihood_changed`, `strengthened` |
| Det. / Inv. | true / true |
| Required context | the lexicon band table (`lexicons/ats_force_lexicon_v1.yaml`); the source band |
| Exclusions | MUST NOT be applied when `term` is at an end of the ordering in the shift direction. MUST NOT shift `term` and the interval together: that variant is preservation-only and leaves `ATS-EPI-001` passing. |
| HN pair | true — a claim whose band was changed by an authorized semantic change under §11.4 |
| Split | `inherit_source_and_operator` |
| v0 | supported |

The mismatch between the shifted `term` and the retained interval is the `ATS-EPI-001` violation
(§8.2, §8.5). The retained `display` will also disagree with the new term; that is a consequence of
the same single feature change, not a second mutation.

### 2.3 `ATS-MUT-WEP-RANGE-STRIP` — Remove the inline WEP range

| Field | Value |
|---|---|
| Title | Remove the first-use inline numeric range |
| Profiles | `ASSESS`, `TRANSFORM` |
| Changes | sets `likelihood.range_shown_inline` to `false` and sets `display` to the canonical phrase without its numeric range |
| Target rules | `ATS-EPI-002` |
| Transformation | `ir_field_replace`, `target_pointer` `/claims/{i}/force/likelihood/range_shown_inline`, `replacement_source` `literal`, `literal` `false` |
| Preconditions | `likelihood.kind` is `wep`; `range_shown_inline` is `true`; the claim is the first material WEP use in its section; `display` contains the lexicon `display_range` for `term` |
| Expected label | `violation` |
| Impact | `P0`, `P2` — matching the `ATS-EPI-002` `protected_impact` in `rules/ats_rules_v1.yaml` |
| Delta classes | `omitted` |
| Det. / Inv. | true / true |
| Required context | section boundaries, so that "first material use in a section" (§8.4) CAN be decided; the lexicon `display_range` |
| Exclusions | MUST NOT be applied to a subsequent local use in the same section: §8.4 permits those to omit the range. |
| HN pair | true — a later WEP use in the same section that legitimately omits the range |
| Split | `inherit_source_and_operator` |
| v0 | supported |

### 2.4 `ATS-MUT-LIKELIHOOD-CONFIDENCE-SWAP` — Exchange likelihood and confidence

| Field | Value |
|---|---|
| Title | Exchange the likelihood and assessment-confidence fields |
| Profiles | `ASSESS`, `TRANSFORM` |
| Changes | replaces `likelihood.display` with the claim's `assessment_confidence.level` word, so the probability is expressed as a confidence and the two are no longer distinct |
| Target rules | `ATS-EPI-004` |
| Transformation | `ir_field_swap`, `target_pointer` `/claims/{i}/force`, `replacement_source` `sibling_field` |
| Preconditions | the claim carries both a `likelihood` of kind `wep`, `point`, or `interval` and an `assessment_confidence`; the claim is material; the claim's role is `judgment` or `forecast` |
| Expected label | `violation` |
| Impact | `P0`, `P1` — assessment-confidence level and probability band are P0; inference provenance is P1 |
| Delta classes | `likelihood_changed`, `confidence_changed` |
| Det. / Inv. | true / true |
| Required context | both source values, so the annotator CAN see which was which |
| Exclusions | MUST NOT be applied when the claim carries no `assessment_confidence`: there is then nothing to exchange and the result would be an invented value. |
| HN pair | true — a claim that states a likelihood and a confidence in adjacent labeled sentences, which §8.11 permits |
| Split | `inherit_source_and_operator` |
| v0 | supported |

Grounding: ATS-1 §4.8 separates assessment confidence from probability of occurrence; §8.11 requires
likelihood and confidence to be distinct fields or labeled sentences.

### 2.5 `ATS-MUT-DEONTIC-EXCHANGE` — Exchange `MAY`, `CAN`, `SHOULD`, and `MUST`

| Field | Value |
|---|---|
| Title | Exchange deontic force |
| Profiles | `SPECIFY`, `TRANSFORM` |
| Changes | replaces `force.deontic` with another member of the closed §8.16 vocabulary while the proposition retains the original surface verbatim |
| Target rules | `ATS-DEON-001`, `ATS-DEON-002`, `ATS-DEON-003`, `ATS-PRES-001` |
| Transformation | `ir_field_replace`, `target_pointer` `/claims/{i}/force/deontic`, `replacement_source` `force_lexicon` |
| Preconditions | `force.deontic` is present; the claim is material; the proposition contains the lexicon surface for the source value verbatim |
| Expected label | `violation` |
| Impact | `P0` — deontic force is P0 (§11.3.1) |
| Delta classes | `deontic_force_changed`, `strengthened` or `weakened` |
| Det. / Inv. | true / true |
| Required context | the proposition text, so the surface/field mismatch is visible; any override policy referenced by a `SHOULD` |
| Exclusions | `CAN` and `CANNOT` are admissible only on non-requirement claims: `requirement_slots.deontic` has no `CAN`, so a requirement-role exchange MUST stay inside `MUST`, `MUST_NOT`, `SHOULD`, `SHOULD_NOT`, `MAY` and MUST mirror `force.deontic` into `requirement.deontic`. MUST NOT be applied to `REQUIRED_BY`, which requires `external_authority`. MUST NOT be applied to a `may` inside a quotation (`HN-6`). |
| HN pair | true — `HN-6`, `HN-7` |
| Split | `inherit_source_and_operator` |
| v0 | supported |

Which target rule fires depends on the substituted value: `MAY` on a claim that also carries a
likelihood or has role `forecast` triggers the §8.17 `force-collision-may` rule `ATS-DEON-002`;
`SHOULD` without exceptions or rationale triggers `ATS-DEON-003` (§9.3.11); any surface/field
mismatch triggers `ATS-DEON-001` (§8.16).

### 2.6 `ATS-MUT-ACTOR-REMOVE` — Remove an explicit actor

| Field | Value |
|---|---|
| Title | Conceal the responsible actor |
| Profiles | `SPECIFY`, `TRANSFORM` |
| Changes | replaces `requirement.actor` with a concealing form the specification itself names nonconforming |
| Target rules | `ATS-REQ-001`, `ATS-PRES-001` |
| Transformation | `ir_field_replace`, `target_pointer` `/claims/{i}/requirement/actor`, `replacement_source` `literal`, `literal` `the system` |
| Preconditions | the claim's `role` is `requirement`; `material` is `true`; `requirement.actor` names a specific component; no enclosing requirement block mechanically supplies the actor |
| Expected label | `violation` |
| Impact | `P0` — named entities and referent identity are P0 (§11.3.1) |
| Delta classes | `omitted`, `scope_changed` |
| Det. / Inv. | true / true |
| Required context | the enclosing requirement block, so that §9.3.4 actor inheritance CAN be checked |
| Exclusions | MUST NOT be applied when the actor is inherited from a mechanically unambiguous requirement block: that yields `HN-12`, not a violation. `requirement.actor` has `minLength: 1`, so the field MUST be replaced, never deleted. |
| HN pair | true — `HN-2`, `HN-12` |
| Split | `inherit_source` |
| v0 | supported |
| `spec_refs` | `ATS-1 9.3.4`, `ATS-1 21.4` |

The literal `the system` is quoted from the ATS-1 §21.4 nonconforming `SPECIFY` example ("The system
should normally reject stale receipts and log them quickly"), where ATS-1 lists `ATS-REQ-001` as an
expected finding because "the system" does not identify the responsible component. ATS-1 §9.3.4
supplies the pronoun form `it` in its own nonconforming example ("It MUST be rejected before
acceptance"). Both literals are spec-enumerated; this catalog MUST NOT introduce an invented
placeholder.

### 2.7 `ATS-MUT-OBLIGATION-MERGE` — Merge two obligations

| Field | Value |
|---|---|
| Title | Merge two requirements into one |
| Profiles | `SPECIFY`, `TRANSFORM` |
| Changes | merges two material requirement claims into one whose `action` is the source actions joined by the literal ` and `, and leaves `indivisible_actions_justification` unset |
| Target rules | `ATS-REQ-002` |
| Transformation | `ir_claim_merge`, `target_pointer` `/claims/{i}`, `replacement_source` `literal`, `literal` ` and ` |
| Preconditions | two material requirement claims in the same section share the same `actor` and the same `deontic`; each has its own `acceptance_criterion`; independently satisfying one action would not satisfy the other (§9.3.3) |
| Expected label | `violation` |
| Impact | `P0`, `P1` — matching the `ATS-REQ-002` `protected_impact`; requirement identifiers are P0 and ordering dependencies are P1 |
| Delta classes | `omitted`, `relation_changed`, `condition_changed` |
| Det. / Inv. | true / true (both source claims are retained) |
| Required context | both source requirements with their identifiers and acceptance criteria |
| Exclusions | MUST NOT merge two actions that are simultaneous parts of one indivisible behavior sharing one acceptance criterion (§9.3.3); such a merge is conforming when the indivisibility is documented. MUST NOT drop either source `requirement_id` silently: §9.3.18 governs requirement identity and supersession. |
| HN pair | true — a documented indivisible two-action requirement |
| Split | `inherit_source` |
| v0 | supported |

The joined form reproduces the shape of the §9.3.3 nonconforming example, "The verifier MUST reject
stale receipts and record an audit event."

### 2.8 `ATS-MUT-UNIT-STRIP` — Remove a unit or denominator

| Field | Value |
|---|---|
| Title | Remove the unit or denominator of a material number |
| Profiles | `ASSESS`, `SPECIFY`, `TRANSFORM` |
| Changes | deletes `quantifier.unit`, or `quantifier.denominator` on a `proportion` |
| Target rules | `ATS-NUM-001`, `ATS-PRES-001` |
| Transformation | `ir_field_delete`, `target_pointer` `/claims/{i}/quantifier/unit`, `replacement_source` `none` |
| Preconditions | `quantifier.kind` ∈ `exact_count`, `minimum`, `maximum`, `range`, `proportion`; the deleted field is present; `scope.unknown_fields` does not already declare the unit unknown; the claim is material |
| Expected label | `violation` |
| Impact | `P0` — numbers, units, signs, precision, and denominators are P0 (§11.3.1) |
| Delta classes | `omitted`, `quantifier_changed` |
| Det. / Inv. | true / true |
| Required context | the sentence containing the number; any table header or heading that supplies a unit |
| Exclusions | MUST NOT be applied when the number is an identifier rather than a quantity (`HN-8`). MUST NOT delete `denominator` from a `proportion` claim, because `ats_common_v1#/$defs/quantifier` conditionally requires it and the result would fail schema validation (MC-11); use the `unit` variant on `proportion` claims. MUST NOT be applied when a unit is supplied by an enclosing table header. |
| HN pair | true — `HN-8` |
| Split | `inherit_source` |
| v0 | supported |

### 2.9 `ATS-MUT-THRESHOLD-BOUNDARY-SHIFT` — Alter an inclusive or exclusive threshold

| Field | Value |
|---|---|
| Title | Remove the comparator or inclusivity declaration of a threshold |
| Profiles | `SPECIFY`, `ASSESS`, `TRANSFORM` |
| Changes | deletes the `requirement.constraints` entry that declares the comparator or inclusivity of a material threshold or range |
| Target rules | `ATS-NUM-002`, `ATS-PRES-001` |
| Transformation | `ir_field_delete`, `target_pointer` `/claims/{i}/requirement/constraints/{j}`, `replacement_source` `none` |
| Preconditions | `quantifier.kind` ∈ `minimum`, `maximum`, `range`; a `constraints` entry declares the comparator or inclusivity; the boundary is material; ordinary reading of the statement leaves the boundary ambiguous (§10.10) |
| Expected label | `violation` |
| Impact | `P0` — thresholds and comparator boundaries are P0 (§11.3.1) |
| Delta classes | `omitted`, `condition_changed` |
| Det. / Inv. | true / true |
| Required context | the threshold value and unit; the measurement window; the aggregation method when material (§9.3.8) |
| Exclusions | MUST NOT rewrite a numeral: changing a threshold *value* is a different feature and is not covered by any v0 operator. MUST NOT be applied when inclusivity is unambiguous from ordinary reading, which §10.10 does not require to be declared. |
| HN pair | true — a threshold whose inclusivity is unambiguous without declaration |
| Split | `inherit_source` |
| v0 | supported |

Deleting the declaration, rather than editing a numeral, is the deterministic form: it reproduces
exactly the `ATS-NUM-002` condition that a material `minimum`, `maximum`, or `range` carries no
declared comparator or inclusivity in `constraints` (§10.10, §9.3.8).

### 2.10 `ATS-MUT-NEGATION-FLIP` — Flip explicit negation

| Field | Value |
|---|---|
| Title | Flip claim polarity |
| Profiles | `TRANSFORM` |
| Changes | replaces `claim.polarity` (`positive` ↔ `negative`) |
| Target rules | `ATS-PRES-001`, `ATS-SCOPE-001` |
| Transformation | `ir_field_replace`, `target_pointer` `/claims/{i}/polarity`, `replacement_source` `literal` |
| Preconditions | the claim is material; `polarity` is present; the claim is part of a source/output IR pair used for preservation evaluation |
| Expected label | `violation` |
| Impact | `P0` — polarity and negation are P0 (§11.3.1) |
| Delta classes | `polarity_changed`, `contradicted` |
| Det. / Inv. | true / true |
| Required context | `source_ir`, `output_ir`; the retention contract when one governs the pair |
| Exclusions | **IR preservation pair only.** The mutant MUST NOT be presented as natural prose, because a deterministic text realization of the flip does not exist (MC-9); this operator MUST NOT rewrite the proposition text. MUST NOT be used to collapse the six polarity and evidence states ATS-1 §7.8 keeps distinct into a two-valued flip on a claim whose proposition is about evidence availability. |
| HN pair | true — a paired output whose polarity change is covered by an authorized semantic change under §11.4 |
| Split | `inherit_source_and_operator` |
| v0 | supported |

### 2.11 `ATS-MUT-QUANTIFIER-WIDEN` — Change `some` to `all`

| Field | Value |
|---|---|
| Title | Widen the quantifier |
| Profiles | `TRANSFORM`, `ASSESS` |
| Changes | replaces `quantifier.kind` `some` with `all` |
| Target rules | `ATS-PRES-001`, `ATS-SCOPE-001` |
| Transformation | `ir_field_replace`, `target_pointer` `/claims/{i}/quantifier/kind`, `replacement_source` `literal`, `literal` `all` |
| Preconditions | `quantifier.kind` is `some`; the claim is material; the widened reading is false or unsupported under the claim's stated scope |
| Expected label | `violation` |
| Impact | `P0` — quantifier kind and value are P0 (§11.3.1); §7.7 forbids silent movement among quantifier kinds during transformation |
| Delta classes | `quantifier_changed`, `strengthened`, `scope_changed` |
| Det. / Inv. | true / true |
| Required context | `source_ir`, `output_ir`; the claim's `scope.population`, so the widened reading CAN be evaluated |
| Exclusions | **IR preservation pair only** (MC-9); the mutant MUST NOT be presented as natural prose, because a deterministic text realization of the widening does not exist. MUST NOT be applied when `scope.population` is a closed set for which `some` and `all` coincide. |
| HN pair | true — a claim legitimately quantified `all` over a closed enumerated population |
| Split | `inherit_source_and_operator` |
| v0 | supported |

### 2.12 `ATS-MUT-RELATION-REVERSE` — Reverse a declared relation direction

| Field | Value |
|---|---|
| Title | Reverse a directional relation |
| Profiles | `TRANSFORM`, `ASSESS`, `SPECIFY` |
| Changes | swaps `source_id` and `target_id` of a material directional relation |
| Target rules | `ATS-PRES-002`, `ATS-EVID-002` |
| Transformation | `ir_relation_reverse`, `target_pointer` `/relations/{i}`, `replacement_source` `none` |
| Preconditions | `relation.material` is `true`; `type` is directional — `supports`, `strongly_supports`, `qualifies`, `depends_on`, `condition_for`, `exception_to`, `derived_from`, `predicts`, `contributes_to`, `causes`, `necessary_for`, `sufficient_for`, `updates`, `reverses`; both endpoints resolve |
| Expected label | `violation` |
| Impact | `P1` — causal direction and force, dependency, and inference provenance are P1 (§11.3.2) |
| Delta classes | `relation_changed`, `causal_force_changed`, `contradicted` |
| Det. / Inv. | true / true |
| Required context | both endpoint claims; the relation's `basis_refs` |
| Exclusions | MUST NOT be applied to symmetric or non-directional types — `consistent_with`, `associated_with`, `contrasts_with`, `alternative_to`, `contradicts` — where reversal is not a semantic change. |
| HN pair | true — a symmetric relation stated in either order |
| Split | `inherit_source_and_operator` |
| v0 | supported |

### 2.13 `ATS-MUT-CAUSAL-UPGRADE` — Replace association with causation

| Field | Value |
|---|---|
| Title | Upgrade association to causation |
| Profiles | `ASSESS`, `TRANSFORM` |
| Changes | replaces `force.causal` or a relation `type` of `associated_with` with `causes` |
| Target rules | `ATS-EVID-002`, `ATS-PRES-002` |
| Transformation | `ir_field_replace`, `target_pointer` `/claims/{i}/force/causal`, `replacement_source` `force_lexicon`, `literal` `causes` |
| Preconditions | the source value is `associated_with` or `predicts`; the claim or relation is material; the declared basis describes only an observational association |
| Expected label | `violation` |
| Impact | `P0`, `P1` — matching the `ATS-EVID-002` `protected_impact`; causal direction and force are P1 |
| Delta classes | `causal_force_changed`, `strengthened` |
| Det. / Inv. | true / true |
| Required context | the causal basis required by §8.15; the evidence objects referenced by `basis_refs` |
| Exclusions | MUST NOT be applied when the basis is a randomized intervention, quasi-experimental identification, controlled deterministic system behavior, mechanistic proof, or formal dependency (§8.15): the upgraded claim would then be supported, and the result is `HN-5`, not a violation. |
| HN pair | true — `HN-5` |
| Split | `inherit_source_and_operator` |
| v0 | supported |

Grounding: ATS-1 §8.13 names "an observational association described as establishing causality" as
an overclaim; §8.14 defines the causal ladder.

### 2.14 `ATS-MUT-EXCEPTION-DELETE` — Delete an exception

| Field | Value |
|---|---|
| Title | Delete a declared exception |
| Profiles | `SPECIFY`, `ASSESS`, `TRANSFORM` |
| Changes | deletes one entry from `requirement.exceptions`, or the `exception_refs` entry linking a claim to its exception claim |
| Target rules | `ATS-REQ-003`, `ATS-DEON-003`, `ATS-PRES-001` |
| Transformation | `ir_field_delete`, `target_pointer` `/claims/{i}/requirement/exceptions/{j}`, `replacement_source` `none` |
| Preconditions | the claim is material; the deleted entry states a condition under which the obligation does not apply; the exception is not restated elsewhere in the artifact |
| Expected label | `violation` |
| Impact | `P0` — conditions and exceptions are P0 (§11.3.1) |
| Delta classes | `exception_changed`, `omitted`, `strengthened`, `scope_changed` |
| Det. / Inv. | true / true |
| Required context | the full requirement including remaining exceptions; any override policy; the retention contract when the pair is a summary |
| Exclusions | MUST NOT be represented as an authorized omission: §11.8 states that a retention contract MUST NOT authorize removal of a condition, exception, or uncertainty marker that changes the interpretation of a retained claim. MUST NOT be applied to a `SHOULD` requirement whose `rationale` independently satisfies §9.3.11. |
| HN pair | true — a requirement with `exception: none` explicitly declared, as in the §21.3 conforming example |
| Split | `inherit_source` |
| v0 | supported |

### 2.15 `ATS-MUT-CONTRARY-EVIDENCE-DELETE` — Delete contrary-evidence linkage

| Field | Value |
|---|---|
| Title | Delete the contrary-evidence or live-alternative relation |
| Profiles | `ASSESS`, `TRANSFORM` |
| Changes | deletes a material relation of type `contradicts`, `alternative_to`, or `contrasts_with` targeting a material judgment |
| Target rules | `ATS-EVID-003`, `ATS-PRES-002` |
| Transformation | `ir_relation_delete`, `target_pointer` `/relations/{i}`, `replacement_source` `none` |
| Preconditions | the target claim's `role` is `judgment`; the target claim is material; the claim either carries no `assessment_confidence`, or its `basis.contrary_evidence` value is supported solely by the deleted relation; no other retained relation of those three types targets the claim |
| Expected label | `violation` |
| Impact | `P1` — support and contradiction, and alternative-hypothesis relationships, are P1 (§11.3.2) |
| Delta classes | `omitted`, `relation_changed`, `strengthened` |
| Det. / Inv. | true / true |
| Required context | the judgment claim; the contrary claim; the claim's `assessment_confidence.basis.contrary_evidence` value |
| Exclusions | MUST NOT be applied when the claim's `basis.contrary_evidence` is `addressed`, `none_found`, `not_searched`, or `not_applicable` independently of the deleted relation: `ATS-EVID-003` is then still satisfied and the result is a hard negative. MUST NOT also change the `contrary_evidence` enum value — that is a separate feature. |
| HN pair | true — a judgment whose contrary evidence is declared `none_found` after a described search |
| Split | `inherit_source` |
| v0 | supported |

Grounding: ATS-1 §9.2.7 (contrary evidence) and §9.2.8 (live alternatives). ATS-1 §8.13 also names
"no contrary evidence found in a narrow search described as no contrary evidence exists" as an
overclaim, which is why the `not_searched` and `none_found` states are kept distinct.

### 2.16 `ATS-MUT-ASSUMPTION-TO-OBSERVATION` — Relabel an assumption as an observation

| Field | Value |
|---|---|
| Title | Change claim role from assumption to observation |
| Profiles | `ASSESS`, `TRANSFORM` |
| Changes | replaces `claim.role` `assumption` with `observation` |
| Target rules | `ATS-EVID-001`, `ATS-PRES-001` |
| Transformation | `ir_claim_role_change`, `target_pointer` `/claims/{i}/role`, `replacement_source` `literal`, `literal` `observation` |
| Preconditions | `role` is `assumption`; the claim is material; `status` is `asserted`; the claim carries no `source_refs` and no evidence object, so the resulting observation has no basis |
| Expected label | `violation` |
| Impact | `P0`, `P1` — matching the `ATS-EVID-001` `protected_impact`; inference provenance is P1 |
| Delta classes | `evidential_force_changed`, `strengthened`, `authority_changed` |
| Det. / Inv. | true / true |
| Required context | the claim's `assumption_refs` and the consequence-if-false statement required by §9.2.9 |
| Exclusions | MUST NOT be applied to an assumption that is in fact directly observed and carries evidence: the relabelled claim would then be accurate. MUST NOT also delete the consequence-if-false text; that is a second feature. |
| HN pair | true — an observation correctly labeled and sourced |
| Split | `inherit_source` |
| v0 | supported |

Grounding: ATS-1 §7.4 (claim roles), §7.12 (assumptions), §9.2.5 (observation, inference, and
judgment must be distinguishable), §9.2.9 (assumption discipline).

### 2.17 `ATS-MUT-SOURCE-ATTRIBUTION-STRIP` — Remove source attribution

| Field | Value |
|---|---|
| Title | Remove source attribution |
| Profiles | `ASSESS`, `SPECIFY`, `TRANSFORM` |
| Changes | deletes `claim.source_refs`, or the `source` locator of the evidence object the claim depends on |
| Target rules | `ATS-EVID-001`, `ATS-PRES-001` |
| Transformation | `ir_field_delete`, `target_pointer` `/claims/{i}/source_refs`, `replacement_source` `none` |
| Preconditions | the claim's `role` is `sourced_report`, or the claim carries non-empty `source_refs`; the claim is material; the attribution is not restated in the proposition text |
| Expected label | `violation` |
| Impact | `P0` — source attribution and authority attribution are P0 (§11.3.1) |
| Delta classes | `source_attribution_changed`, `omitted`, `authority_changed` |
| Det. / Inv. | true / true |
| Required context | the evidence objects; the `source_ref.availability` state |
| Exclusions | MUST NOT be used to model a withheld or redacted source: §20.4 requires redaction to be recorded as `withheld`, not as attribution loss. MUST NOT be applied when the attribution is also carried verbatim in the proposition. |
| HN pair | true — a claim whose source is recorded as `withheld` with authorized-reviewer metadata retained |
| Split | `inherit_source` |
| v0 | supported |

### 2.18 `ATS-MUT-UPDATE-INDICATOR-DELETE` — Delete an update or reversal indicator

| Field | Value |
|---|---|
| Title | Delete the update or reversal indicator |
| Profiles | `ASSESS`, `TRANSFORM` |
| Changes | deletes the `update_indicator` object that targets a material judgment or forecast |
| Target rules | `ATS-EPI-006`, `ATS-PRES-002` |
| Transformation | `ir_field_delete`, `target_pointer` `/update_indicators/{i}`, `replacement_source` `none` |
| Preconditions | the indicator is the only one whose `target_claim_refs` include a material `judgment` or `forecast` claim; no `extraction_issues` entry declares the indicator field unavailable for that claim |
| Expected label | `violation` |
| Impact | `P1` — update and reversal are P1 relations (§11.3.2) |
| Delta classes | `omitted`, `relation_changed` |
| Det. / Inv. | true / true |
| Required context | the targeted judgment or forecast; any `forecast.update_policy` |
| Exclusions | MUST NOT be applied when a second retained indicator targets the same claim, or when the artifact states why no observable indicator exists — `ATS-EPI-006` permits that alternative (§7.14, §9.2.4). |
| HN pair | true — a judgment that states why no observable update indicator exists |
| Split | `inherit_source` |
| v0 | supported |

### 2.19 `ATS-MUT-EVIDENTIAL-STRENGTHEN` — Strengthen evidential force

| Field | Value |
|---|---|
| Title | Strengthen evidential force by one step |
| Profiles | `ASSESS`, `TRANSFORM` |
| Changes | replaces `force.evidential` with the next stronger value in the §8.12 ordering `consistent_with` → `suggests` → `supports` → `strongly_supports` → `establishes` |
| Target rules | `ATS-EVID-002`, `ATS-PRES-001` |
| Transformation | `ir_field_replace`, `target_pointer` `/claims/{i}/force/evidential`, `replacement_source` `force_lexicon` |
| Preconditions | `force.evidential` is present and is not `establishes`; the claim is material; the described basis does not meet the §8.12 interpretation of the stronger value |
| Expected label | `violation` |
| Impact | `P0`, `P1` — matching the `ATS-EVID-002` `protected_impact` |
| Delta classes | `evidential_force_changed`, `strengthened` |
| Det. / Inv. | true / true |
| Required context | the evidence objects and their `quality` metadata; the number of independent lines of evidence |
| Exclusions | MUST NOT be applied when the basis already entails the stronger level. MUST NOT be applied to `establishes`, which has no stronger value. |
| HN pair | true — a claim whose `establishes` is backed by a valid formal demonstration (`HN-5`) |
| Split | `inherit_source_and_operator` |
| v0 | supported |

Grounding: ATS-1 §8.12 (evidential vocabulary), §8.13 (overclaim), §11.6 (non-strengthening
invariant).

### 2.20 `ATS-MUT-RESTATEMENT-INSERT` — Insert a zero-information restatement

| Field | Value |
|---|---|
| Title | Insert a zero-information restatement |
| Profiles | `ASSESS`, `SPECIFY`, `TRANSFORM` |
| Changes | inserts a new non-material claim whose `proposition` is a verbatim copy of an existing material claim's proposition, immediately after it in the same section |
| Target rules | `ATS-DISC-003` |
| Transformation | `ir_claim_insert`, `target_pointer` `/claims/{i}`, `replacement_source` `sibling_field` |
| Preconditions | the copied claim is material; the inserted claim carries `material: false`, `status: asserted`, and adds no scope, evidence, mechanism, implication, contrast, action, or retrieval value |
| Expected label | `violation` |
| Impact | `P2` — matching the `ATS-DISC-003` `protected_impact`; sentence and paragraph structure are P2 (§11.3.3) |
| Delta classes | `added` |
| Det. / Inv. | true / true |
| Required context | the whole section, since §10.19 judges repetition against what the restatement adds |
| Exclusions | The inserted claim MUST carry `material: false`. Inserting a material claim would violate §11.7 (no invented material claims) and would make the record a different kind of defect. MUST NOT be used inside a preservation pair, where any insertion is an `added` delta requiring authorization. MUST NOT be applied where the repetition is needed for referential stability (`HN-4`). |
| HN pair | true — `HN-4`, `HN-11` |
| Split | `inherit_source_and_operator` |
| v0 | supported |

The verbatim copy is what keeps the operator deterministic: it introduces no new information, so no
generation step is needed. `ATS-DISC-003` has no deterministic detector in this implementation — its
required input is `document_context`, so the IR linter reports `UNAVAILABLE` (§10.19). The example is
nevertheless admissible corpus material for a future semantic detector; it MUST NOT be cited as
evidence that a deterministic detector caught it.

### 2.21 `ATS-MUT-JUDGMENT-BURY` — Move a key judgment behind background

| Field | Value |
|---|---|
| Title | Bury the load-bearing claim |
| Profiles | `ASSESS`, `SPECIFY`, `TRANSFORM` |
| Changes | reorders claims within a section so that the load-bearing `judgment` or `requirement` claim no longer precedes background that cannot change it |
| Target rules | `ATS-DISC-001` |
| Transformation | `ir_claim_reorder`, `target_pointer` `/sections/{s}/claim_refs`, `replacement_source` `none` |
| Preconditions | the section contains a material `judgment` or `requirement` claim that is currently first in document order; the section contains at least one background claim that cannot change it |
| Expected label | `violation` |
| Impact | `P2` — local ordering is P2 unless it changes dependencies (§11.3.3); this matches the `ATS-DISC-001` `protected_impact` |
| Delta classes | `preserved` |
| Det. / Inv. | true / true |
| Required context | the whole section in document order; the profile, since ASSESS §9.2.3 governs key-judgment placement |
| Exclusions | MUST NOT reorder claims whose ordering carries a dependency: ordering dependencies are P1 (§11.3.2), and moving those is a different, more severe feature. MUST NOT be applied to a section with no background claim, where the reorder would be a no-op. |
| HN pair | true — a section whose first paragraph is a required scope statement rather than background |
| Split | `inherit_source_and_operator` |
| v0 | supported |

`ATS-DISC-001` states a `SHOULD` and has `severity: minor`, so a finding is advisory under the
default policy. The `violation` label records that the rule's normative statement is not satisfied;
it does not assert that mechanical conformance fails. Under `ASSESS`, burying the key judgment also
bears on profile completeness through §9.2.3 and §9.2.13.

### 2.22 `ATS-MUT-ANTECEDENT-AMBIGUATE` — Introduce a second plausible antecedent

| Field | Value |
|---|---|
| Title | Introduce a second plausible antecedent |
| Profiles | `ASSESS`, `SPECIFY`, `TRANSFORM` |
| Changes | would replace a material noun phrase with a pronoun or demonstrative and introduce a second, genuinely plausible referent nearby |
| Target rules | `ATS-REF-001` |
| Transformation | `text_span_replace`, `replacement_source` `none` |
| Preconditions | the span contains a material referring expression with exactly one plausible antecedent; a second entity of the same type is available in local context |
| Expected label | `violation` |
| Impact | `P0`, `P1` — matching the `ATS-REF-001` `protected_impact`; referent identity is P0 and inference provenance is P1 |
| Delta classes | `ambiguous_after_transform`, `scope_changed` |
| Det. / Inv. | false / false |
| Required context | the containing block, the preceding and following context, and the entity inventory of the section |
| Exclusions | not applicable in v0 |
| HN pair | true — a pronoun with exactly one plausible antecedent in a long sentence |
| Split | `inherit_source_and_operator` |
| **v0** | **not supported** |
| `unsupported_reason` | Inventing a second *plausible* antecedent requires free-form prose generation: plausibility depends on entity type, discourse salience, and reader knowledge, none of which is a deterministic function of the source IR. MC-4 therefore requires this operator to be declared rather than implemented. `apply_operator` raises `UnsupportedCapabilityError`. |

### 2.23 Support summary

| # | `operator_id` | Target rules | Label | Impact | Det. | Inv. | HN pair | Split | v0 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `ATS-MUT-QUAL-DELETE` | `ATS-PRES-002`, `ATS-EVID-002` | violation | P1 | yes | yes | yes | source | yes |
| 2 | `ATS-MUT-WEP-BAND-SHIFT` | `ATS-EPI-001`, `ATS-PRES-001` | violation | P0 | yes | yes | yes | source+op | yes |
| 3 | `ATS-MUT-WEP-RANGE-STRIP` | `ATS-EPI-002` | violation | P0, P2 | yes | yes | yes | source+op | yes |
| 4 | `ATS-MUT-LIKELIHOOD-CONFIDENCE-SWAP` | `ATS-EPI-004` | violation | P0, P1 | yes | yes | yes | source+op | yes |
| 5 | `ATS-MUT-DEONTIC-EXCHANGE` | `ATS-DEON-001`, `ATS-DEON-002`, `ATS-DEON-003`, `ATS-PRES-001` | violation | P0 | yes | yes | yes | source+op | yes |
| 6 | `ATS-MUT-ACTOR-REMOVE` | `ATS-REQ-001`, `ATS-PRES-001` | violation | P0 | yes | yes | yes | source | yes |
| 7 | `ATS-MUT-OBLIGATION-MERGE` | `ATS-REQ-002` | violation | P0, P1 | yes | yes | yes | source | yes |
| 8 | `ATS-MUT-UNIT-STRIP` | `ATS-NUM-001`, `ATS-PRES-001` | violation | P0 | yes | yes | yes | source | yes |
| 9 | `ATS-MUT-THRESHOLD-BOUNDARY-SHIFT` | `ATS-NUM-002`, `ATS-PRES-001` | violation | P0 | yes | yes | yes | source | yes |
| 10 | `ATS-MUT-NEGATION-FLIP` | `ATS-PRES-001`, `ATS-SCOPE-001` | violation | P0 | yes | yes | yes | source+op | yes (IR pair only) |
| 11 | `ATS-MUT-QUANTIFIER-WIDEN` | `ATS-PRES-001`, `ATS-SCOPE-001` | violation | P0 | yes | yes | yes | source+op | yes (IR pair only) |
| 12 | `ATS-MUT-RELATION-REVERSE` | `ATS-PRES-002`, `ATS-EVID-002` | violation | P1 | yes | yes | yes | source+op | yes |
| 13 | `ATS-MUT-CAUSAL-UPGRADE` | `ATS-EVID-002`, `ATS-PRES-002` | violation | P0, P1 | yes | yes | yes | source+op | yes |
| 14 | `ATS-MUT-EXCEPTION-DELETE` | `ATS-REQ-003`, `ATS-DEON-003`, `ATS-PRES-001` | violation | P0 | yes | yes | yes | source | yes |
| 15 | `ATS-MUT-CONTRARY-EVIDENCE-DELETE` | `ATS-EVID-003`, `ATS-PRES-002` | violation | P1 | yes | yes | yes | source | yes |
| 16 | `ATS-MUT-ASSUMPTION-TO-OBSERVATION` | `ATS-EVID-001`, `ATS-PRES-001` | violation | P0, P1 | yes | yes | yes | source | yes |
| 17 | `ATS-MUT-SOURCE-ATTRIBUTION-STRIP` | `ATS-EVID-001`, `ATS-PRES-001` | violation | P0 | yes | yes | yes | source | yes |
| 18 | `ATS-MUT-UPDATE-INDICATOR-DELETE` | `ATS-EPI-006`, `ATS-PRES-002` | violation | P1 | yes | yes | yes | source | yes |
| 19 | `ATS-MUT-EVIDENTIAL-STRENGTHEN` | `ATS-EVID-002`, `ATS-PRES-001` | violation | P0, P1 | yes | yes | yes | source+op | yes |
| 20 | `ATS-MUT-RESTATEMENT-INSERT` | `ATS-DISC-003` | violation | P2 | yes | yes | yes | source+op | yes |
| 21 | `ATS-MUT-JUDGMENT-BURY` | `ATS-DISC-001` | violation | P2 | yes | yes | yes | source+op | yes |
| 22 | `ATS-MUT-ANTECEDENT-AMBIGUATE` | `ATS-REF-001` | violation | P0, P1 | no | no | yes | source+op | **no** |

Twenty-one operators are supported in v0. One, `ATS-MUT-ANTECEDENT-AMBIGUATE`, is specified and
declared unsupported.

### 2.24 Coverage against ATS-1 §17.5

ATS-1 §17.5 lists twenty-one recommended operators. This catalog covers all of them and adds one.
The additional operator is `ATS-MUT-WEP-RANGE-STRIP` (§2.3), which ATS-1 §17.5 does not list; the
milestone brief requires it, and it is grounded in the ATS-1 §8.4 first-use range obligation and the
`ATS-EPI-002` rule record. It is therefore a **Repository policy** addition to a spec-recommended
set, not an ATS-1 obligation.

| ATS-1 §17.5 item | Catalog section of this document |
|---|---|
| delete a qualifier | 2.1 |
| change a WEP band | 2.2 |
| exchange likelihood and confidence | 2.4 |
| exchange `MAY`, `CAN`, `SHOULD`, and `MUST` | 2.5 |
| remove the actor | 2.6 |
| merge two obligations | 2.7 |
| remove a unit or denominator | 2.8 |
| alter a threshold boundary | 2.9 |
| flip negation | 2.10 |
| change `some` to `all` | 2.11 |
| reverse causal direction | 2.12 |
| change association to causation | 2.13 |
| delete an exception | 2.14 |
| remove contrary evidence | 2.15 |
| turn an assumption into an observation | 2.16 |
| remove source attribution | 2.17 |
| delete a reversal condition | 2.18 |
| strengthen evidential force | 2.19 |
| insert a zero-information restatement | 2.20 |
| bury the key judgment | 2.21 |
| introduce a second plausible antecedent | 2.22 |
| *(not in §17.5)* remove the inline WEP range | 2.3 |

---

## 3. What synthetic evidence cannot establish

**MC-15.** Synthetic mutations are never independent evidence of natural prevalence or user value.
Concretely, a synthetic example MUST NOT be counted toward:

1. accepted-finding rate;
2. correction rate;
3. reviewer time per useful finding;
4. false-positive burden per thousand words;
5. first-finding utility; or
6. downstream value.

Those six metrics come from ATS-1 §17.10 and §18.2. Each measures behavior on text a human actually
wrote and reviewed. A synthetic mutation is written by an operator, so it CANNOT evidence how often
the defect occurs or what fixing it is worth.

**MC-16.** Synthetic mutations MAY be counted toward per-rule precision and recall, calibration,
abstention coverage, hard-negative performance, and preservation metrics, provided the synthetic
stratum is reported separately (ATS-1 §17.10: a single macro score is insufficient).

**MC-17.** A promotion receipt that cites synthetic examples MUST identify them as synthetic and
MUST state which gates they contributed to (ATS-1 §18.6, §12.9).

---

## 4. Registry obligations

**MC-18.** `corpus/operators/ats_mutation_operators_v1.yaml` MUST validate against
`schemas/ats_mutation_operator_v1.schema.json`, and MUST contain exactly the twenty-two
`operator_id` values listed in this document §2.23.

**MC-19.** The registry and this catalog MUST agree on every field of every operator. Where they
disagree, the registry is authoritative for machine behavior, and the disagreement MUST be resolved
by amending whichever document is wrong; the mismatch MUST NOT be left standing.

**MC-20.** Adding, removing, or changing the meaning of an operator MUST increment
`registry_version`, and changing an operator's behavior MUST increment that operator's
`operator_version`. A retired `operator_id` MUST NOT be reused.

**MC-21.** An operator application entry point MUST raise a typed unsupported-capability error for an
operator whose `supported` is `false`. It MUST NOT approximate the operator, and MUST NOT return a
silently unmodified artifact (ATS-1 §14.12).

---

## 5. Traceability

| Obligation | Grounding | Authority |
|---|---|---|
| MC-1 | ATS-1 §17.5 ("SHOULD change one semantic feature at a time") | ATS-1 raised |
| MC-2 | ATS-1 §17.5 ("Synthetic examples MUST be tagged. They MUST NOT be counted as independent real-world evidence of rule prevalence or user value.") | ATS-1 normative |
| MC-3 | ATS-1 §12.9 (final paragraph) | ATS-1 normative |
| MC-4 | Milestone: no uncontrolled model generation in v0; `ats_mutation_operator_v1.schema.json` (`supported`, `unsupported_reason`); ATS-1 §16.2 | Repository policy, enforced by Repo schema |
| MC-5 | `ats_mutation_operator_v1.schema.json` `#/$defs/operator` `required` | Repo schema |
| MC-6 | `ats_mutation_operator_v1.schema.json` `split_group_policy`; ATS-1 §17.7 | Repo schema; ATS-1 normative for the grouping obligation |
| MC-7 | `ats_mutation_operator_v1.schema.json` `replacement_source` ("Never a free-form model completion"); ATS-1 §1.2 | Repo schema |
| MC-8 | `ats_mutation_operator_v1.schema.json` `target_pointer`; ATS-1 Appendix B | Repo schema |
| MC-9 | ATS-1 §16.2, §11.3.1; MC-4 | Repository policy |
| MC-10 | ATS-1 §16.2, Appendix C | ATS-1 normative |
| MC-11 | `spec/.../schemas/ats_text_ir_v1.schema.json`; `ats_common_v1#/$defs/requirement_slots` (`actor` `minLength: 1`); `#/$defs/quantifier` conditionals | Repo schema |
| MC-12 | Milestone five per-mutation obligations; ATS-1 §17.5, §16.12 | Repository policy; items 1 and 5 implement ATS-1 §17.5 |
| MC-13 | ATS-1 §17.5, §17.7; `ats_text_example_v1.schema.json` | ATS-1 normative |
| MC-14 | ATS-1 §17.6, §18.4 | ATS-1 normative |
| MC-15 | ATS-1 §17.5, §17.10, §18.2 | ATS-1 normative |
| MC-16 | ATS-1 §17.10 ("A single macro score is insufficient") | ATS-1 raised |
| MC-17 | ATS-1 §18.6, §12.9 | ATS-1 normative |
| MC-18 | Milestone registry path; `schemas/ats_mutation_operator_v1.schema.json` | Repository policy |
| MC-19 | ATS-1 §16.8 (explanation fidelity), §19.4 | Repository policy |
| MC-20 | ATS-1 §18.1 (a retired identifier MUST NOT be reused), §19.2 | ATS-1 normative for rule identifiers; applying it to operator identifiers is Repository policy |
| MC-21 | ATS-1 §14.12, §5.5; milestone scaffold rule | ATS-1 normative |

### 5.1 Per-operator grounding

| Catalog section of this document | ATS-1 sections | Rule records |
|---|---|---|
| 2.1 | §17.5, §11.3.2 | `ATS-PRES-002`, `ATS-EVID-002` |
| 2.2 | §17.5, §8.2, §8.5, §11.3.1 | `ATS-EPI-001`, `ATS-PRES-001` |
| 2.3 | §8.4, §11.3.1, §11.3.3 — milestone addition, not in §17.5 | `ATS-EPI-002` |
| 2.4 | §17.5, §4.8, §8.11 | `ATS-EPI-004` |
| 2.5 | §17.5, §8.16, §8.17, §9.3.11, §9.3.12, §11.3.1 | `ATS-DEON-001`, `ATS-DEON-002`, `ATS-DEON-003`, `ATS-PRES-001` |
| 2.6 | §17.5, §9.3.4, §10.7, §21.4 | `ATS-REQ-001`, `ATS-PRES-001` |
| 2.7 | §17.5, §9.3.3, §9.3.18 | `ATS-REQ-002` |
| 2.8 | §17.5, §10.9, §11.3.1 | `ATS-NUM-001`, `ATS-PRES-001` |
| 2.9 | §17.5, §9.3.8, §10.10, §11.3.1 | `ATS-NUM-002`, `ATS-PRES-001` |
| 2.10 | §17.5, §7.8, §11.3.1 | `ATS-PRES-001`, `ATS-SCOPE-001` |
| 2.11 | §17.5, §7.7, §11.3.1 | `ATS-PRES-001`, `ATS-SCOPE-001` |
| 2.12 | §17.5, §7.11, §11.3.2, §21.5 | `ATS-PRES-002`, `ATS-EVID-002` |
| 2.13 | §17.5, §8.13, §8.14, §8.15 | `ATS-EVID-002`, `ATS-PRES-002` |
| 2.14 | §17.5, §7.13, §9.3.11, §11.3.1, §11.8 | `ATS-REQ-003`, `ATS-DEON-003`, `ATS-PRES-001` |
| 2.15 | §17.5, §9.2.7, §9.2.8, §8.13, §11.3.2 | `ATS-EVID-003`, `ATS-PRES-002` |
| 2.16 | §17.5, §7.4, §7.12, §9.2.5, §9.2.9 | `ATS-EVID-001`, `ATS-PRES-001` |
| 2.17 | §17.5, §7.10, §11.3.1, §20.4 | `ATS-EVID-001`, `ATS-PRES-001` |
| 2.18 | §17.5, §7.14, §9.2.4, §11.3.2 | `ATS-EPI-006`, `ATS-PRES-002` |
| 2.19 | §17.5, §8.12, §8.13, §11.6 | `ATS-EVID-002`, `ATS-PRES-001` |
| 2.20 | §17.5, §10.19, §11.7, §11.3.3 | `ATS-DISC-003` |
| 2.21 | §17.5, §9.2.3, §10.16, §11.3.3 | `ATS-DISC-001` |
| 2.22 | §17.5, §10.6, §13.4 | `ATS-REF-001` |

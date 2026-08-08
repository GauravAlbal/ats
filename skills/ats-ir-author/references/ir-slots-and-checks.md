# TextIR required slots, structural checks, and the rule catalog

Read out of `spec/ATS-1/1.0.0-draft.1/schemas/{ats_text_ir_v1,ats_common_v1}.schema.json`
and `spec/ATS-1/1.0.0-draft.1/rules/ats_rules_v1.yaml`. The package is authoritative.

Vocabulary values and profile-slot obligations live in `vocabularies.md`. This file is the
field-level contract: what the schema requires, what each check defends, and what each rule
says.

---

## 1. Required and optional fields, object by object

`required` is enforced by the schema; omitting one is an `IR-SCHEMA` failure. `optional` in
the schema does **not** mean optional in the standard — §7.5 and the profile sections make
many of them mandatory when applicable, and `IR-PROFILE-SLOTS` / `IR-CLAIM-ROLE-FIELDS`
check that.

### Document root — `ats.text_ir.v1`

| | fields |
|---|---|
| required | `schema_version` (const `ats.text_ir.v1`), `artifact_id`, `source`, `policy_snapshot_id`, `language` (const `en`), `audience`, `sections` (≥1), `extraction_status` |
| optional | `glossary`, `extraction_issues`, `extensions` |

`additionalProperties: false` at every level — an unrecognised key is a schema failure, not
an extension. Extensions go in an `extensions` object.

### `source`

| | fields |
|---|---|
| required | `content_sha256`, `media_type` |
| optional | `normalized_sha256`, `locator`, `revision` |

`normalized_sha256` is schema-optional and **practically mandatory**: §14.2 and Appendix C
require retaining both hashes whenever preprocessing changes the text, and
`IR-SOURCE-HASH` verifies both against `--source`.

### `audience`

| | fields |
|---|---|
| required | `expertise` (`novice`\|`practitioner`\|`expert`\|`mixed`) |
| optional | `audience_id`, `assumed_glossary_refs`, `locale`, `constraints` |

### `sections[]`

| | fields |
|---|---|
| required | `section_id`, `profiles` (≥1, unique), `claims`, `evidence`, `relations`, `update_indicators` |
| optional | `heading`, `span`, `display`, `extensions` |

The four collection fields are required **even when empty**. An empty array is a positive
statement that the section has none; a missing key is a schema failure.

### `claim`

| | fields |
|---|---|
| required | `claim_id`, `role`, `proposition` (`minLength: 1`), `material`, `polarity`, `status` |
| optional | `subject`, `span`, `materiality_rationale`, `quantifier`, `scope`, `force`, `source_refs`, `assumption_refs`, `boundary_refs`, `exception_refs`, `interpretations`, `requirement`, `forecast`, `extensions` |

Conditional requirements in the schema's `allOf`:

| if | then |
|---|---|
| `role == "requirement"` | `requirement` is required |
| `role == "forecast"` | `forecast` is required |
| `status == "ambiguous"` | `interpretations` is required, `minItems: 2` |

### `evidence`

| | fields |
|---|---|
| required | `evidence_id`, `proposition` (`minLength: 1`), `source`, `availability` |
| optional | `quality_notes`, `span`, `extensions` |

### `source_ref` (the `evidence.source` object)

| | fields |
|---|---|
| required | `source_id`, `source_type`, `availability` |
| optional | `locator`, `content_sha256`, `observed_at`, `revision`, `search_scope`, `notes` |

Conditional: when `availability == "present"`, `locator` **or** `content_sha256` is
required. §7.9 additionally requires `search_scope` (or a search-receipt reference) for
`not_found`.

### `relation`

| | fields |
|---|---|
| required | `relation_id`, `source_id`, `type`, `target_id`, `material` |
| optional | `scope`, `basis_refs`, `notes` |

### `update_indicator`

| | fields |
|---|---|
| required | `indicator_id`, `text` (`minLength: 1`), `target_claim_refs` (≥1, unique) |
| optional | `observation_condition`, `effect` |

### `glossary_entry`

| | fields |
|---|---|
| required | `concept_id`, `canonical_term`, `definition`, `scope` — all `minLength: 1` |
| optional | `approved_abbreviations`, `deprecated_aliases`, `audience`, `external_ids` |

### `requirement_slots` (`claim.requirement`)

| | fields |
|---|---|
| required | `requirement_id`, `actor`, `deontic`, `action`, `object`, `source_authority` |
| optional | `scope`, `trigger`, `condition`, `timing`, `constraints`, `exceptions`, `acceptance_criterion`, `rationale`, `indivisible_actions_justification` |

`acceptance_criterion` is schema-optional but **required by §9.3.9 for every `MUST` and
`MUST_NOT`**; `ATS-REQ-003` fails without it and rejects the vacuous forms.
`requirement.deontic` allows only `MUST`, `MUST_NOT`, `SHOULD`, `SHOULD_NOT`, `MAY`.

### `forecast_slots` (`claim.forecast`)

| | fields |
|---|---|
| required | `forecast_id`, `outcome_definition`, `resolution`, `resolution_source`, `update_policy`, `outcome_status` |
| optional | `score` |

### `likelihood`

| | fields |
|---|---|
| required | `kind` (`wep`\|`point`\|`interval`\|`not_applicable`) |
| optional | `term`, `display`, `lower`, `upper`, `point`, `range_shown_inline`, `rationale` |

Conditional: `kind: wep` → `term`, `lower`, `upper`, `range_shown_inline` required.
`kind: point` → `point` required. `kind: interval` → `lower`, `upper` required.
`ATS-EPI-001` additionally requires a `rationale` for `point` and `interval`, and exact
lexicon-interval agreement for `wep`.

### `assessment_confidence` and `confidence_basis`

`assessment_confidence` requires `level` and `basis`, and permits nothing else.
`confidence_basis` requires **all ten**: the nine dimensions plus `rationale`
(`minLength: 1`). There is no partial basis object.

### `force`, `scope`, `quantifier`, `span`

| object | required | optional |
|---|---|---|
| `force` | — | `likelihood`, `assessment_confidence`, `evidential`, `causal`, `deontic`, `external_authority` |
| `scope` | — | `population`, `system`, `environment`, `condition`, `exclusions`, `time_horizon`, `authority_domain`, `version`, `evidence_window`, `unknown_fields` |
| `quantifier` | `kind` | `value`, `lower`, `upper`, `denominator`, `unit` |
| `span` | `kind` | `start`, `end`, `start_line`, `end_line`, `locator`, `source_sha256` |

Conditionals: `force` requires `external_authority` iff `deontic == "REQUIRED_BY"`, and
forbids it otherwise. `quantifier` requires `value` for `exact_count`/`minimum`/`maximum`/
`proportion`, `lower`+`upper` for `range`, and `denominator` for `proportion`.
`span` requires `start`+`end` for `character`, `start_line`+`end_line` for `line`, and
`locator` for `locator`/`json_pointer`.

### `extraction_issues[]`

| | fields |
|---|---|
| required | `issue_id`, `status` (`partial`\|`ambiguous`\|`unavailable`), `description` |
| optional | `span`, `affected_fields`, `candidate_interpretations` |

---

## 2. The 26 structural checks (`ats ir lint` → `structural_checks[]`)

Ids are stable. Read every non-`PASS` `detail`.

Ids, titles, and spec refs below are read verbatim from a real `ats ir lint` report.

| check | title (verbatim) | spec ref |
|---|---|---|
| `IR-SCHEMA` | TextIR conforms to ats_text_ir_v1.schema.json | ATS-1 19.4, Appendix C |
| `IR-POLICY-IDENTITY` | The bound policy snapshot is the one supplied, and its content address holds | ATS-1 6.6, 14.13 |
| `IR-POLICY-CURRENTNESS` | Policy currentness inputs hold for the artifact scope | ATS-1 14.3, 14.12, 15.8 |
| `IR-SOURCE-HASH` | Source and normalized hashes bind the exact input bytes | ATS-1 14.2, Appendix C |
| `IR-ID-UNIQUE` | Every identifier is used once | ATS-1 7.3, 9.3.18 |
| `IR-REFS` | Every internal reference resolves to an object of the right kind | ATS-1 7.9, 7.11, 7.13, 7.14 |
| `IR-SECTION-PROFILE` | Every section resolves to a declared content profile | ATS-1 6.5, 9.4, 9.5 |
| `IR-PROFILE-SLOTS` | Profile-required semantic slots are resolved | ATS-1 9.1, 9.2.2, 9.2.4, 9.2.13, 9.3.2, 9.3.20, 12.8 |
| `IR-CLAIM-ROLE-FIELDS` | Claim roles carry only the fields their role admits | ATS-1 7.4, 7.5, 9.2.5, 9.2.10 |
| `IR-EVIDENCE-ENDPOINTS` | Evidence objects are retrievable or carry an exact availability state | ATS-1 7.9, 7.10, 9.2.6, 9.2.7 |
| `IR-GLOSSARY-REFS` | Glossary and assumed term-base references resolve | ATS-1 7.2, 10.3 |
| `IR-LIKELIHOOD-VOCAB` | WEP terms and intervals match the active lexicon | ATS-1 8.2, 19.3 |
| `IR-FIRST-USE-RANGE` | First material WEP use declares its display range | ATS-1 8.4 |
| `IR-LIKELIHOOD-CONFIDENCE-SEP` | Likelihood and assessment confidence occupy distinct fields | ATS-1 8.11, 4.8 |
| `IR-CONFIDENCE-BASIS` | Confidence-basis structure matches the lexicon dimensions | ATS-1 8.8, 8.9 |
| `IR-UPDATE-INDICATORS` | Update and reversal indicators are well formed | ATS-1 7.14 |
| `IR-DEONTIC-VALIDITY` | Deontic force values come from the closed lexicon | ATS-1 8.16 |
| `IR-REQUIREMENT-SLOTS` | Requirement slots are explicit or referenced | ATS-1 9.3.2, 9.3.7, 9.3.9 |
| `IR-ONE-OBLIGATION` | Each requirement object carries one obligation | ATS-1 9.3.3 |
| `IR-QUANT-UNITS` | Material numbers are represented as quantifier objects | ATS-1 7.7, 10.9 |
| `IR-POLARITY-QUANTIFIER` | Polarity, scope, attribution, and authority fields are represented | ATS-1 7.5, 7.6, 7.8, 9.3.15 |
| `IR-P0-P1-DECLARATIONS` | Protected-impact exposure is declared coherently | ATS-1 7.15, 11.3.1, 11.3.2 |
| `IR-EXTRACTION-STATUS` | Extraction status, issues, and ambiguous claims agree | ATS-1 7.5, 7.16, 13.4 |
| `IR-POLICY-EXCEPTIONS` | Policy exceptions are valid, scoped, and unexpired | ATS-1 6.3, 6.4 |
| `IR-CAPABILITY` | Unsupported and partially supported capabilities are declared | ATS-1 5.5, 14.12, 16.1 |
| `IR-CANONICAL` | Canonical serialization is stable and reproduces the content address | ATS-1 Appendix C, 16.2 |

Notes on the ones most often misread:

- `IR-SOURCE-HASH` is `UNAVAILABLE` unless you pass `--source`. That is §5.4 working: the check
  could not execute, so it is not `PASS`.
- `IR-EVIDENCE-ENDPOINTS` is about **evidence retrievability** — a `present` source needs a
  locator or content hash, and every other state must be the exact §7.9 availability value.
  Reference resolution across `*_refs`, `source_id`, and `target_id` is `IR-REFS`.
- `IR-QUANT-UNITS` and `IR-POLARITY-QUANTIFIER` are structural: the first checks that a material
  number is modelled as a `quantifier` object with its unit, the second that polarity, scope,
  source attribution, and authority are actually represented rather than left to the prose.
- `IR-DEONTIC-VALIDITY`, `IR-REQUIREMENT-SLOTS`, `IR-ONE-OBLIGATION`, `IR-QUANT-UNITS`, and
  `IR-POLICY-EXCEPTIONS` report `NOT_APPLICABLE` when the artifact declares no requirement, no
  deontic force, no material number, or no exception. `NOT_APPLICABLE` is a real answer, not a
  skipped check.
- `IR-CAPABILITY` compares what this build actually ran against
  `capability/ats_rule_capability_v1.json`, so an undeclared gap is a finding (§5.5, §14.12).

---

## 3. The 30 rules (`ats ir lint` → `rule_results[]`)

Normative statements are truncated here; run
`ats ir explain-finding <RULE-ID>` for the full record, the spec anchor, worked repairs, and
this build's declared capability for that rule.

`REVIEW_REQUIRED` from a rule that found nothing is the correct, honest result for a
detector that only recognises a defined subset of violations: §5.4 and §16.5 forbid
inferring conformance from detector silence.

| rule | severity | default state (ASSESS / SPECIFY) | normative statement (truncated) |
|---|---|---|---|
| `ATS-TERM-001` | major | advisory / advisory | Within one scope, a concept MUST use one canonical term unless an explicit contrast or quotation applies. |
| `ATS-TERM-002` | critical | advisory / advisory | A precise approved domain term MUST NOT be replaced solely to use more common vocabulary. |
| `ATS-TERM-003` | minor | required / required | An acronym or abbreviation MUST be expanded on first material use unless policy permits it. |
| `ATS-REF-001` | major | advisory / required | A material pronoun, demonstrative, or elliptical reference MUST have one plausible antecedent. |
| `ATS-SCOPE-001` | critical | advisory / required | Material quantifier, negation, condition, exclusion, and scope relationships MUST be explicit. |
| `ATS-NUM-001` | critical | required / required | A material number MUST include its unit, dimension, denominator, or explicit dimensionless status. |
| `ATS-NUM-002` | critical | required / required | A material range or threshold MUST define comparator and boundary semantics. |
| `ATS-TIME-001` | critical | required / advisory | A material forecast or temporally bounded judgment MUST state a resolution date, event, or horizon. |
| `ATS-TIME-002` | major | required / required | A material relative-time expression MUST resolve to an absolute date, event, version, or snapshot. |
| `ATS-PRES-001` | critical | disabled / disabled | A transformation MUST preserve all retained P0 fields exactly unless authorized. |
| `ATS-EPI-001` | critical | required / advisory | A material probabilistic judgment MUST use the canonical WEP vocabulary or a justified number. |
| `ATS-EPI-002` | major | required / advisory | The first material WEP use in a section MUST include its numeric display range inline. |
| `ATS-EPI-003` | major | required / advisory | A section MUST NOT mix noncanonical WEP synonyms with canonical ATS-1 output. |
| `ATS-EPI-004` | critical | required / advisory | Likelihood and assessment confidence MUST be represented as distinct fields or labeled sentences. |
| `ATS-EPI-005` | critical | required / advisory | A material assessment-confidence label MUST include an inspectable basis and rationale. |
| `ATS-EPI-006` | major | required / advisory | A material assessment MUST identify an observable update or reversal indicator, or say why none exists. |
| `ATS-EPI-007` | major | required / advisory | "Possible," "plausible," "might," and "could" MUST NOT serve as the only likelihood expression. |
| `ATS-DEON-001` | critical | advisory / required | Normative statements MUST use ATS-1 deontic terms with their defined force. |
| `ATS-DEON-002` | critical | advisory / required | `MAY` MUST express permission, not probability or capability. |
| `ATS-DEON-003` | critical | advisory / required | `SHOULD` and `SHOULD NOT` MUST express defeasible recommendation, not an unstated forecast. |
| `ATS-REQ-001` | critical | disabled / required | Every material requirement MUST identify the responsible actor explicitly. |
| `ATS-REQ-002` | critical | disabled / required | Every material requirement MUST contain one obligation unless indivisibility is proven. |
| `ATS-REQ-003` | critical | disabled / required | Every applicable requirement slot MUST be resolved or explicitly marked unknown. |
| `ATS-EVID-001` | critical | required / required | Observation, sourced report, assumption, inference, judgment, forecast, recommendation, and requirement MUST stay distinguishable. |
| `ATS-EVID-002` | critical | advisory / advisory | Evidential and causal wording MUST NOT exceed the basis described or referenced. |
| `ATS-EVID-003` | major | required / advisory | A material assessment MUST identify contrary evidence and live alternatives, or the exact search state. |
| `ATS-DISC-001` | minor | advisory / advisory | The load-bearing judgment, requirement, or answer SHOULD precede unchanging background. |
| `ATS-DISC-002` | minor | advisory / advisory | A paragraph SHOULD perform one primary conceptual move. |
| `ATS-DISC-003` | minor | advisory / advisory | A restatement SHOULD add scope, evidence, mechanism, implication, contrast, action, or retrievability. |
| `ATS-PRES-002` | critical | disabled / disabled | A transformation MUST preserve all retained material P1 relations with the same type, direction, and force. |

Both `ATS-PRES-*` rules default to `disabled` under `ASSESS` and `SPECIFY`; they activate
only when `TRANSFORM` is among the resolved profiles, and §6.4 forbids reporting
`preservation: PASS` while either is disabled, unavailable, failed, or waived for a
material retained claim.

Policy resolution may strengthen or weaken a default state through `rule_overrides` or an
authorized `policy_exception` (§6.1–§6.3). The state that governs a run is the one in the
lint report, not the default in this table.

---

## 4. Repository fixtures to compare against

| fixture | what it demonstrates |
|---|---|
| `fixtures/ir/valid/assess_conforming.json` | a complete `ASSESS` ledger: WEP judgment, nine-dimension basis, three evidence objects, six relations, one update indicator |
| `fixtures/ir/valid/specify_conforming.json` | a complete `SPECIFY` requirement with every applicable §9.3.2 slot |
| `fixtures/ir/valid/composed_profiles.json` | `ASSESS` and `SPECIFY` sections in one artifact (§9.4), and the `ATS-ID-1` ordinal convention |
| `fixtures/ir/valid/assess_partial_extraction.json` | `extraction_status: partial` with `affected_fields` |
| `fixtures/ir/valid/assess_represented_ambiguity.json` | `extraction_status: ambiguous`, `claim.status: ambiguous`, two `interpretations`, matching `candidate_interpretations` |
| `fixtures/ir/valid/assess_transform_output.json` | an artifact evaluated with `TRANSFORM` active |
| `fixtures/ir/invalid/*.json` | 17 documents, each violating exactly one named thing — the fastest way to see what a given check catches |

Each invalid fixture is named for its defect: `wep_interval_mismatch`,
`noncanonical_wep_synonym`, `observation_with_confidence`, `blank_confidence_basis`,
`possibility_term_only`, `no_update_indicator`, `ambiguous_without_distinct_readings`,
`concealed_actor`, `two_obligations`, `missing_acceptance_criterion`,
`should_without_override`, `noncanonical_modal`, `quantifier_without_unit`,
`unanchored_relative_time`, `dangling_reference`, `duplicate_ids`, `reserved_profile`.

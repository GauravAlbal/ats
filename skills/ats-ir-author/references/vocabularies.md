# ATS-1 controlled vocabularies and required slots

Every value below was read out of the normative package, not recalled:

- vocabularies: `spec/ATS-1/1.0.0-draft.1/lexicons/ats_force_lexicon_v1.yaml`
- enums: `spec/ATS-1/1.0.0-draft.1/schemas/ats_common_v1.schema.json`,
  `ats_text_ir_v1.schema.json`, and repo-local `schemas/ats_output_trace_v1.schema.json`
- prose obligations: `spec/ATS-1/1.0.0-draft.1/ATS-1_SPEC.md`

If this file and the package ever disagree, **the package wins**. Re-read the YAML.

---

## 1. The five force axes are separate (§8.1)

ATS-1 represents five axes and forbids using one as a substitute for another:
likelihood, assessment confidence, evidential force, causal force, deontic force.

In the IR they are five sibling fields of `claim.force`:
`likelihood`, `assessment_confidence`, `evidential`, `causal`, `deontic`
(+ `external_authority`, required iff `deontic == "REQUIRED_BY"`).

---

## 2. Likelihood — words of estimative probability (§8.2, lexicon `likelihood.terms`)

Canonical set `ats-wep-v1`. `first_material_use_must_show_range: true`.
Machine boundary convention, verbatim from the lexicon:
`lower-inclusive, upper-exclusive; final interval includes 0.99`.

| `term` | canonical phrase | `display_range` | `lower` | `upper` | machine interval | `input_aliases` (recognise on input, NEVER render) |
|---|---|---|---|---|---|---|
| `almost_no_chance` | almost no chance | 1–5% | `0.01` | `0.05` | `[0.01, 0.05)` | "remote", "highly improbable" |
| `very_unlikely` | very unlikely | 5–20% | `0.05` | `0.2` | `[0.05, 0.2)` | (none) |
| `unlikely` | unlikely | 20–45% | `0.2` | `0.45` | `[0.2, 0.45)` | "improbable" |
| `roughly_even_chance` | roughly even chance | 45–55% | `0.45` | `0.55` | `[0.45, 0.55)` | "roughly even odds" |
| `likely` | likely | 55–80% | `0.55` | `0.8` | `[0.55, 0.8)` | "probable" |
| `very_likely` | very likely | 80–95% | `0.8` | `0.95` | `[0.8, 0.95)` | "highly probable" |
| `almost_certain` | almost certain | 95–99% | `0.95` | `0.99` | `[0.95, 0.99]` | "nearly certain" |

`likelihood.kind` enum: `wep`, `point`, `interval`, `not_applicable`.

- `kind: wep` requires `term`, `lower`, `upper`, `range_shown_inline`.
  `lower`/`upper` MUST equal the lexicon numbers above exactly (`ATS-EPI-001`, §8.2).
- `kind: point` requires `point`; `kind: interval` requires `lower` and `upper`.
  Both require a `rationale` under `ATS-EPI-001` (§8.5).
- `display` carries the rendered surface, e.g. `"likely (55–80%)"`.

Out-of-band handling, verbatim from `likelihood.out_of_band`:

| key | value |
|---|---|
| `below_1_percent` | state numerically |
| `above_99_percent` | state numerically |
| `zero_and_one` | reserved for logical, definitional, or exhaustive certainty |

**Not likelihood bands** — `likelihood.non_probability_terms` (§8.7): `"possible"`,
`"plausible"`, `"might"`, `"could"`. A material probabilistic judgment MUST NOT use one
of these as its only likelihood expression (`ATS-EPI-007`).

A material point forecast MUST additionally carry the six §8.5 fields; in the IR they
live in `claim.forecast` (see §5 below).

---

## 3. Assessment confidence (§8.8, lexicon `assessment_confidence.terms`)

Exactly three levels. Confidence is robustness of the judgment, **not** the probability
of the event (§4.8, §8.8).

| `level` | lexicon definition |
|---|---|
| `low` | Materially fragile to plausible evidence, assumption, interpretation, or environmental changes. |
| `moderate` | Useful and generally coherent, but at least one material gap, assumption, limitation, or instability remains. |
| `high` | Robust to plausible updates because the basis is strong and major assumptions and contrary evidence are resolved or formally bounded. |

### The 9 basis dimensions (§8.9, lexicon `assessment_confidence.basis_dimensions`)

`assessment_confidence.basis` is required by the schema whenever `assessment_confidence`
is present, and **all nine dimensions plus `rationale` are required properties** of
`confidence_basis`. There is no partial basis object; an unknown dimension is spelled
`unknown` where the enum offers it.

| dimension | allowed values |
|---|---|
| `basis_type` | `empirical` `formal` `direct_observation` `expert_judgment` `mixed` |
| `evidence_quality` | `weak` `mixed` `strong` `unknown` |
| `evidence_coverage` | `narrow` `partial` `broad` `unknown` |
| `source_independence` | `single` `partially_independent` `independent` `not_applicable` `unknown` |
| `directness` | `indirect` `mixed` `direct` `unknown` |
| `consistency` | `conflicting` `mixed` `convergent` `unknown` |
| `assumption_sensitivity` | `high` `moderate` `low` `unknown` |
| `environmental_stability` | `volatile` `mixed` `stable` `not_applicable` `unknown` |
| `contrary_evidence` | `unaddressed` `addressed` `none_found` `not_searched` `not_applicable` `unknown` |

Plus `rationale`: a non-blank string (`minLength: 1`) explaining the displayed level.
`ATS-EPI-005` fails a material claim whose `rationale` is blank or whose dimensions are
all `unknown`. The vector is inspectable evidence for the scalar label and MUST NOT be
converted into an authoritative arithmetic score (§8.9).

`ATS-EPI-004` (§8.11) fails a `likelihood.display` that contains a confidence word, or a
probabilistic judgment whose only likelihood expression is an `assessment_confidence`.

---

## 4. Evidential and causal force

### Evidential force (§8.12, lexicon `evidential_force.terms`) — `claim.force.evidential`

| `evidential` | rendered phrase | lexicon definition |
|---|---|---|
| `consistent_with` | consistent with | Does not contradict but does not materially discriminate for the claim. |
| `suggests` | suggests | Weakly favors the claim with substantial alternatives, gaps, or noise. |
| `supports` | supports | Materially favors the claim over at least one live alternative. |
| `strongly_supports` | strongly supports | Multiple independent or highly discriminating lines favor the claim and important alternatives are substantially weaker. |
| `establishes` | establishes | Entails the claim under explicit assumptions, directly observes the complete condition, or supplies a valid formal demonstration. |

§8.12: "Proves" SHOULD be reserved for formal demonstration or logically exhaustive
evidence. §8.13 names five overclaim patterns: one compatible example described as
support; an observational association described as establishing causality; a green test
suite described as proving absence of defects; a model-generated explanation described as
independent evidence; and no contrary evidence found in a narrow search described as no
contrary evidence existing.

### Causal force (§8.14, lexicon `causal_force.terms`) — `claim.force.causal`

| `causal` | rendered phrase | lexicon definition |
|---|---|---|
| `associated_with` | associated with | Covaries or co-occurs without a causal claim. |
| `predicts` | predicts | Improves prediction in a declared setting without asserting causation. |
| `contributes_to` | contributes to | Has a causal role but is not independently sufficient. |
| `causes` | causes | An intervention changes the outcome under stated scope and assumptions. |
| `necessary_for` | necessary for | The outcome cannot occur under scope without the factor. |
| `sufficient_for` | sufficient for | The factor is enough to produce the outcome under scope. |

`causal_force.untyped_candidates` (§8.14) — replace or accompany with an explicit causal
relation when causality is material: `"drives"`, `"leads to"`, `"explains"`, `"powers"`,
`"results in"`.

§8.15: a material causal claim MUST state or reference its basis — randomized
intervention, quasi-experimental identification, controlled deterministic system
behavior, mechanistic proof, formal dependency, simulation under declared assumptions, or
expert judgment. `ATS-EVID-002` enforces non-empty `relation.basis_refs` for
discriminating and causal relation types.

---

## 5. Deontic force (§8.16, lexicon `deontic_force.terms`)

| `id` | rendered surface | lexicon definition |
|---|---|---|
| `MUST` | `MUST` | Absolute obligation within authority and scope. |
| `MUST_NOT` | `MUST NOT` | Absolute prohibition within authority and scope. |
| `SHOULD` | `SHOULD` | Defeasible recommendation requiring an explicit material reason to override. |
| `SHOULD_NOT` | `SHOULD NOT` | Defeasible discouragement requiring an explicit material reason to override. |
| `MAY` | `MAY` | Permission. |
| `CAN` | `CAN` | Capability, not permission or probability. |
| `CANNOT` | `CANNOT` | Lack of capability or logical impossibility, not prohibition. |
| `REQUIRED_BY` | `IS REQUIRED BY <source>` | Obligation attributed to an identified external authority. |

`deontic_force.noncanonical` (§8.16): `SHALL`, `SHALL NOT`. Nonconforming in ATS-1 output;
`ATS-DEON-001` fails a material proposition containing either.

**Two different enums, deliberately:**

| field | allowed values | consequence |
|---|---|---|
| `claim.force.deontic` | all eight ids above | a capability (`CAN`/`CANNOT`) or an external obligation (`REQUIRED_BY`) is expressible |
| `claim.requirement.deontic` | `MUST` `MUST_NOT` `SHOULD` `SHOULD_NOT` `MAY` — **only these five** | `CAN`/`CANNOT` cannot be a requirement slot, which is §9.3.13: "A capability statement MUST NOT satisfy a required-behavior slot" |

`external_authority` is required iff `force.deontic == "REQUIRED_BY"`, and forbidden
otherwise (schema `force.allOf`).

### The 4 collision rules (§8.17, lexicon `collision_rules`)

Each names a bare lowercase surface that is nonconforming when the intended force is
material, plus the readings it fails to discriminate.

| `id` | surface | disallowed ambiguities |
|---|---|---|
| `force-collision-may` | "may" | `permission`, `probability`, `capability` |
| `force-collision-should` | "should" | `recommendation`, `forecast`, `uncertainty` |
| `force-collision-will` | "will" | `forecast`, `design_description`, `obligation` |
| `force-collision-confidence` | "confidence" | `assessment_confidence`, `detector_confidence` |

§8.17 conforming alternatives, each selecting exactly one type:
`The verifier MUST reject the receipt.` (obligation) ·
`The verifier MAY reject the receipt.` (permission) ·
`The verifier can reject the receipt.` (capability) ·
`The verifier is likely (55–80%) to reject the receipt.` (probability) ·
`Policy X requires the verifier to reject the receipt.` (external obligation).

`force-collision-confidence` is why §13.5 requires the machine field name
`detector_confidence` and forbids labelling it merely `confidence` anywhere assessment
confidence also appears.

---

## 6. Claim roles (§7.4) — the schema `role` enum

Twelve values: `definition`, `observation`, `sourced_report`, `assumption`, `inference`,
`judgment`, `forecast`, `recommendation`, `requirement`, `exception`, `boundary`,
`open_question`.

The thirteen author-facing epistemic/normative roles map on as follows. **Permission and
capability are deontic force values, not roles.**

| author-facing role | `role` | force field |
|---|---|---|
| observation | `observation` | no `likelihood`, no `assessment_confidence` (`ATS-EVID-001`) |
| sourced report | `sourced_report` | no `likelihood`, no `assessment_confidence`; `source_refs` names the source (§7.10) |
| assumption | `assumption` | no `evidential` when `status: asserted` (`ATS-EVID-001`) |
| inference | `inference` | `derived_from` relation to its premises (§7.11) |
| judgment | `judgment` | `likelihood` when probabilistic + `assessment_confidence` + `basis` |
| forecast | `forecast` | `likelihood` + the `forecast` slot object (§9.2.11) |
| recommendation | `recommendation` | no `evidential` (`ATS-EVID-001`, §9.2.10) |
| requirement | `requirement` | `force.deontic` ∈ {`MUST`,`MUST_NOT`,`SHOULD`,`SHOULD_NOT`,`MAY`,`REQUIRED_BY`} + the `requirement` slot object |
| **permission** | `requirement` | `force.deontic: MAY` and `requirement.deontic: MAY` (§9.3.12) |
| **capability** | *not* `requirement` — use `observation`, `definition`, or `judgment` as the material fact warrants | `force.deontic: CAN` or `CANNOT` (§9.3.13; `requirement.deontic` has no `CAN`) |
| exception | `exception` | referenced from `claim.exception_refs`, or an `exception_to` relation |
| boundary | `boundary` | referenced from `claim.boundary_refs`, or a `qualifies` relation |
| open question | `open_question` | `status: unresolved` (§7.5) |

The thirteenth schema role, `definition`, establishes the meaning of a term within a scope
(§7.4) and is the IR home for glossary-bearing prose.

§7.4: a claim MAY have secondary tags, but MUST NOT use multiple primary roles to conceal
a transition from observation to inference or from judgment to recommendation.

---

## 7. Other closed enums the IR uses

| enum | values | source |
|---|---|---|
| `extraction_status` | `complete` `partial` `ambiguous` `unavailable` | §7.16 |
| `extraction_issues[].status` | `partial` `ambiguous` `unavailable` | schema |
| `claim.status` | `asserted` `ambiguous` `unresolved` `withdrawn` `superseded` | §7.5 |
| `claim.polarity` | `positive` `negative` | §7.8 |
| `quantifier.kind` | `none` `one` `some` `at_least_one` `most` `all` `exact_count` `minimum` `maximum` `range` `proportion` `unspecified` | §7.7 |
| `evidence.availability`, `source.availability` | `present` `not_found` `not_searched` `unavailable` `withheld` `not_applicable` | §7.9 |
| `source.source_type` | `direct_observation` `test` `benchmark` `repository_artifact` `external_source` `model_output` `human_report` `formal_derivation` `simulation` `synthetic_fixture` `policy` `other` | §7.10 |
| `relation.type` | `consistent_with` `supports` `strongly_supports` `contradicts` `qualifies` `depends_on` `condition_for` `exception_to` `derived_from` `associated_with` `predicts` `contributes_to` `causes` `necessary_for` `sufficient_for` `contrasts_with` `alternative_to` `updates` `reverses` | §7.11 |
| `update_indicator.effect` | `increase_likelihood` `decrease_likelihood` `change_confidence` `invalidate_assumption` `activate_exception` `reverse_recommendation` `reevaluate` | §7.14 |
| `audience.expertise` | `novice` `practitioner` `expert` `mixed` | §7.2 |
| `forecast.outcome_status` | `open` `resolved_true` `resolved_false` `void` `ambiguous` | §9.2.11 |
| `profile` | `ASSESS` `SPECIFY` `TRANSFORM`, or an extension matching `^(X-[A-Z0-9]+-[A-Z0-9-]+\|ATS-X-[A-Z0-9]+-[A-Z0-9-]+)$` | §3.2, §3.3, §9.5 |
| `rule_state` | `disabled` `shadow` `advisory` `required` | §6.2 |
| `conformance_status` | `PASS` `FAIL` `NOT_APPLICABLE` `UNAVAILABLE` `INSUFFICIENT_EVIDENCE` | §5.2 |

Relations are directional; a transformation MUST NOT reverse relation direction (§7.11).

Scope fields (§7.6, schema `scope`): `population`, `system`, `environment`, `condition`,
`exclusions`, `time_horizon`, `authority_domain`, `version`, `evidence_window`,
`unknown_fields`. **An unknown scope field MUST be represented as unknown** — list it in
`unknown_fields`; omitting it in a way that implies universal scope is nonconforming
(§7.6).

§7.8 forbids collapsing these six states: absence of evidence for a claim; evidence
against a claim; evidence establishing the negation; a search that found none; a search
not performed; evidence unavailable.

---

## 8. `ASSESS` required slots

### §9.2.2 — required document-level slots

An `ASSESS` artifact MUST contain:

1. the analytic question or decision context;
2. one or more key judgments;
3. the scope and time horizon;
4. the evidence base or its availability state;
5. material assumptions;
6. material boundaries;
7. material contrary evidence or the exact search state;
8. update indicators for each material judgment; and
9. a separation between judgments and recommendations.

A heading MAY provide a slot when its meaning is unambiguous, but headings alone do not
satisfy evidence or basis obligations (§9.2.2).

### §9.2.4 — material assessment object

Every material judgment or forecast MUST contain or reference:

1. a proposition;
2. scope;
3. time horizon when temporally bounded;
4. likelihood when the proposition is probabilistic;
5. assessment confidence;
6. confidence basis;
7. supporting evidence;
8. contrary evidence or search state;
9. assumptions;
10. boundaries;
11. live alternatives when materially plausible; and
12. update indicators.

A non-probabilistic judgment (formal entailment, direct deterministic conclusion) MAY omit
a WEP but MUST state the basis that makes likelihood inapplicable (§9.2.4).

### §9.2.12 — canonical rendering order

`Question` · `Key judgment` · `Likelihood` · `Confidence and basis` ·
`Supporting evidence` · `Contrary evidence and alternatives` · `Assumptions` ·
`Boundary` · `Update indicators` · `Recommendation or next discriminating test`.

Headings are not all required "when the artifact remains clear" (§9.2.12).

### §9.2.13 — profile completeness

`profile: PASS` requires: all material judgments have the §9.2.4 slots; missing
information uses exact availability states; likelihood and confidence are distinct;
assumptions and contrary evidence are not presented as established facts; and
recommendations are distinguishable from judgments. An unresolved missing material slot
produces `profile: FAIL`; a detector incapable of evaluating a required slot produces
`profile: UNAVAILABLE`.

### Supporting `ASSESS` obligations

- §9.2.3 — the first material key judgment SHOULD precede extended background.
- §9.2.6 — every material evidence item MUST have a source locator, content hash,
  execution receipt, or explicit `unavailable` state. A model's analysis of evidence is
  an inference or judgment, never an independent evidence line.
- §9.2.7 — distinguish: found-and-addressed; found-and-unresolved; a defined search found
  none; no search performed; relevant evidence unavailable; not applicable because the
  claim is formally entailed. "No contrary evidence" is conforming only when the search or
  proof domain is bounded and referenced.
- §9.2.8 — identify materially plausible alternatives when they would change action or
  confidence; an alternative MAY be omitted only under one of the four stated grounds.
- §9.2.9 — for each material assumption bridging an evidence gap, state the consequence if
  false.
- §9.2.10 — a recommendation is advice, not an observed consequence of the evidence.
- §9.2.11 — a material forecast MUST include a resolvable outcome definition, probability
  or WEP, resolution date or event, resolution source, update policy, forecast identifier,
  and outcome status once resolved. The IR's `forecast_slots` requires `forecast_id`,
  `outcome_definition`, `resolution`, `resolution_source`, `update_policy`,
  `outcome_status`.

---

## 9. `SPECIFY` required slots

### §9.3.2 — requirement object

Every material requirement MUST have a stable identifier and these slots:

| slot | §9.3.2 gloss | schema |
|---|---|---|
| `requirement_id` | stable identifier | required |
| `actor` | the entity responsible for satisfying the requirement | required, `minLength: 1` |
| `deontic` | `MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, or `MAY` | required |
| `action` | the required behavior | required, `minLength: 1` |
| `object` | the entity acted on or result produced | required, `minLength: 1` |
| `scope` | the system, version, authority domain, or population to which it applies | optional string |
| `trigger` | the event that activates it, when applicable | optional |
| `condition` | the state in which it applies, when applicable | optional |
| `timing` | deadline, ordering, frequency, or duration, when material | optional |
| `constraints` | quantitative or qualitative bounds, when applicable | optional array |
| `exceptions` | exact defeat conditions, when applicable | optional array |
| `acceptance_criterion` | observable evidence that determines satisfaction | optional in schema, **required by §9.3.9 for every `MUST`/`MUST_NOT`** |
| `source_authority` | the authority creating or imposing the obligation | required, `minLength: 1` |
| `rationale` | optional non-normative explanation, stored separately | optional |
| `indivisible_actions_justification` | documents §9.3.3 indivisibility | optional |

§9.3.2: a slot that is not applicable MAY be omitted. **A slot that is applicable but
unknown MUST be marked unknown and prevents profile conformance.** `ATS-REQ-003` treats
any slot value equal to `"unknown"` as a violation.

### §9.3.5 — canonical statement order

```text
[scope] [trigger] [condition] <actor> <DEONTIC> <action> <object> [timing] [constraints].
```

Recommended forms: `The <actor> MUST <action> <object>.` ·
`When <trigger>, the <actor> MUST <action> <object>.` ·
`While <condition>, the <actor> MUST <action> <object>.` ·
`If <undesired event>, the <actor> MUST <protective action>.` ·
`Within <duration> after <trigger>, the <actor> MUST <action> <object>.` ·
`The <actor> MAY <action> <object> only when <permission boundary>.`

Canonical order is a rendering convention, **not** a substitute for structured slots
(§9.3.5).

### §9.3.20 — profile completeness

`profile: PASS` requires: each material requirement has a stable identifier; each has one
obligation; actor and deontic force are explicit; applicable trigger, condition, timing,
boundary, and exception slots are resolved; each `MUST` and `MUST NOT` has a verifiable
acceptance criterion; rationale is separated; and no unresolved set-level contradiction is
known.

### Supporting `SPECIFY` obligations

- §9.3.3 — one obligation per requirement. Two actions MAY share one requirement only when
  they are simultaneous parts of one indivisible behavior sharing one acceptance
  criterion, and the requirement MUST document that indivisibility.
- §9.3.4 — the actor MUST be explicit; a pronoun or passive construction MUST NOT conceal
  it. `ATS-REQ-001` rejects `"it"`, `"this"`, `"that"`, `"they"`, `"the system"`,
  `"system"`.
- §9.3.6 — a trigger is an event; a condition is a state. Not interchangeable.
- §9.3.7 — a material timing requirement MUST state an observable boundary.
  `"promptly"`, `"soon"`, `"regularly"`, `"eventually"` are nonconforming when timing is
  material and no policy defines them quantitatively.
- §9.3.8 — a threshold or range MUST identify value, unit, comparator, inclusivity or
  exclusivity when ambiguous, measurement window, and aggregation method when material.
- §9.3.9 — `"works correctly"` and `"is robust"` are not acceptance criteria.
- §9.3.11 — a `SHOULD`/`SHOULD_NOT` requirement MUST identify why exceptions may be valid
  or link to an override policy. `SHOULD` MUST NOT be used merely because the author is
  uncertain whether the requirement matters; uncertainty belongs in an `ASSESS` claim.
- §9.3.12 — a `MAY` statement MUST identify the permitted actor, permitted action,
  boundary of permission, and any conditions or prohibitions that still apply. Permission
  does not imply capability.
- §9.3.15 — an obligation imposed by another authority MUST identify that authority; the
  current document MUST NOT silently restate it as if it originated locally.
- §9.3.16 — rationale, examples, implementation notes, and recommendations MUST be
  distinguishable from normative requirement text, and a rationale MUST NOT introduce a
  hidden requirement.
- §9.3.18 — requirement identifiers MUST be unique within their authority domain and MUST
  NOT be reused for a materially different obligation. A superseded requirement MUST
  retain a link to its successor.

### §9.4 — composition

An artifact MAY compose profiles at section level. A recommendation in `ASSESS` does not
become a requirement until adopted in `SPECIFY` or by an identified external authority.

---

## 10. Preservation classes

### P0 — exact protected fields (§11.3.1), when material

named entities and referent identity · identifiers and code symbols · numbers, units,
signs, precision, and denominators · dates, durations, and time horizons · polarity and
negation · quantifier kind and value · probability points and bands ·
assessment-confidence level · deontic force · authority attribution · source attribution ·
conditions and exceptions · thresholds and comparator boundaries · requirement identifiers
· version and revision identifiers · acceptance criteria.

A P0 field MUST remain exact unless the transformation includes an explicit authorized
semantic change (§11.3.1, §11.4).

### P1 — protected relations (§11.3.2), when material

support and contradiction · qualification · dependency · condition and exception · causal
direction and force · comparison dimension · alternative-hypothesis relationships · update
and reversal · inference provenance · ordering dependencies.

P1 wording MAY change. The relation's **type, direction, scope, and force MUST remain
recoverable** (§11.3.2).

### P2 — surface realization (§11.3.3)

sentence boundaries · paragraph boundaries · heading wording · list versus prose rendering
· approved lexical substitution · deletion of functionless repetition · punctuation ·
local ordering that does not change dependencies · other presentation choices not covered
by P0 or P1.

P2 MAY be optimized freely under active surface rules (§11.3.3).

### Semantic delta classes (§11.5)

`preserved` `omitted` `added` `weakened` `strengthened` `contradicted` `scope_changed`
`polarity_changed` `quantifier_changed` `likelihood_changed` `confidence_changed`
`evidential_force_changed` `causal_force_changed` `deontic_force_changed`
`source_attribution_changed` `authority_changed` `condition_changed` `exception_changed`
`relation_changed` `ambiguous_after_transform` `authorized_change`.

### Non-strengthening (§11.6) — nine named strengthening moves

moving to a higher likelihood band · increasing assessment confidence · changing
"consistent with" to "supports" · changing association to causation · changing `SHOULD` to
`MUST` · changing "some" to "all" · deleting a condition or exception · removing source
attribution so a report appears directly verified · turning an assumption into a fact.

§11.7: a rewrite, copyedit, compression, or simplification MUST NOT add a material claim
absent from the source or an authorized external evidence object.

§8.18: a transformation MUST NOT silently change a likelihood band or point probability, an
assessment-confidence level, an evidential-force term, a causal relation, a deontic term,
or the authority source of an obligation.

---

## 11. Surface term lists enumerated verbatim in the spec

A detector or renderer may only match against the force lexicon, a list enumerated
verbatim in `ATS-1_SPEC.md`, or declared glossary content in the IR (spec §5.6 discipline;
inventing a keyword list is prohibited).

| list | values | section |
|---|---|---|
| relative-time terms | "today", "currently", "recently", "soon", "later", "next", "the latest" | §10.11 |
| empty intensifiers | "clearly", "obviously", "simply", "just", "very", "really", "quite" | §10.20 |
| vague evaluative terms | "significant", "large", "small", "meaningful", "material", "robust", "fast", "safe", "reliable" | §10.21 |
| vague timing terms | "promptly", "soon", "regularly", "eventually" | §9.3.7 |
| concealing actors | "it", "this", "that", "they", "the system", "system" | §9.3.4 |
| vacuous acceptance criteria | "works correctly", "is robust" | §9.3.9 |
| protected contrast markers | "but", "only", "unless", "despite" | §10.22, Appendix A |

Content classes that Section 5.6 exempts from surface rules **only when the region is
marked**: `quotation`, `code`, `log`, `schema`, `counterexample`. The trace's
`content_class` enum also offers `prose` and `table`, which are not exempt.

---

## 12. Conformance vector (§5.2, §15.x)

Five dimensions, never averaged into a scalar (§5.2, §15.6):
`mechanical`, `profile`, `semantic_review`, `preservation`, `forecast_calibration`.

- §5.4 — a required check that cannot execute is `UNAVAILABLE`, not `PASS`.
- §15.3 / §14.11 — final authority for semantic acceptance belongs to an authorized human
  or an explicitly governed external acceptance system. This implementation holds none, so
  `semantic_review` is always `UNAVAILABLE` here.
- §15.5 / §9.2.11 — `forecast_calibration` is `INSUFFICIENT_EVIDENCE` until enough resolved
  forecasts exist for a declared scoring procedure and uncertainty interval.
- §20.6 — `UNAVAILABLE` and `INSUFFICIENT_EVIDENCE` are valid outcomes. A system MUST
  prefer a typed insufficiency to an unsupported pass, confident rewrite, or guessed
  interpretation.

§20.5 fail-closed conditions: policy currentness unknown · source hashes do not match ·
required schemas cannot be validated · required parsing fails · a required detector is
unavailable · material P0 or P1 deltas unresolved · a required finding unresolved ·
authority for an exception or adjudication cannot be established.

---

## 13. Canonical serialization (Appendix C)

Content-addressed objects MUST: omit the object's own hash field from the hash input;
serialize the remaining object with RFC 8785 JCS; hash the canonical bytes with SHA-256;
encode the digest as lowercase hexadecimal; and prefix identifiers with the object type
when used as human-facing IDs (e.g. `ats-policy-sha256:4f23…`).

Binary attachments MUST be hashed over their exact bytes. **A text normalization step MUST
produce and retain a separate normalized hash rather than replacing the source hash**
(Appendix C, §14.2).

`schema_version` values (Appendix B) used by this workflow: `ats.text_ir.v1`,
`ats.policy_snapshot.v1`, `ats.force_lexicon.v1`, `ats.acceptance_receipt.v1`,
`ats.retention_contract.v1`, `ats.preservation_report.v1`, `ats.capability.v1`.
Repo-local: `ats.output_trace.v1`, `ats.ir_lint_report.v1`, `ats.output_lint_report.v1`.

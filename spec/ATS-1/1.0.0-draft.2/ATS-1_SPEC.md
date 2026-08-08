# ATS-1: Arq Text Standard

## Normative Specification for Concept-Preserving Technical and Analytic Text

| Field | Value |
|---|---|
| Standard identifier | `ATS-1` |
| Specification version | `1.0.0-draft.2` |
| Status | Working Draft |
| Date | 2026-08-02 |
| Language | English |
| Stable profiles in this edition | `ASSESS`, `SPECIFY` |
| Cross-cutting conformance profile | `TRANSFORM` |
| Reserved profile identifiers | `EXPLAIN`, `DECIDE`, `EXECUTE`, `DELTA`, `EXPLORE` |
| Machine schemas | JSON Schema Draft 2020-12 |
| Canonical serialization | JSON Canonicalization Scheme (JCS), RFC 8785 |
| Package license | Unspecified in this draft |

---

## Abstract

ATS-1 defines a text standard for technical and analytic artifacts whose correctness depends on preserving distinctions, qualifications, evidence relationships, calibrated uncertainty, causal force, and normative force.

ATS-1 does not optimize prose for short sentences in isolation. It optimizes for the reader's ability to:

1. locate the load-bearing statement;
2. reconstruct the writer's model;
3. distinguish observation from inference and judgment;
4. interpret probability, confidence, evidence, causality, and obligation correctly;
5. verify the basis of material claims; and
6. act without recovering omitted conditions, exceptions, or scope from context.

The standard defines:

- a typed semantic intermediate representation;
- profile-specific content obligations;
- controlled vocabularies for calibrated force;
- deterministic and semantic lint rules;
- preservation classes for rewrites and summaries;
- policy, exception, finding, adjudication, and receipt objects;
- non-compensatory conformance claims; and
- authority boundaries between detectors, repair systems, verifiers, and human adjudicators.

ATS-1 is intended to support human authors, AI writing systems, linters, small specialized language models, editors, CI gates, and Arq acceptance workflows.

---

## 1. Status and document authority

### 1.1 Working Draft status

This document is a complete candidate specification for the ATS-1 normative kernel. Its status is **Working Draft** until the corpus, detector fixtures, and implementation trials establish that the rules are sufficiently precise and useful for ratification.

Downstream implementations MAY target this draft. They MUST record the exact specification version and policy snapshot used. They MUST NOT claim conformance to a later ATS-1 edition without revalidation.

### 1.2 Normative package

The ATS-1 package consists of:

- `ATS-1_SPEC.md` — normative semantics and conformance requirements;
- `schemas/*.schema.json` — normative object structure;
- `rules/ats_rules_v2.yaml` — normative rule registry and default rule states;
- `lexicons/ats_force_lexicon_v1.yaml` — normative calibrated-force vocabulary;
- `examples/*` — informative worked examples unless an example explicitly states that it is a conformance fixture;
- `schemas/ats_package_manifest_v1.schema.json` — the normative package-manifest structure;
- `MANIFEST.json` — content hashes and byte lengths for every package file other than the manifest itself; and
- `requirements-validation.txt` and `tools/validate_package.py` — informative reference-validation dependencies and tooling.

A package is internally valid only when these artifacts agree. An implementation that detects a contradiction among normative package artifacts MUST report `UNAVAILABLE` and MUST NOT select one interpretation silently.

### 1.3 Normative language

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** in this document are to be interpreted as normative requirement levels when, and only when, they appear in uppercase.

ATS-1 additionally defines:

- **CAN** and **CANNOT** as statements of capability, not permission or probability;
- **IS REQUIRED BY _source_** as attribution of an external obligation; and
- **ADVISORY** as a finding that requires disposition when semantic review is claimed but does not independently block mechanical conformance.

Lowercase forms have their ordinary English meanings and carry no ATS-1 normative force. Authors SHOULD avoid lowercase modal words in normative sections when they can be mistaken for ATS-1 terms.

### 1.4 Originality and external standards

ATS-1 is an original specification. External standards and research informed its design, but their text, dictionaries, and rule sets are not incorporated by reference. An ATS-1 implementation MUST NOT represent itself as an ASD-STE100, INCOSE, ISO, IETF, intelligence-community, or other third-party conformant implementation unless it separately satisfies that standard's requirements and licensing terms.

---

## 2. Purpose

### 2.1 Governing objective

ATS-1 governs the recovery cost of meaning, not sentence simplicity alone.

For design and evaluation, implementations SHOULD treat reader cost as a vector:

```text
reader_cost = navigation_cost
            + parsing_cost
            + model_reconstruction_cost
            + verification_cost
            + action_selection_cost
```

The components are not freely compensatory. A rewrite that lowers parsing cost but removes a reversal condition has failed even if readers prefer its surface style.

> **Draft.2 amendment (D-A):** ATS-1 is a controlled technical discourse standard for
> transferring operative models between reasoning systems while preserving human
> inspectability. Its primary objective is not linguistic simplicity. Its primary
> objective is faithful, low-cost recovery of the distinctions required to understand,
> verify, continue, decompose, or act on a model.

**Semantic recovery cost** is the principal concept of this standard: the cost of
recovering the operative model from an artifact across the reader-cost components above.
The components MUST NOT be treated as freely compensatory, and a sentence-level
readability improvement MUST NOT justify material semantic loss. (Amendment D-A; see the
migration table in the package CHANGELOG.)

### 2.2 Core invariant

An ATS-1 transformation MUST preserve every distinction that can materially change interpretation, action, prioritization, risk, compliance, acceptance, or confidence, except where an explicit retention contract authorizes omission.

### 2.3 Design principles

ATS-1 follows these principles:

1. **Meaning before surface.** Prose is a rendering of a typed meaning model, not the sole source of truth when a structured representation is available.
2. **Profile before style.** The reader's job determines required discourse structure and permissible surface controls.
3. **One force, one type.** Probability, assessment confidence, evidential force, causal force, and deontic force are represented separately.
4. **Stable terms.** One concept uses one canonical term within a declared scope unless a deliberate contrast requires otherwise.
5. **Exact insufficiency.** `Unknown`, `not searched`, `not found`, `ambiguous`, and `not applicable` are distinct states.
6. **Non-compensatory acceptance.** Readability, semantic fidelity, calibrated force, requirement quality, and evidence quality are separate conformance dimensions.
7. **Determinism where available.** Closed-form checks run before model-based criticism.
8. **Bounded semantic review.** Semantic findings are prioritized to minimize reviewer burden without suppressing guardrail findings.
9. **Separation of authority.** A detector proposes; an adjudicator disposes; a repair system proposes a patch; an independent verifier evaluates the patch.
10. **Evidence-backed change.** A rewrite is accepted on preservation evidence, not fluency or aesthetic preference alone.

---

## 3. Scope

### 3.1 In scope

ATS-1 applies to English-language technical and analytic artifacts, including:

- engineering specifications;
- RFCs and architecture decisions;
- analytic assessments;
- investigation reports;
- acceptance findings and receipts;
- implementation contracts;
- policy documents;
- AI-generated technical explanations;
- summaries and rewrites of those artifacts; and
- structured representations used to lint or render those artifacts.

### 3.2 Stable profiles

This edition fully specifies two reader-task profiles:

- `ASSESS`: communicate a material judgment under uncertainty; and
- `SPECIFY`: state an obligation, permission, prohibition, capability boundary, or acceptance condition so that it can be implemented and verified.

The cross-cutting `TRANSFORM` profile applies when one artifact is derived from another through editing, compression, rewriting, summarization, or reformatting.

### 3.3 Reserved profiles

The following identifiers are reserved for future ATS editions or registered extensions:

- `EXPLAIN`
- `DECIDE`
- `EXECUTE`
- `DELTA`
- `EXPLORE`

An implementation MAY experiment with these profiles but MUST namespace them as extensions and MUST NOT claim core ATS-1 profile conformance for them.

### 3.4 Out of scope

ATS-1 is not:

- a universal restricted vocabulary;
- a global sentence-length standard;
- a factual truth oracle;
- a replacement for source validation, experimentation, or domain review;
- a single readability or quality score;
- a requirement that all technical prose use elementary vocabulary;
- a mandate to use active voice in every sentence;
- a mandate to remove all repetition;
- a complete formal logic for arbitrary natural language;
- a license to omit complexity that remains material to the reader's task; or
- an authority for accepting its own model-generated repairs.

### 3.5 Relationship to domain standards

A domain standard MAY impose stricter or additional rules. ATS-1 policy resolution MUST preserve the stricter obligation unless a typed conflict is recorded and adjudicated.

A domain-approved technical term takes precedence over a simpler but less precise substitute.

---

## 4. Definitions

For ATS-1, the following terms have the specified meanings.

### 4.1 Artifact

A bounded body of text and metadata evaluated under one content hash and policy snapshot.

### 4.2 Section

A contiguous artifact region with an explicit or inherited profile, audience, and rule scope.

### 4.3 Profile

A named set of semantic slots, ordering constraints, and rule defaults tied to a reader task.

### 4.4 Claim

A proposition represented as a typed semantic object. A claim has a role, scope, polarity, materiality, and optional force and provenance fields.

### 4.5 Material

A claim, field, relation, omission, or ambiguity is **material** when a reasonable change to it could alter at least one of:

- a decision or action;
- acceptance or conformance;
- risk, safety, security, or compliance;
- interpretation of evidence or causality;
- priority or resource allocation;
- a forecast or expectation;
- the applicability boundary of another claim; or
- the reader's confidence in a key judgment.

### 4.6 Evidence

Information offered as a basis for accepting, rejecting, qualifying, or updating a claim.

### 4.7 Assessment

A judgment that extends beyond direct observation and is stated with explicit scope and, when probabilistic, calibrated likelihood.

### 4.8 Assessment confidence

The robustness of an assessment to plausible changes in evidence, assumptions, interpretation, and environmental conditions. Assessment confidence is not the probability that the assessed event occurs.

### 4.9 Detector confidence

A detector's estimate that a finding applies. Detector confidence is implementation metadata and MUST NOT be presented as assessment confidence in the analyzed artifact.

### 4.10 Word of estimative probability

A controlled phrase whose ATS-1 meaning corresponds to a declared probability interval.

### 4.11 Deontic force

The type and strength of an obligation, prohibition, recommendation, permission, or capability statement.

### 4.12 Evidential force

The degree to which evidence discriminates in favor of a claim relative to live alternatives.

### 4.13 Causal force

The relationship asserted between variables or events, such as association, prediction, contribution, cause, necessity, or sufficiency.

### 4.14 Meaning ledger

The typed representation of claims, relations, force, scope, provenance, assumptions, boundaries, and update indicators extracted from or used to generate an artifact.

### 4.15 P0 field

A protected exact field whose unauthorized change blocks transformation-preservation conformance.

### 4.16 P1 relation

A protected semantic relation that MAY be rephrased but MUST remain recoverable with the same force and direction.

### 4.17 P2 surface

A presentation choice that MAY be optimized freely when P0 and P1 obligations remain satisfied.

### 4.18 Finding

A rule-scoped assertion that a text span or semantic object violates, may violate, or fails to establish conformance with an ATS-1 rule.

### 4.19 Adjudication

An authorized disposition of a finding as accepted, rejected, waived, deferred, or unresolved.

### 4.20 Policy snapshot

A content-addressed resolution of standard version, profiles, audience, glossary, rule states, exceptions, budgets, and detector artifacts.

### 4.21 Retention contract

A declaration of the source claims, fields, and relations that a deliberately lossy transformation, such as a summary, MUST preserve.

### 4.22 Conformance receipt

A content-addressed record of the source, policy, implementation, checks, findings, adjudications, preservation evidence, and resulting conformance vector.

> **Draft.2 amendments (D-C, D-D, D-F):**

### 4.23 Stable semantic coordinate

A machine-stable identifier whose loss can break joins among specification, planning, task decomposition, acceptance criteria, implementation, tests, review, receipts, postmortems, and later amendments. A stable semantic coordinate is distinct from a semantic proposition: a proposition MAY remain recoverable through another coordinate while its own coordinate is lost.

The protected coordinate kinds are: `requirement_id`, `decision_id`, `acceptance_criterion_id`, `work_item_id`, `protocol_id`, `protocol_version`, `dependency_target`, and explicit cross-document authority reference.

### 4.24 Local semantic closure

A unit is locally closed when its operative meaning can be recovered from the unit plus explicitly declared dependencies, without requiring undeclared document-wide inference.

### 4.25 Semantic basis

A declared account of how a semantic value was established. The basis vocabulary is:

| Value | Definition |
|---|---|
| `EXPLICIT` | The authoritative source or explicit author intent directly states the semantic value. |
| `DERIVED` | The value follows mechanically from explicit structure without substantive interpretive judgment. |
| `INFERRED` | A competent reader or model can reasonably infer the value, but the source does not establish it uniquely or normatively. |
| `UNAVAILABLE` | The value cannot be established from the available source or author intent. |
| `AUTHOR_JUDGMENT` | The ATS authoring process intentionally introduces a new judgment, recommendation, design choice, or requirement under the authority granted for new authoring. This is distinct from extracting source truth. |

---

## 5. Conformance model

### 5.1 Conformance subjects

ATS-1 defines conformance for four subject types:

1. **Artifact conformance** — whether one artifact satisfies its declared profile and rules.
2. **Transformation conformance** — whether an output preserves the required meaning of a source or retention contract.
3. **Implementation conformance** — whether a tool executes declared ATS-1 capabilities correctly and reports unsupported checks honestly.
4. **Policy conformance** — whether policy resolution, exceptions, and rule-state changes follow ATS-1 precedence and authority rules.

### 5.2 Conformance is a vector

An implementation MUST NOT reduce ATS-1 conformance to one scalar score.

The canonical conformance dimensions are:

| Dimension | Meaning |
|---|---|
| `mechanical` | All required deterministic checks executed and passed. |
| `profile` | Required semantic slots and profile structure are present. |
| `semantic_review` | All surfaced semantic findings within the declared review scope were dispositioned. |
| `preservation` | A transformation preserved its source or retention contract. |
| `forecast_calibration` | Sufficient resolved forecasts support an empirical calibration claim. |

Each dimension has one of these statuses:

- `PASS`
- `FAIL`
- `NOT_APPLICABLE`
- `UNAVAILABLE`
- `INSUFFICIENT_EVIDENCE`

### 5.3 No bare conformance claim

A producer MUST NOT state only that an artifact is “ATS-1 compliant.” A conformance claim MUST include:

- the ATS-1 specification version;
- the applied profile or profiles;
- the policy snapshot identifier;
- the conformance vector; and
- the receipt identifier when a receipt exists.

Example:

```text
ATS-1 1.0.0-draft.1 / ASSESS
Mechanical: PASS
Profile: PASS
Semantic review: PASS
Preservation: NOT_APPLICABLE
Forecast calibration: INSUFFICIENT_EVIDENCE
Receipt: ats-receipt-4f23…
```

### 5.4 Required check failure semantics

A required check that cannot execute is `UNAVAILABLE`, not `PASS`.

If any required check is `FAIL` or `UNAVAILABLE`, the corresponding conformance dimension MUST NOT be `PASS`.

### 5.5 Partial implementations

An implementation MAY support only part of ATS-1. It MUST publish a machine-readable capability declaration that identifies:

- supported profiles;
- supported rules;
- detector class per rule;
- autofix capability;
- preservation capability;
- schema versions; and
- known limitations.

Unsupported rules MUST be reported as `UNAVAILABLE` when required by the active policy.

### 5.6 Examples and quoted material

Quoted source text, code, logs, schemas, and deliberate counterexamples MAY be exempt from surface rules. The enclosing artifact MUST mark the region's content class so that an implementation does not silently exempt ordinary prose.

Semantic claims made about quoted material remain in scope.

---

## 6. Policy resolution

### 6.1 Policy layers

ATS-1 policy is resolved through these layers, from least to most specialized:

1. ATS-1 standard defaults;
2. profile defaults;
3. organization policy;
4. repository or project policy;
5. artifact policy; and
6. exact scoped exceptions.

### 6.2 Rule-state lattice

Rule states form this ordered lattice:

```text
disabled < shadow < advisory < required
```

- `disabled`: the rule does not run.
- `shadow`: the rule runs and records metrics but does not surface findings to ordinary authors.
- `advisory`: findings surface and require disposition for semantic-review conformance.
- `required`: unresolved findings block the associated conformance dimension.

A more specialized policy MAY strengthen a rule by moving it upward in the lattice.

A more specialized policy MUST NOT weaken a rule without an exact `TextPolicyExceptionV1`.

### 6.3 Policy exceptions

A policy exception MUST contain:

- the rule identifier;
- the original and replacement states;
- the exact artifact, path, section, or claim scope;
- a rationale;
- the authorizing identity;
- creation time;
- expiration time or explicit non-expiring justification;
- evidence or issue references; and
- a content hash.

An exception MUST NOT apply outside its declared scope.

An expired exception is invalid. A linter MUST re-evaluate the original rule state after expiration.

### 6.4 Unwaivable claims

An implementation MUST NOT report `preservation: PASS` when either `ATS-PRES-001` or `ATS-PRES-002` is disabled, unavailable, failed, or waived for a material retained claim.

A policy MAY allow the transformation to proceed, but the result is not ATS-1 preservation-conformant.

### 6.5 Profile resolution

Every artifact section MUST resolve to at least one content profile.

When multiple profiles apply:

- all non-conflicting requirements accumulate;
- the stricter rule state applies;
- a conflict MUST produce a typed policy conflict; and
- the implementation MUST NOT select a winner by heuristic probability.

### 6.6 Content-addressed policy

A policy snapshot MUST be serialized with JCS and hashed with SHA-256.

`snapshot_sha256` is the normative content address. It MUST be derived from the canonical bytes after omitting only `snapshot_sha256` itself. `snapshot_id` is an opaque stable identifier and MAY be human-readable or digest-derived; it MUST NOT substitute for the content hash in a conformance decision.

A receipt MUST bind both the declared `snapshot_id` and the exact `snapshot_sha256` used during evaluation. Two snapshots with the same `snapshot_id` and different hashes are distinct policy versions and MUST trigger stale-policy handling.


---

## 7. ATS-1 semantic model

### 7.1 Artifact model

A `TextIRV1` artifact MUST contain:

- an artifact identifier;
- the source content hash and media type;
- the policy snapshot identifier;
- a language identifier;
- audience metadata;
- one or more profiled sections;
- zero or more glossary entries;
- extraction status; and
- any extraction ambiguities or unavailable fields.

A structured representation MUST preserve source spans when the source format permits stable offsets. When stable character offsets are not available, the representation MUST use a deterministic locator such as a JSON Pointer, Markdown block identifier, XML path, page-line locator, or syntax-tree node path.

### 7.2 Audience model

Audience metadata MUST declare:

- expertise: `novice`, `practitioner`, `expert`, or `mixed`;
- reader task through the applied profile;
- assumed glossary or term base;
- language or locale constraints when relevant; and
- any accessibility or scanning constraints used to specialize policy.

An implementation MUST NOT infer that a term is understood merely because it appears frequently in the source corpus. Audience assumptions require policy or artifact evidence.

### 7.3 Section model

Each section has:

- a stable section identifier;
- source span or locator;
- one or more profiles;
- inherited or local audience policy;
- claims;
- evidence objects;
- semantic relations;
- update indicators; and
- optional display metadata.

A section boundary MAY follow a document heading, but semantic sectioning is not required to match visual heading boundaries exactly.

### 7.4 Claim roles

Every material claim MUST have one primary role from the following registry.

| Role | Meaning |
|---|---|
| `definition` | Establishes the intended meaning of a term or object within a scope. |
| `observation` | Reports a direct measurement, inspection, execution result, or other first-order observation. |
| `sourced_report` | Reports what an identified source states without asserting independent verification. |
| `assumption` | States a supposition used to bridge a gap or condition an argument. |
| `inference` | States a proposition derived from other claims through an identified reasoning step. |
| `judgment` | States an analytic conclusion that extends beyond direct observation. |
| `forecast` | States a future or otherwise resolvable judgment with an outcome definition and horizon. |
| `recommendation` | Advises a course of action without creating an ATS-1 conformance obligation. |
| `requirement` | States an obligation, prohibition, recommendation, or permission with deontic force. |
| `exception` | States a condition under which a rule, claim, or requirement does not apply. |
| `boundary` | States a limit on scope, generality, mechanism, or applicability. |
| `open_question` | Identifies an unresolved question whose answer can affect a material claim or action. |

A claim MAY have secondary tags, but it MUST NOT use multiple primary roles to conceal a transition from observation to inference or from judgment to recommendation.

### 7.5 Claim fields

A material claim MUST represent, when applicable:

- `subject`;
- `proposition`;
- `scope`;
- `polarity`;
- `quantifier`;
- `time_horizon`;
- `materiality`;
- `force`;
- `source_refs`;
- `assumption_refs`;
- `boundary_refs`;
- `exception_refs`;
- `status`; and
- `semantic_basis` (Draft.2 amendment D-F): for material claims whose semantic values
  are not mechanically derivable, the basis of each material value SHOULD be declared
  using the vocabulary of §4.25. A declared basis MUST be one of the five defined
  values. Basis declarations are optional; their absence is a typed silence, not a
  claim of `EXPLICIT`.

The canonical claim statuses are:

- `asserted`
- `ambiguous`
- `unresolved`
- `withdrawn`
- `superseded`

An `ambiguous` claim MUST include at least two materially distinct candidate interpretations or an explicit statement that no bounded interpretation set could be produced.

### 7.6 Scope model

Scope SHOULD be decomposed into fields rather than buried in prose. Available fields include:

- population or entity set;
- system or component;
- environment;
- condition;
- exclusions;
- time horizon;
- jurisdiction or authority domain;
- version or revision;
- data or evidence window; and
- confidence applicability.

A scope field that is unknown MUST be represented as unknown. It MUST NOT be omitted in a way that implies universal scope.

### 7.7 Quantifier model

ATS-1 recognizes these quantifier kinds:

- `none`
- `one`
- `some`
- `at_least_one`
- `most`
- `all`
- `exact_count`
- `minimum`
- `maximum`
- `range`
- `proportion`
- `unspecified`

A material claim MUST NOT silently move among quantifier kinds during a transformation.

Natural-language quantifiers such as “generally,” “usually,” “often,” and “rarely” are not calibrated probability terms. A policy MAY allow them for frequency descriptions only when the reference class and measurement basis are clear.

### 7.8 Polarity and negation

ATS-1 distinguishes:

- absence of evidence for a claim;
- evidence against a claim;
- evidence establishing the negation of a claim;
- a search that found no evidence;
- a search that was not performed; and
- evidence that was unavailable.

These states MUST NOT be collapsed.

Example:

```text
No evidence was collected about X.      # evidence state
The collected evidence does not support X. # evidential relation
The collected evidence supports not-X.     # contrary proposition
X is false.                                 # judgment or established result
```

### 7.9 Evidence objects

An evidence object MUST contain:

- an evidence identifier;
- a source type;
- a source locator or content hash when available;
- a proposition or observation;
- acquisition or observation time when material;
- provenance status;
- availability status; and
- optional quality metadata.

Canonical availability states are:

- `present`
- `not_found`
- `not_searched`
- `unavailable`
- `withheld`
- `not_applicable`

“Not found” asserts that a bounded search was performed. It MUST include the search scope or a reference to the search receipt.

### 7.10 Evidence provenance

Evidence provenance MAY identify:

- direct observation;
- test or benchmark;
- repository artifact;
- external source;
- model output;
- human report;
- formal derivation;
- simulation; or
- synthetic fixture.

Model-generated evidence summaries MUST retain links to their underlying source objects. A model output without an inspectable basis MUST be labeled as model output, not independent evidence.

### 7.11 Semantic relations

A material relationship among claims or evidence MUST use a typed relation when a structured representation is produced.

| Relation | Directional meaning |
|---|---|
| `consistent_with` | Source does not contradict target but does not materially discriminate for it. |
| `supports` | Source materially favors target over at least one live alternative. |
| `strongly_supports` | Multiple or highly discriminating lines of evidence substantially favor target. |
| `contradicts` | Source materially conflicts with target. |
| `qualifies` | Source limits the force, scope, or interpretation of target. |
| `depends_on` | Target's validity materially relies on source. |
| `condition_for` | Source states a condition under which target applies. |
| `exception_to` | Source states a condition under which target does not apply. |
| `derived_from` | Target follows from source through an inference or transformation. |
| `associated_with` | Source and target covary or co-occur without a causal claim. |
| `predicts` | Source provides out-of-sample or forward predictive information about target without itself asserting causation. |
| `contributes_to` | Source is one causal factor among others and is not asserted as independently sufficient. |
| `causes` | Source is asserted to produce a change in target under the stated intervention and scope. |
| `necessary_for` | Target cannot occur under the stated scope without source. |
| `sufficient_for` | Source is enough to produce target under the stated scope. |
| `contrasts_with` | Source is compared with target on an explicit dimension. |
| `alternative_to` | Source and target are competing explanations, options, or hypotheses. |
| `updates` | Source changes the force or status of target without reversing it. |
| `reverses` | Source changes the accepted polarity, recommendation, or decision of target. |

Relations are directional. A transformation MUST NOT reverse relation direction.

### 7.12 Assumptions

A material assumption MUST state:

- what is being assumed;
- why the assumption is needed;
- which claims depend on it;
- the consequence if it is false; and
- an update indicator or test when one is available.

An assumption MUST NOT be rendered as an observation or established fact.

### 7.13 Boundaries and exceptions

A boundary identifies where a claim stops applying. An exception identifies a condition that defeats a rule or claim that otherwise applies.

Material boundaries and exceptions are protected relations under `TRANSFORM`.

A generic caveat such as “results may vary” does not satisfy a boundary obligation unless it identifies a discriminating condition.

### 7.14 Update indicators

An update indicator states observable evidence that would:

- move a likelihood assessment to another band;
- change assessment confidence;
- invalidate a material assumption;
- activate an exception;
- reverse a recommendation; or
- require re-evaluation.

An update indicator SHOULD be operational enough that a reviewer can determine whether it occurred.

### 7.15 Materiality authority

Authors and authoritative upstream systems MAY mark claims or relations as material.

A downstream detector MAY promote an unmarked item to material. It MUST NOT demote an explicitly material item without adjudication.

When materiality is unresolved in a transformation and the item may affect P0 or P1 obligations, preservation conformance is `UNAVAILABLE` or `FAIL`; it is not `PASS`.

### 7.16 Extraction status

A meaning-ledger extractor MUST report one of:

- `complete`
- `partial`
- `ambiguous`
- `unavailable`

A partial or ambiguous extraction MUST identify affected spans and fields. It MUST NOT fill missing semantic slots with likely values without marking them as inferred candidates.

### 7.17 Stable semantic coordinates

> **Draft.2 amendment (D-C).**

A stable semantic coordinate MUST survive a transformation exactly, even when the proposition associated with it remains recoverable through another coordinate. Semantic equivalence does not imply coordinate equivalence when units have different authority, lifecycle, dependency, execution, verification, or evidence roles.

An artifact MAY declare its stable coordinates in a document-level `stable_coordinates` block. When declared, every protected coordinate used anywhere in the artifact (requirement identifiers, decision identifiers, acceptance-criterion identifiers, dependency targets, and cross-document authority references) MUST resolve to a declared coordinate, and no coordinate id MAY be declared twice.

### 7.18 Local semantic closure

> **Draft.2 amendment (D-D).**

For extractable normative units, recovery SHOULD include, where applicable: stable identity; actor; modality; action; object; condition or trigger; scope; exception; quantitative boundary; dependency; proof obligation; acceptance criterion; and rationale or evidence reference. Explicit enclosing scope MAY provide values, but extraction MUST remain reliable: an extractable unit MUST NOT require undeclared prior-paragraph inference to be understood. Not every field must appear in every sentence.

### 7.19 Semantic basis mechanics

> **Draft.2 amendment (D-F).**

A transformation MUST NOT silently convert `INFERRED` or `UNAVAILABLE` source material into an explicit source-authoritative semantic fact. Material axes include: authority; authority precedence; deontic force; acceptance or settlement state; likelihood; confidence; quantifier; polarity; causal force; normative dependency; exception removal; and source attribution.

Where a value's basis is not `EXPLICIT`, a transformation MAY: preserve the value as `INFERRED`; represent it as unresolved; omit it when nonessential; propose a candidate interpretation; or ask for adjudication when a material action depends on resolution. It MUST NOT silently pretend the source declared it. Authoring under a task that grants new-authoring authority MAY introduce values with basis `AUTHOR_JUDGMENT`.

---

## 8. Calibrated force

### 8.1 General rule

ATS-1 represents five force axes separately:

1. likelihood;
2. assessment confidence;
3. evidential force;
4. causal force; and
5. deontic force.

A sentence or structured field MUST NOT use one axis as a substitute for another.

### 8.2 Likelihood vocabulary

ATS-1 uses one coherent canonical row of words of estimative probability.

| Identifier | Canonical phrase | Display range | Machine interval |
|---|---|---:|---:|
| `almost_no_chance` | almost no chance | 1–5% | `[0.01, 0.05)` |
| `very_unlikely` | very unlikely | 5–20% | `[0.05, 0.20)` |
| `unlikely` | unlikely | 20–45% | `[0.20, 0.45)` |
| `roughly_even_chance` | roughly even chance | 45–55% | `[0.45, 0.55)` |
| `likely` | likely | 55–80% | `[0.55, 0.80)` |
| `very_likely` | very likely | 80–95% | `[0.80, 0.95)` |
| `almost_certain` | almost certain | 95–99% | `[0.95, 0.99]` |

The display ranges communicate familiar rounded bands. The machine intervals are lower-inclusive and upper-exclusive except for the final interval, which includes 0.99. This convention removes boundary overlap.

Probabilities below 1% or above 99% MUST be stated numerically. Exact 0% and 100% MUST be reserved for logical impossibility, logical necessity, definitional truth, or directly established exhaustive conditions.

### 8.3 Canonical output rule

An ATS-1 conforming renderer MUST use the canonical phrase in the table. It MUST NOT emit alternate synonyms such as “probable,” “remote,” “highly probable,” or “nearly certain” unless:

- the text is a quote;
- a domain policy explicitly requires the alternate vocabulary; or
- an input-normalization report records the noncanonical source wording.

Input tools MAY recognize synonyms, but output normalization MUST select one canonical phrase.

### 8.4 First-use numeric range

The first material use of a likelihood phrase in a section MUST include the display range inline.

Conforming:

```text
The migration is likely (55–80%) to reduce invalid-state defects.
```

Subsequent local uses MAY omit the range while the same policy and scale remain visually available.

### 8.5 Point forecasts

A numeric point forecast MAY be used when the evidence and use case justify greater precision.

A material point forecast MUST include:

- the numeric probability;
- an outcome definition;
- a resolution date or event;
- a resolution source;
- an update policy; and
- a stable forecast identifier.

A renderer MAY add the matching ATS-1 phrase:

```text
70% (likely)
```

It MUST NOT replace the point probability with only the wider phrase during transformation unless a retention contract authorizes that loss of precision.

### 8.6 False precision

An author SHOULD use a probability band rather than a point estimate when the basis does not support point precision.

A linter MAY flag point probabilities whose elicitation process, model, data, or calibration basis is absent. Such a finding is semantic unless the profile requires the missing fields.

### 8.7 “Possible” and “plausible”

“Possible” indicates non-impossibility or permission depending on context. “Plausible” indicates coherence with available knowledge or a lack of immediate contradiction. Neither is an ATS-1 likelihood band.

A material probabilistic judgment MUST NOT use “possible,” “plausible,” “might,” or “could” as its only likelihood expression.

### 8.8 Assessment confidence vocabulary

ATS-1 uses three assessment-confidence levels:

| Level | Meaning |
|---|---|
| `low` | The judgment is materially fragile because evidence is sparse, indirect, conflicting, assumption-sensitive, unstable, or poorly scoped. Plausible updates could readily change the judgment. |
| `moderate` | The basis is relevant and generally coherent, but at least one material gap, assumption, limitation, or instability remains. The judgment is useful but not robust to every plausible update. |
| `high` | The judgment is robust to plausible changes in evidence and interpretation because the basis is strong, major assumptions are explicit and tested or formally bounded, and material contrary evidence is absent or resolved. |

Assessment confidence MUST NOT be represented as another event probability.

### 8.9 Confidence basis

Every material confidence label MUST include a basis object or a nearby basis statement.

The structured basis supports these dimensions:

- `basis_type`: `empirical`, `formal`, `direct_observation`, `expert_judgment`, or `mixed`;
- `evidence_quality`: `weak`, `mixed`, `strong`, or `unknown`;
- `evidence_coverage`: `narrow`, `partial`, `broad`, or `unknown`;
- `source_independence`: `single`, `partially_independent`, `independent`, `not_applicable`, or `unknown`;
- `directness`: `indirect`, `mixed`, `direct`, or `unknown`;
- `consistency`: `conflicting`, `mixed`, `convergent`, or `unknown`;
- `assumption_sensitivity`: `high`, `moderate`, `low`, or `unknown`;
- `environmental_stability`: `volatile`, `mixed`, `stable`, `not_applicable`, or `unknown`;
- `contrary_evidence`: `unaddressed`, `addressed`, `none_found`, `not_searched`, `not_applicable`, or `unknown`; and
- `rationale`: a concise explanation of the displayed level.

The vector is inspectable evidence for the scalar label. Implementations MUST NOT convert it into an authoritative arithmetic score unless an extension defines and validates that mapping.

### 8.10 Confidence coherence

A semantic critic SHOULD flag `high` confidence when any material basis dimension is unknown, weak, unaddressed, or highly assumption-sensitive without an explicit robustness argument.

A formal proof MAY justify high confidence despite a single source when the proof, assumptions, and verification are inspectable.

### 8.11 Likelihood and confidence separation

Likelihood and assessment confidence MUST be represented as distinct fields or distinct labeled sentences.

Conforming:

```text
Assessment: The selector is likely (55–80%) to improve first-result utility.
Confidence: Moderate. The ablation isolates selector diversity, but repository coverage remains narrow.
```

Nonconforming:

```text
We are highly confident that the selector is very likely to improve utility.
```

The nonconforming form forces the reader to recover two scales from one unstructured sentence and encourages conflation.

### 8.12 Evidential force vocabulary

ATS-1 uses these preferred evidential expressions:

| Expression | Required interpretation |
|---|---|
| `consistent with` | The evidence does not contradict the claim but does not materially discriminate for it. |
| `suggests` | The evidence weakly favors the claim, with substantial alternatives, gaps, or noise. |
| `supports` | The evidence materially favors the claim over at least one live alternative. |
| `strongly supports` | Multiple independent or highly discriminating lines of evidence favor the claim and important alternatives are substantially weaker. |
| `establishes` | The evidence entails the claim under explicit assumptions, directly observes the complete relevant condition, or supplies a valid formal demonstration. |

“Proves” SHOULD be reserved for formal demonstration or logically exhaustive evidence. A policy MAY prohibit it entirely outside formal contexts.

### 8.13 Evidential overclaim

An evidential expression MUST NOT exceed the described basis.

Examples of potential overclaim include:

- one compatible example described as support;
- an observational association described as establishing causality;
- a green test suite described as proving absence of defects;
- a model-generated explanation described as independent evidence; and
- no contrary evidence found in a narrow search described as no contrary evidence exists.

### 8.14 Causal force vocabulary

ATS-1 uses these causal relations:

| Relation | Required interpretation |
|---|---|
| `associated with` | Variables covary or co-occur; no causal direction is asserted. |
| `predicts` | One variable improves prediction of another in a declared setting; causality is not asserted. |
| `contributes to` | The factor has a causal role but is not asserted as independently sufficient. |
| `causes` | An intervention on the factor changes the outcome under the stated scope and assumptions. |
| `necessary for` | The outcome cannot occur under the stated scope without the factor. |
| `sufficient for` | The factor is enough to produce the outcome under the stated scope. |

Untyped verbs such as “drives,” “leads to,” “explains,” “powers,” and “results in” SHOULD be replaced or accompanied by an explicit causal relation when causality is material.

### 8.15 Causal basis

A material causal claim MUST state or reference its basis, such as:

- randomized intervention;
- quasi-experimental identification;
- controlled deterministic system behavior;
- mechanistic proof;
- formal dependency;
- simulation under declared assumptions; or
- expert judgment.

A causal claim without an inspectable basis is not mechanically false, but it MUST receive a semantic finding when `ATS-EVID-002` is active.

### 8.16 Deontic force vocabulary

ATS-1 uses this closed vocabulary in normative text:

| Form | Meaning |
|---|---|
| `MUST` | Absolute obligation within the declared authority and scope. |
| `MUST NOT` | Absolute prohibition within the declared authority and scope. |
| `SHOULD` | Recommendation that can be overridden only for an explicit, material reason. |
| `SHOULD NOT` | Discouraged behavior that can be used only for an explicit, material reason. |
| `MAY` | Permission; the actor is allowed but not required to act. |
| `CAN` | Capability; the actor or system is able to act. |
| `CANNOT` | Lack of capability or logical impossibility, not prohibition. |
| `IS REQUIRED BY <source>` | Obligation attributed to an identified external authority. |

`SHALL` and `SHALL NOT` are noncanonical in ATS-1 output.

### 8.17 Deontic collisions

The following forms are nonconforming when the intended force is material:

```text
The system may reject the receipt.      # permission, capability, or probability?
The system should reject the receipt.   # recommendation or expectation?
The system will reject the receipt.     # forecast, design description, or obligation?
The system can reject the receipt.      # capability, not authorization or requirement
```

Conforming alternatives select one type:

```text
The verifier MUST reject the receipt.                 # obligation
The verifier MAY reject the receipt.                  # permission
The verifier can reject the receipt.                  # capability
The verifier is likely (55–80%) to reject the receipt. # probability
Policy X requires the verifier to reject the receipt. # external obligation
```

### 8.18 Force-preservation rule

A transformation MUST NOT silently change:

- a likelihood band or point probability;
- an assessment-confidence level;
- an evidential-force term;
- a causal relation;
- a deontic term; or
- the authority source of an obligation.

Such a change is a P0 or P1 delta according to Section 11.


---

## 9. Profiles

### 9.1 Common profile obligations

All stable ATS-1 profiles inherit these obligations:

1. Material claims MUST have recoverable scope, polarity, and role.
2. Material quantities MUST include units or dimensions.
3. Material dates and relative times MUST have deterministic anchors.
4. Material terms MUST resolve to one concept within their scope.
5. Evidence, assumptions, judgments, recommendations, and requirements MUST be distinguishable.
6. Conditions, exceptions, boundaries, and reversal points MUST remain attached to the claims they govern.
7. A section MUST not imply that an unavailable check passed.
8. The first load-bearing statement SHOULD precede background that cannot change its interpretation.
9. A profile-complete artifact MUST include every required slot or an explicit typed state such as `unknown`, `not_searched`, or `not_applicable` where the profile permits it.

### 9.2 `ASSESS` profile

#### 9.2.1 Reader job

The `ASSESS` profile supports a reader who must understand and use a judgment under uncertainty.

Typical artifacts include:

- Tribunal findings;
- forensic reviews;
- technical risk assessments;
- investigation memos;
- benchmark interpretations;
- architecture assessments;
- launch-readiness reviews; and
- model or policy evaluations.

#### 9.2.2 Required document-level slots

An `ASSESS` artifact MUST contain:

- the analytic question or decision context;
- one or more key judgments;
- the scope and time horizon;
- the evidence base or its availability state;
- material assumptions;
- material boundaries;
- material contrary evidence or the exact search state;
- update indicators for each material judgment; and
- a separation between judgments and recommendations.

A heading MAY provide a slot when its meaning is unambiguous, but headings alone do not satisfy evidence or basis obligations.

#### 9.2.3 Key judgment placement

The first material key judgment SHOULD appear before extended background.

If background is necessary to prevent a harmful misreading, the artifact MAY place a short framing statement first. The framing statement MUST not delay the key judgment beyond the first conceptual block.

#### 9.2.4 Material assessment object

Every material judgment or forecast MUST contain or reference:

- a proposition;
- scope;
- time horizon when temporally bounded;
- likelihood when the proposition is probabilistic;
- assessment confidence;
- confidence basis;
- supporting evidence;
- contrary evidence or search state;
- assumptions;
- boundaries;
- live alternatives when materially plausible; and
- update indicators.

A judgment that is not probabilistic, such as a formal entailment or direct deterministic conclusion, MAY omit a WEP. It MUST state the basis that makes likelihood inapplicable.

#### 9.2.5 Observation, inference, and judgment

An `ASSESS` artifact MUST not serialize this chain as one undifferentiated assertion:

```text
observation → inference → judgment → recommendation
```

The transitions MUST be recoverable through labels, sentence structure, typed relations, or explicit reasoning language.

Conforming pattern:

```text
Observation: The conceptual gate improved recall at 20 from 0.18 to 0.24.
Inference: Because candidate generation was unchanged, the gain is attributable to ranking within the retrieved set.
Judgment: The reranker is likely (55–80%) to improve first-result utility on similar queries.
Recommendation: Promote it to a project-disjoint validation run before default activation.
```

The labels are optional when the roles remain unmistakable.

#### 9.2.6 Evidence attribution

Every material evidence item MUST have a source locator, content hash, execution receipt, or explicit `unavailable` state.

A source summary MAY be used, but the summary MUST link to the underlying evidence object.

A model's analysis of evidence is an inference or judgment. It MUST NOT be represented as another independent evidence line.

#### 9.2.7 Contrary evidence

An `ASSESS` artifact MUST distinguish among:

- contrary evidence was found and addressed;
- contrary evidence was found and remains unresolved;
- a defined search found none;
- no search was performed;
- relevant evidence was unavailable; and
- contrary evidence is not applicable because the claim is formally entailed.

The phrase “no contrary evidence” is conforming only when the evidence search or proof domain is bounded and referenced.

#### 9.2.8 Live alternatives

A material assessment MUST identify materially plausible alternatives when they would change action or confidence.

An alternative MAY be omitted when:

- a formal proof eliminates it;
- the decision context does not depend on it;
- it is dominated under every declared criterion; or
- a typed insufficiency states that alternatives could not be bounded.

The artifact SHOULD state why an apparently relevant alternative is excluded.

#### 9.2.9 Assumption discipline

A material assumption that bridges an evidence gap MUST be explicit.

For each such assumption, the artifact MUST state the consequence if false. It SHOULD include a discriminating test or update indicator.

#### 9.2.10 Recommendation separation

A recommendation MUST be represented as advice, not as an observed consequence of the evidence.

A recommendation SHOULD identify:

- the action;
- the decision owner;
- the decisive reasons;
- principal cost or risk;
- dependencies; and
- a reversal condition when material.

The `ASSESS` profile does not itself create implementation obligations. A recommendation becomes normative only when a `SPECIFY` section or external authority adopts it.

#### 9.2.11 Forecast subprofile

A forecast is an `ASSESS` claim with role `forecast`.

A material forecast MUST include:

- a resolvable outcome definition;
- probability or WEP;
- resolution date or event;
- resolution source;
- update policy;
- forecast identifier; and
- outcome status once resolved.

A system MUST NOT claim empirical forecast calibration until enough resolved forecasts exist for a declared scoring procedure and uncertainty interval. Otherwise `forecast_calibration` is `INSUFFICIENT_EVIDENCE`.

#### 9.2.12 Canonical `ASSESS` rendering

An ATS-1 renderer SHOULD support this structure without requiring every heading when the artifact remains clear:

```text
Question
Key judgment
Likelihood
Confidence and basis
Supporting evidence
Contrary evidence and alternatives
Assumptions
Boundary
Update indicators
Recommendation or next discriminating test
```

#### 9.2.13 `ASSESS` profile completeness

`profile: PASS` requires:

- all material judgments have the slots in Section 9.2.4;
- missing information uses exact availability states;
- likelihood and confidence are distinct;
- assumptions and contrary evidence are not presented as established facts; and
- recommendations are distinguishable from judgments.

An unresolved missing material slot produces `profile: FAIL`. A detector incapable of evaluating a required slot produces `profile: UNAVAILABLE`.

### 9.3 `SPECIFY` profile

#### 9.3.1 Reader job

The `SPECIFY` profile supports a reader or implementation that must determine exactly what behavior, constraint, permission, prohibition, or acceptance condition applies.

Typical artifacts include:

- Arq intents and compiled contracts;
- policy rules;
- API behavior requirements;
- state-transition obligations;
- acceptance gates;
- security constraints;
- interoperability requirements; and
- implementation-neutral system requirements.

#### 9.3.2 Requirement object

Every material requirement MUST have a stable identifier and these slots:

- `actor` — the entity responsible for satisfying the requirement;
- `deontic` — `MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, or `MAY`;
- `action` — the required behavior;
- `object` — the entity acted on or result produced;
- `scope` — the system, version, authority domain, or population to which it applies;
- `trigger` — the event that activates it, when applicable;
- `condition` — the state in which it applies, when applicable;
- `timing` — deadline, ordering, frequency, or duration, when material;
- `constraints` — quantitative or qualitative bounds, when applicable;
- `exceptions` — exact defeat conditions, when applicable;
- `acceptance_criterion` — observable evidence that determines satisfaction;
- `source_authority` — the authority creating or imposing the obligation; and
- `rationale` — optional non-normative explanation, stored separately.

A slot that is not applicable MAY be omitted. A slot that is applicable but unknown MUST be marked unknown and prevents profile conformance.

#### 9.3.3 One obligation per requirement

A requirement MUST state one obligation.

A statement contains multiple obligations when independently satisfying one action would not satisfy the other.

Nonconforming:

```text
The verifier MUST reject stale receipts and record an audit event.
```

Conforming decomposition:

```text
REQ-VER-001: The verifier MUST reject a receipt whose policy hash is stale.
REQ-VER-002: After rejecting a stale receipt, the verifier MUST record an audit event.
```

Two actions MAY remain in one requirement only when they are simultaneous parts of one indivisible behavior and share one acceptance criterion. The requirement MUST document that indivisibility.

#### 9.3.4 Explicit actor

The responsible actor MUST be explicit in each requirement statement or inherited from a mechanically unambiguous requirement block.

A pronoun or passive construction MUST NOT conceal the actor.

Nonconforming:

```text
It MUST be rejected before acceptance.
```

Conforming:

```text
The verifier MUST reject the receipt before the acceptance transition.
```

#### 9.3.5 Canonical statement order

A renderer SHOULD use this order:

```text
[scope] [trigger] [condition] <actor> <DEONTIC> <action> <object> [timing] [constraints].
```

Recommended forms include:

```text
The <actor> MUST <action> <object>.
When <trigger>, the <actor> MUST <action> <object>.
While <condition>, the <actor> MUST <action> <object>.
If <undesired event>, the <actor> MUST <protective action>.
Within <duration> after <trigger>, the <actor> MUST <action> <object>.
The <actor> MAY <action> <object> only when <permission boundary>.
```

Canonical order is a rendering convention, not a substitute for structured slots.

#### 9.3.6 Trigger and condition

A trigger is an event. A condition is a state.

Implementations MUST NOT treat them as interchangeable when timing or repeated activation differs.

Example:

```text
When a receipt arrives, ...   # event trigger
While the policy snapshot is stale, ... # state condition
```

#### 9.3.7 Timing and ordering

A material timing requirement MUST state an observable boundary:

- before or after a named event;
- within a duration;
- at a frequency;
- for a duration;
- until a condition; or
- in a specified sequence.

Terms such as “promptly,” “soon,” “regularly,” and “eventually” are nonconforming when timing is material and no policy defines them quantitatively.

#### 9.3.8 Quantitative boundaries

A threshold or range MUST identify:

- value;
- unit;
- comparator;
- inclusivity or exclusivity when ambiguous;
- measurement window; and
- aggregation method when material.

Conforming:

```text
The verifier MUST complete policy revalidation in less than 500 ms at the 99th percentile over a rolling 24-hour window.
```

This statement still requires an acceptance method that defines load and environment.

#### 9.3.9 Acceptance criteria

Every `MUST` and `MUST NOT` requirement MUST have an acceptance criterion or a reference to one.

The acceptance criterion MUST identify observable evidence. It SHOULD identify the evidence provider, fixture, environment, and threshold.

A statement such as “works correctly” or “is robust” is not an acceptance criterion.

#### 9.3.10 Verifiability

A requirement is verifiable when an authorized reviewer can determine satisfaction from declared evidence without inventing missing thresholds, actors, or conditions.

A `SPECIFY` artifact MUST NOT report `profile: PASS` if a material `MUST` or `MUST NOT` requirement lacks a verifiable acceptance criterion.

#### 9.3.11 `SHOULD` obligations

A `SHOULD` or `SHOULD NOT` requirement MUST identify why exceptions may be valid or link to an override policy.

When an implementation intentionally does not follow a `SHOULD`, it MUST record the reason in an adjudication or implementation receipt if conformance is claimed.

`SHOULD` MUST NOT be used merely because the author is uncertain whether the requirement matters. Uncertainty belongs in an `ASSESS` claim.

#### 9.3.12 Permissions

A `MAY` statement MUST identify:

- the permitted actor;
- the permitted action;
- the boundary of permission; and
- any conditions or prohibitions that still apply.

Permission does not imply capability. A separate `CAN` statement MAY describe capability.

#### 9.3.13 Capability statements

`CAN` and `CANNOT` describe capability and are non-normative unless another requirement references that capability.

A capability statement MUST NOT satisfy a required-behavior slot.

#### 9.3.14 Prohibitions

A `MUST NOT` requirement SHOULD state the undesired behavior directly and define how violation is detected.

Negative phrasing SHOULD NOT be used when an affirmative requirement states the desired behavior more precisely. A prohibition is appropriate when the forbidden event itself is material.

#### 9.3.15 External obligations

An obligation imposed by another authority MUST identify that authority.

Conforming:

```text
Policy ATS-POL-17 requires the verifier to retain the rejection receipt for 30 days.
```

The current document MUST NOT silently restate an external obligation as if it originated locally.

#### 9.3.16 Rationale separation

Rationale, examples, implementation notes, and recommendations MUST be distinguishable from normative requirement text.

A rationale MUST NOT introduce a hidden requirement.

Nonconforming:

```text
The verifier MUST reject stale receipts because it also needs to log every rejection.
```

The logging obligation requires a separate requirement.

#### 9.3.17 Implementation neutrality

A requirement SHOULD state observable behavior rather than a particular implementation unless the implementation choice is itself a material constraint.

When implementation is constrained, the requirement MUST state the reason or source authority when available.

#### 9.3.18 Requirement identity and supersession

Requirement identifiers MUST be unique within their authority domain and MUST NOT be reused for a materially different obligation.

A changed requirement MUST record one of:

- compatible clarification;
- strengthened obligation;
- weakened obligation;
- changed scope;
- changed acceptance criterion;
- supersession by another requirement; or
- withdrawal.

A superseded requirement MUST retain a link to its successor.

#### 9.3.19 Requirement-set conformance

A set of individually conforming requirements MAY still be nonconforming as a set.

A `SPECIFY` set MUST be checked for:

- contradictions;
- duplicate obligations;
- gaps in required behavior;
- inconsistent terms or units;
- incompatible timing;
- circular dependencies;
- ambiguous precedence; and
- acceptance criteria that cannot all be satisfied simultaneously.

Set-level checks are semantic unless a closed formal model makes them deterministic.

#### 9.3.20 `SPECIFY` profile completeness

`profile: PASS` requires:

- each material requirement has a stable identifier;
- each has one obligation;
- actor and deontic force are explicit;
- applicable trigger, condition, timing, boundary, and exception slots are resolved;
- each `MUST` and `MUST NOT` has a verifiable acceptance criterion;
- rationale is separated; and
- no unresolved set-level contradiction is known.

### 9.4 Section composition

An artifact MAY compose profiles at section level.

Example:

```text
ASSESS: The current stale-policy path can accept an invalid receipt under one race condition.
SPECIFY: When policy currentness cannot be established, the verifier MUST refuse acceptance.
```

A recommendation in `ASSESS` does not become a requirement until adopted in `SPECIFY` or by an identified external authority.

### 9.5 Reserved profile behavior

Reserved profiles MAY appear only under an extension namespace such as:

```text
X-ARQ-EXPLAIN-1
```

Core ATS-1 implementations MUST preserve the identifier and report the profile as unsupported rather than treating it as `ASSESS` or `SPECIFY` by similarity.


---

## 10. Surface realization

### 10.1 Surface policy objective

Surface rules reduce ambiguity and local decoding cost without deleting material semantic structure.

A surface rule MUST NOT authorize a P0 or P1 change.

### 10.2 Canonical terminology

Within a declared scope:

- one concept SHOULD use one canonical term;
- one canonical term SHOULD denote one concept;
- approved domain terminology SHOULD be retained;
- aliases SHOULD appear only in definitions, quotations, migration notes, or explicit synonym mappings; and
- a shorter term MAY replace a long term after an explicit definition when referential identity remains exact.

A linter MUST distinguish deliberate contrast from accidental synonym drift.

### 10.3 Glossary entries

A glossary entry SHOULD contain:

- `concept_id`;
- canonical term;
- definition;
- scope;
- approved abbreviations;
- disallowed or deprecated aliases;
- audience level; and
- external ontology or code identifiers when available.

A glossary term MUST NOT be silently redefined in a narrower section. A local specialization requires a new concept identifier or explicit subtype relation.

### 10.4 Technical terms

A precise technical term MUST NOT be replaced solely because it is uncommon.

A technical term SHOULD be defined when the declared audience cannot be expected to know it and its interpretation is material.

A definition SHOULD be local to first material use or mechanically accessible through a glossary link. Repeating the definition on every use is not required.

### 10.5 Acronyms and abbreviations

An acronym or abbreviation MUST be expanded on first material use unless:

- it is included in the audience's assumed glossary;
- it is a code, identifier, unit, or universally recognized symbol in the domain; or
- expansion would be less clear than the canonical term.

Acronyms MUST retain one expansion within scope.

### 10.6 Referential clarity

Pronouns, demonstratives, and elliptical references SHOULD have one plausible antecedent.

Material ambiguity is nonconforming. A semantic finding SHOULD show the competing antecedents rather than merely state “unclear reference.”

Terms such as “this,” “that,” “it,” “they,” “the former,” and “the above” SHOULD be replaced by the canonical noun when two or more plausible referents exist.

### 10.7 Actor visibility

Active voice is preferred when agency, responsibility, or authority matters.

Passive voice is permitted when:

- the actor is unknown;
- the actor is irrelevant;
- the object or result is the deliberate focus; or
- domain convention requires it.

The `SPECIFY` profile still requires a recoverable responsible actor.

### 10.8 Concrete actions

Actions SHOULD use verbs rather than abstract nominalizations when the verb exposes agency or sequence.

Example:

```text
Prefer: The verifier revalidates the policy.
Avoid: Policy revalidation is performed.
```

The nominal form is permitted when the process itself is the defined technical object.

### 10.9 Quantities and units

A material number MUST include its unit, dimension, count basis, or explicit dimensionless status.

A transformed artifact MUST preserve:

- numeric value;
- unit;
- scale;
- sign;
- precision when material;
- comparator;
- aggregation method;
- denominator; and
- measurement window.

“Improved by 20%” and “improved by 20 percentage points” are distinct and MUST NOT be interchanged.

### 10.10 Ranges and thresholds

A material range or threshold MUST specify boundary semantics when ordinary language is ambiguous.

Examples:

```text
0 ≤ x < 10
at least 10
more than 10
no more than 10
between 10 and 20, inclusive
```

A machine representation SHOULD store comparators rather than infer them from punctuation.

### 10.11 Relative time

Relative expressions such as “today,” “currently,” “recently,” “soon,” “later,” “next,” and “the latest” MUST resolve to a date, event, version, or policy snapshot when time is material.

In a long-lived artifact, absolute anchors are preferred.

### 10.12 Source and revision currentness

A claim that depends on current software, policy, prices, office holders, schedules, or other mutable facts SHOULD identify the observation date and source revision.

A stale source does not automatically make the prose nonconforming, but the artifact MUST NOT present stale evidence as current when currentness is material.

### 10.13 Sentence length

ATS-1 imposes no global sentence-word limit on `ASSESS` or `SPECIFY` prose.

Implementations MAY use sentence length as a screening heuristic. They MUST NOT treat length alone as a semantic defect.

A long sentence SHOULD be split when it contains:

- multiple independent conceptual moves;
- competing clause attachments;
- more than one requirement obligation;
- an unbounded conditional stack;
- mixed epistemic roles; or
- a relation that becomes clearer when explicitly labeled.

A sentence SHOULD remain intact when splitting it would hide a material causal, conditional, contrastive, or qualifying relation.

### 10.14 Dependency and condition depth

A linter SHOULD inspect syntactic and logical nesting rather than word count alone.

Potential findings include:

- more than two nested conditions;
- a condition whose governed clause is unclear;
- a negation applied to an ambiguous span;
- a causal clause separated from its target;
- a relative clause with multiple candidate heads; and
- a requirement whose exception appears to modify the wrong obligation.

These findings are semantic unless a grammar makes the interpretation deterministic.

### 10.15 Paragraphs as conceptual moves

A paragraph SHOULD perform one primary conceptual move, such as:

- state a claim;
- explain a mechanism;
- present evidence;
- qualify a claim;
- compare alternatives;
- derive a consequence; or
- state an action.

“One conceptual move” is not equivalent to “one topic.” A paragraph MAY contain several sentences and relations when they jointly perform one move.

### 10.16 Load-bearing order

The key answer, judgment, requirement, or change SHOULD appear before background that does not alter its interpretation.

Exceptions include:

- a prerequisite definition;
- a safety warning;
- an authority or scope statement;
- a framing fact needed to prevent a materially wrong reading; and
- a deliberate suspense or pedagogical form outside the stable ATS-1 profiles.

### 10.17 Headings

A heading SHOULD state the content or decision under it rather than use a generic label.

Prefer:

```text
Why the selector cannot recover missing candidates
```

Over:

```text
Discussion
```

A heading MUST NOT imply that a question is resolved when the section reports uncertainty or insufficiency.

### 10.18 Lists and tables

Lists SHOULD be used when items are coordinate, sequential, or independently scannable.

A list MUST NOT flatten relationships that are causal, conditional, hierarchical, or argumentative unless those relations are explicitly encoded.

Table columns SHOULD compare like dimensions. Missing values MUST distinguish `unknown`, `not applicable`, and `not measured`.

### 10.19 Repetition

Repetition is permitted when it performs a function such as:

- re-establishing a referent;
- carrying a technical term consistently;
- restating a requirement at an enforcement boundary;
- summarizing after a long derivation;
- contrasting old and new states; or
- supporting accessibility.

A restatement SHOULD add at least one of:

- scope;
- evidence;
- mechanism;
- implication;
- contrast;
- action; or
- retrieval value.

Multiple phrasings of the same conclusion without added function are candidate `ATS-DISC-003` findings.

### 10.20 Empty intensifiers and attitude markers

Words such as “clearly,” “obviously,” “simply,” “just,” “very,” “really,” and “quite” SHOULD be removed when they add no calibrated meaning.

They MAY remain in quotations, interpersonal communication, or when their literal degree meaning is defined.

A linter SHOULD not replace them with stronger technical claims.

### 10.21 Vague evaluative terms

Material uses of “significant,” “large,” “small,” “meaningful,” “material,” “robust,” “fast,” “safe,” “reliable,” and similar terms SHOULD identify the comparison, threshold, or acceptance criterion.

“Statistically significant” MUST identify the statistical procedure or reference one. It MUST NOT imply practical importance.

### 10.22 Contrast and limitation markers

Contrastive and limiting relations are semantically protected when material.

Words and phrases such as these often encode P1 relations:

- but;
- however;
- only;
- unless;
- except;
- despite;
- whereas;
- although;
- even if;
- subject to; and
- under the condition that.

A transformation MUST not delete such a marker without preserving its relation through another form.

### 10.23 Examples

An example MUST be distinguishable from evidence and from a population claim.

One example MUST NOT be presented as an estimate of prevalence unless sampling and inference justify that claim.

### 10.24 Notes and non-normative text

In `SPECIFY`, notes, examples, rationale, and commentary MUST be visually or structurally distinguishable from normative requirements.

A note MUST NOT create an obligation indirectly.

### 10.25 Progressive disclosure

An implementation MAY render one meaning ledger at multiple levels:

- `L0`: verdict, obligation, or thesis;
- `L1`: operative model and key reasons;
- `L2`: evidence, derivation, assumptions, exceptions, and alternatives.

Each level MUST be a declared projection. Lower levels MUST not contradict or strengthen higher levels.

---

## 11. Transformation and semantic preservation

### 11.1 Applicability

`TRANSFORM` applies when an output artifact is derived from a source through:

- copyediting;
- lint repair;
- paraphrase;
- structural reorganization;
- compression;
- simplification;
- summarization;
- format conversion; or
- model-assisted rewriting.

### 11.2 Transformation classes

A transformation MUST declare one class:

| Class | Intended semantic behavior |
|---|---|
| `format_only` | Changes markup or layout without changing wording or meaning. |
| `copyedit` | Corrects mechanical defects while preserving all source claims and relations. |
| `rewrite` | Changes wording or structure while preserving all material source claims and relations. |
| `compress` | Removes non-load-bearing surface material while preserving all material source claims and relations. |
| `simplify` | Reduces local decoding burden while preserving all material source claims and relations. |
| `summarize` | Deliberately retains only a declared projection of source meaning. |
| `translate` | Renders into another language; reserved for a future ATS extension and not core-conformant in this edition. |

### 11.3 Preservation classes

#### 11.3.1 P0: exact protected fields

P0 includes, when material:

- named entities and referent identity;
- identifiers and code symbols;
- numbers, units, signs, precision, and denominators;
- dates, durations, and time horizons;
- polarity and negation;
- quantifier kind and value;
- probability points and bands;
- assessment-confidence level;
- deontic force;
- authority attribution;
- source attribution;
- conditions and exceptions;
- thresholds and comparator boundaries;
- requirement identifiers;
- version and revision identifiers; and
- acceptance criteria; and
- stable semantic coordinates (as defined in §4.23). (Draft.2 amendment D-C.)

A P0 field MUST remain exact unless the transformation includes an explicit authorized semantic change.

#### 11.3.2 P1: protected relations

P1 includes, when material:

- support and contradiction;
- qualification;
- dependency;
- condition and exception;
- causal direction and force;
- comparison dimension;
- alternative-hypothesis relationships;
- update and reversal;
- inference provenance;
- ordering dependencies;
- authority (the relation between an assertion and the authority that grounds it); (Draft.2 amendment D-B)
- temporal ordering; and (Draft.2 amendment D-B)
- acceptance dependency (a criterion whose satisfaction is a precondition of acceptance). (Draft.2 amendment D-B)

P1 wording MAY change. The relation's type, direction, scope, and force MUST remain recoverable.

> **Draft.2 amendment (D-B):** A transformation MUST NOT remove, weaken, strengthen,
> reverse, or make materially implicit a protected relation solely to reduce surface
> length, syntactic complexity, or repetition. Surface compression remains permitted;
> semantic-relational compression does not.

#### 11.3.3 P2: surface realization

P2 includes:

- sentence boundaries;
- paragraph boundaries;
- heading wording;
- list versus prose rendering;
- approved lexical substitution;
- deletion of functionless repetition;
- punctuation;
- local ordering that does not change dependencies; and
- other presentation choices not covered by P0 or P1.

P2 MAY be optimized freely under active surface rules.

> **Draft.2 amendment (D-E):** Locality-preserving redundancy — repetition that adds
> stable identity, standalone extraction, task or acceptance-criterion generation,
> review, receipt linkage, or retrieval locality — is not functionless and MAY be
> retained. ATS permits and often prefers it for artifacts expected to be sharded or
> retrieved in fragments. Deletion of repetition under P2 is limited to
> zero-information repetition: the same proposition restated without adding a semantic
> role, locality, or extraction benefit.

### 11.4 Authorized semantic changes

A transformation MAY intentionally change P0 or P1 only when an authorization object identifies:

- the exact source object;
- the old and new values or relations;
- the reason;
- the authority;
- affected downstream claims;
- required revalidation; and
- the change receipt.

An authorized semantic change is not “preserved.” The preservation report MUST classify it separately.

### 11.5 Semantic delta classes

A source-to-output comparison MUST use these delta classes where applicable:

- `preserved`
- `omitted`
- `added`
- `weakened`
- `strengthened`
- `contradicted`
- `scope_changed`
- `polarity_changed`
- `quantifier_changed`
- `likelihood_changed`
- `confidence_changed`
- `evidential_force_changed`
- `causal_force_changed`
- `deontic_force_changed`
- `source_attribution_changed`
- `authority_changed`
- `condition_changed`
- `exception_changed`
- `relation_changed`
- `ambiguous_after_transform`
- `authorized_change`

### 11.6 Non-strengthening invariant

A transformation MUST NOT make a source claim stronger unless an authorized semantic change permits it.

Strengthening includes:

- moving to a higher likelihood band;
- increasing assessment confidence;
- changing “consistent with” to “supports”;
- changing association to causation;
- changing `SHOULD` to `MUST`;
- changing “some” to “all”;
- deleting a condition or exception;
- removing source attribution so a report appears directly verified; and
- turning an assumption into a fact.

### 11.7 No invented material claims

A rewrite, copyedit, compression, or simplification MUST NOT add a material claim absent from the source or an authorized external evidence object.

A clarifying connective or explicit relation MAY be added when it is entailed by the source. The preservation report SHOULD record the derivation.

### 11.8 Summaries and retention contracts

Summarization is deliberately lossy. A summary MUST NOT claim preservation of the complete source unless it actually retains every material source obligation.

A conforming summary MUST bind a `RetentionContractV1` that identifies:

- the intended reader task;
- maximum or target length when relevant;
- mandatory claims;
- mandatory P0 fields;
- mandatory P1 relations;
- optional claims;
- intentionally omitted classes;
- required caveats and boundaries; and
- questions the summary must leave answerable.

Preservation is evaluated against the retention contract, not against every source sentence.

A retention contract governs only the `preservation` dimension. It does not waive the target artifact's content-profile obligations. A deliberately compressed output can therefore report `preservation: PASS` while reporting `profile: FAIL` or `profile: UNAVAILABLE` as a standalone `ASSESS` or `SPECIFY` artifact. Consumers MUST select the dimensions required for the downstream use rather than treating one passing dimension as global conformance.

A retention contract MUST NOT authorize removal of a condition, exception, or uncertainty marker that changes the interpretation of a retained claim.

### 11.9 Boundary-question preservation

A preservation evaluation SHOULD include questions that distinguish the source claim from nearby but incorrect interpretations.

Examples:

- Does the claim apply to all repositories or only project-disjoint evaluation repositories?
- Was no contrary evidence found, or was no search performed?
- Is the change required, recommended, permitted, or merely possible?
- Does the evidence support causation or only association?
- Does the recommendation reverse if the latency threshold is exceeded?

A transformation fails the question check when the source supports a determinate answer and the output does not.

### 11.10 Preservation evidence

A preservation report SHOULD combine:

- exact P0 comparison;
- meaning-ledger claim comparison;
- P1 relation comparison;
- source-to-output entailment evidence;
- output-to-source non-strengthening evidence;
- boundary-question results; and
- human adjudication of unresolved deltas.

No single model score is sufficient authority.

### 11.11 Preservation outcome

`preservation: PASS` requires:

- zero unauthorized P0 changes;
- zero unresolved material P1 changes;
- zero unsupported material additions;
- zero unadjudicated strengthening deltas;
- all required retention-contract obligations satisfied; and
- all required preservation checks available.

### 11.12 Repair authority

A repair system MAY propose a patch. It MUST declare:

- the finding addressed;
- source span;
- replacement span;
- expected P0/P1/P2 impact;
- protected fields;
- model or rule identity; and
- confidence or abstention state.

The repair system MUST NOT accept its own patch.

A verifier MUST re-run applicable checks on the patched artifact under the current policy snapshot.

### 11.13 Minimal repair

A proposed repair SHOULD make the smallest change that resolves the accepted finding while preserving unaffected meaning and authorial register.

A large rewrite is non-minimal when a local correction would suffice. Large rewrites require broader preservation evaluation.


---

## 12. Rule system

### 12.1 Rule identity

Every ATS-1 rule has an immutable identifier of the form:

```text
ATS-<CATEGORY>-<NUMBER>
```

A rule identifier MUST NOT be reused for a materially different rule. Clarifications that change accepted or rejected cases require a new rule version and, when semantics change materially, a new identifier or specification version.

### 12.2 Rule record

A rule record MUST contain:

- identifier;
- title;
- normative statement;
- rationale;
- applicable profiles;
- default state by profile;
- severity;
- detector class;
- required inputs;
- protected impact;
- autofix class;
- exceptions or exemptions; and
- required fixture classes.

A promoted rule MUST additionally bind concrete conforming, violation, exception, and hard-negative fixture references in its promotion receipt or an immutable corpus query. The draft registry records fixture obligations before the repository-derived corpus exists; it does not pretend that uncreated fixtures already satisfy promotion.

The machine-readable registry is in `rules/ats_rules_v2.yaml`.

### 12.3 Detector classes

ATS-1 recognizes these detector classes:

| Class | Mechanism | Typical authority |
|---|---|---|
| `D0` | Token, lexicon, pattern, and exact-value checks | May be required after fixture validation |
| `D1` | Syntax tree, document AST, glossary, and structural checks | May be required after parser validation |
| `D2` | Static retrieval of candidate rules and analogous adjudications | Candidate generation only |
| `D3` | Rule-conditioned semantic critic | Advisory by default in this draft |
| `D4` | Cross-text preservation, contradiction, and repair verification | Required only when an independently validated policy activates it |

A detector MAY use multiple classes. It MUST report the highest class required for the finding.

Rule state and detector authority are orthogonal:

- the rule state declares what the artifact must satisfy;
- detector authority declares what a particular result can establish;
- `candidate_only` output can route work but cannot establish applicability;
- `proposal_only` output can create a finding for adjudication but cannot independently establish `PASS` or `FAIL`; and
- `conformance_evidence` can contribute directly to a conformance decision only under an active validation receipt and policy.

In this draft, D2 output is `candidate_only`; D3 output is `proposal_only`; D0/D1 output MAY be `conformance_evidence` after deterministic fixture and parser validation; and D4 output MAY be `conformance_evidence` only after independent preservation validation. The absence of a proposal-only finding is not evidence that a required semantic predicate passed.

### 12.4 Severity

Finding severity describes potential impact, not enforcement state.

| Severity | Meaning |
|---|---|
| `critical` | Likely to change action, acceptance, authority, safety, material probability, or source meaning. |
| `major` | Likely to cause material ambiguity, overclaim, omission, or reconstruction burden. |
| `minor` | Local clarity or consistency defect with low expected semantic impact. |
| `info` | Non-defect observation or coaching opportunity. |

A required rule can produce a minor finding, and an advisory rule can produce a critical finding. Policy determines enforcement.

### 12.5 Autofix classes

| Class | Meaning |
|---|---|
| `safe_p2` | A deterministic P2-only fix MAY be applied automatically and then revalidated. |
| `review_required` | The fix may affect meaning or register and requires adjudication. |
| `forbidden` | ATS-1 does not permit automatic repair for this rule. |

Any proposed fix that changes or may change P0 or P1 is `review_required` or `forbidden`.

### 12.6 Default finding budget

The default semantic finding budget is:

- guardrail findings: all deduplicated `critical` findings;
- coach findings: the five highest-ranked remaining findings per artifact;
- per-rule duplicates: collapsed when one repair or adjudication can address them together.

A policy MAY set the coach budget from 1 through 8. A higher budget requires an explicit reviewer-load rationale.

The budget limits surfaced findings, not recorded shadow telemetry.

### 12.7 Normative rule catalog

The following catalog is normative. “Required” and “Advisory” refer to default profile states; policy resolution may strengthen them under Section 6.

#### 12.7.1 Terminology, reference, scope, quantity, and time

| Rule | Normative statement | `ASSESS` | `SPECIFY` | Detector |
|---|---|---:|---:|---:|
| `ATS-TERM-001` | Within one scope, a concept MUST use one canonical term unless an explicit contrast, quotation, or alias mapping justifies another term. | Advisory | Advisory | D1/D3 |
| `ATS-TERM-002` | A precise approved domain term MUST NOT be replaced solely to use more common vocabulary when the substitute changes or broadens meaning. | Advisory | Advisory | D3 |
| `ATS-TERM-003` | An acronym or abbreviation MUST be expanded on first material use unless the audience policy or glossary explicitly permits it. | Required | Required | D0/D1 |
| `ATS-REF-001` | A material pronoun, demonstrative, or elliptical reference MUST have one plausible antecedent. | Advisory | Required for requirement actor/object references | D1/D3 |
| `ATS-SCOPE-001` | Material quantifier, negation, condition, exclusion, and scope relationships MUST be explicit enough to admit one action-relevant interpretation. | Advisory | Required | D1/D3 |
| `ATS-NUM-001` | A material number MUST include its unit, dimension, denominator, or explicit dimensionless status. | Required | Required | D0/D1 |
| `ATS-NUM-002` | A material range or threshold MUST define comparator and boundary semantics when ordinary language is ambiguous. | Required | Required | D0/D1 |
| `ATS-TIME-001` | A material forecast or temporally bounded judgment MUST state a resolution date, event, or time horizon. | Required | Advisory when future behavior is described | D0/D1 |
| `ATS-TIME-002` | A material relative-time expression MUST resolve to an absolute date, event, version, or policy snapshot. | Required | Required | D0/D1 |

#### 12.7.2 Preservation and epistemics

| Rule | Normative statement | `ASSESS` | `SPECIFY` | Detector |
|---|---|---:|---:|---:|
| `ATS-PRES-001` | A transformation MUST preserve all retained P0 fields exactly unless an authorized semantic change records the delta. | Required under `TRANSFORM` | Required under `TRANSFORM` | D0/D4 |
| `ATS-EPI-001` | A material probabilistic judgment MUST use the canonical ATS-1 WEP vocabulary or a justified numeric point probability. | Required | Advisory when probability appears | D0/D3 |
| `ATS-EPI-002` | The first material WEP use in a section MUST include its numeric display range inline. | Required | Advisory | D0/D1 |
| `ATS-EPI-003` | A section MUST NOT mix noncanonical WEP synonyms with canonical ATS-1 output unless the alternate term is quoted or policy-required. | Required | Advisory | D0 |
| `ATS-EPI-004` | Likelihood and assessment confidence MUST be represented as distinct fields or labeled sentences. | Required | Advisory | D1/D3 |
| `ATS-EPI-005` | A material assessment-confidence label MUST include an inspectable basis and rationale. | Required | Advisory | D1/D3 |
| `ATS-EPI-006` | A material assessment MUST identify an observable update or reversal indicator, or state why none is available. | Required | Advisory | D3 |
| `ATS-EPI-007` | “Possible,” “plausible,” “might,” and “could” MUST NOT serve as the only likelihood expression for a material probabilistic judgment. | Required | Advisory | D0/D3 |

#### 12.7.3 Deontics and requirements

| Rule | Normative statement | `ASSESS` | `SPECIFY` | Detector |
|---|---|---:|---:|---:|
| `ATS-DEON-001` | Normative statements MUST use ATS-1 deontic terms with their defined force; lowercase or alternate modals MUST NOT carry hidden normative meaning. | Advisory | Required | D0/D1/D3 |
| `ATS-DEON-002` | `MAY` MUST express permission, not probability or capability. | Advisory | Required | D0/D3 |
| `ATS-DEON-003` | `SHOULD` and `SHOULD NOT` MUST express defeasible recommendation, not an unstated forecast or uncertainty about importance. | Advisory | Required | D0/D3 |
| `ATS-REQ-001` | Every material requirement MUST identify the responsible actor explicitly or through a mechanically unambiguous inherited block. | Not applicable | Required | D1/D3 |
| `ATS-REQ-002` | Every material requirement MUST contain one obligation unless multiple actions are proven indivisible under one acceptance criterion. | Not applicable | Required | D1/D3 |
| `ATS-REQ-003` | Every applicable requirement slot—scope, trigger, condition, timing, constraint, exception, and acceptance criterion—MUST be explicit or referenced. | Not applicable | Required | D1/D3 |

#### 12.7.4 Evidence, discourse, and relation preservation

| Rule | Normative statement | `ASSESS` | `SPECIFY` | Detector |
|---|---|---:|---:|---:|
| `ATS-EVID-001` | Observation, sourced report, assumption, inference, judgment, forecast, recommendation, and requirement MUST be distinguishable when their difference is material. | Required | Required where rationale or evidence appears | D1/D3 |
| `ATS-EVID-002` | Evidential and causal wording MUST NOT exceed the basis described or referenced by the artifact. | Advisory | Advisory | D3 |
| `ATS-EVID-003` | A material assessment MUST identify contrary evidence and live alternatives, or state the exact search and applicability status. | Required | Advisory for requirement rationale | D3 |
| `ATS-DISC-001` | The load-bearing judgment, requirement, or answer SHOULD precede background that cannot change its interpretation. | Advisory | Advisory | D1/D3 |
| `ATS-DISC-002` | A paragraph SHOULD perform one primary conceptual move. | Advisory | Advisory | D1/D3 |
| `ATS-DISC-003` | Restatements MUST add function. Zero-information repetition — the same proposition restated without adding a semantic role, locality, or extraction benefit — is a defect. Locality-preserving redundancy is not zero-information repetition and is permitted. (Draft.2 amendment D-E) | Advisory | Advisory | D3 |
| `ATS-PRES-002` | A transformation MUST preserve all retained material P1 relations with the same type, direction, scope, and force. | Required under `TRANSFORM` | Required under `TRANSFORM` | D4 |
| `ATS-PRES-003` | A transformation MUST NOT remove, weaken, strengthen, reverse, or make materially implicit a protected relation solely to reduce surface length, syntactic complexity, or repetition; surface compression remains permitted, semantic-relational compression does not. (Draft.2 amendment D-B) | Advisory | Advisory | D1 |

#### 12.7.5 Coordinates, basis, and closure

| Rule | Normative statement | `ASSESS` | `SPECIFY` | Detector |
|---|---|---:|---:|---:|
| `ATS-COORD-001` | A stable semantic coordinate declared in a source artifact MUST survive a transformation exactly, including when the associated proposition remains recoverable through another coordinate. (Draft.2 amendment D-C) | Advisory | Required | D1 |
| `ATS-COORD-002` | Stable semantic coordinates MUST be unique within an artifact, and every reference to a coordinate (dependency target, acceptance-criterion reference, cross-document authority reference) MUST resolve to a declared coordinate. (Draft.2 amendment D-C) | Advisory | Required | D1 |
| `ATS-BASIS-001` | Material semantic values SHOULD declare their basis, and a declared basis MUST be one of EXPLICIT, DERIVED, INFERRED, UNAVAILABLE, or AUTHOR_JUDGMENT. (Draft.2 amendment D-F) | Advisory | Advisory | D3 |
| `ATS-BASIS-002` | A transformation MUST NOT silently convert INFERRED or UNAVAILABLE source material into an explicit source-authoritative semantic fact. (Draft.2 amendment D-F) | Advisory | Advisory | D1 |
| `ATS-CLOSE-001` | An extractable normative unit MUST be locally closed: its operative meaning is recoverable from the unit plus explicitly declared dependencies, without undeclared document-wide inference. (Draft.2 amendment D-D) | Advisory | Required | D1 |

### 12.8 Profile completeness is not a style score

The profile validators in Section 9 operate in addition to the text rules (thirty in
draft.1; thirty-six in draft.2). An artifact can pass every individual local rule and
still fail profile completeness because a required section-level semantic slot is absent.

### 12.9 Rule exceptions and counterexamples

Every rule corpus MUST include:

- conforming positives;
- clear violations;
- near misses;
- hard negatives containing likely surface cues without a violation;
- domain-specific exceptions;
- adversarial examples; and
- transformation pairs when the rule can be affected by rewriting.

A rule MUST NOT be promoted to `required` based only on synthetic violations or examples that repeat the rule's wording.

### 12.10 Rule explanation

An implementation MUST be able to explain a surfaced rule by returning:

- normative statement;
- why it applies to the span;
- evidence spans;
- materially distinct interpretations when ambiguity is involved;
- protected impact;
- example conforming repairs; and
- exception conditions.

A generic message such as “make this clearer” does not satisfy ATS-1 finding requirements.

---

## 13. Findings, interpretations, and adjudication

### 13.1 Finding object

A `TextFindingV1` MUST contain:

- finding identifier;
- artifact and policy identifiers;
- rule identifier and version;
- profile;
- source spans or locators;
- issue code;
- concise explanation;
- evidence spans;
- severity;
- detector identity and version;
- detector class and authority;
- detector confidence or deterministic status;
- applicability result;
- protected impact;
- candidate interpretations when relevant;
- proposed repairs when available; and
- adjudication state.

### 13.2 Applicability result

A semantic detector MUST return one of:

- `applies`
- `does_not_apply`
- `abstain`

A probability score without one of these states is insufficient.

An `abstain` result MUST identify the missing context, unsupported domain, parser failure, or ambiguity that prevented a decision.

### 13.3 Evidence spans

A finding MUST point to the smallest sufficient source spans that establish why the rule may apply.

A document-wide finding MAY reference several spans. It SHOULD not cite the whole artifact when a smaller set is available.

### 13.4 Distinguishing interpretations

An ambiguity finding SHOULD enumerate the materially distinct interpretations.

Example:

```yaml
span: "The system may reject stale receipts."
interpretations:
  - force: permission
    reading: "The system is permitted to reject stale receipts."
  - force: capability
    reading: "The system can reject stale receipts."
  - force: probability
    reading: "The system might reject stale receipts."
  - force: obligation
    reading: "The system is required to reject stale receipts."
```

A repair SHOULD ask the author to select the intended interpretation when context cannot resolve it.

### 13.5 Detector confidence

Detector confidence MUST be named `detector_confidence` in machine objects.

It MUST NOT be labeled merely `confidence` in a context where assessment confidence also appears.

Deterministic findings SHOULD use `detector_status: deterministic` rather than an invented probability.

### 13.6 Finding lifecycle

A finding has one of these states:

- `proposed`
- `accepted`
- `rejected`
- `waived`
- `deferred`
- `resolved`
- `unresolved`

`resolved` requires a patch or evidence change and successful re-evaluation. Acceptance of a finding is not the same as resolution.

### 13.7 Adjudication object

An adjudication MUST record:

- finding identifier;
- disposition;
- adjudicator identity;
- rationale;
- timestamp;
- selected interpretation when applicable;
- authorized repair or waiver;
- evidence references; and
- policy snapshot.

A model MAY propose an adjudication rationale. It MUST NOT become the authoritative adjudicator for its own finding unless a separate policy explicitly delegates that authority and an independent verifier checks the result. Core ATS-1 policy SHOULD NOT delegate such authority.

### 13.8 Waivers

A waiver applies to one finding, not automatically to every future instance of the rule.

A waiver MUST include exact scope and expiration. Repeated waivers SHOULD trigger review of the rule, glossary, parser, or project policy.

### 13.9 Deduplication

Findings MAY be deduplicated when:

- they have the same root semantic defect;
- one repair addresses every cited span; and
- deduplication does not hide a distinct P0 or P1 impact.

A deduplicated finding MUST retain all affected spans.

### 13.10 Ranking

Semantic findings SHOULD be ranked by expected reviewer utility, considering:

- materiality;
- severity;
- detector calibration;
- actionability;
- novelty relative to already surfaced findings;
- repair scope;
- likely downstream impact; and
- reviewer effort.

Ranking MUST NOT suppress an unresolved critical guardrail finding merely because it resembles another finding.


---

## 14. Processing pipeline and authority

### 14.1 Required stage order

An ATS-1 implementation SHOULD execute stages in this order:

```text
source acquisition
→ policy resolution
→ profile resolution
→ parse and source mapping
→ meaning-ledger extraction or validation
→ deterministic checks
→ candidate-rule retrieval
→ semantic criticism
→ finding ranking and budgeting
→ adjudication
→ bounded repair
→ preservation verification
→ conformance evaluation
→ receipt emission
```

A stage MAY be skipped only when it is not applicable or the capability declaration says it is unsupported. A skipped required stage produces `UNAVAILABLE`.

### 14.2 Source acquisition

The implementation MUST bind the exact input bytes or stable source object to a content hash before evaluation.

If preprocessing changes the text, the implementation MUST preserve both original and normalized hashes and a deterministic mapping between them.

### 14.3 Policy currentness

The implementation MUST resolve the current applicable policy before evaluation.

Before acceptance, it MUST confirm that:

- the policy snapshot is still current for the artifact scope;
- no governing rule or exception changed;
- detector artifacts match the snapshot; and
- any prior receipt has not been superseded.

When currentness cannot be established, the implementation MUST fail closed for required conformance claims.

### 14.4 Parsing and source mapping

A parser MUST preserve enough source mapping to localize findings and patches.

A parser failure MUST identify the affected region. It MUST NOT cause the implementation to silently run token-only rules and report full conformance.

### 14.5 Meaning-ledger generation

For newly generated text, a system SHOULD construct the meaning ledger before rendering.

For legacy text, an extractor MAY reconstruct the ledger. It MUST expose uncertainty, ambiguity, and missing fields.

The extracted ledger is evidence, not automatically authoritative meaning. Human or upstream structured intent can supersede it through adjudication.

### 14.6 Deterministic checks

D0 and D1 checks SHOULD run before learned checks. Their outputs SHOULD be cached by source hash, policy hash, parser version, and rule version.

A deterministic detector MUST be reproducible from the same inputs.

### 14.7 Rule retrieval

A D2 rule router MAY retrieve:

- candidate rule cards;
- similar accepted findings;
- similar rejected findings;
- relevant glossary entries;
- profile examples; and
- repair precedents.

Retrieval is candidate generation. A retrieved rule MUST NOT be treated as applicable merely because it ranked highly.

### 14.8 Semantic criticism

A D3 critic is proposal-only in core ATS-1 draft policy. Its finding can be accepted, rejected, or used to request more evidence, but the critic MUST NOT directly set a conformance dimension to `PASS` or `FAIL`.

A D3 critic SHOULD be conditioned on:

- active profile;
- local and document context;
- candidate rule;
- glossary;
- meaning-ledger objects;
- analogous adjudications; and
- protected fields and relations.

The critic SHOULD return structured applicability, evidence spans, interpretations, protected impact, and abstention.

### 14.9 Repair

A repair stage MUST consume an accepted finding or explicit author instruction. It MUST NOT repair every proposed finding preemptively when doing so could alter meaning.

A repair MUST bind the policy, source hash, finding, and protected objects.

### 14.10 Independent verification

The component that generates a semantic repair MUST NOT be the sole component that verifies preservation.

Independence MAY be provided by:

- deterministic exact checks;
- a separately trained delta critic;
- a different model family;
- a formal checker;
- human review; or
- a combination.

Model diversity alone is not sufficient evidence of correctness.

### 14.11 Human authority

Core ATS-1 assigns final authority for semantic acceptance to an authorized human or an explicitly governed external acceptance system.

The human MAY accept, reject, modify, or waive a finding. The receipt MUST preserve the disposition and rationale.

### 14.12 No silent fallback

When a configured detector, model, glossary, or evidence provider is unavailable, the implementation MUST report the unavailable capability.

It MUST NOT substitute a weaker component and preserve the same conformance claim unless the policy snapshot explicitly authorizes that fallback and records its identity.

### 14.13 Receipt emission

A conformance receipt MUST bind:

- source and output hashes;
- policy hash;
- parser and implementation identities;
- rule registry and lexicon versions;
- model artifacts;
- deterministic results;
- semantic findings and adjudications;
- preservation report;
- conformance vector;
- timestamps;
- authority identities; and
- supersession links.

Receipts SHOULD be serialized canonically and content-addressed.

---

## 15. Conformance evaluation

### 15.1 Mechanical conformance

`mechanical: PASS` requires:

- every active `required` D0/D1 rule executed;
- no unresolved required mechanical finding;
- no required parser capability unavailable;
- glossary and policy references resolved; and
- deterministic replay succeeds.

An advisory mechanical finding does not block mechanical conformance, but it remains visible when within the finding budget or guardrail lane.

### 15.2 Profile conformance

`profile: PASS` requires the active profile's semantic slots and structural obligations to be satisfied.

Profile conformance MAY rely on deterministic and semantic evidence. If a required semantic slot cannot be evaluated, the result is `UNAVAILABLE`, not `PASS`.

### 15.3 Semantic-review conformance

`semantic_review: PASS` requires:

- the declared semantic rule scope was executed;
- every surfaced advisory or required finding was dispositioned;
- every required semantic predicate was evaluated by an authorized human, authoritative structured source, or detector operating as validated `conformance_evidence`;
- no accepted critical finding remains unresolved unless an exact waiver applies;
- abstentions that affect material claims were adjudicated or marked unavailable; and
- the finding budget and ranking policy were recorded.

A semantic review can pass with rejected findings. It cannot pass with undispositioned surfaced findings. The absence of D3 findings is insufficient by itself because D3 output is proposal-only in this draft.

### 15.4 Preservation conformance

`preservation: PASS` is defined in Section 11.11.

For a non-transformed artifact, preservation is `NOT_APPLICABLE`.

For a summary without a retention contract, preservation is `UNAVAILABLE`.

### 15.5 Forecast-calibration conformance

`forecast_calibration: PASS` requires:

- a declared forecast cohort;
- resolved outcomes;
- a scoring rule;
- reliability or calibration analysis;
- uncertainty estimates;
- no outcome leakage; and
- a minimum evidence threshold defined before evaluation.

ATS-1 does not prescribe one minimum sample size because it depends on forecast distribution and intended claim. An implementation MUST report `INSUFFICIENT_EVIDENCE` when the data do not support the claimed granularity.

### 15.6 Conformance aggregation

An implementation MAY display a compact status line, but it MUST retain the full vector.

It MUST NOT average failed dimensions into a passing score.

### 15.7 Artifact conformance algorithm

A conforming evaluator SHOULD perform:

```text
1. Validate object schemas.
2. Resolve and hash policy.
3. Resolve section profiles.
4. Execute required mechanical rules.
5. Validate profile slots.
6. Execute configured semantic review.
7. Adjudicate findings.
8. Execute transformation checks when applicable.
9. Compute each conformance dimension independently.
10. Emit a receipt.
```

### 15.8 Conformance claim freshness

A conformance claim is stale when any material input changes, including:

- source bytes;
- policy;
- rule registry;
- glossary;
- profile;
- accepted finding disposition;
- repair;
- model artifact when semantic evidence is relied upon; or
- external evidence required by a material assessment.

A stale claim MUST be re-evaluated before downstream acceptance.

---

## 16. Implementation requirements

### 16.1 Capability declaration

A conforming implementation MUST expose a capability object containing:

- implementation name and version;
- ATS-1 versions supported;
- schemas supported;
- profiles supported;
- rules supported;
- detector class and declared authority per rule;
- authority-basis receipt for every detector that contributes conformance evidence;
- languages supported;
- markup formats supported;
- autofix classes supported;
- preservation methods supported;
- semantic model identities;
- deterministic replay guarantees; and
- known limitations.

### 16.2 Determinism

Deterministic components MUST produce identical results for identical canonical inputs.

Nondeterministic components MUST record:

- model identity and content hash where possible;
- decoding or sampling configuration;
- prompt or program identity;
- tool-access policy;
- run identifier;
- attempt count; and
- observed output.

### 16.3 Parser fidelity

An implementation MUST test parsing and source mapping against:

- headings;
- lists;
- tables;
- code blocks;
- block quotes;
- inline code;
- links;
- footnotes;
- requirement blocks;
- embedded structured data; and
- malformed markup.

It MUST identify unsupported constructs.

### 16.4 Rule fixtures

A required D0 or D1 rule MUST have:

- deterministic positive fixtures;
- deterministic violation fixtures;
- boundary fixtures;
- exemption fixtures;
- malformed-input fixtures; and
- regression fixtures for every repaired false positive or false negative.

### 16.5 Semantic model authority

In this draft, D3 semantic-detector output is `proposal_only` regardless of the active rule state. A required rule can therefore remain a normative artifact obligation while its learned detector lacks authority to decide conformance.

For a required semantic rule:

- an accepted D3 finding can establish that the artifact currently fails or requires repair;
- a rejected D3 finding removes that proposal but does not prove the rule passed;
- no surfaced finding does not prove the rule passed; and
- `PASS` requires human adjudication, authoritative structured intent, a formally verified predicate, or a detector promoted to `conformance_evidence` under Section 18.

A policy MUST NOT grant a learned detector `conformance_evidence` authority unless the detector has passed the promotion requirements in Section 18. A capability declaration and receipt MUST bind the authority basis.

### 16.6 Calibration

A semantic detector that emits probabilities MUST be calibrated per rule or per justified rule family.

Aggregate calibration across unrelated rules is insufficient when individual rule behavior differs materially.

### 16.7 Abstention

A semantic detector MUST support abstention.

A detector SHOULD abstain when:

- required context is missing;
- the domain is unsupported;
- competing interpretations remain unresolved;
- source mapping is unreliable;
- the rule is not applicable to the active profile; or
- detector evidence is below its declared operating threshold.

### 16.8 Explanation fidelity

A finding explanation MUST be grounded in the cited spans and active rule.

The implementation MUST NOT generate a plausible but unsupported explanation merely because the detector classified the span as a violation.

### 16.9 Privacy and repository boundaries

An implementation MUST declare whether source text leaves the local environment.

Remote processing MUST follow project policy for:

- source-code confidentiality;
- personal data;
- security findings;
- customer information;
- model retention; and
- training use.

A receipt SHOULD record the processing boundary without embedding sensitive source text unnecessarily.

### 16.10 Performance reporting

Performance claims SHOULD report:

- corpus size;
- artifact lengths;
- rule set;
- hardware;
- latency distribution;
- throughput;
- peak memory;
- semantic-model cost; and
- cache conditions.

A latency claim MUST distinguish cold, warm, and cached execution when material.

### 16.11 Editor and CI integration

An editor integration SHOULD present:

- local finding span;
- rule explanation;
- interpretations;
- minimal repair options;
- protected impact; and
- adjudication controls.

A CI integration MUST output stable machine-readable findings and exit semantics. It SHOULD avoid failing a build on advisory semantic findings unless policy explicitly requires disposition before merge.

### 16.12 Reproducible receipts

A receipt verification command SHOULD be able to:

- fetch or resolve declared artifacts;
- validate hashes;
- validate schemas;
- re-run deterministic rules;
- verify policy currentness; and
- identify semantic evidence that cannot be reproduced.

A semantic result that cannot be reproduced MAY remain valid as historical evidence, but the receipt MUST state that replay is unavailable.

---

## 17. Corpus and model-governance requirements

### 17.1 Corpus purpose

The ATS corpus exists to support:

- rule definition;
- deterministic fixtures;
- semantic-detector training;
- rule retrieval;
- hard-negative evaluation;
- repair evaluation;
- preservation testing; and
- rule promotion.

It is not merely a collection of “good” and “bad” prose.

### 17.2 Corpus record

Each corpus example SHOULD use a `TextExampleV1` record containing:

- example identifier;
- source artifact and span;
- repository or domain group;
- profile;
- rule identifier;
- label;
- rationale;
- protected impact;
- adjudicator identity;
- provenance;
- license or use authority;
- synthetic or natural status;
- mutation operator when synthetic;
- split group; and
- related accepted or rejected finding identifiers.

### 17.3 Labels

Canonical example labels are:

- `conforming`
- `violation`
- `near_miss`
- `hard_negative`
- `exception`
- `ambiguous`
- `insufficient_context`

“Positive” and “negative” SHOULD be avoided in stored records because they are ambiguous between rule applicability and writing quality.

### 17.4 Natural corpus extraction

When mining repository documents, the corpus pipeline SHOULD preserve:

- complete local context;
- heading and profile context;
- glossary and policy context;
- source revision;
- author or model provenance where available;
- subsequent edits;
- review comments;
- acceptance outcomes; and
- downstream defects or reversals.

An isolated sentence SHOULD not be labeled when the rule depends on document context that was discarded.

### 17.5 Synthetic mutations

Synthetic mutations SHOULD change one semantic feature at a time.

Recommended operators include:

- delete a qualifier;
- change a WEP band;
- exchange likelihood and confidence;
- exchange `MAY`, `CAN`, `SHOULD`, and `MUST`;
- remove the actor;
- merge two obligations;
- remove a unit or denominator;
- alter a threshold boundary;
- flip negation;
- change `some` to `all`;
- reverse causal direction;
- change association to causation;
- delete an exception;
- remove contrary evidence;
- turn an assumption into an observation;
- remove source attribution;
- delete a reversal condition;
- strengthen evidential force;
- insert a zero-information restatement;
- bury the key judgment; and
- introduce a second plausible antecedent.

Synthetic examples MUST be tagged. They MUST NOT be counted as independent real-world evidence of rule prevalence or user value.

### 17.6 Hard negatives

Every semantic rule corpus MUST include hard negatives that contain the expected surface cue without the violation.

Examples include:

- a long but coherent sentence;
- a passive sentence with an irrelevant actor;
- a technical term used precisely;
- repeated terminology needed for referential stability;
- a causal verb backed by formal system semantics;
- “may” inside a quotation;
- “should” used in a non-normative discussion of another document;
- a paragraph with several sentences performing one conceptual move; and
- a summary that omits content authorized by its retention contract.

### 17.7 Split discipline

Training, development, and evaluation splits MUST prevent leakage by grouping on applicable dimensions:

- source document;
- repository or project;
- author;
- source-model family;
- template;
- mutation operator;
- domain; and
- near-duplicate cluster.

A random sentence split is nonconforming for semantic-detector evaluation.

### 17.8 Conceptual gate

A semantic rule evaluation SHOULD include a conceptual gate in which:

- direct rule terms are absent;
- diagnostic phrases are paraphrased;
- the violation remains material;
- lexical baselines perform poorly; and
- humans can still adjudicate the case from available context.

A rule SHOULD NOT be promoted based only on examples that contain its canonical terminology.

### 17.9 Annotation

Material semantic examples SHOULD receive at least two independent adjudications before becoming gold data.

Disagreement MUST be retained and categorized. A forced majority label MUST NOT erase a genuine ambiguity in the standard or source.

### 17.10 Evaluation metrics

Semantic-detector evaluation SHOULD report:

- per-rule precision and recall;
- calibration;
- abstention coverage and selective risk;
- first-finding utility;
- accepted-finding rate;
- correction rate;
- reviewer time per useful finding;
- false-positive burden per thousand words;
- out-of-domain performance;
- performance on conceptual gates; and
- performance on hard negatives.

A single macro score is insufficient.

### 17.11 Preservation evaluation

Transformation systems SHOULD be evaluated on:

- P0 exact retention;
- P1 relation recall;
- claim recall;
- qualification and boundary recall;
- unsupported strengthening;
- source attribution retention;
- answerability of boundary questions;
- human decision accuracy;
- navigation latency; and
- subjective effort.

A fluent rewrite that fails a protected invariant is a failure regardless of preference score.

### 17.12 Model training target

The first ATS learned model SHOULD be a rule-conditioned critic or preservation verifier, not an unconstrained writer.

A rule-conditioned critic SHOULD map:

```text
profile + text + context + candidate rule + glossary
→ applicability + evidence spans + interpretations + impact + abstention
```

A repair model SHOULD be trained only after the corpus contains enough accepted and rejected findings to define desired repair behavior.

### 17.13 Data provenance

Training data MUST record use authority. Private repository text MUST NOT be used outside its authorized environment or for external model training without explicit permission.

Derived embeddings, labels, and synthetic mutations SHOULD inherit the source's handling policy.

---

## 18. Rule and model promotion

### 18.1 Lifecycle

Rules and learned detectors use this promotion lifecycle:

```text
draft → shadow → advisory → required
```

A rule state MAY also move to `deprecated` and then `retired`. A retired identifier MUST NOT be reused.

### 18.2 Promotion evidence

Promotion requires evidence for:

- rule-definition stability;
- positive, violation, exception, and hard-negative coverage;
- parser and source-mapping reliability;
- detector calibration;
- conceptual-gate performance;
- out-of-domain behavior;
- abstention behavior;
- reviewer burden;
- actionability;
- repair safety when autofix exists;
- downstream value; and
- independent validation.

### 18.3 Promotion to advisory

A semantic rule MAY become advisory when:

- its wording is stable;
- reviewers can adjudicate it consistently;
- its first-finding utility exceeds the preregistered threshold;
- false-positive burden is acceptable; and
- the detector abstains rather than guessing outside its competence.

### 18.4 Promotion to required

A learned semantic rule MUST NOT become required until:

- the operating threshold and calibration are frozen;
- project-disjoint and domain-disjoint evaluation passes;
- hard-negative precision passes;
- known failure modes are documented;
- required-context absence produces `UNAVAILABLE` or abstention;
- an override and exception path exists;
- an independent acceptance authority approves promotion; and
- a rollback policy exists.

### 18.5 No promotion by aggregate score alone

A high aggregate score MUST NOT compensate for catastrophic errors on material subtypes such as:

- polarity changes;
- deontic-force changes;
- causal overclaim;
- source-attribution loss;
- probability-band changes; or
- omitted exceptions.

### 18.6 Promotion receipts

Every promotion MUST produce a receipt containing:

- rule and detector versions;
- preregistered gates;
- evaluation corpus hashes;
- split policy;
- metrics;
- failure cases;
- reviewer decision;
- effective policy date; and
- rollback trigger.


---

## 19. Versioning and extension

### 19.1 Specification versioning

ATS-1 uses semantic versioning for the specification package.

- A **patch** version clarifies wording, fixes examples, or corrects schemas without changing which conforming artifacts are accepted.
- A **minor** version adds backward-compatible optional fields, advisory rules, or registered extensions.
- A **major** version changes normative semantics, required fields, force vocabulary, conformance behavior, or accepted artifact classes.

Before final `1.0.0`, draft revisions MAY make breaking changes. Every downstream artifact MUST bind the exact draft version.

### 19.2 Rule versioning

Rule identifiers are stable. Each rule also has a rule version.

A rule-version change that changes accepted or rejected cases MUST trigger re-evaluation of affected receipts. A mere rationale or example correction MAY avoid re-evaluation when normative semantics are unchanged.

### 19.3 Lexicon versioning

Calibrated-force lexicons are versioned independently.

Changing:

- a canonical phrase;
- a numeric range;
- an interval boundary;
- a confidence definition;
- a causal-force definition; or
- a deontic definition

is a breaking change for artifacts that use the affected field.

### 19.4 Schema versioning

Machine objects include a `schema_version` discriminator.

An implementation MUST reject an unknown major schema version. It MAY accept an unknown optional field only when the schema permits it and the field does not alter conformance semantics.

### 19.5 Extensions

Extension identifiers MUST use a namespace that cannot collide with core ATS identifiers.

Recommended forms:

```text
X-<ORG>-<PROFILE>-<VERSION>
ATS-X-<ORG>-<CATEGORY>-<NUMBER>
urn:ats:x:<org>:<object>:<version>
```

An extension MUST declare:

- governing organization;
- version;
- base ATS version;
- added profiles, rules, fields, or lexicons;
- conflict-resolution policy; and
- whether it strengthens or weakens core behavior.

An extension MUST NOT redefine a core identifier.

### 19.6 Deprecation

A deprecated rule or field remains interpretable for at least one declared compatibility window.

Deprecation metadata MUST identify the replacement and migration path.

### 19.7 Supersession

A receipt, policy, requirement, or artifact may be superseded. Supersession MUST be typed and directional.

The superseding object MUST identify:

- the predecessor;
- reason;
- effective time;
- compatibility status; and
- downstream objects requiring revalidation.

---

## 20. Security, safety, and failure behavior

### 20.1 Misleading fluency as a hazard

ATS-1 treats fluent but semantically weakened prose as a material risk.

A system SHOULD test specifically for:

- confidence unsupported by evidence;
- binary framing of unresolved tradeoffs;
- omission of reversal conditions;
- repetition presented as corroboration;
- examples presented as prevalence evidence;
- model output presented as source evidence;
- causal claims inferred from association; and
- clean headings that imply resolution where evidence is insufficient.

### 20.2 Prompt and source injection

A linter or critic that processes untrusted text MUST treat instructions inside the artifact as content unless policy explicitly designates them as executable configuration.

Quoted text, code, comments, and examples MUST NOT alter detector policy or authority.

### 20.3 Adversarial evasion

Implementations SHOULD test evasion through:

- homoglyphs;
- unusual punctuation;
- hidden markup;
- code formatting around modal terms;
- sentence fragments;
- tables that split one requirement across cells;
- footnotes that reverse a claim;
- links whose anchor text changes force;
- negation in parentheticals; and
- contradictory captions or labels.

### 20.4 Sensitive evidence

A finding MAY cite a redacted source. The receipt MUST preserve enough metadata to establish that evidence existed and was reviewed by authorized parties.

Redaction MUST NOT be represented as evidence unavailability when the authorized adjudicator had access.

### 20.5 Fail-closed conditions

An implementation MUST fail closed for required conformance when:

- policy currentness is unknown;
- source hashes do not match;
- required schemas cannot be validated;
- required parsing fails;
- a required detector is unavailable;
- material P0 or P1 deltas are unresolved;
- a required finding is unresolved; or
- authority for an exception or adjudication cannot be established.

### 20.6 Honest insufficiency

`UNAVAILABLE` and `INSUFFICIENT_EVIDENCE` are valid outcomes.

A system MUST prefer a typed insufficiency to an unsupported pass, confident rewrite, or guessed interpretation.

---

## 21. Canonical worked examples

### 21.1 `ASSESS`: conforming example

```text
Question
Should Arq move the acceptance kernel from Python to Rust after the state model stabilizes?

Key judgment
A Rust migration is likely (55–80%) to reduce invalid-state defects in the acceptance kernel after the transition model is stable.

Confidence
Moderate. Rust can encode closed transitions and construction invariants directly, but the current evidence is architectural and observational rather than a controlled migration ablation. Repository coverage is broad enough to identify recurring invalid-state risks, but no project-disjoint defect-rate comparison exists.

Supporting evidence
1. Current acceptance failures cluster around illegal intermediate states and stale-policy transitions.
2. The destination design has a closed state graph and content-addressed evidence objects.
3. Existing Rust components have prevented several construction-time invalid states that remain runtime checks in Python.

Contrary evidence and alternatives
The Python implementation has fast iteration and mature integration coverage. A smaller typed Python kernel or generated state-transition layer may capture part of the benefit at lower migration cost. No controlled comparison has been run.

Assumptions
The state model will remain substantially stable after the current envelope-expansion work. If the state graph continues to change materially, a Rust port could encode uncertainty rather than remove it.

Boundary
This assessment applies to the acceptance kernel. It does not imply that the policy-fluid orchestration plane should migrate.

Update indicators
Upgrade the likelihood if a prototype eliminates at least two currently runtime-only invalid states without increasing change lead time materially. Downgrade it if the prototype requires frequent unsafe escape hatches or doubles iteration time over three representative changes.

Recommendation
Prototype one closed transition family in Rust and compare defect prevention, integration cost, and change latency before authorizing a broad migration.
```

Why it conforms:

- the key judgment appears early;
- likelihood and confidence are separate;
- the confidence basis includes strengths and limitations;
- alternatives and contrary considerations are explicit;
- the principal assumption and consequence if false are visible;
- the boundary prevents an overbroad conclusion; and
- update indicators can change the assessment.

### 21.2 `ASSESS`: nonconforming example

```text
Rust should probably make Arq much safer, and we are highly confident because the system is very typestatey. It is obviously the right destination language.
```

Expected findings include:

- `ATS-DEON-003`: “should” is being used as forecast or recommendation without typed force;
- `ATS-EPI-007`: “probably” is not normalized to the ATS-1 scale;
- `ATS-EPI-004`: likelihood and confidence are conflated;
- `ATS-EPI-005`: high confidence lacks an inspectable basis;
- `ATS-EVID-002`: “much safer” exceeds the evidence and lacks a metric;
- `ATS-EVID-001`: judgment and recommendation are not distinguished;
- `ATS-DISC-003`: “obviously” adds attitude rather than evidence; and
- profile failure: no boundary, alternatives, assumption, or update indicator.

### 21.3 `SPECIFY`: conforming example

```text
Requirement ID: REQ-POLICY-017

Statement
When the executor presents an acceptance receipt whose `policy_sha256` differs from the current resolved policy snapshot, the verifier MUST reject the receipt before the acceptance transition.

Acceptance criterion
Given a receipt with a stale `policy_sha256`, the verifier returns `refused_stale_policy`, emits no accepted-change transition, and records the current and presented policy hashes in the rejection receipt.

Authority
Arq acceptance-policy kernel.

Exception
None.

Rationale
A receipt proves conformance only under the policy used to evaluate it. Accepting it under a different policy would transfer authority from the current policy to stale evidence.
```

Structured slots:

```yaml
actor: verifier
deontic: MUST
action: reject
object: acceptance receipt
trigger: executor presents a receipt
condition: presented policy_sha256 differs from current policy_sha256
timing: before acceptance transition
acceptance_criterion: stale-policy fixture yields refused_stale_policy and no accepted transition
source_authority: Arq acceptance-policy kernel
exception: none
```

### 21.4 `SPECIFY`: nonconforming example

```text
The system should normally reject stale receipts and log them quickly.
```

Expected findings include:

- `ATS-REQ-001`: “the system” does not identify the responsible component;
- `ATS-DEON-003`: `should` is defeasible but no override policy is given;
- `ATS-SCOPE-001`: “normally” hides an exception set;
- `ATS-REQ-002`: reject and log are two obligations;
- `ATS-TIME-002`: “quickly” is not an observable timing boundary;
- `ATS-REQ-003`: trigger, stale definition, acceptance criteria, and exceptions are unresolved; and
- profile failure: no stable requirement identifier.

### 21.5 Transformation: lost qualification

Source:

```text
The selector is likely (55–80%) to improve first-result utility on multi-topic conceptual queries, but it cannot recover candidates absent from lexical retrieval.
```

Bad rewrite:

```text
The selector will improve retrieval quality.
```

Deltas:

```yaml
- type: likelihood_changed
  from: likely
  to: implicit_certainty
- type: scope_changed
  removed: multi-topic conceptual queries
- type: relation_changed
  removed: qualification
- type: omitted
  claim: cannot recover candidates absent from lexical retrieval
- type: evidential_force_changed
  from: assessment
  to: unqualified assertion
```

The rewrite is shorter and easier to parse, but preservation fails.

### 21.6 Summary with retention contract

Source obligations:

- C1: The selector is likely to improve first-result utility on multi-topic conceptual queries.
- C2: It cannot recover candidates absent from lexical retrieval.
- C3: Confidence is moderate because repository coverage is narrow.
- C4: The next test is project-disjoint conceptual evaluation.

Retention contract:

```yaml
transformation: summarize
reader_task: decide_next_test
mandatory_claims: [C1, C2, C4]
mandatory_fields:
  C1: [scope, likelihood]
mandatory_relations:
  - [C2, qualifies, C1]
allowed_omissions: [C3]
required_questions:
  - Can the selector recover missing lexical candidates?
  - What test should run next?
```

Conforming summary:

```text
The selector is likely (55–80%) to improve first-result utility on multi-topic conceptual queries, but it cannot recover candidates missing from lexical retrieval. Run a project-disjoint conceptual evaluation next.
```

The omission of C3 is authorized. The qualification and next action remain recoverable.

---

## Appendix A. Elements of Technical Judgment

This appendix is informative. It is the compact author-facing companion to the normative standard.

1. **Put the load-bearing statement first.**
2. **Give each concept one term and each term one meaning.**
3. **Use the exact domain term; define it once when necessary.**
4. **Name the actor when action, responsibility, or authority matters.**
5. **Separate observation, assumption, inference, judgment, and recommendation.**
6. **Make scope, quantity, units, thresholds, and time explicit.**
7. **Calibrate probability; do not hide it inside modal verbs.**
8. **State confidence separately and give its basis.**
9. **Match evidential and causal verbs to what the basis supports.**
10. **Preserve conditions, contrasts, exceptions, and reversal points.**
11. **Make each paragraph perform one conceptual move.**
12. **Remove words before removing relations.**

Corollaries:

- A long sentence can be correct when it encodes one tightly coupled relation.
- Several short sentences can be costly when the reader must reconstruct their relationship.
- Rephrasing the same conclusion is not additional evidence.
- A precise technical word is often easier than a vague common paraphrase.
- “But,” “only,” “unless,” and “despite” frequently carry the decisive meaning.
- “Clearly,” “obviously,” “simply,” and “just” usually report attitude rather than evidence.
- “Significant,” “material,” “large,” and “meaningful” need a comparison or threshold.
- A summary is a projection contract, not a license to delete the condition that makes the conclusion true.

---

## Appendix B. Canonical object identifiers

| Object | `schema_version` value |
|---|---|
| Text intermediate representation | `ats.text_ir.v1` |
| Policy snapshot | `ats.policy_snapshot.v1` |
| Policy exception | `ats.policy_exception.v1` |
| Rule | `ats.rule.v1` |
| Rule registry | `ats.ruleset.v1` |
| Force lexicon | `ats.force_lexicon.v1` |
| Finding | `ats.finding.v1` |
| Adjudication | `ats.adjudication.v1` |
| Retention contract | `ats.retention_contract.v1` |
| Preservation report | `ats.preservation_report.v1` |
| Acceptance receipt | `ats.acceptance_receipt.v1` |
| Corpus example | `ats.text_example.v1` |
| Capability declaration | `ats.capability.v1` |
| Package manifest | `ats.package_manifest.v1` |

---

## Appendix C. Canonical serialization and hashes

Normative ATS-1 JSON objects MUST conform to JSON Schema Draft 2020-12.

Content-addressed objects MUST:

1. omit the object's own hash field from the hash input;
2. serialize the remaining object with RFC 8785 JCS;
3. hash the canonical bytes with SHA-256;
4. encode the digest as lowercase hexadecimal; and
5. prefix identifiers with the object type when used as human-facing IDs.

Example:

```text
ats-policy-sha256:4f23…
ats-receipt-sha256:91ac…
```

Binary attachments MUST be hashed over their exact bytes. A text normalization step MUST produce and retain a separate normalized hash rather than replacing the source hash.

---

## Appendix D. Informative prior art and references

The following sources informed ATS-1. They are informative, not incorporated by reference.

1. ASD Simplified Technical English Maintenance Group, **ASD-STE100 Simplified Technical English, Issue 9**, 2025. Official distribution: <https://www.asd-ste100.org/STE_downloads.html>
2. Office of the Director of National Intelligence, **ICD 203: Analytic Standards**. <https://www.dni.gov/files/documents/ICD/ICD-203.pdf>
3. S. Bradner, **RFC 2119: Key words for use in RFCs to Indicate Requirement Levels**. <https://www.rfc-editor.org/info/rfc2119/>
4. B. Leiba, **RFC 8174: Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words**. <https://www.rfc-editor.org/info/rfc8174/>
5. A. Rundgren, B. Jordan, and S. Erdtman, **RFC 8785: JSON Canonicalization Scheme**. <https://www.rfc-editor.org/info/rfc8785/>
6. IARPA, **REASON: Rapid Explanation, Analysis, and Sourcing Online — Technical Description**. <https://www.iarpa.gov/images/PropsersDayPDFs/REASON/REASONTechnicalDescriptionfinal122222-1.pdf>
7. INCOSE Requirements Working Group, **Guide to Writing Requirements v4 — Summary Sheet**. <https://www.incose.org/docs/default-source/working-groups/requirements-wg/guidetowritingrequirements/incose_rwg_gtwr_v4_summary_sheet.pdf>
8. NASA, **Formal Requirements Elicitation with FRET**. <https://ntrs.nasa.gov/citations/20200001989>
9. OASIS, **Darwin Information Typing Architecture (DITA) Version 1.3**. <https://docs.oasis-open.org/dita/dita/v1.3/>
10. U.S. Securities and Exchange Commission, **A Plain English Handbook**. <https://www.sec.gov/pdf/handbook.pdf>
11. JSON Schema, **Draft 2020-12**. <https://json-schema.org/draft/2020-12>

---

## Appendix E. Open ratification questions

The normative kernel is complete enough for implementation, but these questions require empirical closure before final `1.0.0` ratification:

1. Should `ATS-EPI-006` require an update indicator for every material judgment or only judgments above a materiality threshold defined by policy?
2. Should first-use WEP ranges be mandatory in expert-only documents after a persistent scale is visible in the interface?
3. What reviewer-load threshold should govern the default coach finding budget: five or eight?
4. Which semantic rules can safely move from advisory to required after corpus evaluation?
5. What minimum evidence is necessary for a `high` confidence label in empirical versus formal domains?
6. Should `SPECIFY` require acceptance criteria for `SHOULD` statements or only for `MUST` and `MUST NOT`?
7. What exact boundary-question battery best predicts downstream conceptual retention?
8. Should the final standard register `DECIDE` and `DELTA` as stable profiles in ATS-1.1 or reserve them for ATS-2?

These are explicit ratification questions, not gaps that an implementation may resolve silently. A project policy MAY choose an answer, but it MUST record the choice and bind it in the policy snapshot.


# ATS Annotation Guide V0

Status: repository protocol, version 0, for ATS-1 `1.0.0-draft.1`.
Record schema: `schemas/ats_judgment_v1.schema.json`. Context schema:
`schemas/ats_context_bundle_v1.schema.json`. Example schema: the normative
`ats_text_example_v1.schema.json`.

## 0. How to read this document

### 0.1 Normative language

ATS-1 §1.3 applies: **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** carry normative
force only in uppercase. `CAN` and `CANNOT` state capability. Obligations are identified `AG-n`; a
retired identifier MUST NOT be reused.

**Reference convention.** `ATS-1 §n`, and a bare `§n` inside a grounding note or parenthetical,
name a section of `ATS-1_SPEC.md`. A reference to a section of this document is always written
`this document §n`. Other protocol documents are referenced by filename.

### 0.2 Authority of an obligation

Each obligation is tagged in this document §5 as **ATS-1 normative**, **ATS-1 raised** (an ATS-1 §17.x `SHOULD`
raised to a repository `MUST`), **Repo schema**, or **Repository policy**. An obligation marked
**Repository policy** MUST NOT be cited as an ATS-1 conformance requirement.

### 0.3 What an annotator produces

One `JudgmentV1` record: a label for one example, under one rule, at one rule version, with an
evidence-span citation and a rationale tied to the rule's normative statement. An annotator does not
decide whether the artifact conforms overall, and does not disposition a finding.

---

## 1. The eleven annotation requirements

**AG-1. Complete context bundles.** An annotator MUST be given a `ContextBundleV1` whose required
context slots are populated or explicitly typed as unavailable. An annotator MUST NOT be shown a
truncated bundle presented as complete; when `context_completeness` is `partial` or `insufficient`,
that value MUST be visible in the annotation surface.

**AG-2. One rule judgment at a time.** Each `JudgmentV1` carries exactly one `rule_id`. An annotator
MUST NOT combine several rules in one judgment, and MUST NOT let a defect under one rule change the
label under another. The same span MAY receive several judgments, one per rule.

**AG-3. At least two independent judgments for material semantic examples.** A material semantic
example MUST receive at least two independent adjudications before becoming gold data. "Independent"
means two distinct `annotator_id` values, neither having seen the other's label at submission time.

**AG-4. Blind annotation where practical.** Annotation SHOULD be blind: the annotator sees the
context bundle and the rule, not other labels, not the mining signal's guess, and not the detector's
output. When an annotation is blind, the judgment MUST set `blind: true`; when it is not, `blind`
MUST be `false` and the reason SHOULD be recorded in `extensions`.

**AG-5. Exact evidence spans.** A judgment MUST cite the smallest sufficient spans that establish why
the rule may apply. `evidence_spans` MUST be non-empty for a `violation` label — the schema enforces
this — and SHOULD be non-empty for `near_miss`, `hard_negative`, and `exception`. Citing the whole
artifact when a smaller set is available is nonconforming.

**AG-6. Rationale tied to normative rule text.** `rationale` MUST reference the rule's
`normative_statement` from `rules/ats_rules_v1.yaml` or the ATS-1 section that states it. An
annotator SHOULD quote it in `normative_statement_quoted`. A rationale that expresses a style
preference, or that says only that the text is unclear, MUST NOT be accepted.

**AG-7. Explicit `insufficient_context`.** When the rule cannot be decided from the bundle, the label
MUST be `insufficient_context`, and `requested_additional_context` MUST name what is missing — the
schema requires at least one entry. Guessing MUST NOT be substituted for a typed insufficiency.

**AG-8. Explicit `ambiguous`.** When the span admits two or more materially distinct readings and
context does not resolve them, the label MUST be `ambiguous` and `ambiguity_category` MUST NOT be
`none`. The annotator SHOULD enumerate the materially distinct interpretations in `rationale`.

**AG-9. No inference from repository acceptance alone.** An annotator MUST NOT derive a label from
`review_state`. That a document was merged, reverted, superseded, or rejected is context, not a
conformance verdict.

**AG-10. No access to the other annotator's label before submission.** The annotation tool MUST NOT
reveal another annotator's label, rationale, or spans for the same `(example_id, rule_id)` pair until
the current annotator's judgment is submitted and sealed.

**AG-11. Retained disagreements.** Disagreement MUST be retained and categorized. A judgment MUST NOT
be edited or deleted to produce agreement; the records are append-only and the adjudication retains
all originals verbatim.

### 1.1 Additional obligations that follow from the schema

**AG-12.** A judgment MUST carry `rule_version` and `tool_version`, so a label CAN be re-scoped when
a rule's wording changes. A label produced under an earlier rule version MUST NOT be silently carried
forward across a rule amendment (ATS-1 §19.2); the schema's `needs_rule_revision` condition records
the boundary.

**AG-13.** `protected_impact` MUST record the preservation classes the annotator judges affected
(`P0`, `P1`, `P2`, per ATS-1 §11.3.1–§11.3.3). It MUST NOT be copied from the rule record without
inspecting the span: a rule whose record lists `P0` and `P1` MAY be violated in a way that affects
only one of them.

**AG-14.** `annotation_confidence` MUST be one of `low`, `moderate`, `high`, and MUST describe the
annotator's confidence in the label only (this document §2.4).

**AG-15.** An annotator MUST NOT label a span under a rule whose `effective_state` is `disabled` for
the applicable profile and scope. The correct outcome is no record, not `conforming`.

---

## 2. Six distinctions an annotator MUST keep apart

These six are routinely conflated, and each conflation corrupts a different part of the corpus.

| # | Concept | Whose property | Where it lives | ATS-1 |
|---|---|---|---|---|
| 1 | Rule applicability | the rule against the span | `applies` / `does_not_apply` / `abstain` | §13.2 |
| 2 | Actual conformance | the artifact | the seven `label` values | §5.2, §17.3 |
| 3 | Detector confidence | the implementation | `detector_confidence` on a finding | §4.9, §13.5 |
| 4 | Annotator confidence | the annotator | `annotation_confidence` on a judgment | milestone; §4.9 by analogy |
| 5 | Assessment confidence in the source text | the analyzed artifact's author | `force.assessment_confidence` in the IR | §4.8, §8.8–§8.10 |
| 6 | Adjudication authority | the governance model | `CorpusAdjudicationV1.adjudicator`; for findings, an authorized human | §13.7, §14.11 |

**AG-16.** These six MUST NOT be merged in a record, a rationale, or a rendered surface. In
particular, detector confidence MUST NOT be presented as assessment confidence (ATS-1 §4.9), and
`annotation_confidence` MUST NOT be rendered as either.

### 2.1 Rule applicability is not conformance

Applicability asks whether the rule reaches the span at all. Conformance asks whether the span
satisfies it.

**Worked contrast.** Under `ATS-REQ-001` ("Every material requirement MUST identify the responsible
actor explicitly or through a mechanically unambiguous block"):

- ATS-1 §21.1 key judgment — "A Rust migration is likely (55–80%) to reduce invalid-state defects in
  the acceptance kernel after the transition model is stable." — is a judgment, not a requirement.
  `ATS-REQ-001` **does not apply**. No label is recorded for this rule.
- ATS-1 §21.4 — "The system should normally reject stale receipts and log them quickly." —
  `ATS-REQ-001` **applies** and is **violated**: ATS-1 itself lists `ATS-REQ-001` as an expected
  finding because "the system" does not identify the responsible component.

The error to avoid is recording `conforming` for the first case. A rule that does not apply produces
no example under that rule; it does not produce a passing one.

### 2.2 Conformance is not a single verdict

ATS-1 §5.2 makes conformance a five-dimension vector, never averaged, and §5.3 forbids a bare
conformance claim. A judgment's `label` is a rule-scoped verdict, not an artifact verdict.

**Worked contrast.** The ATS-1 §21.6 conforming summary — "The selector is likely (55–80%) to improve
first-result utility on multi-topic conceptual queries, but it cannot recover candidates missing from
lexical retrieval. Run a project-disjoint conceptual evaluation next." — is `conforming` under
`ATS-PRES-001`, because its retention contract authorizes the omission of C3. The same text as a
standalone `ASSESS` artifact would fail `profile`, since it has no confidence basis, no alternatives,
and no update indicator. ATS-1 §11.8 states exactly this: a compressed output CAN report
`preservation: PASS` while reporting `profile: FAIL`. An annotator MUST NOT convert a
`conforming` label under one rule into a claim about the artifact.

### 2.3 Detector confidence is implementation metadata

**Worked contrast.** A deterministic detector that finds `likelihood.term: likely` with
`lower: 0.55`, `upper: 0.80` matching the lexicon reports `detector_status: deterministic` and no
probability at all (ATS-1 §13.5). A future semantic detector examining ATS-1 §21.2 —
"Rust should probably make Arq much safer, and we are highly confident because the system is very
typestatey." — might report `detector_confidence: 0.9` for `ATS-EPI-004`. Neither number belongs in a
`JudgmentV1`, and neither may be rendered in the analyzed artifact as if the artifact's author were
that confident.

**AG-17.** An annotator MUST NOT read a detector's confidence before submitting a judgment (AG-4),
and MUST NOT copy it into `annotation_confidence`.

### 2.4 Annotator confidence is confidence in the label

**Worked contrast.** For ATS-1 §21.2 under `ATS-EPI-004`, an annotator records
`label: violation`, `annotation_confidence: high` — the conflation of "probably" and "highly
confident" in one clause is unmistakable. For a borderline `ATS-DISC-001` ordering case, the same
annotator might record `label: violation`, `annotation_confidence: low`. The label is the verdict;
the confidence describes how sure the annotator is of that verdict, and nothing about the text's own
epistemic state.

### 2.5 Assessment confidence belongs to the analyzed text

ATS-1 §4.8: assessment confidence is the robustness of an assessment to plausible changes in
evidence, assumptions, interpretation, and environmental conditions. It is not the probability that
the assessed event occurs, and it is not a property of the annotation.

**Worked contrast.** ATS-1 §21.1 carries two separate things:

- a likelihood — "likely (55–80%)";
- an assessment confidence — "Moderate. Rust can encode closed transitions and construction
  invariants directly, but the current evidence is architectural and observational rather than a
  controlled migration ablation."

An annotator judging `ATS-EPI-005` inspects that basis text and asks whether it is inspectable and
whether its dimensions are stated. `annotation_confidence: high` on that judgment says the annotator
is sure the basis is adequate; it does not upgrade the artifact's `moderate` to `high`.

### 2.6 Adjudication authority is not the annotator's

**AG-18.** An annotator produces a judgment. An annotator MUST NOT write a `CorpusAdjudicationV1`
for an example they judged, MUST NOT set `gold_eligible`, and MUST NOT decide a `final_state`.

**Worked contrast.** Two annotators split on ATS-1 §13.4's example, "The system may reject stale
receipts." One records `violation` under `ATS-DEON-002`; the other records `ambiguous` with
`ambiguity_category: multiple_valid_interpretations`. Neither annotator resolves the split. A later
adjudication, when separately authorized, records `disagreement_category` and `final_state` in the
adjudication schema. Separately, and not in the corpus at all, disposition of a *finding
on a live artifact* rests with an authorized human or an explicitly governed external acceptance
system (ATS-1 §14.11).

---

## 3. Worked examples: all seven labels

Each example gives the span, the rule, the label, the rationale shape, and the grounding. Spans are
quoted from ATS-1 §21 (canonical worked examples) and §13.4 wherever the specification supplies
suitable material.

### 3.1 `conforming`

**Span** (ATS-1 §21.1, key judgment):

> A Rust migration is likely (55–80%) to reduce invalid-state defects in the acceptance kernel after
> the transition model is stable.

**Rule:** `ATS-EPI-002` — "The first material WEP use in a section MUST include its numeric display
range inline."

**Label:** `conforming`. `annotation_confidence: high`. `protected_impact: []` is not permitted by the
example schema's intent, so the annotator records the classes the rule protects and judges them
unaffected: `["P0","P2"]` with a rationale stating no impact occurred.

**Rationale shape:** the span is the first material use of a canonical WEP in its section, and it
carries the lexicon display range `55–80%` inline, which is what §8.4 requires.

**Required context:** the section boundary, so "first material use in a section" CAN be decided.
Without it, the correct label is `insufficient_context` (this document §3.7).

### 3.2 `violation`

**Span** (ATS-1 §21.2, the nonconforming `ASSESS` example):

> Rust should probably make Arq much safer, and we are highly confident because the system is very
> typestatey. It is obviously the right destination language.

**Rule:** `ATS-EPI-004` — "Likelihood and assessment confidence MUST be represented as distinct
fields or labeled sentences."

**Label:** `violation`. `annotation_confidence: high`. `protected_impact: ["P0","P1"]`.

**Evidence spans:** the smallest sufficient span is "should probably … we are highly confident",
not the whole paragraph (ATS-1 §13.3).

**Rationale shape:** "probably" expresses a likelihood and "highly confident" expresses an assessment
confidence; the clause presents them as one graded claim, so the two are not distinct. ATS-1 §21.2
lists `ATS-EPI-004` among the expected findings for exactly this text.

**Note.** The same span also violates `ATS-EPI-007` ("probably" is not normalized to the ATS-1
scale), `ATS-EPI-005` (high confidence with no inspectable basis), `ATS-DEON-003`, `ATS-EVID-001`,
and `ATS-EVID-002`, each of which ATS-1 §21.2 names. Per AG-2 those are separate judgments, each with
its own record.

### 3.3 `near_miss`

**Span** (derived from ATS-1 §21.3 by weakening only the acceptance criterion):

> Requirement ID: REQ-POLICY-017. When the executor presents an acceptance receipt whose
> `policy_sha256` differs from the current resolved policy snapshot, the verifier MUST reject the
> receipt before the acceptance transition.
> Acceptance criterion: the verifier rejects the receipt and the rejection is observable in the
> rejection receipt.

**Rule:** `ATS-REQ-003` — every applicable requirement slot is resolved, and every `MUST` carries an
acceptance criterion.

**Label:** `near_miss`. `annotation_confidence: moderate`. `protected_impact: ["P0"]`.

**Rationale shape:** ATS-1 §9.3.9 states two things at different levels. The acceptance criterion
**MUST** identify observable evidence — satisfied here, since the rejection receipt is observable.
It **SHOULD** identify the evidence provider, fixture, environment, and threshold — not satisfied,
since no fixture or return value is named. Contrast the §21.3 conforming form, which names both:
"the verifier returns `refused_stale_policy`, emits no accepted-change transition, and records the
current and presented policy hashes."

**Why `near_miss` and not `violation`:** the rule's `MUST` clause is met. A `near_miss` records that
the example sits just inside the boundary; it is the class ATS-1 §12.9 requires a rule corpus to
contain alongside clear violations.

### 3.4 `hard_negative`

**Span** (a sentence that quotes ATS-1 §21.4 inside a discussion of the standard):

> ATS-1 §21.4 gives "The system should normally reject stale receipts and log them quickly" as its
> nonconforming `SPECIFY` example.

**Rules:** `ATS-REQ-001` and `ATS-DEON-003`.

**Label:** `hard_negative`. `annotation_confidence: high`. Hard-negative classes: `HN-6` (a modal
inside a quotation) and `HN-7` (lowercase `should` describing another document's text) — see
`ATS_CORPUS_PROTOCOL_V0.md` §6.

**Rationale shape:** every surface cue for both rules is present — "The system", lowercase "should",
"normally" — and no violation exists, because the sentence is quoted material discussing another
document rather than a normative statement of this artifact. ATS-1 §5.6 governs examples and quoted
material; ATS-1 §1.3 states that lowercase modal words carry no ATS-1 normative force.

**Required context:** the containing block and the preceding sentence, so the annotator CAN see that
the material is quoted. Stripped of that frame, the correct label is `insufficient_context`.

### 3.5 `exception`

**Span:**

> Under the aviation-safety documentation policy, the assessment states that the failure is highly
> probable in the declared envelope.

**Rule:** `ATS-EPI-003` — "A section MUST NOT mix noncanonical WEP synonyms with canonical ATS-1
output unless the alternate vocabulary is authorized."

**Label:** `exception`. `annotation_confidence: moderate`. `protected_impact: ["P0","P2"]`.

**Rationale shape:** "highly probable" is a noncanonical synonym that ATS-1 §8.3 names explicitly.
§8.3 also states the conditions under which it is admissible: the text is a quote, **a domain policy
explicitly requires the alternate vocabulary**, or an input-normalization report records the
noncanonical source wording. The second condition holds here, and the artifact's policy snapshot
carries a scoped exception moving `ATS-EPI-003` for this section under ATS-1 §6.3.

**Required context:** the `policy_context` slot of the bundle, resolving to the policy snapshot and
its exception. Without a resolvable policy snapshot the correct label is `insufficient_context`, not
`exception` — an annotator MUST NOT assume an authorization exists.

**Why `exception` and not `hard_negative`:** a hard negative carries the cue and no violation. An
exception carries the cue and *would be* a violation but for a declared, authorized condition. The
two are stored distinctly because ATS-1 §12.9 requires domain-specific exceptions as their own class.

### 3.6 `ambiguous`

**Span** (ATS-1 §13.4, verbatim):

> The system may reject stale receipts.

**Rule:** `ATS-DEON-002` — "`MAY` MUST express permission, not probability or capability."

**Label:** `ambiguous`. `ambiguity_category: multiple_valid_interpretations`.
`annotation_confidence: high` — the annotator is confident the case is ambiguous.
`protected_impact: ["P0"]`.

**Rationale shape:** ATS-1 §13.4 enumerates four materially distinct readings of this exact span:
permission ("is permitted to reject"), capability ("can reject"), probability ("might reject"), and
obligation ("is required to reject"). Local context does not select one. Under `ATS-DEON-002` the
label is `violation` on the probability and capability readings and `conforming` on the permission
reading, so the judgment cannot resolve to either without inventing the author's intent.

**What the annotator MUST do:** enumerate the interpretations in `rationale`, per ATS-1 §13.4. A
repair asks the author which reading was intended (§13.4, final paragraph); the annotator does not
choose for them.

**What the annotator MUST NOT do:** pick the modal reading of "may" because it is most common in the
corpus. That is the forced-label trap (§4.5).

### 3.7 `insufficient_context`

**Span** (ATS-1 §21.6, the conforming summary, presented without its retention contract):

> The selector is likely (55–80%) to improve first-result utility on multi-topic conceptual queries,
> but it cannot recover candidates missing from lexical retrieval. Run a project-disjoint conceptual
> evaluation next.

**Rule:** `ATS-PRES-001` — a transformation MUST preserve all retained P0 fields exactly unless an
authorized semantic change applies.

**Label:** `insufficient_context`. `annotation_confidence: high`.
`requested_additional_context: ["source_ir", "retention_contract", "authorizations"]`.

**Rationale shape:** the summary omits source obligation C3 ("Confidence is moderate because
repository coverage is narrow"). Whether that omission is authorized is decided by the retention
contract: ATS-1 §21.6 shows `allowed_omissions: [C3]`, which makes the omission authorized and the
summary conforming. Without the contract, the same span is indistinguishable from an unauthorized
loss of the confidence basis. Preservation is evaluated against the retention contract, not against
every source sentence (ATS-1 §11.8), so the required input is genuinely absent.

**Grounding for the label rather than a guess:** ATS-1 §20.6 requires a typed insufficiency in
preference to an unsupported pass or a guessed interpretation; §11.3 evaluation is `UNAVAILABLE`
rather than `PASS` when the required inputs are missing.

### 3.8 Label selection summary

**AG-19.** An annotator MUST select the label by this order of questions, stopping at the first that
resolves:

1. Is a required context slot missing such that the rule cannot be decided? → `insufficient_context`.
2. Does the rule apply to this span at all? If not, record no judgment for this rule (§2.1).
3. Is there a declared, authorized condition under which the rule's obligation does not bind here? →
   `exception`.
4. Do two or more materially distinct readings survive the available context? → `ambiguous`.
5. Is the rule's normative statement unsatisfied? → `violation`.
6. Is the rule's normative statement satisfied while a related `SHOULD` in the same section is not,
   or does the span sit immediately inside the rule's boundary? → `near_miss`.
7. Does the span carry the rule's expected surface cue while satisfying the rule? →
   `hard_negative`.
8. Otherwise → `conforming`.

**AG-20.** The order in AG-19 is a tie-breaking procedure, not a licence to skip a question. In
particular, question 1 MUST be asked before question 5: a missing input produces
`insufficient_context`, never `violation`.

---

## 4. Common traps

### 4.1 Labelling an isolated sentence whose rule depends on discarded context

**The trap.** A mining signal surfaces one sentence. The annotator labels it because the sentence
looks decidable on its own.

**Why it is wrong.** ATS-1 §17.4: an isolated sentence SHOULD not be labeled when the rule depends on
document context that was discarded. Half the rules in `rules/ats_rules_v1.yaml` are section-scoped
or document-scoped — `ATS-EPI-002` needs the section, `ATS-TERM-001` needs the scope, `ATS-TERM-003`
needs first-material-occurrence order, `ATS-EPI-006` needs the whole IR, `ATS-PRES-001` and
`ATS-PRES-002` need both IRs and the retention contract.

**AG-21.** When a rule's required context is not `present` in the bundle, the annotator MUST label
`insufficient_context` and name the missing slot. Deciding from the sentence alone MUST NOT be
accepted, even when the sentence "obviously" violates the rule.

### 4.2 Reading acceptance as conformance

**The trap.** The span comes from a merged document, so the annotator labels it `conforming`; or it
comes from a reverted commit, so the annotator labels it `violation`.

**Why it is wrong.** `review_state` records what a repository did, not what a rule says. ATS-1 §5.3
forbids a bare conformance claim: conformance is a vector over declared dimensions, produced by
evaluation. Nothing about a merge evaluates any rule.

**AG-22.** A rationale MUST NOT cite `review_state`, `acceptance_evidence`, `later_edit`, or
`review_comment` as the reason for a label. Those fields are context that CAN direct attention; they
CANNOT decide a rule. See `ATS_CORPUS_PROTOCOL_V0.md` §5 for the six non-inferences.

### 4.3 Treating a surface cue as a violation

**The trap.** The span contains "may", or a long sentence, or a causal verb, so the annotator labels
`violation`.

**Why it is wrong.** A matched phrase generates a candidate only. ATS-1 §17.6 requires the corpus to
contain hard negatives precisely because surface cues are not violations, and §10.13 states that
ATS-1 imposes no global sentence-word limit at all. Labelling cues as violations trains a lexical
detector that fails the conceptual gate (ATS-1 §17.8).

**AG-23.** An annotator MUST test the cue against the rule's normative statement and the twelve
hard-negative classes before recording `violation`. Where the cue is present and the violation is
not, the correct label is `hard_negative`, and that record MUST be stored (`ATS_CORPUS_PROTOCOL_V0.md`
CP-41).

### 4.4 Conflating annotator confidence with assessment confidence

**The trap.** The artifact says its assessment confidence is `moderate`, so the annotator sets
`annotation_confidence: moderate`. Or the annotator is unsure of the label and records that
uncertainty as though the *text* were hedged.

**Why it is wrong.** ATS-1 §4.8 defines assessment confidence as a property of the assessment in the
analyzed text; §4.9 defines detector confidence as implementation metadata that MUST NOT be presented
as assessment confidence. `annotation_confidence` is a third thing again: confidence in the label.

**AG-24.** `annotation_confidence` MUST be set from the annotator's own certainty about the label and
MUST NOT be derived from the artifact's `assessment_confidence.level` or from any detector output.
The two values are frequently different: an annotator CAN be highly confident that a `low`-confidence
assessment violates `ATS-EPI-005`.

### 4.5 Forcing a label to avoid `ambiguous`

**The trap.** The span admits two readings. The annotator picks the more likely one so the example
becomes usable gold data.

**Why it is wrong.** ATS-1 §17.9: a forced majority label MUST NOT erase a genuine ambiguity in the
standard or source. An ambiguity that is labelled away is worse than a missing example: it teaches a
detector to resolve ambiguity silently, which ATS-1 §13.4 and §16.7 both forbid.

**AG-25.** When two or more materially distinct interpretations survive the available context, the
label MUST be `ambiguous` with a non-`none` `ambiguity_category`, and the interpretations SHOULD be
enumerated. An annotator MUST NOT choose a reading in order to make the example gold-eligible;
`ambiguous_by_design` is a legitimate final state recorded by the adjudication schema.

### 4.6 Two further traps worth naming

**AG-26.** *Rule bleed.* An annotator who has just recorded a `violation` under one rule MUST re-read
the span against the next rule's normative statement rather than carrying the verdict across.
`ATS-1` §21.2 and §21.4 each list six or more distinct expected findings for one sentence precisely
because the rules are independent.

**AG-27.** *Impact inflation.* `protected_impact` MUST be judged from the span, not copied from the
rule record (AG-13). Recording `P0` on every violation destroys the ability to report the material
subtypes ATS-1 §18.5 requires to be reported separately.

---

## 5. Traceability

| Obligation | Grounding | Authority |
|---|---|---|
| AG-1 | ATS-1 §17.4 (complete local context); `ats_context_bundle_v1.schema.json` (`context_completeness`) | ATS-1 raised; Repo schema |
| AG-2 | Milestone: one rule judgment at a time; `ats_judgment_v1.schema.json` (single `rule_id`) | Repository policy, enforced by Repo schema |
| AG-3 | ATS-1 §17.9 ("at least two independent adjudications before becoming gold data") | ATS-1 raised |
| AG-4 | Milestone: blind annotation where practical; `ats_judgment_v1.schema.json` (`blind`) | Repository policy |
| AG-5 | ATS-1 §13.3 (smallest sufficient spans); `ats_judgment_v1.schema.json` (`violation` requires ≥ 1 span) | ATS-1 normative; Repo schema |
| AG-6 | `ats_judgment_v1.schema.json` (`rationale` description); ATS-1 §12.10, §16.8 | Repo schema |
| AG-7 | ATS-1 §20.6, §16.7, §13.2; `ats_judgment_v1.schema.json` conditional | ATS-1 normative; Repo schema |
| AG-8 | ATS-1 §13.4, §17.9; `ats_judgment_v1.schema.json` conditional | ATS-1 normative (§17.9 MUST) |
| AG-9 | Milestone: no inference from repository acceptance alone; ATS-1 §5.3, §17.4 | Repository policy |
| AG-10 | Milestone: no access to the other annotator's label before submission; ATS-1 §14.10 (independent verification) | Repository policy |
| AG-11 | ATS-1 §17.9 ("Disagreement MUST be retained and categorized") | ATS-1 normative |
| AG-12 | `ats_judgment_v1.schema.json` (`rule_version`, `tool_version`); ATS-1 §12.1 (a clarification that changes accepted or rejected cases requires a new rule version), §19.2 | Repo schema; the re-scoping obligation for corpus labels is Repository policy by analogy with ATS-1 §19.2 receipt re-evaluation |
| AG-13 | ATS-1 §11.3.1–§11.3.3, §18.5; `ats_judgment_v1.schema.json` (`protected_impact`) | Repo schema |
| AG-14 | `ats_judgment_v1.schema.json` (`annotation_confidence` description); ATS-1 §4.8, §4.9 | Repo schema |
| AG-15 | ATS-1 §6.2 (rule-state lattice), §5.4 | Repository policy |
| AG-16 | ATS-1 §4.8, §4.9, §13.5 | ATS-1 normative |
| AG-17 | ATS-1 §13.5, §14.10; AG-4 | Repository policy |
| AG-18 | ATS-1 §13.7, §14.11; `ats_corpus_adjudication_v1.schema.json` (`adjudicator`, `gold_eligible`) | Repository policy for the corpus role; ATS-1 normative for finding disposition |
| AG-19 | ATS-1 §17.3 (label set), §20.6, §12.9, §13.4, §6.3 | Repository policy (the ordering is a repository procedure) |
| AG-20 | ATS-1 §5.4, §20.6 | ATS-1 normative |
| AG-21 | ATS-1 §17.4 (final paragraph) | ATS-1 raised |
| AG-22 | ATS-1 §5.3, §17.4; `ATS_CORPUS_PROTOCOL_V0.md` CP-38 | Repository policy |
| AG-23 | ATS-1 §17.6, §17.8, §10.13; `ATS_CORPUS_PROTOCOL_V0.md` CP-34, CP-41, CP-42 | ATS-1 normative for §17.6; Repository policy for the twelve-class check |
| AG-24 | ATS-1 §4.8, §4.9; `ats_judgment_v1.schema.json` | ATS-1 normative |
| AG-25 | ATS-1 §17.9, §13.4, §16.7 | ATS-1 normative |
| AG-26 | ATS-1 §21.2, §21.4, §12.1 | Repository policy |
| AG-27 | ATS-1 §18.5, §11.3; AG-13 | Repository policy |

### 5.1 Provenance of the worked examples

| This document § | Label | Source of the span |
|---|---|---|
| 3.1 | `conforming` | ATS-1 §21.1, verbatim |
| 3.2 | `violation` | ATS-1 §21.2, verbatim |
| 3.3 | `near_miss` | derived from ATS-1 §21.3 by weakening only the acceptance criterion; the contrast quotes §21.3 verbatim |
| 3.4 | `hard_negative` | a quotation frame around the ATS-1 §21.4 nonconforming example |
| 3.5 | `exception` | constructed; the synonym "highly probable" and its three admissibility conditions are quoted from ATS-1 §8.3 |
| 3.6 | `ambiguous` | ATS-1 §13.4, verbatim, including its four enumerated interpretations |
| 3.7 | `insufficient_context` | ATS-1 §21.6 conforming summary, verbatim, with its retention contract withheld |

Only this document §3.5 has no ATS-1 §21 counterpart, because §21 contains no worked policy-exception example. Its
vocabulary and admissibility conditions are quoted from ATS-1 §8.3 and §6.3 rather than invented.

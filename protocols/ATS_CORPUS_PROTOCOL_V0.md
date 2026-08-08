# ATS Corpus Protocol V0

Status: repository protocol, version 0, for ATS-1 `1.0.0-draft.1`.
Scope: the corpus that this repository mines, mutates, annotates, adjudicates, splits, and cites
as promotion evidence.

## 0. How to read this document

### 0.1 Normative language

This document uses ATS-1 normative language as defined in ATS-1 §1.3: **MUST**, **MUST NOT**,
**SHOULD**, **SHOULD NOT**, and **MAY** carry normative force only in uppercase. Lowercase modal
words carry no force. `CAN` and `CANNOT` state capability, not permission or probability.

**Reference convention.** `ATS-1 §n`, and a bare `§n` inside a grounding note or parenthetical,
name a section of `ATS-1_SPEC.md`. A reference to a section of this document is always written
`this document §n`. Other protocol documents are referenced by filename.

### 0.2 Authority of an obligation

Every numbered obligation below is tagged in this document §10 (Traceability) with one of:

- **ATS-1 normative** — ATS-1 states the obligation at the same requirement level.
- **ATS-1 raised** — ATS-1 states the obligation at `SHOULD`; this repository raises it to `MUST`
  as a local policy decision. The ATS-1 requirement level is unchanged.
- **Repo schema** — the obligation is enforced by a repository-local JSON Schema in `schemas/`.
- **Repository policy** — a decision of this repository. ATS-1 does not state it. An
  implementation MAY conform to ATS-1 without satisfying it.

An obligation marked **Repository policy** MUST NOT be cited as an ATS-1 conformance requirement.

### 0.3 Obligation identifiers

Obligations are identified `CP-n`. Identifiers are stable. A retired identifier MUST NOT be reused,
by analogy with ATS-1 §18.1 for rule identifiers.

---

## 1. Corpus purpose

**CP-1.** The corpus MUST be constructed and maintained to support the eight uses ATS-1 §17.1
enumerates:

1. rule definition;
2. deterministic fixtures;
3. semantic-detector training;
4. rule retrieval;
5. hard-negative evaluation;
6. repair evaluation;
7. preservation testing; and
8. rule promotion.

**CP-2.** The corpus is not merely a collection of "good" and "bad" prose (ATS-1 §17.1). A record
whose only content is an aesthetic verdict on a passage MUST NOT be stored. Every stored example
MUST name the rule under which it was judged and the label it received under that rule.

**CP-3.** Because a corpus record is scoped to one rule, the same span MAY carry several records
under different rule identifiers, with different labels. A record MUST NOT be reinterpreted as a
judgment about a rule it does not name.

**CP-4.** In v0 this repository builds no learned model. Uses 3, 4, and 6 of CP-1 are therefore
prospective: the corpus MUST be shaped so that they remain possible, and no v0 artifact MAY claim
that a learned detector was trained or evaluated.

### 1.1 Use-specific admission

**CP-5.** An example admitted for one use MUST NOT be silently reused for another use whose entry
criteria it does not meet. In particular:

- a deterministic fixture MUST be reproducible from repository content alone;
- a promotion-evidence example MUST satisfy ATS-1 §12.9 and §17.8 (see CP-6);
- a training example MUST carry a `use_authority` permitting training (see this document §8).

**CP-6.** A rule MUST NOT be promoted to `required` on the basis of synthetic violations alone, or
on examples that repeat the rule's own wording (ATS-1 §12.9, §17.8). Promotion evidence MUST
therefore include, per rule, the seven example classes ATS-1 §12.9 requires: conforming positives;
clear violations; near misses; hard negatives carrying the likely surface cue without a violation;
domain-specific exceptions; adversarial examples; and transformation pairs when the rule can be
affected by rewriting.

---

## 2. Corpus objects

The corpus is composed of four repository-defined record types plus the normative example record.
Each record type is content-addressed and append-only (this document §2.7).

| Object | Schema | Role |
|---|---|---|
| `SourceArtifactV1` | `schemas/ats_source_artifact_v1.schema.json` | a repository document pinned at an exact revision |
| `ContextBundleV1` | `schemas/ats_context_bundle_v1.schema.json` | the minimum context needed to adjudicate one candidate span |
| `TextExampleV1` | `spec/ATS-1/1.0.0-draft.1/schemas/ats_text_example_v1.schema.json` | the stored example, normative ATS-1 format |
| `JudgmentV1` | `schemas/ats_judgment_v1.schema.json` | one independent annotator judgment |
| `CorpusAdjudicationV1` | `schemas/ats_corpus_adjudication_v1.schema.json` | append-only resolution of two or more judgments |

**CP-7.** Every emitted corpus record MUST validate against the schema named above for its type
before it is written. A record that fails validation MUST NOT be stored.

**CP-8.** `TextExampleV1` is a normative ATS-1 schema. This repository MUST NOT redefine it.
Repository-specific data MUST be carried in its `extensions` object under a namespaced key, or in a
separately versioned repository schema, per the milestone constraint and ATS-1 §19.5.

### 2.1 `SourceArtifactV1` — field map

Required by `ats_source_artifact_v1.schema.json`:

| Field | Type / vocabulary | Obligation |
|---|---|---|
| `schema_version` | const `ats.source_artifact.v1` | fixed |
| `artifact_id` | `ats_common_v1#/$defs/identifier` | stable within the corpus |
| `repository` | non-empty string | repository identity |
| `repository_group` | non-empty string | leakage grouping key; repositories sharing a template or owner share a group |
| `path` | non-empty string | path within the repository |
| `revision` | non-empty string | exact revision (CP-27) |
| `content_sha256` | `sha256` | hash of the exact bytes |
| `normalized_sha256` | `sha256` | hash after ATS text normalization |
| `media_type` | non-empty string | e.g. `text/markdown`, `text/plain` |
| `review_state` | `accepted` \| `rejected` \| `superseded` \| `reverted` \| `draft` \| `unknown` | kept distinct (CP-30) |
| `use_authority` | `internal_only` \| `internal_training_permitted` \| `external_training_permitted` \| `unknown` \| `prohibited` | this document §8 |
| `handling_policy` | `public` \| `internal` \| `confidential` \| `restricted` | this document §8 |
| `ingested_at` | `timestamp` | ingestion time |

Optional in the same schema: `record_sha256` (`sha256`); `bytes` (integer ≥ 0);
`author_provenance` (object, required `availability`, optional `author`, `authored_at`,
`committer`); `model_provenance` (object, required `availability`, optional `model`
(`model_artifact`), `evidence`, `authorship`); `acceptance_evidence` (object, required
`availability`, optional `locator`, `reviewers`, `notes`); `template_family` (string);
`near_duplicate_cluster` (string);
`domain` (string); `profile_hypotheses` (unique array of `profile`); `heading_paths` (array of
arrays of string); `extensions` (object). `additionalProperties` is `false`.

**CP-9.** `author_provenance`, `model_provenance`, and `acceptance_evidence` each require an
`availability` value drawn from `ats_common_v1#/$defs/availability`
(`present`, `not_found`, `not_searched`, `unavailable`, `withheld`, `not_applicable`). Absence of
author or model information MUST be recorded as a typed availability state, not by omitting the
object (ATS-1 §7.8, §20.6).

**CP-9.1.** `model_provenance.authorship` records who authored the text, using
`human | model | mixed | unknown`. `unknown` is the default and the only value reachable
without an explicit declaration; a non-`unknown` value MUST cite the declaration that
established it in `authorship.evidence`, whose `kind` is one of `commit_trailer`,
`artifact_receipt`, `agent_run_manifest`, `document_front_matter`, or `execution_trace`.
Authorship MUST NOT be inferred from prose style, commit size, author identity, commit
timestamps, phrase reuse, or the presence of an agent configuration file in the repository.
`authorship.searched` names every source consulted and is never empty, so an `unknown`
authorship is distinguishable from an authorship nobody looked for (ATS-1 §17.4).

**CP-9.2.** Acceptance is a decision an authority recorded, never a fact derived from
repository history. An artifact's `acceptance_state` uses `accepted | rejected | superseded |
unknown`, defaults to `unknown` with `acceptance_evidence: []`, and MUST NOT leave `unknown`
except on an authoritative artifact whose `kind` is one of `arq_receipt`, `decision_record`,
`review_disposition`, or `review_state_declaration`. Each evidence record MUST carry the
state, a `locator`, and the deciding `authority`; an authority naming the producing
implementation MUST be refused (ATS-1 §13.7, §14.11). `rejected` and `unknown` are distinct
and MUST stay distinct: the first is a refusal an authority made, the second is the absence
of a sufficient decision.

Version control establishes presence at a revision, deletion, modification, ancestry, and
merge topology. It establishes acceptance of none of them. The following MUST be observed and
reported, and MUST NOT move `acceptance_state`: `merge_topology`, `default_branch_presence`,
`survival_duration`, `deletion`, `revert_marker`, `later_edit_absence`,
`reviewed_by_trailer`, `candidate_receipt`. Each observation MUST carry the reason it does
not establish acceptance. `acceptance_evidence` names every artifact kind that was searched
and is never empty of its search record, so an `unknown` acceptance is distinguishable from
an acceptance nobody looked for (ATS-1 §17.4, ADR-0002).

A merged document is not thereby accepted, and a deleted document is not thereby rejected.
`reverted` remains detectable from Git's own `This reverts commit` line and MUST continue to
be detected and reported; a revert is a topological fact about a change being undone, not a
reviewer's judgment about the prose, so it is recorded as topology rather than as an
acceptance state.

**CP-9.3.** An artifact *this* system produces MUST bind, at production time, all seven of:
the producing skill; the model name and version where a model applies; the prompt or
instruction identity; the source IR; the human edits; the adjudicator; and the acceptance
receipt. None of the seven is recoverable from the artifact afterwards, and none MAY be
omitted: a field with no value carries an explicit token (`not_applicable`, `none`,
`not_yet_adjudicated`, `not_yet_accepted`) so that "there was no model" stays distinguishable
from "nobody recorded the model" (ADR-0002). A bound model requires a bound prompt, a named
acceptance receipt requires a named adjudicator, and a named adjudicator MUST NOT be the
producing implementation (ATS-1 §13.7, §14.11).

The prospective binding is a statement about how a producer made something. It MUST NOT be
attached to a retrospective reading of a document that already existed, and a retrospective
read MUST NOT produce one. The binding travels in the producer's own declaration, which the
artifact's provenance cites by locator rather than copying, so the seven facts live in
exactly one place.

**CP-10.** `profile_hypotheses` records candidate profiles only. A profile hypothesis MUST NOT be
recorded as a declared profile, and MUST NOT by itself make a profile-scoped rule applicable to a
span drawn from the artifact.

### 2.2 `ContextBundleV1` — field map

Required by `ats_context_bundle_v1.schema.json`: `schema_version` (const
`ats.context_bundle.v1`), `bundle_id`, `source_artifact_id`, `source_revision`, `source_span`
(`ats_common_v1#/$defs/span`), `span_text` (non-empty), `containing_block`, `heading_path`,
`preceding_context`, `following_context`, `local_definitions`, `glossary_entries`,
`profile_hypothesis`, `policy_context`, `diff`, `review_comment`, `later_edit`.

Optional: `record_sha256`, `reversal`, `context_completeness`, `extensions`.
`additionalProperties` is `false`.

Sub-object shapes, verbatim from the schema:

- `containing_block` — object, required `kind`, `text`, `span`. `kind` ∈ `paragraph`, `list`,
  `list_item`, `table`, `code_block`, `block_quote`, `heading`.
- `heading_path` — array of strings, outermost heading first.
- `local_definitions` — array of objects, each requiring `term`, `definition`, `locator`.
- `glossary_entries` — array of `ats_common_v1#/$defs/glossary_entry`.
- `profile_hypothesis` — object, required `profile` and `basis`; `basis` ∈ `heading_path`,
  `declared_front_matter`, `path_convention`, `annotator_supplied`, `unknown`; optional
  `alternatives` (unique array of `profile`).
- `policy_context` — object, required `availability`; optional `policy_snapshot_id`,
  `policy_sha256`.
- `preceding_context`, `following_context`, `diff`, `review_comment`, `later_edit`, `reversal` —
  the bundle's local `optional_text` shape: required `availability`; optional `text`, `locator`,
  `span`; when `availability` is `present`, `text` is required.
- `context_completeness` ∈ `complete`, `partial`, `insufficient`.

**CP-11.** An isolated sentence MUST NOT be labeled when the rule depends on document context that
was discarded (ATS-1 §17.4). Every context field in `ContextBundleV1` is therefore mandatory as a
*slot*: when the context does not exist or was not retrieved, the bundle MUST carry the
corresponding `availability` value rather than omit the field.

**CP-12.** When any required context slot has an `availability` other than `present` or
`not_applicable`, the bundle MUST set `context_completeness` to `partial` or `insufficient` so the
annotator CAN see that context was truncated. An annotator MUST NOT be shown a truncated bundle
presented as complete.

**CP-13.** `source_revision` in the bundle MUST equal the `revision` of the referenced
`SourceArtifactV1`. A bundle whose span offsets were computed against a different revision MUST be
regenerated, not repaired.

### 2.3 `TextExampleV1` — field map

Required by the normative `ats_text_example_v1.schema.json`: `schema_version` (const
`ats.text_example.v1`), `example_id`, `text`, `profile`, `rule_id` (`^ATS-[A-Z]+-[0-9]{3}$`),
`label`, `rationale`, `protected_impact` (unique array over `P0`, `P1`, `P2`), `provenance`
(`natural` \| `synthetic_mutation` \| `human_authored_fixture` \| `model_authored_fixture`),
`synthetic` (boolean), `split_group`.

Optional: `context`, `source_artifact`, `source_span`, `repository_group`, `domain`,
`adjudicators`, `use_authority`, `mutation_operator`, `related_finding_refs`, `extensions`.
`additionalProperties` is `false`.

`label` ∈ the seven canonical labels of ATS-1 §17.3: `conforming`, `violation`, `near_miss`,
`hard_negative`, `exception`, `ambiguous`, `insufficient_context`.

**CP-14.** "Positive" and "negative" MUST NOT be stored as labels, because they are ambiguous
between rule applicability and writing quality (ATS-1 §17.3, raised from SHOULD). Only the seven
canonical labels are admissible.

**CP-15.** `synthetic` MUST be `true` and `mutation_operator` MUST name a registered operator
whenever `provenance` is `synthetic_mutation` (ATS-1 §17.5: synthetic examples MUST be tagged).

**CP-16.** ATS-1 §17.2 also lists *adjudicator identity*, *provenance*, *license or use authority*,
and *related accepted or rejected finding identifiers* as record content. Because the normative
schema makes `adjudicators`, `use_authority`, and `related_finding_refs` optional, this repository
requires them as follows: an example whose `final_state` is `gold` or
`gold_with_context_constraint` MUST carry at least two `adjudicators`, matching the two independent
judgments required by ATS-1 §17.9 and `ATS_ANNOTATION_GUIDE_V0.md`; every example
MUST carry `use_authority`; and `related_finding_refs` MUST be populated when the example was
derived from an accepted or rejected finding.

### 2.4 `JudgmentV1` — field map

Required by `ats_judgment_v1.schema.json`: `schema_version` (const `ats.judgment.v1`),
`judgment_id`, `example_id`, `annotator_id`, `rule_id`, `rule_version`, `profile`, `label`,
`rationale`, `evidence_spans`, `protected_impact`, `annotation_confidence`,
`requested_additional_context`, `ambiguity_category`, `timestamp`, `tool_version`.

Optional: `record_sha256`, `context_bundle_id`, `normative_statement_quoted`, `blind`,
`extensions`. `additionalProperties` is `false`.

- `annotation_confidence` ∈ `low`, `moderate`, `high`.
- `ambiguity_category` ∈ `none`, `source_ambiguity`, `standard_ambiguity`, `profile_ambiguity`,
  `policy_ambiguity`, `rule_boundary`, `multiple_valid_interpretations`.
- Schema-enforced conditionals: `label: insufficient_context` requires at least one
  `requested_additional_context` entry; `label: ambiguous` requires `ambiguity_category` other than
  `none`; `label: violation` requires at least one `evidence_spans` entry.

**CP-17.** `annotation_confidence` is confidence in the label. It is neither ATS-1 assessment
confidence (§4.8) nor detector confidence (§4.9), and it MUST NOT be rendered as either.

**CP-18.** `rationale` MUST be tied to the normative rule text, not to personal style preference.

### 2.5 `CorpusAdjudicationV1` — field map

Required by `ats_corpus_adjudication_v1.schema.json`: `schema_version` (const
`ats.corpus_adjudication.v1`), `adjudication_id`, `example_id`, `rule_id`, `rule_version`,
`judgment_ids` (≥ 2, unique), `judgments` (≥ 2, complete `JudgmentV1` objects), `agreement`
(`unanimous` \| `majority` \| `split`), `disagreement_category`, `final_state`, `adjudicator`,
`rationale`, `gold_eligible` (boolean), `timestamp`.

Optional: `record_sha256`, `context_constraint`, `standard_ambiguity_discovered`,
`source_ambiguity_discovered`, `policy_mismatch`, `annotation_error`, `required_rule_amendment`,
`required_corpus_correction`, `tool_version`, `extensions`. `additionalProperties` is `false`.

The disagreement categories, final states, and schema-enforced conditionals are
defined by `schemas/ats_corpus_adjudication_v1.schema.json`.

**CP-19.** `judgments` MUST retain the complete original judgments rather than a summary. A forced
majority label MUST NOT erase a genuine ambiguity in the standard or the source (ATS-1 §17.9). This
record type is distinct from the normative `ats.adjudication.v1`, which dispositions a *finding on
an artifact*; `CorpusAdjudicationV1` dispositions a *corpus example*, and the two MUST NOT be
substituted for one another.

### 2.6 Cross-record integrity

**CP-20.** Referential obligations, all Repository policy unless noted:

1. `ContextBundleV1.source_artifact_id` MUST resolve to a stored `SourceArtifactV1`.
2. `TextExampleV1.source_artifact` MUST resolve to a stored `SourceArtifactV1` when `provenance` is
   `natural`.
3. `JudgmentV1.example_id` MUST resolve to a stored `TextExampleV1`, and `JudgmentV1.profile` MUST
   equal that example's `profile`.
4. `JudgmentV1.rule_id` MUST be a rule identifier present in
   `spec/ATS-1/1.0.0-draft.1/rules/ats_rules_v1.yaml`.
5. `CorpusAdjudicationV1.judgment_ids` MUST be exactly the `judgment_id` values of its `judgments`
   array, and every one of those judgments MUST carry the same `example_id`, `rule_id`, and
   `rule_version` as the adjudication.
6. `TextExampleV1.split_group` MUST equal the group key assigned by `ATS_SPLIT_POLICY_V0.md`.

### 2.7 Append-only, content-addressed storage

**CP-21.** Corpus records MUST be append-only. A stored record MUST NOT be edited in place. A
correction MUST be expressed as a new record that supersedes the earlier one by identifier, leaving
the earlier record readable.

**CP-22.** Every record MUST be content-addressed: `record_sha256` MUST equal the SHA-256 of the
RFC 8785 canonical serialization of the record with `record_sha256` itself excluded, matching the
sealing convention used elsewhere in this repository (`ats.canonical.seal`) and ATS-1 Appendix C.

**CP-23.** Judgments and adjudications carry adjudicator and annotator identity. A record whose
handling policy is `confidential` or `restricted` MUST NOT be copied outside its authorized
environment merely because it is content-addressed (this document §8).

---

## 3. Mining protocol

Mining converts repository documents into `SourceArtifactV1` inventory records and candidate spans.
In v0 the mining system implements the protocol, a local Git inventory, candidate-extraction
scaffolding, and fixtures. It MUST NOT require access to repositories not provided to it.

**CP-24.** The inventory process MUST:

1. operate locally;
2. default to no network access;
3. support include and exclude globs;
4. preserve the exact Git revision of every inventoried document;
5. inspect Markdown and plain-text documents first;
6. identify likely profile sections;
7. collect heading paths;
8. collect Git history when available;
9. identify relevant before/after edits;
10. identify review comments only when they are locally available;
11. preserve `accepted`, `rejected`, `superseded`, and `reverted` states separately, without
    treating preservation as promotion (CP-9.2);
12. identify near duplicates and copied templates; and
13. emit content-addressed inventory records.

**CP-25.** Because the default is no network access (CP-24.2), an implementation MUST declare
whether source text leaves the local environment (ATS-1 §16.9). Any non-local processing step MUST
be recorded, and MUST NOT be enabled implicitly by a mining configuration.

**CP-26.** A document not matched by the include globs, or matched by an exclude glob, MUST NOT
appear in the inventory. Glob sets MUST be recorded with the inventory run so the inventory is
reproducible.

**CP-27.** `revision` MUST be an exact revision identifier, not a branch or tag name that CAN move.
A span whose revision cannot be pinned MUST NOT be turned into a labeled example; the artifact MAY
still be inventoried with `review_state: unknown`.

**CP-28.** Profile identification produces `profile_hypotheses` with a recorded `basis` (§2.2).
Mining MUST NOT assert a profile for which no basis exists; it records `basis: unknown` instead.

**CP-29.** Git history, before/after edits, and review comments MUST be attached to the
`ContextBundleV1` as `diff`, `later_edit`, `reversal`, and `review_comment`, each with a typed
`availability`. A review comment that is not locally available MUST be recorded with
`availability: not_found`, `not_searched`, or `unavailable` — never reconstructed from memory or
inferred.

**CP-30.** The four review states MUST remain separate fields of `review_state`, never collapsed
into a binary good/bad axis. `superseded` and `reverted` are distinct from `rejected`: the first two
describe what later happened to accepted text; the third describes text that was never accepted.

`review_state` records what the repository declared or what Git shows. It is not
`acceptance_state`, which is governed by CP-9.2 and requires an authoritative artifact.
`review_state: accepted` promotes `acceptance_state` only through the
`review_state_declaration` evidence kind — that is, only when an `ATS-Review-State` trailer or
note was deliberately written — and `review_state: reverted` never promotes it at all.

**CP-30.1.** An acceptance state MUST NOT be a required stratum of a sampling frame.
Repository history can expose review-state declarations and topology, but it cannot
establish that an authorized party accepted the text. A frame that requests
acceptance coverage MUST record the missing authority as `unavailable` or
`expectation_withdrawn`, with who withdrew the expectation and why. It MUST NOT
turn an unavailable acceptance record into a count, a pass, or a promotion claim.

**CP-31.** Near-duplicate and copied-template detection MUST run before split assignment, and MUST
populate `near_duplicate_cluster` and `template_family` on the `SourceArtifactV1`. These fields are
leakage grouping keys (`ATS_SPLIT_POLICY_V0.md`), so a missing value blocks assignment rather than
defaulting to "unique".

**CP-32.** Inventory records MUST carry both `content_sha256` (exact bytes) and
`normalized_sha256`. Two artifacts with equal `normalized_sha256` and different `content_sha256`
MUST be treated as near duplicates for split purposes.

---

## 4. Deterministic candidate signals

**CP-33.** Candidate mining MAY use deterministic signals, including:

1. ATS force vocabulary;
2. deontic terms;
3. numerical thresholds;
4. requirement-like sentences;
5. actor/action constructions;
6. forecast expressions;
7. confidence language;
8. assumptions and exceptions;
9. contrary-evidence sections;
10. explicit decisions;
11. repeated terminology;
12. ambiguous referents;
13. relative time; and
14. diffs that change force, scope, polarity, quantities, or conditions.

**CP-34.** A signal generates a candidate only. **A matched phrase does not establish a
violation.** A candidate MUST NOT be stored with a `violation` label on the strength of a lexical
match. It enters the annotation queue (`ATS_ANNOTATION_GUIDE_V0.md`) with no label.

**CP-35.** A signal MUST match only against (a) `lexicons/ats_force_lexicon_v1.yaml` in the
normative package, (b) a list enumerated verbatim in `ATS-1_SPEC.md`, or (c) glossary content
declared in the artifact itself. A mined term list MUST NOT be invented; each signal MUST record
its vocabulary source.

**CP-36.** A candidate record MUST identify the signal that produced it, so that the corpus CAN be
audited for the cue-driven sampling bias that makes conceptual-gate construction necessary
(ATS-1 §17.8, `ATS_SPLIT_POLICY_V0.md`).

**CP-37.** Because signal-driven mining oversamples spans containing canonical rule terminology,
mining MUST additionally sample spans that carry none of the signals in CP-33, so that
conceptual-gate and hard-negative material CAN be built. A rule SHOULD NOT be promoted based only
on examples containing its canonical terminology (ATS-1 §17.8).

---

## 5. The six non-inferences

**CP-38.** The mining and annotation pipeline MUST NOT infer any of the following. Each is stated
as the prohibited inference, with the reason it fails.

1. **Merged prose is not conforming.** `review_state: accepted` records that a repository accepted
   the text. It does not record that any ATS-1 rule was evaluated. Acceptance MUST NOT be converted
   into a `conforming` label (ATS-1 §5.3: no bare conformance claim; §17.4 lists acceptance
   outcomes as retained context, not as labels).
2. **Deleted prose is neither a violation nor a rejection.** Text MAY be deleted because it
   became redundant, moved, or lost its subject. A deletion MUST NOT be converted into a
   `violation` label, and MUST NOT be converted into `acceptance_state: rejected` (CP-9.2).
3. **A later edit is not better.** A subsequent revision MAY introduce a violation, strengthen a
   claim beyond its basis, or drop a qualification. The direction of an edit MUST NOT be treated as
   the direction of conformance (compare ATS-1 §11.6, which forbids unsupported strengthening).
4. **A review comment is not correct.** A reviewer's remark is evidence that an issue was raised.
   It MUST NOT be treated as an adjudication. For findings on artifacts, adjudication authority rests
   with an authorized human or explicitly governed external acceptance system (ATS-1 §14.11).
5. **An author's preferred style is not an ATS-1 rule.** A judgment MUST cite the normative
   statement of a rule in `rules/ats_rules_v1.yaml` (CP-18). A house style that ATS-1 does not
   state MUST NOT be labeled as a violation of ATS-1.
6. **Template-sharing documents are not independent.** Accepted documents that share a template are
   not independent examples. They MUST share a `template_family`, and therefore a split group
   (ATS-1 §17.7).

**CP-39.** Where a non-inference blocks a label, the correct outcome is `insufficient_context` or
`ambiguous`, or no record at all. A typed insufficiency MUST be preferred to an unsupported pass or
a guessed interpretation (ATS-1 §20.6).

---

## 6. Hard-negative protocol

A hard negative is an example in which the expected surface cue for a rule is present and no
violation exists.

**CP-40.** Every rule corpus MUST include hard negatives that contain the expected surface cue
without the violation (ATS-1 §17.6).

**CP-41.** Hard negatives MUST be first-class records: mined, labeled, adjudicated, split, and
counted like any other example. A hard negative MUST NOT be stored as an annotation on another
example, as a comment, or as a leftover of a rejected candidate.

**CP-42.** The following twelve hard-negative classes are required. Each row names the class, the
cue that makes it hard, and the rules it primarily defends.

| # | Class | Cue present | Primarily defends |
|---|---|---|---|
| HN-1 | A long but coherent sentence | sentence length | `ATS-SCOPE-001`, `ATS-REF-001` false positives; ATS-1 §10.13 imposes no global sentence-word limit, and §10.14 governs dependency depth instead |
| HN-2 | A passive construction whose actor is irrelevant or intentionally unknown | passive voice, no named actor | `ATS-REQ-001`, ATS-1 §10.7 |
| HN-3 | A precise technical term | rare or "jargon" vocabulary | `ATS-TERM-002`, ATS-1 §10.4 |
| HN-4 | Repeated canonical terms needed for referential stability | repetition | `ATS-DISC-003`, ATS-1 §10.19; `ATS-TERM-001` requires one term per concept |
| HN-5 | Causal language backed by formal system semantics | `causes`, `necessary for` | `ATS-EVID-002`, ATS-1 §8.15 (formal dependency is a valid basis) |
| HN-6 | `may` inside a quotation or historical description | the deontic surface `may` | `ATS-DEON-002`, ATS-1 §5.6, §8.3 (quoted material) |
| HN-7 | Lowercase `should` describing another author's expectation | the deontic surface `should` | `ATS-DEON-003`, ATS-1 §1.3 (lowercase carries no force), §10.24 |
| HN-8 | Material numbers that are identifiers rather than quantities | a bare number | `ATS-NUM-001`; ATS-1 §11.3.1 separates identifiers from numbers with units |
| HN-9 | Apparent relative time anchored by surrounding metadata | `currently`, `the latest` | `ATS-TIME-002`, ATS-1 §10.11 (resolution MAY come from an anchor in context) |
| HN-10 | A summary that omits content explicitly excluded by its retention contract | missing source claim | `ATS-PRES-001`, `ATS-PRES-002`, ATS-1 §11.8 (authorized omission) |
| HN-11 | Several sentences performing one conceptual move | paragraph length | `ATS-DISC-002`, ATS-1 §10.15 |
| HN-12 | A requirement whose actor is supplied by an unambiguous enclosing requirement block | no actor in the sentence | `ATS-REQ-001`, ATS-1 §9.3.4 (actor MAY be inherited from a mechanically unambiguous block) |

**CP-43.** A hard negative MUST carry a `ContextBundleV1` whose `context_completeness` is
`complete` for the context that makes it a negative. HN-9, HN-10, and HN-12 are defined by context
outside the span; without that context the correct label is `insufficient_context`, not
`hard_negative`.

**CP-44.** A hard negative MUST NOT be produced by a mutation operator whose `expected_label` is
`violation`. Hard-negative pairing requirements for mutation operators are specified in the public
registry `corpus/operators/ats_mutation_operators_v1.yaml`.

**CP-45.** Hard-negative performance MUST be reported separately in any evaluation, never folded
into a single macro score (ATS-1 §17.10; ATS-1 §18.4 requires hard-negative precision to pass
before a learned semantic rule becomes `required`).

---

## 7. Synthetic material

**CP-46.** Synthetic examples MUST be tagged (`synthetic: true`, `provenance:
synthetic_mutation`, `mutation_operator` set), and MUST NOT be counted as independent real-world
evidence of rule prevalence or user value (ATS-1 §17.5).

**CP-47.** A synthetic mutation MUST remain in the same split group as its source
(ATS-1 §17.7, `ATS_SPLIT_POLICY_V0.md`).

**CP-48.** Operator definitions, determinism obligations, and the v0 support matrix are normative in
the public registry `corpus/operators/ats_mutation_operators_v1.yaml`.

---

## 8. Provenance and use authority

**CP-49.** Training data MUST record use authority (ATS-1 §17.13). Every `SourceArtifactV1`
therefore requires `use_authority`, and every `TextExampleV1` MUST carry `use_authority`
(CP-16).

**CP-50.** Private repository text MUST NOT be used outside its authorized environment, and MUST
NOT be used for external model training, without explicit permission (ATS-1 §17.13). Operationally:

1. `use_authority: prohibited` — the artifact MUST NOT be used for any corpus purpose beyond
   inventory.
2. `use_authority: unknown` — the artifact MUST NOT be used for training or external evaluation. It
   MAY be used for local fixture authoring only when `handling_policy` is `public`.
3. `use_authority: internal_only` — no training use.
4. `use_authority: internal_training_permitted` — training within the authorized environment only.
5. `use_authority: external_training_permitted` — external training use permitted.

**CP-51.** Derived embeddings, labels, and synthetic mutations inherit the source's handling policy
(ATS-1 §17.13, raised from SHOULD). A derived record MUST NOT carry a weaker `handling_policy` or a
broader `use_authority` than its source. Where a derived record has several sources, it takes the
most restrictive value of each.

**CP-52.** A corpus export MUST refuse to emit any record whose effective `use_authority` does not
permit the requested destination, and MUST report the refusal rather than silently dropping the
record (ATS-1 §14.12: no silent fallback).

**CP-53.** A finding MAY cite a redacted source, and redaction MUST NOT be represented as evidence
unavailability when the authorized adjudicator had access (ATS-1 §20.4). In corpus records this
means `availability: withheld` — not `unavailable` — when content exists but is not exposed to the
current reader.

---

## 9. Relationship to promotion

**CP-54.** A promotion decision MUST cite corpus artifacts by content hash: evaluation corpus
hashes and the split policy are required receipt content (ATS-1 §18.6). A promotion receipt that
cites a corpus without hashes is invalid.

**CP-55.** A high aggregate score MUST NOT compensate for catastrophic errors on material subtypes
— polarity changes, deontic-force changes, causal overclaim, source-attribution loss,
probability-band changes, or omitted exceptions (ATS-1 §18.5). The corpus MUST therefore keep these
subtypes separately identifiable, which the mutation catalog achieves through
`target_rule_ids` and `expected_delta_classes`.

**CP-56.** No learned model is built in v0. Any promotion claim in v0 MUST be limited to
deterministic detector classes, and MUST NOT assert conceptual-gate or out-of-domain performance
that has not been measured.

---

## 10. Traceability

| Obligation | Grounding | Authority |
|---|---|---|
| CP-1 | ATS-1 §17.1 (eight uses) | ATS-1 normative |
| CP-2 | ATS-1 §17.1 ("not merely a collection of 'good' and 'bad' prose"), §17.2 | ATS-1 raised (record content is §17.2 SHOULD) |
| CP-3 | `ats_text_example_v1.schema.json` (`rule_id` required); ATS-1 §13.2 | Repo schema |
| CP-4 | ATS-1 §17.12; §5.3 | Repository policy (v0 scope) |
| CP-5 | ATS-1 §16.2, §17.13, §12.9 | Repository policy |
| CP-6 | ATS-1 §12.9, §17.8 | ATS-1 normative (§12.9 MUST) |
| CP-7 | `schemas/*.schema.json`; ATS-1 §19.4 | Repo schema |
| CP-8 | ATS-1 §19.5; milestone constraint | Repository policy |
| CP-9 | `ats_source_artifact_v1.schema.json`; ATS-1 §7.8, §20.6 | Repo schema |
| CP-9.2 | ATS-1 §17.4 (acceptance outcomes as retained context), §13.7, §14.11; ADR-0002; `ats.corpus.acceptance` | Repository policy, grounded as shown |
| CP-9.3 | ATS-1 §13.7, §14.11, §17.4; ADR-0002; `ats.corpus.authorship.ProspectiveBinding` | Repository policy |
| CP-10 | `ats_source_artifact_v1.schema.json` (`profile_hypotheses`); ATS-1 §6.5 | Repository policy |
| CP-11 | ATS-1 §17.4 (final paragraph) | ATS-1 raised |
| CP-12 | `ats_context_bundle_v1.schema.json` (`context_completeness`); ATS-1 §7.16 | Repo schema |
| CP-13 | `ats_context_bundle_v1.schema.json` (`source_revision`); ATS-1 §14.4, §20.5 | Repository policy |
| CP-14 | ATS-1 §17.3 (avoid "positive"/"negative") | ATS-1 raised |
| CP-15 | ATS-1 §17.5 ("Synthetic examples MUST be tagged") | ATS-1 normative |
| CP-16 | ATS-1 §17.2; `ats_text_example_v1.schema.json` optional fields | Repository policy |
| CP-17 | ATS-1 §4.8, §4.9, §13.5; `ats_judgment_v1.schema.json` | ATS-1 normative (§4.9 MUST NOT) |
| CP-18 | `ats_judgment_v1.schema.json` (`rationale` description); ATS-1 §12.10, §16.8 | Repo schema |
| CP-19 | ATS-1 §17.9; §13.7 | ATS-1 normative (§17.9 MUST) |
| CP-20 | Repo schemas; `rules/ats_rules_v1.yaml`; ATS-1 §12.1 | Repository policy |
| CP-21 | ATS-1 §17.9 (disagreement MUST be retained); milestone append-only requirement | Repository policy |
| CP-22 | ATS-1 Appendix C; §6.6, §16.12 | Repository policy |
| CP-23 | ATS-1 §16.9, §17.13 | ATS-1 normative (§17.13 MUST NOT) |
| CP-24 | Milestone mining requirements; ATS-1 §17.4, §16.9 | Repository policy (items 5–12 implement §17.4 SHOULD) |
| CP-25 | ATS-1 §16.9 | ATS-1 normative |
| CP-26 | ATS-1 §16.2 (determinism) | Repository policy |
| CP-27 | ATS-1 §17.4 (source revision), §20.5 | ATS-1 raised |
| CP-28 | ATS-1 §6.5, §7.16 | Repository policy |
| CP-29 | ATS-1 §17.4; `ats_context_bundle_v1.schema.json` `optional_text` | Repo schema |
| CP-30 | ATS-1 §17.4; `ats_source_artifact_v1.schema.json` `review_state` | Repo schema |
| CP-30.1 | ATS-1 §17.4; `ats_sampling_frame_v1.schema.json` (`expectation_withdrawn`) | Repository policy |
| CP-31 | ATS-1 §17.7 (template, near-duplicate cluster) | ATS-1 normative (§17.7 MUST) |
| CP-32 | `ats_source_artifact_v1.schema.json`; ATS-1 §17.7 | Repository policy |
| CP-33 | Milestone candidate-signal list | Repository policy (MAY) |
| CP-34 | Milestone: "a matched phrase does not establish a violation"; ATS-1 §13.2, §5.4 | Repository policy, consistent with ATS-1 §5.4 |
| CP-35 | ATS-1 §1.2, §8.2, §8.3; `lexicons/ats_force_lexicon_v1.yaml` | Repository policy |
| CP-36 | ATS-1 §17.8 | Repository policy |
| CP-37 | ATS-1 §17.8 (final paragraph) | ATS-1 raised |
| CP-38 | Milestone non-inference list; ATS-1 §5.3, §11.6, §14.11, §17.4, §17.7 | Repository policy, each item grounded as shown in the item text |
| CP-39 | ATS-1 §20.6, §16.7 | ATS-1 normative |
| CP-40 | ATS-1 §17.6 | ATS-1 normative |
| CP-41 | Milestone: hard negatives are first-class records | Repository policy |
| CP-42 | ATS-1 §17.6 (nine classes); milestone (twelve classes) | ATS-1 §17.6 for HN-1…HN-7, HN-10, HN-11; Repository policy for HN-8, HN-9, HN-12 |
| CP-43 | ATS-1 §17.4; `ats_context_bundle_v1.schema.json` | Repository policy |
| CP-44 | `ats_mutation_operator_v1.schema.json` (`expected_label`) | Repo schema |
| CP-45 | ATS-1 §17.10, §18.4 | ATS-1 normative (§18.4 MUST NOT) |
| CP-46 | ATS-1 §17.5 | ATS-1 normative |
| CP-47 | ATS-1 §17.7; `ats_mutation_operator_v1.schema.json` `split_group_policy` | ATS-1 normative |
| CP-48 | `ats_mutation_operator_v1.schema.json`; milestone registry path | Repository policy |
| CP-49 | ATS-1 §17.13 ("Training data MUST record use authority") | ATS-1 normative |
| CP-50 | ATS-1 §17.13; `ats_source_artifact_v1.schema.json` `use_authority` | ATS-1 normative; the five-way mapping is Repository policy |
| CP-51 | ATS-1 §17.13 (inheritance, SHOULD) | ATS-1 raised |
| CP-52 | ATS-1 §14.12, §16.9 | ATS-1 normative |
| CP-53 | ATS-1 §20.4; `ats_common_v1#/$defs/availability` | ATS-1 normative |
| CP-54 | ATS-1 §18.6 | ATS-1 normative |
| CP-55 | ATS-1 §18.5 | ATS-1 normative |
| CP-56 | ATS-1 §5.3, §17.12, §18.4 | Repository policy (v0 scope) |

### 10.1 Companion protocols

| `corpus/operators/ats_mutation_operators_v1.yaml` | mutation operator definitions and exclusions |
| `ATS_ANNOTATION_GUIDE_V0.md` | annotation requirements, distinctions, seven-label examples, traps |
| `ATS_SPLIT_POLICY_V0.md` | leakage dimensions, partitions, conceptual gate, deterministic assignment |

# ATS Split Policy V0

Status: repository protocol, version 0, for ATS-1 `1.0.0-draft.1`.
Record schema: `schemas/ats_corpus_split_v1.schema.json`.

## 0. How to read this document

### 0.1 Normative language

ATS-1 §1.3 applies: **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** carry normative
force only in uppercase. `CAN` and `CANNOT` state capability. Obligations are identified `SP-n`; a
retired identifier MUST NOT be reused.

**Reference convention.** `ATS-1 §n`, and a bare `§n` inside a grounding note or parenthetical,
name a section of `ATS-1_SPEC.md`. A reference to a section of this document is always written
`this document §n`. Other protocol documents are referenced by filename.

### 0.2 Authority of an obligation

Each obligation is tagged in this document §6 as **ATS-1 normative**, **ATS-1 raised**, **Repo schema**, or
**Repository policy**. An obligation marked **Repository policy** MUST NOT be cited as an ATS-1
conformance requirement.

### 0.3 What a split is for

A split exists so that an evaluation number means something. If any information that makes an example
easy is also present in training, the number measures memorization rather than the rule.

**SP-1.** Training, development, and evaluation splits MUST prevent leakage by grouping on the
applicable dimensions (ATS-1 §17.7). Grouping, not sampling, is the mechanism: examples that share a
leakage dimension MUST be assigned as one unit.

**SP-2.** No learned model is built in v0. The split generator and this policy exist so that future
leakage is difficult, and MUST NOT be described as having validated any model.

---

## 1. The fourteen leakage grouping dimensions

`grouping_dimensions`, `groups[].dimension_values`, `leakage_checks[].dimension`, and
`unassignable[].missing_dimensions` all draw from the fourteen values of `#/$defs/dimension` in
`schemas/ats_corpus_split_v1.schema.json`.

| Dimension | What it prevents | Source field | Role (§1.2) | Priority (§1.3) |
|---|---|---|---|---|
| `source_mutation_pair` | a mutation being evaluated against its own unmutated source | the pair identity of a synthetic example and its source | closure | 1 |
| `explicit_derivation` | a declared derivative being evaluated against what it was derived from | `TextExampleV1.extensions["x-ats-repo-derived-from"]` | closure | 1 |
| `common_ancestor_document` | two documents forked from one ancestor leaking | ancestry detection over document history | closure | 1 |
| `source_document` | two spans from the same document landing on opposite sides | `SourceArtifactV1.artifact_id` | closure | 2 |
| `content_hash` | the same bytes, in two repositories, landing on both sides | `SourceArtifactV1.content_sha256` | closure | 2 |
| `normalized_content_hash` | the same text, reformatted, landing on both sides | `SourceArtifactV1.normalized_sha256` | closure | 2 |
| `near_duplicate_cluster` | near-identical documents leaking | `SourceArtifactV1.near_duplicate_cluster` | closure | 3 |
| `copied_text_cluster` | text copied between documents leaking | copy detection over normalized text | closure | 3 |
| `repository` | project-specific vocabulary and house style leaking | `SourceArtifactV1.repository`, `repository_group` | constraint | 4 |
| `template` | boilerplate shared by templated documents leaking | `SourceArtifactV1.template_family` | constraint | 5 |
| `author` | an author's idiolect leaking | `SourceArtifactV1.author_provenance.author` | constraint | 6 |
| `domain` | domain-specific phrasing leaking, and a domain absent from a partition | `SourceArtifactV1.domain` | constraint (balance, §1.5) | 7 |
| `source_model_family` | a generator model's stylistic signature leaking | `SourceArtifactV1.model_provenance.model` | constraint | 8 |
| `mutation_family` | a detector scoring on an operator's signature rather than the rule | `TextExampleV1.mutation_operator` | constraint | 8 |

**SP-3.** ATS-1 §17.7 names eight of these: source document; repository or project; author;
source-model family; template; mutation operator; domain; near-duplicate cluster. Six —
`source_mutation_pair`, `copied_text_cluster`, `common_ancestor_document`, `content_hash`,
`normalized_content_hash`, and `explicit_derivation` — are additions required by this repository's
milestone. They MUST be treated as **repository policy** additions and MUST NOT be cited as ATS-1
enumerations. `mutation_family` is this repository's name for ATS-1's "mutation operator" dimension.

**SP-40.** `content_hash`, `normalized_content_hash`, and `explicit_derivation` are
required because `repository` is not a sufficient grouping key. Equal or near-equal
content can cross repository boundaries, and a repository-only split would place
copies on opposite sides. Both hashes are required fields of `SourceArtifactV1`.
When the generator is not given the source artifacts, it MUST report both
dimensions `UNAVAILABLE` and MUST NOT report them `PASS`.

### 1.1 Leakage check statuses

**SP-4.** `leakage_checks[].status` is `PASS`, `FAIL`, `UNAVAILABLE`, `NOT_APPLICABLE`, or `UNMET`:

- `PASS` — the generator verified that no group spans two partitions on this dimension, over every
  assigned example.
- `FAIL` — at least one group does; `offending_groups` MUST name them.
- `UNAVAILABLE` — the dimension's value was missing for at least one assigned example, so the check
  could not be completed over the corpus.
- `NOT_APPLICABLE` — no partition declares the dimension in `disjoint_on`, or no example in the
  corpus carries it. `detail` MUST state which of the two.
- `UNMET` — a declared target could not be met without dividing a group formed at a higher priority
  (§1.3). This is not leakage: nothing crossed a partition boundary that should not have.
  `blocked_by` MUST name the groups that hold, with the dimension and priority that protect each.

`leakage_checks[].kind` states which of three things an entry verifies — `closure` that a group did
not span partitions, `disjointness` that a declared `disjoint_on` holds, `balance` that a declared
`balance_on` target was met — and `leakage_checks[].priority` records the dimension's rank.

**SP-5.** A leakage check MUST NOT report `PASS` when the dimension's value was unavailable for any
assigned example, and MUST NOT report `PASS` for a dimension no partition declares disjoint.
Reporting `PASS` by absence is prohibited, on the same principle as ATS-1 §5.4 for required checks and
§20.6 for typed insufficiency.

**SP-6.** Checks are evaluated per dimension relative to the partitions that declare that dimension in
`disjoint_on`. Every **closure** dimension MUST be checked over every partition regardless of what any
partition declares, because a closure dimension spanning two partitions means the closure itself was
broken, and a split that leaks on one is not a split.

### 1.2 Closure dimensions and constraint dimensions

The fourteen dimensions play two different roles, and conflating them breaks the split in opposite
directions.

**SP-7.** A **closure** dimension is an *edge*: two examples sharing a value on one, or joined by a
declared lineage pointer, MUST land in the same group, transitively. The closure dimensions are
`source_mutation_pair`, `explicit_derivation`, `common_ancestor_document`, `source_document`,
`content_hash`, `normalized_content_hash`, `near_duplicate_cluster`, and `copied_text_cluster`. Each
of them means the two examples carry the same text or one descends from the other.

**SP-8.** A **constraint** dimension MUST NOT be joined. It constrains only *where whole groups are
placed*: when a partition declares it in `disjoint_on`, the groups that share a value on it MUST be
co-placed into one partition, and a group MUST NOT be divided to achieve that. The constraint
dimensions are `repository`, `template`, `author`, `domain`, `source_model_family`, and
`mutation_family`.

**SP-9.** `repository` MUST NOT be a closure dimension. Joining on it would collapse
a single-repository corpus into exactly one group, which makes every split impossible
rather than safe. The same reasoning applies to `domain`, `source_model_family`,
`mutation_family`, and `author` when those values are broadly shared. `template` is
a constraint for a different reason: a shared section skeleton is evidence of shared
shape, not necessarily shared prose, and shared prose is already caught above by
`content_hash`, `normalized_content_hash`, and `copied_text_cluster`. Each remains a
real leakage axis that the corresponding disjoint-evaluation partition is built to
separate.

### 1.3 Priority order

**SP-41.** The dimensions are ranked, highest first: (1) lineage integrity, (2) exact-content
integrity, (3) near-duplicate integrity, (4) project disjointness, (5) template disjointness, (6)
author disjointness, (7) domain balance, (8) the residual disjointness dimensions ATS-1 names and this
order does not rank. A group formed at a higher priority MUST NOT be broken to improve a
lower-priority distribution target.

**SP-42.** Constraints MUST be applied in ascending priority, and a constraint MUST be either applied
whole or refused whole. A constraint MUST be refused when co-placing its values would leave fewer
placement blocks than there are partitions with a nonzero `target_fraction`, because a split collapsed
into fewer sides than the policy declared is worse than a target honestly reported unmet.

**SP-43.** When a target cannot be met without violating SP-41, the split MUST report it `UNMET` with
`blocked_by` naming the protecting groups, and MUST NOT report it met, MUST NOT silently rebalance,
and MUST NOT divide a group. A generator that reaches a distribution target by dividing a closure
group is nonconforming with this document even when every `leakage_checks` entry reads `PASS`.

**SP-44.** `groups[].closure_dimensions` MUST record the closure dimensions that actually joined a
group's members, and `groups[].closure_priority` the highest priority among them, so an `UNMET`
report is auditable against the group it names. `groups[].placement_block` MUST record the group key
whose assignment a co-placed group inherited, and MUST be absent when the group was placed on its own
key.

### 1.4 Balance targets

**SP-45.** A balance target — declared as `policy.balance_on`, with an optional
`policy.balance_tolerance` — asks that every value of a dimension appear in each partition in
proportion to that partition's `target_fraction`. A dimension not named in `policy.balance_on` MUST
produce no `balance` entry at all: an undeclared target is not a target, and reporting one either way
would invent a claim. A declared target whose dimension is missing from any assigned example MUST be
`UNAVAILABLE`, never `PASS`.

**SP-46.** Placement MUST NOT be reordered to reach a balance target. Moving a group to improve a
distribution is the pressure SP-41 exists to resist, so the target is measured rather than optimized:
`PASS` within tolerance, `UNMET` when a group's own size makes it unreachable, and `FAIL` when the
deviation is a property of the placement and no group's integrity accounts for it.

### 1.5 Group keys

**SP-10.** Grouping MUST be computed as connected components over the closure dimensions, not as a
join of one example's own values. Two examples sharing a source document MUST land in one group even
when they differ on `near_duplicate_cluster`; a per-example join would separate them and leak. The
closure MUST be transitive: A near-duplicate B and B copied-from C puts A, B, and C in one group even
though A and C share no value.

**SP-47.** A lineage pointer MUST be followed as a directed edge in addition to being joined on its
shared value. A chain shares no single value — a mutant of a mutant names its parent while the parent
names the original — so value joining alone would leave the grandchild in its own group, one diff away
from a training example. A pointer to an example the split does not contain MUST be skipped rather
than treated as a missing key: there is nothing present for it to leak against.

**SP-11.** The group key MUST be derived from the component, as follows:

1. for each of the fourteen dimensions, in the order of the `#/$defs/dimension` enum, collect the
   distinct values carried by any example in the component, sort them, and join them with `,`; a
   dimension no example in the component carries contributes the empty string;
2. percent-escape any `|` in a value as `%7C`;
3. join the fourteen per-dimension strings with `|`;
4. the stored `group_key` is `group-` followed by the first 32 hex characters of the SHA-256 of that
   join, because the raw join is unbounded in length.

**SP-12.** `groups[].dimension_values` MUST record the values the key was built from, so the key is
auditable without re-deriving the component. A dimension absent from the component MUST be recorded as
absent, not as the string `unknown`.

**SP-13.** Every assigned example MUST belong to exactly one group, and every example in a group MUST
receive that group's partition. `assignments` maps `example_id` to a partition name and MUST agree with
`groups[].partition` for every example.

---

## 2. Mutations share their source's split group

**SP-14.** A source example and any mutation derived from it MUST remain in the same split group.
`ats_mutation_operator_v1.schema.json` enforces the operator side of this through
`split_group_policy`, whose two admissible values both inherit the source's group:

- `inherit_source` — the derived example joins its source's component through
  `source_mutation_pair`.
- `inherit_source_and_operator` — the same, and the example additionally carries `mutation_family`, so
  that a mutation-disjoint evaluation partition CAN be separated (§4.6).

**SP-15.** A synthetic example whose source is not stored MUST NOT be assigned: it has no
`source_mutation_pair` value, which is a required grouping dimension (§5.3).

**SP-16.** `TextExampleV1.split_group` MUST equal the `group_key` of the group the example was assigned
to. A record whose `split_group` disagrees with the split record MUST be treated as a generation defect
and MUST NOT be exported.

---

## 3. Random sentence splits are prohibited

**SP-17.** A random sentence split MUST NOT be used for semantic-detector evaluation. ATS-1 §17.7
states that a random sentence split is nonconforming.

**The reason, stated concretely.** A random sentence split assigns each span independently, so it
breaks none of the fourteen dimensions in §1. In an ATS corpus, that failure is not marginal:

1. Section-scoped rules leak whole. `ATS-EPI-002` is decided by whether a WEP use is the first
   material one *in its section* (ATS-1 §8.4). Splitting sentences from one section across partitions
   puts the deciding context of an evaluation example into training.
2. Mutations leak against their own sources. A source and its mutation differ in one feature; a random
   split places them on opposite sides, so an evaluation example's answer is derivable by diffing
   against a training example.
3. Templated and copied documents leak verbatim. Accepted documents that share a template are not
   independent examples (`ATS_CORPUS_PROTOCOL_V0.md` CP-38.6); a random split treats them as if they
   were.
4. The resulting number cannot support promotion. ATS-1 §18.4 requires project-disjoint and
   domain-disjoint evaluation to pass before a learned semantic rule becomes required, and §17.8
   requires conceptual-gate performance. A random sentence split can produce neither.

**SP-18.** A split record MUST NOT be emitted with an empty `grouping_dimensions` array — the schema
enforces `minItems: 1` — and a generator MUST NOT offer a "no grouping" mode.

---

## 4. The eight partitions

`policy.partitions[].kind` takes the eight values of the enum in
`schemas/ats_corpus_split_v1.schema.json`. Each partition entry requires `name`, `kind`, and
`target_fraction`, and MAY declare `disjoint_on`.

**SP-19.** Every partition MUST declare `disjoint_on` explicitly except `training`, whose disjointness
is the complement of the others'. A partition with no declared disjointness and no complement
relationship MUST NOT be emitted, because SP-6 would then have nothing to check it against.

### 4.1 `training`

**Definition.** Examples eligible for fitting a model, selecting features, or authoring rules.

**Entry criteria.**

1. the example's adjudication has `gold_eligible: true`, or the example is a stored `hard_negative`,
   `exception`, or `ambiguous_by_design` record admitted for its declared use;
2. `use_authority` permits training for the intended destination
   (`ATS_CORPUS_PROTOCOL_V0.md` CP-50);
3. every required grouping dimension has a value (§5.3);
4. the group is not claimed by a `conceptual_gate` or `adversarial_hard_negative` partition (§4.7,
   §4.8), which take precedence.

**Prohibition.** An example whose adjudication is `needs_rule_revision` or `needs_more_context` MUST
NOT enter `training`; the schema's `gold_eligible: false` condition enforces this boundary.

### 4.2 `development`

**Definition.** Examples used to select operating thresholds, iterate on configuration, and analyze
errors.

**Entry criteria.** As `training`, and additionally disjoint from every evaluation partition on at
least `source_document`, `near_duplicate_cluster`, `copied_text_cluster`, `template`,
`common_ancestor_document`, and `source_mutation_pair`.

**Prohibition.** `development` MUST NOT be used to report final performance, and a threshold selected
on `development` MUST be frozen before evaluation. ATS-1 §18.4 requires the operating threshold and
calibration to be frozen before a learned semantic rule becomes required.

### 4.3 `in_domain_evaluation`

**Definition.** Held-out examples drawn from the same repositories, domains, and templates as
training. Measures performance where the detector is expected to work.

**Entry criteria.** Disjoint from `training` and `development` on `source_document`,
`near_duplicate_cluster`, `copied_text_cluster`, `template`, `common_ancestor_document`, and
`source_mutation_pair`. `repository`, `author`, `domain`, and `source_model_family` MAY overlap; that
overlap is what makes the partition in-domain.

**Reporting.** An `in_domain_evaluation` result MUST NOT be reported as out-of-domain performance.
ATS-1 §17.10 requires out-of-domain performance to be reported as its own metric.

### 4.4 `project_disjoint_evaluation`

**Definition.** Held-out examples from repositories that contribute nothing to training or
development.

**Entry criteria.** Disjoint on everything `in_domain_evaluation` requires, plus `repository`. Because
`SourceArtifactV1.repository_group` groups repositories that share a template or owner, disjointness
MUST be enforced on the group, not the bare repository name.

**Why it exists.** ATS-1 §18.4 requires project-disjoint and domain-disjoint evaluation to pass before
a learned semantic rule becomes `required`; §18.2 requires out-of-domain behavior as promotion
evidence.

**Domain disjointness.** When `domain` values are available, this partition SHOULD also be
`domain`-disjoint and SHOULD declare `domain` in `disjoint_on`. When `domain` is unavailable for a
candidate group, the `domain` entry in `leakage_checks` MUST be `UNAVAILABLE` (SP-5), and the partition
MUST NOT be described as domain-disjoint.

### 4.5 `author_disjoint_evaluation`

**Definition.** Held-out examples written by authors who contribute nothing to training or
development.

**Entry criteria.** Disjoint on everything `project_disjoint_evaluation` requires, plus `author`.

**"Where possible."** `SourceArtifactV1.author_provenance` carries an `availability` state, and
authorship is frequently `not_found`, `not_searched`, `unavailable`, or `withheld`.

**SP-20.** A group MUST NOT be placed in `author_disjoint_evaluation` unless
`author_provenance.availability` is `present` for every example in it. When author information is
unavailable across the corpus, this partition MUST be omitted from `policy.partitions` and the omission
MUST be recorded, rather than emitted with an `UNAVAILABLE` author check and described as
author-disjoint.

### 4.6 `mutation_disjoint_evaluation`

**Definition.** Held-out examples whose mutation families appear nowhere in training or development.
Measures whether a detector learned the rule or the operator's signature.

**Entry criteria.** Disjoint on `mutation_family` and `source_mutation_pair`, in addition to
`source_document`, `near_duplicate_cluster`, and `copied_text_cluster`. Every operator whose
`split_group_policy` is `inherit_source_and_operator` carries a `mutation_family` value and is
separable here; an operator declared `inherit_source` MUST NOT be relied on for mutation
disjointness.

**Reporting.** A `mutation_disjoint_evaluation` result is still a result on synthetic material.
The public mutation registry's exclusions forbid counting it toward natural prevalence or user value.

### 4.7 `conceptual_gate`

**Definition.** Held-out examples in which the rule's canonical terminology is absent and the
violation remains material. This is the partition that distinguishes a rule detector from a keyword
matcher.

**Construction rules (ATS-1 §17.8).** A conceptual-gate example MUST satisfy all five:

1. direct rule terms are absent;
2. diagnostic phrases are paraphrased;
3. the violation remains material;
4. lexical baselines perform poorly; and
5. humans CAN still adjudicate the case from available context.

**SP-21.** Criterion 4 MUST be measured, not asserted. A lexical baseline over the rule's declared
vocabulary source — the force lexicon, or a list enumerated verbatim in `ATS-1_SPEC.md` — MUST be run
over the partition and its result recorded. A partition on which the lexical baseline performs well is
not a conceptual gate and MUST NOT be labelled one.

**SP-22.** Criterion 5 MUST be evidenced by the adjudication record: a conceptual-gate example MUST
have a `final_state` of `gold` or `gold_with_context_constraint`. An example whose adjudication is
`needs_more_context` fails criterion 5 by construction and MUST NOT be admitted.

**SP-23.** A rule SHOULD NOT be promoted based only on examples that contain its canonical terminology
(ATS-1 §17.8). Consequently, a promotion receipt MUST report conceptual-gate performance separately,
and MUST NOT substitute in-domain performance for it (ATS-1 §17.10, §18.2, §18.6).

**Entry criteria.** All five construction rules; disjoint on everything
`project_disjoint_evaluation` requires; and precedence over `training` for the group (§4.1 criterion 4),
because a conceptual-gate example that also appears in training is worthless.

**Sourcing.** `ATS_CORPUS_PROTOCOL_V0.md` CP-37 requires mining to sample spans carrying none of the
deterministic candidate signals, precisely so that this partition CAN be populated. Cue-driven mining
alone cannot produce it.

### 4.8 `adversarial_hard_negative`

**Definition.** Held-out examples that carry a rule's expected surface cue without the violation,
together with evasion-shaped material.

**Entry criteria.**

1. every example is a stored hard negative with one or more `HN-n` classes from
   `ATS_CORPUS_PROTOCOL_V0.md` §6, or an adversarial example under ATS-1 §12.9;
2. every `HN-n` class applicable to the rule under evaluation is represented, or the absent classes are
   recorded as unrepresented;
3. disjoint on everything `project_disjoint_evaluation` requires;
4. precedence over `training` for the group.

**Evasion coverage.** This partition SHOULD also carry the evasion shapes ATS-1 §20.3 names —
homoglyphs, unusual punctuation, hidden markup, code formatting around modal terms, sentence
fragments, tables that split one requirement across cells, footnotes that reverse a claim, links
whose anchor text changes force, negation in parentheticals, and contradictory captions or labels.

**Reporting.** ATS-1 §18.4 requires hard-negative precision to pass before a learned semantic rule
becomes `required`, and §17.10 requires performance on hard negatives to be reported separately. A
macro score MUST NOT absorb it.

### 4.9 Partition summary

| `kind` | Overlaps with training on | Disjoint from training on |
|---|---|---|
| `training` | — | — |
| `development` | `repository`, `author`, `domain`, `source_model_family` | `source_document`, `near_duplicate_cluster`, `copied_text_cluster`, `template`, `common_ancestor_document`, `source_mutation_pair` |
| `in_domain_evaluation` | `repository`, `author`, `domain`, `source_model_family` | as `development` |
| `project_disjoint_evaluation` | `author` (may), `source_model_family` (may) | as `development`, plus `repository` by `repository_group`, and `domain` where available |
| `author_disjoint_evaluation` | `source_model_family` (may) | as `project_disjoint_evaluation`, plus `author` |
| `mutation_disjoint_evaluation` | `repository`, `author`, `domain` | `mutation_family`, `source_mutation_pair`, `source_document`, `near_duplicate_cluster`, `copied_text_cluster` |
| `conceptual_gate` | — | as `project_disjoint_evaluation` |
| `adversarial_hard_negative` | — | as `project_disjoint_evaluation` |

---

## 5. Deterministic assignment

**SP-24.** Partition assignment MUST be a pure function of the seed and the group key. `policy.seed`
is a string and the schema states that no RNG state is carried. Two runs with the same corpus, policy,
and seed MUST produce byte-identical `groups`, `assignments`, and `unassignable` arrays under RFC 8785
canonical serialization (ATS-1 §16.2, Appendix C).

### 5.1 The canonical construction

**SP-25.** The group key is constructed per SP-10 through SP-12 and SP-47: connected components over
the closure dimensions and the lineage pointers, then the fourteen-slot canonical join, then `group-`
plus the first 32 hex characters of its SHA-256. The partition is drawn on the key of the group's
*placement block* (SP-42, SP-44), which equals its own key unless a declared constraint co-placed it.

**SP-26.** The assignment is computed as follows:

1. `u = int.from_bytes(sha256(seed.encode() + b"\x00" + group_key.encode()).digest()[:8], "big") /
   2**64`, a value in `[0, 1)`;
2. walk `policy.partitions` in declared order, accumulating `target_fraction`;
3. assign the group to the first partition whose cumulative fraction strictly exceeds `u`;
4. the last partition in declared order absorbs any rounding remainder, so every group receives a
   partition and no group falls through to a default.

**SP-27.** Precedence overrides the fraction walk for two partitions: a group all of whose examples
meet the `conceptual_gate` entry criteria, or all of whose examples meet the
`adversarial_hard_negative` entry criteria, MUST be assigned to that partition regardless of `u`.
Precedence assignments MUST be applied before the fraction walk, and the remaining `target_fraction`
values then apply to the groups that remain.

**SP-28.** The construction in SP-25 through SP-27 is a **repository policy** decision. ATS-1 §17.7
requires grouping and forbids a random sentence split; it does not prescribe an assignment function.
Any construction satisfying SP-24 and the disjointness criteria of this document §4 conforms to ATS-1. A change to
this construction MUST increment `policy.policy_id`, because it re-partitions the corpus.

### 5.2 Properties the construction guarantees, and one it does not

**SP-29.** The construction MUST satisfy all of:

1. **Purity** — no clock read, no filesystem order, no iteration order, no RNG state.
2. **Group atomicity** — every example sharing a group key lands in one partition (SP-13).
3. **Assignment stability** — for a fixed `group_key` and `seed`, the partition never changes; adding
   examples elsewhere in the corpus cannot move an existing group.
4. **Seed sensitivity** — changing `policy.seed` re-partitions the corpus, which is why `seed` and
   `policy_id` are both recorded and why `corpus_sha256` binds the split to a corpus state.

**SP-30.** Group keys are **not** stable under insertion, and this MUST be stated wherever splits are
compared across corpus versions. Adding a near-duplicate, a copied-text match, or a common-ancestor
match merges two previously separate components by design, which changes the merged component's
`group_key` and therefore MAY move its examples to a different partition. That is the cost of
near-duplicate grouping, and it is the correct behavior: leaving the two components separate would
leak. A split MUST therefore be regenerated, and its `corpus_sha256` updated, whenever the corpus
changes — never patched incrementally.

### 5.3 Refusal, not assignment, when a required key is missing

**SP-31.** `grouping_dimensions` is the **required** set: a dimension listed there MUST have a value on
every assigned example. Two values are defined:

1. **Generator default**, when a caller supplies no `grouping_dimensions`: `repository`,
   `source_mutation_pair`. A hand-authored fixture legitimately has no `source_document`, so a default
   that required one would send an entire seed corpus to `unassignable`, and a generator whose default
   output is "nothing is assignable" gets worked around rather than used.
2. **Recommended value for a mined corpus**: `source_document`, `repository`, `source_mutation_pair`.
   Every mined example has a pinned source artifact by construction
   (`ATS_CORPUS_PROTOCOL_V0.md` CP-27), so requiring `source_document` costs nothing and closes the
   single largest leakage channel (this document §3, reason 1).

**SP-32.** A dimension not listed in `grouping_dimensions` contributes to the group key when present
(SP-11) and is recorded as absent when not. It MAY still appear in `leakage_checks`, whose `dimension`
field is not constrained to `grouping_dimensions`. This is what makes hand-authored fixtures
assignable: `near_duplicate_cluster`, `template`, and `author` are legitimately absent for a fixture,
and requiring them would send the entire seed corpus to `unassignable`.

**SP-33.** An example missing a value for any dimension in `grouping_dimensions` MUST NOT be assigned.
It MUST be recorded in `unassignable` with `example_id` and the non-empty `missing_dimensions` array,
and it MUST NOT appear in `assignments` or in any `groups[].example_ids`.

**SP-34.** A missing dimension MUST NOT be replaced by a default, a placeholder, a hash of the
example's own text, or the string `unknown`. Any of those would silently create a singleton group that
defeats the dimension it stands in for — the failure mode SP-17 describes. Refusal is the correct
behavior, on the principle of ATS-1 §14.12 (no silent fallback) and §20.6 (a typed insufficiency is
preferred to a guess).

**SP-35.** `unassignable` being non-empty is not a generator error. It is the honest output for a
corpus whose provenance is incomplete, and the remedy is to complete the source records — not to widen
the assignment rule.

**SP-36.** When any example carries no value for a dimension that some partition declares in
`disjoint_on`, that dimension's `leakage_checks` entry MUST be `UNAVAILABLE` rather than `PASS`
(SP-5), because the check could not be completed over the corpus.

**Note on the schema.** The required set is carried by `grouping_dimensions` rather than by a separate
policy field because `grouping_dimensions` is where the schema already declares it, and the top-level
object has no `extensions`. `policy` declares `additionalProperties: false` over exactly `policy_id`,
`seed`, `partitions`, `balance_on`, and `balance_tolerance`; a record carrying any other policy key
would fail validation, so no other carrier is legal. `balance_on` and `balance_tolerance` are policy
keys rather than top-level ones because a distribution target is an input to the split, like the seed,
not an observation about the corpus.

### 5.4 Record obligations

**SP-37.** A split record MUST carry `schema_version`, `split_id`, `policy`, `generated_at`,
`corpus_sha256`, `grouping_dimensions`, `groups`, `assignments`, and `leakage_checks` — the schema's
`required` array. `corpus_sha256` binds the split to an exact corpus state.

**SP-38.** A split record MUST be content-addressed via `record_sha256` on the same convention as
`ATS_CORPUS_PROTOCOL_V0.md` CP-22, and MUST be cited by hash in any promotion receipt, since ATS-1
§18.6 requires the split policy and evaluation corpus hashes in the receipt.

**SP-39.** A split whose `leakage_checks` contains any `FAIL` MUST NOT be used for evaluation
reporting. A split containing `UNAVAILABLE` entries MAY be used, provided every report derived from it
names the unavailable dimensions and does not claim disjointness on them. A split containing `UNMET`
entries MAY be used, provided every report derived from it names the unmet targets and does not claim
them: an `UNMET` disjointness entry means the partition MUST NOT be described as disjoint on that
dimension, and an `UNMET` balance entry means the partition MUST NOT be described as balanced on it.

---

## 6. Traceability

| Obligation | Grounding | Authority |
|---|---|---|
| SP-1 | ATS-1 §17.7 ("Training, development, and evaluation splits MUST prevent leakage by grouping on applicable dimensions") | ATS-1 normative |
| SP-2 | ATS-1 §17.12, §5.3; milestone v0 scope | Repository policy |
| SP-3 | ATS-1 §17.7 (eight dimensions); milestone (fourteen) | ATS-1 normative for the eight; Repository policy for `source_mutation_pair`, `copied_text_cluster`, `common_ancestor_document`, `content_hash`, `normalized_content_hash`, `explicit_derivation` |
| SP-4 | `ats_corpus_split_v1.schema.json` (`leakage_checks`, `status` enum) | Repo schema |
| SP-5 | ATS-1 §5.4, §20.6 | Repository policy, applying the ATS-1 never-pass-by-absence principle to split checks |
| SP-6 | ATS-1 §17.7; `ats_corpus_split_v1.schema.json` (`disjoint_on`, `leakage_checks`) | Repository policy |
| SP-7 | ATS-1 §17.7 (grouping); `ats_corpus_split_v1.schema.json` (`groups`) | Repository policy — ATS-1 does not classify its dimensions as closure or constraint |
| SP-8 | as SP-7 | Repository policy |
| SP-9 | ATS-1 §17.7; `ats_source_artifact_v1.schema.json` (`repository_group`) | Repository policy |
| SP-10 | ATS-1 §17.7 ("grouping on applicable dimensions") | Repository policy implementing an ATS-1 obligation |
| SP-11 | `ats_corpus_split_v1.schema.json` `#/$defs/dimension` order, `groups[].group_key` (`minLength: 1`) | Repository policy |
| SP-12 | `ats_corpus_split_v1.schema.json` (`groups[].dimension_values`) | Repo schema |
| SP-13 | `ats_corpus_split_v1.schema.json` (`assignments`, `groups[].partition`) | Repo schema |
| SP-14 | ATS-1 §17.7; `ats_mutation_operator_v1.schema.json` (`split_group_policy`: "A mutation MUST stay in the same split group as its source") | ATS-1 normative; Repo schema |
| SP-15 | ATS-1 §17.5, §17.7; SP-33 | Repository policy |
| SP-16 | `ats_text_example_v1.schema.json` (`split_group`); ATS-1 §17.2 | Repo schema |
| SP-17 | ATS-1 §17.7 ("A random sentence split is nonconforming for semantic-detector evaluation"); reasons 1–4 grounded in §8.4, §17.5, §17.7, §17.8, §18.4 | ATS-1 normative |
| SP-18 | `ats_corpus_split_v1.schema.json` (`grouping_dimensions` `minItems: 1`) | Repo schema |
| SP-19 | `ats_corpus_split_v1.schema.json` (`disjoint_on`); SP-6 | Repository policy |
| SP-20 | `ats_source_artifact_v1.schema.json` (`author_provenance.availability`); ATS-1 §17.4, §20.6; milestone "author-disjoint evaluation where possible" | Repository policy |
| SP-21 | ATS-1 §17.8 ("lexical baselines perform poorly") | ATS-1 states the criterion; requiring it be measured is Repository policy |
| SP-22 | ATS-1 §17.8 ("humans can still adjudicate the case from available context"); `ats_corpus_adjudication_v1.schema.json` (`final_state`) | Repository policy implementing an ATS-1 criterion |
| SP-23 | ATS-1 §17.8 (final paragraph), §17.10, §18.2, §18.6 | ATS-1 normative for the §17.8 SHOULD NOT and the §18.6 receipt content |
| SP-24 | `ats_corpus_split_v1.schema.json` (`policy.seed`: "Assignment is a deterministic function of (seed, group key); no RNG state is carried"); ATS-1 §16.2, Appendix C | Repo schema; ATS-1 normative for determinism |
| SP-25 | SP-10 through SP-12, SP-42, SP-44, SP-47 | Repository policy |
| SP-26 | `ats_corpus_split_v1.schema.json` (`policy.partitions[].target_fraction`) | Repository policy |
| SP-27 | ATS-1 §17.8, §17.6; §4.7 and §4.8 entry criteria | Repository policy |
| SP-28 | ATS-1 §17.7; `ats_corpus_split_v1.schema.json` (`policy_id`) | Repository policy, stated explicitly as such |
| SP-29 | ATS-1 §16.2, Appendix C; `ats_corpus_split_v1.schema.json` (`seed`, `policy_id`, `corpus_sha256`) | Repo schema; ATS-1 normative for determinism |
| SP-30 | ATS-1 §17.7 (near-duplicate cluster grouping), §16.12; `ats_corpus_split_v1.schema.json` (`corpus_sha256`) | Repository policy — an honest limitation, not an ATS-1 obligation |
| SP-31 | `ats_corpus_split_v1.schema.json` (`grouping_dimensions`, and the schema description: the generator "refuses when a key is unavailable") | Repo schema; the default set is Repository policy |
| SP-32 | `ats_corpus_split_v1.schema.json` (`leakage_checks[].dimension` unconstrained by `grouping_dimensions`) | Repo schema |
| SP-33 | `ats_corpus_split_v1.schema.json` (`unassignable`: "Examples the generator refused to assign because a required grouping key was unavailable") | Repo schema |
| SP-34 | ATS-1 §14.12, §20.6, §17.7 | ATS-1 normative |
| SP-35 | ATS-1 §20.6; `ats_source_artifact_v1.schema.json` availability states | Repository policy |
| SP-36 | ATS-1 §5.4, §20.6; SP-5 | Repository policy |
| SP-37 | `ats_corpus_split_v1.schema.json` `required` array | Repo schema |
| SP-38 | ATS-1 §18.6, Appendix C; `ATS_CORPUS_PROTOCOL_V0.md` CP-22 | ATS-1 normative for §18.6 |
| SP-39 | ATS-1 §17.10, §18.5, §20.6 | Repository policy |
| SP-40 | `ats_source_artifact_v1.schema.json` (`content_sha256`, `normalized_sha256` required); SP-40 rationale above | Repository policy |
| SP-41 | ATS-1 §17.7 (grouping prevents leakage); §18.4 (project-disjoint and domain-disjoint evaluation as promotion evidence) | Repository policy — ATS-1 does not rank its dimensions |
| SP-42 | as SP-41; `ats_corpus_split_v1.schema.json` (`policy.partitions[].target_fraction`) | Repository policy |
| SP-43 | ATS-1 §5.4, §14.12, §20.6; SP-5 | Repository policy, applying the ATS-1 never-pass-by-absence principle to distribution targets |
| SP-44 | `ats_corpus_split_v1.schema.json` (`groups[].closure_dimensions`, `closure_priority`, `placement_block`) | Repo schema |
| SP-45 | `ats_corpus_split_v1.schema.json` (`policy.balance_on`, `policy.balance_tolerance`); ATS-1 §17.7 (domain), §20.6 | Repo schema; the tolerance default is Repository policy |
| SP-46 | as SP-41 and SP-43 | Repository policy |
| SP-47 | ATS-1 §17.5, §17.7; `ats_mutation_operator_v1.schema.json` (`split_group_policy`) | Repository policy implementing an ATS-1 obligation |

### 6.1 Vocabulary provenance

| Vocabulary | Source |
|---|---|
| the fourteen grouping dimensions | `ats_corpus_split_v1.schema.json` `#/$defs/dimension`; eight of them from ATS-1 §17.7 |
| the closure / constraint split of those dimensions, and their priority order | this repository (§1.2, §1.3); ATS-1 §17.7 neither classifies nor ranks its dimensions |
| the eight partition kinds | `ats_corpus_split_v1.schema.json` `policy.partitions[].kind`; the same eight the milestone requires |
| the five `leakage_checks` statuses | `ats_corpus_split_v1.schema.json`; `PASS`, `FAIL`, `UNAVAILABLE`, and `NOT_APPLICABLE` are the `ats_common_v1#/$defs/conformance_status` vocabulary minus `INSUFFICIENT_EVIDENCE`; `UNMET` is this repository's, for a declared target a higher-priority group protects (§1.3) |
| the five conceptual-gate criteria | ATS-1 §17.8, verbatim |
| the ten evasion shapes in §4.8 | ATS-1 §20.3, verbatim |

ATS-1 §17.7 requires grouping on applicable dimensions and forbids a random sentence split, but does
not enumerate partitions, classify dimensions, rank them, or prescribe an assignment function. The
eight partition kinds, the closure/constraint classification, the priority order in §1.3, the balance
targets in §1.4, and the construction in §5.1 are therefore a **repository policy** vocabulary and
procedure that implement normative ATS-1 obligations; they MUST NOT be cited as ATS-1 enumerations.

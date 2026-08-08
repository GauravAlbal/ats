# ATS-1 corpus

The corpus exists to support rule definition, deterministic fixtures,
semantic-detector training, rule retrieval, hard-negative evaluation, repair
evaluation, preservation testing, and rule promotion (spec Section 17.1). It is
not a collection of good and bad prose.

## Curated versus generated

Two kinds of content live here, and the distinction is load-bearing: a
regeneration must never silently rewrite a human's editorial decision.

| Location | Kind | Who owns it |
|---|---|---|
| `corpus/seeds/seed_examples.jsonl` | **Curated.** Hand-authored examples, one or more per label the vocabulary defines. | A person. Editing the text is an editorial act. |
| `corpus/operators/ats_mutation_operators_v1.yaml` | **Curated.** The 22 mutation operators, their preconditions, and their expected rule impact. | A person, reviewed against spec Section 17.5. |
| `fixtures/mutations/sources/*.json` | **Curated.** Two hand-authored TextIR documents carrying every slot the operators need. | A person. |
| `fixtures/repositories/sample-repo/` | **Curated.** Document content plus `COMMITS.json`, the plan that replays it into a real Git repository. | A person. |
| `fixtures/corpus/*.jsonl` | **Generated.** Examples, context bundles, judgments, and adjudications produced by running the pipeline over the sample repository. | `tools/generate_corpus_fixtures.py`. |
| `fixtures/mutations/pairs/<operator>.json` | **Generated.** One source/mutant pair per supported operator, with its transformation and expected rule impact. | `tools/generate_corpus_fixtures.py`. |
| `fixtures/mutations/INDEX.json` | **Generated.** The pair index, plus the operators each source refused and why. | `tools/generate_corpus_fixtures.py`. |

Regenerate the generated half with:

```
PYTHONPATH=src .venv/bin/python tools/generate_corpus_fixtures.py
```

The sample repository's `.git` directory is **not** checked in. An embedded
repository inside this one would become a gitlink and its documents would stop
being visible to the parent. The setup helper runs a real `git init` and real
commits into a destination directory of the caller's choosing, so the inventory
is tested against genuine git output rather than a mock.

## What mining does not do

Spec Section 17.4 lists three inferences the pipeline refuses, and
`ats.corpus.mine` implements each as a function that returns no label:

* a merged or accepted commit is **not** evidence that its text conforms;
* deleted text is **not** thereby a violation;
* a later edit is **not** a verdict on the version it replaced.

Acceptance outcomes, deletions, and later edits are all preserved as context so
an annotator can see them. None of them becomes a label. A mined candidate
carries `label: null`, the signal that triggered it, the vocabulary that signal
came from, and a note saying in as many words that a matched phrase generates a
candidate only.

Every vocabulary a signal matches against comes from the force lexicon, a list
enumerated verbatim in `ATS-1_SPEC.md` (Sections 10.11, 10.20, 10.21), or the
artifact's own declared glossary. There is no invented keyword list.

## Synthetic examples

A synthetic mutation is tagged `synthetic: true` with
`provenance: synthetic_mutation`, and `ats.corpus.records.text_example` refuses
to build a record where those two disagree. `ats.corpus.stats` reports natural
and synthetic counts separately and never sums them: a synthetic mutation shows
that a rule *can* be violated in a given way, not that the violation occurs in
real repositories (spec Section 17.5).

One of the 22 operators, `ATS-MUT-ANTECEDENT-AMBIGUATE`, is declared
`supported: false`. Introducing a second plausible antecedent requires
generating a noun phrase that is grammatically compatible, semantically
plausible, and different from the real antecedent; no deterministic procedure
over a TextIR document produces that, and a model completion would change an
unknown number of features at once. `apply_operator` raises
`UnsupportedCapabilityError` rather than degrading to generation. The operator
is declared anyway so the gap is visible and countable.

## Split discipline

`ats.corpus.split` groups on all fourteen leakage dimensions in
`schemas/ats_corpus_split_v1.schema.json`, in two stages. A group is the
connected component (transitive closure) over the *closure* dimensions — source
document, content hash, normalized content hash, source-mutation pair, explicit
derivation, common-ancestor document, copied-text cluster, near-duplicate
cluster — so two examples joined by any chain of them land in one group.
`repository`, `template`, `author`, `domain`, `source_model_family`, and
`mutation_family` are *constraints*: they decide where whole groups are placed
and never divide one. Joining on repository can collapse a single-repository
input into exactly one group, so the caller must choose grouping dimensions that
match the supplied artifacts.

Content and normalized hashes are the dimensions that catch identical bytes
across repository labels. Both hashes live on `SourceArtifactV1`, not on the
example, so pass the artifacts to `generate_split(..., artifacts=...)`; without
them the two dimensions report `UNAVAILABLE` rather than `PASS`.

The priority order is strict — lineage, exact content, near duplication, then
project, template, and author disjointness, then domain balance — and a
lower-priority target that cannot be met without dividing a higher-priority
group is reported `UNMET` with the blocking group named, never met by dividing
it (`protocols/ATS_SPLIT_POLICY_V0.md` §1.3, §1.4).

Assignment is `u = sha256(seed || 0x00 || block_key)[:8] / 2**64`, and the group
falls into the first partition whose cumulative target fraction exceeds `u`. No
RNG object is constructed, so inserting an example never reshuffles the rest.
The key itself is *not* stable under insertion: adding a near-duplicate merges
two components, by design. `block_key` is the group's own key unless a declared
constraint co-placed it with other groups, in which case it is the lowest key in
the block and `placement_block` records it.

`grouping_dimensions` names the dimensions an example MUST carry to be
assignable. The default is `["repository", "source_mutation_pair"]`, because a
hand-authored fixture legitimately has no source document and defaulting to a
stricter set would send an entire seed corpus to `unassignable`. **For a mined
corpus, declare `["source_document", "repository", "source_mutation_pair"]`.**
An example missing a required dimension is recorded in `unassignable` with the
dimensions it lacks; it is never quietly dropped into training.

A leakage check is reported per dimension, relative to the partitions that
declare it in `disjoint_on`. Every closure dimension is checked regardless,
because a closure dimension spanning two partitions means the closure itself
broke, which is not something a policy may authorise. A constraint dimension no
partition declares disjoint is reported `NOT_APPLICABLE` with the reason — never
`PASS`, which would claim a guarantee nobody asked for and nobody verified — and
a dimension some assigned example does not carry is `UNAVAILABLE` even when the
examples that do carry it are confined.

A source example and any mutation derived from it share a
`source_mutation_pair` value and therefore always share a group. A chain — a
mutation of a mutation — shares no single value, so the lineage pointers are
also followed as directed edges.

## Annotation and adjudication

One queue item is one rule judgment (spec Section 12.10). An item is built from
the example and its context bundle alone; no other annotator's label, rationale,
or judgment identifier ever enters it, and `build_queue` searches the serialized
queue to confirm that before returning. An example whose context bundle is
missing or rated `insufficient` is withheld with a reason rather than queued.

A material semantic example needs at least two *independent* judgments — two
distinct annotator identities — before it can be gold (spec Section 17.9). An
example is material and semantic when its rule is served by a D2, D3, or D4
detector class, or when it claims protected impact on P0 or P1.

Adjudication retains every original judgment verbatim, categorises the
disagreement into one of the nine schema categories, and produces one of the
eight final states. A majority becomes gold only when the adjudicator explicitly
records the minority as an annotation error and names it. Otherwise a divergence
stays `ambiguous_by_design`: a forced majority label MUST NOT erase a genuine
ambiguity in the standard or source. `needs_rule_revision` and
`needs_more_context` are never gold-eligible.

## Data provenance

Spec Section 17.13 requires training data to record use authority. Every
`SourceArtifactV1` carries `use_authority` and `handling_policy`. They cannot be
derived from a document's contents, so they are read from a repository-level
declaration at `.ats/corpus.json`:

```json
{
  "repository_group": "ats-sample",
  "use_authority": "external_training_permitted",
  "handling_policy": "public",
  "domain": "acceptance-kernel"
}
```

The checked-in sample repository is ATS-authored synthetic content and is
independently redistributable. Its public declaration is the only authority for
generated fixture provenance. Without a declaration the inventory records
`use_authority: "unknown"` and `handling_policy: "internal"`, so the public
boundary rejects derived records until an explicit public declaration exists. A
commit may override the authority for one document with an
`ATS-Use-Authority:` trailer.

## Public corpus boundary

The public corpus contains only curated seeds, mutation operators, and generated
fixtures derived from the synthetic sample repository. Authority records and
evidence derived from publication-denied inputs are not distributed: they are
omitted rather than counted, hashed, summarized, or relabeled. The public
surface has no private pilot output or private repository metadata.

# ATS North Star

## What ATS exists to do

ATS exists to make technical and analytic text easier to **locate**, **reconstruct**,
**verify**, and **act on** — *without deleting distinctions that can change interpretation
or action*.

That second half is the whole point. Every readability system in existence can make a
document shorter and smoother. ATS-1 governs the recovery cost of *meaning*, not sentence
simplicity alone (`ATS-1_SPEC.md` §2.1), and it holds one core invariant: a transformation
MUST preserve every distinction that can materially change interpretation, action,
prioritization, risk, compliance, acceptance, or confidence, except where an explicit
retention contract authorizes omission (§2.2).

> **Operational mission (Draft.2 amendment D-A):** ATS is a **controlled technical
discourse standard for transferring operative models between reasoning systems while
preserving human inspectability**. Its primary objective is not linguistic simplicity — it
is faithful, low-cost recovery of the distinctions required to understand, verify,
continue, decompose, or act on a technical model. **Semantic recovery cost** is the
principal concept: the cost of recovering the operative model from the artifact. A
sentence-level readability improvement MUST NOT justify material semantic loss.

ATS is not primarily a readability style guide, and the program is no longer on the
critical path of a large annotation campaign feeding learned detectors. Internal
annotation/adjudication material is omitted from the public distribution and is not
public evidence. Targeted rule development and ambiguity investigation require
separately authorized inputs. Production use is a future evidence source (§27 of
the pivot directive), not a replacement for omitted results.

The distinctions that matter are named, not vibed. They are the five force axes ATS-1
represents separately (§8.1) — likelihood, assessment confidence, evidential force, causal
force, deontic force — plus scope, polarity, quantifier kind, source attribution, authority,
conditions, exceptions, and the protected-field/protected-relation classes P0 and P1
(§11.3.1, §11.3.2). A rewrite that reads better and quietly converts `likely (55–80%)` into
`probable`, or `SHOULD` into `must`, or an assumption into an observation, has destroyed the
thing the reader needed.

Draft.2 adds three protected surfaces on top of P0/P1:

- **Stable semantic coordinates** (D-C): machine-stable identifiers (`requirement_id`,
  `decision_id`, `acceptance_criterion_id`, `work_item_id`, `protocol_id`,
  `protocol_version`, `dependency_target`, authority reference) that MUST survive a
transformation exactly, because downstream planning, tasks, acceptance, and receipts use
them as joins. A coordinate is part of meaning when downstream systems join on it.
- **Semantic basis** (D-F): every material semantic value MAY declare how it was
established — `EXPLICIT`, `DERIVED`, `INFERRED`, `UNAVAILABLE`, `AUTHOR_JUDGMENT`. A
transformation MUST NOT silently convert `INFERRED`/`UNAVAILABLE` source material into an
explicit source-authoritative fact (the raw-prose authority-hierarchy failure the pivot
directive documents).
- **Local semantic closure** (D-D): extractable normative units MUST be understandable
from the unit plus explicitly declared dependencies, without undeclared document-wide
inference.

Locality-preserving redundancy is permitted and often preferred (D-E): repetition that
adds stable identity or extraction locality is not a defect.

## The v0 pipeline

```text
source prose / author intent
        ↓
ATS IR-authoring skill  (records semantic basis; preserves stable coordinates)
        ↓
validated TextIRV1
        ↓
IR linter  (deterministic: coordinates, basis, closure, force)
        ↓
profile-specific output skill
        ↓
Markdown output + semantic trace sidecar
        ↓
output linter  (deterministic: coordinates preserved, no silent strengthening)
        ↓
typed findings → material unresolved semantic review only when needed
        ↓
approved IR → profile renderer → candidate/accepted receipt
        ↓
planning projection  (AtsPlanningProjectionV1 → Arq/VX tasks with source lineage)
```

Three structural properties of that pipeline are load-bearing:

1. **The meaning ledger comes before the prose.** The IR-authoring skill produces an
   `ats.text_ir.v1` document — the typed representation of claims, relations, force, scope,
   provenance, assumptions, boundaries, and update indicators (§4.14). Rendering is a
   projection over that ledger, not the primary artifact. §14.5 states the preference
   directly: for newly generated text, construct the meaning ledger before rendering.
2. **The rendered document stays deterministically traceable.** The output bundle carries a
   trace sidecar mapping each rendered block to the IR objects it realizes, and the Markdown
   carries invisible `<!-- ats:block <id> -->` markers so an ordinary reader sees clean prose
   while a linter can hash each block against the trace
   (`src/ats/output/parse.py`, `src/ats/output/trace.py`).
3. **Acceptance authority stays outside the producing system.** The pipeline ends in a
   *candidate* receipt. §14.11 assigns final authority for semantic acceptance to an
   authorized human or an explicitly governed external acceptance system, and §13.7 forbids
   a component from becoming the authoritative adjudicator for its own finding.
   `ats.output.receipt.build_candidate_receipt` refuses an adjudicator identity in
   `SELF_IDENTITIES` for exactly that reason.

## What v0 is NOT

The first implementation is **not an AI rewriting product** and **not an SLM-training
project**. It is a deterministic evaluator over a normative standard.

The explicit non-goals for v0 (still non-goals for the fleet milestone) are:

- an SLM;
- an embedding index;
- a learned rule router;
- a learned semantic critic;
- an unconstrained rewrite model;
- a generic "writing quality" score;
- a web application;
- a collaborative annotation service;
- support for every reserved ATS profile;
- broad natural-language parsing presented as authoritative;
- a linter that reports semantic `PASS` from the absence of keyword matches;
- a corpus that labels accepted repository prose as automatically conforming;
- a style bureaucracy: style findings are ADVISORY and never block builds, while
deterministic semantic-integrity failures block (Draft.2 operational classes);
- a workflow engine or execution authority: ATS owns semantic representation and
conformance evidence; Arq owns workflow, planning, and acceptance policy;
- an annotation project: human grounding is exceptional and reserved for material
unresolved semantics (near-zero human grounding by default).

The corpus work in this milestone prepares data and governance for later learned components.
It does not train them. The fleet is now the primary evidence source; learned semantic
checking remains deferred advisory infrastructure.

Two of those non-goals are enforced in code rather than aspired to:

- *No semantic PASS from keyword absence.* `ats.rules.results.decide()` derives the status
  from a declared `DecisionPower`; a detector that recognises only a subset of violations
  declares `DETECTS_VIOLATIONS` and gets `REVIEW_REQUIRED`, never `PASS`, when it finds
  nothing. `semantic_review` is a hardcoded `UNAVAILABLE` in both
  `ats.ir.lint.compute_conformance` and `ats.output.lint._compute_conformance`.
- *No corpus that assumes merged prose conforms.* `schemas/ats_source_artifact_v1.schema.json`
  makes `review_state` a required field with the values `accepted | rejected | superseded |
  reverted | draft | unknown` kept distinct, and its own description records that merged
  prose is not assumed conforming (§17.4).

## The normative package is upstream truth

`spec/ATS-1/1.0.0-draft.1/` is the imported normative package and is immutable. Its
`MANIFEST.json` is verified byte-for-byte, its `IMPORT_RECEIPT.json` records the archive
hash, manifest hash, import timestamp, and the result of the package's own validator, and
`ats.spec_package.SpecPackage` is the only read path (`src/ats/spec_import.py`,
`src/ats/spec_package.py`).

Implementation code may expose defects or ambiguities in the draft. It **must not silently
redefine the standard**. Where this implementation found the draft under-determined, the
finding is recorded as an observation with a spec citation in
[`PACKAGE_OBSERVATIONS.md`](PACKAGE_OBSERVATIONS.md) and the code takes the conservative
option — report less authority, not more. Two structural guards back that up:

- No normative object is restated in Python. `ats.schemas.SchemaSet` refuses to load a
  repository-local schema whose `$id` collides with a normative one
  (`NORMATIVE_SCHEMA_IDS`), and the typed views in `ats.ir.model` read a validated document
  rather than declaring which fields exist.
- No detector invents a vocabulary. A term list must come from
  `lexicons/ats_force_lexicon_v1.yaml`, a list enumerated verbatim in `ATS-1_SPEC.md`, or
  declared glossary content in the artifact itself. Every subcheck records its
  `vocabulary_source` in `capability/ats_rule_capability_v1.json`.

## How to read the rest of these docs

| Document | Question it answers |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | What are the modules, how do they depend on each other, and what does the pipeline actually run? |
| [`AUTHORITY_MODEL.md`](AUTHORITY_MODEL.md) | What is any given result *entitled* to establish, and who may accept it? |
| [`SKILL_CONTRACTS.md`](SKILL_CONTRACTS.md) | What do the three authoring skills consume, emit, and refuse? |
| [`CORPUS_DATA_MODEL.md`](CORPUS_DATA_MODEL.md) | What corpus objects exist, how do they relate, and what governs them? |
| [`PACKAGE_OBSERVATIONS.md`](PACKAGE_OBSERVATIONS.md) | Where did the draft turn out to be under-determined, and what did we do about it? |
| [`decisions/`](decisions/) | Why is it built this way rather than the obvious other way? |

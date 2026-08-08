# Evidence and claim boundaries

This document separates what the public repository establishes mechanically from
what has only been observed in a case study. It is informative and does not
change the ATS-1 normative package. When this document conflicts with the
standard, the [normative package](../spec/ATS-1/) wins.

The current public identity is **ATS-1 — Applied Technical Semantics**. The
rename establishes no new effectiveness evidence and does not change the
boundaries or status of the claims below.

## Mechanically established claims

The implementation and its repository checks establish the following bounded
claims for the inputs they receive:

- The imported normative package is checked against its manifest and its own
  validator by `ats spec validate`.
- The implementation exposes both `1.0.0-draft.1` and
  `1.0.0-draft.2`; the draft.1 package is preserved as an immutable imported
  package, while draft.2 is the current new-authoring edition.
- Rule evaluation is deterministic for fixed inputs and a pinned evaluation
  time. A check that cannot decide reports `UNAVAILABLE`, and a detector that
  only recognises a subset does not become `PASS` merely because it found no
  finding.
- The generated public skill pack can be checked against its canonical source
  with `ats skills verify --pack dist/skill-pack`. Its manifest records host
  files, source provenance, standard compatibility, implementation identity,
  and per-file digests.
- Planning projection preserves ATS source coordinates while allowing a
  planner to map requirements to tasks. The projection is a mapping boundary,
  not proof that a requirement and a task are the same object.

These are implementation and packaging properties, not evidence that ATS is
better than another writing system or that every generated artifact is
semantically correct. They hold only within the documented capabilities and
inputs; the implementation does not claim authority it does not possess.

## Case-study observations

The repository also contains bounded observations from particular comparisons:

- an ATS-guided reconstruction of an architecture-scale artifact (the
  repository's Sear comparison);
- a reconstruction from pre-ATS prose;
- an ATS-to-STE transformation; and
- an STE-oriented reconstruction.

In the observed material, consolidation and simplification could remove
state, authority, evidence, or lifecycle distinctions that permitted materially
different implementations. An ATS-guided reconstruction preserved more of the
operative model in that comparison. The lifecycle shorthand
`accepted → routed → disclosed → consumed` illustrates the kind of distinction
under discussion; it is not a universal benchmark result.

These observations are case-study evidence. They depend on the source,
transformation, task, evaluators, and comparison method used. In particular,
they do not isolate STE from the other transformations that occurred. See the
[informative lineage and prior-art record](LINEAGE_AND_PRIOR_ART.md) for the
methodological boundary and provenance classifications.

## Claims not established here

The public evidence does **not** establish any of the following broad claims:

- ATS always improves coding-agent performance.
- ATS universally beats ASD-STE100 or any other style guide.
- ATS reduces defects by a fixed percentage.
- ATS guarantees semantic equivalence.
- ATS is the optimal technical-writing system.
- A clean deterministic lint result proves that an artifact is complete,
  correct, or fit for every downstream use.
- A case study is a general benchmark, production success rate, or causal proof
  about all transformations.

Those claims require separately designed evidence. Until such evidence exists,
public documentation must not imply them.

## Preferred claim shape

A supported high-level description is:

> ATS is designed to preserve implementation-relevant semantic distinctions
> across technical handoffs.

A supported observed-case description is:

> In one architecture-scale comparison, a simplification transform removed
> distinctions that permitted materially different implementations, while an
> ATS-guided reconstruction preserved substantially more of the operative
> model.

The second statement must retain its case-study and methodology caveat. The
first describes the design objective; neither is a universal superiority claim.

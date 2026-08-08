# Stability and version contract

This document describes public compatibility expectations. It is informative;
the [ATS-1 normative package](../spec/ATS-1/) and its explicit migration/change
records remain authoritative.

## Three version domains

ATS has three version identities. They must not be substituted for one another:

| Domain | Current value | What it versions |
|---|---|---|
| ATS-1 normative edition | `1.0.0-draft.2` for new durable authoring | Rules, force semantics, schemas, and other normative meaning |
| ATS implementation | `0.5.0` | The local runtime and CLI that validate, lint, resolve, and receipt artifacts |
| ATS skill pack | `0.1.1` | The released `ats`, `ats-spec`, `ats-assess`, and `ats-review` skills and recipes |

A skill-pack release can support an ATS-1 edition without being that edition.
Likewise, an implementation release can expose a package finding without
silently changing normative meaning.
Release `0.1.1` is published under the signed annotated tag
`v0.1.1-skill-pack`; canonical source precedes deterministic generation and
verification.

## Draft status

`ATS-1 1.0.0-draft.2` is still a **draft standard**. While it is a draft, the
project may make explicitly recorded changes to normative rules, schemas,
examples, and compatibility or migration guidance. Such changes belong in the
normative package and its migration/change record; they are not implied by an
ordinary README edit or implementation refactor.

Draft status does not make all behavior fluid. The following are protected:

- `ATS-1 1.0.0-draft.1` remains byte-identical to its imported package and is
  not cleaned up in place.
- An artifact's standard edition and relevant provenance are recorded rather
  than inferred from the latest implementation.
- A draft.1 artifact does not silently acquire draft.2 semantics.
- A draft.2 artifact is not silently downgraded to draft.1 under an incompatible
  policy; incompatible interpretation is refused.
- A skill pack is generated from one canonical source and its manifest binds
  host files, source provenance, supported standard editions, and digests.

## The two-default law

The repository keeps two defaults because historical material and new authoring
have different compatibility obligations:

| Material or action | Default edition |
|---|---|
| Unlabeled historical, corpus, and annotation-bench material | `ATS-1 1.0.0-draft.1` |
| New durable authoring under the current ATS policy | `ATS-1 1.0.0-draft.2` |

The historical default stays draft.1 unless an explicit migration selects
draft.2. New durable authoring starts at draft.2. Neither direction may happen
silently.

The CLI can make an edition explicit, for example:

```bash
ats --spec-version 1.0.0-draft.2 capability show
```

`ats spec status` shows the editions available in the checkout and the
implementation identity. It does not turn implementation version into a
standard version.

## Artifact version binding

Artifacts remain bound to the ATS edition under which they were authored. ATS
does not silently reinterpret them under a later standard edition. A consumer
must use the artifact's recorded edition, or perform an explicit migration
with the documented compatibility and evidence obligations.

This binding is important for receipts, lint findings, planning projections,
and generated skill-pack provenance: “latest installed implementation” is not a
substitute for “edition used to author and verify this artifact.”

## Authority and compatibility boundary

When public documents disagree, use this order:

1. ATS-1 normative package;
2. normative migration and change records;
3. public skill contracts;
4. artifact recipes;
5. README and quickstart guidance;
6. case studies and lineage notes.

Optional consumers may add workflow policy, but they cannot redefine what ATS
means. Generic authoring, verification, and planning projection remain public
capabilities.

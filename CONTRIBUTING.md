# Contributing to ATS

Thank you for helping improve ATS. Contributions should remain useful to an
unrelated user of the public repository: reproducible, reviewable, and free of
private infrastructure assumptions.

## Before opening a pull request

1. Read the relevant documentation and inspect nearby tests or fixtures before
   changing behavior.
2. Keep changes focused. Explain the user-visible behavior, affected files, and
   verification you performed in the pull request description.
3. Do not add credentials, private corpus material, local paths, or runtime/build
   dependencies on private or sibling fleet repositories/services.
4. Run the narrowest relevant checks locally. For implementation changes, include
   the command and result; for documentation or examples, check links, commands,
   and provenance/redistribution status as applicable.
5. Do not edit the imported ATS-1 draft.1 package in place. Historical and
   unlabeled corpus or benchmark material remains interpreted as
   `ATS-1 1.0.0-draft.1`; new durable authoring defaults to
   `ATS-1 1.0.0-draft.2`. A version change must be explicit, never an accidental
   consequence of cleanup.

Open a pull request against the default branch. Maintainers may request a
smaller change, additional evidence, or a separate proposal when a patch crosses
one of the classes below.

## Contribution classes

### 1. Implementation and tooling

Bug fixes, performance work, tests, generated-output updates, packaging, and
other executable/tooling changes follow the normal pull-request process. They
must preserve the meaning of the selected ATS edition. If a change exposes a
specification defect or ambiguity, record it for review rather than silently
changing a rule, schema, force, profile, protected meaning, or normative example.

Generated files should be updated through their documented generator or command,
not by hand, when a generator exists.

### 2. Documentation and examples

Documentation, fixtures, walkthroughs, and examples should state which ATS
edition they use when that distinction matters. Examples must be technically
accurate and safe to redistribute. Before submitting one, verify that it does not
include secrets, private data, copied material without permission, or an implied
dependency on private infrastructure. Include source/provenance notes in the PR
when the material is adapted from elsewhere.

A documentation cleanup must not quietly revise normative ATS meaning. If prose
needs to change because the rule itself should change, use the normative process
below instead of treating it as editorial work.

### 3. Normative ATS changes

A normative change is any change to rule meaning, force semantics, schema
semantics, profile semantics, protected meaning, or a normative example. It
requires an explicit proposal in the PR description (or a linked proposal) before
implementation is merged. The proposal must include all of:

- **Problem** — the concrete ambiguity, defect, or unmet need.
- **Current rule** — the current normative text and edition affected.
- **Proposed rule** — exact replacement or addition, including its scope.
- **Rationale/evidence** — examples, implementation evidence, or other grounds.
- **Positive example** — an artifact that should be accepted under the proposal.
- **Negative/hard case** — an artifact that must still be rejected, refused, or
  remain undecidable.
- **Compatibility impact** — effects on existing draft.1 and draft.2 artifacts,
  schemas, validators, and consumers.
- **Migration impact** — required migration table entry, version selection, or
  explicit statement that no migration is needed.

The proposal must identify whether it targets draft.1, draft.2, or a future
edition. Normative changes are reviewed as semantic changes even when their diff
looks like cleanup; they must never land accidentally through formatting,
refactoring, generated-file refreshes, or documentation-only edits.

## Review standard

Reviewers look for a clear claim boundary, deterministic verification where
available, compatibility with the edition named by the change, and evidence that
public users can exercise the result without private services. Maintainers may
ask for a regression fixture or a migration note when behavior changes.

Security-sensitive defects should not be disclosed in a public pull request or
issue. Follow [`SECURITY.md`](SECURITY.md) instead.

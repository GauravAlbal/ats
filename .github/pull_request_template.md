## Summary

What changed, and what user-visible problem does it solve?

## Scope and compatibility

- [ ] This change preserves ATS-1 normative semantics unless explicitly described here:
- [ ] New durable authoring remains draft.2; historical unlabeled material remains draft.1 unless explicitly migrated.
- [ ] Generated skill-pack files were regenerated from canonical source, or are intentionally unchanged.
- [ ] No private repository, credential, operator-home path, sibling checkout, or hosted service is required.

- [ ] This change is non-normative; or
- [ ] This change is normative and I linked an explicit proposal for any change
  to rule meaning, force semantics, schema semantics, profile semantics,
  protected meaning, or a normative example; an inline explanation alone is not
  sufficient.
  **Proposal link (required for normative changes):** <!-- paste a URL or
  `#anchor` to the explicit proposal; do not leave this blank -->
  The linked proposal identifies its target edition (`draft.1`, `draft.2`, or
  future) and includes:
  - **Problem** — concrete ambiguity, defect, or unmet need.
  - **Current rule** — current normative text and edition affected.
  - **Proposed rule** — exact replacement or addition, including scope.
  - **Rationale/evidence** — examples, implementation evidence, or other grounds.
  - **Positive example** — artifact accepted under the proposal.
  - **Negative/hard case** — artifact still rejected, refused, or undecidable.
  - **Compatibility impact** — effects on draft.1/draft.2 artifacts, schemas,
    validators, and consumers.
  - **Migration impact** — required migration entry/version selection, or an
    explicit statement that no migration is needed.

## Verification

Commands run and relevant results:

```text

```

- [ ] I added or updated a focused test when this change introduces a new observable contract.
- [ ] `ats skills verify --pack dist/skill-pack` passes when the skill pack is affected.

## Disclosure and provenance

- [ ] Public examples and fixtures contain no private or sensitive material.
- [ ] Claims are bounded to observed evidence and do not imply unsupported integrations or guarantees.
- [ ] Documentation, release notes, or migration guidance is updated when needed.

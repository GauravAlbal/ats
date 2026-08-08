# ADR-0015: Intentional semantic redundancy is permitted

**Status:** Accepted
**Date:** 2026-08-07

## Context

Draft.1's ATS-DISC-003 ("restatements MUST add function") was written for a
document where a single linear read is the consumption pattern. The fleet
consumption pattern is fragmentary: units are sharded into tasks, retrieved
in fragments, reviewed one requirement at a time, and linked by identity
across planning and evidence. Under that pattern, repetition is not noise.

The operational thesis makes this concrete: fragment-level consumption benefits
from intentional repetition — repeated actors, stable requirement IDs, repeated
normative force, acceptance criteria adjacent to requirements, and locally
repeated conditions and boundaries. That repetition can make local semantic
closure achievable: a unit that restates its actor and acceptance criterion is
extractable without document-wide inference. Internal comparative evidence for
this thesis is omitted from the public distribution and is not public evidence.

The failure mode the rule must avoid is the inverse: a detector trained on
the old statement would flag the very repetition the fleet depends on, and
an author optimizing for minimal word count would delete the locality the
pipeline needs. Draft.1's normative statement did not distinguish
functionless repetition from locality-preserving repetition, so the rule
itself was mis-scoped for the operational thesis.

## Decision

Draft.2 re-scopes ATS-DISC-003 (delta D-E, spec §11.3.3):

- "Deletion of functionless repetition" stays, and the normative statement
  is amended to: "Restatements MUST add function. Zero-information
  repetition — the same proposition restated without adding a semantic
  role, locality, or extraction benefit — is a defect. Locality-preserving
  redundancy is not zero-information repetition and is permitted."
- **Locality-preserving redundancy** — repetition that adds stable identity,
  standalone extraction, task or acceptance-criterion generation, review,
  receipt linkage, or retrieval locality — is explicitly not functionless
  and MAY be retained. ATS permits and often prefers it for artifacts
  expected to be sharded or retrieved in fragments.
- ATS-DISC-003's `rule_version` bumps to `1.0.0-draft.2` and its
  operational class is `advisory`: the rule surfaces style findings and
  never blocks. No new anti-repetition rule is added; the scope of this
  decision is DISC-003 only, and the force, evidence, and preservation
  rules are untouched.
- The output skills are updated accordingly: `ats-specify-output` and
  `ats-assess-output` instruct authors that requirements and acceptance
  criteria MAY restate overlapping semantics when the restatement changes
  discourse role or extraction locality — not minimal word count.

## Consequences

- Restating a requirement's actor and force in an adjacent acceptance
- Style findings stay advisory and never block builds under the public operational
  class policy, so even genuine zero-information repetition is a review
  suggestion, not a gate.
- The migration table classifies the change honestly: the normative
  statement is a rule-boundary change plus clarification, with the
  behavioral consequence that draft.1-era findings of "repetition" do not
  carry over as draft.2 defects.
- Cost: "adds function" is a judgment, so DISC-003 remains advisory rather
  than deterministic. That is the correct ceiling — no mechanical check
  can decide whether repetition adds extraction locality.

## Alternatives considered

**Delete ATS-DISC-003 entirely.** Rejected. Zero-information repetition is
still a real defect — it inflates review cost and obscures signal. The rule
has a job; its statement was wrong, not its existence.

**Make redundancy required.** Rejected. Mandatory restatement would
manufacture padding in documents that are consumed linearly, and it would
turn a permission into a tax. The decision permits locality-preserving
redundancy; it does not mandate it.

**Leave the draft.1 statement and carve exceptions in the detector.**
Rejected. The normative statement itself misdescribes the operational
thesis — "repetition" as presumptive defect. Fixing the standard (ADR-0003:
never restate normative objects in code) instead of special-casing the
detector keeps the registry and the rule honest.

## References

- ATS-1 draft.2 §11.3.3 (P2), §12.7.4 (ATS-DISC-003 row, advisory), and the
  public operational class policy
- Draft.2 spec §11.3.3 (P2), §12.7.4 (ATS-DISC-003 row, advisory)
- Draft.2 rules registry entry for ATS-DISC-003 (`rule_version`
  `1.0.0-draft.2`); `skills/ats-specify-output/SKILL.md`,
  `skills/ats-assess-output/SKILL.md`
- ADR-0014 (local closure), ADR-0003 (no restatement of normative objects)

# ADR-0016: Human grounding escalates only when a material action depends on resolution

**Status:** Accepted
**Date:** 2026-08-07

## Context

The pre-pivot program treated human adjudication as the primary resolution
mechanism for semantic uncertainty. Internal program evidence is omitted from the
public distribution and is not public evidence. The public architectural decision
is that broad manual adjudication is not a release prerequisite; targeted review
is reserved for material action-blocking uncertainty.

The fleet workflow needs the opposite default. Artifacts are authored and
consumed continuously; every missing field cannot become a question, or
authoring turns back into an annotation project and the fleet never ships.
Silent reconstruction can make downstream models invent authority and strengthen
semantics without license. The resolution policy must therefore be explicit about
*when* a human is consulted — and just as explicit about when one is not.

## Decision

Human grounding in the fleet is **near-zero by default**, with escalation
only when a material action depends on resolution:

- The resolution order is fixed: (1) preserve explicit source semantics; (2)
  derive mechanically when valid; (3) preserve author judgments when authority
  permits new authoring; (4) represent uncertainty explicitly; (5) continue when
  the unresolved value is non-blocking; (6) escalate only when a material action
  depends on resolution.
- **Human review MUST NOT be required merely because a field is absent.**
  Absence is a typed silence (ADR-0012), not a defect signal.
- Escalation is a `REVIEW_REQUIRED` outcome on the specific unresolved
  semantic, not a general adjudication wave and not a blocking question to
  the operator. It fires when a material action — acceptance, task
  derivation, a decision with real consequence — depends on the value.
- This is consistent with ATS-BASIS-002's permitted moves: when action
  requires resolution, asking for adjudication is one of the explicitly
  permitted compiler behaviors. Escalation is therefore the *licensed*
  path for action-blocking uncertainty, and silent promotion is never one
  of the options.
- The behavior is pinned by the public basis and human-grounding fixtures:
  missing nonessential precedence → no operator question, stays `UNAVAILABLE`;
  action-blocking ambiguity → `REVIEW_REQUIRED`; explicit author intent resolves;
  absence is never silently converted into a fact.
  operator's attention is a scarce resource spent on material decisions.
- Non-blocking unknowns remain unknown in the receipt. That is correct
  behavior, not incomplete work: typed insufficiency over invented
  completion.
- When an escalation does fire, it routes through the targeted adjudication
  triggers of ADR-0011 (production friction, boundary change, detector
  promotion, recurring ambiguity, hard-gating review, forensic review) —
  not through queue completion.
- Cost: some artifacts will carry `UNAVAILABLE` fields that a patient human
  could have filled. Accepting that cost is the point of the policy; the
  alternative is the annotation project the pivot explicitly forbids.

## Alternatives considered

**Block on every missing field.** Rejected. Human review MUST NOT be required
merely because a field is absent; absence is typed `UNAVAILABLE`, and making every
missing value blocking would make ATS authoring unviable as fleet infrastructure.

**Ask the operator about every `UNAVAILABLE` value.** Rejected. This is
the annotation project re-imported through the back door; unnecessary
questions are exactly what the policy forbids.

**Auto-fill missing values with the most plausible reading.** Rejected. That is
silent promotion, which is precisely the semantic-strengthening violation
ATS-BASIS-002 blocks.

**Resolve ambiguity through scheduled adjudication waves.** Rejected.
Adjudication is now trigger-driven and targeted (ADR-0011); a standing
wave would recreate the bench-as-gate pattern.

## References

- ATS-1 draft.2 §4.25 (semantic basis and `UNAVAILABLE`), §7.19 (basis
  mechanics), and the public human-grounding fixtures; rule ATS-BASIS-002 (no
  silent strengthening)
- `fixtures/ir/` basis fixtures; tests/unit for basis and closure detectors
- ADR-0012 (source semantic basis), ADR-0011 (bench de-prioritization),
  ADR-0002 (never pass by absence)

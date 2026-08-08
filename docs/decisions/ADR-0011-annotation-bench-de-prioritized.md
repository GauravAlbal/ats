# ADR-0011: Annotation adjudication is de-prioritized as a rollout gate

**Status:** Accepted
**Date:** 2026-08-07

## Context

An internal annotation program informed this pivot. Its records and empirical
measurements are omitted from the public distribution and are not public evidence.
The public decision is architectural: deterministic package, schema, lint, receipt,
and projection checks can ship independently, while semantic classification remains
a separate evidence-gated research problem.

Before the pivot, completion of an adjudication workflow was treated as a rollout
precondition. That coupling is removed. Public release MUST NOT depend on an
unavailable private record, and no omitted internal result is carried forward as a
reliability, transfer, acceptance, or promotion claim.

## Decision

The annotation bench is **de-prioritized as a rollout gate**:

- Internal queues, gold records, adjudications, and gates are outside the public
  distribution and are not public evidence. No public claim depends on them.
- The fleet-release gates are the deterministic, capstone, and repository gates
  defined by the public release workflow. No unfinished internal evaluation is
  cited as evidence for rule promotion.
- Human adjudication is triggered only by the following six conditions: (1) a
  production rule repeatedly generates high-value or high-friction findings; (2)
  a draft rule boundary must change; (3) a semantic detector is being promoted
  from advisory/candidate authority; (4) a real artifact exposes a recurring
  ambiguity; (5) a rule is being considered for deterministic or semantic
  hard-gating; (6) a production failure requires forensic review of the
  standard's behavior.
- Queue existence is not a trigger. Operator time is not spent completing
  the queue merely because it exists.
- Any future targeted rule-development or detector-calibration work requires
  separately authorized, reproducible inputs and an explicit evidence record; it
  is not drained by a release calendar.

## Consequences

- The release no longer waits on completion of an internal adjudication workflow.
  Rules whose boundary is disputed or whose behavior is uncertain stay advisory
  or `REVIEW_REQUIRED` (ADR-0005, ADR-0008).
- De-prioritizing an internal bench does not promote rules. Promotion remains
  subject to the evidence and authority requirements in this ADR and ADR-0008.
- Conformance-classification questions without public evidence remain unavailable.
  The pivot ships deterministic checks plus capstones, and future production
  feedback is a separately governed evidence source.
- What must not regress: fail-closed behavior, no-PASS-by-absence
  (ADR-0002), and the rule that a detector's authority is capped by the
  classes the registry declares (ADR-0008). The evidence boundary is part of
  that honesty floor.

## Alternatives considered

**Finish an internal adjudication workflow as a precondition.** Rejected. The
underlying records are omitted and are not public evidence; the six targeted
triggers above govern adjudication, and completion of an unpublished workflow is
not one of them.

**Run another adjudication pass with a stronger model.** Rejected. A further model
pass is not an independent acceptance authority. Targeted adjudication remains
available for boundary questions when separately authorized evidence exists.

**Treat the internal bench as a release artifact.** Rejected. Its publication
status is outside this ADR; omitting it prevents accidental reuse as public
promotion or reliability evidence.

**Keep the gate nominally but ignore it.** Rejected. A gate that exists but is not
enforced is worse than none: it invites the dishonest claim that unavailable
adjudication stands behind findings it never produced.


## References

- ADR-0010 (operationalization pivot), ADR-0016 (human-grounding escalation),
  ADR-0002 (never pass by absence), ADR-0005 (semantic review structurally
  unavailable), ADR-0008 (authority capped by registry classes)

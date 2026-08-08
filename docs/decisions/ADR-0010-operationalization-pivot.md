# ADR-0010: Operationalization pivot — ATS becomes fleet infrastructure

**Status:** Accepted
**Date:** 2026-08-07

## Context

An internal annotation pilot and operational examples informed this pivot.
Those source records are not part of the public distribution and are not
public evidence for reliability, transfer quality, or empirical superiority.
No private-derived count or score is carried into this ADR.

The public rationale is architectural. ATS already has deterministic package,
schema, lint, receipt, and projection mechanics that can be exercised against
the independently redistributable fixtures in this repository. Semantic
classification remains a separate research problem whose uncertainty need not
prevent users from adopting the deterministic surface. The critical path
therefore changes from “finish a large annotation campaign, then build semantic
detectors, then roll out” to “deploy the deterministic standard infrastructure,
keep semantic detectors explicitly unavailable where evidence is insufficient,
and require separate public evidence before making empirical performance
claims.”

## Decision

ATS changes program role from research standard to **operational fleet
infrastructure**:

- The production thesis becomes: *a controlled technical discourse standard
  for transferring operative models between reasoning systems while preserving
  human inspectability.* Primary objective: faithful, low-cost recovery of the
  distinctions required to understand, verify, continue, decompose, or act on
  a technical model.
- The next normative package is **ATS-1 `1.0.0-draft.2`**, a narrow hardening:
  mission statement, relation-preservation as a normative rule, stable
  semantic coordinates as protected semantics, local semantic closure,
  intentional-redundancy policy, source-basis provenance, and a narrow
  semantic-strengthening prohibition. Draft.1 stays immutable.
- The implementation adds the deterministic operational substrate:
  fleet-policy resolution, planning projection, mock Arq/VX bridge, and
  deterministic lint for the new protected surfaces.
- **The internal annotation pilot is de-prioritized as a rollout gate.** Its
  private queue, blind records, and gate are omitted from the public distribution
  and are not public evidence. Targeted rule development, detector calibration,
  and ambiguity investigation require separately authorized evidence. Human
  adjudication is triggered by production friction, boundary changes, detector
  promotion, or forensic review — not by queue existence.
- Learned semantic components stay deferred advisory infrastructure.
  Production authority remains: deterministic checks + explicit policy +
  human/Arq acceptance.

## Consequences

- **What ATS is not:** a readability style guide, a universal writing voice,
  an SLM, an execution authority, or a workflow engine. Style findings are
  ADVISORY and never block builds; deterministic semantic-integrity failures
  block.
- **What changes in the pipeline:** the IR-authoring skill records semantic
  basis where material; stable coordinates are protected exactly; extraction
  must produce locally closed units; the deterministic linter gains
  coordinate, basis, closure, and strengthening checks; a planning projection
  feeds Arq/VX with source lineage; near-zero human grounding is the default,
  with escalation only for material unresolved semantics.
- **What must not regress:** fail-closed behavior, no-PASS-by-absence,
  content-addressed receipts, authority separation, immutable package
  discipline, and the distinction between "artifact satisfies a rule" and
  "a detector had authority to decide the rule."
- **Evidence discipline:** the public distribution does not treat omitted internal
  material as evidence. Future production artifacts require their own provenance
  and evidence records; historical documents are not mass-converted. Source
  states stay distinct so no detector is trained to recognize its own renderer's
  output.
- **Cost:** the milestone must not trade testing for speed — the pivot ships with
  contract tests and three capstones, and release acceptance remains governed by
  those repository-local gates.

## Alternatives considered

**Treat completion of an internal adjudication workflow as a precondition.**
Rejected. The underlying pilot records are omitted and are not public evidence;
ADR-0011 defines targeted adjudication triggers, and completion of an unpublished
queue is not one of them.

**Wait for a stronger model pass.** Rejected. A further model pass is not an
independent acceptance authority. The architecture keeps adjudication available
for targeted boundary questions without treating private pilot material as
evidence for a rollout or detector claim.

**Promote draft.2 wholesale without evidence.** Rejected. Draft.2 carries only
deltas represented in the immutable package and covered by implementation
fixtures; boundary-defective or disputed rules stay advisory/`REVIEW_REQUIRED`
rather than being promoted to make the release look complete.

**Build the semantic SLM now.** Rejected. The architecture stays compatible
(static router, rule-conditioned critic, preservation critic, bounded repair),
but learned components must not distort the v0.5 design.

## References

- ATS-1 draft.2 normative package (`spec/ATS-1/1.0.0-draft.2/`), especially its
  mission, protected-semantics, evidence, and release requirements
- ADR-0002 (never pass by absence) — preserved, extended by the
  basis/strengthening rules
- ADR-0001 (immutable package) — draft.2 is a new immutable package, not an
  edit
- `docs/NORTH_STAR.md` (amended by this pivot)

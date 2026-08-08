# ADR-0014: Local semantic closure is the extraction contract

**Status:** Accepted
**Date:** 2026-08-07

## Context

An internal operational observation motivated this pivot, but its source records
and measurements are omitted from the public distribution and are not public
evidence. The public design rationale is that intentional repetition — stable IDs,
actors, normative force, acceptance criteria adjacent to requirements — supports
fragment-level extraction for task decomposition, review, and evidence lineage.
That use case requires a unit to carry its own operative meaning.

Draft.1 had no such requirement. A unit could lean on document-wide
inference: the actor, the boundary, the dependency, the proof obligation
might live anywhere in the document and be recoverable only by reading the
whole thing. That is not a failure for a linear read, but it is a failure
for the fleet's actual consumption pattern, where units are sharded into
tasks, retrieved in fragments, and reviewed one requirement at a time. A
requirement that only means something once three other sections are
mentally loaded cannot be planned against, accepted against, or evidenced
against reliably.

## Decision

Draft.2 defines **local semantic closure** as a normative concept (delta
D-D, spec §4.24 and §7.18):

- A unit is locally closed when its operative meaning can be recovered from
  the unit plus explicitly declared dependencies without requiring
  undeclared document-wide inference.
- For extractable normative units, recovery SHOULD include, where
  applicable: stable identity, actor, modality, action, object, condition
  or trigger, scope, exception, quantitative boundary, dependency, proof
  obligation, acceptance criterion, and rationale/evidence reference.
  Explicit enclosing scope MAY provide values, but extraction MUST remain
  reliable. Not every field must appear in every sentence.
- Enforcement is mechanical presence checking with an honest ceiling.
  ATS-CLOSE-001 (major, `review_required`) runs for the SPECIFY profile:
  every requirement slot must carry actor (or a declared inherited-scope
  marker), deontic, action, and object; every `acceptance_criterion_id`
  and `dependency_target` reference must resolve. The detector's
  `known_limits` states the boundary explicitly: **mechanical checks do not
  prove semantic closure.** Presence of the slots is evidence the unit
  *can* be locally recovered; it is not proof that a reader *does* recover
  the same operative meaning. On a clean run the rule yields
  `REVIEW_REQUIRED`, never PASS-by-absence (ADR-0002).
- Closure is a property of the unit plus its declared dependencies, so
  sharding and retrieval are safe: a unit that declares its dependency
  targets can be extracted without the rest of the document.

## Consequences

- SPECIFY authoring must fill the named slots or declare an inherited-scope
  marker; a requirement that silently inherits its actor from prose three
  sections away is a finding, not a style note.
- The planning projection (ADR-0019) can rely on closure: requirement slots
  that must be present for projection are the same slots ATS-CLOSE-001
  checks, so projection input is mechanically well-formed before the
  projection runs.
- Retrieval and review get a stable contract: fragments are consumable in
  isolation, which is what makes fleet-scale review and evidence lineage
  cheap.
- Cost: authors may no longer rely on document-wide inference as a license. That
  is the price of making units extractable; committed fixtures exercise the
  mechanical boundary without implying general recovery performance.

## Alternatives considered

**Require every field in every unit.** Rejected. The spec itself says not
every field must appear in every sentence; mandatory-everything would
manufacture noise, bloat, and false precision (and would contradict the
intentional-redundancy decision, ADR-0015).

**Treat closure as a style guideline with no checks.** Rejected. A
guideline without a check would be dropped under the same compression
pressure that drops coordinates; the mechanical slot check is what makes
closure part of acceptance rather than aspiration.

**Claim the mechanical checks prove semantic closure.** Rejected. Presence of
slots does not establish that recovery succeeds; the `known_limits` boundary is
the honest version and does not claim empirical performance.

**Enforce closure only at whole-document validation.** Rejected. That
defeats the fragment-extraction use case that motivated the concept; the
unit-plus-declared-dependencies scope is the entire point.

## References

- ATS-1 draft.2 §4.24 (local semantic closure), §7.18 (closure mechanics), and
  the task/acceptance decomposition contract in the public package
- Draft.2 spec §4.24 (definition), §7.18 (closure mechanics); rule
  ATS-CLOSE-001 (registry §12.7.5)
- `src/ats/rules/deterministic/closure.py`; `fixtures/ir/conforming/
  ats-close-001-*.json`, `fixtures/ir/violation/ats-close-001-*.json`
- ADR-0002 (never pass by absence), ADR-0015 (intentional redundancy),
  ADR-0019 (planning projection)

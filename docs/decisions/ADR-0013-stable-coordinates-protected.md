# ADR-0013: Stable semantic coordinates are protected semantics

**Status:** Accepted
**Date:** 2026-08-07

## Context

Internal reconstruction exercises informed this pivot, but their source records
and measurements are omitted from the public distribution and are not public
evidence. The design rationale is architectural: a proposition that survives under
a different identifier is not a recovered proposition for any downstream system
that joins on identity.

That asymmetry is the hazard. A proposition that survives under a different
identifier is not a recovered proposition for any downstream system that joins on
identity: planning, task decomposition, acceptance criteria, implementation,
tests, review, receipts, and postmortems all link by coordinate. "The semantics
are still recoverable" is exactly the wrong consolation when recovery requires
re-deriving identity through document-wide inference — the same unauthorized
reconstruction that an authority boundary must prohibit.

A coordinate is therefore not a surface convenience. Its loss can break
joins even when its proposition survives, so it must be protected with the
same force as the semantic value itself.

## Decision

Draft.2 makes stable semantic coordinates **protected semantics** (delta
D-C, spec §4.23 and §7.17):

- Definition: a stable semantic coordinate is a machine-stable identifier
  whose loss can break joins among specification, planning, task
  decomposition, acceptance criteria, implementation, tests, review,
  receipts, postmortems, and later amendments. It is distinct from a
  semantic proposition: a proposition may remain recoverable while its
  coordinate is lost.
- The protected kinds are exactly eight: `requirement_id`, `decision_id`,
  `acceptance_criterion_id`, `work_item_id`, `protocol_id`,
  `protocol_version`, `dependency_target`, and explicit cross-document
  authority reference. The IR declares them in a document-level
  `stable_coordinates` array of `{kind, id, source_pointer}` with
  `uniqueItems: true` on ids.
- **Coordinate ≠ proposition.** The §7.17 principle is normative: a stable
  coordinate MUST survive a transformation even when the associated
  proposition remains recoverable through another coordinate, because units
  with different authority, lifecycle, dependency, execution, verification,
  or evidence roles are not interchangeable. Semantic equivalence does not
  imply coordinate equivalence.
- The P0 field list (§11.3.1) gains "stable semantic coordinates", so
  coordinate preservation is a P0 preservation obligation, not a style rule.
- Enforcement is deterministic and blocking: ATS-COORD-001 (every declared
  coordinate resolves to a real id in the IR; every coordinate id used in
  the IR is declared when the document declares the block) and ATS-COORD-002
  (no duplicate coordinates; `dependency_target` and
  `acceptance_criterion_id` references resolve) are critical/block rules
  with DECIDES power, implemented in
  `src/ats/rules/deterministic/coordinates.py`. The structural checks
  IR-ID-UNIQUE and IR-REFS are extended in place to cover the new ids —
  no new check IDs are introduced.
- Output lint `OUT-COORD-PRESERVED` (in `src/ats/output/lint.py`) fails when
  a declared coordinate does not appear in at least one output block's
  `references()` *and* in the block text verbatim. A dropped or altered
  coordinate string is a FAIL.

## Consequences

- Renderers must carry coordinate strings exactly; a paraphrase that preserves
  meaning but alters the identifier fails lint. Deterministic output checks make
  retention checkable without relying on private reconstruction evidence.
- Downstream joins become exact: the planning projection (ADR-0019) and every
  derived task link use the source coordinates, so one obligation can map to
  several tasks while keeping a machine-stable join instead of unrelated
  statements.
- Receipts bind the IR, so coordinate sets are frozen per receipt; a later
  amendment that renames an id is a new artifact, not an edit.
- Cost: authors may no longer "improve" ids for readability mid-stream, and
  documents that use coordinates are obligated to declare them. The block
  rules are unwaivable (contract §3), consistent with the integrity class.

## Alternatives considered

**Treat coordinates as advisory style guidance.** Rejected. Dropping coordinates
under compression pressure would break the operational joins the fleet needs;
"advisory" would make that loss permissible.

**Regenerate coordinates downstream (planner or renderer assigns fresh
ids).** Rejected. New ids break the join to the source artifact; the whole
point is that identity is source-bound and stable across the pipeline.

**Carry coordinates only in the planning projection, not in rendered
text.** Rejected. `OUT-COORD-PRESERVED` needs text-level survival because
rendered artifacts are the human-inspectable surface and the input to
later steps; a projection-only coordinate is a join that only exists while
the projection is regenerated.

**Content-hash-based coordinates.** Rejected. A hash changes with any edit,
so it is the opposite of stable: it would invalidate every downstream link
on every revision.

## References

- ATS-1 draft.2 §4.23 (stable-coordinate definition), §7.17 (coordinate
  principle), and §11.3.1 (P0 field list)
- Draft.2 package `schemas/ats_text_ir_v1.schema.json`
  (`stable_coordinates`); `src/ats/rules/deterministic/coordinates.py`;
  `src/ats/ir/checks.py` (IR-ID-UNIQUE, IR-REFS); `src/ats/output/lint.py`
  (`OUT-COORD-PRESERVED`)
- ADR-0010 (pivot; private empirical material omitted and not public evidence),
  ADR-0019 (planning projection), ADR-0020 (draft coexistence)

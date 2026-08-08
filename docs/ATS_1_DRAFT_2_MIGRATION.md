# ATS-1 draft.1 → draft.2 Migration

Standard: ATS-1 · Editions: `1.0.0-draft.1` (immutable, preserved) → `1.0.0-draft.2`
(authored normative package). Milestone: `v0.5.0-fleet`.

## What draft.2 is

A narrow normative hardening. Draft.2 preserves the draft.1 semantic model — the
meaning-ledger claim model, the five calibrated force axes, the P0/P1/P2 preservation
classes, the non-strengthening invariant, no-invented-claims, retention contracts, the
30-rule registry — and adds six deltas (D-A … D-F) supported by implementation evidence
and the operational thesis. It is not a redesign.

The full delta texts are normative in `spec/ATS-1/1.0.0-draft.2/ATS-1_SPEC.md`, marked
with `> **Draft.2 amendment (D-<X>):**` callouts at each amendment site. This document
classifies every delta and states migration requirements. The package validator
cross-checks that every delta ID below appears as a marker in the spec and every marker
is classified here.

## Delta classification table

| Delta | Classification | Section(s) changed | Rules changed/added | Schema impact |
|---|---|---|---|---|
| D-A Mission | clarification + new invariant | §2.1 | — | none |
| D-B Relation preservation | new protected semantic + rule boundary change | §4.23, §11.3.2 | ATS-PRES-003 (new), Appendix A §12 promoted | none |
| D-C Stable coordinates | new protected semantic + field addition | §4.23, §7.17, §11.3.1 | ATS-COORD-001, ATS-COORD-002 (new) | `stable_coordinates` (optional), `decision_id`, `acceptance_criterion_id`, `dependency_target` (optional) |
| D-D Local semantic closure | new invariant | §4.24, §7.18 | ATS-CLOSE-001 (new) | none |
| D-E Intentional redundancy | clarification | §11.3.3 | ATS-DISC-003 (rule_version bump, statement amended) | none |
| D-F Source basis | field addition + new invariant | §4.25, §7.5, §7.19 | ATS-BASIS-001, ATS-BASIS-002 (new) | `semantic_basis` (optional), `basis_policy` (optional) |

## Per-delta detail

### D-A — ATS mission

- **Previous behavior:** §2.1 stated ATS governs the recovery cost of meaning with a
  non-compensatory reader-cost vector. The standard's program role was not normative.
- **New behavior:** ATS is normatively declared a *controlled technical discourse standard
  for transferring operative models between reasoning systems while preserving human
  inspectability*. Semantic recovery cost is the principal concept; a sentence-level
  readability improvement MUST NOT justify material semantic loss.
- **Affected schemas:** none. **Affected rules:** none. **Affected fixtures:** none.
- **Migration requirement:** none (no artifact behavior changes; receipts unaffected).
- **Old artifacts under draft.1:** valid. **Checkable under draft.2 without rerendering:** yes.

### D-B — Relation preservation

- **Previous behavior:** P1 protected relations (§11.3.2) covered support/contradiction,
  qualification, dependency, condition/exception, causal direction, comparison,
  alternatives, update/reversal, inference provenance, ordering. "Remove words before
  removing relations" lived in Appendix A as a principle.
- **New behavior:** P1 list extends to authority, temporal ordering, and acceptance
  dependency. A normative transformation rule (ATS-PRES-003, `operational_class: block`)
  forbids removing, weakening, strengthening, reversing, or making materially implicit a
  protected relation solely to reduce surface length, complexity, or repetition. The
  Appendix A maxim is promoted to normative form in §11.3.2.
- **Affected schemas:** none. **Affected rules:** ATS-PRES-003 (new), D1 detector.
- **Migration requirement:** existing TRANSFORM preservation evidence is unaffected; new
  transformations must preserve the three added relation kinds.
- **Old artifacts under draft.1:** valid. **Checkable under draft.2:** yes.

### D-C — Stable semantic coordinates

- **Previous behavior:** `requirement_id` and `acceptance_criterion` were P0 fields;
  there was no coordinate class, no document-level declaration, no uniqueness/dangling
  obligation.
- **New behavior:** stable semantic coordinates are a distinct protected-exact class
  (eight kinds: `requirement_id`, `decision_id`, `acceptance_criterion_id`,
  `work_item_id`, `protocol_id`, `protocol_version`, `dependency_target`, authority
  reference). A coordinate MUST survive a transformation exactly even when its
  proposition is recoverable elsewhere. Document-level `stable_coordinates` MAY declare
  coordinates; when declared, uniqueness and reference resolution are required
  (ATS-COORD-001/002, `operational_class: block`).
- **Affected schemas:** `ats_common_v1.schema.json` (optional `decision_id`,
  `acceptance_criterion_id`, `dependency_target`), `ats_text_ir_v1.schema.json` (optional
  `stable_coordinates`). All additions optional.
- **Affected fixtures:** new COORD fixtures (4 per rule).
- **Migration requirement:** existing IRs carry no `stable_coordinates` block and remain
  valid; nothing must be back-filled. New artifacts SHOULD declare coordinates.
- **Old artifacts under draft.1:** valid. **Checkable under draft.2 without rerendering:**
  yes (optional fields).

### D-D — Local semantic closure

- **Previous behavior:** no closure concept.
- **New behavior:** a unit is locally closed when its operative meaning is recoverable
  from the unit plus explicitly declared dependencies. ATS-CLOSE-001
  (`operational_class: review_required`, SPECIFY-required) mechanically checks actor
  presence or declared inheritance, modality, action/object representation, and
  dependency/AC reference resolution for extractable units — explicitly not a claim of
  full semantic closure.
- **Affected schemas:** none. **Affected rules:** ATS-CLOSE-001 (new).
- **Migration requirement:** none; closure is a production-quality property, not a
  re-validation obligation on existing artifacts.
- **Old artifacts under draft.1:** valid. **Checkable under draft.2:** yes.

### D-E — Intentional semantic redundancy

- **Previous behavior:** §11.3.3 P2 permitted "deletion of functionless repetition";
  ATS-DISC-003 required restatements to add scope/evidence/mechanism/contrast/action/
  retrieval value.
- **New behavior:** locality-preserving redundancy is explicitly not functionless and
  MAY be retained (and is often preferred for shardable artifacts). ATS-DISC-003's
  statement is amended to distinguish zero-information repetition (defect) from
  locality-preserving redundancy (permitted). No blanket anti-repetition rule.
- **Affected rules:** ATS-DISC-003 (rule_version → `1.0.0-draft.2`, normative_statement
  amended; no detector change).
- **Migration requirement:** none; advisory-only rule wording change.
- **Old artifacts under draft.1:** valid. **Checkable under draft.2:** yes.

### D-F — Source semantic basis

- **Previous behavior:** claims carried provenance via `source_refs`; there was no
  per-value basis vocabulary and no prohibition on promoting inferred material.
- **New behavior:** five-value basis vocabulary (`EXPLICIT`, `DERIVED`, `INFERRED`,
  `UNAVAILABLE`, `AUTHOR_JUDGMENT`); material values SHOULD declare basis
  (ATS-BASIS-001, `review_required`); a transformation MUST NOT silently convert
  `INFERRED`/`UNAVAILABLE` material into explicit source-authoritative fact
  (ATS-BASIS-002, `block`), with the compiler's permitted alternatives enumerated
  (§7.19). The raw-prose authority-hierarchy failure is the canonical fixture.
- **Affected schemas:** `ats_common_v1.schema.json` (optional `semantic_basis` on claim,
  requirement_slots, relation), `ats_text_ir_v1.schema.json` (optional `basis_policy`).
- **Affected fixtures:** new BASIS fixtures (4 per rule).
- **Migration requirement:** existing IRs have no basis declarations; absence is a typed
  silence (never read as `EXPLICIT`). Nothing back-filled.
- **Old artifacts under draft.1:** valid. **Checkable under draft.2 without rerendering:**
  yes.

## Operational-class corrections (no normative delta)

- **ATS-TERM-003** carries `operational_class: block` in draft.2 (D0/D1
  conformance evidence, required-state in every profile, mechanically
  decidable). The severity-minor → advisory mechanical mapping would have
  mislabeled it as style; the validator now asserts an advisory-class rule
  never carries a required default state, so any future reclassification is a
  decision, not an accident.

## Receipts and version identity

- Draft.1 receipts bind `spec_version: 1.0.0-draft.1` and remain valid as draft.1
  conformance evidence. They MUST NOT be reinterpreted as draft.2 conformance.
- Draft.2 receipts bind `spec_version: 1.0.0-draft.2` (receipt builders already stamp
  `ctx.spec_version`; draft.2 contexts emit draft.2 receipts).
- **Two defaults (F0 amendment, ADR-0020).** Legacy interpretation — corpus reads, the
  annotation bench, unlabeled historical material — resolves draft.1
  (`DEFAULT_SPEC_VERSION`). New durable authoring resolves the edition the binding
  policy pins: the fleet policy pins draft.2 (`AUTHORING_SPEC_VERSION`), so a command
  run under it resolves draft.2 without an explicit `--spec-version`. An old artifact
  never acquires draft.2 semantics merely because the fleet advanced; an explicit
  `--spec-version` always wins.
- Implementation version moves independently to `0.5.0` (pyproject).

## Package observations (draft.1 → draft.2 disposition)

Each existing package observation is classified using the disposition vocabulary
`adopt_now | defer | superseded_by_pivot | implementation_only | needs_more_evidence`.
This classification is recorded in `docs/PACKAGE_OBSERVATIONS.md` alongside the
observations; ATS-NUM-002 and other boundary-defective or uncertain rules remain
advisory/REVIEW_REQUIRED in draft.2 and are not promoted.

## Compatibility summary

| Question | Answer |
|---|---|
| Are old artifacts valid under draft.1? | Yes — draft.1 is byte-immutable, manifest-verified. |
| Can old artifacts be checked under draft.2 without rerendering? | Yes — all new fields optional; draft.1-valid IR validates under draft.2 schemas (tested). |
| Are draft.1 receipts valid under draft.2? | As draft.1 evidence only; never silently re-read as draft.2. |
| Is migration of historical corpus required? | No — fleet rollout is prospective (§29). |
| Do new rules apply to old artifacts? | Only on explicit draft.2 re-checking; absence of coordinates/basis is a typed silence, not a violation. |

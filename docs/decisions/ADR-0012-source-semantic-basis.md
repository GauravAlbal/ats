# ADR-0012: Source semantic basis is a five-value typed provenance field

**Status:** Accepted
**Date:** 2026-08-07

## Context

An internal reconstruction control motivated this decision, but its source records
and results are omitted from the public distribution and are not public evidence.
The public design rationale is architectural: when semantic typing is implicit,
downstream models must reconstruct the type system and can make plausible but
unauthorized semantic decisions.

Draft.1 had no field recording *where a semantic value came from*. The IR
could say a claim had deontic force `MUST` or authority precedence, but not
whether the source declared it, the author derived it, a reader inferred it,
or it was unavailable. Without that provenance, a renderer or downstream model
cannot distinguish "the source says this" from "a competent reader would guess
this". ATS therefore requires the authoring surface to preserve that distinction
instead of reconstructing it after the fact.

## Decision

Draft.2 adds a **source semantic basis** as a typed, enum-enforced field
(delta D-F, spec §4.25 and §7.5):

- The vocabulary is exactly five values: `EXPLICIT` (the authoritative
  source or explicit author intent directly states the value), `DERIVED`
  (the value follows mechanically from explicit structure without
  substantive interpretive judgment), `INFERRED` (a competent reader/model
  can reasonably infer it but the source does not establish it uniquely or
  normatively), `UNAVAILABLE` (it cannot be established from the available
  source or author intent), and `AUTHOR_JUDGMENT` (the ATS authoring process
  intentionally introduces a new judgment under the authority granted for
  new authoring). The enum is enforced by schema, never restated in Python
  (ADR-0003).
- The basis attaches where semantics attach: `ats_common_v1.schema.json`
  gains an optional `semantic_basis` (`{basis, rationale}`) on `claim`,
  `requirement_slots`, and `relation`, plus `decision_id` and
  `dependency_target` as optional identifiers. `ats_text_ir_v1.schema.json`
  gains a document-level `basis_policy` (`{default_basis, declared}`) and a
  stable coordinates block. All new fields are optional so draft.1 IRs still
  validate under draft.2 schemas without rerendering; package compatibility is
  governed by ADR-0020.
- **Absence is a typed silence, not an omission.** Under
  `basis_policy.declared: true`, every material claim must carry a basis —
  the new structural check `IR-BASIS-SCHEMA` fails otherwise. Under an
  undeclared policy, a missing basis means "not declared", which is a legal
  and mechanically distinguishable state, not a gap the renderer may fill.
  ATS-BASIS-001 (major, `review_required`) flags material claims without a
  declared basis; per ADR-0002 it can never PASS by absence — a clean run
  yields `REVIEW_REQUIRED`, not silent approval.
- ATS-BASIS-002 (critical, `block`) is the narrow semantic-strengthening
  prohibition: a transformation MUST NOT silently convert `INFERRED` or
  `UNAVAILABLE` source material into an explicit source-authoritative
  semantic fact. Material axes: authority, authority precedence, deontic
  force, acceptance/settlement state, likelihood, confidence, quantifier,
  polarity, causal force, normative dependency, exception removal, and
  source attribution. The compiler may preserve the value as `INFERRED`,
  represent it as unresolved, omit it when nonessential, propose a
  candidate interpretation, or ask for adjudication when action requires
  resolution — it may not pretend the source declared it.
- Where `AUTHOR_JUDGMENT` is used, the authoring authority must be explicit and
  authorized for the new artifact. Extracting source truth is distinct from
  introducing a new judgment, and the field keeps them distinguishable.

## Consequences

- The invented-authority failure becomes a detectable, blocking class: a
  renderer that turns `UNAVAILABLE` precedence into a stated hierarchy trips
  ATS-BASIS-002 deterministically (`src/ats/rules/deterministic/basis.py`).
- Rendering gets honest vocabulary: where no document authority hierarchy
  exists, `authority_precedence = UNAVAILABLE` renders as "No cross-document
  precedence is established by the supplied sources" instead of a fabricated
  hierarchy.
- Migration cost is low by construction: draft.1 IRs validate under draft.2
  unchanged; basis is recorded prospectively where material (the IR-authoring
  skill, `skills/ats-ir-author/SKILL.md`, instructs this) and never
  back-filled by guessing.
- Receipts carry the IR hash and `spec_version`, so a reader can tell which
  basis policy a verdict was computed under.
- Cost: `UNAVAILABLE` values stay unresolved in output. That is correct —
  typed insufficiency over invented completion.

## Alternatives considered

**Free-text provenance strings.** Rejected. Without an enum there is no
mechanical check and no stable vocabulary for detectors or renderers to
consume; two documents would declare the same fact in two spellings.

**A two-value basis (explicit / implicit).** Rejected. It cannot separate
`DERIVED` from `INFERRED` — the difference between mechanical consequence
and interpretive judgment is the difference between checkable and
uncheckable — and it conflates `AUTHOR_JUDGMENT` with `EXPLICIT`, which is
precisely the conflation that lets invented authority masquerade as source
truth.

**Require basis on every claim unconditionally.** Rejected. It would break
draft.1 IR validation and turn authoring into an annotation project. The
`basis_policy.declared` gate makes strictness a policy choice, not a schema tax.

**No field; rely on style guidance.** Rejected. That leaves semantic typing
implicit. The whole point is to move semantic typing from reconstruction-time
inference to authoring-time declaration.

## References

- ATS-1 draft.2 §4.25 (semantic basis), §7.5 (claim fields), §7.19 (basis
  mechanics), and §31 compatibility; rules ATS-BASIS-001, ATS-BASIS-002
  (registry §12.7.5)
- Draft.2 package `schemas/ats_common_v1.schema.json`,
  `schemas/ats_text_ir_v1.schema.json`; `src/ats/ir/checks.py`
  (`IR-BASIS-SCHEMA`); `src/ats/rules/deterministic/basis.py`;
  `fixtures/ir/{conforming,violation}/ats-basis-*-*.json`
- ADR-0002 (never pass by absence), ADR-0003 (schemas namespaced, no
  restatement), ADR-0001 (immutable package)

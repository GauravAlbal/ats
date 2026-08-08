# ADR-0020: Draft.1 and draft.2 coexist; the default stays draft.1

**Status:** Accepted
**Date:** 2026-08-07

## Context

Draft.2 exists because the fleet needs six narrow deltas (mission, relation
preservation, stable coordinates, local closure, intentional redundancy, source
basis) that draft.1 cannot express. Draft.1 is an immutable, receipted import
(ADR-0001). Internal corpus, bench, review, and comparative material about
draft.1 is omitted from the public distribution and is not public evidence; no
private result is carried into this versioning decision.

The failure mode is silent reinterpretation. If the default spec version flipped
to draft.2, every existing receipt and historical artifact would suddenly be read
under a standard it was never checked against. ADR-0001's immutable-package law
and ADR-0020's compatibility contract forbid reinterpreting draft.1 receipts as
draft.2 conformance.
If, instead, the two packages drifted apart without a migration discipline, a
draft.2 artifact would be claimed conformant to a spec it does not match.
Coexistence must therefore be explicit, versioned, and receipted.

## Decision

Draft.1 and draft.2 coexist as two immutable, receipted packages (ADR-0001
and `spec/ATS-1/*/MANIFEST.json`):

- **Two defaults, not one (F0 amendment).** A single global default served
two incompatible obligations — legacy interpretation and new authoring — and
flipping it would have made old artifacts acquire draft.2 semantics whenever
the fleet advanced. The policy is now explicit:
  - *Legacy / historical interpretation default* = `1.0.0-draft.1`
    (`DEFAULT_SPEC_VERSION`): unlabeled historical material resolves here.
  - *New durable authoring default* = `1.0.0-draft.2`
    (`AUTHORING_SPEC_VERSION`): a command run under a policy document
    resolves the edition the policy pins — the fleet policy pins draft.2,
    so new authoring gets draft.2 without an explicit
    `--spec-version 1.0.0-draft.2`. `declared_policy_spec_version` reads
    the edition from a policy snapshot (`spec_version`) or the fleet policy
    document (`text_policy.version`) before a Context exists; an explicit
    `--spec-version` always wins.
- **Draft.1 is never edited.** Its package directory stays byte-identical
  with its manifest intact (ADR-0001). Draft.2 is a new immutable package
  with its own manifest, schemas, registry, lexicon, examples, validator,
  changelog, and migration notes; once its manifest is sealed the directory
  is treated as immutable.
- **Draft.2 schemas are supersets.** All new fields — `semantic_basis`,
  `decision_id`, `dependency_target`, `stable_coordinates`,
  `basis_policy`, and the rest — are optional, so draft.1 IR documents
  validate under draft.2 schemas without rerendering.
- **Receipts keep identity.** Receipts bind `spec_version` at creation and
  the field is stamped on every new surface; a receipt is never rewritten,
  re-stamped, or re-interpreted. A draft.1 receipt is evidence about
  draft.1 forever; draft.2 conformance requires a draft.2 check.
- **Capability declaration resolution** is package-relative: draft.2
  carries `capability/ats_rule_capability_v1.json` inside its package,
  resolved before the repo-root fallback, so the draft.1 default keeps the
  repo-root file and the two never shadow each other.
- **The migration table is the contract between them.**
  `docs/ATS_1_DRAFT_2_MIGRATION.md` enumerates every delta (D-A…D-F plus
  the operational surfaces D-G/D-H/D-I) and classifies each change as
  clarification, new invariant, field addition, rule boundary change, new
  protected semantic, or behavior-changing migration, with previous and
  new behavior, affected schemas/rules/fixtures/receipts, migration
  requirement, whether old artifacts remain valid under draft.1, and
  whether they can be checked under draft.2 without rerendering. The
  package validator cross-checks that every `D-<X>` amendment marker exists
  in the draft.2 spec text.
- Implementation version bumps to `0.5.0` independently of the standard
  version; the milestone is `v0.5.0-fleet`.

## Consequences

- Historical internal evaluation material is omitted from the public distribution
  and is not public evidence; its version binding is not silently changed.
- New fleet artifacts pin draft.2 through policy (ADR-0017); the upgrade
  is per-artifact and explicit, never a repo-wide flip.
- A reader of any receipt can tell which standard produced it, and a
  draft.1 receipt can never be presented as draft.2 conformance — the
  "never reinterpret" rule is enforced by the field, not by convention.
- Migration is cheap for old artifacts: because the new fields are
  optional, draft.1 IRs check under draft.2 unchanged, and authors add
  basis/coordinates prospectively (ADR-0012, ADR-0013).
- Cost: two packages to maintain the boundary of, and every new surface
  must stamp `spec_version`. That is the price of keeping draft.1's
  evidence honest while shipping draft.2's semantics.

## Alternatives considered

**Replace draft.1 with draft.2 in place.** Rejected. It would violate the
immutability receipt (ADR-0001), change the meaning of every existing draft.1
artifact and historical receipt, and make their provenance unanchored.
ADR-0001 preserves draft.1 as an immutable import.

**Flip the default to draft.2.** Rejected. It would silently re-read all
un-versioned invocations and old receipts under a new standard — exactly
the reinterpretation §31 forbids. The F0 amendment replaces the single
default with two: legacy interpretation stays draft.1, while the
policy-pinned authoring path resolves draft.2 automatically.

**Maintain one merged spec with draft.2 amendments folded in.** Rejected.
Draft.1 is an imported immutable package; merging would create a fork that
is neither draft.1 nor draft.2 and that no receipt could name (ADR-0001).

**Migrate draft.1 receipts to draft.2 by re-checking.** Rejected. A
re-check under a new standard produces new evidence; stamping it onto the
old receipt would destroy the receipt's identity and the distinction
between "checked under draft.1" and "checked under draft.2".

## References

- ATS-1 draft.2 §30 (versioning) and §31 (compatibility and migration
  classification); ADR-0001 (immutable package)
- `src/ats/spec_package.py` (`DEFAULT_SPEC_VERSION` for legacy/corpus
  interpretation, `AUTHORING_SPEC_VERSION` for policy-pinned authoring,
  `Context.load`, `declared_policy_spec_version`),
  `spec/ATS-1/1.0.0-draft.2/MANIFEST.json`,
  `spec/ATS-1/1.0.0-draft.2/capability/ats_rule_capability_v1.json`,
  `capability/ats_rule_capability_v1.json` (repo-root fallback),
  `docs/ATS_1_DRAFT_2_MIGRATION.md`
- ADR-0001 (immutable, receipted package), ADR-0017 (fleet policy pins
  draft.2), ADR-0012, ADR-0013

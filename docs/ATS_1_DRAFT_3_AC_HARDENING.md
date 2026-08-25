# ATS-1 draft.3 — Behavioral Acceptance-Criterion Hardening

**Status:** PROPOSED NORMATIVE DELTA  
**Baseline:** ATS-1 `1.0.0-draft.2`  
**Prospective edition:** ATS-1 `1.0.0-draft.3`  
**Delta:** D-G — behavioral acceptance criteria  
**Profiles affected:** `SPECIFY`; `TRANSFORM` when preserving a `SPECIFY` artifact  
**Schema impact:** none  
**New structured fields:** none

## 1. Decision

Draft.3 SHOULD make one narrow semantic correction to `SPECIFY`:

> **An acceptance criterion is the canonical falsifiable behavioral proposition for its requirement, not a test invocation or other evidence instrument.**

The existing `REQ` / `acceptance_criterion` structure is retained. No evidence-planning ontology, failure-mechanism field, test mapping, assurance provider, or additional authoring artifact is added to ATS-1.

The category error to prevent is:

```text
REQ
→ test name
→ green
```

The required relationship is:

```text
REQ
→ canonical falsifiable proposition
→ evidence used to adjudicate that proposition
```

Evidence may be a test, property, live probe, proof, receipt, review, or another admissible instrument. The instrument is subordinate to the criterion and MUST NOT silently define it.

---

## 2. Normative changes

### 2.1 Requirement-object definition

In §9.3.2, replace:

```text
acceptance_criterion — observable evidence that determines satisfaction
```

with:

```text
acceptance_criterion — the canonical falsifiable behavioral proposition by which
satisfaction or violation of this requirement can be determined
```

No schema change is required. The existing `acceptance_criterion` field remains canonical.

### 2.2 Replace §9.3.9 — Acceptance criteria

The section SHOULD read:

> #### 9.3.9 Acceptance criteria
>
> Every `MUST` and `MUST NOT` requirement MUST have exactly one canonical acceptance criterion, stated inline or uniquely referenced.
>
> An acceptance criterion MUST express an observable, falsifiable proposition about the behavior, state, invariant, boundary, or result governed by its requirement.
>
> A test name, command, provider invocation, fixture, tool result, exit status, receipt identifier, or other evidence instrument MUST NOT by itself serve as an acceptance criterion.
>
> A canonical acceptance criterion MUST map to exactly one normative requirement. Multiple requirements MAY rely on the same evidence instrument, but MUST NOT share one canonical acceptance criterion.
>
> **Load-bearing rule:** if a materially broken implementation that violates the requirement could plausibly satisfy the acceptance criterion as written, the acceptance criterion is nonconforming. The criterion MUST be strengthened or the requirement MUST be decomposed.
>
> **Scope-fidelity rule:** an acceptance criterion MUST NOT add an independently meaningful obligation, broaden the governed scope, or strengthen the deontic force of its requirement. If the desired acceptance proposition requires additional normative behavior, that behavior MUST be specified as a separate requirement or as an explicitly indivisible part of the existing requirement.
>
> Evidence instruments, providers, fixtures, environments, and instrument-specific execution configuration MAY be referenced separately when useful. A threshold or boundary that defines normative satisfaction remains part of the requirement or its acceptance criterion. Evidence details MUST NOT redefine the canonical acceptance criterion unless the requirement itself normatively constrains them.

“Materially broken” is scoped to the behavior, invariant, authority boundary, or product property governed by the requirement. The rule does not require enumeration of every hypothetical defect.

### 2.3 Amend §9.3.10 — Verifiability

Replace the first paragraph with:

> A requirement is verifiable when an authorized reviewer can determine whether its canonical acceptance criterion is established or refuted without inventing missing behavior, thresholds, actors, conditions, or boundaries.

Retain the existing profile-failure rule for material `MUST` / `MUST NOT` requirements lacking a verifiable acceptance criterion.

### 2.4 Keep §9.3.20 profile completeness structural

Draft.3 MUST retain the existing structural profile-completeness condition:

```text
each MUST and MUST NOT has a verifiable acceptance criterion
```

Load-bearingness and scope fidelity remain normative under §9.3.9 / `ATS-REQ-004`, but MUST NOT be smuggled into `profile: PASS`. `profile` answers whether required semantic slots are present; semantic adjudication remains a separate conformance dimension. This preserves ATS-1's non-compensatory conformance vector and avoids granting a structural profile validator authority it does not possess.

---

## 3. New rule: `ATS-REQ-004`

Draft.3 SHOULD add exactly one rule:

```yaml
schema_version: ats.rule.v1
rule_id: ATS-REQ-004
operational_class: review_required
rule_version: 1.0.0-draft.3
title: Canonical behavioral acceptance criterion
category: requirements
normative_statement: >-
  Every material MUST or MUST NOT requirement MUST map to exactly one canonical,
  falsifiable behavioral acceptance criterion. A canonical acceptance criterion
  MUST NOT be shared across normative requirements, MUST NOT consist solely of an
  evidence instrument or its result, and MUST NOT add an independently meaningful
  obligation or strengthen the requirement it adjudicates. If a materially broken
  implementation can plausibly satisfy the criterion while violating its requirement,
  the criterion MUST be strengthened or the requirement decomposed.
rationale: >-
  Test-shaped or scope-widening acceptance criteria can respectively pass while the
  protected behavior remains broken or create hidden requirements. Keeping the
  normative falsification proposition distinct from its evidence instrument preserves
  requirement meaning across implementations, test suites, and verification providers.
default_states:
  ASSESS: disabled
  SPECIFY: advisory
  TRANSFORM: advisory
severity: critical
detector_classes:
  - D1
  - D3
required_inputs:
  - text
  - profile
  - requirement_ir
protected_impact:
  - P0
  - P1
autofix: review_required
waivable: true
exceptions: []
```

The rule is deliberately **advisory at the automated rule layer in draft.3**. The semantic requirement remains normative in §9.3, but the current implementation has no complete D3 decision procedure for the load-bearing question. ATS-1's never-PASS-by-absence law would otherwise turn a SPECIFY-required `ATS-REQ-004` into `REVIEW_REQUIRED` or `UNAVAILABLE` on ordinary authoring and thereby create a new mandatory semantic-review/model pass.

`D1` MAY detect structural pathologies such as absent, duplicated, shared-by-reference, or obviously test-shaped criteria. It MUST NOT establish the load-bearing semantic judgment merely because no structural pathology was found. The load-bearing judgment belongs to `D3` or an authorized semantic review.

A policy MAY strengthen `ATS-REQ-004` to `required` only when the active toolchain provides a qualified decision/review path at the required cadence. Draft.3 MUST NOT introduce a new mandatory model call or lint phase solely for this rule.

---

## 4. Canonical examples

### 4.1 Conforming

```text
Requirement ID: REQ-POLICY-017

Statement
When the executor presents an acceptance receipt whose policy_sha256 differs
from the current resolved policy snapshot, the verifier MUST reject the receipt
before the acceptance transition.

Acceptance criterion
Given an acceptance receipt whose policy_sha256 differs from the current
resolved policy snapshot, the verifier returns refused_stale_policy and emits
no accepted-change transition.
```

The criterion describes exactly the governed behavior. A fixture or test that demonstrates it is evidence for the criterion, not the criterion itself.

### 4.2 Nonconforming: evidence substituted for criterion

```text
Acceptance criterion
TestStalePolicyRejection passes.
```

The text names an evidence instrument rather than the behavioral proposition being adjudicated.

### 4.3 Nonconforming: non-load-bearing criterion

```text
Requirement
VX MUST be the only authority that determines next-ready work.

Acceptance criterion
The executor returns success when given W1.
```

An executor could still select or advance unauthorized work while satisfying the criterion.

### 4.4 Nonconforming: AC silently widens the REQ

```text
Requirement
The verifier MUST reject a receipt whose policy hash is stale.

Acceptance criterion
Given a stale receipt, the verifier rejects it and records both policy hashes
in an audit log retained for 30 days.
```

The audit-log and retention behavior are independently meaningful obligations absent from the requirement. They require their own REQ/AC pair unless the requirement is explicitly and justifiably indivisible.

---

## 5. Relationship to requirement atomicity

Draft.3 adds no new atomicity mechanism. It sharpens §9.3.3 / `ATS-REQ-002`.

If one requirement needs multiple independently meaningful falsification propositions, that is evidence that the requirement contains multiple obligations. The ordinary remedy is decomposition, not preserving cosmetic 1:1 structure by joining several independent criteria into one paragraph.

```text
one coherent normative obligation
↔
one canonical falsification proposition
```

---

## 6. Evidence boundary

This delta deliberately does **not** standardize evidence planning.

ATS-1 may preserve evidence references supplied by a source artifact, but core `SPECIFY` does not choose testing frameworks, mutation tools, live probes, proof systems, provider implementations, or assurance portfolios.

```text
REQ      = what must be true
AC       = what observable proposition determines whether it is true
Evidence = how an authorized verifier finds out
```

A passing evidence instrument is not definitionally equivalent to establishment of the acceptance criterion.

---

## 7. Migration and compatibility

Draft.2 remains sealed and byte-immutable. Existing draft.1 and draft.2 artifacts and receipts retain their original semantics.

For prospective draft.3 authoring:

1. existing `REQ` and `acceptance_criterion` fields are reused;
2. no historical field backfill is required;
3. no schema migration is required;
4. already behavioral, load-bearing, scope-faithful acceptance criteria require no rewrite;
5. test-shaped, non-load-bearing, or scope-widening acceptance criteria must be rewritten when an artifact is explicitly authored or revalidated under draft.3.

When rewriting an acceptance criterion:

- if the new wording only makes the already-intended behavioral proposition explicit, the change MAY be classified as a compatible clarification;
- if the new wording changes which implementations satisfy the requirement, the change MUST be recorded as a changed acceptance criterion under existing requirement-identity and supersession law.

No draft.2 receipt acquires draft.3 conformance merely because draft.3 exists.

---

## 8. Explicit non-goals

D-G MUST NOT require in ATS core:

- `failure_mechanism` on every requirement;
- `most_consequential_falsifier` fields;
- `why_load_bearing` prose;
- required evidence-provider or test identifiers;
- evidence qualification or assurance-planning state;
- mutation testing;
- generated adversarial witnesses;
- another mandatory semantic-review pass;
- a repo-wide rewrite of historical ATS artifacts.

Those may exist downstream. They are not necessary to correct the `REQ` / AC boundary.

---

## 9. Promotion criterion

D-G is ready for a sealed draft.3 package when the package change demonstrates, at minimum:

1. one conforming behavioral-AC fixture;
2. one test-shaped negative fixture;
3. one non-load-bearing negative fixture;
4. one scope-widening negative fixture;
5. `ATS-REQ-004` is consistent across normative prose and the rule registry;
6. draft.1 and draft.2 packages remain byte-identical;
7. no new schema field or mandatory lint/model pass has been introduced.

Until a sealed `1.0.0-draft.3` package is imported and selected by policy, this document is a prospective normative delta and MUST NOT be cited as draft.3 conformance authority.

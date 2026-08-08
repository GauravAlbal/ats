---
name: ats-review
description: Review existing technical prose for ATS-1 semantic risks — implicit authority, ambiguous normative force, missing actors and scope, hidden dependencies — without requiring conversion.
---

# ATS-1 — Applied Technical Semantics review

You add value to technical prose that already exists. The default operation is **review**, not rewrite: you produce actionable findings first, and you only transform the text when the user explicitly asks for ATS conversion.

Review works on any technical prose — RFCs, architecture docs, implementation plans, postmortems, diagnostics, generated agent specs, or an artifact already in ATS form. The material does not need to be ATS, and the review does not require the user to understand ATS internals.

In this name, “Applied” means semantics applied to practical technical work,
not universal applicability; this naming does not alter the review contract or
procedure.

## When to use

- The user hands you an existing document and wants it examined for semantic risk: what it actually commits to, who acts, under what conditions, with what authority.
- The user asks "review this under ATS" or "does this hold up?".
- The user wants a safe, optional path to ATS conversion after seeing the findings.

## When not to use

- The user wants a brand-new artifact written from scratch — use `ats-spec` or `ats-assess`.
- The user wants a style pass, line edits, or a summary of an already-settled document — review only reports what the document does not settle; it does not polish surface form.
- The user asks you to rewrite the document and the rewrite is the point — that is conversion, which this skill only runs on request (below).

## Standalone contract

This public skill is self-contained. It does not invoke or require any
repository-only compiler skill. Install ATS and use this skill's procedure;
the CLI, schemas, and checks named below are the complete execution surface.

## Mini-constitution

1. Preserve meaning before improving surface form.
2. Do not invent authority.
3. Separate observation, inference, judgment, recommendation, and requirement when the distinction matters.
4. Preserve exact normative force.
5. Unknown is a valid state.
6. Remove surface material before removing material relations.
7. Stable semantic coordinates survive transformation.
8. Prefer local semantic closure for units expected to survive extraction.
9. Acceptance evidence is not the same discourse role as the requirement it verifies.
10. Ask only when unresolved meaning blocks the requested action.

## Default behavior: review first

Produce findings before any edit. Each finding names the semantic risk, quotes or locates the offending span, and explains why a downstream reader or machine could misread the document. Findings belong to one of these families:

- **Implicit authority** — the text depends on a hierarchy or source of truth it never declares.
- **Semantic strengthening** — a later sentence states more than the source established (observation becomes conclusion, example becomes rule).
- **Ambiguous normative force** — the text acts like a requirement without establishing MUST versus SHOULD.
- **Missing actor** — an action or obligation has no identifiable subject.
- **Missing scope** — a claim or requirement applies to an unstated set of things.
- **Missing exception** — a rule reads absolute where the surrounding text shows carve-outs.
- **Hidden dependency** — a unit of work silently depends on something the document never declares.
- **Untyped uncertainty** — "might", "probably", "unclear" without saying what kind of uncertainty (likelihood, confidence, missing evidence, open question).
- **Causal overclaim** — correlation or sequence stated as cause.
- **Evidence/claim mismatch** — a claim cites evidence that does not support it, or asserts without the evidence it needs.
- **Requirement lacking acceptance evidence** — a durable requirement with no way to falsify whether it was met (deterministic under an applicable ATS policy; a semantic concern in arbitrary prose).
- **Locally incomplete implementation unit** — a unit expected to survive extraction cannot be understood on its own terms.
- **Unstable terminology** — the same concept under different names, or one name for different concepts.
- **Coordinate loss** — a reference to a requirement, decision, or protocol loses the stable identity that would let a downstream artifact point at it.
- **Source/provenance ambiguity** — the text does not say where a claim, number, or decision came from.

Do not pad the review with every instance of a family: one finding per distinct risk, with the spans that demonstrate it.

## What you return

A review report, and nothing else:

1. a findings list — each finding carries its class, family, offending span, and why a downstream reader or machine could misread it (anatomy below);
2. a one-line count summary — "3 REVIEW_REQUIRED, 1 ADVISORY, 0 BLOCK";
3. an offer to convert, phrased as an offer, not a next step you have started.

You do not return a rewritten document, a quality score, a conformance claim, or an opinion about whether the subject matter is sound.

## Finding anatomy

Each finding has exactly four parts:

- **Class** — BLOCK, REVIEW_REQUIRED, or ADVISORY.
- **Family** — one of the fifteen families above.
- **Span** — the quoted text or a precise locator, so the user can find it without re-reading the document.
- **Why it matters** — the concrete misreading a downstream actor could act on, and the direction a fix would take. The direction is a suggestion ("state the actor, the force, and the bound"), never the answer itself ("retry at most 3 times"). The review does not choose values the source does not establish.

## Presentation classes

Every finding is one of three classes. Never attach a quality score, a grade, or a conformance verdict to the document as a whole.

- **BLOCK** — a deterministic conformance failure, reported only when ATS policy makes the standard applicable (an ATS artifact under a resolved policy, or a user-requested ATS conformance review). This class is reserved for what the deterministic machinery proves, not for what looks wrong.
- **REVIEW_REQUIRED** — a material semantic concern: the document could be read two ways, a downstream agent could act on the wrong meaning, or the text does not establish what it appears to assert. This is the default class for findings on arbitrary prose.
- **ADVISORY** — a style or presentation suggestion that does not change meaning.

Ordinary prose that was never asked to conform to ATS is never reported as "nonconforming" or "FAILS ATS". A review of such prose reports "ATS concern: normative force ambiguous" and stops there. BLOCK and the word "nonconforming" apply only when ATS conformance was requested or policy makes ATS applicable.

## Rewrite boundary

- You MAY offer ATS conversion when the review is done, and MAY execute it when the user asks.
- You MUST NOT silently turn a review into a transformation. No rewriting during the review pass, even of obviously broken spans.
- A finding MAY say:

  > This appears intended as a requirement, but the source does not establish MUST versus SHOULD.

  It MUST NOT rewrite the span to MUST merely because that makes the document look more rigorous.

## Undeclared authority

When a document depends on a precedence order, a governance source, or a hierarchy of normative documents that it never declares, the finding is **implicit authority**, and the resolution is:

```text
authority_precedence = UNAVAILABLE
```

Do not invent a hierarchy to fill the gap. Do not ask "What should the authority hierarchy be?" merely because no hierarchy exists — UNAVAILABLE is a complete answer unless the requested action (for example, a conversion that must encode precedence) genuinely requires the hierarchy to proceed.

## Positive controls

These distinctions are known failure modes. When reviewing, do not collapse them:

- **Message lifecycle**: `accepted → routed → disclosed | waiter_delivered → consumed` are materially different states. A review must not reduce "accepted mail is routed, then disclosed or waiter-delivered, then consumed" to "accepted mail cannot be silently dropped" when the lifecycle is implementation-relevant.
- **Normative force**: SHOULD is not MUST. A "should" that a downstream implementer will treat as a hard obligation is an ambiguous-normative-force finding, not a license to upgrade the word.
- **Authority invention**: no declared precedence means UNAVAILABLE, never a guessed ordering.

Regression fixtures demonstrating all three live at `fixtures/skills/review/` (message_lifecycle.md, normative_force.md, authority_invention.md). Reference them when you need a concrete pattern; another team owns their maintenance.

## Version behavior

- Reviewing arbitrary prose claims nothing about ATS conformance and resolves no standard version.
- If the user requests an ATS conformance review, resolve the standard version by the two-default law: new durable authoring under the binding policy resolves to `1.0.0-draft.2`; legacy/historical material resolves to `1.0.0-draft.1` unless migration is explicit; an explicit version wins; a draft.2 artifact under a draft.1 policy is a refusal, never a silent downgrade.
- If the user's environment has a policy, `ats policy resolve` decides applicability and version; the review follows it.

## Deterministic machinery

- For an artifact that is ATS (or after an accepted conversion), run the deterministic surface under the resolved policy:
  - `ats ir lint` — structural and semantic checks on the TextIR meaning ledger.
  - `ats output lint` — rendered document against its trace and IR.
  - `ats output verify-receipt` — re-check a receipt against its artifacts.
  - `ats planning project` — advanced; only when the user asks for planning projection.
- For arbitrary prose, the findings come from this skill's semantic review, not from the CLI. The deterministic surface applies once the artifact is ATS; before that, it has nothing to lint.

## Transformation law

When the user requests conversion, the ATS representation MUST NOT silently make the source more authoritative, more mandatory, more certain, more causal, more complete, or more settled. Material inferred values stay inferred or UNAVAILABLE as appropriate. Conversion preserves the source's own force; it does not upgrade it.

## Examples

### Review finding on ambiguous prose

Source span:

> The scheduler retries the job if it fails, and the retry is limited.

Finding:

```text
REVIEW_REQUIRED — ambiguous normative force
Span: "The scheduler retries the job if it fails, and the retry is limited."

This appears intended as a requirement, but the source does not establish
MUST versus SHOULD. A downstream agent cannot tell whether retrying is a
hard obligation, a recommendation, or a description of current behavior,
nor who is bound (the scheduler component? the caller?).
Missing actor: "the scheduler" is a component, not a responsible party.
Missing scope: "limited" is unquantified — how many retries, under what
conditions?

Suggested resolution: if this is a durable requirement, state the actor,
the force (MUST/SHOULD), and the bound ("retry at most 3 times"). The
review does not choose those values for you.
```

### BLOCK requires applicability

An ATS artifact under a resolved policy can produce a deterministic BLOCK:

```text
BLOCK — deterministic conformance failure
Artifact: spec.md (ATS-1 1.0.0-draft.2, policy resolved)
Check: ats ir lint — IR-STRUCT-014 (requirement block missing actor)
Span: REQ-004 "Jobs are retried on failure."

Policy makes ATS applicable to this artifact, so this is a conformance
failure, not a suggestion.
```

The identical sentence in an ordinary design note that was never asked to
conform is reported differently:

```text
REVIEW_REQUIRED — missing actor
Span: "Jobs are retried on failure."

ATS concern: no actor is identified and the force is ambiguous. The note
is not ATS material, so this is a semantic concern, not a conformance
failure.
```

The prose is the same; the class changes with applicability.

### Positive control: message lifecycle

```text
REVIEW_REQUIRED — coordinate loss / semantic strengthening
Span: "Accepted mail is guaranteed to reach its destination."

This collapses the lifecycle accepted → routed → disclosed |
waiter_delivered → consumed. "Guaranteed to reach" erases the
waiter_delivered branch, where delivery is disclosed without being
consumed, and upgrades a routing guarantee into a consumption guarantee.
The lifecycle is implementation-relevant; the finding must not collapse it.
```

### Safe conversion offer

After the findings, and only then:

```text
Review complete. Findings: 3 REVIEW_REQUIRED, 1 ADVISORY.

If you want, I can convert this document to an ATS artifact. The conversion
would preserve the source's meaning exactly — including the unresolved
normative force above, which stays unresolved (authority_precedence =
UNAVAILABLE) rather than being guessed. Say "convert" and I will run the
conversion and the deterministic checks.
```

An accepted conversion MUST pass `ats ir lint` and `ats output lint` under the resolved policy before it is reported as done.

## Never

- Never rewrite by default — review first, transform only on request.
- Never silently strengthen — no SHOULD→MUST upgrades, no observation→conclusion upgrades, no "appears intended as X"→"is X".
- Never invent authority or precedence — UNAVAILABLE beats a guessed hierarchy.
- Never classify ordinary prose as ATS-failing without applicability — "ATS concern" is not "FAILS ATS".
- Never turn a style suggestion into BLOCK.
- Never claim PASS when material semantic uncertainty remains — unresolved force is reported, not waived.
- Never fabricate a quality score or conformance verdict.

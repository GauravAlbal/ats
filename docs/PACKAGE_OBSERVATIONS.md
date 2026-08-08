# Package observations — ATS-1 1.0.0-draft.1

This document records implementation-facing observations about the immutable ATS-1
`draft.1` package. It is informative, not an amendment: the imported package is
upstream truth, and this repository does not edit it or silently resolve its
ambiguities. Normative changes belong in the separately authored `draft.2`
package and its migration record.

The public distribution contains no private corpus, census, pilot, or adjudication
evidence. Historical internal empirical material is omitted and is not public
evidence. The bounded public evidence for implementation behavior is the committed
normative package, repository-local schemas, synthetic fixtures, and reproducible
checks. None of those artifacts establishes a general performance, acceptance, or
promotion result.

Each observation below states the boundary that remains useful to maintainers and
the conservative implementation choice: claim less authority, never more.

## Observation index

| ID | Boundary | Current public disposition |
|---|---|---|
| A | Detector-class declarations can leave a decidable sub-obligation implicit. | The implementation caps authority at the registry and reports only what the declared detector can establish. |
| B | Ordering obligations may need an explicit ordering input distinct from block structure. | Draft.2 defines the required distinction; callers must provide the input needed by the selected rule. |
| C | A requirement rule may name `syntax` while consuming structured requirement slots. | The implementation does not infer a missing syntax surface or claim conformance from absence. |
| D | Package examples and their source bindings must be self-consistent. | Packaging and manifest checks refuse unresolved or mismatched example bindings. |
| E | A capability declaration needs to represent a rule with no implemented detector. | The declaration uses an explicit empty detector class and the weakest allowed authority where a normative shape requires an entry. |
| F | A recognizer that ran without establishing conformance is not a pass. | The implementation reports `UNAVAILABLE` or a typed review outcome rather than `PASS` by absence. |
| G | A semantic-review result needs a recorded finding budget and ranking policy. | The policy and receipt surfaces carry those declarations; the implementation does not invent a ranking decision. |
| H | Appendix questions can remain ratification questions when the package does not settle their scope. | The implementation preserves the broad, least-claiming interpretation and leaves unresolved scope visible. |

The IDs are retained because decision records use them as stable references. Their
presence is not a claim that a private empirical gate was satisfied, and no ID is a
promotion or acceptance receipt.

## A. Detector authority is capped by the registry

A detector declaration cannot grant itself authority. The registry and the
normative package determine the maximum class a detector may report. When a
structural check can establish a bounded fact, that fact is kept separate from a
semantic proposal; lower-authority output is routed for review rather than treated
as conformance evidence. See ADR-0008 and `docs/AUTHORITY_MODEL.md`.

## B. Ordering and structure are distinct inputs

An implementation may need both the order of material objects and the structure of
blocks. Supplying one as a substitute for the other is safe only when the selected
rule explicitly permits it and the resulting basis is recorded. Draft.2 makes this
boundary explicit; no private corpus result is needed to define the interface.

## C. Structured requirements are not silently reparsed

When a rule names a syntax input but its normative obligation is expressed over
structured requirement slots, the implementation does not manufacture a parse or
upgrade a partial check into conformance evidence. Missing or mismatched inputs
remain visible as unavailable or review-required outcomes.

## D. Example bindings are packaging integrity

An example that names a source or hash the package does not ship is a packaging
problem, not a reason to reinterpret ATS semantics. Manifest and package checks keep
source bindings explicit and refuse unresolved references. This observation does
not rely on external or private source material.

## E. Capability declarations represent absence explicitly

A rule with no implemented detector must remain distinguishable from a detector that
ran and found nothing. The implementation therefore emits an empty detector-class
list in its repository-local declaration and uses only the weakest permitted
normative authority representation where the imported shape requires an entry. It
never invents an authority-basis receipt.

## F. No finding is not a semantic pass

A detector that cannot establish conformance reports an unavailable or review state.
The implementation maps that boundary consistently instead of treating the absence
of a surfaced finding as proof. This is the same conservative rule expressed by
ADR-0002 and the normative ATS-1 lifecycle.

## G. Ranking and budgets are claim inputs

A semantic-review claim must identify its finding budget and ranking policy. These
are policy inputs and receipt fields, not values an implementation may infer after
the fact. The public implementation records them when supplied and remains
unavailable when the required basis is absent.

## H. Unsettled scope remains visible

Appendix questions that depend on a policy threshold or an unstated profile remain
questions for the standard's governance process. The implementation chooses the
least-claiming behavior, records the unresolved boundary, and does not turn a
repository-local choice into normative ATS-1 text.

## Relationship to the two editions

`draft.1` remains immutable and is interpreted through its own package and receipt.
New durable authoring uses `draft.2` under the migration rules in
[`ATS_1_DRAFT_2_MIGRATION.md`](ATS_1_DRAFT_2_MIGRATION.md). This document does not
change either package, and it must not be read as a report of private pilot state or
as evidence that any detector has been promoted.

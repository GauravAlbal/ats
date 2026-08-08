# ADR-0007: Finding identity is `artifact:rule:issue_code:ordinal`, derived not generated

**Status:** Accepted
**Date:** 2026-08-02

## Context

§13.1 requires every `TextFindingV1` to carry a finding identifier. Downstream, that
identifier is what an adjudication points at (§13.7), what a waiver is scoped to (§13.8), what
a receipt lists in `finding_refs`, and what `ats ir explain-finding` resolves.

§16.2 requires deterministic components to produce identical results for identical canonical
inputs. §16.12 requires a receipt-verification command to re-run deterministic rules and
identify semantic evidence that cannot be reproduced.

A UUID satisfies §13.1 and destroys both of the others. Re-linting an unchanged artifact under
an unchanged policy would produce a byte-different report, so the sealed report's own
`report_sha256` would change, `IR-CANONICAL`'s replay guarantee would be meaningless, and an
adjudication recorded yesterday would point at an identifier that no longer exists. A
timestamp-based identifier fails the same way and additionally reads a clock during evaluation.

A content hash over the finding is tempting and has a subtler defect: two genuinely distinct
instances of the same issue with identical spans and identical summaries would collide into
one identifier, and §13.9 permits deduplication only under stated conditions, requiring a
deduplicated finding to retain all affected spans. Silent collision is not deduplication.

## Decision

Identity is a pure function of the run's own content, assembled in
`ats.ir.model.IrEvaluation.finding_id`:

```python
def finding_id(self, rule_id: str, issue_code: str) -> str:
    key = f"{rule_id}:{issue_code}"
    ordinal = self._counters.get(key, 0)
    self._counters[key] = ordinal + 1
    return f"{self.ir.artifact_id}:{rule_id}:{issue_code}:{ordinal:03d}"
```

Four segments:

| Segment | Source | Why |
|---|---|---|
| `artifact_id` | the IR document | Scopes the identifier to one artifact; §13.1 requires the finding to carry the artifact identifier anyway. |
| `rule_id` | the rule registry | Immutable per §12.1, and never reused for a materially different rule (§18.1). |
| `issue_code` | the detector's subcheck | Distinguishes *which* obligation of the rule was missed, which is what a reader needs to understand the finding. |
| `ordinal` | a per-`(rule_id, issue_code)` counter, zero-padded to three digits | Distinguishes repeated instances without hashing away the distinction. |

`_counters` lives on the `IrEvaluation`, which is constructed once per lint run, so the
counter starts at zero for every run and is a function of that run alone. The docstring
records the constraint directly: identity is a function of the artifact, rule, issue code, and
the ordinal of this issue within the run, "never of a clock or a UUID."

The ordinal is deterministic because everything upstream of it is. Detectors run in
`ctx.registry.ids()` order, which is sorted; within a detector, findings are appended while
walking the IR's `sections` and their ordered claim lists (§7.3); and the IR itself is a
validated document whose ordering is fixed by its canonical bytes. Same inputs, same sequence,
same ordinals.

The same discipline holds for the objects that contain findings. Report identifiers are
derived, not generated: `f"irlint:{ir.artifact_id}:{ir.ir_sha256[:16]}"`,
`f"outlint:{ir.artifact_id}:{binding.content_sha256[:16]}"`, and
`f"candidate:{ir.artifact_id}:{ir.ir_sha256[:16]}"` for a candidate receipt.

## Consequences

- **Re-linting an unchanged artifact reproduces the report exactly**, including its
  `report_sha256`. That is what makes `IR-CANONICAL` and §16.12 receipt replay meaningful
  rather than decorative.
- **An adjudication stays attached.** A finding accepted yesterday has the same identifier
  today, so §13.7's record and §13.8's scoped waiver do not dangle.
- **Adding a claim renumbers later findings of the same issue.** If a new claim is inserted
  before an existing violation, the existing violation's ordinal shifts. This is a real cost.
  It is bounded by the segmentation — only findings sharing the same `(artifact, rule,
  issue_code)` triple are affected — and it is the correct behaviour anyway, because §15.8
  makes a conformance claim stale when the source bytes change, so every finding on the
  modified artifact must be re-evaluated regardless. An identifier that survived the edit
  would create the illusion that a disposition carried over when it should not.
- **The identifier is human-readable**, which matters for `ats ir explain-finding` and for a
  reviewer reading a diff of two reports.
- **Nothing in the finding path reads a clock.** The only timestamp in a report comes from
  `ctx.timestamp()`, which formats the `now` passed into `Context.load(...)`. The CLI exposes
  `--now` explicitly: "RFC 3339 evaluation time; pin it for reproducible receipts."

## Alternatives considered

**UUID4.** Rejected. Breaks replay, breaks receipt stability, breaks adjudication linkage.

**Timestamp plus counter.** Rejected for the same reasons, and it reads a clock inside
evaluation, which the determinism contract forbids.

**SHA-256 over the finding's canonical content.** Rejected. Two distinct instances of the same
issue at the same location with the same summary would collide, and §13.9 requires a
deduplicated finding to retain all affected spans — a collision retains one. It is also opaque:
`a3f9c2…` tells a reviewer nothing that the four-segment form does not tell them immediately.

**Include a span locator instead of an ordinal, e.g. the JSON Pointer.** Considered. It would
be stable under insertion elsewhere in the document, which is the ordinal's weakness. Rejected
because a finding may legitimately carry several spans (§13.3, §13.9) and the identifier would
have to pick one, making identity depend on span ordering — trading a visible renumbering for
a hidden one. Pointers also change under any structural edit, so the stability gain is
narrower than it looks.

**Global monotonic counter across all rules.** Rejected. It makes every finding's identity
depend on every other detector's output, so adding an unrelated detector renumbers everything.

## References

- ATS-1 §13.1 (finding object), §13.3 (evidence spans), §13.7 (adjudication object), §13.8
  (waivers), §13.9 (deduplication), §12.1 (rule identity is immutable), §15.8 (conformance
  claim freshness), §16.2 (determinism), §16.12 (reproducible receipts), §18.1 (a retired
  identifier MUST NOT be reused)
- Constitution #5 (typed references, not inline copies), #18 (crash-reconstructible state —
  identity must survive a re-run)
- `src/ats/ir/model.py::IrEvaluation.finding_id`, `src/ats/ir/lint.py::_build_report`,
  `src/ats/output/receipt.py::build_candidate_receipt`, `src/ats/cli.py` (`--now`)

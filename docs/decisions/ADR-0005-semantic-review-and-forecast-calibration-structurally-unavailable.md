# ADR-0005: `semantic_review` and `forecast_calibration` are structurally unavailable in v0

**Status:** Accepted
**Date:** 2026-08-02

## Context

§5.2 makes conformance a five-dimension vector: `mechanical`, `profile`, `semantic_review`,
`preservation`, `forecast_calibration`. Every report must carry all five, and §15.6 forbids
averaging failed dimensions into a passing score.

Two of the five are not merely unimplemented. They are unreachable by anything this
repository could build without becoming a different kind of system.

`semantic_review: PASS` requires, per §15.3, that every surfaced advisory or required finding
was **dispositioned**, and that every required semantic predicate was evaluated by an
authorized human, an authoritative structured source, or a detector operating as validated
`conformance_evidence`. Disposition is an act of authority. §14.11 assigns final authority for
semantic acceptance to an authorized human or an explicitly governed external acceptance
system. A linter is neither.

`forecast_calibration: PASS` requires, per §15.5, a declared forecast cohort, resolved
outcomes, a scoring rule, reliability or calibration analysis, uncertainty estimates, no
outcome leakage, and a minimum evidence threshold defined *before* evaluation. That is an
empirical programme over resolved forecasts across time, not a property of one artifact.

The pressure here is real: a report where three of five dimensions read `PASS` and two read
something else looks broken, and the cheapest way to make it look clean is to report `PASS`
for a dimension nothing contradicted.

## Decision

Both dimensions are computed as constants, in code, with a rationale string that states why.

**`semantic_review` is always `UNAVAILABLE`.** In `ats.ir.lint.compute_conformance` the
variable is assigned the literal `"UNAVAILABLE"`, and the rationale counts the results
awaiting disposition and cites §15.3 and §14.11:

> "N rule result(s) require disposition and this implementation holds no disposition
> authority. Section 15.3 requires every surfaced finding to be dispositioned by an authorized
> human, an authoritative structured source, or a detector validated as conformance_evidence,
> and Section 14.11 assigns final semantic acceptance to an external authority.
> semantic_review is therefore never PASS in this implementation."

`ats.output.lint._compute_conformance` reaches the same constant by a second route, adding the
output-specific reason: mapping a block to an IR object establishes that the renderer declared
the object, not that the prose realizes it.

**`forecast_calibration` is always `INSUFFICIENT_EVIDENCE`.** The rationale reports the
observed forecast count and how many carry `outcome_status` in
`{resolved_true, resolved_false}`, then lists the §15.5 requirements that are not implemented.
Reporting the counts matters: it quantifies the gap instead of asserting it, and it means the
same rationale would read differently on an artifact with a hundred resolved forecasts.

**`preservation` follows the same shape for a different reason** — §6.4 makes `ATS-PRES-001`
and `ATS-PRES-002` unwaivable, so it is `NOT_APPLICABLE` when no TRANSFORM profile is active
and `UNAVAILABLE` when one is. There is no third branch.

**The declaration says so.** Two entries in `ats.capability.KNOWN_LIMITATIONS` state both
constants in the machine-readable capability document, so a consumer learns it without reading
a report.

**The exit code excludes them.** `cli.RUN_DEPENDENT_DIMENSIONS = ("mechanical", "profile",
"preservation")`. `UNAVAILABLE` in one of those three exits 4; `semantic_review` and
`forecast_calibration` are excluded because this build can never move them, and letting them
force a non-zero exit on every run would train operators to ignore the exit code. They remain
fully visible in the reported vector — §15.6 permits a compact status line, not a truncated
vector.

## Consequences

- **No clean run ever reports five `PASS`es.** The best achievable vector is
  `mechanical: PASS`, `profile: PASS`, `semantic_review: UNAVAILABLE`,
  `preservation: NOT_APPLICABLE`, `forecast_calibration: INSUFFICIENT_EVIDENCE` — which is
  exactly what the ASSESS conforming fixture produces.
- **§5.3's example is honest about this.** The spec's own sample conformance claim shows
  `Forecast calibration: INSUFFICIENT_EVIDENCE` beside three passes, so the shape is expected
  rather than anomalous.
- **A receipt claiming otherwise is caught.** `verify_receipt` adds an `unreplayable` entry —
  and returns `UNAVAILABLE` rather than `PASS` — when a receipt records
  `semantic_review: PASS` or `preservation: PASS`, because this implementation cannot reproduce
  a semantic disposition or a source-to-output comparison. §16.12 allows such a result to
  remain valid as historical evidence but requires the receipt to state that replay is
  unavailable.
- **Adding a D3 critic would not change `semantic_review`.** §16.5 caps D3 at `proposal_only`
  regardless of rule state, so a critic would add proposals, not dispositions. Only §18
  promotion plus an external acceptance authority moves this dimension.
- **The path forward is legible.** Wire in an external adjudication record and
  `OUT-FINDING-DISPOSITIONS` starts checking real dispositions instead of reporting
  `UNAVAILABLE` for want of a receipt. The constant is the *linter's* position, not a ceiling
  on the pipeline.

## Alternatives considered

**Report `PASS` when no semantic finding was surfaced.** Rejected — this is the exact failure
§16.5 names ("no surfaced finding does not prove the rule passed") and the milestone's non-goal
("a linter that reports semantic `PASS` from the absence of keyword matches"). It is ADR-0002's
error moved from the rule level to the dimension level.

**Report `NOT_APPLICABLE`.** Rejected. §15.4 shows what `NOT_APPLICABLE` means: the dimension
does not apply to this subject, as preservation does not apply to a non-transformed artifact.
Semantic review *does* apply to every artifact with a surfaced finding; the reviewer is
missing, not the obligation. `UNAVAILABLE` is §5.4's word for a required check that could not
execute.

**Omit the two dimensions from the vector.** Rejected. §5.2 defines the canonical dimensions
and §15.6 requires retaining the full vector. An omitted dimension also reads as "fine" to a
scanner.

**Make it configurable — a flag to assume semantic review passed in CI.** Rejected. §14.12
forbids substituting a weaker component while preserving the same conformance claim unless the
policy snapshot explicitly authorizes the fallback and records its identity. A CLI flag is not
a policy snapshot, and a flag that turns an honest `UNAVAILABLE` into a `PASS` is a
self-issued override — precisely the hole constitution #27 names.

**Report `forecast_calibration: NOT_APPLICABLE` for artifacts with no forecasts.** Tempting and
still rejected. It would be defensible for a document containing zero forecast claims, but it
creates a status that flips based on document content in a way a reader would misread as
calibration having been assessed. §15.5's own instruction is to report `INSUFFICIENT_EVIDENCE`
when the data do not support the claimed granularity, and zero data is the strongest case of
that. The rationale carries the forecast count, so the distinction is visible without being
encoded in the status.

## References

- ATS-1 §5.2 (conformance is a vector), §5.3 (no bare conformance claim), §5.4 (`UNAVAILABLE`,
  not `PASS`), §6.4 (unwaivable claims), §15.3 (semantic-review conformance), §15.4
  (preservation conformance), §15.5 (forecast-calibration conformance), §15.6 (no aggregation),
  §16.5 (semantic model authority), §16.12 (reproducible receipts), §20.6 (honest
  insufficiency)
- Constitution #16 (low confidence shrinks prescription; abstention is a feature), #10
  (non-compensatory gating — a required gate that silently passes when it cannot be evaluated
  is the named violation pattern), #27 (no self-issued override)
- `src/ats/ir/lint.py::compute_conformance`, `src/ats/output/lint.py::_compute_conformance`,
  `src/ats/output/receipt.py::verify_receipt`, `src/ats/capability.py::KNOWN_LIMITATIONS`,
  `src/ats/cli.py::RUN_DEPENDENT_DIMENSIONS`

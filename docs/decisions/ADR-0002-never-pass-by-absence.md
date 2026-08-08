# ADR-0002: Never PASS by absence, enforced by `decide()` and a declared `DecisionPower`

**Status:** Accepted
**Date:** 2026-08-02

## Context

The default shape of a linter is: run some checks, collect problems, report success if the
list is empty. That shape is correct only when the checks are a *complete decision procedure*
for the thing being reported. For most ATS-1 rules they are not.

`ATS-TERM-003` recognises an unexpanded acronym in the canonical `Expansion (ACR)` form. It
does not recognise an expansion carried in prose three paragraphs earlier. `ATS-REQ-002`
recognises a coordinating connective in a requirement's action slot. It does not recognise
two obligations expressed across separate sentences. In both cases "no finding" means *this
particular recogniser saw nothing*, which is not the same proposition as *the rule holds*.

The standard is unusually explicit that conflating them is a defect. §5.4: a required check
that cannot execute is `UNAVAILABLE`, not `PASS`. §16.5: "no surfaced finding does not prove
the rule passed," and `PASS` for a required semantic rule "requires human adjudication,
authoritative structured intent, a formally verified predicate, or a detector promoted to
`conformance_evidence` under Section 18." The milestone's non-goals name the failure mode
directly: *a linter that reports semantic `PASS` from the absence of keyword matches.*

The engineering question is not whether to obey this. It is where to put the obedience so it
survives the tenth detector written by someone who has not read this document.

## Decision

**Status is derived, never supplied.** Each detector declares a `DecisionPower` in its
`DetectorSpec`; `ats.rules.results.decide()` computes the `Status` from it.

```python
class DecisionPower(StrEnum):
    DECIDES = "decides"                       # complete procedure over the inputs supplied
    DETECTS_VIOLATIONS = "detects_violations" # recognises a defined subset
    UNDECIDABLE = "undecidable"               # cannot decide at all
```

The derivation, in order, in `decide()`:

| Condition | Status |
|---|---|
| `effective_state == "disabled"` | `NOT_APPLICABLE` |
| any `missing_inputs` | `UNAVAILABLE` |
| `decision_power is UNDECIDABLE` | `UNAVAILABLE` |
| findings, `authority == conformance_evidence` | `FAIL` |
| findings, lower authority | `REVIEW_REQUIRED` (findings attached) |
| no findings, `DECIDES`, `conformance_evidence` | `PASS` |
| no findings, `DECIDES`, lower authority | `REVIEW_REQUIRED` |
| no findings, `DETECTS_VIOLATIONS` | `REVIEW_REQUIRED` |

Three structural properties make this a mechanism rather than a convention:

1. **`RuleResult.status` is not a parameter of `decide()`.** There is no argument through
   which a detector can pass `Status.PASS`.
2. **A detector body cannot construct a result at all.** Its type is
   `Callable[[IrEvaluation, Detector], tuple[list[Finding], list[dict]]]` — findings and
   subcheck records. `run_detector` applies the policy state, the blocking-input rules, and
   `decide()`. `RuleResult` is not reachable from a body.
3. **The declaration is cross-checked.** `capability.py::coherence_errors()` rejects a
   `decides` declaration whose authority is not `conformance_evidence`, because such a
   detector can never report `PASS` and declaring `decides` would overstate it.

The same discipline applies one level down. `_support.subcheck()` maps an
inspected-but-clean subcheck with `decides: false` to `REVIEW_REQUIRED`, not `PASS`, so a
rule's per-subcheck record is honest even where the rule's overall result is coarser.

And one level up. `ats.ir.lint._unimplemented` handles a rule with no registered detector by
building an `UNDECIDABLE` result with every `required_input` listed as missing — *"no
detector is registered for this rule in this build."* There is no path where a rule silently
does not appear in the report.

## Consequences

- **A conforming artifact does not produce an all-`PASS` report.** On
  `fixtures/ir/valid/assess_conforming.json` with `fixtures/policies/assess.json` and its
  source file: 9 rules `PASS`, 0 `FAIL`, 11 `REVIEW_REQUIRED`, 5 `UNAVAILABLE`, 5
  `NOT_APPLICABLE`. This surprises people and
  it is correct. §20.6: `UNAVAILABLE` and `INSUFFICIENT_EVIDENCE` are valid outcomes.
- **`REVIEW_REQUIRED` on a required rule blocks its dimension.** `RuleResult.blocks_conformance`
  treats it alongside `FAIL` and `UNAVAILABLE`, because an undispositioned surfaced obligation
  is not a pass (§15.3).
- **A new detector cannot regress the property by forgetting it.** The only way to get `PASS`
  is to declare `DECIDES` *and* have a class whose ceiling is `conformance_evidence` — and
  both are checked, at runtime by `Context.detector()` and against the registry by
  `coherence_errors()`.
- **`REVIEW_REQUIRED` is not a normative status.** It is implementation-level, and
  `to_conformance_status()` maps it to `UNAVAILABLE` at the single boundary where the two
  vocabularies meet. See [`../PACKAGE_OBSERVATIONS.md`](../PACKAGE_OBSERVATIONS.md) F.
- **Reviewer load is real.** Twelve rules declare `detects_violations`, so a clean artifact
  still routes twelve results to review. Reducing that number requires *promoting* a detector
  to a complete procedure — the work §18 describes — not relabelling it.

## Alternatives considered

**A code-review convention: "detectors should not return PASS when they only recognise
violations."** Rejected. It is invisible at the point of failure, and the failure is silent —
a wrong `PASS` looks exactly like a right one. Constitution #23's thinking-trace signature
applies: the shortcut is available precisely when someone is in a hurry.

**Let each detector return its own `Status`, with a test asserting the honest ones don't
return `PASS`.** Rejected. That is a test of every current detector, not of the property. The
eleventh detector is written after the test.

**Compute decision power from the code — e.g. infer `decides` when the detector has no
`known_limits`.** Rejected. It makes the safety property depend on an author remembering to
document a limitation, which inverts the failure direction: forgetting to write prose would
*grant* authority.

**Report `PASS` with a confidence or coverage annotation.** Rejected outright. §5.2 forbids
reducing conformance to a scalar, and constitution #9/#10 forbid a compensatory score where a
high dimension offsets a low one. A `PASS` with a caveat is read as a `PASS`.

**Suppress `REVIEW_REQUIRED` for advisory rules to reduce noise.** Rejected. §6.2 makes
advisory findings surface and require disposition for semantic-review conformance; hiding
them would make `semantic_review` unauditable. The finding-budget mechanism (§12.6) is the
sanctioned way to manage reviewer load, and this build does not apply it — see
[`../ARCHITECTURE.md`](../ARCHITECTURE.md) and observation G.

## References

- ATS-1 §5.4 (required check failure semantics), §16.5 (semantic model authority), §12.3
  (rule state and detector authority are orthogonal), §15.3 (semantic-review conformance),
  §20.6 (honest insufficiency)
- Constitution #9 (mechanical evaluation, layered gating), #10 (non-compensatory gating),
  #16 (abstention is a feature), #23 (flag cuts, never hide them)
- `src/ats/rules/results.py::decide`, `src/ats/rules/deterministic/_support.py::run_detector`,
  `src/ats/capability.py::coherence_errors`

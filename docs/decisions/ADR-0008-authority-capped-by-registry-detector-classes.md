# ADR-0008: Detector authority is capped by the classes the registry declares for the rule

**Status:** Accepted
**Date:** 2026-08-02

## Context

Three rules — `ATS-EPI-006`, `ATS-EVID-002`, `ATS-EVID-003` — carry
`detector_classes: [D3, D4]` in `rules/ats_rules_v1.yaml`, and the §12.7 catalog lists their
detector as `D3`. Each nonetheless has a sub-obligation that a deterministic structural
procedure over the meaning ledger can decide:

- `ATS-EPI-006`: is *any* `update_indicator` targeting this material judgment, or does an
  `extraction_issues` entry state why none is available? (§7.14, §9.2.4)
- `ATS-EVID-002`: does a material relation of a discriminating type carry non-empty
  `basis_refs`, and do they resolve? (§8.13, §8.15)
- `ATS-EVID-003`: is this material judgment opposed by a `contradicts` / `alternative_to` /
  `contrasts_with` relation, or does it carry one of the exact `contrary_evidence` states
  §9.2.7 enumerates?

None of those requires reading prose semantics. Under §12.3's mechanism table they are D1
work — "syntax tree, document AST, glossary, and structural checks" — and D1 output MAY be
`conformance_evidence` after deterministic fixture and parser validation.

So the implementation is offered a shortcut: report D1, take `conformance_evidence`, and let
`ATS-EVID-003` report `PASS` on a conforming artifact instead of `REVIEW_REQUIRED`. The report
gets cleaner and a required rule stops blocking. The only cost is that the detector would be
claiming a class the rule's own registry record does not list.

§12.3 also says a detector "MUST report the highest class required for the finding," which
reads naturally as a floor on honesty, not a licence to pick a class the rule does not declare.
And §16.5 requires that "a capability declaration and receipt MUST bind the authority basis" —
so whatever class is claimed becomes a published, checkable assertion.

## Decision

**A detector's authority is derived from its declared class, and its class must be one the
registry lists for that rule.** `DetectorSpec.authority` is not a field an author sets:

```python
@property
def authority(self) -> str:
    from ...rules.registry import DETECTOR_CLASS_MAX_AUTHORITY
    if self.power is DecisionPower.UNDECIDABLE:
        return "none"
    return DETECTOR_CLASS_MAX_AUTHORITY[self.detector_class]
```

For these three rules the declared class is `D3`, whose ceiling is `proposal_only`. The
docstring on that property records why:

> "A rule whose registry record lists only D3 and D4 has no declared class describing a
> deterministic structural detector. Rather than claim a class the registry does not list,
> such a detector reports D3, and Section 12.3 caps D3 output at `proposal_only`. Its findings
> are then surfaced for adjudication instead of deciding the rule."

Three enforcement points make it non-optional:

1. **`CapabilityDeclaration.coherence_errors()`** rejects any declared `detector_class` that is
   not among the registry's `detector_classes` for the rule, and rejects
   `conformance_evidence` on a class whose ceiling forbids it. `load_capability` calls
   `require_coherent()`, so violation is a hard failure of `Context.load()`.
2. **`Context.detector()`** re-checks the ceiling when constructing the runtime identity and
   raises `UsageError` rather than emitting a `Detector` with unearned authority.
3. **`decide()`** routes findings from a `proposal_only` detector to `REVIEW_REQUIRED` rather
   than `FAIL`, and refuses `PASS` outright — so even a `decides` declaration could not produce
   one. `coherence_errors()` closes that loop too, rejecting `decides` on a non-
   `conformance_evidence` authority as an overstatement.

Consequently all three declare `decision_power: detects_violations`, and each carries a
`known_limits` entry naming this ADR.

## Consequences

- **A required rule reports `REVIEW_REQUIRED` on a conforming artifact.** On
  `fixtures/ir/valid/assess_conforming.json`, `ATS-EVID-003` is `required` and reports
  `REVIEW_REQUIRED`. The obligation is real, the check ran, and nothing here is entitled to
  close it. §16.5 describes exactly this state: "a required rule can therefore remain a
  normative artifact obligation while its learned detector lacks authority to decide
  conformance."
- **`mechanical` is unaffected.** It counts only required rules whose detector class is D0 or
  D1 *and* whose authority is `conformance_evidence`, so these three neither help nor block it.
  They land in `semantic_review`, which is `UNAVAILABLE` for independent reasons (ADR-0005).
- **The findings are still useful.** They are attached to the result and appear in the report's
  `findings` array with full spans and summaries. `proposal_only` means they cannot *decide*
  the rule, not that they are discarded — which is precisely §12.3's definition: "can create a
  finding for adjudication but cannot independently establish `PASS` or `FAIL`."
- **The declaration cannot silently gain authority.** Changing `detector_class` to `D1` for one
  of these rules fails `coherence_errors()` against the imported registry, so the change would
  have to be accompanied by a registry change — which means an upstream package version
  (ADR-0001).
- **We are recording a finding against the draft, not routing around it.**
  [`../PACKAGE_OBSERVATIONS.md`](../PACKAGE_OBSERVATIONS.md) observation A states the
  ambiguity — whether `detector_classes` is exhaustive or indicative — and names what would
  resolve it.

## Alternatives considered

**Report D1 anyway, on the grounds that §12.3's mechanism table describes what the detector
does.** This is the strongest alternative and it may well be the correct reading of the draft.
Rejected because the two readings are both available and they differ in *direction*: reporting
D1 buys a stronger claim, reporting D3 buys a weaker one. When an ambiguity in a standard has
a self-serving side, taking it is how an implementation quietly becomes non-conformant.
§16.5's requirement that the capability declaration bind the authority basis makes the choice
public either way, and the weaker claim is the one that cannot be wrong in a harmful direction.

**Report both classes, `[D1, D3]`, with per-class authority.** The normative
`ats_capability_v1` schema supports this — `authority_by_class` is a map. Rejected because
§12.3 says a detector "MUST report the highest class required for the finding," singular, and
a single finding from a single procedure has one class. A map would let the same finding be
read as D1 evidence by one consumer and D3 proposal by another.

**Split each rule into two detectors: a D1 structural one and a D3 semantic one.** Rejected for
the same reason as above — the D1 half would still be claiming a class the registry does not
list for the rule. If the registry gains `D1`, this becomes the natural implementation.

**Leave the three rules unimplemented (`undecidable`) rather than reporting proposal-only
findings.** Rejected. It would lose real, actionable findings — a material judgment with no
update indicator is worth surfacing — and §16.7 makes abstention appropriate when required
context is missing, which is not the case here. The context is present; only the authority is
absent.

**Add `D1` to the three rules in the imported registry.** Prohibited by ADR-0001. The package
is immutable; a defect is recorded, not patched.

## References

- ATS-1 §12.2 (rule record contents), §12.3 (detector classes; rule state and detector
  authority are orthogonal), §12.7.2 and §12.7.4 (the catalog entries for these three rules),
  §14.8 (D3 is proposal-only in core draft policy), §16.5 (semantic model authority; the
  declaration MUST bind the authority basis), §18 (promotion)
- Constitution #16 (abstention is a feature; do not widen a claim under low confidence),
  #10 (a required gate that silently passes when it cannot be evaluated is the named violation
  pattern), #27 (the worker does not certify its own standing)
- `src/ats/rules/registry.py::DETECTOR_CLASS_MAX_AUTHORITY`,
  `src/ats/rules/deterministic/_support.py::DetectorSpec.authority`,
  `src/ats/context.py::Context.detector`, `src/ats/capability.py::coherence_errors`,
  [`../PACKAGE_OBSERVATIONS.md`](../PACKAGE_OBSERVATIONS.md) observation A

# ADR-0009: The capability declaration is generated from the detector specs, not hand-maintained

**Status:** Accepted
**Date:** 2026-08-02

## Context

§5.5 requires an implementation that supports only part of ATS-1 to publish a machine-readable
capability declaration identifying supported profiles, supported rules, detector class per
rule, autofix capability, preservation capability, schema versions, and known limitations.
§16.1 adds detector class and declared authority per rule, plus an authority-basis receipt for
every detector that contributes conformance evidence. `ats_common_v1#/$defs/detector` enforces
the last one structurally: `authority_basis_ref` is required whenever `authority` is
`conformance_evidence`.

So the declaration is not documentation. It is the artifact a consumer reads to decide what a
report from this implementation means, and §14.12 makes it the thing that authorizes a
fallback at all.

A hand-maintained declaration is a second description of the code. The failure mode is not
hypothetical and it is silent in the dangerous direction: a detector is narrowed to fix a
false positive, its `decision_power` stays `decides` in the JSON, and the declaration now
claims a complete decision procedure the code no longer implements. Nothing crashes. Every
report still says `PASS`.

The same information is needed in three places that would otherwise drift apart:

1. what the detector may conclude at runtime (`DecisionPower`, class, authority);
2. what the published declaration says it may conclude;
3. what authority is stamped on each finding the detector emits.

## Decision

**One declaration drives all three.** Each detector is declared once as a `DetectorSpec` in
`src/ats/rules/deterministic/_support.py`, carrying `rule_id`, `detector_class`, `power`,
`subchecks` (each with `subcheck_id`, `decides`, `spec_ref`, `description`,
`vocabulary_source`), `unavailable_conditions`, `known_limits`, `substitutions`, and the body.
The module docstring states the intent: the same declaration drives three things that would
otherwise drift apart (constitution #5).

**`capability/ats_rule_capability_v1.json` is generated.** `tools/generate_capability.py`
imports the detector modules, reads `SPECS`, and emits one entry per rule in
`registry.ids()` order. Derived fields are computed, never typed:

```python
"implemented": spec.implemented,                                   # power is not UNDECIDABLE
"surfaces": ["ir"] if spec.implemented else [],
"decision_power": str(spec.power),
"produces_conformance_evidence": spec.authority == "conformance_evidence",
"authority": spec.authority,                                       # from the class ceiling
"required_inputs":  list(rule.required_inputs),                    # from the imported registry
"available_inputs": list(spec.available_inputs(required)),
"missing_inputs":   list(spec.missing_inputs(required)),
"blocking_inputs":  list(spec.blocking_inputs(required)),
```

`authority_basis_ref` is emitted only when the authority is `conformance_evidence`, pointing at
`docs/AUTHORITY_MODEL.md#ats-ir-rule` — the same anchor `Context.detector()` constructs at
runtime.

The generator refuses to run if the spec set and the registry disagree in either direction:
`no detector declared for: …` or `detector declared for unknown rule: …`. It validates its
output against `ats_rule_capability_v1.schema.json` before writing.

**Staleness is a test failure.** `--check` re-derives the document and compares it byte-for-byte
with the checked-in file, exiting non-zero with "re-run tools/generate_capability.py".
`tests/unit/test_capability.py` asserts the same equality.

**A generated-but-wrong document is also caught.** `CapabilityDeclaration.coherence_errors()`
cross-checks the loaded declaration against the *imported registry* — a source the generator
does not control — and `load_capability` raises on any problem, so `Context.load()` fails
rather than proceeding. The checks include: every registry rule is declared and no extra rule
is; `required_inputs` equals the registry's exactly; the declared class is among the registry's
classes; the class may carry the declared authority; conformance evidence implies an authority
basis ref; `decides` implies `conformance_evidence`; `missing_inputs` equals `required_inputs`
minus `available_inputs`; substitutions are declared only for genuinely missing inputs;
`blocking_inputs` equals `missing_inputs` minus substituted; an `implemented` rule has no
blocking inputs; an `undecidable` rule names at least one blocking input; and an unimplemented
rule declares no surfaces.

**The normative projection is also derived.** `CapabilityDeclaration.to_normative()` produces
an `ats.capability.v1` document from the same loaded object — two representations, one source,
per ADR-0003.

## Consequences

- **The declaration cannot lie about the code**, because it is a function of the code, and it
  cannot lie about the registry, because a source the generator does not own re-checks it.
- **Changing a detector's power is a two-file diff** — the spec and the regenerated JSON — and
  the diff is reviewable: `"decision_power": "decides"` → `"detects_violations"` is legible in
  a way a Python edit alone is not.
- **`known_limits` and `unavailable_conditions` live next to the code they describe**, so the
  prose a consumer reads was written by whoever wrote the detector, in the same edit.
- **A generated file is checked in.** That is deliberate: §5.5 requires the declaration to be
  *published*, and a consumer must be able to read it without running our build. The `--check`
  mode and the unit test are what keep the artifact and its source honest, which is the
  standard trade for any generated-and-committed file.
- **Cost: an import-time dependency.** The generator imports every detector module, so a
  detector that fails to import breaks capability generation. This is arguably a feature —
  the declaration cannot describe code that does not load.
- **The generator is not the gate.** Constitution #27's separation holds: the thing that
  produces the document (`generate_capability.py`) and the thing that accepts it
  (`coherence_errors()` against the imported registry) are different code with different
  inputs.

## Alternatives considered

**Hand-author the JSON.** Rejected. It is a second description of the code with no mechanism
keeping them equal, and the drift is silent in the direction that overstates authority.

**Generate at runtime and never check in a file.** Rejected. §5.5 requires a published
declaration; a consumer would have to install and run this package to learn what it does.
Runtime generation would also remove the `--check` diff, which is where a reviewer actually
sees an authority change.

**Derive the declaration from the code by introspection alone — no `DetectorSpec`.** Rejected.
`decision_power`, `vocabulary_source`, `unavailable_conditions`, and `known_limits` are
genuine authorial claims about coverage; they are not recoverable from a function body. Trying
to infer them would invert the failure direction, making a missing docstring grant authority.

**Skip the coherence checks and trust the generator.** Rejected. The generator reads
`DetectorSpec`s; the coherence checks read the imported registry. A detector that declared
`ATS-EPI-006` as `D1` would produce a perfectly self-consistent generated document — and fail
coherence against the registry, which is exactly the case ADR-0008 exists for. Constitution
#27: the producer does not certify itself.

**Emit only the normative `ats.capability.v1` and drop the richer local document.** Rejected.
The normative schema cannot express decision power, subchecks, vocabulary sources, input
substitutions, or blocking inputs, and it cannot even express "no detector for this rule" —
see [`../PACKAGE_OBSERVATIONS.md`](../PACKAGE_OBSERVATIONS.md) observation E. Dropping the
local document would delete most of what makes the declaration checkable.

## References

- ATS-1 §5.5 (partial implementations), §14.12 (no silent fallback), §16.1 (capability
  declaration contents, including the authority-basis receipt), §16.5 (the declaration and
  receipt MUST bind the authority basis), `ats_common_v1#/$defs/detector` (conditional
  requirement of `authority_basis_ref`)
- Constitution #5 (single source of truth with typed references), #21 (ought, not is — the
  declaration is derived from the contract-bearing spec object, not transcribed from observed
  behaviour), #27 (trust receipts, not self-reports — a separate check, on a separate input,
  accepts the generated artifact)
- `tools/generate_capability.py`, `src/ats/rules/deterministic/_support.py::DetectorSpec`,
  `src/ats/capability.py`, `capability/ats_rule_capability_v1.json`

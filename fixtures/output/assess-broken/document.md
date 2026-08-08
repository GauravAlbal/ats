# Acceptance-kernel language assessment

## Question

<!-- ats:block assess-question -->
Should Arq move the acceptance kernel from Python to Rust after the state model stabilizes?

## Key judgment

<!-- ats:block assess-key-judgment -->
A Rust migration is likely to reduce invalid-state defects in the acceptance kernel after the transition model is stable.

## Confidence

<!-- ats:block assess-confidence -->
moderate. The type-system argument is direct, but no controlled migration ablation exists.

## Supporting evidence

<!-- ats:block assess-evidence-1 -->
- Current acceptance failures cluster around illegal intermediate states and stale-policy transitions.
- Existing Rust components prevent construction of several invalid states that remain runtime checks in Python.

## Contrary evidence

<!-- ats:block assess-contrary -->
The Python implementation supports faster iteration and mature integration coverage as of revision 2026-08-03.

## Live alternatives

<!-- ats:block assess-alternative -->
Whether a smaller typed Python kernel or generated transition layer captures enough of the benefit at lower migration cost remains unresolved.

## Assumptions

<!-- ats:block assess-assumption -->
The transition model will remain substantially stable during the migration; if it does not, the port could encode uncertainty rather than remove it.

## Boundary

<!-- ats:block assess-boundary -->
The assessment also covers the policy-fluid orchestration plane.

## Update indicators

<!-- ats:block assess-update-indicator -->
Downgrade the assessment if the prototype doubles change lead time or requires frequent unsafe escape hatches.

## Recommendation

<!-- ats:block assess-recommendation -->
Prototype one closed transition family before authorizing a broad migration.

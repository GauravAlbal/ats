# Rust kernel assessment

<!-- ats:profile ASSESS -->

## ASSESS: acceptance-kernel language

A Rust migration is likely (55-80%) to reduce invalid-state defects in the
acceptance kernel after the transition model stabilizes. Confidence is moderate
because the evidence is mixed and partially indirect.

## Evidence

Current acceptance failures cluster around illegal intermediate states. It is
possible that a smaller typed Python kernel would close the same gap.

## Boundaries

The assessment does not apply to the policy-fluid orchestration plane.

## Update indicators

If two consecutive releases show no invalid-state defects, the judgment is
currently expected to weaken. This is clearly a significant change in the
evidence base.

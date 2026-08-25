# ATS-REQ-004 fixtures

## Conforming
REQ: The verifier MUST reject a stale-policy receipt before acceptance.
AC: Given a stale policy hash, the verifier returns `refused_stale_policy` and emits no accepted transition.

## Violation — evidence substituted for criterion
AC: `TestStalePolicyRejection` passes.

## Hard negative — non-load-bearing
REQ: Only VX MUST determine next-ready work.
AC: The executor returns success when given W1.

## Violation — scope widening / hidden obligation
REQ: The verifier MUST reject a stale-policy receipt.
AC: The verifier rejects the stale receipt and MUST also persist a seven-year audit record.

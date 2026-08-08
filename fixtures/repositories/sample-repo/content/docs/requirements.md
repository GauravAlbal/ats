# Acceptance policy requirements

<!-- ats:profile SPECIFY -->

## SPECIFY: stale-policy rejection

REQ-POLICY-017: When the executor presents an acceptance receipt whose
policy_sha256 differs from the current resolved policy snapshot, the verifier
MUST reject the receipt before the acceptance transition.

## SPECIFY: retention

The verifier SHOULD retain both policy hashes. An operator MAY export them.
The exporter SHALL NOT redact the source revision.

## Acceptance criteria

A stale-policy fixture returns refused_stale_policy and records both hashes.

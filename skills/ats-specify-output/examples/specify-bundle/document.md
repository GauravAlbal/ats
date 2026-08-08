# Stale-policy rejection

## Requirement REQ-POLICY-017

<!-- ats:block specify-req-policy-017 -->
REQ-POLICY-017: When the executor presents an acceptance receipt and the receipt policy_sha256 differs from the current resolved policy snapshot, the verifier MUST reject the acceptance receipt before the acceptance transition.

## Acceptance criterion

<!-- ats:block specify-acceptance-criterion -->
A stale-policy fixture returns refused_stale_policy, emits no accepted transition, and records both policy hashes.

## Source authority

<!-- ats:block specify-authority -->
The obligation is imposed by the Arq acceptance-policy kernel.

## Rationale (non-normative)

<!-- ats:block specify-rationale -->
A receipt proves conformance only under the policy used to evaluate it. This paragraph is rationale and creates no obligation.

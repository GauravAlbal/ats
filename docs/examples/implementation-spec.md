# Implementation specification example: request-signature rotation

> **Provenance:** Synthetic example authored for the public ATS documentation. It contains no copied source, private identity, local path, or repository-specific material. It is an ordinary implementation artifact, not a TextIR dump.
>
> **ATS edition:** New durable authoring uses ATS-1 `1.0.0-draft.2`; profile `SPECIFY` is shown in prose.

## Destination

Add support for two active request-signing keys so a key can be rotated without rejecting requests already in flight. The change covers key selection and verification in the HTTP gateway. It does not change the request payload format or define a remote key-management service.

## Stable requirements

- **`REQ-KEY-001` (MUST):** The gateway MUST accept a request signed by either configured active key during the rotation window.
- **`REQ-KEY-002` (MUST):** The gateway MUST choose the key by the request's declared key identifier; it MUST NOT try every configured key when the identifier is unknown.
- **`REQ-KEY-003` (MUST):** The gateway MUST reject an unknown key identifier with the existing authentication failure behavior.
- **`REQ-KEY-004` (MUST):** Configuration reload MUST validate that active key identifiers are distinct before replacing the in-memory key set.
- **`REQ-KEY-005` (MUST NOT):** The gateway MUST NOT log private key material or the complete request signature.

## Implementation units and shardability

Each unit below is locally closed: it names the requirement, dependency, changed behavior, and proof needed to understand the unit after extraction. One requirement is not automatically one implementation task.

### `WORK-KEY-01`: key-set model and validation

- **Owns:** `REQ-KEY-004`.
- **Depends on:** the existing configuration parser and the key identifier type.
- **Change:** represent zero, one, or two active key entries; reject duplicate identifiers before an atomic in-memory replacement.
- **Proof:** unit tests show duplicate identifiers leave the previous valid key set unchanged.
- **Not this unit:** request verification and logging behavior.

### `WORK-KEY-02`: key-directed verification

- **Owns:** `REQ-KEY-001`, `REQ-KEY-002`, `REQ-KEY-003`.
- **Depends on:** `WORK-KEY-01` and the existing verification primitive.
- **Change:** select exactly the declared key, accept either active key, and preserve the existing authentication failure response for unknown identifiers.
- **Proof:** integration tests cover old key, new key, unknown identifier, and bad signature cases.
- **Not this unit:** config file migration.

### `WORK-KEY-03`: secret-safe observability

- **Owns:** `REQ-KEY-005`.
- **Depends on:** the gateway's structured logging adapter.
- **Change:** record key identifier and outcome only; redact signature and key bytes before serialization.
- **Proof:** a log-capture test asserts that neither configured secret nor complete signature appears in emitted fields.
- **Not this unit:** changing log retention or access policy.

### `WORK-KEY-04`: rollout and operator instructions

- **Owns:** the ordered activation procedure for `REQ-KEY-001`.
- **Depends on:** `WORK-KEY-01`, `WORK-KEY-02`, and the deployment configuration mechanism.
- **Change:** add the new key, verify both keys are accepted, then remove the old key after the declared rotation window. The duration of that window is **UNAVAILABLE** until the operator supplies it.
- **Proof:** a staging run records acceptance with both keys and a separate run records rejection after old-key removal.
- **Not this unit:** inventing a rotation duration.

## Dependency graph

`WORK-KEY-01 → WORK-KEY-02 → WORK-KEY-04`; `WORK-KEY-03` may proceed after the logging adapter is identified and is otherwise independent. The rollout cannot be accepted while the rotation-window input is **UNAVAILABLE**.

## Acceptance contract

- **`AC-KEY-001`** verifies `REQ-KEY-001` and `REQ-KEY-002`: integration tests cover old key, new key, unknown identifier, and bad signature cases, and observe that verification uses only the declared active key.
- **`AC-KEY-002`** verifies `REQ-KEY-003`: an unknown key identifier preserves the existing authentication failure behavior.
- **`AC-KEY-003`** verifies `REQ-KEY-004`: duplicate identifiers leave the previous valid key set unchanged after a rejected reload.
- **`AC-KEY-004`** verifies `REQ-KEY-005`: a log-capture test shows that neither configured secret nor complete signature appears in emitted fields.

The implementation is accepted only when all four work units have their named proof, the existing single-key behavior remains green, and an operator has supplied the rotation-window value. A test passing is acceptance evidence for a criterion; it does not change the `MUST` force of the requirement it verifies.

## Non-goals and update indicators

**Non-goals:** changing payload canonicalization, adding a third active key, changing authentication status codes, or selecting keys by trial verification.

Revisit this specification if the gateway's signature scheme changes, if the deployment configuration cannot atomically reload, or if operational policy requires more than two simultaneously active keys. Those are update indicators, not hidden assumptions.

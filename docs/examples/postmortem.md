# Postmortem example: duplicate webhook deliveries

> **Provenance:** Synthetic postmortem authored for the public ATS documentation. The incident, measurements, and service names are fictional and redistribution-safe; no private identities, paths, repositories, or copied incident text are present. This is an `ASSESS` artifact, not a TextIR dump.
>
> **ATS edition:** New durable authoring uses ATS-1 `1.0.0-draft.2`.

## Incident and impact

For 27 minutes, a webhook sender delivered some event identities more than once. Three downstream consumers processed duplicate notifications. No event data was lost, and the sender was paused after detection. The exact number of duplicate side effects is **UNAVAILABLE** because one consumer did not expose an idempotency counter.

## Observed sequence

1. A deploy enabled a retry path for responses that timed out after the request body had been sent.
2. The sender timed out on a subset of requests and retried them.
3. The receiver had already committed those requests but had not returned a response before the timeout.
4. A dashboard showed a rise in timeout responses, but no alert connected that rise to duplicate event identities.
5. Pausing the sender stopped new duplicates; replaying the affected event range was intentionally not performed.

These are observations about order and system records. They do not, by themselves, establish why the receiver response was delayed.

## Evidence

- Request logs show the same event identity with a first attempt marked `timeout` and a second attempt marked `accepted`.
- Receiver audit records show one committed row for some identities and two committed rows for others.
- The retry change was present in the release diff and had no test for “commit before response timeout.”
- Receiver latency was elevated during the interval, but the source of the elevation is **UNAVAILABLE**.

## Causal and contributing factors

**Primary causal assessment (medium confidence):** the sender retried after an ambiguous timeout, while receiver-side handling did not enforce idempotency for every event identity. This explains the duplicate pattern and is supported by the paired request/audit records.

**Contributing factor (high confidence):** acceptance testing covered a timeout before receiver commit but not a timeout after receiver commit and before response delivery.

**Possible contributing factor (low confidence):** elevated receiver latency may have increased the ambiguous-timeout window. The evidence does not establish whether latency was caused by the deploy, a dependency, or load.

Do not summarize this incident as “the deploy caused all duplicates.” The deploy exposed a missing receiver invariant; the cause of the latency increase remains unresolved.

## Detection failure and recovery

The timeout alert fired, but it did not include event-identity duplication or a runbook step to pause retries. The sender was paused manually after audit logs were compared. Existing records were preserved, and no destructive replay was attempted.

## Corrective actions

- **`REQ-WEBHOOK-001` (MUST):** The receiver MUST enforce one committed processing result per event identity and return the stored result for a duplicate request.
- **`REQ-WEBHOOK-002` (MUST):** The sender MUST record retry attempts with event identity and reason, including ambiguous timeout.
- **`REQ-WEBHOOK-003` (MUST):** Acceptance tests MUST cover timeout before commit, after commit before response, and repeated delivery after restart.
- **`AC-WEBHOOK-001`** verifies `REQ-WEBHOOK-001` by submitting the same identity across those timing windows and observing one committed side effect.
- **`AC-WEBHOOK-002`** verifies `REQ-WEBHOOK-002` by inspecting a retry record without exposing payload secrets.
- **`AC-WEBHOOK-003`** verifies `REQ-WEBHOOK-003` with deterministic fault injection at each named boundary.

These are recommendations elevated to requirements for the corrective implementation; the original causal assessment remains an evidence-bearing judgment, not a requirement.

## Unresolved questions

The source of elevated receiver latency, the complete duplicate count, and whether any downstream consumer performed an irreversible side effect remain **UNAVAILABLE**. Close those questions with records from the affected consumers before publishing a quantitative impact claim.

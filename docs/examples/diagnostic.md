# Diagnostic example: delayed notification delivery

> **Provenance:** Synthetic diagnostic written for the public ATS documentation. All measurements and names are fictional; no private identity, path, repository, or copied incident record is used. This is an `ASSESS` artifact, not a TextIR dump.
>
> **ATS edition:** New durable authoring uses ATS-1 `1.0.0-draft.2`.

## Observed behavior

From 09:10 to 09:25 UTC, the notification dashboard showed a growing queue and a median delivery delay above 90 seconds. At 09:26 UTC, the queue returned to its normal range. The service emitted no alert during the first five minutes because the alert threshold is five consecutive minutes above the queue limit.

## Expected behavior

The queue should drain at the configured worker rate, and an operator should receive an alert while delivery delay is material. The expected alert latency is **UNAVAILABLE** in the supplied evidence because the alert policy does not state a target.

## Evidence

1. Queue depth rose from 200 to 8,400 messages in 4 minutes.
2. Worker throughput fell from a synthetic baseline of 500 messages/minute to 70 messages/minute.
3. Database latency and error rate stayed within their prior 24-hour ranges.
4. A worker log contains repeated `connection pool exhausted` messages during the interval.
5. A single worker restart at 09:18 UTC was followed by recovery; no controlled comparison was run.

Items 1–4 are observations from captured metrics or logs. Item 5 is an observation about sequence, not proof that the restart caused recovery.

## Competing explanations

- **H1 — pool exhaustion throttled workers:** repeated pool-exhaustion messages are consistent with the throughput drop.
- **H2 — downstream provider throttling:** a provider-side limit could reduce throughput while local database metrics remain normal.
- **H3 — worker restart removed a stuck resource:** the recovery after restart is consistent with this explanation, but the restart was not isolated from other changes.

## Inference and causal assessment

The evidence supports an inference that worker-side connection pressure contributed to the throughput reduction. It does not establish whether the pressure originated in the database client, a downstream call holding connections, or an external throttle. The restart/recovery sequence is temporally associated, not proof of causation.

**Confidence:** medium that connection pressure was a contributing factor; low that it was the sole cause; low that the restart itself was sufficient.

## Insufficiency

The diagnostic lacks per-operation connection hold time, provider throttle responses, and a controlled reproduction. The alert target and the intended queue limit are also **UNAVAILABLE**. No claim about the single root cause or alert-policy nonconformance should be made until those inputs are supplied.

## Recommendation

1. Capture pool occupancy, wait time, and connection hold duration at one-minute resolution.
2. Capture provider response codes and retry headers for the same interval.
3. Reproduce with a bounded worker load and compare no-restart versus restart runs.
4. Set and record an explicit alert-latency requirement before changing the threshold.
5. Until evidence distinguishes H1 from H2, treat both as active hypotheses rather than declaring a root cause.

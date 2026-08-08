# Architecture example: bounded export service

> **Provenance:** Synthetic example authored for the public ATS documentation. No source text, identities, paths, or repository material has been copied. It is an ordinary technical artifact, not a TextIR dump.
>
> **ATS edition:** New durable authoring uses ATS-1 `1.0.0-draft.2`; this example is illustrative prose for the composed `ASSESS + SPECIFY` architecture recipe.

## ASSESS

### Current state (observation)

The export service reads rows from the application database, builds a CSV file in the worker's local temporary directory, and uploads that file to object storage. A scheduler starts one export per customer each night. The service currently keeps no durable record of an export after the upload request returns.

### Evidence

- A synthetic load test with 10,000 rows produced a 42 MB CSV and completed in 3 minutes.
- A synthetic restart test interrupted an upload after 18 MB; the next scheduled run started from row 1 and produced a second object.
- The object-storage API supports multipart upload and an idempotency key, but the current service does not use either feature.

These measurements are observations from a fictional test setup, not claims about a deployed system.

### Problem and constraints

The target must tolerate a worker restart without silently losing an export or creating an unbounded number of duplicate objects. The service must remain usable when a single export is larger than local disk. Existing consumers read the current object naming convention, so changing that convention is out of scope for this change.

### Alternatives and judgment

1. **Keep local CSV assembly and retry whole uploads.** This is the smallest code change, but it preserves the disk bound and repeats work after a restart.
2. **Stream rows into a multipart upload.** This removes the local-disk requirement and uses the storage API's resumability. It requires durable export state.
3. **Introduce a separate export database.** This gives independent scaling but adds an operational dependency not justified by the stated problem.

**Decision (`DEC-EXPORT-001`, `AUTHOR_JUDGMENT`):** choose streaming multipart upload with a small durable export-state table. This decision is a recommendation for this design, not an observation about the current service.

### Unresolved points

The retention period for completed export-state rows is **UNAVAILABLE**. The storage provider's maximum multipart part count is also **UNAVAILABLE** in this example. Resolve both before production rollout; neither is silently assumed here.

## SPECIFY

### Target state and authority boundary

The export worker owns export state transitions and upload retries. Object storage owns object bytes. The scheduler may request an export but may not mark one complete. A status endpoint may report state but may not advance it. No component may claim success until the storage provider has acknowledged completion.

### Requirements

- **`REQ-EXPORT-001` (MUST):** The worker MUST stream each source row into a multipart upload without requiring a complete export-sized local file.
- **`REQ-EXPORT-002` (MUST):** The worker MUST persist an idempotency key, upload identifier, and completed-part list before acknowledging a retryable progress checkpoint.
- **`REQ-EXPORT-003` (MUST):** Retrying an interrupted export MUST resume the recorded upload or safely abort it; it MUST NOT publish a second object under the same export identity.
- **`REQ-EXPORT-004` (MUST):** The worker MUST mark an export `complete` only after the storage provider acknowledges multipart completion.
- **`REQ-EXPORT-005` (MUST NOT):** The worker MUST NOT delete a prior successfully published object as part of ordinary retry handling.

### Dependencies and failure behavior

- `REQ-EXPORT-001` depends on the storage client's multipart-streaming API.
- `REQ-EXPORT-002` depends on a transactional database table with a unique export identity.
- `REQ-EXPORT-003` depends on `REQ-EXPORT-002`; a retry without durable state is not locally closed.
- If the source query fails, the export remains `failed` with the error recorded; no object is published.
- If storage is temporarily unavailable, the export remains `retryable` and the scheduler may retry with bounded backoff.
- If the provider rejects completion, the worker records `failed` and leaves the object unpublished.

### Acceptance

- **`AC-EXPORT-001`** verifies `REQ-EXPORT-001`: a test exports a dataset larger than available worker temporary space and observes successful multipart completion without a full local file.
- **`AC-EXPORT-002`** verifies `REQ-EXPORT-002`: a test interrupts after a committed part, restarts the worker, and observes the same upload identifier and idempotency key in the resumed operation.
- **`AC-EXPORT-003`** verifies `REQ-EXPORT-003`: repeated retry requests result in one export identity and at most one published object.
- **`AC-EXPORT-004`** verifies `REQ-EXPORT-004`: a provider completion rejection leaves state `failed` and produces no success response.

Acceptance criteria are evidence obligations; they are not additional requirements. The retention period and provider part-count limit remain unresolved inputs to the implementation plan.

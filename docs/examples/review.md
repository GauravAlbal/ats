# Review example: cache invalidation proposal

> **Provenance:** Synthetic source excerpt and findings authored for the public ATS documentation. It is not copied from a real proposal and contains no private identities, paths, repositories, or credentials. This is an `ats-review`-style artifact, not a TextIR dump.
>
> **ATS edition:** New durable authoring uses ATS-1 `1.0.0-draft.2`; the reviewed source has no declared edition, so this example does not silently assign one.

## Source under review

> We **should** invalidate the product cache whenever a product changes. The API updates the database and then publishes an event. Consumers will process the event quickly, so stale reads will no longer occur. The worker retries failed events until they succeed. This design is safe for all products and requires no migration.

The excerpt is reproduced as a short synthetic review target. The review reports findings; it does not silently rewrite the source or label it nonconforming without a resolved ATS policy.

## Findings

### `REVIEW_REQUIRED`: ambiguous normative force

“Should” could be a recommendation or a requirement, while “will” describes an expectation without naming an owner or guarantee. The source does not establish whether invalidation is mandatory, who owns the event contract, or what happens when publication fails.

**Preserved unknown:** force, actor, and failure authority are **UNAVAILABLE**. Do not convert “should” to `MUST` merely to make the proposal appear precise.

### `REVIEW_REQUIRED`: evidence/claim mismatch

The sentence “stale reads will no longer occur” is a universal outcome claim. No ordering guarantee, cache-read policy, event delivery bound, or evidence is supplied to establish it.

**Preserved unknown:** whether the design provides read-after-write consistency, eventual consistency with a bounded window, or no such guarantee is **UNAVAILABLE**.

### `REVIEW_REQUIRED`: hidden dependency and missing exception

The retry statement assumes durable retry state, a retry limit or dead-letter policy, and an idempotent invalidation operation. None is named. “Until they succeed” could produce an unbounded retry loop.

**Preserved unknown:** retry ownership, delivery semantics, and terminal failure behavior are **UNAVAILABLE**.

### `ADVISORY`: scope too broad

“All products” is a scope claim with no product-class inventory or exclusion. A narrower scope would be easier to verify, but the review does not invent one.

## Review disposition

This review recommends a follow-up `SPECIFY` artifact that names stable requirements, actors, cache consistency semantics, event identity, retry failure behavior, migration, and acceptance evidence. Until those inputs are supplied, the proposal remains an unresolved design statement. No acceptance or conformance claim is made.

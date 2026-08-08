# Message lifecycle — review positive control

Public `ats-review` positive-control source material. The lifecycle semantics are
implementation-relevant and MUST NOT be collapsed by a review or transform.

## Source prose

A message accepted by the mail service passes through a lifecycle. On
acceptance the service records the message and returns an acceptance
receipt. A routed message is either disclosed to a waiter or delivered into a
waiter's own delivery queue (`waiter_delivered`). Only a consumed message —
one a waiter has explicitly marked consumed — is eligible for deletion from
the service's storage. Accepted messages cannot be lost.

## Review control

- The lifecycle distinction `accepted → routed → disclosed | waiter_delivered
  → consumed` is material: retention, deletion eligibility, and replay
  obligations all key off which state a message is in.
- A review finding MAY restate the invariant ("accepted mail cannot be
  silently dropped"), but the transform MUST NOT collapse the lifecycle into
  that single sentence when downstream implementation depends on the states.
- Expected review surface: the phrase "Accepted messages cannot be lost" is a
  valid invariant restatement; it is NOT a substitute for the state machine.

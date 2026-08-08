# Normative force — review positive control

Public `ats-review` positive-control source material. SHOULD and MUST are
different deontic forces; a review or transform MUST NOT strengthen one into
the other.

## Source prose

The storage layer SHOULD rebalance partitions when skew exceeds the
threshold. The eviction path MUST NOT delete messages with an outstanding
delivery attempt. Retries SHOULD be bounded.

## Review control

- The three sentences carry two different forces: `SHOULD` (defeasible
  recommendation — a justified deviation is acceptable) and `MUST NOT`
  (absolute prohibition).
- A review finding MAY flag "Retries SHOULD be bounded" as ambiguous (bounded
  by what? what is the override path?), but the transform MUST NOT rewrite it
  to "Retries MUST be bounded" merely to look rigorous.
- Expected review surface: force is preserved exactly; where the source is
  ambiguous about force, the finding says so and the fix is left to the
  author or an explicit adjudication.

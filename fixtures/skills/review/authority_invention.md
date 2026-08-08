# Authority invention — review positive control

Public `ats-review` positive-control source material. These documents describe
their own roles but never declare a cross-document authority hierarchy. A
downstream model reading them without ATS may invent one; the review must
surface `authority_precedence = UNAVAILABLE` instead.

## Source prose

**Document A — Product thesis.** Describes the product's purpose and the
intended evolution of the platform.

**Document B — Target architecture.** Describes the target system structure
and the components that will realize it.

**Document C — Evaluation strategy.** Describes how candidate implementations
are evaluated against the target architecture.

None of the three documents states which document governs the others. In
particular, neither A nor B claims precedence over the other; the evaluation
strategy does not claim authority over either.

## Review control

- No document declares precedence over another. The correct review outcome is
  `authority_precedence = UNAVAILABLE` (or an explicit statement that no
  cross-document precedence is established by the supplied sources), never an
  invented hierarchy such as "product thesis > target architecture > eval
  strategy".
- A transform MUST NOT promote any document to governing status absent an
  explicit declaration or an authorized new authoring decision.
- Expected review surface: a finding that the material is *tempting to
  hierarchize* and that the source does not establish it — with the
  resolution left as UNAVAILABLE, not inferred.

# Architecture decision records

Each ADR records one decision that shapes what this implementation is allowed to claim. The
format is Context / Decision / Consequences / Alternatives considered / References, and every
one cites the ATS-1 section or constitution principle it answers to.

They are not a changelog. An ADR exists when the obvious alternative was reasonable and was
rejected for a reason a future maintainer will otherwise have to rediscover.

| ADR | Decision | Turns on |
|---|---|---|
| [0001](ADR-0001-imported-package-immutable-and-receipted.md) | The imported normative package is immutable and receipted | §1.2, §19.1 |
| [0002](ADR-0002-never-pass-by-absence.md) | Never PASS by absence, enforced by `decide()` and a declared `DecisionPower` | §5.4, §16.5 |
| [0003](ADR-0003-local-schemas-namespaced-never-shadow-normative.md) | Repository-local schemas are namespaced and may not shadow a normative schema id | §19.4, §19.5 |
| [0004](ADR-0004-rfc8785-canonicalization-delegated.md) | RFC 8785 canonicalization is delegated to the `rfc8785` library | Appendix C, §6.6 |
| [0005](ADR-0005-semantic-review-and-forecast-calibration-structurally-unavailable.md) | `semantic_review` and `forecast_calibration` are structurally unavailable in v0 | §15.3, §15.5, §14.11 |
| [0006](ADR-0006-detector-term-lists-from-lexicon-or-enumerated-spec-list.md) | Detector term lists come from the lexicon, an enumerated spec list, or the artifact's glossary | §12.10, §16.8, §19.3 |
| [0007](ADR-0007-deterministic-finding-identity.md) | Finding identity is `artifact:rule:issue_code:ordinal`, derived not generated | §13.1, §16.2, §16.12 |
| [0008](ADR-0008-authority-capped-by-registry-detector-classes.md) | Detector authority is capped by the classes the registry declares for the rule | §12.3, §16.5 |
| [0009](ADR-0009-capability-declaration-is-generated.md) | The capability declaration is generated from the detector specs | §5.5, §16.1 |

Three of them form one argument, read in order: **0002** says a result may only claim what its
procedure earns; **0008** says the class the registry declares caps what the procedure may
earn; **0009** says the published declaration of both is derived from the code rather than
asserted beside it.

Findings about the draft itself — as opposed to decisions about this implementation — are in
[`../PACKAGE_OBSERVATIONS.md`](../PACKAGE_OBSERVATIONS.md). ADR-0008 and observation A are the
two halves of the same issue: the observation states the ambiguity in the standard, the ADR
states what this build does about it.

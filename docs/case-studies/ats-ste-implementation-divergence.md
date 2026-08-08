# Case study: ATS and STE when implementation state diverges

> **Status:** Non-normative case study. It is explanatory evidence, not an ATS rule, conformance claim, or universal comparison.
>
> **Provenance:** Concise synthesis of the repository's documented prior-art observation in [`docs/LINEAGE_AND_PRIOR_ART.md`](../LINEAGE_AND_PRIOR_ART.md). The state names and sentences below are an intentionally small public paraphrase; no private identity, path, repository, or credential is included. The source observation remains authoritative for its own bounded history.

## Question

Can a transformation improve surface readability while making a technical artifact less useful for implementation? ATS and ASD-STE100 address different layers:

- STE-oriented rewriting controls vocabulary, grammar, and local reading burden.
- ATS protects the semantic handoff: force, actors, scope, dependencies, evidence, uncertainty, and state relations.

The question is therefore not whether simpler prose is good. It is whether simplification preserves the relations that an implementer must recover.

## Observed divergence

The source behavior distinguished four implementation-relevant states:

```text
accepted → routed → disclosed → consumed
```

A transformed sentence compressed that behavior to a simpler statement equivalent to “accepted mail cannot be silently dropped.” The result is easier to read locally, but it does not tell an implementer whether routing is required, what disclosure means, when consumption occurs, which actor owns each transition, or how recovery differs between states.

That is **implementation divergence**: the surface statement remains directionally related to the source, while a consumer can no longer reconstruct the same state machine, obligations, or recovery points.

## What the observation supports

- Consolidation can remove repeated context that looked editorially redundant but carried a relation.
- A shorter sentence can preserve a broad intent while losing an implementation boundary.
- Readability and semantic recoverability are distinct evaluation dimensions.
- ATS's `ASSESS` vocabulary makes the distinction explicit: the observed transform is evidence; “the transform causes implementation loss” would be an inference whose confidence must be bounded.

## Required caveat

The observed transform **combined consolidation/simplification and STE-oriented rewriting**. It therefore does **not** show that STE universally causes losses. The bounded lesson is narrower: any transformation, including a readability-oriented one, should be checked for preservation of implementation-relevant relations before its output is used as a specification.

## ATS response

For an implementation artifact, retain the state transitions as explicit requirements or locally closed units, give each material relation a stable coordinate when downstream work joins on it, and keep acceptance evidence distinct from the requirement it verifies. If the source does not establish an actor, scope, or recovery rule, represent that value as unresolved or **UNAVAILABLE** rather than choosing a convenient interpretation.

This case study does not rank ATS above STE. It illustrates why they can be complementary: STE can improve the surface, while ATS supplies a semantic-preservation and handoff check for the implementation boundary.

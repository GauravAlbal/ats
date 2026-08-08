# ATS-1 generic host form

This pack contains the public ATS skills — the four skills that make up the
public surface of ATS-1:

- `ats` — the front door: author, transform, or review durable technical
  artifacts, routed to the right skill with the correct standard version.
- `ats-spec` — durable buildable artifacts (implementation specifications,
  protocols, acceptance contracts) with stable requirement coordinates.
- `ats-assess` — reasoning artifacts (diagnosis, postmortem, assessment,
  comparison, recommendation) with preserved uncertainty and force.
- `ats-review` — value-adding review of existing technical prose, without
  requiring conversion.

## What ATS is

ATS-1 is a technical writing standard for AI-generated and AI-consumed
engineering artifacts: architecture, RFCs and technical proposals,
implementation specifications, diagnostics, postmortems, technical
assessments, and acceptance/change-control records. It is not a universal
writing style. Its job is the semantic handoff: the operative meaning of a
durable artifact must survive being passed between agents and humans without
reconstructing undeclared state.

Use ATS for durable technical artifacts whose meaning must survive handoff.
Do not use ATS for scratch notes, exploratory chat, marketing copy, or casual
prose.

## The mini-constitution

Every public skill is governed by a ten-law mini-constitution. Each skill
reproduces it in full; the canonical recipes reference
(`recipes/ARTIFACT_RECIPES.md`) restates it:

1. Preserve meaning before improving surface form.
2. Do not invent authority.
3. Separate observation, inference, judgment, recommendation, and requirement
   when the distinction matters.
4. Preserve exact normative force.
5. Unknown is a valid state.
6. Remove surface material before removing material relations.
7. Stable semantic coordinates survive transformation.
8. Prefer local semantic closure for units expected to survive extraction.
9. Acceptance evidence is not the same discourse role as the requirement it
   verifies.
10. Ask only when unresolved meaning blocks the requested action.

## Installing

Keep the four skill directories and `recipes/` together under one host root;
`recipes/` is the installed artifact-recipe directory. Configure any host that
accepts Markdown skills to load `ats/`, `ats-spec/`, `ats-assess/`, and
`ats-review/` from this root. Do not copy only the skill directories: each
skill's recipe-guided path depends on the sibling `recipes/` tree.

Before installation, verify the release archive against its published
`SHA256SUMS`. Full canonical-parity verification requires the matching source
checkout:

```bash
ats skills verify --repo /path/to/ats-public --pack /path/to/skill-pack
```

## Licensing map

The skill bodies (`SKILL.md`) and packaging machinery are Apache-2.0. The
vendored canonical recipe document and summaries under `recipes/` are
CC-BY-4.0. See `LICENSE`, `LICENSES/`, `LICENSE.md`, and
`THIRD_PARTY_NOTICES.md` for the scoped notices and attribution.

## Deterministic provenance

`skill-pack-manifest.json` at the parent pack root binds this host form to its
canonical source: a tree hash over `skills/public/**` plus
`docs/ARTIFACT_RECIPES.md`, the source commit, the implementation and
skill-pack versions, and per-file SHA-256s for every host file.

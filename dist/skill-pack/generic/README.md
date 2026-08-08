# ATS-1 skill pack

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

## Installing a host form

Each subdirectory is one host representation of the same canonical skills
(identical skill identity, laws, recipes, version behavior, and invocation
semantics):

- `generic/` — plain markdown, frontmatter preserved. Use with any host that
  accepts markdown skills directly.
- `claude/` — Claude Code skills. Copy each skill directory into your Claude
  skills directory (`~/.claude/skills/`, or `.claude/skills/` in a project);
  `references/` holds the shared canonical recipes reference.
- `codex/` — plain markdown skills with placement guidance. See
  `codex/README.md` for the honest boundary: no codex-specific skill API is
  assumed.
- `agent-plugins/` — a portable Agent Plugins root (agent-plugins.org,
  schema 1.0.0). Copy the directory into any client that supports Agent
  Plugins; `plugin.json` declares the identity and `skills/` holds the four
  skills.

## Licensing map

The skill bodies (`SKILL.md`) and packaging machinery are Apache-2.0. The
vendored `docs/ARTIFACT_RECIPES.md` and public recipe summaries are CC-BY-4.0.
See each host's `LICENSE`, `LICENSES/`, `LICENSE.md`, and
`THIRD_PARTY_NOTICES.md` for the scoped notices and attribution.

## Deterministic provenance

`skill-pack-manifest.json` at the pack root binds this pack to its canonical
source: a tree hash over `skills/public/**` plus `docs/ARTIFACT_RECIPES.md`,
the source commit, the implementation and skill-pack versions, and per-file
SHA-256s for every host file. `ats skills verify --pack .` re-derives all of
it and fails with typed findings on any drift.

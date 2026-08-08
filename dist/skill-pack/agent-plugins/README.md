# ATS-1 Agent Plugin

A portable Agent Plugins root (agent-plugins.org, schema 1.0.0).

- `plugin.json` — the plugin manifest (identity + metadata).
- `skills/` — the four ATS public skills as Agent Skills. Each skill directory
  contains a single `SKILL.md` whose frontmatter carries `name` and
  `description`, satisfying the Agent Skills specification; the files are
  byte-identical to the canonical public skills.
- `references/` — the artifact recipes (docs/ARTIFACT_RECIPES.md + the five
  recipe summaries) that the skills reference. Recipe parity: every host form
  ships the same recipes; the vendored skills' recipe references resolve here.

## Installing

Copy this directory (or publish it) to any client that supports Agent
Plugins. A skills-capable client discovers the immediate children of
`skills/` and validates each `SKILL.md` against the Agent Skills
specification.

## Package boundaries

All files live within this plugin root. No symlinks are used; plugin-relative
paths, where any appear, start with `./`.

## Licensing map

The skill bodies (`SKILL.md`) and packaging machinery are Apache-2.0. The
vendored `docs/ARTIFACT_RECIPES.md` and summaries under `references/` are
CC-BY-4.0. `plugin.json` records the mixed scope as
`Apache-2.0 AND CC-BY-4.0`. See `LICENSE`, `LICENSES/`, `LICENSE.md`, and
`THIRD_PARTY_NOTICES.md` for scoped notices and attribution.

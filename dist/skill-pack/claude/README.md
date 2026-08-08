# Claude host form

This directory packages the ATS public skills for Claude Code.

## What a Claude skill needs

A Claude Code skill is a directory containing a `SKILL.md` whose YAML
frontmatter carries `name` and `description`, followed by the skill body.
The canonical public skills already carry exactly that frontmatter, so each
`SKILL.md` here is byte-identical to the canonical file — nothing was
rewritten for this host.

## Installing

Copy each skill directory (or the whole host directory) into your Claude
skills directory:

- User-level: `~/.claude/skills/<name>/SKILL.md`
- Project-level: `.claude/skills/<name>/SKILL.md` in the repository

The four skills reference `docs/ARTIFACT_RECIPES.md` (the canonical artifact
recipes). The pack vendors that document at `references/ARTIFACT_RECIPES.md`;
make it available alongside the skills (for example by copying
`references/` next to your skills directory) so the recipe reference resolves.

## What this host does not assume

No Claude-specific API beyond the documented `name` + `description`
frontmatter and `references/` convention is assumed. The skills invoke the
`ats` CLI for deterministic checking; that CLI is a separate install and is
not part of this directory.

## Licensing map

The skill bodies (`SKILL.md`) and packaging machinery are Apache-2.0. The
vendored canonical recipe document and summaries under `references/` are
CC-BY-4.0. See `LICENSE`, `LICENSES/`, `LICENSE.md`, and
`THIRD_PARTY_NOTICES.md` for scoped notices and attribution.

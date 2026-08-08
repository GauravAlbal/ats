# Claude host form

This directory packages the ATS public skills for Claude Code.

## What a Claude skill needs

A Claude Code skill is a directory containing a `SKILL.md` whose YAML
frontmatter carries `name` and `description`, followed by the skill body.
The canonical public skills already carry exactly that frontmatter, so each
`SKILL.md` here is byte-identical to the canonical file — nothing was
rewritten for this host.

## Installing

Copy the four skill directories and `references/` as siblings into the Claude
skills directory. Preserve that relative layout; `references/` is the
installed artifact-recipe directory.

```bash
# user-level
cp -R ats ats-spec ats-assess ats-review references "$HOME/.claude/skills/"

# project-level, run from this host root
cp -R ats ats-spec ats-assess ats-review references /path/to/project/.claude/skills/
```

The resulting skill paths are `~/.claude/skills/<name>/SKILL.md` (or
`.claude/skills/<name>/SKILL.md`) and the recipe index is the sibling
`references/ARTIFACT_RECIPES.md`.

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

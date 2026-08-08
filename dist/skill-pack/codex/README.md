# Codex host form

This directory packages the ATS public skills for OpenAI Codex.

## Honest boundary

Codex consumes plain markdown skills; there is no documented per-skill
manifest API for Codex beyond the markdown itself. Accordingly this host
form:

- ships each skill as plain markdown (`ats/SKILL.md` and so on), byte-identical
  to the canonical file;
- makes **no** codex-specific API assumption — no frontmatter contract, no
  plugin schema, nothing that would break if Codex's skill surface changes;
- treats the YAML frontmatter in each file as inert markdown (it is not parsed
  by this host).

## Placement guidance

Codex reads guidance from `AGENTS.md` files in the repository. To use these
skills with Codex:

1. Copy the skill bodies into your `AGENTS.md` (or a file it references),
   under a heading naming the skill (`ats`, `ats-spec`, `ats-assess`,
   `ats-review`).
2. Make the canonical recipes reference available: the skills reference
   `docs/ARTIFACT_RECIPES.md`; vendor `recipes/ARTIFACT_RECIPES.md` from this
   directory (or the canonical document) at a path the skill body can reach.

Verify placement against OpenAI's current guidance before relying on it; this
directory intentionally does not encode an API that may not exist.

## Licensing map

The skill bodies (`SKILL.md`) and packaging machinery are Apache-2.0. The
vendored canonical recipe document and summaries under `recipes/` are
CC-BY-4.0. See `LICENSE`, `LICENSES/`, `LICENSE.md`, and
`THIRD_PARTY_NOTICES.md` for scoped notices and attribution.

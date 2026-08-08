# ATS Skill Pack — Packaging Reference

This document is the packaging reference for the ATS public skill pack:
canonical source → deterministic packager → host representations, the manifest
and its three version strings, verification (`ats skills verify`), parity
guarantees, and the upgrade/drift mechanism.

Related documents:

- `docs/SKILL_PACK_NORTH_STAR.md` — program north star;
  `docs/decisions/ADR-0023-public-skill-pack-architecture.md` is the governing
  architecture decision.
- `docs/FLEET_SKILL_ROLLOUT.md` — how fleet repos vendor the pack (§50 ten
  answers).
- `docs/OSS_SKILL_PACK.md` — install/use/upgrade for a standalone user.
- `docs/decisions/ADR-0020` (two-default version law), `docs/decisions/ADR-0023`
  (pack architecture, authority precedence).

## 1. Canonical source

The pack is generated from exactly one canonical source set in this
repository:

```text
skills/public/ats/SKILL.md
skills/public/ats-spec/SKILL.md
skills/public/ats-assess/SKILL.md
skills/public/ats-review/SKILL.md
skills/public/recipes/               # architecture, diagnostic, implementation_program,
                                     # postmortem, rfc_technical_proposal
docs/ARTIFACT_RECIPES.md             # canonical recipes document
```

The four public skills are the only distributed skills. Their procedures are
self-contained and do not invoke or require repository-only compiler skills.
The internal compiler skills (`ats-ir-author`, `ats-specify-output`,
`ats-assess-output`) remain repository-only development artifacts and are not
packaged or required to use the public pack.
Canonical source comes first: complete these source files and recipes, then
run `tools/generate_skill_pack.py` and `ats skills verify`; generated host
forms are never hand-maintained.

Authority precedence (§39, ADR-0023): ATS-1 normative package > public skill
contract > artifact recipe > host packaging adapter. A host adapter that
cannot express a required behavior fails package validation; it never
silently weakens the skill.

## 2. The deterministic packager

`tools/generate_skill_pack.py` maps canonical source → `dist/skill-pack/`:

```bash
python tools/generate_skill_pack.py
python tools/generate_skill_pack.py --repo /path/to/ats --out /tmp/skill-pack
python tools/generate_skill_pack.py --now 2026-08-07T00:00:00Z --source-commit <source-commit>
```

Flags:

- `--repo REPO` — canonical source repo root (default: the ats package repo).
- `--out DIR` — output pack directory (default: `<repo>/dist/skill-pack`).
- `--now RFC3339` — `generated_at`; default is the **source commit timestamp**
  (git committer time), never the wall clock.
- `--source-commit SHA` — provenance commit; default is git HEAD (or the
  `SOURCE_COMMIT` env). When pinned, `generated_at` derives from that commit's
  timestamp.

Determinism contract (§6, §19.2): the pack is a pure function of (canonical
source bytes, repository-root `LICENSE` bytes, source commit, generation
timestamp). Regenerating at the same commit — or with the same
`--now`/`--source-commit` — produces byte-identical output: sorted manifest
keys, fixed static READMEs, verbatim file copies, per-file SHA-256s.
The packager validates the manifest against the registered
schema before writing anything, and `write_pack` wipes the target directory
first (refusing any directory not named `skill-pack`, and refusing the repo
root or its ancestors), so stale host files can never linger.

## 3. The four host forms

Every host carries the same skill identity, laws, recipes, version behavior,
and invocation semantics (§19.2, §45); only layout/transport differ. Each
`SKILL.md` is byte-identical to the canonical file — nothing is rewritten per
host.

| Identity | Layout | Notes |
|---|---|---|
| `generic` | `generic/<name>/SKILL.md`, `generic/recipes/`, `generic/README.md`, `generic/LICENSE` | Plain markdown, frontmatter preserved. Canonical form; the verifier's parity baseline. Works in any host that reads markdown skills. |
| `claude` | `claude/<name>/SKILL.md`, `claude/references/`, `claude/README.md`, `claude/LICENSE` | Claude Code skills. Each skill directory carries `SKILL.md` whose YAML frontmatter provides `name` + `description` (the only host API assumed). Install into `~/.claude/skills/` or `.claude/skills/`; the host README identifies `references/` as the installed recipe directory. |
| `codex` | `codex/<name>/SKILL.md`, `codex/recipes/`, `codex/README.md`, `codex/LICENSE` | Plain markdown with placement guidance for `AGENTS.md`. Honest boundary: no codex-specific per-skill manifest API is assumed; frontmatter is inert markdown here. The host README identifies `recipes/` as the installed recipe directory. |
| `agent-plugins` | `agent-plugins/plugin.json`, `agent-plugins/skills/<name>/SKILL.md`, `agent-plugins/references/`, `agent-plugins/README.md`, `agent-plugins/LICENSE` | Portable Agent Plugins root (agent-plugins.org, schema 1.0.0). `plugin.json` declares identity and metadata; `skills/` holds the four Agent Skills; the host README identifies `references/` as the installed recipe directory. No symlinks; plugin-relative paths only. |

Canonical skills preserve the source locations `docs/ARTIFACT_RECIPES.md` and
`skills/public/recipes/` as provenance, but do not treat those paths as
standalone install locations. They explicitly map installed generic/Codex
hosts to `recipes/` and Claude/Agent Plugins hosts to `references/`. The
verifier resolves every manifest-declared recipe basename inside each host
root, and the isolated-pack capstone prevents repository files from satisfying
that contract.

Every host root includes `LICENSE`, copied byte-for-byte from
`LICENSES/Apache-2.0.txt`, plus the separately copied `LICENSE.md` scope map,
both complete license texts, and `THIRD_PARTY_NOTICES.md`. The manifest
enumerates each copy and records its SHA-256, so missing or tampered notices
fail `ats skills verify`.

The `agent-plugins` host is validated against the Agent Plugins rules it
actually relies on:

- `$schema` must equal `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`.
- `name` must match the 1–64 character lowercase ASCII / hyphen / dot rule
  (no `--`, no `..`) and equal `ats-skill-pack`; `version` is a non-empty
  string; `description`, `license`, `keywords` are strings/string-array when
  present.
- `skills/` immediate children must be exactly the four required skills, each
  with a `SKILL.md` byte-identical to canonical.

## 4. The manifest (`skill-pack-manifest.json`)

`dist/skill-pack/skill-pack-manifest.json` is the pack's identity and
provenance record. Schema: `schemas/ats_skill_pack_manifest_v1.schema.json`
(`$id` `ats_skill_pack_manifest_v1.schema.json`, schema version
`ats.skill_pack_manifest.v1`), registered in `SCHEMA_FOR_VERSION`.

| Field | Meaning | Example |
|---|---|---|
| `schema_version` | manifest schema identity (const) | `ats.skill_pack_manifest.v1` |
| `skill_pack_version` | the public skill surface + packaging (§38) | `0.1.2` |
| `implementation_version` | the runtime/CLI the skills invoke | `0.5.0` |
| `standard_versions_supported` | editions the skills resolve: `new_authoring` draft.2, `legacy_interpretation` draft.1 | `{"new_authoring": "1.0.0-draft.2", "legacy_interpretation": "1.0.0-draft.1"}` |
| `canonical_source_sha256` | deterministic tree hash of the canonical source (§5) | `7a43f7e…` |
| `skills` | the four public skills: `name`, canonical `path`, `sha256` | `[{name: ats, path: skills/public/ats/SKILL.md, …}]` |
| `recipes` | canonical recipe paths (recipes doc + public summaries) | `["docs/ARTIFACT_RECIPES.md", "skills/public/recipes/…"]` |
| `hosts` | per-host identity + `files[{path, sha256}]` for every distributed file | `[{identity: generic, files: […]}]` |
| `generated_at` | RFC 3339; default = source commit timestamp (deterministic) | `2026-08-07T19:31:12-07:00` |
| `source_commit` | canonical source commit the pack was generated at | `<source-commit>…` |
| `packager_version` | packager/layout version, independent of impl + pack versions | `0.1.0` |

Three version strings, never collapsed (§38):

- **ATS-1 standard**: `1.0.0-draft.2` (new authoring) / `1.0.0-draft.1`
  (legacy interpretation) — the two-default law (ADR-0020).
- **ATS implementation**: `0.5.0` (`src/ats/__init__.py`).
- **ATS skill pack**: `0.1.2` (`SKILL_PACK_VERSION` in `src/ats/__init__.py`),
  stamped in the manifest and in the agent-plugins `plugin.json`.

Release `0.1.1` remains published under `v0.1.1-skill-pack`. Candidate `0.1.2`
repairs portable recipe lookup and receives a new signed annotated tag only
after its own gates pass. The manifest's `source_commit` identifies the canonical
source commit used before generation.

## 5. The canonical tree hash

`canonical_source_sha256` is a deterministic tree hash over the canonical
source: every file under `skills/public/**` (excluding `__pycache__`/`.pyc`)
plus `docs/ARTIFACT_RECIPES.md`, sorted by relative path, hashing each entry
as `relpath \0 file-sha256 \0`. It is a pure function of the canonical source
bytes, so it changes if and only if the canonical source changes — the verifier
recomputes it and compares.

## 6. Verification: `ats skills verify`

```bash
ats skills verify                        # pack default: dist/skill-pack
ats skills verify --pack dist/skill-pack
ats skills verify --pack <dir> --repo /path/to/ats
ats --format text skills verify          # JSON is the default output format
```

`--repo` defaults to the nearest ancestor of the current directory that holds
the canonical skill source. Output is `{"status": "PASS"|"FAIL",
"findings": […], "pack": …, "repo": …}`; exit code 0 on PASS, 1 on FAIL.

Checks and their typed finding codes (§40):

| Check | Finding code |
|---|---|
| Manifest matches the registered schema | (schema violations) |
| `implementation_version` / `packager_version` match the runtime | `MANIFEST-VERSION` |
| `generated_at` is RFC 3339 | `MANIFEST-TIMESTAMP` |
| `standard_versions_supported` matches (new authoring must be draft.2) | `STANDARD-VERSIONS` |
| Required skills present in manifest, canonical source, and generic pack | `SKILLS-REQUIRED`, `SKILLS-SOURCE`, `SKILLS-PACK` |
| Recomputed canonical tree hash matches the manifest | `TREE-HASH` |
| Recipes list matches the canonical set | `RECIPES-LIST` |
| All ten mini-constitution laws present in each skill | `LAWS-MISSING` |
| Host identities exactly the four known ones | `HOSTS-REQUIRED`, `HOSTS-UNKNOWN` |
| Every enumerated host file exists and matches its SHA-256 | `HOST-FILE-MISSING`, `HOST-FILE-HASH` |
| `generic`/`claude`/`codex` skills byte-identical to canonical | `HOST-PARITY` |
| agent-plugins manifest/layout/parity rules | `AGENT-PLUGINS-*` |
| Every host root carries the repository `LICENSE`; manifest enumerates and hashes it | `HOST-FILE-MISSING`, `HOST-FILE-HASH` |
| Recipe references and internal-skill references resolve | `RECIPE-REF`, `INTERNAL-REF`, `FIXTURE-REF` |
| No local absolute paths in distributed files | `ABS-PATH` |
| No new-authoring-tied-to-draft.1 language | `DRAFT1-DEFAULT` |
| Human escalation gated on action-blocking unresolved semantics | `ESCALATION` |
| No PASS-by-absence language | `PASS-ABSENCE` |
| No private fleet (arq) dependency in the generic pack | `ARQ-DEP` |
| Regeneration produces zero diff (see below) | `HOST-REGEN-DRIFT` |

## 7. The zero-diff regeneration guarantee

The verifier itself proves determinism: it regenerates the pack in a temp
directory (pinned to the manifest's `generated_at` and `source_commit`) and
byte-diffs it against the pack under test. Any file that differs, is missing,
or is present only in the regeneration is a `HOST-REGEN-DRIFT` finding. A pack
that was hand-edited, generated from a different commit, or produced by a
different packager fails. The committed baseline is regenerated from a verified
canonical source commit and passes verification; the unit suite covers
determinism and clean regeneration in `tests/unit/test_skill_pack.py`.

## 8. Upgrade mechanism (§51)

Upgrade is **regenerate → verify → re-vendor**; there is no copy-paste
archaeology and no incremental patching of a vendored copy:

1. **Regenerate** from the new canonical source:
   `python tools/generate_skill_pack.py` (pins `generated_at` to the new
   commit's timestamp). If reproducing an exact artifact instead,
   `--now`/`--source-commit` pin it.
2. **Verify**: `ats skills verify --pack dist/skill-pack` must PASS with zero
   findings. This recomputes the tree hash, checks every host file, and
   proves zero-diff regeneration.
3. **Re-vendor**: consumers (fleet repos, standalone users) replace their
   vendored host form and the manifest with the new baseline, and record the
   new `skill_pack_version` / `source_commit` / `canonical_source_sha256`
   (`docs/FLEET_SKILL_ROLLOUT.md` §6.6).

**Drift detection** is layered and byte-honest: the manifest binds the pack to
its canonical source (`canonical_source_sha256`), to its generation
(`source_commit`, `generated_at`, `packager_version`), and to every
distributed file (per-host `sha256`). A vendored copy drifts if (a) the
canonical source changed and the manifest's tree hash no longer matches, or
(b) any vendored file differs from its manifest SHA-256. Both are detected
without trusting copy history. `ats skills verify` catches drift in the ATS
repo; a consumer compares vendored files against the manifest's per-file
hashes in CI.

## 9. Parity requirements (§19.2, §45)

Every host package must preserve, per skill: **skill identity** (name +
description frontmatter), the **mini-constitution laws** (all ten, verbatim
key phrases), the **recipes** (identical references to the canonical recipes
document and summaries), **version behavior** (draft.2 new authoring,
draft.1 legacy, explicit `--spec-version` wins, no silent downgrade), and
**invocation semantics** (the same `ats` CLI commands, the same routing
rules). The verifier enforces parity mechanically (`HOST-PARITY`,
`AGENT-PLUGINS-PARITY`: byte-identity of every skill file against canonical;
`LAWS-MISSING`; recipe/version checks).

Authority precedence (§39) closes the escape hatch: where a host **cannot
express** a required behavior (e.g. a host with no frontmatter contract, no
plugin schema, no policy file), the host form must say so honestly and the
package must still satisfy validation — it never silently weakens a skill to
fit the host. A host representation that cannot meet validation fails the
pack, it does not degrade the skill.

## 10. Reproducibility and provenance, restated

```text
skills/public/** + docs/ARTIFACT_RECIPES.md        (canonical source)
        │ tools/generate_skill_pack.py             (deterministic; now = commit timestamp)
        ▼
dist/skill-pack/
├── generic/    plain markdown, canonical
├── claude/     Claude Code skills (frontmatter name/description, references/)
├── codex/      plain markdown + AGENTS.md placement guidance
├── agent-plugins/  plugin.json + skills/ (agent-plugins.org schema 1.0.0)
└── skill-pack-manifest.json   (schema ats.skill_pack_manifest.v1)
        │ ats skills verify    (schema, versions, tree hash, per-file hashes,
        │                       parity, regen zero-diff)
        ▼
PASS ⇒ consumable baseline (committed); FAIL ⇒ typed findings, do not ship
```

The manifest's provenance fields (`source_commit`, `generated_at` from the
commit, `packager_version`) make every shipped pack traceable to the exact
canonical bytes it was generated from, and the tree hash makes the canonical
bytes themselves verifiable without trusting any intermediate copy.

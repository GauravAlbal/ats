"""Deterministic packaging and verification of the ATS public skill pack.

Canonical source
    ``skills/public/**`` (the public SKILL.md files plus the public recipe
    summary files) and ``docs/ARTIFACT_RECIPES.md`` (the canonical recipes
    reference). The pack copies the complete split licensing notice set into
    every host root. The pack is a pure function of these bytes, the notice
    bytes, the source commit, and the generation timestamp.

Tree hash (``canonical_source_sha256``)
    SHA-256 over the concatenation, in ascending byte order of the relative
    POSIX path, of ``<path>\\x00<hex sha256 of the file bytes>\\x00`` for every
    canonical file. Sorted paths + per-file content hashes make the hash
    independent of directory iteration order and of absolute locations.

Hosts
    Every host root carries ``LICENSE`` (the complete Apache-2.0 text),
    ``LICENSES/Apache-2.0.txt``, ``LICENSES/CC-BY-4.0.txt``, ``LICENSE.md``,
    and ``THIRD_PARTY_NOTICES.md``; all are enumerated and hash-bound in the
    manifest. Layouts otherwise are:
    generic/        plain markdown, frontmatter preserved, ``recipes/`` copy of
                    the canonical recipes reference, pack-level README
    claude/         Claude Code skills: SKILL.md with ``name`` + ``description``
                    frontmatter (the canonical files already carry both),
                    shared ``references/`` recipe files, README
    codex/          plain markdown skills + placement-guidance README. No
                    codex-specific API is invented: the boundary is documented
                    honestly in the README.
    agent-plugins/  agent-plugins.org plugin root (schema 1.0.0): ``plugin.json``
                    at the root and ``skills/`` with the four skills as Agent
                    Skills (verbatim SKILL.md, whose frontmatter already
                    satisfies that format). No symlinks; no files outside the
                    plugin root.

Verification
    ``ats skills verify --pack dist/skill-pack`` re-derives every manifest
    claim deterministically and returns typed findings; see :func:`verify_pack`.

Determinism contract (§6, §45)
    Regenerating with the same ``now`` and ``source_commit`` must produce zero
    diff: sorted keys, fixed timestamps, relative paths only, no wall clock
    reads.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from jsonschema import Draft202012Validator, FormatChecker

from . import SKILL_PACK_VERSION, __version__
from .errors import UsageError
from .schemas import SCHEMA_FOR_VERSION
from .spec_package import REPO_ROOT

#: Version of this packager (the manifest's ``packager_version``). Independent
#: of the implementation version and of the skill-pack version: it only moves
#: when the pack layout or manifest shape changes.
PACKAGER_VERSION: Final[str] = "0.1.0"

MANIFEST_SCHEMA_VERSION: Final[str] = "ats.skill_pack_manifest.v1"
MANIFEST_SCHEMA_ID: Final[str] = "ats_skill_pack_manifest_v1.schema.json"

#: agent-plugins.org portable manifest (schema 1.0.0, plugin-authors/manifest).
PLUGIN_SCHEMA_URL: Final[str] = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PLUGIN_NAME: Final[str] = "ats-skill-pack"
PLUGIN_LICENSE: Final[str] = "Apache-2.0 AND CC-BY-4.0"

STANDARD_VERSIONS_SUPPORTED: Final[dict[str, str]] = {
    "new_authoring": "1.0.0-draft.3",
    "legacy_interpretation": "1.0.0-draft.1",
}

REQUIRED_SKILLS: Final[tuple[str, ...]] = ("ats", "ats-spec", "ats-assess", "ats-review")
HOST_IDENTITIES: Final[tuple[str, ...]] = ("generic", "claude", "codex", "agent-plugins")
HOST_RECIPE_DIRECTORIES: Final[dict[str, str]] = {
    "generic": "recipes",
    "codex": "recipes",
    "claude": "references",
    "agent-plugins": "references",
}
# Every host is independently redistributable and therefore carries the full
# split notice set. ``LICENSE`` is the conventional host entry point and is
# the complete Apache-2.0 implementation text.
HOST_NOTICE_SOURCES: Final[tuple[tuple[str, str], ...]] = (
    ("LICENSE", "LICENSES/Apache-2.0.txt"),
    ("LICENSES/Apache-2.0.txt", "LICENSES/Apache-2.0.txt"),
    ("LICENSES/CC-BY-4.0.txt", "LICENSES/CC-BY-4.0.txt"),
    ("LICENSE.md", "LICENSE.md"),
    ("THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md"),
)

#: Canonical recipes document, and the public recipe-summary directory the
#: skills reference.
CANONICAL_RECIPES_PATH: Final[str] = "docs/ARTIFACT_RECIPES.md"
PUBLIC_RECIPES_DIR: Final[str] = "skills/public/recipes"

#: Internal skills the public skills may reference; resolved against the
#: canonical source root and checked by the pack validator.
INTERNAL_SKILLS: Final[tuple[str, ...]] = ("ats-ir-author", "ats-specify-output", "ats-assess-output")

#: The mini-constitution, verbatim, as whitespace-normalized key phrases.
#: Every distributed skill must carry all ten.
MINI_CONSTITUTION: Final[tuple[str, ...]] = (
    "Preserve meaning before improving surface form",
    "Do not invent authority",
    "Separate observation, inference, judgment, recommendation, and requirement when the distinction matters",
    "Preserve exact normative force",
    "Unknown is a valid state",
    "Remove surface material before removing material relations",
    "Stable semantic coordinates survive transformation",
    "Prefer local semantic closure for units expected to survive extraction",
    "Acceptance evidence is not the same discourse role as the requirement it verifies",
    "Ask only when unresolved meaning blocks the requested action",
)

#: PASS-by-absence language: the machinery may never imply that absence of
#: checks means conformance.
_PASS_BY_ABSENCE_PATTERNS: Final[tuple[str, ...]] = (
    r"passes? by default",
    r"conforms? unless flagged",
    r"pass(?:es)? when nothing",
    r"pass(?:es)? (?:if|when) (?:nothing|no (?:checks?|findings?|issues?))",
    r"reports? conforming by default",
)

#: Local developer path prefixes that must never appear in distributed files.
_LOCAL_PATH_PREFIXES: Final[tuple[str, ...]] = (
    "/" + "Users/",
    "/" + "tmp",
    "/" + "private/",
    "/" + "home/",
)

#: Private fleet identifiers are forbidden in generated public hosts. This
#: applies only to distributed pack files, not canonical repository docs.
_PRIVATE_FLEET_RESIDUE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:" + "ats-" + r"internal|arq|sear|tribunal|vx|moat)\b",
    re.IGNORECASE,
)


def _norm(text: str) -> str:
    """Collapse all whitespace runs to single spaces (law matching is line-wrap safe)."""
    return re.sub(r"\s+", " ", text).strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_source_files(repo_root: Path) -> dict[str, Path]:
    """Relative POSIX path -> path for every canonical source file.

    ``skills/public/**`` (excluding junk like ``__pycache__``) plus the
    canonical recipes document. Sorted by relative path.
    """
    out: dict[str, Path] = {}
    public = repo_root / "skills" / "public"
    if public.is_dir():
        for path in sorted(public.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            out[path.relative_to(repo_root).as_posix()] = path
    recipes = repo_root / "docs" / "ARTIFACT_RECIPES.md"
    if recipes.is_file():
        out[CANONICAL_RECIPES_PATH] = recipes
    return dict(sorted(out.items()))


def tree_hash(files: dict[str, Path]) -> str:
    """Deterministic tree hash over canonical source files (see module docstring)."""
    digest = hashlib.sha256()
    for rel, path in files.items():
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_sha256(path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _public_skill_paths(repo_root: Path) -> list[tuple[str, Path]]:
    """``(name, canonical SKILL.md path)`` for every public skill, sorted by name."""
    out: list[tuple[str, Path]] = []
    public = repo_root / "skills" / "public"
    if public.is_dir():
        for skill_dir in sorted(public.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.is_file():
                out.append((skill_dir.name, skill_md))
    return out


def _canonical_recipe_paths(repo_root: Path) -> list[str]:
    """Canonical recipe source paths: the recipes doc plus any public summaries."""
    paths = [CANONICAL_RECIPES_PATH]
    public_recipes = repo_root / "skills" / "public" / "recipes"
    if public_recipes.is_dir():
        paths.extend(
            sorted(
                p.relative_to(repo_root).as_posix()
                for p in public_recipes.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts
            )
        )
    return sorted(set(paths))


def _validate_recipe_basenames(recipe_paths: list[str]) -> None:
    """Reject recipe sources that would collide in a host's flat copy layout."""
    by_basename: dict[str, list[str]] = {}
    for rel in recipe_paths:
        by_basename.setdefault(Path(rel).name, []).append(rel)
    duplicates = {
        basename: paths for basename, paths in by_basename.items() if len(paths) > 1
    }
    if duplicates:
        details = "; ".join(
            f"{basename}: {', '.join(paths)}" for basename, paths in sorted(duplicates.items())
        )
        raise ValueError(f"recipe files must have unique basenames ({details})")


def _manifest_schema(repo_root: Path) -> dict[str, Any]:
    schema_path = repo_root / "schemas" / MANIFEST_SCHEMA_ID
    if not schema_path.is_file():
        raise UsageError(
            f"manifest schema not found at {schema_path}; expected it registered as "
            f"{MANIFEST_SCHEMA_VERSION!r} in SCHEMA_FOR_VERSION"
        )
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_manifest_schema(manifest: dict[str, Any], repo_root: Path) -> list[str]:
    """Validate the manifest against the registered schema; returns violation messages."""
    schema = _manifest_schema(repo_root)
    validator = Draft202012Validator(schema, format_checker=_MANIFEST_FORMAT_CHECKER)
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(manifest)
    ]


def _is_rfc3339_datetime(value: object) -> bool:
    """Return whether ``value`` is a strict RFC 3339 date-time."""
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
        value,
    ):
        return False
    try:
        _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


_MANIFEST_FORMAT_CHECKER = FormatChecker()
_MANIFEST_FORMAT_CHECKER.checks("date-time")(_is_rfc3339_datetime)


def _validate_generated_at(now: str) -> None:
    if not _is_rfc3339_datetime(now):
        raise ValueError(f"generated_at must be a strict RFC 3339 date-time: {now!r}")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def _copy_bytes(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def _generate_host_notices(host_dir: Path, repo_root: Path) -> list[Path]:
    """Copy the complete manifest-bound split notice set into one host."""
    written: list[Path] = []
    for destination, source in HOST_NOTICE_SOURCES:
        src = repo_root / source
        dst = host_dir / destination
        if not src.is_file():
            raise UsageError(f"required licensing notice is missing: {source}")
        _copy_bytes(src, dst)
        written.append(dst)
    return written


def _generate_host_skills(
    host_dir: Path, skills: list[tuple[str, Path]], *, skills_subdir: str | None = None
) -> list[Path]:
    """Copy each canonical SKILL.md verbatim under ``host_dir/<subdir>/<name>/SKILL.md``."""
    written: list[Path] = []
    base = host_dir / skills_subdir if skills_subdir else host_dir
    for name, skill_md in skills:
        dst = base / name / "SKILL.md"
        _copy_bytes(skill_md, dst)
        written.append(dst)
    return written


def _generate_recipes_copy(host_dir: Path, repo_root: Path, rel_subdir: str) -> list[Path]:
    """Copy canonical recipe files into ``host_dir/<rel_subdir>/``, verbatim."""
    written: list[Path] = []
    for rel in _canonical_recipe_paths(repo_root):
        src = repo_root / rel
        dst = host_dir / rel_subdir / src.name
        _copy_bytes(src, dst)
        written.append(dst)
    return written


# -- pack-level and host READMEs (static, deterministic) -----------------------


def _pack_readme() -> str:
    return """# ATS-1 generic host form

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
"""


def _claude_readme() -> str:
    return """# Claude host form

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
"""


def _codex_readme() -> str:
    return """# Codex host form

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
2. Copy this host's complete `recipes/` directory into the repository and
   identify that installed path in `AGENTS.md`. `recipes/` is the installed
   artifact-recipe directory; the skill bodies' Codex recipe path resolves to
   `recipes/ARTIFACT_RECIPES.md` plus the five recipe summaries.

Verify placement against OpenAI's current guidance before relying on it; this
directory intentionally does not encode an API that may not exist.

## Licensing map

The skill bodies (`SKILL.md`) and packaging machinery are Apache-2.0. The
vendored canonical recipe document and summaries under `recipes/` are
CC-BY-4.0. See `LICENSE`, `LICENSES/`, `LICENSE.md`, and
`THIRD_PARTY_NOTICES.md` for scoped notices and attribution.
"""


def _agent_plugins_readme() -> str:
    return """# ATS-1 Agent Plugin

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
"""


def _plugin_json() -> dict[str, Any]:
    return {
        "$schema": PLUGIN_SCHEMA_URL,
        "name": PLUGIN_NAME,
        "version": SKILL_PACK_VERSION,
        "description": (
            "ATS-1 public skills: author, transform, or review durable technical "
            "artifacts with a preserved semantic handoff."
        ),
        "license": PLUGIN_LICENSE,
        "keywords": [
            "ats",
            "technical-writing",
            "specification",
            "semantic-preservation",
            "artifact",
            "review",
        ],
    }


# -- generation ---------------------------------------------------------------


def _generate_pack_contents(
    repo_root: Path, pack_dir: Path, *, now: str, source_commit: str
) -> dict[str, Any]:
    """Materialize and validate one complete pack in an isolated directory."""
    _validate_generated_at(now)
    files = canonical_source_files(repo_root)
    skills = _public_skill_paths(repo_root)
    recipe_paths = _canonical_recipe_paths(repo_root)
    _validate_recipe_basenames(recipe_paths)
    skill_entries = sorted(
        (
            {
                "name": name,
                "path": f"skills/public/{name}/SKILL.md",
                "sha256": file_sha256(skill_md),
            }
            for name, skill_md in skills
        ),
        key=lambda entry: entry["name"],
    )

    host_files: dict[str, list[tuple[str, str]]] = {identity: [] for identity in HOST_IDENTITIES}

    generic = pack_dir / "generic"
    for dst in _generate_host_skills(generic, skills):
        host_files["generic"].append((dst.relative_to(pack_dir).as_posix(), file_sha256(dst)))
    for notice in _generate_host_notices(generic, repo_root):
        host_files["generic"].append((notice.relative_to(pack_dir).as_posix(), file_sha256(notice)))
    for dst in _generate_recipes_copy(generic, repo_root, "recipes"):
        host_files["generic"].append((dst.relative_to(pack_dir).as_posix(), file_sha256(dst)))
    _write_text(generic / "README.md", _pack_readme())
    host_files["generic"].append(("generic/README.md", file_sha256(generic / "README.md")))

    claude = pack_dir / "claude"
    for dst in _generate_host_skills(claude, skills):
        host_files["claude"].append((dst.relative_to(pack_dir).as_posix(), file_sha256(dst)))
    for notice in _generate_host_notices(claude, repo_root):
        host_files["claude"].append((notice.relative_to(pack_dir).as_posix(), file_sha256(notice)))
    for dst in _generate_recipes_copy(claude, repo_root, "references"):
        host_files["claude"].append((dst.relative_to(pack_dir).as_posix(), file_sha256(dst)))
    _write_text(claude / "README.md", _claude_readme())
    host_files["claude"].append(("claude/README.md", file_sha256(claude / "README.md")))

    codex = pack_dir / "codex"
    for dst in _generate_host_skills(codex, skills):
        host_files["codex"].append((dst.relative_to(pack_dir).as_posix(), file_sha256(dst)))
    for notice in _generate_host_notices(codex, repo_root):
        host_files["codex"].append((notice.relative_to(pack_dir).as_posix(), file_sha256(notice)))
    for dst in _generate_recipes_copy(codex, repo_root, "recipes"):
        host_files["codex"].append((dst.relative_to(pack_dir).as_posix(), file_sha256(dst)))
    _write_text(codex / "README.md", _codex_readme())
    host_files["codex"].append(("codex/README.md", file_sha256(codex / "README.md")))

    plugins = pack_dir / "agent-plugins"
    for dst in _generate_host_skills(plugins, skills, skills_subdir="skills"):
        host_files["agent-plugins"].append((dst.relative_to(pack_dir).as_posix(), file_sha256(dst)))
    for notice in _generate_host_notices(plugins, repo_root):
        host_files["agent-plugins"].append((notice.relative_to(pack_dir).as_posix(), file_sha256(notice)))
    # Recipe parity (review F2): every host form ships the recipes; agent-plugins
    # carries them under references/ (an Agent Skills convention for skill
    # support files), so the vendored skills' recipe references resolve.
    for dst in _generate_recipes_copy(plugins, repo_root, "references"):
        host_files["agent-plugins"].append((dst.relative_to(pack_dir).as_posix(), file_sha256(dst)))
    _write_text(plugins / "plugin.json", json.dumps(_plugin_json(), indent=2, sort_keys=True) + "\n")
    host_files["agent-plugins"].append(("agent-plugins/plugin.json", file_sha256(plugins / "plugin.json")))
    _write_text(plugins / "README.md", _agent_plugins_readme())
    host_files["agent-plugins"].append(("agent-plugins/README.md", file_sha256(plugins / "README.md")))

    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "skill_pack_version": SKILL_PACK_VERSION,
        "implementation_version": __version__,
        "standard_versions_supported": dict(STANDARD_VERSIONS_SUPPORTED),
        "canonical_source_sha256": tree_hash(files),
        "skills": skill_entries,
        "recipes": recipe_paths,
        "hosts": [
            {
                "identity": identity,
                "files": [{"path": rel, "sha256": sha} for rel, sha in sorted(host_files[identity])],
            }
            for identity in HOST_IDENTITIES
        ],
        "generated_at": now,
        "source_commit": source_commit,
        "packager_version": PACKAGER_VERSION,
    }

    violations = validate_manifest_schema(manifest, repo_root)
    if violations:
        raise ValueError(
            "generated manifest fails the registered schema "
            f"({MANIFEST_SCHEMA_VERSION}):\n" + "\n".join(f"  - {v}" for v in violations)
        )

    _write_text(
        pack_dir / "skill-pack-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    return manifest


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _replace_staged_pack(staged: Path, destination: Path) -> None:
    """Atomically install ``staged`` while retaining rollback on install failure."""
    backup: Path | None = None
    if destination.exists():
        backup = Path(tempfile.mkdtemp(prefix=f".{destination.name}.backup-", dir=destination.parent))
        backup.rmdir()
        os.replace(destination, backup)
    try:
        os.replace(staged, destination)
    except BaseException:
        if backup is not None and not destination.exists():
            os.replace(backup, destination)
        raise
    if backup is not None:
        _remove_path(backup)


def generate_pack(repo_root: Path, pack_dir: Path, *, now: str, source_commit: str) -> dict[str, Any]:
    """Write a deterministic skill pack under ``pack_dir``; returns the manifest dict.

    Generation is fully materialized and schema-validated in a sibling staging
    directory. The destination is replaced only after successful validation.
    ``now`` must be an RFC 3339 date-time (never a date-only value).
    """
    destination = pack_dir.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        manifest = _generate_pack_contents(
            repo_root, staged, now=now, source_commit=source_commit
        )
        _replace_staged_pack(staged, destination)
        return manifest
    except BaseException:
        if staged.exists():
            _remove_path(staged)
        raise


def write_pack(repo_root: Path, pack_dir: Path, *, now: str, source_commit: str) -> dict[str, Any]:
    """Replace ``pack_dir`` with a fresh deterministic pack after validation.

    Generation is staged in a sibling temporary directory, so an invalid
    timestamp, schema failure, or source-generation error leaves an existing
    destination untouched. Refuses to touch anything outside a ``skill-pack``
    directory by name.
    """
    resolved = pack_dir.resolve()
    repo = repo_root.resolve()
    if resolved == repo or resolved in repo.parents:
        raise UsageError(
            f"refusing to replace {pack_dir}: it is the repo root or an ancestor of it"
        )
    if resolved.name != "skill-pack":
        raise UsageError(f"refusing to replace {pack_dir}: expected a directory named skill-pack")
    return generate_pack(repo_root, resolved, now=now, source_commit=source_commit)


def commit_timestamp(repo_root: Path, commit: str) -> str:
    """Committer timestamp (RFC 3339) of ``commit``, deterministically."""
    proc = subprocess.run(
        ["git", "show", "-s", "--format=%cI", commit],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise UsageError(f"cannot read commit timestamp for {commit!r}")
    return proc.stdout.strip()


def git_source_identity(repo_root: Path) -> tuple[str, str]:
    """``(source_commit, generated_at)`` from the repo HEAD, deterministically.

    ``generated_at`` defaults to the source commit's committer timestamp, so a
    pack regenerated at the same commit is byte-identical. ``SOURCE_COMMIT``
    overrides the commit (for detached or dirty workflows).
    """
    source_commit = os.environ.get("SOURCE_COMMIT")
    if source_commit is None:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=False
        )
        if proc.returncode != 0:
            raise UsageError("cannot read HEAD; pass --source-commit or set SOURCE_COMMIT")
        source_commit = proc.stdout.strip()
    return source_commit, commit_timestamp(repo_root, source_commit)


def find_repo_root(start: Path) -> Path:
    """Nearest ancestor of ``start`` holding the canonical ATS skill source."""
    for candidate in [start, *start.parents]:
        if (candidate / "skills" / "public").is_dir() and (candidate / CANONICAL_RECIPES_PATH).is_file():
            return candidate
    raise UsageError(
        f"cannot find the ATS canonical source (skills/public/ and {CANONICAL_RECIPES_PATH}) "
        "from here; pass --repo"
    )


# -- verification -------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One typed verification finding."""

    code: str
    message: str
    file: str | None = None

    def to_dict(self) -> dict[str, str]:
        out: dict[str, str] = {"code": self.code, "message": self.message}
        if self.file is not None:
            out["file"] = self.file
        return out


def _uses_symlink(root: Path, relative: Path) -> bool:
    """Whether any component below ``root`` is a symlink."""
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _distributed_files(pack_dir: Path, manifest: dict[str, Any]) -> list[Path]:
    """Contained host files the manifest enumerates, in manifest order."""
    out: list[Path] = []
    pack_root = pack_dir.resolve()
    hosts = manifest.get("hosts")
    if not isinstance(hosts, list):
        return out
    for host in hosts:
        if not isinstance(host, dict):
            continue
        entries = host.get("files")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            rel = entry.get("path")
            if not isinstance(rel, str):
                continue
            rel_path = Path(rel)
            if rel_path.is_absolute() or ".." in rel_path.parts:
                continue
            if _uses_symlink(pack_dir, rel_path):
                continue
            path = pack_dir / rel_path
            try:
                path.resolve().relative_to(pack_root)
            except (OSError, RuntimeError, ValueError):
                continue
            out.append(path)
    return out


def verify_pack(pack_dir: Path, repo_root: Path) -> list[Finding]:
    """Deterministically verify a generated pack against its manifest.

    Checks, each with a typed finding code:

    - PACK / MANIFEST — the pack directory and manifest exist and parse.
    - MANIFEST-SCHEMA / MANIFEST-REGISTRATION — schema-valid and registered.
    - MANIFEST-VERSION / STANDARD-VERSIONS — version identity fields.
    - MANIFEST-TIMESTAMP — ``generated_at`` is RFC 3339.
    - SKILLS-* — the four required public skills exist (manifest, canonical
      source, and generic pack).
    - TREE-HASH — canonical source identity matches the manifest.
    - RECIPES-LIST / RECIPE-STANDALONE — manifest recipe provenance matches
      canonical source; every host-local recipe target exists inside the pack.
    - LAWS-MISSING — all ten mini-constitution phrases in every skill.
    - PACK-SYMLINK / HOSTS-* / HOST-SYMLINK / HOST-PATH-ESCAPE — the pack
      contains no symlinks, the four host identities exist, every enumerated
      file is regular, contained by the pack, present with the manifest
      SHA-256, and every host skill is byte-identical to the canonical file.
    - HOST-REGEN-DRIFT — regenerating in a temp dir at the manifest's own
      timestamp/commit reproduces the pack byte-for-byte.
    - SOURCE-COMMIT — the recorded ``source_commit`` reproduces the manifest's
      canonical-source tree hash (byte-level cross-check via ``git show``;
      review F1 hardening — a commit that predates or omits the canonical
      source fails even though it exists in git).
    - RECIPE-REF / INTERNAL-REF / FIXTURE-REF — referenced files resolve.
    - ABS-PATH — no local developer absolute paths.
    - PRIVATE-FLEET-DEP — no private fleet identifiers in distributed public-pack files.
    - DRAFT1-DEFAULT — no stale draft.1 new-authoring default.
    - ESCALATION — no conflicting human-escalation instructions.
    - PASS-ABSENCE — no PASS-by-absence language.
    - AGENT-PLUGINS-* — plugin.json fields and the skills/ layout.
    """
    findings: list[Finding] = []

    if not pack_dir.is_dir():
        return [Finding("PACK-MISSING", f"pack directory not found: {pack_dir}")]

    manifest_path = pack_dir / "skill-pack-manifest.json"
    if manifest_path.is_symlink():
        return [
            Finding(
                "MANIFEST-SYMLINK",
                "skill-pack-manifest.json must not be a symlink",
                file="skill-pack-manifest.json",
            )
        ]
    if not manifest_path.is_file():
        return [Finding("MANIFEST-MISSING", f"manifest not found at {manifest_path}")]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [Finding("MANIFEST-PARSE", f"manifest is not valid JSON: {exc}", file="skill-pack-manifest.json")]
    if not isinstance(manifest, dict):
        return [Finding("MANIFEST-PARSE", "manifest root is not a JSON object")]

    # -- schema -----------------------------------------------------------------
    for candidate in pack_dir.rglob("*"):
        if candidate.is_symlink():
            findings.append(
                Finding(
                    "PACK-SYMLINK",
                    "generated pack files must not be symlinks",
                    file=candidate.relative_to(pack_dir).as_posix(),
                )
            )
    for violation in validate_manifest_schema(manifest, repo_root):
        findings.append(
            Finding("MANIFEST-SCHEMA", f"manifest schema violation: {violation}", file="skill-pack-manifest.json")
        )
    registered_id = SCHEMA_FOR_VERSION.get(MANIFEST_SCHEMA_VERSION)
    if registered_id != MANIFEST_SCHEMA_ID:
        findings.append(
            Finding(
                "MANIFEST-REGISTRATION",
                f"SCHEMA_FOR_VERSION[{MANIFEST_SCHEMA_VERSION!r}] = {registered_id!r}, expected {MANIFEST_SCHEMA_ID!r}",
            )
        )

    # -- identity ---------------------------------------------------------------
    if manifest.get("skill_pack_version") != SKILL_PACK_VERSION:
        findings.append(
            Finding(
                "MANIFEST-VERSION",
                f"skill_pack_version {manifest.get('skill_pack_version')!r} != {SKILL_PACK_VERSION!r}",
            )
        )
    if manifest.get("implementation_version") != __version__:
        findings.append(
            Finding(
                "MANIFEST-VERSION",
                f"implementation_version {manifest.get('implementation_version')!r} != {__version__!r}",
            )
        )
    if manifest.get("packager_version") != PACKAGER_VERSION:
        findings.append(
            Finding(
                "MANIFEST-VERSION",
                f"packager_version {manifest.get('packager_version')!r} != {PACKAGER_VERSION!r}",
            )
        )
    if manifest.get("standard_versions_supported") != STANDARD_VERSIONS_SUPPORTED:
        findings.append(
            Finding(
                "STANDARD-VERSIONS",
                f"standard_versions_supported {manifest.get('standard_versions_supported')!r} "
                f"!= {STANDARD_VERSIONS_SUPPORTED!r} (new authoring must be {STANDARD_VERSIONS_SUPPORTED['new_authoring']})",
            )
        )
    generated_at = manifest.get("generated_at")
    if isinstance(generated_at, str):
        if not _is_rfc3339_datetime(generated_at):
            findings.append(
                Finding("MANIFEST-TIMESTAMP", f"generated_at {generated_at!r} is not RFC 3339 date-time")
            )
    else:
        findings.append(Finding("MANIFEST-TIMESTAMP", f"generated_at missing or not a string: {generated_at!r}"))

    # -- required skills ---------------------------------------------------------
    manifest_skills = manifest.get("skills")
    manifest_skill_names = (
        {entry.get("name") for entry in manifest_skills} if isinstance(manifest_skills, list) else set()
    )
    for name in REQUIRED_SKILLS:
        if name not in manifest_skill_names:
            findings.append(Finding("SKILLS-REQUIRED", f"required public skill {name!r} missing from manifest.skills"))
        canonical = repo_root / "skills" / "public" / name / "SKILL.md"
        if not canonical.is_file():
            findings.append(Finding("SKILLS-SOURCE", f"canonical source missing: skills/public/{name}/SKILL.md"))
        if not (pack_dir / "generic" / name / "SKILL.md").is_file():
            findings.append(Finding("SKILLS-PACK", f"generic/{name}/SKILL.md missing from the pack"))

    # -- canonical source identity ------------------------------------------------
    computed_tree = tree_hash(canonical_source_files(repo_root))
    if manifest.get("canonical_source_sha256") != computed_tree:
        findings.append(
            Finding(
                "TREE-HASH",
                f"canonical_source_sha256 {manifest.get('canonical_source_sha256')!r} != recomputed {computed_tree!r}",
            )
        )
    if manifest.get("recipes") != _canonical_recipe_paths(repo_root):
        findings.append(
            Finding(
                "RECIPES-LIST",
                f"manifest recipes {manifest.get('recipes')!r} != canonical {_canonical_recipe_paths(repo_root)!r}",
            )
        )

    # -- governing laws ------------------------------------------------------------
    for name in REQUIRED_SKILLS:
        skill_md = pack_dir / "generic" / name / "SKILL.md"
        skill_rel = Path("generic") / name / "SKILL.md"
        if _uses_symlink(pack_dir, skill_rel):
            continue  # reported under HOST-SYMLINK
        if not skill_md.is_file():
            continue  # already reported under SKILLS-PACK
        text = _norm(skill_md.read_text(encoding="utf-8"))
        missing = [law for law in MINI_CONSTITUTION if law not in text]
        if missing:
            findings.append(
                Finding(
                    "LAWS-MISSING",
                    f"missing mini-constitution laws: {missing}",
                    file=f"generic/{name}/SKILL.md",
                )
            )

    # -- hosts ----------------------------------------------------------------------
    manifest_hosts = manifest.get("hosts")
    host_by_identity: dict[str, dict[str, Any]] = {}
    if isinstance(manifest_hosts, list):
        for host in manifest_hosts:
            if isinstance(host, dict):
                host_by_identity[host.get("identity", "")] = host
    # -- standalone recipe layout -------------------------------------------------
    # Manifest recipe sources are canonical provenance paths; installed hosts
    # must nevertheless carry each basename in their host-specific recipe dir.
    manifest_recipes = manifest.get("recipes")
    recipe_basenames = (
        sorted({Path(rel).name for rel in manifest_recipes if isinstance(rel, str)})
        if isinstance(manifest_recipes, list)
        else []
    )
    pack_root = pack_dir.resolve()
    for identity in host_by_identity:
        recipe_dir = HOST_RECIPE_DIRECTORIES.get(identity)
        if recipe_dir is None:
            continue
        readme_rel = Path(identity) / "README.md"
        readme = pack_dir / readme_rel
        layout_marker = f"`{recipe_dir}/`"
        if _uses_symlink(pack_dir, readme_rel):
            findings.append(
                Finding(
                    "RECIPE-STANDALONE",
                    f"host {identity} README must not use symlinks",
                    file=f"{identity}/README.md",
                )
            )
        elif not readme.is_file() or layout_marker not in readme.read_text(encoding="utf-8"):
            findings.append(
                Finding(
                    "RECIPE-STANDALONE",
                    f"host {identity} README does not identify installed recipe directory {recipe_dir}/",
                    file=f"{identity}/README.md",
                )
            )
        for basename in recipe_basenames:
            target = pack_dir / identity / recipe_dir / basename
            target_rel = Path(identity) / recipe_dir / basename
            if _uses_symlink(pack_dir, target_rel):
                findings.append(
                    Finding(
                        "RECIPE-STANDALONE",
                        f"host {identity} recipe target must not use symlinks: {recipe_dir}/{basename}",
                        file=f"{identity}/{recipe_dir}/{basename}",
                    )
                )
                continue
            try:
                target.resolve().relative_to(pack_root)
            except (OSError, RuntimeError, ValueError):
                findings.append(
                    Finding(
                        "RECIPE-STANDALONE",
                        f"host {identity} recipe target escapes the installed pack: {recipe_dir}/{basename}",
                        file=f"{identity}/{recipe_dir}/{basename}",
                    )
                )
                continue
            if not target.is_file():
                findings.append(
                    Finding(
                        "RECIPE-STANDALONE",
                        f"host {identity} missing installed recipe {recipe_dir}/{basename}",
                        file=f"{identity}/{recipe_dir}/{basename}",
                    )
                )

    for identity in HOST_IDENTITIES:
        if identity not in host_by_identity:
            findings.append(Finding("HOSTS-REQUIRED", f"host identity {identity!r} missing from manifest.hosts"))
    for identity, host in host_by_identity.items():
        if identity not in HOST_IDENTITIES:
            findings.append(Finding("HOSTS-UNKNOWN", f"unexpected host identity {identity!r} in manifest.hosts"))
            continue
        host_root = pack_dir / identity
        if host_root.is_symlink():
            findings.append(
                Finding("HOST-SYMLINK", "host root must not be a symlink", file=identity)
            )
        elif host_root.is_dir():
            for candidate in host_root.rglob("*"):
                if candidate.is_symlink():
                    findings.append(
                        Finding(
                            "HOST-SYMLINK",
                            "generated host files must not be symlinks",
                            file=candidate.relative_to(pack_dir).as_posix(),
                        )
                    )
        entries = host.get("files")
        if not isinstance(entries, list):
            findings.append(
                Finding("HOSTS-MALFORMED", f"host {identity}: files must be an array")
            )
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                findings.append(
                    Finding("HOSTS-MALFORMED", f"host {identity}: file entry must be an object")
                )
                continue
            rel = entry.get("path")
            if not isinstance(rel, str):
                findings.append(Finding("HOSTS-MALFORMED", f"host {identity}: file entry without a path"))
                continue
            rel_path = Path(rel)
            if rel_path.is_absolute() or ".." in rel_path.parts:
                findings.append(
                    Finding(
                        "HOST-PATH-ESCAPE",
                        f"enumerated host file path must be pack-relative: {rel}",
                        file=rel,
                    )
                )
                continue
            path = pack_dir / rel_path
            if _uses_symlink(pack_dir, rel_path):
                continue
            try:
                path.resolve().relative_to(pack_root)
            except (OSError, RuntimeError, ValueError):
                findings.append(
                    Finding(
                        "HOST-PATH-ESCAPE",
                        f"enumerated host file cannot resolve inside the installed pack: {rel}",
                        file=rel,
                    )
                )
                continue
            if not path.is_file():
                findings.append(Finding("HOST-FILE-MISSING", f"enumerated file not found: {rel}", file=rel))
                continue
            if file_sha256(path) != entry.get("sha256"):
                findings.append(Finding("HOST-FILE-HASH", f"sha256 mismatch for {rel}", file=rel))
        for destination, source in HOST_NOTICE_SOURCES:
            notice_rel = Path(identity) / destination
            if _uses_symlink(pack_dir, notice_rel):
                continue
            notice = pack_dir / notice_rel
            canonical_notice = repo_root / source
            if not notice.is_file():
                findings.append(
                    Finding(
                        "HOST-NOTICE-MISSING",
                        f"host {identity} missing required notice {destination}",
                        file=f"{identity}/{destination}",
                    )
                )
            elif not canonical_notice.is_file() or notice.read_bytes() != canonical_notice.read_bytes():
                findings.append(
                    Finding(
                        "HOST-NOTICE-PARITY",
                        f"host {identity} notice {destination} differs from canonical {source}",
                        file=f"{identity}/{destination}",
                    )
                )
        if identity in ("generic", "claude", "codex"):
            for name in REQUIRED_SKILLS:
                skill_rel = Path(identity) / name / "SKILL.md"
                if _uses_symlink(pack_dir, skill_rel):
                    continue
                path = pack_dir / skill_rel
                canonical = repo_root / "skills" / "public" / name / "SKILL.md"
                if path.is_file() and canonical.is_file() and path.read_bytes() != canonical.read_bytes():
                    findings.append(
                        Finding(
                            "HOST-PARITY",
                            f"host {identity} skill diverges from canonical",
                            file=f"{identity}/{name}/SKILL.md",
                        )
                    )
        if identity == "agent-plugins":
            findings.extend(_verify_agent_plugins(pack_dir / "agent-plugins", repo_root))

    # -- regeneration drift -----------------------------------------------------------
    try:
        with tempfile.TemporaryDirectory(prefix="ats-pack-verify-") as tmp:
            tmp_pack = Path(tmp) / "skill-pack"
            generate_pack(repo_root, tmp_pack, now=generated_at or "", source_commit=manifest.get("source_commit") or "")
            for rel, kind in _diff_trees(pack_dir, tmp_pack):
                findings.append(Finding("HOST-REGEN-DRIFT", f"{rel}: {kind}", file=rel))
    except (ValueError, UsageError) as exc:
        findings.append(Finding("HOST-REGEN-DRIFT", f"regeneration failed: {exc}"))

    # -- provenance ----------------------------------------------------------------
    # Review F1: the recorded source_commit must actually contain the canonical
    # source, or the 'reproducible from this commit' claim is false. The check
    # is a tree-hash cross-check, not an existence check: the canonical-source
    # blobs at the recorded commit must hash to the manifest's
    # canonical_source_sha256 (a pack generated from a commit that predates or
    # omits the canonical source fails even if the commit exists).
    recorded = manifest.get("source_commit")
    if isinstance(recorded, str) and recorded:
        ok = False
        try:
            digest = hashlib.sha256()
            missing = []
            for rel in sorted(canonical_source_files(repo_root)):
                shown = subprocess.run(
                    ["git", "show", f"{recorded}:{rel}"],
                    cwd=repo_root,
                    capture_output=True,
                )
                if shown.returncode != 0:
                    missing.append(rel)
                    continue
                blob_sha = hashlib.sha256(shown.stdout).hexdigest()
                digest.update(rel.encode("utf-8"))
                digest.update(b"\0")
                digest.update(blob_sha.encode("ascii"))
                digest.update(b"\0")
            manifest_tree = manifest.get("canonical_source_sha256")
            ok = (
                not missing
                and isinstance(manifest_tree, str)
                and digest.hexdigest() == manifest_tree
            )
        except (OSError, subprocess.SubprocessError):
            ok = False
        if not ok:
            findings.append(
                Finding(
                    "SOURCE-COMMIT",
                    f"recorded source_commit {recorded!r} does not reproduce the "
                    "manifest's canonical_source_sha256 (missing canonical files "
                    f"{missing[:3]} or tree-hash mismatch); the pack cannot be "
                    "reproduced from it",
                    file="skill-pack-manifest.json",
                )
            )

    # -- distributed file content checks ------------------------------------------------
    for path in _distributed_files(pack_dir, manifest):
        if not path.is_file():
            continue  # already reported under HOST-FILE-MISSING
        rel = path.relative_to(pack_dir).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        findings.extend(_recipe_reference_findings(text, rel, repo_root))
        findings.extend(_internal_reference_findings(text, rel, repo_root))
        findings.extend(_absolute_path_findings(text, rel, repo_root))
        findings.extend(_stale_draft1_findings(text, rel))
        findings.extend(_escalation_findings(text, rel))
        findings.extend(_pass_absence_findings(text, rel))
        findings.extend(_private_fleet_findings(text, rel))

    return findings


def _diff_trees(left: Path, right: Path) -> list[tuple[str, str]]:
    """Relative paths whose bytes differ, plus files present on only one side."""

    def index(root: Path) -> dict[str, bytes]:
        root_resolved = root.resolve()
        files: dict[str, bytes] = {}
        for path in root.rglob("*"):
            if path.is_symlink():
                continue
            try:
                path.resolve().relative_to(root_resolved)
            except (OSError, RuntimeError, ValueError):
                continue
            if path.is_file():
                files[path.relative_to(root).as_posix()] = path.read_bytes()
        return files

    left_files = index(left)
    right_files = index(right)
    drift: list[tuple[str, str]] = []
    for rel in sorted(set(left_files) | set(right_files)):
        if rel not in right_files:
            drift.append((rel, "missing from regeneration"))
        elif rel not in left_files:
            drift.append((rel, "present only in regeneration"))
        elif left_files[rel] != right_files[rel]:
            drift.append((rel, "bytes differ"))
    return drift


def _recipe_reference_findings(text: str, rel: str, repo_root: Path) -> list[Finding]:
    """Recipe references (docs/ARTIFACT_RECIPES.md, skills/public/recipes/*) resolve."""
    findings: list[Finding] = []
    if CANONICAL_RECIPES_PATH in text and not (repo_root / CANONICAL_RECIPES_PATH).is_file():
        findings.append(Finding("RECIPE-REF", f"references {CANONICAL_RECIPES_PATH} which does not exist", file=rel))
    if PUBLIC_RECIPES_DIR in text and not (repo_root / PUBLIC_RECIPES_DIR).is_dir():
        findings.append(
            Finding("RECIPE-REF", f"references {PUBLIC_RECIPES_DIR} which does not exist", file=rel)
        )
    for file_ref in re.findall(r"skills/public/recipes/[\w.\-]+", text):
        if not (repo_root / file_ref).is_file():
            findings.append(Finding("RECIPE-REF", f"references {file_ref} which does not exist", file=rel))
    return findings


def _internal_reference_findings(text: str, rel: str, repo_root: Path) -> list[Finding]:
    """Internal skill references (ats-ir-author etc.) resolve to existing skills."""
    findings: list[Finding] = []
    for name in INTERNAL_SKILLS:
        if name in text and not (repo_root / "skills" / name / "SKILL.md").is_file():
            findings.append(
                Finding(
                    "INTERNAL-REF",
                    f"references internal skill {name!r} whose SKILL.md does not exist",
                    file=rel,
                )
            )
    if "fixtures/skills/review/" in text and not (repo_root / "fixtures" / "skills" / "review").is_dir():
        findings.append(Finding("FIXTURE-REF", "references fixtures/skills/review/ which does not exist", file=rel))
    return findings


def _absolute_path_findings(text: str, rel: str, repo_root: Path) -> list[Finding]:
    """No hard-coded local developer paths in distributed files."""
    findings: list[Finding] = []
    for prefix in _LOCAL_PATH_PREFIXES:
        if prefix in text:
            findings.append(Finding("ABS-PATH", f"contains local absolute path prefix {prefix!r}", file=rel))
    root_str = str(repo_root.resolve())
    if root_str in text:
        findings.append(Finding("ABS-PATH", f"contains the repo root path {root_str!r}", file=rel))
    return findings


def _stale_draft1_findings(text: str, rel: str) -> list[Finding]:
    """No instruction binding new authoring to the legacy draft.1 edition.

    Evaluate clause-local bindings rather than treating the mere presence of the
    current edition elsewhere on a line as exculpatory. This permits the canonical
    two-default construction (new authoring -> current edition; legacy -> draft.1)
    while still catching contradictory clauses that bind new authoring to draft.1.
    """
    findings: list[Finding] = []
    new_authoring = re.compile(r"new(?: durable)? authoring", re.IGNORECASE)
    clause_break = re.compile(r";|[!?](?=\s|$)|\.(?=\s+[A-Z]|\s*$)")
    for line in text.splitlines():
        for clause in clause_break.split(line):
            if new_authoring.search(clause) and "1.0.0-draft.1" in clause:
                findings.append(
                    Finding("DRAFT1-DEFAULT", "language ties new authoring to draft.1", file=rel)
                )
    return findings


def _escalation_findings(text: str, rel: str) -> list[Finding]:
    """Human escalation is allowed only for action-blocking unresolved semantics."""
    findings: list[Finding] = []
    escalate = re.compile(r"\b(?:ask|consult|escalate|contact|involve|call)\b[^.!?\n]{0,140}\bhuman\b", re.IGNORECASE)
    qualified = re.compile(
        r"(?:only when|only if|unless|\bnever\b|do not|non-blocking|block(?:s|ing|ed)?|"
        r"requires? resolution|blocks the action|blocks the requested)",
        re.IGNORECASE,
    )
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if escalate.search(sentence) and not qualified.search(sentence):
            findings.append(
                Finding(
                    "ESCALATION",
                    f"human escalation not gated on action-blocking unresolved semantics: {sentence[:120]!r}",
                    file=rel,
                )
            )
    return findings


def _pass_absence_findings(text: str, rel: str) -> list[Finding]:
    """No PASS-by-absence language."""
    findings: list[Finding] = []
    lowered = _norm(text.lower())
    for pattern in _PASS_BY_ABSENCE_PATTERNS:
        if re.search(pattern, lowered):
            findings.append(Finding("PASS-ABSENCE", f"PASS-by-absence language ({pattern!r})", file=rel))
    return findings


def _private_fleet_findings(text: str, rel: str) -> list[Finding]:
    """Reject private fleet identifiers in distributed public-pack files."""
    findings: list[Finding] = []
    for match in _PRIVATE_FLEET_RESIDUE.finditer(text):
        findings.append(
            Finding(
                "PRIVATE-FLEET-DEP",
                f"private fleet identifier {match.group(0)!r} in the public pack",
                file=rel,
            )
        )
    return findings


def _verify_agent_plugins(plugin_root: Path, repo_root: Path) -> list[Finding]:
    """agent-plugins.org checks: plugin.json fields, the skills/ layout, and
    recipe parity (review F2) — the vendored skills reference the recipes, so
    the plugin must ship them."""
    findings: list[Finding] = []
    if plugin_root.is_symlink():
        return [
            Finding(
                "AGENT-PLUGINS-SYMLINK",
                "agent-plugins root must not be a symlink",
                file="agent-plugins",
            )
        ]

    if plugin_root.is_dir():
        for path in plugin_root.rglob("*"):
            if path.is_symlink():
                findings.append(
                    Finding(
                        "AGENT-PLUGINS-SYMLINK",
                        "symlink inside the plugin root",
                        file=path.relative_to(plugin_root).as_posix(),
                    )
                )

    # Recipe parity: every host form ships the recipes; the agent-plugins host
    # carries them under references/ and must not drift from canonical.
    recipes_dir = plugin_root / "references"
    canonical_recipes = {
        rel: file_sha256(path)
        for rel, path in sorted(canonical_source_files(repo_root).items())
        if "ARTIFACT_RECIPES.md" in rel or rel.startswith("skills/public/recipes/")
    }
    for rel, sha in sorted(canonical_recipes.items()):
        vendored = recipes_dir / Path(rel).name
        vendored_rel = Path("references") / Path(rel).name
        if _uses_symlink(plugin_root, vendored_rel):
            continue
        if not vendored.is_file():
            findings.append(
                Finding(
                    "AGENT-PLUGINS-RECIPE",
                    f"recipe {rel} missing from the agent-plugins references/",
                    file="agent-plugins/references/" + Path(rel).name,
                )
            )
        elif file_sha256(vendored) != sha:
            findings.append(
                Finding(
                    "AGENT-PLUGINS-RECIPE",
                    f"recipe {rel} drifted from canonical",
                    file="agent-plugins/references/" + Path(rel).name,
                )
            )

    manifest_path = plugin_root / "plugin.json"
    if _uses_symlink(plugin_root, Path("plugin.json")):
        return findings
    if not manifest_path.is_file():
        return findings + [Finding("AGENT-PLUGINS-MANIFEST", "plugin.json missing at the agent-plugins root")]
    try:
        plugin = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return findings + [Finding("AGENT-PLUGINS-MANIFEST", f"plugin.json is not valid JSON: {exc}")]
    if not isinstance(plugin, dict):
        return findings + [Finding("AGENT-PLUGINS-MANIFEST", "plugin.json root is not a JSON object")]

    if plugin.get("$schema") != PLUGIN_SCHEMA_URL:
        findings.append(
            Finding(
                "AGENT-PLUGINS-SCHEMA",
                f"$schema {plugin.get('$schema')!r} != {PLUGIN_SCHEMA_URL!r}",
                file="agent-plugins/plugin.json",
            )
        )
    name = plugin.get("name")
    if (
        not isinstance(name, str)
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.\-]*[a-z0-9])?", name)
        or len(name) > 64
        or "--" in name
        or ".." in name
    ):
        findings.append(
            Finding(
                "AGENT-PLUGINS-NAME",
                f"plugin name {name!r} violates the 1-64 lowercase ASCII/hyphen/dot rule",
                file="agent-plugins/plugin.json",
            )
        )
    elif name != PLUGIN_NAME:
        findings.append(
            Finding("AGENT-PLUGINS-NAME", f"plugin name {name!r} != expected {PLUGIN_NAME!r}", file="agent-plugins/plugin.json")
        )
    if not isinstance(plugin.get("version"), str) or not plugin.get("version"):
        findings.append(
            Finding("AGENT-PLUGINS-VERSION", "plugin version must be a non-empty string", file="agent-plugins/plugin.json")
        )
    for field in ("description", "license"):
        value = plugin.get(field)
        if value is not None and not isinstance(value, str):
            findings.append(
                Finding("AGENT-PLUGINS-FIELD", f"plugin {field} must be a string when present", file="agent-plugins/plugin.json")
            )
    if plugin.get("license") != PLUGIN_LICENSE:
        findings.append(
            Finding(
                "AGENT-PLUGINS-LICENSE",
                f"plugin license {plugin.get('license')!r} != {PLUGIN_LICENSE!r}",
                file="agent-plugins/plugin.json",
            )
        )
    keywords = plugin.get("keywords")
    if keywords is not None and (not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords)):
        findings.append(
            Finding("AGENT-PLUGINS-FIELD", "plugin keywords must be an array of strings", file="agent-plugins/plugin.json")
        )

    skills_dir = plugin_root / "skills"
    if _uses_symlink(plugin_root, Path("skills")):
        return findings
    if not skills_dir.is_dir():
        return findings + [Finding("AGENT-PLUGINS-SKILLS", "skills/ missing at the plugin root")]
    children = {p.name for p in skills_dir.iterdir()}
    if children != set(REQUIRED_SKILLS):
        findings.append(
            Finding(
                "AGENT-PLUGINS-SKILLS",
                f"skills/ immediate children {sorted(children)} != the four required skills {list(REQUIRED_SKILLS)}",
            )
        )
    for name in REQUIRED_SKILLS:
        skill_md = skills_dir / name / "SKILL.md"
        skill_rel = Path("skills") / name / "SKILL.md"
        if _uses_symlink(plugin_root, skill_rel):
            continue
        canonical = repo_root / "skills" / "public" / name / "SKILL.md"
        if not skill_md.is_file():
            findings.append(
                Finding("AGENT-PLUGINS-SKILLS", f"skills/{name}/SKILL.md missing", file=f"agent-plugins/skills/{name}/SKILL.md")
            )
        elif canonical.is_file() and skill_md.read_bytes() != canonical.read_bytes():
            findings.append(
                Finding("AGENT-PLUGINS-PARITY", "skill diverges from canonical", file=f"agent-plugins/skills/{name}/SKILL.md")
            )
    return findings

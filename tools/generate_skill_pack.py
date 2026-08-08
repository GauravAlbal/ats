#!/usr/bin/env python3
"""Deterministic ATS public skill-pack generator (contract §6).

Usage:
    python tools/generate_skill_pack.py [--repo REPO] [--out dist/skill-pack]
        [--now RFC3339-DATETIME] [--source-commit SHA]

The pack is a pure function of the canonical source bytes, repository-root
``LICENSE`` bytes, the source commit, and the generation timestamp. Regenerating
at the same commit (or with the same --now and --source-commit) must produce
zero diff. The manifest is schema-validated in a sibling staging directory; the
destination is replaced atomically only after complete successful materialization.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ats.skill_pack import (  # noqa: E402
    commit_timestamp,
    git_source_identity,
    write_pack,
)
from ats.errors import UsageError  # noqa: E402
from ats.spec_package import REPO_ROOT  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo", default=None, help="canonical source repo root (default: the ats package repo)"
    )
    parser.add_argument(
        "--out", default=None, help="output pack directory (default: <repo>/dist/skill-pack)"
    )
    parser.add_argument(
        "--now", default=None, help="RFC 3339 date-time generated_at (default: source commit timestamp)"
    )
    parser.add_argument(
        "--source-commit", default=None, help="source commit (default: git HEAD or SOURCE_COMMIT env)"
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).resolve() if args.repo else REPO_ROOT
    if args.source_commit:
        source_commit = args.source_commit
        commit_now = commit_timestamp(repo_root, source_commit)
    else:
        source_commit, commit_now = git_source_identity(repo_root)
    now = args.now or commit_now

    out_dir = Path(args.out).resolve() if args.out else repo_root / "dist" / "skill-pack"
    try:
        manifest = write_pack(repo_root, out_dir, now=now, source_commit=source_commit)
    except (UsageError, ValueError) as exc:  # schema failures and usage errors
        print(f"error: {exc}", file=sys.stderr)
        return 1

    summary = {
        "pack_dir": str(out_dir),
        "manifest": str(out_dir / "skill-pack-manifest.json"),
        "canonical_source_sha256": manifest["canonical_source_sha256"],
        "source_commit": source_commit,
        "generated_at": now,
        "skill_pack_version": manifest["skill_pack_version"],
        "implementation_version": manifest["implementation_version"],
        "packager_version": manifest["packager_version"],
        "skills": [entry["name"] for entry in manifest["skills"]],
        "recipes": manifest["recipes"],
        "hosts": [host["identity"] for host in manifest["hosts"]],
        "files": sum(len(host["files"]) for host in manifest["hosts"]) + 1,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

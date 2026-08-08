"""Focused tests for the public publication checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from validate_repo import (  # noqa: E402
    check_public_dependencies,
    check_public_disclosure_surface,
    check_skill_pack,
)


def test_public_dependency_audit_passes_current_tree() -> None:
    result = check_public_dependencies(REPO_ROOT)
    assert result.ok, result.detail


def test_public_dependency_audit_rejects_private_checkout_path(tmp_path: Path) -> None:
    runtime = tmp_path / "src" / "ats" / "private_adapter.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_text(
        'CHECKOUT = "' + "/" + "Users/example/private-project/config/fleet.json" + '"\n',
        encoding="utf-8",
    )

    result = check_public_dependencies(tmp_path)

    assert not result.ok
    assert "private/developer checkout path" in result.detail


def test_public_dependency_audit_rejects_private_fleet_token_in_runtime_config(
    tmp_path: Path,
) -> None:
    policy = tmp_path / "config" / "policies" / "fleet_policy.json"
    policy.parent.mkdir(parents=True)
    policy.write_text(
        '{"repository_overrides": [{"repository": "arq"}]}\n',
        encoding="utf-8",
    )

    result = check_public_dependencies(tmp_path)

    assert not result.ok
    assert "private fleet token" in result.detail



def test_public_dependency_audit_rejects_private_build_package(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["arq>=1.0"]\n',
        encoding="utf-8",
    )

    result = check_public_dependencies(tmp_path)

    assert not result.ok
    assert "private build dependency" in result.detail



@pytest.mark.parametrize(
    ("filename", "content", "reason"),
    (
        (
            "users.md",
            "/" + "Users" + "/galbal/project",
            "absolute host path",
        ),
        (
            "home.md",
            "\\" + "HOME" + "\\galbal\\project",
            "absolute host path",
        ),
        (
            "private.md",
            "/" + "private" + "/var/lib/receipt",
            "absolute host path",
        ),
        (
            "repository.md",
            "checkout: ats-" + "internal",
            "private repository identifier",
        ),
        (
            "pilot.md",
            "source: " + "CORPUS" + "\\" + "PILOT-0" + "\\record.json",
            "denied pilot corpus path",
        ),
        (
            "authority.md",
            "source: " + "corpus" + "/" + "authority\\private-sample",
            "denied authority corpus path",
        ),
        (
            "pearls.md",
            "receipt: foo/" + "." + "PEARLS" + "/wal",
            "private operator state path",
        ),
        (
            "email.md",
            "contact: GALBAL" + "@" + "COMCAST.NET",
            "operator credential/email residue",
        ),
        (
            "directive-citation.md",
            "see directive " + "§" + "7",
            "unavailable private authority citation",
        ),
        (
            "program-citation.md",
            "see program " + "directive",
            "unavailable private authority citation",
        ),
        (
            "operator-citation.md",
            "see operator " + "directive",
            "unavailable private authority citation",
        ),
        (
            "local-citation.md",
            "source: " + "local://" + "paste-private-authority",
            "unavailable private authority citation",
        ),
    ),
)
def test_public_disclosure_surface_rejects_concrete_residue(
    tmp_path: Path,
    filename: str,
    content: str,
    reason: str,
) -> None:
    path = tmp_path / "docs" / "nested" / filename
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")

    result = check_public_disclosure_surface(tmp_path)

    assert not result.ok
    assert f"docs/nested/{filename}" in result.detail
    assert reason in result.detail


def test_public_disclosure_surface_scans_committed_dist(tmp_path: Path) -> None:
    path = tmp_path / "dist" / "skill-pack" / "nested" / "manifest.txt"
    path.parent.mkdir(parents=True)
    path.write_text("owner: " + "galbal" + "@" + "comcast.net", encoding="utf-8")

    result = check_public_disclosure_surface(tmp_path)

    assert not result.ok
    assert "dist/skill-pack/nested/manifest.txt" in result.detail
    assert "operator credential/email residue" in result.detail



def test_public_disclosure_surface_scans_public_root_files(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("owner: " + "galbal" + "@" + "comcast.net", encoding="utf-8")

    result = check_public_disclosure_surface(tmp_path)

    assert not result.ok
    assert "README.md" in result.detail
    assert "operator credential/email residue" in result.detail


def test_public_disclosure_surface_rejects_reachable_commit_metadata(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init", "-b", "master"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Private Author"], cwd=tmp_path, check=True
    )
    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "galbal" + "@" + "comcast.net",
        ],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "README.md").write_text("Public source.\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Seed source"], cwd=tmp_path, check=True)

    result = check_public_disclosure_surface(tmp_path)

    assert not result.ok
    assert "reachable Git commit" in result.detail
    assert "operator credential/email residue" in result.detail


def test_public_disclosure_surface_rejects_reachable_tag_metadata(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init", "-b", "master"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Public Author"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "157336828+GauravAlbal@users.noreply.github.com",
        ],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "README.md").write_text("Public source.\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Seed source"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "galbal" + "@" + "comcast.net"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "tag", "-a", "v1", "-m", "Release"], cwd=tmp_path, check=True
    )

    result = check_public_disclosure_surface(tmp_path)

    assert not result.ok
    assert "reachable Git tag refs/tags/v1" in result.detail
    assert "operator credential/email residue" in result.detail


def test_public_disclosure_surface_allows_exact_gitignore_pearls_exclusion(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".gitignore"
    path.write_text("." + "pearls" + "/\n", encoding="utf-8")

    result = check_public_disclosure_surface(tmp_path)

    assert result.ok, result.detail


def test_public_disclosure_surface_rejects_pearls_outside_gitignore(
    tmp_path: Path,
) -> None:
    path = tmp_path / "README.md"
    path.write_text("receipt: " + "." + "pearls" + "/wal\n", encoding="utf-8")

    result = check_public_disclosure_surface(tmp_path)

    assert not result.ok
    assert "README.md" in result.detail
    assert "private operator state path" in result.detail


def test_public_disclosure_surface_allows_generic_privacy_and_integrations(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".github" / "workflows" / "publish.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "This internal workflow keeps private data out of the public report.\n"
        "Optional Arq, Tribunal, Sear, VX, and Moat integrations are supported.\n",
        encoding="utf-8",
    )

    result = check_public_disclosure_surface(tmp_path)

    assert result.ok, result.detail


def test_public_disclosure_surface_ignores_cache_and_venv_files(tmp_path: Path) -> None:
    for relative in ("docs/cache/leak.md", "tests/.venv/leak.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        path.write_text(
            "/" + "Users" + "/galbal/project and " + "galbal" + "@" + "comcast.net",
            encoding="utf-8",
        )

    result = check_public_disclosure_surface(tmp_path)

    assert result.ok, result.detail




def test_public_skill_pack_gate_passes_current_pack() -> None:
    result = check_skill_pack(REPO_ROOT)
    assert result.ok, result.detail
    assert "zero-diff regeneration" in result.detail

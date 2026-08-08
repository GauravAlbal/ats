"""Regression tests for the current ATS public naming surface."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from ats.cli import build_parser


REPO_ROOT = Path(__file__).resolve().parents[2]
CURRENT_PUBLIC_IDENTITY = "Applied Technical Semantics"
HISTORICAL_EXPANSION = "Arq Text Standard"


def test_cli_help_uses_the_current_public_identity() -> None:
    help_text = build_parser().format_help()
    assert CURRENT_PUBLIC_IDENTITY in help_text
    assert HISTORICAL_EXPANSION not in help_text


def test_package_metadata_uses_the_current_public_identity() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert CURRENT_PUBLIC_IDENTITY in project["description"]
    assert HISTORICAL_EXPANSION not in project["description"]


@pytest.mark.parametrize(
    "relative_path",
    [
        "README.md",
        "docs/NORTH_STAR.md",
        "docs/ARCHITECTURE.md",
        "docs/AUTHORITY_MODEL.md",
        "docs/SKILL_CONTRACTS.md",
        "docs/LINEAGE_AND_PRIOR_ART.md",
        "docs/EVIDENCE.md",
        "skills/public/ats/SKILL.md",
        "skills/public/ats-spec/SKILL.md",
        "skills/public/ats-assess/SKILL.md",
        "skills/public/ats-review/SKILL.md",
    ],
)
def test_current_operator_surfaces_state_the_public_identity(relative_path: str) -> None:
    text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    assert CURRENT_PUBLIC_IDENTITY in text

"""The public corpus excludes denied authority and withheld evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from validate_repo import check_public_corpus_boundary  # noqa: E402


def test_checked_in_corpus_has_only_public_surface() -> None:
    result = check_public_corpus_boundary(REPO_ROOT)
    assert result.ok, result.detail


def test_denied_authority_record_is_rejected(tmp_path: Path) -> None:
    authority = tmp_path / "corpus" / "authority"
    authority.mkdir(parents=True)
    (authority / "denied.json").write_text(
        json.dumps({"classification": "private", "publication": "deny"}), encoding="utf-8"
    )
    result = check_public_corpus_boundary(tmp_path)
    assert not result.ok
    assert "publication-denied authority record" in result.detail


def test_withheld_corpus_tree_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "corpus" / "withheld").mkdir(parents=True)
    result = check_public_corpus_boundary(tmp_path)
    assert not result.ok
    assert "withheld must be absent" in result.detail


def test_private_metadata_in_public_fixture_is_rejected(tmp_path: Path) -> None:
    fixture = tmp_path / "fixtures" / "corpus"
    fixture.mkdir(parents=True)
    (fixture / "examples.jsonl").write_text(
        '{"classification":"private","publication":"deny"}\n', encoding="utf-8"
    )
    result = check_public_corpus_boundary(tmp_path)
    assert not result.ok
    assert "contains denied corpus metadata" in result.detail

def test_internal_authority_metadata_is_rejected(tmp_path: Path) -> None:
    fixture = tmp_path / "fixtures" / "repositories" / "sample-repo"
    fixture.mkdir(parents=True)
    (fixture / "corpus.json").write_text(
        '{"use_authority":"internal_training_permitted","handling_policy":"public"}\n',
        encoding="utf-8",
    )
    result = check_public_corpus_boundary(tmp_path)
    assert not result.ok
    assert "contains denied corpus metadata" in result.detail


def test_nonpublic_handling_metadata_is_rejected(tmp_path: Path) -> None:
    fixture = tmp_path / "fixtures" / "corpus"
    fixture.mkdir(parents=True)
    (fixture / "examples.jsonl").write_text(
        '{"use_authority":"external_training_permitted","handling_policy":"restricted"}\n',
        encoding="utf-8",
    )
    result = check_public_corpus_boundary(tmp_path)
    assert not result.ok
    assert "contains denied corpus metadata" in result.detail

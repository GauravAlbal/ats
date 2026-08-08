"""Observable repository licensing boundaries.

These tests cover split notices, normative-package adjacency, and tamper
rejection without mutating draft.1 or invoking generation.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
from pathlib import Path

from tools.validate_repo import check_license_deliverables

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_root_scope_map_declares_the_split_without_mit_or_by_nc() -> None:
    text = (REPO_ROOT / "LICENSE.md").read_text(encoding="utf-8")
    assert "Apache-2.0" in text
    assert "CC-BY-4.0" in text
    assert "spec/ATS-1/" in text
    assert "THIRD_PARTY_NOTICES.md" in text
    assert "MIT" not in text
    assert "BY-NC" not in text
    assert "Mixed generated hosts" in text
    assert "recipe/documentation class" in text
    assert "pyproject.toml" in text


def test_package_license_metadata_points_to_split_scope_map() -> None:
    metadata = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["license"] == {"file": "LICENSE.md"}


def test_build_backend_pin_has_a_matching_dependency_notice() -> None:
    metadata = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["build-system"]["requires"] == ["hatchling==1.31.0"]
    notices = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert (
        "| `hatchling` (build backend) | 1.31.0 (pinned in `pyproject.toml`; "
        "not present in `uv.lock`) | MIT |"
    ) in notices
    assert "no lock hash (build requirement is outside `uv.lock`)" in notices


def test_canonical_legal_texts_are_present() -> None:
    expected = {
        "LICENSES/Apache-2.0.txt": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
        "LICENSES/CC-BY-4.0.txt": "9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411",
    }
    for relative, digest in expected.items():
        path = REPO_ROOT / relative
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_draft1_manifest_bytes_are_intact_and_adjacent_notice_is_external() -> None:
    package = REPO_ROOT / "spec" / "ATS-1" / "1.0.0-draft.1"
    manifest = json.loads((package / "MANIFEST.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        path = package / entry["path"]
        assert path.is_file(), entry["path"]
        data = path.read_bytes()
        assert len(data) == entry["bytes"], entry["path"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], entry["path"]
    receipt = json.loads(
        (REPO_ROOT / "spec" / "ATS-1" / "receipts" / "1.0.0-draft.1.json").read_text(
            encoding="utf-8"
        )
    )
    assert hashlib.sha256((package / "MANIFEST.json").read_bytes()).hexdigest() == receipt["manifest_sha256"]
    assert not any(entry["path"] == "LICENSE.md" for entry in manifest["files"])
    assert (REPO_ROOT / "spec" / "ATS-1" / "LICENSE.md").is_file()


def test_draft2_adjacent_grant_supersedes_historical_unspecified_line() -> None:
    text = (REPO_ROOT / "spec" / "ATS-1" / "LICENSE.md").read_text(encoding="utf-8")
    assert "Gaurav Albal" in text
    assert "rightsholder" in text
    assert "draft.1" in text and "draft.2" in text
    assert "CC-BY-4.0" in text
    assert "Unspecified" in text
    assert "supersedes" in text
    assert "BY-NC" not in text


def test_repository_validator_rejects_tampered_license_text(tmp_path: Path) -> None:
    for relative in (
        "LICENSE.md",
        "LICENSES/Apache-2.0.txt",
        "LICENSES/CC-BY-4.0.txt",
        "THIRD_PARTY_NOTICES.md",
        "spec/ATS-1/LICENSE.md",
    ):
        source = REPO_ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    clean = check_license_deliverables(tmp_path)
    assert clean.ok

    apache = tmp_path / "LICENSES" / "Apache-2.0.txt"
    apache.write_bytes(apache.read_bytes() + b"\ntampered\n")
    findings = check_license_deliverables(tmp_path)
    assert not findings.ok
    assert "canonical legal text" in findings.detail

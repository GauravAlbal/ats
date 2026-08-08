"""The draft.2 normative package: validator, manifest, migration, registry.

The public draft.2 package contract requires that the package validate with
its own offline validator; the draft.1 package the pivot left behind remains
byte-identical to its sealed manifest; the draft.2 manifest is exact and
schema-valid; the migration table covers every normative delta; the rule
registry and the draft.2 spec agree; and a draft.2 context loads 36 rules
with a coherent capability declaration. The draft.1 directory is never
touched here or anywhere else: its bytes are checked, not rewritten.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

import pytest

from ats.spec_import import run_package_validator
from ats.spec_package import REPO_ROOT, SPEC_ROOT

DRAFT1: Final[str] = "1.0.0-draft.1"
DRAFT2: Final[str] = "1.0.0-draft.2"

#: Section 12.7 catalogues the v0 rule set; draft.2 carries 30 + 6 new rules.
EXPECTED_RULE_COUNT: Final[int] = 36

#: The six rules draft.2 adds, with their operational class.
NEW_RULES: Final[tuple[tuple[str, str], ...]] = (
    ("ATS-COORD-001", "block"),
    ("ATS-COORD-002", "block"),
    ("ATS-BASIS-001", "review_required"),
    ("ATS-BASIS-002", "block"),
    ("ATS-PRES-003", "block"),
    ("ATS-CLOSE-001", "review_required"),
)

#: The migration document the draft.2 validator cross-checks against the spec.
MIGRATION_DOC: Final[Path] = REPO_ROOT / "docs" / "ATS_1_DRAFT_2_MIGRATION.md"

#: Every normative delta D-A … D-F MUST be both classified and amended.
ALL_DELTAS: Final[frozenset[str]] = frozenset(f"D-{c}" for c in "ABCDEF")


def _package_bytes_by_manifest(root: Path) -> tuple[dict[str, tuple[int, str]], dict[str, tuple[int, str]]]:
    """The manifest's (bytes, sha256) map vs the on-disk files' (bytes, sha256) map.

    ``MANIFEST.json`` is deliberately excluded from both sides: the manifest
    describes the package contents, not itself (the same discipline the
    package validators apply).
    """
    manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    observed = {
        entry["path"]: (entry["bytes"], entry["sha256"]) for entry in manifest["files"]
    }
    expected: dict[str, tuple[int, str]] = {}
    for path in sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.name != "MANIFEST.json" and not p.name.endswith(".zip")
    ):
        rel = str(path.relative_to(root))
        expected[rel] = (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
    return expected, observed


def _assert_package_matches_manifest(root: Path) -> None:
    expected, observed = _package_bytes_by_manifest(root)
    assert observed == expected, (
        "manifest/package drift under " + str(root) + ":\n"
        f"  only in manifest: {sorted(set(observed) - set(expected))}\n"
        f"  only on disk: {sorted(set(expected) - set(observed))}\n"
        f"  differing bytes: "
        f"{[p for p in sorted(set(expected) & set(observed)) if observed[p] != expected[p]]}"
    )


def test_draft2_package_validates_with_its_own_offline_validator(ctx_d2) -> None:
    """Spec 1.2, §35.1: the draft.2 package ships a validator that must pass."""
    run = run_package_validator(ctx_d2.package)
    assert run.exit_code == 0, f"draft.2 package validator failed:\n{run.stdout}\n{run.stderr}"
    assert run.status == "PASS"
    assert "ATS-1 package valid" in run.stdout


def test_draft2_validator_rejects_normative_metadata_contradiction(tmp_path: Path) -> None:
    """The manifest edition cannot coexist with a draft.1 normative spec marker."""
    source = SPEC_ROOT / DRAFT2
    repo = tmp_path / "repo"
    package = repo / "spec" / "ATS-1" / DRAFT2
    package.parent.mkdir(parents=True)
    shutil.copytree(source, package)
    migration = repo / "docs" / "ATS_1_DRAFT_2_MIGRATION.md"
    migration.parent.mkdir(parents=True)
    shutil.copy2(MIGRATION_DOC, migration)
    spec_path = package / "ATS-1_SPEC.md"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8").replace(
            "| Specification version | `1.0.0-draft.2` |",
            "| Specification version | `1.0.0-draft.1` |",
            1,
        ),
        encoding="utf-8",
    )

    run = subprocess.run(
        (sys.executable, "tools/validate_package.py"),
        cwd=package,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode != 0
    assert "ATS-1_SPEC metadata contradicts manifest" in run.stderr


def test_draft1_directory_is_byte_identical_to_its_manifest() -> None:
    """§30/§35.1: the pivot never touched draft.1; its bytes match its manifest.

    Draft.1 is imported upstream territory: the directory is immutable and the
    manifest is its sealed content address. Every file must match its entry
    exactly, and nothing unmanifested may have appeared.
    """
    root = SPEC_ROOT / DRAFT1
    assert (root / "MANIFEST.json").is_file()
    _assert_package_matches_manifest(root)


def test_draft2_manifest_is_exact_and_schema_valid(ctx_d2) -> None:
    """§35.1: every file under the draft.2 package matches its manifest entry."""
    ctx_d2.schemas.validate(ctx_d2.package.manifest, "ats_package_manifest_v1.schema.json")
    assert ctx_d2.package.manifest["spec_version"] == DRAFT2
    _assert_package_matches_manifest(SPEC_ROOT / DRAFT2)


def test_migration_table_covers_every_normative_delta(ctx_d2) -> None:
    """§35.1: the migration document and the spec amendment markers agree.

    This is the validator's cross-check restated as a test: every delta the
    migration classifies (D-A … D-F) carries a ``Draft.2 amendment (D-<X>)``
    marker in the draft.2 spec, and every marker is classified.
    """
    spec = ctx_d2.package.spec_document.read_text(encoding="utf-8")
    migration = MIGRATION_DOC.read_text(encoding="utf-8")
    spec_markers = set(re.findall(r"Draft\.2 amendment \((D-[A-F])\)", spec))
    migration_ids = set(re.findall(r"\bD-[A-F]\b", migration))
    assert spec_markers == ALL_DELTAS, f"spec carries unexpected/missing markers: {sorted(spec_markers ^ ALL_DELTAS)}"
    assert migration_ids == spec_markers, (
        "migration/spec delta drift: "
        f"spec-only={sorted(spec_markers - migration_ids)}, "
        f"migration-only={sorted(migration_ids - spec_markers)}"
    )


def test_rule_registry_agrees_with_the_draft2_spec(ctx_d2) -> None:
    """§30/§35.1: the 36 registry rule IDs are exactly the spec's rule IDs."""
    spec = ctx_d2.package.spec_document.read_text(encoding="utf-8")
    ids = set(ctx_d2.registry.ids())
    spec_ids = set(re.findall(r"ATS-[A-Z]+-[0-9]{3}", spec))
    assert len(ids) == EXPECTED_RULE_COUNT
    assert spec_ids == ids, (
        f"spec/registry rule-id drift: spec-only={sorted(spec_ids - ids)}, "
        f"registry-only={sorted(ids - spec_ids)}"
    )


def test_the_six_new_rules_declare_their_operational_class(ctx_d2) -> None:
    """§30: each new rule carries the operational class the contract assigns."""
    for rule_id, expected_class in NEW_RULES:
        rule = ctx_d2.registry.get(rule_id)
        assert rule.rule_version == DRAFT2, rule_id
        assert rule.raw["operational_class"] == expected_class, rule_id
        assert rule.raw["operational_class"] in ("block", "review_required", "advisory")


def test_disc_003_carries_the_amended_statement(ctx_d2) -> None:
    """D-E: ATS-DISC-003 is amended, not replaced; the statement changes."""
    rule = ctx_d2.registry.get("ATS-DISC-003")
    assert rule.rule_version == DRAFT2
    assert rule.raw["operational_class"] == "advisory"
    statement = rule.normative_statement
    assert statement.startswith("Restatements MUST add function.")
    assert "Zero-information repetition" in statement
    assert "Locality-preserving redundancy is not zero-information repetition" in statement


def test_draft2_context_loads_thirty_six_rules_with_coherent_capability(ctx_d2) -> None:
    """§30: Context.load(spec_version='1.0.0-draft.2') is complete and coherent."""
    assert ctx_d2.spec_version == DRAFT2
    assert len(ctx_d2.registry) == EXPECTED_RULE_COUNT
    assert ctx_d2.registry.spec_version == DRAFT2
    assert len(ctx_d2.registry.ids()) == EXPECTED_RULE_COUNT
    assert len(set(ctx_d2.registry.ids())) == EXPECTED_RULE_COUNT
    # The draft.2 capability declaration lives inside the package and must be
    # coherent with the 36-rule registry.
    package_capability = ctx_d2.package.root / "capability" / "ats_rule_capability_v1.json"
    assert package_capability.is_file()
    assert ctx_d2.capability.path == package_capability
    assert len(ctx_d2.capability.rules) == EXPECTED_RULE_COUNT
    assert ctx_d2.capability.coherence_errors() == []

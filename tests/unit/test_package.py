"""The imported normative package is byte-exact and read-only.

Spec Section 1.2 makes the normative package the authority for rules, lexicon,
and schemas; Section 19.1 requires an implementation to record the exact
specification version it targets. Every later claim this repository makes is a
claim against these bytes, so the bytes are checked first and the evaluation
path is proved not to touch them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ats.hashes import file_sha256
from ats.ir.lint import lint_ir
from ats.spec_import import KNOWN_ARCHIVE_SHA256, run_package_validator, verify_import
from ats.spec_package import RECEIPTS_DIRNAME

#: The SHA-256 of the published ``ATS-1_1.0.0-draft.1.zip`` distribution.
#: Written here as a literal so a re-import that silently swapped the archive
#: fails this test rather than agreeing with itself.
PUBLISHED_ARCHIVE_SHA256 = "8ccef3dffdf39ad8f6a2a27f5ed2940c0c6180c57eee0f085a8b4644e7d37c28"

#: Section 12.7 catalogues the v0 rule set; the ruleset file carries exactly it.
EXPECTED_RULE_COUNT = 30


def test_import_receipt_records_the_published_archive_hash(ctx) -> None:
    """Spec 19.1: the recorded package identity must be the published one."""
    receipt = ctx.package.import_receipt()
    assert receipt is not None, "the import is unreceipted"
    archive = receipt["source_archive"]
    assert archive["sha256"] == PUBLISHED_ARCHIVE_SHA256
    assert archive["expected_sha256"] == PUBLISHED_ARCHIVE_SHA256
    assert archive["sha256_matches"] is True
    assert KNOWN_ARCHIVE_SHA256[ctx.spec_version] == PUBLISHED_ARCHIVE_SHA256

def test_import_receipt_revalidation_does_not_relabel_old_evidence(ctx) -> None:
    """A portable rerun must carry its own timestamp and result."""
    receipt = ctx.package.import_receipt()
    assert receipt is not None
    assert receipt["imported_at"] == "2026-08-03T00:00:00Z"
    assert receipt["revalidation_requested_at"] == "2026-08-07T00:00:00Z"
    validator = receipt["package_validator"]
    assert validator["command"] == [
        "python",
        "spec/ATS-1/1.0.0-draft.1/tools/validate_package.py",
    ]
    assert validator["interpreter"] == "python"
    assert all("/Users/" not in str(value) for value in validator.values())
    assert not any("normalizes" in note for note in receipt["notes"])
    if validator["status"] == "PENDING":
        assert validator["exit_code"] is None
        assert validator["stdout"] is None
        assert validator["recorded_at"] is None
    else:
        assert validator["status"] in {"PASS", "FAIL"}
        assert validator["recorded_at"] == "2026-08-08T05:19:04Z"
        assert isinstance(validator["exit_code"], int)
        assert isinstance(validator["stdout"], str)


def test_upstream_validator_passes_when_rerun(ctx) -> None:
    """Spec 1.2: the package ships its own offline validator; it must still pass."""
    run = run_package_validator(ctx.package)
    assert run.exit_code == 0, f"package validator failed:\n{run.stdout}\n{run.stderr}"
    assert run.status == "PASS"


def test_every_manifest_file_matches_its_recorded_bytes(ctx) -> None:
    """Spec 1.2 and Appendix C: the manifest is a byte-for-byte content address."""
    report = ctx.package.verify()
    mismatched = [f.path for f in report.files if f.status == "mismatch"]
    missing = [f.path for f in report.files if f.status == "missing"]
    assert mismatched == [], f"bytes differ from MANIFEST.json: {mismatched}"
    assert missing == [], f"files listed in MANIFEST.json are absent: {missing}"
    assert len(report.files) == len(ctx.package.manifest["files"])
    assert report.ok


def test_the_package_directory_holds_nothing_this_repository_added(ctx) -> None:
    """Spec 1.2: the imported version directory is byte-identical to upstream.

    The import receipt is this repository's own artifact, so it lives beside
    the version directory rather than inside it. Anything unlisted found under
    the package root is therefore a genuine extra file.
    """
    listed = {record["path"] for record in ctx.package.manifest["files"]}
    listed.add("MANIFEST.json")
    present = {
        str(p.relative_to(ctx.package.root))
        for p in ctx.package.root.rglob("*")
        if p.is_file()
    }
    assert present - listed == set()
    assert ctx.package.verify().extra_files == ()

    receipt_path = ctx.package.import_receipt_path
    assert receipt_path.is_file()
    assert receipt_path.parent.name == RECEIPTS_DIRNAME
    assert ctx.package.root not in receipt_path.parents


def test_verify_import_reports_pass(ctx) -> None:
    """Spec 14.13: the receipt must still agree with the artifacts it binds."""
    result = verify_import(ctx.package)
    assert result["problems"] == []
    assert result["status"] == "PASS"


def test_linting_does_not_write_into_the_package(ctx, load_ir, load_policy, source_path) -> None:
    """Spec 1.2: the imported package is immutable; evaluation only reads it."""
    files = sorted(p for p in ctx.package.root.rglob("*") if p.is_file())
    before = {p: file_sha256(p) for p in files}

    lint_ir(
        ctx,
        load_ir("assess_conforming"),
        load_policy("assess"),
        source_path=source_path("assess_rust_kernel.txt"),
    )

    after_files = sorted(p for p in ctx.package.root.rglob("*") if p.is_file())
    assert after_files == files, "linting added or removed a package file"
    assert {p: file_sha256(p) for p in after_files} == before


def test_registry_holds_exactly_thirty_rules_with_unique_ids(ctx) -> None:
    """Spec 12.1 and 12.7: rule identifiers are immutable and the catalog is closed."""
    raw_ids = [record["rule_id"] for record in ctx.package.ruleset["rules"]]
    assert len(raw_ids) == EXPECTED_RULE_COUNT
    assert len(set(raw_ids)) == EXPECTED_RULE_COUNT
    assert ctx.registry.ids() == tuple(sorted(raw_ids))
    assert len(ctx.registry) == EXPECTED_RULE_COUNT
    assert ctx.registry.spec_version == ctx.spec_version


def test_wep_intervals_are_contiguous_and_cover_the_final_boundary(ctx) -> None:
    """Spec 8.2 and 19.3: the WEP row is a partition, lower-inclusive upper-exclusive."""
    terms = list(ctx.package.force_lexicon["likelihood"]["terms"])
    intervals = [ctx.lexicon.interval_for(t["id"]) for t in terms]

    for (lower, upper, upper_inclusive) in intervals:
        assert lower < upper, "an interval must be non-empty"

    for (_, prev_upper, prev_inclusive), (next_lower, _, _) in zip(intervals, intervals[1:]):
        assert prev_upper == next_lower, "adjacent intervals must abut without a gap"
        assert prev_inclusive is False, "only the final interval may include its upper bound"

    final_lower, final_upper, final_inclusive = intervals[-1]
    assert final_upper == 0.99
    assert final_inclusive is True, "spec 8.2: the final interval includes 0.99"
    assert final_lower <= 0.99 <= final_upper


def test_wep_terms_and_aliases_are_disjoint_and_resolvable(ctx) -> None:
    """Spec 8.3: an input alias maps to exactly one canonical term."""
    phrases = set(ctx.lexicon.wep_phrases)
    aliases = set(ctx.lexicon.wep_aliases)
    assert phrases & aliases == set(), "a canonical phrase may not also be an alias"
    for alias, term_id in ctx.lexicon.wep_aliases.items():
        assert term_id in ctx.lexicon.wep_terms, f"{alias!r} maps to an unknown term"


def test_schema_set_is_metaschema_valid_and_does_not_shadow_normative_ids(ctx) -> None:
    """Spec 19.4: schemas are authoritative and a local schema may not shadow one."""
    assert ctx.schemas.check_own_schemas() == []
    package_ids = {json.loads(Path(p).read_text(encoding="utf-8"))["$id"]
                   for p in ctx.package.schema_paths}
    for schema_id in package_ids:
        assert ctx.schemas.schema(schema_id)["$id"] == schema_id


@pytest.mark.parametrize("schema_version", ["ats.text_ir.v1", "ats.policy_snapshot.v1"])
def test_unknown_schema_version_is_rejected(ctx, schema_version) -> None:
    """Spec 19.4: an implementation MUST reject an unknown major schema version."""
    schema_id, _ = ctx.schemas.schema_for_version(schema_version)
    assert schema_id.endswith(".schema.json")
    with pytest.raises(Exception):
        ctx.schemas.schema_for_version(schema_version + ".9")

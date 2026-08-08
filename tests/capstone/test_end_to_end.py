"""The capstone: one test drives every seam the v0 system has.

Constitution #22 makes the integration test the promotion gate. This module
drives the full chain on realistic state — imported package, real policy
snapshot, real TextIR, real rendered Markdown, real trace, real receipt — and
asserts on contract-relevant fields at the far end, including through the CLI
process boundary.

Expectations come from ``ATS-1_SPEC.md``, the imported schemas, and the force
lexicon. None was obtained by running the implementation and pasting output.
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ats.canonical import canonical_bytes, load_json, sha256_hex, verify_seal
from ats.cli import main as cli_main
from ats.context import Context
from ats.hashes import file_sha256
from ats.ir.lint import lint_ir
from ats.ir.model import IrDocument
from ats.output.lint import lint_output
from ats.output.receipt import build_candidate_receipt, verify_receipt
from ats.rules.deterministic import load_detectors

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXED_NOW = _dt.datetime(2026, 8, 3, tzinfo=_dt.UTC)

#: The published SHA-256 of the ATS-1 1.0.0-draft.1 distribution archive.
EXPECTED_ARCHIVE_SHA256 = "8ccef3dffdf39ad8f6a2a27f5ed2940c0c6180c57eee0f085a8b4644e7d37c28"

#: The five conformance dimensions, spec Section 5.2.
DIMENSIONS = ("mechanical", "profile", "semantic_review", "preservation", "forecast_calibration")

#: The statuses each dimension may hold, spec Section 5.2.
STATUSES = {"PASS", "FAIL", "NOT_APPLICABLE", "UNAVAILABLE", "INSUFFICIENT_EVIDENCE"}


@pytest.fixture(scope="module")
def ctx() -> Context:
    """A context pinned to a fixed evaluation time, so receipts are reproducible."""
    return Context.load(now=FIXED_NOW)


@pytest.fixture(scope="module")
def assess_ir() -> dict:
    return load_json(REPO_ROOT / "fixtures/ir/valid/assess_conforming.json")


@pytest.fixture(scope="module")
def assess_policy() -> dict:
    return load_json(REPO_ROOT / "fixtures/policies/assess.json")


def _run_cli(*argv: str) -> tuple[int, dict | None]:
    """Invoke the CLI in-process and parse its JSON stdout."""
    import io
    import contextlib

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
        code = cli_main(list(argv))
    text = buffer.getvalue().strip()
    payload = json.loads(text) if text.startswith("{") else None
    return code, payload


# -- the chain --------------------------------------------------------------


def test_imported_package_is_intact_and_receipted(ctx: Context) -> None:
    """Section 14.2 and 14.3: evaluation binds an exact, verified package."""
    report = ctx.package.verify()
    assert report.ok, [f.path for f in report.failures()]
    assert report.extra_files == (), "no unlisted file may sit inside the imported package"

    receipt = ctx.package.import_receipt()
    assert receipt is not None, "the import must leave a receipt"
    assert receipt["source_archive"]["expected_sha256"] == EXPECTED_ARCHIVE_SHA256
    assert receipt["source_archive"]["sha256_matches"] is True
    assert receipt["manifest_verification"]["status"] == "match"
    assert receipt["package_validator"]["status"] == "PASS"
    assert receipt["manifest_verification"]["excluded_from_manifest"] == [], (
        "nothing inside the package directory may be excluded from its manifest"
    )
    assert ctx.package.import_receipt_path.parent.name == "receipts", (
        "the receipt must live beside the version directory, not inside it"
    )


def test_upstream_validator_passes_after_import(ctx: Context) -> None:
    """The package's own validator must stay green forever, not only at import.

    ``tools/validate_package.py`` asserts that the files under the package root
    equal MANIFEST.json exactly. Anything this repository writes inside the
    package would break that permanently, so the import receipt lives outside.
    """
    from ats.spec_import import run_package_validator

    run = run_package_validator(ctx.package)
    assert run.exit_code == 0, run.stderr
    assert "package valid" in run.stdout


def test_registry_and_lexicon_match_the_specification(ctx: Context) -> None:
    """Section 12.7 declares thirty rules; Section 8.2 declares one WEP row."""
    assert len(ctx.registry) == 30
    assert len(set(ctx.registry.ids())) == 30

    terms = list(ctx.lexicon.wep_terms.values())
    assert len(terms) == 7, "Section 8.2 defines seven canonical bands"
    ordered = sorted(terms, key=lambda t: t["lower"])
    for lower_band, upper_band in zip(ordered, ordered[1:]):
        assert lower_band["upper"] == upper_band["lower"], (
            "Section 8.2 requires contiguous non-overlapping intervals"
        )
    assert ordered[-1]["upper"] == 0.99
    assert ordered[-1]["upper_inclusive"] is True, (
        "the lexicon's machine boundary convention includes 0.99 in the final interval"
    )


def test_every_rule_receives_an_explicit_result(ctx: Context, assess_ir, assess_policy) -> None:
    """Section 5.4 and the v0 milestone: every active rule gets an explicit result."""
    report = lint_ir(
        ctx,
        assess_ir,
        assess_policy,
        source_path=REPO_ROOT / "fixtures/ir/sources/assess_rust_kernel.txt",
    )
    seen = [r["rule_id"] for r in report["rule_results"]]
    assert sorted(seen) == list(ctx.registry.ids())
    assert len(seen) == len(set(seen)), "a rule may not be evaluated twice"
    for result in report["rule_results"]:
        assert result["status"] in {
            "PASS",
            "FAIL",
            "UNAVAILABLE",
            "NOT_APPLICABLE",
            "REVIEW_REQUIRED",
        }


def test_no_rule_passes_without_a_complete_decision_procedure(
    ctx: Context, assess_ir, assess_policy
) -> None:
    """Section 16.5: no surfaced finding does not prove the rule passed."""
    report = lint_ir(ctx, assess_ir, assess_policy)
    for result in report["rule_results"]:
        if result["status"] == "PASS":
            assert result["decision_power"] == "decides", (
                f"{result['rule_id']} reports PASS with decision power "
                f"{result['decision_power']!r}"
            )
            assert result["detector"]["authority"] == "conformance_evidence", (
                f"{result['rule_id']} reports PASS from a "
                f"{result['detector']['authority']} detector"
            )


def test_proposal_only_findings_never_decide_a_rule(ctx: Context) -> None:
    """Section 12.3: proposal-only output cannot independently establish PASS or FAIL."""
    detectors = load_detectors()
    policy_document = load_json(REPO_ROOT / "fixtures/policies/assess.json")
    policy = ctx.policy(policy_document)
    for path in sorted((REPO_ROOT / "fixtures/ir/invalid").glob("*.json")):
        document = load_json(path)
        ir = IrDocument.from_document(document)
        if "SPECIFY" in ir.profiles:
            continue
        states, _ = policy.resolve_all(ir.profiles, now=ctx.now, artifact_id=ir.artifact_id)
        from ats.ir.model import IrEvaluation

        evaluation = IrEvaluation(ctx=ctx, ir=ir, policy=policy, states=states)
        for rule_id in ctx.registry.ids():
            result = detectors[rule_id](evaluation)
            if result.detector.authority != "conformance_evidence":
                assert result.status.value != "FAIL", (
                    f"{rule_id} on {path.name}: a {result.detector.authority} detector "
                    "decided FAIL"
                )
                assert result.status.value != "PASS"


def test_conforming_artifact_reaches_mechanical_and_profile_pass(
    ctx: Context, assess_ir, assess_policy
) -> None:
    """Sections 15.1 and 9.2.13 define what these two dimensions require."""
    report = lint_ir(
        ctx,
        assess_ir,
        assess_policy,
        source_path=REPO_ROOT / "fixtures/ir/sources/assess_rust_kernel.txt",
    )
    assert report["conformance"]["mechanical"] == "PASS"
    assert report["conformance"]["profile"] == "PASS"


def test_semantic_review_and_forecast_calibration_are_never_claimed(
    ctx: Context, assess_ir, assess_policy
) -> None:
    """Sections 15.3, 14.11, and 15.5: this build holds neither authority nor data."""
    report = lint_ir(ctx, assess_ir, assess_policy)
    assert report["conformance"]["semantic_review"] == "UNAVAILABLE"
    assert report["conformance"]["forecast_calibration"] == "INSUFFICIENT_EVIDENCE"
    for dimension in DIMENSIONS:
        assert report["conformance"][dimension] in STATUSES
        assert report["conformance_rationale"][dimension].strip(), (
            f"{dimension} holds a status with no stated reason"
        )


def test_preservation_is_unavailable_when_transform_is_active(ctx: Context) -> None:
    """Section 6.4: preservation MUST NOT be PASS while PRES-001/002 are unavailable."""
    report = lint_ir(
        ctx,
        load_json(REPO_ROOT / "fixtures/ir/valid/assess_transform_output.json"),
        load_json(REPO_ROOT / "fixtures/policies/assess_transform.json"),
        source_path=REPO_ROOT / "fixtures/ir/sources/assess_rust_kernel.txt",
    )
    assert report["conformance"]["preservation"] == "UNAVAILABLE"
    for rule_id in ("ATS-PRES-001", "ATS-PRES-002"):
        result = next(r for r in report["rule_results"] if r["rule_id"] == rule_id)
        assert result["effective_state"] == "required"
        assert result["status"] == "UNAVAILABLE"
        assert result["missing_inputs"], "an unavailable rule must name what it lacks"


def test_preservation_is_not_applicable_without_transform(
    ctx: Context, assess_ir, assess_policy
) -> None:
    """Section 15.4: for a non-transformed artifact, preservation is NOT_APPLICABLE."""
    report = lint_ir(ctx, assess_ir, assess_policy)
    assert report["conformance"]["preservation"] == "NOT_APPLICABLE"


def test_each_invalid_fixture_fails_for_its_own_reason(ctx: Context) -> None:
    """A violation fixture must fail for the reason the rule exists (constitution #21)."""
    expected: dict[str, tuple[str, ...]] = {
        "duplicate_ids.json": ("IR-ID-UNIQUE",),
        "dangling_reference.json": ("IR-REFS",),
        "wep_interval_mismatch.json": ("IR-LIKELIHOOD-VOCAB",),
        "ambiguous_without_distinct_readings.json": ("IR-EXTRACTION-STATUS",),
        "observation_with_confidence.json": ("IR-CLAIM-ROLE-FIELDS",),
    }
    expected_codes: dict[str, str] = {
        "blank_confidence_basis.json": "confidence-basis-rationale-blank",
        "noncanonical_wep_synonym.json": "noncanonical-wep-synonym",
        "possibility_term_only.json": "possibility-term-as-only-likelihood",
        "no_update_indicator.json": "no-update-indicator",
        "unanchored_relative_time.json": "unanchored-relative-time",
        "wep_interval_mismatch.json": "wep-interval-mismatch",
    }
    policy = load_json(REPO_ROOT / "fixtures/policies/assess.json")
    source = REPO_ROOT / "fixtures/ir/sources/assess_rust_kernel.txt"

    for name, check_ids in expected.items():
        report = lint_ir(
            ctx, load_json(REPO_ROOT / "fixtures/ir/invalid" / name), policy, source_path=source
        )
        failed = {c["check_id"] for c in report["structural_checks"] if c["status"] == "FAIL"}
        for check_id in check_ids:
            assert check_id in failed, f"{name} did not fail {check_id}; failed {sorted(failed)}"

    for name, code in expected_codes.items():
        report = lint_ir(
            ctx, load_json(REPO_ROOT / "fixtures/ir/invalid" / name), policy, source_path=source
        )
        codes = {f["issue_code"] for f in report["findings"]}
        assert code in codes, f"{name} did not raise {code}; raised {sorted(codes)}"


def test_conforming_bundle_lints_clean_and_broken_bundle_fails_precisely(ctx: Context) -> None:
    """The output linter must discriminate, not merely complain."""
    ir_document = load_json(REPO_ROOT / "fixtures/ir/valid/assess_conforming.json")
    policy_document = load_json(REPO_ROOT / "fixtures/policies/assess.json")

    good = lint_output(
        ctx,
        output_path=REPO_ROOT / "fixtures/output/assess-bundle/document.md",
        trace_document=load_json(REPO_ROOT / "fixtures/output/assess-bundle/document.trace.json"),
        ir_document=ir_document,
        policy_document=policy_document,
    )
    assert good["conformance"]["mechanical"] == "PASS"
    assert [c["check_id"] for c in good["checks"] if c["status"] == "FAIL"] == []

    bad = lint_output(
        ctx,
        output_path=REPO_ROOT / "fixtures/output/assess-broken/document.md",
        trace_document=load_json(REPO_ROOT / "fixtures/output/assess-broken/document.trace.json"),
        ir_document=ir_document,
        policy_document=policy_document,
    )
    failed = {c["check_id"] for c in bad["checks"] if c["status"] == "FAIL"}
    assert failed == {"OUT-WEP-INLINE-RANGE", "OUT-P0-EXACT"}, sorted(failed)
    assert bad["conformance"]["mechanical"] == "FAIL"


def test_receipt_binds_the_bundle_and_names_an_external_adjudicator(ctx: Context) -> None:
    """Sections 13.7 and 14.11: acceptance authority is never the producing component."""
    ir_document = load_json(REPO_ROOT / "fixtures/ir/valid/assess_conforming.json")
    policy_document = load_json(REPO_ROOT / "fixtures/policies/assess.json")
    document = REPO_ROOT / "fixtures/output/assess-bundle/document.md"
    receipt = load_json(REPO_ROOT / "fixtures/output/assess-bundle/document.receipt.json")

    ok, declared, recomputed = verify_seal(dict(receipt))
    assert ok, f"receipt seal {declared} != {recomputed}"
    assert receipt["output_sha256"] == file_sha256(document)
    assert receipt["source_sha256"] == ir_document["source"]["content_sha256"]
    assert receipt["adjudicator"] not in ("ats", "self", "")

    verification = verify_receipt(
        ctx,
        receipt,
        ir_document=ir_document,
        output_sha256=file_sha256(document),
        policy_document=policy_document,
    )
    assert verification["status"] == "PASS", verification["detail"]


def test_receipt_construction_refuses_to_name_itself(ctx: Context) -> None:
    """Section 13.7: a model MUST NOT become the authoritative adjudicator of its own finding."""
    from ats.errors import UsageError

    ir_document = load_json(REPO_ROOT / "fixtures/ir/valid/assess_conforming.json")
    policy = ctx.policy(load_json(REPO_ROOT / "fixtures/policies/assess.json"))
    report = load_json(REPO_ROOT / "fixtures/output/assess-bundle/document.lint.json")
    with pytest.raises(UsageError, match="adjudicat"):
        build_candidate_receipt(
            ctx,
            ir=IrDocument.from_document(ir_document),
            policy=policy,
            output_sha256=None,
            lint_report=report,
            adjudicator="ats",
        )


def test_tampering_with_a_receipt_is_detected(ctx: Context) -> None:
    """Section 16.12: receipt verification re-derives the content address."""
    receipt = dict(load_json(REPO_ROOT / "fixtures/output/assess-bundle/document.receipt.json"))
    receipt["adjudicator"] = "someone-else"
    result = verify_receipt(ctx, receipt)
    assert result["status"] == "FAIL"
    assert "receipt_sha256" in result["detail"]


def test_evaluation_never_mutates_the_imported_package(ctx: Context, assess_ir, assess_policy) -> None:
    """The imported package is immutable; no command may write into it."""
    root = ctx.package.root
    before = {
        p: file_sha256(p) for p in sorted(root.rglob("*")) if p.is_file()
    }
    lint_ir(ctx, assess_ir, assess_policy)
    lint_output(
        ctx,
        output_path=REPO_ROOT / "fixtures/output/assess-bundle/document.md",
        trace_document=load_json(REPO_ROOT / "fixtures/output/assess-bundle/document.trace.json"),
        ir_document=assess_ir,
        policy_document=assess_policy,
    )
    after = {p: file_sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}
    assert before == after


def test_deterministic_replay(ctx: Context, assess_ir, assess_policy) -> None:
    """Section 16.2: identical canonical inputs produce identical results."""
    first = lint_ir(ctx, assess_ir, assess_policy)
    second = lint_ir(ctx, assess_ir, assess_policy)
    assert canonical_bytes(first) == canonical_bytes(second)
    assert first["report_sha256"] == second["report_sha256"]

    ok, _, recomputed = verify_seal(dict(first))
    assert ok and recomputed == first["report_sha256"]


def test_capability_declaration_is_coherent_and_generated(ctx: Context) -> None:
    """Sections 5.5 and 16.1: the declaration must describe what the code does."""
    assert ctx.capability.coherence_errors() == []
    result = subprocess.run(
        [sys.executable, "tools/generate_capability.py", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr


# -- the process boundary ---------------------------------------------------


def test_cli_exit_codes_discriminate_clean_failed_and_unsupported() -> None:
    """Section 16.11: a CI integration needs stable machine-readable exit semantics."""
    clean, payload = _run_cli(
        "--now",
        "2026-08-03T00:00:00Z",
        "ir",
        "lint",
        "fixtures/ir/valid/assess_conforming.json",
        "--policy",
        "fixtures/policies/assess.json",
        "--source",
        "fixtures/ir/sources/assess_rust_kernel.txt",
    )
    assert clean == 0
    assert payload is not None and payload["conformance"]["mechanical"] == "PASS"

    failed, _ = _run_cli(
        "--now",
        "2026-08-03T00:00:00Z",
        "ir",
        "lint",
        "fixtures/ir/invalid/wep_interval_mismatch.json",
        "--policy",
        "fixtures/policies/assess.json",
        "--source",
        "fixtures/ir/sources/assess_rust_kernel.txt",
    )
    assert failed == 1

    usage, _ = _run_cli("ir", "lint", "does-not-exist.json", "--policy", "also-missing.json")
    assert usage == 2


def test_every_documented_cli_command_behaves_as_contracted() -> None:
    """Section 16.11: a CI integration needs the whole surface to be stable.

    ``tools/smoke_cli.py`` drives every command the milestone names and asserts
    its exit code against the documented contract. Running it here makes the
    full surface a permanent gate rather than a one-time manual check.
    """
    result = subprocess.run(
        [sys.executable, "tools/smoke_cli.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "commands behaved as contracted" in result.stdout


def test_cli_explains_a_rule_with_everything_section_12_10_requires() -> None:
    """Section 12.10 lists exactly what a rule explanation must return."""
    code, payload = _run_cli("rules", "explain", "ATS-REQ-001")
    assert code == 0
    assert payload is not None
    assert payload["normative_statement"]
    assert payload["protected_impact"]
    assert payload["exception_conditions"]
    assert payload["conforming_repair_examples"]
    assert payload["detector"]["subchecks"], "an explanation must say what was inspected"


def test_cli_reports_an_unimplemented_capability_as_typed_unavailable() -> None:
    """Sections 5.5 and 14.12: an unsupported capability is reported, never emulated."""
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer), contextlib.redirect_stdout(io.StringIO()):
        code = cli_main(["corpus", "mine", "--inventory", "does-not-matter.json"])
    if code == 3:
        payload = json.loads(buffer.getvalue().strip())
        assert payload["error"] == "unsupported_capability"
        assert payload["status"] == "UNAVAILABLE"
    else:
        # The corpus capability is present in this build; it must then fail on
        # the missing input rather than silently succeeding.
        assert code in (1, 2), f"unexpected exit {code} for a missing inventory file"

"""Determinism.

Section 16.2: identical canonical inputs, the same rule set, the same lexicon,
and the same policy snapshot MUST produce identical results. Appendix C makes
the content address the test of that: if any byte of the report changes, its
seal changes. Section 16.12 extends the same requirement to receipts.
"""

from __future__ import annotations

import datetime as _dt
import json

import pytest

from conftest import FIXED_NOW, INVALID_IR_POLICY

from ats.canonical import canonical_bytes, sha256_hex, verify_seal
from ats.context import Context
from ats.ir.lint import lint_ir
from ats.ir.model import IrDocument
from ats.output.lint import lint_output
from ats.output.parse import parse_markdown
from ats.output.receipt import build_candidate_receipt

GENERATORS = (
    "tools/generate_capability.py",
    "tools/generate_ir_fixtures.py",
    "tools/generate_policies.py",
    "tools/generate_output_bundle.py",
)


@pytest.fixture(scope="module")
def fresh_context():
    """A context built independently of the session-wide one.

    Determinism must hold across processes, so the second run of every pair
    below uses a context that shares no cached state with the first.
    """
    return Context.load(now=FIXED_NOW)


# -- the IR linter ----------------------------------------------------------


def test_ir_lint_is_byte_identical_across_runs(
    ctx, fresh_context, load_ir, load_policy, source_path
) -> None:
    """Spec 16.2: the same inputs at the same evaluation time give the same report."""
    args = (load_ir("assess_conforming"), load_policy("assess"))
    path = source_path("assess_rust_kernel.txt")

    first = lint_ir(ctx, *args, source_path=path)
    second = lint_ir(fresh_context, *args, source_path=path)

    assert first["report_sha256"] == second["report_sha256"]
    assert canonical_bytes(first) == canonical_bytes(second)
    ok, declared, recomputed = verify_seal(first)
    assert ok and declared == recomputed == first["report_sha256"]


@pytest.mark.parametrize("fixture_name", sorted(INVALID_IR_POLICY))
def test_every_violation_fixture_lints_reproducibly(
    ctx, fresh_context, load_ir, load_policy, fixture_name
) -> None:
    """Spec 16.2: reproducibility must hold on failing artifacts too."""
    policy_name = INVALID_IR_POLICY[fixture_name]
    first = lint_ir(ctx, load_ir(fixture_name), load_policy(policy_name))
    second = lint_ir(fresh_context, load_ir(fixture_name), load_policy(policy_name))
    assert first["report_sha256"] == second["report_sha256"]


def test_finding_identities_are_stable_across_runs(
    ctx, fresh_context, load_ir, load_policy
) -> None:
    """Spec 16.2 and 13.9: identity is a function of the inputs, not of a clock."""
    args = (load_ir("wep_interval_mismatch"), load_policy("assess"))
    first = lint_ir(ctx, *args)
    second = lint_ir(fresh_context, *args)

    ids = [f["finding_id"] for f in first["findings"]]
    assert ids, "the violation fixture must raise a finding"
    assert ids == [f["finding_id"] for f in second["findings"]]
    assert len(ids) == len(set(ids))
    assert first["findings"] == second["findings"]


def test_the_evaluation_time_is_the_only_clock_input(
    ctx, load_ir, load_policy
) -> None:
    """Spec 16.2: no wall clock is read; ``now`` is an explicit input."""
    later = Context.load(now=_dt.datetime(2026, 9, 1, tzinfo=_dt.UTC))
    args = (load_ir("assess_conforming"), load_policy("assess"))
    first = lint_ir(ctx, *args)
    second = lint_ir(later, *args)

    assert first["created_at"] != second["created_at"]
    assert first["report_sha256"] != second["report_sha256"]
    # Everything except the recorded instant is identical.
    stripped = [
        {k: v for k, v in report.items() if k not in ("created_at", "report_sha256")}
        for report in (first, second)
    ]
    assert stripped[0] == stripped[1]


def test_rule_and_check_ordering_is_stable(ctx, fresh_context, load_ir, load_policy) -> None:
    """Spec 16.2: a stable order is part of a reproducible report."""
    args = (load_ir("composed_profiles"), load_policy("composed"))
    first = lint_ir(ctx, *args)
    second = lint_ir(fresh_context, *args)
    assert [r["rule_id"] for r in first["rule_results"]] == [
        r["rule_id"] for r in second["rule_results"]
    ]
    assert [c["check_id"] for c in first["structural_checks"]] == [
        c["check_id"] for c in second["structural_checks"]
    ]


# -- the output linter ------------------------------------------------------


@pytest.mark.parametrize("bundle_name", ["assess-bundle", "assess-broken"])
def test_output_lint_is_byte_identical_across_runs(
    ctx, fresh_context, load_bundle, load_ir, load_policy, bundle_name
) -> None:
    """Spec 16.2: the output surface is reproducible from the same bytes."""
    bundle = load_bundle(bundle_name)
    kwargs = dict(
        output_path=bundle["output_path"],
        trace_document=bundle["trace"],
        ir_document=load_ir("assess_conforming"),
        policy_document=load_policy("assess"),
    )
    first = lint_output(ctx, **kwargs)
    second = lint_output(fresh_context, **kwargs)

    assert first["report_sha256"] == second["report_sha256"]
    assert canonical_bytes(first) == canonical_bytes(second)
    ok, _, _ = verify_seal(first)
    assert ok


def test_a_candidate_receipt_is_reproducible(
    ctx, fresh_context, load_bundle, load_ir, load_policy
) -> None:
    """Spec 16.12: a receipt must be reproducible from the same artifacts."""
    bundle = load_bundle("assess-bundle")
    output_sha = sha256_hex(bundle["output_path"].read_bytes())

    def build(context):
        ir = IrDocument.from_document(load_ir("assess_conforming"))
        policy = context.policy(load_policy("assess"))
        report = lint_output(
            context,
            output_path=bundle["output_path"],
            trace_document=bundle["trace"],
            ir_document=load_ir("assess_conforming"),
            policy_document=load_policy("assess"),
        )
        return build_candidate_receipt(
            context,
            ir=ir,
            policy=policy,
            output_sha256=output_sha,
            lint_report=report,
            adjudicator="arq-acceptance-authority",
        )

    first, second = build(ctx), build(fresh_context)
    assert first["receipt_sha256"] == second["receipt_sha256"]
    assert first == second


# -- canonical stability ----------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name",
    ["assess_conforming", "specify_conforming", "composed_profiles"],
)
def test_canonical_bytes_survive_a_parse_round_trip(load_ir, fixture_name) -> None:
    """Appendix C: JCS output re-serializes to itself, so the address is stable."""
    document = load_ir(fixture_name)
    first = canonical_bytes(document)
    second = canonical_bytes(json.loads(first.decode("utf-8")))
    assert first == second
    assert sha256_hex(first) == IrDocument.from_document(document).ir_sha256


def test_markdown_parsing_is_stable_across_a_round_trip(load_bundle) -> None:
    """Spec 16.2 and 14.4: the block model is a function of the bytes."""
    text = load_bundle("assess-bundle")["text"]
    first = parse_markdown(text)
    second = parse_markdown(first.text)
    assert [(b.index, b.kind, b.start_line, b.end_line, b.marker_id, b.text)
            for b in first.blocks] == [
        (b.index, b.kind, b.start_line, b.end_line, b.marker_id, b.text)
        for b in second.blocks
    ]
    assert first.markers_in_order() == second.markers_in_order()


def test_the_schema_set_address_is_stable(ctx, fresh_context) -> None:
    """Spec 15.8: a schema change must invalidate a prior claim, so it is addressed."""
    assert ctx.schema_set_sha256 == fresh_context.schema_set_sha256
    assert len(ctx.schema_set_sha256) == 64


# -- generated artifacts ----------------------------------------------------


@pytest.mark.parametrize("tool", GENERATORS)
def test_every_generator_is_idempotent(run_tool, tool) -> None:
    """Spec 16.2: a derived artifact must regenerate to the same bytes."""
    result = run_tool(tool, "--check")
    assert result.returncode == 0, f"{tool}: {result.stdout}\n{result.stderr}"

"""The full output-bundle lint seam.

IR -> trace -> rendered Markdown -> lint report -> candidate receipt ->
receipt verification. Section 14.4 requires source mapping, Section 11.3
defines what a rendering must preserve, and Section 5.2 keeps the conformance
vector non-compensatory.
"""

from __future__ import annotations

import copy

import pytest

from ats.canonical import sha256_hex, verify_seal
from ats.ir.model import IrDocument
from ats.output.lint import MECHANICAL_CHECKS, SURFACE_CHECK_SPECS, lint_output
from ats.output.parse import parse_markdown
from ats.output.receipt import build_candidate_receipt, verify_receipt
from ats.output.trace import build_trace

REPORT_SCHEMA_ID = "ats_output_lint_report_v1.schema.json"

#: The binding output-check identifier set.
CHECK_IDS = frozenset(
    {
        "OUT-BYTES",
        "OUT-MARKDOWN-PARSE",
        "OUT-CONSTRUCTS",
        "OUT-MARKERS",
        "OUT-TRACE-SCHEMA",
        "OUT-BLOCK-HASHES",
        "OUT-IR-REFS",
        "OUT-MATERIAL-COVERAGE",
        "OUT-UNKNOWN-REFS",
        "OUT-BLOCK-ORDER",
        "OUT-PROFILE-SECTIONS",
        "OUT-WEP-CANONICAL",
        "OUT-WEP-INLINE-RANGE",
        "OUT-DEONTIC-KEYWORDS",
        "OUT-ACRONYMS",
        "OUT-UNITS",
        "OUT-RELATIVE-TIME",
        "OUT-TERMINOLOGY",
        "OUT-HEADINGS-LISTS",
        "OUT-P0-EXACT",
        "OUT-P1-DECLARED",
        "OUT-COORD-PRESERVED",
        "OUT-BASIS-NOT-STRENGTHENED",
        "OUT-POLICY-EXCEPTIONS",
        "OUT-FINDING-DISPOSITIONS",
        "OUT-CONFORMANCE-VECTOR",
        "OUT-RECEIPT",
    }
)

ADJUDICATOR = "arq-acceptance-authority"


@pytest.fixture(scope="module")
def run_lint(ctx, load_ir, load_policy, load_bundle):
    def _run(bundle_name, *, receipt=False, trace=None, output_path=None):
        bundle = load_bundle(bundle_name)
        return lint_output(
            ctx,
            output_path=output_path or bundle["output_path"],
            trace_document=trace if trace is not None else bundle["trace"],
            ir_document=load_ir("assess_conforming"),
            policy_document=load_policy("assess"),
            receipt_document=bundle["receipt"] if receipt else None,
        )

    return _run


@pytest.fixture(scope="module")
def conforming(run_lint):
    return run_lint("assess-bundle")


@pytest.fixture(scope="module")
def broken(run_lint):
    return run_lint("assess-broken")


def by_id(report):
    return {c["check_id"]: c for c in report["checks"]}


def failed(report) -> set[str]:
    return {c["check_id"] for c in report["checks"] if c["status"] == "FAIL"}


# -- the emitted report -----------------------------------------------------


def test_the_report_is_sealed_and_schema_valid(ctx, conforming, assert_valid) -> None:
    """Appendix C and 19.4: the report addresses itself and validates."""
    assert_valid(conforming, REPORT_SCHEMA_ID)
    ok, declared, recomputed = verify_seal(conforming)
    assert ok and declared == recomputed
    assert ctx.schemas.validate_document(conforming) == REPORT_SCHEMA_ID


def test_every_output_check_runs(conforming) -> None:
    """Spec 12.8: the output surface carries its own closed check set."""
    ids = [c["check_id"] for c in conforming["checks"]]
    assert set(ids) == CHECK_IDS
    assert len(ids) == len(CHECK_IDS) == 27
    assert MECHANICAL_CHECKS <= CHECK_IDS
    assert set(SURFACE_CHECK_SPECS) <= CHECK_IDS
    for check in conforming["checks"]:
        assert check["spec_ref"].startswith("ATS-1 ")
        assert check["title"].strip()
    # The draft.2 gated checks are present but non-required and NOT_APPLICABLE
    # on a draft.1-shaped bundle whose IR declares neither coordinates nor basis
    # (draft.2 D-C/D-F): absence of the surface is nothing to check, and they
    # must not gate the mechanical dimension (GATED_MECHANICAL_CHECKS).
    for check_id in ("OUT-COORD-PRESERVED", "OUT-BASIS-NOT-STRENGTHENED"):
        check = by_id(conforming)[check_id]
        assert check["status"] == "NOT_APPLICABLE", check_id
        assert check["required"] is False, check_id


def test_the_report_binds_the_bytes_it_judged(
    ctx, conforming, load_bundle, load_ir, load_policy
) -> None:
    """Spec 14.13: the report names the exact rendering, trace, IR, and policy."""
    bundle = load_bundle("assess-bundle")
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    assert conforming["output_sha256"] == sha256_hex(bundle["output_path"].read_bytes())
    assert conforming["trace_sha256"] == bundle["trace"]["trace_sha256"]
    assert conforming["ir_sha256"] == ir.ir_sha256
    assert conforming["policy_sha256"] == load_policy("assess")["snapshot_sha256"]
    assert conforming["spec_version"] == ctx.spec_version
    assert conforming["implementation"]["parser_version"].startswith("markdown-it-py/")
    assert conforming["created_at"] == ctx.timestamp()


# -- the conforming bundle --------------------------------------------------


def test_the_conforming_bundle_has_no_required_check_failure(conforming) -> None:
    """Spec 11.3 and 16.3: a conforming rendering preserves what it declares."""
    assert failed(conforming) == set()
    assert conforming["summary"]["required_failed"] == 0
    assert conforming["conformance"]["mechanical"] == "PASS"
    assert conforming["conformance"]["profile"] == "PASS"


def test_the_conforming_bundle_maps_every_material_object(conforming) -> None:
    """Spec 11.7 and 11.8: nothing material is dropped without authorization."""
    coverage = conforming["block_coverage"]
    assert coverage["unmapped_material_ir_objects"] == []
    assert coverage["unknown_ir_references"] == []
    assert coverage["material_ir_objects_mapped"] == coverage["material_ir_objects"]
    assert coverage["blocks_found"] == coverage["blocks_declared"]


def test_declared_p0_values_render_exactly(conforming) -> None:
    """Spec 11.3.1 and 11.6: a P0 field renders byte-for-byte as the IR states it."""
    assert by_id(conforming)["OUT-P0-EXACT"]["status"] == "PASS"
    assert conforming["p0_checks"]
    assert {entry["status"] for entry in conforming["p0_checks"]} == {"preserved"}


def test_declared_p1_relations_are_review_required_not_passed(conforming) -> None:
    """Spec 11.3.2: declaring a relation is not proving the prose realizes it."""
    check = by_id(conforming)["OUT-P1-DECLARED"]
    assert check["status"] == "REVIEW_REQUIRED"
    assert "semantic judgement" in check["detail"]
    assert {entry["status"] for entry in conforming["p1_checks"]} == {"declared"}


def test_semantic_review_and_preservation_are_never_claimed(conforming) -> None:
    """Spec 15.3, 15.4, 15.5: this surface holds no disposition or transform authority."""
    conformance = conforming["conformance"]
    assert conformance["semantic_review"] == "UNAVAILABLE"
    assert conformance["preservation"] == "NOT_APPLICABLE"
    assert conformance["forecast_calibration"] == "INSUFFICIENT_EVIDENCE"
    rationale = conforming["conformance_rationale"]
    assert set(rationale) == set(conformance)
    assert all(text.strip() for text in rationale.values())
    assert "15.3" in rationale["semantic_review"]
    vector_check = by_id(conforming)["OUT-CONFORMANCE-VECTOR"]
    assert "no dimension is averaged" in vector_check["detail"]


# -- the broken bundle ------------------------------------------------------


def test_the_broken_bundle_fails_exactly_its_two_planted_defects(
    conforming, broken
) -> None:
    """Spec 16.4: each planted defect targets exactly one check."""
    assert failed(broken) == {"OUT-WEP-INLINE-RANGE", "OUT-P0-EXACT"}
    assert failed(broken) - failed(conforming) == {
        "OUT-WEP-INLINE-RANGE",
        "OUT-P0-EXACT",
    }


def test_the_broken_bundle_reports_no_new_status_regression_elsewhere(
    conforming, broken
) -> None:
    """Spec 16.4: a twin fixture differs only where its defect is."""
    before = {c["check_id"]: c["status"] for c in conforming["checks"]}
    after = {c["check_id"]: c["status"] for c in broken["checks"]}
    changed = {k for k in before if before[k] != after[k]}
    assert changed == {"OUT-WEP-INLINE-RANGE", "OUT-P0-EXACT"}


def test_the_dropped_inline_range_is_named(ctx, broken) -> None:
    """Spec 8.4: the first material WEP use must show its numeric range."""
    check = by_id(broken)["OUT-WEP-INLINE-RANGE"]
    assert check["status"] == "FAIL"
    assert ctx.lexicon.display_range("likely") in check["detail"]
    assert "assess-key-judgment" in check["detail"]


def test_the_altered_p0_value_is_named(broken) -> None:
    """Spec 11.3.1: an unauthorized change to a protected field is a preservation defect."""
    check = by_id(broken)["OUT-P0-EXACT"]
    assert check["status"] == "FAIL"
    altered = [e for e in broken["p0_checks"] if e["status"] == "changed_unauthorized"]
    assert len(altered) == 1
    assert altered[0]["field_ref"] == "b1.proposition"
    assert "does not apply" in altered[0]["source_value"]
    assert "also covers" in altered[0]["rendered_value"]


def test_a_surface_failure_blocks_mechanical(broken) -> None:
    """Spec 15.1: a failed required deterministic check blocks the dimension."""
    assert broken["conformance"]["mechanical"] == "FAIL"
    why = broken["conformance_rationale"]["mechanical"]
    assert "OUT-P0-EXACT" in why
    assert "OUT-WEP-INLINE-RANGE" in why


# -- integrity failures -----------------------------------------------------


def test_a_tampered_document_fails_bytes_and_block_hashes(
    ctx, load_bundle, load_ir, load_policy, tmp_path
) -> None:
    """Spec 14.2 and 16.2: the trace describes specific bytes."""
    bundle = load_bundle("assess-bundle")
    edited = bundle["text"].replace("Prototype one", "Prototype three")
    target = tmp_path / "document.md"
    target.write_text(edited, encoding="utf-8")

    report = lint_output(
        ctx,
        output_path=target,
        trace_document=bundle["trace"],
        ir_document=load_ir("assess_conforming"),
        policy_document=load_policy("assess"),
    )
    checks = by_id(report)
    assert checks["OUT-BYTES"]["status"] == "FAIL"
    assert checks["OUT-BLOCK-HASHES"]["status"] == "FAIL"
    assert "assess-recommendation" in checks["OUT-BLOCK-HASHES"]["detail"]


def test_a_missing_marker_is_reported(
    ctx, load_bundle, load_ir, load_policy, tmp_path
) -> None:
    """Spec 14.4: a declared block that is not in the document breaks the source map."""
    bundle = load_bundle("assess-bundle")
    edited = bundle["text"].replace("<!-- ats:block assess-boundary -->\n", "")
    target = tmp_path / "document.md"
    target.write_text(edited, encoding="utf-8")

    trace = copy.deepcopy(bundle["trace"])
    trace["output_sha256"] = sha256_hex(edited.encode("utf-8"))
    from ats.canonical import seal

    report = lint_output(
        ctx,
        output_path=target,
        trace_document=seal(trace),
        ir_document=load_ir("assess_conforming"),
        policy_document=load_policy("assess"),
    )
    checks = by_id(report)
    assert checks["OUT-MARKERS"]["status"] == "FAIL"
    assert "assess-boundary" in checks["OUT-MARKERS"]["detail"]


def test_a_reference_to_an_object_outside_the_ir_is_reported(
    ctx, load_bundle, load_ir, load_policy
) -> None:
    """Spec 11.7: a rendering may not invent a material object."""
    from ats.canonical import seal

    bundle = load_bundle("assess-bundle")
    trace = copy.deepcopy(bundle["trace"])
    for block in trace["blocks"]:
        if block["block_id"] == "assess-key-judgment":
            block["claim_ids"] = ["c1", "c-invented"]
    report = lint_output(
        ctx,
        output_path=bundle["output_path"],
        trace_document=seal(trace),
        ir_document=load_ir("assess_conforming"),
        policy_document=load_policy("assess"),
    )
    checks = by_id(report)
    assert checks["OUT-IR-REFS"]["status"] == "FAIL"
    assert checks["OUT-UNKNOWN-REFS"]["status"] == "FAIL"
    assert "c-invented" in checks["OUT-UNKNOWN-REFS"]["detail"]


def test_a_parse_failure_makes_the_surface_checks_unavailable(
    ctx, load_bundle, load_ir, load_policy, tmp_path
) -> None:
    """Spec 14.4: a parser failure MUST NOT let token-only rules report conformance."""
    from ats.canonical import seal

    bundle = load_bundle("assess-bundle")
    edited = bundle["text"] + "\n<!-- ats:block trailing -->\n"
    target = tmp_path / "document.md"
    target.write_text(edited, encoding="utf-8")
    trace = copy.deepcopy(bundle["trace"])
    trace["output_sha256"] = sha256_hex(edited.encode("utf-8"))

    report = lint_output(
        ctx,
        output_path=target,
        trace_document=seal(trace),
        ir_document=load_ir("assess_conforming"),
        policy_document=load_policy("assess"),
    )
    checks = by_id(report)
    assert checks["OUT-MARKDOWN-PARSE"]["status"] == "FAIL"
    assert "trailing" in checks["OUT-MARKDOWN-PARSE"]["detail"]
    assert checks["OUT-MARKERS"]["status"] == "UNAVAILABLE"
    for check_id in SURFACE_CHECK_SPECS:
        assert checks[check_id]["status"] == "UNAVAILABLE", check_id
    assert report["conformance"]["mechanical"] in ("FAIL", "UNAVAILABLE")


# -- the receipt seam -------------------------------------------------------


def test_the_receipt_path_is_driven_end_to_end(
    ctx, load_bundle, load_ir, load_policy, assert_valid
) -> None:
    """Spec 14.13 and 16.12: a receipt is issued from a lint report and re-verified."""
    bundle = load_bundle("assess-bundle")
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    policy = ctx.policy(load_policy("assess"))
    output_bytes = bundle["output_path"].read_bytes()

    # Rebuild the trace from the rendered bytes rather than trusting the sidecar.
    parsed = parse_markdown(bundle["text"])
    metadata = {
        block["block_id"]: {
            key: value
            for key, value in block.items()
            if key
            not in ("block_id", "marker", "ordinal", "text_sha256")
        }
        for block in bundle["trace"]["blocks"]
    }
    rebuilt = build_trace(
        ctx,
        ir=ir,
        parsed=parsed,
        output_bytes=output_bytes,
        policy_snapshot_id=policy.snapshot_id,
        policy_sha256=policy.declared_sha256,
        block_metadata=metadata,
        renderer=bundle["trace"]["renderer"],
    )
    assert rebuilt["trace_sha256"] == bundle["trace"]["trace_sha256"]

    report = lint_output(
        ctx,
        output_path=bundle["output_path"],
        trace_document=rebuilt,
        ir_document=load_ir("assess_conforming"),
        policy_document=load_policy("assess"),
    )
    receipt = build_candidate_receipt(
        ctx,
        ir=ir,
        policy=policy,
        output_sha256=sha256_hex(output_bytes),
        lint_report=report,
        adjudicator=ADJUDICATOR,
    )
    assert_valid(receipt, "ats_acceptance_receipt_v1.schema.json")

    verification = verify_receipt(
        ctx,
        receipt,
        ir_document=load_ir("assess_conforming"),
        output_sha256=sha256_hex(output_bytes),
        policy=policy,
    )
    assert verification["status"] == "PASS"
    assert verification["unreplayable"] == []
    assert receipt["conformance"] == report["conformance"]


def test_a_supplied_receipt_is_verified_by_the_linter(run_lint) -> None:
    """Spec 16.12: OUT-RECEIPT re-checks the receipt against this bundle."""
    report = run_lint("assess-bundle", receipt=True)
    checks = by_id(report)
    assert checks["OUT-RECEIPT"]["status"] == "PASS"
    assert report["receipt_verification"]["status"] == "PASS"
    assert (
        report["receipt_verification"]["declared_sha256"]
        == report["receipt_verification"]["recomputed_sha256"]
    )


def test_undispositioned_findings_block_the_disposition_check(run_lint) -> None:
    """Spec 15.3: semantic-review conformance is impossible while findings are open."""
    report = run_lint("assess-bundle", receipt=True)
    check = by_id(report)["OUT-FINDING-DISPOSITIONS"]
    assert check["status"] == "FAIL"
    assert "undispositioned" in check["detail"]
    assert report["finding_dispositions"]["undispositioned"]


def test_without_a_receipt_dispositions_are_unavailable_not_passed(
    conforming,
) -> None:
    """Spec 5.4: no disposition record is UNAVAILABLE, never a pass."""
    checks = by_id(conforming)
    assert checks["OUT-FINDING-DISPOSITIONS"]["status"] == "UNAVAILABLE"
    assert checks["OUT-RECEIPT"]["status"] == "NOT_APPLICABLE"
    assert "receipt_verification" not in conforming


def test_a_receipt_bound_to_another_policy_fails_the_receipt_check(
    ctx, load_bundle, load_ir, load_policy
) -> None:
    """Spec 15.8: a claim under a superseded policy is stale."""
    from ats.canonical import seal

    bundle = load_bundle("assess-bundle")
    receipt = seal(
        {**copy.deepcopy(bundle["receipt"]), "policy_snapshot_sha256": "0" * 64}
    )
    report = lint_output(
        ctx,
        output_path=bundle["output_path"],
        trace_document=bundle["trace"],
        ir_document=load_ir("assess_conforming"),
        policy_document=load_policy("assess"),
        receipt_document=receipt,
    )
    check = by_id(report)["OUT-RECEIPT"]
    assert check["status"] == "FAIL"
    assert "15.8" in check["detail"]

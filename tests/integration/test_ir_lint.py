"""The full IR lint seam.

Package -> schemas -> policy -> IR -> detectors -> report -> report schema ->
seal verification. Section 14.1 fixes that stage order, Section 5.2 makes
conformance a five-dimension vector that is never averaged, and Section 15.x
fixes what each dimension may say.
"""

from __future__ import annotations

import copy

import pytest

from conftest import INVALID_IR_POLICY

from ats.canonical import verify_seal
from ats.errors import StalePolicyError
from ats.ir.lint import MECHANICAL_CHECKS, lint_ir
from ats.rules.results import RESULT_STATUSES

REPORT_SCHEMA_ID = "ats_ir_lint_report_v1.schema.json"

#: All twenty-six structural check identifiers (spec 12.8).
CHECK_IDS = frozenset(
    {
        "IR-SCHEMA",
        "IR-POLICY-IDENTITY",
        "IR-POLICY-CURRENTNESS",
        "IR-SOURCE-HASH",
        "IR-ID-UNIQUE",
        "IR-REFS",
        "IR-SECTION-PROFILE",
        "IR-PROFILE-SLOTS",
        "IR-CLAIM-ROLE-FIELDS",
        "IR-EVIDENCE-ENDPOINTS",
        "IR-GLOSSARY-REFS",
        "IR-LIKELIHOOD-VOCAB",
        "IR-FIRST-USE-RANGE",
        "IR-LIKELIHOOD-CONFIDENCE-SEP",
        "IR-CONFIDENCE-BASIS",
        "IR-UPDATE-INDICATORS",
        "IR-DEONTIC-VALIDITY",
        "IR-REQUIREMENT-SLOTS",
        "IR-ONE-OBLIGATION",
        "IR-QUANT-UNITS",
        "IR-POLARITY-QUANTIFIER",
        "IR-P0-P1-DECLARATIONS",
        "IR-EXTRACTION-STATUS",
        "IR-POLICY-EXCEPTIONS",
        "IR-CAPABILITY",
        "IR-CANONICAL",
        "IR-BASIS-SCHEMA",
    }
)

#: The failure each violation fixture must produce, named by check id or rule id.
#: Derived from the single field each fixture perturbs, not from a linter run.
EXPECTED_FAILURES: dict[str, tuple[str, ...]] = {
    "ambiguous_without_distinct_readings": ("IR-EXTRACTION-STATUS",),
    "blank_confidence_basis": ("ATS-EPI-005",),
    "concealed_actor": ("ATS-REQ-001",),
    "dangling_reference": ("IR-REFS",),
    "duplicate_ids": ("IR-ID-UNIQUE",),
    "missing_acceptance_criterion": (
        "ATS-REQ-003",
        "IR-REQUIREMENT-SLOTS",
        "IR-PROFILE-SLOTS",
    ),
    "no_update_indicator": ("IR-PROFILE-SLOTS",),
    "noncanonical_modal": ("ATS-DEON-001",),
    "noncanonical_wep_synonym": ("ATS-EPI-003",),
    # Recasting the key judgment as an observation also empties the ASSESS
    # key-judgment slot that Section 9.2.2 requires.
    "observation_with_confidence": (
        "ATS-EVID-001",
        "IR-CLAIM-ROLE-FIELDS",
        "IR-PROFILE-SLOTS",
    ),
    "possibility_term_only": ("ATS-EPI-007",),
    "quantifier_without_unit": ("ATS-NUM-001", "ATS-NUM-002"),
    "reserved_profile": (),
    "should_without_override": ("ATS-DEON-003",),
    "two_obligations": ("ATS-REQ-002", "IR-ONE-OBLIGATION"),
    "unanchored_relative_time": ("ATS-TIME-001", "ATS-TIME-002"),
    "wep_interval_mismatch": ("ATS-EPI-001", "IR-LIKELIHOOD-VOCAB"),
}


@pytest.fixture(scope="module")
def lint(ctx, load_ir, load_policy, source_path):
    def _lint(ir_name, policy_name, *, source=None):
        document = load_ir(ir_name) if isinstance(ir_name, str) else ir_name
        return lint_ir(
            ctx,
            document,
            load_policy(policy_name),
            source_path=source_path(source) if source else None,
        )

    return _lint


@pytest.fixture(scope="module")
def conforming_report(lint):
    return lint("assess_conforming", "assess", source="assess_rust_kernel.txt")


def failed_ids(report) -> set[str]:
    """Every check and rule that FAILed, by identifier."""
    return {c["check_id"] for c in report["structural_checks"] if c["status"] == "FAIL"} | {
        r["rule_id"] for r in report["rule_results"] if r["status"] == "FAIL"
    }


# -- the emitted report -----------------------------------------------------


def test_the_report_is_sealed_and_schema_valid(ctx, conforming_report, assert_valid) -> None:
    """Appendix C and 19.4: the report addresses itself and validates."""
    assert_valid(conforming_report, REPORT_SCHEMA_ID)
    ok, declared, recomputed = verify_seal(conforming_report)
    assert ok and declared == recomputed
    assert conforming_report["schema_version"] == "ats.ir_lint_report.v1"
    assert ctx.schemas.validate_document(conforming_report) == REPORT_SCHEMA_ID


def test_the_report_binds_every_input_it_was_evaluated_against(
    ctx, conforming_report, load_ir, load_policy
) -> None:
    """Spec 14.13 and 15.8: a claim names the exact artifacts behind it."""
    document = load_ir("assess_conforming")
    policy = load_policy("assess")
    assert conforming_report["artifact_id"] == document["artifact_id"]
    assert conforming_report["source_content_sha256"] == document["source"]["content_sha256"]
    assert conforming_report["policy_snapshot_id"] == policy["snapshot_id"]
    assert conforming_report["policy_sha256"] == policy["snapshot_sha256"]
    assert conforming_report["spec_version"] == ctx.spec_version
    assert conforming_report["profiles"] == ["ASSESS"]
    assert conforming_report["created_at"] == ctx.timestamp()

    implementation = conforming_report["implementation"]
    assert implementation["rule_registry_version"] == ctx.registry.spec_version
    assert implementation["lexicon_version"] == ctx.lexicon.version
    assert implementation["schema_set_sha256"] == ctx.schema_set_sha256


def test_every_registry_rule_appears_exactly_once(ctx, conforming_report) -> None:
    """Spec 5.5: every rule is answered, once, with an explicit result."""
    rule_ids = [r["rule_id"] for r in conforming_report["rule_results"]]
    assert sorted(rule_ids) == list(ctx.registry.ids())
    assert len(rule_ids) == len(set(rule_ids)) == 30
    assert conforming_report["summary"]["rules_total"] == 30
    assert sum(conforming_report["summary"]["by_status"].values()) == 30
    assert set(conforming_report["summary"]["by_status"]) == set(RESULT_STATUSES)


def test_all_twenty_seven_structural_checks_are_present(conforming_report) -> None:
    """Spec 12.8: the profile and structural validators run alongside the rules."""
    ids = [c["check_id"] for c in conforming_report["structural_checks"]]
    assert set(ids) == CHECK_IDS
    assert len(ids) == 27
    assert MECHANICAL_CHECKS <= CHECK_IDS
    # IR-BASIS-SCHEMA (draft.2 D-F) is advisory: basis declaration is a SHOULD
    # in the spec, so the check enforces the policy obligation but never gates.
    basis = next(c for c in conforming_report["structural_checks"] if c["check_id"] == "IR-BASIS-SCHEMA")
    assert basis["required"] is False
    assert basis["status"] == "NOT_APPLICABLE"


def test_the_conforming_assess_artifact_passes_mechanical_and_profile(
    conforming_report,
) -> None:
    """Spec 15.1 and 15.2: the spec's own conforming example is mechanically sound."""
    assert failed_ids(conforming_report) == set()
    conformance = conforming_report["conformance"]
    assert conformance["mechanical"] == "PASS"
    assert conformance["profile"] == "PASS"
    assert conforming_report["summary"]["required_failed"] == 0
    # Mechanical PASS is only reachable because no rule that is *required* under
    # ASSESS is unavailable. The syntax-dependent rules are unavailable, but the
    # ASSESS defaults make them advisory, so Section 15.1 is satisfied.
    assert conforming_report["summary"]["required_unavailable"] == 0
    unavailable = {
        r["rule_id"]
        for r in conforming_report["rule_results"]
        if r["status"] == "UNAVAILABLE"
    }
    assert unavailable == {
        "ATS-TERM-002",
        "ATS-REF-001",
        "ATS-SCOPE-001",
        "ATS-DISC-002",
        "ATS-DISC-003",
    }
    assert all(
        r["effective_state"] == "advisory"
        for r in conforming_report["rule_results"]
        if r["rule_id"] in unavailable
    )


def test_the_conforming_specify_artifact_passes_mechanical_and_profile(lint) -> None:
    """Spec 21.3: likewise for the conforming SPECIFY example."""
    report = lint("specify_conforming", "specify", source="specify_stale_policy.txt")
    assert failed_ids(report) == set()
    assert report["conformance"]["mechanical"] == "PASS"
    assert report["conformance"]["profile"] == "PASS"


# -- the conformance vector -------------------------------------------------


@pytest.mark.parametrize(
    ("ir_name", "policy_name"),
    [
        ("assess_conforming", "assess"),
        ("specify_conforming", "specify"),
        ("composed_profiles", "composed"),
        ("assess_transform_output", "assess_transform"),
        ("reserved_profile", "assess"),
        ("wep_interval_mismatch", "assess"),
    ],
)
def test_semantic_review_and_forecast_calibration_are_never_claimed(
    lint, ir_name, policy_name
) -> None:
    """Spec 15.3 and 15.5: this implementation holds neither authority nor a cohort."""
    report = lint(ir_name, policy_name)
    conformance = report["conformance"]
    assert conformance["semantic_review"] == "UNAVAILABLE"
    assert conformance["forecast_calibration"] == "INSUFFICIENT_EVIDENCE"

    rationale = report["conformance_rationale"]
    assert set(rationale) == set(conformance)
    for dimension, why in rationale.items():
        assert why.strip(), dimension
    assert "15.3" in rationale["semantic_review"]
    assert "14.11" in rationale["semantic_review"]
    assert "15.5" in rationale["forecast_calibration"]


def test_preservation_is_not_applicable_without_a_transform_profile(lint) -> None:
    """Spec 15.4: an artifact that is not a transformation output is NOT_APPLICABLE."""
    report = lint("assess_conforming", "assess", source="assess_rust_kernel.txt")
    assert report["conformance"]["preservation"] == "NOT_APPLICABLE"
    assert "15.4" in report["conformance_rationale"]["preservation"]


def test_preservation_is_unavailable_when_transform_is_active(lint) -> None:
    """Spec 6.4 and 15.4: unwaivable rules that cannot be evaluated block the dimension.

    Section 11.1 makes TRANSFORM a section-level profile carried alongside the
    content profile, so it is the artifact — not the policy alone — that puts a
    rendering under preservation obligations.
    """
    report = lint("assess_transform_output", "assess_transform")
    assert "TRANSFORM" in report["profiles"]
    assert report["conformance"]["preservation"] == "UNAVAILABLE"
    why = report["conformance_rationale"]["preservation"]
    assert "ATS-PRES-001" in why and "ATS-PRES-002" in why
    assert "6.4" in why
    for rule_id in ("ATS-PRES-001", "ATS-PRES-002"):
        result = next(r for r in report["rule_results"] if r["rule_id"] == rule_id)
        assert result["effective_state"] == "required"
        assert result["status"] == "UNAVAILABLE"


def test_a_transform_policy_alone_does_not_activate_preservation(lint) -> None:
    """Spec 11.1 and 6.5: the artifact's own section profiles decide what runs."""
    report = lint("assess_conforming", "assess_transform")
    assert report["profiles"] == ["ASSESS"]
    assert report["conformance"]["preservation"] == "NOT_APPLICABLE"


def test_the_five_dimensions_are_reported_independently(conforming_report) -> None:
    """Spec 5.2 and 15.6: no dimension is averaged into another."""
    conformance = conforming_report["conformance"]
    assert set(conformance) == {
        "mechanical",
        "profile",
        "semantic_review",
        "preservation",
        "forecast_calibration",
    }
    allowed = {"PASS", "FAIL", "NOT_APPLICABLE", "UNAVAILABLE", "INSUFFICIENT_EVIDENCE"}
    assert set(conformance.values()) <= allowed
    # Two dimensions are not PASS while mechanical is: no compensation happened.
    assert conformance["mechanical"] == "PASS"
    assert conformance["semantic_review"] != "PASS"


def test_mechanical_is_unavailable_when_the_source_binding_is_unverified(lint) -> None:
    """Spec 5.4 and 14.2: an unverified precondition is UNAVAILABLE, not PASS."""
    report = lint("assess_conforming", "assess")
    source_check = next(
        c for c in report["structural_checks"] if c["check_id"] == "IR-SOURCE-HASH"
    )
    assert source_check["status"] == "UNAVAILABLE"
    assert report["conformance"]["mechanical"] == "UNAVAILABLE"
    assert "IR-SOURCE-HASH" in report["conformance_rationale"]["mechanical"]
    assert "5.4" in report["conformance_rationale"]["mechanical"]


def test_a_reserved_profile_makes_the_profile_dimension_unavailable(lint) -> None:
    """Spec 9.5: a reserved profile is preserved, and completeness is unavailable."""
    report = lint("reserved_profile", "assess")
    assert report["conformance"]["profile"] == "UNAVAILABLE"
    assert report["unsupported_profiles"] == ["X-ARQ-EXPLAIN-1"]
    assert {r["status"] for r in report["rule_results"]} == {"NOT_APPLICABLE"}


# -- violation fixtures -----------------------------------------------------


@pytest.mark.parametrize("fixture_name", sorted(INVALID_IR_POLICY))
def test_each_violation_fixture_fails_for_the_reason_it_exists(
    lint, fixture_name
) -> None:
    """Spec 16.4 and 12.9: a fixture must fail for the reason the rule exists."""
    report = lint(fixture_name, INVALID_IR_POLICY[fixture_name])
    expected = set(EXPECTED_FAILURES[fixture_name])
    observed = failed_ids(report)
    assert observed == expected, f"{fixture_name}: {sorted(observed)}"


@pytest.mark.parametrize("fixture_name", sorted(INVALID_IR_POLICY))
def test_no_violation_fixture_produces_a_spurious_pass(
    ctx, lint, fixture_name
) -> None:
    """Spec 5.4 and 16.5: PASS requires a complete procedure and real authority."""
    report = lint(fixture_name, INVALID_IR_POLICY[fixture_name])
    for result in report["rule_results"]:
        if result["status"] != "PASS":
            continue
        assert result["decision_power"] == "decides", result["rule_id"]
        assert result["detector"]["authority"] == "conformance_evidence", result["rule_id"]
        assert result["finding_ids"] == [], result["rule_id"]
        cap = ctx.capability.rules[result["rule_id"]]
        assert cap.produces_conformance_evidence, result["rule_id"]


@pytest.mark.parametrize(
    "fixture_name",
    sorted(
        f for f, ids in EXPECTED_FAILURES.items() if any(i.startswith("ATS-") for i in ids)
    ),
)
def test_a_rule_failure_carries_findings_into_the_report(lint, fixture_name) -> None:
    """Spec 13.1: a FAIL is grounded in at least one located finding."""
    report = lint(fixture_name, INVALID_IR_POLICY[fixture_name])
    failing = [r for r in report["rule_results"] if r["status"] == "FAIL"]
    assert failing
    finding_ids = {f["finding_id"] for f in report["findings"]}
    for result in failing:
        assert result["finding_ids"], result["rule_id"]
        assert set(result["finding_ids"]) <= finding_ids
    for finding in report["findings"]:
        assert finding["schema_version"] == "ats.finding.v1"
        assert finding["spans"]


def test_a_failing_artifact_does_not_report_mechanical_pass(lint) -> None:
    """Spec 15.1: a required deterministic failure blocks the mechanical dimension."""
    report = lint("wep_interval_mismatch", "assess", source="assess_rust_kernel.txt")
    assert report["conformance"]["mechanical"] == "FAIL"
    why = report["conformance_rationale"]["mechanical"]
    assert "IR-LIKELIHOOD-VOCAB" in why or "ATS-EPI-001" in why


# -- policy interaction -----------------------------------------------------


def test_a_refused_weakening_override_is_recorded_in_the_report(lint) -> None:
    """Spec 6.2: a declined directive is retained, not dropped."""
    report = lint("assess_conforming", "weakening_override")
    ignored = report["ignored_policy_directives"]
    assert [d["rule_id"] for d in ignored] == ["ATS-EPI-001"]
    assert ignored[0]["attempted_state"] == "advisory"
    assert ignored[0]["effective_state"] == "required"
    result = next(r for r in report["rule_results"] if r["rule_id"] == "ATS-EPI-001")
    assert result["effective_state"] == "required"


def test_a_scoped_exception_downgrades_the_rule_it_names(lint) -> None:
    """Spec 6.3: an exception in force changes the effective state, in scope."""
    report = lint("assess_conforming", "scoped_exception")
    result = next(r for r in report["rule_results"] if r["rule_id"] == "ATS-EPI-002")
    assert result["effective_state"] == "advisory"
    other = next(r for r in report["rule_results"] if r["rule_id"] == "ATS-EPI-001")
    assert other["effective_state"] == "required"


def test_an_expired_exception_fails_currentness_and_restores_the_state(lint) -> None:
    """Spec 6.3 and 14.3: expiry invalidates the exception."""
    report = lint("assess_conforming", "expired_exception")
    failed = failed_ids(report)
    assert {"IR-POLICY-CURRENTNESS", "IR-POLICY-EXCEPTIONS"} <= failed
    result = next(r for r in report["rule_results"] if r["rule_id"] == "ATS-EPI-002")
    assert result["effective_state"] == "required"


def test_lint_refuses_a_stale_policy_snapshot(ctx, load_ir, load_policy) -> None:
    """Spec 14.3: currentness is resolved before evaluation, and fails closed."""
    policy = {**load_policy("assess"), "snapshot_sha256": "0" * 64}
    with pytest.raises(StalePolicyError):
        lint_ir(ctx, load_ir("assess_conforming"), policy)


def test_a_composed_artifact_accumulates_the_stricter_state(lint) -> None:
    """Spec 6.5: composition takes the stricter state across profiles."""
    report = lint("composed_profiles", "composed")
    assert report["profiles"] == ["ASSESS", "SPECIFY"]
    requirement_rule = next(
        r for r in report["rule_results"] if r["rule_id"] == "ATS-REQ-001"
    )
    assert requirement_rule["effective_state"] == "required"
    assert requirement_rule["status"] != "NOT_APPLICABLE"


# -- honest insufficiency ---------------------------------------------------


def test_unavailable_rules_name_their_missing_inputs_in_the_report(
    ctx, conforming_report
) -> None:
    """Spec 5.4 and 20.6: UNAVAILABLE says what is missing."""
    unavailable = [
        r for r in conforming_report["rule_results"] if r["status"] == "UNAVAILABLE"
    ]
    assert unavailable
    for result in unavailable:
        assert result["missing_inputs"], result["rule_id"]
        required = set(ctx.registry.get(result["rule_id"]).required_inputs)
        assert set(result["missing_inputs"]) <= required
        assert result["reason"].strip()


def test_an_unimplemented_rule_would_report_unavailable(
    ctx, load_ir, load_policy, monkeypatch
) -> None:
    """Spec 5.5: a rule with no detector is UNAVAILABLE, never a silent pass."""
    import ats.ir.lint as lint_module

    real = lint_module.load_detectors(ctx.registry.ids())
    monkeypatch.setattr(
        lint_module,
        "load_detectors",
        lambda ids: {k: v for k, v in real.items() if k != "ATS-EPI-001"},
    )
    report = lint_ir(ctx, load_ir("assess_conforming"), load_policy("assess"))
    result = next(r for r in report["rule_results"] if r["rule_id"] == "ATS-EPI-001")
    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "no detector is registered for this rule in this build"
    assert set(result["missing_inputs"]) == set(
        ctx.registry.get("ATS-EPI-001").required_inputs
    )


def test_linting_does_not_mutate_the_documents_it_was_given(
    ctx, load_ir, load_policy, source_path
) -> None:
    """Spec 16.2: evaluation is a pure function of its inputs."""
    document = load_ir("assess_conforming")
    policy = load_policy("assess")
    before = (copy.deepcopy(document), copy.deepcopy(policy))
    lint_ir(ctx, document, policy, source_path=source_path("assess_rust_kernel.txt"))
    assert (document, policy) == before

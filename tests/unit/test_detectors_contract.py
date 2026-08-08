"""The calling contract every deterministic detector obeys.

Spec Section 5.4 makes a required check that cannot execute UNAVAILABLE rather
than PASS. Section 16.5 says the absence of a surfaced finding does not prove a
required semantic rule passed. Section 12.3 caps what each detector class may
conclude. This file asserts those three invariants over every rule and every
fixture at once, so no individual detector can quietly buy itself a pass.

The draft.1 package (the default context) carries 30 rules and the draft.2
package carries 36. The invariants are asserted over both: the draft.1 tests
below keep their historical scope, and the draft.2 tests run the same checks
over the 36-rule registry and the 24 draft.2 rule fixtures. Two draft.2
TRANSFORM rules (ATS-BASIS-002, ATS-PRES-003) receive their transformation
inputs through document extensions when present and report UNAVAILABLE with the
missing inputs named when absent (ADR-0002), so their power assertion is
scoped to the evaluations where the inputs are supplied.
"""

from __future__ import annotations

import itertools

import pytest

from conftest import (
    INVALID_IR_POLICY,
    IR_DRAFT2_ROOTS,
    VALID_IR_NAMES,
    clean_status,
)

from ats.rules.deterministic import load_detectors
from ats.rules.registry import DETECTOR_CLASS_MAX_AUTHORITY
from ats.rules.results import DecisionPower, Status

#: The decision power each rule declares, derived from what the TextIR surface
#: can supply (spec 5.5) and from the detector classes the registry lists for
#: the rule (spec 12.3). A rule whose only listed classes are D3/D4 cannot
#: declare a complete decision procedure, because Section 12.3 caps D3 output
#: at proposal_only and such a detector may never report PASS.
EXPECTED_POWER: dict[str, str] = {
    "ATS-TERM-001": "detects_violations",
    "ATS-TERM-002": "undecidable",
    "ATS-TERM-003": "detects_violations",
    "ATS-REF-001": "undecidable",
    "ATS-SCOPE-001": "undecidable",
    "ATS-NUM-001": "decides",
    "ATS-NUM-002": "detects_violations",
    "ATS-TIME-001": "detects_violations",
    "ATS-TIME-002": "detects_violations",
    "ATS-PRES-001": "undecidable",
    "ATS-EPI-001": "decides",
    "ATS-EPI-002": "decides",
    "ATS-EPI-003": "decides",
    "ATS-EPI-004": "detects_violations",
    "ATS-EPI-005": "decides",
    "ATS-EPI-006": "detects_violations",
    "ATS-EPI-007": "decides",
    "ATS-DEON-001": "decides",
    "ATS-DEON-002": "detects_violations",
    "ATS-DEON-003": "decides",
    "ATS-REQ-001": "decides",
    "ATS-REQ-002": "detects_violations",
    "ATS-REQ-003": "decides",
    "ATS-EVID-001": "decides",
    "ATS-EVID-002": "detects_violations",
    "ATS-EVID-003": "detects_violations",
    "ATS-DISC-001": "detects_violations",
    "ATS-DISC-002": "undecidable",
    "ATS-DISC-003": "undecidable",
    "ATS-PRES-002": "undecidable",
    # -- draft.2 additions (draft.2 registry: 36 rules) --------------------
    "ATS-COORD-001": "decides",
    "ATS-COORD-002": "decides",
    "ATS-BASIS-001": "detects_violations",
    "ATS-BASIS-002": "decides",
    "ATS-PRES-003": "decides",
    "ATS-CLOSE-001": "detects_violations",
}

#: Rules the TextIR surface cannot decide at all (spec 5.5). Each names the
#: input it lacks.
UNDECIDABLE_RULES = tuple(sorted(r for r, p in EXPECTED_POWER.items() if p == "undecidable"))

#: Draft.2 TRANSFORM rules whose transformation inputs arrive through document
#: extensions when present; without those inputs they report UNAVAILABLE with
#: the missing inputs named and their declared power is not exercised.
CONDITIONAL_IR_RULES = ("ATS-BASIS-002", "ATS-PRES-003")

#: Rules that opt into the ADR-0002 vacuous-pass discipline (review finding F1):
#: a clean run whose every subcheck is NOT_APPLICABLE reports NOT_APPLICABLE
#: instead of a decided PASS. The coordinate rules are exact set checks, and a
#: renderer could otherwise drop every coordinate with nothing failing.
VACUOUS_PASS_RULES = ("ATS-COORD-001", "ATS-COORD-002")

#: (ir fixture, policy fixture) pairs covering every checked-in TextIR.
ALL_CASES = tuple(
    itertools.chain(
        (("assess_conforming", "assess"),
         ("assess_partial_extraction", "assess"),
         ("assess_represented_ambiguity", "assess"),
         ("assess_transform_output", "assess_transform"),
         ("composed_profiles", "composed"),
         ("specify_conforming", "specify")),
        tuple(sorted(INVALID_IR_POLICY.items())),
    )
)

#: The 24 draft.2 rule fixtures, each evaluated under the draft.2 policy
#: snapshot (which carries ASSESS, SPECIFY, and TRANSFORM profiles).
DRAFT2_FIXTURE_STEMS = tuple(
    sorted(stem for root in IR_DRAFT2_ROOTS for stem in (p.stem for p in root.glob("ats-*.json")))
)
DRAFT2_CASES = tuple((stem, "draft2") for stem in DRAFT2_FIXTURE_STEMS)


def _expected_power_for(registry_ids: set[str]) -> dict[str, str]:
    """EXPECTED_POWER sliced to one package version's registry."""
    return {rid: p for rid, p in EXPECTED_POWER.items() if rid in registry_ids}


def test_every_valid_fixture_is_covered_by_a_case() -> None:
    """Guard: the cross-cutting assertions below must see every fixture."""
    assert {ir for ir, _ in ALL_CASES} >= set(VALID_IR_NAMES)
    assert {ir for ir, _ in ALL_CASES} >= set(INVALID_IR_POLICY)


# -- registry coverage (draft.1: 30 rules, draft.2: 36 rules) --------------


def test_load_detectors_covers_exactly_the_registry(ctx) -> None:
    """Spec 5.5: every draft.1 rule must be answered, even if the answer is UNAVAILABLE."""
    detectors = load_detectors(rule_ids=ctx.registry.ids())
    assert tuple(sorted(detectors)) == ctx.registry.ids()
    assert len(detectors) == 30


def test_load_detectors_covers_the_full_draft2_registry(ctx_d2) -> None:
    """Spec 5.5: the draft.2 lint dispatch sees exactly the 36-rule registry."""
    detectors = load_detectors(rule_ids=ctx_d2.registry.ids())
    assert tuple(sorted(detectors)) == ctx_d2.registry.ids()
    assert len(detectors) == 36
    assert set(EXPECTED_POWER) == set(ctx_d2.registry.ids())


def test_declared_power_matches_the_registry_and_capability(ctx) -> None:
    """Spec 12.3 and 16.1: the declaration and the runtime state the same power."""
    expected = _expected_power_for(set(ctx.registry.ids()))
    assert set(expected) == set(ctx.registry.ids())
    for rule_id, power in sorted(expected.items()):
        cap = ctx.capability.rules[rule_id]
        assert cap.decision_power == power, rule_id
        if power == "undecidable":
            continue
        # A detector may only declare a complete procedure when its class is
        # allowed to produce conformance evidence at all (spec 12.3).
        ceiling = DETECTOR_CLASS_MAX_AUTHORITY[cap.detector_class]
        if power == "decides":
            assert ceiling == "conformance_evidence", rule_id


def test_declared_power_matches_the_registry_and_capability_draft2(ctx_d2) -> None:
    """Spec 12.3 and 16.1 over the full 36-rule draft.2 registry."""
    for rule_id, power in sorted(EXPECTED_POWER.items()):
        cap = ctx_d2.capability.rules[rule_id]
        assert cap.decision_power == power, rule_id
        if power == "undecidable":
            continue
        ceiling = DETECTOR_CLASS_MAX_AUTHORITY[cap.detector_class]
        if power == "decides":
            assert ceiling == "conformance_evidence", rule_id


# -- runtime behaviour (draft.1 fixtures) -----------------------------------


@pytest.mark.parametrize(("ir_name", "policy_name"), ALL_CASES)
def test_runtime_power_matches_the_declaration(ctx, evaluate_ir, ir_name, policy_name) -> None:
    """Spec 16.1: the capability declaration must describe the running code."""
    expected = _expected_power_for(set(ctx.registry.ids()))
    results = evaluate_ir(ir_name, policy_name)
    assert set(results) == set(ctx.registry.ids())
    for rule_id, result in sorted(results.items()):
        assert str(result.decision_power) == expected[rule_id], (ir_name, rule_id)
        assert result.rule_version == ctx.registry.get(rule_id).rule_version
        assert result.detector.authority in (
            "conformance_evidence",
            "candidate_only",
            "proposal_only",
        )


@pytest.mark.parametrize(("ir_name", "policy_name"), ALL_CASES)
def test_no_detector_passes_without_a_decision_procedure_and_authority(
    evaluate_ir, ir_name, policy_name
) -> None:
    """Spec 5.4, 12.3, 16.5: PASS requires `decides` AND conformance_evidence."""
    for rule_id, result in sorted(evaluate_ir(ir_name, policy_name).items()):
        if result.status is not Status.PASS:
            continue
        assert result.decision_power is DecisionPower.DECIDES, (ir_name, rule_id)
        assert result.detector.authority == "conformance_evidence", (ir_name, rule_id)
        assert result.findings == (), (ir_name, rule_id)
        assert result.missing_inputs == (), (ir_name, rule_id)
        assert result.effective_state != "disabled", (ir_name, rule_id)


@pytest.mark.parametrize(("ir_name", "policy_name"), ALL_CASES)
def test_a_finding_never_coexists_with_a_pass_or_an_unavailable(
    evaluate_ir, ir_name, policy_name
) -> None:
    """Spec 5.4: a surfaced finding is FAIL or REVIEW_REQUIRED, never a pass."""
    for rule_id, result in sorted(evaluate_ir(ir_name, policy_name).items()):
        if not result.findings:
            continue
        assert result.status in (Status.FAIL, Status.REVIEW_REQUIRED), (ir_name, rule_id)
        if result.status is Status.FAIL:
            assert result.detector.authority == "conformance_evidence", (ir_name, rule_id)
        else:
            assert result.detector.authority != "conformance_evidence", (ir_name, rule_id)


@pytest.mark.parametrize(("ir_name", "policy_name"), ALL_CASES)
def test_a_clean_run_reports_the_status_its_power_entitles_it_to(
    evaluate_ir, ir_name, policy_name
) -> None:
    """Spec 16.5: only a complete decision procedure may conclude from silence."""
    for rule_id, result in sorted(evaluate_ir(ir_name, policy_name).items()):
        if result.effective_state == "disabled":
            assert result.status is Status.NOT_APPLICABLE, (ir_name, rule_id)
            continue
        if result.findings:
            continue
        expected = clean_status(EXPECTED_POWER[rule_id], result.detector.authority)
        assert str(result.status) == expected, (ir_name, rule_id)


@pytest.mark.parametrize("rule_id", UNDECIDABLE_RULES)
def test_every_undecidable_rule_names_a_missing_input(ctx, evaluate_ir, rule_id) -> None:
    """Spec 5.4 and 20.6: UNAVAILABLE must say what is missing, not just decline."""
    result = evaluate_ir("assess_conforming", "assess")[rule_id]
    required = set(ctx.registry.get(rule_id).required_inputs)
    if result.status is Status.NOT_APPLICABLE:
        pytest.skip("disabled under this policy; input availability is not reached")
    assert result.status is Status.UNAVAILABLE
    assert result.missing_inputs, rule_id
    assert set(result.missing_inputs) <= required, rule_id
    assert result.reason.strip(), rule_id
    assert result.findings == ()
    # The same inputs are declared in the published capability (spec 16.1).
    assert set(ctx.capability.rules[rule_id].blocking_inputs) == set(result.missing_inputs)


@pytest.mark.parametrize(("ir_name", "policy_name"), ALL_CASES)
def test_every_subcheck_record_is_grounded_and_typed(evaluate_ir, ir_name, policy_name) -> None:
    """Spec 12.10 and 16.8: a check explains itself against a spec section."""
    allowed = {"PASS", "FAIL", "NOT_APPLICABLE", "REVIEW_REQUIRED", "UNAVAILABLE"}
    for rule_id, result in sorted(evaluate_ir(ir_name, policy_name).items()):
        if result.effective_state == "disabled":
            assert result.subchecks == (), (ir_name, rule_id)
            continue
        assert result.subchecks, (ir_name, rule_id)
        for record in result.subchecks:
            assert record["status"] in allowed, (rule_id, record)
            assert record["spec_ref"].startswith("ATS-1 "), (rule_id, record)
            assert record["detail"].strip(), (rule_id, record)


@pytest.mark.parametrize(("ir_name", "policy_name"), ALL_CASES)
def test_findings_are_well_formed_and_bound_to_the_registry(
    ctx, evaluate_ir, load_ir, ir_name, policy_name
) -> None:
    """Spec 13.1: a finding carries the rule's own severity and protected impact."""
    artifact_id = load_ir(ir_name)["artifact_id"]
    seen: set[str] = set()
    for rule_id, result in sorted(evaluate_ir(ir_name, policy_name).items()):
        rule = ctx.registry.get(rule_id)
        for finding in result.findings:
            assert finding.rule_id == rule_id
            assert finding.artifact_id == artifact_id
            assert finding.severity == rule.severity
            assert finding.protected_impact == rule.protected_impact
            assert finding.spans, "spec 13.1 requires a locatable span"
            assert finding.summary.strip()
            assert finding.state == "proposed", "spec 13.6: a new finding is proposed"
            assert finding.finding_id not in seen, "spec 13.9: identities are unique"
            seen.add(finding.finding_id)
            assert finding.finding_id.startswith(f"{artifact_id}:{rule_id}:{finding.issue_code}:")


def test_findings_validate_against_the_normative_finding_schema(
    evaluate_ir, assert_valid
) -> None:
    """Spec 13.1 and 19.4: every emitted finding is a schema-valid object."""
    emitted = 0
    for ir_name, policy_name in ALL_CASES:
        for result in evaluate_ir(ir_name, policy_name).values():
            for finding in result.findings:
                assert_valid(finding.to_dict(), "ats_finding_v1.schema.json")
                emitted += 1
    assert emitted > 0, "the violation fixtures must raise findings"


def test_rule_results_validate_against_the_local_result_schema(
    evaluate_ir, assert_valid
) -> None:
    """Spec 19.4: the per-rule result is a schema-governed object too."""
    for result in evaluate_ir("assess_conforming", "assess").values():
        assert_valid(result.to_dict(), "ats_rule_result_v1.schema.json")


def test_disabled_rules_report_not_applicable_under_a_reserved_profile(evaluate_ir) -> None:
    """Spec 9.5: a reserved profile inherits no rule states, so nothing runs."""
    results = evaluate_ir("reserved_profile", "assess")
    assert {str(r.status) for r in results.values()} == {"NOT_APPLICABLE"}
    assert all(r.effective_state == "disabled" for r in results.values())
    assert all(r.findings == () for r in results.values())


# -- runtime behaviour (draft.2 fixtures, 36 rules) --------------------------


def _draft2_assert_statuses_allowed(
    ctx_d2, evaluate_ir_d2, ir_name, policy_name
) -> None:
    """Shared draft.2 invariants over every fixture in :data:`DRAFT2_CASES`."""
    results = evaluate_ir_d2(ir_name, policy_name)
    assert set(results) == set(ctx_d2.registry.ids())
    for rule_id, result in sorted(results.items()):
        assert result.rule_version == ctx_d2.registry.get(rule_id).rule_version
        assert result.detector.authority in (
            "conformance_evidence",
            "candidate_only",
            "proposal_only",
        )


@pytest.mark.parametrize(("ir_name", "policy_name"), DRAFT2_CASES)
def test_runtime_power_matches_the_declaration_draft2(
    ctx_d2, evaluate_ir_d2, ir_name, policy_name
) -> None:
    """Spec 16.1 over the 36-rule registry.

    ATS-BASIS-002 and ATS-PRES-003 declare a complete procedure on the surface
    where their transformation inputs are supplied; over an IR that carries no
    such inputs they report UNAVAILABLE with the missing inputs named (never
    PASS), and their declared power is not exercised on that evaluation.
    """
    _draft2_assert_statuses_allowed(ctx_d2, evaluate_ir_d2, ir_name, policy_name)
    for rule_id, result in sorted(evaluate_ir_d2(ir_name, policy_name).items()):
        if rule_id in CONDITIONAL_IR_RULES and result.status is Status.UNAVAILABLE:
            assert result.missing_inputs, (ir_name, rule_id)
            assert str(result.decision_power) == "undecidable", (ir_name, rule_id)
            continue
        assert str(result.decision_power) == EXPECTED_POWER[rule_id], (ir_name, rule_id)


@pytest.mark.parametrize(("ir_name", "policy_name"), DRAFT2_CASES)
def test_no_detector_passes_without_a_decision_procedure_and_authority_draft2(
    evaluate_ir_d2, ir_name, policy_name
) -> None:
    """Spec 5.4, 12.3, 16.5: PASS requires `decides` AND conformance_evidence."""
    for rule_id, result in sorted(evaluate_ir_d2(ir_name, policy_name).items()):
        if result.status is not Status.PASS:
            continue
        assert result.decision_power is DecisionPower.DECIDES, (ir_name, rule_id)
        assert result.detector.authority == "conformance_evidence", (ir_name, rule_id)
        assert result.findings == (), (ir_name, rule_id)
        assert result.missing_inputs == (), (ir_name, rule_id)
        assert result.effective_state != "disabled", (ir_name, rule_id)


@pytest.mark.parametrize(("ir_name", "policy_name"), DRAFT2_CASES)
def test_a_finding_never_coexists_with_a_pass_or_an_unavailable_draft2(
    evaluate_ir_d2, ir_name, policy_name
) -> None:
    """Spec 5.4: a surfaced finding is FAIL or REVIEW_REQUIRED, never a pass."""
    for rule_id, result in sorted(evaluate_ir_d2(ir_name, policy_name).items()):
        if not result.findings:
            continue
        assert result.status in (Status.FAIL, Status.REVIEW_REQUIRED), (ir_name, rule_id)
        if result.status is Status.FAIL:
            assert result.detector.authority == "conformance_evidence", (ir_name, rule_id)
        else:
            assert result.detector.authority != "conformance_evidence", (ir_name, rule_id)


@pytest.mark.parametrize(("ir_name", "policy_name"), DRAFT2_CASES)
def test_a_clean_run_reports_the_status_its_power_entitles_it_to_draft2(
    evaluate_ir_d2, ir_name, policy_name
) -> None:
    """Spec 16.5: silence concludes only for a complete decision procedure."""
    for rule_id, result in sorted(evaluate_ir_d2(ir_name, policy_name).items()):
        if result.effective_state == "disabled":
            assert result.status is Status.NOT_APPLICABLE, (ir_name, rule_id)
            continue
        if result.findings:
            continue
        if rule_id in CONDITIONAL_IR_RULES and result.status is Status.UNAVAILABLE:
            # Transformation inputs absent: the rule honestly reports
            # UNAVAILABLE with the missing inputs named, never PASS by absence.
            assert result.missing_inputs, (ir_name, rule_id)
            continue
        if rule_id in VACUOUS_PASS_RULES and result.status is Status.NOT_APPLICABLE:
            # ADR-0002 / review F1: the coordinate rules opt into the discipline
            # that a clean run with every subcheck NOT_APPLICABLE reports
            # NOT_APPLICABLE (no exact comparison ran) rather than a decided
            # PASS. NOT_APPLICABLE never blocks, so a document that never
            # declares a coordinate block is not penalized.
            assert result.findings == (), (ir_name, rule_id)
            continue
        expected = clean_status(EXPECTED_POWER[rule_id], result.detector.authority)
        assert str(result.status) == expected, (ir_name, rule_id)


@pytest.mark.parametrize(("ir_name", "policy_name"), DRAFT2_CASES)
def test_every_subcheck_record_is_grounded_and_typed_draft2(
    evaluate_ir_d2, ir_name, policy_name
) -> None:
    """Spec 12.10 and 16.8 over the draft.2 fixtures."""
    allowed = {"PASS", "FAIL", "NOT_APPLICABLE", "REVIEW_REQUIRED", "UNAVAILABLE"}
    for rule_id, result in sorted(evaluate_ir_d2(ir_name, policy_name).items()):
        if result.effective_state == "disabled":
            assert result.subchecks == (), (ir_name, rule_id)
            continue
        assert result.subchecks, (ir_name, rule_id)
        for record in result.subchecks:
            assert record["status"] in allowed, (rule_id, record)
            assert record["spec_ref"].startswith("ATS-1 "), (rule_id, record)
            assert record["detail"].strip(), (rule_id, record)


@pytest.mark.parametrize(("ir_name", "policy_name"), DRAFT2_CASES)
def test_findings_are_well_formed_and_bound_to_the_registry_draft2(
    ctx_d2, evaluate_ir_d2, load_ir, ir_name, policy_name
) -> None:
    """Spec 13.1: draft.2 findings carry the rule's own severity and impact."""
    artifact_id = load_ir(ir_name)["artifact_id"]
    seen: set[str] = set()
    for rule_id, result in sorted(evaluate_ir_d2(ir_name, policy_name).items()):
        rule = ctx_d2.registry.get(rule_id)
        for finding in result.findings:
            assert finding.rule_id == rule_id
            assert finding.artifact_id == artifact_id
            assert finding.severity == rule.severity
            assert finding.protected_impact == rule.protected_impact
            assert finding.spans, "spec 13.1 requires a locatable span"
            assert finding.summary.strip()
            assert finding.state == "proposed", "spec 13.6: a new finding is proposed"
            assert finding.finding_id not in seen, "spec 13.9: identities are unique"
            seen.add(finding.finding_id)
            assert finding.finding_id.startswith(f"{artifact_id}:{rule_id}:{finding.issue_code}:")


def test_draft2_findings_validate_against_the_normative_finding_schema(
    ctx_d2, evaluate_ir_d2
) -> None:
    """Spec 13.1 and 19.4: draft.2 findings are schema-valid objects too."""
    from ats.errors import SchemaValidationError

    emitted = 0
    for ir_name, policy_name in DRAFT2_CASES:
        for result in evaluate_ir_d2(ir_name, policy_name).values():
            for finding in result.findings:
                try:
                    ctx_d2.schemas.validate(finding.to_dict(), "ats_finding_v1.schema.json")
                except SchemaValidationError as exc:  # pragma: no cover - failure path
                    rendered = "; ".join(
                        f"{v.pointer or '/'}: {v.message}" for v in exc.violations
                    )
                    raise AssertionError(
                        f"{finding.finding_id} failed ats_finding_v1: {rendered}"
                    ) from None
                emitted += 1
    assert emitted > 0, "the draft.2 violation fixtures must raise findings"


def test_draft2_rule_results_validate_against_the_local_result_schema(
    ctx_d2, evaluate_ir_d2
) -> None:
    """Spec 19.4: draft.2 per-rule results validate too."""
    from ats.errors import SchemaValidationError

    for result in evaluate_ir_d2("ats-basis-002-promoted", "draft2").values():
        try:
            ctx_d2.schemas.validate(result.to_dict(), "ats_rule_result_v1.schema.json")
        except SchemaValidationError as exc:  # pragma: no cover - failure path
            rendered = "; ".join(f"{v.pointer or '/'}: {v.message}" for v in exc.violations)
            raise AssertionError(f"{result.rule_id}: {rendered}") from None

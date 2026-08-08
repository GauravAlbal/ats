"""The twenty-seven structural checks over a TextIR document and its policy.

Section 12.8 puts these alongside the thirty rules: an artifact can satisfy
every local rule and still be structurally incoherent. Each check carries a
stable identifier, a spec reference, and one of the five statuses, and none of
them reports PASS because nothing was inspected (Section 5.4).
"""

from __future__ import annotations

import copy

import pytest

from ats.canonical import seal
from ats.errors import SchemaViolation
from ats.ir.checks import run_structural_checks
from ats.ir.model import IrDocument
from ats.rules.results import Status

#: The binding identifier set. All twenty-six run on every artifact.
CHECK_IDS = (
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
)


@pytest.fixture(scope="module")
def run_checks(ctx, load_ir, load_policy, source_path):
    """Run the structural checks over a document, returning ``check_id -> result``."""

    def _run(document, policy_name="assess", *, source=None, schema_violations=()):
        if isinstance(document, str):
            document = load_ir(document)
        policy = ctx.policy(load_policy(policy_name))
        ir = IrDocument.from_document(document)
        checks = run_structural_checks(
            ctx,
            ir,
            policy,
            schema_violations=list(schema_violations),
            source_path=source_path(source) if source else None,
        )
        return {check.check_id: check for check in checks}

    return _run


def test_all_twenty_seven_checks_run_in_a_stable_order(run_checks) -> None:
    """Spec 12.8 and 16.2: the check set is closed and deterministically ordered."""
    first = run_checks("assess_conforming")
    second = run_checks("assess_conforming")
    assert tuple(first) == CHECK_IDS
    assert tuple(second) == CHECK_IDS
    assert len(CHECK_IDS) == 27


def test_every_check_cites_a_spec_section_and_is_required(run_checks) -> None:
    """Spec 12.10 and 16.8: a check explains itself against the specification.

    IR-BASIS-SCHEMA is deliberately non-required (draft.2 D-F): the spec makes
    basis declaration a SHOULD, so the check enforces only the policy-level
    obligation and must not gate the mechanical dimension.
    """
    for check_id, check in run_checks("assess_conforming").items():
        assert check.spec_ref.startswith("ATS-1 "), check_id
        assert check.title.strip(), check_id
        assert check.detail.strip(), check_id
        assert check.status in tuple(Status)
        if check_id == "IR-BASIS-SCHEMA":
            assert check.required is False, check_id
            assert check.status is Status.NOT_APPLICABLE, check_id
        else:
            assert check.required is True, check_id


def test_the_conforming_assess_artifact_raises_no_structural_failure(
    run_checks,
) -> None:
    """Spec 21.1: the specification's own conforming example is structurally sound."""
    checks = run_checks("assess_conforming", source="assess_rust_kernel.txt")
    failed = {cid: c.detail for cid, c in checks.items() if c.status is Status.FAIL}
    assert failed == {}


def test_the_conforming_specify_artifact_raises_no_structural_failure(
    run_checks,
) -> None:
    """Spec 21.3: likewise for the conforming SPECIFY example."""
    checks = run_checks(
        "specify_conforming", "specify", source="specify_stale_policy.txt"
    )
    failed = {cid: c.detail for cid, c in checks.items() if c.status is Status.FAIL}
    assert failed == {}


# -- IR-SCHEMA --------------------------------------------------------------


def test_ir_schema_reports_the_violations_it_was_handed(run_checks) -> None:
    """Spec 19.4: schema conformance is reported, not inferred."""
    violation = SchemaViolation("/sections/0", "boom", "ats_text_ir_v1.schema.json", "type")
    checks = run_checks("assess_conforming", schema_violations=[violation])
    check = checks["IR-SCHEMA"]
    assert check.status is Status.FAIL
    assert "/sections/0: boom" in check.detail
    assert run_checks("assess_conforming")["IR-SCHEMA"].status is Status.PASS


# -- IR-POLICY-IDENTITY / IR-POLICY-CURRENTNESS -----------------------------


def test_ir_policy_identity_fails_when_the_ir_binds_a_different_snapshot(
    run_checks, load_ir
) -> None:
    """Spec 6.6 and 14.13: the artifact is judged under the policy it names."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["policy_snapshot_id"] = "policy-something-else"
    check = run_checks(document)["IR-POLICY-IDENTITY"]
    assert check.status is Status.FAIL
    assert "policy-something-else" in check.detail


def test_ir_policy_currentness_fails_on_an_expired_exception(run_checks) -> None:
    """Spec 6.3 and 14.3: an expired exception left in the snapshot is stale policy."""
    check = run_checks("assess_conforming", "expired_exception")["IR-POLICY-CURRENTNESS"]
    assert check.status is Status.FAIL
    assert "expired" in check.detail
    assert run_checks("assess_conforming")["IR-POLICY-CURRENTNESS"].status is Status.PASS


def test_ir_policy_currentness_fails_when_the_fallback_is_not_fail_closed(
    ctx, load_ir, load_policy
) -> None:
    """Spec 14.12: no silent fallback; this implementation declares no fallback component."""
    document = seal({**load_policy("assess"), "fallback_policy": "explicit_only"})
    policy = ctx.policy(document)
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    checks = {
        c.check_id: c
        for c in run_structural_checks(ctx, ir, policy, schema_violations=[])
    }
    check = checks["IR-POLICY-CURRENTNESS"]
    assert check.status is Status.FAIL
    assert "14.12" in check.detail


def test_ir_policy_exceptions_reports_expiry_and_absence_distinctly(
    run_checks,
) -> None:
    """Spec 6.3: no exception is NOT_APPLICABLE; an expired one is a failure."""
    assert run_checks("assess_conforming")["IR-POLICY-EXCEPTIONS"].status is (
        Status.NOT_APPLICABLE
    )
    active = run_checks("assess_conforming", "scoped_exception")["IR-POLICY-EXCEPTIONS"]
    assert active.status is Status.PASS
    expired = run_checks("assess_conforming", "expired_exception")["IR-POLICY-EXCEPTIONS"]
    assert expired.status is Status.FAIL
    assert "expired" in expired.detail


# -- IR-SOURCE-HASH ---------------------------------------------------------


def test_ir_source_hash_passes_against_the_bound_source_file(run_checks) -> None:
    """Spec 14.2: the declared hashes must be the hashes of the actual bytes."""
    check = run_checks("assess_conforming", source="assess_rust_kernel.txt")[
        "IR-SOURCE-HASH"
    ]
    assert check.status is Status.PASS
    assert "assess_rust_kernel.txt" in check.detail


def test_ir_source_hash_is_unavailable_without_the_source_file(run_checks) -> None:
    """Spec 5.4 and 14.2: an unverified binding is UNAVAILABLE, not a decided result.

    Appendix C requires a normalization step to retain a separate normalized
    hash rather than replacing the source hash. It does not require the two
    digests to differ: for an already-normalized source they legitimately
    coincide, which the with-source branch of this same check confirms.
    """
    check = run_checks("assess_conforming")["IR-SOURCE-HASH"]
    assert check.status is Status.UNAVAILABLE
    assert "unverified" in check.detail


def test_ir_source_hash_fails_when_the_declared_hash_is_not_the_file_hash(
    run_checks, load_ir
) -> None:
    """Spec 14.2: the implementation binds the exact input bytes before evaluation."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["source"]["content_sha256"] = "0" * 64
    check = run_checks(document, source="assess_rust_kernel.txt")["IR-SOURCE-HASH"]
    assert check.status is Status.FAIL
    assert "0" * 64 in check.detail


# -- IR-ID-UNIQUE / IR-REFS -------------------------------------------------


def test_ir_id_unique_fails_on_a_reused_identifier(run_checks) -> None:
    """Spec 7.3: an identifier denotes one object."""
    check = run_checks("duplicate_ids")["IR-ID-UNIQUE"]
    assert check.status is Status.FAIL
    assert "a1" in check.detail


def test_ir_refs_fails_on_a_dangling_reference(run_checks) -> None:
    """Spec 7.9: a cited object must exist in the artifact."""
    check = run_checks("dangling_reference")["IR-REFS"]
    assert check.status is Status.FAIL
    assert "e-does-not-exist" in check.detail


# -- IR-SECTION-PROFILE -----------------------------------------------------


def test_ir_section_profile_is_unavailable_for_a_reserved_profile(run_checks) -> None:
    """Spec 9.5: a reserved profile is preserved and named, never coerced."""
    check = run_checks("reserved_profile")["IR-SECTION-PROFILE"]
    assert check.status is Status.UNAVAILABLE
    assert "X-ARQ-EXPLAIN-1" in check.detail


def test_ir_section_profile_fails_when_the_policy_does_not_declare_the_profile(
    run_checks, load_ir
) -> None:
    """Spec 6.5: a section resolves to a profile the active policy declares."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["profiles"] = ["SPECIFY"]
    check = run_checks(document)["IR-SECTION-PROFILE"]
    assert check.status is Status.FAIL
    assert "SPECIFY" in check.detail


# -- IR-CLAIM-ROLE-FIELDS ---------------------------------------------------


def test_ir_claim_role_fields_fails_when_a_role_carries_foreign_force(
    run_checks,
) -> None:
    """Spec 7.4 and 9.2.5: an observation does not carry assessment machinery."""
    check = run_checks("observation_with_confidence")["IR-CLAIM-ROLE-FIELDS"]
    assert check.status is Status.FAIL
    assert "observation" in check.detail


def test_ir_claim_role_fields_fails_when_a_requirement_hides_behind_another_role(
    run_checks, load_ir
) -> None:
    """Spec 7.4: a requirement object on a non-normative role hides an obligation."""
    document = copy.deepcopy(load_ir("specify_conforming"))
    document["sections"][0]["claims"][0]["role"] = "observation"
    document["sections"][0]["claims"][0]["force"] = {}
    check = run_checks(document, "specify")["IR-CLAIM-ROLE-FIELDS"]
    assert check.status is Status.FAIL
    assert "hides a normative obligation" in check.detail


# -- IR-EVIDENCE-ENDPOINTS --------------------------------------------------


def test_ir_evidence_endpoints_fails_on_present_evidence_with_no_locator(
    run_checks, load_ir
) -> None:
    """Spec 9.2.6: evidence declared present must be retrievable."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    source = document["sections"][0]["evidence"][0]["source"]
    source.pop("locator", None)
    source.pop("content_sha256", None)
    check = run_checks(document)["IR-EVIDENCE-ENDPOINTS"]
    assert check.status is Status.FAIL
    assert "cannot be retrieved" in check.detail


def test_ir_evidence_endpoints_fails_when_availability_disagrees_with_its_source(
    run_checks, load_ir
) -> None:
    """Spec 7.10: one availability state, stated once."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["evidence"][0]["source"]["availability"] = "withheld"
    check = run_checks(document)["IR-EVIDENCE-ENDPOINTS"]
    assert check.status is Status.FAIL
    assert "disagrees" in check.detail


# -- IR-GLOSSARY-REFS -------------------------------------------------------


def test_ir_glossary_refs_fails_on_an_undeclared_term_base(run_checks, load_ir) -> None:
    """Spec 7.2: an audience assumption requires policy or artifact evidence."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["audience"]["assumed_glossary_refs"] = ["unknown-term-base"]
    check = run_checks(document)["IR-GLOSSARY-REFS"]
    assert check.status is Status.FAIL
    assert "unknown-term-base" in check.detail


# -- IR-LIKELIHOOD-VOCAB / IR-FIRST-USE-RANGE -------------------------------


def test_ir_likelihood_vocab_fails_on_a_mismatched_interval(run_checks) -> None:
    """Spec 8.2 and 19.3: the interval is the lexicon's, not the author's."""
    check = run_checks("wep_interval_mismatch")["IR-LIKELIHOOD-VOCAB"]
    assert check.status is Status.FAIL
    assert "likely" in check.detail


def test_ir_likelihood_vocab_is_not_applicable_without_a_likelihood(
    run_checks,
) -> None:
    """Spec 5.4: nothing inspected is NOT_APPLICABLE, never PASS."""
    check = run_checks("specify_conforming", "specify")["IR-LIKELIHOOD-VOCAB"]
    assert check.status is Status.NOT_APPLICABLE
    assert "no claim declares a likelihood" in check.detail


def test_ir_first_use_range_fails_when_the_range_is_not_shown(
    run_checks, load_ir
) -> None:
    """Spec 8.4: the first material WEP use shows its numeric range."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["claims"][0]["force"]["likelihood"][
        "range_shown_inline"
    ] = False
    check = run_checks(document)["IR-FIRST-USE-RANGE"]
    assert check.status is Status.FAIL
    assert "does not show its range inline" in check.detail


def test_ir_first_use_range_is_not_applicable_without_a_material_wep_use(
    run_checks,
) -> None:
    """Spec 8.4 attaches to a first material use; absence is not a pass."""
    check = run_checks("possibility_term_only")["IR-FIRST-USE-RANGE"]
    assert check.status is Status.NOT_APPLICABLE


# -- IR-LIKELIHOOD-CONFIDENCE-SEP / IR-CONFIDENCE-BASIS ---------------------


def test_ir_likelihood_confidence_sep_fails_when_the_two_axes_collapse(
    run_checks, load_ir
) -> None:
    """Spec 8.11: probability and analytic robustness are distinguishable."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    force = document["sections"][0]["claims"][0]["force"]
    force["likelihood"]["display"] = force["assessment_confidence"]["level"]
    check = run_checks(document)["IR-LIKELIHOOD-CONFIDENCE-SEP"]
    assert check.status is Status.FAIL
    assert "not distinguishable" in check.detail


def test_ir_confidence_basis_fails_on_a_dimension_outside_the_lexicon(
    run_checks, load_ir
) -> None:
    """Spec 8.8 and 8.9: the basis dimensions and their values are a closed set."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    basis = document["sections"][0]["claims"][0]["force"]["assessment_confidence"]["basis"]
    basis["evidence_quality"] = "excellent"
    check = run_checks(document)["IR-CONFIDENCE-BASIS"]
    assert check.status is Status.FAIL
    assert "evidence_quality='excellent'" in check.detail


def test_ir_confidence_basis_fails_when_a_dimension_is_absent(
    ctx, run_checks, load_ir
) -> None:
    """Spec 8.9: every dimension the lexicon declares is answered."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    basis = document["sections"][0]["claims"][0]["force"]["assessment_confidence"]["basis"]
    dimension = next(iter(ctx.lexicon.basis_dimensions))
    del basis[dimension]
    check = run_checks(document)["IR-CONFIDENCE-BASIS"]
    assert check.status is Status.FAIL
    assert f"{dimension!r} is absent" in check.detail


# -- IR-UPDATE-INDICATORS ---------------------------------------------------


def test_ir_update_indicators_is_not_applicable_when_none_exists(run_checks) -> None:
    """Spec 7.14: no indicator and no update relation is nothing to check."""
    check = run_checks("no_update_indicator")["IR-UPDATE-INDICATORS"]
    assert check.status is Status.NOT_APPLICABLE


def test_ir_update_indicators_fails_on_an_unrecognised_effect(
    run_checks, load_ir
) -> None:
    """Spec 7.14: the effect vocabulary is closed."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["update_indicators"][0]["effect"] = "make_it_better"
    check = run_checks(document)["IR-UPDATE-INDICATORS"]
    assert check.status is Status.FAIL
    assert "make_it_better" in check.detail


def test_ir_update_indicators_fails_on_an_update_relation_with_no_basis_or_note(
    run_checks, load_ir
) -> None:
    """Spec 7.14: what an update changed must remain recoverable."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["relations"].append(
        {
            "relation_id": "rel-update",
            "type": "updates",
            "source_id": "e1",
            "target_id": "c1",
            "material": True,
        }
    )
    check = run_checks(document)["IR-UPDATE-INDICATORS"]
    assert check.status is Status.FAIL
    assert "neither a basis nor a note" in check.detail


@pytest.mark.parametrize(
    "recovery",
    [
        {"notes": "The likelihood moved from unlikely to likely."},
        {"basis_refs": ["e2"]},
    ],
)
def test_a_note_or_a_basis_makes_an_update_recoverable(
    run_checks, load_ir, recovery
) -> None:
    """Spec 7.14: either a recorded basis or a note preserves what changed."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["relations"].append(
        {
            "relation_id": "rel-update",
            "type": "updates",
            "source_id": "e1",
            "target_id": "c1",
            "material": True,
            **recovery,
        }
    )
    check = run_checks(document)["IR-UPDATE-INDICATORS"]
    assert check.status is Status.PASS


# -- IR-DEONTIC-VALIDITY / IR-REQUIREMENT-SLOTS / IR-ONE-OBLIGATION ---------


def test_ir_deontic_validity_fails_when_the_two_deontics_disagree(
    run_checks, load_ir
) -> None:
    """Spec 8.16: one obligation strength, represented once."""
    document = copy.deepcopy(load_ir("specify_conforming"))
    document["sections"][0]["claims"][0]["requirement"]["deontic"] = "SHOULD"
    check = run_checks(document, "specify")["IR-DEONTIC-VALIDITY"]
    assert check.status is Status.FAIL
    assert "disagrees" in check.detail


def test_ir_deontic_validity_is_not_applicable_without_a_deontic(run_checks) -> None:
    """Spec 8.16 applies where deontic force is declared."""
    check = run_checks("assess_conforming")["IR-DEONTIC-VALIDITY"]
    assert check.status is Status.NOT_APPLICABLE


def test_ir_requirement_slots_fails_on_a_missing_acceptance_criterion(
    run_checks,
) -> None:
    """Spec 9.3.9: a MUST requirement carries a verifiable acceptance criterion."""
    check = run_checks("missing_acceptance_criterion", "specify")["IR-REQUIREMENT-SLOTS"]
    assert check.status is Status.FAIL
    assert "acceptance_criterion" in check.detail


def test_ir_one_obligation_fails_on_a_coordinated_action(run_checks) -> None:
    """Spec 9.3.3: one obligation per requirement."""
    check = run_checks("two_obligations", "specify")["IR-ONE-OBLIGATION"]
    assert check.status is Status.FAIL
    assert "coordinates more than one behaviour" in check.detail


def test_ir_one_obligation_is_review_required_when_no_connective_appears(
    run_checks,
) -> None:
    """Spec 9.3.3: absence of a connective does not prove one obligation."""
    check = run_checks("specify_conforming", "specify")["IR-ONE-OBLIGATION"]
    assert check.status is Status.REVIEW_REQUIRED
    assert "semantic judgement" in check.detail


# -- IR-QUANT-UNITS / IR-POLARITY-QUANTIFIER --------------------------------


def test_ir_quant_units_reports_a_number_with_no_quantifier_object(
    run_checks, load_ir
) -> None:
    """Spec 7.7 and 10.9: a number in prose alone cannot be checked for units."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["claims"][1]["proposition"] = (
        "The transition model has been stable for 12 releases."
    )
    check = run_checks(document)["IR-QUANT-UNITS"]
    assert check.status is Status.REVIEW_REQUIRED
    assert "no quantifier object" in check.detail


def test_ir_quant_units_passes_when_the_number_is_represented(
    run_checks, load_ir
) -> None:
    """Spec 7.7: a represented quantifier is what ATS-NUM-001 can decide."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    claim = document["sections"][0]["claims"][1]
    claim["proposition"] = "The transition model has been stable for 12 releases."
    claim["quantifier"] = {"kind": "exact_count", "value": 12, "unit": "releases"}
    check = run_checks(document)["IR-QUANT-UNITS"]
    assert check.status is Status.PASS


def test_ir_polarity_quantifier_fails_when_a_judgment_declares_no_usable_scope(
    run_checks, load_ir
) -> None:
    """Spec 7.6: an absent scope reads as universal scope."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["claims"][0]["scope"] = {"time_horizon": "next quarter"}
    check = run_checks(document)["IR-POLARITY-QUANTIFIER"]
    assert check.status is Status.FAIL
    assert "names no population, system, environment, or condition" in check.detail


def test_ir_polarity_quantifier_fails_when_a_sourced_report_cites_nothing(
    run_checks, load_ir
) -> None:
    """Spec 7.4 and 11.3.1: attribution is what makes a sourced report checkable."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    claim = document["sections"][0]["claims"][1]
    claim["role"] = "sourced_report"
    check = run_checks(document)["IR-POLARITY-QUANTIFIER"]
    assert check.status is Status.FAIL
    assert "cites no source" in check.detail


# -- IR-P0-P1-DECLARATIONS --------------------------------------------------


def test_ir_p0_p1_declarations_reports_the_declared_exposure(run_checks) -> None:
    """Spec 7.15, 11.3.1, 11.3.2: materiality is declared and counted, not inferred."""
    check = run_checks("assess_conforming")["IR-P0-P1-DECLARATIONS"]
    assert check.status is Status.PASS
    assert "P0 exposure: 5 material claim(s)" in check.detail
    assert "P1 exposure: 6 material relation(s)" in check.detail


def test_ir_p0_p1_declarations_fails_on_a_material_relation_between_immaterial_objects(
    run_checks, load_ir
) -> None:
    """Spec 11.3.2: a P1 relation between unprotected objects protects nothing."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    for claim in document["sections"][0]["claims"]:
        if claim["claim_id"] in ("alt1", "r1"):
            claim["material"] = False
    check = run_checks(document)["IR-P0-P1-DECLARATIONS"]
    assert check.status is Status.FAIL
    assert "rel6" in check.detail


# -- IR-EXTRACTION-STATUS ---------------------------------------------------


def test_ir_extraction_status_fails_on_repeated_candidate_readings(
    run_checks,
) -> None:
    """Spec 13.4: candidate interpretations must be materially distinct."""
    check = run_checks("ambiguous_without_distinct_readings")["IR-EXTRACTION-STATUS"]
    assert check.status is Status.FAIL
    assert "materially distinct" in check.detail


def test_ir_extraction_status_accepts_a_represented_ambiguity(run_checks) -> None:
    """Spec 7.16: a declared ambiguity with distinct readings is conforming."""
    check = run_checks("assess_represented_ambiguity")["IR-EXTRACTION-STATUS"]
    assert check.status is Status.PASS


def test_ir_extraction_status_accepts_a_declared_partial_extraction(
    run_checks,
) -> None:
    """Spec 7.16: partial extraction is honest when the gap is recorded."""
    check = run_checks("assess_partial_extraction")["IR-EXTRACTION-STATUS"]
    assert check.status is Status.PASS


def test_ir_extraction_status_fails_when_complete_hides_a_recorded_issue(
    run_checks, load_ir
) -> None:
    """Spec 7.16: 'complete' and a recorded gap cannot both be true."""
    document = copy.deepcopy(load_ir("assess_partial_extraction"))
    document["extraction_status"] = "complete"
    check = run_checks(document)["IR-EXTRACTION-STATUS"]
    assert check.status is Status.FAIL
    assert "complete" in check.detail


# -- IR-CAPABILITY / IR-CANONICAL -------------------------------------------


def test_ir_capability_declares_what_is_undecidable_and_partial(
    ctx, run_checks
) -> None:
    """Spec 5.5 and 16.1: unsupported and partial capabilities are named per rule."""
    check = run_checks("assess_conforming")["IR-CAPABILITY"]
    assert check.status is Status.PASS
    undecidable = sorted(
        r for r, c in ctx.capability.rules.items() if c.decision_power == "undecidable"
    )
    for rule_id in undecidable:
        assert rule_id in check.detail
    assert "absorbed" in check.detail


def test_ir_canonical_reproduces_the_content_address(run_checks) -> None:
    """Appendix C and spec 16.2: canonical bytes are stable and reproduce the address."""
    check = run_checks("assess_conforming")["IR-CANONICAL"]
    assert check.status is Status.PASS
    assert "canonical byte(s) hash to" in check.detail

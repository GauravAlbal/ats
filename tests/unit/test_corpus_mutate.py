"""Mutation operators: one semantic feature, tagged, paired, and never generated.

Defends spec Section 17.5 (one semantic feature at a time; synthetic examples
MUST be tagged and MUST NOT count as independent evidence), Section 17.7 (a
mutation stays in its source's split group), and Section 5.5 (an unsupported
capability is reported, not emulated).
"""

from __future__ import annotations

import copy
import datetime as dt
import json

import pytest
import yaml

from ats.context import Context
from ats.corpus import mutate
from ats.corpus import records as rec
from ats.errors import UnsupportedCapabilityError, UsageError
from ats.spec_package import REPO_ROOT

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)

#: The twenty-two operators spec Section 17.5 recommends.
EXPECTED_OPERATORS = {
    "ATS-MUT-QUAL-DELETE",
    "ATS-MUT-WEP-BAND-SHIFT",
    "ATS-MUT-WEP-RANGE-STRIP",
    "ATS-MUT-LIKELIHOOD-CONFIDENCE-SWAP",
    "ATS-MUT-DEONTIC-EXCHANGE",
    "ATS-MUT-ACTOR-REMOVE",
    "ATS-MUT-OBLIGATION-MERGE",
    "ATS-MUT-UNIT-STRIP",
    "ATS-MUT-THRESHOLD-BOUNDARY-SHIFT",
    "ATS-MUT-NEGATION-FLIP",
    "ATS-MUT-QUANTIFIER-WIDEN",
    "ATS-MUT-RELATION-REVERSE",
    "ATS-MUT-CAUSAL-UPGRADE",
    "ATS-MUT-EXCEPTION-DELETE",
    "ATS-MUT-CONTRARY-EVIDENCE-DELETE",
    "ATS-MUT-ASSUMPTION-TO-OBSERVATION",
    "ATS-MUT-SOURCE-ATTRIBUTION-STRIP",
    "ATS-MUT-UPDATE-INDICATOR-DELETE",
    "ATS-MUT-EVIDENTIAL-STRENGTHEN",
    "ATS-MUT-RESTATEMENT-INSERT",
    "ATS-MUT-JUDGMENT-BURY",
    "ATS-MUT-ANTECEDENT-AMBIGUATE",
}


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


def _source(name: str, profile: str, rule_id: str) -> dict:
    ir = json.loads(
        (REPO_ROOT / "fixtures" / "mutations" / "sources" / f"{name}_mutation_source.json")
        .read_text(encoding="utf-8")
    )
    return rec.text_example(
        text=ir["sections"][0]["claims"][0]["proposition"],
        profile=profile,
        rule_id=rule_id,
        label="conforming",
        rationale="Hand-authored mutation source.",
        protected_impact=["P0"],
        provenance="human_authored_fixture",
        synthetic=False,
        split_group=f"mutation-source-{name}",
        repository_group="ats-seed",
        extensions={rec.EXT_TEXT_IR: ir},
    )


@pytest.fixture(scope="module")
def assess_source() -> dict:
    return _source("assess", "ASSESS", "ATS-EPI-001")


@pytest.fixture(scope="module")
def specify_source() -> dict:
    return _source("specify", "SPECIFY", "ATS-REQ-001")


def test_registry_declares_all_twenty_two_operators(ctx: Context) -> None:
    """Spec 17.5 recommends twenty-two operators; every one is declared."""
    operators = mutate.load_operators(ctx)["operators"]
    assert set(operators) == EXPECTED_OPERATORS
    assert len(operators) == 22


def test_registry_validates_against_its_schema(ctx: Context) -> None:
    """Every emitted and shipped object validates against its schema."""
    document = yaml.safe_load(mutate.OPERATOR_REGISTRY_PATH.read_text(encoding="utf-8"))
    ctx.schemas.validate(document, "ats_mutation_operator_v1.schema.json")
    assert document["schema_version"] == "ats.mutation_operator.v1"


def test_every_target_rule_exists(ctx: Context) -> None:
    """An operator pointing at a rule the registry does not define is unusable."""
    for operator_id, declaration in mutate.load_operators(ctx)["operators"].items():
        for rule_id in declaration["target_rule_ids"]:
            assert ctx.registry.get(rule_id).rule_id == rule_id, operator_id


def test_declarations_and_appliers_correspond(ctx: Context) -> None:
    """A declared-supported operator with no applier is a promise nothing keeps."""
    operators = mutate.load_operators(ctx)["operators"]
    supported = {k for k, v in operators.items() if v["supported"]}
    assert supported == set(mutate.APPLIERS)
    assert len(supported) == 21


def test_the_unsupported_operator_is_declared_not_approximated(ctx: Context) -> None:
    """Spec 17.5: an operator that cannot be deterministic is declared, never generated."""
    operators = mutate.load_operators(ctx)["operators"]
    unsupported = {k for k, v in operators.items() if not v["supported"]}
    assert unsupported == {"ATS-MUT-ANTECEDENT-AMBIGUATE"}
    declaration = operators["ATS-MUT-ANTECEDENT-AMBIGUATE"]
    assert declaration["deterministic"] is False
    assert "generat" in declaration["unsupported_reason"]


def test_an_unsupported_operator_raises_rather_than_degrading(
    ctx: Context, assess_source
) -> None:
    """Spec 5.5: an unsupported capability is reported, not emulated by a weaker path."""
    with pytest.raises(UnsupportedCapabilityError) as excinfo:
        mutate.apply_operator(ctx, assess_source, "ATS-MUT-ANTECEDENT-AMBIGUATE")
    error = excinfo.value
    assert error.exit_code == 3
    assert error.payload()["status"] == "UNAVAILABLE"
    assert "ATS-MUT-ANTECEDENT-AMBIGUATE" in error.capability


def test_every_supported_operator_applies_to_a_curated_source(
    ctx: Context, assess_source, specify_source
) -> None:
    """Each operator has at least one source whose preconditions it meets."""
    applied: set[str] = set()
    for source in (assess_source, specify_source):
        results, _refused = mutate.apply_all(ctx, source)
        applied.update(r["operator_id"] for r in results)
    assert applied == set(mutate.APPLIERS)


def test_an_unmet_precondition_is_refused_not_approximated(ctx: Context, specify_source) -> None:
    """A mutation with no target is an error, not an empty edit."""
    with pytest.raises(UsageError, match="cannot be applied"):
        mutate.apply_operator(ctx, specify_source, "ATS-MUT-WEP-BAND-SHIFT")


def test_the_mutant_is_tagged_synthetic(ctx: Context, assess_source) -> None:
    """Spec 17.5: synthetic examples MUST be tagged."""
    result = mutate.apply_operator(ctx, assess_source, "ATS-MUT-QUAL-DELETE")
    mutant = result["mutant"]
    assert mutant["synthetic"] is True
    assert mutant["provenance"] == "synthetic_mutation"
    assert mutant["mutation_operator"] == "ATS-MUT-QUAL-DELETE"
    assert "MUST NOT be counted as independent real-world evidence" in mutant["rationale"]


def test_the_source_is_preserved_verbatim(ctx: Context, assess_source) -> None:
    """A mutation that loses its source cannot be a preservation pair."""
    before = copy.deepcopy(assess_source)
    result = mutate.apply_operator(ctx, assess_source, "ATS-MUT-NEGATION-FLIP")
    assert result["source_example"] == before
    assert assess_source == before
    assert mutate.source_ir(result["source_example"]) == mutate.source_ir(before)


def test_the_mutant_inherits_its_source_split_group(ctx: Context, assess_source) -> None:
    """Spec 17.7: a mutation stays in the same split group as its source."""
    for operator_id in sorted(mutate.APPLIERS):
        try:
            result = mutate.apply_operator(ctx, assess_source, operator_id)
        except UsageError:
            continue
        assert result["mutant"]["split_group"] == assess_source["split_group"]
        assert (
            result["mutant"]["extensions"][rec.EXT_SOURCE_EXAMPLE_ID]
            == assess_source["example_id"]
        )


def test_the_transformation_records_both_hashes(ctx: Context, assess_source) -> None:
    """A replayable mutation records what it started from and what it produced."""
    result = mutate.apply_operator(ctx, assess_source, "ATS-MUT-WEP-BAND-SHIFT")
    transformation = result["transformation"]
    assert len(transformation["source_sha256"]) == 64
    assert len(transformation["output_sha256"]) == 64
    assert transformation["source_sha256"] != transformation["output_sha256"]
    assert transformation["old_value"] == "likely"
    assert transformation["new_value"] == "very_likely"
    assert transformation["target_pointer"] == "/sections/0/claims/0/force/likelihood/term"


def test_the_recorded_old_value_is_what_the_source_actually_held(
    ctx: Context, assess_source, specify_source
) -> None:
    """The transformation record is checkable against the source, not merely plausible."""
    for source in (assess_source, specify_source):
        original = mutate.source_ir(source)
        for operator_id in sorted(mutate.APPLIERS):
            try:
                result = mutate.apply_operator(ctx, source, operator_id)
            except UsageError:
                continue
            transformation = result["transformation"]
            pointer = transformation["target_pointer"]
            old = transformation["old_value"]
            if not isinstance(old, (str, bool, int, float)) or old is None:
                continue
            node = original
            for part in pointer.strip("/").split("/"):
                node = node[int(part)] if part.isdigit() else node[part]
            assert node == old, (operator_id, pointer)


def test_a_mutation_is_deterministic(ctx: Context, assess_source) -> None:
    """Spec 16.2: identical canonical inputs produce identical results."""
    for operator_id in sorted(mutate.APPLIERS):
        try:
            first = mutate.apply_operator(ctx, assess_source, operator_id)
            second = mutate.apply_operator(ctx, assess_source, operator_id)
        except UsageError:
            continue
        assert first["mutant"]["example_id"] == second["mutant"]["example_id"]
        assert (
            first["transformation"]["output_sha256"] == second["transformation"]["output_sha256"]
        )


def test_the_wep_band_shift_leaves_the_interval_at_the_source_band(
    ctx: Context, assess_source
) -> None:
    """Spec 8.2, 8.5: the term moves, the bounds do not, so ATS-EPI-001 can see it."""
    result = mutate.apply_operator(ctx, assess_source, "ATS-MUT-WEP-BAND-SHIFT")
    likelihood = mutate.source_ir(result["mutant"])["sections"][0]["claims"][0]["force"][
        "likelihood"
    ]
    lower, upper, _inclusive = ctx.lexicon.interval_for("likely")
    assert likelihood["term"] == "very_likely"
    assert (likelihood["lower"], likelihood["upper"]) == (lower, upper)
    assert (likelihood["lower"], likelihood["upper"]) != ctx.lexicon.interval_for("very_likely")[
        :2
    ]


def test_the_deontic_exchange_stays_in_the_requirement_vocabulary(
    ctx: Context, specify_source
) -> None:
    """requirement_slots.deontic has no CAN, so a requirement exchange cannot produce one."""
    result = mutate.apply_operator(ctx, specify_source, "ATS-MUT-DEONTIC-EXCHANGE")
    claim = mutate.source_ir(result["mutant"])["sections"][0]["claims"][0]
    assert claim["force"]["deontic"] == "SHOULD"
    assert claim["requirement"]["deontic"] == "SHOULD"
    assert "SHOULD reject" in claim["proposition"]
    assert claim["requirement"]["deontic"] in mutate.REQUIREMENT_DEONTICS


def test_the_actor_literal_is_quoted_from_the_specification(
    ctx: Context, specify_source
) -> None:
    """Spec 9.3.4, 21.4: the concealing form comes from the specification's own example."""
    result = mutate.apply_operator(ctx, specify_source, "ATS-MUT-ACTOR-REMOVE")
    claim = mutate.source_ir(result["mutant"])["sections"][0]["claims"][0]
    assert claim["requirement"]["actor"] == "the system"
    assert "the system MUST reject" in claim["proposition"]


def test_the_expected_impact_quotes_the_registry(ctx: Context, assess_source) -> None:
    """Spec 12.10: a surfaced rule is explained by its normative statement."""
    result = mutate.apply_operator(ctx, assess_source, "ATS-MUT-UPDATE-INDICATOR-DELETE")
    impact = result["expected_impact"]
    assert impact["target_rule_ids"] == ["ATS-EPI-006"]
    rule = ctx.registry.get("ATS-EPI-006")
    assert impact["rules"][0]["normative_statement"] == rule.normative_statement
    assert impact["rules"][0]["severity"] == rule.severity
    assert "not evidence that the violation occurs" in impact["synthetic_evidence_note"]


def test_the_mutant_ir_stays_schema_valid(ctx: Context, assess_source, specify_source) -> None:
    """A mutation that breaks the schema tests the validator, not the rule."""
    for source in (assess_source, specify_source):
        results, _refused = mutate.apply_all(ctx, source)
        for result in results:
            ctx.schemas.validate_document(mutate.source_ir(result["mutant"]))
            ctx.schemas.validate_document(result["mutant"])


def test_an_example_with_no_ir_is_refused(ctx: Context) -> None:
    """An operator edits the meaning ledger; a bare sentence is not one."""
    bare = rec.text_example(
        text="The verifier MUST reject a stale receipt.",
        profile="SPECIFY",
        rule_id="ATS-DEON-001",
        label="conforming",
        rationale="No IR attached.",
        protected_impact=["P0"],
        provenance="human_authored_fixture",
        synthetic=False,
        split_group="unit-test",
    )
    with pytest.raises(UsageError, match="carries no TextIR"):
        mutate.apply_operator(ctx, bare, "ATS-MUT-NEGATION-FLIP")


def test_an_unknown_operator_names_the_known_ones(ctx: Context, assess_source) -> None:
    with pytest.raises(UsageError, match="unknown mutation operator"):
        mutate.apply_operator(ctx, assess_source, "ATS-MUT-INVENTED")


def test_the_shipped_pair_fixtures_cover_every_supported_operator(ctx: Context) -> None:
    """Spec 17.5: each mutation is stored beside the source it was derived from."""
    pairs_dir = REPO_ROOT / "fixtures" / "mutations" / "pairs"
    files = sorted(p.stem for p in pairs_dir.glob("*.json"))
    assert set(files) == set(mutate.APPLIERS)

    for path in sorted(pairs_dir.glob("*.json")):
        pair = json.loads(path.read_text(encoding="utf-8"))
        assert pair["operator_id"] == path.stem
        source, mutant = pair["source_example"], pair["mutant"]
        ctx.schemas.validate_document(source)
        ctx.schemas.validate_document(mutant)
        assert source["synthetic"] is False
        assert mutant["synthetic"] is True
        assert mutant["mutation_operator"] == path.stem
        # Spec 17.7: the pair cannot be separated by a split.
        assert mutant["split_group"] == source["split_group"] == pair["split_group"]
        assert mutant["extensions"][rec.EXT_SOURCE_EXAMPLE_ID] == source["example_id"]
        assert (
            pair["transformation"]["source_sha256"] != pair["transformation"]["output_sha256"]
        )

"""The agreement report, and the ways an agreement number can lie.

Every contract here is one way an agreement number can lie. A synthetic
fixture whose modal outcome is "the rule does not apply" can produce high
headline agreement while rare classes disagree completely, so the load-bearing
test is :func:`test_high_overall_agreement_with_a_rare_class_split_is_not_success`.
Beside it sit the absence contracts: a round that never ran must not read as
total disagreement, a kappa whose denominator is zero must not read as perfect
agreement, and a context-sufficiency rating nobody gave must not be inferred
from an annotator's silence (ADR-0002).
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

from ats.canonical import canonical_bytes, verify_seal
from ats.context import Context
from ats.corpus import agreement
from ats.corpus import records as rec
from ats.errors import UsageError

NOW = _dt.datetime(2026, 8, 3, tzinfo=_dt.UTC)

#: The seven axes the report promises. Named here so an axis that silently
#: disappears fails a test rather than shrinking the vector.
EXPECTED_METRICS = (
    "profile_agreement",
    "rule_applicability_agreement",
    "label_agreement_conditional_on_applicable",
    "context_sufficiency_agreement",
    "protected_impact_agreement",
    "evidence_span_token_f1",
    "ambiguous_or_insufficient_context_rate",
)

REGISTRY = {
    "annotators": [
        {
            "annotator_id": "llm-annotator-a",
            "kind": "llm",
            "model": "test-model-a",
            "prompt_id": "synthetic-round-a",
            "prompt_sha256": "a" * 64,
        },
        {
            "annotator_id": "llm-annotator-b",
            "kind": "llm",
            "model": "test-model-b",
            "prompt_id": "synthetic-round-b",
            "prompt_sha256": "b" * 64,
        },
    ]
}


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


@pytest.fixture(scope="module")
def rule_id(ctx: Context) -> str:
    return list(ctx.registry.ids())[0]


@pytest.fixture(scope="module")
def other_rule_id(ctx: Context) -> str:
    return list(ctx.registry.ids())[1]


def judgment(
    annotator: str,
    example: str,
    rule: str,
    label: str,
    *,
    profile: str = "ASSESS",
    spans: Sequence[Mapping[str, Any]] = (),
    applicability: str | None = "applicable",
    sufficiency: str | None = "complete",
    protected: Sequence[str] = ("P2",),
    ambiguity: str = "none",
    requested: Sequence[str] = (),
) -> dict[str, Any]:
    extensions: dict[str, Any] = {}
    if applicability is not None:
        extensions[agreement.EXT_APPLICABILITY] = applicability
    if sufficiency is not None:
        extensions[agreement.EXT_CONTEXT_SUFFICIENCY] = sufficiency
    return rec.judgment(
        example_id=example,
        annotator_id=annotator,
        rule_id=rule,
        rule_version="1.0.0",
        profile=profile,
        label=label,
        rationale="the normative statement requires it",
        evidence_spans=[dict(span) for span in spans],
        protected_impact=list(protected),
        annotation_confidence="high",
        requested_additional_context=list(requested),
        ambiguity_category=ambiguity,
        timestamp="2026-08-03T00:00:00Z",
        tool_version="0.0.0-test",
        extensions=extensions or None,
    )


def non_judgment(
    annotator: str, example: str, rule: str, applicability: str = "not_applicable"
) -> dict[str, Any]:
    """A decline record: AG-19 step 2 leaves no judgment behind for an inapplicable rule."""
    return {
        "schema_version": agreement.NON_JUDGMENT_SCHEMA_VERSION,
        "example_id": example,
        "rule_id": rule,
        "annotator_id": annotator,
        "applicability": applicability,
        "reason": "annotator reported the rule inapplicable; AG-19 step 2 records no "
        "conformance judgment",
        "rationale": "the surface cue is present but the rule does not govern this text",
    }


def write_rounds(
    directory: Path,
    round_a: Sequence[Mapping[str, Any]],
    round_b: Sequence[Mapping[str, Any]] | None,
    *,
    registry: Mapping[str, Any] | None = REGISTRY,
    extra_a: Sequence[Mapping[str, Any]] = (),
    declined_a: Sequence[Mapping[str, Any]] = (),
    declined_b: Sequence[Mapping[str, Any]] = (),
    sidecars: bool = True,
) -> dict[str, Path]:
    """Lay out a synthetic pilot: two round files, two sidecars, and a registry.

    ``sidecars=True`` writes both sidecar files even when empty, mirroring the real
    pilot layout: an empty file states that the pass declined nothing, which is a
    different claim from no file at all.
    """
    paths = {
        "round_a": directory / "round-a.jsonl",
        "round_b": directory / "round-b.jsonl",
        "annotators": directory / "annotators.json",
        "sidecar_a": directory / "round-a-inapplicable.jsonl",
        "sidecar_b": directory / "round-b-inapplicable.jsonl",
    }
    paths["round_a"].write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in [*round_a, *extra_a]),
        encoding="utf-8",
    )
    if round_b is not None:
        paths["round_b"].write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in round_b), encoding="utf-8"
        )
    if registry is not None:
        paths["annotators"].write_text(json.dumps(registry), encoding="utf-8")
    if sidecars:
        for key, entries in (("sidecar_a", declined_a), ("sidecar_b", declined_b)):
            paths[key].write_text(
                "".join(json.dumps(r, sort_keys=True) + "\n" for r in entries), encoding="utf-8"
            )
    return paths


def build(ctx: Context, paths: Mapping[str, Path]) -> dict[str, Any]:
    return agreement.build_agreement_report(
        ctx,
        round_a=paths["round_a"],
        round_b=paths["round_b"],
        annotators=paths["annotators"],
    )


@pytest.fixture(scope="module")
def skewed(ctx: Context, rule_id: str, tmp_path_factory) -> dict[str, Any]:
    """Fifty-seven easy agreements and a three-unit rare class they split on.

    This is the corpus shape the whole report exists for: raw agreement 0.95,
    and no unit anywhere on which both passes chose ``violation``.
    """
    a: list[dict[str, Any]] = []
    b: list[dict[str, Any]] = []
    for index in range(57):
        example = f"ex-{index:03}"
        a.append(judgment("llm-annotator-a", example, rule_id, "conforming"))
        b.append(judgment("llm-annotator-b", example, rule_id, "conforming"))
    for index in range(3):
        example = f"rare-{index:03}"
        a.append(
            judgment(
                "llm-annotator-a",
                example,
                rule_id,
                "violation",
                spans=[{"kind": "character", "start": 10, "end": 20}],
            )
        )
        b.append(
            judgment(
                "llm-annotator-b",
                example,
                rule_id,
                "hard_negative",
                spans=[{"kind": "character", "start": 14, "end": 24}],
            )
        )
    directory = tmp_path_factory.mktemp("skewed")
    return build(ctx, write_rounds(directory, a, b))


def metric(report: Mapping[str, Any], name: str) -> dict[str, Any]:
    for item in report["metrics"]:
        if item["metric"] == name:
            return item
    raise AssertionError(f"{name} is missing from the metric vector")


# -- schema, seal, determinism ----------------------------------------------


def test_the_report_validates_and_verifies_its_own_seal(ctx: Context, skewed) -> None:
    """Spec 19.4: a document is validated by its declared schema_version."""
    assert ctx.schemas.validate_document(skewed) == agreement.SCHEMA_ID
    ok, declared, recomputed = verify_seal(skewed)
    assert ok, (declared, recomputed)


def test_regenerating_over_unchanged_rounds_is_byte_identical(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """A report whose bytes move on a rerun cannot be used as a baseline."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "conforming")]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming")]
    paths = write_rounds(tmp_path, a, b)
    first, second = build(ctx, paths), build(ctx, paths)
    assert canonical_bytes(first) == canonical_bytes(second)
    assert first["report_sha256"] == second["report_sha256"]


def test_the_report_has_no_overall_agreement_number(skewed) -> None:
    """The refusal is the design. A headline score would be read instead of the vector."""
    assert "single_number_refusal" in skewed["assessment"]
    numeric_top_level = {
        key for key, value in skewed.items() if isinstance(value, (int, float))
    }
    assert numeric_top_level == set()


# -- the vector --------------------------------------------------------------


def test_all_seven_metrics_appear_with_n_and_prevalence(skewed) -> None:
    """An axis that vanishes when inconvenient is an axis nobody has to answer for."""
    assert [m["metric"] for m in skewed["metrics"]] == list(EXPECTED_METRICS)
    for item in skewed["metrics"]:
        assert isinstance(item["n"], int)
        if item["available"]:
            assert item["raw_agreement"] is not None
            assert item["unavailable_reason"] is None
        else:
            assert item["raw_agreement"] is None
            assert item["unavailable_reason"]["code"] in agreement.UNAVAILABLE_REASONS
    # Every categorical axis reports the prevalence of each class it scored over.
    for name in EXPECTED_METRICS:
        if name == "evidence_span_token_f1":
            continue
        rows = metric(skewed, name)["class_prevalence"]
        assert rows, name
        for row in rows:
            assert row["role_a_count"] >= 0 and row["role_b_count"] >= 0
            assert row["role_a_rate"] is not None and row["role_b_rate"] is not None


def test_protected_impact_reports_each_class_in_its_own_right(skewed) -> None:
    """A set score hides which protected class the two passes split on (spec 11.3.1)."""
    components = metric(skewed, "protected_impact_agreement")["components"]
    assert [c["metric"].rsplit(".", 1)[-1] for c in components] == list(
        agreement.PROTECTED_CLASSES
    )


# -- the reason the report exists -------------------------------------------


def test_high_overall_agreement_with_a_rare_class_split_is_not_success(skewed) -> None:
    """0.95 agreement and a rare class with zero joint uses must not read as success.

    This is the report's whole reason to exist. The headline is high because the
    majority class is easy; the three units that carry the rule's actual decision
    were labelled ``violation`` by one pass and ``hard_negative`` by the other,
    and nothing in a corpus-level statistic shows that.
    """
    conditional = metric(skewed, "label_agreement_conditional_on_applicable")
    assert conditional["raw_agreement"] == 0.95

    rule_row = skewed["per_rule"][0]
    violation = next(r for r in rule_row["labels"] if r["label"] == "violation")
    assert violation["rare"] and violation["total_disagreement"]
    assert violation["both_count"] == 0
    assert violation["positive_specific_agreement"]["value"] == 0.0

    rare_findings = {
        f["subject"]
        for f in skewed["findings"]
        if f["code"] == "rare_class_total_disagreement"
    }
    assert f"{rule_row['rule_id']} / violation" in rare_findings
    assert f"{rule_row['rule_id']} / hard_negative" in rare_findings
    assert all(
        f["severity"] == "blocking"
        for f in skewed["findings"]
        if f["code"] == "rare_class_total_disagreement"
    )
    assert skewed["assessment"]["status"] == "blocking_concerns"


def test_a_common_class_agreement_does_not_raise_a_rare_class_finding(skewed) -> None:
    """The flag has to discriminate: the easy majority class must not trip it."""
    rule_row = skewed["per_rule"][0]
    conforming = next(r for r in rule_row["labels"] if r["label"] == "conforming")
    assert conforming["both_count"] == 57
    assert not conforming["rare"]
    assert not conforming["total_disagreement"]


# -- absence -----------------------------------------------------------------


def test_an_absent_round_yields_an_unavailable_report_not_a_zeroed_one(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """An unrun round and a round nobody agreed on are opposite facts (ADR-0002)."""
    a = [judgment("llm-annotator-a", f"ex-{i}", rule_id, "conforming") for i in range(5)]
    paths = write_rounds(tmp_path, a, None)
    assert not paths["round_b"].exists()
    report = build(ctx, paths)

    assert [m["metric"] for m in report["metrics"]] == list(EXPECTED_METRICS)
    for item in report["metrics"]:
        assert item["available"] is False
        assert item["raw_agreement"] is None
        assert item["unavailable_reason"]["code"] == "round_unavailable"
        assert item["chance_corrected"]["value"] is None
        for component in item.get("components", ()):
            assert component["raw_agreement"] is None
    assert report["assessment"]["status"] == "insufficient_evidence"
    assert report["per_rule"] == []
    assert report["rounds"][1]["available"] is False
    assert "no annotation round file" in report["rounds"][1]["unavailable_reason"]["detail"]
    # The report still names whose pass is missing, and says the identity was not
    # observed -- a declared instrument is not one that ran.
    assert report["annotators"][1]["annotator_id"] == "llm-annotator-b"
    assert report["annotators"][1]["identity_source"] == "expected_from_caller"
    assert report["annotators"][1]["judgments"] == 0


def test_a_round_holding_no_judgments_is_unavailable_not_empty_agreement(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """An existing but empty round file is still a round that produced nothing."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "conforming")]
    paths = write_rounds(tmp_path, a, [])
    report = build(ctx, paths)
    assert report["rounds"][1]["available"] is False
    assert report["rounds"][1]["unavailable_reason"]["code"] == "round_unavailable"
    assert report["assessment"]["status"] == "insufficient_evidence"


def test_kappa_is_unavailable_rather_than_one_when_chance_predicts_everything(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """Expected agreement of exactly 1 is a divide by zero, not perfect agreement.

    Both passes calling every unit ``ASSESS`` is the ordinary shape of the profile
    axis. Reporting kappa 1.0 there claims skill the data cannot show.
    """
    a = [judgment("llm-annotator-a", f"ex-{i}", rule_id, "conforming") for i in range(4)]
    b = [judgment("llm-annotator-b", f"ex-{i}", rule_id, "conforming") for i in range(4)]
    report = build(ctx, write_rounds(tmp_path, a, b))
    profile = metric(report, "profile_agreement")
    assert profile["available"] is True
    assert profile["raw_agreement"] == 1.0
    assert profile["chance_corrected"]["available"] is False
    assert profile["chance_corrected"]["value"] is None
    assert profile["chance_corrected"]["unavailable_reason"]["code"] == "expected_agreement_is_one"


def test_a_condition_no_unit_satisfies_is_unavailable_not_zero(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """No pair where both found the rule applicable is not zero label agreement."""
    a = [
        judgment(
            "llm-annotator-a", f"ex-{i}", rule_id, "hard_negative",
            applicability="not_applicable",
        )
        for i in range(4)
    ]
    b = [
        judgment(
            "llm-annotator-b", f"ex-{i}", rule_id, "hard_negative",
            applicability="not_applicable",
        )
        for i in range(4)
    ]
    report = build(ctx, write_rounds(tmp_path, a, b))
    conditional = metric(report, "label_agreement_conditional_on_applicable")
    assert conditional["available"] is False
    assert conditional["raw_agreement"] is None
    assert conditional["unavailable_reason"]["code"] == "no_unit_satisfied_condition"
    assert conditional["exclusions"][0]["count"] == 4


def test_context_sufficiency_is_never_inferred_from_an_empty_request_list(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """An annotator who asked for nothing did not thereby rate the context sufficient.

    ``requested_additional_context`` is a list of asks, not a rating. Reading its
    emptiness as ``sufficient`` would manufacture a unanimous rating out of two
    silences.
    """
    a = [
        judgment("llm-annotator-a", f"ex-{i}", rule_id, "conforming", sufficiency=None)
        for i in range(4)
    ]
    b = [
        judgment("llm-annotator-b", f"ex-{i}", rule_id, "conforming", sufficiency=None)
        for i in range(4)
    ]
    report = build(ctx, write_rounds(tmp_path, a, b))
    sufficiency = metric(report, "context_sufficiency_agreement")
    assert sufficiency["available"] is False
    assert sufficiency["raw_agreement"] is None
    assert sufficiency["unavailable_reason"]["code"] == "value_not_stated"
    assert sufficiency["exclusions"][0]["count"] == 4
    sources = {row["source"]: row["count"] for row in sufficiency["value_sources"]}
    assert sources["unavailable"] == 8 and sources["stated"] == 0


def test_the_insufficient_context_label_still_states_insufficiency(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """The one permitted fallback, and it is counted as derived rather than stated."""
    a = [
        judgment(
            "llm-annotator-a",
            f"ex-{i}",
            rule_id,
            "insufficient_context",
            sufficiency=None,
            applicability="undetermined",
            requested=["the surrounding section"],
        )
        for i in range(4)
    ]
    b = [
        judgment("llm-annotator-b", f"ex-{i}", rule_id, "conforming", sufficiency="complete")
        for i in range(4)
    ]
    report = build(ctx, write_rounds(tmp_path, a, b))
    sufficiency = metric(report, "context_sufficiency_agreement")
    assert sufficiency["available"] is True
    assert sufficiency["raw_agreement"] == 0.0
    sources = {row["source"]: row["count"] for row in sufficiency["value_sources"]}
    assert sources["derived_from_label"] == 4 and sources["stated"] == 4


# -- stated beats derived ----------------------------------------------------


def test_a_stated_applicability_outranks_the_label_derivation(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """A conforming judgment that states ``not_applicable`` is read as stated."""
    a = [
        judgment("llm-annotator-a", "ex-1", rule_id, "conforming", applicability="not_applicable")
    ]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming", applicability=None)]
    report = build(ctx, write_rounds(tmp_path, a, b))
    applicability = metric(report, "rule_applicability_agreement")
    assert applicability["raw_agreement"] == 0.0
    sources = {row["source"]: row["count"] for row in applicability["value_sources"]}
    assert sources["stated"] == 1 and sources["derived_from_label"] == 1
    assert any(f["code"] == "value_derived_not_stated" for f in report["findings"])


def test_an_unreadable_stated_value_raises_rather_than_falling_back(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """A value the annotator supplied and this tool cannot read is a defect, not an absence."""
    broken = judgment("llm-annotator-a", "ex-1", rule_id, "conforming")
    broken["extensions"][agreement.EXT_APPLICABILITY] = "probably"
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming")]
    with pytest.raises(UsageError, match="probably"):
        build(ctx, write_rounds(tmp_path, [broken], b))


# -- per-rule matrices -------------------------------------------------------


def test_a_thin_rule_gets_a_matrix_and_a_small_n_flag_not_suppression(
    ctx: Context, rule_id: str, other_rule_id: str, tmp_path: Path
) -> None:
    """Suppressing thin rows hides exactly the rules whose evidence is thinnest."""
    a = [judgment("llm-annotator-a", f"ex-{i}", rule_id, "conforming") for i in range(3)]
    b = [judgment("llm-annotator-b", f"ex-{i}", rule_id, "conforming") for i in range(3)]
    a.append(judgment("llm-annotator-a", "ex-x", other_rule_id, "violation",
                      spans=[{"kind": "character", "start": 0, "end": 4}]))
    b.append(judgment("llm-annotator-b", "ex-x", other_rule_id, "violation",
                      spans=[{"kind": "character", "start": 0, "end": 4}]))
    report = build(ctx, write_rounds(tmp_path, a, b))

    rows = {row["rule_id"]: row for row in report["per_rule"]}
    assert set(rows) == {rule_id, other_rule_id}
    thin = rows[other_rule_id]
    assert thin["n"] == 1
    assert thin["small_n"] is True
    assert thin["small_n_threshold"] == agreement.SMALL_N_THRESHOLD
    assert thin["confusion"]["class_order"] == list(agreement.LABELS)
    assert len(thin["confusion"]["matrix"]) == len(agreement.LABELS)
    assert sum(sum(row) for row in thin["confusion"]["matrix"]) == thin["n"]
    assert {f["subject"] for f in report["findings"] if f["code"] == "small_n_rule"} == {
        rule_id,
        other_rule_id,
    }


def test_a_rule_nobody_judged_twice_is_named_not_given_a_matrix_of_zeros(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """A zero matrix would read as measured agreement on nothing."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "conforming")]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming")]
    report = build(ctx, write_rounds(tmp_path, a, b))
    assert [row["rule_id"] for row in report["per_rule"]] == [rule_id]
    assert rule_id not in report["rules_without_paired_units"]
    assert len(report["rules_without_paired_units"]) == len(ctx.registry) - 1


def test_a_label_neither_pass_used_reports_unavailable_specific_agreement(skewed) -> None:
    """Zero over zero is not zero agreement about a label nobody applied."""
    row = next(
        r for r in skewed["per_rule"][0]["labels"] if r["label"] == "insufficient_context"
    )
    assert row["role_a_count"] == 0 and row["role_b_count"] == 0
    assert row["positive_specific_agreement"]["available"] is False
    assert row["positive_specific_agreement"]["value"] is None
    assert row["positive_specific_agreement"]["unavailable_reason"]["code"] == (
        "class_unused_by_both"
    )


# -- evidence spans ----------------------------------------------------------


def test_a_span_token_is_one_character_position_over_a_half_open_interval() -> None:
    """[0, 3) is three tokens, and an adjacent span never double-counts the boundary."""
    one = judgment("a", "ex-1", "ATS-X-000", "violation",
                   spans=[{"kind": "character", "start": 0, "end": 3}])
    tokens, convention = agreement.span_tokens(one)
    assert tokens == frozenset({("ex-1", 0), ("ex-1", 1), ("ex-1", 2)})
    assert convention == "example_id"

    adjacent = judgment("a", "ex-1", "ATS-X-000", "violation",
                        spans=[{"kind": "character", "start": 0, "end": 3},
                               {"kind": "character", "start": 3, "end": 5}])
    assert len(agreement.span_tokens(adjacent)[0]) == 5


def test_overlapping_and_reordered_spans_do_not_change_the_token_set() -> None:
    """Tokens are a set, so a citation split into two overlapping spans scores the same."""
    single = judgment("a", "ex-1", "ATS-X-000", "violation",
                      spans=[{"kind": "character", "start": 0, "end": 10}])
    split = judgment("a", "ex-1", "ATS-X-000", "violation",
                     spans=[{"kind": "character", "start": 6, "end": 10},
                            {"kind": "character", "start": 0, "end": 8}])
    assert agreement.span_tokens(single)[0] == agreement.span_tokens(split)[0]


def test_token_f1_scores_the_overlap_of_the_two_span_sets(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """Ten characters each, six shared: F1 = 2*6 / (10 + 10)."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "violation",
                  spans=[{"kind": "character", "start": 10, "end": 20}])]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "violation",
                  spans=[{"kind": "character", "start": 14, "end": 24}])]
    report = build(ctx, write_rounds(tmp_path, a, b))
    spans = metric(report, "evidence_span_token_f1")
    assert spans["available"] is True
    assert spans["n"] == 1
    assert spans["raw_agreement"] == 0.6
    assert spans["chance_corrected"]["available"] is False
    assert spans["chance_corrected"]["unavailable_reason"]["code"] == "chance_baseline_undefined"


def test_units_where_neither_pass_cited_a_span_are_excluded_not_scored_perfect(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """Two annotators who cited nothing have not agreed about where the evidence is."""
    a = [judgment("llm-annotator-a", f"ex-{i}", rule_id, "conforming") for i in range(3)]
    b = [judgment("llm-annotator-b", f"ex-{i}", rule_id, "conforming") for i in range(3)]
    report = build(ctx, write_rounds(tmp_path, a, b))
    spans = metric(report, "evidence_span_token_f1")
    assert spans["available"] is False
    assert spans["raw_agreement"] is None
    assert spans["unavailable_reason"]["code"] == "no_spans_cited"
    assert spans["n"] == 0 and spans["n_excluded"] == 3
    assert spans["exclusions"][0]["reason"] == "no_span_cited_by_either"


def test_a_line_span_is_excluded_rather_than_tokenised_as_characters(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """A line range carries no character offsets; reading its numbers as offsets
    would score noise."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "violation",
                  spans=[{"kind": "line", "start_line": 3, "end_line": 4}])]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "violation",
                  spans=[{"kind": "character", "start": 3, "end": 4}])]
    report = build(ctx, write_rounds(tmp_path, a, b))
    spans = metric(report, "evidence_span_token_f1")
    assert spans["available"] is False
    assert spans["n_excluded"] == 1
    assert spans["exclusions"][0]["reason"] == "span_not_character_addressed"


def test_offsets_keyed_against_different_targets_are_not_compared(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """One pass keying offsets to a source digest and one to the example would
    score a false zero."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "violation",
                  spans=[{"kind": "character", "start": 0, "end": 5, "source_sha256": "c" * 64}])]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "violation",
                  spans=[{"kind": "character", "start": 0, "end": 5}])]
    report = build(ctx, write_rounds(tmp_path, a, b))
    spans = metric(report, "evidence_span_token_f1")
    assert spans["available"] is False
    assert spans["exclusions"][0]["reason"] == "inconsistent_span_target"


# -- who the annotators are --------------------------------------------------


def test_the_report_states_that_both_passes_are_llm_passes(skewed) -> None:
    """Instrument reproducibility and inter-rater reliability are different claims."""
    assert skewed["measurement"]["kind"] == "instrument_reproducibility"
    statement = skewed["measurement"]["statement"]
    assert "LLM passes" in statement
    assert "NOT human inter-rater reliability" in statement
    assert [row["kind"] for row in skewed["annotators"]] == ["llm", "llm"]
    assert [row["model"] for row in skewed["annotators"]] == ["test-model-a", "test-model-b"]
    assert [row["prompt_id"] for row in skewed["annotators"]] == [
        "synthetic-round-a",
        "synthetic-round-b",
    ]


def test_an_undeclared_annotator_kind_is_unknown_and_never_human(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """``unknown`` and ``human`` are distinct states; absence resolves to neither."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "conforming")]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming")]
    paths = write_rounds(tmp_path, a, b, registry=None)
    report = build(ctx, paths)
    assert report["annotator_registry"]["available"] is False
    assert report["annotator_registry"]["unavailable_reason"]["code"] == "registry_missing"
    assert [row["kind"] for row in report["annotators"]] == ["unknown", "unknown"]
    assert report["measurement"]["kind"] == "unknown"
    assert "NOT assumed to be human" in report["measurement"]["statement"]
    codes = {f["code"] for f in report["findings"]}
    assert "annotator_registry_unavailable" in codes
    assert "annotator_kind_undeclared" in codes


def test_a_registry_that_disagrees_with_the_round_is_a_blocking_finding(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """Two sources naming different models for one id means one is wrong; neither is chosen."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "conforming")]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming")]
    round_record = {
        "schema_version": "ats.annotation_round.v1",
        "annotators": [
            {
                "annotator_id": "llm-annotator-a",
                "kind": "llm",
                "model": "a-different-model",
                "prompt_id": "synthetic-round-a",
                "prompt_sha256": "a" * 64,
            }
        ],
    }
    report = build(ctx, write_rounds(tmp_path, a, b, extra_a=[round_record]))
    mismatch = [f for f in report["findings"] if f["code"] == "annotator_registry_round_mismatch"]
    assert mismatch and mismatch[0]["severity"] == "blocking"
    assert report["annotator_registry"]["cross_check"]["agrees"] is False
    assert report["assessment"]["status"] == "blocking_concerns"


def test_the_round_record_document_corroborates_the_registry(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """The pilot keeps its round record beside the rounds, not inside them.

    The registry file alone is one source. Corroboration is the point of reading
    the round record at all, so the report says whether it happened.
    """
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "conforming")]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming")]
    paths = write_rounds(tmp_path, a, b)
    record = tmp_path / "annotation_round.json"
    record.write_text(
        json.dumps({"schema_version": "ats.annotation_round.v1", **REGISTRY}), encoding="utf-8"
    )

    uncorroborated = build(ctx, paths)
    assert uncorroborated["annotator_registry"]["cross_check"]["performed"] is False

    report = agreement.build_agreement_report(
        ctx,
        round_a=paths["round_a"],
        round_b=paths["round_b"],
        annotators=paths["annotators"],
        round_record=record,
    )
    cross_check = report["annotator_registry"]["cross_check"]
    assert cross_check["performed"] is True and cross_check["agrees"] is True
    assert not [
        f for f in report["findings"] if f["code"] == "annotator_registry_round_mismatch"
    ]


def test_a_round_record_naming_a_different_prompt_blocks(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """Prompt identity is instrument identity; two answers means neither is established."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "conforming")]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming")]
    paths = write_rounds(tmp_path, a, b)
    record = tmp_path / "annotation_round.json"
    drifted = json.loads(json.dumps(REGISTRY))
    drifted["annotators"][0]["prompt_sha256"] = "f" * 64
    record.write_text(
        json.dumps({"schema_version": "ats.annotation_round.v1", **drifted}), encoding="utf-8"
    )
    report = agreement.build_agreement_report(
        ctx,
        round_a=paths["round_a"],
        round_b=paths["round_b"],
        annotators=paths["annotators"],
        round_record=record,
    )
    mismatch = [
        f for f in report["findings"] if f["code"] == "annotator_registry_round_mismatch"
    ]
    assert mismatch and mismatch[0]["subject"] == "llm-annotator-a"
    assert report["assessment"]["status"] == "blocking_concerns"



def test_a_round_mixing_two_annotators_is_not_one_pass(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """A round compared as one pass must be one pass."""
    a = [
        judgment("llm-annotator-a", "ex-1", rule_id, "conforming"),
        judgment("llm-annotator-b", "ex-2", rule_id, "conforming"),
    ]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming")]
    report = build(ctx, write_rounds(tmp_path, a, b))
    assert report["rounds"][0]["available"] is False
    assert "mixes judgments" in report["rounds"][0]["unavailable_reason"]["detail"]
    assert report["assessment"]["status"] == "insufficient_evidence"


# -- pairing -----------------------------------------------------------------


def test_a_unit_judged_twice_by_one_pass_is_dropped_with_its_reason(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """Choosing between one annotator's two answers would decide which opinion counts."""
    a = [
        judgment("llm-annotator-a", "ex-1", rule_id, "conforming"),
        judgment("llm-annotator-a", "ex-1", rule_id, "violation",
                 spans=[{"kind": "character", "start": 0, "end": 2}]),
        judgment("llm-annotator-a", "ex-2", rule_id, "conforming"),
    ]
    b = [
        judgment("llm-annotator-b", "ex-1", rule_id, "conforming"),
        judgment("llm-annotator-b", "ex-2", rule_id, "conforming"),
    ]
    report = build(ctx, write_rounds(tmp_path, a, b))
    assert report["pairing"]["paired_units"] == 1
    dropped = report["pairing"]["dropped_units"]
    assert [d["example_id"] for d in dropped] == ["ex-1"]
    assert dropped[0]["reason"] == "duplicate_judgments_from_one_annotator"
    assert any(f["code"] == "duplicate_judgments_for_unit" for f in report["findings"])


def test_units_only_one_pass_saw_are_counted_not_compared(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """Spec 17.9's two-judgment floor is unmet for a unit only one pass judged."""
    a = [judgment("llm-annotator-a", f"ex-{i}", rule_id, "conforming") for i in range(3)]
    b = [judgment("llm-annotator-b", "ex-0", rule_id, "conforming")]
    report = build(ctx, write_rounds(tmp_path, a, b))
    assert report["pairing"]["paired_units"] == 1
    assert report["pairing"]["role_a_only"] == 2
    assert report["pairing"]["role_b_only"] == 0
    assert any(f["code"] == "unpaired_units" for f in report["findings"])


# -- conditioning ------------------------------------------------------------


def test_label_agreement_excludes_units_one_pass_found_inapplicable(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """Unconditional label agreement measures the corpus's class balance, not the passes."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "conforming")]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming")]
    a.append(
        judgment("llm-annotator-a", "ex-2", rule_id, "hard_negative",
                 applicability="not_applicable")
    )
    b.append(
        judgment("llm-annotator-b", "ex-2", rule_id, "hard_negative",
                 applicability="not_applicable")
    )
    report = build(ctx, write_rounds(tmp_path, a, b))
    conditional = metric(report, "label_agreement_conditional_on_applicable")
    assert conditional["n"] == 1
    assert conditional["exclusions"][0]["count"] == 1
    # The unconditional applicability axis still sees both units.
    assert metric(report, "rule_applicability_agreement")["n"] == 2


# -- declines (AG-19 step 2) -------------------------------------------------


@pytest.fixture(scope="module")
def declined(ctx: Context, rule_id: str, tmp_path_factory) -> dict[str, Any]:
    """Ten units both passes judged, five round A declined and round B labelled."""
    a = [judgment("llm-annotator-a", f"ex-{i:02}", rule_id, "conforming") for i in range(10)]
    b = [judgment("llm-annotator-b", f"ex-{i:02}", rule_id, "conforming") for i in range(15)]
    declines = [
        non_judgment("llm-annotator-a", f"ex-{i:02}", rule_id) for i in range(10, 15)
    ]
    directory = tmp_path_factory.mktemp("declined")
    return build(ctx, write_rounds(directory, a, b, declined_a=declines))


def test_applicability_is_computed_over_declines_not_judgments_alone(declined) -> None:
    """Scoring only the judged units drops exactly where the passes disagree.

    Ten units both passes judged applicable, five round A declined and round B
    labelled. Over the judged units alone applicability agreement is a perfect
    1.0; over the units both passes actually answered it is 10/15. The first
    number is the dangerous one, and it is the one a judgment-only universe
    produces.
    """
    applicability = metric(declined, "rule_applicability_agreement")
    assert applicability["n"] == 15
    assert applicability["raw_agreement"] == round(10 / 15, 6)
    assert declined["pairing"]["applicability_paired_units"] == 15
    assert declined["pairing"]["paired_units"] == 10
    counts = {row["class"]: row for row in applicability["class_prevalence"]}
    assert counts["not_applicable"]["role_a_count"] == 5
    assert counts["not_applicable"]["role_b_count"] == 0
    assert counts["applicable"]["both_count"] == 10


def test_a_unit_one_pass_declined_is_not_counted_as_label_disagreement(declined) -> None:
    """It is an applicability disagreement; scoring it as a label outcome is wrong twice."""
    conditional = metric(declined, "label_agreement_conditional_on_applicable")
    assert conditional["n"] == 10
    assert conditional["raw_agreement"] == 1.0
    exclusions = {row["reason"]: row["count"] for row in conditional["exclusions"]}
    assert exclusions["one_pass_declined_to_judge"] == 5
    assert exclusions["both_passes_declined_to_judge"] == 0


def test_the_declines_are_reported_as_their_own_line(declined) -> None:
    """'One pass declined and the other did not' is the round's most useful output."""
    line = declined["declined_to_judge"]
    assert line["role_a_declined"] == 5
    assert line["role_b_declined"] == 0
    assert line["declined_by_exactly_one_pass"] == 5
    assert line["declined_by_both_passes"] == 0
    blocking = [
        f for f in declined["findings"] if f["code"] == "one_pass_declined_the_other_judged"
    ]
    assert blocking and blocking[0]["severity"] == "blocking"
    assert declined["assessment"]["status"] == "blocking_concerns"
    assert declined["rounds"][0]["sidecar"]["records"] == 5
    assert declined["rounds"][1]["sidecar"]["records"] == 0
    assert declined["rounds"][1]["sidecar"]["available"] is True


def test_an_absent_sidecar_is_unavailable_rather_than_zero_declines(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """An empty sidecar says 'I declined nothing'. A missing one says nothing at all."""
    a = [judgment("llm-annotator-a", f"ex-{i}", rule_id, "conforming") for i in range(3)]
    b = [judgment("llm-annotator-b", f"ex-{i}", rule_id, "conforming") for i in range(3)]
    report = build(ctx, write_rounds(tmp_path, a, b, sidecars=False))
    for round_row in report["rounds"]:
        assert round_row["sidecar"]["available"] is False
        assert round_row["sidecar"]["unavailable_reason"]["code"] == "sidecar_missing"
        assert round_row["sidecar"]["records"] == 0
    codes = {f["code"] for f in report["findings"]}
    assert "applicability_sidecar_unavailable" in codes
    # The round itself still stands: a missing sidecar limits the applicability
    # universe, it does not invalidate the judgments.
    assert report["rounds"][0]["available"] is True
    assert metric(report, "rule_applicability_agreement")["n"] == 3


def test_a_unit_both_judged_and_declined_by_one_pass_is_dropped(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """'I judged it' and 'I declined it' contradict; neither answer is chosen."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "conforming")]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming")]
    report = build(
        ctx,
        write_rounds(
            tmp_path, a, b, declined_a=[non_judgment("llm-annotator-a", "ex-1", rule_id)]
        ),
    )
    contradiction = [
        f for f in report["findings"] if f["code"] == "unit_both_judged_and_declined"
    ]
    assert contradiction and contradiction[0]["severity"] == "blocking"
    assert report["pairing"]["applicability_paired_units"] == 0
    assert metric(report, "rule_applicability_agreement")["available"] is False


def test_a_sidecar_belonging_to_another_annotator_is_refused(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """A sidecar from the wrong pass would attribute one annotator's declines to another."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "conforming")]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming")]
    report = build(
        ctx,
        write_rounds(
            tmp_path, a, b, declined_a=[non_judgment("llm-annotator-b", "ex-2", rule_id)]
        ),
    )
    sidecar = report["rounds"][0]["sidecar"]
    assert sidecar["available"] is False
    assert sidecar["unavailable_reason"]["code"] == "sidecar_annotator_mismatch"
    # Its records are counted in the sidecar row as a fact about the file, but they
    # are not attributed to round a: an unusable file never becomes a count.
    assert sidecar["records"] == 1
    assert report["declined_to_judge"]["role_a_declined"] == 0
    assert report["declined_to_judge"]["universe_complete"] is False
    # The records were not folded into the universe: only the judged unit pairs.
    assert report["pairing"]["applicability_paired_units"] == 1


def test_a_decline_record_with_an_unreadable_state_raises(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """A stated applicability this tool cannot read is a defect, not an absence."""
    a = [judgment("llm-annotator-a", "ex-1", rule_id, "conforming")]
    b = [judgment("llm-annotator-b", "ex-1", rule_id, "conforming")]
    broken = non_judgment("llm-annotator-a", "ex-2", rule_id, applicability="maybe")
    with pytest.raises(UsageError, match="maybe"):
        build(ctx, write_rounds(tmp_path, a, b, declined_a=[broken]))


def test_a_rare_class_on_a_non_label_axis_is_flagged_too(
    ctx: Context, rule_id: str, tmp_path: Path
) -> None:
    """The blindness is not specific to labels: any axis's rare class can vanish.

    Forty units where both passes say the rule applies, and two where one pass says
    it cannot tell. Applicability agreement reads 0.952; the class that carries the
    round's actual uncertainty has no unit on which the passes agree.
    """
    a = [judgment("llm-annotator-a", f"ex-{i:02}", rule_id, "conforming") for i in range(40)]
    b = [judgment("llm-annotator-b", f"ex-{i:02}", rule_id, "conforming") for i in range(40)]
    for index in (40, 41):
        a.append(
            judgment(
                "llm-annotator-a", f"ex-{index}", rule_id, "ambiguous",
                applicability="undetermined", ambiguity="rule_boundary",
            )
        )
        b.append(judgment("llm-annotator-b", f"ex-{index}", rule_id, "conforming"))
    report = build(ctx, write_rounds(tmp_path, a, b))

    applicability = metric(report, "rule_applicability_agreement")
    assert applicability["raw_agreement"] == round(40 / 42, 6)
    undetermined = next(
        row for row in applicability["class_prevalence"] if row["class"] == "undetermined"
    )
    assert undetermined["role_a_count"] == 2 and undetermined["both_count"] == 0
    subjects = {
        f["subject"] for f in report["findings"] if f["code"] == "rare_class_total_disagreement"
    }
    assert "rule_applicability_agreement / undetermined" in subjects
    assert report["assessment"]["status"] == "blocking_concerns"

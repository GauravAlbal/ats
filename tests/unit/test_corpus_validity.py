"""Instrument validity against operator gold.

Three failures these tests defend. The first is a wrong number: every metric is
computed over a six-unit synthetic gold whose arithmetic is worked out by hand
below, so a change to a denominator, a mapping, or a conditional stratum moves a
value the test names exactly. The second is a silent narrowing: the report must
refuse to exist without gold, and a partial report must say so rather than
publishing figures that read as covering the corpus. The third is an absence
coerced into a value: an unused confidence bin, an unused class, and an
uncomputable ratio must all carry a code and a reason, never 0.0.

The fixture is deliberately small enough to check by inspection. The table in
``_CASES`` is the whole ground truth; every expected figure in this file is
derivable from it with a pencil.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from ats.context import Context
from ats.corpus import validity
from ats.errors import UsageError

NOW = _dt.datetime(2026, 8, 3, tzinfo=_dt.UTC)
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The text digest every evidence span in the fixture is keyed against.
SOURCE = "a" * 64

R1 = "ATS-TIME-002"
R2 = "ATS-DISC-001"

#: One row per conformance unit: (unit, rule, gold disposition, pass a, pass b).
#: Pass entries are ``(label | None, applicability, confidence | None)``; a
#: ``None`` label is a decline. ``u6`` is the operator excluding a unit from
#: gold, so it must vanish from every denominator.
_CASES: tuple[tuple[str, str, str, tuple, tuple], ...] = (
    ("u1", R1, "violation", ("violation", "applicable", "high"), ("conforming", "applicable", "high")),
    ("u2", R1, "conforming", ("conforming", "applicable", "moderate"), (None, "not_applicable", None)),
    ("u3", R1, "hard_negative", ("violation", "applicable", "moderate"), ("hard_negative", "applicable", "moderate")),
    ("u4", R2, "ambiguous_by_design", ("ambiguous", "applicable", "moderate"), ("violation", "applicable", "high")),
    ("u5", R2, "insufficient_context", ("insufficient_context", "applicable", "moderate"), ("insufficient_context", "applicable", "moderate")),
    ("u6", R2, "excluded", ("violation", "applicable", "high"), ("violation", "applicable", "high")),
)

#: Operator evidence, by unit: the offsets and which stage carries them. Units
#: absent from this map are units the operator cited nothing on.
_OPERATOR_OFFSETS: dict[str, tuple[str, list[list[int]]]] = {
    "u1": ("disagreement_review", [[5, 15]]),
    "u2": ("disagreement_review", [[0, 4]]),
    "u4": ("source_only", [[0, 2]]),
}

#: Instrument evidence spans, by (role, unit). A unit absent from a role's map
#: is a unit that role left no judgment for.
_SPANS: dict[tuple[str, str], list[list[int]]] = {
    ("a", "u1"): [[0, 10]],
    ("a", "u2"): [[0, 4]],
    ("a", "u3"): [[0, 3]],
    ("a", "u4"): [],
    ("a", "u5"): [[0, 3]],
    ("a", "u6"): [[0, 3]],
    ("b", "u1"): [[8, 12]],
    ("b", "u3"): [[0, 3]],
    ("b", "u4"): [[0, 1]],
    ("b", "u5"): [[0, 3]],
    ("b", "u6"): [[0, 3]],
}

#: Profile units: (unit, gold classification, recon-a vote, recon-b vote).
_PROFILE: tuple[tuple[str, str, str, str], ...] = (
    ("p1", "SPECIFY", "SPECIFY", "ASSESS"),
    ("p2", "mixed", "mixed", "mixed"),
)


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


def _bundle(unit_id: str) -> str:
    """A stable synthetic bundle id. Never ``hash()``: it is salted per process."""
    return "ats-bundle-sha256:" + hashlib.sha256(unit_id.encode()).hexdigest()


def _unit(unit_id: str) -> str:
    """The identifier-format id a raw case name takes in any document.

    The tables keep symbolic names; every id that enters a queue, a gold row,
    or an assertion about a report takes this form, because the report schema
    holds exposure entries to the identifier contract and the fixture adapts
    to the schema, never the reverse."""
    return "ats-adjunit-sha256:" + hashlib.sha256(("unit:" + unit_id).encode()).hexdigest()


def _pass(entry: tuple) -> dict[str, Any]:
    label, applicability, confidence = entry
    if label is None:
        return {"kind": "declined", "applicability": applicability}
    return {
        "kind": "judged",
        "label": label,
        "applicability": applicability,
        "context_sufficiency": "partial",
        "annotation_confidence": confidence,
    }


def _queue_unit(unit_id: str, kind: str, rule_id: str | None, judgments: dict) -> dict[str, Any]:
    return {
        "kind": kind,
        "bundle_id": _bundle(unit_id),
        "rule_id": rule_id,
        "repository": "fixture",
        "stratum": "fixture",
        "split_group": "group-fixture",
        "source_artifact_id": "ats-artifact-sha256:" + "0" * 64,
        "scope_reasons": ["applicable_by_at_least_one_pass"],
        "control": False,
        "priority_blocks": ["specify_form"] if kind == "profile" else [],
        "judgments": judgments,
        "payload_sha256": "0" * 64,
        "unit_id": _unit(unit_id),
    }


def build_queue() -> dict[str, Any]:
    """The synthetic adjudication queue the fixture is scored over."""
    units = [
        _queue_unit(unit_id, "conformance", rule_id, {"a": _pass(a), "b": _pass(b)})
        for unit_id, rule_id, _, a, b in _CASES
    ]
    units += [
        _queue_unit(
            unit_id,
            "profile",
            None,
            {
                "llm-recon-a": {"kind": "classified", "classification": vote_a},
                "llm-recon-b": {"kind": "classified", "classification": vote_b},
            },
        )
        for unit_id, _, vote_a, vote_b in _PROFILE
    ]
    return {
        "schema_version": "ats.adjudication_queue.v1",
        "queue_id": "ats-adjqueue-sha256:" + "1" * 64,
        "record_sha256": "1" * 64,
        "units": units,
    }


def _adjudicator() -> dict[str, str]:
    return {"kind": "human", "id": "operator:fixture"}


def _gold_rows(*, review_units: set[str] | None = None) -> list[dict[str, Any]]:
    """Append-only gold for the fixture, source-only then review per unit."""
    rows: list[dict[str, Any]] = []
    entries = [(unit_id, disposition) for unit_id, _, disposition, _, _ in _CASES]
    entries += [(unit_id, disposition) for unit_id, disposition, _, _ in _PROFILE]
    for unit_id, disposition in entries:
        stage, offsets = _OPERATOR_OFFSETS.get(unit_id, (None, None))
        source_only: dict[str, Any] = {
            "schema_version": "ats.operator_adjudication.v1",
            "unit_id": _unit(unit_id),
            "stage": "source_only",
            "adjudicator": _adjudicator(),
            "rationale": f"source-only reading of {unit_id}",
            "recorded_at": "2026-08-03T00:00:00Z",
            "disposition": disposition,
            "determinacy": "yes",
        }
        if disposition == "insufficient_context":
            source_only["missing_context"] = ["full_paragraph"]
        if stage == "source_only":
            source_only["evidence_offsets"] = offsets
        rows.append(source_only)

        if review_units is not None and unit_id not in review_units:
            continue
        review: dict[str, Any] = {
            "schema_version": "ats.operator_adjudication.v1",
            "unit_id": _unit(unit_id),
            "stage": "disagreement_review",
            "adjudicator": _adjudicator(),
            "rationale": f"review of {unit_id}",
            "recorded_at": "2026-08-03T00:00:00Z",
            "final_disposition": disposition,
            "decision_changed": False,
            "system_diagnosis": [{"code": "no_system_defect", "primary": True}],
            "competent_reader_could_reach_rejected": False,
        }
        if disposition == "insufficient_context":
            review["missing_context"] = ["full_paragraph"]
        if unit_id.startswith("p"):
            review["requirement_forms"] = ["declarative_invariant"]
        if stage == "disagreement_review":
            review["evidence_offsets"] = offsets
        rows.append(review)
    return rows


def _round_rows(role: str) -> list[dict[str, Any]]:
    rows = []
    for unit_id, rule_id, _, a, b in _CASES:
        entry = a if role == "a" else b
        label, applicability, confidence = entry
        if label is None or (role, unit_id) not in _SPANS:
            continue
        rows.append(
            {
                "schema_version": "ats.judgment.v1",
                "annotator_id": f"llm-annotator-{role}",
                "example_id": _bundle(unit_id),
                "rule_id": rule_id,
                "label": label,
                "annotation_confidence": confidence,
                "extensions": {"x-ats-repo-applicability": applicability},
                "evidence_spans": [
                    {"kind": "character", "start": s, "end": e, "source_sha256": SOURCE}
                    for s, e in _SPANS[(role, unit_id)]
                ],
            }
        )
    return rows


def _write_inputs(root: Path, *, review_units: set[str] | None = None, gold: bool = True) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    queue_path = root / "queue.json"
    queue_path.write_text(json.dumps(build_queue()), encoding="utf-8")
    gold_path = root / "gold.jsonl"
    if gold:
        gold_path.write_text(
            "".join(json.dumps(row) + "\n" for row in _gold_rows(review_units=review_units)),
            encoding="utf-8",
        )
    paths = {"queue": queue_path, "gold": gold_path}
    for role in ("a", "b"):
        path = root / f"round-{role}.jsonl"
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in _round_rows(role)), encoding="utf-8"
        )
        paths[f"round_{role}"] = path
    agreement = root / "agreement.json"
    agreement.write_text(
        json.dumps(
            {"schema_version": "ats.agreement_report.v1", "report_sha256": "a" * 64}
        ),
        encoding="utf-8",
    )
    paths["agreement"] = agreement
    return paths


@pytest.fixture(scope="module")
def report(ctx: Context, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """The report over complete synthetic gold. Every arithmetic test reads this."""
    paths = _write_inputs(tmp_path_factory.mktemp("validity-complete"))
    return validity.build_validity_report(
        ctx,
        queue=paths["queue"],
        gold=paths["gold"],
        round_a=paths["round_a"],
        round_b=paths["round_b"],
        agreement_report=paths["agreement"],
    )


# -- accessors ---------------------------------------------------------------


def metric_of(report: Mapping[str, Any], role: str, name: str) -> Mapping[str, Any]:
    block = next(b for b in report["instruments"] if b["role"] == role)
    return next(m for m in block["metrics"] if m["metric"] == name)


def rate_of(metric: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    return next(r for r in metric["rates"] if r["name"] == name)


def class_of(metric: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    return next(row for row in metric["per_class"] if row["class"] == name)


def bin_of(metric: Mapping[str, Any], level: str) -> Mapping[str, Any]:
    return next(row for row in metric["bins"] if row["confidence"] == level)


# -- refusal -----------------------------------------------------------------


def test_refuses_when_gold_is_absent(ctx: Context, tmp_path: Path) -> None:
    """No gold, no report. The counts are in the refusal, not in a stub artefact."""
    paths = _write_inputs(tmp_path, gold=False)
    with pytest.raises(validity.GoldIncomplete) as raised:
        validity.build_validity_report(ctx, queue=paths["queue"], gold=paths["gold"])
    payload = raised.value.payload()
    assert payload["error"] == "gold_incomplete"
    assert raised.value.exit_code == 2
    assert "0/8" in payload["message"]
    assert {row["unit_kind"]: row["adjudicated"] for row in payload["coverage"]} == {
        "conformance": 0,
        "profile": 0,
    }
    assert {row["unit_kind"]: row["required"] for row in payload["coverage"]} == {
        "conformance": 6,
        "profile": 2,
    }


def test_refuses_when_gold_covers_only_some_units(ctx: Context, tmp_path: Path) -> None:
    """A source-only judgment is not gold, and neither is a half-adjudicated queue."""
    paths = _write_inputs(tmp_path, review_units={"u1", "u2", "p1"})
    with pytest.raises(validity.GoldIncomplete) as raised:
        validity.build_validity_report(
            ctx, queue=paths["queue"], gold=paths["gold"], allow_partial=False
        )
    payload = raised.value.payload()
    assert "3/8" in payload["message"]
    conformance = next(r for r in payload["coverage"] if r["unit_kind"] == "conformance")
    assert conformance["adjudicated"] == 2
    assert conformance["source_only_awaiting_review"] == 4
    assert conformance["complete"] is False


def test_allow_partial_publishes_coverage_and_per_metric_n(ctx: Context, tmp_path: Path) -> None:
    """The partial mode narrows out loud: coverage at the top, n on every metric."""
    paths = _write_inputs(tmp_path, review_units={"u1", "u2", "p1"})
    partial = validity.build_validity_report(
        ctx,
        queue=paths["queue"],
        gold=paths["gold"],
        round_a=paths["round_a"],
        round_b=paths["round_b"],
        allow_partial=True,
    )
    assert partial["coverage"]["partial"] is True
    assert partial["coverage"]["allow_partial"] is True
    assert partial["coverage"]["adjudicated"] == 3
    assert partial["coverage"]["required"] == 8
    assert all("n" in m for block in partial["instruments"] for m in block["metrics"])
    assert metric_of(partial, "a", "applicability")["n"] == 2
    assert partial["assessment"]["status"] == "insufficient_evidence"
    assert any(f["code"] == "gold_partial" for f in partial["findings"])


def test_missing_queue_is_a_usage_error_not_a_gold_refusal(ctx: Context, tmp_path: Path) -> None:
    """The queue is committed; its absence is a different failure from missing gold."""
    with pytest.raises(UsageError) as raised:
        validity.build_validity_report(
            ctx, queue=tmp_path / "nope.json", gold=tmp_path / "gold.jsonl"
        )
    assert not isinstance(raised.value, validity.GoldIncomplete)


# -- scope -------------------------------------------------------------------


def test_excluded_units_leave_every_denominator(report: Mapping[str, Any]) -> None:
    """``excluded`` removes a unit from gold, so it may not be scored against."""
    assert next(b for b in report["instruments"] if b["role"] == "a")["units_scored"] == 5
    conformance = next(
        row for row in report["coverage"]["by_unit_kind"] if row["unit_kind"] == "conformance"
    )
    assert conformance["adjudicated"] == 6
    assert conformance["excluded_by_operator"] == 1
    assert conformance["scored"] == 5
    assert conformance["complete"] is True


def test_coverage_is_complete_and_the_report_carries_no_partial_finding(
    report: Mapping[str, Any],
) -> None:
    assert report["coverage"]["partial"] is False
    assert report["coverage"]["adjudicated"] == 8
    assert [f["code"] for f in report["findings"]] == []
    assert report["assessment"]["status"] == "no_concerns_detected"


# -- applicability -----------------------------------------------------------


def test_applicability_precision_recall_for_instrument_a(report: Mapping[str, Any]) -> None:
    """a claims applicable on all five; gold makes three applicable and two undetermined."""
    metric = metric_of(report, "a", "applicability")
    assert metric["n"] == 5
    applicable = class_of(metric, "applicable")
    assert (applicable["instrument_count"], applicable["gold_count"], applicable["agreements"]) == (
        5,
        3,
        3,
    )
    assert applicable["precision"]["value"] == pytest.approx(0.6)
    assert applicable["precision"]["numerator"] == 3
    assert applicable["precision"]["denominator"] == 5
    assert applicable["recall"]["value"] == pytest.approx(1.0)
    assert applicable["f1"]["value"] == pytest.approx(0.75)


def test_hard_negative_counts_as_applicable_gold(report: Mapping[str, Any]) -> None:
    """The mapping the module documents, asserted rather than assumed.

    If ``hard_negative`` mapped to ``not_applicable`` as the agreement report's
    label fallback does, gold would show two applicable units, not three, and an
    instrument that correctly saw the rule was in scope would lose precision for
    it.
    """
    assert validity.GOLD_APPLICABILITY["hard_negative"] == "applicable"
    entry = next(
        row
        for row in report["vocabularies"]["gold_applicability_map"]
        if row["gold_disposition"] == "hard_negative"
    )
    assert entry["applicability_class"] == "applicable"
    assert class_of(metric_of(report, "a", "applicability"), "applicable")["gold_count"] == 3


def test_undecidable_gold_is_a_retained_third_class(report: Mapping[str, Any]) -> None:
    """Not excluded from the denominator: a is charged for claiming applicability."""
    metric = metric_of(report, "a", "applicability")
    undetermined = class_of(metric, "undetermined")
    assert undetermined["gold_count"] == 2
    assert undetermined["recall"]["value"] == pytest.approx(0.0)
    assert undetermined["recall"]["denominator"] == 2
    assert undetermined["precision"]["available"] is False
    assert undetermined["precision"]["unavailable_reason"]["code"] == "zero_denominator"
    # The two undecidable units are inside the applicability denominator, which
    # is why a's precision is 3/5 rather than 3/3.
    assert class_of(metric, "applicable")["precision"]["denominator"] == 5


def test_applicability_for_instrument_b_counts_its_decline(report: Mapping[str, Any]) -> None:
    metric = metric_of(report, "b", "applicability")
    applicable = class_of(metric, "applicable")
    assert applicable["precision"]["value"] == pytest.approx(0.5)
    assert applicable["recall"]["value"] == pytest.approx(2 / 3)
    not_applicable = class_of(metric, "not_applicable")
    assert not_applicable["precision"]["value"] == pytest.approx(0.0)
    assert not_applicable["precision"]["denominator"] == 1
    assert not_applicable["recall"]["available"] is False


def test_applicability_confusion_axes_are_named(report: Mapping[str, Any]) -> None:
    confusion = metric_of(report, "a", "applicability")["confusion"]
    assert confusion["row_axis"] == "instrument"
    assert confusion["column_axis"] == "operator_gold"
    row = confusion["table"][confusion["rows"].index("applicable")]
    assert row[confusion["columns"].index("applicable")] == 3
    assert row[confusion["columns"].index("undetermined")] == 2


# -- label accuracy ----------------------------------------------------------


def test_label_accuracy_is_conditional_on_both_applicable(report: Mapping[str, Any]) -> None:
    """a judged five units; only three have applicable gold, and two of those match."""
    metric = metric_of(report, "a", "label_accuracy_given_both_applicable")
    assert metric["n"] == 3
    accuracy = rate_of(metric, "accuracy")
    assert (accuracy["numerator"], accuracy["denominator"]) == (2, 3)
    assert accuracy["value"] == pytest.approx(2 / 3)


def test_label_confusion_locates_the_single_error(report: Mapping[str, Any]) -> None:
    confusion = metric_of(report, "a", "label_accuracy_given_both_applicable")["confusion"]
    row = confusion["table"][confusion["rows"].index("violation")]
    assert row[confusion["columns"].index("violation")] == 1
    assert row[confusion["columns"].index("hard_negative")] == 1


def test_label_accuracy_excludes_declines_from_its_denominator(report: Mapping[str, Any]) -> None:
    """b declined u2, so the both-applicable stratum holds two units, not three."""
    metric = metric_of(report, "b", "label_accuracy_given_both_applicable")
    assert metric["n"] == 2
    assert rate_of(metric, "accuracy")["value"] == pytest.approx(0.5)


# -- ambiguity and context insufficiency -------------------------------------


def test_ambiguity_aligns_the_two_vocabularies(report: Mapping[str, Any]) -> None:
    """`ambiguous` and `ambiguous_by_design` are one claim; a gets it right once."""
    metric = metric_of(report, "a", "ambiguity")
    assert metric["n"] == 5
    assert metric["counts"] == {
        "true_positive": 1,
        "false_positive": 0,
        "false_negative": 0,
        "true_negative": 4,
    }
    assert rate_of(metric, "precision")["value"] == pytest.approx(1.0)
    assert rate_of(metric, "recall")["value"] == pytest.approx(1.0)


def test_ambiguity_miss_is_recall_zero_and_precision_unavailable(
    report: Mapping[str, Any],
) -> None:
    """b never says ambiguous. Recall is a measured 0.0; precision was never measured."""
    metric = metric_of(report, "b", "ambiguity")
    assert metric["counts"]["false_negative"] == 1
    recall = rate_of(metric, "recall")
    assert recall["value"] == pytest.approx(0.0)
    assert recall["denominator"] == 1
    precision = rate_of(metric, "precision")
    assert precision["available"] is False
    assert precision["value"] is None
    assert precision["unavailable_reason"]["code"] == "zero_denominator"


def test_context_insufficiency_reads_the_label_not_the_rating(
    report: Mapping[str, Any],
) -> None:
    """Both passes call u5 insufficient, and both are right; no other unit is."""
    for role in ("a", "b"):
        metric = metric_of(report, role, "context_insufficiency")
        assert metric["counts"] == {
            "true_positive": 1,
            "false_positive": 0,
            "false_negative": 0,
            "true_negative": 4,
        }
    assert any(
        "context_sufficiency rating" in note
        for note in metric_of(report, "a", "context_insufficiency")["notes"]
    )


# -- evidence spans ----------------------------------------------------------


def test_evidence_span_token_f1_is_micro_pooled_over_character_positions(
    report: Mapping[str, Any],
) -> None:
    """u1 overlaps 5 of 10 and 10; u2 overlaps 4 of 4 and 4; u4 has no instrument span.

    True positives 5 + 4 + 0 = 9, false positives 5, false negatives 5 + 0 + 2 = 7,
    so micro F1 is 18/30.
    """
    metric = metric_of(report, "a", "evidence_span_token_f1")
    assert metric["n"] == 3
    micro = rate_of(metric, "micro_token_f1")
    assert (micro["numerator"], micro["denominator"]) == (18, 30)
    assert micro["value"] == pytest.approx(0.6)
    assert rate_of(metric, "precision")["value"] == pytest.approx(9 / 14)
    assert rate_of(metric, "recall")["value"] == pytest.approx(9 / 16)
    assert metric["macro_token_f1"] == pytest.approx((0.5 + 1.0 + 0.0) / 3)


def test_evidence_reports_how_many_units_the_operator_cited(
    report: Mapping[str, Any],
) -> None:
    metric = metric_of(report, "a", "evidence_span_token_f1")
    assert metric["operator_evidence"] == {
        "units_with_operator_offsets": 3,
        "from_disagreement_review": 2,
        "from_source_only": 1,
    }
    reasons = {row["reason"]: row["count"] for row in metric["exclusions"]}
    assert reasons == {"operator_cited_nothing": 2}
    considered = rate_of(metric, "units_scored_of_units_considered")
    assert (considered["numerator"], considered["denominator"]) == (3, 5)


def test_a_decline_is_excluded_from_span_overlap_rather_than_scored_zero(
    report: Mapping[str, Any],
) -> None:
    """b left no judgment on u2, so u2 leaves the span denominator with a reason."""
    metric = metric_of(report, "b", "evidence_span_token_f1")
    reasons = {row["reason"]: row["count"] for row in metric["exclusions"]}
    assert reasons["pass_left_no_judgment"] == 1
    assert metric["n"] == 2


def test_evidence_is_unavailable_when_the_round_is_absent(
    ctx: Context, tmp_path: Path
) -> None:
    """Every other metric still computes; the span metric says why it cannot."""
    paths = _write_inputs(tmp_path)
    built = validity.build_validity_report(ctx, queue=paths["queue"], gold=paths["gold"])
    metric = metric_of(built, "a", "evidence_span_token_f1")
    assert metric["available"] is False
    assert metric["unavailable_reason"]["code"] == "rounds_absent"
    assert metric_of(built, "a", "applicability")["available"] is True


# -- confidence calibration --------------------------------------------------


def test_empty_confidence_bin_is_unavailable_never_zero(report: Mapping[str, Any]) -> None:
    """Neither pass ever declared low confidence. That is not an accuracy of 0.0."""
    for role in ("a", "b"):
        low = bin_of(metric_of(report, role, "confidence_calibration"), "low")
        assert low["n"] == 0
        assert low["accuracy"]["available"] is False
        assert low["accuracy"]["value"] is None
        assert low["accuracy"]["unavailable_reason"]["code"] == "confidence_bin_empty"


def test_a_measured_zero_bin_is_distinguishable_from_an_empty_one(
    report: Mapping[str, Any],
) -> None:
    """b is wrong on both of its high-confidence units: 0.0, available, n=2."""
    high = bin_of(metric_of(report, "b", "confidence_calibration"), "high")
    assert high["n"] == 2
    assert high["matches"] == 0
    assert high["accuracy"]["available"] is True
    assert high["accuracy"]["value"] == pytest.approx(0.0)
    assert high["accuracy"]["denominator"] == 2


def test_calibration_bins_count_and_score_correctly(report: Mapping[str, Any]) -> None:
    metric = metric_of(report, "a", "confidence_calibration")
    assert metric["n"] == 5
    moderate = bin_of(metric, "moderate")
    assert (moderate["n"], moderate["matches"]) == (4, 3)
    assert moderate["accuracy"]["value"] == pytest.approx(0.75)
    high = bin_of(metric, "high")
    assert (high["n"], high["matches"]) == (1, 1)
    assert metric["declined_without_confidence"] == 0


def test_declines_sit_outside_every_confidence_bin(report: Mapping[str, Any]) -> None:
    """b declined one in-scope unit; it is named, not folded into the weakest bin."""
    metric = metric_of(report, "b", "confidence_calibration")
    assert metric["declined_without_confidence"] == 1
    assert sum(row["n"] for row in metric["bins"]) == 4


# -- error type by rule ------------------------------------------------------


def test_error_type_by_rule_localises_the_mismatch(report: Mapping[str, Any]) -> None:
    rows = {
        row["rule_id"]: row
        for row in next(b for b in report["instruments"] if b["role"] == "a")[
            "error_type_by_rule"
        ]
    }
    assert rows[R1]["n"] == 3
    assert rows[R1]["mismatches"] == 1
    assert rows[R1]["mismatch_rate"]["value"] == pytest.approx(1 / 3)
    assert rows[R1]["by_outcome_pair"] == [
        {"instrument": "violation", "gold": "hard_negative", "count": 1}
    ]
    assert rows[R2]["mismatches"] == 0
    assert rows[R2]["by_outcome_pair"] == []


def test_a_decline_is_its_own_outcome_class(report: Mapping[str, Any]) -> None:
    """b's decline on u2 is a mismatch recorded as a refusal, not as a wrong label."""
    rows = {
        row["rule_id"]: row
        for row in next(b for b in report["instruments"] if b["role"] == "b")[
            "error_type_by_rule"
        ]
    }
    pairs = {(p["instrument"], p["gold"]) for p in rows[R1]["by_outcome_pair"]}
    assert ("declined_not_applicable", "conforming") in pairs
    assert rows[R1]["mismatches"] == 2


# -- profile reconnaissance --------------------------------------------------


def test_profile_instruments_are_scored_separately(report: Mapping[str, Any]) -> None:
    blocks = {b["annotator_id"]: b for b in report["profile_instruments"]}
    assert set(blocks) == {"llm-recon-a", "llm-recon-b"}
    metric_a = blocks["llm-recon-a"]["metrics"][0]
    assert rate_of(metric_a, "accuracy")["value"] == pytest.approx(1.0)
    metric_b = blocks["llm-recon-b"]["metrics"][0]
    assert (
        rate_of(metric_b, "accuracy")["numerator"],
        rate_of(metric_b, "accuracy")["denominator"],
    ) == (1, 2)
    confusion = metric_b["confusion"]
    assert confusion["columns"] == list(validity.PROFILE_DISPOSITIONS)
    row = confusion["table"][confusion["rows"].index("ASSESS")]
    assert row[confusion["columns"].index("SPECIFY")] == 1


# -- framing -----------------------------------------------------------------


def test_measurement_kinds_are_structural(report: Mapping[str, Any]) -> None:
    """Three kinds, named. Reproducibility is cross-referenced, not established here."""
    kinds = {entry["kind"]: entry for entry in report["measurements"]}
    assert set(kinds) == set(validity.MEASUREMENT_KINDS)
    for role in ("a", "b"):
        entry = kinds[f"instrument_{role}_reproducibility"]
        assert entry["established_by"] == "cross_reference"
        assert entry["separable_by_instrument"] is False
        assert entry["cross_reference"]["available"] is True
        assert entry["cross_reference"]["schema_version"] == "ats.agreement_report.v1"
        assert len(entry["cross_reference"]["report_sha256"]) == 64
    validity_entry = kinds["instrument_to_operator_validity"]
    assert validity_entry["established_by"] == "this_report"
    assert validity_entry["separable_by_instrument"] is True


def test_absent_agreement_report_is_a_typed_unavailability(
    ctx: Context, tmp_path: Path
) -> None:
    paths = _write_inputs(tmp_path)
    built = validity.build_validity_report(
        ctx,
        queue=paths["queue"],
        gold=paths["gold"],
        agreement_report=tmp_path / "no-such-report.json",
    )
    reference = built["measurements"][0]["cross_reference"]
    assert reference["available"] is False
    assert reference["report_sha256"] is None
    assert reference["unavailable_reason"]["code"] == "agreement_report_absent"
    assert any(f["code"] == "reproducibility_not_cross_referenced" for f in built["findings"])


def test_stale_round_against_the_queue_is_blocking_not_reconciled(
    ctx: Context, tmp_path: Path
) -> None:
    """Two documents disagreeing about what a pass answered means one is stale."""
    paths = _write_inputs(tmp_path)
    rows = [json.loads(line) for line in paths["round_a"].read_text().splitlines()]
    rows[0]["label"] = "near_miss"
    paths["round_a"].write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    built = validity.build_validity_report(
        ctx,
        queue=paths["queue"],
        gold=paths["gold"],
        round_a=paths["round_a"],
        round_b=paths["round_b"],
    )
    assert any(f["code"] == "round_queue_label_mismatch" for f in built["findings"])
    assert built["assessment"]["status"] == "blocking_concerns"


# -- the schema --------------------------------------------------------------


def test_schema_has_no_field_a_pooled_instrument_number_could_occupy(
    ctx: Context, report: Mapping[str, Any]
) -> None:
    """The refusal is structural, not a convention a later edit can drift past."""
    schema = json.loads(
        (REPO_ROOT / "schemas" / validity.SCHEMA_ID).read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False
    forbidden = ("pool", "overall", "combined", "aggregate", "average", "mean", "headline")
    names = set(schema["properties"]) | {
        key for definition in schema["$defs"].values() for key in definition.get("properties", {})
    }
    offenders = sorted(
        name
        for name in names
        if any(word in name for word in forbidden) and name != "pooled_refusal"
    )
    assert offenders == []
    # Two instruments, and no third slot a summary row could be appended into.
    assert schema["properties"]["instruments"]["maxItems"] == 2
    assert schema["properties"]["assessment"]["properties"]["pooled_refusal"]["minLength"] == 1

    polluted = dict(report)
    polluted["overall_instrument_accuracy"] = 0.5
    with pytest.raises(Exception) as raised:
        ctx.schemas.validate(polluted, validity.SCHEMA_ID)
    assert "overall_instrument_accuracy" in str(raised.value)


def test_report_validates_and_seals(ctx: Context, report: Mapping[str, Any]) -> None:
    from ats.canonical import verify_seal

    ctx.schemas.validate(report, validity.SCHEMA_ID)
    ok, declared, recomputed = verify_seal(dict(report))
    assert ok, f"{declared} != {recomputed}"


# -- narrative ---------------------------------------------------------------


def test_narrative_renders_every_figure_from_the_report(report: Mapping[str, Any]) -> None:
    """Rendered, not written: the numbers in the prose are the numbers in the JSON."""
    rendered = validity.render_report_markdown(report)
    assert report["report_sha256"] in rendered
    assert "0.600 (3/5)" in rendered  # instrument a applicability precision
    assert "UNAVAILABLE (`confidence_bin_empty`)" in rendered
    assert report["assessment"]["pooled_refusal"] in rendered
    # The blocks a reader needs to size a figure, not just the figure itself.
    assert "n = 3; unit of analysis:" in rendered
    assert (
        "3 in-scope unit(s) carried operator offsets: 2 from the disagreement review "
        "and 1 from the source-only pass alone." in rendered
    )
    assert "`operator_cited_nothing` | 2 |" in rendered
    assert "true positive 1, false positive 0, false negative 0, true negative 4" in rendered
    assert "Macro token F1 (unweighted mean over scored units): 0.500." in rendered
    assert "1 in-scope unit(s) were declined and carry no confidence." in rendered
    assert rendered.endswith("\n")


def test_narrative_is_a_pure_function_of_the_report(report: Mapping[str, Any]) -> None:
    assert validity.render_report_markdown(report) == validity.render_report_markdown(report)


# -- the tool ----------------------------------------------------------------




# -- exposure ----------------------------------------------------------------


def test_exposure_joins_on_the_log_not_the_row_field(ctx: Context, tmp_path: Path) -> None:
    """A gold row recorded before its breach was logged carries no
    prior_exposure field. The log is the authority; a scorer trusting the row
    would score exactly that unit as clean."""
    paths = _write_inputs(tmp_path)
    # u1's gold rows carry NO prior_exposure field; only the log names it.
    (tmp_path / "exposure_log.json").write_text(
        json.dumps(
            {
                "schema_version": "x-ats-repo.adjudication_exposure.v0",
                "exposures": [
                    {
                        "unit_id": _unit("u1"),
                        "code": "instrument_verdict_summaries_shown",
                        "detail": "fixture breach",
                        "occurred_at": "2026-08-03T00:00:00Z",
                    },
                    {
                        "unit_id": "not-in-this-queue",
                        "code": "instrument_verdict_summaries_shown",
                        "detail": "another report's unit",
                        "occurred_at": "2026-08-03T00:00:00Z",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    report = validity.build_validity_report(
        ctx,
        queue=paths["queue"],
        gold=paths["gold"],
        round_a=paths["round_a"],
        round_b=paths["round_b"],
        agreement_report=paths["agreement"],
    )
    exposure = report["exposure"]
    assert exposure["log_available"] is True
    assert [e["unit_id"] for e in exposure["exposed_units"]] == [_unit("u1")]
    assert exposure["exposed_in_scored_set"] == 1
    finding = next(f for f in report["findings"] if f["code"] == "exposed_units_in_scored_set")
    assert finding["severity"] == "concern"
    assert _unit("u1")[:44] in finding["detail"]


def test_an_absent_log_reports_itself_rather_than_clean(
    ctx: Context, report: Mapping[str, Any]
) -> None:
    """No log beside the gold file: the block says so, and says what that
    absence does and does not establish."""
    exposure = report["exposure"]
    assert exposure["log_available"] is False
    assert exposure["exposed_units"] == []
    assert exposure["exposed_in_scored_set"] == 0
    assert "session discipline" in exposure["note"]
    assert not any(f["code"] == "exposed_units_in_scored_set" for f in report["findings"])

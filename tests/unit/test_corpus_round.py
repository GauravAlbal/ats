"""Annotation rounds over a caller-supplied frame.

Defends spec Section 17.7 (leakage grouping), Section 17.9 (the two-judgment
floor), and the structural rules that a round never mutates the frame it drew
from and adjudication cannot begin before every pass is frozen.

The properties here are the ones whose failure would be invisible in the
output. A round that quietly re-flagged the frame, a blind item that leaked the
sampling mechanism, or an adjudication opened over one finished pass all
produce plausible-looking numbers that mean something other than they claim.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import pytest

from ats.context import Context
from ats.corpus import round as rd
from ats.errors import UsageError

NOW = dt.datetime(2026, 8, 3, tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


def selection(index: int, stratum: str, *, group: str | None = None, rules=("ATS-NUM-001",)):
    return {
        "bundle_id": f"ats-bundle-sha256:{index:064d}",
        "source_artifact_id": f"ats-artifact-sha256:{index:064d}",
        "repository": "synthetic-repo",
        "stratum": stratum,
        "candidate_rule_ids": list(rules),
        "split_group": group or f"group-{index:032d}",
    }


def frame_with(rows) -> dict[str, Any]:
    return {
        "frame_id": "ats-frame-sha256:" + "a" * 64,
        "record_sha256": "b" * 64,
        "selection": list(rows),
    }


def annotators():
    return [
        rd.Annotator("llm-annotator-a", "llm", model="m1", prompt_id="p"),
        rd.Annotator("llm-annotator-b", "llm", model="m2", prompt_id="p"),
    ]


# -- selection ---------------------------------------------------------------


def test_a_round_takes_at_most_one_bundle_per_leakage_component() -> None:
    """Two views of the same material are not two independent judgments."""
    rows = [selection(i, "natural_rule_candidate", group="shared") for i in range(10)]
    chosen, report = rd.select_round(frame_with(rows), seed=1, targets=(("natural_rule_candidate", 5),))
    assert len(chosen) == 1
    assert report[0]["selected"] == 1
    assert "leakage component already represented" in report[0]["shortfall_reason"]


def test_a_stratum_shortfall_is_reported_not_borrowed() -> None:
    """The strata are different sampling mechanisms, not interchangeable quota."""
    rows = [selection(i, "natural_rule_candidate") for i in range(3)]
    rows += [selection(100 + i, "low_signal_random_control") for i in range(20)]
    _chosen, report = rd.select_round(
        frame_with(rows),
        seed=1,
        targets=(("natural_rule_candidate", 10), ("low_signal_random_control", 5)),
    )
    natural = next(r for r in report if r["stratum"] == "natural_rule_candidate")
    control = next(r for r in report if r["stratum"] == "low_signal_random_control")
    assert natural["selected"] == 3 and natural["target"] == 10
    assert natural["shortfall_reason"]
    # The control stratum keeps its own target; it does not absorb the gap.
    assert control["selected"] == 5


def test_selection_is_deterministic_in_the_seed() -> None:
    rows = [selection(i, "natural_rule_candidate") for i in range(40)]
    targets = (("natural_rule_candidate", 10),)
    first, _ = rd.select_round(frame_with(rows), seed=7, targets=targets)
    again, _ = rd.select_round(frame_with(rows), seed=7, targets=targets)
    other, _ = rd.select_round(frame_with(rows), seed=8, targets=targets)
    assert [r["bundle_id"] for r in first] == [r["bundle_id"] for r in again]
    assert [r["bundle_id"] for r in first] != [r["bundle_id"] for r in other]


def test_a_bundle_with_no_candidate_rule_is_still_judged_against_something() -> None:
    """A control has no candidate rule and still needs a stated question."""
    rows = [selection(1, "low_signal_random_control", rules=())]
    chosen, _ = rd.select_round(frame_with(rows), seed=1, targets=(("low_signal_random_control", 1),))
    assert chosen[0]["rule_ids"] == [rd.FALLBACK_RULE]


# -- the round record --------------------------------------------------------


def test_a_round_binds_the_frame_it_drew_from(ctx: Context) -> None:
    """An agreement figure is only meaningful against the exact set measured."""
    rows = [selection(i, "natural_rule_candidate") for i in range(5)]
    record = rd.build_round(
        ctx, frame_with(rows), annotators(), seed=1, targets=(("natural_rule_candidate", 3),)
    )
    assert record["frame"]["record_sha256"] == "b" * 64
    assert record["frame"]["selection_count"] == 5
    assert ctx.schemas.validate_document(record) == rd.SCHEMA_ID


def test_a_round_declares_that_it_supersedes_the_frame_flag(ctx: Context) -> None:
    """Two answers to 'which bundles get two judgments' must not both look live."""
    rows = [selection(i, "natural_rule_candidate") for i in range(5)]
    record = rd.build_round(
        ctx, frame_with(rows), annotators(), seed=1, targets=(("natural_rule_candidate", 3),)
    )
    assert record["frame"]["supersedes_frame_flag"] is True


def test_a_frame_without_a_content_address_is_refused(ctx: Context) -> None:
    frame = frame_with([selection(1, "natural_rule_candidate")])
    del frame["record_sha256"]
    with pytest.raises(UsageError, match="record_sha256"):
        rd.build_round(ctx, frame, annotators(), seed=1)


def test_one_annotator_is_not_an_agreement_measurement(ctx: Context) -> None:
    rows = [selection(1, "natural_rule_candidate")]
    with pytest.raises(UsageError, match="two annotators"):
        rd.build_round(ctx, frame_with(rows), annotators()[:1], seed=1)


def test_the_round_never_writes_back_to_the_frame(ctx: Context) -> None:
    """The frame is content-addressed; a round that edited it would break its own binding."""
    rows = [selection(i, "natural_rule_candidate") for i in range(5)]
    frame = frame_with(rows)
    before = json.dumps(frame, sort_keys=True)
    rd.build_round(ctx, frame, annotators(), seed=1, targets=(("natural_rule_candidate", 3),))
    assert json.dumps(frame, sort_keys=True) == before


# -- blinding ----------------------------------------------------------------


def test_a_blind_item_carries_no_field_that_says_why_it_was_sampled() -> None:
    """Telling an annotator a span is a 'hard negative' hands over the answer."""
    row = {
        "bundle_id": "b1",
        "rule_ids": ["ATS-NUM-001"],
        "stratum": "surface_cue_hard_negative",
        "candidate_source": "hard_negative_configuration:HN-1",
        "split_group": "group-1",
        "near_duplicate_cluster": "nd-1",
        "template_family": "t-1",
    }
    bundle = {"span_text": "some words", "heading_path": ["A"], "context_completeness": "complete"}
    item = rd.blind_item(row, bundle, "ATS-NUM-001")
    assert not set(rd.WITHHELD_UNTIL_SUBMISSION).intersection(item)
    serialised = json.dumps(item)
    for leak in ("surface_cue_hard_negative", "hard_negative_configuration", "nd-1", "t-1"):
        assert leak not in serialised


def test_a_rule_outside_the_round_cannot_be_asked_of_a_bundle() -> None:
    row = {"bundle_id": "b1", "rule_ids": ["ATS-NUM-001"], "split_group": "g"}
    with pytest.raises(UsageError, match="not a rule this round judges"):
        rd.blind_item(row, {"span_text": "x"}, "ATS-EPI-001")


def test_a_missing_bundle_refuses_rather_than_judging_a_bare_span(ctx: Context) -> None:
    """Spec 17.4: an isolated sentence should not be labelled when context was discarded."""
    rows = [selection(1, "natural_rule_candidate")]
    record = rd.build_round(
        ctx, frame_with(rows), annotators(), seed=1, targets=(("natural_rule_candidate", 1),)
    )
    with pytest.raises(UsageError, match="without its context"):
        list(rd.iter_items(record, {}))


# -- freezing and the adjudication gate --------------------------------------


def test_adjudication_is_refused_until_every_pass_is_frozen(ctx: Context) -> None:
    """Adjudicating early lets one disagreement steer the judgments after it."""
    rows = [selection(i, "natural_rule_candidate") for i in range(3)]
    record = rd.build_round(
        ctx, frame_with(rows), annotators(), seed=1, targets=(("natural_rule_candidate", 2),)
    )
    ready, why = rd.adjudication_ready(record)
    assert not ready
    assert "not frozen" in why


def test_a_frozen_pass_is_bound_to_the_exact_bytes_of_its_judgments(tmp_path) -> None:
    path = tmp_path / "round-a.jsonl"
    path.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")
    frozen = rd.freeze_pass("llm-annotator-a", path)
    assert frozen["state"] == "frozen"
    assert frozen["judgment_count"] == 2
    path.write_text('{"a": 1}\n{"a": 3}\n', encoding="utf-8")
    assert rd.freeze_pass("llm-annotator-a", path)["judgments_sha256"] != frozen["judgments_sha256"]


def test_a_missing_pass_is_unavailable_not_empty(tmp_path) -> None:
    """Zero judgments and no judgment file are different states."""
    frozen = rd.freeze_pass("llm-annotator-a", tmp_path / "absent.jsonl")
    assert frozen["state"] == "unavailable"
    assert "no judgments" in frozen["detail"]


def test_passes_of_different_length_block_adjudication(ctx: Context) -> None:
    """A missing judgment is not a disagreement and must not be counted as one."""
    rows = [selection(i, "natural_rule_candidate") for i in range(3)]
    record = dict(
        rd.build_round(
            ctx, frame_with(rows), annotators(), seed=1, targets=(("natural_rule_candidate", 2),)
        )
    )
    record["passes"] = [
        {"annotator_id": "llm-annotator-a", "state": "frozen", "judgment_count": 2},
        {"annotator_id": "llm-annotator-b", "state": "frozen", "judgment_count": 1},
    ]
    ready, why = rd.adjudication_ready(record)
    assert not ready
    assert "not a disagreement" in why


def test_two_frozen_equal_passes_open_adjudication(ctx: Context) -> None:
    rows = [selection(i, "natural_rule_candidate") for i in range(3)]
    record = dict(
        rd.build_round(
            ctx, frame_with(rows), annotators(), seed=1, targets=(("natural_rule_candidate", 2),)
        )
    )
    record["passes"] = [
        {"annotator_id": "llm-annotator-a", "state": "frozen", "judgment_count": 2},
        {"annotator_id": "llm-annotator-b", "state": "frozen", "judgment_count": 2},
    ]
    ready, why = rd.adjudication_ready(record)
    assert ready
    assert "2 pass(es) frozen" in why

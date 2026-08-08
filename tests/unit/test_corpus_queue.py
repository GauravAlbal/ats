"""Queue selection over a caller-supplied sampling frame.

The queue decides what an annotator's time is spent on, so these tests defend
against silent narrowing: a scope category that stops matching, a control
sample that stops being drawn, prose leaking into the committed record, or an
instrument conclusion leaking into the source-only surface.

"""
from __future__ import annotations

import datetime as _dt
import json

import pytest

from ats.canonical import content_hash
from ats.context import Context
from ats.corpus import gold
from ats.errors import UsageError

NOW = _dt.datetime(2026, 8, 3, tzinfo=_dt.UTC)

B = "ats-bundle-sha256:"


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


def _bundle_id(i: int) -> str:
    return f"{B}{i:064x}"


def _judged(bundle: str, rule: str, label: str, *, suff: str = "partial") -> dict[str, Any]:
    return {
        "example_id": bundle,
        "rule_id": rule,
        "label": label,
        "annotation_confidence": "moderate",
        "extensions": {
            "x-ats-repo-applicability": "applicable",
            "x-ats-repo-context-sufficiency": suff,
        },
    }


def _declined(bundle: str, rule: str, kind: str = "not_applicable") -> dict[str, Any]:
    return {"example_id": bundle, "rule_id": rule, "applicability": kind}


def _units(
    judgments: dict[str, list[dict[str, Any]]], declines: dict[str, list[dict[str, Any]]]
) -> dict[tuple[str, str], dict[str, dict[str, Any]]]:
    return gold._unit_states(judgments, declines)


def _round(selection: list[dict[str, Any]]) -> dict[str, Any]:
    return {"selection": selection}


def _pick(bundle: str, rule: str, stratum: str = "natural_rule_candidate") -> dict[str, Any]:
    return {
        "bundle_id": bundle,
        "rule_ids": [rule],
        "stratum": stratum,
        "split_group": f"group-{bundle[-4:]}",
        "repository": "arq",
        "source_artifact_id": "ats-artifact-sha256:" + "b" * 64,
    }


def test_every_unit_one_pass_judged_is_in_scope() -> None:
    """The 32 one-declined units were the round's largest disagreement; a
    judgments-only scope would drop exactly them."""
    b1, b2 = _bundle_id(1), _bundle_id(2)
    units = _units(
        {"a": [_judged(b1, "ATS-EPI-001", "violation")], "b": []},
        {
            "a": [_declined(b2, "ATS-EPI-001")],
            "b": [_declined(b1, "ATS-EPI-001"), _declined(b2, "ATS-EPI-001")],
        },
    )
    scope, _, _ = gold.select_scope(
        _round([_pick(b1, "ATS-EPI-001"), _pick(b2, "ATS-EPI-001")]),
        units,
        {"classifications": []},
        seed=1,
        control_target=0,
    )
    assert "applicable_by_at_least_one_pass" in scope[(b1, "ATS-EPI-001")]
    assert (b2, "ATS-EPI-001") not in scope


def test_every_probe_unit_is_observation_evidence() -> None:
    """The both-declined probes are the naturally_rare evidence; exempting them
    from adjudication would exempt the strongest claim from audit."""
    b1 = _bundle_id(3)
    units = _units(
        {"a": [], "b": []},
        {"a": [_declined(b1, "ATS-TIME-001")], "b": [_declined(b1, "ATS-TIME-001")]},
    )
    scope, _, _ = gold.select_scope(
        _round([_pick(b1, "ATS-TIME-001", "zero_candidate_rule_probe")]),
        units,
        {"classifications": []},
        seed=1,
    )
    assert "cited_as_observation_evidence" in scope[(b1, "ATS-TIME-001")]


def test_probe_decline_kind_disagreement_is_flagged() -> None:
    """not_applicable versus undetermined is a scope disagreement even when
    neither pass judged."""
    b1 = _bundle_id(4)
    units = _units(
        {"a": [], "b": []},
        {
            "a": [_declined(b1, "ATS-NUM-002", "not_applicable")],
            "b": [_declined(b1, "ATS-NUM-002", "undetermined")],
        },
    )
    scope, _, _ = gold.select_scope(
        _round([_pick(b1, "ATS-NUM-002", "zero_candidate_rule_probe")]),
        units,
        {"classifications": []},
        seed=1,
    )
    assert "probe_applicability_disagreement" in scope[(b1, "ATS-NUM-002")]


def test_sufficiency_disagreement_is_flagged() -> None:
    b1 = _bundle_id(5)
    units = _units(
        {
            "a": [_judged(b1, "ATS-EPI-001", "conforming", suff="partial")],
            "b": [_judged(b1, "ATS-EPI-001", "conforming", suff="insufficient")],
        },
        {"a": [], "b": []},
    )
    scope, _, _ = gold.select_scope(
        _round([_pick(b1, "ATS-EPI-001")]), units, {"classifications": []}, seed=1
    )
    assert "context_sufficiency_disagreement" in scope[(b1, "ATS-EPI-001")]


def test_control_sample_is_deterministic_and_bounded() -> None:
    picks, declines_a, declines_b = [], [], []
    for i in range(30):
        bundle = _bundle_id(100 + i)
        picks.append(_pick(bundle, "ATS-EPI-001"))
        declines_a.append(_declined(bundle, "ATS-EPI-001"))
        declines_b.append(_declined(bundle, "ATS-EPI-001"))
    units = _units({"a": [], "b": []}, {"a": declines_a, "b": declines_b})
    first, _, _ = gold.select_scope(
        _round(picks), units, {"classifications": []}, seed=7, control_target=5
    )
    second, _, _ = gold.select_scope(
        _round(picks), units, {"classifications": []}, seed=7, control_target=5
    )
    assert first == second, "the control draw must be a pure function of the seed"
    assert sum(1 for r in first.values() if "control_apparent_agreement" in r) == 5
    third, _, _ = gold.select_scope(
        _round(picks), units, {"classifications": []}, seed=8, control_target=5
    )
    assert set(third) != set(first), "a different seed draws a different control sample"


def test_label_agreed_pairs_are_always_controls() -> None:
    """Two passes agreeing on a label is the agreement the milestone says not
    to trust; every such pair is audited, not sampled."""
    b1 = _bundle_id(6)
    units = _units(
        {
            "a": [_judged(b1, "ATS-EPI-001", "conforming")],
            "b": [_judged(b1, "ATS-EPI-001", "conforming")],
        },
        {"a": [], "b": []},
    )
    scope, _, _ = gold.select_scope(
        _round([_pick(b1, "ATS-EPI-001")]),
        units,
        {"classifications": []},
        seed=1,
        control_target=0,
    )
    assert "control_apparent_agreement" in scope[(b1, "ATS-EPI-001")]


def test_recon_disagreements_and_agreed_specify_sample() -> None:
    classifications = []
    for i in range(12):
        bundle = _bundle_id(200 + i)
        b_label = "SPECIFY" if i < 10 else "ASSESS"
        classifications.append(
            {"bundle_id": bundle, "annotator_id": "llm-recon-a", "classification": "SPECIFY"}
        )
        classifications.append(
            {"bundle_id": bundle, "annotator_id": "llm-recon-b", "classification": b_label}
        )
    _, disagreed, controls = gold.select_scope(
        _round([]), {}, {"classifications": classifications}, seed=1
    )
    assert len(disagreed) == 2
    assert len(controls) == 8
    assert not set(disagreed) & set(controls)


def test_a_pass_that_both_judged_and_declined_is_refused() -> None:
    b1 = _bundle_id(7)
    with pytest.raises(UsageError, match="both judged and declined"):
        _units(
            {"a": [_judged(b1, "ATS-EPI-001", "violation")], "b": []},
            {"a": [_declined(b1, "ATS-EPI-001")], "b": []},
        )



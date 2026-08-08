"""Corpus statistics, with synthetic and natural evidence kept apart.

Defends spec Section 17.5 (synthetic examples MUST NOT be counted as
independent real-world evidence), Section 12.9 and Section 16.4 (what a rule
corpus MUST contain), Section 17.6 (hard negatives), and Section 17.9 (gold
eligibility).
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from ats.context import Context
from ats.corpus import records as rec
from ats.corpus import stats
from ats.errors import UsageError

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


@pytest.fixture(scope="module")
def report(ctx: Context):
    return stats.corpus_stats(ctx, "fixtures/corpus")


def test_fixture_requirements_come_from_the_registry(ctx: Context, report) -> None:
    """Spec 16.4: the required fixture classes are the rule record's, not this module's."""
    assert set(report["by_rule"]) == set(ctx.registry.ids())
    for rule_id, value in report["by_rule"].items():
        rule = ctx.registry.get(rule_id)
        assert value["fixture_requirements"] == list(rule.fixture_requirements)
        assert set(value["requirement_coverage"]) == set(rule.fixture_requirements)
        assert value["rule_version"] == rule.rule_version


def test_natural_and_synthetic_counts_are_never_summed(report) -> None:
    """Spec 17.5: a synthetic mutation is not evidence of real-world prevalence."""
    counts = report["synthetic_vs_natural"]
    assert set(counts) == {"natural", "synthetic", "note"}
    assert "MUST NOT" not in counts["note"] or "17.5" in counts["note"]
    assert counts["natural"] > 0 and counts["synthetic"] > 0
    # No key anywhere reports a mixed total.
    serialized = json.dumps(report)
    assert '"total"' not in serialized
    for value in report["by_rule"].values():
        assert set(value["examples"]) == {"natural", "synthetic"}
    for value in report["by_label"].values():
        assert set(value) == {"natural", "synthetic"}


def test_a_requirement_met_only_by_mutations_is_reported_as_such(report) -> None:
    """Spec 12.9: a rule is not promoted on synthetic violations alone."""
    statuses = {
        requirement["status"]
        for value in report["by_rule"].values()
        for requirement in value["requirement_coverage"].values()
    }
    assert statuses <= {"PASS", "SYNTHETIC_ONLY", "MISSING", "UNAVAILABLE"}
    assert "SYNTHETIC_ONLY" in statuses
    synthetic_only = [
        rule_id
        for rule_id, value in report["by_rule"].items()
        if value["examples"]["synthetic"] and not value["examples"]["natural"]
    ]
    assert synthetic_only
    for rule_id in synthetic_only:
        coverage = report["by_rule"][rule_id]["requirement_coverage"]
        assert any(v["status"] == "SYNTHETIC_ONLY" for v in coverage.values())


def test_hard_negative_coverage_is_reported_per_rule(ctx: Context, report) -> None:
    """Spec 17.6: every semantic rule corpus MUST include hard negatives."""
    coverage = report["hard_negative_coverage"]
    assert set(coverage) == set(ctx.registry.ids())
    for rule_id, value in coverage.items():
        rule = ctx.registry.get(rule_id)
        assert value["required"] == ("hard_negative" in rule.fixture_requirements)
        assert value["status"] in {"PASS", "SYNTHETIC_ONLY", "MISSING", "NOT_APPLICABLE"}
        assert set(value) >= {"natural", "synthetic"}


def test_the_curated_seeds_supply_the_missing_labels(ctx: Context) -> None:
    """The seed set exists to cover labels mining cannot produce."""
    seeds = stats.corpus_stats(ctx, "corpus/seeds")
    labels = set(seeds["by_label"])
    assert {"hard_negative", "exception", "ambiguous", "insufficient_context"} <= labels
    assert seeds["synthetic_vs_natural"]["synthetic"] == 0
    hard_negatives = seeds["hard_negative_coverage"]["ATS-DEON-002"]
    assert hard_negatives["status"] == "PASS"
    assert hard_negatives["natural"] >= 1


def test_agreement_rates_are_reported(report) -> None:
    """Spec 17.9: retained disagreement is countable."""
    agreement = report["agreement"]
    assert agreement["judgments"] > 0
    assert agreement["adjudications"] > 0
    assert sum(agreement["by_agreement"].values()) == agreement["adjudications"]
    assert 0.0 <= agreement["unanimous_rate"] <= 1.0
    assert agreement["example_rule_pairs_with_two_independent_judgments"] > 0
    assert set(agreement["by_disagreement_category"]) <= {
        "none",
        "annotation_error",
        "source_ambiguity",
        "insufficient_context",
        "profile_disagreement",
        "policy_disagreement",
        "rule_boundary_disagreement",
        "standard_defect",
        "multiple_valid_interpretations",
        "true_annotator_disagreement",
    }


def test_an_unadjudicated_corpus_reports_no_agreement_rate(ctx: Context, tmp_path) -> None:
    """A rate over zero cases would report agreement nobody measured."""
    example = rec.text_example(
        text="The verifier MUST reject a stale receipt.",
        profile="SPECIFY",
        rule_id="ATS-DEON-001",
        label="conforming",
        rationale="Canonical surface.",
        protected_impact=["P0"],
        provenance="human_authored_fixture",
        synthetic=False,
        split_group="unit",
    )
    rec.append_records(ctx, tmp_path / "examples.jsonl", [example])
    report = stats.corpus_stats(ctx, tmp_path)
    assert report["agreement"]["unanimous_rate"] is None
    assert report["gold_eligible"]["eligible"] == 0


def test_gold_eligibility_is_counted_by_final_state(report) -> None:
    """Spec 17.9: needs_rule_revision and needs_more_context are never gold-eligible."""
    gold = report["gold_eligible"]
    assert gold["eligible"] > 0
    assert gold["not_eligible"] > 0
    assert gold["eligible"] + gold["not_eligible"] == report["records"]["adjudications"]
    assert "needs_rule_revision" in gold["blocked_by_final_state"]
    assert "needs_more_context" in gold["blocked_by_final_state"]
    assert "gold" not in gold["blocked_by_final_state"]
    assert len(gold["eligible_examples"]) == len(set(gold["eligible_examples"]))


def test_rules_with_no_examples_are_named(ctx: Context, report) -> None:
    """A gap nobody names is a gap nobody fills."""
    named = set(report["rules_with_no_examples"])
    assert named
    for rule_id in named:
        assert report["by_rule"][rule_id]["examples"] == {"natural": 0, "synthetic": 0}
    covered = {
        rule_id
        for rule_id, value in report["by_rule"].items()
        if value["examples"]["natural"] or value["examples"]["synthetic"]
    }
    assert named & covered == set()


def test_coverage_gaps_and_promotion_blockers(ctx: Context, report) -> None:
    """Spec 18.5: report the blockers, not a score that can hide one."""
    gaps = stats.coverage_gaps(report)
    assert gaps
    assert all(gap["missing"] or gap["synthetic_only"] for gap in gaps)

    blockers = stats.promotion_blockers(ctx, report)
    assert blockers
    kinds = {b["blocker"] for b in blockers}
    assert kinds <= {"no_natural_examples", "hard_negative_coverage", "no_gold_data"}
    assert "no_natural_examples" in kinds
    for blocker in blockers:
        assert blocker["detail"]


def test_an_empty_path_is_refused(ctx: Context, tmp_path) -> None:
    with pytest.raises(UsageError):
        stats.corpus_stats(ctx, tmp_path / "nothing-here")

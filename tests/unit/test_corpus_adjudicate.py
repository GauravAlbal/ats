"""Adjudication: retained disagreement, nine categories, eight final states.

Defends spec Section 17.9: disagreement MUST be retained and categorized, and a
forced majority label MUST NOT erase a genuine ambiguity in the standard or
source. Also defends the schema's own invariant that ``needs_rule_revision`` and
``needs_more_context`` are never gold-eligible.
"""

from __future__ import annotations

import datetime as dt

import pytest

from ats.context import Context
from ats.corpus import adjudicate
from ats.corpus import records as rec
from ats.errors import UsageError

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)

#: The nine disagreement categories the schema defines, beyond ``none``.
DISAGREEMENT_CATEGORIES = {
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

#: The eight final states.
FINAL_STATES = {
    "gold",
    "gold_with_context_constraint",
    "hard_negative",
    "exception",
    "ambiguous_by_design",
    "needs_more_context",
    "needs_rule_revision",
    "excluded",
}


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


def _judgment(ctx: Context, annotator: str, label: str, **overrides) -> dict:
    fields = {
        "example_id": "ats-example-sha256:" + "e" * 64,
        "annotator_id": annotator,
        "rule_id": "ATS-DEON-001",
        "rule_version": ctx.registry.get("ATS-DEON-001").rule_version,
        "profile": "SPECIFY",
        "label": label,
        "rationale": f"{annotator} says {label} under the normative statement.",
        "evidence_spans": [{"kind": "character", "start": 0, "end": 4}]
        if label == "violation"
        else [],
        "protected_impact": ["P0"],
        "annotation_confidence": "moderate",
        "requested_additional_context": [],
        "ambiguity_category": "none",
        "blind": True,
        "timestamp": "2026-02-01T00:00:00Z",
        "tool_version": ctx.implementation["version"],
    }
    fields.update(overrides)
    judgment = rec.judgment(**fields)
    ctx.schemas.validate_document(judgment)
    return judgment


def test_the_schema_defines_nine_categories_and_eight_states(ctx: Context) -> None:
    """The vocabulary this module maps onto is the schema's, not an invented one."""
    schema = ctx.schemas.schema("ats_corpus_adjudication_v1.schema.json")
    categories = set(schema["properties"]["disagreement_category"]["enum"])
    assert categories == DISAGREEMENT_CATEGORIES | {"none"}
    assert set(schema["properties"]["final_state"]["enum"]) == FINAL_STATES


def test_unanimity_is_gold(ctx: Context) -> None:
    judgments = [
        _judgment(ctx, "human:a", "conforming"),
        _judgment(ctx, "human:b", "conforming"),
    ]
    result = adjudicate.adjudicate_group(ctx, judgments, "human:adjudicator")
    assert result["agreement"] == "unanimous"
    assert result["disagreement_category"] == "none"
    assert result["final_state"] == "gold"
    assert result["gold_eligible"] is True


def test_every_original_judgment_is_retained_verbatim(ctx: Context) -> None:
    """Spec 17.9: disagreement MUST be retained, which means the records, not a summary."""
    judgments = [
        _judgment(ctx, "human:a", "violation"),
        _judgment(ctx, "human:b", "near_miss"),
    ]
    result = adjudicate.adjudicate_group(ctx, judgments, "human:adjudicator")
    assert result["judgments"] == judgments
    assert result["judgment_ids"] == [rec.record_id(j) for j in judgments]
    assert len(result["judgments"]) == 2


def test_a_standard_ambiguity_forces_rule_revision_and_blocks_gold(ctx: Context) -> None:
    """Spec 17.9: resolving under an unclear rule would erase the finding."""
    judgments = [
        _judgment(ctx, "human:a", "violation"),
        _judgment(
            ctx,
            "human:b",
            "ambiguous",
            ambiguity_category="standard_ambiguity",
            rationale="The rule text does not distinguish this case at all.",
        ),
    ]
    result = adjudicate.adjudicate_group(ctx, judgments, "human:adjudicator")
    assert result["disagreement_category"] == "standard_defect"
    assert result["final_state"] == "needs_rule_revision"
    assert result["gold_eligible"] is False
    assert result["required_rule_amendment"]
    assert result["standard_ambiguity_discovered"]


def test_insufficient_context_blocks_gold(ctx: Context) -> None:
    """Nobody could have decided from what they were shown."""
    judgments = [
        _judgment(ctx, "human:a", "violation"),
        _judgment(
            ctx,
            "human:b",
            "insufficient_context",
            requested_additional_context=["the acceptance criterion"],
        ),
    ]
    result = adjudicate.adjudicate_group(ctx, judgments, "human:adjudicator")
    assert result["disagreement_category"] == "insufficient_context"
    assert result["final_state"] == "needs_more_context"
    assert result["gold_eligible"] is False


def test_a_majority_is_not_forced_over_a_genuine_split(ctx: Context) -> None:
    """Spec 17.9: a forced majority label MUST NOT erase a genuine ambiguity."""
    judgments = [
        _judgment(ctx, "human:a", "violation"),
        _judgment(ctx, "human:b", "violation"),
        _judgment(ctx, "human:c", "conforming"),
    ]
    result = adjudicate.adjudicate_group(ctx, judgments, "human:adjudicator")
    assert result["agreement"] == "majority"
    assert result["disagreement_category"] == "true_annotator_disagreement"
    assert result["final_state"] == "ambiguous_by_design"
    assert result["gold_eligible"] is False
    assert "forcing a majority" in result["rationale"] or "vote" in result["rationale"]


def test_a_majority_becomes_gold_only_on_a_named_annotation_error(ctx: Context) -> None:
    """Calling a colleague wrong is an adjudicator's decision, with a name attached."""
    judgments = [
        _judgment(ctx, "human:a", "violation"),
        _judgment(ctx, "human:b", "violation"),
        _judgment(ctx, "human:c", "conforming"),
    ]
    result = adjudicate.adjudicate_group(
        ctx,
        judgments,
        "human:adjudicator",
        annotation_error="human:c read the requirement's trigger as its condition.",
    )
    assert result["disagreement_category"] == "annotation_error"
    assert result["final_state"] == "gold"
    assert result["gold_eligible"] is True
    assert result["annotation_error"]


def test_a_unanimous_ambiguous_label_is_the_finding(ctx: Context) -> None:
    """When everyone agrees the source is ambiguous, that agreement is gold data."""
    judgments = [
        _judgment(ctx, "human:a", "ambiguous", ambiguity_category="source_ambiguity"),
        _judgment(ctx, "human:b", "ambiguous", ambiguity_category="source_ambiguity"),
    ]
    result = adjudicate.adjudicate_group(ctx, judgments, "human:adjudicator")
    assert result["final_state"] == "ambiguous_by_design"
    assert result["gold_eligible"] is True


def test_an_outstanding_context_request_constrains_the_gold_label(ctx: Context) -> None:
    judgments = [
        _judgment(
            ctx,
            "human:a",
            "conforming",
            requested_additional_context=["the section's declared profile"],
        ),
        _judgment(ctx, "human:b", "conforming"),
    ]
    result = adjudicate.adjudicate_group(ctx, judgments, "human:adjudicator")
    assert result["final_state"] == "gold_with_context_constraint"
    assert "declared profile" in result["context_constraint"]
    assert result["gold_eligible"] is True


def test_a_unanimous_hard_negative_is_recorded_as_one(ctx: Context) -> None:
    """Spec 17.6: hard negatives are a corpus category in their own right."""
    judgments = [
        _judgment(ctx, "human:a", "hard_negative"),
        _judgment(ctx, "human:b", "hard_negative"),
    ]
    result = adjudicate.adjudicate_group(ctx, judgments, "human:adjudicator")
    assert result["final_state"] == "hard_negative"
    assert result["gold_eligible"] is True


def test_source_ambiguity_stays_ambiguous(ctx: Context) -> None:
    judgments = [
        _judgment(ctx, "human:a", "violation"),
        _judgment(ctx, "human:b", "ambiguous", ambiguity_category="source_ambiguity"),
    ]
    result = adjudicate.adjudicate_group(ctx, judgments, "human:adjudicator")
    assert result["disagreement_category"] == "source_ambiguity"
    assert result["final_state"] == "ambiguous_by_design"
    assert result["source_ambiguity_discovered"]


def test_profile_and_policy_disagreements_are_distinguished(ctx: Context) -> None:
    """Two annotators reading different profiles is not the same as reading the rule badly."""
    profile = adjudicate.adjudicate_group(
        ctx,
        [
            _judgment(ctx, "human:a", "violation"),
            _judgment(ctx, "human:b", "ambiguous", ambiguity_category="profile_ambiguity"),
        ],
        "human:adjudicator",
    )
    assert profile["disagreement_category"] == "profile_disagreement"

    policy = adjudicate.adjudicate_group(
        ctx,
        [
            _judgment(ctx, "human:a", "violation"),
            _judgment(ctx, "human:b", "ambiguous", ambiguity_category="policy_ambiguity"),
        ],
        "human:adjudicator",
    )
    assert policy["disagreement_category"] == "policy_disagreement"
    assert policy["policy_mismatch"]


def test_every_derived_category_is_in_the_schema_vocabulary(ctx: Context) -> None:
    """The mapping from judgment ambiguity to disagreement uses only declared values."""
    assert set(adjudicate.AMBIGUITY_TO_DISAGREEMENT.values()) <= DISAGREEMENT_CATEGORIES
    assert set(adjudicate.UNANIMOUS_STATES.values()) <= FINAL_STATES
    assert adjudicate.GOLD_ELIGIBLE_STATES | adjudicate.NEVER_GOLD_STATES <= FINAL_STATES
    assert not adjudicate.GOLD_ELIGIBLE_STATES & adjudicate.NEVER_GOLD_STATES


def test_two_judgments_from_one_annotator_are_refused(ctx: Context) -> None:
    """Spec 17.9 requires independence, and one person answering twice is one opinion."""
    judgments = [
        _judgment(ctx, "human:a", "conforming"),
        _judgment(ctx, "human:a", "violation"),
    ]
    with pytest.raises(UsageError, match="independent judgments"):
        adjudicate.adjudicate_group(ctx, judgments, "human:adjudicator")


def test_a_single_judgment_is_deferred_not_adjudicated(ctx: Context) -> None:
    """A group that cannot be adjudicated is reported, never resolved by one voice."""
    adjudications, deferred = adjudicate.adjudicate_judgments(
        ctx, [_judgment(ctx, "human:a", "conforming")], "human:adjudicator"
    )
    assert adjudications == []
    assert deferred[0]["reason"] == "insufficient_independent_judgments"


def test_judgments_about_different_examples_are_not_merged(ctx: Context) -> None:
    judgments = [
        _judgment(ctx, "human:a", "conforming"),
        _judgment(ctx, "human:b", "conforming", example_id="ats-example-sha256:" + "f" * 64),
    ]
    with pytest.raises(UsageError, match="one example under one rule"):
        adjudicate.adjudicate_group(ctx, judgments, "human:adjudicator")


def test_adjudicate_file_reads_the_shipped_fixture(ctx: Context) -> None:
    """The generated judgment fixture re-adjudicates to the same outcomes."""
    results = adjudicate.adjudicate_file(
        ctx, "fixtures/corpus/judgments.jsonl", "human:adjudicator"
    )
    assert results
    states = {r["final_state"] for r in results}
    assert "gold" in states
    assert "needs_rule_revision" in states
    assert "needs_more_context" in states
    for result in results:
        ctx.schemas.validate_document(result)
        if result["final_state"] in adjudicate.NEVER_GOLD_STATES:
            assert result["gold_eligible"] is False


def test_agreement_classification(ctx: Context) -> None:
    assert adjudicate.agreement_of(["a", "a"]) == "unanimous"
    assert adjudicate.agreement_of(["a", "a", "b"]) == "majority"
    assert adjudicate.agreement_of(["a", "b"]) == "split"
    assert adjudicate.agreement_of(["a", "b", "c"]) == "split"
    # Two against two is not a majority.
    assert adjudicate.agreement_of(["a", "a", "b", "b"]) == "split"

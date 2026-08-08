"""Blind annotation queues and the two-independent-judgment floor.

Defends spec Section 17.9 (at least two independent adjudications before gold),
Section 17.4 (an isolated sentence SHOULD NOT be labeled), Section 13.3 (a
finding points at the smallest sufficient spans), and Section 12.10 (a rule is
explained, and therefore judged, one at a time).
"""

from __future__ import annotations

import datetime as dt

import pytest

from ats.context import Context
from ats.corpus import annotate
from ats.corpus import records as rec
from ats.errors import UsageError

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


def _bundle(ctx: Context, completeness: str = "complete") -> dict:
    bundle = rec.context_bundle(
        source_artifact_id="ats-artifact-sha256:" + "a" * 64,
        source_revision="0" * 40,
        source_span={"kind": "character", "start": 0, "end": 41},
        span_text="The verifier MUST reject a stale receipt.",
        containing_block={
            "kind": "paragraph",
            "text": "The verifier MUST reject a stale receipt.",
            "span": {"kind": "character", "start": 0, "end": 41},
        },
        heading_path=["Requirements", "SPECIFY: stale policy"],
        preceding_context={"availability": "not_found", "locator": "first block"},
        following_context={"availability": "present", "text": "Acceptance criteria"},
        local_definitions=[],
        glossary_entries=[],
        profile_hypothesis={"profile": "SPECIFY", "basis": "heading_path"},
        policy_context={"availability": "present", "policy_sha256": "b" * 64},
        diff={"availability": "present", "text": "@@ -0,0 +1 @@"},
        review_comment={"availability": "not_found"},
        later_edit={"availability": "not_found"},
        context_completeness=completeness,
    )
    ctx.schemas.validate_document(bundle)
    return bundle


def _example(ctx: Context, *, rule_id: str = "ATS-DEON-001", **overrides) -> dict:
    fields = {
        "text": "The verifier MUST reject a stale receipt.",
        "profile": "SPECIFY",
        "rule_id": rule_id,
        "label": "conforming",
        "rationale": "Canonical MUST surface with a named actor.",
        "protected_impact": ["P0"],
        "provenance": "human_authored_fixture",
        "synthetic": False,
        "split_group": "unit-test",
    }
    fields.update(overrides)
    example = rec.text_example(**fields)
    ctx.schemas.validate_document(example)
    return example


def test_one_item_is_one_rule_judgment(ctx: Context) -> None:
    """Spec 12.10: a rule is explained, and judged, on its own."""
    example = _example(ctx)
    queue = annotate.build_queue(
        ctx, [example], "human:a", bundles={example["example_id"]: _bundle(ctx)}
    )
    assert len(queue["items"]) == 1
    item = queue["items"][0]
    assert item["rule_id"] == "ATS-DEON-001"
    assert isinstance(item["rule_id"], str)
    assert item["normative_statement"] == ctx.registry.get("ATS-DEON-001").normative_statement


def test_the_queue_is_blind(ctx: Context) -> None:
    """Spec 17.9: independence requires the annotator not to see another's label."""
    example = _example(ctx)
    bundle = _bundle(ctx)
    first = annotate.submit_judgment(
        ctx,
        item=annotate.build_queue(
            ctx, [example], "human:a", bundles={example["example_id"]: bundle}
        )["items"][0],
        annotator_id="human:a",
        label="violation",
        rationale="A distinctive rationale nobody else should see: heliotrope kernel.",
        evidence_spans=[{"kind": "character", "start": 0, "end": 4}],
    )
    queue = annotate.build_queue(
        ctx,
        [example],
        "human:b",
        bundles={example["example_id"]: bundle},
        existing_judgments=[first],
    )
    assert queue["blind"] is True
    serialized = repr(queue["items"])
    assert "heliotrope kernel" not in serialized
    assert first["judgment_id"] not in serialized
    assert "violation" not in serialized.split("allowed_labels")[0]
    # Only the count is exposed, and a count reveals no direction.
    assert queue["items"][0]["independent_judgments_so_far"] == 1


def test_an_annotator_is_not_asked_twice(ctx: Context) -> None:
    """A second answer from the same person is not a second independent judgment."""
    example = _example(ctx)
    bundle = _bundle(ctx)
    item = annotate.build_queue(
        ctx, [example], "human:a", bundles={example["example_id"]: bundle}
    )["items"][0]
    judgment = annotate.submit_judgment(
        ctx,
        item=item,
        annotator_id="human:a",
        label="conforming",
        rationale="The canonical surface is present.",
    )
    queue = annotate.build_queue(
        ctx,
        [example],
        "human:a",
        bundles={example["example_id"]: bundle},
        existing_judgments=[judgment],
    )
    assert queue["items"] == []
    assert queue["withheld"][0]["reason"] == "already_judged"


def test_a_missing_bundle_withholds_the_item(ctx: Context) -> None:
    """Spec 17.4: an isolated span is not adjudicable."""
    example = _example(ctx)
    queue = annotate.build_queue(ctx, [example], "human:a", bundles={})
    assert queue["items"] == []
    assert queue["withheld"][0]["reason"] == "no_context_bundle"


def test_an_insufficient_bundle_withholds_the_item(ctx: Context) -> None:
    """A truncated bundle announces itself and is not queued."""
    example = _example(ctx)
    queue = annotate.build_queue(
        ctx,
        [example],
        "human:a",
        bundles={example["example_id"]: _bundle(ctx, "insufficient")},
    )
    assert queue["items"] == []
    assert queue["withheld"][0]["reason"] == "context_incomplete"


def test_a_partial_bundle_can_be_required_to_be_complete(ctx: Context) -> None:
    """The completeness floor is explicit, and the queue records which floor applied."""
    example = _example(ctx)
    bundles = {example["example_id"]: _bundle(ctx, "partial")}
    assert annotate.build_queue(ctx, [example], "human:a", bundles=bundles)["items"]
    strict = annotate.build_queue(
        ctx, [example], "human:a", bundles=bundles, minimum_completeness="complete"
    )
    assert strict["items"] == []
    assert strict["minimum_completeness"] == "complete"


def test_a_violation_judgment_needs_an_evidence_span(ctx: Context) -> None:
    """Spec 13.3: a finding points at the spans that establish why the rule may apply."""
    example = _example(ctx)
    item = annotate.build_queue(
        ctx, [example], "human:a", bundles={example["example_id"]: _bundle(ctx)}
    )["items"][0]
    with pytest.raises(UsageError, match="at least one exact evidence span"):
        annotate.submit_judgment(
            ctx, item=item, annotator_id="human:a", label="violation", rationale="Because."
        )


def test_a_judgment_needs_a_rationale(ctx: Context) -> None:
    """Spec 17.9: a judgment is tied to the normative rule text, not to a preference."""
    example = _example(ctx)
    item = annotate.build_queue(
        ctx, [example], "human:a", bundles={example["example_id"]: _bundle(ctx)}
    )["items"][0]
    with pytest.raises(UsageError, match="MUST carry a rationale"):
        annotate.submit_judgment(
            ctx, item=item, annotator_id="human:a", label="conforming", rationale="   "
        )


def test_insufficient_context_must_name_what_is_missing(ctx: Context) -> None:
    example = _example(ctx)
    item = annotate.build_queue(
        ctx, [example], "human:a", bundles={example["example_id"]: _bundle(ctx)}
    )["items"][0]
    with pytest.raises(UsageError, match="MUST name the context it is missing"):
        annotate.submit_judgment(
            ctx,
            item=item,
            annotator_id="human:a",
            label="insufficient_context",
            rationale="Cannot tell.",
        )


def test_an_ambiguous_judgment_must_categorise_the_ambiguity(ctx: Context) -> None:
    example = _example(ctx)
    item = annotate.build_queue(
        ctx, [example], "human:a", bundles={example["example_id"]: _bundle(ctx)}
    )["items"][0]
    with pytest.raises(UsageError, match="MUST categorise the ambiguity"):
        annotate.submit_judgment(
            ctx,
            item=item,
            annotator_id="human:a",
            label="ambiguous",
            rationale="Two readings.",
            ambiguity_category="none",
        )


def test_a_material_semantic_example_needs_two_independent_judgments(ctx: Context) -> None:
    """Spec 17.9: two independent adjudications before gold."""
    example = _example(ctx)
    assert annotate.is_material_semantic(ctx, example)
    bundle = _bundle(ctx)
    item = annotate.build_queue(
        ctx, [example], "human:a", bundles={example["example_id"]: bundle}
    )["items"][0]
    first = annotate.submit_judgment(
        ctx, item=item, annotator_id="human:a", label="conforming", rationale="Canonical surface."
    )
    gate = annotate.gold_gate(ctx, example, [first])
    assert gate["eligible"] is False
    assert gate["required_independent_judgments"] == 2

    second = annotate.submit_judgment(
        ctx, item=item, annotator_id="human:b", label="conforming", rationale="Agreed."
    )
    passing = annotate.gold_gate(ctx, example, [first, second])
    assert passing["eligible"] is True
    assert passing["annotators"] == ["human:a", "human:b"]


def test_one_annotator_answering_twice_is_one_opinion(ctx: Context) -> None:
    """The floor counts distinct annotator identities, not judgment records."""
    example = _example(ctx)
    bundle = _bundle(ctx)
    item = annotate.build_queue(
        ctx, [example], "human:a", bundles={example["example_id"]: bundle}
    )["items"][0]
    first = annotate.submit_judgment(
        ctx, item=item, annotator_id="human:a", label="conforming", rationale="Once."
    )
    again = annotate.submit_judgment(
        ctx, item=item, annotator_id="human:a", label="conforming", rationale="Twice."
    )
    gate = annotate.gold_gate(ctx, example, [first, again])
    assert gate["independent_judgments"] == 1
    assert gate["eligible"] is False


def test_the_semantic_floor_follows_the_rule_registry(ctx: Context) -> None:
    """Spec 12.3: D2, D3, and D4 are the semantic detector classes."""
    assert annotate.SEMANTIC_DETECTOR_CLASSES == {"D2", "D3", "D4"}
    semantic = _example(ctx, rule_id="ATS-DISC-002", protected_impact=["P2"])
    assert "D3" in ctx.registry.get("ATS-DISC-002").detector_classes
    assert annotate.is_material_semantic(ctx, semantic)


def test_a_judgment_validates_and_declares_its_blindness(ctx: Context) -> None:
    example = _example(ctx)
    item = annotate.build_queue(
        ctx, [example], "human:a", bundles={example["example_id"]: _bundle(ctx)}
    )["items"][0]
    judgment = annotate.submit_judgment(
        ctx,
        item=item,
        annotator_id="human:a",
        label="conforming",
        rationale="The canonical surface is present and the actor is named.",
        protected_impact=["P0"],
    )
    assert ctx.schemas.validate_document(judgment) == "ats_judgment_v1.schema.json"
    assert judgment["blind"] is True
    assert judgment["context_bundle_id"].startswith("ats-bundle-sha256:")
    assert judgment["normative_statement_quoted"]


def test_an_unnamed_annotator_is_refused(ctx: Context) -> None:
    with pytest.raises(UsageError, match="must name its annotator"):
        annotate.build_queue(ctx, [], "  ")

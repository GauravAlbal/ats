"""Blind annotation queues and judgment construction.

Spec Section 17.9: material semantic examples SHOULD receive at least two
independent adjudications before becoming gold data, and disagreement MUST be
retained rather than resolved by a forced majority. Independence is only real if
the second annotator cannot see the first one's answer, so this module builds
queue items from the example and its context bundle alone. A label, rationale,
or judgment identifier belonging to another annotator never enters an item, and
:func:`build_queue` verifies that before returning.

One item is one rule judgment. Section 12.10 makes a rule explainable in
isolation, and asking an annotator to decide several rules at once produces a
label that cannot be attributed to any of them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

from ..canonical import sha256_hex
from ..errors import UsageError
from . import records as rec

#: Detector classes that make a rule *semantic* rather than mechanical
#: (spec Section 12.3: D2 retrieves candidates, D3 is a rule-conditioned
#: semantic critic, D4 verifies cross-text preservation).
SEMANTIC_DETECTOR_CLASSES: Final[frozenset[str]] = frozenset({"D2", "D3", "D4"})

#: Labels an annotator may choose, from ``ats_judgment_v1.schema.json``.
LABELS: Final[tuple[str, ...]] = (
    "conforming",
    "violation",
    "near_miss",
    "hard_negative",
    "exception",
    "ambiguous",
    "insufficient_context",
)

#: Ambiguity categories, from the same schema.
AMBIGUITY_CATEGORIES: Final[tuple[str, ...]] = (
    "none",
    "source_ambiguity",
    "standard_ambiguity",
    "profile_ambiguity",
    "policy_ambiguity",
    "rule_boundary",
    "multiple_valid_interpretations",
)

#: Completeness ratings, weakest first.
COMPLETENESS_ORDER: Final[tuple[str, ...]] = ("insufficient", "partial", "complete")


def is_material_semantic(ctx: Any, example: Mapping[str, Any]) -> bool:
    """Whether spec Section 17.9's two-judgment floor applies to this example.

    An example is material and semantic when its rule is served by a semantic
    detector class, or when the example claims protected impact on P0 or P1. A
    purely mechanical P2 example — a missing inline range, say — is decidable by
    one competent annotator; a judgment about causal force is not.
    """
    rule = ctx.registry.get(example["rule_id"])
    if SEMANTIC_DETECTOR_CLASSES.intersection(rule.detector_classes):
        return True
    return bool({"P0", "P1"}.intersection(example.get("protected_impact", ())))


def _completeness_ok(bundle: Mapping[str, Any], minimum: str) -> bool:
    rating = bundle.get("context_completeness", "insufficient")
    if rating not in COMPLETENESS_ORDER:
        return False
    return COMPLETENESS_ORDER.index(rating) >= COMPLETENESS_ORDER.index(minimum)


def _bundle_index(
    bundles: Mapping[str, Mapping[str, Any]] | str | Path | None,
) -> dict[str, Mapping[str, Any]]:
    """Resolve the ``bundles`` argument to ``identifier -> bundle``.

    A JSONL path is indexed by both bundle identifier and source artifact, so a
    caller can key an example either way.
    """
    if bundles is None:
        return {}
    if isinstance(bundles, (str, Path)):
        index: dict[str, Mapping[str, Any]] = {}
        for record in rec.read_records(bundles):
            if record.get("schema_version") != "ats.context_bundle.v1":
                continue
            index[record["bundle_id"]] = record
        return index
    return dict(bundles)


def build_queue(
    ctx: Any,
    examples: Sequence[Mapping[str, Any]],
    annotator_id: str,
    *,
    bundles: Mapping[str, Mapping[str, Any]] | str | Path | None = None,
    existing_judgments: Iterable[Mapping[str, Any]] = (),
    minimum_completeness: str = "partial",
) -> dict[str, Any]:
    """Build a blind annotation queue for one annotator.

    Returns ``{"annotator_id", "items", "blind", "withheld"}``. Each item names
    exactly one rule, carries the example's context bundle, and states what the
    judgment must contain. An example whose bundle is missing or rated
    ``insufficient`` is withheld with a reason rather than queued: spec Section
    17.4 says an isolated sentence SHOULD NOT be labeled when the rule depends
    on context that was discarded.

    ``bundles`` maps an example identifier (or a bundle identifier) to its
    context bundle, or names a JSONL file holding ``ats.context_bundle.v1``
    records, which a caller that already stored them can pass directly.

    ``existing_judgments`` is used only to skip work this annotator has already
    submitted and to report how many independent judgments an example already
    has. No other annotator's label reaches an item.
    """
    if minimum_completeness not in COMPLETENESS_ORDER:
        raise UsageError(
            f"minimum_completeness must be one of {COMPLETENESS_ORDER}, got "
            f"{minimum_completeness!r}"
        )
    if not annotator_id.strip():
        raise UsageError("an annotation queue must name its annotator")

    bundle_index = _bundle_index(bundles)
    prior = list(existing_judgments)
    mine = {
        (j["example_id"], j["rule_id"]) for j in prior if j["annotator_id"] == annotator_id
    }
    counts: dict[tuple[str, str], set[str]] = {}
    for judgment in prior:
        counts.setdefault((judgment["example_id"], judgment["rule_id"]), set()).add(
            judgment["annotator_id"]
        )

    items: list[dict[str, Any]] = []
    withheld: list[dict[str, Any]] = []
    for example in examples:
        example_id = example["example_id"]
        rule_id = example["rule_id"]
        if (example_id, rule_id) in mine:
            withheld.append(
                {
                    "example_id": example_id,
                    "rule_id": rule_id,
                    "reason": "already_judged",
                    "detail": f"{annotator_id} has already submitted a judgment for this pair",
                }
            )
            continue

        bundle_id = (example.get("extensions") or {}).get(rec.EXT_CONTEXT_BUNDLE_ID)
        bundle = bundle_index.get(example_id) or (
            bundle_index.get(bundle_id) if bundle_id else None
        )
        if bundle is None:
            withheld.append(
                {
                    "example_id": example_id,
                    "rule_id": rule_id,
                    "reason": "no_context_bundle",
                    "detail": "no context bundle was supplied; an isolated span is not "
                    "adjudicable (spec 17.4)",
                }
            )
            continue
        if not _completeness_ok(bundle, minimum_completeness):
            withheld.append(
                {
                    "example_id": example_id,
                    "rule_id": rule_id,
                    "reason": "context_incomplete",
                    "detail": f"context_completeness is "
                    f"{bundle.get('context_completeness')!r}, below the required "
                    f"{minimum_completeness!r}",
                }
            )
            continue

        rule = ctx.registry.get(rule_id)
        independent = sorted(counts.get((example_id, rule_id), set()))
        items.append(
            {
                "item_id": "ats-queue-sha256:"
                + sha256_hex(f"{annotator_id}|{example_id}|{rule_id}".encode("utf-8")),
                "example_id": example_id,
                "rule_id": rule_id,
                "rule_version": rule.rule_version,
                "profile": example["profile"],
                "text": example["text"],
                "normative_statement": rule.normative_statement,
                "rule_title": rule.title,
                "protected_impact": list(rule.protected_impact),
                "context_bundle": dict(bundle),
                "context_completeness": bundle.get("context_completeness"),
                "allowed_labels": list(LABELS),
                "allowed_ambiguity_categories": list(AMBIGUITY_CATEGORIES),
                "requires": {
                    "rationale": "tied to the normative rule text, not to style preference",
                    "evidence_spans": "at least one exact span when the label is violation",
                    "requested_additional_context": "at least one entry when the label is "
                    "insufficient_context",
                },
                "material_semantic": is_material_semantic(ctx, example),
                "independent_judgments_so_far": len(independent),
            }
        )

    blind = _verify_blind(items, prior)
    return {
        "annotator_id": annotator_id,
        "items": items,
        "blind": blind,
        "withheld": withheld,
        "minimum_completeness": minimum_completeness,
    }


def _verify_blind(items: Sequence[Mapping[str, Any]], prior: Sequence[Mapping[str, Any]]) -> bool:
    """Check that no prior judgment's content leaked into the queue.

    A boolean nobody computes is a boolean nobody can trust, so this really
    searches the serialized queue for each prior judgment's identifier and
    rationale. Only the count of independent judgments is exposed, and that
    reveals nothing about which way they went.
    """
    if not items:
        return True
    serialized = json.dumps(items, sort_keys=True)
    for judgment in prior:
        for leak in (judgment.get("judgment_id"), judgment.get("rationale")):
            if leak and leak in serialized:
                raise UsageError(
                    f"annotation queue exposes judgment content ({leak[:48]!r}); an "
                    "independent judgment requires the annotator not to see another "
                    "annotator's label before submission (spec 17.9)"
                )
        for item in items:
            if "label" in item:
                raise UsageError("annotation queue item carries a label field")
    return True


def submit_judgment(
    ctx: Any,
    *,
    item: Mapping[str, Any],
    annotator_id: str,
    label: str,
    rationale: str,
    evidence_spans: Sequence[Mapping[str, Any]] = (),
    protected_impact: Sequence[str] = (),
    annotation_confidence: str = "moderate",
    requested_additional_context: Sequence[str] = (),
    ambiguity_category: str = "none",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Turn a queue item plus an annotator's answer into a ``JudgmentV1``.

    The completeness, evidence-span, and rationale obligations are checked here
    with named errors before the schema sees the record, so an annotator learns
    what is missing rather than reading a JSON Pointer.
    """
    bundle = item.get("context_bundle")
    if not bundle:
        raise UsageError("a judgment requires the item's complete context bundle (spec 17.4)")
    if label not in LABELS:
        raise UsageError(f"{label!r} is not an ATS corpus label; choose one of {LABELS}")
    if not rationale.strip():
        raise UsageError(
            "a judgment MUST carry a rationale tied to the normative rule text (spec 17.9)"
        )
    if label == "violation" and not evidence_spans:
        raise UsageError(
            "a violation judgment MUST cite at least one exact evidence span (spec 13.3)"
        )
    if label == "insufficient_context" and not requested_additional_context:
        raise UsageError(
            "an insufficient_context judgment MUST name the context it is missing"
        )
    if label == "ambiguous" and ambiguity_category == "none":
        raise UsageError("an ambiguous judgment MUST categorise the ambiguity (spec 17.9)")

    judgment = rec.judgment(
        example_id=item["example_id"],
        context_bundle_id=bundle["bundle_id"],
        annotator_id=annotator_id,
        rule_id=item["rule_id"],
        rule_version=item["rule_version"],
        profile=item["profile"],
        label=label,
        rationale=rationale,
        normative_statement_quoted=item.get("normative_statement"),
        evidence_spans=[dict(s) for s in evidence_spans],
        protected_impact=list(protected_impact),
        annotation_confidence=annotation_confidence,
        requested_additional_context=list(requested_additional_context),
        ambiguity_category=ambiguity_category,
        blind=True,
        timestamp=timestamp or ctx.timestamp(),
        tool_version=ctx.implementation["version"],
    )
    ctx.schemas.validate_document(judgment)
    return judgment


def gold_gate(
    ctx: Any, example: Mapping[str, Any], judgments: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Whether an example has enough independent judgments to become gold.

    Spec Section 17.9 sets the floor at two independent adjudications for a
    material semantic example. Two judgments from the same annotator are one
    opinion recorded twice, so the count is over distinct annotator identities.
    """
    relevant = [
        j
        for j in judgments
        if j["example_id"] == example["example_id"] and j["rule_id"] == example["rule_id"]
    ]
    annotators = sorted({j["annotator_id"] for j in relevant})
    material_semantic = is_material_semantic(ctx, example)
    required = 2 if material_semantic else 1
    eligible = len(annotators) >= required
    return {
        "example_id": example["example_id"],
        "rule_id": example["rule_id"],
        "material_semantic": material_semantic,
        "independent_judgments": len(annotators),
        "annotators": annotators,
        "required_independent_judgments": required,
        "eligible": eligible,
        "reason": (
            f"{len(annotators)} independent judgment(s) against a floor of {required}"
            + (
                " for a material semantic example (spec 17.9)"
                if material_semantic
                else " for a mechanical P2 example"
            )
        ),
    }

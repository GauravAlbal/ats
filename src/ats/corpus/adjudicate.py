"""Resolve independent judgments into a corpus adjudication.

Spec Section 17.9: disagreement MUST be retained and categorized, and a forced
majority label MUST NOT erase a genuine ambiguity in the standard or source.
This module therefore:

* keeps every original judgment verbatim inside the adjudication record, not a
  summary of them;
* categorises disagreement into one of the nine categories the schema defines,
  derived from what the annotators actually said rather than from a vote;
* refuses to turn a genuine split into gold. A majority becomes gold only when
  the adjudicator explicitly records the minority as an annotation error, which
  is a decision with a name attached, not an automatic rounding.

``needs_rule_revision`` and ``needs_more_context`` are never gold-eligible: the
first means the rule as written cannot decide the case, and the second means
nobody could have decided it from what they were shown.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

from ..errors import UsageError
from . import records as rec

#: Judgment-level ambiguity category -> adjudication-level disagreement
#: category. The two enums differ: a judgment describes what one annotator saw,
#: an adjudication describes why the set disagreed.
AMBIGUITY_TO_DISAGREEMENT: Final[dict[str, str]] = {
    "source_ambiguity": "source_ambiguity",
    "standard_ambiguity": "standard_defect",
    "profile_ambiguity": "profile_disagreement",
    "policy_ambiguity": "policy_disagreement",
    "rule_boundary": "rule_boundary_disagreement",
    "multiple_valid_interpretations": "multiple_valid_interpretations",
}

#: Final states that may carry gold data.
GOLD_ELIGIBLE_STATES: Final[frozenset[str]] = frozenset(
    {"gold", "gold_with_context_constraint", "hard_negative", "exception"}
)

#: Final states the schema forbids from being gold-eligible.
NEVER_GOLD_STATES: Final[frozenset[str]] = frozenset(
    {"needs_rule_revision", "needs_more_context", "excluded"}
)

#: Unanimous label -> final state, for labels that are their own verdict.
UNANIMOUS_STATES: Final[dict[str, str]] = {
    "hard_negative": "hard_negative",
    "exception": "exception",
    "ambiguous": "ambiguous_by_design",
    "insufficient_context": "needs_more_context",
}


def agreement_of(labels: Sequence[str]) -> str:
    """``unanimous``, ``majority``, or ``split`` over a set of labels."""
    if len(set(labels)) == 1:
        return "unanimous"
    counts = Counter(labels)
    top, count = counts.most_common(1)[0]
    tied = [label for label, n in counts.items() if n == count]
    if len(tied) == 1 and count * 2 > len(labels):
        return "majority"
    return "split"


def disagreement_of(
    judgments: Sequence[Mapping[str, Any]], agreement: str, *, declared: str | None = None
) -> str:
    """Why the annotators disagreed, derived from what they recorded.

    ``annotation_error`` is never derived: calling one annotator wrong is an
    adjudicator's decision, so it only appears when ``declared`` says so.
    """
    if declared:
        return declared
    if agreement == "unanimous":
        return "none"
    labels = [j["label"] for j in judgments]
    if "insufficient_context" in labels:
        return "insufficient_context"
    categories = [
        AMBIGUITY_TO_DISAGREEMENT[j["ambiguity_category"]]
        for j in judgments
        if j["ambiguity_category"] in AMBIGUITY_TO_DISAGREEMENT
    ]
    if categories:
        # A standard defect outranks every other explanation: if one annotator
        # says the rule itself is unclear, resolving the case under the current
        # rule would bury the finding the corpus exists to surface.
        if "standard_defect" in categories:
            return "standard_defect"
        counts = Counter(categories)
        top, count = counts.most_common(1)[0]
        if len([c for c, n in counts.items() if n == count]) == 1:
            return top
        return "multiple_valid_interpretations"
    return "true_annotator_disagreement"


def _final_state(
    judgments: Sequence[Mapping[str, Any]], agreement: str, disagreement: str
) -> tuple[str, str]:
    """``(final_state, rationale)`` for a resolved judgment set."""
    labels = [j["label"] for j in judgments]
    requested = sorted(
        {c for j in judgments for c in j.get("requested_additional_context", ())}
    )

    if agreement == "unanimous":
        label = labels[0]
        if label in UNANIMOUS_STATES:
            state = UNANIMOUS_STATES[label]
            return state, (
                f"All {len(judgments)} independent judgments returned {label!r}, so the "
                f"example is recorded as {state}."
            )
        if requested:
            return "gold_with_context_constraint", (
                f"All {len(judgments)} independent judgments returned {label!r}, but at least "
                "one annotator named context they needed, so the example is gold only under "
                "that constraint."
            )
        return "gold", (
            f"All {len(judgments)} independent judgments returned {label!r} with no outstanding "
            "context request."
        )

    if disagreement == "standard_defect":
        return "needs_rule_revision", (
            "An annotator recorded that the standard itself is ambiguous here. Resolving the "
            "case under the current rule wording would erase that finding, which spec Section "
            "17.9 forbids."
        )
    if disagreement == "insufficient_context":
        return "needs_more_context", (
            "At least one annotator could not decide from the context supplied, so the example "
            "is not adjudicable as shown."
        )
    if disagreement == "annotation_error":
        return "gold", (
            "The adjudicator recorded the minority judgment as an annotation error and named "
            "it, so the majority label stands as gold."
        )
    if disagreement in ("source_ambiguity", "multiple_valid_interpretations"):
        return "ambiguous_by_design", (
            f"The judgments diverge because of {disagreement.replace('_', ' ')}. The divergence "
            "is the finding; forcing a majority label would erase a genuine ambiguity in the "
            "source (spec 17.9)."
        )
    return "ambiguous_by_design", (
        f"The judgments diverge ({agreement}, {disagreement}) and no adjudicator decision "
        "explains the minority away. The example is retained as ambiguous rather than resolved "
        "by a vote (spec 17.9)."
    )


def adjudicate_group(
    ctx: Any,
    judgments: Sequence[Mapping[str, Any]],
    adjudicator: str,
    *,
    declared_disagreement: str | None = None,
    annotation_error: str | None = None,
    required_rule_amendment: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Resolve two or more judgments about one example under one rule."""
    if len(judgments) < 2:
        raise UsageError(
            "an adjudication resolves at least two independent judgments (spec 17.9); "
            f"got {len(judgments)}"
        )
    example_ids = {j["example_id"] for j in judgments}
    rule_ids = {j["rule_id"] for j in judgments}
    if len(example_ids) != 1 or len(rule_ids) != 1:
        raise UsageError(
            f"judgments span {sorted(example_ids)} and {sorted(rule_ids)}; an adjudication "
            "resolves one example under one rule"
        )
    annotators = {j["annotator_id"] for j in judgments}
    if len(annotators) < 2:
        raise UsageError(
            f"all {len(judgments)} judgments come from {sorted(annotators)}; spec Section 17.9 "
            "requires independent judgments, and one annotator answering twice is one opinion"
        )

    if annotation_error and not declared_disagreement:
        declared_disagreement = "annotation_error"

    labels = [j["label"] for j in judgments]
    agreement = agreement_of(labels)
    disagreement = disagreement_of(judgments, agreement, declared=declared_disagreement)
    state, rationale = _final_state(judgments, agreement, disagreement)

    if state == "needs_rule_revision" and not required_rule_amendment:
        offending = next(
            (j for j in judgments if j["ambiguity_category"] == "standard_ambiguity"), None
        )
        required_rule_amendment = (
            "The rule wording must distinguish this case before it can be adjudicated. "
            f"Annotator {offending['annotator_id']} recorded: {offending['rationale']}"
            if offending
            else "The rule wording must distinguish this case before it can be adjudicated."
        )

    gold_eligible = state in GOLD_ELIGIBLE_STATES or (
        state == "ambiguous_by_design" and agreement == "unanimous"
    )
    if state in NEVER_GOLD_STATES:
        gold_eligible = False

    context_constraint = None
    if state == "gold_with_context_constraint":
        requested = sorted(
            {c for j in judgments for c in j.get("requested_additional_context", ())}
        )
        context_constraint = (
            "The label holds only when the annotator can see: " + "; ".join(requested)
        )

    standard_ambiguity = next(
        (
            j["rationale"]
            for j in judgments
            if j["ambiguity_category"] == "standard_ambiguity"
        ),
        None,
    )
    source_ambiguity = next(
        (j["rationale"] for j in judgments if j["ambiguity_category"] == "source_ambiguity"),
        None,
    )
    policy_mismatch = next(
        (j["rationale"] for j in judgments if j["ambiguity_category"] == "policy_ambiguity"),
        None,
    )

    adjudication = rec.adjudication(
        example_id=judgments[0]["example_id"],
        rule_id=judgments[0]["rule_id"],
        rule_version=judgments[0]["rule_version"],
        judgments=[dict(j) for j in judgments],
        agreement=agreement,
        disagreement_category=disagreement,
        final_state=state,
        context_constraint=context_constraint,
        adjudicator=adjudicator,
        rationale=(
            f"{rationale} Labels recorded: {', '.join(sorted(labels))}. Every original judgment "
            "is retained verbatim in this record (spec 17.9)."
        ),
        standard_ambiguity_discovered=standard_ambiguity,
        source_ambiguity_discovered=source_ambiguity,
        policy_mismatch=policy_mismatch,
        annotation_error=annotation_error,
        required_rule_amendment=required_rule_amendment if state == "needs_rule_revision" else None,
        gold_eligible=gold_eligible,
        timestamp=timestamp or ctx.timestamp(),
        tool_version=ctx.implementation["version"],
    )
    ctx.schemas.validate_document(adjudication)
    return adjudication


def group_judgments(
    judgments: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Judgments indexed by ``(example_id, rule_id)``, in file order."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for judgment in judgments:
        groups.setdefault((judgment["example_id"], judgment["rule_id"]), []).append(
            dict(judgment)
        )
    return groups


def adjudicate_judgments(
    ctx: Any,
    judgments: Sequence[Mapping[str, Any]],
    adjudicator: str,
    *,
    overrides: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
    timestamp: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve every adjudicable group.

    Returns ``(adjudications, deferred)``. A group with fewer than two
    independent annotators is deferred with a reason rather than adjudicated by
    one voice or silently dropped.
    """
    overrides = dict(overrides or {})
    adjudications: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for key in sorted(group_judgments(judgments)):
        group = group_judgments(judgments)[key]
        annotators = sorted({j["annotator_id"] for j in group})
        if len(annotators) < 2:
            deferred.append(
                {
                    "example_id": key[0],
                    "rule_id": key[1],
                    "reason": "insufficient_independent_judgments",
                    "detail": f"{len(group)} judgment(s) from {annotators}; spec 17.9 requires "
                    "two independent annotators",
                    "judgment_ids": [rec.record_id(j) for j in group],
                }
            )
            continue
        override = overrides.get(key, {})
        adjudications.append(
            adjudicate_group(
                ctx,
                group,
                adjudicator,
                declared_disagreement=override.get("disagreement_category"),
                annotation_error=override.get("annotation_error"),
                required_rule_amendment=override.get("required_rule_amendment"),
                timestamp=timestamp,
            )
        )
    return adjudications, deferred


def adjudicate_file(
    ctx: Any,
    judgments_path: str | Path,
    adjudicator: str,
    *,
    timestamp: str | None = None,
) -> list[dict[str, Any]]:
    """Adjudicate every group in a judgments JSONL file."""
    judgments = [
        record
        for record in rec.read_records(judgments_path)
        if record.get("schema_version") == "ats.judgment.v1"
    ]
    if not judgments:
        raise UsageError(f"{judgments_path} holds no ats.judgment.v1 records")
    for judgment in judgments:
        ctx.schemas.validate_document(judgment)
    adjudications, _deferred = adjudicate_judgments(
        ctx, judgments, adjudicator, timestamp=timestamp
    )
    return adjudications

"""Corpus coverage statistics, with synthetic and natural evidence kept apart.

Spec Section 16.4 requires every required D0 or D1 rule to have fixtures;
Section 12.9 lists what a rule corpus MUST include; Section 17.6 requires hard
negatives per semantic rule; and Section 17.5 says synthetic examples MUST NOT
be counted as independent real-world evidence of rule prevalence or user value.

The last obligation shapes the whole report: every count is reported twice, once
natural and once synthetic, and no field adds them together. A ``total`` that
mixes the two would be exactly the number a promotion decision must not use, so
this module does not compute one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Mapping

from ..errors import UsageError
from . import records as rec

#: The label vocabulary of ``ats_text_example_v1.schema.json``.
LABELS: Final[tuple[str, ...]] = (
    "conforming",
    "violation",
    "near_miss",
    "hard_negative",
    "exception",
    "ambiguous",
    "insufficient_context",
)

#: Adjudication final states, from ``ats_corpus_adjudication_v1.schema.json``.
FINAL_STATES: Final[tuple[str, ...]] = (
    "gold",
    "gold_with_context_constraint",
    "hard_negative",
    "exception",
    "ambiguous_by_design",
    "needs_more_context",
    "needs_rule_revision",
    "excluded",
)

#: Why a mixed count is never reported.
SYNTHETIC_SEPARATION_NOTE: Final[str] = (
    "Natural and synthetic counts are reported separately and never summed. A synthetic "
    "mutation shows that a rule can be violated in a given way; it is not evidence that the "
    "violation occurs in real repositories, and spec Section 17.5 forbids counting it as "
    "independent real-world evidence of rule prevalence or user value."
)


def _empty_counts() -> dict[str, int]:
    return {"natural": 0, "synthetic": 0}


def _bump(counts: dict[str, int], example: Mapping[str, Any]) -> None:
    counts["synthetic" if example.get("synthetic") else "natural"] += 1


def corpus_stats(ctx: Any, path: str | Path) -> dict[str, Any]:
    """Coverage, label distribution, agreement, and gold eligibility under ``path``.

    Reads every ``*.jsonl`` file under ``path`` (or the single file named), sorts
    the records by ``schema_version``, and reports:

    ``by_rule``
        Per rule, the ``fixture_requirements`` the registry declares and whether
        each is met, counted natural and synthetic separately.
    ``by_label``
        The label distribution, again split by provenance.
    ``synthetic_vs_natural``
        The two totals, with the reason they stay apart.
    ``hard_negative_coverage``
        Per rule, natural and synthetic hard negatives against the requirement.
    ``agreement``
        Judgment and adjudication agreement rates.
    ``gold_eligible``
        Adjudication outcomes by final state and gold eligibility.
    """
    corpus = rec.load_corpus(path)
    examples = corpus.get("ats.text_example.v1", [])
    judgments = corpus.get("ats.judgment.v1", [])
    adjudications = corpus.get("ats.corpus_adjudication.v1", [])
    if not examples and not judgments and not adjudications:
        raise UsageError(f"no corpus records found under {path}")

    by_example = {e["example_id"]: e for e in examples}

    # -- per-rule coverage --------------------------------------------------
    by_rule: dict[str, Any] = {}
    for rule in sorted(ctx.registry, key=lambda r: r.rule_id):
        rule_examples = [e for e in examples if e["rule_id"] == rule.rule_id]
        labels: dict[str, dict[str, int]] = {label: _empty_counts() for label in LABELS}
        for example in rule_examples:
            _bump(labels[example["label"]], example)

        requirements: dict[str, Any] = {}
        for requirement in rule.fixture_requirements:
            counts = labels.get(requirement)
            if counts is None:
                requirements[requirement] = {
                    "status": "UNAVAILABLE",
                    "detail": f"{requirement!r} is not a corpus label; the registry names a "
                    "fixture class this corpus cannot represent",
                }
                continue
            requirements[requirement] = {
                "natural": counts["natural"],
                "synthetic": counts["synthetic"],
                # Spec 12.9: a rule MUST NOT be promoted to required based only
                # on synthetic violations, so a requirement met only by
                # mutations is reported as met synthetically, not as met.
                "status": (
                    "PASS"
                    if counts["natural"]
                    else "SYNTHETIC_ONLY"
                    if counts["synthetic"]
                    else "MISSING"
                ),
            }

        rule_judgments = [j for j in judgments if j["rule_id"] == rule.rule_id]
        rule_adjudications = [a for a in adjudications if a["rule_id"] == rule.rule_id]
        by_rule[rule.rule_id] = {
            "rule_version": rule.rule_version,
            "severity": rule.severity,
            "detector_classes": list(rule.detector_classes),
            "fixture_requirements": list(rule.fixture_requirements),
            "requirement_coverage": requirements,
            "examples": {
                "natural": sum(1 for e in rule_examples if not e.get("synthetic")),
                "synthetic": sum(1 for e in rule_examples if e.get("synthetic")),
            },
            "labels": {k: v for k, v in labels.items() if v["natural"] or v["synthetic"]},
            "judgments": len(rule_judgments),
            "adjudications": len(rule_adjudications),
            "gold_eligible_adjudications": sum(
                1 for a in rule_adjudications if a["gold_eligible"]
            ),
            "unmet_requirements": sorted(
                name
                for name, value in requirements.items()
                if value.get("status") in ("MISSING", "UNAVAILABLE")
            ),
        }

    # -- label distribution -------------------------------------------------
    by_label: dict[str, dict[str, int]] = {label: _empty_counts() for label in LABELS}
    for example in examples:
        _bump(by_label[example["label"]], example)

    # -- hard negatives -----------------------------------------------------
    hard_negative_coverage: dict[str, Any] = {}
    for rule in sorted(ctx.registry, key=lambda r: r.rule_id):
        required = "hard_negative" in rule.fixture_requirements
        counts = by_rule[rule.rule_id]["labels"].get("hard_negative", _empty_counts())
        hard_negative_coverage[rule.rule_id] = {
            "required": required,
            "natural": counts["natural"],
            "synthetic": counts["synthetic"],
            "status": (
                "NOT_APPLICABLE"
                if not required
                else "PASS"
                if counts["natural"]
                else "SYNTHETIC_ONLY"
                if counts["synthetic"]
                else "MISSING"
            ),
        }

    # -- agreement ----------------------------------------------------------
    agreement_counts = {"unanimous": 0, "majority": 0, "split": 0}
    disagreement_counts: dict[str, int] = {}
    for adjudication in adjudications:
        agreement_counts[adjudication["agreement"]] += 1
        category = adjudication["disagreement_category"]
        disagreement_counts[category] = disagreement_counts.get(category, 0) + 1
    adjudicated = len(adjudications)

    annotators_per_example: dict[tuple[str, str], set[str]] = {}
    for judgment in judgments:
        annotators_per_example.setdefault(
            (judgment["example_id"], judgment["rule_id"]), set()
        ).add(judgment["annotator_id"])
    multiply_judged = sum(1 for a in annotators_per_example.values() if len(a) >= 2)

    agreement = {
        "adjudications": adjudicated,
        "by_agreement": agreement_counts,
        "by_disagreement_category": dict(sorted(disagreement_counts.items())),
        "unanimous_rate": (agreement_counts["unanimous"] / adjudicated) if adjudicated else None,
        "judgments": len(judgments),
        "example_rule_pairs_judged": len(annotators_per_example),
        "example_rule_pairs_with_two_independent_judgments": multiply_judged,
        "note": (
            "unanimous_rate is None when nothing has been adjudicated; a rate over zero cases "
            "would report agreement nobody measured."
        ),
    }

    # -- gold eligibility ---------------------------------------------------
    by_final_state = {state: 0 for state in FINAL_STATES}
    eligible = blocked = 0
    blocked_reasons: dict[str, int] = {}
    for adjudication in adjudications:
        by_final_state[adjudication["final_state"]] += 1
        if adjudication["gold_eligible"]:
            eligible += 1
        else:
            blocked += 1
            state = adjudication["final_state"]
            blocked_reasons[state] = blocked_reasons.get(state, 0) + 1

    gold_eligible = {
        "eligible": eligible,
        "not_eligible": blocked,
        "by_final_state": {k: v for k, v in by_final_state.items() if v},
        "blocked_by_final_state": dict(sorted(blocked_reasons.items())),
        "eligible_examples": sorted(
            {a["example_id"] for a in adjudications if a["gold_eligible"]}
        ),
        "note": (
            "needs_rule_revision and needs_more_context are never gold-eligible: the first "
            "means the rule as written cannot decide the case, the second means nobody could "
            "have decided it from what they were shown (spec 17.9)."
        ),
    }

    natural = sum(1 for e in examples if not e.get("synthetic"))
    synthetic = sum(1 for e in examples if e.get("synthetic"))
    return {
        "path": str(path),
        "records": {
            "examples": len(examples),
            "judgments": len(judgments),
            "adjudications": len(adjudications),
        },
        "by_rule": by_rule,
        "by_label": {k: v for k, v in by_label.items() if v["natural"] or v["synthetic"]},
        "synthetic_vs_natural": {
            "natural": natural,
            "synthetic": synthetic,
            "note": SYNTHETIC_SEPARATION_NOTE,
        },
        "hard_negative_coverage": hard_negative_coverage,
        "agreement": agreement,
        "gold_eligible": gold_eligible,
        "rules_with_no_examples": sorted(
            rule_id
            for rule_id, value in by_rule.items()
            if not value["examples"]["natural"] and not value["examples"]["synthetic"]
        ),
        "orphan_judgments": sorted(
            {j["example_id"] for j in judgments if j["example_id"] not in by_example}
        ),
    }


def coverage_gaps(stats: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Rules whose registry-declared fixture requirements are not yet met."""
    gaps: list[dict[str, Any]] = []
    for rule_id, value in sorted(stats["by_rule"].items()):
        synthetic_only = sorted(
            name
            for name, requirement in value["requirement_coverage"].items()
            if requirement.get("status") == "SYNTHETIC_ONLY"
        )
        if value["unmet_requirements"] or synthetic_only:
            gaps.append(
                {
                    "rule_id": rule_id,
                    "missing": value["unmet_requirements"],
                    "synthetic_only": synthetic_only,
                }
            )
    return gaps


def promotion_blockers(ctx: Any, stats: Mapping[str, Any]) -> list[dict[str, str]]:
    """Why each rule cannot be promoted on this corpus alone.

    Spec Sections 12.9 and 18.4: a rule MUST NOT be promoted to required on
    synthetic violations alone, and hard-negative precision must pass. This
    returns the blockers rather than a score, because Section 18.5 forbids an
    aggregate score from compensating for a gap on a material subtype.
    """
    blockers: list[dict[str, str]] = []
    for rule_id, value in sorted(stats["by_rule"].items()):
        if value["examples"]["natural"] == 0:
            blockers.append(
                {
                    "rule_id": rule_id,
                    "blocker": "no_natural_examples",
                    "detail": "the corpus holds no natural example for this rule; spec 12.9 "
                    "forbids promotion on synthetic violations alone",
                }
            )
        hard_negative = stats["hard_negative_coverage"][rule_id]
        if hard_negative["required"] and hard_negative["status"] != "PASS":
            blockers.append(
                {
                    "rule_id": rule_id,
                    "blocker": "hard_negative_coverage",
                    "detail": f"hard-negative coverage is {hard_negative['status']}; spec 17.6 "
                    "requires hard negatives that carry the surface cue without the violation",
                }
            )
        if value["gold_eligible_adjudications"] == 0:
            blockers.append(
                {
                    "rule_id": rule_id,
                    "blocker": "no_gold_data",
                    "detail": "no adjudication for this rule is gold-eligible",
                }
            )
    return blockers

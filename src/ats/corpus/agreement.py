"""Agreement between two independent annotation rounds, reported as a vector.

Spec Section 17.9 requires material semantic examples to receive at least two
independent adjudications and requires disagreement to be retained rather than
resolved by a forced majority. A report that compresses those rounds into one
agreement number hides class prevalence and the mechanism behind disagreement,
so this module computes named metrics with their own denominators, prevalence,
and chance-corrected statistic.

Two rules govern every number here.

*Never pass by absence* (ADR-0002). A metric that could not be computed is
reported unavailable with a code and a detail. It is never 0.0, which would
invent total disagreement, and never 1.0, which would invent perfect agreement.
The degenerate case matters in practice: Cohen's kappa is ``(po - pe) / (1 - pe)``
and ``pe`` reaches exactly 1 whenever both annotators used a single class for
everything, which is the *common* shape of a rare-class row. That row reports
:data:`UNAVAILABLE_REASONS`\\ ``["expected_agreement_is_one"]``, not a kappa.

*A stated value outranks a derived one.* Applicability and context sufficiency
are carried on the judgment's extensions (:data:`EXT_APPLICABILITY`,
:data:`EXT_CONTEXT_SUFFICIENCY`). Where a judgment does not state one, a narrow
label-derived fallback applies and is counted separately in the metric's
``value_sources``, because an inference this tool made is weaker evidence than an
answer the annotator gave. Context sufficiency has no fallback except the
``insufficient_context`` label itself: an annotator who requested no additional
context may simply not have thought to, so an empty
``requested_additional_context`` establishes nothing.

What agreement between two *model* passes measures is stated in the report
itself. It is instrument reproducibility, not human inter-rater reliability, and
:data:`MEASUREMENT_STATEMENTS` refuses to describe an undeclared annotator kind
as human.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

from ..canonical import seal, sha256_hex
from ..errors import UsageError
from . import records as rec
from .annotate import AMBIGUITY_CATEGORIES, COMPLETENESS_ORDER, LABELS

SCHEMA_ID: Final[str] = "ats_agreement_report_v1.schema.json"
SCHEMA_VERSION: Final[str] = "ats.agreement_report.v1"

#: Where a judgment states whether the rule applied to the text at all. Read in
#: preference to the label-derived fallback below.
EXT_APPLICABILITY: Final[str] = f"{rec.EXT_PREFIX}applicability"

#: Where a judgment states how sufficient the supplied context was. Distinct from
#: ``requested_additional_context``, which is a list of asks, not a rating.
EXT_CONTEXT_SUFFICIENCY: Final[str] = f"{rec.EXT_PREFIX}context-sufficiency"

#: Applicability states, from the annotation protocol.
APPLICABILITY_STATES: Final[tuple[str, ...]] = ("applicable", "not_applicable", "undetermined")

#: The record a pass leaves when it declines to judge. AG-19 step 2: a rule the
#: annotator finds inapplicable yields no conformance judgment, so fabricating a
#: label for that unit would invent an opinion nobody held. It is deliberately
#: not an ``ats.judgment.v1``, because it is not a judgment -- but it *is* an
#: applicability answer, and the applicability metric would be wrong without it.
NON_JUDGMENT_SCHEMA_VERSION: Final[str] = "x-ats-repo.non_judgment.v0"

#: Context-sufficiency ratings, weakest first. The same scale the bundles carry
#: in ``context_completeness`` and the annotator rates against, so a rating a
#: judgment states is comparable with the rating the miner recorded. Imported
#: rather than restated: three copies of this tuple already drifted once.
CONTEXT_SUFFICIENCY_STATES: Final[tuple[str, ...]] = COMPLETENESS_ORDER

#: Protected-field classes (spec Sections 11.3.1, 11.3.2).
PROTECTED_CLASSES: Final[tuple[str, ...]] = ("P0", "P1", "P2")

#: Labels that mark a judgment as not deciding the case.
UNDECIDED_LABELS: Final[tuple[str, ...]] = ("ambiguous", "insufficient_context")

#: Fallback applicability for a judgment that did not state one.
#:
#: ``hard_negative`` is the only label that asserts the rule does *not* govern the
#: text: spec Section 17.6 defines it as a case that superficially resembles a
#: trigger and is nonetheless correct. ``ambiguous`` and ``insufficient_context``
#: are not answers about applicability in either direction, so they map to
#: ``undetermined`` and drop out of the applicability comparison rather than being
#: counted as "the rule does not apply".
APPLICABILITY_BY_LABEL: Final[dict[str, str]] = {
    "conforming": "applicable",
    "violation": "applicable",
    "near_miss": "applicable",
    "exception": "applicable",
    "hard_negative": "not_applicable",
    "ambiguous": "undetermined",
    "insufficient_context": "undetermined",
}

#: Declared annotator kinds. ``unknown`` is a distinct state from ``human``.
ANNOTATOR_KINDS: Final[tuple[str, ...]] = ("llm", "human", "unknown")

#: What agreement measures, by the set of annotator kinds that produced it.
MEASUREMENT_STATEMENTS: Final[dict[str, str]] = {
    "instrument_reproducibility": (
        "Both annotators are LLM passes. Every number in this report is instrument "
        "reproducibility -- how repeatably the annotation instrument returns the same "
        "answer on the same unit -- and is NOT human inter-rater reliability. Two model "
        "passes can agree perfectly and be wrong together in the same way, which is a "
        "failure mode no agreement statistic detects; high agreement here licenses "
        "claims about the instrument's stability and licenses no claim about whether "
        "the labels are correct."
    ),
    "human_inter_rater_reliability": (
        "Every annotator is declared human, so these numbers are human inter-rater "
        "reliability over the annotation protocol."
    ),
    "human_model_concordance": (
        "The annotators are of mixed kind (at least one human and at least one model), "
        "so these numbers are human-model concordance. They are neither instrument "
        "reproducibility nor inter-rater reliability and MUST NOT be reported as either."
    ),
    "unknown": (
        "At least one annotator's kind is undeclared, so what these numbers measure is "
        "unknown. An undeclared annotator is NOT assumed to be human: without the "
        "declaration this report cannot say whether the figures are instrument "
        "reproducibility or inter-rater reliability, and the two are different claims."
    ),
}

#: How independence was maintained, and its limit.
INDEPENDENCE_STATEMENT: Final[str] = (
    "Each pass judged from the queue alone, with no access to the other pass's labels, "
    "rationales, or judgment identifiers (spec Section 17.9; enforced by "
    "ats.corpus.annotate.build_queue). Independence of the two passes is not "
    "independence of their errors: passes sharing a model family or a prompt lineage "
    "share their systematic mistakes, and agreement cannot distinguish a correct "
    "convergence from a shared blind spot."
)

#: Why this report has no headline number.
SINGLE_NUMBER_REFUSAL: Final[str] = (
    "No overall agreement score is reported. The metrics disagree with each other by "
    "design: on this corpus the modal judgment is that a rule does not apply, so any "
    "aggregate is dominated by the easy majority class and reads high while the rare "
    "classes that decide whether the data is usable disagree completely. Read the "
    "vector, the per-rule matrices, and the findings; a reader who needs one number "
    "needs a decision, and the decision is in `assessment.status`."
)

#: Closed vocabulary for why a quantity could not be computed.
UNAVAILABLE_REASONS: Final[dict[str, str]] = {
    "round_unavailable": "an annotation round this metric compares was not present",
    "no_paired_units": "no unit was judged by both annotators",
    "no_unit_satisfied_condition": (
        "units exist, but none satisfied the condition this metric is defined over"
    ),
    "value_not_stated": "neither annotator stated the value this metric compares",
    "chance_baseline_undefined": (
        "the measure has no agreed chance baseline, so no chance-corrected form exists"
    ),
    "expected_agreement_is_one": (
        "expected agreement is exactly 1, so the chance-corrected statistic divides by "
        "zero; agreement here carries no information about skill"
    ),
    "no_spans_cited": "neither annotator cited an evidence span on any comparable unit",
    "class_unused_by_both": "neither annotator ever used this class",
    "registry_missing": "the annotator registry file was not present",
    "registry_malformed": "the annotator registry file could not be read as a registry",
    "sidecar_missing": (
        "the applicability sidecar naming the units a pass declined to judge was not "
        "present, so the applicability universe is unestablished"
    ),
    "sidecar_annotator_mismatch": (
        "the applicability sidecar carries records from an annotator other than the one "
        "whose round it accompanies"
    ),
}

#: Below this many paired units, a per-rule row is flagged small-N. Thirty is the
#: conventional floor at which a kappa's confidence interval narrows enough to
#: separate "agrees" from "happens to agree"; the threshold is published rather
#: than applied silently, and a row below it is flagged, never suppressed.
SMALL_N_THRESHOLD: Final[int] = 30

#: Pooled prevalence at or below which a class counts as rare. A rare class is
#: where a corpus-level statistic goes blind, so rare classes get their own
#: prevalence-robust measures and their own findings.
RARE_CLASS_PREVALENCE: Final[Fraction] = Fraction(15, 100)

#: The two roles this report compares. Order is fixed so the confusion matrices
#: read the same way on every run.
ROLES: Final[tuple[str, str]] = ("a", "b")


# -- small numeric helpers ---------------------------------------------------


def _num(value: Fraction | None) -> float | None:
    """A ratio as a JSON number, or ``None``.

    Rounded to six places so the report's bytes are reproducible; the exact value
    stays a :class:`~fractions.Fraction` inside the computation, so no rounding
    ever decides a comparison.
    """
    return None if value is None else round(float(value), 6)


def _rate(numerator: int, denominator: int) -> Fraction | None:
    """``numerator / denominator``, or ``None`` when the denominator is zero.

    A rate over zero observations is not zero. It is a rate nobody measured.
    """
    return None if denominator == 0 else Fraction(numerator, denominator)


def unavailable(code: str, detail: str) -> dict[str, str]:
    """An unavailability record, refusing an unknown code."""
    if code not in UNAVAILABLE_REASONS:
        raise UsageError(
            f"{code!r} is not an agreement-report unavailability code; add it to "
            "UNAVAILABLE_REASONS deliberately rather than inventing a reason at the "
            "call site"
        )
    return {"code": code, "detail": detail}


def _statistic(
    name: str,
    value: Fraction | None,
    *,
    reason: Mapping[str, str] | None = None,
    expected_agreement: Fraction | None = None,
    interpretation: str | None = None,
) -> dict[str, Any]:
    available = value is not None
    if available == (reason is not None):
        raise UsageError(
            f"statistic {name!r} must carry either a value or an unavailability, never both "
            "and never neither"
        )
    out: dict[str, Any] = {
        "statistic": name,
        "available": available,
        "value": _num(value),
        "unavailable_reason": dict(reason) if reason else None,
    }
    if expected_agreement is not None:
        out["expected_agreement"] = _num(expected_agreement)
    if interpretation:
        out["interpretation"] = interpretation
    return out


# -- contingency tables ------------------------------------------------------


def contingency(
    pairs: Sequence[tuple[str, str]], classes: Sequence[str]
) -> list[list[int]]:
    """Dense contingency table, rows indexed by annotator A's class."""
    index = {name: position for position, name in enumerate(classes)}
    table = [[0] * len(classes) for _ in classes]
    for left, right in pairs:
        table[index[left]][index[right]] += 1
    return table


def cohen_kappa(table: Sequence[Sequence[int]]) -> dict[str, Any]:
    """Cohen's kappa over a square contingency table.

    Returns the statistic record, unavailable rather than numeric in the two
    degenerate cases: an empty table, and an expected agreement of exactly 1.
    The second is not an edge case here. It occurs whenever both annotators used
    a single class throughout, which is the ordinary shape of a rare-label
    one-versus-rest table, and the textbook answer -- report 1.0 because they
    agreed -- would claim skill that the data cannot show.
    """
    total = sum(sum(row) for row in table)
    if total == 0:
        return _statistic(
            "cohen_kappa",
            None,
            reason=unavailable("no_paired_units", UNAVAILABLE_REASONS["no_paired_units"]),
        )
    observed = Fraction(sum(table[i][i] for i in range(len(table))), total)
    expected = sum(
        Fraction(sum(table[i]), total) * Fraction(sum(row[i] for row in table), total)
        for i in range(len(table))
    )
    expected = Fraction(expected)
    if expected == 1:
        return _statistic(
            "cohen_kappa",
            None,
            reason=unavailable(
                "expected_agreement_is_one",
                "both annotators used a single class over all "
                f"{total} unit(s), so chance alone predicts every match",
            ),
            expected_agreement=expected,
        )
    return _statistic(
        "cohen_kappa",
        (observed - expected) / (1 - expected),
        expected_agreement=expected,
        interpretation=(
            "agreement beyond what the two annotators' own class frequencies predict; "
            "negative means worse than chance"
        ),
    )


def _pabak(table: Sequence[Sequence[int]]) -> dict[str, Any]:
    """Prevalence-adjusted bias-adjusted kappa, ``2 * observed - 1``.

    Cohen's kappa falls towards zero when one class dominates even though the
    annotators agree on nearly every unit -- the kappa paradox. PABAK reports what
    kappa would have been under balanced marginals, so the pair of them separates
    "they disagree" from "the class distribution is skewed". It is reported
    alongside kappa and never instead of it.
    """
    total = sum(sum(row) for row in table)
    if total == 0:
        return _statistic(
            "pabak",
            None,
            reason=unavailable("no_paired_units", UNAVAILABLE_REASONS["no_paired_units"]),
        )
    observed = Fraction(sum(table[i][i] for i in range(len(table))), total)
    return _statistic(
        "pabak",
        2 * observed - 1,
        interpretation=(
            "kappa recomputed as if the classes were balanced; a large gap from "
            "cohen_kappa means the class distribution, not the annotators, moved the "
            "statistic"
        ),
    )


def _prevalence(
    pairs: Sequence[tuple[str, str]], classes: Sequence[str]
) -> list[dict[str, Any]]:
    total = len(pairs)
    rows = []
    for name in classes:
        left = sum(1 for a, _ in pairs if a == name)
        right = sum(1 for _, b in pairs if b == name)
        rows.append(
            {
                "class": name,
                "role_a_count": left,
                "role_b_count": right,
                "role_a_rate": _num(_rate(left, total)),
                "role_b_rate": _num(_rate(right, total)),
                "both_count": sum(1 for a, b in pairs if a == name and b == name),
            }
        )
    return rows


def _classes_present(pairs: Sequence[tuple[str, str]], base: Sequence[str]) -> list[str]:
    """The published vocabulary, plus any observed value outside it.

    An unexpected value is added rather than dropped: a class silently excluded
    from a contingency table changes every marginal in it.
    """
    observed = {value for pair in pairs for value in pair}
    return list(base) + sorted(observed.difference(base))


# -- metric construction -----------------------------------------------------


def agreement_metric(
    *,
    metric: str,
    question: str,
    unit_of_analysis: str,
    pairs: Sequence[tuple[str, str]],
    classes: Sequence[str],
    empty_reason: Mapping[str, str],
    forced_unavailable: Mapping[str, str] | None = None,
    exclusions: Sequence[Mapping[str, Any]] = (),
    notes: Sequence[str] = (),
    value_sources: Sequence[Mapping[str, Any]] | None = None,
    derived_rates: Sequence[Mapping[str, Any]] = (),
    components: Sequence[Mapping[str, Any]] = (),
    with_pabak: bool = False,
) -> dict[str, Any]:
    """One axis of the agreement vector.

    ``empty_reason`` is supplied by the caller because "no unit was judged twice"
    and "units were judged twice but none met this metric's condition" are
    different facts about the corpus, and collapsing them would hide which one
    has to be fixed.
    """
    excluded = sum(int(item["count"]) for item in exclusions)
    out: dict[str, Any] = {
        "metric": metric,
        "question": question,
        "unit_of_analysis": unit_of_analysis,
        "available": False,
        "unavailable_reason": None,
        "n": len(pairs),
        "n_excluded": excluded,
        "exclusions": [dict(item) for item in exclusions],
        "raw_agreement": None,
        "chance_corrected": _statistic(
            "cohen_kappa",
            None,
            reason=unavailable("no_paired_units", UNAVAILABLE_REASONS["no_paired_units"]),
        ),
        "class_prevalence": [],
        "small_n": len(pairs) < SMALL_N_THRESHOLD,
        "notes": list(notes),
    }
    if value_sources is not None:
        out["value_sources"] = [dict(item) for item in value_sources]
    if derived_rates:
        out["derived_rates"] = [dict(item) for item in derived_rates]
    if components:
        out["components"] = [dict(item) for item in components]

    reason = forced_unavailable or (empty_reason if not pairs else None)
    if reason is not None:
        out["unavailable_reason"] = dict(reason)
        out["chance_corrected"] = _statistic("cohen_kappa", None, reason=dict(reason))
        return out

    order = _classes_present(pairs, classes)
    table = contingency(pairs, order)
    out["available"] = True
    out["raw_agreement"] = _num(
        Fraction(sum(1 for a, b in pairs if a == b), len(pairs))
    )
    out["chance_corrected"] = cohen_kappa(table)
    out["class_prevalence"] = _prevalence(pairs, order)
    out["confusion"] = {"class_order": order, "matrix": table}
    if with_pabak:
        out["additional_statistics"] = [_pabak(table)]
    return out


# -- reading the judgments ---------------------------------------------------


def applicability_of(judgment: Mapping[str, Any]) -> tuple[str, str]:
    """``(state, source)`` for whether the annotator found the rule applicable.

    A stated value wins. A malformed stated value raises rather than falling back:
    a value the annotator supplied and this tool could not read is a data defect,
    not an absence, and quietly replacing it with a derivation would hide it.
    """
    stated = (judgment.get("extensions") or {}).get(EXT_APPLICABILITY)
    if stated is not None:
        if stated not in APPLICABILITY_STATES:
            raise UsageError(
                f"judgment {judgment.get('judgment_id')!r} states applicability "
                f"{stated!r}, which is not one of {APPLICABILITY_STATES}"
            )
        return str(stated), "stated"
    return APPLICABILITY_BY_LABEL[judgment["label"]], "derived_from_label"


def context_sufficiency_of(judgment: Mapping[str, Any]) -> tuple[str | None, str]:
    """``(rating, source)`` for how sufficient the annotator found the context.

    The only fallback is the ``insufficient_context`` label, which is itself a
    statement that the context did not suffice. Emptiness of
    ``requested_additional_context`` is deliberately *not* read as sufficiency: an
    annotator who asked for nothing may not have thought to ask, and inferring a
    rating from silence is the absence-to-value coercion ADR-0002 forbids.
    """
    stated = (judgment.get("extensions") or {}).get(EXT_CONTEXT_SUFFICIENCY)
    if stated is not None:
        if stated not in CONTEXT_SUFFICIENCY_STATES:
            raise UsageError(
                f"judgment {judgment.get('judgment_id')!r} states context sufficiency "
                f"{stated!r}, which is not one of {CONTEXT_SUFFICIENCY_STATES}"
            )
        return str(stated), "stated"
    if judgment["label"] == "insufficient_context":
        return "insufficient", "derived_from_label"
    return None, "unavailable"


def span_tokens(judgment: Mapping[str, Any]) -> tuple[frozenset[tuple[str, int]] | None, str]:
    """``(tokens, convention)`` for one judgment's evidence spans.

    **A token is one character position.** Precisely: a token is the pair
    ``(target, offset)``, where ``offset`` is a single integer character index and
    ``target`` names the text the index is into. A span of kind ``character``
    covering ``[start, end)`` contributes the tokens ``start``, ``start + 1``, ...,
    ``end - 1`` -- the half-open interval, matching the span schema, so two
    adjacent spans never double-count the boundary character. Tokens are a set, so
    overlapping spans from one annotator contribute each position once, and span
    order and span count do not affect the score.

    Character positions, not words, because word tokenisation needs source text
    and this report deliberately never reads it: the score is determined by the
    judgment record's offsets and content identities, without exporting raw
    source text. A character-offset token is fully determined by the judgment
    record itself, so the score is reproducible from committed data alone. The
    cost is that agreement on a long word counts more
    than agreement on a short one; the benefit is that no tokeniser version can
    move the number.

    ``target`` is the span's ``source_sha256`` when it carries one, and the
    judgment's ``example_id`` when no span carries one. Returns the convention
    used (``"source_sha256"``, ``"example_id"``, ``"mixed"``, or ``"none"``) so a
    caller can refuse to compare two annotators who keyed their offsets
    differently -- comparing them would score a guaranteed empty intersection as
    total disagreement.

    A span of any non-``character`` kind returns ``None``: a line range or a JSON
    pointer carries no character offsets, and converting one into offsets would
    require the source text.
    """
    spans = judgment.get("evidence_spans") or []
    if not spans:
        return frozenset(), "none"
    if any(span.get("kind") != "character" for span in spans):
        return None, "mixed"
    with_hash = sum(1 for span in spans if span.get("source_sha256"))
    if with_hash == 0:
        convention = "example_id"
    elif with_hash == len(spans):
        convention = "source_sha256"
    else:
        return None, "mixed"
    tokens: set[tuple[str, int]] = set()
    for span in spans:
        target = str(span.get("source_sha256") or judgment["example_id"])
        start, end = int(span["start"]), int(span["end"])
        if end < start:
            raise UsageError(
                f"judgment {judgment.get('judgment_id')!r} cites a span ending before it "
                f"begins ({start}, {end})"
            )
        tokens.update((target, offset) for offset in range(start, end))
    return frozenset(tokens), convention


def _token_f1_metric(units: Sequence[tuple[str, Mapping[str, Any], Mapping[str, Any]]]) -> dict:
    """Evidence-span token F1, micro-pooled with a macro companion."""
    true_positive = false_positive = false_negative = 0
    per_unit: list[Fraction] = []
    excluded: dict[str, int] = {}
    scored = 0
    for _, left, right in units:
        left_tokens, left_convention = span_tokens(left)
        right_tokens, right_convention = span_tokens(right)
        if left_tokens is None or right_tokens is None:
            excluded["span_not_character_addressed"] = (
                excluded.get("span_not_character_addressed", 0) + 1
            )
            continue
        conventions = {left_convention, right_convention} - {"none"}
        if len(conventions) > 1:
            excluded["inconsistent_span_target"] = excluded.get("inconsistent_span_target", 0) + 1
            continue
        if not left_tokens and not right_tokens:
            excluded["no_span_cited_by_either"] = excluded.get("no_span_cited_by_either", 0) + 1
            continue
        overlap = len(left_tokens & right_tokens)
        true_positive += overlap
        false_positive += len(right_tokens) - overlap
        false_negative += len(left_tokens) - overlap
        per_unit.append(Fraction(2 * overlap, len(left_tokens) + len(right_tokens)))
        scored += 1

    exclusion_detail = {
        "span_not_character_addressed": (
            "at least one cited span is a line range, locator, or JSON pointer, which "
            "carries no character offsets to tokenise"
        ),
        "inconsistent_span_target": (
            "the two annotators keyed their offsets differently (one against a source "
            "digest, one against the example), so an empty overlap would be an artefact"
        ),
        "no_span_cited_by_either": (
            "neither annotator cited a span, so there is no overlap to score; scoring "
            "this as 1.0 would reward two annotators for citing nothing"
        ),
    }
    exclusions = [
        {"reason": reason, "count": count, "detail": exclusion_detail[reason]}
        for reason, count in sorted(excluded.items())
    ]

    metric: dict[str, Any] = {
        "metric": "evidence_span_token_f1",
        "question": (
            "When both annotators point at the text, do they point at the same "
            "characters?"
        ),
        "unit_of_analysis": "paired judgment on one (example_id, rule_id) unit",
        "available": False,
        "unavailable_reason": None,
        "n": scored,
        "n_excluded": sum(excluded.values()),
        "exclusions": exclusions,
        "raw_agreement": None,
        "chance_corrected": _statistic(
            "none_defined",
            None,
            reason=unavailable(
                "chance_baseline_undefined",
                "token overlap has no agreed chance model: the number of characters an "
                "annotator could have selected is not fixed by the protocol, so there is "
                "no marginal distribution to correct against",
            ),
        ),
        "class_prevalence": [],
        "small_n": scored < SMALL_N_THRESHOLD,
        "notes": [
            "A token is one character position, identified by (target, offset); a "
            "character span [start, end) contributes end - start tokens. See "
            "ats.corpus.agreement.span_tokens for the full definition.",
            "raw_agreement is the micro-pooled F1 over all scored units. Micro is the "
            "headline because a macro mean lets a unit with one cited character weigh as "
            "much as a unit with a whole paragraph.",
        ],
    }
    denominator = 2 * true_positive + false_positive + false_negative
    if scored == 0 or denominator == 0:
        metric["unavailable_reason"] = unavailable(
            "no_spans_cited",
            f"{sum(excluded.values())} unit(s) were excluded and {scored} were scored, "
            "leaving no cited character to compare",
        )
        return metric
    metric["available"] = True
    metric["raw_agreement"] = _num(Fraction(2 * true_positive, denominator))
    metric["additional_statistics"] = [
        _statistic(
            "macro_token_f1",
            Fraction(sum(per_unit), len(per_unit)),
            interpretation="unweighted mean of the per-unit F1 scores",
        )
    ]
    metric["derived_rates"] = [
        {
            "name": "units_where_both_cited_at_least_one_character",
            "numerator": scored,
            "denominator": scored + sum(excluded.values()),
            "value": _num(_rate(scored, scored + sum(excluded.values()))),
        }
    ]
    return metric


# -- per-rule confusion ------------------------------------------------------


def _label_row(label: str, pairs: Sequence[tuple[str, str]]) -> dict[str, Any]:
    """One label's row: prevalence, specific agreement, one-versus-rest kappa."""
    total = len(pairs)
    left = sum(1 for a, _ in pairs if a == label)
    right = sum(1 for _, b in pairs if b == label)
    both = sum(1 for a, b in pairs if a == label and b == label)
    pooled = Fraction(left + right, 2 * total) if total else Fraction(0)

    if left + right == 0:
        specific = _statistic(
            "positive_specific_agreement",
            None,
            reason=unavailable(
                "class_unused_by_both",
                f"neither annotator applied {label!r} to any of the {total} unit(s), so "
                "there is no positive case to agree about",
            ),
        )
    else:
        specific = _statistic(
            "positive_specific_agreement",
            Fraction(2 * both, left + right),
            interpretation=(
                "chance-independent agreement on this label alone: 2 * both / "
                "(a_uses + b_uses). Unlike kappa it does not collapse when the label is "
                "rare, which is the case a corpus-wide statistic cannot see."
            ),
        )

    binary = [
        [both, left - both],
        [right - both, total - left - right + both],
    ]
    return {
        "label": label,
        "role_a_count": left,
        "role_b_count": right,
        "both_count": both,
        "pooled_prevalence": _num(pooled),
        "rare": bool(0 < pooled <= RARE_CLASS_PREVALENCE),
        "total_disagreement": bool(left + right > 0 and both == 0),
        "positive_specific_agreement": specific,
        "one_vs_rest_kappa": cohen_kappa(binary),
    }


def _rule_row(rule_id: str, pairs: Sequence[tuple[str, str]]) -> dict[str, Any]:
    order = _classes_present(pairs, LABELS)
    table = contingency(pairs, order)
    return {
        "rule_id": rule_id,
        "n": len(pairs),
        "small_n": len(pairs) < SMALL_N_THRESHOLD,
        "small_n_threshold": SMALL_N_THRESHOLD,
        "confusion": {"class_order": order, "matrix": table},
        "raw_agreement": _num(Fraction(sum(1 for a, b in pairs if a == b), len(pairs))),
        "chance_corrected": cohen_kappa(table),
        "labels": [_label_row(label, pairs) for label in order],
    }


# -- inputs ------------------------------------------------------------------


def load_round(
    path: str | Path, role: str
) -> tuple[dict[str, Any], list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    """Read one annotation round: ``(record, judgments, embedded_annotators)``.

    A missing round makes every metric unavailable. It never makes them zero: an
    unrun round and a round where the annotators agreed on nothing are opposite
    facts, and a report that renders both as 0.0 is worse than no report.

    ``embedded_annotators`` is whatever annotator list the round record carries,
    returned whether or not the round is usable, so the registry cross-check can
    run against a round whose judgments were rejected.
    """
    file = Path(path)
    record: dict[str, Any] = {
        "role": role,
        "path": str(path),
        "available": False,
        "unavailable_reason": None,
        "judgments": 0,
        "annotator_ids": [],
    }
    if not file.is_file():
        record["unavailable_reason"] = unavailable(
            "round_unavailable", f"no annotation round file at {file}"
        )
        return record, [], []
    records = rec.read_records(file)
    judgments = [r for r in records if r.get("schema_version") == "ats.judgment.v1"]
    embedded = [
        entry
        for r in records
        if r.get("schema_version") == "ats.annotation_round.v1"
        for entry in (r.get("annotators") or [])
    ]
    record["file_sha256"] = sha256_hex(file.read_bytes())
    record["judgments"] = len(judgments)
    record["annotator_ids"] = sorted({j["annotator_id"] for j in judgments})
    record["embedded_annotators"] = len(embedded)
    if not judgments:
        record["unavailable_reason"] = unavailable(
            "round_unavailable",
            f"{file} holds no ats.judgment.v1 record, so this round contributed nothing",
        )
        return record, [], embedded
    if len(record["annotator_ids"]) > 1:
        record["unavailable_reason"] = unavailable(
            "round_unavailable",
            f"{file} mixes judgments from {len(record['annotator_ids'])} annotators "
            f"({', '.join(record['annotator_ids'])}); a round compared as one pass must "
            "be one pass",
        )
        return record, [], embedded
    record["available"] = True
    return record, judgments, embedded


def sidecar_path(round_path: str | Path) -> Path:
    """Where a round's applicability sidecar sits, by convention.

    ``round-a.jsonl`` pairs with ``round-a-inapplicable.jsonl``. Derived rather
    than guessed at read time: if the derived path does not exist the sidecar is
    reported unavailable, never assumed empty.
    """
    file = Path(round_path)
    return file.with_name(f"{file.stem}-inapplicable{file.suffix}")


def load_sidecar(
    path: str | Path, role: str, annotator_id: str | None
) -> tuple[dict[str, Any], list[Mapping[str, Any]]]:
    """Read one round's applicability sidecar: units a pass declined to judge.

    AG-19 step 2: a rule the annotator finds inapplicable yields no conformance
    judgment, so those units leave no ``ats.judgment.v1`` behind. They are
    recorded as ``x-ats-repo.non_judgment.v0`` instead, and they matter more than
    the judgments do: computing applicability agreement over the judged units
    alone drops exactly the units where one pass declined and the other did not,
    and reports better agreement than the round achieved.

    A present-but-empty sidecar is a positive statement that this pass declined
    nothing. An *absent* sidecar is not: it leaves the applicability universe
    unestablished, and is reported unavailable rather than read as zero.
    """
    file = Path(path)
    record: dict[str, Any] = {
        "path": str(path),
        "available": False,
        "unavailable_reason": None,
        "records": 0,
        "annotator_ids": [],
    }
    if not file.is_file():
        record["unavailable_reason"] = unavailable(
            "sidecar_missing",
            f"no applicability sidecar at {file}; the units round {role} declined to "
            "judge are therefore unknown, and are not assumed to be none",
        )
        return record, []
    entries = [
        r
        for r in rec.read_records(file)
        if r.get("schema_version") == NON_JUDGMENT_SCHEMA_VERSION
    ]
    record["file_sha256"] = sha256_hex(file.read_bytes())
    record["records"] = len(entries)
    record["annotator_ids"] = sorted({str(r.get("annotator_id")) for r in entries})
    if annotator_id and record["annotator_ids"] not in ([], [annotator_id]):
        record["unavailable_reason"] = unavailable(
            "sidecar_annotator_mismatch",
            f"{file} carries records from {', '.join(record['annotator_ids'])} but round "
            f"{role} is {annotator_id}; the sidecar does not belong to this pass",
        )
        return record, []
    record["available"] = True
    return record, entries


def load_registry(path: str | Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Read the annotator registry: identities, kinds, models, prompt identity."""
    file = Path(path)
    meta: dict[str, Any] = {
        "path": str(path),
        "available": False,
        "unavailable_reason": None,
        "declared_annotators": 0,
    }
    if not file.is_file():
        meta["unavailable_reason"] = unavailable(
            "registry_missing",
            f"no annotator registry at {file}; without it this report cannot say what "
            "kind of annotator produced the judgments, and an undeclared annotator is "
            "not assumed to be human",
        )
        return meta, {}
    raw = file.read_bytes()
    try:
        document = json.loads(raw.decode("utf-8"))
        entries = document["annotators"]
        index = {str(entry["annotator_id"]): dict(entry) for entry in entries}
    except (ValueError, KeyError, TypeError) as exc:
        meta["file_sha256"] = sha256_hex(raw)
        meta["unavailable_reason"] = unavailable(
            "registry_malformed",
            f"{file} is not an annotator registry ({{'annotators': [...]}}): {exc}",
        )
        return meta, {}
    meta["file_sha256"] = sha256_hex(raw)
    meta["available"] = True
    meta["declared_annotators"] = len(index)
    return meta, index


#: Which annotator each round file is expected to hold, when the caller knows.
#: Used only to name a round that is absent; an observed identity always wins.
DEFAULT_EXPECTED_ANNOTATORS: Final[dict[str, str]] = {
    "a": "llm-annotator-a",
    "b": "llm-annotator-b",
}


def _annotator_entry(
    role: str,
    observed_id: str | None,
    expected_id: str | None,
    registry: Mapping[str, Mapping[str, Any]],
    judgments: int,
) -> dict[str, Any]:
    """One annotator row, recording where its identity came from.

    An absent round has no observed annotator. Naming the annotator the caller
    expected there keeps the report able to say *whose* pass is missing, but the
    row marks the identity ``expected_from_caller`` so a reader never mistakes a
    declared instrument for one that ran.
    """
    annotator_id = observed_id or expected_id
    source = (
        "observed_in_round"
        if observed_id
        else "expected_from_caller"
        if expected_id
        else "undeclared"
    )
    declared = registry.get(annotator_id or "", {})
    kind = declared.get("kind")
    return {
        "role": role,
        "annotator_id": annotator_id or f"<undeclared-round-{role}>",
        "identity_source": source,
        "kind": kind if kind in ANNOTATOR_KINDS else "unknown",
        "model": declared.get("model") or None,
        "prompt_id": declared.get("prompt_id") or None,
        "prompt_sha256": declared.get("prompt_sha256") or None,
        "judgments": judgments,
    }


def measurement_kind(kinds: Sequence[str]) -> str:
    """What agreement between annotators of these kinds measures."""
    unique = set(kinds)
    if "unknown" in unique or not unique:
        return "unknown"
    if unique == {"llm"}:
        return "instrument_reproducibility"
    if unique == {"human"}:
        return "human_inter_rater_reliability"
    return "human_model_concordance"


# -- report ------------------------------------------------------------------


def _pair_units(
    judgments_a: Sequence[Mapping[str, Any]], judgments_b: Sequence[Mapping[str, Any]]
) -> tuple[list[tuple[str, Mapping[str, Any], Mapping[str, Any]]], dict[str, Any]]:
    """Match the two rounds on ``(example_id, rule_id)``.

    A unit an annotator judged twice is dropped with a reason rather than
    silently resolved to the first or the last: two judgments from one annotator
    on one unit are a protocol violation, and picking one of them would decide
    which opinion counts.
    """
    def index(
        judgments: Sequence[Mapping[str, Any]],
    ) -> tuple[dict[tuple[str, str], Mapping[str, Any]], set[tuple[str, str]]]:
        out: dict[tuple[str, str], Mapping[str, Any]] = {}
        duplicates: set[tuple[str, str]] = set()
        for judgment in judgments:
            key = (judgment["example_id"], judgment["rule_id"])
            if key in out:
                duplicates.add(key)
            out[key] = judgment
        return out, duplicates

    left, left_dupes = index(judgments_a)
    right, right_dupes = index(judgments_b)
    duplicates = left_dupes | right_dupes
    shared = sorted((set(left) & set(right)) - duplicates)
    units = [
        (f"{example}|{rule}", left[(example, rule)], right[(example, rule)])
        for example, rule in shared
    ]
    dropped = [
        {
            "example_id": example,
            "rule_id": rule,
            "reason": "duplicate_judgments_from_one_annotator",
            "detail": "one annotator submitted more than one judgment for this unit; "
            "choosing between them would decide which opinion counts",
        }
        for example, rule in sorted(duplicates)
    ]
    pairing = {
        "unit_of_analysis": "(example_id, rule_id); spec Section 12.10 makes one rule "
        "judgment the smallest attributable unit",
        "paired_units": len(units),
        "role_a_only": len(set(left) - set(right) - duplicates),
        "role_b_only": len(set(right) - set(left) - duplicates),
        "dropped_units": dropped,
        "notes": [
            "Units judged by only one round are counted, not compared: a unit one pass "
            "never saw carries no agreement information in either direction."
        ],
    }
    return units, pairing


def applicability_universe(
    judgments: Sequence[Mapping[str, Any]],
    declined: Sequence[Mapping[str, Any]],
) -> tuple[dict[tuple[str, str], tuple[str, str, str]], list[tuple[str, str]]]:
    """Every unit one pass answered an applicability question about.

    Returns ``unit -> (state, value_source, origin)`` plus the units that appear
    both as a judgment and as a decline record. A unit answered twice by one pass
    is a contradiction, not a duplicate: it is dropped and reported, because
    choosing between "I judged this" and "I declined this" would decide which
    answer counts.

    The universe is judgments *and* declines because the two rounds' declines are
    where they disagree hardest. AG-19 leaves no judgment behind for a declined
    unit, so a universe built from judgments alone silently omits every unit one
    pass declined and the other labelled -- and reports better agreement than the
    round achieved.
    """
    universe: dict[tuple[str, str], tuple[str, str, str]] = {}
    for judgment in judgments:
        key = (judgment["example_id"], judgment["rule_id"])
        state, source = applicability_of(judgment)
        universe[key] = (state, source, "judgment")
    conflicts: list[tuple[str, str]] = []
    for entry in declined:
        key = (str(entry.get("example_id")), str(entry.get("rule_id")))
        state = entry.get("applicability")
        if state not in APPLICABILITY_STATES:
            raise UsageError(
                f"non-judgment record for {key[0]}/{key[1]} states applicability "
                f"{state!r}, which is not one of {APPLICABILITY_STATES}"
            )
        if key in universe:
            conflicts.append(key)
            continue
        universe[key] = (str(state), "stated", "declined_record")
    for key in conflicts:
        universe.pop(key, None)
    return universe, sorted(set(conflicts))


def _sources(counts: Mapping[str, int]) -> list[dict[str, Any]]:
    return [
        {"source": source, "count": counts.get(source, 0)}
        for source in ("stated", "derived_from_label", "unavailable")
    ]


def _protected_metric(
    units: Sequence[tuple[str, Mapping[str, Any], Mapping[str, Any]]],
    empty_reason: Mapping[str, str],
    forced: Mapping[str, str] | None,
) -> dict[str, Any]:
    """Protected-impact agreement: the exact set, plus one metric per class.

    The exact-set headline and the per-class components answer different
    questions. Two annotators who both flag P2 and split on P0 have partially
    agreed on the set and completely disagreed about the class that decides
    whether a transformation may ship (spec Section 11.3.1), so the P0 component
    is reported in its own right rather than averaged into the set score.
    """
    def as_set(judgment: Mapping[str, Any]) -> str:
        values = sorted(set(judgment.get("protected_impact") or ()))
        return "+".join(values) if values else "none"

    pairs = [(as_set(left), as_set(right)) for _, left, right in units]
    observed = sorted({value for pair in pairs for value in pair})

    components = []
    for protected_class in PROTECTED_CLASSES:
        def marks(judgment: Mapping[str, Any], name: str = protected_class) -> str:
            return "present" if name in (judgment.get("protected_impact") or ()) else "absent"

        class_pairs = [(marks(left), marks(right)) for _, left, right in units]
        components.append(
            agreement_metric(
                metric=f"protected_impact_agreement.{protected_class}",
                question=f"Do both annotators mark this unit as touching {protected_class}?",
                unit_of_analysis="paired judgment on one (example_id, rule_id) unit",
                pairs=class_pairs,
                classes=("present", "absent"),
                empty_reason=empty_reason,
                forced_unavailable=forced,
                with_pabak=True,
                notes=[
                    f"{protected_class} presence as a binary; kappa collapses when the "
                    "class is rare, so PABAK is reported beside it."
                ],
            )
        )

    return agreement_metric(
        metric="protected_impact_agreement",
        question="Do both annotators assign the same set of protected-field classes?",
        unit_of_analysis="paired judgment on one (example_id, rule_id) unit",
        pairs=pairs,
        classes=observed or ("none",),
        empty_reason=empty_reason,
        forced_unavailable=forced,
        components=components,
        notes=[
            "The headline compares the exact set: '+'-joined class names, 'none' for an "
            "empty set. Per-class components follow, because a set score hides which "
            "class the two passes split on."
        ],
    )


def round_record_annotators(path: str | Path | None) -> list[Mapping[str, Any]]:
    """The annotator list an ``ats.annotation_round.v1`` document declares.

    The round record is where the pilot states which instrument ran, so it is the
    corroborating source for the registry file. An absent or non-round document
    yields an empty list, which leaves the registry uncorroborated rather than
    silently confirmed.
    """
    if path is None:
        return []
    file = Path(path)
    if not file.is_file():
        return []
    try:
        document = json.loads(file.read_bytes().decode("utf-8"))
    except ValueError:
        return []
    if not isinstance(document, dict):
        return []
    if document.get("schema_version") != "ats.annotation_round.v1":
        return []
    return [entry for entry in (document.get("annotators") or []) if isinstance(entry, dict)]


def build_agreement_report(
    ctx: Any,
    *,
    round_a: str | Path,
    round_b: str | Path,
    annotators: str | Path,
    round_record: str | Path | None = None,
    sidecar_a: str | Path | None = None,
    sidecar_b: str | Path | None = None,
    expected_annotators: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The agreement report over two independent annotation rounds.

    Both rounds and the annotator registry are read, never recomputed. Any of the
    three being absent yields a report whose metrics are explicitly unavailable,
    which is the honest artefact for a pilot mid-flight; it is not an error,
    because a caller regenerating the report before round B lands should get the
    document that says so.

    ``expected_annotators`` maps a role to the annotator identity the caller says
    belongs in that round file. It never overrides an observed identity; it only
    lets an unavailable round say whose pass is missing, and a round whose
    judgments name a different annotator raises a blocking finding rather than
    being quietly accepted.

    ``round_record`` names the ``ats.annotation_round.v1`` document whose embedded
    annotator list corroborates the registry file. Where the two disagree the
    report says so and reconciles neither: two sources naming different models for
    one annotator identity means one of them is wrong, and picking silently
    publishes the wrong one.

    ``sidecar_a`` and ``sidecar_b`` name the applicability sidecars holding the
    units each pass declined to judge (AG-19 step 2 leaves no judgment behind for
    those). They default to the ``-inapplicable`` companion of each round path.
    Applicability agreement is computed over judgments *and* declines, because a
    universe of judged units alone omits every unit one pass declined and the
    other labelled -- the units where the two passes disagree hardest.
    """
    registry_meta, registry = load_registry(annotators)
    record_a, judgments_a, embedded_a = load_round(round_a, "a")
    record_b, judgments_b, embedded_b = load_round(round_b, "b")
    embedded = [*embedded_a, *embedded_b, *round_record_annotators(round_record)]
    sidecar_record_a, declined_a = load_sidecar(
        sidecar_a if sidecar_a is not None else sidecar_path(round_a),
        "a",
        record_a["annotator_ids"][0] if record_a["annotator_ids"] else None,
    )
    sidecar_record_b, declined_b = load_sidecar(
        sidecar_b if sidecar_b is not None else sidecar_path(round_b),
        "b",
        record_b["annotator_ids"][0] if record_b["annotator_ids"] else None,
    )
    record_a["sidecar"] = sidecar_record_a
    record_b["sidecar"] = sidecar_record_b

    findings: list[dict[str, str]] = []
    rounds = [record_a, record_b]
    for record in rounds:
        if not record["available"]:
            findings.append(
                {
                    "code": "round_unavailable",
                    "severity": "blocking",
                    "subject": f"round {record['role']}",
                    "detail": record["unavailable_reason"]["detail"],
                }
            )
        if not record["sidecar"]["available"]:
            findings.append(
                {
                    "code": "applicability_sidecar_unavailable",
                    "severity": "concern",
                    "subject": f"round {record['role']}",
                    "detail": record["sidecar"]["unavailable_reason"]["detail"],
                }
            )

    expected = dict(expected_annotators or DEFAULT_EXPECTED_ANNOTATORS)
    annotator_rows = [
        _annotator_entry(
            record["role"],
            record["annotator_ids"][0] if record["annotator_ids"] else None,
            expected.get(record["role"]),
            registry,
            record["judgments"],
        )
        for record in rounds
    ]
    for record in rounds:
        wanted = expected.get(record["role"])
        if wanted and record["annotator_ids"] and record["annotator_ids"] != [wanted]:
            findings.append(
                {
                    "code": "round_annotator_mismatch",
                    "severity": "blocking",
                    "subject": f"round {record['role']}",
                    "detail": f"{record['path']} holds judgments from "
                    f"{record['annotator_ids'][0]!r} but the caller expects {wanted!r}; "
                    "the two rounds may not be the two passes this report claims to "
                    "compare",
                }
            )

    # Registry against what the rounds embed. A disagreement is reported, never
    # reconciled: two sources naming different models for one annotator id means
    # one of them is wrong, and choosing silently would publish the wrong one.
    if embedded:
        by_id = {str(entry.get("annotator_id")): entry for entry in embedded}
        mismatches = sorted(
            key
            for key, entry in by_id.items()
            if key not in registry
            or any(
                (registry[key].get(field) or None) != (entry.get(field) or None)
                for field in ("kind", "model", "prompt_id", "prompt_sha256")
            )
        )
        registry_meta["cross_check"] = {
            "performed": True,
            "agrees": not mismatches,
            "detail": (
                f"{len(by_id)} annotator entry(ies) embedded in the round records agree "
                "with the registry file"
                if not mismatches
                else "registry file and round-embedded annotators disagree for: "
                + ", ".join(mismatches)
            ),
        }
        if mismatches:
            findings.append(
                {
                    "code": "annotator_registry_round_mismatch",
                    "severity": "blocking",
                    "subject": ", ".join(mismatches),
                    "detail": registry_meta["cross_check"]["detail"]
                    + "; the identity of the instrument that produced these labels is "
                    "therefore unestablished",
                }
            )
    else:
        registry_meta["cross_check"] = {
            "performed": False,
            "agrees": False,
            "detail": "no round record embedded an annotator list, so the registry file "
            "stands uncorroborated",
        }

    if not registry_meta["available"]:
        findings.append(
            {
                "code": "annotator_registry_unavailable",
                "severity": "blocking",
                "subject": str(annotators),
                "detail": registry_meta["unavailable_reason"]["detail"],
            }
        )
    for row in annotator_rows:
        if row["kind"] == "unknown":
            findings.append(
                {
                    "code": "annotator_kind_undeclared",
                    "severity": "blocking",
                    "subject": row["annotator_id"],
                    "detail": "no declared kind for this annotator; the report cannot "
                    "state whether its numbers are instrument reproducibility or "
                    "inter-rater reliability, and does not guess",
                }
            )

    kind = measurement_kind([row["kind"] for row in annotator_rows])
    measurement = {
        "kind": kind,
        "statement": MEASUREMENT_STATEMENTS[kind],
        "annotator_kinds": [row["kind"] for row in annotator_rows],
        "independence": INDEPENDENCE_STATEMENT,
    }

    rounds_usable = record_a["available"] and record_b["available"]
    forced = (
        None
        if rounds_usable
        else unavailable(
            "round_unavailable",
            "round "
            + " and ".join(r["role"] for r in rounds if not r["available"])
            + " unavailable, so nothing was compared; this is not zero agreement",
        )
    )
    units, pairing = (
        _pair_units(judgments_a, judgments_b) if rounds_usable else ([], {
            "unit_of_analysis": "(example_id, rule_id)",
            "paired_units": 0,
            "role_a_only": record_a["judgments"],
            "role_b_only": record_b["judgments"],
            "dropped_units": [],
            "notes": ["No pairing was attempted: at least one round is unavailable."],
        })
    )
    for dropped in pairing["dropped_units"]:
        findings.append(
            {
                "code": "duplicate_judgments_for_unit",
                "severity": "blocking",
                "subject": f"{dropped['example_id']} / {dropped['rule_id']}",
                "detail": dropped["detail"],
            }
        )
    if rounds_usable and (pairing["role_a_only"] or pairing["role_b_only"]):
        findings.append(
            {
                "code": "unpaired_units",
                "severity": "concern",
                "subject": "pairing",
                "detail": f"{pairing['role_a_only']} unit(s) judged only by round a and "
                f"{pairing['role_b_only']} only by round b; spec Section 17.9's two-judgment "
                "floor is unmet for those units",
            }
        )

    no_pairs = unavailable(
        "no_paired_units",
        "no (example_id, rule_id) unit was judged by both rounds",
    )

    # -- the vector ---------------------------------------------------------
    metrics: list[dict[str, Any]] = []

    metrics.append(
        agreement_metric(
            metric="profile_agreement",
            question="Do both annotators judge the unit under the same ATS profile?",
            unit_of_analysis="paired judgment on one (example_id, rule_id) unit",
            pairs=[(left["profile"], right["profile"]) for _, left, right in units],
            classes=("ASSESS", "SPECIFY", "TRANSFORM"),
            empty_reason=no_pairs,
            forced_unavailable=forced,
            notes=[
                "Profile is upstream of every other axis: two annotators applying the "
                "same rule under different profiles are answering different questions, "
                "so a label disagreement beneath a profile disagreement is not a label "
                "disagreement."
            ],
        )
    )

    universe_a, conflicts_a = applicability_universe(judgments_a, declined_a)
    universe_b, conflicts_b = applicability_universe(judgments_b, declined_b)
    for role, conflicts in (("a", conflicts_a), ("b", conflicts_b)):
        for example, rule in conflicts:
            findings.append(
                {
                    "code": "unit_both_judged_and_declined",
                    "severity": "blocking",
                    "subject": f"{example} / {rule}",
                    "detail": f"round {role} both submitted a judgment for this unit and "
                    "recorded it as declined; the two answers contradict each other and "
                    "neither is chosen",
                }
            )
    applicability_units = sorted(set(universe_a) & set(universe_b)) if rounds_usable else []
    applicability_sources: dict[str, int] = {}
    applicability_pairs: list[tuple[str, str]] = []
    applicability_state: dict[tuple[str, str], tuple[str, str]] = {}
    applicability_origin: dict[tuple[str, str], tuple[str, str]] = {}
    for key in applicability_units:
        left_value, left_source, left_origin = universe_a[key]
        right_value, right_source, right_origin = universe_b[key]
        applicability_sources[left_source] = applicability_sources.get(left_source, 0) + 1
        applicability_sources[right_source] = applicability_sources.get(right_source, 0) + 1
        applicability_pairs.append((left_value, right_value))
        applicability_state[key] = (left_value, right_value)
        applicability_origin[key] = (left_origin, right_origin)
    pairing["applicability_paired_units"] = len(applicability_units)
    metrics.append(
        agreement_metric(
            metric="rule_applicability_agreement",
            question="Do both annotators agree that the rule governs this text at all?",
            unit_of_analysis=(
                "every (example_id, rule_id) unit both passes answered an applicability "
                "question about, whether by judging it or by declining to judge it"
            ),
            pairs=applicability_pairs,
            classes=APPLICABILITY_STATES,
            empty_reason=no_pairs,
            forced_unavailable=forced,
            value_sources=_sources(applicability_sources),
            with_pabak=True,
            notes=[
                "Applicability is read from the judgment's "
                f"{EXT_APPLICABILITY} extension where stated; value_sources counts how "
                "many values were instead derived from the label, which is weaker "
                "evidence.",
                "The universe is judgments plus decline records, not judgments alone. "
                "AG-19 step 2 leaves no judgment behind for a unit a pass found "
                "inapplicable, so scoring only the judged units would drop every unit "
                "one pass declined and the other labelled -- and report better agreement "
                "than the round achieved.",
            ],
        )
    )

    conditional_pairs: list[tuple[str, str]] = []
    excluded_conditional = 0
    for _, left, right in units:
        key = (left["example_id"], left["rule_id"])
        left_applicable, right_applicable = applicability_state.get(key, ("", ""))
        if left_applicable == "applicable" and right_applicable == "applicable":
            conditional_pairs.append((left["label"], right["label"]))
        else:
            excluded_conditional += 1
    # Units one pass declined never became a judgment pair, so they are counted
    # here rather than silently vanishing between the two metrics.
    declined_a_only = sum(
        1 for left, right in applicability_origin.values()
        if left == "declined_record" and right != "declined_record"
    )
    declined_b_only = sum(
        1 for left, right in applicability_origin.values()
        if right == "declined_record" and left != "declined_record"
    )
    declined_both = sum(
        1 for left, right in applicability_origin.values()
        if left == "declined_record" and right == "declined_record"
    )
    metrics.append(
        agreement_metric(
            metric="label_agreement_conditional_on_applicable",
            question=(
                "Where both annotators found the rule applicable, do they choose the "
                "same label?"
            ),
            unit_of_analysis="paired judgment where both annotators found the rule applicable",
            pairs=conditional_pairs,
            classes=LABELS,
            empty_reason=unavailable(
                "no_unit_satisfied_condition",
                f"{len(units)} unit(s) were paired but none had both annotators finding "
                "the rule applicable, so there is no conditional label agreement to "
                "report",
            ),
            forced_unavailable=forced,
            exclusions=[
                {
                    "reason": "not_applicable_to_both",
                    "count": excluded_conditional,
                    "detail": "at least one annotator did not find the rule applicable; "
                    "including these units would let agreement about 'this rule does not "
                    "apply' inflate agreement about which violation occurred",
                },
                {
                    "reason": "one_pass_declined_to_judge",
                    "count": declined_a_only + declined_b_only,
                    "detail": "one pass recorded no judgment because it found the rule "
                    "inapplicable while the other labelled it; that is an applicability "
                    "disagreement, and counting it as label agreement or as label "
                    "disagreement would both be wrong",
                },
                {
                    "reason": "both_passes_declined_to_judge",
                    "count": declined_both,
                    "detail": "both passes found the rule inapplicable and neither left a "
                    "label; they agree on applicability, which the applicability metric "
                    "records, and there is no label to compare",
                },
            ],
            notes=[
                "Conditioning is the point of this metric. Unconditional label agreement "
                "on a corpus dominated by inapplicable rules measures the corpus's class "
                "balance, not the annotators."
            ],
        )
    )

    sufficiency_sources: dict[str, int] = {}
    sufficiency_pairs: list[tuple[str, str]] = []
    unstated_sufficiency = 0
    for _, left, right in units:
        left_value, left_source = context_sufficiency_of(left)
        right_value, right_source = context_sufficiency_of(right)
        sufficiency_sources[left_source] = sufficiency_sources.get(left_source, 0) + 1
        sufficiency_sources[right_source] = sufficiency_sources.get(right_source, 0) + 1
        if left_value is None or right_value is None:
            unstated_sufficiency += 1
            continue
        sufficiency_pairs.append((left_value, right_value))
    metrics.append(
        agreement_metric(
            metric="context_sufficiency_agreement",
            question="Do both annotators find the supplied context equally sufficient?",
            unit_of_analysis="paired judgment where both annotators rated context sufficiency",
            pairs=sufficiency_pairs,
            classes=CONTEXT_SUFFICIENCY_STATES,
            empty_reason=unavailable(
                "value_not_stated",
                f"{len(units)} unit(s) were paired but no unit had a context-sufficiency "
                f"rating from both annotators; the rating is read from the "
                f"{EXT_CONTEXT_SUFFICIENCY} extension and is never inferred from an empty "
                "requested_additional_context",
            ),
            forced_unavailable=forced,
            value_sources=_sources(sufficiency_sources),
            exclusions=[
                {
                    "reason": "rating_not_stated",
                    "count": unstated_sufficiency,
                    "detail": "at least one annotator supplied no context-sufficiency "
                    "rating; an unstated rating is not 'sufficient'",
                }
            ],
            notes=[
                "Spec Section 17.4: an isolated span SHOULD NOT be labelled when the rule "
                "depends on discarded context. Disagreement here says the queue's context "
                "budget is wrong, not that the annotators are."
            ],
        )
    )

    metrics.append(_protected_metric(units, no_pairs, forced))

    if forced is not None:
        token_metric = _token_f1_metric([])
        token_metric["unavailable_reason"] = dict(forced)
        token_metric["chance_corrected"] = _statistic("none_defined", None, reason=dict(forced))
        token_metric["available"] = False
        token_metric["raw_agreement"] = None
    else:
        token_metric = _token_f1_metric(units)
    metrics.append(token_metric)

    def undecided(judgment: Mapping[str, Any]) -> str:
        return judgment["label"] if judgment["label"] in UNDECIDED_LABELS else "decided"

    undecided_pairs = [(undecided(left), undecided(right)) for _, left, right in units]
    either_flagged = sum(1 for a, b in undecided_pairs if a != "decided" or b != "decided")
    ambiguity_categories = sorted(
        {
            j["ambiguity_category"]
            for _, left, right in units
            for j in (left, right)
            if j["ambiguity_category"] != "none"
        }
    )
    metrics.append(
        agreement_metric(
            metric="ambiguous_or_insufficient_context_rate",
            question=(
                "How often does a pass decline to decide, and do the two passes decline "
                "on the same units?"
            ),
            unit_of_analysis="paired judgment on one (example_id, rule_id) unit",
            pairs=undecided_pairs,
            classes=("decided", *UNDECIDED_LABELS),
            empty_reason=no_pairs,
            forced_unavailable=forced,
            with_pabak=True,
            derived_rates=[
                {
                    "name": "either_annotator_declined_to_decide",
                    "numerator": either_flagged,
                    "denominator": len(undecided_pairs),
                    "value": _num(_rate(either_flagged, len(undecided_pairs))),
                }
            ],
            notes=[
                "class_prevalence carries the per-pass rate; raw_agreement is concordance "
                "on declining. A high rate is a finding about the rule text or the "
                "context budget, not annotator failure (spec Section 17.9 retains "
                "ambiguity rather than resolving it).",
                "Ambiguity categories seen on these units: "
                + (", ".join(ambiguity_categories) if ambiguity_categories else "none"),
            ],
        )
    )

    # -- per-rule -----------------------------------------------------------
    by_rule: dict[str, list[tuple[str, str]]] = {}
    for _, left, right in units:
        by_rule.setdefault(left["rule_id"], []).append((left["label"], right["label"]))
    per_rule = [_rule_row(rule_id, pairs) for rule_id, pairs in sorted(by_rule.items())]

    for row in per_rule:
        if row["small_n"]:
            findings.append(
                {
                    "code": "small_n_rule",
                    "severity": "note",
                    "subject": row["rule_id"],
                    "detail": f"{row['n']} paired unit(s), below the published "
                    f"{SMALL_N_THRESHOLD}-unit threshold; the matrix is reported in full "
                    "and its statistics are not stable evidence",
                }
            )
        for label_row in row["labels"]:
            if label_row["rare"] and label_row["total_disagreement"]:
                findings.append(
                    {
                        "code": "rare_class_total_disagreement",
                        "severity": "blocking",
                        "subject": f"{row['rule_id']} / {label_row['label']}",
                        "detail": f"label {label_row['label']!r} has pooled prevalence "
                        f"{label_row['pooled_prevalence']} on {row['n']} unit(s) and no unit "
                        f"where both annotators chose it (a={label_row['role_a_count']}, "
                        f"b={label_row['role_b_count']}, both=0). The rule's overall raw "
                        f"agreement is {row['raw_agreement']}; that number is carried by the "
                        "majority class and says nothing about this one",
                    }
                )
        if not row["chance_corrected"]["available"]:
            findings.append(
                {
                    "code": "chance_correction_undefined",
                    "severity": "concern",
                    "subject": row["rule_id"],
                    "detail": row["chance_corrected"]["unavailable_reason"]["detail"],
                }
            )

    for metric in metrics:
        if not metric["available"]:
            findings.append(
                {
                    "code": "metric_unavailable",
                    "severity": "concern",
                    "subject": metric["metric"],
                    "detail": metric["unavailable_reason"]["detail"],
                }
            )
        sources = {item["source"]: item["count"] for item in metric.get("value_sources", ())}
        if sources.get("derived_from_label"):
            findings.append(
                {
                    "code": "value_derived_not_stated",
                    "severity": "note",
                    "subject": metric["metric"],
                    "detail": f"{sources['derived_from_label']} of "
                    f"{sum(sources.values())} value(s) were derived by this tool from the "
                    "label rather than stated by the annotator",
                }
            )
        # The same blindness the per-rule label rows are checked for, one level up:
        # a class both passes barely use and never once agree on is invisible in the
        # metric's headline, which is carried by the majority class.
        for row in metric["class_prevalence"]:
            used = row["role_a_count"] + row["role_b_count"]
            pooled = _rate(used, 2 * metric["n"]) if metric["n"] else None
            if pooled is None or not (0 < pooled <= RARE_CLASS_PREVALENCE):
                continue
            if row["both_count"]:
                continue
            findings.append(
                {
                    "code": "rare_class_total_disagreement",
                    "severity": "blocking",
                    "subject": f"{metric['metric']} / {row['class']}",
                    "detail": f"class {row['class']!r} has pooled prevalence "
                    f"{_num(pooled)} over {metric['n']} unit(s) and no unit where both "
                    f"passes chose it (a={row['role_a_count']}, b={row['role_b_count']}, "
                    f"both=0). The metric's raw agreement is {metric['raw_agreement']}; "
                    "that number is carried by the majority class",
                }
            )

    # The single most informative line the pilot has produced: one pass declining
    # to judge a unit the other labelled is a disagreement about the rule's scope,
    # and it is invisible in every metric that only compares judgments.
    one_sided_declines = declined_a_only + declined_b_only
    declined_to_judge = {
        "unit_of_analysis": "(example_id, rule_id) unit both passes answered about",
        "role_a_declined": len(declined_a),
        "role_b_declined": len(declined_b),
        "declined_by_exactly_one_pass": one_sided_declines,
        "declined_by_both_passes": declined_both,
        "universe_complete": (
            record_a["sidecar"]["available"] and record_b["sidecar"]["available"]
        ),
        "detail": (
            "AG-19 step 2: a pass that finds the rule inapplicable records no "
            "conformance judgment, because fabricating a label there would invent an "
            "opinion nobody held. A unit exactly one pass declined is therefore a "
            "scope disagreement carried entirely by the sidecars: it appears in the "
            "applicability metric and is excluded from the label metric, and it would "
            "vanish from both if the applicability universe were built from judgments "
            "alone. `universe_complete` is false when a sidecar could not be read, in "
            "which case these counts are a floor and not a total: units a pass declined "
            "without recording it are absent from every number in this report."
        ),
    }
    if one_sided_declines:
        findings.append(
            {
                "code": "one_pass_declined_the_other_judged",
                "severity": "blocking",
                "subject": "applicability",
                "detail": f"{one_sided_declines} of {len(applicability_units)} paired "
                f"unit(s) were declined by exactly one pass ({declined_a_only} by a, "
                f"{declined_b_only} by b) and labelled by the other. The two passes "
                "disagree about what the rule governs, not about how to apply it, and "
                "no label statistic in this report measures that disagreement",
            }
        )

    judged_rules = set(by_rule)
    rules_without = sorted(
        rule_id for rule_id in ctx.registry.ids() if rule_id not in judged_rules
    )

    severities = {finding["severity"] for finding in findings}
    if not rounds_usable or pairing["paired_units"] == 0:
        status = "insufficient_evidence"
    elif "blocking" in severities:
        status = "blocking_concerns"
    elif "concern" in severities:
        status = "concerns_present"
    else:
        status = "no_concerns_detected"

    reasons = sorted(
        {
            f"{finding['code']}: {finding['subject']}"
            for finding in findings
            if finding["severity"] in ("blocking", "concern")
        }
    )
    if status == "insufficient_evidence":
        reasons.insert(
            0,
            "no unit was compared, so no metric in this report is evidence of anything",
        )
    elif not reasons:
        reasons.append(
            "every metric was computable and no rare class showed total disagreement; "
            "this is a statement about instrument stability only"
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "report_sha256": "",
        "generated_at": ctx.timestamp(),
        "spec_version": ctx.spec_version,
        "implementation": ctx.implementation,
        "measurement": measurement,
        "annotator_registry": registry_meta,
        "annotators": annotator_rows,
        "rounds": rounds,
        "pairing": pairing,
        "declined_to_judge": declined_to_judge,
        "vocabularies": {
            "labels": list(LABELS),
            "applicability": list(APPLICABILITY_STATES),
            "context_sufficiency": list(CONTEXT_SUFFICIENCY_STATES),
            "protected_impact": list(PROTECTED_CLASSES),
            "ambiguity_categories": list(AMBIGUITY_CATEGORIES),
            "applicability_fallback": [
                {"label": label, "applicability": state}
                for label, state in sorted(APPLICABILITY_BY_LABEL.items())
            ],
            "unavailability_codes": [
                {"code": code, "meaning": meaning}
                for code, meaning in sorted(UNAVAILABLE_REASONS.items())
            ],
        },
        "metrics": metrics,
        "per_rule": per_rule,
        "rules_without_paired_units": rules_without,
        "findings": sorted(
            findings, key=lambda f: (f["severity"], f["code"], f["subject"], f["detail"])
        ),
        "assessment": {
            "status": status,
            "reasons": reasons,
            "single_number_refusal": SINGLE_NUMBER_REFUSAL,
        },
    }
    sealed = seal(report)
    ctx.schemas.validate_document(sealed)
    return sealed


def summarise(report: Mapping[str, Any]) -> list[str]:
    """Terminal lines for the report, metric by metric. Never one number."""
    lines = [f"measurement: {report['measurement']['kind']}"]
    for metric in report["metrics"]:
        if metric["available"]:
            kappa = metric["chance_corrected"]
            corrected = (
                f"{kappa['statistic']}={kappa['value']}"
                if kappa["available"]
                else f"{kappa['statistic']}=UNAVAILABLE ({kappa['unavailable_reason']['code']})"
            )
            lines.append(
                f"  {metric['metric']:48} n={metric['n']:5} raw={metric['raw_agreement']} "
                f"{corrected}"
            )
        else:
            lines.append(
                f"  {metric['metric']:48} UNAVAILABLE "
                f"({metric['unavailable_reason']['code']})"
            )
    declined = report["declined_to_judge"]
    lines.append(
        f"declined to judge: a={declined['role_a_declined']} b={declined['role_b_declined']}, "
        f"one pass only={declined['declined_by_exactly_one_pass']}, "
        f"both={declined['declined_by_both_passes']} "
        f"(of {report['pairing']['applicability_paired_units']} applicability-paired units; "
        f"{report['pairing']['paired_units']} judgment pairs)"
    )
    lines.append(f"assessment: {report['assessment']['status']}")
    for reason in report["assessment"]["reasons"]:
        lines.append(f"  - {reason}")
    return lines


def iter_blocking(report: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    """The findings that stop this report from reading as success."""
    return (f for f in report["findings"] if f["severity"] == "blocking")

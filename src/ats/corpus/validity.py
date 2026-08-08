"""Instrument validity against caller-supplied adjudication.

Reproducibility and validity are different quantities. This module computes
per-instrument comparisons against the disposition supplied by an authorized
adjudicator, never pooling instruments. It refuses to emit a complete-looking
report when the authority record is absent or incomplete; partial reports carry
explicit coverage and per-metric denominators.

**The gold applicability mapping.** Applicability precision and recall need gold
expressed in the instrument's own three-state vocabulary
(:data:`~ats.corpus.agreement.APPLICABILITY_STATES`). :data:`GOLD_APPLICABILITY`
does that, and two of its decisions are deliberate:

``hard_negative`` maps to ``applicable``, which is the opposite of
:data:`ats.corpus.agreement.APPLICABILITY_BY_LABEL`. The two maps answer
different questions and both are published. Agreement's map is a *fallback* for a
judgment that stated no applicability, reading a ``hard_negative`` label as the
annotator implicitly claiming the rule does not govern the text. This map answers
"was the rule in scope, as the operator found it", and a hard negative is exactly
the unit where the rule is in scope and a surface cue fires -- that is what the
``surface_cue_hard_negative`` stratum is for. Mapping it to ``not_applicable``
here would score an instrument that correctly recognised the rule was in scope
and correctly declined to call a violation as a false applicability claim, and the
metric would reward declining to look. The instrument side of this comparison also
never uses a derived fallback: it reads the applicability each pass *stated*, out
of the queue's judgment summary, so no asymmetry between the two maps can enter
the number silently.

``insufficient_context`` and ``ambiguous_by_design`` map to ``undetermined``, a
third class that stays in the denominators rather than being excluded from them.
Excluding them would narrow precision to the units gold could decide, and
precision is the one number that must pay for an instrument asserting a rule
governs text the operator found undecidable. Keeping them also aligns the two
vocabularies exactly -- the instrument has its own ``undetermined`` state -- so
the three-by-three confusion shows where the instrument and the operator disagree
about decidability instead of hiding it behind an exclusion count.

**The label equivalence.** The instrument's ``ambiguous`` and gold's
``ambiguous_by_design`` are the same claim in two vocabularies:
:data:`LABEL_TO_GOLD_DISPOSITION` aligns them, because refusing to would score
every correct ambiguity call as an error. Nothing else is renamed; the
remaining labels are string-identical across the two vocabularies.

**A decline is never a match.** An instrument that declined to judge a unit
states no disposition, and every in-scope gold row states one, so a decline
counts as a mismatch and is recorded as its own outcome class. That keeps "the
instrument labelled it wrongly" separable from "the instrument refused to look",
which are different defects with different repairs.

**No pooling.** ``instrument_a`` and ``instrument_b`` are two instruments, not
two samples of one. Averaging their validity would report a number no
instrument has, and the schema has no field a pooled number could occupy. Read
the two blocks separately; if they disagree, that disagreement remains visible.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

from ..canonical import load_json, seal, sha256_hex
from ..errors import UsageError
from .agreement import APPLICABILITY_STATES, span_tokens
from .annotate import LABELS
from .gold import (
    PROFILE_DISPOSITIONS,
    SOURCE_DISPOSITIONS,
    gold_disposition,
    load_gold,
)

SCHEMA_ID: Final[str] = "ats_instrument_validity_v1.schema.json"
SCHEMA_VERSION: Final[str] = "ats.instrument_validity.v1"

#: Where the rendered narrative sits beside the artefact when a caller chooses
#: to render one; no repository-local path is assumed.
NARRATIVE_PATH: Final[str] = "INSTRUMENT_VALIDITY.md"

#: The two conformance instruments, in fixed order so every matrix reads the same
#: way on every run. They are never combined.
ROLES: Final[tuple[str, str]] = ("a", "b")

#: Confidence bins an annotator may declare, from ``ats_judgment_v1.schema.json``.
#: A bin nobody used is reported unavailable, never as a 0.0 accuracy.
CONFIDENCE_BINS: Final[tuple[str, ...]] = ("low", "moderate", "high")

#: Gold dispositions that bear a measurement. ``excluded`` is the operator
#: removing a unit from gold with a reason, so it is out of scope rather than a
#: class to predict.
SCORED_DISPOSITIONS: Final[tuple[str, ...]] = tuple(
    d for d in SOURCE_DISPOSITIONS if d != "excluded"
)

#: Gold disposition -> applicability class, in the instrument's own three-state
#: vocabulary. See the module docstring for why ``hard_negative`` is
#: ``applicable`` here and ``undetermined`` is a retained third class.
GOLD_APPLICABILITY: Final[dict[str, str]] = {
    "conforming": "applicable",
    "violation": "applicable",
    "near_miss": "applicable",
    "exception": "applicable",
    "hard_negative": "applicable",
    "ambiguous_by_design": "undetermined",
    "insufficient_context": "undetermined",
}

#: Instrument label -> the gold disposition making the same claim. Identity
#: except for the ambiguity pair, which is one claim in two vocabularies.
LABEL_TO_GOLD_DISPOSITION: Final[dict[str, str]] = {
    label: ("ambiguous_by_design" if label == "ambiguous" else label) for label in LABELS
}

#: Measurement kinds this document names. The reproducibility kinds are carried
#: so a reader cannot mistake a validity number for a reproducibility one; they
#: are established elsewhere and cross-referenced by sha256.
MEASUREMENT_KINDS: Final[tuple[str, ...]] = (
    "instrument_a_reproducibility",
    "instrument_b_reproducibility",
    "instrument_to_operator_validity",
)

#: Why this document reports no combined instrument number. Required by the
#: schema so that adding one later is a visible schema change.
POOLED_REFUSAL: Final[str] = (
    "No pooled or averaged instrument figure is reported, and the schema has no field "
    "one could be written into. Instrument a and instrument b are two instruments, not "
    "two samples of one. Read the two blocks separately; if they disagree, that "
    "disagreement remains visible."
)

#: Closed vocabulary for why a quantity could not be computed. Distinct from the
#: agreement report's vocabulary because the reasons are different: nothing here
#: can be unavailable because a round is missing, and nothing there can be
#: unavailable because gold is partial.
UNAVAILABLE_REASONS: Final[dict[str, str]] = {
    "gold_partial": (
        "the operator has not adjudicated every unit this metric is defined over, and "
        "the report was generated with --allow-partial"
    ),
    "no_unit_satisfied_condition": (
        "in-scope units exist, but none satisfied the condition this metric is defined "
        "over"
    ),
    "zero_denominator": (
        "the ratio's denominator is zero: neither the instrument nor gold ever used "
        "this class, so the ratio was never measured rather than being zero"
    ),
    "confidence_bin_empty": (
        "the instrument never declared this confidence level, so it has no accuracy; "
        "reporting 0.0 would assert the instrument is always wrong when confident this "
        "way"
    ),
    "instrument_never_judged": (
        "the instrument declined every in-scope unit, so it stated no label to compare"
    ),
    "no_operator_evidence": (
        "the operator cited no character offsets on any comparable unit, so there is no "
        "span to overlap with"
    ),
    "no_spans_comparable": (
        "no unit carried both an operator offset and an instrument span that could be "
        "tokenised against a common target"
    ),
    "agreement_report_absent": (
        "the supplied agreement report was not present, so the reproducibility "
        "measurement cannot be cross-referenced by content address"
    ),
    "rounds_absent": (
        "the annotation round holding this instrument's evidence spans was not present"
    ),
}


class GoldIncomplete(UsageError):
    """Gold is absent or does not cover every queue unit.

    A subclass of :class:`~ats.errors.UsageError` -- exit status 2 -- rather than
    a new entry in the shared error hierarchy, because the condition is specific
    to this measurement: the caller asked for a validity report before the
    authority it is measured against exists. The payload names the counts so the
    refusal is actionable without opening the gold file.
    """

    code = "gold_incomplete"

    def __init__(self, message: str, coverage: Sequence[Mapping[str, Any]]) -> None:
        super().__init__(message)
        self.coverage = [dict(row) for row in coverage]

    def payload(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": str(self),
            "coverage": self.coverage,
            "remedy": (
                "adjudicate the remaining units, or pass --allow-partial to publish a "
                "report whose coverage and per-metric n say what it does not cover"
            ),
        }


# -- small numeric helpers ---------------------------------------------------


def _num(value: Fraction | None) -> float | None:
    """A ratio as a JSON number, or ``None``.

    Rounded to six places so the report's bytes are reproducible. The exact value
    stays a :class:`~fractions.Fraction` through the computation, so no rounding
    ever decides a comparison.
    """
    return None if value is None else round(float(value), 6)


def unavailable(code: str, detail: str) -> dict[str, str]:
    """An unavailability record, refusing an unknown code."""
    if code not in UNAVAILABLE_REASONS:
        raise UsageError(
            f"{code!r} is not an instrument-validity unavailability code; add it to "
            "UNAVAILABLE_REASONS deliberately rather than inventing a reason at the "
            "call site"
        )
    return {"code": code, "detail": detail}


def ratio(
    name: str,
    numerator: int,
    denominator: int,
    *,
    detail: str,
    code: str = "zero_denominator",
) -> dict[str, Any]:
    """One rate, carrying the two counts it was computed from.

    A rate over zero observations is not zero; it is a rate nobody measured, and
    it is reported as an unavailability with the counts still visible so the
    reader can see the denominator was empty rather than the numerator.
    """
    available = denominator > 0
    return {
        "name": name,
        "numerator": numerator,
        "denominator": denominator,
        "available": available,
        "value": _num(Fraction(numerator, denominator)) if available else None,
        "unavailable_reason": None if available else unavailable(code, detail),
    }


def _metric(
    name: str,
    question: str,
    unit_of_analysis: str,
    *,
    n: int,
    reason: Mapping[str, str] | None = None,
    notes: Sequence[str] = (),
) -> dict[str, Any]:
    """The common envelope every metric carries: its n and its availability."""
    return {
        "metric": name,
        "question": question,
        "unit_of_analysis": unit_of_analysis,
        "n": n,
        "available": reason is None,
        "unavailable_reason": dict(reason) if reason else None,
        "rates": [],
        "confusion": None,
        "per_class": [],
        "bins": [],
        "notes": list(notes),
    }


def _confusion(
    pairs: Sequence[tuple[str, str]], rows: Sequence[str], columns: Sequence[str]
) -> dict[str, Any]:
    """Dense instrument-versus-gold table, instrument on the rows."""
    row_index = {value: i for i, value in enumerate(rows)}
    column_index = {value: i for i, value in enumerate(columns)}
    table = [[0] * len(columns) for _ in rows]
    for instrument, gold in pairs:
        table[row_index[instrument]][column_index[gold]] += 1
    return {
        "row_axis": "instrument",
        "column_axis": "operator_gold",
        "rows": list(rows),
        "columns": list(columns),
        "table": table,
    }


def _per_class(pairs: Sequence[tuple[str, str]], classes: Sequence[str]) -> list[dict[str, Any]]:
    """Precision, recall and F1 for each class, one-versus-rest."""
    out: list[dict[str, Any]] = []
    for name in classes:
        predicted = sum(1 for instrument, _ in pairs if instrument == name)
        actual = sum(1 for _, gold in pairs if gold == name)
        hits = sum(1 for instrument, gold in pairs if instrument == gold == name)
        out.append(
            {
                "class": name,
                "instrument_count": predicted,
                "gold_count": actual,
                "agreements": hits,
                "precision": ratio(
                    "precision",
                    hits,
                    predicted,
                    detail=f"the instrument never answered {name!r}",
                ),
                "recall": ratio(
                    "recall",
                    hits,
                    actual,
                    detail=f"gold never carries {name!r}",
                ),
                "f1": ratio(
                    "f1",
                    2 * hits,
                    predicted + actual,
                    detail=f"neither the instrument nor gold ever used {name!r}",
                ),
            }
        )
    return out


def _binary_rates(
    flags: Sequence[tuple[bool, bool]], subject: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Precision, recall and F1 for one binary claim, plus its four counts."""
    true_positive = sum(1 for i, g in flags if i and g)
    false_positive = sum(1 for i, g in flags if i and not g)
    false_negative = sum(1 for i, g in flags if not i and g)
    true_negative = sum(1 for i, g in flags if not i and not g)
    counts = {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
    }
    rates = [
        ratio(
            "precision",
            true_positive,
            true_positive + false_positive,
            detail=f"the instrument never claimed {subject}",
        ),
        ratio(
            "recall",
            true_positive,
            true_positive + false_negative,
            detail=f"gold never carries {subject}",
        ),
        ratio(
            "f1",
            2 * true_positive,
            2 * true_positive + false_positive + false_negative,
            detail=f"neither the instrument nor gold ever carries {subject}",
        ),
    ]
    return rates, counts


# -- reading the two sides ---------------------------------------------------


def instrument_applicability(judgment: Mapping[str, Any]) -> str:
    """What this pass stated about whether the rule governed the text.

    Read from the queue's judgment summary, which carries the applicability each
    pass stated for judged and declined units alike. Never derived from a label:
    a derivation would silently import the agreement report's fallback map, whose
    ``hard_negative`` reading is the opposite of :data:`GOLD_APPLICABILITY`.
    """
    stated = judgment.get("applicability")
    if stated not in APPLICABILITY_STATES:
        raise UsageError(
            f"queue judgment states applicability {stated!r}, which is not one of "
            f"{APPLICABILITY_STATES}; the queue is the record of what each pass "
            "answered and a value this tool cannot read is a data defect"
        )
    return str(stated)


def instrument_outcome(judgment: Mapping[str, Any]) -> str:
    """The instrument's decision on one unit, as a single outcome class.

    A judged unit reports its label. A declined unit reports
    ``declined_<applicability>``, so a refusal to judge stays visible as a
    refusal instead of being counted as some label the pass never chose.
    """
    if judgment.get("kind") == "judged":
        label = judgment.get("label")
        if label not in LABELS:
            raise UsageError(f"queue judgment carries label {label!r}, which is not in {LABELS}")
        return str(label)
    return f"declined_{instrument_applicability(judgment)}"


def decision_matches(judgment: Mapping[str, Any], disposition: str) -> bool:
    """Whether this pass's decision agrees with the operator's disposition.

    A decline never matches: it states no disposition, and every in-scope gold
    row states one. See the module docstring.
    """
    if judgment.get("kind") != "judged":
        return False
    return LABEL_TO_GOLD_DISPOSITION[str(judgment["label"])] == disposition


def gold_applicability(disposition: str) -> str:
    """The applicability class gold implies, refusing an unmapped disposition."""
    if disposition not in GOLD_APPLICABILITY:
        raise UsageError(
            f"{disposition!r} has no applicability reading; add it to GOLD_APPLICABILITY "
            "deliberately, because an unmapped disposition would otherwise drop out of "
            "the precision denominator without anyone deciding that it should"
        )
    return GOLD_APPLICABILITY[disposition]


def operator_tokens(
    row: Mapping[str, Any], target: str
) -> frozenset[tuple[str, int]]:
    """The operator's evidence as character-position tokens.

    Same token definition as :func:`ats.corpus.agreement.span_tokens`: a token is
    the pair ``(target, offset)`` and a half-open ``[start, end)`` pair
    contributes ``end - start`` of them, so two adjacent spans never double-count
    the boundary character.

    ``evidence_offsets`` carries no target of its own -- the operator adjudicates
    one unit whose source is one text -- so the caller supplies the target the
    instrument's spans are keyed against. Projecting the offsets onto that target
    is what makes the intersection meaningful; a unit where the instrument's
    spans have no single target is excluded rather than scored against a
    guaranteed empty overlap.
    """
    tokens: set[tuple[str, int]] = set()
    for pair in row.get("evidence_offsets") or ():
        start, end = int(pair[0]), int(pair[1])
        if end < start:
            raise UsageError(
                f"operator record for {row.get('unit_id')!r} cites an offset pair ending "
                f"before it begins ({start}, {end})"
            )
        tokens.update((target, offset) for offset in range(start, end))
    return frozenset(tokens)


def _span_target(judgment: Mapping[str, Any]) -> str | None:
    """The single target this judgment's character spans are keyed against."""
    spans = judgment.get("evidence_spans") or []
    if not spans:
        return None
    targets = {str(span.get("source_sha256") or judgment.get("example_id")) for span in spans}
    return targets.pop() if len(targets) == 1 else None


# -- coverage ----------------------------------------------------------------


def coverage_rows(
    queue: Mapping[str, Any], rows: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> list[dict[str, Any]]:
    """Adjudicated against required, per unit kind. The top-level coverage claim."""
    kinds = sorted({str(unit["kind"]) for unit in queue.get("units", ())})
    out: list[dict[str, Any]] = []
    for kind in kinds:
        units = [u for u in queue["units"] if u["kind"] == kind]
        adjudicated = [u for u in units if gold_disposition(rows.get(u["unit_id"], {})) is not None]
        started = [u for u in units if rows.get(u["unit_id"])]
        excluded = [
            u
            for u in adjudicated
            if gold_disposition(rows[u["unit_id"]]) == "excluded"
        ]
        out.append(
            {
                "unit_kind": kind,
                "required": len(units),
                "adjudicated": len(adjudicated),
                "source_only_awaiting_review": len(started) - len(adjudicated),
                "unstarted": len(units) - len(started),
                "excluded_by_operator": len(excluded),
                "scored": len(adjudicated) - len(excluded),
                "complete": len(adjudicated) == len(units),
            }
        )
    return out


def exposure_join(
    gold_path: str | Path, queue: Mapping[str, Any]
) -> tuple[dict[str, str], dict[str, Any]]:
    """Blinding breaches joined from the exposure log, keyed by unit id.

    The log beside the gold file is the authority, never the row field: a gold
    row recorded before its breach was logged carries no ``prior_exposure``
    block, so a consumer trusting the row field scores a breached unit as clean,
    which is exactly the outcome the exposure apparatus is built to prevent.

    Returns ``(exposed_by_unit, report_block)``. Log entries naming units
    outside the queue are ignored here; they are not this report's units.
    """
    log_path = Path(gold_path).parent / "exposure_log.json"
    unit_ids = {str(unit["unit_id"]) for unit in queue.get("units", ())}
    if not log_path.is_file():
        return {}, {
            "log_available": False,
            "log_path": None,
            "exposed_units": [],
            "exposed_in_scored_set": 0,
            "note": (
                "no exposure log exists beside the gold file; absence of the log is "
                "read as no recorded breach, which is only as true as the session "
                "discipline that maintains the log"
            ),
        }
    log = load_json(log_path)
    exposed: dict[str, str] = {}
    for entry in log.get("exposures", ()):
        unit_id = str(entry.get("unit_id"))
        if unit_id in unit_ids and unit_id not in exposed:
            exposed[unit_id] = str(entry.get("code"))
    block = {
        "log_available": True,
        "log_path": str(log_path),
        "exposed_units": [
            {"unit_id": unit_id, "code": code} for unit_id, code in sorted(exposed.items())
        ],
        "exposed_in_scored_set": 0,  # filled in by the report builder
        "note": (
            "joined from the log by unit_id; the row-level prior_exposure field is a "
            "convenience copy attached at record time and is not consulted, because a "
            "row recorded before its breach was logged carries none"
        ),
    }
    return exposed, block


def _require_coverage(rows: Sequence[Mapping[str, Any]], *, gold_present: bool) -> None:
    """Refuse the report unless every queue unit carries a disagreement review."""
    if all(row["complete"] for row in rows) and gold_present:
        return
    adjudicated = sum(row["adjudicated"] for row in rows)
    required = sum(row["required"] for row in rows)
    breakdown = ", ".join(
        f"{row['unit_kind']} {row['adjudicated']}/{row['required']}" for row in rows
    )
    lead = (
        "no operator gold exists"
        if not gold_present
        else "operator gold does not cover every queue unit"
    )
    raise GoldIncomplete(
        f"{lead}: {adjudicated}/{required} unit(s) carry a disagreement review "
        f"({breakdown}). Instrument validity is measured against the operator's "
        "disposition, so a report generated now would name a measurement nobody "
        "made; the unmet condition belongs in the milestone gate, not in a "
        "published report whose every metric is unavailable.",
        rows,
    )


# -- per-instrument metrics --------------------------------------------------


def _applicability_metric(
    scored: Sequence[tuple[Mapping[str, Any], str, Mapping[str, Any]]], role: str
) -> dict[str, Any]:
    pairs = [
        (instrument_applicability(judgment), gold_applicability(disposition))
        for _, disposition, judgment in scored
    ]
    metric = _metric(
        "applicability",
        "Does this pass decide that the rule governs the text where the operator "
        "decides it does?",
        "one in-scope conformance unit",
        n=len(pairs),
        reason=None
        if pairs
        else unavailable(
            "no_unit_satisfied_condition",
            f"instrument {role} has no in-scope conformance unit to compare",
        ),
        notes=[
            "Gold applicability is derived from final_disposition by "
            "ats.corpus.validity.GOLD_APPLICABILITY. hard_negative reads as applicable "
            "here, which is the opposite of the agreement report's label fallback; the "
            "module docstring states why both are correct for their own question.",
            "insufficient_context and ambiguous_by_design are a retained third class "
            "(undetermined), not an exclusion, so an instrument asserting applicability "
            "on a unit the operator found undecidable pays for it in precision.",
        ],
    )
    if not pairs:
        return metric
    metric["confusion"] = _confusion(pairs, APPLICABILITY_STATES, APPLICABILITY_STATES)
    metric["per_class"] = _per_class(pairs, APPLICABILITY_STATES)
    return metric


def _label_accuracy_metric(
    scored: Sequence[tuple[Mapping[str, Any], str, Mapping[str, Any]]], role: str
) -> dict[str, Any]:
    both = [
        (judgment, disposition)
        for _, disposition, judgment in scored
        if judgment.get("kind") == "judged" and gold_applicability(disposition) == "applicable"
    ]
    pairs = [(str(j["label"]), d) for j, d in both]
    metric = _metric(
        "label_accuracy_given_both_applicable",
        "Where both this pass and the operator hold that the rule applies, do they "
        "reach the same label?",
        "one conformance unit this pass judged and the operator found applicable",
        n=len(pairs),
        reason=None
        if pairs
        else unavailable(
            "no_unit_satisfied_condition",
            f"instrument {role} judged no unit whose gold disposition is applicable",
        ),
        notes=[
            "Conditional on both sides holding the rule applicable, so it is not "
            "inflated by the units where the modal answer is that no rule applies.",
            "The instrument's `ambiguous` is compared against gold's "
            "`ambiguous_by_design` via LABEL_TO_GOLD_DISPOSITION: one claim, two "
            "vocabularies. Under this condition gold is never ambiguous_by_design, so "
            "an ambiguous row here is always a mismatch, which is what the separate "
            "ambiguity metric measures without the condition.",
        ],
    )
    if not pairs:
        return metric
    columns = [d for d in SCORED_DISPOSITIONS if gold_applicability(d) == "applicable"]
    observed = sorted({d for _, d in pairs}.difference(columns))
    metric["confusion"] = _confusion(pairs, LABELS, [*columns, *observed])
    metric["per_class"] = _per_class(pairs, LABELS)
    metric["rates"] = [
        ratio(
            "accuracy",
            sum(1 for label, disposition in pairs if LABEL_TO_GOLD_DISPOSITION[label] == disposition),
            len(pairs),
            detail="no unit satisfied the both-applicable condition",
        )
    ]
    return metric


def _claim_metric(
    scored: Sequence[tuple[Mapping[str, Any], str, Mapping[str, Any]]],
    *,
    name: str,
    question: str,
    instrument_label: str,
    gold_value: str,
    role: str,
    notes: Sequence[str],
) -> dict[str, Any]:
    """One binary instrument claim against one gold disposition."""
    flags = [
        (
            judgment.get("kind") == "judged" and judgment.get("label") == instrument_label,
            disposition == gold_value,
        )
        for _, disposition, judgment in scored
    ]
    metric = _metric(
        name,
        question,
        "one in-scope conformance unit",
        n=len(flags),
        reason=None
        if flags
        else unavailable(
            "no_unit_satisfied_condition",
            f"instrument {role} has no in-scope conformance unit to compare",
        ),
        notes=notes,
    )
    if not flags:
        return metric
    rates, counts = _binary_rates(flags, f"{instrument_label!r}/{gold_value!r}")
    metric["rates"] = rates
    metric["counts"] = counts
    return metric


def _evidence_metric(
    scored: Sequence[tuple[Mapping[str, Any], str, Mapping[str, Any]]],
    *,
    role: str,
    round_available: bool,
    spans_by_unit: Mapping[str, Mapping[str, Any]],
    operator_rows: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Token F1 between this pass's evidence spans and the operator's offsets."""
    notes = [
        "A token is one character position, identified by (target, offset); a character "
        "span [start, end) contributes end - start tokens. The definition is "
        "ats.corpus.agreement.span_tokens, reused rather than restated.",
        "The operator's evidence_offsets carry no target. They are projected onto the "
        "single target this pass's spans are keyed against; a unit whose spans have no "
        "single target is excluded rather than scored against an overlap that is empty "
        "by construction.",
        "raw F1 is micro-pooled over scored units, so a unit citing one character does "
        "not weigh as much as a unit citing a paragraph.",
    ]
    if not round_available:
        metric = _metric(
            "evidence_span_token_f1",
            "When this pass points at the text, does it point where the operator points?",
            "one in-scope conformance unit where both sides cited characters",
            n=0,
            reason=unavailable(
                "rounds_absent",
                f"annotation round {role} was not present, so instrument {role} has no "
                "evidence spans to compare",
            ),
            notes=notes,
        )
        metric["operator_evidence"] = {
            "units_with_operator_offsets": 0,
            "from_disagreement_review": 0,
            "from_source_only": 0,
        }
        metric["exclusions"] = []
        return metric

    true_positive = false_positive = false_negative = 0
    per_unit: list[Fraction] = []
    excluded: dict[str, int] = {}
    scored_units = 0
    with_operator = 0
    by_stage = {"disagreement_review": 0, "source_only": 0}

    for unit, _, _ in scored:
        unit_id = str(unit["unit_id"])
        stages = operator_rows.get(unit_id, {})
        source_row: Mapping[str, Any] | None = None
        for stage in ("disagreement_review", "source_only"):
            candidate = stages.get(stage)
            if candidate and candidate.get("evidence_offsets"):
                source_row = candidate
                by_stage[stage] += 1
                break
        if source_row is None:
            excluded["operator_cited_nothing"] = excluded.get("operator_cited_nothing", 0) + 1
            continue
        with_operator += 1

        judgment = spans_by_unit.get(unit_id)
        if judgment is None:
            excluded["pass_left_no_judgment"] = excluded.get("pass_left_no_judgment", 0) + 1
            continue
        tokens, _convention = span_tokens(judgment)
        if tokens is None:
            excluded["span_not_character_addressed"] = (
                excluded.get("span_not_character_addressed", 0) + 1
            )
            continue
        target = _span_target(judgment)
        if tokens and target is None:
            excluded["no_single_span_target"] = excluded.get("no_single_span_target", 0) + 1
            continue
        operator = operator_tokens(source_row, target or unit_id)
        if not operator and not tokens:
            excluded["neither_side_cited"] = excluded.get("neither_side_cited", 0) + 1
            continue
        overlap = len(operator & tokens)
        true_positive += overlap
        false_positive += len(tokens) - overlap
        false_negative += len(operator) - overlap
        per_unit.append(Fraction(2 * overlap, len(operator) + len(tokens)))
        scored_units += 1

    exclusion_detail = {
        "operator_cited_nothing": (
            "the operator recorded no evidence_offsets on either stage of this unit, so "
            "there is no operator span to overlap with"
        ),
        "pass_left_no_judgment": (
            "this pass declined the unit, so it left no evidence span; scoring the "
            "decline as zero overlap would conflate refusing to look with pointing "
            "at the wrong characters"
        ),
        "span_not_character_addressed": (
            "at least one cited span is a line range, locator, or JSON pointer, which "
            "carries no character offsets to tokenise"
        ),
        "no_single_span_target": (
            "this pass's spans are keyed against more than one target, so the operator's "
            "untargeted offsets cannot be projected onto one of them"
        ),
        "neither_side_cited": (
            "neither side cited a character, so there is no overlap to score; scoring "
            "this as 1.0 would reward citing nothing"
        ),
    }
    metric = _metric(
        "evidence_span_token_f1",
        "When this pass points at the text, does it point where the operator points?",
        "one in-scope conformance unit where both sides cited characters",
        n=scored_units,
        reason=None,
        notes=notes,
    )
    metric["operator_evidence"] = {
        "units_with_operator_offsets": with_operator,
        "from_disagreement_review": by_stage["disagreement_review"],
        "from_source_only": by_stage["source_only"],
    }
    metric["exclusions"] = [
        {"reason": reason, "count": count, "detail": exclusion_detail[reason]}
        for reason, count in sorted(excluded.items())
    ]
    denominator = 2 * true_positive + false_positive + false_negative
    if scored_units == 0 or denominator == 0:
        metric["available"] = False
        metric["unavailable_reason"] = unavailable(
            "no_operator_evidence" if with_operator == 0 else "no_spans_comparable",
            f"{with_operator} unit(s) carried operator offsets and {scored_units} were "
            "scored, leaving no cited character to compare",
        )
        return metric
    metric["rates"] = [
        ratio(
            "micro_token_f1",
            2 * true_positive,
            denominator,
            detail="no character was cited on either side",
        ),
        ratio(
            "precision",
            true_positive,
            true_positive + false_positive,
            detail="this pass cited no character on any scored unit",
        ),
        ratio(
            "recall",
            true_positive,
            true_positive + false_negative,
            detail="the operator cited no character on any scored unit",
        ),
        ratio(
            "units_scored_of_units_considered",
            scored_units,
            scored_units + sum(excluded.values()),
            detail="no unit was considered",
        ),
    ]
    metric["macro_token_f1"] = _num(Fraction(sum(per_unit), len(per_unit)))
    return metric


def _calibration_metric(
    scored: Sequence[tuple[Mapping[str, Any], str, Mapping[str, Any]]], role: str
) -> dict[str, Any]:
    """Accuracy within each declared confidence bin. An empty bin is unavailable."""
    judged = [
        (judgment, disposition)
        for _, disposition, judgment in scored
        if judgment.get("kind") == "judged"
    ]
    declined = len(scored) - len(judged)
    metric = _metric(
        "confidence_calibration",
        "When this pass declares a confidence level, how often is its label the "
        "operator's disposition?",
        "one in-scope conformance unit this pass judged, grouped by declared confidence",
        n=len(judged),
        reason=None
        if judged
        else unavailable(
            "instrument_never_judged",
            f"instrument {role} declined every in-scope conformance unit, so it declared "
            "no confidence",
        ),
        notes=[
            "annotation_confidence is confidence in the label. It is not ATS assessment "
            "confidence and is not rendered as such (spec Sections 4.8, 4.9, 13.5).",
            "A bin the instrument never used reports an unavailability. A 0.0 there "
            "would assert the instrument is always wrong when it is confident that way, "
            "which is a measurement nobody made (ADR-0002).",
            f"{declined} in-scope unit(s) were declined and carry no confidence, so they "
            "are outside every bin rather than being counted in the weakest one.",
        ],
    )
    unknown = sorted(
        {str(j.get("annotation_confidence")) for j, _ in judged}.difference(CONFIDENCE_BINS)
    )
    bins: list[dict[str, Any]] = []
    for level in [*CONFIDENCE_BINS, *unknown]:
        members = [(j, d) for j, d in judged if str(j.get("annotation_confidence")) == level]
        matches = sum(1 for j, d in members if decision_matches(j, d))
        bins.append(
            {
                "confidence": level,
                "n": len(members),
                "matches": matches,
                "accuracy": ratio(
                    "accuracy",
                    matches,
                    len(members),
                    detail=f"instrument {role} never declared confidence {level!r} on an "
                    "in-scope unit",
                    code="confidence_bin_empty",
                ),
            }
        )
    metric["bins"] = bins
    metric["declined_without_confidence"] = declined
    return metric


def _error_type_by_rule(
    scored: Sequence[tuple[Mapping[str, Any], str, Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """Per-rule instrument-versus-gold mismatch counts, by outcome pair."""
    by_rule: dict[str, list[tuple[Mapping[str, Any], str]]] = {}
    for unit, disposition, judgment in scored:
        by_rule.setdefault(str(unit["rule_id"]), []).append((judgment, disposition))
    rows: list[dict[str, Any]] = []
    for rule_id, members in sorted(by_rule.items()):
        matches = sum(1 for j, d in members if decision_matches(j, d))
        pairs: dict[tuple[str, str], int] = {}
        for judgment, disposition in members:
            if decision_matches(judgment, disposition):
                continue
            key = (instrument_outcome(judgment), disposition)
            pairs[key] = pairs.get(key, 0) + 1
        rows.append(
            {
                "rule_id": rule_id,
                "n": len(members),
                "matches": matches,
                "mismatches": len(members) - matches,
                "mismatch_rate": ratio(
                    "mismatch_rate",
                    len(members) - matches,
                    len(members),
                    detail=f"{rule_id} has no in-scope unit",
                ),
                "by_outcome_pair": [
                    {"instrument": instrument, "gold": gold, "count": count}
                    for (instrument, gold), count in sorted(pairs.items())
                ],
            }
        )
    return rows


def _instrument_block(
    role: str,
    *,
    scored: Sequence[tuple[Mapping[str, Any], str, Mapping[str, Any]]],
    round_available: bool,
    spans_by_unit: Mapping[str, Mapping[str, Any]],
    operator_rows: Mapping[str, Mapping[str, Mapping[str, Any]]],
    annotator_id: str | None,
) -> dict[str, Any]:
    return {
        "role": role,
        "annotator_id": annotator_id,
        "units_scored": len(scored),
        "metrics": [
            _applicability_metric(scored, role),
            _label_accuracy_metric(scored, role),
            _claim_metric(
                scored,
                name="ambiguity",
                question="Does this pass call the text ambiguous where the operator "
                "finds it ambiguous by design?",
                instrument_label="ambiguous",
                gold_value="ambiguous_by_design",
                role=role,
                notes=[
                    "Unconditional on applicability, because an ambiguity claim is a "
                    "claim about the prose rather than about scope.",
                    "A declined unit counts as not claiming ambiguity, which is what a "
                    "decline is: the pass stated no ambiguity.",
                ],
            ),
            _claim_metric(
                scored,
                name="context_insufficiency",
                question="Does this pass report insufficient context where the operator "
                "adjudicates insufficient_context?",
                instrument_label="insufficient_context",
                gold_value="insufficient_context",
                role=role,
                notes=[
                    "The instrument side is the `insufficient_context` label, not the "
                    "stated context_sufficiency rating. The rating is a three-point "
                    "scale on which `partial` is not a refusal to judge, so reading "
                    "insufficiency out of it would count hedged judgments as refusals.",
                ],
            ),
            _evidence_metric(
                scored,
                role=role,
                round_available=round_available,
                spans_by_unit=spans_by_unit,
                operator_rows=operator_rows,
            ),
            _calibration_metric(scored, role),
        ],
        "error_type_by_rule": _error_type_by_rule(scored),
    }


# -- profile reconnaissance --------------------------------------------------


def _profile_block(
    annotator_id: str,
    pairs: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    metric = _metric(
        "profile_classification",
        "Does this reconnaissance pass classify the section's profile as the operator "
        "adjudicates it?",
        "one in-scope profile-reconnaissance unit",
        n=len(pairs),
        reason=None
        if pairs
        else unavailable(
            "no_unit_satisfied_condition",
            f"{annotator_id} classified no in-scope profile unit",
        ),
        notes=[
            "Scored against the six-value reconnaissance vocabulary, which is the same "
            "vocabulary the passes answered in, so adjudicated gold and the instrument "
            "answer one question rather than two.",
            "Reported separately from the conformance instruments: a profile "
            "classification and a conformance label are different decisions and a "
            "combined figure would describe neither.",
        ],
    )
    if pairs:
        metric["confusion"] = _confusion(pairs, PROFILE_DISPOSITIONS, PROFILE_DISPOSITIONS)
        metric["per_class"] = _per_class(pairs, PROFILE_DISPOSITIONS)
        metric["rates"] = [
            ratio(
                "accuracy",
                sum(1 for instrument, gold in pairs if instrument == gold),
                len(pairs),
                detail="no in-scope profile unit was classified",
            )
        ]
    return {
        "annotator_id": annotator_id,
        "units_scored": len(pairs),
        "metrics": [metric],
    }


# -- framing -----------------------------------------------------------------


def _cross_reference(path: str | Path | None) -> dict[str, Any]:
    """The supplied agreement report's identity, or a typed absence."""
    if path is None:
        return {
            "path": None,
            "available": False,
            "schema_version": None,
            "report_sha256": None,
            "unavailable_reason": unavailable(
                "agreement_report_absent", "no agreement report path was supplied"
            ),
        }
    source = Path(path)
    if not source.is_file():
        return {
            "path": str(path),
            "available": False,
            "schema_version": None,
            "report_sha256": None,
            "unavailable_reason": unavailable(
                "agreement_report_absent", f"{path} does not exist"
            ),
        }
    document = load_json(source)
    return {
        "path": str(path),
        "available": True,
        "schema_version": str(document.get("schema_version")),
        "report_sha256": str(document.get("report_sha256")),
        "unavailable_reason": None,
    }


def _measurements(reference: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The three measurement kinds, and which document establishes each."""
    reproducibility = (
        "How repeatably instrument {role}'s procedure answers the same unit. This "
        "document does not establish it. Reproducibility is cross-referenced to "
        "the supplied agreement report by content address; that report compares "
        "a against b, so it bounds the two instruments jointly and instrument "
        "{role}'s reproducibility is not separable from the other's. Do not read "
        "a validity figure below as a reproducibility figure: an instrument can "
        "reproduce itself perfectly and be wrong every time."
    )
    rows = [
        {
            "kind": f"instrument_{role}_reproducibility",
            "role": role,
            "established_by": "cross_reference",
            "separable_by_instrument": False,
            "statement": reproducibility.format(role=role),
            "cross_reference": dict(reference),
        }
        for role in ROLES
    ]
    rows.append(
        {
            "kind": "instrument_to_operator_validity",
            "role": None,
            "established_by": "this_report",
            "separable_by_instrument": True,
            "statement": (
                "Whether each pass reaches the disposition the operator adjudicated. "
                "Gold is operator-authored and the record refuses a non-human "
                "adjudicator, so this is the instrument measured against the standard "
                "rather than against another correlated reading of the rubric. Each "
                "instrument is scored against gold on its own; the two are never pooled."
            ),
            "cross_reference": None,
        }
    )
    return rows


# -- report ------------------------------------------------------------------


def build_validity_report(
    ctx: Any,
    *,
    queue: str | Path,
    gold: str | Path,
    round_a: str | Path | None = None,
    round_b: str | Path | None = None,
    agreement_report: str | Path | None = None,
    allow_partial: bool = False,
) -> dict[str, Any]:
    """Score both annotation instruments against caller-supplied adjudication.

    Raises :class:`GoldIncomplete` unless every queue unit carries a disagreement
    review, or ``allow_partial`` is set. The queue itself is a supplied
    artefact, so its absence is an ordinary :class:`~ats.errors.UsageError`.

    ``round_a`` and ``round_b`` supply evidence spans, which the queue's
    judgment summaries deliberately do not carry. The rounds' labels are
    cross-checked against the queue's summaries: a disagreement is a blocking
    finding, never reconciled silently.
    """
    queue_path = Path(queue)
    if not queue_path.is_file():
        raise UsageError(
            f"{queue_path} does not exist; the adjudication queue is a committed "
            "artefact and validity cannot be scored without the record naming the units"
        )
    queue_doc = load_json(queue_path)

    gold_path = Path(gold)
    gold_present = gold_path.is_file()
    rows = load_gold(gold_path, queue_doc) if gold_present else {}
    coverage = coverage_rows(queue_doc, rows)
    exposed_by_unit, exposure_block = exposure_join(gold_path, queue_doc)
    if not allow_partial:
        _require_coverage(coverage, gold_present=gold_present)

    findings: list[dict[str, str]] = []
    partial = not gold_present or not all(row["complete"] for row in coverage)
    if partial:
        adjudicated = sum(row["adjudicated"] for row in coverage)
        required = sum(row["required"] for row in coverage)
        findings.append(
            {
                "code": "gold_partial",
                "severity": "blocking",
                "subject": "adjudicated gold",
                "detail": (
                    f"{adjudicated}/{required} queue unit(s) carry a disagreement "
                    "review. Every metric below is computed over the adjudicated subset "
                    "only, and its n says which; no figure here describes the supplied "
                    "units."
                ),
            }
        )

    # Evidence spans come from the rounds, which the queue summaries omit.
    spans: dict[str, dict[str, Mapping[str, Any]]] = {role: {} for role in ROLES}
    round_available = {role: False for role in ROLES}
    annotator_ids: dict[str, str | None] = {role: None for role in ROLES}
    for role, path in (("a", round_a), ("b", round_b)):
        if path is None or not Path(path).is_file():
            findings.append(
                {
                    "code": "round_unavailable",
                    "severity": "concern",
                    "subject": f"round {role}",
                    "detail": (
                        f"{path} was not read, so instrument {role}'s evidence spans "
                        "could not be compared with the operator's offsets. Every other "
                        "metric for this instrument comes from the sealed queue and is "
                        "unaffected."
                    ),
                }
            )
            continue
        round_available[role] = True
        by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
        ids: set[str] = set()
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            judgment = json.loads(line)
            by_key[(str(judgment["example_id"]), str(judgment["rule_id"]))] = judgment
            ids.add(str(judgment.get("annotator_id")))
        annotator_ids[role] = sorted(ids)[0] if len(ids) == 1 else None
        for unit in queue_doc["units"]:
            if unit["kind"] != "conformance":
                continue
            judgment = by_key.get((str(unit["bundle_id"]), str(unit["rule_id"])))
            if judgment is None:
                continue
            spans[role][str(unit["unit_id"])] = judgment
            summary = unit["judgments"].get(role, {})
            if summary.get("kind") == "judged" and summary.get("label") != judgment.get("label"):
                findings.append(
                    {
                        "code": "round_queue_label_mismatch",
                        "severity": "blocking",
                        "subject": f"{unit['unit_id']} round {role}",
                        "detail": (
                            f"the queue records label {summary.get('label')!r} and "
                            f"{path} records {judgment.get('label')!r}. One of the two "
                            "documents is stale; neither is reconciled here, because "
                            "choosing silently would publish the stale one."
                        ),
                    }
                )

    # The scored set: conformance units with a disagreement review that is not
    # the operator excluding the unit from gold.
    scored: dict[str, list[tuple[Mapping[str, Any], str, Mapping[str, Any]]]] = {
        role: [] for role in ROLES
    }
    missing_role: set[str] = set()
    for unit in queue_doc["units"]:
        if unit["kind"] != "conformance":
            continue
        disposition = gold_disposition(rows.get(str(unit["unit_id"]), {}))
        if disposition is None or disposition == "excluded":
            continue
        for role in ROLES:
            judgment = unit["judgments"].get(role)
            if judgment is None:
                missing_role.add(f"{unit['unit_id']} role {role}")
                continue
            scored[role].append((unit, disposition, judgment))
    if missing_role:
        findings.append(
            {
                "code": "unit_missing_instrument",
                "severity": "blocking",
                "subject": "adjudication queue",
                "detail": (
                    f"{len(missing_role)} in-scope unit(s) carry no judgment summary for "
                    "one of the two instruments, so that instrument is scored over fewer "
                    "units than the other: " + ", ".join(sorted(missing_role)[:5])
                ),
            }
        )

    # Every scored unit that the exposure log names is counted and surfaced as
    # a finding: those judgments are still gold, but gold with a named caveat,
    # and a report that averaged them in silently would erase the caveat.
    scored_unit_ids = {
        str(unit["unit_id"])
        for role in ROLES
        for unit, _disposition, _judgment in scored[role]
    }
    exposed_scored = sorted(scored_unit_ids & set(exposed_by_unit))
    exposure_block["exposed_in_scored_set"] = len(exposed_scored)
    if exposed_scored:
        findings.append(
            {
                "code": "exposed_units_in_scored_set",
                "severity": "concern",
                "subject": "adjudicated gold",
                "detail": (
                    f"{len(exposed_scored)} scored unit(s) carry a logged blinding "
                    "breach (joined from the exposure log, not the row field): "
                    + ", ".join(unit_id[:44] for unit_id in exposed_scored[:5])
                    + ". Their metrics are computed and reported like any other unit; "
                    "a consumer weighting for exposure filters on the report's "
                    "exposure block."
                ),
            }
        )

    instruments = [
        _instrument_block(
            role,
            scored=scored[role],
            round_available=round_available[role],
            spans_by_unit=spans[role],
            operator_rows=rows,
            annotator_id=annotator_ids[role],
        )
        for role in ROLES
    ]

    profile_pairs: dict[str, list[tuple[str, str]]] = {}
    for unit in queue_doc["units"]:
        if unit["kind"] != "profile":
            continue
        disposition = gold_disposition(rows.get(str(unit["unit_id"]), {}))
        if disposition is None or disposition == "excluded":
            continue
        for annotator_id, vote in sorted(unit["judgments"].items()):
            classification = str(vote.get("classification"))
            if classification not in PROFILE_DISPOSITIONS:
                raise UsageError(
                    f"{unit['unit_id']} records reconnaissance classification "
                    f"{classification!r}, which is not in {PROFILE_DISPOSITIONS}"
                )
            profile_pairs.setdefault(annotator_id, []).append((classification, disposition))
    profile_instruments = [
        _profile_block(annotator_id, pairs) for annotator_id, pairs in sorted(profile_pairs.items())
    ]
    if not profile_instruments:
        findings.append(
            {
                "code": "no_profile_unit_adjudicated",
                "severity": "concern",
                "subject": "profile reconnaissance",
                "detail": (
                    "no profile-reconnaissance unit carries a scoreable disagreement "
                    "review, so the reconnaissance instruments are unmeasured; no "
                    "profile verdict is established"
                ),
            }
        )

    reference = _cross_reference(agreement_report)
    if not reference["available"]:
        findings.append(
            {
                "code": "reproducibility_not_cross_referenced",
                "severity": "concern",
                "subject": "supplied agreement report",
                "detail": reference["unavailable_reason"]["detail"]
                + "; the reproducibility framing is stated but unbound, so a reader "
            }
        )

    blocking = [f for f in findings if f["severity"] == "blocking"]
    if partial or not any(block["units_scored"] for block in instruments):
        status = "insufficient_evidence"
    elif blocking:
        status = "blocking_concerns"
    elif findings:
        status = "concerns_present"
    else:
        status = "no_concerns_detected"

    reasons: list[str] = []
    if partial:
        reasons.append(
            "gold does not cover every queue unit, so every figure describes the "
            "adjudicated subset and none describes the corpus"
        )
    if not any(block["units_scored"] for block in instruments):
        reasons.append(
            "no in-scope conformance unit was scored, so no metric here is evidence "
            "of anything"
        )
    for finding in sorted(blocking, key=lambda f: (f["code"], f["subject"])):
        reasons.append(f"{finding['code']}: {finding['subject']}")
    if not reasons:
        reasons.append(
            "every metric was computable over complete gold; this is a statement about "
            "each instrument's agreement with the operator, per instrument, and about "
            "nothing pooled across them"
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "report_sha256": "",
        "generated_at": ctx.timestamp(),
        "spec_version": ctx.spec_version,
        "implementation": ctx.implementation,
        "measurements": _measurements(reference),
        "queue": {
            "path": str(queue_path),
            "queue_id": str(queue_doc["queue_id"]),
            "record_sha256": str(queue_doc["record_sha256"]),
        },
        "gold": {
            "path": str(gold_path),
            "available": gold_present,
            "file_sha256": sha256_hex(gold_path.read_bytes()) if gold_present else None,
            "records": sum(len(stages) for stages in rows.values()),
            "unavailable_reason": None
            if gold_present
            else unavailable("gold_partial", f"{gold_path} does not exist"),
        },
        "coverage": {
            "partial": partial,
            "allow_partial": allow_partial,
            "adjudicated": sum(row["adjudicated"] for row in coverage),
            "required": sum(row["required"] for row in coverage),
            "by_unit_kind": coverage,
            "statement": (
                "Coverage is stated at the top level because a partial report is the "
                "only kind that can mislead: every metric below carries the n it was "
                "computed over, and every ratio carries its numerator and denominator, "
                "so no figure can be read as covering units the adjudicator has not "
                "adjudicated."
            ),
        },
        "exposure": exposure_block,
        "vocabularies": {
            "instrument_labels": list(LABELS),
            "gold_dispositions": list(SCORED_DISPOSITIONS),
            "profile_dispositions": list(PROFILE_DISPOSITIONS),
            "applicability_classes": list(APPLICABILITY_STATES),
            "confidence_bins": list(CONFIDENCE_BINS),
            "gold_applicability_map": [
                {"gold_disposition": key, "applicability_class": value}
                for key, value in sorted(GOLD_APPLICABILITY.items())
            ],
            "label_equivalence": [
                {"instrument_label": key, "gold_disposition": value}
                for key, value in sorted(LABEL_TO_GOLD_DISPOSITION.items())
            ],
            "unavailability_codes": [
                {"code": code, "meaning": meaning}
                for code, meaning in sorted(UNAVAILABLE_REASONS.items())
            ],
        },
        "instruments": instruments,
        "profile_instruments": profile_instruments,
        "findings": sorted(
            findings, key=lambda f: (f["severity"], f["code"], f["subject"], f["detail"])
        ),
        "assessment": {
            "status": status,
            "reasons": reasons,
            "pooled_refusal": POOLED_REFUSAL,
        },
    }
    sealed = seal(report)
    ctx.schemas.validate_document(sealed)
    return sealed


def summarise(report: Mapping[str, Any]) -> list[str]:
    """Terminal lines, per instrument. Never one number across the two."""
    lines: list[str] = []
    cov = report["coverage"]
    lines.append(
        f"gold coverage: {cov['adjudicated']}/{cov['required']} unit(s)"
        + (" (PARTIAL)" if cov["partial"] else "")
    )
    for block in report["instruments"]:
        lines.append("")
        lines.append(f"instrument {block['role']} — {block['units_scored']} unit(s) scored")
        for metric in block["metrics"]:
            if not metric["available"]:
                lines.append(
                    f"  {metric['metric']:38} UNAVAILABLE "
                    f"({metric['unavailable_reason']['code']})"
                )
                continue
            rendered = ", ".join(
                f"{rate['name']}="
                + (
                    f"{rate['value']:.3f} [{rate['numerator']}/{rate['denominator']}]"
                    if rate["available"]
                    else f"UNAVAILABLE ({rate['unavailable_reason']['code']})"
                )
                for rate in metric["rates"]
            )
            lines.append(f"  {metric['metric']:38} n={metric['n']:<4} {rendered}")
            for entry in metric["bins"]:
                rate = entry["accuracy"]
                value = (
                    f"{rate['value']:.3f} [{rate['numerator']}/{rate['denominator']}]"
                    if rate["available"]
                    else f"UNAVAILABLE ({rate['unavailable_reason']['code']})"
                )
                lines.append(f"    confidence {entry['confidence']:10} n={entry['n']:<4} {value}")
    for block in report["profile_instruments"]:
        lines.append("")
        lines.append(
            f"reconnaissance {block['annotator_id']} — {block['units_scored']} unit(s) scored"
        )
        for metric in block["metrics"]:
            for rate in metric["rates"]:
                lines.append(
                    f"  {rate['name']:38} "
                    + (
                        f"{rate['value']:.3f} [{rate['numerator']}/{rate['denominator']}]"
                        if rate["available"]
                        else f"UNAVAILABLE ({rate['unavailable_reason']['code']})"
                    )
                )
    return lines


def iter_blocking(report: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    """The findings that stop this report from reading as success."""
    return (f for f in report["findings"] if f["severity"] == "blocking")


# -- narrative ---------------------------------------------------------------

GENERATED_NARRATIVE_RATIONALE: Final[str] = (
    "Generated from the caller-supplied instrument-validity artifact. Every figure is read "
    "from that JSON rather than retyped into prose. Producers should compare the rendered "
    "narrative with its bound artifact before publication; a narrative that has drifted from "
    "its evidence is worse than no narrative."
)


def _table(header: Sequence[str], align: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(align) + "|",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def _rate_cell(rate: Mapping[str, Any]) -> str:
    if not rate["available"]:
        return f"UNAVAILABLE (`{rate['unavailable_reason']['code']}`)"
    return f"{rate['value']:.3f} ({rate['numerator']}/{rate['denominator']})"


def _metric_section(metric: Mapping[str, Any]) -> list[str]:
    lines = [f"#### `{metric['metric']}`", "", metric["question"], ""]
    if not metric["available"]:
        reason = metric["unavailable_reason"]
        lines += [
            f"UNAVAILABLE — `{reason['code']}`: {reason['detail']}",
            "",
            f"n = {metric['n']}; unit of analysis: {metric['unit_of_analysis']}.",
            "",
        ]
        return lines
    lines += [f"n = {metric['n']}; unit of analysis: {metric['unit_of_analysis']}.", ""]
    if metric["rates"]:
        lines += _table(
            ["rate", "value (numerator/denominator)"],
            ["---", "---"],
            [[f"`{rate['name']}`", _rate_cell(rate)] for rate in metric["rates"]],
        )
        lines.append("")
    if "counts" in metric:
        counts = metric["counts"]
        lines += [
            "Cells: true positive "
            f"{counts['true_positive']}, false positive {counts['false_positive']}, "
            f"false negative {counts['false_negative']}, true negative "
            f"{counts['true_negative']}.",
            "",
        ]
    if metric.get("macro_token_f1") is not None:
        lines += [
            f"Macro token F1 (unweighted mean over scored units): "
            f"{metric['macro_token_f1']:.3f}. Reported beside the micro figure, never "
            "instead of it.",
            "",
        ]
    if "operator_evidence" in metric:
        evidence = metric["operator_evidence"]
        lines += [
            f"{evidence['units_with_operator_offsets']} in-scope unit(s) carried "
            "operator offsets: "
            f"{evidence['from_disagreement_review']} from the disagreement review and "
            f"{evidence['from_source_only']} from the source-only pass alone.",
            "",
        ]
    if metric.get("exclusions"):
        lines += [
            *_table(
                ["excluded", "count", "why"],
                ["---", "---:", "---"],
                [
                    [f"`{row['reason']}`", str(row["count"]), row["detail"]]
                    for row in metric["exclusions"]
                ],
            ),
            "",
        ]
    if "declined_without_confidence" in metric:
        lines += [
            f"{metric['declined_without_confidence']} in-scope unit(s) were declined and "
            "carry no confidence. They sit outside every bin rather than in the weakest "
            "one.",
            "",
        ]
    if metric["per_class"]:
        lines += _table(
            ["class", "instrument", "gold", "agreements", "precision", "recall", "f1"],
            ["---", "---:", "---:", "---:", "---", "---", "---"],
            [
                [
                    f"`{row['class']}`",
                    str(row["instrument_count"]),
                    str(row["gold_count"]),
                    str(row["agreements"]),
                    _rate_cell(row["precision"]),
                    _rate_cell(row["recall"]),
                    _rate_cell(row["f1"]),
                ]
                for row in metric["per_class"]
            ],
        )
        lines.append("")
    if metric["confusion"]:
        confusion = metric["confusion"]
        lines += [
            "Instrument on the rows, adjudicated gold on the columns.",
            "",
            *_table(
                ["instrument \\ gold", *(f"`{c}`" for c in confusion["columns"])],
                ["---", *("---:" for _ in confusion["columns"])],
                [
                    [f"`{name}`", *(str(cell) for cell in row)]
                    for name, row in zip(confusion["rows"], confusion["table"])
                ],
            ),
            "",
        ]
    if metric["bins"]:
        lines += _table(
            ["confidence", "n", "matches", "accuracy"],
            ["---", "---:", "---:", "---"],
            [
                [
                    f"`{entry['confidence']}`",
                    str(entry["n"]),
                    str(entry["matches"]),
                    _rate_cell(entry["accuracy"]),
                ]
                for entry in metric["bins"]
            ],
        )
        lines.append("")
    for note in metric["notes"]:
        lines += [f"- {note}", ""]
    return lines


def render_report_markdown(report: Mapping[str, Any]) -> str:
    """The prose account of one validity report, derived from the report.

    A pure function of the sealed JSON. Nothing is transcribed: every count and
    ratio below is read out of ``report``.
    """
    cov = report["coverage"]
    lines = [
        "# ATS-1 instrument validity against adjudicated gold",
        "",
        "This document measures whether each instrument reaches the adjudicator's "
        "disposition by scoring each pass independently against supplied gold.",
        "",
        GENERATED_NARRATIVE_RATIONALE,
        "",
        f"- `schema_version`: `{report['schema_version']}`",
        f"- `report_sha256`: `{report['report_sha256']}`",
        f"- `spec_version`: `{report['spec_version']}`",
        f"- queue: `{report['queue']['queue_id']}`",
        f"- gold: `{report['gold']['path']}`"
        + (
            f" (`{report['gold']['file_sha256']}`, {report['gold']['records']} record(s))"
            if report["gold"]["available"]
            else " — absent"
        ),
        "",
        "## What is being measured, and what is not",
        "",
    ]
    for entry in report["measurements"]:
        lines += [
            f"**`{entry['kind']}`** — established by `{entry['established_by']}`, "
            f"separable by instrument: {str(entry['separable_by_instrument']).lower()}.",
            "",
            entry["statement"],
            "",
        ]
        reference = entry["cross_reference"]
        if reference is not None:
            lines += [
                (
                    f"Cross-reference: `{reference['path']}`, "
                    f"`{reference['schema_version']}`, `{reference['report_sha256']}`."
                    if reference["available"]
                    else "Cross-reference UNAVAILABLE — "
                    f"`{reference['unavailable_reason']['code']}`: "
                    f"{reference['unavailable_reason']['detail']}."
                ),
                "",
            ]
    lines += [
        "## Coverage",
        "",
        cov["statement"],
        "",
        f"{cov['adjudicated']} of {cov['required']} queue unit(s) carry a disagreement "
        f"review. `partial`: {str(cov['partial']).lower()}; `allow_partial`: "
        f"{str(cov['allow_partial']).lower()}.",
        "",
        *_table(
            [
                "unit kind",
                "adjudicated",
                "required",
                "awaiting review",
                "unstarted",
                "excluded",
                "scored",
            ],
            ["---", "---:", "---:", "---:", "---:", "---:", "---:"],
            [
                [
                    f"`{row['unit_kind']}`",
                    str(row["adjudicated"]),
                    str(row["required"]),
                    str(row["source_only_awaiting_review"]),
                    str(row["unstarted"]),
                    str(row["excluded_by_operator"]),
                    str(row["scored"]),
                ]
                for row in cov["by_unit_kind"]
            ],
        ),
        "",
        "## The gold applicability mapping",
        "",
        "Applicability precision and recall need gold in the instrument's own "
        "three-state vocabulary. The mapping is published rather than applied "
        "silently, because it decides which denominators a claim of applicability "
        "is charged against.",
        "",
        *_table(
            ["gold disposition", "applicability class"],
            ["---", "---"],
            [
                [f"`{row['gold_disposition']}`", f"`{row['applicability_class']}`"]
                for row in report["vocabularies"]["gold_applicability_map"]
            ],
        ),
        "",
    ]
    for block in report["instruments"]:
        lines += [
            f"## Instrument {block['role']}",
            "",
            f"Annotator: `{block['annotator_id']}`. Units scored: "
            f"{block['units_scored']}.",
            "",
        ]
        for metric in block["metrics"]:
            lines += _metric_section(metric)
        rules = block["error_type_by_rule"]
        lines += [
            "### Error type by rule",
            "",
            f"{len(rules)} rule(s) carry an in-scope unit for this instrument.",
            "",
        ]
        if rules:
            lines += _table(
                ["rule", "n", "matches", "mismatches", "mismatch rate"],
                ["---", "---:", "---:", "---:", "---"],
                [
                    [
                        f"`{row['rule_id']}`",
                        str(row["n"]),
                        str(row["matches"]),
                        str(row["mismatches"]),
                        _rate_cell(row["mismatch_rate"]),
                    ]
                    for row in rules
                ],
            )
            lines.append("")
            for row in rules:
                if not row["by_outcome_pair"]:
                    continue
                lines += [
                    f"`{row['rule_id']}` mismatches by outcome pair: "
                    + ", ".join(
                        f"instrument `{pair['instrument']}` vs gold `{pair['gold']}` "
                        f"({pair['count']})"
                        for pair in row["by_outcome_pair"]
                    )
                    + ".",
                    "",
                ]
    lines += ["## Profile reconnaissance", ""]
    if report["profile_instruments"]:
        for block in report["profile_instruments"]:
            lines += [
                f"### `{block['annotator_id']}`",
                "",
                f"Units scored: {block['units_scored']}.",
                "",
            ]
            for metric in block["metrics"]:
                lines += _metric_section(metric)
    else:
        lines += [
            "No profile-reconnaissance unit carries a scoreable disagreement review.",
            "",
        ]
    lines += ["## Findings", ""]
    if report["findings"]:
        lines += _table(
            ["severity", "code", "subject", "detail"],
            ["---", "---", "---", "---"],
            [
                [
                    finding["severity"],
                    f"`{finding['code']}`",
                    finding["subject"],
                    finding["detail"],
                ]
                for finding in report["findings"]
            ],
        )
        lines.append("")
    else:
        lines += ["None.", ""]
    lines += [
        "## Assessment",
        "",
        f"Status: `{report['assessment']['status']}`.",
        "",
    ]
    for reason in report["assessment"]["reasons"]:
        lines += [f"- {reason}", ""]
    lines += ["## Why there is no combined figure", "", report["assessment"]["pooled_refusal"], ""]
    return "\n".join(lines).rstrip("\n") + "\n"

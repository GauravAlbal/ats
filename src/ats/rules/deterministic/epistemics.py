"""Epistemics rules: ATS-EPI-001 through ATS-EPI-007.

Every vocabulary used here is read from ``lexicons/ats_force_lexicon_v1.yaml``
through :class:`~ats.rules.registry.ForceLexicon`. No probability word,
confidence level, or synonym is written into this module.
"""

from __future__ import annotations

from typing import Any

from ...ir.model import IrEvaluation
from ...rules.results import DecisionPower, Detector, Finding
from ._support import (
    IR_SECTION_ORDER_SUBSTITUTION,
    Collector,
    DetectorSpec,
    SubcheckSpec,
    contains_phrase,
    detector,
)

LEXICON_SOURCE = "lexicons/ats_force_lexicon_v1.yaml"

# -- ATS-EPI-001 ------------------------------------------------------------

EPI001_TERM = SubcheckSpec(
    subcheck_id="wep-term-not-canonical",
    decides=True,
    spec_ref="ATS-1 8.2, 8.3",
    vocabulary_source=LEXICON_SOURCE,
    description="A likelihood of kind `wep` names a term absent from the canonical ATS-1 row.",
)
EPI001_INTERVAL = SubcheckSpec(
    subcheck_id="wep-interval-mismatch",
    decides=True,
    spec_ref="ATS-1 8.2",
    vocabulary_source=LEXICON_SOURCE,
    description=(
        "A likelihood of kind `wep` declares bounds that differ from the lexicon interval for "
        "its term, silently redefining the calibrated scale."
    ),
)
EPI001_POINT = SubcheckSpec(
    subcheck_id="point-probability-unjustified",
    decides=True,
    spec_ref="ATS-1 8.5, 8.6",
    vocabulary_source=LEXICON_SOURCE,
    description=(
        "A numeric point or interval probability carries no rationale, so the precision it "
        "claims has no stated justification."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-EPI-001",
        detector_class="D0",
        power=DecisionPower.DECIDES,
        subchecks=(EPI001_TERM, EPI001_INTERVAL, EPI001_POINT),
        unavailable_conditions=(
            "None on this surface: every likelihood object the IR carries is fully inspectable "
            "against the lexicon.",
        ),
        known_limits=(
            "This decides the represented likelihood. Whether the author should have attached a "
            "likelihood at all is a materiality judgement handled by profile completeness.",
        ),
    )
)
def epi_001(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """A material probabilistic judgment MUST use canonical WEP or a justified point."""
    c = Collector(ev, det, "ATS-EPI-001")
    lex = ev.ctx.lexicon
    for claim in ev.ir.material_claims():
        likelihood = claim.likelihood
        if likelihood is None:
            continue
        kind = likelihood.get("kind")
        ptr = claim.field_pointer("force", "likelihood")
        if kind == "wep":
            term = likelihood.get("term")
            c.saw(EPI001_TERM.subcheck_id)
            if term not in lex.wep_terms:
                c.flag(
                    EPI001_TERM.subcheck_id,
                    issue_code="wep-term-not-canonical",
                    summary=(
                        f"Claim {claim.claim_id} declares WEP term {term!r}, which is not in the "
                        f"canonical ATS-1 row ({', '.join(sorted(lex.wep_terms))})."
                    ),
                    spans=[{"kind": "json_pointer", "locator": ptr}],
                )
                continue
            c.saw(EPI001_INTERVAL.subcheck_id)
            lower, upper, _ = lex.interval_for(term)
            if likelihood.get("lower") != lower or likelihood.get("upper") != upper:
                c.flag(
                    EPI001_INTERVAL.subcheck_id,
                    issue_code="wep-interval-mismatch",
                    summary=(
                        f"Claim {claim.claim_id} declares term {term!r} with bounds "
                        f"[{likelihood.get('lower')}, {likelihood.get('upper')}], but the "
                        f"lexicon defines {term!r} as [{lower}, {upper}]. Changing an interval "
                        "boundary is a breaking change to the calibrated scale (spec 19.3)."
                    ),
                    spans=[{"kind": "json_pointer", "locator": ptr}],
                )
        elif kind in ("point", "interval"):
            c.saw(EPI001_POINT.subcheck_id)
            if not str(likelihood.get("rationale", "")).strip():
                c.flag(
                    EPI001_POINT.subcheck_id,
                    issue_code="point-probability-unjustified",
                    summary=(
                        f"Claim {claim.claim_id} states a numeric {kind} probability with no "
                        "rationale. Section 8.5 permits greater precision only when the evidence "
                        "and use case justify it, and Section 8.6 prefers a band otherwise."
                    ),
                    spans=[{"kind": "json_pointer", "locator": ptr}],
                )
    return c.result((EPI001_TERM, EPI001_INTERVAL, EPI001_POINT))


# -- ATS-EPI-002 ------------------------------------------------------------

EPI002_FLAG = SubcheckSpec(
    subcheck_id="first-use-range-not-shown",
    decides=True,
    spec_ref="ATS-1 8.4",
    vocabulary_source=LEXICON_SOURCE,
    description=(
        "The first material WEP use in a section does not declare `range_shown_inline: true`."
    ),
)
EPI002_DISPLAY = SubcheckSpec(
    subcheck_id="first-use-display-missing-range",
    decides=True,
    spec_ref="ATS-1 8.4",
    vocabulary_source=LEXICON_SOURCE,
    description=(
        "The first material WEP use declares the range shown inline, but its `display` string "
        "does not contain the lexicon display range."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-EPI-002",
        detector_class="D0",
        power=DecisionPower.DECIDES,
        subchecks=(EPI002_FLAG, EPI002_DISPLAY),
        substitutions=(IR_SECTION_ORDER_SUBSTITUTION,),
        unavailable_conditions=(
            "A section containing no material WEP use has no first use to check.",
        ),
        known_limits=(
            "This decides what the IR declares about the inline range. Whether the rendered "
            "Markdown actually shows it is decided by the output linter's OUT-WEP-INLINE-RANGE.",
            "The lexicon's `first_material_use_must_show_range` flag gates this rule; if a future "
            "lexicon sets it false the subchecks report NOT_APPLICABLE.",
        ),
    )
)
def epi_002(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """The first material WEP use in a section MUST include its numeric range inline."""
    c = Collector(ev, det, "ATS-EPI-002")
    lex = ev.ctx.lexicon
    if not lex.first_use_must_show_range:
        return [], [
            {
                "subcheck_id": sc.subcheck_id,
                "status": "NOT_APPLICABLE",
                "spec_ref": sc.spec_ref,
                "detail": "the active lexicon does not require a first-use range",
                "observed": 0,
            }
            for sc in (EPI002_FLAG, EPI002_DISPLAY)
        ]

    for section in ev.ir.sections:
        first = next(
            (
                claim
                for claim in section.claims
                if claim.material
                and claim.likelihood is not None
                and claim.likelihood.get("kind") == "wep"
            ),
            None,
        )
        if first is None:
            continue
        likelihood = first.likelihood or {}
        term = likelihood.get("term")
        ptr = first.field_pointer("force", "likelihood")
        c.saw(EPI002_FLAG.subcheck_id)
        if not likelihood.get("range_shown_inline"):
            c.flag(
                EPI002_FLAG.subcheck_id,
                issue_code="first-use-range-not-shown",
                summary=(
                    f"Claim {first.claim_id} is the first material WEP use in section "
                    f"{section.section_id!r} and declares `range_shown_inline: false`. The "
                    "intended probability scale is then unavailable at the point of "
                    "interpretation."
                ),
                spans=[{"kind": "json_pointer", "locator": ptr}],
            )
            continue
        if term not in lex.wep_terms:
            # ATS-EPI-001 owns the non-canonical term; do not double-report it.
            continue
        c.saw(EPI002_DISPLAY.subcheck_id)
        expected = lex.display_range(term)
        display = str(likelihood.get("display", ""))
        if not _display_shows_range(display, expected):
            c.flag(
                EPI002_DISPLAY.subcheck_id,
                issue_code="first-use-display-missing-range",
                summary=(
                    f"Claim {first.claim_id} declares the range shown inline, but its display "
                    f"string {display!r} does not contain the lexicon range {expected!r} for "
                    f"term {term!r}."
                ),
                spans=[{"kind": "json_pointer", "locator": ptr}],
            )
    return c.result((EPI002_FLAG, EPI002_DISPLAY))


def _display_shows_range(display: str, expected: str) -> bool:
    """True when ``display`` carries the lexicon range.

    The lexicon writes ranges with an en dash (``55–80%``). Accept a hyphen too:
    the numbers and the percent sign are the semantic content, and Section 8.4
    constrains the range shown, not the dash character used to show it.
    """
    if expected in display:
        return True
    return expected.replace("\u2013", "-") in display.replace("\u2013", "-")


# -- ATS-EPI-003 ------------------------------------------------------------

EPI003 = SubcheckSpec(
    subcheck_id="noncanonical-wep-synonym",
    decides=True,
    spec_ref="ATS-1 8.3",
    vocabulary_source=f"{LEXICON_SOURCE} likelihood.terms[].input_aliases",
    description=(
        "A material claim's proposition uses a noncanonical probability synonym the lexicon maps "
        "to a canonical term."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-EPI-003",
        detector_class="D0",
        power=DecisionPower.DECIDES,
        subchecks=(EPI003,),
        unavailable_conditions=(
            "An artifact with no material claims presents no probability vocabulary to check.",
        ),
        known_limits=(
            "The alias set is exactly the lexicon's `input_aliases`. Section 8.3 permits a "
            "noncanonical term inside a quotation or when policy requires it; the IR does not mark "
            "quoted regions, so such a case is a hard negative and must be adjudicated. The "
            "output linter, which does see content classes, skips quoted blocks.",
        ),
    )
)
def epi_003(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """A section MUST NOT mix noncanonical WEP synonyms with canonical output."""
    c = Collector(ev, det, "ATS-EPI-003")
    aliases = ev.ctx.lexicon.wep_aliases
    for claim in ev.ir.material_claims():
        c.saw(EPI003.subcheck_id)
        for alias, canonical in sorted(aliases.items()):
            if contains_phrase(claim.proposition, alias):
                phrase = ev.ctx.lexicon.wep_terms[canonical]["phrase"]
                c.flag(
                    EPI003.subcheck_id,
                    issue_code="noncanonical-wep-synonym",
                    summary=(
                        f"Claim {claim.claim_id} uses the noncanonical probability word "
                        f"{alias!r}. The lexicon maps it to the canonical term {canonical!r}, "
                        f"whose ATS-1 surface form is {phrase!r}. Mixed scales invite readers to "
                        "assign unintended differences."
                    ),
                    spans=[claim.span()],
                )
    return c.result((EPI003,))


# -- ATS-EPI-004 ------------------------------------------------------------

EPI004_DISPLAY = SubcheckSpec(
    subcheck_id="confidence-word-inside-likelihood",
    decides=False,
    spec_ref="ATS-1 8.11, 4.8",
    vocabulary_source=f"{LEXICON_SOURCE} assessment_confidence.terms",
    description=(
        "A likelihood's display string carries an assessment-confidence level, conflating the "
        "probability of the event with the robustness of the analysis."
    ),
)
EPI004_SUBSTITUTE = SubcheckSpec(
    subcheck_id="confidence-substituted-for-likelihood",
    decides=False,
    spec_ref="ATS-1 8.11",
    vocabulary_source=f"{LEXICON_SOURCE} assessment_confidence.terms",
    description=(
        "A material judgment whose proposition states a probability word carries an assessment "
        "confidence but no likelihood field, so confidence is standing in for likelihood."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-EPI-004",
        detector_class="D1",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(EPI004_DISPLAY, EPI004_SUBSTITUTE),
        unavailable_conditions=(
            "A claim carrying neither a likelihood nor an assessment confidence presents no "
            "separation to check.",
        ),
        known_limits=(
            "The schema already keeps likelihood and assessment confidence in distinct fields, so "
            "representational separation is structural. What remains is prose-level conflation, "
            "which is only partially visible from the IR. A clean run is REVIEW_REQUIRED.",
        ),
    )
)
def epi_004(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Likelihood and assessment confidence MUST be represented as distinct fields."""
    c = Collector(ev, det, "ATS-EPI-004")
    lex = ev.ctx.lexicon
    levels = lex.confidence_levels
    canonical_phrases = [t["phrase"] for t in lex.wep_terms.values()]

    for claim in ev.ir.material_claims():
        likelihood = claim.likelihood
        confidence = claim.assessment_confidence
        if likelihood is not None:
            c.saw(EPI004_DISPLAY.subcheck_id)
            display = str(likelihood.get("display", ""))
            hits = [lvl for lvl in levels if contains_phrase(display, lvl)]
            if hits:
                c.flag(
                    EPI004_DISPLAY.subcheck_id,
                    issue_code="confidence-word-inside-likelihood",
                    summary=(
                        f"Claim {claim.claim_id} renders its likelihood as {display!r}, which "
                        f"contains the assessment-confidence level {hits[0]!r}. Event probability "
                        "and robustness of the analytic basis answer different questions and must "
                        "be shown separately."
                    ),
                    spans=[
                        {
                            "kind": "json_pointer",
                            "locator": claim.field_pointer("force", "likelihood", "display"),
                        }
                    ],
                )
        if confidence is not None and likelihood is None and claim.role in ("judgment", "forecast"):
            c.saw(EPI004_SUBSTITUTE.subcheck_id)
            probabilistic = any(
                contains_phrase(claim.proposition, p) for p in canonical_phrases
            ) or any(contains_phrase(claim.proposition, a) for a in lex.wep_aliases)
            if probabilistic:
                c.flag(
                    EPI004_SUBSTITUTE.subcheck_id,
                    issue_code="confidence-substituted-for-likelihood",
                    summary=(
                        f"Claim {claim.claim_id} states a probability in prose and carries an "
                        f"assessment confidence of {confidence.get('level')!r}, but no likelihood "
                        "field. The confidence label is standing in for the probability."
                    ),
                    spans=[claim.span()],
                    interpretations=[
                        {
                            "interpretation_id": f"{claim.claim_id}-as-likelihood",
                            "reading": "The stated word is the probability of the event.",
                            "material_difference": "The reader treats it as an event probability.",
                        },
                        {
                            "interpretation_id": f"{claim.claim_id}-as-confidence",
                            "reading": "The stated word is the robustness of the analysis.",
                            "material_difference": (
                                "The reader treats it as analytic robustness and has no event "
                                "probability at all."
                            ),
                        },
                    ],
                )
    return c.result((EPI004_DISPLAY, EPI004_SUBSTITUTE))


# -- ATS-EPI-005 ------------------------------------------------------------

EPI005_RATIONALE = SubcheckSpec(
    subcheck_id="confidence-basis-rationale-blank",
    decides=True,
    spec_ref="ATS-1 8.9",
    vocabulary_source=f"{LEXICON_SOURCE} assessment_confidence.basis_dimensions",
    description="A material confidence label carries a basis whose rationale is blank.",
)
EPI005_UNKNOWN = SubcheckSpec(
    subcheck_id="confidence-basis-wholly-unknown",
    decides=True,
    spec_ref="ATS-1 8.9, 8.10",
    vocabulary_source=f"{LEXICON_SOURCE} assessment_confidence.basis_dimensions",
    description=(
        "Every basis dimension of a material confidence label is `unknown`, so the label carries "
        "authority with nothing inspectable behind it."
    ),
)
EPI005_HIGH = SubcheckSpec(
    subcheck_id="high-confidence-on-unknown-dimension",
    decides=True,
    spec_ref="ATS-1 8.10",
    vocabulary_source=f"{LEXICON_SOURCE} assessment_confidence.basis_dimensions",
    description=(
        "A `high` confidence label rests on a basis with at least one unknown dimension and no "
        "robustness argument in its rationale."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-EPI-005",
        detector_class="D1",
        power=DecisionPower.DECIDES,
        subchecks=(EPI005_RATIONALE, EPI005_UNKNOWN, EPI005_HIGH),
        unavailable_conditions=(
            "A claim with no assessment confidence presents no basis to inspect.",
        ),
        known_limits=(
            "Whether a present rationale is a *good* rationale is a semantic judgement. This "
            "decides that an inspectable basis exists and is not wholly unknown, which is what "
            "Section 8.9 requires structurally.",
        ),
    )
)
def epi_005(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """A material assessment-confidence label MUST include an inspectable basis and rationale."""
    c = Collector(ev, det, "ATS-EPI-005")
    dimensions = tuple(ev.ctx.lexicon.basis_dimensions)
    for claim in ev.ir.material_claims():
        confidence = claim.assessment_confidence
        if confidence is None:
            continue
        basis = confidence.get("basis", {})
        ptr = claim.field_pointer("force", "assessment_confidence", "basis")
        c.saw(EPI005_RATIONALE.subcheck_id)
        if not str(basis.get("rationale", "")).strip():
            c.flag(
                EPI005_RATIONALE.subcheck_id,
                issue_code="confidence-basis-rationale-blank",
                summary=(
                    f"Claim {claim.claim_id} labels its confidence {confidence.get('level')!r} "
                    "with a blank basis rationale. A confidence label without a stated basis "
                    "creates unsupported authority."
                ),
                spans=[{"kind": "json_pointer", "locator": ptr}],
            )
        unknown = [d for d in dimensions if basis.get(d) == "unknown"]
        c.saw(EPI005_UNKNOWN.subcheck_id)
        if unknown and len(unknown) == len([d for d in dimensions if d in basis]):
            c.flag(
                EPI005_UNKNOWN.subcheck_id,
                issue_code="confidence-basis-wholly-unknown",
                summary=(
                    f"Claim {claim.claim_id} declares every basis dimension as `unknown` while "
                    f"still asserting {confidence.get('level')!r} confidence. Nothing about the "
                    "basis is inspectable."
                ),
                spans=[{"kind": "json_pointer", "locator": ptr}],
            )
        if confidence.get("level") == "high":
            c.saw(EPI005_HIGH.subcheck_id)
            weak = [d for d in dimensions if basis.get(d) in ("unknown", "weak", "unaddressed")]
            if weak and not str(basis.get("rationale", "")).strip():
                c.flag(
                    EPI005_HIGH.subcheck_id,
                    issue_code="high-confidence-on-unknown-dimension",
                    summary=(
                        f"Claim {claim.claim_id} asserts `high` confidence while the basis "
                        f"dimensions {', '.join(weak)} are unknown, weak, or unaddressed, and the "
                        "rationale offers no robustness argument."
                    ),
                    spans=[{"kind": "json_pointer", "locator": ptr}],
                )
    return c.result((EPI005_RATIONALE, EPI005_UNKNOWN, EPI005_HIGH))


# -- ATS-EPI-006 ------------------------------------------------------------

EPI006 = SubcheckSpec(
    subcheck_id="material-assessment-without-update-indicator",
    decides=False,
    spec_ref="ATS-1 7.14, 9.2.4",
    vocabulary_source="update_indicator objects and extraction_issues declared in the IR",
    description=(
        "A material judgment or forecast is targeted by no update indicator and no extraction "
        "issue states why none is available."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-EPI-006",
        detector_class="D3",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(EPI006,),
        unavailable_conditions=(
            "An artifact with no material judgment or forecast presents no assessment to make "
            "revisable.",
        ),
        known_limits=(
            "Whether an indicator is genuinely observable is a semantic judgement. This decides "
            "that an indicator exists and points at the claim, or that the artifact states why "
            "none does — which is what Section 7.14 makes checkable.",
            "The registry lists only D3 and D4 as this rule's detector classes, so a deterministic structural detector has no class of its own to report. It reports D3, whose output is proposal_only in this draft (spec 12.3), and its findings are surfaced for adjudication rather than deciding the rule. See docs/decisions/ADR-0008.",
            "Appendix E question 1 asks whether this rule should apply to every material judgment "
            "or only above a policy-defined materiality threshold. Until that is ratified this "
            "implementation applies it to every material judgment and forecast.",
        ),
    )
)
def epi_006(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """A material assessment MUST identify an update indicator or state why none is available."""
    c = Collector(ev, det, "ATS-EPI-006")
    excused: set[str] = set()
    for issue in ev.ir.extraction_issues:
        for field in issue.get("affected_fields", ()):
            excused.add(field)
    for claim in ev.ir.material_claims():
        if claim.role not in ("judgment", "forecast"):
            continue
        c.saw(EPI006.subcheck_id)
        if ev.ir.indicators_targeting(claim.claim_id):
            continue
        if any(claim.claim_id in field for field in excused):
            continue
        c.flag(
            EPI006.subcheck_id,
            issue_code="no-update-indicator",
            summary=(
                f"{claim.role.capitalize()} {claim.claim_id} is material but no update indicator "
                "targets it, and no extraction issue records that none is available. The "
                "assessment is rhetorically final rather than operationally revisable."
            ),
            spans=[claim.span()],
        )
    return c.result((EPI006,))


# -- ATS-EPI-007 ------------------------------------------------------------

EPI007 = SubcheckSpec(
    subcheck_id="possibility-term-as-only-likelihood",
    decides=True,
    spec_ref="ATS-1 8.7",
    vocabulary_source=f"{LEXICON_SOURCE} likelihood.non_probability_terms",
    description=(
        "A material claim states a possibility term the lexicon marks as non-probability and "
        "carries no likelihood of kind wep, point, or interval."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-EPI-007",
        detector_class="D0",
        power=DecisionPower.DECIDES,
        subchecks=(EPI007,),
        unavailable_conditions=(
            "An artifact with no material claims presents no likelihood expression to check.",
        ),
        known_limits=(
            "The term set is exactly the lexicon's `non_probability_terms`. A claim that is not "
            "probabilistic at all may legitimately use these words; the rule fires only when the "
            "claim also supplies no calibrated likelihood, which is the condition Section 8.7 "
            "names.",
        ),
    )
)
def epi_007(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Possibility terms MUST NOT serve as the only likelihood expression."""
    c = Collector(ev, det, "ATS-EPI-007")
    terms = ev.ctx.lexicon.non_probability_terms
    for claim in ev.ir.material_claims():
        if claim.role not in ("judgment", "forecast", "inference"):
            continue
        c.saw(EPI007.subcheck_id)
        hits = [t for t in terms if contains_phrase(claim.proposition, t)]
        if not hits:
            continue
        likelihood = claim.likelihood
        calibrated = likelihood is not None and likelihood.get("kind") in (
            "wep",
            "point",
            "interval",
        )
        if calibrated:
            continue
        c.flag(
            EPI007.subcheck_id,
            issue_code="possibility-term-as-only-likelihood",
            summary=(
                f"Claim {claim.claim_id} expresses its likelihood only through "
                f"{', '.join(repr(h) for h in hits)}, which the lexicon lists as a "
                "non-probability term. These words do not map to one calibrated probability "
                "range, so the reader cannot recover the intended likelihood."
            ),
            spans=[claim.span()],
        )
    return c.result((EPI007,))

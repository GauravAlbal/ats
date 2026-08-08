"""Time rules: ATS-TIME-001, ATS-TIME-002."""

from __future__ import annotations

from typing import Any

from ...ir.model import IrEvaluation
from ...rules.results import DecisionPower, Detector, Finding
from ._support import Collector, DetectorSpec, SubcheckSpec, contains_phrase, detector

TIME001_FORECAST = SubcheckSpec(
    subcheck_id="forecast-without-resolution",
    decides=True,
    spec_ref="ATS-1 9.2.11",
    vocabulary_source="forecast slots defined in ats_common_v1#/$defs/forecast_slots",
    description=(
        "A material forecast declares no resolvable outcome, resolution event, or resolution "
        "source, so its probability is not a stable proposition."
    ),
)
TIME001_JUDGMENT = SubcheckSpec(
    subcheck_id="probabilistic-judgment-without-horizon",
    decides=False,
    spec_ref="ATS-1 9.2.4",
    vocabulary_source="scope fields defined in ats_common_v1#/$defs/scope",
    description=(
        "A material judgment carrying a likelihood declares no time horizon, so the reader "
        "cannot tell over what period the probability holds."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-TIME-001",
        detector_class="D0",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(TIME001_FORECAST, TIME001_JUDGMENT),
        unavailable_conditions=(
            "An artifact with no material forecast and no probabilistic judgment states nothing "
            "temporally bounded to check.",
        ),
        known_limits=(
            "Whether a non-probabilistic judgment is temporally bounded is a semantic question. "
            "Only judgments that carry a likelihood are checked for a horizon, so a clean run is "
            "REVIEW_REQUIRED rather than PASS.",
        ),
    )
)
def time_001(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """A material forecast or temporally bounded judgment MUST state a resolution or horizon."""
    c = Collector(ev, det, "ATS-TIME-001")
    for claim in ev.ir.material_claims():
        if claim.role == "forecast":
            c.saw(TIME001_FORECAST.subcheck_id)
            forecast = claim.forecast or {}
            gaps = [
                slot
                for slot in ("outcome_definition", "resolution", "resolution_source")
                if not str(forecast.get(slot, "")).strip()
            ]
            if gaps:
                c.flag(
                    TIME001_FORECAST.subcheck_id,
                    issue_code="forecast-without-resolution",
                    summary=(
                        f"Forecast {forecast.get('forecast_id', claim.claim_id)} leaves "
                        f"{', '.join(gaps)} empty. Without a resolvable outcome and a resolution "
                        "date, event, or source the forecast can never be scored."
                    ),
                    spans=[{"kind": "json_pointer", "locator": claim.field_pointer("forecast")}],
                )
        if claim.role in ("judgment", "inference") and claim.likelihood is not None:
            if claim.likelihood.get("kind") == "not_applicable":
                continue
            c.saw(TIME001_JUDGMENT.subcheck_id)
            if not str(claim.scope.get("time_horizon", "")).strip():
                c.flag(
                    TIME001_JUDGMENT.subcheck_id,
                    issue_code="probabilistic-judgment-without-horizon",
                    summary=(
                        f"Claim {claim.claim_id} attaches a likelihood to a {claim.role} but "
                        "declares no `scope.time_horizon`. A probability without a horizon is not "
                        "a stable proposition."
                    ),
                    spans=[{"kind": "json_pointer", "locator": claim.field_pointer("scope")}],
                )
    return c.result((TIME001_FORECAST, TIME001_JUDGMENT))


# -- ATS-TIME-002 -----------------------------------------------------------

#: Relative expressions enumerated verbatim by ATS-1 Section 10.11. This list is
#: quoted from the specification, not assembled by the implementation.
RELATIVE_TIME_TERMS = (
    "today",
    "currently",
    "recently",
    "soon",
    "later",
    "next",
    "the latest",
)

#: Scope fields that constitute a deterministic anchor (Section 10.11 names a
#: date, event, version, or policy snapshot).
ANCHOR_FIELDS = ("time_horizon", "version", "evidence_window", "environment")

TIME002 = SubcheckSpec(
    subcheck_id="unanchored-relative-time",
    decides=False,
    spec_ref="ATS-1 10.11",
    vocabulary_source="the relative expressions enumerated verbatim in ATS-1 10.11",
    description=(
        "A material claim uses a relative-time expression the specification names while its scope "
        "declares no date, event, version, or evidence window to anchor it."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-TIME-002",
        detector_class="D0",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(TIME002,),
        unavailable_conditions=(
            "An artifact with no material claims presents no relative-time expression to anchor.",
        ),
        known_limits=(
            "Only the seven expressions Section 10.11 enumerates are matched. A relative reference "
            "phrased differently is not detected, so a clean run is REVIEW_REQUIRED.",
            "An anchor supplied by surrounding document metadata rather than by the claim's own "
            "scope is not visible on this surface; Section 10.11 permits such an anchor, so a "
            "finding here may be a hard negative and must be adjudicated, not auto-repaired.",
        ),
    )
)
def time_002(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """A material relative-time expression MUST resolve to an absolute anchor."""
    c = Collector(ev, det, "ATS-TIME-002")
    for claim in ev.ir.material_claims():
        c.saw(TIME002.subcheck_id)
        hits = [t for t in RELATIVE_TIME_TERMS if contains_phrase(claim.proposition, t)]
        if not hits:
            continue
        anchored = any(str(claim.scope.get(f, "")).strip() for f in ANCHOR_FIELDS)
        if anchored:
            continue
        c.flag(
            TIME002.subcheck_id,
            issue_code="unanchored-relative-time",
            summary=(
                f"Claim {claim.claim_id} uses the relative expression"
                f"{'s' if len(hits) > 1 else ''} {', '.join(repr(h) for h in hits)} while its "
                "scope declares no time horizon, version, evidence window, or environment. The "
                "claim's meaning changes as time passes."
            ),
            spans=[claim.span()],
            evidence_spans=[{"kind": "json_pointer", "locator": claim.field_pointer("scope")}],
        )
    return c.result((TIME002,))

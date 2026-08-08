"""Evidence rules: ATS-EVID-001, ATS-EVID-002, ATS-EVID-003."""

from __future__ import annotations

from typing import Any

from ...ir.model import IrEvaluation
from ...rules.results import DecisionPower, Detector, Finding
from ._support import Collector, DetectorSpec, SubcheckSpec, detector

#: Relation types that assert discrimination in favour of a claim or a causal
#: mechanism. Read from the relation enum in ats_common_v1 and grouped by the
#: evidential and causal vocabularies in Sections 8.12 and 8.14.
DISCRIMINATING_RELATIONS = (
    "supports",
    "strongly_supports",
    "predicts",
    "contributes_to",
    "causes",
    "necessary_for",
    "sufficient_for",
)

#: Relation types that put a live alternative or contrary consideration against
#: a claim (Sections 9.2.7 and 9.2.8).
CONTRARY_RELATIONS = ("contradicts", "alternative_to", "contrasts_with")

#: Contrary-evidence states the lexicon defines for a confidence basis.
CONTRARY_STATES = ("addressed", "none_found", "not_searched", "not_applicable")


EVID001_OBSERVATION = SubcheckSpec(
    subcheck_id="observation-carrying-assessment-force",
    decides=True,
    spec_ref="ATS-1 7.4, 9.2.5",
    vocabulary_source="claim roles enumerated in ATS-1 7.4",
    description=(
        "A claim whose role reports a first-order observation or a sourced report also carries "
        "assessment machinery — a likelihood or an assessment confidence — which belongs to a "
        "judgment."
    ),
)
EVID001_RECOMMENDATION = SubcheckSpec(
    subcheck_id="recommendation-carrying-evidential-force",
    decides=True,
    spec_ref="ATS-1 9.2.10",
    vocabulary_source="claim roles enumerated in ATS-1 7.4",
    description=(
        "A recommendation carries evidential force, presenting advice as an observed consequence "
        "of the evidence."
    ),
)
EVID001_ASSUMPTION = SubcheckSpec(
    subcheck_id="assumption-presented-as-established",
    decides=True,
    spec_ref="ATS-1 7.12, 9.2.9, 9.2.13",
    vocabulary_source="claim roles enumerated in ATS-1 7.4",
    description=(
        "An assumption carries evidential force, presenting a supposition as an evidenced fact."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-EVID-001",
        detector_class="D1",
        power=DecisionPower.DECIDES,
        subchecks=(EVID001_OBSERVATION, EVID001_RECOMMENDATION, EVID001_ASSUMPTION),
        unavailable_conditions=(
            "An artifact with no claims presents no epistemic roles to separate.",
        ),
        known_limits=(
            "The schema gives every claim exactly one primary role, so role separation is "
            "structural. What this decides is field compatibility: a role carrying force that "
            "belongs to a different role. Whether the author chose the right role for a given "
            "sentence is a semantic judgement outside this surface.",
        ),
    )
)
def evid_001(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Epistemic and normative roles MUST be distinguishable when their difference is material."""
    c = Collector(ev, det, "ATS-EVID-001")
    for claim in ev.ir.material_claims():
        force = claim.force
        ptr = claim.field_pointer("force")
        if claim.role in ("observation", "sourced_report"):
            c.saw(EVID001_OBSERVATION.subcheck_id)
            carried = [
                name
                for name in ("likelihood", "assessment_confidence")
                if force.get(name) is not None
            ]
            if carried:
                c.flag(
                    EVID001_OBSERVATION.subcheck_id,
                    issue_code="observation-carrying-assessment-force",
                    summary=(
                        f"Claim {claim.claim_id} has role {claim.role!r} but carries "
                        f"{', '.join(carried)}. Fluent prose often conceals the transition from "
                        "an observation to a judgment; representing the assessment machinery on "
                        "the observation itself makes that transition unrecoverable."
                    ),
                    spans=[{"kind": "json_pointer", "locator": ptr}],
                )
        if claim.role == "recommendation":
            c.saw(EVID001_RECOMMENDATION.subcheck_id)
            if force.get("evidential") is not None:
                c.flag(
                    EVID001_RECOMMENDATION.subcheck_id,
                    issue_code="recommendation-carrying-evidential-force",
                    summary=(
                        f"Claim {claim.claim_id} is a recommendation carrying evidential force "
                        f"{force['evidential']!r}. Section 9.2.10 requires a recommendation to be "
                        "represented as advice, not as an observed consequence of the evidence."
                    ),
                    spans=[{"kind": "json_pointer", "locator": ptr}],
                )
        if claim.role == "assumption":
            c.saw(EVID001_ASSUMPTION.subcheck_id)
            if force.get("evidential") is not None:
                c.flag(
                    EVID001_ASSUMPTION.subcheck_id,
                    issue_code="assumption-presented-as-established",
                    summary=(
                        f"Claim {claim.claim_id} is an assumption carrying evidential force "
                        f"{force['evidential']!r}. Section 9.2.13 requires that assumptions are "
                        "not presented as established facts."
                    ),
                    spans=[{"kind": "json_pointer", "locator": ptr}],
                )
    return c.result((EVID001_OBSERVATION, EVID001_RECOMMENDATION, EVID001_ASSUMPTION))


# -- ATS-EVID-002 -----------------------------------------------------------

EVID002_BASIS = SubcheckSpec(
    subcheck_id="discriminating-relation-without-basis",
    decides=False,
    spec_ref="ATS-1 8.13, 8.15",
    vocabulary_source="relation types enumerated in ats_common_v1#/$defs/relation",
    description=(
        "A material relation asserting support or causation declares no basis references, so the "
        "wording exceeds any described basis."
    ),
)
EVID002_DANGLING = SubcheckSpec(
    subcheck_id="basis-reference-unresolved",
    decides=False,
    spec_ref="ATS-1 8.15",
    vocabulary_source="relation types enumerated in ats_common_v1#/$defs/relation",
    description="A relation's basis reference does not resolve to an object in the artifact.",
)
EVID002_MODEL = SubcheckSpec(
    subcheck_id="model-output-as-independent-evidence",
    decides=False,
    spec_ref="ATS-1 9.2.6",
    vocabulary_source="source types enumerated in ats_common_v1#/$defs/source_ref",
    description=(
        "An evidence object sourced from model output supports a claim as if it were an "
        "independent evidence line; Section 9.2.6 makes a model's analysis an inference."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-EVID-002",
        detector_class="D3",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(EVID002_BASIS, EVID002_DANGLING, EVID002_MODEL),
        unavailable_conditions=(
            "An artifact with no material relations asserts no evidential or causal force.",
        ),
        known_limits=(
            "The registry lists only D3 and D4 as this rule's detector classes, so a deterministic structural detector has no class of its own to report. It reports D3, whose output is proposal_only in this draft (spec 12.3), and its findings are surfaced for adjudication rather than deciding the rule. See docs/decisions/ADR-0008.",
            "Whether a present basis is strong enough for the force asserted is a semantic "
            "judgement. This decides that a basis is declared and resolves, which is the "
            "structural half of Sections 8.13 and 8.15.",
        ),
    )
)
def evid_002(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Evidential and causal wording MUST NOT exceed the described basis."""
    c = Collector(ev, det, "ATS-EVID-002")
    known = ev.ir.object_ids
    for relation in sorted(ev.ir.relations.values(), key=lambda r: r.relation_id):
        if not relation.material or relation.type not in DISCRIMINATING_RELATIONS:
            continue
        c.saw(EVID002_BASIS.subcheck_id)
        basis = [b for b in relation.basis_refs if str(b).strip()]
        source = ev.ir.evidence.get(relation.source_id)
        if not basis and source is None:
            c.flag(
                EVID002_BASIS.subcheck_id,
                issue_code="discriminating-relation-without-basis",
                summary=(
                    f"Relation {relation.relation_id} asserts {relation.type!r} from "
                    f"{relation.source_id!r} to {relation.target_id!r} with no basis references "
                    "and no evidence object as its source. The asserted force has nothing "
                    "described or referenced behind it."
                ),
                spans=[relation.span()],
            )
        for ref in basis:
            c.saw(EVID002_DANGLING.subcheck_id)
            if ref not in known:
                c.flag(
                    EVID002_DANGLING.subcheck_id,
                    issue_code="basis-reference-unresolved",
                    summary=(
                        f"Relation {relation.relation_id} cites basis {ref!r}, which is not an "
                        "object in this artifact, so the basis cannot be inspected."
                    ),
                    spans=[relation.span()],
                )
        if source is not None:
            c.saw(EVID002_MODEL.subcheck_id)
            if source.source.get("source_type") == "model_output":
                c.flag(
                    EVID002_MODEL.subcheck_id,
                    issue_code="model-output-as-independent-evidence",
                    summary=(
                        f"Evidence {source.evidence_id} is sourced from model output and stands "
                        f"as the {relation.type!r} basis for {relation.target_id!r}. Section "
                        "9.2.6 makes a model's analysis an inference or judgment, not another "
                        "independent evidence line."
                    ),
                    spans=[relation.span()],
                    evidence_spans=[source.span()],
                )
    return c.result((EVID002_BASIS, EVID002_DANGLING, EVID002_MODEL))


# -- ATS-EVID-003 -----------------------------------------------------------

EVID003 = SubcheckSpec(
    subcheck_id="judgment-without-contrary-evidence-state",
    decides=False,
    spec_ref="ATS-1 9.2.7, 9.2.8",
    vocabulary_source=(
        "relation types in ats_common_v1 plus the contrary_evidence states in "
        "lexicons/ats_force_lexicon_v1.yaml"
    ),
    description=(
        "A material judgment is neither opposed by a contrary or alternative relation nor "
        "accompanied by an exact contrary-evidence search state."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-EVID-003",
        detector_class="D3",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(EVID003,),
        unavailable_conditions=(
            "An artifact with no material judgments presents no assessment to calibrate.",
        ),
        known_limits=(
            "The registry lists only D3 and D4 as this rule's detector classes, so a deterministic structural detector has no class of its own to report. It reports D3, whose output is proposal_only in this draft (spec 12.3), and its findings are surfaced for adjudication rather than deciding the rule. See docs/decisions/ADR-0008.",
            "Whether the contrary evidence actually cited is the relevant contrary evidence is a "
            "semantic judgement. This decides that the artifact states one of the exact "
            "availability positions Section 9.2.7 enumerates rather than leaving the reader "
            "unable to tell a bounded search from no search.",
        ),
    )
)
def evid_003(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """A material assessment MUST identify contrary evidence or state the exact search status."""
    c = Collector(ev, det, "ATS-EVID-003")
    for claim in ev.ir.material_claims():
        if claim.role != "judgment":
            continue
        c.saw(EVID003.subcheck_id)
        opposed = any(
            r.type in CONTRARY_RELATIONS for r in ev.ir.relations_targeting(claim.claim_id)
        )
        if opposed:
            continue
        confidence = claim.assessment_confidence or {}
        state = confidence.get("basis", {}).get("contrary_evidence")
        if state in CONTRARY_STATES:
            continue
        c.flag(
            EVID003.subcheck_id,
            issue_code="judgment-without-contrary-evidence-state",
            summary=(
                f"Judgment {claim.claim_id} is material but no relation of type "
                f"{', '.join(CONTRARY_RELATIONS)} targets it, and its confidence basis records "
                f"contrary evidence as {state!r} rather than one of the exact states "
                f"{', '.join(CONTRARY_STATES)}. A reader cannot tell whether a bounded search "
                "found nothing or no search was performed."
            ),
            spans=[claim.span()],
        )
    return c.result((EVID003,))

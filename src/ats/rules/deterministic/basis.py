"""Semantic basis rules: ATS-BASIS-001, ATS-BASIS-002.

Spec Section 4.25 defines the semantic-basis vocabulary (EXPLICIT, DERIVED,
INFERRED, UNAVAILABLE, AUTHOR_JUDGMENT) and the draft.2 amendment D-F adds the
two normative rules: material values SHOULD declare their basis (ATS-BASIS-001,
a review_required rule, D3) and a transformation MUST NOT silently promote
INFERRED or UNAVAILABLE source material into an explicit source-authoritative
fact (ATS-BASIS-002, a block rule, D1).

ATS-BASIS-002 is a TRANSFORM rule whose required inputs are a source IR and an
output IR. ``ats ir lint`` evaluates one artifact, so those inputs are missing
and the rule reports UNAVAILABLE naming them — never PASS by absence. When the
artifact carries a source-side basis ledger in ``extensions.source_basis``
(claim-level or document-level), that ledger stands in for the source side and
the comparison is decided mechanically: a claim whose declared basis is
EXPLICIT while the recorded source basis for the same value is INFERRED or
UNAVAILABLE is a silent promotion. An ``extensions.authorized_change`` record
for this rule declares the promotion as an authorized semantic change (spec
11.4) and suppresses the finding.
"""

from __future__ import annotations

from typing import Any, Mapping

from ...ir.model import IrDocument, IrEvaluation
from ...rules.results import DecisionPower, Detector, Finding, RuleResult
from . import register
from ._support import (
    SPECS,
    Collector,
    DetectorSpec,
    SubcheckSpec,
    detector,
    run_with_optional_inputs,
)

#: The basis vocabulary enumerated verbatim at ATS-1 4.25. The detector only
#: ever compares declared values; the enum itself is schema-enforced.
BASIS_VALUES = ("EXPLICIT", "DERIVED", "INFERRED", "UNAVAILABLE", "AUTHOR_JUDGMENT")

#: Source bases whose silent promotion to EXPLICIT is forbidden (D-F).
PROMOTION_SOURCE_BASES = ("INFERRED", "UNAVAILABLE")


# -- ATS-BASIS-001 ----------------------------------------------------------

BASIS001 = SubcheckSpec(
    subcheck_id="material-claim-without-basis",
    decides=False,
    spec_ref="ATS-1 4.25, 7.19",
    vocabulary_source="the semantic_basis definition at ats_common_v1.schema.json#/$defs/semantic_basis",
    description=(
        "A material claim or requirement slot declares no semantic_basis, so the source "
        "of its semantic values is undeclared."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-BASIS-001",
        detector_class="D3",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(BASIS001,),
        unavailable_conditions=(
            "A document with no material claim or requirement declares no material "
            "semantic value whose basis could be checked.",
        ),
        known_limits=(
            "The basis enum (EXPLICIT, DERIVED, INFERRED, UNAVAILABLE, AUTHOR_JUDGMENT) is "
            "enforced by schema; this detector checks presence only. Whether an omitted "
            "basis is genuinely nonessential is the author's judgement, and the rule's "
            "review_required class defers that to review.",
            "A requirement claim is satisfied by a basis declared at either the claim level "
            "or the requirement-slot level; the two objects carry one claim's semantic "
            "values, so one declared basis covers the unit.",
        ),
    )
)
def basis_001(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Material semantic values SHOULD declare their basis."""
    c = Collector(ev, det, "ATS-BASIS-001")
    basis_policy = ev.ir.basis_policy or {}
    declared_required = bool(basis_policy.get("declared"))
    for claim in ev.ir.material_claims():
        c.saw(BASIS001.subcheck_id)
        basis = claim.data.get("semantic_basis")
        requirement = claim.requirement
        if basis is None and requirement is not None:
            basis = requirement.get("semantic_basis")
        if basis is not None:
            continue
        span = claim.span()
        if requirement is not None:
            span = {"kind": "json_pointer", "locator": claim.field_pointer("requirement")}
        if declared_required:
            summary = (
                f"Material claim {claim.claim_id} declares no semantic_basis while the "
                "document's basis_policy requires a declared basis for every material "
                "value. A reader cannot tell whether the claim states source truth or "
                "author judgment, so verification and safe transformation are impossible."
            )
        else:
            summary = (
                f"Material claim {claim.claim_id} declares no semantic_basis. Its semantic "
                "values are not mechanically derivable on their face, so the basis "
                "recommended by ATS-BASIS-001 is undeclared."
            )
        c.flag(
            BASIS001.subcheck_id,
            issue_code="material-claim-without-basis",
            summary=summary,
            spans=[span],
        )
    return c.result((BASIS001,))


# -- ATS-BASIS-002 ----------------------------------------------------------

BASIS002 = SubcheckSpec(
    subcheck_id="inferred-source-promoted-to-explicit",
    decides=True,
    spec_ref="ATS-1 4.25, 7.19",
    vocabulary_source="the semantic_basis values enumerated at ATS-1 4.25",
    description=(
        "An output claim declares basis EXPLICIT while the source basis recorded for the "
        "same value is INFERRED or UNAVAILABLE, silently converting source material into "
        "an explicit source-authoritative fact."
    ),
)

BASIS002_SPEC = DetectorSpec(
    rule_id="ATS-BASIS-002",
    detector_class="D1",
    power=DecisionPower.DECIDES,
    subchecks=(BASIS002,),
    unavailable_conditions=(
        "The IR carries no extensions.source_basis ledger, so no source-side basis is "
        "recorded to compare against; the required transformation inputs (source_ir, "
        "output_ir) are unavailable and the rule reports UNAVAILABLE rather than PASS by "
        "absence.",
    ),
    known_limits=(
        "The comparison is mechanical: a claim declaring basis EXPLICIT while the source "
        "basis recorded for the same value is INFERRED or UNAVAILABLE is a silent "
        "promotion. Whether the source truly established the value is a semantic judgement "
        "this detector does not make.",
        "The basis enum is schema-enforced; only declared values are compared. An "
        "authorized semantic change recorded in extensions.authorized_change (spec 11.4) "
        "declares the promotion explicitly and suppresses the finding.",
    ),
)
SPECS["ATS-BASIS-002"] = BASIS002_SPEC


def _source_basis_ledger(ir: IrDocument) -> dict[str, str]:
    """The merged source-side basis ledger, if any.

    Reads the document-level ``extensions.source_basis`` map and every
    claim-level ``extensions.source_basis`` map; entries map a source ref to
    the basis recorded for it in the source.
    """
    out: dict[str, str] = {}
    document_ext = ir.raw.get("extensions", {})
    if isinstance(document_ext, Mapping):
        ledger = document_ext.get("source_basis")
        if isinstance(ledger, Mapping):
            out.update({str(k): str(v) for k, v in ledger.items()})
    for claim in ir.all_claims():
        claim_ext = claim.data.get("extensions")
        if not isinstance(claim_ext, Mapping):
            continue
        ledger = claim_ext.get("source_basis")
        if isinstance(ledger, Mapping):
            out.update({str(k): str(v) for k, v in ledger.items()})
    return out


def _has_source_basis_ledger(ir: IrDocument) -> bool:
    return bool(_source_basis_ledger(ir))


def _authorized_changes(ir: IrDocument) -> list[Mapping[str, Any]]:
    """The authorized semantic changes declared for this rule (spec 11.4)."""
    document_ext = ir.raw.get("extensions", {})
    if not isinstance(document_ext, Mapping):
        return []
    record = document_ext.get("authorized_change")
    if record is None:
        return []
    if isinstance(record, list):
        return [r for r in record if isinstance(r, Mapping)]
    if isinstance(record, Mapping):
        return [record]
    return []


def _is_authorized(authorized: list[Mapping[str, Any]], source_basis: str) -> bool:
    """True when an authorized-change record covers this exact promotion."""
    for record in authorized:
        if record.get("rule_id") != "ATS-BASIS-002":
            continue
        if record.get("from_basis") == source_basis and record.get("to_basis") == "EXPLICIT":
            return True
    return False


def _basis_002_body(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    c = Collector(ev, det, "ATS-BASIS-002")
    ledger = _source_basis_ledger(ev.ir)
    authorized = _authorized_changes(ev.ir)
    for claim in ev.ir.all_claims():
        basis = claim.data.get("semantic_basis")
        requirement = claim.requirement
        if not isinstance(basis, Mapping) and requirement is not None:
            # The schema permits basis at either level; a requirement-slot
            # declaration is the claim's basis (same fallback as BASIS-001).
            basis = requirement.get("semantic_basis")
        for source_ref in claim.refs("source_refs"):
            # The subcheck runs for every source-bearing claim: a non-EXPLICIT
            # basis over INFERRED/UNAVAILABLE source is an inspected, passed
            # comparison, not an uninspected one (ADR-0002).
            c.saw(BASIS002.subcheck_id)
            if not isinstance(basis, Mapping) or basis.get("basis") != "EXPLICIT":
                continue
            source_basis = ledger.get(source_ref)
            if source_basis not in PROMOTION_SOURCE_BASES:
                continue
            if _is_authorized(authorized, source_basis):
                continue
            c.flag(
                BASIS002.subcheck_id,
                issue_code="inferred-source-promoted-to-explicit",
                summary=(
                    f"Claim {claim.claim_id} declares semantic_basis EXPLICIT while the "
                    f"source basis recorded for {source_ref!r} is {source_basis}. The "
                    "transformation silently converts inferred or unavailable source "
                    "material into an explicit source-authoritative fact, which "
                    "ATS-BASIS-002 forbids."
                ),
                spans=[claim.span()],
                evidence_spans=[
                    {"kind": "json_pointer", "locator": claim.field_pointer("semantic_basis")}
                ],
            )
    return c.result((BASIS002,))


@register("ATS-BASIS-002")
def detect_ats_basis_002(ev: IrEvaluation) -> RuleResult:
    """A transformation MUST NOT silently promote INFERRED or UNAVAILABLE source material."""
    return run_with_optional_inputs(
        ev,
        BASIS002_SPEC,
        _basis_002_body,
        supplied=_has_source_basis_ledger,
        missing=("source_ir", "output_ir"),
    )

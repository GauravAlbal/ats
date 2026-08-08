"""Preservation rules: ATS-PRES-001, ATS-PRES-002, ATS-PRES-003.

ATS-PRES-001 and ATS-PRES-002 are TRANSFORM rules. Their required inputs are a
source IR, an output IR, a retention contract, and an authorization set.
``ats ir lint`` receives one IR and none of the others, so neither rule can be
decided here.

Under the ASSESS and SPECIFY defaults both rules are ``disabled``, and the
result is NOT_APPLICABLE. Under TRANSFORM both are ``required``, and the result
is UNAVAILABLE — which, per Section 6.4, means an implementation MUST NOT report
``preservation: PASS``. That is exactly the intended outcome: the v0 IR linter
cannot establish preservation, and it says so rather than staying silent.

ATS-PRES-003 (draft.2 amendment D-B) protects the P1 relation set under
compression. Its required inputs are a source IR, an output IR, and an output
trace; without a trace the rule reports UNAVAILABLE naming ``trace``, never
PASS. When the artifact carries the output trace in
``extensions.output_trace``, the source side is the IR's own typed relations
(plus any ``extensions.source_relations`` ledger entries), and realization is
decided over the trace's ``p1_relations``: a protected relation dropped from
the trace is a violation. An ``extensions.authorized_semantic_change`` record
(spec 11.4) declares the drop as authorized and suppresses the finding.
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
    run_with_optional_inputs,
    undecidable,
)

_TRANSFORM_ONLY = (
    "`ats ir lint` evaluates one artifact. Preservation compares a source artifact against an "
    "output artifact under a retention contract, and no v0 command constructs that pair.",
)

_UNWAIVABLE = (
    "Section 6.4 makes this rule unwaivable: while it is unavailable, preservation MUST NOT be "
    "reported as PASS. The conformance vector reflects that directly.",
)

undecidable(
    DetectorSpec(
        rule_id="ATS-PRES-001",
        detector_class="none",
        power=DecisionPower.UNDECIDABLE,
        subchecks=(
            SubcheckSpec(
                subcheck_id="p0-exact-retention",
                decides=False,
                spec_ref="ATS-1 11.3.1, 11.11",
                description=(
                    "Comparing every retained P0 field between source and output requires both "
                    "artifacts and the authorizations for any intended change."
                ),
            ),
        ),
        unavailable_conditions=_TRANSFORM_ONLY,
        known_limits=(
            *_UNWAIVABLE,
            "The output linter checks that declared P0 values are rendered exactly, which is "
            "evidence about one rendering, not about a source-to-output transformation.",
        ),
    )
)

undecidable(
    DetectorSpec(
        rule_id="ATS-PRES-002",
        detector_class="none",
        power=DecisionPower.UNDECIDABLE,
        subchecks=(
            SubcheckSpec(
                subcheck_id="p1-relation-retention",
                decides=False,
                spec_ref="ATS-1 11.3.2, 11.11",
                description=(
                    "Confirming that every retained P1 relation keeps its type, direction, scope, "
                    "and force requires the source and output meaning ledgers together."
                ),
            ),
        ),
        unavailable_conditions=_TRANSFORM_ONLY,
        known_limits=(
            *_UNWAIVABLE,
            "The output linter checks that material relations are declared by some rendered block, "
            "which establishes declaration, not preservation across a transformation.",
        ),
    )
)


# -- ATS-PRES-003 -----------------------------------------------------------

#: Relation types whose category ATS-1 11.3.2 P1 protects. The P1 list names
#: categories, not types; each type below is quoted from the IR relation enum
#: (ats_common_v1.schema.json#/$defs/relation.type) and mapped to the P1
#: category it realizes. The D-B additions (authority, temporal ordering,
#: acceptance dependency) are not representable as IR relation types; a
#: ``source_relations`` ledger in extensions may record them by protected kind.
PROTECTED_RELATION_TYPES = (
    "consistent_with",  # support
    "supports",  # support
    "strongly_supports",  # support
    "contradicts",  # contradiction
    "qualifies",  # qualification
    "depends_on",  # dependency
    "condition_for",  # condition
    "exception_to",  # exception
    "derived_from",  # inference provenance
    "associated_with",  # causal direction and force
    "predicts",  # causal direction and force
    "contributes_to",  # causal direction and force
    "causes",  # causal direction and force
    "necessary_for",  # ordering dependency
    "sufficient_for",  # ordering dependency
    "contrasts_with",  # comparison dimension
    "alternative_to",  # alternative-hypothesis relationships
    "updates",  # update and reversal
    "reverses",  # update and reversal
)

PRES003 = SubcheckSpec(
    subcheck_id="protected-relation-dropped",
    decides=True,
    spec_ref="ATS-1 11.3.2",
    vocabulary_source="the protected relation kinds enumerated at ATS-1 11.3.2 P1",
    description=(
        "A protected relation declared in the source IR appears in no output-trace "
        "p1_relations entry, so the transformation removed or made it materially implicit."
    ),
)

PRES003_SPEC = DetectorSpec(
    rule_id="ATS-PRES-003",
    detector_class="D1",
    power=DecisionPower.DECIDES,
    subchecks=(PRES003,),
    unavailable_conditions=(
        "No output trace is supplied, so protected-relation realization cannot be verified; "
        "the rule reports UNAVAILABLE rather than PASS (never PASS by absence).",
    ),
    known_limits=(
        "Realization is decided over the trace's p1_relations: a protected relation is "
        "realized when its id appears there with its declared type and direction. Whether "
        "the rendered prose genuinely preserves the relation's semantic force remains a "
        "semantic judgement.",
        "The P1 categories added by draft.2 amendment D-B (authority, temporal ordering, "
        "acceptance dependency) are not representable in the current IR relation-type "
        "enum; when a source_relations ledger in extensions records them by protected "
        "kind, they are checked like any other protected relation.",
    ),
)
SPECS["ATS-PRES-003"] = PRES003_SPEC


def _output_trace(ir: IrDocument) -> Mapping[str, Any] | None:
    """The output-trace document carried in ``extensions.output_trace``, if any."""
    extensions = ir.raw.get("extensions")
    if not isinstance(extensions, Mapping):
        return None
    trace = extensions.get("output_trace")
    return trace if isinstance(trace, Mapping) else None


def _has_output_trace(ir: IrDocument) -> bool:
    return _output_trace(ir) is not None


def _authorized_drops(ir: IrDocument) -> list[Mapping[str, Any]]:
    """Authorized semantic changes that permit dropping a protected relation (spec 11.4)."""
    extensions = ir.raw.get("extensions")
    if not isinstance(extensions, Mapping):
        return []
    record = extensions.get("authorized_semantic_change")
    if isinstance(record, list):
        return [r for r in record if isinstance(r, Mapping)]
    if isinstance(record, Mapping):
        return [record]
    return []


def _realized_relation_ids(trace: Mapping[str, Any]) -> set[str]:
    """Every relation id any trace block declares in its ``p1_relations``."""
    out: set[str] = set()
    for block in trace.get("blocks", ()):
        if not isinstance(block, Mapping):
            continue
        for entry in block.get("p1_relations", ()):
            if isinstance(entry, Mapping) and entry.get("relation_id"):
                out.add(str(entry["relation_id"]))
    return out


def _pres_003_body(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    c = Collector(ev, det, "ATS-PRES-003")
    trace = _output_trace(ev.ir)
    assert trace is not None
    realized = _realized_relation_ids(trace)
    authorized = _authorized_drops(ev.ir)

    protected: list[tuple[str, str, str]] = []  # (relation_id, type, pointer)
    for relation in ev.ir.relations.values():
        if relation.type in PROTECTED_RELATION_TYPES:
            protected.append(
                (relation.relation_id, relation.type, relation.pointer)
            )
    extensions = ev.ir.raw.get("extensions")
    if isinstance(extensions, Mapping):
        ledger = extensions.get("source_relations")
        if isinstance(ledger, list):
            for entry in ledger:
                if not isinstance(entry, Mapping) or not entry.get("relation_id"):
                    continue
                protected.append(
                    (
                        str(entry["relation_id"]),
                        str(entry.get("kind", "protected_relation")),
                        "#/extensions/source_relations",
                    )
                )

    for relation_id, rel_type, ptr in protected:
        c.saw(PRES003.subcheck_id)
        if relation_id in realized:
            continue
        if any(
            record.get("rule_id") == "ATS-PRES-003"
            and record.get("changed_relation") == relation_id
            for record in authorized
        ):
            continue
        c.flag(
            PRES003.subcheck_id,
            issue_code="protected-relation-dropped",
            summary=(
                f"The protected relation {relation_id!r} ({rel_type}) declared in the "
                "source IR appears in no output-trace p1_relations entry. The "
                "transformation removed or made the relation materially implicit, which "
                "ATS-PRES-003 forbids under surface compression."
            ),
            spans=[{"kind": "json_pointer", "locator": ptr}],
        )
    return c.result((PRES003,))


@register("ATS-PRES-003")
def detect_ats_pres_003(ev: IrEvaluation) -> RuleResult:
    """A transformation MUST NOT remove a protected relation solely to compress surface."""
    return run_with_optional_inputs(
        ev,
        PRES003_SPEC,
        _pres_003_body,
        supplied=_has_output_trace,
        missing=("trace",),
    )

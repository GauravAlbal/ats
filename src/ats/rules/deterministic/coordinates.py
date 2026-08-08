"""Stable semantic coordinate rules: ATS-COORD-001, ATS-COORD-002.

Spec Section 4.23 defines a stable semantic coordinate and the draft.2
amendment D-C promotes the eight protected coordinate kinds; Section 7.17
carries the ``stable_coordinates`` block. Both rules are exact set and
reference checks over declared ids, so both declare a complete decision
procedure (D1, DECIDES).

ATS-COORD-001 preserves the coordinate set: every protected coordinate used in
the IR must be declared in ``stable_coordinates``, and every declared
coordinate must resolve to a real object in the IR. A document that declares
no ``stable_coordinates`` block declares no preservation set, so the rule is
not triggered and decides PASS with the subchecks noting the absent block.

ATS-COORD-002 guards coordinate integrity: no coordinate id may be declared
twice or used twice as a requirement or decision coordinate, and every
``dependency_target`` and ``acceptance_criterion_id`` reference must resolve
to a declared coordinate when the block exists, or to a claim id when it does
not (a dangling reference is still a violation).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from ...ir.model import IrDocument, IrEvaluation, pointer
from ...rules.results import DecisionPower, Detector, Finding
from ._support import Collector, DetectorSpec, SubcheckSpec, detector

#: The protected coordinate kinds enumerated verbatim at ATS-1 4.23 (draft.2
#: amendment D-C). Only ids of these kinds may appear in the
#: ``stable_coordinates`` block; the vocabulary is quoted from the spec, not
#: assembled by the implementation.
PROTECTED_COORDINATE_KINDS = (
    "requirement_id",
    "decision_id",
    "acceptance_criterion_id",
    "work_item_id",
    "protocol_id",
    "protocol_version",
    "dependency_target",
    "authority_reference",
)


COORD001_USED = SubcheckSpec(
    subcheck_id="coordinate-used-but-undeclared",
    decides=True,
    spec_ref="ATS-1 4.23, 7.17",
    vocabulary_source="the protected coordinate kinds enumerated at ATS-1 4.23",
    description=(
        "A protected coordinate used in the IR (requirement_id, decision_id, "
        "acceptance_criterion_id, dependency_target, or cross-document authority "
        "reference) is not declared in the document's stable_coordinates block."
    ),
)
COORD001_DECLARED = SubcheckSpec(
    subcheck_id="declared-coordinate-unresolved",
    decides=True,
    spec_ref="ATS-1 4.23, 7.17",
    vocabulary_source="none",
    description=(
        "A coordinate declared in stable_coordinates resolves to no claim, requirement, "
        "relation, or update indicator id in the IR."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-COORD-001",
        detector_class="D1",
        power=DecisionPower.DECIDES,
        subchecks=(COORD001_USED, COORD001_DECLARED),
        vacuous_pass=True,
        unavailable_conditions=(
            "A document with no stable_coordinates block declares no coordinate set to "
            "preserve, and a document that uses no protected coordinate id has nothing to "
            "resolve.",
        ),
        known_limits=(
            "Declaration and resolution are exact set checks over the IR: every protected "
            "coordinate used must be declared, and every declared coordinate must resolve to "
            "a real claim, requirement, relation, or update indicator. Whether a coordinate "
            "still denotes the same semantic object after a transformation is a semantic "
            "judgement this mechanical check does not make.",
            "Only the coordinate fields the IR schema carries are read (requirement_id, "
            "decision_id, acceptance_criterion_id, dependency_target). A cross-document "
            "authority reference that is declared in the block but never used is resolved "
            "against the IR object ids, so an external coordinate that names no object here "
            "is reported.",
        ),
    )
)
def coord_001(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Every protected coordinate used MUST be declared, and every declared coordinate MUST resolve."""
    c = Collector(ev, det, "ATS-COORD-001")
    block = ev.ir.stable_coordinates
    if not block:
        # Hard negative (draft.2 7.17 makes the block optional): no coordinate
        # set is declared, so there is nothing to preserve and the rule is not
        # triggered. Each subcheck notes the absent block rather than claiming
        # it inspected a set that does not exist.
        return (
            [],
            [
                {
                    "subcheck_id": COORD001_USED.subcheck_id,
                    "status": "NOT_APPLICABLE",
                    "spec_ref": COORD001_USED.spec_ref,
                    "detail": (
                        "the document declares no stable_coordinates block, so no coordinate "
                        "preservation set is declared for this rule to enforce"
                    ),
                    "observed": 0,
                },
                {
                    "subcheck_id": COORD001_DECLARED.subcheck_id,
                    "status": "NOT_APPLICABLE",
                    "spec_ref": COORD001_DECLARED.spec_ref,
                    "detail": (
                        "the document declares no stable_coordinates block, so no declared "
                        "coordinate can be resolved"
                    ),
                    "observed": 0,
                },
            ],
        )

    declared = {entry["id"] for entry in block}
    universe = _resolution_universe(ev.ir)

    for coord_id, (kind, ptr) in sorted(_used_coordinates(ev.ir).items()):
        c.saw(COORD001_USED.subcheck_id)
        if coord_id in declared:
            continue
        c.flag(
            COORD001_USED.subcheck_id,
            issue_code="coordinate-used-but-undeclared",
            summary=(
                f"The {kind} {coord_id!r} is used in the IR but is absent from the "
                "stable_coordinates block. A stable semantic coordinate used without "
                "declaration cannot join this artifact to its downstream consumers, so "
                "specification, planning, review, and receipts lose the coordinate."
            ),
            spans=[{"kind": "json_pointer", "locator": ptr}],
        )

    for entry in block:
        c.saw(COORD001_DECLARED.subcheck_id)
        coord_id = entry["id"]
        if entry["kind"] in EXTERNAL_KINDS:
            # Cross-document or externally-scoped kinds (protocol ids, work-item
            # ids, authority references, dependency targets) legitimately name
            # objects outside this IR. This mirrors the package validator's kind
            # split: only document-scoped kinds must resolve in-IR.
            continue
        if coord_id in universe:
            continue
        c.flag(
            COORD001_DECLARED.subcheck_id,
            issue_code="declared-coordinate-unresolved",
            summary=(
                f"The declared {entry['kind']} coordinate {coord_id!r} resolves to no claim, "
                "requirement, relation, or update indicator id in the IR. A coordinate that "
                "names nothing cannot join anything."
            ),
            spans=[
                {
                    "kind": "json_pointer",
                    "locator": pointer("stable_coordinates", i, "id"),
                }
                for i, e in enumerate(block)
                if e["id"] == coord_id
            ],
        )

    return c.result((COORD001_USED, COORD001_DECLARED))


# -- ATS-COORD-002 ----------------------------------------------------------

COORD002_DUPLICATE = SubcheckSpec(
    subcheck_id="duplicate-coordinate-id",
    decides=True,
    spec_ref="ATS-1 4.23, 7.17",
    vocabulary_source="none",
    description=(
        "The same coordinate id is declared twice in stable_coordinates, so coordinate "
        "integrity is broken."
    ),
)
COORD002_DEPENDENCY = SubcheckSpec(
    subcheck_id="dependency-target-unresolved",
    decides=True,
    spec_ref="ATS-1 4.23, 7.17",
    vocabulary_source="none",
    description=(
        "A relation's dependency_target does not resolve to a declared coordinate or IR "
        "object."
    ),
)
COORD002_ACCEPTANCE = SubcheckSpec(
    subcheck_id="acceptance-criterion-ref-unresolved",
    decides=True,
    spec_ref="ATS-1 4.23, 7.17",
    vocabulary_source="none",
    description=(
        "A requirement's acceptance_criterion_id does not resolve to a declared coordinate "
        "or IR object."
    ),
)


@detector(
    DetectorSpec(
        rule_id="ATS-COORD-002",
        detector_class="D1",
        power=DecisionPower.DECIDES,
        subchecks=(COORD002_DUPLICATE, COORD002_DEPENDENCY, COORD002_ACCEPTANCE),
        vacuous_pass=True,
        unavailable_conditions=(
            "A document with no stable_coordinates block and no coordinate-bearing "
            "references declares no coordinate integrity to check.",
        ),
        known_limits=(
            "Uniqueness and reference resolution are exact mechanical checks over declared "
            "ids. Two distinct coordinates that denote the same semantic object are not "
            "detected as duplicates, and two requirements sharing one acceptance criterion "
            "are legitimate references to one object, not a duplicate coordinate.",
        ),
    )
)
def coord_002(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Stable semantic coordinates MUST be unique, and every coordinate reference MUST resolve."""
    c = Collector(ev, det, "ATS-COORD-002")
    block = ev.ir.stable_coordinates
    declared = {entry["id"] for entry in block}
    claim_ids = set(ev.ir.claims)

    # -- duplicates ---------------------------------------------------------
    # Within the declared block, the schema's uniqueItems compares whole
    # entries, so the same id declared twice with different source pointers
    # validates yet still breaks coordinate integrity; the detector catches it.
    declared_counts = Counter(entry["id"] for entry in block)
    for coord_id, count in sorted(declared_counts.items()):
        if count < 2:
            continue
        c.saw(COORD002_DUPLICATE.subcheck_id)
        c.flag(
            COORD002_DUPLICATE.subcheck_id,
            issue_code="duplicate-coordinate-id",
            summary=(
                f"The coordinate {coord_id!r} is declared {count} times in "
                "stable_coordinates. Duplicate coordinates make reference resolution "
                "ambiguous and silently corrupt joins."
            ),
            spans=[
                {
                    "kind": "json_pointer",
                    "locator": pointer("stable_coordinates", i, "id"),
                }
                for i, entry in enumerate(block)
                if entry["id"] == coord_id
            ],
        )

    # A requirement or decision coordinate must be unique across the claims
    # that carry it; sharing an acceptance criterion or dependency target is a
    # reference to one object and is not a duplicate.
    requirement_uses: dict[str, list[str]] = {}
    decision_uses: dict[str, list[str]] = {}
    for claim in ev.ir.all_claims():
        requirement = claim.requirement
        if requirement is not None:
            rid = requirement.get("requirement_id")
            if rid:
                requirement_uses.setdefault(rid, []).append(
                    claim.field_pointer("requirement", "requirement_id")
                )
        decision_id = claim.data.get("decision_id")
        if decision_id:
            decision_uses.setdefault(decision_id, []).append(claim.field_pointer("decision_id"))
    for coord_id, pointers in sorted(requirement_uses.items()):
        if len(pointers) < 2:
            continue
        c.saw(COORD002_DUPLICATE.subcheck_id)
        c.flag(
            COORD002_DUPLICATE.subcheck_id,
            issue_code="duplicate-coordinate-id",
            summary=(
                f"The requirement coordinate {coord_id!r} is used by more than one claim, so "
                "the coordinate is not unique within the artifact and references to it are "
                "ambiguous."
            ),
            spans=[{"kind": "json_pointer", "locator": p} for p in pointers],
        )
    for coord_id, pointers in sorted(decision_uses.items()):
        if len(pointers) < 2:
            continue
        c.saw(COORD002_DUPLICATE.subcheck_id)
        c.flag(
            COORD002_DUPLICATE.subcheck_id,
            issue_code="duplicate-coordinate-id",
            summary=(
                f"The decision coordinate {coord_id!r} is used by more than one claim, so "
                "the coordinate is not unique within the artifact."
            ),
            spans=[{"kind": "json_pointer", "locator": p} for p in pointers],
        )

    # -- reference resolution ------------------------------------------------
    # With a stable_coordinates block, a coordinate reference must resolve to a
    # declared coordinate. Without the block, it must still resolve to a claim
    # id; a reference to nothing is a dangling reference either way.
    for relation in ev.ir.relations.values():
        dep = relation.data.get("dependency_target")
        if not dep:
            continue
        c.saw(COORD002_DEPENDENCY.subcheck_id)
        if dep in declared or (not block and dep in claim_ids):
            continue
        c.flag(
            COORD002_DEPENDENCY.subcheck_id,
            issue_code="dependency-target-unresolved",
            summary=(
                f"Relation {relation.relation_id} declares dependency_target {dep!r}, which "
                "resolves to no declared coordinate"
                + ("" if block else " and no claim id")
                + ". The dependency silently decouples from its declared target."
            ),
            spans=[
                {
                    "kind": "json_pointer",
                    "locator": relation.pointer + pointer("dependency_target"),
                }
            ],
        )

    for claim in ev.ir.all_claims():
        requirement = claim.requirement
        if requirement is None:
            continue
        ac_id = requirement.get("acceptance_criterion_id")
        if not ac_id:
            continue
        c.saw(COORD002_ACCEPTANCE.subcheck_id)
        if ac_id in declared or (not block and ac_id in claim_ids):
            continue
        c.flag(
            COORD002_ACCEPTANCE.subcheck_id,
            issue_code="acceptance-criterion-ref-unresolved",
            summary=(
                f"Requirement {requirement['requirement_id']} references acceptance "
                f"criterion {ac_id!r}, which resolves to no declared coordinate"
                + ("" if block else " and no claim id")
                + ". Acceptance cannot be joined to its criterion."
            ),
            spans=[
                {
                    "kind": "json_pointer",
                    "locator": claim.field_pointer("requirement", "acceptance_criterion_id"),
                }
            ],
        )

    return c.result((COORD002_DUPLICATE, COORD002_DEPENDENCY, COORD002_ACCEPTANCE))


# -- shared helpers ---------------------------------------------------------


#: Coordinate kinds that legitimately name objects outside this IR (cross-document
#: protocol ids, work-item ids, authority references, dependency targets). They are
#: declared without an in-IR resolution obligation, mirroring the package validator's
#: kind split; only document-scoped kinds must resolve to in-IR objects.
EXTERNAL_KINDS: frozenset[str] = frozenset(
    {"protocol_id", "protocol_version", "work_item_id", "dependency_target",
     "authority_reference"}
)


def _used_coordinates(ir: IrDocument) -> dict[str, tuple[str, str]]:
    """Every protected coordinate the IR actually uses: id -> (kind, pointer)."""
    uses: dict[str, tuple[str, str]] = {}
    for claim in ir.all_claims():
        requirement = claim.requirement
        if requirement is not None:
            rid = requirement.get("requirement_id")
            if rid:
                uses.setdefault(
                    rid, ("requirement_id", claim.field_pointer("requirement", "requirement_id"))
                )
            ac_id = requirement.get("acceptance_criterion_id")
            if ac_id:
                uses.setdefault(
                    ac_id,
                    (
                        "acceptance_criterion_id",
                        claim.field_pointer("requirement", "acceptance_criterion_id"),
                    ),
                )
        decision_id = claim.data.get("decision_id")
        if decision_id:
            uses.setdefault(decision_id, ("decision_id", claim.field_pointer("decision_id")))
    for relation in ir.relations.values():
        dep = relation.data.get("dependency_target")
        if dep:
            uses.setdefault(
                dep, ("dependency_target", relation.pointer + pointer("dependency_target"))
            )
    return uses


def _resolution_universe(ir: IrDocument) -> set[str]:
    """Every id a declared coordinate may legitimately resolve to.

    Object ids (claims, evidence, relations, update indicators) plus every
    coordinate value used in the IR: a declared acceptance-criterion coordinate
    commonly exists only as a reference (draft.2 7.17 permits coordinates that
    name objects declared elsewhere).
    """
    ids = set(ir.claims) | set(ir.evidence) | set(ir.relations) | set(ir.indicators)
    for coord_id in _used_coordinates(ir):
        ids.add(coord_id)
    return ids

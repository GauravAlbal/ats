"""Internal reference resolution for a TextIR document.

The schema constrains each reference to be an identifier string. Whether that
identifier resolves to an object in the same artifact is a cross-object
property the schema cannot express, so it is checked here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Literal

from .model import IrDocument

#: Which object kinds may satisfy each reference field, from the semantic model
#: in spec Sections 7.9 through 7.14.
REFERENCE_TARGETS: dict[str, tuple[str, ...]] = {
    "source_refs": ("evidence",),
    "assumption_refs": ("claim",),
    "boundary_refs": ("claim",),
    "exception_refs": ("claim",),
    "relation.source_id": ("claim", "evidence"),
    "relation.target_id": ("claim", "evidence"),
    "relation.basis_refs": ("claim", "evidence"),
    "update_indicator.target_claim_refs": ("claim",),
}

#: Claim roles a role-typed reference must point at (Section 7.4).
ROLE_TARGETS: dict[str, str] = {
    "assumption_refs": "assumption",
    "boundary_refs": "boundary",
    "exception_refs": "exception",
}

#: Protected-coordinate reference fields (draft.2 D-C, spec 7.17). Each
#: resolves against the union of document-declared stable-coordinate ids and
#: claim ids: a coordinate may name an object declared elsewhere (a work item,
#: a protocol) or a claim inside this artifact. When no ``stable_coordinates``
#: block is declared the refs must still resolve against claim ids, so the
#: resolution universe is independent of whether the block is present.
COORDINATE_REF_FIELDS: tuple[str, ...] = (
    "relation.dependency_target",
    "requirement.acceptance_criterion_id",
)


@dataclass(frozen=True, slots=True)
class ReferenceProblem:
    kind: Literal["dangling", "wrong_kind", "wrong_role", "self_reference"]
    field: str
    reference: str
    pointer: str
    detail: str


def iter_reference_problems(ir: IrDocument) -> Iterator[ReferenceProblem]:
    """Yield every reference that does not resolve as its field requires."""
    kinds = ir.object_ids

    def check(field: str, ref: str, ptr: str) -> Iterator[ReferenceProblem]:
        allowed = REFERENCE_TARGETS[field]
        kind = kinds.get(ref)
        if kind is None:
            yield ReferenceProblem(
                "dangling",
                field,
                ref,
                ptr,
                f"{field} cites {ref!r}, which is not an object in this artifact",
            )
            return
        if kind not in allowed:
            yield ReferenceProblem(
                "wrong_kind",
                field,
                ref,
                ptr,
                f"{field} must cite {' or '.join(allowed)}, but {ref!r} is a {kind}",
            )
            return
        expected_role = ROLE_TARGETS.get(field)
        if expected_role and kind == "claim":
            actual = ir.claims[ref].role
            if actual != expected_role:
                yield ReferenceProblem(
                    "wrong_role",
                    field,
                    ref,
                    ptr,
                    f"{field} must cite a claim with role {expected_role!r}, "
                    f"but {ref!r} has role {actual!r}",
                )

    coordinate_ids = {entry["id"] for entry in ir.stable_coordinates}
    claim_ids = set(ir.claims)

    def check_coordinate_ref(field: str, ref: str, ptr: str) -> Iterator[ReferenceProblem]:
        if ref in claim_ids or ref in coordinate_ids:
            return
        yield ReferenceProblem(
            "dangling",
            field,
            ref,
            ptr,
            f"{field} cites {ref!r}, which is neither a claim id nor a declared stable "
            "coordinate (spec 7.17)",
        )

    for claim in ir.all_claims():
        for field in ("source_refs", "assumption_refs", "boundary_refs", "exception_refs"):
            for i, ref in enumerate(claim.refs(field)):
                yield from check(field, ref, claim.field_pointer(field, i))
        requirement = claim.requirement
        if requirement is not None and requirement.get("acceptance_criterion_id"):
            yield from check_coordinate_ref(
                "requirement.acceptance_criterion_id",
                requirement["acceptance_criterion_id"],
                claim.field_pointer("requirement", "acceptance_criterion_id"),
            )

    for section in ir.sections:
        for relation in section.relations:
            yield from check("relation.source_id", relation.source_id, relation.pointer + "/source_id")
            yield from check("relation.target_id", relation.target_id, relation.pointer + "/target_id")
            if relation.data.get("dependency_target"):
                yield from check_coordinate_ref(
                    "relation.dependency_target",
                    relation.data["dependency_target"],
                    f"{relation.pointer}/dependency_target",
                )
            if relation.source_id == relation.target_id:
                yield ReferenceProblem(
                    "self_reference",
                    "relation",
                    relation.source_id,
                    relation.pointer,
                    f"relation {relation.relation_id!r} points an object at itself, which "
                    "carries no semantic relationship",
                )
            for i, ref in enumerate(relation.basis_refs):
                yield from check("relation.basis_refs", ref, f"{relation.pointer}/basis_refs/{i}")
        for indicator in section.update_indicators:
            for i, ref in enumerate(indicator.target_claim_refs):
                yield from check(
                    "update_indicator.target_claim_refs",
                    ref,
                    f"{indicator.pointer}/target_claim_refs/{i}",
                )


def unresolved_glossary_refs(
    ir: IrDocument, policy_glossary_refs: Iterable[str] = ()
) -> list[tuple[str, str]]:
    """Assumed term bases the resolved policy does not declare.

    ``audience.assumed_glossary_refs`` names term bases, not concepts inside
    this artifact's own glossary. Spec Section 7.2 says audience assumptions
    require policy or artifact evidence, so a term base the policy snapshot
    does not list is an unverified assumption and is surfaced.
    """
    declared = set(policy_glossary_refs) | set(ir.glossary_by_concept)
    out: list[tuple[str, str]] = []
    for i, ref in enumerate(ir.audience.get("assumed_glossary_refs", ())):
        if ref in declared:
            continue
        out.append((ref, f"/audience/assumed_glossary_refs/{i}"))
    return out


def unresolved_concept_refs(ir: IrDocument) -> list[tuple[str, str]]:
    """Glossary entries whose canonical term is blank or whose scope is absent."""
    out: list[tuple[str, str]] = []
    for i, entry in enumerate(ir.glossary):
        if not str(entry.get("canonical_term", "")).strip():
            out.append((entry.get("concept_id", "?"), f"/glossary/{i}/canonical_term"))
        if not str(entry.get("scope", "")).strip():
            out.append((entry.get("concept_id", "?"), f"/glossary/{i}/scope"))
    return out

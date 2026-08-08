"""Internal reference resolution.

Sections 7.9 through 7.14 fix what each reference field may point at. The
schema constrains a reference to be an identifier string; whether it resolves
to an object of the right kind and role is a cross-object property only this
layer can check.
"""

from __future__ import annotations

import copy

import pytest

from ats.ir.model import IrDocument
from ats.ir.references import (
    REFERENCE_TARGETS,
    ROLE_TARGETS,
    iter_reference_problems,
    unresolved_concept_refs,
    unresolved_glossary_refs,
)


def problems(document):
    return list(iter_reference_problems(IrDocument.from_document(document)))


def test_conforming_fixtures_resolve_every_reference(load_ir) -> None:
    """Spec 7.9-7.14: every declared reference points at a real object."""
    for name in ("assess_conforming", "specify_conforming", "composed_profiles"):
        assert problems(load_ir(name)) == [], name


def test_a_dangling_source_reference_is_reported(load_ir) -> None:
    """Spec 7.9: evidence attribution requires the evidence object to exist."""
    found = problems(load_ir("dangling_reference"))
    assert len(found) == 1
    problem = found[0]
    assert problem.kind == "dangling"
    assert problem.field == "source_refs"
    assert problem.reference == "e-does-not-exist"
    assert problem.pointer == "/sections/0/claims/0/source_refs/1"
    assert "not an object in this artifact" in problem.detail


def test_a_reference_to_the_wrong_kind_of_object_is_reported(load_ir) -> None:
    """Spec 7.9: ``source_refs`` cites evidence, not another claim."""
    assert REFERENCE_TARGETS["source_refs"] == ("evidence",)
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["claims"][0]["source_refs"] = ["a1"]

    (problem,) = problems(document)
    assert problem.kind == "wrong_kind"
    assert problem.reference == "a1"
    assert "must cite evidence" in problem.detail


def test_a_role_typed_reference_must_cite_that_role(load_ir) -> None:
    """Spec 7.12 and 7.13: an assumption reference cites a claim with role assumption."""
    assert ROLE_TARGETS["assumption_refs"] == "assumption"
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["claims"][0]["assumption_refs"] = ["b1"]

    (problem,) = problems(document)
    assert problem.kind == "wrong_role"
    assert problem.reference == "b1"
    assert "role 'assumption'" in problem.detail
    assert "'boundary'" in problem.detail


def test_a_relation_pointing_at_itself_is_reported(load_ir) -> None:
    """Spec 7.11: a relation between an object and itself carries no relationship."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    relation = document["sections"][0]["relations"][0]
    relation["target_id"] = relation["source_id"]

    kinds = {p.kind for p in problems(document)}
    assert "self_reference" in kinds


def test_a_dangling_basis_reference_is_reported(load_ir) -> None:
    """Spec 8.15: a cited basis must be inspectable."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["relations"][0]["basis_refs"] = ["nope"]

    (problem,) = problems(document)
    assert problem.kind == "dangling"
    assert problem.field == "relation.basis_refs"
    assert problem.pointer.endswith("/basis_refs/0")


def test_a_dangling_indicator_target_is_reported(load_ir) -> None:
    """Spec 7.14: an update indicator must target a claim that exists."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["update_indicators"][0]["target_claim_refs"] = ["ghost"]

    (problem,) = problems(document)
    assert problem.kind == "dangling"
    assert problem.field == "update_indicator.target_claim_refs"


def test_an_assumed_term_base_must_be_declared_by_the_policy(
    ctx, load_ir, load_policy
) -> None:
    """Spec 7.2: an audience assumption requires policy or artifact evidence."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    declared = load_policy("assess")["glossary_refs"]
    assert ir.audience["assumed_glossary_refs"] == ["arq-core-v1"]
    assert unresolved_glossary_refs(ir, declared) == []
    assert unresolved_glossary_refs(ir, []) == [
        ("arq-core-v1", "/audience/assumed_glossary_refs/0")
    ]


def test_an_artifact_glossary_entry_also_satisfies_the_assumption(load_ir) -> None:
    """Spec 7.2: the artifact's own glossary is evidence for its assumption."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["audience"]["assumed_glossary_refs"] = ["acceptance-kernel"]
    ir = IrDocument.from_document(document)
    assert unresolved_glossary_refs(ir, []) == []


@pytest.mark.parametrize("field", ["canonical_term", "scope"])
def test_an_incomplete_glossary_entry_is_reported(load_ir, field) -> None:
    """Spec 10.3: a glossary entry declares a canonical term and its scope."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["glossary"][0][field] = "   "
    ir = IrDocument.from_document(document)
    reported = unresolved_concept_refs(ir)
    assert reported == [("acceptance-kernel", f"/glossary/0/{field}")]


def test_a_complete_glossary_reports_nothing(load_ir) -> None:
    """Spec 10.3: the conforming fixture's glossary entry is complete."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    assert unresolved_concept_refs(ir) == []

"""Draft.2 structural-check extensions (D-C, D-F).

The draft.1 structural checks are extended in place: IR-ID-UNIQUE now also
covers declared stable coordinates and requirement/decision/acceptance-criterion
ids, IR-REFS resolves dependency-target and acceptance-criterion references, and
IR-BASIS-SCHEMA enforces the basis-policy presence obligation. Every check must
be a no-op (or NOT_APPLICABLE) on a draft.1 document, which these fixtures
guarantee by starting from the draft.1 conforming fixtures.
"""

from __future__ import annotations

import copy

import pytest

from ats.ir.checks import run_structural_checks
from ats.ir.model import IrDocument
from ats.rules.results import Status

BASIS_SCHEMA = "IR-BASIS-SCHEMA"
ID_UNIQUE = "IR-ID-UNIQUE"
REFS = "IR-REFS"


@pytest.fixture(scope="module")
def run_checks(ctx, load_ir, load_policy):
    """Run the structural checks over a document, returning ``check_id -> result``."""

    def _run(document, policy_name="assess"):
        if isinstance(document, str):
            document = load_ir(document)
        policy = ctx.policy(load_policy(policy_name))
        ir = IrDocument.from_document(document)
        checks = run_structural_checks(ctx, ir, policy, schema_violations=[])
        return {check.check_id: check for check in checks}

    return _run


def _with_coordinates(document, coordinates):
    document = copy.deepcopy(document)
    document["stable_coordinates"] = coordinates
    return document


# -- IR-ID-UNIQUE: stable coordinates and protected-coordinate uses ----------


def test_ir_id_unique_fails_on_a_duplicate_stable_coordinate(
    run_checks, load_ir
) -> None:
    """Spec 7.17: no coordinate id MAY be declared twice, even with a different kind.

    The schema's ``uniqueItems`` compares whole entries, so the same id under
    two different ``source_pointer`` values passes validation; the structural
    check is what catches the collision.
    """
    document = _with_coordinates(
        load_ir("assess_conforming"),
        [
            {"kind": "requirement_id", "id": "REQ-X", "source_pointer": "#/sections/0"},
            {"kind": "decision_id", "id": "REQ-X", "source_pointer": "#/sections/1"},
        ],
    )
    check = run_checks(document)[ID_UNIQUE]
    assert check.status is Status.FAIL
    assert "REQ-X" in check.detail
    assert "/stable_coordinates/0/id" in check.detail
    assert "/stable_coordinates/1/id" in check.detail


def test_ir_id_unique_passes_when_a_coordinate_equals_a_claim_id(
    run_checks, load_ir
) -> None:
    """Spec 7.17: declaring a claim's own id as a coordinate is a reference, not a collision."""
    document = _with_coordinates(
        load_ir("assess_conforming"),
        [{"kind": "requirement_id", "id": "c1", "source_pointer": "#/sections/0/claims/0"}],
    )
    check = run_checks(document)[ID_UNIQUE]
    assert check.status is Status.PASS


def test_ir_id_unique_fails_on_a_duplicate_requirement_id_across_sections(
    run_checks, load_ir
) -> None:
    """Spec 7.17: a requirement id names one obligation, wherever it appears."""
    document = copy.deepcopy(load_ir("specify_conforming"))
    document["sections"].append(
        {
            "section_id": "s2",
            "heading": "second section",
            "profiles": ["SPECIFY"],
            "claims": [
                {
                    "claim_id": "REQ-DUP",
                    "role": "requirement",
                    "proposition": "The verifier MUST archive the audit trail.",
                    "material": True,
                    "polarity": "positive",
                    "status": "asserted",
                    "requirement": {
                        "requirement_id": "REQ-POLICY-017",
                        "actor": "verifier",
                        "deontic": "MUST",
                        "action": "archive",
                        "object": "the audit trail",
                        "source_authority": "kernel",
                    },
                }
            ],
            "evidence": [],
            "relations": [],
            "update_indicators": [],
        }
    )
    check = run_checks(document, "specify")[ID_UNIQUE]
    assert check.status is Status.FAIL
    assert "REQ-POLICY-017" in check.detail
    assert "requirement" in check.detail


@pytest.mark.parametrize(
    "mutate",
    [
        # decision_id repeated on two claims
        lambda claims: (claims[0].__setitem__("decision_id", "DEC-1"), claims[1].__setitem__("decision_id", "DEC-1")),
        # acceptance_criterion_id repeated on two requirements
        lambda claims: (
            claims[0].setdefault("requirement", {}).__setitem__("acceptance_criterion_id", "AC-1"),
            claims[1].setdefault("requirement", {}).__setitem__("acceptance_criterion_id", "AC-1"),
        ),
    ],
    ids=["decision_id", "acceptance_criterion_id"],
)
def test_ir_id_unique_fails_on_a_duplicate_protected_coordinate_use(
    run_checks, load_ir, mutate
) -> None:
    """Spec 7.17: decision and acceptance-criterion ids are unique across sections."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    claims = document["sections"][0]["claims"]
    # claims 0 and 1 carry no requirement today; give both a requirement object
    # so the acceptance_criterion_id case has a slot to repeat.
    for claim in claims[:2]:
        claim.setdefault(
            "requirement",
            {
                "requirement_id": f"{claim['claim_id']}-req",
                "actor": "verifier",
                "deontic": "MUST",
                "action": "verify",
                "object": "state",
                "source_authority": "kernel",
            },
        )
    mutate(claims)
    check = run_checks(document)[ID_UNIQUE]
    assert check.status is Status.FAIL
    assert "DEC-1" in check.detail or "AC-1" in check.detail


# -- IR-REFS: dependency targets and acceptance-criterion references ---------


def test_ir_refs_fails_on_a_dangling_dependency_target(run_checks, load_ir) -> None:
    """Spec 7.17: a dependency target resolves to a claim id or a declared coordinate."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["relations"].append(
        {
            "relation_id": "rel-dep",
            "type": "depends_on",
            "source_id": "c1",
            "target_id": "c2",
            "material": True,
            "dependency_target": "WI-NOPE",
        }
    )
    check = run_checks(document)[REFS]
    assert check.status is Status.FAIL
    assert "WI-NOPE" in check.detail
    assert "dependency_target" in check.detail


def test_ir_refs_resolves_a_dependency_target_against_claim_ids_without_a_block(
    run_checks, load_ir
) -> None:
    """Spec 7.17: with no stable_coordinates block, claim ids still satisfy refs."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["relations"].append(
        {
            "relation_id": "rel-dep",
            "type": "depends_on",
            "source_id": "c1",
            "target_id": "a1",
            "material": True,
            "dependency_target": "a1",
        }
    )
    check = run_checks(document)[REFS]
    assert check.status is Status.PASS


def test_ir_refs_resolves_a_dependency_target_declared_as_a_stable_coordinate(
    run_checks, load_ir
) -> None:
    """Spec 7.17: an external coordinate (work item, protocol) resolves via the block."""
    document = _with_coordinates(
        load_ir("assess_conforming"),
        [
            {
                "kind": "work_item_id",
                "id": "WI-42",
                "source_pointer": "#/sections/0/relations/0/dependency_target",
            }
        ],
    )
    document["sections"][0]["relations"].append(
        {
            "relation_id": "rel-dep",
            "type": "depends_on",
            "source_id": "c1",
            "target_id": "a1",
            "material": True,
            "dependency_target": "WI-42",
        }
    )
    check = run_checks(document)[REFS]
    assert check.status is Status.PASS


def test_ir_refs_fails_on_a_dangling_acceptance_criterion_id(
    run_checks, load_ir
) -> None:
    """Spec 7.17: an acceptance_criterion_id cites a real criterion or coordinate."""
    document = copy.deepcopy(load_ir("specify_conforming"))
    document["sections"][0]["claims"][0]["requirement"]["acceptance_criterion_id"] = "AC-NOPE"
    check = run_checks(document, "specify")[REFS]
    assert check.status is Status.FAIL
    assert "AC-NOPE" in check.detail
    assert "acceptance_criterion_id" in check.detail


def test_ir_refs_resolves_an_acceptance_criterion_id_declared_as_a_coordinate(
    run_checks, load_ir
) -> None:
    """Spec 7.17: a criterion declared as a coordinate satisfies the reference."""
    document = _with_coordinates(
        load_ir("specify_conforming"),
        [
            {
                "kind": "acceptance_criterion_id",
                "id": "AC-1",
                "source_pointer": "#/sections/0/claims/0/requirement/acceptance_criterion_id",
            }
        ],
    )
    document["sections"][0]["claims"][0]["requirement"]["acceptance_criterion_id"] = "AC-1"
    check = run_checks(document, "specify")[REFS]
    assert check.status is Status.PASS


def test_ir_refs_resolves_an_acceptance_criterion_id_against_a_claim_id(
    run_checks, load_ir
) -> None:
    """Spec 7.17: a criterion claim inside the artifact satisfies the reference."""
    document = copy.deepcopy(load_ir("specify_conforming"))
    document["sections"][0]["claims"].append(
        {
            "claim_id": "AC-1",
            "role": "definition",
            "proposition": "The criterion resolves as a claim.",
            "material": False,
            "polarity": "positive",
            "status": "asserted",
        }
    )
    document["sections"][0]["claims"][0]["requirement"]["acceptance_criterion_id"] = "AC-1"
    check = run_checks(document, "specify")[REFS]
    assert check.status is Status.PASS


# -- IR-BASIS-SCHEMA (draft.2 D-F) ------------------------------------------


def test_ir_basis_schema_fails_when_declared_true_and_a_material_claim_is_missing_basis(
    run_checks, load_ir
) -> None:
    """Spec 7.5: a declared basis policy obliges every material claim."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["basis_policy"] = {"default_basis": "DERIVED", "declared": True}
    check = run_checks(document)[BASIS_SCHEMA]
    assert check.status is Status.FAIL
    assert "c1" in check.detail
    assert "semantic_basis" in check.detail


def test_ir_basis_schema_fails_when_a_material_requirement_is_missing_basis(
    run_checks, load_ir
) -> None:
    """Spec 7.5: the requirement object on a material claim carries its own basis."""
    document = copy.deepcopy(load_ir("specify_conforming"))
    document["basis_policy"] = {"default_basis": "EXPLICIT", "declared": True}
    document["sections"][0]["claims"][0]["semantic_basis"] = {"basis": "EXPLICIT"}
    check = run_checks(document, "specify")[BASIS_SCHEMA]
    assert check.status is Status.FAIL
    assert "REQ-POLICY-017" in check.detail


def test_ir_basis_schema_passes_when_declared_true_and_basis_is_declared(
    run_checks, load_ir
) -> None:
    """Spec 7.5: every material claim and requirement carrying basis is conforming."""
    document = copy.deepcopy(load_ir("specify_conforming"))
    document["basis_policy"] = {"default_basis": "EXPLICIT", "declared": True}
    claim = document["sections"][0]["claims"][0]
    claim["semantic_basis"] = {"basis": "EXPLICIT"}
    claim["requirement"]["semantic_basis"] = {"basis": "EXPLICIT"}
    check = run_checks(document, "specify")[BASIS_SCHEMA]
    assert check.status is Status.PASS


def test_ir_basis_schema_ignores_immaterial_claims(run_checks, load_ir) -> None:
    """Spec 7.5: the obligation attaches to material semantic values only."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["basis_policy"] = {"default_basis": "DERIVED", "declared": True}
    for claim in document["sections"][0]["claims"]:
        claim["material"] = False
    # No claim carries semantic_basis, yet nothing is material, so nothing is
    # obliged: the check must not demand basis from immaterial claims.
    check = run_checks(document)[BASIS_SCHEMA]
    assert check.status is Status.PASS


def test_ir_basis_schema_passes_with_a_note_when_declared_is_false(
    run_checks, load_ir
) -> None:
    """Spec 7.5: ``declared: false`` is an explicit policy choice, not a defect."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["basis_policy"] = {"default_basis": "INFERRED", "declared": False}
    check = run_checks(document)[BASIS_SCHEMA]
    assert check.status is Status.PASS
    assert "declared is false" in check.detail


def test_ir_basis_schema_is_not_applicable_without_a_policy(run_checks) -> None:
    """Spec 7.5: no basis policy means no basis obligation is in force."""
    check = run_checks("assess_conforming")[BASIS_SCHEMA]
    assert check.status is Status.NOT_APPLICABLE
    assert "no basis_policy" in check.detail


def test_ir_basis_schema_is_never_required(run_checks) -> None:
    """Spec 7.5 / draft.2 D-F: basis declaration is a SHOULD, so the check is advisory."""
    check = run_checks("assess_conforming")[BASIS_SCHEMA]
    assert check.required is False

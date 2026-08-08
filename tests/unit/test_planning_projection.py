"""Planning projection (draft.2 D-H): determinism, lineage, and fail-closed gates.

The projection is a pure function of (validated IR, resolved policy,
artifact hash). These tests assert that the projected surface preserves the
IR's stable semantic coordinates and source pointers, binds the artifact and
policy hashes, refuses an invalid IR or stale policy, and stays deterministic
(same input, same ``projection_id``). The mock-planner assertions at the end
exercise one-to-many and many-to-one derivation shapes over the public
projection output, proving every derived task retains its ``source_ats``
lineage.
"""

from __future__ import annotations

import copy
import datetime as _dt

import pytest

from conftest import FIXTURES, FIXED_NOW

from ats.canonical import canonical_bytes, content_hash, sha256_hex, verify_seal
from ats.context import Context
from ats.errors import SchemaValidationError, StalePolicyError, UsageError
from ats.planning import project_from_ir

PROJECTION_SCHEMA_ID = "ats_planning_projection_v1.schema.json"

#: The content hash of the source artifact the projection binds.
SHA = "9" * 64


@pytest.fixture(scope="module")
def ctx() -> Context:
    """The draft.2 evaluation context (stable coordinates are a draft.2 surface)."""
    return Context.load(spec_version="1.0.0-draft.2", now=FIXED_NOW)


def _policy(ctx: Context, **overrides) -> dict:
    """A content-addressed draft.2 policy snapshot, rescaled to its own bytes."""
    document = copy.deepcopy(
        __import__("json").loads(
            (FIXTURES / "policies" / "specify.json").read_text(encoding="utf-8")
        )
    )
    document["spec_version"] = "1.0.0-draft.2"
    document["snapshot_id"] = "policy-fixture-draft2"
    document.update(overrides)
    document["snapshot_sha256"] = content_hash(document, exclude={"snapshot_sha256"})
    # The document must actually be current under the draft.2 context.
    ctx.policy(document)
    return document


@pytest.fixture(scope="module")
def policy(ctx: Context) -> dict:
    return _policy(ctx)


def _ir() -> dict:
    """A feature-complete draft.2 TextIR exercising every projection group."""
    return {
        "schema_version": "ats.text_ir.v1",
        "artifact_id": "artifact-planning-001",
        "source": {
            "content_sha256": SHA,
            "normalized_sha256": SHA,
            "media_type": "text/plain",
            "locator": "planning-source.txt",
        },
        "policy_snapshot_id": "policy-fixture-draft2",
        "language": "en",
        "audience": {"expertise": "expert"},
        "sections": [
            {
                "section_id": "s1",
                "profiles": ["SPECIFY", "TRANSFORM"],
                "claims": [
                    {
                        "claim_id": "REQ-1",
                        "role": "requirement",
                        "proposition": "The gate MUST reject a stale acceptance receipt.",
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "source_refs": ["OBS-1"],
                        "requirement": {
                            "requirement_id": "REQ-1",
                            "actor": "gate",
                            "deontic": "MUST",
                            "action": "reject",
                            "object": "stale acceptance receipt",
                            "scope": "before the transition",
                            "trigger": "the executor presents a receipt",
                            "condition": "the policy hash differs",
                            "acceptance_criterion_id": "AC-1",
                            "source_authority": "Acceptance kernel",
                        },
                    },
                    {
                        "claim_id": "REQ-2",
                        "role": "requirement",
                        "proposition": "The adjudicator SHOULD confirm a quorum first.",
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "source_refs": ["JUDG-1"],
                        "requirement": {
                            "requirement_id": "REQ-2",
                            "actor": "adjudicator",
                            "deontic": "SHOULD",
                            "action": "confirm",
                            "object": "a quorum",
                            "acceptance_criterion_id": "AC-2",
                            "source_authority": "Acceptance kernel",
                        },
                    },
                    {
                        "claim_id": "REQ-3",
                        "role": "requirement",
                        "proposition": "The planner MUST NOT derive a task graph.",
                        "material": True,
                        "polarity": "negative",
                        "status": "asserted",
                        "requirement": {
                            "requirement_id": "REQ-3",
                            "actor": "planner",
                            "deontic": "MUST_NOT",
                            "action": "derive",
                            "object": "a task graph",
                            "acceptance_criterion_id": "AC-2",
                            "source_authority": "Planning authority",
                        },
                    },
                    {
                        "claim_id": "AC-1",
                        "role": "definition",
                        "proposition": "The stale receipt is rejected before the transition.",
                        "material": False,
                        "polarity": "positive",
                        "status": "asserted",
                    },
                    {
                        "claim_id": "AC-2",
                        "role": "definition",
                        "proposition": "The quorum is confirmed before any gate opens.",
                        "material": False,
                        "polarity": "positive",
                        "status": "asserted",
                    },
                    {
                        "claim_id": "DEC-1",
                        "role": "recommendation",
                        "proposition": "Adopt the kernel gate for acceptance.",
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "decision_id": "DEC-1",
                    },
                    {
                        "claim_id": "OBS-1",
                        "role": "observation",
                        "proposition": "Receipts carry a policy hash in the live system.",
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                    },
                    {
                        "claim_id": "JUDG-1",
                        "role": "judgment",
                        "proposition": "Quorum confirmation is a precondition of trust.",
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                    },
                    {
                        "claim_id": "NG-1",
                        "role": "boundary",
                        "proposition": "No task-graph derivation in the projection.",
                        "material": True,
                        "polarity": "negative",
                        "status": "asserted",
                    },
                    {
                        "claim_id": "BD-1",
                        "role": "boundary",
                        "proposition": "The projection stays within the gate plane.",
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                    },
                    {
                        "claim_id": "EX-1",
                        "role": "exception",
                        "proposition": "Unless the operator holds a quorum.",
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                    },
                ],
                "evidence": [],
                "relations": [
                    {
                        "relation_id": "rel1",
                        "source_id": "REQ-1",
                        "type": "depends_on",
                        "target_id": "REQ-2",
                        "material": True,
                    },
                    {
                        "relation_id": "rel2",
                        "source_id": "REQ-2",
                        "type": "necessary_for",
                        "target_id": "REQ-3",
                        "material": True,
                    },
                    {
                        # ``dependency_target`` selects the target requirement
                        # even though the relation's own target is not one.
                        "relation_id": "rel3",
                        "source_id": "REQ-3",
                        "type": "depends_on",
                        "target_id": "EX-1",
                        "dependency_target": "REQ-1",
                        "material": True,
                    },
                    {
                        # A dependency-kind relation whose target is not a
                        # requirement is not a requirement-level dependency.
                        "relation_id": "rel5",
                        "source_id": "REQ-2",
                        "type": "condition_for",
                        "target_id": "AC-1",
                        "material": True,
                    },
                ],
                "update_indicators": [
                    {
                        "indicator_id": "UI-1",
                        "text": "Invalidate the gate assumption when receipts go hashless.",
                        "target_claim_refs": ["REQ-1"],
                        "effect": "invalidate_assumption",
                    }
                ],
            }
        ],
        "extraction_status": "complete",
        "stable_coordinates": [
            {
                "kind": "requirement_id",
                "id": "REQ-1",
                "source_pointer": "#/sections/0/claims/0",
            },
            {
                "kind": "requirement_id",
                "id": "REQ-2",
                "source_pointer": "#/sections/0/claims/1",
            },
            {
                "kind": "requirement_id",
                "id": "REQ-3",
                "source_pointer": "#/sections/0/claims/2",
            },
            {
                "kind": "acceptance_criterion_id",
                "id": "AC-1",
                "source_pointer": "#/sections/0/claims/0/requirement/acceptance_criterion_id",
            },
            {
                "kind": "acceptance_criterion_id",
                "id": "AC-2",
                "source_pointer": "#/sections/0/claims/1/requirement/acceptance_criterion_id",
            },
            {
                "kind": "decision_id",
                "id": "DEC-1",
                "source_pointer": "#/sections/0/claims/5",
            },
        ],
    }


@pytest.fixture(scope="module")
def ir() -> dict:
    return _ir()


def project(ctx: Context, ir_document: dict, policy_document: dict) -> dict:
    return project_from_ir(
        ctx, ir_document, policy_document, artifact_sha256=SHA
    )


# -- seal and identity ------------------------------------------------------


def test_projection_is_sealed_and_schema_valid(ctx, ir, policy) -> None:
    """Appendix C: the projection addresses itself and validates (spec 19.4)."""
    projection = project(ctx, ir, policy)
    assert projection["schema_version"] == "ats.planning_projection.v1"
    ok, declared, recomputed = verify_seal(projection)
    assert ok
    assert declared == recomputed == projection["projection_id"]
    ctx.schemas.validate(projection, PROJECTION_SCHEMA_ID)

    assert projection["artifact_id"] == "artifact-planning-001"
    assert projection["artifact_sha256"] == SHA
    assert projection["ir_sha256"] == sha256_hex(canonical_bytes(ir))
    assert projection["policy_snapshot_id"] == policy["snapshot_id"]
    assert projection["policy_snapshot_sha256"] == policy["snapshot_sha256"]
    assert projection["spec_version"] == "1.0.0-draft.2"
    assert projection["profile"] == "SPECIFY+TRANSFORM"


# -- source coordinate preservation -----------------------------------------


def test_projection_preserves_requirements_and_slots(ctx, ir, policy) -> None:
    """Every requirement slot projects with its IR pointer and authority."""
    projection = project(ctx, ir, policy)
    reqs = projection["requirements"]
    assert [r["requirement_id"] for r in reqs] == ["REQ-1", "REQ-2", "REQ-3"]

    (req1,) = [r for r in reqs if r["requirement_id"] == "REQ-1"]
    assert req1 == {
        "requirement_id": "REQ-1",
        "actor": "gate",
        "deontic": "MUST",
        "action": "reject",
        "object": "stale acceptance receipt",
        "scope": "before the transition",
        "trigger": "the executor presents a receipt",
        "condition": "the policy hash differs",
        "acceptance_criterion_id": "AC-1",
        "source_pointer": "/sections/0/claims/0",
        "authority": "Acceptance kernel",
    }
    (req3,) = [r for r in reqs if r["requirement_id"] == "REQ-3"]
    assert req3["deontic"] == "MUST_NOT"
    assert req3["acceptance_criterion_id"] == "AC-2"
    assert "trigger" not in req3


def test_projection_preserves_decision_ids(ctx, ir, policy) -> None:
    """Claims carrying a decision_id project with proposition and status."""
    projection = project(ctx, ir, policy)
    assert projection["decisions"] == [
        {
            "decision_id": "DEC-1",
            "proposition": "Adopt the kernel gate for acceptance.",
            "status": "asserted",
            "source_pointer": "/sections/0/claims/5",
        }
    ]


def test_projection_preserves_acceptance_criteria_and_backrefs(ctx, ir, policy) -> None:
    """ACs project with their defining text and every referencing requirement."""
    projection = project(ctx, ir, policy)
    acs = {a["acceptance_criterion_id"]: a for a in projection["acceptance_criteria"]}
    assert set(acs) == {"AC-1", "AC-2"}
    assert acs["AC-1"]["criterion"] == "The stale receipt is rejected before the transition."
    assert acs["AC-1"]["requirement_ids"] == ["REQ-1"]
    # AC-2 is referenced by two requirements (the acceptance-dependency backref).
    assert acs["AC-2"]["criterion"] == "The quorum is confirmed before any gate opens."
    assert acs["AC-2"]["requirement_ids"] == ["REQ-2", "REQ-3"]


def test_projection_preserves_dependency_links(ctx, ir, policy) -> None:
    """Dependency-kind relations project with both requirement endpoints."""
    projection = project(ctx, ir, policy)
    deps = [
        (d["from_requirement_id"], d["to_requirement_id"], d["kind"])
        for d in projection["dependencies"]
    ]
    assert deps == [
        ("REQ-1", "REQ-2", "depends_on"),
        ("REQ-2", "REQ-3", "necessary_for"),
        # rel3's ``dependency_target`` ref selects the target requirement.
        ("REQ-3", "REQ-1", "depends_on"),
    ]


def test_projection_preserves_proof_obligations(ctx, ir, policy) -> None:
    """Requirement-referenced observations/judgments are named obligations."""
    projection = project(ctx, ir, policy)
    assert projection["proof_obligations"] == [
        {
            "obligation_id": "REQ-1:OBS-1",
            "claim_id": "OBS-1",
            "requirement_id": "REQ-1",
        },
        {
            "obligation_id": "REQ-2:JUDG-1",
            "claim_id": "JUDG-1",
            "requirement_id": "REQ-2",
        },
    ]


def test_projection_preserves_non_goals_boundaries_exceptions(ctx, ir, policy) -> None:
    """Exclusion, limit, and exception claims project with their pointers."""
    projection = project(ctx, ir, policy)
    assert projection["non_goals"] == [
        {
            "statement": "No task-graph derivation in the projection.",
            "source_pointer": "/sections/0/claims/8",
        }
    ]
    assert projection["boundaries"] == [
        {
            "statement": "The projection stays within the gate plane.",
            "source_pointer": "/sections/0/claims/9",
        }
    ]
    assert projection["exceptions"] == [
        {
            "statement": "Unless the operator holds a quorum.",
            "source_pointer": "/sections/0/claims/10",
        }
    ]


def test_projection_preserves_update_indicators(ctx, ir, policy) -> None:
    """Indicators project with their target claim and effect as kind."""
    projection = project(ctx, ir, policy)
    assert projection["update_indicators"] == [
        {
            "indicator_id": "UI-1",
            "claim_id": "REQ-1",
            "kind": "invalidate_assumption",
            "source_pointer": "/sections/0/update_indicators/0",
        }
    ]


def test_projection_preserves_stable_coordinates_and_authority(ctx, ir, policy) -> None:
    """Coordinates copy verbatim; authority dedups distinct source_authority."""
    projection = project(ctx, ir, policy)
    assert len(projection["stable_coordinates"]) == 6
    assert projection["stable_coordinates"][0] == {
        "kind": "requirement_id",
        "id": "REQ-1",
        "source_pointer": "#/sections/0/claims/0",
    }
    kinds = {c["kind"] for c in projection["stable_coordinates"]}
    assert kinds == {"requirement_id", "acceptance_criterion_id", "decision_id"}

    assert projection["authority"] == [
        {"source_id": "REQ-1", "authority": "Acceptance kernel"},
        {"source_id": "REQ-3", "authority": "Planning authority"},
    ]
    # precedence is never invented (ATS-BASIS-002): the IR declares none.
    assert all("precedence" not in a for a in projection["authority"])


# -- determinism and hash binding -------------------------------------------


def test_projection_is_deterministic(ctx, ir, policy) -> None:
    """Spec 16.2: identical inputs yield an identical sealed projection."""
    first = project(ctx, ir, policy)
    second = project(ctx, ir, policy)
    assert first == second
    assert first["projection_id"] == second["projection_id"]


def test_projection_binds_artifact_sha256(ctx, ir, policy) -> None:
    """A different artifact version invalidates the projection deterministically."""
    base = project(ctx, ir, policy)
    other = project_from_ir(ctx, ir, policy, artifact_sha256="1" * 64)
    assert other["artifact_sha256"] == "1" * 64
    assert other["projection_id"] != base["projection_id"]
    # Only the bound hash and its content address may differ.
    shared = {k: v for k, v in base.items() if k not in ("projection_id", "artifact_sha256")}
    shared_other = {
        k: v for k, v in other.items() if k not in ("projection_id", "artifact_sha256")
    }
    assert shared == shared_other


def test_projection_binds_ir_sha256(ctx, ir, policy) -> None:
    """A mutated IR yields a different ir_sha256 and a different projection."""
    base = project(ctx, ir, policy)
    mutated = copy.deepcopy(ir)
    mutated["sections"][0]["claims"][3]["proposition"] = "A different criterion text."
    other = project(ctx, mutated, policy)
    assert other["ir_sha256"] != base["ir_sha256"]
    assert other["projection_id"] != base["projection_id"]
    assert other["acceptance_criteria"][0]["criterion"] != base["acceptance_criteria"][0][
        "criterion"
    ]


def test_projection_binds_policy_snapshot(ctx, ir, policy) -> None:
    """A different policy snapshot invalidates the projection deterministically."""
    base = project(ctx, ir, policy)
    other_policy = _policy(ctx, snapshot_id="policy-fixture-other")
    other_ir = copy.deepcopy(ir)
    other_ir["policy_snapshot_id"] = "policy-fixture-other"
    other = project(ctx, other_ir, other_policy)
    assert other["policy_snapshot_id"] == "policy-fixture-other"
    assert other["policy_snapshot_sha256"] != base["policy_snapshot_sha256"]
    assert other["projection_id"] != base["projection_id"]


# -- fail-closed gates ------------------------------------------------------


def test_invalid_ir_is_refused(ctx, ir, policy) -> None:
    """An IR that fails schema validation is refused, never partially projected."""
    missing_sections = copy.deepcopy(ir)
    del missing_sections["sections"]
    with pytest.raises(SchemaValidationError):
        project(ctx, missing_sections, policy)

    with pytest.raises(SchemaValidationError):
        project(ctx, ["not", "a", "document"], policy)


def test_stale_policy_is_refused(ctx, ir, policy) -> None:
    """A policy whose hash no longer matches its bytes is stale (spec 14.3)."""
    stale = copy.deepcopy(policy)
    stale["snapshot_sha256"] = "0" * 64
    with pytest.raises(StalePolicyError):
        project(ctx, ir, stale)


def test_policy_for_another_spec_version_is_refused(ctx, ir, policy) -> None:
    """A draft.1 policy is not current under the draft.2 package."""
    draft1 = copy.deepcopy(policy)
    draft1["spec_version"] = "1.0.0-draft.1"
    draft1["snapshot_sha256"] = content_hash(draft1, exclude={"snapshot_sha256"})
    with pytest.raises(StalePolicyError):
        project(ctx, ir, draft1)


def test_ir_under_a_different_policy_is_refused(ctx, ir, policy) -> None:
    """An IR authored against another policy is refused, never mislabeled."""
    mismatched = copy.deepcopy(ir)
    mismatched["policy_snapshot_id"] = "policy-fixture-elsewhere"
    with pytest.raises(UsageError, match="policy_snapshot_id"):
        project(ctx, mismatched, policy)


# -- missing-value rules ----------------------------------------------------


def test_missing_values_stay_missing(ctx, policy) -> None:
    """ACs and indicators with no stated value are omitted, never invented."""
    document = _ir()
    # AC-3 has only free text; AC-4 has nothing at all.
    document["sections"][0]["claims"].append(
        {
            "claim_id": "REQ-4",
            "role": "requirement",
            "proposition": "The gate MUST echo the receipt hash.",
            "material": True,
            "polarity": "positive",
            "status": "asserted",
            "requirement": {
                "requirement_id": "REQ-4",
                "actor": "gate",
                "deontic": "MUST",
                "action": "echo",
                "object": "the receipt hash",
                "acceptance_criterion_id": "AC-3",
                "acceptance_criterion": "The echoed hash matches the receipt.",
                "source_authority": "Acceptance kernel",
            },
        }
    )
    document["sections"][0]["claims"].append(
        {
            "claim_id": "REQ-5",
            "role": "requirement",
            "proposition": "The gate MUST log every refusal.",
            "material": True,
            "polarity": "positive",
            "status": "asserted",
            "requirement": {
                "requirement_id": "REQ-5",
                "actor": "gate",
                "deontic": "MUST",
                "action": "log",
                "object": "every refusal",
                "acceptance_criterion_id": "AC-4",
                "source_authority": "Acceptance kernel",
            },
        }
    )
    # An indicator with no declared effect cannot supply the required kind.
    document["sections"][0]["update_indicators"].append(
        {
            "indicator_id": "UI-2",
            "text": "Watch the receipt schema.",
            "target_claim_refs": ["REQ-5"],
        }
    )
    projection = project(ctx, document, policy)
    acs = {a["acceptance_criterion_id"]: a for a in projection["acceptance_criteria"]}
    assert acs["AC-3"]["criterion"] == "The echoed hash matches the receipt."
    assert acs["AC-3"]["requirement_ids"] == ["REQ-4"]
    assert "AC-4" not in acs
    # The referencing requirement still carries its criterion coordinate.
    (req5,) = [r for r in projection["requirements"] if r["requirement_id"] == "REQ-5"]
    assert req5["acceptance_criterion_id"] == "AC-4"
    assert [u["indicator_id"] for u in projection["update_indicators"]] == ["UI-1"]


# -- downstream mock planner (one-to-many / many-to-one) --------------------


def test_mock_planner_derivations_preserve_source_lineage(ctx, ir, policy) -> None:
    """Every derived task retains source_ats coordinates that resolve upstream."""
    projection = project(ctx, ir, policy)
    proj_reqs = {r["requirement_id"] for r in projection["requirements"]}
    proj_decs = {d["decision_id"] for d in projection["decisions"]}
    proj_acs = {a["acceptance_criterion_id"] for a in projection["acceptance_criteria"]}

    # One -> many: REQ-1 decomposes into two independently verifiable tasks.
    tasks = [
        {
            "task_id": "VX-T1",
            "source_ats": {
                "artifact_id": projection["artifact_id"],
                "artifact_sha256": projection["artifact_sha256"],
                "requirement_ids": ["REQ-1"],
                "decision_ids": ["DEC-1"],
                "acceptance_criterion_ids": ["AC-1"],
            },
        },
        {
            "task_id": "VX-T2",
            "source_ats": {
                "artifact_id": projection["artifact_id"],
                "artifact_sha256": projection["artifact_sha256"],
                "requirement_ids": ["REQ-1"],
                "decision_ids": [],
                "acceptance_criterion_ids": [],
            },
        },
        # Many -> one: REQ-2 and REQ-3 land atomically in one task.
        {
            "task_id": "VX-T3",
            "source_ats": {
                "artifact_id": projection["artifact_id"],
                "artifact_sha256": projection["artifact_sha256"],
                "requirement_ids": ["REQ-2", "REQ-3"],
                "decision_ids": [],
                "acceptance_criterion_ids": ["AC-2"],
            },
        },
    ]

    for task in tasks:
        lineage = task["source_ats"]
        assert lineage["artifact_id"] == projection["artifact_id"]
        assert lineage["artifact_sha256"] == projection["artifact_sha256"]
        assert set(lineage["requirement_ids"]) <= proj_reqs
        assert set(lineage["decision_ids"]) <= proj_decs
        assert set(lineage["acceptance_criterion_ids"]) <= proj_acs

    # One -> many: the same requirement id rides on both execution tasks.
    one_to_many = [
        t["task_id"]
        for t in tasks
        if "REQ-1" in t["source_ats"]["requirement_ids"]
    ]
    assert one_to_many == ["VX-T1", "VX-T2"]

    # Many -> one: one execution task couples REQ-2 and REQ-3.
    (many_to_one,) = [t for t in tasks if t["task_id"] == "VX-T3"]
    assert set(many_to_one["source_ats"]["requirement_ids"]) == {"REQ-2", "REQ-3"}

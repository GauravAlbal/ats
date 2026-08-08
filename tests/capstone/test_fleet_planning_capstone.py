"""Planning capstone: public ats-spec -> draft.2 TextIR -> lint ->
receipt -> planning projection -> execution tasks.

The capstone reuses the planning-chain fixture's machinery — the fence
program is a technical program request — and checks the public-skill
pipeline's guarantees: source coordinates preserved, AC coordinates
preserved, task IDs distinct from ATS IDs, one requirement can produce
multiple tasks, tasks receive local source context, and no hidden semantic
invention is required.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import test_capstone_c_tribunal_chain as c3

from ats.canonical import content_hash
from ats.context import Context

REPO_ROOT = Path(__file__).resolve().parents[2]
DRAFT2_POLICY_PATH = REPO_ROOT / "fixtures" / "policies" / "draft2.json"
FIXED_NOW = c3.FIXED_NOW


@pytest.fixture(scope="module")
def ctx() -> Context:
    """The draft.2 evaluation context (stable coordinates are draft.2)."""
    return Context.load(spec_version="1.0.0-draft.2", now=FIXED_NOW)


def test_fleet_planning_chain_preserves_coordinates_and_distinguishes_task_ids(
    ctx: Context, tmp_path_factory,
) -> None:
    """An ats-spec draft.2 program flows through lint, receipt, and projection
    into execution tasks with full source lineage."""
    policy = json.loads(DRAFT2_POLICY_PATH.read_text(encoding="utf-8"))
    # Build the fence program from deliberation state through adjudication,
    # bound source, and TextIR.
    source_path = tmp_path_factory.mktemp("fence-brief") / "brief.md"
    source_path.write_text(c3.BRIEF, encoding="utf-8")
    binding = c3.bind_file(source_path)
    deliberation = c3._deliberation_fixture()
    adjudications = c3.adjudicate(deliberation)
    ir = c3._build_ir(deliberation, adjudications, binding, source_path)
    artifact_sha = binding.content_sha256

    # 1. draft.2 deterministic lint is integrity-green.
    report = c3.lint_ir(ctx, ir, policy, source_path=source_path)
    assert report["spec_version"] == "1.0.0-draft.2"
    assert report["summary"]["required_failed"] == 0

    # 2. Receipt verifies (draft.2 bound).
    ir_view = c3.IrDocument.from_document(ir)
    receipt = c3.build_candidate_receipt(
        ctx,
        ir=ir_view,
        policy=ctx.policy(policy),
        output_sha256=None,
        lint_report=report,
        adjudicator="fleet-planning-capstone-fixture",
    )
    verification = c3.verify_receipt(
        ctx, receipt, ir_document=ir, policy=ctx.policy(policy)
    )
    assert verification["status"] == "PASS"

    # 3. Projection from the accepted artifact.
    projection = c3.project_from_ir(ctx, ir, policy, artifact_sha256=artifact_sha)
    assert projection["spec_version"] == "1.0.0-draft.2"

    # 4. A planning consumer derives execution tasks (one->many and many->one).
    tasks = c3.derive_tasks(projection, verification)

    # -- assertions -----------------------------------------------------------
    source_reqs = {r["requirement_id"] for r in projection["requirements"]}
    source_acs = {a["acceptance_criterion_id"] for a in projection["acceptance_criteria"]}
    assert "REQ-FENCE-001" in source_reqs
    assert "AC-FENCE-001-A" in source_acs

    # Task IDs remain distinct from ATS IDs: execution IDs never collide with
    # REQ-*/AC-*/DEC-* (semantic requirement identity != execution task identity).
    ats_ids = source_reqs | source_acs | {d["decision_id"] for d in projection["decisions"]}
    for task in tasks:
        assert task["task_id"] not in ats_ids
        assert task["task_id"].startswith("VX-")

    # One requirement produces multiple tasks.
    fence_tasks = [
        t for t in tasks if "REQ-FENCE-001" in t["source_ats"]["requirement_ids"]
    ]
    assert len(fence_tasks) >= 2

    # Every source-backed task's coordinates resolve in the projection, and
    # local source context travels with the task.
    for task in tasks:
        c3._verify_source_ats(projection, task["source_ats"])
        assert task["source_ats"]["artifact_id"] == projection["artifact_id"]
        assert task["source_ats"]["artifact_sha256"] == projection["artifact_sha256"]
        if task["source_ats"]["requirement_ids"]:
            req_id = task["source_ats"]["requirement_ids"][0]
            local = next(r for r in projection["requirements"] if r["requirement_id"] == req_id)
            assert local["actor"] and local["deontic"] and local["action"]
            assert task["title"]

    # No hidden semantic invention: the consumer does not modify the projection.
    projection_copy = copy.deepcopy(projection)
    c3.derive_tasks(projection, verification)
    assert projection == projection_copy

    # Many->one: REQ-FENCE-002 depends on REQ-FENCE-001 and lands atomically.
    coupled = [
        t
        for t in tasks
        if set(t["source_ats"]["requirement_ids"]) >= {"REQ-FENCE-001", "REQ-FENCE-002"}
    ]
    assert coupled, "no many->one task couples the dependent requirements"

"""Capstone C: the Tribunal-first planning chain (draft.2).

Obligation (contract §1 D-I, §8 capstone C): drive the operator's chain end to
end — operator intent + repo evidence → Tribunal-like deliberation fixture →
Tribunal-like adjudication tier (no human) → ATS TextIR implementation
specification (ASSESS+SPECIFY) → deterministic lint → ATS receipt → downstream
planning consumer, and prove that stable semantic coordinates
(REQ-FENCE-001, AC-FENCE-001-A, DEC-FENCE-001) survive the whole chain, that
the semantic-ambiguity case resolves to AUTHOR_JUDGMENT without human
intervention, and that a second ambiguity with no measured evidence stays
UNAVAILABLE and is never promoted.

The Tribunal-like parts (the deliberation fixture and the adjudication tier)
are stubs owned by this test. The ATS side is real: the IR is validated,
linter-green, receipted, projected by ``ats.planning.project_from_ir``, and
consumed by a pure-Python downstream-planner consumer that verifies the
receipt before deriving tasks and never re-authors.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

from conftest import FIXTURES, FIXED_NOW

from ats.canonical import verify_seal
from ats.context import Context
from ats.hashes import bind_file
from ats.ir.lint import lint_ir
from ats.ir.model import IrDocument
from ats.output.receipt import build_candidate_receipt, verify_receipt
from ats.planning import project_from_ir

PROJECTION_SCHEMA_ID = "ats_planning_projection_v1.schema.json"

#: The operator intent — the raw input to the chain (the brief of §1 D-I).
BRIEF = (
    "Fence stale effect starts: an agent's effect must not start after its "
    "steer epoch has been superseded."
)

#: The repo evidence fact sheet — the mechanism Tribunal deliberates over.
FACT_SHEET: dict[str, Any] = {
    "source_id": "fact-sheet",
    "title": "Repo evidence: steer-epoch effect-start race (sear-style runtime)",
    "mechanism": (
        "The runtime records a steer epoch for every agent and stamps every effect "
        "with the epoch at which it was issued. When the agent is re-steered "
        "between issue and start, the start path still starts the stale effect. "
        "The race is silent: no error is logged and the stale effect's outcomes "
        "are lost."
    ),
    "consequence": "The race causes silent data loss of the stale effect's outcomes.",
    "latency": "No measurement of a fence check's latency exists in the current runtime.",
    "authority": "sear-style runtime scheduler (repo evidence)",
}

#: The five-value basis vocabulary (ATS-1 §4.25, verbatim from the spec).
BASIS_VALUES = ("EXPLICIT", "DERIVED", "INFERRED", "UNAVAILABLE", "AUTHOR_JUDGMENT")


# ---------------------------------------------------------------------------
# 1. The Tribunal-like deliberation fixture (durable-output boundary state)
# ---------------------------------------------------------------------------


def _deliberation_fixture() -> dict[str, Any]:
    """The settled reasoning state Tribunal holds when it crosses the
    durable-output boundary: competing hypotheses, the adopted judgment, the
    boundary, the evidence, and two unresolved ambiguities.
    """
    return {
        "deliberation_id": "tribunal-capstone-c-fence",
        "artifact_type": "implementation_spec",
        "operator_intent": BRIEF,
        "competing_hypotheses": [
            {
                "id": "H1",
                "text": (
                    "The start race is benign: a stale effect's outcomes are eventually "
                    "overwritten by the newer steer, so no fence is required."
                ),
            },
            {
                "id": "H2",
                "text": (
                    "The start race is harmful: stale effects start silently and their "
                    "outcomes are lost, so effect starts must be fenced against "
                    "superseded steer epochs."
                ),
            },
        ],
        "adopted_judgment": "H2",
        "boundary": (
            "The fence applies at effect start only; the steer-epoch mechanism "
            "itself is unchanged."
        ),
        "evidence": [
            {
                "evidence_id": "EV-FENCE-001",
                "proposition": (
                    "Steer epochs are recorded per agent and every effect start carries "
                    "the epoch at issue."
                ),
                "availability": "present",
                "authority": FACT_SHEET["authority"],
            },
            {
                "evidence_id": "EV-FENCE-002",
                "proposition": (
                    "A stale effect start is silent: no error is logged and the stale "
                    "effect's outcomes are lost."
                ),
                "availability": "present",
                "authority": FACT_SHEET["authority"],
            },
            {
                "evidence_id": "EV-FENCE-003",
                "proposition": (
                    "No latency measurement exists for the fence check in the current "
                    "runtime."
                ),
                "availability": "present",
                "authority": FACT_SHEET["authority"],
            },
        ],
        "ambiguities": [
            {
                "id": "requirement_force",
                "target": "REQ-FENCE-001",
                "alternatives": ["SHOULD", "MUST"],
                "question": (
                    "The fact sheet establishes the race mechanism but never states a "
                    "deontic force: is fencing stale starts a SHOULD or a MUST?"
                ),
            },
            {
                "id": "latency_budget",
                "target": "REQ-FENCE-002",
                "alternatives": ["SHOULD", "MUST"],
                "question": (
                    "May the fence check carry a latency budget, and with what force, "
                    "when no measured evidence exists?"
                ),
            },
        ],
    }


# ---------------------------------------------------------------------------
# 2. The Tribunal-like adjudication tier (pure Python, no human)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Adjudication:
    """One resolved ambiguity record from the Tribunal-like adjudication tier."""

    ambiguity: str
    target: str
    resolution: str | None
    basis: str
    ladder: tuple[str, ...]
    rationale: str
    human: bool = False


def _rung_deterministic_recovery(evidence: Mapping[str, str], *, needle: str) -> bool:
    """Rung 1 of the escalation ladder: the source itself fixes the value.

    Deterministic recovery means the evidence *verbatim* states the semantic
    value — here, an explicit deontic surface. A mechanism consequence ("data
    loss") is not an explicit deontic, so it does NOT recover the value.
    """
    return any(needle in text for text in evidence.values())


def _rung_adjudicate_requirement_force(evidence: Mapping[str, str]) -> bool:
    """Rung 2 for requirement_force: can the evidence carry a MUST?

    The adopted mechanism (silent race + lost outcomes) makes the harm
    irreversible data loss, which warrants MUST over SHOULD. The judgment is
    interpretive — the source never states the deontic — which is exactly why
    the recorded basis is AUTHOR_JUDGMENT, not EXPLICIT/DERIVED.
    """
    return any(
        "silent" in text and ("lost" in text or "data loss" in text)
        for text in evidence.values()
    )


def _rung_adjudicate_latency_budget(evidence: Mapping[str, str]) -> bool:
    """Rung 2 for latency_budget: is any measurement present to judge from?"""
    import re

    measured = re.compile(r"\d+\s*(?:ms|milliseconds?|s\b|seconds?)")
    return any(measured.search(text) for text in evidence.values())


def _adjudicate_requirement_force(evidence: Mapping[str, str]) -> Adjudication:
    if _rung_deterministic_recovery(evidence, needle="must"):
        return Adjudication(
            ambiguity="requirement_force",
            target="REQ-FENCE-001",
            resolution="MUST",
            basis="EXPLICIT",
            ladder=("deterministic_recovery",),
            rationale="A source fact states the deontic force verbatim.",
        )
    if _rung_adjudicate_requirement_force(evidence):
        return Adjudication(
            ambiguity="requirement_force",
            target="REQ-FENCE-001",
            resolution="MUST",
            basis="AUTHOR_JUDGMENT",
            ladder=("deterministic_recovery", "adjudicate_from_evidence"),
            rationale=(
                "No source fact fixes the force; the Tribunal-like tier adjudicates from "
                "evidence: the mechanism is silent and loses the stale effect's outcomes "
                "(data loss), which warrants MUST over SHOULD. Recorded as AUTHOR_JUDGMENT; "
                "no human was consulted."
            ),
        )
    return Adjudication(
        ambiguity="requirement_force",
        target="REQ-FENCE-001",
        resolution=None,
        basis="UNAVAILABLE",
        ladder=("deterministic_recovery", "adjudicate_from_evidence", "unavailable"),
        rationale=(
            "Neither a source fact nor adjudicable evidence establishes the force; the "
            "value stays UNAVAILABLE and is never promoted."
        ),
    )


def _adjudicate_latency_budget(evidence: Mapping[str, str]) -> Adjudication:
    if _rung_deterministic_recovery(evidence, needle="ms"):
        return Adjudication(
            ambiguity="latency_budget",
            target="REQ-FENCE-002",
            resolution="SHOULD",
            basis="EXPLICIT",
            ladder=("deterministic_recovery",),
            rationale="A measured budget exists in the evidence and fixes the value.",
        )
    if _rung_adjudicate_latency_budget(evidence):
        return Adjudication(
            ambiguity="latency_budget",
            target="REQ-FENCE-002",
            resolution="SHOULD",
            basis="AUTHOR_JUDGMENT",
            ladder=("deterministic_recovery", "adjudicate_from_evidence"),
            rationale="Measured evidence supports an adjudicated budget target.",
        )
    return Adjudication(
        ambiguity="latency_budget",
        target="REQ-FENCE-002",
        resolution=None,
        basis="UNAVAILABLE",
        ladder=("deterministic_recovery", "adjudicate_from_evidence", "unavailable"),
        rationale=(
            "The evidence records that no measurement exists, so no budget value can be "
            "established; the ambiguity stays UNAVAILABLE and is never promoted to an "
            "explicit bound."
        ),
    )


def adjudicate(deliberation: Mapping[str, Any]) -> list[Adjudication]:
    """The Tribunal-like adjudication tier.

    Runs the escalation ladder of §1 D-I per ambiguity: deterministically
    recover → adjudicate from evidence → record AUTHOR_JUDGMENT / stay
    UNAVAILABLE → continue. Nothing here escalates to a human: product-
    authority distinctions are the only things that may.
    """
    evidence = {e["evidence_id"]: e["proposition"] for e in deliberation["evidence"]}
    records: list[Adjudication] = []
    for ambiguity in deliberation["ambiguities"]:
        if ambiguity["id"] == "requirement_force":
            records.append(_adjudicate_requirement_force(evidence))
        elif ambiguity["id"] == "latency_budget":
            records.append(_adjudicate_latency_budget(evidence))
        else:  # pragma: no cover - the fixture is closed
            raise ValueError(f"unhandled ambiguity {ambiguity['id']!r}")
    return records


# ---------------------------------------------------------------------------
# 3. ATS side: hand-authored TextIR implementation specification (ASSESS+SPECIFY)
# ---------------------------------------------------------------------------


def _basis(value: str, rationale: str) -> dict[str, str]:
    assert value in BASIS_VALUES
    return {"basis": value, "rationale": rationale}


def _build_ir(
    deliberation: Mapping[str, Any],
    adjudications: Sequence[Adjudication],
    binding: Any,
    source_path: Path,
) -> dict[str, Any]:
    """Hand-author the TextIR implementation specification from the settled
    reasoning state (the durable-output boundary). Coordinates are born here:
    REQ-FENCE-001, AC-FENCE-001-A, DEC-FENCE-001.
    """
    by_ambiguity = {a.ambiguity: a for a in adjudications}
    force_record = by_ambiguity["requirement_force"]
    budget_record = by_ambiguity["latency_budget"]
    # Fail closed: IR authoring requires the adjudication records to exist.
    assert force_record.basis == "AUTHOR_JUDGMENT" and force_record.resolution == "MUST"
    assert budget_record.basis == "UNAVAILABLE" and budget_record.resolution is None

    authority = "Tribunal capstone C deliberation fixture"

    claims: list[dict[str, Any]] = [
        {
            "claim_id": "JUDG-FENCE-001",
            "role": "judgment",
            "proposition": (
                "The silent start race causes data loss, so fencing stale effect starts "
                "is a MUST, not a SHOULD."
            ),
            "material": True,
            "polarity": "positive",
            "status": "asserted",
            "scope": {
                "system": "sear-style runtime effect-start path",
                "condition": "when the agent is re-steered between effect issue and start",
            },
            "force": {
                "assessment_confidence": {
                    "level": "high",
                    "basis": {
                        "basis_type": "direct_observation",
                        "evidence_quality": "strong",
                        "evidence_coverage": "narrow",
                        "source_independence": "single",
                        "directness": "direct",
                        "consistency": "convergent",
                        "assumption_sensitivity": "low",
                        "environmental_stability": "stable",
                        "contrary_evidence": "none_found",
                        "rationale": (
                            "The runtime records the race directly; the data-loss "
                            "consequence is stated in the repo evidence; no contrary "
                            "observation exists."
                        ),
                    },
                }
            },
            "source_refs": ["EV-FENCE-001", "EV-FENCE-002"],
            "assumption_refs": ["ASM-FENCE-001"],
            "boundary_refs": ["BD-FENCE-001"],
            "semantic_basis": _basis(
                "AUTHOR_JUDGMENT",
                "The adopted judgment is Tribunal's settled reasoning state, recorded at "
                "the durable-output boundary.",
            ),
        },
        {
            "claim_id": "OBS-FENCE-001",
            "role": "observation",
            "proposition": (
                "The sear-style runtime records a steer epoch for every agent and stamps "
                "every effect with the epoch at issue."
            ),
            "material": True,
            "polarity": "positive",
            "status": "asserted",
            "semantic_basis": _basis(
                "EXPLICIT", "Stated directly in the repo fact sheet (mechanism)."
            ),
        },
        {
            "claim_id": "OBS-FENCE-002",
            "role": "observation",
            "proposition": (
                "When an agent is re-steered between issue and start, the start path still "
                "starts the stale effect; the race is silent and the stale effect's "
                "outcomes are lost."
            ),
            "material": True,
            "polarity": "positive",
            "status": "asserted",
            "semantic_basis": _basis(
                "EXPLICIT", "Stated directly in the repo fact sheet (mechanism)."
            ),
        },
        {
            "claim_id": "OQ-FENCE-001",
            "role": "open_question",
            "proposition": (
                "Whether a re-issue path alone would suffice without a start-path fence "
                "remains unresolved."
            ),
            "material": True,
            "polarity": "positive",
            "status": "unresolved",
            "semantic_basis": _basis(
                "EXPLICIT",
                "The open question is carried in the deliberation fixture's competing "
                "hypotheses.",
            ),
        },
        {
            "claim_id": "ASM-FENCE-001",
            "role": "assumption",
            "proposition": (
                "The steer epoch stays monotonic per agent; if epochs can regress the "
                "fence cannot be evaluated."
            ),
            "material": True,
            "polarity": "positive",
            "status": "asserted",
            "semantic_basis": _basis(
                "EXPLICIT", "Stated in the repo fact sheet's mechanism."
            ),
        },
        {
            "claim_id": "BD-FENCE-001",
            "role": "boundary",
            "proposition": (
                "The fence applies at effect start only; the steer-epoch mechanism "
                "itself is unchanged."
            ),
            "material": True,
            "polarity": "positive",
            "status": "asserted",
            "semantic_basis": _basis(
                "EXPLICIT", "The boundary is the deliberation fixture's settled boundary."
            ),
        },
        {
            "claim_id": "NG-FENCE-001",
            "role": "boundary",
            "proposition": "No change to effect issue or to the steer-epoch mechanism itself.",
            "material": True,
            "polarity": "negative",
            "status": "asserted",
            "semantic_basis": _basis(
                "EXPLICIT", "The exclusion is the deliberation fixture's settled boundary."
            ),
        },
        {
            "claim_id": "EX-FENCE-001",
            "role": "exception",
            "proposition": "Unless the effect is re-issued under the current steer epoch.",
            "material": True,
            "polarity": "positive",
            "status": "asserted",
            "semantic_basis": _basis(
                "EXPLICIT", "Stated in the deliberation fixture's boundary."
            ),
        },
        {
            "claim_id": "REQ-FENCE-001",
            "role": "requirement",
            "proposition": (
                "The effect start path MUST refuse an effect whose issue epoch predates "
                "the agent's current steer epoch."
            ),
            "material": True,
            "polarity": "positive",
            "status": "asserted",
            "scope": {"system": "sear-style runtime effect-start path"},
            "force": {"deontic": "MUST"},
            "source_refs": ["EV-FENCE-001", "EV-FENCE-002"],
            "requirement": {
                "requirement_id": "REQ-FENCE-001",
                "actor": "effect start path",
                "deontic": "MUST",
                "action": "refuse",
                "object": "an effect whose issue epoch predates the agent's current steer epoch",
                "trigger": "the agent is re-steered between effect issue and effect start",
                "condition": "the effect's issue epoch predates the current steer epoch",
                "acceptance_criterion_id": "AC-FENCE-001-A",
                "acceptance_criterion": (
                    "A stale effect start is refused and an explicit error is recorded "
                    "before any side effect runs."
                ),
                "source_authority": authority,
                "semantic_basis": _basis(
                    "AUTHOR_JUDGMENT",
                    "The Tribunal-like tier resolved the SHOULD/MUST ambiguity from the "
                    "evidence of silent data loss; no human was consulted.",
                ),
            },
            "semantic_basis": _basis(
                "AUTHOR_JUDGMENT",
                "The requirement force is the adjudication record for requirement_force.",
            ),
        },
        {
            "claim_id": "REQ-FENCE-002",
            "role": "requirement",
            "proposition": "The runtime SHOULD keep the fence check overhead within a latency budget.",
            "material": True,
            "polarity": "positive",
            "status": "asserted",
            "scope": {"system": "sear-style runtime effect-start path"},
            "force": {"deontic": "SHOULD"},
            "requirement": {
                "requirement_id": "REQ-FENCE-002",
                "actor": "runtime",
                "deontic": "SHOULD",
                "action": "keep",
                "object": "the fence check overhead within a latency budget",
                "rationale": (
                    "The budget stays advisory until a measurement exists; the fence MUST "
                    "NOT be blocked on an unmeasured bound, which is the override path "
                    "for this SHOULD."
                ),
                "source_authority": authority,
                "semantic_basis": _basis(
                    "UNAVAILABLE",
                    "No measured evidence for a budget exists; the value stays UNAVAILABLE "
                    "and is never promoted to an explicit bound.",
                ),
            },
            "semantic_basis": _basis(
                "UNAVAILABLE",
                "The latency-budget adjudication record resolved to UNAVAILABLE.",
            ),
        },
        {
            "claim_id": "AC-FENCE-001-A",
            "role": "definition",
            "proposition": (
                "A stale effect start is refused and an explicit error is recorded before "
                "any side effect runs."
            ),
            "material": False,
            "polarity": "positive",
            "status": "asserted",
            "semantic_basis": _basis(
                "AUTHOR_JUDGMENT",
                "Acceptance criterion authored at the durable-output boundary from the "
                "adopted judgment.",
            ),
        },
        {
            "claim_id": "DEC-FENCE-001",
            "role": "recommendation",
            "proposition": (
                "Adopt the steer-epoch fence at effect start as the mechanism that "
                "prevents stale effect starts."
            ),
            "material": True,
            "polarity": "positive",
            "status": "asserted",
            "decision_id": "DEC-FENCE-001",
            "semantic_basis": _basis(
                "AUTHOR_JUDGMENT",
                "The adopted design decision is new authoring at the durable-output "
                "boundary, not extracted source truth.",
            ),
        },
    ]

    def ptr(index: int) -> str:
        return f"#/sections/0/claims/{index}"

    # The definition claim for the acceptance criterion.
    ac_index = next(i for i, c in enumerate(claims) if c["claim_id"] == "AC-FENCE-001-A")
    req1_index = next(i for i, c in enumerate(claims) if c["claim_id"] == "REQ-FENCE-001")
    req2_index = next(i for i, c in enumerate(claims) if c["claim_id"] == "REQ-FENCE-002")
    dec_index = next(i for i, c in enumerate(claims) if c["claim_id"] == "DEC-FENCE-001")

    document: dict[str, Any] = {
        "schema_version": "ats.text_ir.v1",
        "artifact_id": "artifact-tribunal-capstone-c-fence",
        "source": {
            "content_sha256": binding.content_sha256,
            "normalized_sha256": binding.normalized_sha256,
            "media_type": "text/plain",
            "locator": source_path.name,
        },
        "policy_snapshot_id": "policy-fixture-draft2",
        "language": "en",
        "audience": {"audience_id": "tribunal-capstone-c", "expertise": "expert"},
        "sections": [
            {
                "section_id": "s1",
                "heading": (
                    "Steer-epoch effect fence — Tribunal deliberation and implementation "
                    "specification"
                ),
                "profiles": ["ASSESS", "SPECIFY"],
                "claims": claims,
                "evidence": [
                    {
                        "evidence_id": "EV-FENCE-001",
                        "proposition": (
                            "Steer epochs are recorded per agent and every effect start "
                            "carries the epoch at issue."
                        ),
                        "source": {
                            "source_id": FACT_SHEET["source_id"],
                            "source_type": "repository_artifact",
                            "availability": "present",
                            "locator": "capstone-c:repo-evidence",
                        },
                        "availability": "present",
                    },
                    {
                        "evidence_id": "EV-FENCE-002",
                        "proposition": (
                            "A stale effect start is silent: no error is logged and the "
                            "stale effect's outcomes are lost."
                        ),
                        "source": {
                            "source_id": FACT_SHEET["source_id"],
                            "source_type": "repository_artifact",
                            "availability": "present",
                            "locator": "capstone-c:repo-evidence",
                        },
                        "availability": "present",
                    },
                    {
                        "evidence_id": "EV-FENCE-003",
                        "proposition": (
                            "No latency measurement exists for the fence check in the "
                            "current runtime."
                        ),
                        "source": {
                            "source_id": FACT_SHEET["source_id"],
                            "source_type": "repository_artifact",
                            "availability": "present",
                            "locator": "capstone-c:repo-evidence",
                        },
                        "availability": "present",
                    },
                ],
                "relations": [
                    {
                        "relation_id": "rel1",
                        "source_id": "EV-FENCE-001",
                        "type": "supports",
                        "target_id": "JUDG-FENCE-001",
                        "material": True,
                    },
                    {
                        "relation_id": "rel2",
                        "source_id": "EV-FENCE-002",
                        "type": "supports",
                        "target_id": "JUDG-FENCE-001",
                        "material": True,
                    },
                    {
                        "relation_id": "rel3",
                        "source_id": "ASM-FENCE-001",
                        "type": "condition_for",
                        "target_id": "JUDG-FENCE-001",
                        "material": True,
                    },
                    {
                        "relation_id": "rel4",
                        "source_id": "BD-FENCE-001",
                        "type": "qualifies",
                        "target_id": "JUDG-FENCE-001",
                        "material": True,
                    },
                    {
                        "relation_id": "rel5",
                        "source_id": "EX-FENCE-001",
                        "type": "exception_to",
                        "target_id": "REQ-FENCE-001",
                        "material": True,
                    },
                    {
                        "relation_id": "rel6",
                        "source_id": "REQ-FENCE-002",
                        "type": "depends_on",
                        "target_id": "REQ-FENCE-001",
                        "material": True,
                    },
                ],
                "update_indicators": [
                    {
                        "indicator_id": "UI-FENCE-001",
                        "text": (
                            "Downgrade the fence judgment if the runtime gains a mechanism "
                            "that prevents stale starts at issue time."
                        ),
                        "target_claim_refs": ["JUDG-FENCE-001"],
                        "effect": "decrease_likelihood",
                    }
                ],
            }
        ],
        "extraction_status": "complete",
        "basis_policy": {"default_basis": "EXPLICIT", "declared": True},
        "stable_coordinates": [
            {
                "kind": "requirement_id",
                "id": "REQ-FENCE-001",
                "source_pointer": ptr(req1_index),
            },
            {
                "kind": "requirement_id",
                "id": "REQ-FENCE-002",
                "source_pointer": ptr(req2_index),
            },
            {
                "kind": "acceptance_criterion_id",
                "id": "AC-FENCE-001-A",
                "source_pointer": ptr(req1_index) + "/requirement/acceptance_criterion_id",
            },
            {
                "kind": "decision_id",
                "id": "DEC-FENCE-001",
                "source_pointer": ptr(dec_index),
            },
        ],
    }
    return document


# ---------------------------------------------------------------------------
# 4. The Arq-like planning consumer (pure Python, in this test)
# ---------------------------------------------------------------------------


def _verify_source_ats(projection: Mapping[str, Any], source_ats: Mapping[str, Any]) -> None:
    """Arq-like validation: a source-backed task's coordinates must resolve in
    the projection, and at least one coordinate must be present."""
    if not source_ats.get("requirement_ids") and not source_ats.get("decision_ids") and not (
        source_ats.get("acceptance_criterion_ids")
    ):
        raise ValueError(
            f"source-backed task carries no source coordinate; refusing to fabricate one"
        )
    proj_reqs = {r["requirement_id"] for r in projection["requirements"]}
    proj_decs = {d["decision_id"] for d in projection["decisions"]}
    proj_acs = {a["acceptance_criterion_id"] for a in projection["acceptance_criteria"]}
    bad = set(source_ats["requirement_ids"]) - proj_reqs
    if bad:
        raise ValueError(f"requirement ids do not resolve in the projection: {sorted(bad)}")
    bad = set(source_ats["decision_ids"]) - proj_decs
    if bad:
        raise ValueError(f"decision ids do not resolve in the projection: {sorted(bad)}")
    bad = set(source_ats["acceptance_criterion_ids"]) - proj_acs
    if bad:
        raise ValueError(f"acceptance criterion ids do not resolve in the projection: {sorted(bad)}")


def _derive_task(
    projection: Mapping[str, Any],
    *,
    task_id: str,
    title: str,
    requirement_ids: Sequence[str],
    decision_ids: Sequence[str] = (),
    acceptance_criterion_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """One derived VX-like task carrying its ``source_ats`` lineage."""
    source_ats = {
        "artifact_id": projection["artifact_id"],
        "artifact_sha256": projection["artifact_sha256"],
        "requirement_ids": list(requirement_ids),
        "decision_ids": list(decision_ids),
        "acceptance_criterion_ids": list(acceptance_criterion_ids),
    }
    _verify_source_ats(projection, source_ats)
    return {"task_id": task_id, "title": title, "source_ats": source_ats}


def derive_tasks(
    projection: Mapping[str, Any], receipt_verification: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """The Arq-like planning consumer.

    Arq verifies the receipt, consumes the projection, and never re-authors:
    tasks are derived by mapping projection coordinates onto execution units,
    and every source-backed task carries ``source_ats`` lineage.
    """
    if receipt_verification["status"] != "PASS":
        raise ValueError(
            "Arq refuses to consume a projection whose ATS receipt does not verify "
            f"(status {receipt_verification['status']!r})"
        )
    projection_before = copy.deepcopy(projection)

    # One -> many: REQ-FENCE-001 decomposes into three independently verifiable tasks.
    tasks = [
        _derive_task(
            projection,
            task_id="VX-T1",
            title="Introduce the steer epoch basis for effect starts",
            requirement_ids=["REQ-FENCE-001"],
            decision_ids=["DEC-FENCE-001"],
        ),
        _derive_task(
            projection,
            task_id="VX-T2",
            title="Fence stale effect starts at the start path",
            requirement_ids=["REQ-FENCE-001"],
            decision_ids=["DEC-FENCE-001"],
            acceptance_criterion_ids=["AC-FENCE-001-A"],
        ),
        _derive_task(
            projection,
            task_id="VX-T3",
            title="Add race fixtures reproducing silent stale starts",
            requirement_ids=["REQ-FENCE-001"],
        ),
        # Many -> one: REQ-FENCE-001 and its dependency REQ-FENCE-002 land atomically.
        _derive_task(
            projection,
            task_id="VX-T4",
            title="Land the fence with budget instrumentation as one atomic change",
            requirement_ids=["REQ-FENCE-001", "REQ-FENCE-002"],
            decision_ids=["DEC-FENCE-001"],
            acceptance_criterion_ids=["AC-FENCE-001-A"],
        ),
    ]
    # Arq consumes, does not re-author: the projection is untouched.
    assert copy.deepcopy(projection) == projection_before
    return tasks


def planner_task_with_rationale(task_id: str, rationale: str) -> dict[str, Any]:
    """The only way a task without a source coordinate may exist: an explicit
    planner-created rationale. Without one the mock rejects the task."""
    if not rationale.strip():
        raise ValueError(
            f"task {task_id!r} has no source_ats and no explicit planner-created rationale; "
            "refusing to source-back an unsourced task"
        )
    return {"task_id": task_id, "planner_rationale": rationale}


# ---------------------------------------------------------------------------
# The chain fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ctx() -> Context:
    """The draft.2 evaluation context (stable coordinates are draft.2)."""
    return Context.load(spec_version="1.0.0-draft.2", now=FIXED_NOW)


@pytest.fixture(scope="module")
def policy() -> dict[str, Any]:
    """The fleet policy snapshot (draft.2, content-addressed)."""
    return json.loads((FIXTURES / "policies" / "draft2.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def source_path(tmp_path_factory) -> Path:
    """The operator brief as a bound source artifact (the chain's input)."""
    directory = tmp_path_factory.mktemp("capstone_c")
    path = directory / "operator_brief.txt"
    path.write_text(BRIEF + "\n", encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def source_binding(source_path) -> Any:
    """The source binding (content + normalized hashes) of the operator brief."""
    binding = bind_file(source_path)
    assert binding.content_sha256 == binding.normalized_sha256  # normalization is a no-op
    return binding


@pytest.fixture(scope="module")
def deliberation() -> dict[str, Any]:
    return _deliberation_fixture()


@pytest.fixture(scope="module")
def adjudications(deliberation) -> list[Adjudication]:
    return adjudicate(deliberation)


@pytest.fixture(scope="module")
def ir_document(deliberation, adjudications, source_binding, source_path) -> dict[str, Any]:
    return _build_ir(deliberation, adjudications, source_binding, source_path)


@pytest.fixture(scope="module")
def lint_report(ctx, ir_document, policy, source_path) -> dict[str, Any]:
    return lint_ir(ctx, ir_document, policy, source_path=source_path)


@pytest.fixture(scope="module")
def receipt(ctx, ir_document, policy, lint_report) -> dict[str, Any]:
    ir = IrDocument.from_document(ir_document)
    return build_candidate_receipt(
        ctx,
        ir=ir,
        policy=ctx.policy(policy),
        output_sha256=None,
        lint_report=lint_report,
        adjudicator="tribunal-capstone-c-fixture",
    )


@pytest.fixture(scope="module")
def receipt_verification(ctx, receipt, ir_document, policy) -> dict[str, Any]:
    return verify_receipt(
        ctx,
        receipt,
        ir_document=ir_document,
        policy=ctx.policy(policy),
    )


@pytest.fixture(scope="module")
def projection(ctx, ir_document, policy, source_binding) -> dict[str, Any]:
    return project_from_ir(
        ctx, ir_document, policy, artifact_sha256=source_binding.content_sha256
    )


@pytest.fixture(scope="module")
def tasks(projection, receipt_verification) -> list[dict[str, Any]]:
    return derive_tasks(projection, receipt_verification)


# ---------------------------------------------------------------------------
# The assertions
# ---------------------------------------------------------------------------


class TestCapstoneCTribunalChain:
    """Capstone C: operator intent → Tribunal-like deliberation → adjudication
    → ATS IR → lint → receipt → projection → Arq-like tasks, coordinates
    preserved end to end."""

    # -- 1/2. Tribunal-like deliberation and adjudication -------------------

    def test_deliberation_fixture_captures_the_settled_reasoning_state(
        self, deliberation
    ) -> None:
        """The fixture carries what Tribunal knows at the durable-output boundary:
        competing hypotheses, adopted judgment, boundary, evidence, ambiguities."""
        assert deliberation["artifact_type"] == "implementation_spec"
        assert {h["id"] for h in deliberation["competing_hypotheses"]} == {"H1", "H2"}
        assert deliberation["adopted_judgment"] == "H2"
        assert "effect start" in deliberation["boundary"]
        assert {e["evidence_id"] for e in deliberation["evidence"]} == {
            "EV-FENCE-001",
            "EV-FENCE-002",
            "EV-FENCE-003",
        }
        by_id = {a["id"]: a for a in deliberation["ambiguities"]}
        assert by_id["requirement_force"]["alternatives"] == ["SHOULD", "MUST"]
        assert by_id["latency_budget"]["alternatives"] == ["SHOULD", "MUST"]

    def test_adjudication_resolves_must_from_evidence_without_human(
        self, adjudications
    ) -> None:
        """The ladder proves out: deterministic recovery fails, the Tribunal-like
        tier adjudicates from evidence, and the record is AUTHOR_JUDGMENT with no
        human — while the latency budget stays UNAVAILABLE, never promoted."""
        by_ambiguity = {a.ambiguity: a for a in adjudications}

        force = by_ambiguity["requirement_force"]
        assert force.resolution == "MUST"
        assert force.basis == "AUTHOR_JUDGMENT"
        assert force.ladder == ("deterministic_recovery", "adjudicate_from_evidence")
        assert force.human is False
        assert "data loss" in force.rationale

        budget = by_ambiguity["latency_budget"]
        assert budget.resolution is None
        assert budget.basis == "UNAVAILABLE"
        assert budget.ladder == (
            "deterministic_recovery",
            "adjudicate_from_evidence",
            "unavailable",
        )
        assert budget.human is False

    def test_adjudication_never_promotes_without_evidence(self) -> None:
        """Negative control: with the evidence stripped, the same ambiguity
        resolves to UNAVAILABLE — never a silent promotion (ATS-BASIS-002)."""
        deliberation = _deliberation_fixture()
        deliberation["evidence"] = []
        records = {a.ambiguity: a for a in adjudicate(deliberation)}
        assert records["requirement_force"].basis == "UNAVAILABLE"
        assert records["requirement_force"].resolution is None
        assert records["latency_budget"].basis == "UNAVAILABLE"
        assert records["latency_budget"].resolution is None

    # -- 3. The ATS side ---------------------------------------------------

    def test_ir_is_hand_authored_from_the_deliberation_state(self, ir_document) -> None:
        """ASSESS+SPECIFY IR carrying the born-here coordinates and the two
        adjudication resolutions with their declared semantic bases."""
        assert ir_document["schema_version"] == "ats.text_ir.v1"
        assert ir_document["sections"][0]["profiles"] == ["ASSESS", "SPECIFY"]
        assert ir_document["basis_policy"] == {
            "default_basis": "EXPLICIT",
            "declared": True,
        }

        claims = {c["claim_id"]: c for c in ir_document["sections"][0]["claims"]}
        req1 = claims["REQ-FENCE-001"]
        assert req1["requirement"]["deontic"] == "MUST"
        assert req1["requirement"]["semantic_basis"]["basis"] == "AUTHOR_JUDGMENT"
        assert req1["requirement"]["acceptance_criterion_id"] == "AC-FENCE-001-A"
        assert req1["semantic_basis"]["basis"] == "AUTHOR_JUDGMENT"

        req2 = claims["REQ-FENCE-002"]
        assert req2["requirement"]["deontic"] == "SHOULD"
        assert req2["requirement"]["semantic_basis"]["basis"] == "UNAVAILABLE"
        assert req2["semantic_basis"]["basis"] == "UNAVAILABLE"

        coordinates = {c["id"]: c for c in ir_document["stable_coordinates"]}
        assert set(coordinates) == {
            "REQ-FENCE-001",
            "REQ-FENCE-002",
            "AC-FENCE-001-A",
            "DEC-FENCE-001",
        }
        assert coordinates["AC-FENCE-001-A"]["source_pointer"].endswith(
            "/requirement/acceptance_criterion_id"
        )

    def test_lint_is_integrity_green_and_never_promotes(
        self, lint_report, ir_document
    ) -> None:
        """The real pipeline's lint: integrity-green (mechanical PASS, zero
        required failures), profile complete, and no promotion of the UNAVAILABLE
        latency budget."""
        assert lint_report["conformance"]["mechanical"] == "PASS", lint_report[
            "conformance_rationale"
        ]["mechanical"]
        assert lint_report["summary"]["required_failed"] == 0
        assert lint_report["conformance"]["profile"] == "PASS"
        checks = {c["check_id"]: c for c in lint_report["structural_checks"]}
        assert checks["IR-SOURCE-HASH"]["status"] == "PASS"
        assert checks["IR-BASIS-SCHEMA"]["status"] == "PASS"
        assert checks["IR-PROFILE-SLOTS"]["status"] == "PASS"

        basis002 = next(
            r for r in lint_report["rule_results"] if r["rule_id"] == "ATS-BASIS-002"
        )
        # No source basis ledger exists to compare against, so BASIS-002 is honestly
        # UNAVAILABLE (never PASS-by-absence) and never FAILs: nothing was promoted.
        assert basis002["status"] in ("UNAVAILABLE", "REVIEW_REQUIRED")
        assert basis002["status"] != "FAIL"
        assert all(
            f.get("rule_id") != "ATS-BASIS-002" for f in lint_report["findings"]
        )

    def test_receipt_binds_the_bundle_and_verifies(
        self, receipt, receipt_verification, lint_report
    ) -> None:
        """The ATS receipt: sealed, bound to the source and policy, adjudicated
        by an external identity, and verified green against the artifacts."""
        assert receipt["spec_version"] == "1.0.0-draft.2"
        assert receipt["adjudicator"] == "tribunal-capstone-c-fixture"
        ok, declared, recomputed = verify_seal(receipt)
        assert ok and declared == recomputed == receipt["receipt_sha256"]
        assert receipt_verification["status"] == "PASS", receipt_verification["detail"]
        assert receipt["conformance"]["mechanical"] == lint_report["conformance"]["mechanical"]

    # -- 4/5. The real projection and the Arq-like consumer -----------------

    def test_projection_carries_the_born_here_coordinates(
        self, projection, ir_document, policy, source_binding
    ) -> None:
        """The real projection: sealed, schema-valid, profile ASSESS+SPECIFY, and
        carrying REQ-FENCE-001, AC-FENCE-001-A, DEC-FENCE-001 with source pointers."""
        assert projection["spec_version"] == "1.0.0-draft.2"
        assert projection["profile"] == "ASSESS+SPECIFY"
        assert projection["artifact_id"] == "artifact-tribunal-capstone-c-fence"
        assert projection["artifact_sha256"] == source_binding.content_sha256
        assert projection["policy_snapshot_id"] == policy["snapshot_id"]
        assert projection["policy_snapshot_sha256"] == policy["snapshot_sha256"]
        ok, declared, recomputed = verify_seal(projection)
        assert ok and declared == recomputed == projection["projection_id"]

        reqs = {r["requirement_id"]: r for r in projection["requirements"]}
        req1 = reqs["REQ-FENCE-001"]
        assert req1["deontic"] == "MUST"
        assert req1["actor"] == "effect start path"
        assert req1["action"] == "refuse"
        assert req1["acceptance_criterion_id"] == "AC-FENCE-001-A"
        assert req1["source_pointer"].startswith("/sections/0/claims/")
        assert req1["authority"] == "Tribunal capstone C deliberation fixture"
        # The UNAVAILABLE budget is carried, never promoted to MUST.
        assert reqs["REQ-FENCE-002"]["deontic"] == "SHOULD"

        assert projection["decisions"] == [
            {
                "decision_id": "DEC-FENCE-001",
                "proposition": (
                    "Adopt the steer-epoch fence at effect start as the mechanism that "
                    "prevents stale effect starts."
                ),
                "status": "asserted",
                "source_pointer": "/sections/0/claims/11",
            }
        ]
        acs = {a["acceptance_criterion_id"]: a for a in projection["acceptance_criteria"]}
        assert acs["AC-FENCE-001-A"]["criterion"] == (
            "A stale effect start is refused and an explicit error is recorded before "
            "any side effect runs."
        )
        assert acs["AC-FENCE-001-A"]["requirement_ids"] == ["REQ-FENCE-001"]
        # Coordinates copy verbatim from the IR.
        assert projection["stable_coordinates"] == ir_document["stable_coordinates"]
        # REQ-FENCE-002 depends on REQ-FENCE-001 (drives the many→one task).
        assert projection["dependencies"] == [
            {"from_requirement_id": "REQ-FENCE-002", "to_requirement_id": "REQ-FENCE-001",
             "kind": "depends_on"}
        ]

    def test_arq_consumer_derives_one_to_many_tasks(self, tasks) -> None:
        """REQ-FENCE-001 decomposes into three VX-like tasks, each carrying the
        source_ats lineage {artifact_id, artifact_sha256, requirement_ids,
        decision_ids, acceptance_criterion_ids}."""
        one_to_many = [t for t in tasks if t["task_id"] in ("VX-T1", "VX-T2", "VX-T3")]
        assert [t["task_id"] for t in one_to_many] == ["VX-T1", "VX-T2", "VX-T3"]
        for task in one_to_many:
            lineage = task["source_ats"]
            assert lineage["artifact_id"] == "artifact-tribunal-capstone-c-fence"
            assert set(lineage["requirement_ids"]) == {"REQ-FENCE-001"}
            # Lineage validity (ids resolve in the projection) is enforced by the
            # consumer's own gate; the end-to-end test re-asserts it over the
            # full projection.
        (t2,) = [t for t in tasks if t["task_id"] == "VX-T2"]
        assert t2["source_ats"]["acceptance_criterion_ids"] == ["AC-FENCE-001-A"]
        (t1,) = [t for t in tasks if t["task_id"] == "VX-T1"]
        assert t1["source_ats"]["decision_ids"] == ["DEC-FENCE-001"]

    def test_arq_consumer_derives_many_to_one_task(self, tasks) -> None:
        """REQ-FENCE-001 and its dependency REQ-FENCE-002 land atomically in one
        combined task."""
        (many_to_one,) = [t for t in tasks if t["task_id"] == "VX-T4"]
        assert set(many_to_one["source_ats"]["requirement_ids"]) == {
            "REQ-FENCE-001",
            "REQ-FENCE-002",
        }
        assert many_to_one["source_ats"]["decision_ids"] == ["DEC-FENCE-001"]
        assert many_to_one["source_ats"]["acceptance_criterion_ids"] == ["AC-FENCE-001-A"]

    def test_unsourced_task_needs_planner_rationale_or_is_rejected(self) -> None:
        """No task is source-backed without a source coordinate: the deliberately
        unsourced task is rejected unless it carries an explicit planner-created
        rationale (the mock's fail-closed gate)."""
        with pytest.raises(ValueError, match="no source_ats and no explicit"):
            planner_task_with_rationale("VX-T5", "")
        accepted = planner_task_with_rationale(
            "VX-T5", "Planner-created warm-up script; no ATS source coordinate exists."
        )
        assert accepted["task_id"] == "VX-T5"
        assert "planner_rationale" in accepted

    def test_coordinates_survive_the_full_chain(
        self, ir_document, lint_report, receipt, projection, tasks
    ) -> None:
        """End to end: the coordinates born at Tribunal survive IR → lint →
        receipt → projection → every source-backed VX task, and the two
        adjudication resolutions hold at every stage."""
        ir_ids = {c["id"] for c in ir_document["stable_coordinates"]}
        projection_ids = {c["id"] for c in projection["stable_coordinates"]}
        assert projection_ids == ir_ids

        reqs = {r["requirement_id"] for r in projection["requirements"]}
        decs = {d["decision_id"] for d in projection["decisions"]}
        acs = {a["acceptance_criterion_id"] for a in projection["acceptance_criteria"]}
        assert {"REQ-FENCE-001", "REQ-FENCE-002"} <= reqs
        assert "DEC-FENCE-001" in decs
        assert "AC-FENCE-001-A" in acs

        source_backed = [t for t in tasks if "source_ats" in t]
        assert source_backed, "the consumer must derive source-backed tasks"
        for task in source_backed:
            lineage = task["source_ats"]
            assert lineage["artifact_id"] == projection["artifact_id"]
            assert lineage["artifact_sha256"] == projection["artifact_sha256"]
            # Every source-backed task references REQ-FENCE-001.
            assert "REQ-FENCE-001" in lineage["requirement_ids"]
            assert set(lineage["requirement_ids"]) <= reqs
            assert set(lineage["decision_ids"]) <= decs
            assert set(lineage["acceptance_criterion_ids"]) <= acs

        # The receipt's identity rides on the same artifact lineage.
        assert receipt["source_sha256"] == projection["artifact_sha256"]
        assert receipt["spec_version"] == projection["spec_version"] == "1.0.0-draft.2"
        assert lint_report["spec_version"] == "1.0.0-draft.2"

        # The ambiguity resolved to AUTHOR_JUDGMENT without human; the latency
        # budget stayed UNAVAILABLE — both visible in the IR and the projection.
        claims = {c["claim_id"]: c for c in ir_document["sections"][0]["claims"]}
        assert claims["REQ-FENCE-001"]["requirement"]["semantic_basis"]["basis"] == (
            "AUTHOR_JUDGMENT"
        )
        assert claims["REQ-FENCE-002"]["requirement"]["semantic_basis"]["basis"] == "UNAVAILABLE"
        by_id = {r["requirement_id"]: r for r in projection["requirements"]}
        assert by_id["REQ-FENCE-001"]["deontic"] == "MUST"
        assert by_id["REQ-FENCE-002"]["deontic"] == "SHOULD"

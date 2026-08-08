"""Milestone capstones A and B for the draft.2 pipeline.

Each capstone drives the real draft.2 pipeline end to end — bound source file,
hand-authored TextIR (simulating the authoring-skill output, not human
field-by-field annotation), ``Context.load(spec_version="1.0.0-draft.2")``,
``lint_ir``, and (where the public contract calls for it) the planning
projection — and checks the documented invariants at the far end. Both are
deterministic, network-free, and pinned to the fixed evaluation clock.

Capstone A — pre-ATS prose → ATS without invented authority. A three-document
technical set whose sources never declare an authority hierarchy. The prose
contains the deliberate temptation: document 1 calls itself "the authoritative
reference for the storage subsystem" and "the foundation of the platform",
which invites a downstream model to invent "doc 1 > doc 2 / doc 3". The ATS
treatment records the temptation as an unresolved question with basis
UNAVAILABLE, keeps every requirement's authority-axis basis at
INFERRED/EXPLICIT-with-declared-source, and never emits a precedence in the
planning projection: without a declared hierarchy, precedence remains absent.

Capstone B — new-architecture authoring. An operator brief plus a repository
fact sheet drive an ASSESS+SPECIFY document whose new design choices carry
``AUTHOR_JUDGMENT`` basis, sourced facts carry ``EXPLICIT``, and missing
evidence (an unmeasured latency budget) stays ``UNAVAILABLE``. Stable
coordinates, decisions, alternatives, requirements, acceptance criteria, and
update indicators are all declared, and the planning projection preserves the
coordinate ids end to end.

The expected lint statuses below come from the public rule table and the
never-PASS-by-absence discipline (ADR-0002): basis presence checks are
meaningful, explicit-vs-inferred distinctions remain visible, and no check
result is ever FAIL on integrity.
"""

from __future__ import annotations

from pathlib import Path

from ats.ir.lint import lint_ir
from ats.planning import project_from_ir

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES = REPO_ROOT / "fixtures" / "ir" / "sources"

#: Content addresses of the two bound source artifacts (``bind_file`` over the
#: fixture bytes; the IRs declare exactly these values).
SOURCE_A_SHA = "73ea387f718fa01074c0c77a7daddc3b0a2c309a91d42f7a0991f63ae6127664"
SOURCE_B_SHA = "cf33e0622b54961550db4e66cf94a68793c8d8116febf991f21752483d217b55"

POLICY_STEM = "draft2"

#: Basis vocabulary verbatim from the draft.2 amendment (D-F / spec 4.25).
EXPLICIT = "EXPLICIT"
INFERRED = "INFERRED"
UNAVAILABLE = "UNAVAILABLE"
AUTHOR_JUDGMENT = "AUTHOR_JUDGMENT"

#: The temptation: doc 1's self-description that would invite a fabricated
#: hierarchy in a non-ATS reading.
TEMPTATION_PHRASE = "authoritative reference"

#: Cross-document precedence vocabulary that must NOT appear anywhere in the
#: pre-ATS source set (the set declares no hierarchy at all).
PRECEDENCE_VOCABULARY = ("overrides", "supersedes", "takes precedence", "outranks", "governs")


def _assert_statuses(report: dict, expected: dict[str, str]) -> None:
    """Every rule id in ``expected`` must hold exactly the status string given."""
    results = {r["rule_id"]: r for r in report["rule_results"]}
    for rule_id, status in expected.items():
        assert results[rule_id]["status"] == status, (
            f"{rule_id}: expected {status}, got {results[rule_id]['status']} "
            f"({results[rule_id].get('reason', '')})"
        )


def _basis_of(ir: dict, claim_id: str) -> str | None:
    for section in ir["sections"]:
        for claim in section["claims"]:
            if claim["claim_id"] == claim_id:
                basis = claim.get("semantic_basis") or {}
                return basis.get("basis")
    raise AssertionError(f"no claim {claim_id!r} in the IR")


def _ledger_of(ir: dict, claim_id: str) -> dict[str, str]:
    for section in ir["sections"]:
        for claim in section["claims"]:
            if claim["claim_id"] == claim_id:
                return dict(claim.get("extensions", {}).get("source_basis", {}))
    raise AssertionError(f"no claim {claim_id!r} in the IR")


def _explicit_claims_with_promoted_source(ir: dict) -> list[str]:
    """Claims declaring EXPLICIT basis over a source recorded INFERRED/UNAVAILABLE.

    This is exactly the silent-promotion condition ATS-BASIS-002 forbids,
    checked directly against the IR data so the capstone does not depend on
    the linter alone to prove the point.
    """
    promoted: list[str] = []
    for section in ir["sections"]:
        for claim in section["claims"]:
            basis = (claim.get("semantic_basis") or {}).get("basis")
            if basis != EXPLICIT:
                continue
            ledger = _ledger_of(ir, claim["claim_id"])
            for source_ref in claim.get("source_refs", ()):
                if ledger.get(source_ref) in (INFERRED, UNAVAILABLE):
                    promoted.append(claim["claim_id"])
    return promoted


def _resolve_pointer(ir: dict, pointer: str):
    """Resolve a JSON pointer of the form ``#/sections/1/claims/0`` into the IR."""
    node = ir
    for part in pointer.lstrip("#/").split("/"):
        node = node[int(part)] if part.isdigit() else node[part]
    return node


def _assert_coordinate_pointers_resolve(ir: dict) -> None:
    """Every declared coordinate's source_pointer must point at its carrier.

    This keeps the hand-authored fixture honest: the declared coordinate ids
    are not merely present in the IR, each one is declared at the exact
    location that carries it (contract D-C "stable semantic coordinates").
    """
    for entry in ir["stable_coordinates"]:
        kind, coord_id, pointer = entry["kind"], entry["id"], entry["source_pointer"]
        node = _resolve_pointer(ir, pointer)
        if kind == "requirement_id":
            assert node["requirement"]["requirement_id"] == coord_id, pointer
        elif kind == "decision_id":
            assert node["decision_id"] == coord_id, pointer
        elif kind == "acceptance_criterion_id":
            assert node == coord_id, pointer
        else:  # pragma: no cover - the fixtures only declare these three kinds
            raise AssertionError(f"unexpected coordinate kind {kind!r}")


class TestCapstoneA:
    """Capstone A: pre-ATS prose → ATS without invented authority (§36).

    Fixture: three short pre-ATS documents (``fixtures/ir/sources/
    capstone_a_multi_doc_set.txt``). The documents describe the storage
    service, the gateway, and the retention policy. None declares any
    precedence among the three — yet document 1 describes itself as "the
    authoritative reference for the storage subsystem" and "the foundation of
    the platform".

    Temptation (comment-level note, §36 "prove the temptation is resisted"):
    a downstream model reading the raw prose is invited to invent "doc 1 > doc
    2 > doc 3" — doc 1's "authoritative"/"foundation" self-description reads
    as hierarchy, and doc 2's write-path obligation reads as if it derived
    from doc 1's authority. The ATS treatment does not resolve the question;
    it records it: the IR carries the precedence question as an open question
    with basis UNAVAILABLE, keeps requirement bases at EXPLICIT only where a
    document states the obligation verbatim (doc 2's SHALL NOT prohibition)
    and INFERRED where the prose merely describes behavior (doc 1's retention
    statement), and the lint + projection never upgrade any of that to an
    explicit authority fact.
    """

    #: The hand-authored TextIR — the simulated output of the authoring
    #: skill over the pre-ATS set, not a human annotation pass.
    IR: dict = {
        "schema_version": "ats.text_ir.v1",
        "artifact_id": "capstone-a-pre-ats-authoring",
        "source": {
            "content_sha256": SOURCE_A_SHA,
            "normalized_sha256": SOURCE_A_SHA,
            "media_type": "text/plain",
            "locator": "fixtures/ir/sources/capstone_a_multi_doc_set.txt",
        },
        "policy_snapshot_id": "policy-fixture-draft2",
        "language": "en",
        "audience": {"audience_id": "capstone-a-audience", "expertise": "expert"},
        "basis_policy": {"default_basis": INFERRED, "declared": True},
        "sections": [
            {
                "section_id": "authority-assessment",
                "heading": "Authority assessment of the pre-ATS document set",
                "profiles": ["ASSESS"],
                "claims": [
                    {
                        "claim_id": "J-A-1",
                        "role": "judgment",
                        "proposition": (
                            "The document set declares no precedence among its three documents: "
                            "no document names another as subordinate, superior, or "
                            "conditionally authoritative."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "scope": {"system": "capstone-a document set"},
                        "force": {
                            "assessment_confidence": {
                                "level": "moderate",
                                "basis": {
                                    "basis_type": "direct_observation",
                                    "evidence_quality": "strong",
                                    "evidence_coverage": "broad",
                                    "source_independence": "independent",
                                    "directness": "direct",
                                    "consistency": "convergent",
                                    "assumption_sensitivity": "low",
                                    "environmental_stability": "stable",
                                    "contrary_evidence": "none_found",
                                    "rationale": (
                                        "The judgment restates what the three documents do and do "
                                        "not say; no likelihood applies because the claim is about "
                                        "document content, not an uncertain event."
                                    ),
                                },
                            }
                        },
                        "source_refs": ["EV-A-1"],
                        "assumption_refs": ["AS-A-1"],
                        "boundary_refs": ["BD-A-1"],
                        "status": "asserted",
                        "semantic_basis": {
                            "basis": INFERRED,
                            "rationale": (
                                "The absence of any precedence declaration is inferred from the "
                                "three documents; none of them states the absence itself."
                            ),
                        },
                        "extensions": {"source_basis": {"EV-A-1": INFERRED}},
                    },
                    {
                        "claim_id": "OQ-A-1",
                        "role": "open_question",
                        "proposition": (
                            "Whether document 1's self-description as the authoritative reference "
                            "for the storage subsystem also makes it authoritative over the "
                            "gateway and retention documents is unresolved: the source set does "
                            "not say."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "unresolved",
                        "source_refs": ["EV-A-1"],
                        "semantic_basis": {
                            "basis": UNAVAILABLE,
                            "rationale": (
                                "No document declares what the authoritative-reference claim "
                                "ranges over; any hierarchy would be invented, so the question "
                                "stays open with basis UNAVAILABLE."
                            ),
                        },
                    },
                    {
                        "claim_id": "AS-A-1",
                        "role": "assumption",
                        "proposition": (
                            "The three documents describe the same platform generation and the "
                            "same blob lifecycle."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "semantic_basis": {
                            "basis": INFERRED,
                            "rationale": (
                                "The documents share vocabulary and refer to one storage service, "
                                "which is inferred rather than stated."
                            ),
                        },
                    },
                    {
                        "claim_id": "BD-A-1",
                        "role": "boundary",
                        "proposition": (
                            "The assessment covers only the three documents in the set, not "
                            "platform-wide documentation."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "semantic_basis": {
                            "basis": INFERRED,
                            "rationale": (
                                "The boundary follows from the fixture scope; the source does not "
                                "state it."
                            ),
                        },
                    },
                    {
                        "claim_id": "R-A-1",
                        "role": "recommendation",
                        "proposition": (
                            "Treat no document in the set as precedence-superior to another "
                            "without an explicit declaration of precedence."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "semantic_basis": {
                            "basis": AUTHOR_JUDGMENT,
                            "rationale": (
                                "The non-promotion rule is introduced by the authoring skill "
                                "under new-authoring authority; no source states it."
                            ),
                        },
                    },
                ],
                "evidence": [
                    {
                        "evidence_id": "EV-A-1",
                        "proposition": (
                            "Document 1 describes the storage service, calls itself the "
                            "authoritative reference for the storage subsystem, and states a "
                            "30-day retention behavior."
                        ),
                        "source": {
                            "source_id": "src-capstone-a-doc1",
                            "source_type": "external_source",
                            "availability": "present",
                            "locator": "capstone_a_multi_doc_set.txt:doc1",
                        },
                        "availability": "present",
                    },
                    {
                        "evidence_id": "EV-A-2",
                        "proposition": (
                            "Document 2 describes the gateway, states that it SHALL NOT bypass "
                            "the storage service's versioning when writing blobs, and names no "
                            "other document as its authority."
                        ),
                        "source": {
                            "source_id": "src-capstone-a-doc2",
                            "source_type": "external_source",
                            "availability": "present",
                            "locator": "capstone_a_multi_doc_set.txt:doc2",
                        },
                        "availability": "present",
                    },
                    {
                        "evidence_id": "EV-A-3",
                        "proposition": (
                            "Document 3 defines the retention schedule without declaring "
                            "precedence over the other documents."
                        ),
                        "source": {
                            "source_id": "src-capstone-a-doc3",
                            "source_type": "external_source",
                            "availability": "present",
                            "locator": "capstone_a_multi_doc_set.txt:doc3",
                        },
                        "availability": "present",
                    },
                ],
                "relations": [
                    {
                        "relation_id": "REL-A-1",
                        "source_id": "EV-A-1",
                        "type": "supports",
                        "target_id": "J-A-1",
                        "material": True,
                    },
                    {
                        "relation_id": "REL-A-2",
                        "source_id": "AS-A-1",
                        "type": "condition_for",
                        "target_id": "J-A-1",
                        "material": True,
                    },
                    {
                        "relation_id": "REL-A-3",
                        "source_id": "BD-A-1",
                        "type": "qualifies",
                        "target_id": "J-A-1",
                        "material": True,
                    },
                    {
                        "relation_id": "REL-A-4",
                        "source_id": "OQ-A-1",
                        "type": "alternative_to",
                        "target_id": "R-A-1",
                        "material": True,
                    },
                ],
                "update_indicators": [
                    {
                        "indicator_id": "UI-A-1",
                        "text": (
                            "Revise the judgment when any document in the set declares a "
                            "precedence relation."
                        ),
                        "target_claim_refs": ["J-A-1"],
                        "effect": "decrease_likelihood",
                    }
                ],
            },
            {
                "section_id": "extracted-requirements",
                "heading": "Locally closed requirements extracted from the set",
                "profiles": ["SPECIFY"],
                "claims": [
                    {
                        "claim_id": "REQ-A-GW-001",
                        "role": "requirement",
                        "proposition": (
                            "The gateway MUST reject writes that bypass the storage service's "
                            "versioning."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "scope": {"system": "gateway service"},
                        "force": {"deontic": "MUST"},
                        "status": "asserted",
                        "source_refs": ["EV-A-2"],
                        "semantic_basis": {
                            "basis": EXPLICIT,
                            "rationale": (
                                "Document 2 states the prohibition with the SHALL NOT surface; the "
                                "authoring skill records it with the canonical MUST surface, and "
                                "the source basis for the same value is EXPLICIT."
                            ),
                        },
                        "extensions": {"source_basis": {"EV-A-2": EXPLICIT}},
                        "requirement": {
                            "requirement_id": "REQ-A-GW-001",
                            "actor": "gateway",
                            "deontic": "MUST",
                            "action": "reject",
                            "object": "writes that bypass the storage service's versioning",
                            "trigger": "a write that bypasses versioning is presented",
                            "scope": "gateway write path",
                            "source_authority": "gateway-service document",
                            "acceptance_criterion_id": "AC-A-GW-001",
                            "acceptance_criterion": (
                                "A bypassing write is refused by the gateway before it reaches "
                                "storage."
                            ),
                            "semantic_basis": {
                                "basis": EXPLICIT,
                                "rationale": (
                                    "The obligation's strength and content come verbatim from "
                                    "document 2."
                                ),
                            },
                        },
                    },
                    {
                        "claim_id": "REQ-A-ST-001",
                        "role": "requirement",
                        "proposition": (
                            "The storage service MUST retain every blob version for at least 30 "
                            "days."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "scope": {"system": "storage service"},
                        "force": {"deontic": "MUST"},
                        "quantifier": {"kind": "minimum", "value": 30, "unit": "days"},
                        "status": "asserted",
                        "source_refs": ["EV-A-1"],
                        "semantic_basis": {
                            "basis": INFERRED,
                            "rationale": (
                                "Document 1 describes retention behavior as a statement of fact, "
                                "not as a normative requirement; the requirement reading is a "
                                "competent reader's inference, never an explicit requirement."
                            ),
                        },
                        "extensions": {"source_basis": {"EV-A-1": INFERRED}},
                        "requirement": {
                            "requirement_id": "REQ-A-ST-001",
                            "actor": "storage service",
                            "deontic": "MUST",
                            "action": "retain",
                            "object": "every blob version",
                            "condition": "for at least 30 days",
                            "scope": "blob lifecycle",
                            "source_authority": "storage-service document",
                            "acceptance_criterion_id": "AC-A-ST-001",
                            "acceptance_criterion": (
                                "Every blob version younger than 30 days is present in the live "
                                "index."
                            ),
                            "semantic_basis": {
                                "basis": INFERRED,
                                "rationale": (
                                    "Same inference as the claim level: the source describes, it "
                                    "does not require."
                                ),
                            },
                        },
                    },
                    {
                        "claim_id": "AC-A-GW-001",
                        "role": "definition",
                        "proposition": (
                            "A write that bypasses the storage service's versioning is refused by "
                            "the gateway."
                        ),
                        "material": False,
                        "polarity": "positive",
                        "status": "asserted",
                    },
                    {
                        "claim_id": "AC-A-ST-001",
                        "role": "definition",
                        "proposition": (
                            "No blob version younger than 30 days is absent from the live index."
                        ),
                        "material": False,
                        "polarity": "positive",
                        "status": "asserted",
                    },
                ],
                "evidence": [],
                "relations": [
                    {
                        "relation_id": "REL-A-5",
                        "source_id": "REQ-A-ST-001",
                        "type": "depends_on",
                        "target_id": "REQ-A-GW-001",
                        "material": True,
                    }
                ],
                "update_indicators": [],
            },
        ],
        "stable_coordinates": [
            {
                "kind": "requirement_id",
                "id": "REQ-A-GW-001",
                "source_pointer": "#/sections/1/claims/0",
            },
            {
                "kind": "requirement_id",
                "id": "REQ-A-ST-001",
                "source_pointer": "#/sections/1/claims/1",
            },
            {
                "kind": "acceptance_criterion_id",
                "id": "AC-A-GW-001",
                "source_pointer": "#/sections/1/claims/0/requirement/acceptance_criterion_id",
            },
            {
                "kind": "acceptance_criterion_id",
                "id": "AC-A-ST-001",
                "source_pointer": "#/sections/1/claims/1/requirement/acceptance_criterion_id",
            },
        ],
        "extraction_status": "complete",
    }

    def test_source_fixture_contains_the_temptation_without_any_precedence(
        self
    ) -> None:
        """§36 fixture gate: the raw prose invites the hierarchy and declares none."""
        text = " ".join(
            (SOURCES / "capstone_a_multi_doc_set.txt").read_text(encoding="utf-8").split()
        )
        assert TEMPTATION_PHRASE in text, "doc 1 must carry the tempting self-description"
        assert "foundation of the platform" in text, "doc 1 must invite the foundation reading"
        for word in PRECEDENCE_VOCABULARY:
            assert word not in text.casefold(), (
                f"the source set must not declare precedence ({word!r} found)"
            )

    def test_ir_declares_inferred_and_unavailable_authority_basis(
        self
    ) -> None:
        """§36: the IR never invents authority; the temptation is an UNAVAILABLE question."""
        assert _basis_of(self.IR, "J-A-1") == INFERRED
        assert _basis_of(self.IR, "OQ-A-1") == UNAVAILABLE
        assert _basis_of(self.IR, "REQ-A-ST-001") == INFERRED
        assert _basis_of(self.IR, "REQ-A-GW-001") == EXPLICIT
        assert _ledger_of(self.IR, "REQ-A-GW-001") == {"EV-A-2": EXPLICIT}
        _assert_coordinate_pointers_resolve(self.IR)
        # Direct data-level check of the silent-promotion condition: no claim
        # declares EXPLICIT over a source recorded INFERRED or UNAVAILABLE.
        assert _explicit_claims_with_promoted_source(self.IR) == []

    def test_lint_is_deterministic_green_without_invented_authority(
        self, ctx_d2, load_policy
    ) -> None:
        """§36: lint_ir under draft.2 — mechanical PASS, no FAIL anywhere."""
        report = lint_ir(
            ctx_d2,
            self.IR,
            load_policy(POLICY_STEM),
            source_path=SOURCES / "capstone_a_multi_doc_set.txt",
        )
        conformance = report["conformance"]
        assert conformance["mechanical"] == "PASS", conformance["mechanical"]
        assert conformance["profile"] == "PASS", conformance["profile"]
        assert conformance["preservation"] == "NOT_APPLICABLE", conformance["preservation"]

        results = {r["rule_id"]: r for r in report["rule_results"]}
        failed = [rid for rid, r in results.items() if r["status"] == "FAIL"]
        assert failed == [], f"no rule may FAIL on integrity: {failed}"

        # Integrity rules decide PASS; COORD and BASIS-002 are blocking.
        _assert_statuses(
            report,
            {
                "ATS-COORD-001": "PASS",
                "ATS-COORD-002": "PASS",
                "ATS-BASIS-002": "PASS",
            },
        )
        # Basis presence is a declared REVIEW_REQUIRED on a clean run, never FAIL.
        _assert_statuses(
            report,
            {
                "ATS-BASIS-001": "REVIEW_REQUIRED",
                "ATS-CLOSE-001": "REVIEW_REQUIRED",
            },
        )
        assert results["ATS-BASIS-002"]["finding_ids"] == [], (
            "BASIS-002 must not flag anything: no EXPLICIT claim sits on an "
            "INFERRED/UNAVAILABLE source"
        )
        assert conformance["semantic_review"] == "UNAVAILABLE", (
            "the build holds no disposition authority; semantic_review is honestly "
            "UNAVAILABLE, not a failure of this artifact"
        )

        # Spec 16.2: identical inputs produce an identical sealed report.
        replay = lint_ir(
            ctx_d2,
            self.IR,
            load_policy(POLICY_STEM),
            source_path=SOURCES / "capstone_a_multi_doc_set.txt",
        )
        assert replay["report_id"] == report["report_id"]
        assert [r["status"] for r in replay["rule_results"]] == [
            r["status"] for r in report["rule_results"]
        ]

    def test_planning_projection_emits_no_precedence(self, ctx_d2, load_policy) -> None:
        """The rendered projection never emits an authority hierarchy without
        a declared basis."""
        projection = project_from_ir(
            ctx_d2,
            self.IR,
            load_policy(POLICY_STEM),
            artifact_sha256=SOURCE_A_SHA,
        )
        assert projection["profile"] == "ASSESS+SPECIFY"
        # The projection copies the declared coordinate block verbatim.
        assert projection["stable_coordinates"] == self.IR["stable_coordinates"]
        # Authority records carry the declared source authorities with no
        # precedence: inventing a hierarchy is exactly the silent promotion
        # ATS-BASIS-002 forbids (contract D-H authority semantics).
        authorities = projection["authority"]
        assert all("precedence" not in entry for entry in authorities), (
            f"no invented precedence: {authorities}"
        )
        assert {entry["authority"] for entry in authorities} == {
            "gateway-service document",
            "storage-service document",
        }
        requirement_ids = {r["requirement_id"] for r in projection["requirements"]}
        assert requirement_ids == {"REQ-A-GW-001", "REQ-A-ST-001"}


class TestCapstoneB:
    """Capstone B: new-architecture authoring under draft.2 authority.

    Fixture: an operator brief (build an edge cache; 50ms cold-start budget;
    invalidate on storage writes; cache-aside vs write-through both on the
    table) plus a repository fact sheet (gateway is FastAPI; storage is
    append-only and versioned; no cache layer exists; measured p95 is 120ms;
    no cache-layer latency measurement exists). The fact sheet's last fact is
    the deliberate evidence gap: the 50ms budget is a product target, not a
    measured capability.

    The hand-authored ASSESS+SPECIFY IR records the authoring truthfully:
    sourced facts carry EXPLICIT basis, new design choices (the cache pattern,
    the invalidation semantics, the scope boundary, the recommendation) carry
    AUTHOR_JUDGMENT, and the unmeasured feasibility question carries
    UNAVAILABLE — never a silent promotion to explicit.
    """

    IR: dict = {
        "schema_version": "ats.text_ir.v1",
        "artifact_id": "capstone-b-new-architecture-authoring",
        "source": {
            "content_sha256": SOURCE_B_SHA,
            "normalized_sha256": SOURCE_B_SHA,
            "media_type": "text/plain",
            "locator": "fixtures/ir/sources/capstone_b_brief_and_facts.txt",
        },
        "policy_snapshot_id": "policy-fixture-draft2",
        "language": "en",
        "audience": {"audience_id": "capstone-b-audience", "expertise": "expert"},
        "basis_policy": {"default_basis": AUTHOR_JUDGMENT, "declared": True},
        "sections": [
            {
                "section_id": "evidence-assessment",
                "heading": "Evidence assessment for the edge-cache decision",
                "profiles": ["ASSESS"],
                "claims": [
                    {
                        "claim_id": "J-B-1",
                        "role": "judgment",
                        "proposition": (
                            "The current gateway serves reads at 120ms p95 in staging with no "
                            "cache layer in the codebase."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "scope": {"system": "gateway read path", "condition": "in staging"},
                        "force": {
                            "assessment_confidence": {
                                "level": "moderate",
                                "basis": {
                                    "basis_type": "direct_observation",
                                    "evidence_quality": "strong",
                                    "evidence_coverage": "partial",
                                    "source_independence": "single",
                                    "directness": "direct",
                                    "consistency": "convergent",
                                    "assumption_sensitivity": "moderate",
                                    "environmental_stability": "stable",
                                    "contrary_evidence": "none_found",
                                    "rationale": (
                                        "The measured latency and the absence of a cache layer are "
                                        "stated by the fact sheet; no likelihood applies because "
                                        "the claim reports measured state, not an uncertain event."
                                    ),
                                },
                            }
                        },
                        "quantifier": {"kind": "exact_count", "value": 120, "unit": "ms"},
                        "source_refs": ["EV-B-FACTS", "EV-B-LATENCY"],
                        "assumption_refs": ["AS-B-1"],
                        "boundary_refs": ["BD-B-1"],
                        "status": "asserted",
                        "semantic_basis": {
                            "basis": EXPLICIT,
                            "rationale": (
                                "Both facts are stated by the repository fact sheet; the "
                                "assessment adds no new semantics."
                            ),
                        },
                        "extensions": {
                            "source_basis": {
                                "EV-B-FACTS": EXPLICIT,
                                "EV-B-LATENCY": EXPLICIT,
                            }
                        },
                    },
                    {
                        "claim_id": "OQ-B-1",
                        "role": "open_question",
                        "proposition": (
                            "Whether the edge cache can meet the cold-start latency budget is "
                            "unestablished: no cache-layer latency measurement exists in the "
                            "repository."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "unresolved",
                        "source_refs": ["EV-B-NOMEASURE"],
                        "semantic_basis": {
                            "basis": UNAVAILABLE,
                            "rationale": (
                                "The fact sheet records the absence of a measurement; whether the "
                                "budget is achievable is not established by any available source."
                            ),
                        },
                    },
                    {
                        "claim_id": "AS-B-1",
                        "role": "assumption",
                        "proposition": (
                            "The staging measurement is representative of tenant cold-start "
                            "conditions."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "source_refs": ["EV-B-LATENCY"],
                        "semantic_basis": {
                            "basis": INFERRED,
                            "rationale": (
                                "The fact sheet does not claim representativeness; the assumption "
                                "bridges a gap and is marked as such."
                            ),
                        },
                    },
                    {
                        "claim_id": "BD-B-1",
                        "role": "boundary",
                        "proposition": (
                            "The assessment covers the gateway read path; storage internals and "
                            "the write path are out of scope."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "semantic_basis": {
                            "basis": AUTHOR_JUDGMENT,
                            "rationale": (
                                "The scope boundary is chosen by the authoring process; no source "
                                "declares it."
                            ),
                        },
                    },
                    {
                        "claim_id": "R-B-1",
                        "role": "recommendation",
                        "proposition": (
                            "Validate the cold-start latency with a measured ablation before "
                            "promoting the edge cache."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "semantic_basis": {
                            "basis": AUTHOR_JUDGMENT,
                            "rationale": (
                                "The recommendation is introduced by the authoring process under "
                                "new-authoring authority."
                            ),
                        },
                    },
                ],
                "evidence": [
                    {
                        "evidence_id": "EV-B-FACTS",
                        "proposition": (
                            "The gateway is a FastAPI service; storage exposes an append-only, "
                            "content-addressed, versioned blob store; no cache layer exists in "
                            "the codebase."
                        ),
                        "source": {
                            "source_id": "src-capstone-b-fact-sheet",
                            "source_type": "repository_artifact",
                            "availability": "present",
                            "locator": "capstone_b_brief_and_facts.txt:doc2",
                        },
                        "availability": "present",
                    },
                    {
                        "evidence_id": "EV-B-LATENCY",
                        "proposition": (
                            "The team measured gateway p95 latency at 120ms in staging."
                        ),
                        "source": {
                            "source_id": "src-capstone-b-fact-sheet",
                            "source_type": "repository_artifact",
                            "availability": "present",
                            "locator": "capstone_b_brief_and_facts.txt:doc2",
                        },
                        "availability": "present",
                    },
                    {
                        "evidence_id": "EV-B-BRIEF",
                        "proposition": (
                            "The operator brief requires cache invalidation to trigger when "
                            "blobs are written to storage."
                        ),
                        "source": {
                            "source_id": "src-capstone-b-operator-brief",
                            "source_type": "human_report",
                            "availability": "present",
                            "locator": "capstone_b_brief_and_facts.txt:doc1",
                        },
                        "availability": "present",
                    },
                    {
                        "evidence_id": "EV-B-BUDGET",
                        "proposition": (
                            "The operator brief sets a 50ms cold-start latency budget for the "
                            "edge cache."
                        ),
                        "source": {
                            "source_id": "src-capstone-b-operator-brief",
                            "source_type": "human_report",
                            "availability": "present",
                            "locator": "capstone_b_brief_and_facts.txt:doc1",
                        },
                        "availability": "present",
                    },
                    {
                        "evidence_id": "EV-B-NOMEASURE",
                        "proposition": (
                            "The fact sheet records no cache-layer cold-start latency "
                            "measurement."
                        ),
                        "source": {
                            "source_id": "src-capstone-b-fact-sheet",
                            "source_type": "repository_artifact",
                            "availability": "present",
                            "locator": "capstone_b_brief_and_facts.txt:doc2",
                        },
                        "availability": "present",
                    },
                ],
                "relations": [
                    {
                        "relation_id": "REL-B-1",
                        "source_id": "EV-B-FACTS",
                        "type": "supports",
                        "target_id": "J-B-1",
                        "material": True,
                    },
                    {
                        "relation_id": "REL-B-2",
                        "source_id": "EV-B-LATENCY",
                        "type": "supports",
                        "target_id": "J-B-1",
                        "material": True,
                    },
                    {
                        "relation_id": "REL-B-3",
                        "source_id": "AS-B-1",
                        "type": "condition_for",
                        "target_id": "J-B-1",
                        "material": True,
                    },
                    {
                        "relation_id": "REL-B-4",
                        "source_id": "BD-B-1",
                        "type": "qualifies",
                        "target_id": "J-B-1",
                        "material": True,
                    },
                    {
                        "relation_id": "REL-B-5",
                        "source_id": "OQ-B-1",
                        "type": "alternative_to",
                        "target_id": "R-B-1",
                        "material": True,
                    },
                ],
                "update_indicators": [
                    {
                        "indicator_id": "UI-B-1",
                        "text": (
                            "Downgrade the assessment when a cache-layer cold-start latency "
                            "measurement lands."
                        ),
                        "target_claim_refs": ["J-B-1"],
                        "effect": "decrease_likelihood",
                    }
                ],
            },
            {
                "section_id": "edge-cache-specification",
                "heading": "Edge-cache architecture specification",
                "profiles": ["SPECIFY"],
                "claims": [
{
                        "claim_id": "REQ-B-CACHE-001",
                        "role": "requirement",
                        "proposition": (
                            "The edge cache MUST invalidate a cached blob synchronously when a "
                            "blob write reaches storage."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "scope": {"system": "edge cache"},
                        "force": {"deontic": "MUST"},
                        "status": "asserted",
                        "source_refs": ["EV-B-BRIEF"],
                        "semantic_basis": {
                            "basis": EXPLICIT,
                            "rationale": (
                                "The invalidation trigger is stated by the operator brief; only "
                                "the synchronous reading is the author's gloss."
                            ),
                        },
                        "extensions": {"source_basis": {"EV-B-BRIEF": EXPLICIT}},
                        "requirement": {
                            "requirement_id": "REQ-B-CACHE-001",
                            "actor": "edge cache",
                            "deontic": "MUST",
                            "action": "invalidate",
                            "object": "a cached blob",
                            "trigger": "a blob write reaches storage",
                            "source_authority": "operator brief",
                            "acceptance_criterion_id": "AC-B-CACHE-001",
                            "acceptance_criterion": (
                                "A storage write invalidates the corresponding cache entry "
                                "before the write is acknowledged."
                            ),
                            "semantic_basis": {
                                "basis": EXPLICIT,
                                "rationale": "The trigger comes verbatim from the operator brief.",
                            },
                        },
                    },
{
                        "claim_id": "REQ-B-CACHE-002",
                        "role": "requirement",
                        "proposition": (
                            "The edge cache MUST serve tenant cold-start reads within the 50ms "
                            "budget."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "scope": {"system": "edge cache"},
                        "force": {"deontic": "MUST"},
                        "quantifier": {"kind": "maximum", "value": 50, "unit": "ms"},
                        "status": "asserted",
                        "source_refs": ["EV-B-BUDGET"],
                        "semantic_basis": {
                            "basis": EXPLICIT,
                            "rationale": (
                                "The budget figure is stated by the operator brief; the fact "
                                "sheet's note that it is unmeasured is recorded separately as "
                                "UNAVAILABLE, not folded into this EXPLICIT value."
                            ),
                        },
                        "extensions": {"source_basis": {"EV-B-BUDGET": EXPLICIT}},
                        "requirement": {
                            "requirement_id": "REQ-B-CACHE-002",
                            "actor": "edge cache",
                            "deontic": "MUST",
                            "action": "serve",
                            "object": "tenant cold-start reads",
                            "condition": "within at most 50ms",
                            "constraints": ["at most 50ms per cold-start read"],
                            "source_authority": "operator brief",
                            "acceptance_criterion_id": "AC-B-CACHE-002",
                            "acceptance_criterion": (
                                "A cold-start read served by the cache completes within the "
                                "budget."
                            ),
                            "semantic_basis": {
                                "basis": EXPLICIT,
                                "rationale": "The budget target comes from the operator brief.",
                            },
                        },
                    },
{
                        "claim_id": "REQ-B-CACHE-003",
                        "role": "requirement",
                        "proposition": (
                            "The edge cache MUST refuse to serve a blob version the storage "
                            "service has marked for deletion."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "scope": {"system": "edge cache"},
                        "force": {"deontic": "MUST"},
                        "status": "asserted",
                        "semantic_basis": {
                            "basis": AUTHOR_JUDGMENT,
                            "rationale": (
                                "The deletion-visibility constraint is a design choice introduced "
                                "by the authoring process under the operator's intent; no source "
                                "states it."
                            ),
                        },
                        "requirement": {
                            "requirement_id": "REQ-B-CACHE-003",
                            "actor": "edge cache",
                            "deontic": "MUST",
                            "action": "refuse to serve",
                            "object": "a blob version marked for deletion",
                            "source_authority": "edge-cache design authority",
                            "acceptance_criterion_id": "AC-B-CACHE-003",
                            "acceptance_criterion": (
                                "No deleted blob version is served by the cache once the "
                                "deletion marker is visible."
                            ),
                            "semantic_basis": {
                                "basis": AUTHOR_JUDGMENT,
                                "rationale": (
                                    "New design choice; the authoring authority introduced it."
                                ),
                            },
                        },
                    },
{
                        "claim_id": "AL-B-1",
                        "role": "recommendation",
                        "proposition": (
                            "A time-to-live refresh cache would meet the budget with simpler "
                            "invalidation but risks serving stale blobs."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "semantic_basis": {
                            "basis": AUTHOR_JUDGMENT,
                            "rationale": (
                                "The alternative is a design candidate introduced by the "
                                "authoring process."
                            ),
                        },
                    },
{
                        "claim_id": "AL-B-2",
                        "role": "recommendation",
                        "proposition": (
                            "A write-through cache with no read-side population would meet the "
                            "budget only for repeated reads."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "semantic_basis": {
                            "basis": AUTHOR_JUDGMENT,
                            "rationale": (
                                "The alternative is a design candidate introduced by the "
                                "authoring process."
                            ),
                        },
                    },
{
                        "claim_id": "DEC-B-1",
                        "role": "recommendation",
                        "proposition": (
                            "Adopt cache-aside with synchronous write-through invalidation for "
                            "the edge cache."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "decision_id": "DEC-B-1",
                        "semantic_basis": {
                            "basis": AUTHOR_JUDGMENT,
                            "rationale": (
                                "The adopted design is a new judgment under the authority "
                                "granted for new authoring; it is not extracted from any source."
                            ),
                        },
                    },
{
                        "claim_id": "DEC-B-2",
                        "role": "recommendation",
                        "proposition": (
                            "Defer promotion of the edge cache until a cache-layer cold-start "
                            "latency measurement exists."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "decision_id": "DEC-B-2",
                        "source_refs": ["EV-B-NOMEASURE"],
                        "semantic_basis": {
                            "basis": UNAVAILABLE,
                            "rationale": (
                                "The decision's evidence basis is unavailable: the repository "
                                "records no cache-layer latency data, so the deferral is grounded "
                                "in absence, not in a measured number."
                            ),
                        },
                    },
{
                        "claim_id": "AC-B-CACHE-001",
                        "role": "definition",
                        "proposition": (
                            "A storage write invalidates the corresponding cache entry before "
                            "the write is acknowledged."
                        ),
                        "material": False,
                        "polarity": "positive",
                        "status": "asserted",
                    },
{
                        "claim_id": "AC-B-CACHE-002",
                        "role": "definition",
                        "proposition": (
                            "A cold-start read served by the cache completes within the budget."
                        ),
                        "material": False,
                        "polarity": "positive",
                        "status": "asserted",
                    },
{
                        "claim_id": "AC-B-CACHE-003",
                        "role": "definition",
                        "proposition": (
                            "No deleted blob version is served by the cache once the deletion "
                            "marker is visible."
                        ),
                        "material": False,
                        "polarity": "positive",
                        "status": "asserted",
                    }

                ],
                "evidence": [],
                "relations": [
                    {
                        "relation_id": "REL-B-6",
                        "source_id": "AL-B-1",
                        "type": "alternative_to",
                        "target_id": "DEC-B-1",
                        "material": True,
                    },
                    {
                        "relation_id": "REL-B-7",
                        "source_id": "AL-B-2",
                        "type": "alternative_to",
                        "target_id": "DEC-B-1",
                        "material": True,
                    },
                    {
                        "relation_id": "REL-B-8",
                        "source_id": "REQ-B-CACHE-003",
                        "type": "depends_on",
                        "target_id": "REQ-B-CACHE-001",
                        "material": True,
                    },
                ],
                "update_indicators": [
                    {
                        "indicator_id": "UI-B-2",
                        "text": (
                            "Increase the likelihood of promoting the edge cache when a "
                            "cache-layer cold-start latency measurement lands."
                        ),
                        "target_claim_refs": ["DEC-B-2"],
                        "effect": "increase_likelihood",
                    }
                ],
            },
        ],
        "stable_coordinates": [
            {
                "kind": "decision_id",
                "id": "DEC-B-1",
                "source_pointer": "#/sections/1/claims/5",
            },
            {
                "kind": "decision_id",
                "id": "DEC-B-2",
                "source_pointer": "#/sections/1/claims/6",
            },
            {
                "kind": "requirement_id",
                "id": "REQ-B-CACHE-001",
                "source_pointer": "#/sections/1/claims/0",
            },
            {
                "kind": "requirement_id",
                "id": "REQ-B-CACHE-002",
                "source_pointer": "#/sections/1/claims/1",
            },
            {
                "kind": "requirement_id",
                "id": "REQ-B-CACHE-003",
                "source_pointer": "#/sections/1/claims/2",
            },
            {
                "kind": "acceptance_criterion_id",
                "id": "AC-B-CACHE-001",
                "source_pointer": "#/sections/1/claims/0/requirement/acceptance_criterion_id",
            },
            {
                "kind": "acceptance_criterion_id",
                "id": "AC-B-CACHE-002",
                "source_pointer": "#/sections/1/claims/1/requirement/acceptance_criterion_id",
            },
            {
                "kind": "acceptance_criterion_id",
                "id": "AC-B-CACHE-003",
                "source_pointer": "#/sections/1/claims/2/requirement/acceptance_criterion_id",
            },
        ],
        "extraction_status": "complete",
    }

    def test_ir_carries_author_judgment_explicit_and_unavailable_bases(
        self
    ) -> None:
        """§36: new choices are AUTHOR_JUDGMENT, sourced facts EXPLICIT, gaps UNAVAILABLE."""
        assert _basis_of(self.IR, "DEC-B-1") == AUTHOR_JUDGMENT
        assert _basis_of(self.IR, "REQ-B-CACHE-003") == AUTHOR_JUDGMENT
        assert _basis_of(self.IR, "BD-B-1") == AUTHOR_JUDGMENT
        assert _basis_of(self.IR, "J-B-1") == EXPLICIT
        assert _basis_of(self.IR, "REQ-B-CACHE-001") == EXPLICIT
        assert _basis_of(self.IR, "REQ-B-CACHE-002") == EXPLICIT
        assert _basis_of(self.IR, "DEC-B-2") == UNAVAILABLE
        assert _basis_of(self.IR, "OQ-B-1") == UNAVAILABLE
        # No AUTHOR_JUDGMENT claim may be misread as a source promotion, and no
        # EXPLICIT claim may sit on an INFERRED/UNAVAILABLE source.
        assert _explicit_claims_with_promoted_source(self.IR) == []
        _assert_coordinate_pointers_resolve(self.IR)
        # The document declares the protected coordinate kinds (D-C).
        declared = {entry["kind"] for entry in self.IR["stable_coordinates"]}
        assert declared == {"decision_id", "requirement_id", "acceptance_criterion_id"}
        assert len(self.IR["stable_coordinates"]) == len(
            {entry["id"] for entry in self.IR["stable_coordinates"]}
        ), "no duplicate coordinates"

    def test_lint_is_green_on_integrity_and_basis_002_passes(
        self, ctx_d2, load_policy
    ) -> None:
        """§36: draft.2 lint — no FAIL on integrity; AUTHOR_JUDGMENT is not a promotion."""
        report = lint_ir(
            ctx_d2,
            self.IR,
            load_policy(POLICY_STEM),
            source_path=SOURCES / "capstone_b_brief_and_facts.txt",
        )
        conformance = report["conformance"]
        assert conformance["mechanical"] == "PASS", conformance["mechanical"]
        assert conformance["profile"] == "PASS", conformance["profile"]
        assert conformance["preservation"] == "NOT_APPLICABLE", conformance["preservation"]

        results = {r["rule_id"]: r for r in report["rule_results"]}
        failed = [rid for rid, r in results.items() if r["status"] == "FAIL"]
        assert failed == [], f"no rule may FAIL on integrity: {failed}"

        _assert_statuses(
            report,
            {
                "ATS-COORD-001": "PASS",
                "ATS-COORD-002": "PASS",
                "ATS-BASIS-002": "PASS",
                "ATS-BASIS-001": "REVIEW_REQUIRED",
                "ATS-CLOSE-001": "REVIEW_REQUIRED",
            },
        )
        # The AUTHOR_JUDGMENT decisions and requirements are present in the
        # evaluated document and generate no BASIS-002 finding: a new judgment
        # under authoring authority is not a silent promotion of source material.
        assert results["ATS-BASIS-002"]["finding_ids"] == []
        basis002 = results["ATS-BASIS-002"]
        assert basis002["status"] == "PASS", basis002.get("reason", "")
        assert conformance["semantic_review"] == "UNAVAILABLE", (
            "semantic_review is honestly UNAVAILABLE in this build, never claimed"
        )

        # Spec 16.2: identical inputs produce an identical sealed report.
        replay = lint_ir(
            ctx_d2,
            self.IR,
            load_policy(POLICY_STEM),
            source_path=SOURCES / "capstone_b_brief_and_facts.txt",
        )
        assert replay["report_id"] == report["report_id"]
        assert [r["status"] for r in replay["rule_results"]] == [
            r["status"] for r in report["rule_results"]
        ]

    def test_planning_projection_preserves_coordinate_ids(self, ctx_d2, load_policy) -> None:
        """§36 + D-H: decisions, requirements, and ACs keep their ids in the projection."""
        projection = project_from_ir(
            ctx_d2,
            self.IR,
            load_policy(POLICY_STEM),
            artifact_sha256=SOURCE_B_SHA,
        )
        assert projection["profile"] == "ASSESS+SPECIFY"
        assert projection["stable_coordinates"] == self.IR["stable_coordinates"]

        decision_ids = {d["decision_id"] for d in projection["decisions"]}
        assert decision_ids == {"DEC-B-1", "DEC-B-2"}
        assert {d["proposition"] for d in projection["decisions"]} == {
            self.IR["sections"][1]["claims"][5]["proposition"],
            self.IR["sections"][1]["claims"][6]["proposition"],
        }

        requirement_ids = {r["requirement_id"] for r in projection["requirements"]}
        assert requirement_ids == {"REQ-B-CACHE-001", "REQ-B-CACHE-002", "REQ-B-CACHE-003"}
        for entry in projection["requirements"]:
            assert entry["source_pointer"], "every projected requirement keeps its IR pointer"

        ac_ids = {a["acceptance_criterion_id"] for a in projection["acceptance_criteria"]}
        assert ac_ids == {"AC-B-CACHE-001", "AC-B-CACHE-002", "AC-B-CACHE-003"}
        # AC back-references: each criterion names the requirement that cites it.
        ac_by_id = {a["acceptance_criterion_id"]: a for a in projection["acceptance_criteria"]}
        assert ac_by_id["AC-B-CACHE-001"]["requirement_ids"] == ["REQ-B-CACHE-001"]

        # The deferral decision's update indicator projects with its kind.
        indicators = projection["update_indicators"]
        assert {i["indicator_id"] for i in indicators} == {"UI-B-1", "UI-B-2"}
        # No authority precedence is ever emitted (D-H authority semantics).
        assert all("precedence" not in a for a in projection["authority"])

"""Public skill pack contract tests (master design contract §41-44).

Two layers, matching §9's test mechanics:

- Text-level contract checks over the four public SKILL.md files
  (``skills/public/{ats,ats-spec,ats-assess,ats-review}/SKILL.md``):
  frontmatter, mini-constitution key phrases (§2), version-behavior language
  (§4), the routing surface, and each skill's required behavior language.
- Behavior checks that drive the real machinery — ``ats ir lint`` through
  ``ats.cli._context`` (the two-default law), the 36-rule draft.2 detector
  registry, and the planning projection — asserting the version-resolution
  law (§41.1/7/8), human-grounding minimization (§41.9/10), the
  stable-coordinate round trip (§42.1/10), the no-silent-strengthening gate
  (§42.12), and the review positive controls (§30, §44).

All tests are deterministic and network-free: they read checked-in fixtures
and the fixed evaluation clock from ``conftest``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from conftest import REPO_ROOT
from ats.errors import SchemaValidationError
from ats.planning import project_from_ir
from ats.rules.results import Status
from test_cli_spec_defaults import _args, _lint  # reuse the two-default helpers

SKILL_NAMES = ("ats", "ats-spec", "ats-assess", "ats-review")

UNDISTRIBUTED_HELPER_NAMES = (
    "ats-ir-author",
    "ats-specify-output",
    "ats-assess-output",
)

DRAFT2_POLICY = "draft2"

#: The content hash of the synthetic source artifact the projection binds.
SHA = "9" * 64

#: The five mini-constitution key phrases every public skill must carry (§2).
MINI_CONSTITUTION_PHRASES = (
    "Do not invent authority",
    "Unknown is a valid state",
    "Preserve meaning before improving surface form",
    "Stable semantic coordinates survive transformation",
    "Ask only when unresolved meaning blocks the requested action",
)

#: PASS-by-absence phrasing is prohibited everywhere (§40).
PASS_BY_ABSENCE_PHRASES = (
    "passes by default",
    "conforms unless",
    "pass when nothing",
    "conforming by default",
)


def _skill_path(name: str) -> Path:
    return REPO_ROOT / "skills" / "public" / name / "SKILL.md"


def _read_skill(name: str) -> str:
    return _skill_path(name).read_text(encoding="utf-8")


def _flatten(text: str) -> str:
    """Collapse every whitespace run (including hard line wraps) to one space.

    The skills wrap prose at ~80 columns, so a phrase may straddle a line
    break; containment checks run over the flattened text.
    """
    return " ".join(text.split())


def _frontmatter(text: str) -> dict[str, Any]:
    """Parse the YAML frontmatter block (between the two leading ``---`` lines)."""
    assert text.startswith("---\n"), "missing opening frontmatter delimiter"
    end = text.index("\n---", 4)
    payload = yaml.safe_load(text[4:end])
    assert isinstance(payload, dict), "frontmatter is not a mapping"
    return payload


@pytest.fixture(scope="module")
def skill_texts() -> dict[str, str]:
    """The four public SKILL.md bodies, read once (raw, unflattened)."""
    return {name: _read_skill(name) for name in SKILL_NAMES}


# ---------------------------------------------------------------------------
# §12 + §40: text-level contract shared by all four skills
# ---------------------------------------------------------------------------


class TestSkillTextCommon:
    """Shared text-level contract over the four public SKILL.md files."""

    def test_all_four_required_skills_exist(self) -> None:
        for name in SKILL_NAMES:
            assert _skill_path(name).is_file(), f"missing public skill {name}/SKILL.md"

    def test_frontmatter_is_valid_yaml_with_name_and_description(
        self, skill_texts: dict[str, str]
    ) -> None:
        for name, text in skill_texts.items():
            fm = _frontmatter(text)
            assert fm.get("name") == name, f"{name}: frontmatter name mismatch"
            description = fm.get("description")
            assert isinstance(description, str) and description.strip(), (
                f"{name}: frontmatter description missing or empty"
            )

    def test_mini_constitution_key_phrases_present(
        self, skill_texts: dict[str, str]
    ) -> None:
        for name, text in skill_texts.items():
            flat = _flatten(text)
            for phrase in MINI_CONSTITUTION_PHRASES:
                assert phrase in flat, f"{name}: missing mini-constitution phrase {phrase!r}"

    def test_no_private_developer_paths(self, skill_texts: dict[str, str]) -> None:
        patterns = (r"/Users/", r"/tmp/", re.escape(str(REPO_ROOT)))
        for name, text in skill_texts.items():
            flat = _flatten(text)
            for pattern in patterns:
                assert not re.search(pattern, flat), (
                    f"{name}: private developer path pattern {pattern!r} leaked"
                )

    def test_public_skills_are_self_contained(self, skill_texts: dict[str, str]) -> None:
        """Public bodies cannot call repository-only compiler skills."""
        for name, text in skill_texts.items():
            flat = _flatten(text)
            for helper in UNDISTRIBUTED_HELPER_NAMES:
                assert helper not in flat, f"{name}: unavailable helper dependency {helper!r}"
            assert "self-contained" in flat, f"{name}: missing standalone contract"

    def test_no_pass_by_absence_phrasing(self, skill_texts: dict[str, str]) -> None:
        for name, text in skill_texts.items():
            flat = _flatten(text).lower()
            for phrase in PASS_BY_ABSENCE_PHRASES:
                assert phrase not in flat, f"{name}: PASS-by-absence phrase {phrase!r}"

    def test_version_behavior_new_authoring_resolves_draft2(
        self, skill_texts: dict[str, str]
    ) -> None:
        """§4: every skill states the two-default law's new-authoring half."""
        pattern = re.compile(r"[Nn]ew (?:durable )?authoring.{0,120}1\.0\.0-draft\.2")
        for name in SKILL_NAMES:
            assert pattern.search(_flatten(skill_texts[name])), (
                f"{name}: missing new-authoring-resolves-draft.2 language"
            )

    def test_version_behavior_legacy_draft1_preserved(
        self, skill_texts: dict[str, str]
    ) -> None:
        """§4: legacy/historical material stays draft.1 unless migration is explicit."""
        pattern = re.compile(r"[Ll]egacy.{0,240}1\.0\.0-draft\.1")
        for name in SKILL_NAMES:
            assert pattern.search(_flatten(skill_texts[name])), (
                f"{name}: missing legacy-preservation language"
            )

    def test_no_instruction_to_author_new_material_in_draft1(
        self, skill_texts: dict[str, str]
    ) -> None:
        """§4: nothing tells new authoring to use draft.1.

        A mention of both "new authoring" and draft.1 is only legitimate as
        part of the two-default contrast (draft.2 beside it).
        """
        for name, text in skill_texts.items():
            for line in _flatten(text).split(". "):
                if re.search(r"[Nn]ew (?:durable )?authoring", line) and "draft.1" in line:
                    assert "draft.2" in line, (
                        f"{name}: sentence instructs new authoring in draft.1: {line!r}"
                    )

    def test_draft2_downgrade_is_a_refusal_never_a_silent_downgrade(
        self, skill_texts: dict[str, str]
    ) -> None:
        """§4: a draft.2 artifact under a draft.1 policy is a refusal."""
        for name in ("ats", "ats-spec", "ats-assess"):
            assert "silent downgrade" in _flatten(skill_texts[name]), (
                f"{name}: missing no-silent-downgrade language"
            )


# ---------------------------------------------------------------------------
# §41: the ats front door (routing surface)
# ---------------------------------------------------------------------------


class TestAtsSkillText:
    """§41: the front door routes to the sibling skills by name and declines."""

    def test_routes_to_all_three_sibling_skills(self, skill_texts: dict[str, str]) -> None:
        flat = _flatten(skill_texts["ats"])
        for sibling in ("ats-spec", "ats-assess", "ats-review"):
            assert sibling in flat, f"ats front door does not route to {sibling}"

    def test_routing_table_covers_modes_and_profiles(self, skill_texts: dict[str, str]) -> None:
        """§41.2-41.6: SPECIFY, ASSESS, composition, review, and decline rows."""
        flat = _flatten(skill_texts["ats"])
        assert "Determine the mode" in flat
        assert "New authoring" in flat and "Transformation" in flat and "Review" in flat
        # §41.2 new impl spec -> SPECIFY (ats-spec); §41.3 diagnostic -> ASSESS.
        assert "| review | any existing technical prose" in flat
        assert "`ats-spec` (SPECIFY half) + `ats-assess` (ASSESS half)" in flat
        # The worked routing examples carry the same five outcomes.
        assert "ASSESS + SPECIFY composition · ats-spec + ats-assess" in flat
        assert "transformation · SPECIFY · ats-spec" in flat
        assert "transformation · ASSESS · ats-assess" in flat
        assert "review mode · ats-review" in flat
        assert "new authoring · ASSESS · ats-assess" in flat

    def test_declines_casual_prose(self, skill_texts: dict[str, str]) -> None:
        """§41.6: scratch/casual prose does not force ATS."""
        flat = _flatten(skill_texts["ats"])
        assert "casual prose" in flat
        assert "Decline politely" in flat
        assert "Never force ATS onto casual prose" in flat


# ---------------------------------------------------------------------------
# §42: ats-spec (governing objective, task identity, REQ/AC overlap)
# ---------------------------------------------------------------------------


class TestAtsSpecSkillText:
    """§42: the ats-spec required language."""

    def test_governing_objective_verbatim(self, skill_texts: dict[str, str]) -> None:
        """§7.2: the governing objective appears verbatim."""
        objective = (
            "Produce a document from which implementation work can be decomposed "
            "without reconstructing undeclared semantic state"
        )
        assert objective in _flatten(skill_texts["ats-spec"])

    def test_one_requirement_does_not_imply_one_task(
        self, skill_texts: dict[str, str]
    ) -> None:
        """§7.4 / §42.10: semantic identity is never collapsed into task identity."""
        flat = _flatten(skill_texts["ats-spec"])
        assert "One ATS requirement does not imply one implementation task" in flat
        assert "Task identity is derived later by planning projection" in flat
        assert "Never collapse semantic identity into task identity" in flat

    def test_requirement_acceptance_overlap_is_not_a_defect(
        self, skill_texts: dict[str, str]
    ) -> None:
        """§7.5 / §42.9: requirement/AC repetition is intentional redundancy."""
        flat = _flatten(skill_texts["ats-spec"])
        assert "Requirement and acceptance criteria may restate the same invariant" in flat
        assert "This is not a defect" in flat
        assert 'Do not "fix" the overlap by deleting either side' in flat
        assert "Never treat requirement/AC overlap as a defect" in flat

    def test_transformation_never_strengthens(self, skill_texts: dict[str, str]) -> None:
        """§42.12: transformation must not silently strengthen source authority."""
        flat = _flatten(skill_texts["ats-spec"])
        assert "transformation never strengthens" in flat
        assert "Never silently strengthen" in flat


# ---------------------------------------------------------------------------
# §43: ats-assess (force separation, unknown state, discourse roles)
# ---------------------------------------------------------------------------


class TestAtsAssessSkillText:
    """§43: the ats-assess required language."""

    def test_four_force_collapse_prohibitions(self, skill_texts: dict[str, str]) -> None:
        """§8.3: likelihood/confidence, supports/establishes, correlated/caused,
        recommended/required are four explicit prohibitions."""
        flat = _flatten(skill_texts["ats-assess"])
        assert "MUST NOT collapse likelihood into confidence" in flat
        assert "MUST NOT collapse supports into establishes" in flat
        assert "MUST NOT collapse correlated with into caused by" in flat
        assert "MUST NOT collapse recommended into required" in flat

    def test_unknown_state_is_valid_output(self, skill_texts: dict[str, str]) -> None:
        """§8.4: UNAVAILABLE/insufficient/unresolved is valid; never decisive to feel complete."""
        flat = _flatten(skill_texts["ats-assess"])
        assert "UNAVAILABLE / insufficient / unresolved" in flat
        assert "Never make the assessment more decisive to feel complete" in flat
        assert "insufficient-evidence conclusion is complete" in flat

    def test_discourse_roles_are_not_collapsed(self, skill_texts: dict[str, str]) -> None:
        """§8.2: observation/inference/judgment/recommendation stay separate."""
        flat = _flatten(skill_texts["ats-assess"])
        assert "inference written as an observation" in flat
        assert "Never merge two roles to make the document read better" in flat
        assert "Never convert an observation into a causal claim" in flat
        assert "Never collapse likelihood into confidence" in flat
        assert "Never turn a recommendation into a requirement" in flat


# ---------------------------------------------------------------------------
# §44: ats-review (review-first, classes, no quality score)
# ---------------------------------------------------------------------------


class TestAtsReviewSkillText:
    """§44: the ats-review required language."""

    def test_review_before_rewrite(self, skill_texts: dict[str, str]) -> None:
        """§9.2: the default operation is review; transformation only on request."""
        flat = _flatten(skill_texts["ats-review"])
        assert "review first" in flat
        assert "transform only on request" in flat
        assert "Produce findings before any edit" in flat

    def test_must_not_silently_rewrite(self, skill_texts: dict[str, str]) -> None:
        """§9.3: review must never silently become transformation."""
        flat = _flatten(skill_texts["ats-review"])
        assert "MUST NOT silently turn a review into a transformation" in flat
        assert "No rewriting during the review pass" in flat
        assert "Never rewrite by default" in flat

    def test_three_presentation_classes(self, skill_texts: dict[str, str]) -> None:
        """§29: BLOCK / REVIEW_REQUIRED / ADVISORY, with their meanings."""
        flat = _flatten(skill_texts["ats-review"])
        assert re.search(r"BLOCK\b.{0,80}deterministic conformance failure", flat)
        assert re.search(r"REVIEW_REQUIRED.{0,80}material semantic concern", flat)
        assert re.search(r"ADVISORY.{0,80}style or presentation suggestion", flat)

    def test_no_quality_score(self, skill_texts: dict[str, str]) -> None:
        """§29: a quality score is never invented — only negated mentions."""
        flat = _flatten(skill_texts["ats-review"])
        assert "quality score" in flat
        assert re.search(r"do not return.{0,80}quality score", flat)
        assert re.search(r"[Nn]ever.{0,80}quality score", flat)

    def test_ordinary_prose_never_fails_without_applicability(
        self, skill_texts: dict[str, str]
    ) -> None:
        """§9.2: "nonconforming"/BLOCK require requested or policy-applicable ATS."""
        flat = _flatten(skill_texts["ats-review"])
        assert 'BLOCK and the word "nonconforming" apply only when' in flat
        assert "Never classify ordinary prose as ATS-failing without applicability" in flat


# ---------------------------------------------------------------------------
# §41 behavior: version resolution + human-grounding minimization
# ---------------------------------------------------------------------------


def _requirement_claim(
    claim_id: str,
    *,
    proposition: str,
    actor: str,
    deontic: str,
    action: str,
    object_: str,
    authority: str = "acceptance kernel",
    **extra: Any,
) -> dict[str, Any]:
    """One locally closed requirement claim; ``extra`` merges over it."""
    claim: dict[str, Any] = {
        "claim_id": claim_id,
        "role": "requirement",
        "proposition": proposition,
        "material": True,
        "polarity": "positive",
        "status": "asserted",
        "requirement": {
            "requirement_id": claim_id,
            "actor": actor,
            "deontic": deontic,
            "action": action,
            "object": object_,
            "source_authority": authority,
        },
    }
    claim.update(extra)
    return claim


def _ir(artifact_id: str, section: dict[str, Any]) -> dict[str, Any]:
    """A minimal schema-valid draft.2 TextIR document around one section."""
    return {
        "schema_version": "ats.text_ir.v1",
        "artifact_id": artifact_id,
        "source": {
            "content_sha256": SHA,
            "normalized_sha256": SHA,
            "media_type": "text/plain",
            "locator": f"{artifact_id}.txt",
        },
        "policy_snapshot_id": "policy-fixture-draft2",
        "language": "en",
        "audience": {"expertise": "expert"},
        "sections": [section],
        "extraction_status": "complete",
    }


class TestAtsBehavior:
    """§41: the CLI behaviors the front door mandates."""

    def test_new_authoring_resolves_draft2_with_36_rules(self) -> None:
        """§41.1: a draft.2 IR linted under the draft.2 policy needs no
        --spec-version: the policy pins 1.0.0-draft.2 and the full 36-rule
        registry engages."""
        report = _lint(
            "fixtures/ir/conforming/ats-coord-001-declared.json",
            "fixtures/policies/draft2.json",
        )
        assert report["spec_version"] == "1.0.0-draft.2"
        assert report["summary"]["rules_total"] == 36

    def test_legacy_material_stays_draft1(self) -> None:
        """§41.7: a draft.1-valid IR under a draft.1 policy stays draft.1 (30 rules)."""
        report = _lint(
            "fixtures/ir/valid/assess_conforming.json",
            "fixtures/policies/assess.json",
        )
        assert report["spec_version"] == "1.0.0-draft.1"
        assert report["summary"]["rules_total"] == 30
        assert not any(
            x["rule_id"].startswith(("ATS-COORD", "ATS-BASIS", "ATS-CLOSE", "ATS-PRES-003"))
            for x in report["rule_results"]
        )

    def test_draft2_material_cannot_silently_downgrade(self) -> None:
        """§41.8: a draft.2 IR under a draft.1 policy is a schema refusal,
        never a silent reinterpretation."""
        with pytest.raises(SchemaValidationError):
            _lint(
                "fixtures/ir/conforming/ats-coord-001-declared.json",
                "fixtures/policies/assess.json",
            )

    def test_non_blocking_unknown_does_not_trigger_a_question(
        self, ctx_d2, evaluate_document_d2, load_policy
    ) -> None:
        """§41.9: UNAVAILABLE authority basis with no precedence raises no
        question. BASIS-001 is advisory (blocks_conformance False), and the
        projection omits ``precedence`` rather than inventing a hierarchy."""
        document = _ir(
            "hg-precedence-unavailable",
            {
                "section_id": "s1",
                "heading": "hg-precedence-unavailable",
                "profiles": ["SPECIFY"],
                "claims": [
                    _requirement_claim(
                        "REQ-HG-1",
                        proposition="The verifier MUST reject a stale receipt before settlement.",
                        actor="verifier",
                        deontic="MUST",
                        action="reject",
                        object_="a stale receipt",
                        semantic_basis={
                            "basis": "UNAVAILABLE",
                            "rationale": "No authoritative source states the authority hierarchy.",
                        },
                    )
                ],
                "evidence": [],
                "relations": [],
                "update_indicators": [],
            },
        )

        rule = ctx_d2.registry.get("ATS-BASIS-001")
        assert rule.raw["operational_class"] == "review_required"
        assert rule.default_states["SPECIFY"] == "advisory"

        results = evaluate_document_d2(document, DRAFT2_POLICY)
        basis = results["ATS-BASIS-001"]
        assert basis.findings == ()  # the basis is declared: nothing to flag
        assert basis.status is not Status.FAIL
        assert basis.status is Status.REVIEW_REQUIRED  # D3 cannot conclude from silence
        assert basis.blocks_conformance is False  # advisory axis never blocks

        projection = project_from_ir(
            ctx_d2, document, load_policy(DRAFT2_POLICY), artifact_sha256=SHA
        )
        assert projection["authority"] == [
            {"source_id": "REQ-HG-1", "authority": "acceptance kernel"}
        ]
        assert all("precedence" not in record for record in projection["authority"])

    def test_unavailable_basis_stays_unavailable(
        self, ctx_d2, evaluate_document_d2
    ) -> None:
        """§41.9: a claim that declares UNAVAILABLE keeps it — BASIS-002
        decides PASS (no promotion) and the IR is never rewritten to a
        stronger value."""
        document = _ir(
            "hg-confidence-unavailable",
            {
                "section_id": "s1",
                "heading": "hg-confidence-unavailable",
                "profiles": ["TRANSFORM"],
                "claims": [
                    {
                        "claim_id": "OUT-HG-1",
                        "role": "judgment",
                        "proposition": (
                            "The acceptance kernel is likely to reject stale-policy "
                            "transitions (55-80%)."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "semantic_basis": {
                            "basis": "UNAVAILABLE",
                            "rationale": "The source records no confidence for the band.",
                        },
                        "source_refs": ["EV-HG-1"],
                        "extensions": {"source_basis": {"EV-HG-1": "UNAVAILABLE"}},
                    }
                ],
                "evidence": [
                    {
                        "evidence_id": "EV-HG-1",
                        "proposition": (
                            "Audit entries show rejections clustering around "
                            "stale-policy transitions."
                        ),
                        "source": {
                            "source_id": "src-EV-HG-1",
                            "source_type": "synthetic_fixture",
                            "availability": "present",
                            "locator": "EV-HG-1.txt",
                        },
                        "availability": "present",
                    }
                ],
                "relations": [],
                "update_indicators": [],
            },
        )

        results = evaluate_document_d2(document, DRAFT2_POLICY)
        basis002 = results["ATS-BASIS-002"]
        assert basis002.status is Status.PASS  # decided: no promotion
        assert basis002.findings == ()
        assert str(basis002.decision_power) == "decides"

        claim = document["sections"][0]["claims"][0]
        assert claim["semantic_basis"]["basis"] == "UNAVAILABLE"
        assert claim["extensions"]["source_basis"]["EV-HG-1"] == "UNAVAILABLE"

    def test_blocking_unresolved_normative_force_surfaces_review_required(
        self, evaluate_document_d2
    ) -> None:
        """§41.10: a material SPECIFY unit whose deontic force is absent must
        not resolve silently — ATS-DEON-001 raises
        requirement-without-deontic-force and ATS-CLOSE-001 reports
        REVIEW_REQUIRED on the unit."""
        document = _ir(
            "hg-force-ambiguity",
            {
                "section_id": "s1",
                "heading": "hg-force-ambiguity",
                "profiles": ["SPECIFY"],
                "claims": [
                    _requirement_claim(
                        "REQ-HG-2",
                        proposition="The adjudicator SHOULD confirm a quorum first.",
                        actor="adjudicator",
                        deontic="SHOULD",
                        action="confirm",
                        object_="a quorum",
                        authority="adjudication charter",
                        # The represented modality is absent; the ambiguity is
                        # recorded, not resolved: two live candidate forces.
                        force={},
                        extensions={
                            "requirement_force": {"alternatives": ["SHOULD", "MUST"]}
                        },
                    )
                ],
                "evidence": [],
                "relations": [],
                "update_indicators": [],
            },
        )

        results = evaluate_document_d2(document, DRAFT2_POLICY)

        deon = results["ATS-DEON-001"]
        assert deon.status is not Status.PASS
        assert {f.issue_code for f in deon.findings} == {"requirement-without-deontic-force"}

        close = results["ATS-CLOSE-001"]
        assert close.status is Status.REVIEW_REQUIRED  # never a silent PASS
        assert close.findings == ()


# ---------------------------------------------------------------------------
# §42 behavior: stable-coordinate round trip + no silent strengthening
# ---------------------------------------------------------------------------


class TestAtsSpecBehavior:
    """§42: the CLI/library behaviors ats-spec mandates."""

    def test_stable_requirement_and_ac_ids_survive_projection(
        self, ctx_d2, load_ir, load_policy
    ) -> None:
        """§42.1: requirement ID and acceptance-criterion ID project intact,
        with the AC backref and both stable-coordinate kinds."""
        projection = project_from_ir(
            ctx_d2,
            load_ir("ats-coord-001-declared"),
            load_policy(DRAFT2_POLICY),
            artifact_sha256=SHA,
        )
        (req,) = projection["requirements"]
        assert req["requirement_id"] == "REQ-C001-1"
        assert req["acceptance_criterion_id"] == "AC-C001-1"

        acs = {a["acceptance_criterion_id"]: a for a in projection["acceptance_criteria"]}
        assert acs["AC-C001-1"]["requirement_ids"] == ["REQ-C001-1"]

        assert [c["id"] for c in projection["stable_coordinates"]] == [
            "REQ-C001-1",
            "AC-C001-1",
        ]
        kinds = {c["kind"] for c in projection["stable_coordinates"]}
        assert kinds == {"requirement_id", "acceptance_criterion_id"}

    def test_derived_task_ids_are_distinct_from_ats_ids(
        self, ctx_d2, load_ir, load_policy
    ) -> None:
        """§42.10: derived execution task identity never collides with the
        spec's semantic identity, and one requirement may decompose into many
        tasks (one-req->one-task is not implied)."""
        projection = project_from_ir(
            ctx_d2,
            load_ir("ats-coord-001-declared"),
            load_policy(DRAFT2_POLICY),
            artifact_sha256=SHA,
        )
        ats_ids = {"REQ-C001-1", "AC-C001-1"}

        # One -> many: the same requirement rides on two independent tasks.
        tasks = [
            {
                "task_id": "VX-T1",
                "source_ats": {
                    "artifact_id": projection["artifact_id"],
                    "artifact_sha256": projection["artifact_sha256"],
                    "requirement_ids": ["REQ-C001-1"],
                    "decision_ids": [],
                    "acceptance_criterion_ids": ["AC-C001-1"],
                },
            },
            {
                "task_id": "VX-T2",
                "source_ats": {
                    "artifact_id": projection["artifact_id"],
                    "artifact_sha256": projection["artifact_sha256"],
                    "requirement_ids": ["REQ-C001-1"],
                    "decision_ids": [],
                    "acceptance_criterion_ids": [],
                },
            },
        ]

        task_ids = {t["task_id"] for t in tasks}
        assert task_ids.isdisjoint(ats_ids)
        for task in tasks:
            lineage = task["source_ats"]
            assert lineage["requirement_ids"] == ["REQ-C001-1"]
            assert set(lineage["acceptance_criterion_ids"]) <= ats_ids

        one_to_many = [
            t["task_id"]
            for t in tasks
            if "REQ-C001-1" in t["source_ats"]["requirement_ids"]
        ]
        assert one_to_many == ["VX-T1", "VX-T2"]

    def test_transformation_cannot_silently_strengthen(self, evaluate_ir_d2) -> None:
        """§42.12: BASIS-002 FAILs an EXPLICIT output claim promoted from
        INFERRED source material — transformation may not strengthen."""
        result = evaluate_ir_d2("ats-basis-002-promoted", DRAFT2_POLICY)["ATS-BASIS-002"]
        assert result.status is Status.FAIL
        assert {f.issue_code for f in result.findings} == {
            "inferred-source-promoted-to-explicit"
        }
        assert str(result.decision_power) == "decides"


# ---------------------------------------------------------------------------
# §44 behavior: review positive-control fixtures (§30)
# ---------------------------------------------------------------------------


class TestAtsReviewBehavior:
    """§44 + §30: the review positive-control fixtures exist and carry their
    control statements; the authority fixture declares no precedence."""

    REVIEW_FIXTURES = (
        "message_lifecycle.md",
        "normative_force.md",
        "authority_invention.md",
    )

    def _fixture(self, name: str) -> str:
        return _flatten(
            (REPO_ROOT / "fixtures" / "skills" / "review" / name).read_text(
                encoding="utf-8"
            )
        )

    def test_positive_control_fixtures_exist(self) -> None:
        for name in self.REVIEW_FIXTURES:
            path = REPO_ROOT / "fixtures" / "skills" / "review" / name
            assert path.is_file(), f"missing review positive-control fixture {name}"

    def test_message_lifecycle_control_statements(self) -> None:
        """§30.1: the lifecycle state machine is material and must not collapse."""
        text = self._fixture("message_lifecycle.md")
        assert "accepted → routed → disclosed | waiter_delivered → consumed" in text
        assert "MUST NOT be collapsed" in text
        assert "cannot be silently dropped" in text

    def test_normative_force_control_statements(self) -> None:
        """§30.2: SHOULD != MUST; no SHOULD→MUST upgrade to look rigorous."""
        text = self._fixture("normative_force.md")
        assert "SHOULD" in text and "MUST NOT" in text
        assert "MUST NOT strengthen" in text
        assert "MUST NOT rewrite it to" in text

    def test_authority_control_declares_no_precedence(self) -> None:
        """§30.3: the correct review outcome is authority_precedence =
        UNAVAILABLE; the fixture itself never declares a governing hierarchy."""
        text = self._fixture("authority_invention.md")
        assert "authority_precedence = UNAVAILABLE" in text
        assert "No document declares precedence over another" in text
        assert "never an invented hierarchy" in text
        assert "None of the three documents states which document governs the others" in text

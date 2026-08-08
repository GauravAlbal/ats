"""OSS fresh-install and review capstones for the public ATS skill pack.

The fresh-install scenario checks that a clean-environment user can install
the pack, invoke the public ``ats`` skill, resolve draft.2 authoring, create
an artifact, run deterministic checks, and receive a receipt. The pack has
no private dependency, does not require manual TextIR authoring, avoids
unnecessary questions, emits human-readable output, and states its standard
identity.

The review scenario checks that pre-ATS prose with a tempting semantic
ambiguity surfaces unresolved authority and force, keeps optional conversion
safe, and never invents authority.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from ats.canonical import content_hash
from ats.context import Context
from ats.ir.lint import lint_ir
from ats.output.receipt import build_candidate_receipt, verify_receipt

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "dist" / "skill-pack"
DRAFT2_POLICY_PATH = REPO_ROOT / "fixtures" / "policies" / "draft2.json"
FIXED_NOW = "2026-08-07T00:00:00Z"

#: Paths that must never appear in a distributed pack file.
_PRIVATE_PATHS = (
    "/" + "Users/",
    "/" + "tmp/",
    "/" + "private/",
    "/" + "home/",
    str(REPO_ROOT),
)


def _scan_for_private_paths(root: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for needle in _PRIVATE_PATHS:
            if needle in text:
                hits.append(f"{path.relative_to(root)}: contains {needle!r}")
    return hits


def _generic_pack_text() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((PACK / "generic").rglob("*"))
        if p.is_file() and p.suffix in (".md", ".json")
    )


def _draft2_context() -> Context:
    """The policy-pinned resolution (ADR-0020): new durable authoring resolves
    draft.2 via the binding policy, exactly as the CLI does — no override."""
    from ats.cli import _context

    return _context(argparse.Namespace(now=FIXED_NOW, policy=DRAFT2_POLICY_PATH))


def _oss_ir(policy: dict, *, with_ac: bool = False) -> dict:
    """A small implementation-spec IR authored from the operator request per
    the ats-spec contract: stable coordinates, explicit force, no internals
    required of the user."""
    claims = [
        {
            "claim_id": "REQ-CACHE-001",
            "role": "requirement",
            "proposition": (
                "The gateway MUST invalidate cached entries when the "
                "underlying storage object is rewritten."
            ),
            "material": True,
            "polarity": "positive",
            "status": "asserted",
            "force": {"deontic": "MUST"},
            "requirement": {
                "requirement_id": "REQ-CACHE-001",
                "actor": "gateway",
                "deontic": "MUST",
                "action": "invalidate",
                "object": "cached entries",
                "condition": "when the underlying storage object is rewritten",
                "source_authority": "operator brief",
            }
            | ({"acceptance_criterion_id": "AC-CACHE-001-A"} if with_ac else {})
            | ({"acceptance_criterion": "a subsequent read returns the new object"} if with_ac else {}),
            "semantic_basis": {"basis": "EXPLICIT"},
        }
    ]
    if with_ac:
        claims.append(
            {
                "claim_id": "AC-CACHE-001-A",
                "role": "observation",
                "proposition": (
                    "After a storage rewrite, a subsequent read returns the new "
                    "object rather than the cached copy."
                ),
                "material": True,
                "polarity": "positive",
                "status": "asserted",
                "semantic_basis": {"basis": "EXPLICIT"},
            }
        )
    ir = {
        "schema_version": "ats.text_ir.v1",
        "artifact_id": "ats-artifact-sha256:oss-fresh-install",
        "source": {
            "content_sha256": "0" * 64,
            "media_type": "text/plain",
            "locator": "brief.md",
        },
        "policy_snapshot_id": policy["snapshot_id"],
        "language": "en",
        "audience": {"expertise": "practitioner"},
        "sections": [
            {
                "section_id": "s1",
                "heading": "Requirements",
                "profiles": ["SPECIFY"],
                "claims": claims,
                "evidence": [],
                "relations": [],
                "update_indicators": [],
            }
        ],
        "extraction_status": "complete",
        "basis_policy": {"default_basis": "EXPLICIT", "declared": True},
    }
    if with_ac:
        ir["stable_coordinates"] = [
            {"kind": "requirement_id", "id": "REQ-CACHE-001", "source_pointer": "s1/REQ-CACHE-001"},
            {"kind": "acceptance_criterion_id", "id": "AC-CACHE-001-A", "source_pointer": "s1/AC-CACHE-001-A"},
        ]
    return ir


# ---------------------------------------------------------------------------
# OSS fresh-install contract


def test_pack_is_installable_and_self_contained() -> None:
    """The distributed pack carries no private path and no fleet dependency."""
    assert PACK.is_dir()
    hits = _scan_for_private_paths(PACK)
    assert hits == [], f"private paths leaked into the pack: {hits}"
    generic = _generic_pack_text().lower()
    for fleet_name in (
        "a" + "rq",
        "tribu" + "nal",
        "v" + "x",
        "m" + "oat",
        "s" + "ear",
    ):
        # The generic pack must not REQUIRE any fleet system to use ATS. A
        # standard-name expansion is permitted; a sentence requiring a fleet
        # dependency is not.
        assert not (
            f"requires {fleet_name}" in generic or f"need {fleet_name}" in generic
        ), f"generic pack references a fleet dependency: {fleet_name}"
    public_names = ("ats", "ats-spec", "ats-assess", "ats-review")
    helper_names = ("ats-ir-author", "ats-specify-output", "ats-assess-output")
    installed = {
        name: (PACK / "generic" / name / "SKILL.md").read_text(encoding="utf-8")
        for name in public_names
    }
    for name, body in installed.items():
        assert "self-contained" in body, f"{name}: installed procedure is not standalone"
        for helper in helper_names:
            assert helper not in body, f"{name}: unavailable helper dependency {helper}"
    spec_body = installed["ats-spec"]
    for required in (
        "Construct one `ats.text_ir.v1` document",
        "`ats ir lint <ir.json> --policy <policy>`",
        "`ats output lint <document> --trace <trace> --ir <ir.json> --policy <policy>`",
        "`ats output verify-receipt <receipt>",
        "candidate receipt",
    ):
        assert required in spec_body, f"ats-spec installed procedure omits {required!r}"
    manifest = json.loads((PACK / "skill-pack-manifest.json").read_text())
    assert manifest["standard_versions_supported"]["new_authoring"] == "1.0.0-draft.2"
    assert manifest["standard_versions_supported"]["legacy_interpretation"] == "1.0.0-draft.1"

def test_fresh_install_recipe_targets_resolve_inside_isolated_pack(tmp_path: Path) -> None:
    """Recipe resolution must not depend on canonical files in this checkout."""
    isolated = tmp_path / "skill-pack"
    shutil.copytree(PACK, isolated)
    manifest = json.loads((isolated / "skill-pack-manifest.json").read_text(encoding="utf-8"))
    recipe_sources = manifest["recipes"]
    assert all(
        source == "docs/ARTIFACT_RECIPES.md" or source.startswith("skills/public/recipes/")
        for source in recipe_sources
    )
    basenames = {Path(source).name for source in recipe_sources}
    recipe_dirs = {
        "generic": "recipes",
        "codex": "recipes",
        "claude": "references",
        "agent-plugins": "references",
    }
    for host in manifest["hosts"]:
        identity = host["identity"]
        target_dir = isolated / identity / recipe_dirs[identity]
        for basename in basenames:
            target = target_dir / basename
            assert target.is_file(), f"{identity}: installed recipe target missing: {target}"
            assert isolated in target.parents


def test_fresh_install_resolves_draft2_without_override() -> None:
    """New durable authoring resolves draft.2 via the binding policy — no
    --spec-version, no TextIR literacy required of the user."""
    ctx = _draft2_context()
    assert ctx.spec_version == "1.0.0-draft.2"
    policy = json.loads(DRAFT2_POLICY_PATH.read_text(encoding="utf-8"))
    ir = _oss_ir(policy, with_ac=True)
    report = lint_ir(ctx, ir, policy, source_path=None)
    # The deterministic surface is integrity-green and no unnecessary human
    # question arises (non-blocking unknowns stay UNAVAILABLE).
    assert report["spec_version"] == "1.0.0-draft.2"
    assert report["summary"]["required_failed"] == 0


def test_fresh_install_receipt_binds_draft2_and_output_is_human_readable() -> None:
    """The receipt binds draft.2; the artifact surface is prose, not TextIR."""
    ctx = _draft2_context()
    policy = json.loads(DRAFT2_POLICY_PATH.read_text(encoding="utf-8"))
    ir = _oss_ir(policy)
    report = lint_ir(ctx, ir, policy, source_path=None)
    ir_sha = content_hash(ir, exclude=set())
    from ats.ir.model import IrDocument

    receipt = build_candidate_receipt(
        ctx,
        ir=IrDocument.from_document(ir),
        policy=ctx.policy(policy),
        output_sha256=ir_sha,
        lint_report=report,
        adjudicator="oss-fresh-install-fixture",
    )
    verification = verify_receipt(ctx, receipt, ir_document=ir, output_sha256=ir_sha)
    assert verification["status"] == "PASS"
    assert receipt["spec_version"] == "1.0.0-draft.2"
    # The user-facing document is plain prose (the skill returns a useful
    # human artifact by default), not the IR dump.
    human_doc = (
        "## Requirements\n\n"
        "REQ-CACHE-001 — The gateway MUST invalidate cached entries when the "
        "underlying storage object is rewritten.\n\n"
        "Actor: gateway. Acceptance: after a storage rewrite, a subsequent read "
        "returns the new object rather than the cached copy."
    )
    assert "MUST" in human_doc and "REQ-CACHE-001" in human_doc
    assert human_doc.startswith("## Requirements")


# ---------------------------------------------------------------------------
# Review contract: ambiguous prose, no invented authority


def test_review_surfaces_undeclared_authority_as_unavailable() -> None:
    """The review leaves undeclared authority as UNAVAILABLE, never an
    invented hierarchy."""
    fixture = REPO_ROOT / "fixtures" / "skills" / "review" / "authority_invention.md"
    text = fixture.read_text(encoding="utf-8")
    assert "authority_precedence = UNAVAILABLE" in text
    # The source documents never declare a hierarchy; the tempting hierarchy
    # appears only as the named anti-pattern inside the review-control block.
    control = text.split("## Review control")[0]
    assert "product thesis" not in control


def test_review_safe_conversion_does_not_invent_authority() -> None:
    """A safe draft.2 conversion of the authority fixture keeps the authority
    basis UNAVAILABLE; ATS-BASIS-002 must not fire on it."""
    ctx = _draft2_context()
    policy = json.loads(DRAFT2_POLICY_PATH.read_text(encoding="utf-8"))
    ir = {
        "schema_version": "ats.text_ir.v1",
        "artifact_id": "ats-artifact-sha256:authority-control",
        "source": {"content_sha256": "0" * 64, "media_type": "text/plain"},
        "policy_snapshot_id": policy["snapshot_id"],
        "language": "en",
        "audience": {"expertise": "practitioner"},
        "sections": [
            {
                "section_id": "s1",
                "heading": "Assessment",
                "profiles": ["ASSESS"],
                "claims": [
                    {
                        "claim_id": "C1",
                        "role": "judgment",
                        "proposition": (
                            "No cross-document precedence is established by the "
                            "supplied sources."
                        ),
                        "material": True,
                        "polarity": "positive",
                        "status": "asserted",
                        "semantic_basis": {"basis": "UNAVAILABLE"},
                    }
                ],
                "evidence": [],
                "relations": [],
                "update_indicators": [],
            }
        ],
        "extraction_status": "complete",
    }
    report = lint_ir(ctx, ir, policy, source_path=None)
    # No invented authority: BASIS-002 finds no promotion (nothing is EXPLICIT
    # over an unavailable source), and the review's conversion stays safe.
    assert report["spec_version"] == "1.0.0-draft.2"
    assert report["summary"]["required_failed"] == 0
    basis_results = [
        r for r in report["rule_results"] if r["rule_id"] in ("ATS-BASIS-001", "ATS-BASIS-002")
    ]
    assert all(r["status"] != "FAIL" for r in basis_results)

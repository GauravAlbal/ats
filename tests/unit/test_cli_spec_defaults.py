"""The two-default spec-version policy (ADR-0020, F0 entry condition).

Legacy interpretation (corpus reads, bench, unlabeled material) defaults to
draft.1; new durable authoring under a policy resolves the edition the policy
pins — draft.2 for the fleet policy — without an explicit --spec-version.
An old artifact must never acquire draft.2 semantics merely because the
fleet advanced, and an explicit --spec-version always wins.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from ats.cli import _context
from ats.spec_package import AUTHORING_SPEC_VERSION, DEFAULT_SPEC_VERSION


def _args(**kw) -> argparse.Namespace:
    base = {"now": None, "spec_version": None}
    base.update(kw)
    return argparse.Namespace(**base)


def test_no_policy_no_flag_resolves_the_legacy_interpretation_default() -> None:
    ctx = _context(_args())
    assert ctx.spec_version == DEFAULT_SPEC_VERSION == "1.0.0-draft.1"
    assert "ATS-COORD-001" not in ctx.registry.ids()


def test_the_authoring_default_is_draft2() -> None:
    assert AUTHORING_SPEC_VERSION == "1.0.0-draft.2"


def test_a_draft2_policy_snapshot_pins_the_edition_without_a_flag() -> None:
    ctx = _context(_args(policy="fixtures/policies/draft2.json"))
    assert ctx.spec_version == "1.0.0-draft.2"
    assert "ATS-COORD-001" in ctx.registry.ids()
    assert len(ctx.registry.ids()) == 36


def test_the_fleet_policy_pins_draft2_for_new_authoring() -> None:
    ctx = _context(_args(policy="config/policies/fleet_policy.json"))
    assert ctx.spec_version == "1.0.0-draft.2"
    assert len(ctx.registry.ids()) == 36


def test_a_draft1_policy_keeps_the_legacy_interpretation() -> None:
    ctx = _context(_args(policy="fixtures/policies/assess.json"))
    assert ctx.spec_version == "1.0.0-draft.1"
    assert len(ctx.registry.ids()) == 30


def test_an_explicit_spec_version_always_wins_over_the_policy() -> None:
    ctx = _context(
        _args(spec_version="1.0.0-draft.1", policy="fixtures/policies/draft2.json")
    )
    assert ctx.spec_version == "1.0.0-draft.1"
    ctx = _context(
        _args(spec_version="1.0.0-draft.2", policy="fixtures/policies/assess.json")
    )
    assert ctx.spec_version == "1.0.0-draft.2"


def test_an_unreadable_policy_falls_back_to_the_legacy_default() -> None:
    ctx = _context(_args(policy="/nonexistent/policy.json"))
    assert ctx.spec_version == DEFAULT_SPEC_VERSION


def test_an_old_artifact_does_not_acquire_draft2_semantics(tmp_path: Path) -> None:
    """A draft.1-valid artifact linted under a draft.1 policy stays draft.1:
    no draft.2 rules engage, and the draft.2 fixture is rejected by the
    draft.1 schema rather than silently reinterpreted."""
    from ats.corpus import gold  # noqa: F401  (import guard: corpus stack loads)

    report = _lint("fixtures/ir/valid/assess_conforming.json", "fixtures/policies/assess.json")
    assert report["spec_version"] == "1.0.0-draft.1"
    assert report["summary"]["rules_total"] == 30
    assert not any(
        x["rule_id"].startswith(("ATS-COORD", "ATS-BASIS", "ATS-CLOSE", "ATS-PRES-003"))
        for x in report["rule_results"]
    )
    # The converse is also fail-closed: a draft.2 artifact under a draft.1
    # policy is refused by the schema, never silently downgraded.
    with pytest.raises(Exception):
        _lint("fixtures/ir/conforming/ats-coord-001-declared.json",
              "fixtures/policies/assess.json")


def _lint(ir_path: str, policy_path: str) -> dict:
    from ats.ir.lint import lint_ir

    ctx = _context(_args(policy=policy_path))
    return lint_ir(
        ctx,
        json.loads(Path(ir_path).read_text(encoding="utf-8")),
        json.loads(Path(policy_path).read_text(encoding="utf-8")),
    )

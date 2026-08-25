"""ATS-1 draft.3 sealing and runtime-compatibility regression tests."""
from __future__ import annotations

import datetime as dt
from ats.context import Context
from ats.rules.deterministic import load_detectors
from ats.rules.deterministic._support import SPECS
from ats.rules.deterministic.requirements_draft3 import HIDDEN_DEONTIC, TEST_SHAPED_AC
from ats.spec_import import run_package_validator

DRAFT3 = "1.0.0-draft.3"
FIXED_NOW = dt.datetime(2026, 8, 3, tzinfo=dt.UTC)


def test_draft3_package_validates_and_loads_thirty_seven_rules() -> None:
    ctx = Context.load(spec_version=DRAFT3, now=FIXED_NOW)
    run = run_package_validator(ctx.package)
    assert run.exit_code == 0, f"draft.3 package validator failed:\n{run.stdout}\n{run.stderr}"
    assert run.status == "PASS"
    assert ctx.spec_version == DRAFT3
    assert ctx.registry.spec_version == DRAFT3
    assert len(ctx.registry.ids()) == 37
    assert "ATS-REQ-004" in ctx.registry.ids()
    assert ctx.capability.coherence_errors() == []
    spec_text = ctx.package.spec_document.read_text(encoding="utf-8")
    assert "- each `MUST` and `MUST NOT` has a verifiable acceptance criterion;" in spec_text
    assert "load-bearing acceptance criterion that does not widen its requirement" not in spec_text


def test_req004_is_advisory_and_partial_not_a_semantic_pass() -> None:
    ctx = Context.load(spec_version=DRAFT3, now=FIXED_NOW)
    rule = ctx.registry.get("ATS-REQ-004")
    assert rule.rule_version == DRAFT3
    assert rule.default_states["SPECIFY"] == "advisory"
    assert rule.default_states["TRANSFORM"] == "advisory"
    cap = ctx.capability.for_rule("ATS-REQ-004")
    assert cap.implemented is True
    assert cap.detector_class == "D1"
    assert cap.decision_power == "detects_violations"
    assert cap.missing_inputs == ()
    assert cap.blocking_inputs == ()
    detectors = load_detectors(ctx.registry.ids())
    assert "ATS-REQ-004" in detectors
    assert SPECS["ATS-REQ-004"].power == "detects_violations"


def test_req004_d1_scope_is_narrow_and_load_bearing_review_stays_semantic() -> None:
    assert TEST_SHAPED_AC.match("TestStalePolicyRejection passes.")
    assert TEST_SHAPED_AC.match("go test ./pkg succeeds")
    assert not TEST_SHAPED_AC.match(
        "Given a stale receipt, the verifier returns refused_stale_policy and emits no accepted transition."
    )
    assert HIDDEN_DEONTIC.search(
        "The verifier rejects the stale receipt and MUST also persist a seven-year audit record."
    )
    assert not HIDDEN_DEONTIC.search(
        "Given a stale receipt, the verifier returns refused_stale_policy."
    )


def test_draft3_contains_all_four_discriminating_ac_fixtures() -> None:
    ctx = Context.load(spec_version=DRAFT3, now=FIXED_NOW)
    fixture = ctx.package.root / "examples" / "acceptance_criterion_semantics.md"
    text = fixture.read_text(encoding="utf-8")
    assert "## Conforming" in text
    assert "`TestStalePolicyRejection` passes." in text
    assert "## Hard negative — non-load-bearing" in text
    assert "seven-year audit record" in text

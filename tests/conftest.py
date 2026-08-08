"""Shared fixtures for the ATS-1 test suite.

Every test runs against one imported normative package, one fixed evaluation
clock, and the checked-in fixtures. Spec Section 16.2 requires identical results
for identical canonical inputs, so nothing here reads a wall clock, the network,
or an environment variable: an evaluation time is passed explicitly and the
package is the one under ``spec/ATS-1/``.
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from ats.context import Context  # noqa: E402
from ats.errors import SchemaValidationError  # noqa: E402

#: The single evaluation instant every test uses. Spec Section 6.3 makes
#: exception expiry a function of the evaluation time, so that time is an input,
#: never a reading of the host clock.
FIXED_NOW = _dt.datetime(2026, 8, 3, tzinfo=_dt.UTC)

FIXTURES = REPO_ROOT / "fixtures"
IR_VALID = FIXTURES / "ir" / "valid"
IR_INVALID = FIXTURES / "ir" / "invalid"
IR_SOURCES = FIXTURES / "ir" / "sources"
POLICIES = FIXTURES / "policies"
OUTPUT_BUNDLES = FIXTURES / "output"

#: The draft.2 rule fixtures live in the four fixture-kind directories rather
#: than the draft.1 valid/invalid split.
IR_DRAFT2_ROOTS = (
    FIXTURES / "ir" / "conforming",
    FIXTURES / "ir" / "violation",
    FIXTURES / "ir" / "hard_negative",
    FIXTURES / "ir" / "exception",
)

#: Every conforming TextIR fixture, by file stem.
VALID_IR_NAMES = (
    "assess_conforming",
    "assess_partial_extraction",
    "assess_represented_ambiguity",
    "assess_transform_output",
    "composed_profiles",
    "specify_conforming",
)

#: Every violation fixture, mapped to the policy snapshot it is evaluated under.
#: The mapping is a property of the fixture's ``policy_snapshot_id``, not of any
#: linter behaviour.
INVALID_IR_POLICY: Mapping[str, str] = {
    "ambiguous_without_distinct_readings": "assess",
    "blank_confidence_basis": "assess",
    "concealed_actor": "specify",
    "dangling_reference": "assess",
    "duplicate_ids": "assess",
    "missing_acceptance_criterion": "specify",
    "no_update_indicator": "assess",
    "noncanonical_modal": "specify",
    "noncanonical_wep_synonym": "assess",
    "observation_with_confidence": "assess",
    "possibility_term_only": "assess",
    "quantifier_without_unit": "specify",
    "reserved_profile": "assess",
    "should_without_override": "specify",
    "two_obligations": "specify",
    "unanchored_relative_time": "assess",
    "wep_interval_mismatch": "assess",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixed_now() -> _dt.datetime:
    return FIXED_NOW


@pytest.fixture(scope="session")
def ctx() -> Context:
    """The evaluation context, bound to the fixed clock (spec 16.2)."""
    return Context.load(now=FIXED_NOW)


@pytest.fixture(scope="session")
def ctx_d2() -> Context:
    """The draft.2 evaluation context (36 rules), same fixed clock."""
    return Context.load(spec_version="1.0.0-draft.2", now=FIXED_NOW)


@pytest.fixture(scope="session")
def load_ir() -> Callable[[str], dict[str, Any]]:
    """Load a TextIR fixture by stem, searching valid then invalid."""

    def _load(name: str) -> dict[str, Any]:
        stem = name.removesuffix(".json")
        for root in (*IR_DRAFT2_ROOTS, IR_VALID, IR_INVALID):
            candidate = root / f"{stem}.json"
            if candidate.is_file():
                return _read_json(candidate)
        raise AssertionError(f"no TextIR fixture named {name!r}")

    return _load


@pytest.fixture(scope="session")
def load_policy() -> Callable[[str], dict[str, Any]]:
    """Load a policy-snapshot fixture by stem."""

    def _load(name: str) -> dict[str, Any]:
        path = POLICIES / f"{name.removesuffix('.json')}.json"
        if not path.is_file():
            raise AssertionError(f"no policy fixture named {name!r}")
        return _read_json(path)

    return _load


@pytest.fixture(scope="session")
def load_bundle() -> Callable[[str], dict[str, Any]]:
    """Load one rendered output bundle: markdown path plus its three sidecars."""

    def _load(name: str) -> dict[str, Any]:
        root = OUTPUT_BUNDLES / name
        if not root.is_dir():
            raise AssertionError(f"no output bundle named {name!r}")
        return {
            "root": root,
            "output_path": root / "document.md",
            "text": (root / "document.md").read_text(encoding="utf-8"),
            "trace": _read_json(root / "document.trace.json"),
            "lint": _read_json(root / "document.lint.json"),
            "receipt": _read_json(root / "document.receipt.json"),
        }

    return _load


@pytest.fixture(scope="session")
def source_path() -> Callable[[str], Path]:
    """Path to a bound source artifact under ``fixtures/ir/sources``."""

    def _path(name: str) -> Path:
        path = IR_SOURCES / name
        if not path.is_file():
            raise AssertionError(f"no source fixture named {name!r}")
        return path

    return _path


@pytest.fixture(scope="session")
def assert_valid(ctx: Context) -> Callable[[Any, str], None]:
    """Assert a document validates against a named schema (spec 19.4)."""

    def _assert(document: Any, schema_id: str) -> None:
        try:
            ctx.schemas.validate(document, schema_id)
        except SchemaValidationError as exc:  # pragma: no cover - failure path
            rendered = "; ".join(f"{v.pointer or '/'}: {v.message}" for v in exc.violations)
            raise AssertionError(f"{schema_id} validation failed: {rendered}") from None

    return _assert


@pytest.fixture(scope="session")
def run_tool(repo_root: Path) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Run a repository tool in a subprocess with ``src`` on the path."""

    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            env={"PYTHONPATH": str(SRC_ROOT), "PATH": "/usr/bin:/bin"},
        )

    return _run


def clean_status(power: str, authority: str) -> str:
    """The status a detector that raised no finding is entitled to report.

    Spec Section 5.4 and 16.5: absence of a surfaced finding proves conformance
    only for a complete decision procedure whose output counts as conformance
    evidence (Section 12.3). Everything else reports REVIEW_REQUIRED, and a
    rule with no decision procedure at all reports UNAVAILABLE.
    """
    if power == "undecidable":
        return "UNAVAILABLE"
    if power == "decides" and authority == "conformance_evidence":
        return "PASS"
    return "REVIEW_REQUIRED"


@pytest.fixture(scope="session")
def evaluate_ir(ctx: Context, load_ir, load_policy):
    """Run every registered detector over one IR fixture under one policy.

    Returns ``rule_id -> RuleResult``. Results are cached per ``(ir, policy)``
    pair because Section 16.2 makes them a pure function of those inputs.
    """
    from ats.ir.model import IrDocument, IrEvaluation
    from ats.rules.deterministic import load_detectors

    cache: dict[tuple[str, str], dict[str, Any]] = {}

    def _evaluate(ir_name: str, policy_name: str) -> dict[str, Any]:
        key = (ir_name, policy_name)
        if key not in cache:
            policy = ctx.policy(load_policy(policy_name))
            ir = IrDocument.from_document(load_ir(ir_name))
            states, _ = policy.resolve_all(
                ir.profiles or policy.profiles, now=FIXED_NOW, artifact_id=ir.artifact_id
            )
            evaluation = IrEvaluation(ctx=ctx, ir=ir, policy=policy, states=states)
            detectors = load_detectors()
            cache[key] = {rid: detectors[rid](evaluation) for rid in ctx.registry.ids()}
        return cache[key]

    return _evaluate


@pytest.fixture(scope="session")
def evaluate_document(ctx: Context, load_policy):
    """Run every detector over an in-memory TextIR document under one policy.

    Used where the checked-in fixtures carry no violation twin for a rule: a
    single field is mutated in a copy of a conforming fixture, so the pair still
    differs in exactly one place (spec 16.4).
    """
    from ats.ir.model import IrDocument, IrEvaluation
    from ats.rules.deterministic import load_detectors

    def _evaluate(ir_document: Mapping[str, Any], policy_name: str) -> dict[str, Any]:
        policy = ctx.policy(load_policy(policy_name))
        ir = IrDocument.from_document(ir_document)
        states, _ = policy.resolve_all(
            ir.profiles or policy.profiles, now=FIXED_NOW, artifact_id=ir.artifact_id
        )
        evaluation = IrEvaluation(ctx=ctx, ir=ir, policy=policy, states=states)
        detectors = load_detectors()
        return {rid: detectors[rid](evaluation) for rid in ctx.registry.ids()}

    return _evaluate


@pytest.fixture(scope="session")
def evaluate_ir_d2(ctx_d2: Context, load_ir, load_policy):
    """Evaluate the full 36-rule registry over a fixture under the draft.2 package.

    Mirrors :func:`evaluate_ir` with the draft.2 context so the draft.2
    detectors (ATS-COORD-*, ATS-BASIS-*, ATS-PRES-003, ATS-CLOSE-001) resolve
    states and run their bodies over the draft.2 fixtures.
    """
    from ats.ir.model import IrDocument, IrEvaluation
    from ats.rules.deterministic import load_detectors

    cache: dict[tuple[str, str], dict[str, Any]] = {}

    def _evaluate(ir_name: str, policy_name: str) -> dict[str, Any]:
        key = (ir_name, policy_name)
        if key not in cache:
            policy = ctx_d2.policy(load_policy(policy_name))
            ir = IrDocument.from_document(load_ir(ir_name))
            states, _ = policy.resolve_all(
                ir.profiles or policy.profiles, now=FIXED_NOW, artifact_id=ir.artifact_id
            )
            evaluation = IrEvaluation(ctx=ctx_d2, ir=ir, policy=policy, states=states)
            detectors = load_detectors(ctx_d2.registry.ids())
            cache[key] = {rid: detectors[rid](evaluation) for rid in ctx_d2.registry.ids()}
        return cache[key]

    return _evaluate


@pytest.fixture(scope="session")
def evaluate_document_d2(ctx_d2: Context, load_policy):
    """Run the 36-rule registry over an in-memory document under draft.2."""
    from ats.ir.model import IrDocument, IrEvaluation
    from ats.rules.deterministic import load_detectors

    def _evaluate(ir_document: Mapping[str, Any], policy_name: str) -> dict[str, Any]:
        policy = ctx_d2.policy(load_policy(policy_name))
        ir = IrDocument.from_document(ir_document)
        states, _ = policy.resolve_all(
            ir.profiles or policy.profiles, now=FIXED_NOW, artifact_id=ir.artifact_id
        )
        evaluation = IrEvaluation(ctx=ctx_d2, ir=ir, policy=policy, states=states)
        detectors = load_detectors(ctx_d2.registry.ids())
        return {rid: detectors[rid](evaluation) for rid in ctx_d2.registry.ids()}

    return _evaluate


@pytest.fixture(scope="session")
def mutated_ir(load_ir):
    """A deep copy of a TextIR fixture, for one named single-field mutation."""
    import copy

    def _copy(name: str) -> dict[str, Any]:
        return copy.deepcopy(load_ir(name))

    return _copy


@pytest.fixture(scope="session")
def issue_codes():
    """The sorted issue codes a rule result raised."""

    def _codes(result) -> list[str]:
        return sorted(f.issue_code for f in result.findings)

    return _codes

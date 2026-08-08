#!/usr/bin/env python3
"""Generate the policy-snapshot fixtures under ``fixtures/policies/``.

Every snapshot is sealed with :func:`ats.canonical.seal`, so the checked-in
``snapshot_sha256`` is the real content address of the file's own bytes rather
than a placeholder. A test that binds one of these snapshots exercises the same
staleness gate production does.

Usage::

    PYTHONPATH=src python tools/generate_policies.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ats.canonical import seal  # noqa: E402
from ats.schemas import SchemaSet  # noqa: E402
from ats.spec_package import SpecPackage  # noqa: E402

POLICIES = REPO_ROOT / "fixtures" / "policies"


def _base(snapshot_id: str, profiles: list[str], spec_version: str) -> dict[str, Any]:
    return {
        "schema_version": "ats.policy_snapshot.v1",
        "snapshot_id": snapshot_id,
        "standard": "ATS-1",
        "spec_version": spec_version,
        "created_at": "2026-08-03T00:00:00Z",
        "profiles": profiles,
        "audience": {"expertise": "expert", "audience_id": "arq-engineering", "locale": "en-US"},
        "glossary_refs": ["arq-core-v1"],
        "lexicon_refs": ["ats_force_lexicon_v1"],
        "rule_overrides": {},
        "exceptions": [],
        "finding_budget": {"guardrail": "all_critical", "coach": 5},
        "model_artifacts": [],
        "fallback_policy": "fail_closed",
    }


def build() -> dict[Path, str]:
    package = SpecPackage.load()
    schemas = SchemaSet(package)
    version = package.spec_version
    documents: dict[str, dict[str, Any]] = {}

    documents["assess.json"] = _base("policy-example-assess", ["ASSESS"], version)

    documents["assess_transform.json"] = _base(
        "policy-fixture-assess-transform", ["ASSESS", "TRANSFORM"], version
    )

    documents["specify.json"] = _base("policy-fixture-specify", ["SPECIFY"], version)

    composed = _base("policy-fixture-composed", ["ASSESS", "SPECIFY", "TRANSFORM"], version)
    documents["composed.json"] = composed

    strengthened = _base("policy-fixture-strengthened", ["ASSESS"], version)
    # Section 6.2 permits a more specialized policy to strengthen a rule.
    strengthened["rule_overrides"] = {"ATS-DISC-001": "required"}
    documents["strengthened.json"] = strengthened

    weakening = _base("policy-fixture-weakening-override", ["ASSESS"], version)
    # Section 6.2 forbids weakening through a bare override; resolution refuses
    # it and records the refusal.
    weakening["rule_overrides"] = {"ATS-EPI-001": "advisory"}
    documents["weakening_override.json"] = weakening

    excepted = _base("policy-fixture-scoped-exception", ["ASSESS"], version)
    exception = seal(
        {
            "schema_version": "ats.policy_exception.v1",
            "exception_id": "exc-epi-002-fixture",
            "rule_id": "ATS-EPI-002",
            "from_state": "required",
            "to_state": "advisory",
            "scope": {"artifact_id": "fixture-assess-rust-kernel"},
            "rationale": (
                "The persistent probability scale is visible in the reviewing interface for this "
                "artifact, which is the condition Appendix E question 2 leaves open."
            ),
            "authorized_by": "arq-acceptance-policy-owner",
            "created_at": "2026-08-03T00:00:00Z",
            "expires_at": "2027-08-03T00:00:00Z",
        }
    )
    excepted["exceptions"] = [exception]
    documents["scoped_exception.json"] = excepted

    expired = _base("policy-fixture-expired-exception", ["ASSESS"], version)
    expired_exception = seal(
        {
            "schema_version": "ats.policy_exception.v1",
            "exception_id": "exc-epi-002-expired",
            "rule_id": "ATS-EPI-002",
            "from_state": "required",
            "to_state": "advisory",
            "scope": {"artifact_id": "fixture-assess-rust-kernel"},
            "rationale": "Superseded interface assumption, retained to exercise expiry.",
            "authorized_by": "arq-acceptance-policy-owner",
            "created_at": "2025-01-01T00:00:00Z",
            "expires_at": "2025-06-01T00:00:00Z",
        }
    )
    expired["exceptions"] = [expired_exception]
    documents["expired_exception.json"] = expired

    files: dict[Path, str] = {}
    for name, document in documents.items():
        sealed = seal(document)
        schemas.validate(sealed, "ats_policy_snapshot_v1.schema.json")
        files[POLICIES / name] = json.dumps(sealed, indent=2, ensure_ascii=False) + "\n"
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = build()
    if args.check:
        stale = [
            str(p.relative_to(REPO_ROOT))
            for p, content in files.items()
            if not p.is_file() or p.read_text(encoding="utf-8") != content
        ]
        if stale:
            print("stale policy fixtures: " + ", ".join(sorted(stale)), file=sys.stderr)
            return 1
        print(f"{len(files)} policy fixtures are current")
        return 0
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"wrote {len(files)} policy fixtures under {POLICIES.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

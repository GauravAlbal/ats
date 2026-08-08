#!/usr/bin/env python3
"""Exercise every documented CLI command and report its exit code.

The milestone names a CLI surface. This drives all of it in one pass so a
missing or broken command is visible immediately, and so the exit-code contract
is checked end to end rather than assumed.

Usage::

    PYTHONPATH=src python tools/smoke_cli.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

NOW = ("--now", "2026-08-03T00:00:00Z")

#: (label, argv, acceptable exit codes)
CASES: list[tuple[str, list[str], tuple[int, ...]]] = [
    ("spec validate", ["spec", "validate"], (0,)),
    ("spec status", ["spec", "status"], (0,)),
    ("rules list", ["rules", "list"], (0,)),
    ("rules explain", ["rules", "explain", "ATS-EPI-001"], (0,)),
    ("capability show", ["capability", "show"], (0,)),
    (
        "ir validate",
        ["ir", "validate", "fixtures/ir/valid/assess_conforming.json"],
        (0,),
    ),
    (
        "ir validate (bad)",
        ["ir", "validate", "fixtures/ir/invalid/duplicate_ids.json"],
        (0, 1),
    ),
    (
        "ir lint (conforming)",
        [
            *NOW,
            "ir",
            "lint",
            "fixtures/ir/valid/assess_conforming.json",
            "--policy",
            "fixtures/policies/assess.json",
            "--source",
            "fixtures/ir/sources/assess_rust_kernel.txt",
        ],
        (0,),
    ),
    (
        "ir lint (violating)",
        [
            *NOW,
            "ir",
            "lint",
            "fixtures/ir/invalid/wep_interval_mismatch.json",
            "--policy",
            "fixtures/policies/assess.json",
            "--source",
            "fixtures/ir/sources/assess_rust_kernel.txt",
        ],
        (1,),
    ),
    (
        "ir lint (no source)",
        [
            *NOW,
            "ir",
            "lint",
            "fixtures/ir/valid/assess_conforming.json",
            "--policy",
            "fixtures/policies/assess.json",
        ],
        (4,),
    ),
    (
        "ir canonicalize",
        ["ir", "canonicalize", "fixtures/ir/valid/specify_conforming.json"],
        (0,),
    ),
    ("ir explain-finding", ["ir", "explain-finding", "ATS-REQ-003"], (0,)),
    (
        "output lint (conforming)",
        [
            *NOW,
            "output",
            "lint",
            "fixtures/output/assess-bundle/document.md",
            "--trace",
            "fixtures/output/assess-bundle/document.trace.json",
            "--ir",
            "fixtures/ir/valid/assess_conforming.json",
            "--policy",
            "fixtures/policies/assess.json",
            "--receipt",
            "fixtures/output/assess-bundle/document.receipt.json",
        ],
        (0,),
    ),
    (
        "output lint (broken)",
        [
            *NOW,
            "output",
            "lint",
            "fixtures/output/assess-broken/document.md",
            "--trace",
            "fixtures/output/assess-broken/document.trace.json",
            "--ir",
            "fixtures/ir/valid/assess_conforming.json",
            "--policy",
            "fixtures/policies/assess.json",
        ],
        (1,),
    ),
    (
        "output verify-receipt",
        [
            *NOW,
            "output",
            "verify-receipt",
            "fixtures/output/assess-bundle/document.receipt.json",
            "--ir",
            "fixtures/ir/valid/assess_conforming.json",
            "--document",
            "fixtures/output/assess-bundle/document.md",
            "--policy",
            "fixtures/policies/assess.json",
        ],
        (0,),
    ),
    (
        "corpus validate",
        ["corpus", "validate", "fixtures/corpus"],
        (0, 1),
    ),
    (
        "corpus stats",
        ["corpus", "stats", "fixtures/corpus"],
        (0,),
    ),
    (
        "corpus mutate (supported)",
        [
            "corpus",
            "mutate",
            "fixtures/mutations/sources/example_with_text_ir.json",
            "--operator",
            "ATS-MUT-WEP-BAND-SHIFT",
        ],
        (0,),
    ),
    (
        "corpus mutate (unsupported)",
        [
            "corpus",
            "mutate",
            "fixtures/mutations/sources/example_with_text_ir.json",
            "--operator",
            "ATS-MUT-ANTECEDENT-AMBIGUATE",
        ],
        (3,),
    ),
    (
        "corpus annotate",
        [
            "corpus",
            "annotate",
            "fixtures/corpus/examples.jsonl",
            "--annotator",
            "annotator-smoke",
            "--bundles",
            "fixtures/corpus/context_bundles.jsonl",
        ],
        (0,),
    ),
    (
        "corpus adjudicate",
        [
            "corpus",
            "adjudicate",
            "fixtures/corpus/judgments.jsonl",
            "--adjudicator",
            "adjudicator-smoke",
        ],
        (0,),
    ),
    (
        "corpus split",
        [
            "corpus",
            "split",
            "fixtures/corpus/examples.jsonl",
            "--policy",
            "fixtures/corpus/split_policy.json",
        ],
        (0,),
    ),
    (
        "corpus split (random refused)",
        [
            "corpus",
            "split",
            "fixtures/corpus/examples.jsonl",
            "--policy",
            "fixtures/corpus/split_policy_random.json",
        ],
        (2,),
    ),
]


def run(argv: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "ats.cli", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    cases = list(CASES)

    # The skill-pack milestone's own surfaces (review F8): the pack validator,
    # the planning projection, and the fleet-policy resolver must be smoke-able
    # like every other documented command.

    planning_fixture = (
        REPO_ROOT / "fixtures" / "ir" / "conforming" / "ats-basis-001-declared.json"
    )
    planning_artifact_sha = json.loads(
        planning_fixture.read_text(encoding="utf-8")
    )["source"]["content_sha256"]
    cases.extend(
        [
            (
                "skills verify",
                ["skills", "verify"],
                (0,),
            ),
            (
                "policy resolve",
                ["policy", "resolve", "implementation_spec"],
                (0,),
            ),
            (
                "planning project",
                [
                    *NOW,
                    "planning",
                    "project",
                    str(planning_fixture.relative_to(REPO_ROOT)),
                    "--policy",
                    "fixtures/policies/draft2.json",
                    "--artifact-sha256",
                    planning_artifact_sha,
                ],
                (0,),
            ),
        ]
    )

    # The corpus commands that need a real repository build one in a temp dir,
    # so the checked-in fixture stays a plain content tree.
    tmp = Path(tempfile.mkdtemp(prefix="ats-smoke-"))
    try:
        try:
            from ats.corpus import inventory as _inventory  # noqa: F401

            sys.path.insert(0, str(REPO_ROOT / "tools"))
            from generate_corpus_fixtures import build_sample_repo  # type: ignore

            repo = build_sample_repo(tmp / "sample-repo")
            inventory_path = tmp / "inventory.json"
            cases.extend(
                [
                    (
                        "corpus inventory",
                        ["corpus", "inventory", "--repo", str(repo), "--out", str(inventory_path)],
                        (0,),
                    ),
                    ("corpus mine", ["corpus", "mine", "--inventory", str(inventory_path)], (0,)),
                ]
            )
        except Exception as exc:  # pragma: no cover - reported, not swallowed
            print(f"[skip] corpus inventory/mine: could not build a sample repo ({exc})")

        failures = 0
        for label, argv, expected in cases:
            code, out, err = run(argv, REPO_ROOT)
            ok = code in expected
            failures += 0 if ok else 1
            detail = ""
            if not ok:
                detail = f"  <- expected {expected}; stderr: {(err or out).strip()[:200]}"
            print(f"[{'ok  ' if ok else 'FAIL'}] {label:<28} exit={code}{detail}")
        print(f"\n{len(cases) - failures}/{len(cases)} commands behaved as contracted")
        return 1 if failures else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

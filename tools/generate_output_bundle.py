#!/usr/bin/env python3
"""Build the output-bundle fixtures under ``fixtures/output/``.

Two bundles are produced from the same IR:

``assess-bundle``
    A conforming ASSESS rendering following the Section 9.2.12 canonical
    structure, with an invisible source map and a full trace sidecar.

``assess-broken``
    The same rendering with two deliberate defects: the inline WEP range is
    dropped from the key judgment, and a declared P0 value is altered. Each
    defect targets exactly one check so the test can name which.

Usage::

    PYTHONPATH=src python tools/generate_output_bundle.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ats import __version__  # noqa: E402
from ats.canonical import load_json, sha256_hex  # noqa: E402
from ats.context import Context  # noqa: E402
from ats.ir.model import IrDocument  # noqa: E402
from ats.output.lint import lint_output  # noqa: E402
from ats.output.parse import parse_markdown  # noqa: E402
from ats.output.receipt import build_candidate_receipt  # noqa: E402
from ats.output.trace import build_trace  # noqa: E402
import datetime as _dt  # noqa: E402

OUTPUT = REPO_ROOT / "fixtures" / "output"
FIXED_NOW = _dt.datetime(2026, 8, 3, tzinfo=_dt.UTC)

#: An external acceptance authority. The renderer never names itself
#: (spec Sections 13.7 and 14.11).
ADJUDICATOR = "arq-acceptance-authority"


def _block(marker: str, heading: str, body: str) -> str:
    """A heading followed by a marked prose block.

    The marker sits between the heading and the body so that the hashed block
    is the prose a reader acts on. A heading is a navigational label, and
    Section 9.2.2 says headings alone do not satisfy evidence obligations.
    """
    return f"## {heading}\n\n<!-- ats:block {marker} -->\n{body}\n"


def render_document(*, drop_inline_range: bool, alter_p0: bool) -> str:
    judgment = (
        "A Rust migration is likely (55–80%) to reduce invalid-state defects in the acceptance "
        "kernel after the transition model is stable."
    )
    if drop_inline_range:
        judgment = (
            "A Rust migration is likely to reduce invalid-state defects in the acceptance kernel "
            "after the transition model is stable."
        )
    boundary = "The assessment does not apply to the policy-fluid orchestration plane."
    if alter_p0:
        boundary = "The assessment also covers the policy-fluid orchestration plane."

    parts = [
        "# Acceptance-kernel language assessment\n",
        _block(
            "assess-question",
            "Question",
            "Should Arq move the acceptance kernel from Python to Rust after the state model "
            "stabilizes?",
        ),
        _block("assess-key-judgment", "Key judgment", judgment),
        _block(
            "assess-confidence",
            "Confidence",
            "moderate. The type-system argument is direct, but no controlled migration ablation "
            "exists.",
        ),
        _block(
            "assess-evidence-1",
            "Supporting evidence",
            "- Current acceptance failures cluster around illegal intermediate states and "
            "stale-policy transitions.\n- Existing Rust components prevent construction of "
            "several invalid states that remain runtime checks in Python.",
        ),
        _block(
            "assess-contrary",
            "Contrary evidence",
            "The Python implementation supports faster iteration and mature integration "
            "coverage as of revision 2026-08-03.",
        ),
        _block(
            "assess-alternative",
            "Live alternatives",
            "Whether a smaller typed Python kernel or generated transition layer captures enough "
            "of the benefit at lower migration cost remains unresolved.",
        ),
        _block(
            "assess-assumption",
            "Assumptions",
            "The transition model will remain substantially stable during the migration; if it "
            "does not, the port could encode uncertainty rather than remove it.",
        ),
        _block("assess-boundary", "Boundary", boundary),
        _block(
            "assess-update-indicator",
            "Update indicators",
            "Downgrade the assessment if the prototype doubles change lead time or requires "
            "frequent unsafe escape hatches.",
        ),
        _block(
            "assess-recommendation",
            "Recommendation",
            "Prototype one closed transition family before authorizing a broad migration.",
        ),
    ]
    return "\n".join(parts)


def block_metadata(*, alter_p0: bool) -> dict[str, dict[str, Any]]:
    boundary_rendered = (
        "The assessment also covers the policy-fluid orchestration plane."
        if alter_p0
        else "The assessment does not apply to the policy-fluid orchestration plane."
    )
    return {
        "assess-question": {
            "display_role": "question",
            "section_id": "assessment",
            "material": False,
            "profile": "ASSESS",
        },
        "assess-key-judgment": {
            "display_role": "key_judgment",
            "section_id": "assessment",
            "material": True,
            "profile": "ASSESS",
            "claim_ids": ["c1"],
            "p0_fields": [
                {
                    "field_ref": "c1.force.likelihood.term",
                    "ir_pointer": "/sections/0/claims/0/force/likelihood/term",
                    "rendered": "likely",
                }
            ],
        },
        "assess-confidence": {
            "display_role": "confidence",
            "section_id": "assessment",
            "material": True,
            "profile": "ASSESS",
            "claim_ids": ["c1"],
            "p0_fields": [
                {
                    "field_ref": "c1.force.assessment_confidence.level",
                    "ir_pointer": "/sections/0/claims/0/force/assessment_confidence/level",
                    "rendered": "moderate",
                }
            ],
        },
        "assess-evidence-1": {
            "display_role": "supporting_evidence",
            "section_id": "assessment",
            "material": True,
            "profile": "ASSESS",
            "evidence_ids": ["e1", "e2"],
            "relation_ids": ["rel1", "rel2"],
            "p1_relations": [
                {"relation_id": "rel1", "type": "supports", "direction": "source_to_target"},
                {"relation_id": "rel2", "type": "supports", "direction": "source_to_target"},
            ],
        },
        "assess-contrary": {
            "display_role": "contrary_evidence",
            "section_id": "assessment",
            "material": True,
            "profile": "ASSESS",
            "evidence_ids": ["e3"],
            "relation_ids": ["rel5"],
            "p1_relations": [
                {"relation_id": "rel5", "type": "qualifies", "direction": "source_to_target"}
            ],
        },
        "assess-alternative": {
            "display_role": "alternatives",
            "section_id": "assessment",
            "material": True,
            "profile": "ASSESS",
            "claim_ids": ["alt1"],
            "relation_ids": ["rel6"],
            "p1_relations": [
                {"relation_id": "rel6", "type": "alternative_to", "direction": "source_to_target"}
            ],
        },
        "assess-assumption": {
            "display_role": "assumption",
            "section_id": "assessment",
            "material": True,
            "profile": "ASSESS",
            "claim_ids": ["a1"],
            "relation_ids": ["rel3"],
            "p1_relations": [
                {"relation_id": "rel3", "type": "condition_for", "direction": "source_to_target"}
            ],
        },
        "assess-boundary": {
            "display_role": "boundary",
            "section_id": "assessment",
            "material": True,
            "profile": "ASSESS",
            "claim_ids": ["b1"],
            "relation_ids": ["rel4"],
            "p0_fields": [
                {
                    "field_ref": "b1.proposition",
                    "ir_pointer": "/sections/0/claims/2/proposition",
                    "rendered": boundary_rendered,
                }
            ],
            "p1_relations": [
                {"relation_id": "rel4", "type": "qualifies", "direction": "source_to_target"}
            ],
        },
        "assess-update-indicator": {
            "display_role": "update_indicator",
            "section_id": "assessment",
            "material": True,
            "profile": "ASSESS",
            "update_indicator_ids": ["u1"],
        },
        "assess-recommendation": {
            "display_role": "recommendation",
            "section_id": "assessment",
            "material": True,
            "profile": "ASSESS",
            "claim_ids": ["r1"],
        },
    }


def build_bundle(
    ctx: Context, ir_document: dict[str, Any], policy_document: dict[str, Any], *, broken: bool
) -> dict[str, str]:
    ir = IrDocument.from_document(ir_document)
    policy = ctx.policy(policy_document)
    text = render_document(drop_inline_range=broken, alter_p0=broken)
    raw = text.encode("utf-8")
    parsed = parse_markdown(text)
    trace = build_trace(
        ctx,
        ir=ir,
        parsed=parsed,
        output_bytes=raw,
        policy_snapshot_id=policy.snapshot_id,
        policy_sha256=policy.declared_sha256,
        block_metadata=block_metadata(alter_p0=broken),
        renderer={
            "name": "ats-assess-output",
            "version": __version__,
            "skill_id": "skills/ats-assess-output",
        },
    )
    report = lint_output(
        ctx,
        output_path=_temp_write(raw),
        trace_document=trace,
        ir_document=ir_document,
        policy_document=policy_document,
    )
    receipt = build_candidate_receipt(
        ctx,
        ir=ir,
        policy=policy,
        output_sha256=sha256_hex(raw),
        lint_report=report,
        adjudicator=ADJUDICATOR,
    )
    return {
        "document.md": text,
        "document.trace.json": json.dumps(trace, indent=2, ensure_ascii=False) + "\n",
        "document.lint.json": json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        "document.receipt.json": json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
    }


_TEMP: list[Path] = []


def _temp_write(raw: bytes) -> Path:
    import tempfile

    handle = tempfile.NamedTemporaryFile(suffix=".md", delete=False)
    handle.write(raw)
    handle.close()
    path = Path(handle.name)
    _TEMP.append(path)
    return path


def build() -> dict[Path, str]:
    ctx = Context.load(now=FIXED_NOW)
    ir_document = load_json(REPO_ROOT / "fixtures" / "ir" / "valid" / "assess_conforming.json")
    policy_document = load_json(REPO_ROOT / "fixtures" / "policies" / "assess.json")
    files: dict[Path, str] = {}
    for name, broken in (("assess-bundle", False), ("assess-broken", True)):
        for filename, content in build_bundle(
            ctx, ir_document, policy_document, broken=broken
        ).items():
            files[OUTPUT / name / filename] = content
    for path in _TEMP:
        path.unlink(missing_ok=True)
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
            print("stale output fixtures: " + ", ".join(sorted(stale)), file=sys.stderr)
            return 1
        print(f"{len(files)} output-bundle files are current")
        return 0
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"wrote {len(files)} files under {OUTPUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

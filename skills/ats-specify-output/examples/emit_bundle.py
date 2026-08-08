#!/usr/bin/env python3
"""Emit the worked `SPECIFY` output bundle in ``examples/specify-bundle/``.

This is the runnable form of the procedure in ``../SKILL.md``. It renders
``fixtures/ir/valid/specify_conforming.json`` under
``fixtures/policies/specify.json`` and writes the four-file bundle:
``document.md``, ``document.trace.json``, ``document.lint.json``, and
``document.receipt.json``.

Run from anywhere:

    cd <ats-repo>
    PYTHONPATH=src .venv/bin/python skills/ats-specify-output/examples/emit_bundle.py

Add ``--check`` to verify the committed bundle still reproduces byte-for-byte
instead of rewriting it.

Nothing here invents content. Every rendered sentence comes from a slot of
``REQ-POLICY-017``; every ``p0_fields`` entry names the JSON Pointer it came
from and renders that value verbatim; the adjudicator is an authority outside
this workflow, because Sections 13.7 and 14.11 forbid a component from
adjudicating its own output.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ats import __version__  # noqa: E402
from ats.canonical import load_json, sha256_hex  # noqa: E402
from ats.context import Context  # noqa: E402
from ats.ir.model import IrDocument  # noqa: E402
from ats.output.lint import lint_output  # noqa: E402
from ats.output.parse import parse_markdown  # noqa: E402
from ats.output.receipt import build_candidate_receipt  # noqa: E402
from ats.output.trace import build_trace  # noqa: E402

BUNDLE = Path(__file__).resolve().parent / "specify-bundle"
IR_PATH = REPO_ROOT / "fixtures" / "ir" / "valid" / "specify_conforming.json"
POLICY_PATH = REPO_ROOT / "fixtures" / "policies" / "specify.json"

#: Pinned so the bundle, its report, and its receipt replay byte-for-byte
#: (spec Section 16.2). A receipted run never reads the wall clock.
FIXED_NOW = dt.datetime(2026, 8, 3, tzinfo=dt.UTC)

#: An external acceptance authority. Section 13.7 forbids a component from
#: becoming the authoritative adjudicator for its own finding, and Section
#: 14.11 assigns final semantic acceptance to an authorized human or an
#: explicitly governed external acceptance system.
ADJUDICATOR = "arq-acceptance-authority"

#: JSON Pointer prefix for REQ-POLICY-017's requirement slots. Pointers address
#: array indices, not ids (RFC 6901).
REQ = "/sections/0/claims/0/requirement"


def block(marker: str, heading: str, body: str) -> str:
    """A heading, a blank line, the marker on its own line, then the body.

    Copied from ``fixtures/output/assess-bundle/document.md``: the marker sits
    between the heading and its prose, with a blank line above it and none
    below. The marker is an HTML comment, so it is invisible in every ordinary
    Markdown viewer and deterministic for the linter (spec Section 14.4).
    """
    return f"## {heading}\n\n<!-- ats:block {marker} -->\n{body}\n"


def render_document() -> str:
    """Render REQ-POLICY-017 in §9.3.5 canonical statement order.

    Four blocks: the normative requirement, its acceptance criterion, its
    source authority, and its rationale. Section 9.3.16 requires the rationale
    to be structurally distinguishable from normative text, which the separate
    heading and ``display_role: rationale`` both establish.
    """
    parts = ["# Stale-policy rejection\n"]
    parts.append(
        block(
            "specify-req-policy-017",
            "Requirement REQ-POLICY-017",
            # [trigger] [condition] <actor> <DEONTIC> <action> <object> [timing]
            "REQ-POLICY-017: When the executor presents an acceptance receipt and the "
            "receipt policy_sha256 differs from the current resolved policy snapshot, the "
            "verifier MUST reject the acceptance receipt before the acceptance transition.",
        )
    )
    parts.append(
        block(
            "specify-acceptance-criterion",
            "Acceptance criterion",
            "A stale-policy fixture returns refused_stale_policy, emits no accepted "
            "transition, and records both policy hashes.",
        )
    )
    parts.append(
        block(
            "specify-authority",
            "Source authority",
            "The obligation is imposed by the Arq acceptance-policy kernel.",
        )
    )
    parts.append(
        block(
            "specify-rationale",
            "Rationale (non-normative)",
            "A receipt proves conformance only under the policy used to evaluate it. This "
            "paragraph is rationale and creates no obligation.",
        )
    )
    return "\n".join(parts)


def block_metadata() -> dict[str, dict[str, Any]]:
    """What each block realizes, and every P0 value it prints.

    ``OUT-DEONTIC-KEYWORDS`` requires any block declaring ``requirement_ids``
    to render an uppercase ATS-1 deontic keyword, so only the normative block
    declares them; the acceptance-criterion and authority blocks reference the
    claim through ``claim_ids`` instead.
    """
    return {
        "specify-req-policy-017": {
            "display_role": "requirement",
            "section_id": "requirement",
            "profile": "SPECIFY",
            "material": True,
            "claim_ids": ["REQ-POLICY-017"],
            "requirement_ids": ["REQ-POLICY-017"],
            "p0_fields": [
                # Requirement identifiers are P0 (Section 11.3.1). Identifier-class
                # P0 fields are exempt from the units check but still verified
                # byte-for-byte by OUT-P0-EXACT.
                {
                    "field_ref": "REQ-POLICY-017.requirement.requirement_id",
                    "ir_pointer": f"{REQ}/requirement_id",
                    "rendered": "REQ-POLICY-017",
                },
                {
                    "field_ref": "REQ-POLICY-017.requirement.deontic",
                    "ir_pointer": f"{REQ}/deontic",
                    "rendered": "MUST",
                },
                {
                    "field_ref": "REQ-POLICY-017.requirement.actor",
                    "ir_pointer": f"{REQ}/actor",
                    "rendered": "verifier",
                },
                {
                    "field_ref": "REQ-POLICY-017.requirement.action",
                    "ir_pointer": f"{REQ}/action",
                    "rendered": "reject",
                },
                {
                    "field_ref": "REQ-POLICY-017.requirement.object",
                    "ir_pointer": f"{REQ}/object",
                    "rendered": "acceptance receipt",
                },
                {
                    "field_ref": "REQ-POLICY-017.requirement.trigger",
                    "ir_pointer": f"{REQ}/trigger",
                    "rendered": "executor presents an acceptance receipt",
                },
                {
                    "field_ref": "REQ-POLICY-017.requirement.condition",
                    "ir_pointer": f"{REQ}/condition",
                    "rendered": (
                        "receipt policy_sha256 differs from the current resolved policy "
                        "snapshot"
                    ),
                },
                {
                    "field_ref": "REQ-POLICY-017.requirement.timing",
                    "ir_pointer": f"{REQ}/timing",
                    "rendered": "before the acceptance transition",
                },
            ],
        },
        "specify-acceptance-criterion": {
            "display_role": "acceptance_criterion",
            "section_id": "requirement",
            "profile": "SPECIFY",
            "material": True,
            "claim_ids": ["REQ-POLICY-017"],
            "p0_fields": [
                {
                    "field_ref": "REQ-POLICY-017.requirement.acceptance_criterion",
                    "ir_pointer": f"{REQ}/acceptance_criterion",
                    "rendered": (
                        "A stale-policy fixture returns refused_stale_policy, emits no "
                        "accepted transition, and records both policy hashes."
                    ),
                }
            ],
        },
        "specify-authority": {
            "display_role": "authority",
            "section_id": "requirement",
            "profile": "SPECIFY",
            "material": True,
            "claim_ids": ["REQ-POLICY-017"],
            "p0_fields": [
                {
                    "field_ref": "REQ-POLICY-017.requirement.source_authority",
                    "ir_pointer": f"{REQ}/source_authority",
                    "rendered": "Arq acceptance-policy kernel",
                }
            ],
        },
        "specify-rationale": {
            "display_role": "rationale",
            "section_id": "requirement",
            "profile": "SPECIFY",
            "material": False,
        },
    }


def build() -> dict[Path, str]:
    ctx = Context.load(now=FIXED_NOW)
    ir_document = load_json(IR_PATH)
    policy_document = load_json(POLICY_PATH)
    ir = IrDocument.from_document(ir_document)
    policy = ctx.policy(policy_document)

    text = render_document()
    document_path = BUNDLE / "document.md"
    parsed = parse_markdown(text, locator=str(document_path))

    trace = build_trace(
        ctx,
        ir=ir,
        parsed=parsed,
        output_bytes=text.encode("utf-8"),
        policy_snapshot_id=policy.snapshot_id,
        policy_sha256=policy.declared_sha256,
        block_metadata=block_metadata(),
        renderer={
            "name": "ats-specify-output",
            "version": __version__,
            "skill_id": "skills/ats-specify-output",
        },
    )

    # lint_output reads the document from disk, so the bytes must be there first.
    BUNDLE.mkdir(parents=True, exist_ok=True)
    document_path.write_text(text, encoding="utf-8")

    report = lint_output(
        ctx,
        output_path=document_path,
        trace_document=trace,
        ir_document=ir_document,
        policy_document=policy_document,
    )
    receipt = build_candidate_receipt(
        ctx,
        ir=ir,
        policy=policy,
        output_sha256=sha256_hex(text.encode("utf-8")),
        lint_report=report,
        adjudicator=ADJUDICATOR,
    )

    def pretty(obj: Any) -> str:
        return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"

    return {
        document_path: text,
        BUNDLE / "document.trace.json": pretty(trace),
        BUNDLE / "document.lint.json": pretty(report),
        BUNDLE / "document.receipt.json": pretty(receipt),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed bundle reproduces instead of rewriting it",
    )
    args = parser.parse_args()

    files = build()
    if args.check:
        drift = [
            path
            for path, content in files.items()
            if not path.exists() or path.read_text(encoding="utf-8") != content
        ]
        for path in drift:
            print(f"DRIFT {path.relative_to(REPO_ROOT)}")
        if drift:
            return 1
        print(f"OK {len(files)} file(s) reproduce byte-for-byte")
        return 0

    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(REPO_ROOT)}")

    report = json.loads((BUNDLE / "document.lint.json").read_text(encoding="utf-8"))
    print(json.dumps(report["conformance"], indent=2))
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_one(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}: {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> int:
    front = ROOT / "skills/public/ats/SKILL.md"
    replace_one(
        front,
        "9. Acceptance criteria state falsifiable behavior; tests, probes, proofs, and receipts are evidence used to adjudicate them, not substitutes for the criterion.",
        "9. Acceptance evidence is not the same discourse role as the requirement it verifies.",
    )
    replace_one(
        front,
        "10. Ask only when unresolved meaning blocks the requested action.\n\n## How to route",
        "10. Ask only when unresolved meaning blocks the requested action.\n\nDraft.3 `SPECIFY` refinement: an acceptance criterion is the canonical falsifiable behavioral proposition for its REQ. Tests, probes, proofs, and receipts are evidence used to adjudicate that proposition, not substitutes for it; if a materially broken implementation can satisfy the AC, strengthen the AC or decompose the REQ.\n\n## How to route",
    )

    pack = ROOT / "src/ats/skill_pack.py"
    replace_one(pack, '    "new_authoring": "1.0.0-draft.2",', '    "new_authoring": "1.0.0-draft.3",')
    replace_one(
        pack,
        '                f"!= {STANDARD_VERSIONS_SUPPORTED!r} (new authoring must be draft.2)",',
        '                f"!= {STANDARD_VERSIONS_SUPPORTED!r} (new authoring must be {STANDARD_VERSIONS_SUPPORTED[\'new_authoring\']})",',
    )
    old_fn = '''def _stale_draft1_findings(text: str, rel: str) -> list[Finding]:\n    \"\"\"No instruction telling new authoring to use draft.1.\n\n    Matched per line. A \"new authoring … draft.1\" adjacency is legitimate only\n    in the two-default construction, where draft.2 sits between the mentions\n    (new authoring resolves draft.2; legacy stays draft.1); flagging requires\n    the draft.1 mention to be bound to new authoring without an intervening\n    draft.2.\n    \"\"\"\n    findings: list[Finding] = []\n    for match in re.finditer(r\"new(?: durable)? authoring\", text, re.IGNORECASE):\n        window = text[match.end() : match.end() + 200].split(\"\\n\", 1)[0]\n        draft1 = re.search(r\"1\\.0\\.0-draft\\.1\", window)\n        if draft1 and not re.search(r\"1\\.0\\.0-draft\\.2\", window[: draft1.start()]):\n            findings.append(Finding(\"DRAFT1-DEFAULT\", \"language ties new authoring to draft.1\", file=rel))\n    for match in re.finditer(r\"1\\.0\\.0-draft\\.1\", text):\n        window = text[match.end() : match.end() + 200].split(\"\\n\", 1)[0]\n        new_auth = re.search(r\"new(?: durable)? authoring\", window, re.IGNORECASE)\n        if new_auth and not re.search(r\"1\\.0\\.0-draft\\.2\", window[: new_auth.start()]):\n            findings.append(Finding(\"DRAFT1-DEFAULT\", \"language ties new authoring to draft.1\", file=rel))\n    return findings\n'''
    new_fn = '''def _stale_draft1_findings(text: str, rel: str) -> list[Finding]:\n    \"\"\"No instruction telling new authoring to use the legacy draft.1 edition.\n\n    The check is deliberately line-local. Mentioning both defaults on one line is\n    legitimate when that same line also names the currently declared new-authoring\n    edition. This follows STANDARD_VERSIONS_SUPPORTED rather than hardcoding draft.2.\n    \"\"\"\n    findings: list[Finding] = []\n    current = STANDARD_VERSIONS_SUPPORTED[\"new_authoring\"]\n    for line in text.splitlines():\n        if (\n            re.search(r\"new(?: durable)? authoring\", line, re.IGNORECASE)\n            and \"1.0.0-draft.1\" in line\n            and current not in line\n        ):\n            findings.append(\n                Finding(\"DRAFT1-DEFAULT\", \"language ties new authoring to draft.1\", file=rel)\n            )\n    return findings\n'''
    replace_one(pack, old_fn, new_fn)

    tests = ROOT / "tests/unit/test_skill_pack.py"
    replace_one(
        tests,
        '    assert manifest["skill_pack_version"] == SKILL_PACK_VERSION == "0.1.3"',
        '    assert manifest["skill_pack_version"] == SKILL_PACK_VERSION == "0.1.4"',
    )
    replace_one(
        tests,
        '    assert manifest["standard_versions_supported"]["new_authoring"] == "1.0.0-draft.2"',
        '    assert manifest["standard_versions_supported"]["new_authoring"] == "1.0.0-draft.3"',
    )
    replace_one(
        tests,
        '        "New durable authoring** resolves ATS-1 `1.0.0-draft.2`",',
        '        "New durable authoring** resolves ATS-1 `1.0.0-draft.3`",',
    )
    durable_test = '''\n\ndef test_two_default_guard_follows_current_new_authoring_edition() -> None:\n    from ats.skill_pack import _stale_draft1_findings\n\n    assert STANDARD_VERSIONS_SUPPORTED == {\n        "new_authoring": "1.0.0-draft.3",\n        "legacy_interpretation": "1.0.0-draft.1",\n    }\n    legitimate = (\n        "New durable authoring resolves ATS-1 1.0.0-draft.3; "\n        "legacy material stays ATS-1 1.0.0-draft.1."\n    )\n    stale = "New durable authoring uses ATS-1 1.0.0-draft.1."\n    assert _stale_draft1_findings(legitimate, "legitimate.md") == []\n    findings = _stale_draft1_findings(stale, "stale.md")\n    assert [finding.code for finding in findings] == ["DRAFT1-DEFAULT"]\n'''
    text = tests.read_text(encoding="utf-8")
    if "def test_two_default_guard_follows_current_new_authoring_edition" not in text:
        tests.write_text(text + durable_test, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

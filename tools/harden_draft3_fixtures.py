#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "spec" / "ATS-1" / "1.0.0-draft.3"


def main() -> int:
    validator = PKG / "tools" / "validate_package.py"
    text = validator.read_text(encoding="utf-8")
    old = '    assert (ROOT / "examples" / "acceptance_criterion_semantics.md").is_file()\n'
    new = '''    fixture_path = ROOT / "examples" / "acceptance_criterion_semantics.md"\n    assert fixture_path.is_file()\n    fixture_text = fixture_path.read_text(encoding="utf-8")\n    assert "## Conforming" in fixture_text\n    assert "`TestStalePolicyRejection` passes." in fixture_text\n    assert "## Hard negative — non-load-bearing" in fixture_text\n    assert "seven-year audit record" in fixture_text\n'''
    if text.count(old) != 1:
        raise SystemExit(f"fixture-validation anchor count != 1: {text.count(old)}")
    validator.write_text(text.replace(old, new), encoding="utf-8")

    manifest = PKG / "MANIFEST.json"
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    files = []
    for path in sorted(
        p for p in PKG.rglob("*")
        if p.is_file() and p.name != "MANIFEST.json" and not p.name.endswith(".zip")
    ):
        data = path.read_bytes()
        files.append({
            "path": path.relative_to(PKG).as_posix(),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    doc["files"] = files
    manifest.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
pyproject = ROOT / "pyproject.toml"
text = pyproject.read_text(encoding="utf-8")
old = 'version = "0.5.0"'
if text.count(old) != 1:
    raise SystemExit(f"pyproject version anchor count: {text.count(old)}")
pyproject.write_text(text.replace(old, 'version = "0.5.1"'), encoding="utf-8")
lock = ROOT / "uv.lock"
text = lock.read_text(encoding="utf-8")
needle = 'name = "ats"\nversion = "0.5.0"\nsource = { editable = "." }'
if text.count(needle) != 1:
    raise SystemExit(f"uv.lock ats version anchor count: {text.count(needle)}")
lock.write_text(text.replace(needle, 'name = "ats"\nversion = "0.5.1"\nsource = { editable = "." }'), encoding="utf-8")

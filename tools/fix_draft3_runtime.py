#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "spec" / "ATS-1" / "1.0.0-draft.3"
cap = PKG / "capability" / "ats_rule_capability_v1.json"
doc = json.loads(cap.read_text(encoding="utf-8"))
row = next(r for r in doc["rules"] if r["rule_id"] == "ATS-REQ-004")
required = ["text", "profile", "requirement_ir"]
row.update({
    "implemented": False,
    "surfaces": [],
    "detector_class": "D3",
    "decision_power": "undecidable",
    "produces_conformance_evidence": False,
    "authority": "proposal_only",
    "required_inputs": required,
    "available_inputs": [],
    "missing_inputs": required,
    "blocking_inputs": required,
    "unavailable_conditions": ["No ATS-REQ-004 D1/D3 detector or qualified semantic-review surface is implemented in ats 0.5.0."],
    "known_limits": ["The package defines ATS-REQ-004 semantics, but ats 0.5.0 does not adjudicate load-bearing or scope-fidelity conformance. Advisory semantic review remains external."],
    "subchecks": [],
})
cap.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
manifest = PKG / "MANIFEST.json"
m = json.loads(manifest.read_text(encoding="utf-8"))
files = []
for p in sorted(x for x in PKG.rglob("*") if x.is_file() and x.name != "MANIFEST.json" and not x.name.endswith(".zip")):
    b = p.read_bytes()
    files.append({"path": p.relative_to(PKG).as_posix(), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
m["files"] = files
manifest.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

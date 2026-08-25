#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "spec" / "ATS-1" / "1.0.0-draft.3"
cap = PKG / "capability" / "ats_rule_capability_v1.json"
doc = json.loads(cap.read_text(encoding="utf-8"))
doc["implementation_version"] = "0.5.1"
row = next(r for r in doc["rules"] if r["rule_id"] == "ATS-REQ-004")
required = ["text", "profile", "requirement_ir"]
row.clear()
row.update({
    "authority": "conformance_evidence",
    "authority_basis_ref": "docs/AUTHORITY_MODEL.md#ats-ir-rule",
    "available_inputs": required,
    "blocking_inputs": [],
    "decision_power": "detects_violations",
    "detector_class": "D1",
    "detector_name": "ats-ir-ats-req-004",
    "implemented": True,
    "known_limits": [
        "A clean deterministic run does not establish that an AC is load-bearing or fully scope-equivalent; those remain semantic-review questions.",
        "The D1 detector recognises only whole-criterion test/result substitution and hidden uppercase ATS deontics."
    ],
    "missing_inputs": [],
    "produces_conformance_evidence": True,
    "required_inputs": required,
    "rule_id": "ATS-REQ-004",
    "subchecks": [
        {"subcheck_id":"evidence-substituted-for-behavior","decides":False,"spec_ref":"ATS-1 9.3.9 (D-G)","vocabulary_source":"the evidence-instrument examples named by ATS-1 9.3.9 (D-G)","description":"A canonical acceptance criterion consists only of a test/command result rather than an observable behavioral proposition."},
        {"subcheck_id":"acceptance-criterion-hidden-obligation","decides":False,"spec_ref":"ATS-1 9.3.9 (D-G scope-fidelity rule)","vocabulary_source":"the ATS-1 uppercase deontic vocabulary","description":"An acceptance criterion contains an uppercase ATS deontic, indicating normative behavior that belongs in the requirement rather than being introduced by the AC."}
    ],
    "surfaces": ["ir"],
    "unavailable_conditions": ["An artifact with no MUST/MUST NOT requirement acceptance criteria presents nothing to inspect."]
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

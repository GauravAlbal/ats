#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "spec" / "ATS-1" / "1.0.0-draft.2"
DST = ROOT / "spec" / "ATS-1" / "1.0.0-draft.3"
D3 = "1.0.0-draft.3"


def replace_one(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}: {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> int:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    spec = DST / "ATS-1_SPEC.md"
    replace_one(spec, "| Specification version | `1.0.0-draft.2` |", "| Specification version | `1.0.0-draft.3` |")
    replace_one(spec, "- `acceptance_criterion` — observable evidence that determines satisfaction;", "- `acceptance_criterion` — the canonical falsifiable behavioral proposition by which satisfaction or violation of this requirement can be determined;")
    old_ac = """#### 9.3.9 Acceptance criteria\n\nEvery `MUST` and `MUST NOT` requirement MUST have an acceptance criterion or a reference to one.\n\nThe acceptance criterion MUST identify observable evidence. It SHOULD identify the evidence provider, fixture, environment, and threshold.\n\nA statement such as “works correctly” or “is robust” is not an acceptance criterion."""
    new_ac = """#### 9.3.9 Acceptance criteria\n\n> **Draft.3 amendment (D-G):** An acceptance criterion is the canonical falsifiable behavioral proposition for its requirement, not a test invocation or other evidence instrument.\n\nEvery `MUST` and `MUST NOT` requirement MUST have exactly one canonical acceptance criterion, stated inline or uniquely referenced.\n\nAn acceptance criterion MUST express an observable, falsifiable proposition about the behavior, state, invariant, boundary, or result governed by its requirement.\n\nA test name, command, provider invocation, fixture, tool result, exit status, receipt identifier, or other evidence instrument MUST NOT by itself serve as an acceptance criterion.\n\nA canonical acceptance criterion MUST map to exactly one normative requirement. Multiple requirements MAY rely on the same evidence instrument, but MUST NOT share one canonical acceptance criterion.\n\nIf a materially broken implementation that violates the requirement could plausibly satisfy the acceptance criterion as written, the acceptance criterion is nonconforming. The criterion MUST be strengthened or the requirement MUST be decomposed.\n\nAn acceptance criterion MUST NOT add an independently meaningful obligation, broaden the governed scope, or strengthen the deontic force of its requirement. If the desired acceptance proposition requires additional normative behavior, that behavior MUST be specified as a separate requirement or as an explicitly indivisible part of the existing requirement.\n\nEvidence instruments, providers, fixtures, environments, and instrument-specific execution configuration MAY be referenced separately when useful. A threshold or boundary that defines normative satisfaction remains part of the requirement or its acceptance criterion. Evidence details MUST NOT redefine the canonical acceptance criterion unless the requirement itself normatively constrains them.\n\nA statement such as “works correctly,” “is robust,” or `TestFoo passes` is not an acceptance criterion."""
    replace_one(spec, old_ac, new_ac)
    replace_one(spec, "A requirement is verifiable when an authorized reviewer can determine satisfaction from declared evidence without inventing missing thresholds, actors, or conditions.", "A requirement is verifiable when an authorized reviewer can determine whether its canonical acceptance criterion is established or refuted without inventing missing behavior, thresholds, actors, conditions, or boundaries.")
    replace_one(spec, "- each `MUST` and `MUST NOT` has a verifiable acceptance criterion;", "- each `MUST` and `MUST NOT` has exactly one canonical, falsifiable, load-bearing acceptance criterion that does not widen its requirement;")
    req3_row = "| `ATS-REQ-003` | Every applicable requirement slot—scope, trigger, condition, timing, constraint, exception, and acceptance criterion—MUST be explicit or referenced. | Not applicable | Required | D1/D3 |"
    req4_stmt = "Every material MUST or MUST NOT requirement MUST map to exactly one canonical, falsifiable behavioral acceptance criterion. A canonical acceptance criterion MUST NOT be shared across normative requirements, MUST NOT consist solely of an evidence instrument or its result, and MUST NOT add an independently meaningful obligation or strengthen the requirement it adjudicates. If a materially broken implementation can plausibly satisfy the criterion while violating its requirement, the criterion MUST be strengthened or the requirement decomposed."
    replace_one(spec, req3_row, req3_row + "\n| `ATS-REQ-004` | " + req4_stmt + " | Not applicable | Advisory | D1/D3 |")
    replace_one(spec, "The profile validators in Section 9 operate in addition to the text rules (thirty in\ndraft.1; thirty-six in draft.2).", "The profile validators in Section 9 operate in addition to the text rules (thirty in\ndraft.1; thirty-six in draft.2; thirty-seven in draft.3).")
    replace_one(spec, "acceptance_criterion: stale-policy fixture yields refused_stale_policy and no accepted transition", "acceptance_criterion: given a stale policy_sha256, the verifier returns refused_stale_policy and emits no accepted transition")

    rules = DST / "rules" / "ats_rules_v2.yaml"
    replace_one(rules, "spec_version: 1.0.0-draft.2", "spec_version: 1.0.0-draft.3")
    with rules.open("a", encoding="utf-8") as f:
        f.write(f"""\n- schema_version: ats.rule.v1\n  rule_id: ATS-REQ-004\n  operational_class: review_required\n  rule_version: {D3}\n  title: Canonical behavioral acceptance criterion\n  category: requirements\n  normative_statement: >-\n    {req4_stmt}\n  rationale: >-\n    Test-shaped or scope-widening acceptance criteria can respectively pass while the protected behavior remains broken or create hidden requirements. Keeping the normative falsification proposition distinct from its evidence instrument preserves requirement meaning across implementations, test suites, and verification providers.\n  default_states:\n    ASSESS: disabled\n    SPECIFY: advisory\n    TRANSFORM: advisory\n  severity: critical\n  detector_classes:\n  - D1\n  - D3\n  required_inputs:\n  - text\n  - profile\n  - requirement_ir\n  protected_impact:\n  - P0\n  - P1\n  autofix: review_required\n  waivable: true\n  exceptions: []\n  fixture_requirements: *id001\n""")

    (DST / "examples" / "acceptance_criterion_semantics.md").write_text("""# ATS-REQ-004 fixtures\n\n## Conforming\nREQ: The verifier MUST reject a stale-policy receipt before acceptance.\nAC: Given a stale policy hash, the verifier returns `refused_stale_policy` and emits no accepted transition.\n\n## Violation — evidence substituted for criterion\nAC: `TestStalePolicyRejection` passes.\n\n## Hard negative — non-load-bearing\nREQ: Only VX MUST determine next-ready work.\nAC: The executor returns success when given W1.\n\n## Violation — scope widening / hidden obligation\nREQ: The verifier MUST reject a stale-policy receipt.\nAC: The verifier rejects the stale receipt and MUST also persist a seven-year audit record.\n""", encoding="utf-8")

    cap = DST / "capability" / "ats_rule_capability_v1.json"
    cap_doc = json.loads(cap.read_text(encoding="utf-8"))
    cap_doc["ats_version"] = D3
    cap_doc["rules"].append({"authority":"proposal_only","available_inputs":[],"blocking_inputs":["semantic_review"],"decision_power":"undecidable","detector_class":"D3","implemented":False,"known_limits":["No complete D3 decision procedure is implemented for the load-bearing or scope-fidelity judgment; structural D1 checks may surface candidate defects but cannot certify absence."],"missing_inputs":["semantic_review"],"produces_conformance_evidence":False,"required_inputs":["text","profile","requirement_ir"],"rule_id":"ATS-REQ-004","subchecks":[],"surfaces":[],"unavailable_conditions":["A qualified semantic review path is not configured."]})
    cap_doc["rules"] = sorted(cap_doc["rules"], key=lambda r: r["rule_id"])
    cap.write_text(json.dumps(cap_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    readme = DST / "README.md"
    replace_one(readme, "version `1.0.0-draft.2`.", "version `1.0.0-draft.3`.")
    replace_one(readme, "the 36-rule draft.2 registry.", "the 37-rule draft.3 registry.")
    with readme.open("a", encoding="utf-8") as f:
        f.write("\n## Draft.3 delta\n\nDraft.3 adds D-G: canonical behavioral acceptance criteria and ATS-REQ-004. Schemas and calibrated-force lexicons are byte-identical to draft.2.\n")

    changelog = DST / "CHANGELOG.md"
    old = changelog.read_text(encoding="utf-8")
    changelog.write_text("# Changelog\n\n## 1.0.0-draft.3 — 2026-08-24\n\n- D-G redefines acceptance criteria as canonical falsifiable behavioral propositions rather than evidence instruments.\n- Adds ATS-REQ-004 as advisory automated enforcement pending a qualified semantic review path.\n- Adds load-bearing and scope-fidelity laws; no schema or force-lexicon changes.\n\n" + old.removeprefix("# Changelog\n\n"), encoding="utf-8")

    validator = DST / "tools" / "validate_package.py"
    replace_one(validator, 'SPEC_VERSION = "1.0.0-draft.2"', 'SPEC_VERSION = "1.0.0-draft.3"')
    replace_one(validator, "EXPECTED_RULE_COUNT = 36", "EXPECTED_RULE_COUNT = 37")
    replace_one(validator, r"the ([0-9]+)-rule draft\.2 registry", r"the ([0-9]+)-rule draft\.3 registry")
    replace_one(validator, 'assert rule["rule_version"] in ("1.0.0-draft.1", "1.0.0-draft.2"), rule["rule_id"]', 'assert rule["rule_version"] in ("1.0.0-draft.1", "1.0.0-draft.2", "1.0.0-draft.3"), rule["rule_id"]')
    old_bump = '''    # Only amended or new rules carry the draft.2 rule_version.\n    bumped = {"ATS-DISC-003", "ATS-COORD-001", "ATS-COORD-002", "ATS-BASIS-001",\n              "ATS-BASIS-002", "ATS-PRES-003", "ATS-CLOSE-001"}\n    for rule in rules:\n        if rule["rule_id"] in bumped:\n            assert rule["rule_version"] == SPEC_VERSION, rule["rule_id"]\n        else:\n            assert rule["rule_version"] == "1.0.0-draft.1", rule["rule_id"]'''
    new_bump = '''    draft2_bumped = {"ATS-DISC-003", "ATS-COORD-001", "ATS-COORD-002", "ATS-BASIS-001",\n                     "ATS-BASIS-002", "ATS-PRES-003", "ATS-CLOSE-001"}\n    draft3_bumped = {"ATS-REQ-004"}\n    for rule in rules:\n        if rule["rule_id"] in draft3_bumped:\n            assert rule["rule_version"] == SPEC_VERSION, rule["rule_id"]\n        elif rule["rule_id"] in draft2_bumped:\n            assert rule["rule_version"] == "1.0.0-draft.2", rule["rule_id"]\n        else:\n            assert rule["rule_version"] == "1.0.0-draft.1", rule["rule_id"]'''
    replace_one(validator, old_bump, new_bump)
    marker = '    spec = (ROOT / "ATS-1_SPEC.md").read_text(encoding="utf-8")\n'
    replace_one(validator, marker, marker + '    assert "Draft.3 amendment (D-G)" in spec\n    assert (ROOT / "examples" / "acceptance_criterion_semantics.md").is_file()\n')

    manifest = DST / "MANIFEST.json"
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["spec_version"] = D3
    doc["generated_at"] = "2026-08-24T00:00:00Z"
    files = []
    for path in sorted(p for p in DST.rglob("*") if p.is_file() and p.name != "MANIFEST.json" and not p.name.endswith(".zip")):
        data = path.read_bytes()
        files.append({"path": path.relative_to(DST).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    doc["files"] = files
    manifest.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    ci = ROOT / ".github" / "workflows" / "public-ci.yml"
    replace_one(ci, "          (cd spec/ATS-1/1.0.0-draft.2 && python tools/validate_package.py)\n", "          (cd spec/ATS-1/1.0.0-draft.2 && python tools/validate_package.py)\n          (cd spec/ATS-1/1.0.0-draft.3 && python tools/validate_package.py)\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

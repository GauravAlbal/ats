#!/usr/bin/env python3
"""Generate ``capability/ats_rule_capability_v1.json`` from the detector declarations.

The capability document is derived, never hand-maintained. A detector that gains
or loses decision power moves the declaration with it, so the two cannot drift
(constitution #5). ``tests/unit/test_capability.py`` asserts the checked-in file
equals what this script produces.

Usage::

    PYTHONPATH=src python tools/generate_capability.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ats import IMPLEMENTATION_NAME, __version__  # noqa: E402
from ats.rules.deterministic import load_detectors  # noqa: E402
from ats.rules.deterministic._support import SPECS  # noqa: E402
from ats.rules.registry import RuleRegistry  # noqa: E402
from ats.schemas import SchemaSet  # noqa: E402
from ats.spec_package import SpecPackage  # noqa: E402

OUTPUT = REPO_ROOT / "capability" / "ats_rule_capability_v1.json"


def build() -> dict:
    package = SpecPackage.load()
    registry = RuleRegistry(package)
    load_detectors()

    # The generator derives the default (draft.1) package's declaration, whose
    # 30-rule registry is a subset of the loaded detector set: the draft.2
    # detectors (ATS-COORD-*, ATS-BASIS-*, ATS-PRES-003, ATS-CLOSE-001) live in
    # the same modules and register their specs for the draft.2 registry, which
    # publishes its own package-relative capability file. Only specs for rules
    # in THIS package's registry are projected here.
    specs = {rid: SPECS[rid] for rid in registry.ids() if rid in SPECS}
    missing = sorted(set(registry.ids()) - set(specs))
    if missing:
        raise SystemExit(f"no detector declared for: {', '.join(missing)}")

    rules = []
    for rule_id in registry.ids():
        spec = specs[rule_id]
        rule = registry.get(rule_id)
        required = rule.required_inputs
        entry = {
            "rule_id": rule_id,
            "implemented": spec.implemented,
            "surfaces": ["ir"] if spec.implemented else [],
            "detector_class": spec.detector_class,
            "decision_power": str(spec.power),
            "produces_conformance_evidence": spec.authority == "conformance_evidence",
            "authority": spec.authority,
            "required_inputs": list(required),
            "available_inputs": list(spec.available_inputs(required)),
            "missing_inputs": list(spec.missing_inputs(required)),
            "blocking_inputs": list(spec.blocking_inputs(required)),
            "unavailable_conditions": list(spec.unavailable_conditions),
            "known_limits": list(spec.known_limits),
            "subchecks": [sc.to_capability() for sc in spec.subchecks],
        }
        if spec.implemented:
            entry["detector_name"] = spec.detector_name
        if spec.authority == "conformance_evidence":
            entry["authority_basis_ref"] = "docs/AUTHORITY_MODEL.md#ats-ir-rule"
        if spec.substitutions:
            entry["input_substitutions"] = [dict(s) for s in spec.substitutions]
        rules.append(entry)

    return {
        "schema_version": "ats.rule_capability.v1",
        "implementation_name": IMPLEMENTATION_NAME,
        "implementation_version": __version__,
        "ats_version": registry.spec_version,
        "rules": rules,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="exit non-zero when the file is stale"
    )
    args = parser.parse_args()

    document = build()
    rendered = json.dumps(document, indent=2, ensure_ascii=False) + "\n"

    package = SpecPackage.load()
    SchemaSet(package).validate(document, "ats_rule_capability_v1.schema.json")

    if args.check:
        if not OUTPUT.is_file():
            print(f"{OUTPUT} does not exist", file=sys.stderr)
            return 1
        if OUTPUT.read_text(encoding="utf-8") != rendered:
            print(f"{OUTPUT} is stale; re-run tools/generate_capability.py", file=sys.stderr)
            return 1
        print(f"{OUTPUT} is current")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    decided = sum(1 for r in document["rules"] if r["decision_power"] == "decides")
    partial = sum(1 for r in document["rules"] if r["decision_power"] == "detects_violations")
    none = sum(1 for r in document["rules"] if r["decision_power"] == "undecidable")
    print(
        f"wrote {OUTPUT.relative_to(REPO_ROOT)}: {len(document['rules'])} rules "
        f"({decided} decides, {partial} detects_violations, {none} undecidable)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate the TextIR fixtures under ``fixtures/ir/``.

Fixtures are derived, not hand-copied. Each one starts from a worked example in
``ATS-1_SPEC.md`` Section 21 or from the normative package's own example, then
applies one named mutation that violates exactly one rule. That keeps the
"conforming" and "violation" twins genuinely paired: they differ in one field,
so a test that passes on one and fails on the other is testing the rule and not
an incidental difference.

Usage::

    PYTHONPATH=src python tools/generate_ir_fixtures.py [--check]
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ats.hashes import bind_text  # noqa: E402
from ats.schemas import SchemaSet  # noqa: E402
from ats.spec_package import SpecPackage  # noqa: E402

FIXTURES = REPO_ROOT / "fixtures" / "ir"
SOURCES = FIXTURES / "sources"

# The Section 21.1 conforming ASSESS artifact, verbatim from ATS-1_SPEC.md.
ASSESS_SOURCE = """Question
Should Arq move the acceptance kernel from Python to Rust after the state model stabilizes?

Key judgment
A Rust migration is likely (55-80%) to reduce invalid-state defects in the acceptance kernel after the transition model is stable.

Confidence
Moderate. Rust can encode closed transitions and construction invariants directly, but the current evidence is architectural and observational rather than a controlled migration ablation.

Supporting evidence
1. Current acceptance failures cluster around illegal intermediate states and stale-policy transitions.
2. Existing Rust components have prevented several construction-time invalid states that remain runtime checks in Python.

Contrary evidence and alternatives
The Python implementation has fast iteration and mature integration coverage.

Assumptions
The state model will remain substantially stable after the current envelope-expansion work.

Boundary
This assessment applies to the acceptance kernel.

Update indicators
Downgrade the likelihood if the prototype doubles iteration time over three representative changes.

Recommendation
Prototype one closed transition family in Rust before authorizing a broad migration.
"""

# The Section 21.3 conforming SPECIFY artifact, verbatim from ATS-1_SPEC.md.
SPECIFY_SOURCE = """Requirement ID: REQ-POLICY-017

Statement
When the executor presents an acceptance receipt whose policy_sha256 differs from the current resolved policy snapshot, the verifier MUST reject the receipt before the acceptance transition.

Acceptance criterion
Given a receipt with a stale policy_sha256, the verifier returns refused_stale_policy, emits no accepted-change transition, and records the current and presented policy hashes in the rejection receipt.

Authority
Arq acceptance-policy kernel.

Exception
None.
"""


def _bind(document: dict[str, Any], source_name: str, text: str) -> dict[str, Any]:
    """Point a document's source at a real fixture file and bind its hashes."""
    binding = bind_text(text)
    document["source"] = {
        "content_sha256": binding.content_sha256,
        "normalized_sha256": binding.normalized_sha256,
        "media_type": "text/plain",
        "locator": f"fixtures/ir/sources/{source_name}",
    }
    return document


def base_assess(package: SpecPackage) -> dict[str, Any]:
    doc = copy.deepcopy(package.example("assess_text_ir_example.json"))
    doc["artifact_id"] = "fixture-assess-rust-kernel"
    return _bind(doc, "assess_rust_kernel.txt", ASSESS_SOURCE)


def base_specify(package: SpecPackage) -> dict[str, Any]:
    doc = copy.deepcopy(package.example("specify_text_ir_example.json"))
    doc["artifact_id"] = "fixture-specify-stale-policy"
    doc["policy_snapshot_id"] = "policy-fixture-specify"
    return _bind(doc, "specify_stale_policy.txt", SPECIFY_SOURCE)


def _claim(doc: dict[str, Any], claim_id: str) -> dict[str, Any]:
    for section in doc["sections"]:
        for claim in section["claims"]:
            if claim["claim_id"] == claim_id:
                return claim
    raise KeyError(claim_id)


# -- valid documents --------------------------------------------------------


def valid_documents(package: SpecPackage) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {
        "assess_conforming.json": base_assess(package),
        "specify_conforming.json": base_specify(package),
    }

    composed = base_assess(package)
    composed["artifact_id"] = "fixture-composed-profiles"
    composed["policy_snapshot_id"] = "policy-fixture-composed"
    specify_section = copy.deepcopy(base_specify(package)["sections"][0])
    specify_section["section_id"] = "adoption-requirement"
    composed["sections"].append(specify_section)
    composed["glossary"].extend(base_specify(package)["glossary"])
    out["composed_profiles.json"] = composed

    transformed = base_assess(package)
    transformed["artifact_id"] = "fixture-assess-transform-output"
    transformed["policy_snapshot_id"] = "policy-fixture-assess-transform"
    # A transformation output: the section carries TRANSFORM alongside its
    # content profile (spec 11.1), which activates ATS-PRES-001 and
    # ATS-PRES-002 and therefore makes preservation UNAVAILABLE rather than
    # NOT_APPLICABLE (spec 6.4, 15.4).
    transformed["sections"][0]["profiles"] = ["ASSESS", "TRANSFORM"]
    out["assess_transform_output.json"] = transformed

    partial = base_assess(package)
    partial["artifact_id"] = "fixture-assess-partial-extraction"
    partial["extraction_status"] = "partial"
    partial["extraction_issues"] = [
        {
            "issue_id": "missing-alternatives",
            "status": "partial",
            "description": (
                "The source states that alternatives exist but does not enumerate them, so no "
                "alternative claim could be constructed without inventing content."
            ),
            "affected_fields": ["sections/0/claims/c1/alternatives"],
        }
    ]
    out["assess_partial_extraction.json"] = partial

    ambiguous = base_assess(package)
    ambiguous["artifact_id"] = "fixture-assess-represented-ambiguity"
    ambiguous["extraction_status"] = "ambiguous"
    ambiguous["extraction_issues"] = [
        {
            "issue_id": "scope-of-migration",
            "status": "ambiguous",
            "description": "The source does not resolve whether 'kernel' includes the policy plane.",
            "affected_fields": ["sections/0/claims/c1/scope/system"],
            "candidate_interpretations": [
                "The acceptance kernel only.",
                "The acceptance kernel together with the policy-fluid orchestration plane.",
            ],
        }
    ]
    target = _claim(ambiguous, "c1")
    target["status"] = "ambiguous"
    target["interpretations"] = [
        "The migration covers the acceptance kernel only.",
        "The migration covers the acceptance kernel and the policy-fluid orchestration plane.",
    ]
    out["assess_represented_ambiguity.json"] = ambiguous
    return out


# -- invalid documents ------------------------------------------------------


def _duplicate_ids(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-duplicate-ids"
    section = doc["sections"][0]
    clone = copy.deepcopy(section["claims"][1])
    clone["proposition"] = "A second claim reusing an existing identifier."
    section["claims"].append(clone)
    return doc


def _dangling_reference(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-dangling-reference"
    _claim(doc, "c1")["source_refs"] = ["e1", "e-does-not-exist"]
    return doc


def _wep_interval(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-wep-interval"
    _claim(doc, "c1")["force"]["likelihood"]["upper"] = 0.95
    return doc


def _noncanonical_synonym(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-noncanonical-synonym"
    claim = _claim(doc, "c1")
    claim["proposition"] = (
        "A Rust migration is probable to reduce invalid-state defects in the acceptance kernel "
        "after the transition model is stable."
    )
    return doc


def _possibility_only(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-possibility-only"
    claim = _claim(doc, "c1")
    claim["proposition"] = (
        "A Rust migration might reduce invalid-state defects in the acceptance kernel."
    )
    del claim["force"]["likelihood"]
    return doc


def _blank_confidence_basis(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-blank-confidence-basis"
    _claim(doc, "c1")["force"]["assessment_confidence"]["basis"]["rationale"] = "   "
    return doc


def _no_update_indicator(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-no-update-indicator"
    doc["sections"][0]["update_indicators"] = []
    return doc


def _observation_with_confidence(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-observation-with-confidence"
    claim = _claim(doc, "c1")
    claim["role"] = "observation"
    return doc


def _ambiguous_without_distinct(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-ambiguous-not-distinct"
    doc["extraction_status"] = "ambiguous"
    doc["extraction_issues"] = [
        {
            "issue_id": "unresolved-scope",
            "status": "ambiguous",
            "description": "Scope is unresolved.",
            "candidate_interpretations": ["The kernel.", "The kernel."],
        }
    ]
    claim = _claim(doc, "c1")
    claim["status"] = "ambiguous"
    claim["interpretations"] = ["The kernel only.", "The kernel only."]
    return doc


def _reserved_profile(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-reserved-profile"
    doc["sections"][0]["profiles"] = ["X-ARQ-EXPLAIN-1"]
    return doc


def _unanchored_relative_time(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-unanchored-relative-time"
    claim = _claim(doc, "c1")
    claim["proposition"] = (
        "A Rust migration is likely (55-80%) to reduce invalid-state defects soon."
    )
    claim["scope"] = {"system": "Arq acceptance kernel"}
    return doc


def _missing_acceptance_criterion(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-missing-acceptance-criterion"
    del _claim(doc, "REQ-POLICY-017")["requirement"]["acceptance_criterion"]
    return doc


def _concealed_actor(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-concealed-actor"
    _claim(doc, "REQ-POLICY-017")["requirement"]["actor"] = "the system"
    return doc


def _two_obligations(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-two-obligations"
    _claim(doc, "REQ-POLICY-017")["requirement"]["action"] = "reject and record an audit event"
    return doc


def _noncanonical_modal(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-noncanonical-modal"
    claim = _claim(doc, "REQ-POLICY-017")
    claim["proposition"] = claim["proposition"].replace("MUST", "SHALL")
    return doc


def _should_without_override(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-should-without-override"
    claim = _claim(doc, "REQ-POLICY-017")
    claim["proposition"] = claim["proposition"].replace("MUST", "SHOULD")
    claim["force"]["deontic"] = "SHOULD"
    requirement = claim["requirement"]
    requirement["deontic"] = "SHOULD"
    requirement["exceptions"] = []
    requirement.pop("rationale", None)
    return doc


def _quantifier_without_unit(doc: dict[str, Any]) -> dict[str, Any]:
    doc["artifact_id"] = "fixture-invalid-quantifier-without-unit"
    claim = _claim(doc, "REQ-POLICY-017")
    claim["quantifier"] = {"kind": "maximum", "value": 500}
    return doc


ASSESS_INVALID: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "duplicate_ids.json": _duplicate_ids,
    "dangling_reference.json": _dangling_reference,
    "wep_interval_mismatch.json": _wep_interval,
    "noncanonical_wep_synonym.json": _noncanonical_synonym,
    "possibility_term_only.json": _possibility_only,
    "blank_confidence_basis.json": _blank_confidence_basis,
    "no_update_indicator.json": _no_update_indicator,
    "observation_with_confidence.json": _observation_with_confidence,
    "ambiguous_without_distinct_readings.json": _ambiguous_without_distinct,
    "reserved_profile.json": _reserved_profile,
    "unanchored_relative_time.json": _unanchored_relative_time,
}

SPECIFY_INVALID: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "missing_acceptance_criterion.json": _missing_acceptance_criterion,
    "concealed_actor.json": _concealed_actor,
    "two_obligations.json": _two_obligations,
    "noncanonical_modal.json": _noncanonical_modal,
    "should_without_override.json": _should_without_override,
    "quantifier_without_unit.json": _quantifier_without_unit,
}


def build() -> dict[Path, str]:
    package = SpecPackage.load()
    schemas = SchemaSet(package)
    files: dict[Path, str] = {
        SOURCES / "assess_rust_kernel.txt": ASSESS_SOURCE,
        SOURCES / "specify_stale_policy.txt": SPECIFY_SOURCE,
    }

    for name, document in valid_documents(package).items():
        schemas.validate(document, "ats_text_ir_v1.schema.json")
        files[FIXTURES / "valid" / name] = json.dumps(document, indent=2, ensure_ascii=False) + "\n"

    for name, mutate in ASSESS_INVALID.items():
        document = mutate(base_assess(package))
        files[FIXTURES / "invalid" / name] = (
            json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        )
    for name, mutate in SPECIFY_INVALID.items():
        document = mutate(base_specify(package))
        files[FIXTURES / "invalid" / name] = (
            json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        )
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
            print("stale fixtures: " + ", ".join(sorted(stale)), file=sys.stderr)
            return 1
        print(f"{len(files)} IR fixtures are current")
        return 0

    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"wrote {len(files)} IR fixture files under {FIXTURES.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

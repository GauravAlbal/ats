#!/usr/bin/env python3
"""Offline structural and cross-object coherence validator for ATS-1 draft.2.

Extends the draft.1 validator (same checks, same discipline) with the draft.2
surface: the 36-rule registry (30 carried + 6 new), the new examples, the
stable-coordinate resolution check, the migration-table cross-check, and the
operational-class obligation.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
SPEC_VERSION = "1.0.0-draft.3"
REGISTRY_RELATIVE_PATH = Path("rules/ats_rules_v2.yaml")
EXPECTED_RULE_COUNT = 37
#: The repo's migration document, cross-checked against the spec amendment markers.
MIGRATION_DOC = ROOT.parents[2] / "docs" / "ATS_1_DRAFT_2_MIGRATION.md"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def jcs_subset_bytes(value: Any) -> bytes:
    """Exact RFC 8785 bytes for the integral/string subset used by hash examples."""
    def render(v: Any) -> str:
        if v is None:
            return "null"
        if v is True:
            return "true"
        if v is False:
            return "false"
        if isinstance(v, int):
            if not (-(2**53) + 1 <= v <= (2**53) - 1):
                raise AssertionError(f"integer outside interoperable JCS range: {v}")
            return str(v)
        if isinstance(v, float):
            raise AssertionError("hash example uses float; install/use a complete RFC 8785 implementation")
        if isinstance(v, str):
            if any(0xD800 <= ord(ch) <= 0xDFFF for ch in v):
                raise AssertionError("unpaired surrogate is invalid JCS input")
            return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        if isinstance(v, list):
            return "[" + ",".join(render(x) for x in v) + "]"
        if isinstance(v, dict):
            assert all(isinstance(k, str) for k in v), "JCS object key is not a string"
            keys = sorted(v, key=lambda s: s.encode("utf-16be"))
            return "{" + ",".join(render(k) + ":" + render(v[k]) for k in keys) + "}"
        raise AssertionError(f"unsupported JCS value: {type(v)!r}")

    return render(value).encode("utf-8")


def canonical_hash(obj: dict[str, Any], excluded: set[str]) -> str:
    material = {k: v for k, v in obj.items() if k not in excluded}
    return hashlib.sha256(jcs_subset_bytes(material)).hexdigest()


def build_registry(schemas: list[dict[str, Any]]) -> Registry:
    resources = []
    for schema in schemas:
        if "$id" in schema:
            resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def validate_instance(instance: Any, schema: dict[str, Any], registry: Registry, label: str) -> None:
    errors = sorted(
        Draft202012Validator(
            schema,
            registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ).iter_errors(instance),
        key=lambda e: list(e.absolute_path),
    )
    if errors:
        rendered = "\n".join(f"  - {list(e.absolute_path)}: {e.message}" for e in errors)
        raise AssertionError(f"{label} validation failed:\n{rendered}")


def assert_package_edition_metadata(manifest: dict[str, Any]) -> None:
    """Reject contradictory edition markers across the package's public surface."""
    expected = manifest["spec_version"]
    assert expected == SPEC_VERSION, (
        f"manifest spec_version must be {SPEC_VERSION}, got {expected!r}"
    )

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_match = re.search(r"(?m)^This directory .* version `([^`]+)`\.$", readme)
    assert readme_match, "README edition marker missing"
    assert readme_match.group(1) == expected, (
        f"README edition marker contradicts manifest: {readme_match.group(1)!r} != {expected!r}"
    )
    registry_match = re.search(
        r"(?m)^- `([^`]+)` — the ([0-9]+)-rule draft\.3 registry\.$", readme
    )
    assert registry_match, "README registry path/count marker missing"
    assert registry_match.group(1) == REGISTRY_RELATIVE_PATH.as_posix(), (
        f"README registry path contradicts validator: {registry_match.group(1)!r}"
    )
    assert int(registry_match.group(2)) == EXPECTED_RULE_COUNT, (
        f"README registry count contradicts validator: {registry_match.group(2)!r}"
    )

    spec = (ROOT / "ATS-1_SPEC.md").read_text(encoding="utf-8")
    spec_match = re.search(
        r"(?m)^\| Specification version \| `([^`]+)` \|$", spec
    )
    assert spec_match, "ATS-1_SPEC specification-version metadata missing"
    assert spec_match.group(1) == expected, (
        f"ATS-1_SPEC metadata contradicts manifest: {spec_match.group(1)!r} != {expected!r}"
    )
    assert (
        f"- `{REGISTRY_RELATIVE_PATH.as_posix()}` — normative rule registry and default rule states;"
        in spec
    ), "ATS-1_SPEC normative registry path marker missing or contradictory"
    assert (
        f"The machine-readable registry is in `{REGISTRY_RELATIVE_PATH.as_posix()}`."
        in spec
    ), "ATS-1_SPEC machine-readable registry path marker missing or contradictory"

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    changelog_match = re.search(
        r"(?m)^##\s+([0-9]+\.[0-9]+\.[0-9]+-draft\.[0-9]+)\s+—"
        r"\s+[0-9]{4}-[0-9]{2}-[0-9]{2}\s*$",
        changelog,
    )
    assert changelog_match, "latest changelog edition marker missing"
    assert changelog_match.group(1) == expected, (
        f"latest changelog edition contradicts manifest: "
        f"{changelog_match.group(1)!r} != {expected!r}"
    )

    registry_path = ROOT / REGISTRY_RELATIVE_PATH
    assert registry_path.is_file(), f"registry missing: {REGISTRY_RELATIVE_PATH}"


def assert_text_ir_references(ir: dict[str, Any]) -> None:
    ids: set[str] = set()
    claims: dict[str, dict[str, Any]] = {}
    evidence_ids: set[str] = set()
    relation_ids: set[str] = set()
    indicator_ids: set[str] = set()

    for section in ir["sections"]:
        for claim in section["claims"]:
            cid = claim["claim_id"]
            assert cid not in ids, f"duplicate TextIR id: {cid}"
            ids.add(cid)
            claims[cid] = claim
        for evidence in section["evidence"]:
            eid = evidence["evidence_id"]
            assert eid not in ids, f"duplicate TextIR id: {eid}"
            ids.add(eid)
            evidence_ids.add(eid)
        for relation in section["relations"]:
            rid = relation["relation_id"]
            assert rid not in ids, f"duplicate TextIR id: {rid}"
            ids.add(rid)
            relation_ids.add(rid)
        for indicator in section["update_indicators"]:
            iid = indicator["indicator_id"]
            assert iid not in ids, f"duplicate TextIR id: {iid}"
            ids.add(iid)
            indicator_ids.add(iid)

    referents = set(claims) | evidence_ids
    for section in ir["sections"]:
        for claim in section["claims"]:
            for ref in claim.get("source_refs", []):
                assert ref in evidence_ids, f"claim {claim['claim_id']} has unknown evidence ref {ref}"
            for field in ("assumption_refs", "boundary_refs", "exception_refs"):
                for ref in claim.get(field, []):
                    assert ref in claims, f"claim {claim['claim_id']} has unknown {field} ref {ref}"
            if claim["role"] == "requirement":
                assert claim["requirement"]["requirement_id"] == claim["claim_id"], (
                    f"requirement id does not match claim id: {claim['claim_id']}"
                )
        for relation in section["relations"]:
            assert relation["source_id"] in referents, f"unknown relation source {relation['source_id']}"
            assert relation["target_id"] in referents, f"unknown relation target {relation['target_id']}"
        for indicator in section["update_indicators"]:
            for ref in indicator["target_claim_refs"]:
                assert ref in claims, f"unknown update-indicator target {ref}"


def assert_stable_coordinates(ir: dict[str, Any]) -> None:
    """Draft.2: when stable_coordinates is declared, every coordinate resolves and
    every protected coordinate used in the document is declared."""
    block = ir.get("stable_coordinates")
    if not block:
        return
    declared: dict[str, str] = {}
    for entry in block:
        cid = entry["id"]
        assert cid not in declared, f"duplicate stable coordinate {cid}"
        declared[cid] = entry["kind"]

    used: set[str] = set()
    for section in ir["sections"]:
        for claim in section["claims"]:
            if claim["role"] == "requirement":
                req = claim.get("requirement") or {}
                used.add(req.get("requirement_id", claim["claim_id"]))
                if req.get("acceptance_criterion_id"):
                    used.add(req["acceptance_criterion_id"])
            if claim.get("decision_id"):
                used.add(claim["decision_id"])
        for relation in section["relations"]:
            if relation.get("dependency_target"):
                used.add(relation["dependency_target"])
    for cid in used:
        assert cid in declared, (
            f"stable coordinate {cid} is used but not declared in stable_coordinates"
        )
    # Every declared coordinate resolves into the document's own id space.
    document_ids: set[str] = set()
    for section in ir["sections"]:
        for claim in section["claims"]:
            document_ids.add(claim["claim_id"])
            req = claim.get("requirement") or {}
            if req.get("requirement_id"):
                document_ids.add(req["requirement_id"])
            if req.get("acceptance_criterion_id"):
                document_ids.add(req["acceptance_criterion_id"])
            if claim.get("decision_id"):
                document_ids.add(claim["decision_id"])
        for relation in section["relations"]:
            if relation.get("dependency_target"):
                document_ids.add(relation["dependency_target"])
    for cid, kind in declared.items():
        if kind in ("protocol_id", "protocol_version", "work_item_id",
                    "dependency_target", "authority_reference"):
            continue  # cross-document or externally-scoped kinds
        assert cid in document_ids, (
            f"declared stable coordinate {cid} ({kind}) resolves to no document object"
        )


def walk_likelihoods(value: Any):
    if isinstance(value, dict):
        if value.get("kind") == "wep" and "term" in value:
            yield value
        for child in value.values():
            yield from walk_likelihoods(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_likelihoods(child)


def main() -> int:
    schema_paths = sorted(SCHEMAS.glob("*.schema.json"))
    schemas = [load_json(path) for path in schema_paths]
    by_name = {path.name: schema for path, schema in zip(schema_paths, schemas)}
    for schema in schemas:
        Draft202012Validator.check_schema(schema)
    registry = build_registry(schemas)

    registry_path = ROOT / REGISTRY_RELATIVE_PATH
    ruleset = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    validate_instance(ruleset, by_name["ats_ruleset_v1.schema.json"], registry, "ruleset")
    assert ruleset["schema_version"] == "ats.ruleset.v2"
    assert ruleset["spec_version"] == SPEC_VERSION
    rules = ruleset["rules"]
    assert len(rules) == EXPECTED_RULE_COUNT, f"expected {EXPECTED_RULE_COUNT} rules, got {len(rules)}"
    ids = [r["rule_id"] for r in rules]
    assert len(ids) == len(set(ids)), "duplicate rule ids"
    assert all(set(r["default_states"]) == {"ASSESS", "SPECIFY", "TRANSFORM"} for r in rules)
    for rule in rules:
        assert rule["operational_class"] in ("block", "review_required", "advisory"), rule["rule_id"]
        assert rule["rule_version"] in ("1.0.0-draft.1", "1.0.0-draft.2", "1.0.0-draft.3"), rule["rule_id"]
        # Operational-class coherence: an advisory-class rule must not be
        # required-state in any profile (style findings never hard-gate). The
        # exception list is empty because the one rule that would have violated
        # it (ATS-TERM-003, D0/D1 conformance evidence) was reclassified to
        # block; keep the list explicit so a future reclassification is a
        # decision, not an accident.
        if rule["operational_class"] == "advisory":
            assert all(
                state in ("advisory", "disabled")
                for state in rule["default_states"].values()
            ), f"advisory rule must not be required-state: {rule['rule_id']}"
    draft2_bumped = {"ATS-DISC-003", "ATS-COORD-001", "ATS-COORD-002", "ATS-BASIS-001",
                     "ATS-BASIS-002", "ATS-PRES-003", "ATS-CLOSE-001"}
    draft3_bumped = {"ATS-REQ-004"}
    for rule in rules:
        if rule["rule_id"] in draft3_bumped:
            assert rule["rule_version"] == SPEC_VERSION, rule["rule_id"]
        elif rule["rule_id"] in draft2_bumped:
            assert rule["rule_version"] == "1.0.0-draft.2", rule["rule_id"]
        else:
            assert rule["rule_version"] == "1.0.0-draft.1", rule["rule_id"]

    spec = (ROOT / "ATS-1_SPEC.md").read_text(encoding="utf-8")
    assert "Draft.3 amendment (D-G)" in spec
    assert "- each `MUST` and `MUST NOT` has a verifiable acceptance criterion;" in spec
    assert "load-bearing acceptance criterion that does not widen its requirement" not in spec
    fixture_path = ROOT / "examples" / "acceptance_criterion_semantics.md"
    assert fixture_path.is_file()
    fixture_text = fixture_path.read_text(encoding="utf-8")
    assert "## Conforming" in fixture_text
    assert "`TestStalePolicyRejection` passes." in fixture_text
    assert "## Hard negative — non-load-bearing" in fixture_text
    assert "seven-year audit record" in fixture_text
    spec_ids = set(re.findall(r"ATS-[A-Z]+-[0-9]{3}", spec))
    assert spec_ids == set(ids), f"spec/registry rule-id drift: spec-only={spec_ids-set(ids)}, registry-only={set(ids)-spec_ids}"
    for rule in rules:
        assert rule["normative_statement"] in spec, f"normative statement missing from spec: {rule['rule_id']}"

    # Migration-table cross-check: every amendment marker in the spec appears in the
    # migration document, and every delta the migration classifies has a marker.
    spec_markers = set(re.findall(r"Draft\.2 amendment \((D-[A-F])\)", spec))
    assert MIGRATION_DOC.is_file(), f"migration document missing: {MIGRATION_DOC}"
    migration = MIGRATION_DOC.read_text(encoding="utf-8")
    migration_ids = set(re.findall(r"\bD-[A-F]\b", migration))
    assert spec_markers == migration_ids, (
        f"migration/spec delta drift: spec-only={spec_markers - migration_ids}, "
        f"migration-only={migration_ids - spec_markers}"
    )

    lexicon = yaml.safe_load((ROOT / "lexicons/ats_force_lexicon_v1.yaml").read_text(encoding="utf-8"))
    validate_instance(lexicon, by_name["ats_force_lexicon_v1.schema.json"], registry, "force lexicon")
    assert lexicon["spec_version"] == "1.0.0-draft.1", (
        "force lexicon spec_version intentionally stays draft.1 (byte-identical vocabulary); "
        f"got {lexicon['spec_version']}"
    )
    terms = lexicon["likelihood"]["terms"]
    assert len(terms) == 7, "expected seven WEP bands"
    term_map = {t["id"]: t for t in terms}
    for left, right in zip(terms, terms[1:]):
        assert abs(left["upper"] - right["lower"]) < 1e-12, f"WEP gap/overlap: {left['id']} -> {right['id']}"
        assert left["upper_inclusive"] is False, f"non-final WEP upper boundary must be exclusive: {left['id']}"
    assert terms[-1]["upper_inclusive"] is True

    example_map = {
        "assess_text_ir_example.json": "ats_text_ir_v1.schema.json",
        "specify_text_ir_example.json": "ats_text_ir_v1.schema.json",
        "specify_basis_example.json": "ats_text_ir_v1.schema.json",
        "coordinates_example.json": "ats_text_ir_v1.schema.json",
        "closure_example.json": "ats_text_ir_v1.schema.json",
        "policy_snapshot_example.json": "ats_policy_snapshot_v1.schema.json",
        "policy_exception_example.json": "ats_policy_exception_v1.schema.json",
        "finding_example.json": "ats_finding_v1.schema.json",
        "adjudication_example.json": "ats_adjudication_v1.schema.json",
        "retention_contract_example.json": "ats_retention_contract_v1.schema.json",
        "preservation_report_example.json": "ats_preservation_report_v1.schema.json",
        "acceptance_receipt_example.json": "ats_acceptance_receipt_v1.schema.json",
        "capability_example.json": "ats_capability_v1.schema.json",
        "fleet_policy_example.json": "ats_fleet_policy_v1.schema.json",
    }
    loaded_examples: dict[str, Any] = {}
    for filename, schema_name in example_map.items():
        instance = load_json(ROOT / "examples" / filename)
        validate_instance(instance, by_name[schema_name], registry, filename)
        loaded_examples[filename] = instance
        if schema_name == "ats_text_ir_v1.schema.json":
            assert_text_ir_references(instance)
            assert_stable_coordinates(instance)

    # The strengthening-prohibition example is a self-describing transformation pair;
    # its embedded source IR must validate as a TextIR document.
    strengthen = load_json(ROOT / "examples" / "strengthen_prohibition_example.json")
    validate_instance(
        strengthen["source_ir"], by_name["ats_text_ir_v1.schema.json"], registry,
        "strengthen_prohibition_example source_ir",
    )
    assert_text_ir_references(strengthen["source_ir"])

    # Detector class/authority declarations must agree.
    finding = loaded_examples["finding_example.json"]
    if finding["detector"]["class"] == "D3":
        assert finding["detector"]["authority"] == "proposal_only"
    capability = loaded_examples["capability_example.json"]
    for entry in capability["rules"]:
        assert set(entry["detector_classes"]) == set(entry["authority_by_class"]), (
            f"capability class/authority mismatch for {entry['rule_id']}"
        )
        for cls, authority in entry["authority_by_class"].items():
            if cls == "D2":
                assert authority == "candidate_only"
            if cls == "D3":
                assert authority == "proposal_only"
            if authority == "conformance_evidence":
                assert cls in entry.get("authority_basis_refs", {}), (
                    f"missing authority basis for {entry['rule_id']} {cls}"
                )

    # Every WEP object in examples agrees with the canonical lexicon.
    for filename, instance in loaded_examples.items():
        for likelihood in walk_likelihoods(instance):
            canonical = term_map[likelihood["term"]]
            assert abs(likelihood["lower"] - canonical["lower"]) < 1e-12, f"{filename}: WEP lower drift"
            assert abs(likelihood["upper"] - canonical["upper"]) < 1e-12, f"{filename}: WEP upper drift"

    jsonl_count = 0
    with (ROOT / "examples/corpus_seed_examples.jsonl").open(encoding="utf-8") as f:
        for jsonl_count, line in enumerate(f, start=1):
            validate_instance(json.loads(line), by_name["ats_text_example_v1.schema.json"], registry, f"corpus line {jsonl_count}")
    assert jsonl_count > 0, "corpus seed file is empty"

    policy = loaded_examples["policy_snapshot_example.json"]
    assert policy["snapshot_sha256"] == canonical_hash(policy, {"snapshot_sha256"}), "policy example hash mismatch"
    exception = loaded_examples["policy_exception_example.json"]
    assert exception["sha256"] == canonical_hash(exception, {"sha256"}), "policy exception hash mismatch"
    receipt = loaded_examples["acceptance_receipt_example.json"]
    assert receipt["receipt_sha256"] == canonical_hash(receipt, {"receipt_sha256"}), "receipt example hash mismatch"
    manifest = load_json(ROOT / "MANIFEST.json")
    validate_instance(manifest, by_name["ats_package_manifest_v1.schema.json"], registry, "manifest")
    assert_package_edition_metadata(manifest)
    assert manifest["spec_version"] == SPEC_VERSION
    observed_entries = manifest["files"]
    observed_paths = [entry["path"] for entry in observed_entries]
    assert len(observed_paths) == len(set(observed_paths)), "duplicate manifest path"
    expected: dict[str, tuple[int, str]] = {}
    for path in sorted(
        p for p in ROOT.rglob("*")
        if p.is_file() and p.name != "MANIFEST.json" and not p.name.endswith(".zip")
    ):
        rel = str(path.relative_to(ROOT))
        expected[rel] = (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
    observed = {entry["path"]: (entry["bytes"], entry["sha256"]) for entry in observed_entries}
    assert expected == observed, "manifest does not match package bytes"

    total_examples = len(example_map) + jsonl_count
    print(f"ATS-1 package valid: {len(schema_paths)} schemas, {len(rules)} rules, {total_examples} examples")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        raise

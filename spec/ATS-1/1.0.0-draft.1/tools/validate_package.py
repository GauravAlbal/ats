#!/usr/bin/env python3
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
SPEC_VERSION = "1.0.0-draft.1"


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

    ruleset = yaml.safe_load((ROOT / "rules/ats_rules_v1.yaml").read_text(encoding="utf-8"))
    validate_instance(ruleset, by_name["ats_ruleset_v1.schema.json"], registry, "ruleset")
    assert ruleset["spec_version"] == SPEC_VERSION
    rules = ruleset["rules"]
    assert len(rules) == 30, f"expected 30 rules, got {len(rules)}"
    ids = [r["rule_id"] for r in rules]
    assert len(ids) == len(set(ids)), "duplicate rule ids"
    assert all(set(r["default_states"]) == {"ASSESS", "SPECIFY", "TRANSFORM"} for r in rules)

    spec = (ROOT / "ATS-1_SPEC.md").read_text(encoding="utf-8")
    spec_ids = set(re.findall(r"ATS-[A-Z]+-[0-9]{3}", spec))
    assert spec_ids == set(ids), f"spec/registry rule-id drift: spec-only={spec_ids-set(ids)}, registry-only={set(ids)-spec_ids}"
    for rule in rules:
        assert rule["normative_statement"] in spec, f"normative statement missing from spec: {rule['rule_id']}"

    lexicon = yaml.safe_load((ROOT / "lexicons/ats_force_lexicon_v1.yaml").read_text(encoding="utf-8"))
    validate_instance(lexicon, by_name["ats_force_lexicon_v1.schema.json"], registry, "force lexicon")
    assert lexicon["spec_version"] == SPEC_VERSION
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
        "policy_snapshot_example.json": "ats_policy_snapshot_v1.schema.json",
        "policy_exception_example.json": "ats_policy_exception_v1.schema.json",
        "finding_example.json": "ats_finding_v1.schema.json",
        "adjudication_example.json": "ats_adjudication_v1.schema.json",
        "retention_contract_example.json": "ats_retention_contract_v1.schema.json",
        "preservation_report_example.json": "ats_preservation_report_v1.schema.json",
        "acceptance_receipt_example.json": "ats_acceptance_receipt_v1.schema.json",
        "capability_example.json": "ats_capability_v1.schema.json",
    }
    loaded_examples: dict[str, Any] = {}
    for filename, schema_name in example_map.items():
        instance = load_json(ROOT / "examples" / filename)
        validate_instance(instance, by_name[schema_name], registry, filename)
        loaded_examples[filename] = instance
        if schema_name == "ats_text_ir_v1.schema.json":
            assert_text_ir_references(instance)

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

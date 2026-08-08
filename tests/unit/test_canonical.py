"""Canonical serialization and content addressing.

Appendix C fixes the procedure: omit the object's own hash field, serialize the
remainder with RFC 8785 JCS, SHA-256 the canonical bytes, encode lowercase hex,
and prefix human-facing identifiers by object type. The strongest available
oracles are the normative package's own worked examples, whose recorded hashes
were produced upstream by an independent implementation.
"""

from __future__ import annotations

import json

import pytest

from ats.canonical import (
    ID_PREFIXES,
    SELF_HASH_FIELDS,
    canonical_bytes,
    canonical_text,
    content_hash,
    load_json,
    prefixed_id,
    seal,
    sha256_hex,
    verify_seal,
    write_json,
)
from ats.errors import UsageError

#: Each normative example, the field holding its own address, and the section
#: of Appendix C the pairing exercises.
EXAMPLE_ORACLES = (
    ("policy_snapshot_example.json", "snapshot_sha256"),
    ("acceptance_receipt_example.json", "receipt_sha256"),
    ("policy_exception_example.json", "sha256"),
)


@pytest.mark.parametrize(("example", "field"), EXAMPLE_ORACLES)
def test_content_hash_reproduces_the_upstream_recorded_address(ctx, example, field) -> None:
    """Appendix C steps 1-4, checked against the package's own recorded hash."""
    document = ctx.package.example(example)
    recorded = document[field]
    assert content_hash(document, exclude={field}) == recorded
    # The exclusion set is derived from ``schema_version`` when omitted.
    assert content_hash(document) == recorded
    assert SELF_HASH_FIELDS[document["schema_version"]] == field


@pytest.mark.parametrize(("example", "field"), EXAMPLE_ORACLES)
def test_verify_seal_accepts_the_upstream_examples(ctx, example, field) -> None:
    """Appendix C: a correctly sealed object verifies against its own bytes."""
    document = ctx.package.example(example)
    ok, declared, recomputed = verify_seal(document)
    assert ok
    assert declared == recomputed == document[field]


def test_canonical_bytes_round_trip_is_stable(ctx) -> None:
    """Appendix C step 2: JCS output re-serializes to itself byte for byte."""
    document = ctx.package.example("assess_text_ir_example.json")
    first = canonical_bytes(document)
    second = canonical_bytes(json.loads(first.decode("utf-8")))
    assert first == second
    assert canonical_text(document) == first.decode("utf-8")
    assert sha256_hex(first) == sha256_hex(second)


def test_canonical_bytes_orders_keys_and_escapes_per_rfc8785() -> None:
    """RFC 8785: member ordering is by UTF-16 code unit, output is compact UTF-8."""
    assert canonical_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert canonical_bytes({"\u00e9": 1, "e": 2}) == '{"e":2,"é":1}'.encode("utf-8")
    # ES6 number formatting: an integral double is emitted without a fraction.
    assert canonical_bytes({"n": 1.0}) == b'{"n":1}'
    assert canonical_bytes([1, "two", None, True]) == b'[1,"two",null,true]'


def test_canonical_bytes_refuses_a_non_serializable_value() -> None:
    """Appendix C: a value outside the JSON data model has no canonical form."""
    with pytest.raises(UsageError):
        canonical_bytes({"when": object()})


def test_content_hash_ignores_only_the_excluded_field() -> None:
    """Appendix C step 1: exactly the self-hash field is omitted from the input."""
    base = {"schema_version": "ats.policy_snapshot.v1", "snapshot_id": "p", "a": 1}
    with_noise = {**base, "snapshot_sha256": "0" * 64}
    assert content_hash(with_noise) == content_hash(base, exclude=set())
    changed = {**base, "a": 2}
    assert content_hash(changed) != content_hash(base)


def test_seal_and_verify_seal_round_trip() -> None:
    """Appendix C: sealing writes the address the verifier recomputes."""
    document = {
        "schema_version": "ats.output_trace.v1",
        "artifact_id": "fixture",
        "blocks": [],
    }
    sealed = seal(document)
    assert sealed["trace_sha256"] == content_hash(document, exclude={"trace_sha256"})
    ok, declared, recomputed = verify_seal(sealed)
    assert ok and declared == recomputed

    # Sealing is idempotent: a prior address is discarded, not hashed.
    assert seal(sealed) == sealed

    tampered = {**sealed, "artifact_id": "other"}
    ok, declared, recomputed = verify_seal(tampered)
    assert not ok
    assert declared != recomputed


def test_seal_refuses_an_object_with_no_declared_self_hash_field() -> None:
    """Appendix C step 1: an object with nowhere to record its address is unaddressable."""
    with pytest.raises(UsageError, match="no self-hash field"):
        seal({"schema_version": "ats.finding.v1", "finding_id": "f1"})
    with pytest.raises(UsageError, match="no self-hash field"):
        seal({"artifact_id": "no schema_version at all"})
    with pytest.raises(UsageError, match="no self-hash field"):
        verify_seal({"schema_version": "ats.finding.v1"})


def test_prefixed_id_uses_the_object_type_prefix(ctx) -> None:
    """Appendix C step 5 and Appendix B: identifiers are type-prefixed."""
    policy = ctx.package.example("policy_snapshot_example.json")
    digest = policy["snapshot_sha256"]
    assert prefixed_id(policy, digest) == f"{ID_PREFIXES['ats.policy_snapshot.v1']}:{digest}"
    assert prefixed_id({"schema_version": "ats.finding.v1"}, digest) == f"ats-sha256:{digest}"


def test_sha256_hex_is_lowercase_hex_of_exact_bytes() -> None:
    """Appendix C steps 3-4."""
    digest = sha256_hex(b"")
    assert digest == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert digest == digest.lower()
    assert len(digest) == 64


def test_write_json_emits_canonical_bytes_and_load_json_round_trips(tmp_path) -> None:
    """Appendix C: a written artifact is its own content address."""
    document = {"schema_version": "ats.output_trace.v1", "b": 1, "a": [1, 2]}
    target = tmp_path / "nested" / "doc.json"
    digest = write_json(target, document)
    raw = target.read_bytes()
    assert raw == canonical_bytes(document)
    assert digest == sha256_hex(raw)
    assert load_json(target) == document


def test_load_json_reports_unreadable_and_malformed_input(tmp_path) -> None:
    """Spec 20.6: honest insufficiency instead of a silent empty document."""
    with pytest.raises(UsageError, match="cannot read"):
        load_json(tmp_path / "absent.json")
    broken = tmp_path / "broken.json"
    broken.write_bytes(b"{not json")
    with pytest.raises(UsageError, match="not valid UTF-8 JSON"):
        load_json(broken)

"""The output trace sidecar: block hashing, references, and pointer resolution.

The trace is what makes a readable Markdown document deterministically
traceable back to its TextIR (Section 14.4). Its integrity is therefore checked
before any surface rule runs: a trace that does not match the bytes it
describes cannot ground a finding.
"""

from __future__ import annotations

import copy

import pytest

from ats.canonical import sha256_hex, verify_seal
from ats.errors import UsageError
from ats.ir.model import IrDocument
from ats.output.parse import parse_markdown
from ats.output.trace import (
    MARKER_SCHEME,
    REFERENCE_FIELDS,
    block_text_sha256,
    build_trace,
    ir_value_at,
    load_trace,
)


@pytest.fixture(scope="module")
def bundle(load_bundle):
    return load_bundle("assess-bundle")


@pytest.fixture(scope="module")
def trace(ctx, bundle):
    return load_trace(ctx, bundle["trace"])


def test_marker_scheme_is_declared_in_the_trace(trace) -> None:
    """The reader of a trace must be able to find the markers it describes."""
    assert trace.raw["marker_scheme"] == MARKER_SCHEME
    assert MARKER_SCHEME["pattern"] == "<!-- ats:block {block_id} -->"


def test_block_hash_covers_the_body_and_excludes_the_marker(bundle) -> None:
    """The marker is renderer metadata, not content the reader acts on."""
    parsed = parse_markdown(bundle["text"])
    block = parsed.block_by_marker("assess-key-judgment")
    assert block is not None
    assert "ats:block" not in block.text
    assert block_text_sha256(block) == sha256_hex(block.text.rstrip("\n").encode("utf-8"))


def test_declared_block_hashes_reproduce_from_the_document_bytes(bundle, trace) -> None:
    """Spec 14.2 and 16.2: the declared hash is the hash of the rendered bytes."""
    parsed = parse_markdown(bundle["text"])
    for tb in trace.blocks:
        block = parsed.block_by_marker(tb.block_id)
        assert block is not None, tb.block_id
        assert block_text_sha256(block) == tb.text_sha256, tb.block_id


def test_a_block_hash_mismatch_is_detectable(bundle, trace) -> None:
    """Spec 16.2: an edited block no longer reproduces its declared address."""
    parsed = parse_markdown(bundle["text"].replace("Prototype one", "Prototype two"))
    tb = trace.block("assess-recommendation")
    assert tb is not None
    block = parsed.block_by_marker("assess-recommendation")
    assert block_text_sha256(block) != tb.text_sha256


def test_the_trace_is_sealed_and_binds_its_artifacts(ctx, bundle, trace, load_ir) -> None:
    """Appendix C and spec 14.13: the trace is content addressed and bound."""
    ok, declared, recomputed = verify_seal(dict(trace.raw))
    assert ok and declared == recomputed
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    assert trace.ir_sha256 == ir.ir_sha256
    assert trace.artifact_id == ir.artifact_id
    assert trace.output_sha256 == sha256_hex(bundle["output_path"].read_bytes())


def test_block_references_are_typed_by_field(trace) -> None:
    """Spec 14.4: a block declares which IR objects it realizes, by kind."""
    fields = dict(REFERENCE_FIELDS)
    assert fields["claim_ids"] == "claim"
    assert fields["relation_ids"] == "relation"
    judgment = trace.block("assess-key-judgment")
    assert judgment is not None
    assert ("claim_ids", "claim", "c1") in list(judgment.references())
    assert "c1" in trace.declared_object_ids()
    assert trace.block("no-such-block") is None


def test_ordinals_are_dense_and_ascending(trace) -> None:
    """Spec 16.2: block order is a stable function of the document."""
    ordinals = [b.ordinal for b in trace.blocks]
    assert ordinals == list(range(len(ordinals)))


def test_load_trace_rejects_a_schema_invalid_trace(ctx, bundle) -> None:
    """Spec 19.4: the trace is a schema-governed object."""
    from ats.errors import SchemaValidationError

    broken = copy.deepcopy(bundle["trace"])
    del broken["blocks"][0]["text_sha256"]
    with pytest.raises(SchemaValidationError):
        load_trace(ctx, broken)


# -- build_trace ------------------------------------------------------------


def test_build_trace_refuses_a_marked_block_with_no_metadata(ctx, load_ir) -> None:
    """Spec 14.4: every marked block must declare what it realizes."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    text = "<!-- ats:block orphan -->\nSome prose.\n"
    parsed = parse_markdown(text)
    with pytest.raises(UsageError, match="no trace metadata"):
        build_trace(
            ctx,
            ir=ir,
            parsed=parsed,
            output_bytes=text.encode("utf-8"),
            policy_snapshot_id="policy-example-assess",
            policy_sha256="0" * 64,
            block_metadata={},
            renderer={"name": "test", "version": "0"},
        )


def test_build_trace_seals_and_validates_what_it_emits(
    ctx, load_ir, load_policy, assert_valid
) -> None:
    """Appendix C and 19.4: an emitted trace is sealed and schema valid."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    policy = ctx.policy(load_policy("assess"))
    text = "<!-- ats:block only -->\nThe judgment prose.\n"
    parsed = parse_markdown(text)
    document = build_trace(
        ctx,
        ir=ir,
        parsed=parsed,
        output_bytes=text.encode("utf-8"),
        policy_snapshot_id=policy.snapshot_id,
        policy_sha256=policy.declared_sha256,
        block_metadata={
            "only": {
                "display_role": "key_judgment",
                "section_id": "assessment",
                "material": True,
                "claim_ids": ["c1"],
            }
        },
        renderer={"name": "test-renderer", "version": "0"},
    )
    assert_valid(document, "ats_output_trace_v1.schema.json")
    ok, _, _ = verify_seal(document)
    assert ok
    (block,) = document["blocks"]
    assert block["ordinal"] == 0
    assert block["marker"] == "<!-- ats:block only -->"
    assert block["text_sha256"] == sha256_hex(b"The judgment prose.")
    assert document["created_at"] == ctx.timestamp()


def test_build_trace_ignores_unmarked_blocks(ctx, load_ir, load_policy) -> None:
    """Only marked blocks are traceable; an unmarked block declares nothing."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    policy = ctx.policy(load_policy("assess"))
    text = "Unmarked prose.\n\n<!-- ats:block only -->\nMarked prose.\n"
    parsed = parse_markdown(text)
    document = build_trace(
        ctx,
        ir=ir,
        parsed=parsed,
        output_bytes=text.encode("utf-8"),
        policy_snapshot_id=policy.snapshot_id,
        policy_sha256=policy.declared_sha256,
        block_metadata={
            "only": {"display_role": "key_judgment", "section_id": "assessment"}
        },
        renderer={"name": "test-renderer", "version": "0"},
    )
    assert [b["block_id"] for b in document["blocks"]] == ["only"]


# -- ir_value_at ------------------------------------------------------------


def test_ir_value_at_resolves_a_json_pointer(load_ir) -> None:
    """RFC 6901 via spec 11.3.1: a P0 field names an exact location in the IR."""
    document = load_ir("assess_conforming")
    ir = IrDocument.from_document(document)
    assert ir_value_at(ir, "/artifact_id") == document["artifact_id"]
    assert ir_value_at(ir, "/sections/0/claims/0/force/likelihood/term") == "likely"
    assert ir_value_at(ir, "/sections/0/claims/0/force/likelihood/lower") == 0.55
    assert ir_value_at(ir, "") is ir.raw
    assert ir_value_at(ir, "/") is ir.raw


def test_ir_value_at_applies_rfc6901_escapes(load_ir) -> None:
    """RFC 6901: `~1` is `/` and `~0` is `~`, decoded in that order."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["sections"][0]["claims"][0]["scope"]["a/b"] = "slash"
    document["sections"][0]["claims"][0]["scope"]["c~d"] = "tilde"
    ir = IrDocument.from_document(document)
    assert ir_value_at(ir, "/sections/0/claims/0/scope/a~1b") == "slash"
    assert ir_value_at(ir, "/sections/0/claims/0/scope/c~0d") == "tilde"


@pytest.mark.parametrize(
    "pointer",
    [
        "sections/0",
        "/sections/99",
        "/sections/not-a-number",
        "/sections/0/claims/0/force/likelihood/term/deeper",
        "/no-such-key",
    ],
)
def test_ir_value_at_refuses_a_pointer_that_does_not_resolve(load_ir, pointer) -> None:
    """Spec 20.6: an unresolvable pointer is an error, not a silent None."""
    ir = IrDocument.from_document(load_ir("assess_conforming"))
    with pytest.raises(UsageError):
        ir_value_at(ir, pointer)

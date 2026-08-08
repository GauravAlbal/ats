"""Corpus record construction, content addressing, and append-only storage.

Defends spec Section 17.2 (the TextExampleV1 record), Section 17.5 (synthetic
examples MUST be tagged), Section 17.9 (disagreement MUST be retained), and
Appendix C (content addressing omits the object's own hash field).
"""

from __future__ import annotations

import datetime as dt

import pytest

from ats.context import Context
from ats.corpus import records as rec
from ats.errors import UsageError

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


def _example(**overrides):
    fields = {
        "text": "The verifier MUST reject a stale receipt.",
        "profile": "SPECIFY",
        "rule_id": "ATS-DEON-001",
        "label": "conforming",
        "rationale": "The obligation uses the canonical MUST surface.",
        "protected_impact": ["P0"],
        "provenance": "human_authored_fixture",
        "synthetic": False,
        "split_group": "unit-test",
    }
    fields.update(overrides)
    return rec.text_example(**fields)


def test_identifier_is_a_pure_function_of_content(ctx: Context) -> None:
    """Appendix C: the identifier is the content address, so equal content is equal id."""
    first = _example()
    second = _example()
    assert first["example_id"] == second["example_id"]
    assert _example(rationale="A different reason.")["example_id"] != first["example_id"]


def test_text_example_extends_only_through_extensions(ctx: Context) -> None:
    """Spec 19.5: TextExampleV1 is normative, so its digest lives under x-ats-repo-."""
    example = _example()
    ctx.schemas.validate_document(example)
    assert "record_sha256" not in example
    digest = example["extensions"][rec.EXT_RECORD_SHA256]
    assert example["example_id"] == f"ats-example-sha256:{digest}"
    assert all(k.startswith(rec.EXT_PREFIX) for k in example["extensions"])


def test_sealed_records_verify(ctx: Context) -> None:
    """Appendix C: a sealed record's declared hash recomputes from its content."""
    artifact = rec.source_artifact(
        repository="sample-repo",
        repository_group="ats-sample",
        path="docs/a.md",
        revision="0" * 40,
        content_sha256="a" * 64,
        normalized_sha256="a" * 64,
        media_type="text/markdown",
        review_state="unknown",
        use_authority="unknown",
        handling_policy="internal",
        ingested_at=ctx.timestamp(),
    )
    ctx.schemas.validate_document(artifact)
    ok, detail = rec.verify_record(artifact)
    assert ok, detail


def test_tampering_breaks_the_content_address(ctx: Context) -> None:
    """A record whose content changed can never present the original identifier."""
    example = dict(_example())
    example["rationale"] = "Silently rewritten."
    ok, detail = rec.verify_record(example)
    assert not ok
    assert "content addresses to" in detail


def test_synthetic_and_provenance_must_agree() -> None:
    """Spec 17.5: synthetic examples MUST be tagged, so the two fields cannot disagree."""
    with pytest.raises(UsageError, match="MUST be tagged"):
        _example(synthetic=True, provenance="human_authored_fixture")
    with pytest.raises(UsageError, match="requires synthetic=true"):
        _example(synthetic=False, provenance="synthetic_mutation")
    with pytest.raises(UsageError, match="only meaningful on a synthetic"):
        _example(mutation_operator="ATS-MUT-QUAL-DELETE")


def test_append_is_the_only_mutation(ctx: Context, tmp_path) -> None:
    """Spec 17.9: retained disagreement requires a store that cannot be rewritten."""
    path = tmp_path / "examples.jsonl"
    example = _example()
    assert rec.append_records(ctx, path, [example])["appended"] == 1
    with pytest.raises(UsageError, match="append-only"):
        rec.append_records(ctx, path, [example])
    # The refused write left the file untouched.
    assert len(rec.read_records(path)) == 1

    other = _example(rationale="A second, different example.")
    assert rec.append_records(ctx, path, [other])["total"] == 2


def test_append_refuses_a_batch_that_repeats_an_id(ctx: Context, tmp_path) -> None:
    """A duplicate inside one batch is refused before anything is written."""
    path = tmp_path / "examples.jsonl"
    example = _example()
    with pytest.raises(UsageError, match="append-only"):
        rec.append_records(ctx, path, [example, example])
    assert not path.exists()


def test_append_refuses_an_unaddressed_record(ctx: Context, tmp_path) -> None:
    """A record whose id does not match its content is not storable."""
    broken = dict(_example())
    broken["example_id"] = "ats-example-sha256:" + "0" * 64
    with pytest.raises(UsageError, match="not correctly content-addressed"):
        rec.append_records(ctx, tmp_path / "e.jsonl", [broken])


def test_adjudication_requires_two_judgments() -> None:
    """Spec 17.9: an adjudication resolves at least two independent judgments."""
    with pytest.raises(UsageError, match="at least two independent judgments"):
        rec.adjudication(
            example_id="e1",
            rule_id="ATS-DEON-001",
            rule_version="1.0.0-draft.1",
            judgments=[],
            agreement="unanimous",
            disagreement_category="none",
            final_state="gold",
            adjudicator="human:one",
            rationale="No judgments.",
            gold_eligible=True,
            timestamp="2026-02-01T00:00:00Z",
        )


def test_validate_records_reports_every_problem(ctx: Context, tmp_path) -> None:
    """Validation reports schema, addressing, and duplicate failures, not just the first."""
    path = tmp_path / "corpus.jsonl"
    good = _example()
    bad_address = dict(_example(rationale="Two."))
    bad_address["example_id"] = "ats-example-sha256:" + "1" * 64
    path.write_text(
        "\n".join(
            [
                __import__("json").dumps(good),
                __import__("json").dumps(bad_address),
                __import__("json").dumps(good),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    report = rec.validate_records(ctx, path)
    assert report["records_checked"] == 3
    assert report["by_schema"] == {"ats.text_example.v1": 3}
    problems = {p["problem"] for p in report["problems"]}
    assert problems == {"content_address_mismatch", "duplicate_id"}


def test_shipped_corpus_fixtures_validate(ctx: Context) -> None:
    """Every record this repository ships is schema-valid and correctly addressed."""
    for path in ("fixtures/corpus", "corpus/seeds"):
        report = rec.validate_records(ctx, path)
        assert report["problems"] == [], (path, report["problems"])
        assert report["records_checked"] > 0

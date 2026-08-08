"""Context bundles: complete local context, or an explicit statement of what is missing.

Defends spec Section 17.4 (an isolated sentence SHOULD NOT be labeled when the
rule depends on discarded context) and Section 10.3 (a glossary entry is
authored, not inferred from prose).
"""

from __future__ import annotations

import datetime as dt
import sys

import pytest

from ats.context import Context
from ats.corpus import context as ctxmod
from ats.corpus import inventory as inv
from ats.errors import UsageError
from ats.spec_package import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
from generate_corpus_fixtures import build_sample_repo  # noqa: E402

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return build_sample_repo(tmp_path_factory.mktemp("git") / "sample-repo")


@pytest.fixture(scope="module")
def artifacts(ctx: Context, repo):
    inventory = inv.build_inventory(ctx, repo)
    return {a["path"]: a for a in inventory["artifacts"]}


def _span_of(text: str, needle: str) -> dict:
    start = text.index(needle)
    return {"kind": "character", "start": start, "end": start + len(needle)}


def test_bundle_carries_the_complete_containing_block(ctx: Context, repo, artifacts) -> None:
    """Spec 17.4: the complete local context is preserved, not the matched phrase alone."""
    artifact = artifacts["docs/assessment.md"]
    text = inv.artifact_text(repo, artifact)
    bundle = ctxmod.build_context_bundle(
        ctx, artifact=artifact, text=text, span=_span_of(text, "likely"), repo_path=repo
    )
    assert bundle["span_text"] == "likely"
    block = bundle["containing_block"]
    assert block["kind"] == "paragraph"
    assert "A Rust migration is likely" in block["text"]
    assert "reduce invalid-state defects" in block["text"]
    assert bundle["heading_path"] == [
        "Rust kernel assessment",
        "ASSESS: acceptance-kernel language",
    ]


def test_every_dimension_carries_an_availability_state(ctx: Context, repo, artifacts) -> None:
    """Spec 17.4: an absent dimension is typed, never omitted."""
    artifact = artifacts["docs/assessment.md"]
    text = inv.artifact_text(repo, artifact)
    bundle = ctxmod.build_context_bundle(
        ctx, artifact=artifact, text=text, span=_span_of(text, "possible"), repo_path=repo
    )
    for field in ("preceding_context", "following_context", "diff", "review_comment", "later_edit"):
        assert "availability" in bundle[field], field
    assert bundle["policy_context"]["availability"] == "not_searched"
    assert bundle["diff"]["availability"] == "present"
    assert bundle["review_comment"]["availability"] == "not_found"


def test_boundary_blocks_report_not_found_rather_than_nothing(
    ctx: Context, repo, artifacts
) -> None:
    """The first block of a document has no predecessor; that is an answer, not a gap."""
    artifact = artifacts["docs/assessment.md"]
    text = inv.artifact_text(repo, artifact)
    bundle = ctxmod.build_context_bundle(
        ctx,
        artifact=artifact,
        text=text,
        span=_span_of(text, "Rust kernel assessment"),
        repo_path=repo,
    )
    assert bundle["preceding_context"]["availability"] == "not_found"
    assert "first block" in bundle["preceding_context"]["locator"]
    assert bundle["following_context"]["availability"] == "present"


def test_a_policy_snapshot_is_recorded_when_supplied(ctx: Context, repo, artifacts) -> None:
    """Spec 17.4: glossary and policy context are preserved."""
    from ats.canonical import load_json

    policy = load_json(REPO_ROOT / "fixtures" / "policies" / "assess.json")
    artifact = artifacts["docs/assessment.md"]
    text = inv.artifact_text(repo, artifact)
    bundle = ctxmod.build_context_bundle(
        ctx,
        artifact=artifact,
        text=text,
        span=_span_of(text, "likely"),
        repo_path=repo,
        policy_document=policy,
        glossary_entries=[
            {
                "concept_id": "acceptance-kernel",
                "canonical_term": "acceptance kernel",
                "definition": "The closed state-transition component.",
                "scope": "Arq",
            }
        ],
    )
    assert bundle["policy_context"]["availability"] == "present"
    assert len(bundle["policy_context"]["policy_sha256"]) == 64
    assert bundle["glossary_entries"][0]["canonical_term"] == "acceptance kernel"
    assert bundle["context_completeness"] == "complete"


def test_an_unknown_profile_basis_degrades_completeness(ctx: Context, repo, artifacts) -> None:
    """A guessed profile must never read as a determination."""
    artifact = artifacts["docs/notes.txt"]
    text = inv.artifact_text(repo, artifact)
    bundle = ctxmod.build_context_bundle(
        ctx, artifact=artifact, text=text, span=_span_of(text, "robust"), repo_path=repo
    )
    assert bundle["profile_hypothesis"]["basis"] == "unknown"
    assert bundle["profile_hypothesis"]["alternatives"]
    assert bundle["context_completeness"] in ("partial", "insufficient")


def test_a_declared_profile_marker_is_honoured(ctx: Context, repo, artifacts) -> None:
    """A heading naming a profile identifier is evidence; nothing else is."""
    artifact = artifacts["docs/requirements.md"]
    text = inv.artifact_text(repo, artifact)
    bundle = ctxmod.build_context_bundle(
        ctx, artifact=artifact, text=text, span=_span_of(text, "MUST"), repo_path=repo
    )
    assert bundle["profile_hypothesis"] == {"profile": "SPECIFY", "basis": "heading_path"}


def test_local_definitions_come_only_from_a_declaration() -> None:
    """Spec 10.3: a definition is authored. Inferring one from prose would fabricate it."""
    undeclared = "The acceptance kernel is the component that authorizes a change.\n"
    assert ctxmod.local_definitions(undeclared) == []

    declared = (
        "<!-- ats:define acceptance kernel -->\n"
        "The closed state-transition component that authorizes an accepted change.\n"
    )
    definitions = ctxmod.local_definitions(declared)
    assert definitions == [
        {
            "term": "acceptance kernel",
            "definition": "The closed state-transition component that authorizes an accepted "
            "change.",
            "locator": "line:2",
        }
    ]


def test_a_span_crossing_blocks_is_refused(ctx: Context, repo, artifacts) -> None:
    """Spec 17.4: an example MUST carry its complete containing block."""
    artifact = artifacts["docs/requirements.md"]
    text = inv.artifact_text(repo, artifact)
    start = text.index("REQ-POLICY-017")
    end = text.index("Acceptance criteria")
    with pytest.raises(UsageError, match="complete containing block"):
        ctxmod.build_context_bundle(
            ctx,
            artifact=artifact,
            text=text,
            span={"kind": "character", "start": start, "end": end},
            repo_path=repo,
        )


def test_a_line_span_is_refused(ctx: Context, repo, artifacts) -> None:
    """A bundle is cut from character offsets against a pinned content hash."""
    artifact = artifacts["docs/requirements.md"]
    text = inv.artifact_text(repo, artifact)
    with pytest.raises(UsageError, match="character span"):
        ctxmod.build_context_bundle(
            ctx,
            artifact=artifact,
            text=text,
            span={"kind": "line", "start_line": 1, "end_line": 2},
            repo_path=repo,
        )


def test_without_a_repository_the_git_dimensions_are_not_searched(
    ctx: Context, repo, artifacts
) -> None:
    """Not searched and not found are different answers, and both are recorded."""
    artifact = artifacts["docs/assessment.md"]
    text = inv.artifact_text(repo, artifact)
    bundle = ctxmod.build_context_bundle(
        ctx, artifact=artifact, text=text, span=_span_of(text, "likely")
    )
    assert bundle["diff"]["availability"] == "not_searched"
    assert bundle["later_edit"]["availability"] == "not_searched"
    assert bundle["context_completeness"] == "partial"


def test_plain_text_blocks_are_paragraphs(ctx: Context, repo, artifacts) -> None:
    """Plain text has no block grammar, so its blocks are blank-line separated."""
    artifact = artifacts["docs/notes.txt"]
    text = inv.artifact_text(repo, artifact)
    blocks = ctxmod.document_blocks(text, media_type="text/plain")
    assert [b.kind for b in blocks] == ["paragraph", "paragraph"]
    assert blocks[0].text == "Operator notes"
    assert text[blocks[1].start : blocks[1].end].startswith("The migration decision")

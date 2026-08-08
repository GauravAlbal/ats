"""The revision-derived candidate basis, and the interpretation it refuses to make.

A force delta between two revisions is a strong reason to look at a span. These
tests pin the two halves of that sentence: the miner really does find the delta
(``may`` becoming ``MUST``, ``some`` becoming ``all``), and it never converts the
delta into a normative reading of either version. ``normative_interpretation`` is
structurally single-valued, authority gates the whole basis, and a cosmetic
reflow produces nothing at all.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

from ats.context import Context
from ats.corpus import authority as auth
from ats.corpus import context as corpus_context
from ats.corpus import inventory as inv
from ats.corpus import mine
from ats.corpus import records as rec
from ats.errors import UsageError

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)

GIT_IDENTITY = (
    "-c",
    "user.name=Revision Fixture",
    "-c",
    "user.email=revision@ats.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "init.defaultBranch=main",
)
GIT_ENV = {
    "PATH": "/usr/bin:/bin:/usr/local/bin",
    "HOME": "/tmp",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "LC_ALL": "C",
}

#: An owner declaration that opens every use a pilot needs. ``candidate_mining``
#: is the one this module is about; the rest are present because an omitted use
#: resolves ``unknown`` and would confuse a failure for a policy.
AUTHORISED = {
    "schema_version": auth.SCHEMA_VERSION,
    "principal": {"id": "https://example.invalid/fixture-owner", "kind": "person"},
    "authority_basis": {
        "kind": "owner_declared",
        "statement": "The principal authored every commit in this synthetic fixture.",
    },
    "repository": {
        "name": "revision-repo",
        "origin": None,
        "root_commit": "a" * 64,
        "effective_from_revision": "HEAD",
        "declaration_location": "repository",
    },
    "uses": {use: "allow" for use in auth.USES},
    "content": {"include": ["*"]},
    "issued_at": "2026-01-01T00:00:00+00:00",
    "review_after": "2027-01-01T00:00:00+00:00",
    "superseded_by": None,
    "handling": {"classification": "internal", "export_raw_text": False},
    "provenance": {
        "authorship": "unknown_unless_explicit",
        "model_authorship_inference": "prohibited",
    },
}

#: The same owner, deferring on mining alone. ``defer`` is an explicit refusal
#: to decide, and an undecided use is not an authorised one.
DEFERRED = {**AUTHORISED, "uses": {**AUTHORISED["uses"], "candidate_mining": "defer"}}


def _git(repo: Path, *argv: str, date: str | None = None) -> None:
    env = dict(GIT_ENV)
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    proc = subprocess.run(
        ["git", "-C", str(repo), *GIT_IDENTITY, *argv], capture_output=True, env=env
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(argv)}: {proc.stderr.decode('utf-8', 'replace')}")


def build_repo(
    dest: Path, versions: Sequence[Mapping[str, str]], *, declaration: Mapping[str, Any] | None
) -> Path:
    """A real Git repository replaying ``versions`` one commit at a time."""
    dest.mkdir(parents=True, exist_ok=True)
    _git(dest, "init", "--quiet")
    if declaration is not None:
        (dest / ".ats").mkdir(exist_ok=True)
        (dest / ".ats" / "corpus.json").write_text(
            json.dumps(declaration, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    for index, files in enumerate(versions):
        for relative, content in files.items():
            target = dest / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        _git(dest, "add", "--all")
        _git(
            dest,
            "commit",
            "--quiet",
            "-m",
            f"Revision {index}\n",
            date=f"2026-01-0{index + 1}T09:00:00+00:00",
        )
    return dest


DEONTIC_V1 = """# Receipt policy

## SPECIFY: stale receipts

REQ-1: When the presented policy hash differs from the resolved snapshot, the
verifier may reject the receipt.
"""

DEONTIC_V2 = DEONTIC_V1.replace("may reject", "MUST reject")

#: One paragraph per axis, separated by unchanged headings so each edit is its
#: own changed region rather than one region carrying four movements.
FOUR_AXES_V1 = """# Kernel notes

## Obligation

The verifier may reject the receipt.

## Likelihood

The migration is likely to reduce invalid-state defects.

## Quantifier

Some kernels emit a receipt.

## Ordering

The verifier runs the hash check after the acceptance transition.
"""

FOUR_AXES_V2 = (
    FOUR_AXES_V1.replace("verifier may reject", "verifier MUST reject")
    .replace("is likely to", "is very likely to")
    .replace("Some kernels", "All kernels")
    .replace("check after the", "check before the")
)

COSMETIC_V1 = """# Receipt policy

## SPECIFY: stale receipts

REQ-1: The verifier MUST reject the receipt whose policy hash differs from the resolved snapshot.

Some kernels emit a receipt.
"""

#: The same words in the same order: the paragraph is rewrapped so that both
#: axis terms cross a line boundary, and a line gains trailing whitespace. A
#: line-by-line comparison would read this as ``MUST`` and ``Some`` appearing
#: and disappearing; a region comparison reads it as the reflow it is.
COSMETIC_V2 = """# Receipt policy

## SPECIFY: stale receipts

REQ-1: The verifier
MUST reject the receipt whose policy hash differs from the resolved
snapshot.

Some kernels emit a
receipt.\u0020\u0020
"""


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


def mine_repo(ctx: Context, repo: Path) -> dict[str, Any]:
    return mine.mine_candidates(ctx, inv.build_inventory(ctx, repo))


@pytest.fixture(scope="module")
def deontic(ctx: Context, tmp_path_factory) -> dict[str, Any]:
    repo = build_repo(
        tmp_path_factory.mktemp("git") / "deontic",
        [{"docs/policy.md": DEONTIC_V1}, {"docs/policy.md": DEONTIC_V2}],
        declaration=AUTHORISED,
    )
    return {"repo": repo, "result": mine_repo(ctx, repo)}


# -- the delta the standard cares about --------------------------------------


def test_may_becoming_must_yields_one_deontic_force_candidate(deontic) -> None:
    """Spec 11.3.1 protects deontic force; a revision that moved it is worth review."""
    candidates = deontic["result"]["revision_candidates"]
    assert len(candidates) == 1
    basis = candidates[0]["candidate_basis"]
    assert basis["type"] == "revision_force_delta"
    assert basis["changed_axis"] == "deontic_force"
    assert basis["normative_interpretation"] == "unresolved"
    assert basis["before_terms"] == ["may"]
    assert basis["after_terms"] == ["MUST"]


def test_the_candidate_span_points_at_the_changed_words(ctx: Context, deontic) -> None:
    """A span an annotator cannot see the change in is not a reviewable candidate."""
    repo = deontic["repo"]
    inventory = inv.build_inventory(ctx, repo)
    artifact = inventory["artifacts"][0]
    text = inv.artifact_text(str(repo), artifact)
    candidate = deontic["result"]["revision_candidates"][0]
    span = candidate["span"]
    assert text[span["start"] : span["end"]] == "MUST"
    assert span["source_sha256"] == artifact["content_sha256"]
    assert candidate["block"]["kind"] == "paragraph"


def test_the_basis_names_both_revisions_and_both_spans(ctx: Context, deontic) -> None:
    """The before span must resolve in the before revision, not in the pinned one."""
    repo = deontic["repo"]
    basis = deontic["result"]["revision_candidates"][0]["candidate_basis"]
    before = inv.blob_bytes(repo, basis["before_revision"], "docs/policy.md").decode("utf-8")
    region = before[basis["before_span"]["start"] : basis["before_span"]["end"]]
    assert "may reject" in region
    assert basis["before_span"]["revision"] == basis["before_revision"]
    assert basis["after_span"]["revision"] == basis["after_revision"]
    assert basis["before_revision"] != basis["after_revision"]


def test_each_protected_axis_is_detected_separately(ctx: Context, tmp_path) -> None:
    """Four movements the standard names separately must not collapse into one axis."""
    repo = build_repo(
        tmp_path / "axes",
        [{"docs/notes.md": FOUR_AXES_V1}, {"docs/notes.md": FOUR_AXES_V2}],
        declaration=AUTHORISED,
    )
    candidates = mine_repo(ctx, repo)["revision_candidates"]
    by_axis = {c["candidate_basis"]["changed_axis"]: c["candidate_basis"] for c in candidates}
    assert set(by_axis) == {"deontic_force", "likelihood", "quantifier_scope", "temporal_order"}
    assert len(candidates) == 4
    assert by_axis["likelihood"]["after_terms"] == ["likely", "very likely"]
    assert by_axis["quantifier_scope"]["before_terms"] == ["Some"]
    assert by_axis["quantifier_scope"]["after_terms"] == ["All"]
    assert by_axis["temporal_order"]["before_terms"] == ["after"]
    assert by_axis["temporal_order"]["after_terms"] == ["before"]


def test_a_cosmetic_reflow_yields_no_candidate(ctx: Context, tmp_path) -> None:
    """Rewrapping and trailing whitespace move nothing the standard protects."""
    repo = build_repo(
        tmp_path / "cosmetic",
        [{"docs/policy.md": COSMETIC_V1}, {"docs/policy.md": COSMETIC_V2}],
        declaration=AUTHORISED,
    )
    result = mine_repo(ctx, repo)
    assert result["revision_candidates"] == []
    # Examined and classified, not a document nobody looked at: both rewrapped
    # paragraphs are replaced regions, and both resolve to cosmetic.
    assert result["revision_scan"]["documents_scanned"] == 1
    assert result["revision_scan"]["replaced_regions"] == 2
    assert result["revision_scan"]["cosmetic"] == 2


def test_insertions_and_deletions_are_counted_not_silently_dropped(
    ctx: Context, tmp_path
) -> None:
    """A region the basis declines to read is reported, per ADR-0002."""
    repo = build_repo(
        tmp_path / "insertion",
        [
            {"docs/policy.md": "# Policy\n\nThe verifier MUST reject a stale receipt.\n"},
            {
                "docs/policy.md": "# Policy\n\nThe verifier MUST reject a stale receipt.\n"
                "\nAll kernels emit a receipt.\n"
            },
        ],
        declaration=AUTHORISED,
    )
    result = mine_repo(ctx, repo)
    assert result["revision_candidates"] == []
    scan = result["revision_scan"]
    assert scan["inserted_regions"] == 1
    assert scan["replaced_regions"] == 0


# -- the interpretation the basis refuses ------------------------------------


def test_normative_interpretation_has_exactly_one_reachable_value(ctx: Context, tmp_path) -> None:
    """A field with two writers is a field an annotator cannot trust.

    The structural half of the check: the module holds one ``unresolved``
    literal, and every site naming ``normative_interpretation`` reads the
    constant rather than a value of its own.
    """
    source = Path(mine.__file__).read_text(encoding="utf-8")
    assert mine.NORMATIVE_INTERPRETATION == "unresolved"
    assert len(re.findall(r"""["']unresolved["']""", source)) == 1

    writers = re.findall(
        r"""["']?normative_interpretation["']?\s*[:=]\s*([A-Za-z_."'\[\]]+)""", source
    )
    assert writers, "no assignment to normative_interpretation was found to check"
    assert set(writers) == {"NORMATIVE_INTERPRETATION"}


def test_every_emitted_candidate_reads_the_pinned_interpretation(
    ctx: Context, tmp_path
) -> None:
    """The behavioural half: four different axis movements, one interpretation."""
    repo = build_repo(
        tmp_path / "pinned",
        [{"docs/notes.md": FOUR_AXES_V1}, {"docs/notes.md": FOUR_AXES_V2}],
        declaration=AUTHORISED,
    )
    candidates = mine_repo(ctx, repo)["revision_candidates"]
    assert len(candidates) == 4
    for candidate in candidates:
        basis = candidate["candidate_basis"]
        assert basis["normative_interpretation"] == mine.NORMATIVE_INTERPRETATION
        assert "not evidence that the earlier text violated a rule" in (
            basis["normative_interpretation_note"]
        )


def test_a_revision_candidate_carries_no_label_and_every_refusal(deontic) -> None:
    """Spec 13.2, 16.5, 17.9: the delta is a reason to look, never a verdict."""
    for candidate in deontic["result"]["revision_candidates"]:
        assert candidate["label"] is None
        assert candidate["candidate_only"] is True
        assert candidate["requires_context_bundle"] is True
        assert "does not establish" in candidate["note"]
        assert [r["refusal_id"] for r in candidate["refusals"]] == list(mine.REFUSAL_IDS)


# -- authority ---------------------------------------------------------------


def test_authority_use_is_one_the_authority_model_declares(ctx: Context) -> None:
    """A gate naming a use nobody can declare would never open, or never close."""
    assert mine.AUTHORITY_USE in auth.USES


def test_an_undeclared_repository_yields_no_revision_candidates(
    ctx: Context, tmp_path
) -> None:
    """An absent declaration resolves unknown, and unknown never inherits allow."""
    repo = build_repo(
        tmp_path / "undeclared",
        [{"docs/policy.md": DEONTIC_V1}, {"docs/policy.md": DEONTIC_V2}],
        declaration=None,
    )
    result = mine_repo(ctx, repo)
    assert result["revision_candidates"] == []
    assert result["revision_scan"]["documents_scanned"] == 0
    reasons = {s["reason"] for s in result["skipped"]}
    assert "revision_basis_unauthorised" in reasons
    # The surface-signal basis is unaffected: this gate is about the history.
    assert result["candidates"]


def test_a_deferred_use_yields_no_revision_candidates(ctx: Context, tmp_path) -> None:
    """``defer`` is an explicit refusal to decide, not a quiet yes."""
    repo = build_repo(
        tmp_path / "deferred",
        [{"docs/policy.md": DEONTIC_V1}, {"docs/policy.md": DEONTIC_V2}],
        declaration=DEFERRED,
    )
    result = mine_repo(ctx, repo)
    assert result["revision_candidates"] == []
    detail = next(
        s["detail"] for s in result["skipped"] if s["reason"] == "revision_basis_unauthorised"
    )
    assert "'defer'" in detail


def test_an_artifact_without_a_recorded_resolution_is_not_authorised() -> None:
    """ADR-0002: a check that did not run reports unknown, never a pass."""
    permitted, detail = mine.candidate_mining_permitted({"extensions": {}})
    assert permitted is False
    assert "unknown" in detail


# -- vocabulary provenance ---------------------------------------------------


def test_no_axis_invents_a_word_list(ctx: Context) -> None:
    """ADR-0006: the lexicon, a verbatim spec list, or a normative schema enum."""
    axes = {a.axis: a for a in mine.build_force_axes(ctx)}
    lexicon = ctx.lexicon

    deontic_sources = (
        set(lexicon.deontic_surfaces.values())
        | set(lexicon.deontic_noncanonical)
        | {str(r["surface"]) for r in lexicon.collision_rules}
    )
    assert set(axes["deontic_force"].phrases) <= deontic_sources
    # The collision surfaces that do not collide with a deontic keyword stay
    # out: "will" collides with forecast and design description, "confidence"
    # with detector confidence, and neither is a deontic surface.
    assert {"may", "should"} <= set(axes["deontic_force"].phrases)
    assert not {"will", "confidence"} & set(axes["deontic_force"].phrases)

    likelihood_sources = (
        set(lexicon.wep_phrases) | set(lexicon.wep_aliases) | set(lexicon.non_probability_terms)
    )
    assert set(axes["likelihood"].phrases) == likelihood_sources

    quantifier_enum = ctx.schemas.schema("ats_common_v1.schema.json")["$defs"]["quantifier"][
        "properties"
    ]["kind"]["enum"]
    assert set(axes["quantifier_scope"].phrases) == set(quantifier_enum)

    # Only the observable-boundary list counts. The section's closing sentence
    # names "promptly", "soon", "regularly", and "eventually" as *nonconforming*
    # timing terms, so a vocabulary drawn from there would cite 9.3.7 for the
    # opposite of what it says; the slice stops before that sentence.
    section = ctx.package.spec_document.read_text(encoding="utf-8")
    section = section.split("#### 9.3.7 Timing and ordering", 1)[1].split("####", 1)[0]
    boundaries = section.split("Terms such as", 1)[0]
    assert "promptly" not in boundaries
    for term in axes["temporal_order"].phrases:
        assert re.search(rf"(?<!\w){re.escape(term)}(?!\w)", boundaries), term


def test_every_axis_declares_where_its_vocabulary_came_from(ctx: Context) -> None:
    """An axis a reviewer cannot audit is an axis nobody can contest."""
    for axis in mine.build_force_axes(ctx):
        assert axis.vocabulary_source
        assert axis.spec_ref.startswith("ATS-1 ")
        assert axis.origin in {"lexicon", "spec_enumeration", "normative_schema_enum"}
        assert axis.phrases


# -- the boundary into annotation --------------------------------------------


def test_the_basis_survives_into_a_stored_context_bundle(ctx: Context, deontic) -> None:
    """Spec 17.4's refusals only bind where the annotator can read them."""
    repo = deontic["repo"]
    inventory = inv.build_inventory(ctx, repo)
    artifact = inventory["artifacts"][0]
    text = inv.artifact_text(str(repo), artifact)
    candidate = deontic["result"]["revision_candidates"][0]

    bundle = corpus_context.build_context_bundle(
        ctx, artifact=artifact, text=text, span=candidate["span"], repo_path=repo
    )
    carried = mine.attach_candidate_basis(bundle, candidate)

    basis = carried["extensions"][mine.EXT_CANDIDATE_BASIS]
    assert basis["normative_interpretation"] == "unresolved"
    assert basis["changed_axis"] == "deontic_force"
    # Re-addressed, not patched: the identifier must follow the new content.
    assert carried["bundle_id"] != bundle["bundle_id"]
    assert rec.verify_record(carried)[0]
    ctx.schemas.validate_document(carried)


def test_attaching_a_basis_that_does_not_exist_is_refused(ctx: Context, deontic) -> None:
    """A surface candidate has no revision basis, and silence would fake one."""
    surface = deontic["result"]["candidates"][0]
    assert "candidate_basis" not in surface
    with pytest.raises(UsageError, match="carries no candidate_basis"):
        mine.attach_candidate_basis({"schema_version": "ats.context_bundle.v1"}, surface)


# -- determinism -------------------------------------------------------------


def test_revision_mining_is_deterministic(ctx: Context, deontic, tmp_path) -> None:
    """Spec 16.2: the same commits produce the same candidates, byte for byte.

    The replay uses the same directory *name*: a corpus record is addressed by
    repository name and path, so a rename is a different document by design.
    """
    repo = build_repo(
        tmp_path / "deontic",
        [{"docs/policy.md": DEONTIC_V1}, {"docs/policy.md": DEONTIC_V2}],
        declaration=AUTHORISED,
    )
    again = mine_repo(ctx, repo)["revision_candidates"]
    first = deontic["result"]["revision_candidates"]
    assert [c["candidate_id"] for c in again] == [c["candidate_id"] for c in first]
    assert [c["candidate_basis"] for c in again] == [c["candidate_basis"] for c in first]

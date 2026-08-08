"""Local Git inventory, against a real repository rather than a mock.

Defends spec Section 16.9 (declare whether source text leaves the environment),
Section 17.4 (what mining MUST preserve, and what it MUST NOT infer), and
Section 17.7 (template and near-duplicate leakage dimensions).
"""

from __future__ import annotations

import datetime as dt
import sys

import pytest

from ats.context import Context
from ats.corpus import inventory as inv
from ats.errors import UsageError
from ats.spec_package import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
from generate_corpus_fixtures import _git as write_git  # noqa: E402
from generate_corpus_fixtures import build_sample_repo  # noqa: E402

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return build_sample_repo(tmp_path_factory.mktemp("git") / "sample-repo")


@pytest.fixture(scope="module")
def inventory(ctx: Context, repo):
    return inv.build_inventory(ctx, repo)


def _by_path(inventory) -> dict[str, dict]:
    return {a["path"]: a for a in inventory["artifacts"]}


def test_no_network_subcommand_can_be_run(repo) -> None:
    """Spec 16.9: corpus mining is local, so a fetching subcommand is refused."""
    for subcommand in ("fetch", "clone", "remote", "push", "pull", "submodule"):
        with pytest.raises(UsageError, match="not a permitted corpus subcommand"):
            inv._git(repo, subcommand)
    assert not inv.READ_ONLY_GIT_SUBCOMMANDS.intersection(
        {"fetch", "clone", "remote", "push", "pull", "submodule"}
    )


def test_revision_is_pinned_per_file_and_at_head(ctx: Context, repo, inventory) -> None:
    """Spec 17.4: the source revision is preserved, per document, not per run."""
    assert inventory["revision"] == inv.head_revision(repo)
    artifacts = _by_path(inventory)
    # assessment.md was edited in the second commit, requirements.md was not,
    # so they are pinned to different commits under the same HEAD.
    assert artifacts["docs/assessment.md"]["revision"] != artifacts["docs/requirements.md"][
        "revision"
    ]
    for artifact in inventory["artifacts"]:
        assert len(artifact["revision"]) == 40


def test_content_hash_is_over_the_pinned_bytes(ctx: Context, repo, inventory) -> None:
    """A dirty worktree must not be hashed under a revision that does not describe it."""
    artifact = _by_path(inventory)["docs/assessment.md"]
    text = inv.artifact_text(repo, artifact)
    assert "Update indicators" in text
    (repo / "docs" / "assessment.md").write_text("clobbered\n", encoding="utf-8")
    try:
        assert inv.artifact_text(repo, artifact) == text
    finally:
        (repo / "docs" / "assessment.md").write_text(text, encoding="utf-8")


def test_merge_is_not_acceptance(inventory) -> None:
    """Spec 17.4: a committed document is not thereby accepted."""
    artifacts = _by_path(inventory)
    assert artifacts["docs/requirements.md"]["review_state"] == "unknown"
    basis = artifacts["docs/requirements.md"]["extensions"]["x-ats-repo-git"][
        "review_state_basis"
    ]
    assert "not evidence of acceptance" in basis


def test_review_state_follows_an_explicit_declaration(inventory) -> None:
    """Only a declared trailer or note moves the state off unknown."""
    accepted = _by_path(inventory)["docs/requirements-copy.md"]
    assert accepted["review_state"] == "accepted"
    assert "trailer" in accepted["extensions"]["x-ats-repo-git"]["review_state_basis"]


def test_review_states_stay_distinct(ctx: Context) -> None:
    """Spec 17.4: accepted, rejected, superseded, and reverted are separate states."""
    assert inv.DECLARABLE_REVIEW_STATES == {"accepted", "rejected", "superseded", "draft"}
    schema = ctx.schemas.schema("ats_source_artifact_v1.schema.json")
    assert set(schema["properties"]["review_state"]["enum"]) == {
        "accepted",
        "rejected",
        "superseded",
        "reverted",
        "draft",
        "unknown",
    }


def test_review_comments_are_collected_from_notes_and_trailers(inventory) -> None:
    """Spec 17.4: locally available review comments are preserved."""
    evidence = _by_path(inventory)["docs/requirements-copy.md"]["acceptance_evidence"]
    assert evidence["availability"] == "present"
    assert len(evidence["reviewers"]) == 2
    assert "Second reviewer" in evidence["notes"]


def test_an_absent_dimension_states_its_availability(inventory) -> None:
    """Spec 17.4: an unavailable dimension is typed, never silently omitted."""
    artifact = _by_path(inventory)["docs/requirements.md"]
    assert artifact["acceptance_evidence"]["availability"] == "not_found"
    assert "searched" in artifact["acceptance_evidence"]["notes"]
    assert artifact["model_provenance"]["availability"] == "not_found"
    later = artifact["extensions"]["x-ats-repo-git"]["later_edits"]
    assert later["availability"] == "not_found"
    assert "last commit touching this path" in later["detail"]


def test_model_provenance_is_read_only_from_a_declaration(inventory) -> None:
    """Spec 17.4: model provenance is recorded where available, never guessed."""
    declared = _by_path(inventory)["docs/assessment.md"]["model_provenance"]
    assert declared["availability"] == "present"
    assert declared["model"] == {"name": "fixture-writer", "version": "1.0.0"}


def test_before_and_after_edits_are_identified(inventory) -> None:
    """Spec 17.4: subsequent edits are preserved as context."""
    git = _by_path(inventory)["docs/assessment.md"]["extensions"]["x-ats-repo-git"]
    assert git["history"]["commit_count"] == 2
    assert git["previous_edit"]["availability"] == "present"
    fresh = _by_path(inventory)["docs/requirements-copy.md"]["extensions"]["x-ats-repo-git"]
    assert fresh["previous_edit"]["availability"] == "not_found"


def test_markdown_and_text_are_inspected_and_the_rest_is_skipped(inventory) -> None:
    """Anything outside Markdown and plain text is skipped with a named reason."""
    paths = set(_by_path(inventory))
    assert paths == {
        "docs/assessment.md",
        "docs/requirements.md",
        "docs/requirements-copy.md",
        "docs/notes.txt",
    }
    skipped = {s["path"]: s["reason"] for s in inventory["skipped"]}
    assert skipped["src/main.py"] == "unsupported_media_type"
    # Markdown is inspected before plain text.
    order = [a["media_type"] for a in inventory["artifacts"]]
    assert order == sorted(order, key=inv.MEDIA_TYPE_ORDER.index)


def test_include_and_exclude_globs(ctx: Context, repo) -> None:
    """Include and exclude are recorded as skips, not silent absences."""
    filtered = inv.build_inventory(ctx, repo, include=("docs/*.md",), exclude=("*copy*",))
    assert set(_by_path(filtered)) == {"docs/assessment.md", "docs/requirements.md"}
    reasons = {s["path"]: s["reason"] for s in filtered["skipped"]}
    assert reasons["docs/notes.txt"] == "not_included"
    assert reasons["docs/requirements-copy.md"] == "excluded"


def test_copied_template_and_near_duplicate_share_a_cluster(inventory) -> None:
    """Spec 17.7: template and near-duplicate cluster are leakage dimensions."""
    artifacts = _by_path(inventory)
    original = artifacts["docs/requirements.md"]
    copy = artifacts["docs/requirements-copy.md"]
    assert original["template_family"] == copy["template_family"]
    assert original["near_duplicate_cluster"] == copy["near_duplicate_cluster"]
    assert original["near_duplicate_cluster"] != artifacts["docs/assessment.md"][
        "near_duplicate_cluster"
    ]


def test_clustering_is_deterministic_and_threshold_driven() -> None:
    """A near-duplicate cluster is a real overlap decision, not a sketch collision.

    A single-value sketch would separate ``a`` and ``b`` here: they differ by
    one sentence, which is exactly the case that must cluster together.
    """
    a = (
        "When the executor presents an acceptance receipt whose policy digest differs from "
        "the current resolved policy snapshot, the verifier rejects the receipt before the "
        "acceptance transition. The refusal record carries both digests and the source "
        "revision so a later reviewer can reconstruct which policy was in force."
    )
    b = a + " An operator may export both digests to the audit log."
    c = (
        "Scheduling windows are expressed in the operator calendar and never inferred from "
        "the deployment log. A window that overlaps a freeze is deferred to the next "
        "available slot, and the deferral is announced on the release channel."
    )
    clusters = inv.near_duplicate_clusters({"a": a, "b": b, "c": c})
    assert clusters["a"] == clusters["b"] != clusters["c"]
    assert clusters == inv.near_duplicate_clusters({"c": c, "b": b, "a": a})
    assert inv.jaccard(inv.shingles(a), inv.shingles(b)) >= inv.NEAR_DUPLICATE_THRESHOLD
    assert inv.jaccard(inv.shingles(a), inv.shingles(c)) < inv.NEAR_DUPLICATE_THRESHOLD


def test_profile_hypotheses_come_from_declared_evidence(inventory) -> None:
    """Profile identification matches the normative profile enum, not invented labels."""
    artifacts = _by_path(inventory)
    assert artifacts["docs/assessment.md"]["profile_hypotheses"] == ["ASSESS"]
    assert artifacts["docs/requirements.md"]["profile_hypotheses"] == ["SPECIFY"]
    # A plain-text note declares nothing, so no hypothesis is manufactured.
    assert "profile_hypotheses" not in artifacts["docs/notes.txt"]


def test_use_authority_and_handling_policy_come_from_a_declaration(inventory) -> None:
    """Spec 17.13: training data MUST record use authority."""
    assert inventory["declaration_present"] is True
    for artifact in inventory["artifacts"]:
        assert artifact["use_authority"] == "external_training_permitted"
        assert artifact["handling_policy"] == "public"


def test_undeclared_repository_reports_unknown_authority(ctx: Context, tmp_path) -> None:
    """Without a declaration the authority is unknown, never assumed permissive."""
    repo = build_sample_repo(tmp_path / "bare")
    (repo / ".ats" / "corpus.json").unlink()
    inv._git(repo, "config", "user.email", "fixture@ats.invalid")
    declaration = inv.Declaration.load(repo)
    assert declaration.declared is False
    assert declaration.use_authority == "unknown"
    assert declaration.handling_policy == "internal"


def test_a_directory_without_git_is_refused(ctx: Context, tmp_path) -> None:
    """An unpinned directory cannot supply a source revision, so it is refused."""
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "doc.md").write_text("# Title\n\nProse.\n", encoding="utf-8")
    with pytest.raises(UsageError, match="not a readable Git repository"):
        inv.build_inventory(ctx, plain)


def test_every_artifact_validates(ctx: Context, inventory) -> None:
    """Every emitted record validates against ats_source_artifact_v1."""
    assert inventory["artifacts"]
    for artifact in inventory["artifacts"]:
        assert ctx.schemas.validate_document(artifact) == "ats_source_artifact_v1.schema.json"


# -- whole-repository git reads ---------------------------------------------
#
# The inventory reads blobs and history for every tracked document. Asking git
# per document cost one process per document per dimension and dominated the
# runtime. These tests pin the batched reads to the per-path answers they
# replaced, because a faster reader that returns different provenance would
# silently change content-addressed records.


def test_history_index_matches_per_path_log(repo) -> None:
    """One walk must answer exactly what one ``git log`` per path answers."""
    revision = inv.head_revision(repo)
    index = inv.history_index(repo, revision)
    paths = inv.tracked_paths(repo, revision)
    assert paths
    for path in paths:
        walked = [c.sha for c in index.get(path, [])]
        per_path = [c.sha for c in inv.path_history(repo, revision, path)]
        assert walked == per_path, path


def test_history_index_preserves_exact_path_bytes(ctx: Context, tmp_path) -> None:
    """A path git would quote must still resolve to its history.

    Without ``-z`` git renders a path holding a tab, a quote, or any non-ASCII
    byte in escaped form, which matches nothing in ``tracked_paths``. Those
    documents would then be dropped from the corpus as though no commit had
    ever touched them, which is a silent loss rather than a reported skip.
    """
    repo = tmp_path / "hostile-paths"
    repo.mkdir()
    write_git(repo, "init", "--quiet")
    # Leading and trailing whitespace are the cases a ``strip`` would silently
    # rewrite; tab, quote, and non-ASCII are the cases git would quote; the
    # bracket, star, and bang are the cases git would read as a pathspec
    # pattern rather than a literal name.
    names = [
        "plain.md",
        " leading.md",
        "trailing .md",
        "with\ttab.md",
        "na\u00efve.md",
        'quote".md',
        "draft[1].md",
        "star*.md",
        "!bang.md",
    ]
    for name in names:
        (repo / name).write_text("a document with several words in it\n", encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "--message", "add documents")

    revision = inv.head_revision(repo)
    # Both forms: the whole-repository walk and the pathspec-restricted walk
    # build_inventory actually uses. A pathspec is interpreted unless git is
    # told otherwise, so the restricted form is where a pattern-like name goes
    # wrong.
    for index in (
        inv.history_index(repo, revision),
        inv.history_index(repo, revision, names),
    ):
        for name in names:
            assert [c.sha for c in index.get(name, [])] == [
                c.sha for c in inv.path_history(repo, revision, name)
            ], name

    inventory = inv.build_inventory(ctx, repo)
    assert {a["path"] for a in inventory["artifacts"]} == set(names)
    assert not [s for s in inventory["skipped"] if s["reason"] == "no_history"]


def test_blob_batch_matches_per_path_read(repo) -> None:
    """The batched object read must return the same bytes, keyed by path."""
    revision = inv.head_revision(repo)
    paths = inv.tracked_paths(repo, revision)
    batch = inv.blob_batch(repo, revision, paths)
    assert set(batch) == set(paths)
    for path in paths:
        assert batch[path] == inv.blob_bytes(repo, revision, path)


def test_blob_batch_omits_a_path_absent_at_the_revision(repo) -> None:
    """A missing object is left out, not reported as empty content."""
    revision = inv.head_revision(repo)
    batch = inv.blob_batch(repo, revision, ["docs/assessment.md", "docs/not-a-file.md"])
    assert "docs/not-a-file.md" not in batch
    assert batch["docs/assessment.md"]


def test_near_duplicate_clustering_equals_all_pairs() -> None:
    """The inverted index is an exact prune, not an approximation.

    Cluster identity is part of a content-addressed record, so a candidate
    filter that missed a qualifying pair would change stored artifacts. The
    reference here is the definition itself: compare every pair.
    """

    def all_pairs(documents, threshold):
        keys = sorted(documents)
        sets = {k: inv.shingles(documents[k]) for k in keys}
        parent = {k: k for k in keys}

        def find(k):
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k

        for i, left in enumerate(keys):
            for right in keys[i + 1 :]:
                if inv.jaccard(sets[left], sets[right]) >= threshold:
                    a, b = find(left), find(right)
                    if a != b:
                        parent[max(a, b)] = min(a, b)
        return {k: find(k) for k in keys}

    base = "the acceptance gate refuses a claim without evidence and records it "
    corpora = [
        {"a": base * 3, "b": base * 3},
        {"a": base * 3, "b": base * 3 + "one two three", "c": "wholly unrelated prose here"},
        {"a": "   ", "b": "\n\n", "c": base * 2},
        {"only": base},
        {f"d{i}": base * 3 + " ".join(str(n) for n in range(i)) for i in range(8)},
    ]
    for documents in corpora:
        for threshold in (0.0, 0.5, 0.8, 1.0, 1.5):
            expected = all_pairs(documents, threshold)
            actual = inv.near_duplicate_clusters(documents, threshold=threshold)
            # Compare the partition, not the label: both must group identically.
            def partition(mapping):
                groups: dict[str, set[str]] = {}
                for key, root in mapping.items():
                    groups.setdefault(root, set()).add(key)
                return sorted(sorted(g) for g in groups.values())

            assert partition(actual) == partition(expected), (documents, threshold)


def test_later_edits_cannot_report_a_commit(inventory) -> None:
    """The pinned revision is the newest commit touching the path, by construction.

    ``later_edits`` therefore has no commit it could ever list. The field is
    kept because consumers read it, but this test records that it is a
    constant rather than a searched dimension.
    """
    for artifact in inventory["artifacts"]:
        later = artifact["extensions"]["x-ats-repo-git"]["later_edits"]
        assert later["availability"] == "not_found"


def test_history_index_matches_per_path_across_a_merge(ctx: Context, tmp_path) -> None:
    """History simplification prunes commits the walk still reports.

    ``git log -- <path>`` reports the commits needed to explain the file's
    current content. When a side branch and the mainline reach the same content
    independently, the merge is TREESAME and the side commit is pruned; a walk
    has no pathspec to simplify against and lists it. The inventory reconciles
    to the per-path answer, so the two must agree here.
    """
    repo = tmp_path / "merged"
    repo.mkdir()
    doc = repo / "doc.md"
    write_git(repo, "init", "--quiet")
    doc.write_text("first version of the document\n", encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "--message", "create")

    write_git(repo, "checkout", "--quiet", "-b", "side")
    doc.write_text("second version of the document\n", encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "--message", "side edit")

    write_git(repo, "checkout", "--quiet", "-")
    # The same content, reached independently. The merge is then TREESAME and
    # the side commit becomes prunable.
    doc.write_text("second version of the document\n", encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "--message", "mainline edit")
    write_git(repo, "merge", "--quiet", "--no-ff", "-m", "merge side", "side")

    revision = inv.head_revision(repo)
    expected = [c.sha for c in inv.path_history(repo, revision, "doc.md")]
    for index in (
        inv.history_index(repo, revision),
        inv.history_index(repo, revision, ["doc.md"]),
    ):
        assert [c.sha for c in index["doc.md"]] == expected

    inventory = inv.build_inventory(ctx, repo)
    artifact = next(a for a in inventory["artifacts"] if a["path"] == "doc.md")
    assert artifact["revision"] == expected[0]
    assert artifact["extensions"]["x-ats-repo-git"]["history"]["commit_count"] == len(expected)


def test_a_file_created_only_by_a_merge_is_not_lost(ctx: Context, tmp_path) -> None:
    """Git lists no files for a merge, so a merge-resolved path needs recovering.

    A document whose content arrives through the merge itself appears in no
    commit's file list. Without reconciliation it would be dropped as though no
    commit had ever touched it, which is a silent loss of a real document.
    """
    repo = tmp_path / "evil-merge"
    repo.mkdir()
    write_git(repo, "init", "--quiet")
    (repo / "base.md").write_text("a base document with words\n", encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "--message", "base")

    write_git(repo, "checkout", "--quiet", "-b", "side")
    (repo / "side.md").write_text("a side document with words\n", encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "--message", "side document")

    write_git(repo, "checkout", "--quiet", "-")
    write_git(repo, "merge", "--quiet", "--no-ff", "--no-commit", "side")
    # Introduced by the merge commit itself, so no ordinary commit lists it.
    (repo / "resolved.md").write_text("resolved during the merge\n", encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "--message", "merge side")

    revision = inv.head_revision(repo)
    index = inv.history_index(repo, revision)
    assert [c.sha for c in index.get("resolved.md", [])] == [
        c.sha for c in inv.path_history(repo, revision, "resolved.md")
    ]
    assert index["resolved.md"], "a merge-resolved document must carry a history"

    inventory = inv.build_inventory(ctx, repo)
    assert "resolved.md" in {a["path"] for a in inventory["artifacts"]}


def test_a_rename_stays_in_the_source_path_history(ctx: Context, tmp_path) -> None:
    """A commit that renames a document away belongs to that document's history.

    With rename detection on, ``--name-only`` reports a rename as touching the
    destination alone, so the source name never appears in the walk. Pathspec
    matching happens before renames are paired and still sees the deletion, so
    ``git log -- <source>`` does report the commit. Left unfixed, the rename
    disappears from the provenance of a path that was renamed away and later
    reused -- found on a real repository, not hypothesised.
    """
    repo = tmp_path / "renamed"
    repo.mkdir()
    write_git(repo, "init", "--quiet")
    original = repo / "README.md"
    original.write_text(
        "a document with enough words in it to be detected as a rename\n", encoding="utf-8"
    )
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "--message", "create")

    (repo / "nested").mkdir()
    original.rename(repo / "nested" / "README.md")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "--message", "rename away")

    original.write_text("a different document now at the original path\n", encoding="utf-8")
    write_git(repo, "add", "--all")
    write_git(repo, "commit", "--quiet", "--message", "reuse the original path")

    revision = inv.head_revision(repo)
    expected = [c.sha for c in inv.path_history(repo, revision, "README.md")]
    assert len(expected) == 3, "the rename is part of the source path's history"
    for index in (
        inv.history_index(repo, revision),
        inv.history_index(repo, revision, ["README.md", "nested/README.md"]),
    ):
        assert [c.sha for c in index["README.md"]] == expected

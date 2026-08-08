"""The census reproducibility receipt.

A census reports statistics over documents a miner selected and read. When a
statistic moves, either the corpus moved or the miner did, and the statistics
alone cannot say which. Every test here defends one of the bindings that makes
the difference visible, or one of the refusals that keeps a missing input from
looking like a measured one: a partial artifact list passed off as a smaller
corpus, an unconfigured selection passed off as an empty one, an untimed run
passed off as a fast one, an absent authority declaration passed off as a
declared one, or a dirty worktree passed off as a replayable revision.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

import pytest

from ats.canonical import sha256_hex, verify_seal
from ats.context import Context
from ats.corpus import authority as auth
from ats.corpus import inventory as inv
from ats.corpus import receipt as rc
from ats.corpus.records import EXT_PREFIX
from ats.errors import UsageError

#: Where ``build_inventory`` records the git dimensions of one artifact.
GIT_EXTENSION = f"{EXT_PREFIX}git"

NOW = dt.datetime(2026, 8, 3, tzinfo=dt.UTC)

#: Fixed identity and no signing, so a repository built here is reproducible
#: and does not depend on the developer's git configuration.
GIT_CONFIG = (
    "-c",
    "user.name=ATS Test",
    "-c",
    "user.email=test@ats.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "init.defaultBranch=main",
)


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


def git(repo: Path, *argv: str) -> None:
    subprocess.run(
        ["git", *GIT_CONFIG, "-C", str(repo), *argv],
        check=True,
        capture_output=True,
        env={"GIT_CONFIG_NOSYSTEM": "1", "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


def clean_checkout(path: Path) -> Path:
    """A committed, unmodified git repository standing in for this checkout."""
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "--quiet")
    (path / "code.py").write_text("x = 1\n", encoding="utf-8")
    git(path, "add", "--all")
    git(path, "commit", "--quiet", "--message", "initial")
    return path


# -- inputs ------------------------------------------------------------------


def artifact(identifier: str, *, authority_location: str | None | bool = False) -> dict:
    """One inventory artifact, reduced to the fields the receipt reads.

    ``authority_location`` is ``False`` when the artifact carries no resolved
    authority at all, which is what an inventory built before authority was
    resolved per artifact looks like.
    """
    git_extension: dict = {"history": {"availability": "present", "commit_count": 1}}
    if authority_location is not False:
        git_extension["authority"] = {"declaration_location": authority_location}
    return {
        "schema_version": "ats.source_artifact.v1",
        "artifact_id": identifier,
        "extensions": {GIT_EXTENSION: git_extension},
    }


def inventory(repo: Path, *identifiers: str, authority_location: str | None | bool = False) -> dict:
    return {
        "repository": str(repo),
        "revision": "a" * 40,
        "declaration_present": False,
        "artifacts": [artifact(i, authority_location=authority_location) for i in identifiers],
        "skipped": [],
    }


def census_entry(repository: str, family: str, documents: int) -> dict:
    return {
        "repository": repository,
        "family": family,
        "revision": "a" * 40,
        "documents": documents,
    }


def census(*entries: dict, probes: tuple[dict, ...] = ()) -> dict:
    return {
        "schema_version": "x-ats-repo.corpus_census.v0",
        "generated_at": "2026-08-03T00:00:00Z",
        "spec_version": "1.0.0-draft.1",
        "implementation": {"name": "ats", "version": "0.1.0"},
        "stage": "caller-supplied inventory (no labels)",
        "repositories": list(entries),
        "template_collapse_probes": list(probes),
        "totals": {
            "repositories": len(entries),
            "documents": sum(e["documents"] for e in entries),
            "bytes": 1024,
            "families": len({e["family"] for e in entries}),
            "domains": ["prose"],
            "outside_constellation": 0,
            "candidates": 12,
            "distinct_rules_touched": 3,
        },
        "gate": {
            "checks": [
                {"name": "use authority is explicit", "passed": False, "detail": "nothing declared"}
            ],
            "passed": 0,
            "total": 1,
            "clear_to_label": False,
            "lines": ["[FAIL] use authority is explicit"],
        },
    }


@pytest.fixture
def pilot(tmp_path: Path) -> dict:
    """A census directory with two repositories, one of them a probe.

    ``left`` ships nothing, so its authority resolves to absent. ``right``
    is covered by an operator overlay, so its declaration has bytes to hash.
    """
    repos = tmp_path / "repos"
    left = repos / "left"
    right = repos / "right"
    for repo in (left, right):
        repo.mkdir(parents=True)

    overlay = tmp_path / "authority"
    overlay.mkdir()
    declaration = {
        "schema_version": auth.SCHEMA_VERSION,
        "principal": {"id": "https://example.invalid/fixture-owner", "kind": "person"},
        "authority_basis": {
            "kind": "owner_declared",
            "statement": "The principal authored every commit in this synthetic fixture.",
        },
        "repository": {
            "name": "right",
            "origin": None,
            "root_commit": "b" * 64,
            "effective_from_revision": "b" * 40,
            "declaration_location": "pilot_overlay",
        },
        "uses": {use: "allow_private" for use in auth.USES},
        "content": {"include": ["*"]},
        "issued_at": "2026-01-01T00:00:00+00:00",
        "review_after": "2027-01-01T00:00:00+00:00",
        "superseded_by": None,
        "handling": {"classification": "private", "export_raw_text": False},
        "provenance": {
            "authorship": "unknown_unless_explicit",
            "model_authorship_inference": "prohibited",
        },
    }
    (overlay / "right.json").write_text(json.dumps(declaration), encoding="utf-8")

    census_dir = tmp_path / "synthetic-corpus"
    raw = census_dir / "raw"
    raw.mkdir(parents=True)
    document = census(
        census_entry("left", "prose", 2),
        census_entry("right", "specs", 1),
        probes=(census_entry("right", "generated", 1),),
    )
    census_dir.joinpath("census.json").write_text(
        json.dumps(document, indent=2) + "\n", encoding="utf-8"
    )
    # Deliberately not in collection order: the identifiers a later run compares
    # must be sorted by the receipt, not by the order the inventories happened
    # to be read in.
    raw.joinpath("left-prose.json").write_text(
        json.dumps(inventory(left, "ats-artifact-sha256:d", "ats-artifact-sha256:b")),
        encoding="utf-8",
    )
    raw.joinpath("right-specs.json").write_text(
        json.dumps(inventory(right, "ats-artifact-sha256:a")), encoding="utf-8"
    )
    raw.joinpath("right-generated.json").write_text(
        json.dumps(inventory(right, "ats-artifact-sha256:c")), encoding="utf-8"
    )
    return {
        "census_dir": census_dir,
        "raw": raw,
        "overlay": overlay,
        "left": left,
        "right": right,
        "checkout": clean_checkout(tmp_path / "checkout"),
    }


def build(ctx: Context, pilot: dict, *, runs: tuple[rc.RepositoryRun, ...] = ()) -> dict:
    return rc.build_census_receipt(
        ctx,
        pilot["census_dir"],
        runs=runs,
        implementation_repo=pilot["checkout"],
        authority_overlay=pilot["overlay"],
    )


def entry_for(receipt: dict, repository: str, family: str) -> dict:
    for entry in receipt["repositories"]:
        if entry["repository"] == repository and entry["family"] == family:
            return entry
    raise AssertionError(f"no entry for {repository}/{family}")


# -- the record itself -------------------------------------------------------


def test_the_receipt_validates_against_its_own_schema(ctx: Context, pilot: dict) -> None:
    receipt = build(ctx, pilot)
    assert ctx.schemas.validate_document(receipt) == "ats_census_receipt_v1.schema.json"


def test_every_inventory_is_bound_including_the_probes(ctx: Context, pilot: dict) -> None:
    """A probe reads a repository at a revision exactly as a census entry does.

    Leaving probes out would leave part of the run unpinned while the receipt
    claimed to describe it.
    """
    receipt = build(ctx, pilot)
    assert [(e["repository"], e["family"], e["role"]) for e in receipt["repositories"]] == [
        ("left", "prose", "census"),
        ("right", "specs", "census"),
        ("right", "generated", "template_probe"),
    ]
    assert all(len(e["revision"]) == 40 for e in receipt["repositories"])


def test_emitting_twice_over_unchanged_inputs_is_byte_identical(
    ctx: Context, pilot: dict
) -> None:
    """The receipt is the comparison anchor, so its bytes may not drift on their own."""
    first = rc.receipt_bytes(build(ctx, pilot))
    second = rc.receipt_bytes(build(ctx, pilot))
    assert first == second
    written = rc.write_census_receipt(pilot["census_dir"], build(ctx, pilot))
    assert written.read_bytes() == first


def test_the_receipt_is_content_addressed(ctx: Context, pilot: dict) -> None:
    ok, declared, recomputed = verify_seal(build(ctx, pilot))
    assert ok, (declared, recomputed)


# -- artifact identity -------------------------------------------------------


def test_the_artifact_digest_moves_when_one_identifier_changes(
    ctx: Context, pilot: dict
) -> None:
    """The digest is what a later run compares first; it must be sensitive."""
    before = build(ctx, pilot)["artifact_identity"]

    path = pilot["raw"] / "right-specs.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["artifacts"][0]["artifact_id"] = "ats-artifact-sha256:changed"
    path.write_text(json.dumps(document), encoding="utf-8")

    after = build(ctx, pilot)["artifact_identity"]
    assert after["count"] == before["count"] == 4
    assert after["digest"] != before["digest"]
    assert "ats-artifact-sha256:changed" in after["artifact_ids"]


def test_the_artifact_list_is_sorted(ctx: Context, pilot: dict) -> None:
    """An unsorted list would make the digest depend on inventory order."""
    ids = build(ctx, pilot)["artifact_identity"]["artifact_ids"]
    assert ids == sorted(ids)


def test_a_missing_inventory_refuses_a_partial_identifier_list(
    ctx: Context, pilot: dict
) -> None:
    """A shortened list is indistinguishable from a corpus that shrank."""
    (pilot["raw"] / "right-specs.json").unlink()
    receipt = build(ctx, pilot)

    identity = receipt["artifact_identity"]
    assert identity["availability"] == "unavailable"
    assert "right-specs.json" in identity["detail"]
    assert "artifact_ids" not in identity and "digest" not in identity

    missing = entry_for(receipt, "right", "specs")["raw_inventory"]
    assert missing["availability"] == "not_found"
    assert missing["sha256"] is None


def test_the_inventory_bytes_are_bound(ctx: Context, pilot: dict) -> None:
    """Raw inventories stay gitignored, so a digest is how a receipt cites one."""
    before = entry_for(build(ctx, pilot), "left", "prose")["raw_inventory"]

    path = pilot["raw"] / "left-prose.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["skipped"] = [{"path": "x.bin", "reason": "unsupported_media_type"}]
    path.write_text(json.dumps(document), encoding="utf-8")

    after = entry_for(build(ctx, pilot), "left", "prose")["raw_inventory"]
    assert after["sha256"] != before["sha256"]
    assert after["artifacts"] == before["artifacts"] == 2


# -- the implementation side -------------------------------------------------


def test_a_dirty_implementation_worktree_is_recorded_as_dirty(
    ctx: Context, pilot: dict
) -> None:
    """A dirty tree means the revision does not name the code that ran."""
    clean = build(ctx, pilot)["implementation"]["worktree"]
    assert clean["state"] == "clean"
    assert clean["changed_paths"] == []

    (pilot["checkout"] / "code.py").write_text("x = 2\n", encoding="utf-8")
    dirty = build(ctx, pilot)["implementation"]["worktree"]
    assert dirty["state"] == "dirty"
    assert dirty["changed_paths"] == ["code.py"]


def test_an_untracked_file_counts_as_dirty(ctx: Context, pilot: dict) -> None:
    """Deciding which untracked files could matter would mean inspecting them."""
    (pilot["checkout"] / "scratch.py").write_text("y = 3\n", encoding="utf-8")
    worktree = build(ctx, pilot)["implementation"]["worktree"]
    assert worktree["state"] == "dirty"
    assert worktree["changed_paths"] == ["scratch.py"]


def test_an_unreadable_checkout_is_unknown_not_clean(
    ctx: Context, pilot: dict, tmp_path: Path
) -> None:
    """`unknown` and `clean` are different claims; nobody looked is not nothing found."""
    outside = tmp_path / "not-a-repository"
    outside.mkdir()
    implementation = rc.build_census_receipt(
        ctx,
        pilot["census_dir"],
        implementation_repo=outside,
        authority_overlay=pilot["overlay"],
    )["implementation"]
    assert implementation["revision"]["availability"] == "unavailable"
    assert implementation["worktree"]["state"] == "unknown"
    assert implementation["worktree"]["detail"]


def test_the_clustering_procedure_and_its_parameters_are_both_bound(
    ctx: Context, pilot: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parameters can stay fixed while the procedure changes, and either moves a cluster."""
    receipt = build(ctx, pilot)
    assert receipt["implementation"]["clustering"] == {
        "near_duplicate_version": inv.NEAR_DUPLICATE_VERSION,
        "shingle_width": inv.SHINGLE_WIDTH,
        "near_duplicate_threshold": inv.NEAR_DUPLICATE_THRESHOLD,
    }
    assert receipt["implementation"]["normalization_version"] == "ats-normalize-v1"

    # Read from the constants that drive the clustering, not restated here: a
    # receipt that hardcoded them would keep reporting 5 after a change to 7.
    monkeypatch.setattr(inv, "SHINGLE_WIDTH", 7)
    monkeypatch.setattr(inv, "NEAR_DUPLICATE_VERSION", "ats-near-duplicate-v2")
    moved = build(ctx, pilot)["implementation"]["clustering"]
    assert moved["shingle_width"] == 7
    assert moved["near_duplicate_version"] == "ats-near-duplicate-v2"


# -- selection and wall clock ------------------------------------------------


def test_an_unconfigured_inventory_reports_no_selection_rather_than_an_empty_one(
    ctx: Context, pilot: dict
) -> None:
    """Empty globs are a selection. Not knowing the globs is not."""
    selection = entry_for(build(ctx, pilot), "left", "prose")["selection"]
    assert selection["availability"] == "unavailable"
    assert "include" not in selection and "exclude" not in selection
    assert selection["detail"]


def test_a_configured_inventory_records_the_globs_it_was_given(
    ctx: Context, pilot: dict
) -> None:
    runs = (
        rc.RepositoryRun(
            inventory="left-prose.json",
            include=("docs/*",),
            exclude=("tests/*", "*/vendor/*"),
            elapsed_seconds=2.5,
        ),
    )
    entry = entry_for(build(ctx, pilot, runs=runs), "left", "prose")
    assert entry["selection"] == {
        "availability": "present",
        "include": ["docs/*"],
        "exclude": ["tests/*", "*/vendor/*"],
    }
    assert entry["elapsed"] == {"availability": "present", "seconds": 2.5}


def test_an_untimed_inventory_is_not_reported_as_a_zero(ctx: Context, pilot: dict) -> None:
    runs = (
        rc.RepositoryRun(
            inventory="left-prose.json", include=(), exclude=(), elapsed_seconds=None
        ),
    )
    elapsed = entry_for(build(ctx, pilot, runs=runs), "left", "prose")["elapsed"]
    assert elapsed["availability"] == "not_searched"
    assert "seconds" not in elapsed


def test_a_partially_timed_run_reports_no_total(ctx: Context, pilot: dict) -> None:
    """Summing the measured subset would understate the run while looking measured."""
    runs = (
        rc.RepositoryRun(
            inventory="left-prose.json", include=(), exclude=(), elapsed_seconds=1.0
        ),
    )
    total = build(ctx, pilot, runs=runs)["elapsed"]
    assert total["availability"] == "unavailable"
    assert "total_seconds" not in total
    assert (total["measured_repositories"], total["total_repositories"]) == (1, 3)


def test_a_fully_timed_run_totals_every_inventory(ctx: Context, pilot: dict) -> None:
    runs = tuple(
        rc.RepositoryRun(inventory=name, include=(), exclude=(), elapsed_seconds=seconds)
        for name, seconds in (
            ("left-prose.json", 1.5),
            ("right-specs.json", 0.25),
            ("right-generated.json", 0.25),
        )
    )
    total = build(ctx, pilot, runs=runs)["elapsed"]
    assert total == {
        "availability": "present",
        "total_seconds": 2.0,
        "measured_repositories": 3,
        "total_repositories": 3,
    }


# -- authority ---------------------------------------------------------------


def test_an_undeclared_repository_records_a_null_digest_not_a_placeholder(
    ctx: Context, pilot: dict
) -> None:
    """A stand-in digest would make an unauthorised repository look declared."""
    declaration = entry_for(build(ctx, pilot), "left", "prose")["authority_declaration"]
    assert declaration["availability"] == "not_found"
    assert declaration["sha256"] is None
    assert declaration["location"] is None
    assert declaration["detail"]


def test_a_declaration_is_bound_by_its_exact_bytes(ctx: Context, pilot: dict) -> None:
    before = entry_for(build(ctx, pilot), "right", "specs")["authority_declaration"]
    assert before["availability"] == "present"
    assert before["location"] == "pilot_overlay"
    assert before["declared_by"] == "owner_declared"
    assert before["effective_from_revision"] == "b" * 40

    overlay = pilot["overlay"] / "right.json"
    document = json.loads(overlay.read_text(encoding="utf-8"))
    document["uses"]["model_training"] = "deny"
    overlay.write_text(json.dumps(document), encoding="utf-8")

    after = entry_for(build(ctx, pilot), "right", "specs")["authority_declaration"]
    assert after["sha256"] != before["sha256"]


def test_a_repository_declaration_outranks_the_overlay_in_the_digest(
    ctx: Context, pilot: dict
) -> None:
    """The receipt must hash the declaration the loader would use, not the overlay."""
    local = pilot["right"] / auth.REPOSITORY_DECLARATION
    local.parent.mkdir(parents=True)
    document = json.loads((pilot["overlay"] / "right.json").read_text(encoding="utf-8"))
    document["uses"]["candidate_mining"] = "deny"
    # The same policy, now declared in place. The location has to move with the
    # file: a declaration sitting in the repository that still calls itself an
    # overlay is refused, because a declaration may not state a provenance
    # other than the one it was found at.
    document["repository"]["declaration_location"] = "repository"
    local.write_text(json.dumps(document), encoding="utf-8")

    declaration = entry_for(build(ctx, pilot), "right", "specs")["authority_declaration"]
    assert declaration["location"] == "repository"
    assert declaration["source"] == auth.REPOSITORY_DECLARATION
    assert declaration["sha256"] == sha256_hex(local.read_bytes())


def test_an_authority_basis_the_run_did_not_use_is_flagged_as_diverged(
    ctx: Context, pilot: dict
) -> None:
    """A digest of today's declaration does not bind yesterday's run."""
    path = pilot["raw"] / "right-specs.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    for record in document["artifacts"]:
        record["extensions"][GIT_EXTENSION]["authority"] = {
            "declaration_location": "repository"
        }
    path.write_text(json.dumps(document), encoding="utf-8")

    declaration = entry_for(build(ctx, pilot), "right", "specs")["authority_declaration"]
    assert declaration["location"] == "pilot_overlay"
    assert declaration["inventory_agreement"] == "diverged"
    assert "does not bind" in declaration["detail"]


def test_an_authority_basis_the_run_recorded_agrees(ctx: Context, pilot: dict) -> None:
    path = pilot["raw"] / "right-specs.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    for record in document["artifacts"]:
        record["extensions"][GIT_EXTENSION]["authority"] = {
            "declaration_location": "pilot_overlay"
        }
    path.write_text(json.dumps(document), encoding="utf-8")

    declaration = entry_for(build(ctx, pilot), "right", "specs")["authority_declaration"]
    assert declaration["inventory_agreement"] == "agrees"


def test_an_inventory_recording_two_declaration_locations_is_refused(
    ctx: Context, pilot: dict
) -> None:
    """One repository resolves one declaration; two means the inventory is broken."""
    path = pilot["raw"] / "left-prose.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    for record, location in zip(document["artifacts"], ("repository", "pilot_overlay")):
        record["extensions"][GIT_EXTENSION]["authority"] = {
            "declaration_location": location
        }
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(UsageError, match="internally inconsistent"):
        build(ctx, pilot)


# -- what is copied rather than recomputed -----------------------------------


def test_the_census_bytes_are_bound(ctx: Context, pilot: dict) -> None:
    """Without this, a receipt could be paired with any census."""
    path = pilot["census_dir"] / "census.json"
    before = build(ctx, pilot)["census"]

    document = json.loads(path.read_text(encoding="utf-8"))
    document["totals"]["bytes"] = 2048
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    after = build(ctx, pilot)["census"]
    assert after["sha256"] != before["sha256"]
    assert after["sha256"] == sha256_hex(path.read_bytes())


def test_the_statistics_and_gate_are_copied_from_the_census(
    ctx: Context, pilot: dict
) -> None:
    """Recomputing here would create a second answer that can disagree."""
    path = pilot["census_dir"] / "census.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["totals"]["documents"] = 999
    document["gate"]["checks"][0]["passed"] = True
    document["gate"]["passed"] = 1
    document["gate"]["clear_to_label"] = True
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    receipt = build(ctx, pilot)
    assert receipt["corpus_statistics"]["documents"] == 999
    assert receipt["stage_1_gate"]["clear_to_label"] is True
    assert receipt["stage_1_gate"]["checks"][0]["passed"] is True
    # The rendered gate lines are a projection of the same four checks and are
    # deliberately not carried into the receipt.
    assert "lines" not in receipt["stage_1_gate"]


def test_a_census_missing_a_field_is_refused_rather_than_defaulted(
    ctx: Context, pilot: dict
) -> None:
    """A substituted value would bind a run that never happened."""
    path = pilot["census_dir"] / "census.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    del document["totals"]
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(UsageError, match="carries no 'totals'"):
        build(ctx, pilot)


def test_a_census_that_cannot_be_read_is_refused(ctx: Context, tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="cannot read the census"):
        rc.build_census_receipt(ctx, tmp_path)

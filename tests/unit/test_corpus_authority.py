"""Per-use corpus authority.

Defends spec Section 16.9 (declare whether source text leaves the environment)
and Section 17.13 (a repository declares how its prose may be used).

The property under test throughout is that a permission never appears without
somebody granting it. Every case here is a way that could go wrong: a use
inheriting from a sibling, a subtree out-declaring its repository, a consumer
authorising itself, vendored content borrowing its host's authority, or a
locally granted use carrying text off the machine.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import subprocess
from pathlib import Path

import pytest

from ats.context import Context
from ats.corpus import authority as auth
from ats.corpus import frame
from ats.corpus import inventory as inv
from ats.errors import UsageError

NOW = dt.datetime(2026, 8, 3, tzinfo=dt.UTC)


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


#: The clock the fixture declaration is live at. It sits inside
#: ``issued_at``..``review_after`` so that resolution under a clock is the
#: ordinary case and expiry has to be asked for explicitly.
ISSUED_AT = "2026-01-01T00:00:00+00:00"
REVIEW_AFTER = "2027-01-01T00:00:00+00:00"


def declaration(**overrides) -> dict:
    """A minimal valid declaration; individual tests bend one field."""
    base = {
        "schema_version": auth.SCHEMA_VERSION,
        "principal": {"id": "https://example.invalid/sample-owner", "kind": "person"},
        "authority_basis": {
            "kind": "owner_declared",
            "statement": "The principal authored every commit in this repository.",
        },
        "repository": {
            "name": "sample",
            "origin": None,
            "root_commit": "0" * 64,
            "effective_from_revision": "0" * 40,
            "declaration_location": "repository",
        },
        "uses": {use: "allow" for use in auth.USES},
        "content": {"include": ["*"]},
        "issued_at": ISSUED_AT,
        "review_after": REVIEW_AFTER,
        "superseded_by": None,
        "handling": {"classification": "private", "export_raw_text": False},
        "provenance": {
            "authorship": "unknown_unless_explicit",
            "model_authorship_inference": "prohibited",
        },
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = {**base[key], **value}
        else:
            base[key] = value
    return base


def load(data: dict, *, location: str = "repository") -> auth.AuthorityDeclaration:
    return auth.AuthorityDeclaration.from_dict(data, repository="sample", location=location)


# -- the intersection itself -------------------------------------------------


def test_intersection_takes_the_most_restrictive_value() -> None:
    assert auth.intersect("allow", "deny") == "deny"
    assert auth.intersect("allow", "defer") == "defer"
    assert auth.intersect("allow", "allow_private") == "allow_private"
    assert auth.intersect("allow", "allow") == "allow"


def test_unknown_never_inherits_allow() -> None:
    """The absence of a declaration is not a grant, whatever sits beside it."""
    assert auth.intersect("unknown", "allow") == "unknown"
    assert auth.intersect("allow", "unknown") == "unknown"
    assert not auth.permits(auth.intersect("unknown", "allow"))


def test_an_explicit_refusal_outranks_an_absent_one() -> None:
    """Both block, but a refusal is a decision and absence is not.

    Keeping them apart is what lets a report say whether a use was refused or
    merely never considered.
    """
    assert auth.intersect("unknown", "deny") == "deny"


def test_intersecting_nothing_is_unknown_not_allow() -> None:
    assert auth.intersect() == "unknown"


def test_defer_does_not_permit() -> None:
    """`defer` is an explicit refusal to decide; undecided is not authorised."""
    assert not auth.permits("defer")
    assert auth.permits("allow")
    assert auth.permits("allow_private")
    assert not auth.permits("deny")
    assert not auth.permits("unknown")


def test_an_unrecognised_value_is_refused_not_coerced() -> None:
    with pytest.raises(UsageError, match="is not an authority value"):
        auth.intersect("allow", "probably")


# -- declarations ------------------------------------------------------------


def test_an_undeclared_repository_permits_nothing(ctx: Context) -> None:
    undeclared = auth.AuthorityDeclaration.undeclared("nobody")
    for use in auth.USES:
        resolved = undeclared.resolve(use)
        assert resolved.value == "unknown"
        assert not resolved.permitted
        assert resolved.basis == ("no-declaration",)
    assert undeclared.coarse_use_authority() == "unknown"


def test_an_omitted_use_is_unknown_not_inherited() -> None:
    """A declaration that answers nine uses has not answered the tenth."""
    partial = declaration()
    del partial["uses"]["model_training"]
    resolved = load(partial).resolve("model_training")
    assert resolved.value == "unknown"
    assert not resolved.permitted


def test_a_declaration_must_answer_with_a_known_vocabulary() -> None:
    bad = declaration()
    bad["uses"]["model_training"] = "probably"
    with pytest.raises(UsageError, match="expected one of"):
        load(bad)


def test_a_foreign_schema_version_is_refused() -> None:
    stale = declaration()
    stale["schema_version"] = "ats.corpus_authority.v0"
    with pytest.raises(UsageError, match="schema_version"):
        load(stale)


# -- what may only restrict --------------------------------------------------


def test_a_non_owner_declaration_cannot_grant_an_open_use() -> None:
    """A consumer must not be able to authorise itself by writing a manifest."""
    consumer = load(declaration(authority_basis={"kind": "operator_pilot_overlay"}))
    resolved = consumer.resolve("model_training", "docs/a.md")
    assert resolved.value == "allow_private"
    assert any("non-owner-authority-capped" in b for b in resolved.basis)


def test_a_path_override_can_restrict_but_not_widen() -> None:
    data = declaration()
    data["uses"]["publication"] = "deny"
    data["path_overrides"] = [
        {"pattern": "docs/public/*", "uses": {"publication": "allow"}},
        {"pattern": "docs/secret/*", "uses": {"candidate_mining": "deny"}},
    ]
    resolved = load(data)
    # The subtree asks for more than the repository grants, and does not get it.
    assert resolved.resolve("publication", "docs/public/a.md").value == "deny"
    # Asking for less is honoured.
    assert resolved.resolve("candidate_mining", "docs/secret/a.md").value == "deny"
    assert resolved.resolve("candidate_mining", "docs/other/a.md").value == "allow"


def test_vendored_content_caps_at_unknown_rather_than_deny() -> None:
    """The repository owner did not write vendored text and cannot license it.

    Nobody refused it either, so the honest state is missing authority.
    """
    resolved = load(declaration()).resolve(
        "candidate_mining", "vendor/x/README.md", vendored=True
    )
    assert resolved.value == "unknown"
    assert not resolved.permitted
    assert "vendored-content" in resolved.basis


def test_an_operator_exclusion_blocks_a_permitted_use() -> None:
    resolved = load(declaration()).resolve(
        "candidate_mining", "docs/a.md", exclusions=("docs/*",)
    )
    assert resolved.value == "unknown"
    assert "operator-exclusion" in resolved.basis


def test_a_path_outside_the_declared_content_scope_is_unknown() -> None:
    data = declaration()
    data["content"] = {"include": ["docs/*"]}
    resolved = load(data)
    assert resolved.resolve("candidate_mining", "docs/a.md").permitted
    assert resolved.resolve("candidate_mining", "src/a.py").value == "unknown"


def test_a_local_grant_does_not_authorise_sending_text_away() -> None:
    """Permission to mine is not permission to hand the text to a third party."""
    data = declaration()
    data["uses"]["external_model_submission"] = "deny"
    resolved = load(data).resolve("candidate_mining", "docs/a.md", destination="anthropic")
    assert resolved.value == "deny"
    assert not resolved.permitted
    assert any("destination:anthropic" in b for b in resolved.basis)
    # The same use is still permitted locally.
    assert load(data).resolve("candidate_mining", "docs/a.md", destination="local").permitted


def test_an_unknown_use_name_is_refused() -> None:
    with pytest.raises(UsageError, match="is not a corpus use"):
        load(declaration()).resolve("telepathy")


# -- projection onto the artifact record -------------------------------------


def test_coarse_projection_reports_internal_only_while_training_is_deferred() -> None:
    """The pilot state: mine and annotate locally, do not train yet."""
    data = declaration()
    data["uses"].update({"model_training": "defer", "external_model_submission": "deny"})
    assert load(data).coarse_use_authority("docs/a.md") == "internal_only"


def test_coarse_projection_distinguishes_internal_from_external_training() -> None:
    internal = declaration()
    internal["uses"].update(
        {"model_training": "allow", "external_model_submission": "deny"}
    )
    assert load(internal).coarse_use_authority("docs/a.md") == "internal_training_permitted"

    external = declaration()
    external["uses"].update(
        {"model_training": "allow", "external_model_submission": "allow"}
    )
    assert load(external).coarse_use_authority("docs/a.md") == "external_training_permitted"


def test_coarse_projection_separates_refusal_from_absence() -> None:
    refused = declaration()
    refused["uses"]["inventory"] = "deny"
    assert load(refused).coarse_use_authority("docs/a.md") == "prohibited"

    absent = declaration()
    absent["uses"]["inventory"] = "unknown"
    assert load(absent).coarse_use_authority("docs/a.md") == "unknown"


def test_model_authorship_inference_is_prohibited_by_default() -> None:
    assert not load(declaration()).permits_model_authorship_inference()
    assert not auth.AuthorityDeclaration.undeclared("x").permits_model_authorship_inference()


# -- loading -----------------------------------------------------------------


def test_a_repository_declaration_wins_over_an_operator_overlay(tmp_path) -> None:
    """An overlay is scaffolding. It must never mask what a repository says."""
    repo = tmp_path / "repo"
    (repo / ".ats").mkdir(parents=True)
    local = declaration(repository={"name": "repo", "declaration_location": "repository"})
    local["uses"]["candidate_mining"] = "deny"
    (repo / ".ats" / "corpus.json").write_text(json.dumps(local), encoding="utf-8")

    overlay_dir = tmp_path / "overlay"
    overlay_dir.mkdir()
    overlay = declaration(repository={"name": "repo", "declaration_location": "pilot_overlay"})
    (overlay_dir / "repo.json").write_text(json.dumps(overlay), encoding="utf-8")

    resolved = auth.AuthorityDeclaration.load(repo, overlay_dir=overlay_dir)
    assert resolved.declaration_location == "repository"
    assert resolved.resolve("candidate_mining", "docs/a.md").value == "deny"


def test_an_overlay_answers_only_when_the_repository_is_silent(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    overlay_dir = tmp_path / "overlay"
    overlay_dir.mkdir()
    (overlay_dir / "repo.json").write_text(
        json.dumps(
            declaration(
                repository={"name": "repo", "declaration_location": "pilot_overlay"}
            )
        ),
        encoding="utf-8",
    )
    resolved = auth.AuthorityDeclaration.load(repo, overlay_dir=overlay_dir)
    assert resolved.declared
    assert resolved.declaration_location == "pilot_overlay"


def test_a_repository_with_no_declaration_anywhere_is_undeclared(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    resolved = auth.AuthorityDeclaration.load(repo, overlay_dir=tmp_path / "absent")
    assert not resolved.declared
    assert not resolved.resolve("inventory").permitted


def test_a_legacy_declaration_declares_handling_but_not_authority(tmp_path) -> None:
    """``.ats/corpus.json`` predates per-use authority.

    The original form has no ``schema_version`` and carries a repository group
    and one handling policy. It is still honoured for what it says, but it
    cannot express per-use authority, so authority stays undeclared. Reading a
    grant out of it would manufacture permission from a file that never
    mentioned the question.
    """
    repo = tmp_path / "legacy"
    (repo / ".ats").mkdir(parents=True)
    (repo / ".ats" / "corpus.json").write_text(
        json.dumps(
            {
                "repository_group": "legacy-group",
                "use_authority": "internal_training_permitted",
                "handling_policy": "internal",
                "domain": "sample",
            }
        ),
        encoding="utf-8",
    )
    resolved = auth.AuthorityDeclaration.load(repo)
    assert not resolved.declared
    for use in auth.USES:
        assert not resolved.resolve(use, "docs/a.md").permitted


def test_a_declaration_with_the_wrong_version_is_refused_not_ignored(tmp_path) -> None:
    """Absence and error are different. A wrong version is somebody's mistake."""
    repo = tmp_path / "wrong"
    (repo / ".ats").mkdir(parents=True)
    (repo / ".ats" / "corpus.json").write_text(
        json.dumps({"schema_version": "ats.corpus_authority.v99"}), encoding="utf-8"
    )
    with pytest.raises(UsageError, match="schema_version"):
        auth.AuthorityDeclaration.load(repo)


# -- the shipped pilot overlays ----------------------------------------------


def test_every_synthetic_overlay_validates_and_withholds_training(
    ctx: Context, tmp_path: Path
) -> None:
    """Synthetic operator overlays grant review uses but defer training.

    The checked-in private pilot overlays were intentionally removed from the
    public checkout. This keeps the same contract exercised against temporary
    synthetic declarations instead of historical repository material.
    """
    overlay_dir = tmp_path / "authority"
    overlay_dir.mkdir()
    for name in ("alpha", "bravo"):
        data = declaration(
            repository={"name": name, "declaration_location": "pilot_overlay"},
            handling={"classification": "public"},
        )
        data["uses"].update(
            {
                "model_training": "defer",
                "external_model_submission": "deny",
                "publication": "deny",
            }
        )
        (overlay_dir / f"{name}.json").write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )

    overlays = sorted(overlay_dir.glob("*.json"))
    assert overlays, "the synthetic fixture must ship authority overlays"
    for path in overlays:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert ctx.schemas.validate_document(data) == "ats_corpus_authority_v1.schema.json"
        resolved = auth.AuthorityDeclaration.from_dict(
            data, repository=path.stem, location="pilot_overlay"
        )
        assert resolved.declaration_location == "pilot_overlay"
        assert resolved.resolve("candidate_mining", "docs/a.md").permitted
        assert not resolved.resolve("model_training", "docs/a.md").permitted
        assert not resolved.resolve("external_model_submission", "docs/a.md").permitted
        assert not resolved.resolve("publication", "docs/a.md").permitted
        assert resolved.effective_from_revision, "a declaration is bound to a revision"

# -- the nine bindings -------------------------------------------------------


def test_the_contract_binds_exactly_the_nine_named_concepts() -> None:
    """The list is the contract. Dropping one silently is the failure mode."""
    assert auth.BINDING_NAMES == (
        "principal",
        "authority_basis",
        "repository_identity",
        "effective_revision",
        "permitted_uses",
        "content_scope",
        "issued_at",
        "review_after",
        "superseded_by",
    )


@pytest.mark.parametrize("binding", auth.REQUIRED_BINDINGS, ids=lambda b: b.pointer)
def test_a_declaration_missing_any_binding_is_refused_by_name(binding) -> None:
    """Every leaf, individually. A named error, not "invalid declaration".

    The error has to say which concept is missing and what goes wrong without
    it, because the person holding the declaration is the one who has to go and
    find the answer out.
    """
    data = declaration()
    node = data
    for key in binding.path[:-1]:
        node = node[key]
    del node[binding.path[-1]]
    with pytest.raises(UsageError) as caught:
        load(data)
    message = str(caught.value)
    assert binding.name in message
    assert binding.pointer in message
    assert binding.why in message


@pytest.mark.parametrize("binding", auth.REQUIRED_BINDINGS, ids=lambda b: b.pointer)
def test_the_schema_refuses_a_missing_binding_too(ctx: Context, binding) -> None:
    """The loader is not the only gate.

    A declaration is a file people write and read without going through
    :meth:`from_dict`, so the schema has to refuse the same omissions the
    loader does. If only one of the two enforces a binding, a document that
    validates can still be unloadable, or worse, loadable while incomplete.
    """
    data = declaration()
    node = data
    for key in binding.path[:-1]:
        node = node[key]
    del node[binding.path[-1]]
    violations = ctx.schemas.violations(data, auth.SCHEMA_ID)
    assert violations, f"the schema accepted a declaration with no {binding.pointer}"
    assert any(binding.path[-1] in str(v) for v in violations), violations


def test_an_explicit_null_supersedes_differs_from_an_absent_one() -> None:
    """`superseded_by: null` is an answer; a missing key is not.

    A truthiness test would read them alike, which is how "nobody checked"
    becomes "nothing has replaced this".
    """
    assert load(declaration()).superseded_by is None
    absent = declaration()
    del absent["superseded_by"]
    with pytest.raises(UsageError, match="superseded_by"):
        load(absent)


def test_an_empty_content_scope_is_refused_not_read_as_covering_everything(
    ctx: Context,
) -> None:
    """`content: {}` is present but says nothing, and silence is not a scope.

    Treated as "everything", it silently authorises whatever happens to be in
    the tree, including material the principal did not write. A declaration
    that really does cover the whole repository says so with `include: ["*"]`.
    Both the loader and the schema refuse the empty form.
    """
    data = declaration()
    data["content"] = {}
    with pytest.raises(UsageError, match="empty content scope"):
        load(data)
    assert ctx.schemas.violations(data, auth.SCHEMA_ID)

    everything = declaration()
    everything["content"] = {"include": ["*"]}
    assert load(everything).include == ("*",)


def test_a_principal_may_not_be_a_role_word() -> None:
    """A seat cannot be asked to revisit its own declaration."""
    for role in ("owner", "the operator", "admin"):
        with pytest.raises(UsageError, match="role rather than an identity"):
            load(declaration(principal={"id": role}))
    assert load(declaration()).principal.startswith("https://")


def test_a_review_date_before_the_issue_date_is_refused() -> None:
    """A declaration due for review before it existed has no live interval."""
    with pytest.raises(UsageError, match="review_after"):
        load(declaration(issued_at="2026-06-01T00:00:00+00:00", review_after=ISSUED_AT))


def test_an_unreadable_review_date_is_refused_not_treated_as_distant() -> None:
    """A review date nobody can parse never comes due, which is no date at all."""
    with pytest.raises(UsageError, match="not an RFC 3339 timestamp"):
        load(declaration(review_after="whenever"))


# -- provenance --------------------------------------------------------------


def test_a_declaration_cannot_claim_a_provenance_it_was_not_found_at() -> None:
    """An overlay describing itself as repository-owned is refused outright.

    Not corrected: a corrected file keeps shipping the false claim to anyone
    who reads the bytes without going through the loader.
    """
    with pytest.raises(UsageError, match="cannot state a provenance"):
        load(declaration(), location="pilot_overlay")


def test_an_overlay_never_reports_as_repository_owned() -> None:
    """Identical permission, different provenance. The two must not merge.

    The overlay's own basis is ``owner_declared`` -- the operator really does
    own these repositories -- and it still reports ``repository_owned: false``,
    because the basis is a claim and the location is an observation.
    """
    overlay = load(
        declaration(repository={"declaration_location": "pilot_overlay"}),
        location="pilot_overlay",
    )
    in_place = load(declaration())

    assert overlay.authority == in_place.authority == "owner_declared"
    assert overlay.resolve("candidate_mining", "docs/a.md").value == (
        in_place.resolve("candidate_mining", "docs/a.md").value
    )

    assert overlay.provenance()["repository_owned"] is False
    assert overlay.provenance()["declaration_location"] == "pilot_overlay"
    assert in_place.provenance()["repository_owned"] is True


def test_a_single_resolution_carries_its_provenance_too(ctx: Context) -> None:
    """A resolution is the finest grain authority is reported at.

    A profile hypothesis embeds one verbatim, so the provenance has to survive
    down here and not only on the whole-declaration report. The old basis token
    read ``repository:owner_declared:allow`` for an overlay as well, which is
    the exact confusion this task exists to remove.
    """
    overlay = load(
        declaration(repository={"declaration_location": "pilot_overlay"}),
        location="pilot_overlay",
    )
    resolved = overlay.resolve("candidate_mining", "docs/a.md")
    assert resolved.declaration_location == "pilot_overlay"
    assert resolved.to_dict()["declaration_location"] == "pilot_overlay"
    assert resolved.basis[0] == "pilot_overlay:owner_declared:allow"
    assert not any(b.startswith("repository:") for b in resolved.basis)

    in_place = load(declaration()).resolve("candidate_mining", "docs/a.md")
    assert in_place.basis[0] == "repository:owner_declared:allow"

    # Nothing declared, nothing to attribute.
    undeclared = auth.AuthorityDeclaration.undeclared("x").resolve("inventory")
    assert undeclared.declaration_location is None



def test_an_authority_with_no_location_cannot_be_reported_at_all() -> None:
    """The default reading of a bare permission is the wrong one.

    A declared authority that lost its location would render exactly like a
    repository's own declaration, so the report is refused rather than emitted
    without the marker.
    """
    stripped = dataclasses.replace(load(declaration()), declaration_location=None)
    with pytest.raises(UsageError, match="records no declaration location"):
        stripped.provenance()


def test_a_report_block_without_provenance_is_refused() -> None:
    """The guard every report site calls on the block it built."""
    block = load(declaration()).provenance()
    auth.require_provenance(block, where="a well-formed report")
    for key in sorted(auth.PROVENANCE_KEYS):
        partial = {k: v for k, v in block.items() if k != key}
        with pytest.raises(UsageError, match=key):
            auth.require_provenance(partial, where="a report that dropped a key")


def test_an_unchecked_review_is_not_reported_as_current() -> None:
    """A caller with no clock has established nothing about the age."""
    live = load(declaration())
    assert live.provenance()["review_status"] == "unchecked"
    assert live.provenance("2026-06-01T00:00:00Z")["review_status"] == "current"
    assert live.provenance("2027-06-01T00:00:00Z")["review_status"] == "overdue"
    assert auth.AuthorityDeclaration.undeclared("x").provenance()["review_status"] == (
        "not_applicable"
    )


def test_a_lapsed_declaration_stops_granting_without_becoming_a_refusal() -> None:
    """An overlay that never expires is permanent governance nobody renewed.

    It caps at ``unknown`` and not ``deny``: the authority ran out, which is
    not the same as somebody refusing.
    """
    lapsed = load(declaration())
    before = lapsed.resolve("candidate_mining", "docs/a.md", now="2026-06-01T00:00:00Z")
    after = lapsed.resolve("candidate_mining", "docs/a.md", now="2027-06-01T00:00:00Z")
    assert before.permitted
    assert not after.permitted
    assert after.value == "unknown"
    assert any(b.startswith("review-overdue:") for b in after.basis)


# -- unknown and deny, end to end --------------------------------------------


def test_unknown_and_deny_stay_distinct_through_every_projection() -> None:
    """Both block. Only one of them is a decision somebody made.

    Checked at each stage the value passes through: the per-use intersection,
    the resolution's basis, the coarse projection onto the artifact record, and
    the coarse intersection a commit trailer is read through.
    """
    refused = load(declaration(uses={"inventory": "deny"}))
    absent = load(declaration(uses={"inventory": "unknown"}))

    assert refused.resolve("inventory", "docs/a.md").value == "deny"
    assert absent.resolve("inventory", "docs/a.md").value == "unknown"
    assert not refused.resolve("inventory", "docs/a.md").permitted
    assert not absent.resolve("inventory", "docs/a.md").permitted

    assert refused.coarse_use_authority("docs/a.md") == "prohibited"
    assert absent.coarse_use_authority("docs/a.md") == "unknown"

    # And the coarse vocabulary keeps them apart in its own ordering, so a
    # second input cannot collapse a refusal into a mere absence.
    assert auth.intersect_coarse("unknown", "prohibited") == "prohibited"
    assert auth.intersect_coarse("prohibited", "unknown") == "prohibited"
    assert auth.intersect_coarse("internal_only", "unknown") == "unknown"


def test_a_coarse_declaration_can_only_restrict_never_re_grant() -> None:
    """A commit trailer must not hand back a permission the repository refused.

    Substituting rather than intersecting was the hole: a document could
    declare `external_training_permitted` in its own commit message and
    out-declare the repository owner's refusal.
    """
    assert (
        auth.intersect_coarse("prohibited", "external_training_permitted") == "prohibited"
    )
    assert auth.intersect_coarse("internal_only", "external_training_permitted") == (
        "internal_only"
    )
    # Restricting is honoured.
    assert auth.intersect_coarse("external_training_permitted", "internal_only") == (
        "internal_only"
    )


def test_an_unreadable_coarse_value_is_neither_ranked_nor_ignored() -> None:
    assert not auth.coarse_recognised("probably")
    assert auth.coarse_recognised("prohibited")
    with pytest.raises(UsageError, match="is not a coarse use_authority"):
        auth.intersect_coarse("internal_only", "probably")
    assert auth.intersect_coarse() == "unknown"


# -- what a report is allowed to say -----------------------------------------

GIT_IDENTITY = (
    "-c",
    "user.name=Authority Fixture",
    "-c",
    "user.email=authority@ats.invalid",
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
    "GIT_AUTHOR_DATE": "2026-01-05T09:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-05T09:00:00+00:00",
}


def _git(repo: Path, *argv: str) -> None:
    proc = subprocess.run(
        ["git", "-C", str(repo), *GIT_IDENTITY, *argv], capture_output=True, env=GIT_ENV
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(argv)}: {proc.stderr.decode('utf-8', 'replace')}")


def _repo_with_overlay(tmp_path: Path, *, uses: dict[str, str], trailer: str | None) -> tuple:
    """A one-document repository authorised only by an operator overlay."""
    repo = tmp_path / "overlaid"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "a.md").write_text(
        "# Title\n\nThe pilot MUST record its authority.\n", encoding="utf-8"
    )
    _git(repo, "init", "--quiet")
    _git(repo, "add", ".")
    message = "Add a document" if trailer is None else f"Add a document\n\n{trailer}\n"
    _git(repo, "commit", "--quiet", "-m", message)

    overlay_dir = tmp_path / "authority"
    overlay_dir.mkdir()
    document = declaration(
        repository={"name": "overlaid", "declaration_location": "pilot_overlay"},
        uses=uses,
    )
    (overlay_dir / "overlaid.json").write_text(json.dumps(document), encoding="utf-8")
    return repo, overlay_dir


def test_an_inventory_cannot_render_an_overlay_as_repository_owned(ctx, tmp_path) -> None:
    """The report a reader actually sees, built by a real run.

    Every use is granted here, so the permission is indistinguishable from a
    repository-owned one. The provenance is not: the artifact carries the
    location it was found at and ``repository_owned: false``, and there is no
    code path that emits the permission without them --
    :func:`require_provenance` runs on the block the inventory built.
    """
    repo, overlay_dir = _repo_with_overlay(
        tmp_path, uses={use: "allow" for use in auth.USES}, trailer=None
    )
    inventory = inv.build_inventory(ctx, repo, authority_overlay=overlay_dir)

    artifact = inventory["artifacts"][0]
    block = artifact["extensions"]["x-ats-repo-git"]["authority"]
    auth.require_provenance(block, where="the test's own read of the inventory")
    assert block["declaration_location"] == "pilot_overlay"
    assert block["repository_owned"] is False
    assert block["declared_by"] == "owner_declared"
    assert block["principal"] == "https://example.invalid/sample-owner"
    assert block["review_after"] == REVIEW_AFTER
    assert block["review_status"] == "current"
    assert block["superseded_by"] is None


def test_a_commit_trailer_cannot_re_grant_what_the_repository_refused(ctx, tmp_path) -> None:
    """End to end: a refusal survives a document declaring otherwise.

    The repository denies ``inventory``, which projects to ``prohibited``. The
    commit message claims ``external_training_permitted``. The trailer is a
    lower-authority input and is intersected, so the artifact still records the
    refusal -- and records it as ``prohibited``, not as ``unknown``, because a
    refusal somebody made is not an absence.
    """
    uses = {use: "allow" for use in auth.USES}
    uses["inventory"] = "deny"
    repo, overlay_dir = _repo_with_overlay(
        tmp_path, uses=uses, trailer="ATS-Use-Authority: external_training_permitted"
    )
    inventory = inv.build_inventory(ctx, repo, authority_overlay=overlay_dir)

    artifact = inventory["artifacts"][0]
    assert artifact["use_authority"] == "prohibited"
    block = artifact["extensions"]["x-ats-repo-git"]["authority"]
    assert block["trailer"] == {
        "declared": "external_training_permitted",
        "recognised": True,
        "applied": "external_training_permitted",
    }
    assert block["uses"]["inventory"] == "deny"


def test_an_unreadable_trailer_is_recorded_and_resolves_unknown(ctx, tmp_path) -> None:
    """Not dropped, which would ignore a declaration somebody made.

    Not ranked either, which would guess what they meant. It caps the coarse
    projection at ``unknown`` and the mistake stays visible in the record.
    """
    repo, overlay_dir = _repo_with_overlay(
        tmp_path,
        uses={use: "allow" for use in auth.USES},
        trailer="ATS-Use-Authority: probably-fine",
    )
    inventory = inv.build_inventory(ctx, repo, authority_overlay=overlay_dir)

    artifact = inventory["artifacts"][0]
    assert artifact["use_authority"] == "unknown"
    trailer = artifact["extensions"]["x-ats-repo-git"]["authority"]["trailer"]
    assert trailer == {
        "declared": "probably-fine",
        "recognised": False,
        "applied": "unknown",
    }


def test_a_sampling_frame_row_carries_the_overlay_provenance(tmp_path) -> None:
    """The frame's authority rows, which are what the pilot report is read from."""
    _, overlay_dir = _repo_with_overlay(
        tmp_path, uses={use: "allow" for use in auth.USES}, trailer=None
    )
    resolved = frame.resolve_annotation_authority(
        [{"repository": "overlaid", "revision": "c" * 40}],
        overlay_dir,
        now="2026-06-01T00:00:00Z",
    )
    row = resolved["authorised"][0]
    auth.require_provenance(row, where="the test's own read of the frame")
    assert row["repository_owned"] is False
    assert row["declaration_location"] == "pilot_overlay"
    assert row["review_status"] == "current"


def test_a_lapsed_overlay_authorises_no_frame_row(tmp_path) -> None:
    """The teeth behind `review_after`, at the level that selects bundles."""
    _, overlay_dir = _repo_with_overlay(
        tmp_path, uses={use: "allow" for use in auth.USES}, trailer=None
    )
    resolved = frame.resolve_annotation_authority(
        [{"repository": "overlaid", "revision": "c" * 40}],
        overlay_dir,
        now="2027-06-01T00:00:00Z",
    )
    assert resolved["authorised"] == []
    assert "human_annotation=unknown" in resolved["excluded"][0]["reason"]

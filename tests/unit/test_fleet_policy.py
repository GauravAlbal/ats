"""Fleet artifact policy resolution (draft.2 D-G).

The fleet policy decides when ATS applies to an artifact. Resolution must be
deterministic (policy_id is a content hash), fail-closed (a stale document is
an error, not a pass), and never auto-require an unknown class.
"""

from __future__ import annotations

import copy
import datetime as _dt
import json

import pytest

from conftest import REPO_ROOT

from ats import cli
from ats.canonical import content_hash
from ats.context import Context
from ats.errors import SchemaValidationError, StalePolicyError, UsageError
from ats.fleet import (
    BASIS_DEFAULT_EXCLUSION,
    BASIS_REPOSITORY_OVERRIDE,
    BASIS_TEXT_POLICY,
    FLEET_POLICY_SCHEMA_ID,
    FleetPolicy,
    resolve,
)

NOW = _dt.datetime(2026, 8, 7, tzinfo=_dt.UTC)

#: The checked-in public default policy document (draft.2).
SHIPPED_POLICY = REPO_ROOT / "config" / "policies" / "fleet_policy.json"


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


def _shipped() -> dict:
    return json.loads(SHIPPED_POLICY.read_text(encoding="utf-8"))


def _policy(**overrides) -> dict:
    """A content-addressed policy document, rescaled to its own bytes."""
    document = copy.deepcopy(_shipped())
    for key, value in overrides.items():
        document[key] = value
    document["policy_id"] = content_hash(dict(document), exclude={"policy_id"})
    return document


def _override(repository: str = "acme", **fields) -> dict:
    entry = {
        "repository": repository,
        "receipt_binding": f"receipts in {repository} bind policy_id",
    }
    entry.update(fields)
    return entry


# -- validation and content addressing --------------------------------------


def test_shipped_policy_document_validates(ctx) -> None:
    """The fleet's own policy document is schema-valid and content-addressed."""
    policy = FleetPolicy.from_document(_shipped(), ctx.schemas)
    assert policy.spec_version == "1.0.0-draft.2"
    assert len(policy.required_for) == 12
    assert len(policy.default_exclusions) == 9
    assert policy.repository_overrides == {}
    assert policy.enforcement["stable_coordinate_preservation"] == "required"


def test_policy_id_is_the_content_hash_of_the_material(ctx) -> None:
    """The content address excludes the policy_id field itself (Appendix C)."""
    document = _shipped()
    policy = FleetPolicy.from_document(document, ctx.schemas)
    recomputed = content_hash(dict(document), exclude={"policy_id"})
    assert policy.policy_id == recomputed
    assert policy.policy_id == document["policy_id"]


def test_schema_violations_are_refused(ctx) -> None:
    """An invalid document is a schema failure, never a partial resolution."""
    document = _policy()
    del document["text_policy"]
    with pytest.raises(SchemaValidationError) as excinfo:
        FleetPolicy.from_document(document, ctx.schemas)
    assert excinfo.value.schema_id == FLEET_POLICY_SCHEMA_ID


def test_a_stale_policy_id_is_refused(ctx) -> None:
    """Fail-closed: a document whose hash does not match is an error, not a pass."""
    document = _policy()
    document["policy_id"] = "0" * 64
    with pytest.raises(StalePolicyError) as excinfo:
        FleetPolicy.from_document(document, ctx.schemas)
    assert "policy_id" in str(excinfo.value)


def test_duplicate_repository_overrides_are_refused(ctx) -> None:
    """Two overrides for one repository make the resolution ambiguous."""
    document = _policy(repository_overrides=[_override(), _override()])
    with pytest.raises(UsageError) as excinfo:
        FleetPolicy.from_document(document, ctx.schemas)
    assert "more than one repository override" in str(excinfo.value)


# -- resolution --------------------------------------------------------------


def test_required_class_resolves_applicable(ctx) -> None:
    """A class in text_policy.required_for is applicable with text-policy enforcement."""
    resolution = resolve(_shipped(), "implementation_spec", schemas=ctx.schemas)
    assert resolution.applicable is True
    assert resolution.basis == BASIS_TEXT_POLICY
    assert resolution.spec_version == "1.0.0-draft.2"
    assert resolution.policy_id == _shipped()["policy_id"]
    assert resolution.enforcement == _shipped()["text_policy"]["enforcement"]
    assert resolution.failure_policy == _shipped()["text_policy"]["failure_policy"]


def test_excluded_class_resolves_not_applicable(ctx) -> None:
    """A class in default_exclusions is not applicable unless explicitly required."""
    resolution = resolve(_shipped(), "blog_posts", schemas=ctx.schemas)
    assert resolution.applicable is False
    assert resolution.basis == BASIS_DEFAULT_EXCLUSION


def test_unknown_class_is_not_auto_required(ctx) -> None:
    """Default exclusions are the floor; an unknown class is never auto-required."""
    resolution = resolve(_shipped(), "mystery_class", schemas=ctx.schemas)
    assert resolution.applicable is False
    assert resolution.basis == BASIS_TEXT_POLICY


def test_an_explicit_requirement_beats_the_exclusion_floor(ctx) -> None:
    """A class that is BOTH excluded and explicitly required is applicable."""
    required = list(_shipped()["text_policy"]["required_for"]) + ["blog_posts"]
    document = _policy()
    document["text_policy"] = {**_shipped()["text_policy"], "required_for": required}
    document["policy_id"] = content_hash(dict(document), exclude={"policy_id"})
    resolution = resolve(document, "blog_posts", schemas=ctx.schemas)
    assert resolution.applicable is True
    assert resolution.basis == BASIS_TEXT_POLICY


def test_repository_override_adds_a_class(ctx) -> None:
    """required_for_additions makes a class applicable for that repository only."""
    document = _policy(
        repository_overrides=[_override(required_for_additions=["design_note"])]
    )
    added = resolve(document, "design_note", repository="acme", schemas=ctx.schemas)
    assert added.applicable is True
    assert added.basis == BASIS_REPOSITORY_OVERRIDE
    outside = resolve(document, "design_note", schemas=ctx.schemas)
    assert outside.applicable is False
    assert outside.basis == BASIS_TEXT_POLICY


def test_repository_override_removes_a_class(ctx) -> None:
    """required_for_removals takes a base-required class out for that repository."""
    document = _policy(
        repository_overrides=[_override(required_for_removals=["forensic_analysis"])]
    )
    removed = resolve(document, "forensic_analysis", repository="acme", schemas=ctx.schemas)
    assert removed.applicable is False
    assert removed.basis == BASIS_REPOSITORY_OVERRIDE
    base = resolve(document, "forensic_analysis", schemas=ctx.schemas)
    assert base.applicable is True
    assert base.basis == BASIS_TEXT_POLICY


def test_enforcement_override_overlays_the_text_policy(ctx) -> None:
    """enforcement_overrides overlay the enforcement map for that repository."""
    document = _policy(
        repository_overrides=[_override(enforcement_overrides={"semantic_review": "required"})]
    )
    overridden = resolve(document, "implementation_spec", repository="acme", schemas=ctx.schemas)
    assert overridden.enforcement["semantic_review"] == "required"
    base = resolve(document, "implementation_spec", schemas=ctx.schemas)
    assert base.enforcement["semantic_review"] == "advisory"
    # The overlay applies even when the override did not decide membership.
    assert overridden.basis == BASIS_TEXT_POLICY


def test_repository_exclusions_replace_the_fleet_floor(ctx) -> None:
    """A per-repository default_exclusions list replaces the fleet-level list.

    Required membership still beats exclusions: the exclusion floor only
    governs classes the text policy does not explicitly require.
    """
    document = _policy(repository_overrides=[_override(default_exclusions=["design_note"])])
    excluded = resolve(document, "design_note", repository="acme", schemas=ctx.schemas)
    assert excluded.applicable is False
    assert excluded.basis == BASIS_REPOSITORY_OVERRIDE
    # The fleet floor is replaced inside the repository: blog_posts is no
    # longer excluded by name, so it resolves as an unknown class.
    inside = resolve(document, "blog_posts", repository="acme", schemas=ctx.schemas)
    assert inside.applicable is False
    assert inside.basis == BASIS_TEXT_POLICY
    # Required membership is not revoked by a per-repository exclusion list.
    required = resolve(document, "implementation_spec", repository="acme", schemas=ctx.schemas)
    assert required.applicable is True
    assert required.basis == BASIS_TEXT_POLICY

def test_resolve_accepts_a_validated_fleet_policy(ctx) -> None:
    """Module-level resolve() also takes a FleetPolicy, skipping re-validation."""
    policy = FleetPolicy.from_document(_shipped(), ctx.schemas)
    resolution = resolve(policy, "implementation_spec", repository="example")
    assert resolution.applicable is True
    assert resolution.enforcement["semantic_review"] == "advisory"
    with pytest.raises(UsageError):
        resolve(_shipped(), "implementation_spec")  # raw document needs schemas=


# -- CLI ---------------------------------------------------------------------


def test_cli_resolve_produces_the_correct_opposites(capsys) -> None:
    """`ats policy resolve` emits the Resolution as canonical JSON, exit 0."""
    assert cli.main(["policy", "resolve", "implementation_spec"]) == 0
    required = json.loads(capsys.readouterr().out)
    assert required["artifact_class"] == "implementation_spec"
    assert required["applicable"] is True
    assert required["basis"] == BASIS_TEXT_POLICY
    assert required["spec_version"] == "1.0.0-draft.2"
    assert required["policy_id"] == _shipped()["policy_id"]

    assert cli.main(["policy", "resolve", "blog_posts"]) == 0
    excluded = json.loads(capsys.readouterr().out)
    assert excluded["applicable"] is False
    assert excluded["basis"] == BASIS_DEFAULT_EXCLUSION


def test_cli_default_policy_is_host_neutral(capsys) -> None:
    """The no-``--policy`` default never applies a private fleet override."""
    assert cli.main(["policy", "resolve", "design_note", "--repo", "arq"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["applicable"] is False
    assert payload["basis"] == BASIS_TEXT_POLICY
    assert payload["enforcement"]["semantic_review"] == "advisory"


def test_cli_missing_policy_file_is_an_ats_error(capsys) -> None:
    """A missing policy document exits via the standard error path (exit 2)."""
    rc = cli.main(["policy", "resolve", "implementation_spec", "--policy", "/nonexistent.json"])
    assert rc == 2
    error = json.loads(capsys.readouterr().err)
    assert error["error"] == "usage_error"
    assert "not found" in error["message"]


def test_cli_stale_policy_document_is_an_ats_error(tmp_path, capsys) -> None:
    """An invalid policy document exits via the standard error path (exit 4)."""
    document = _policy()
    document["policy_id"] = "0" * 64
    path = tmp_path / "stale.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    rc = cli.main(["policy", "resolve", "implementation_spec", "--policy", str(path)])
    assert rc == 4
    error = json.loads(capsys.readouterr().err)
    assert error["error"] == "stale_policy"

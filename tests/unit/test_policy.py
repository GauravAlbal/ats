"""Policy resolution: the lattice, overrides, exceptions, and currentness.

Spec Section 6.2 orders rule states and permits a more specialized policy to
strengthen but never to weaken. Section 6.3 makes a weakening move require an
exact, scoped, unexpired exception. Section 6.5 composes profiles by taking the
stricter state and refuses to pick a conflict winner heuristically. Sections
6.6 and 14.3 bind the exact snapshot before evaluation and fail closed.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from ats.errors import PolicyResolutionError, StalePolicyError, UsageError
from ats.policy import (
    STABLE_PROFILES,
    STATE_ORDER,
    STATE_RANK,
    ExceptionScope,
    PolicySnapshot,
    parse_timestamp,
    stronger,
)

ARTIFACT = "fixture-assess-rust-kernel"


def snapshot(ctx, document) -> PolicySnapshot:
    return PolicySnapshot.from_document(document, ctx.registry.raw_rules)


# -- the lattice ------------------------------------------------------------


def test_state_lattice_is_ordered_disabled_to_required() -> None:
    """Spec 6.2 names exactly this order."""
    assert STATE_ORDER == ("disabled", "shadow", "advisory", "required")
    assert [STATE_RANK[s] for s in STATE_ORDER] == [0, 1, 2, 3]
    assert stronger("advisory", "shadow") == "advisory"
    assert stronger("shadow", "advisory") == "advisory"
    assert stronger("required", "required") == "required"
    assert stronger("disabled", "shadow") == "shadow"


def test_stable_profiles_are_the_three_this_edition_specifies() -> None:
    """Spec 3.2 and 3.3: ASSESS and SPECIFY are stable, TRANSFORM cross-cutting."""
    assert STABLE_PROFILES == frozenset({"ASSESS", "SPECIFY", "TRANSFORM"})


def test_a_profile_the_rule_does_not_declare_does_not_run(ctx, load_policy) -> None:
    """Spec 9.5: a reserved or extension profile inherits nothing by similarity."""
    policy = snapshot(ctx, load_policy("assess"))
    assert policy.default_state("ATS-EPI-001", "X-ARQ-EXPLAIN-1") == "disabled"
    with pytest.raises(PolicyResolutionError, match="unknown rule id"):
        policy.default_state("ATS-NOPE-999", "ASSESS")


# -- overrides --------------------------------------------------------------


def test_a_bare_override_may_strengthen(ctx, load_policy, fixed_now) -> None:
    """Spec 6.2: a more specialized policy MAY strengthen a rule."""
    policy = snapshot(ctx, load_policy("strengthened"))
    assert policy.raw["rule_overrides"] == {"ATS-DISC-001": "required"}

    state = policy.resolve_rule("ATS-DISC-001", "ASSESS", now=fixed_now)
    assert state.default_state == "advisory"
    assert state.state == "required"
    assert state.layer == "project_policy"
    assert state.ignored == ()
    assert state.blocks_conformance is True
    assert state.surfaces_findings is True
    assert state.runs is True


def test_a_bare_override_must_not_weaken_and_the_refusal_is_recorded(
    ctx, load_policy, fixed_now
) -> None:
    """Spec 6.2: weakening without an exact exception is refused, not applied."""
    policy = snapshot(ctx, load_policy("weakening_override"))
    assert policy.raw["rule_overrides"] == {"ATS-EPI-001": "advisory"}
    assert policy.default_state("ATS-EPI-001", "ASSESS") == "required"

    state = policy.resolve_rule("ATS-EPI-001", "ASSESS", now=fixed_now)
    assert state.state == "required", "the weakening override must not take effect"
    assert state.layer == "profile_default"
    assert state.exception_id is None

    assert len(state.ignored) == 1
    refusal = state.ignored[0]
    assert refusal.rule_id == "ATS-EPI-001"
    assert refusal.directive == "rule_override"
    assert refusal.attempted_state == "advisory"
    assert refusal.effective_state == "required"
    assert "MUST NOT weaken" in refusal.reason

    states, _ = policy.resolve_all(["ASSESS"], now=fixed_now, artifact_id=ARTIFACT)
    recorded = PolicySnapshot.ignored_directives(states)
    assert [d.rule_id for d in recorded] == ["ATS-EPI-001"]
    assert recorded[0].to_dict()["attempted_state"] == "advisory"


# -- exceptions -------------------------------------------------------------


def test_a_scoped_unexpired_exception_weakens_only_within_its_scope(
    ctx, load_policy, fixed_now
) -> None:
    """Spec 6.3: an exception applies to exactly the object its scope names."""
    policy = snapshot(ctx, load_policy("scoped_exception"))
    (exception,) = policy.exceptions
    assert exception.rule_id == "ATS-EPI-002"
    assert exception.from_state == "required"
    assert exception.to_state == "advisory"
    assert exception.hash_matches(), "the exception must be content addressed (Appendix C)"
    assert exception.expired_at(fixed_now) is False

    inside = policy.resolve_rule("ATS-EPI-002", "ASSESS", now=fixed_now, artifact_id=ARTIFACT)
    assert inside.state == "advisory"
    assert inside.layer == "scoped_exception"
    assert inside.exception_id == exception.exception_id
    assert inside.blocks_conformance is False

    outside = policy.resolve_rule(
        "ATS-EPI-002", "ASSESS", now=fixed_now, artifact_id="some-other-artifact"
    )
    assert outside.state == "required", "an exception scoped elsewhere must not apply"
    assert outside.exception_id is None
    assert outside.layer == "profile_default"

    unscoped_target = policy.resolve_rule("ATS-EPI-002", "ASSESS", now=fixed_now)
    assert unscoped_target.state == "required"
    assert unscoped_target.exception_id is None


def test_an_exception_does_not_leak_onto_another_rule(ctx, load_policy, fixed_now) -> None:
    """Spec 6.3: an exception names one rule_id."""
    policy = snapshot(ctx, load_policy("scoped_exception"))
    other = policy.resolve_rule("ATS-EPI-001", "ASSESS", now=fixed_now, artifact_id=ARTIFACT)
    assert other.state == "required"
    assert other.exception_id is None


def test_an_expired_exception_is_invalid_and_the_original_state_returns(
    ctx, load_policy, fixed_now
) -> None:
    """Spec 6.3: expiry invalidates the exception and the rule is re-evaluated."""
    policy = snapshot(ctx, load_policy("expired_exception"))
    (exception,) = policy.exceptions
    assert exception.expires_at == "2025-06-01T00:00:00Z"
    assert exception.expired_at(fixed_now) is True

    state = policy.resolve_rule("ATS-EPI-002", "ASSESS", now=fixed_now, artifact_id=ARTIFACT)
    assert state.state == policy.default_state("ATS-EPI-002", "ASSESS") == "required"
    assert state.exception_id is None
    assert state.layer == "profile_default"

    assert len(state.ignored) == 1
    assert state.ignored[0].directive == f"exception:{exception.exception_id}"
    assert "expired" in state.ignored[0].reason

    (diagnostic,) = policy.exception_diagnostics(fixed_now)
    assert diagnostic.status == "expired"
    assert diagnostic.exception_id == exception.exception_id

    # Before its expiry the same exception is in force.
    before = _dt.datetime(2025, 1, 2, tzinfo=_dt.UTC)
    assert policy.resolve_rule(
        "ATS-EPI-002", "ASSESS", now=before, artifact_id=ARTIFACT
    ).state == "advisory"


def test_an_exception_whose_hash_does_not_match_is_refused(ctx, load_policy, fixed_now) -> None:
    """Spec 6.6 and Appendix C: an exception is bound by its content address."""
    document = load_policy("scoped_exception")
    tampered = {
        **document,
        "exceptions": [{**document["exceptions"][0], "to_state": "disabled"}],
    }
    policy = snapshot(ctx, tampered)
    state = policy.resolve_rule("ATS-EPI-002", "ASSESS", now=fixed_now, artifact_id=ARTIFACT)
    assert state.state == "required"
    assert state.exception_id is None
    assert state.ignored[0].reason == "exception sha256 does not match its canonical bytes"
    assert policy.exception_diagnostics(fixed_now)[0].status == "hash_mismatch"


def test_a_scope_with_no_mechanical_dimension_covers_nothing(ctx, load_policy, fixed_now) -> None:
    """Spec 6.3: a description is not a scope a machine can match."""
    scope = ExceptionScope(description="agreed verbally")
    assert scope.covers(artifact_id=ARTIFACT) is False

    document = load_policy("scoped_exception")
    raw = {**document["exceptions"][0], "scope": {"description": "agreed verbally"}}
    from ats.canonical import seal

    policy = snapshot(ctx, {**document, "exceptions": [seal(raw)]})
    assert policy.resolve_rule(
        "ATS-EPI-002", "ASSESS", now=fixed_now, artifact_id=ARTIFACT
    ).state == "required"
    assert policy.exception_diagnostics(fixed_now)[0].status == "unscoped"


def test_scope_dimensions_must_all_match(ctx) -> None:
    """Spec 6.3: an undeclared dimension is not a wildcard over a declared one."""
    scope = ExceptionScope(artifact_id=ARTIFACT, claim_id="c1")
    assert scope.covers(artifact_id=ARTIFACT, claim_id="c1") is True
    assert scope.covers(artifact_id=ARTIFACT, claim_id="c2") is False
    assert scope.covers(artifact_id=ARTIFACT) is False
    assert scope.covers(claim_id="c1") is False


# -- composition ------------------------------------------------------------


def test_composed_profiles_take_the_stricter_state(ctx, load_policy, fixed_now) -> None:
    """Spec 6.5: non-conflicting requirements accumulate; the stricter state wins."""
    policy = snapshot(ctx, load_policy("composed"))
    assert policy.profiles == ("ASSESS", "SPECIFY", "TRANSFORM")

    # ATS-REQ-001 is disabled under ASSESS and required under SPECIFY.
    assert policy.default_state("ATS-REQ-001", "ASSESS") == "disabled"
    assert policy.default_state("ATS-REQ-001", "SPECIFY") == "required"
    winner, conflict = policy.resolve_composed(
        "ATS-REQ-001", ("ASSESS", "SPECIFY"), now=fixed_now
    )
    assert winner.state == "required"
    assert winner.profile == "SPECIFY"
    assert conflict is None

    # Order of composition does not change the winner.
    reversed_winner, _ = policy.resolve_composed(
        "ATS-REQ-001", ("SPECIFY", "ASSESS"), now=fixed_now
    )
    assert reversed_winner.state == "required"

    # ATS-TIME-001 is required under ASSESS and advisory under SPECIFY.
    assert policy.default_state("ATS-TIME-001", "SPECIFY") == "advisory"
    time_winner, _ = policy.resolve_composed(
        "ATS-TIME-001", ("ASSESS", "SPECIFY"), now=fixed_now
    )
    assert time_winner.state == "required"


def test_a_section_resolving_to_no_profile_is_an_error(ctx, load_policy, fixed_now) -> None:
    """Spec 6.5: every section MUST resolve to at least one content profile."""
    policy = snapshot(ctx, load_policy("composed"))
    with pytest.raises(PolicyResolutionError, match="at least one"):
        policy.resolve_composed("ATS-EPI-001", (), now=fixed_now)


def test_a_scoped_exception_weakens_every_composed_profile_uniformly(
    ctx, load_policy, fixed_now
) -> None:
    """Spec 6.3 and 6.5: an exception is scoped by object, not by profile.

    Because the scope dimensions name artifacts, sections, and claims rather
    than profiles, an applicable exception moves every composed profile to the
    same state. There is therefore no residual profile disagreement to resolve,
    and none is invented.
    """
    document = load_policy("composed")
    excepted = load_policy("scoped_exception")["exceptions"][0]
    policy = snapshot(ctx, {**document, "exceptions": [excepted]})

    assert policy.default_state("ATS-EPI-002", "ASSESS") == "required"
    assert policy.default_state("ATS-EPI-002", "TRANSFORM") == "required"
    winner, conflict = policy.resolve_composed(
        "ATS-EPI-002", ("ASSESS", "TRANSFORM"), now=fixed_now, artifact_id=ARTIFACT
    )
    assert winner.state == "advisory"
    assert winner.layer == "scoped_exception"
    assert winner.exception_id == excepted["exception_id"]
    assert conflict is None, "no profile keeps the rule stronger, so there is no conflict"

    # Outside the exception's scope every composed profile keeps its default.
    elsewhere, elsewhere_conflict = policy.resolve_composed(
        "ATS-EPI-002", ("ASSESS", "TRANSFORM"), now=fixed_now, artifact_id="other-artifact"
    )
    assert elsewhere.state == "required"
    assert elsewhere_conflict is None


def test_refusals_from_every_composed_profile_reach_the_winning_state(
    ctx, load_policy, fixed_now
) -> None:
    """Spec 6.2: a declined directive is retained, once per profile that declined it."""
    document = {**load_policy("composed"), "rule_overrides": {"ATS-EPI-001": "advisory"}}
    policy = snapshot(ctx, document)
    assert policy.default_state("ATS-EPI-001", "ASSESS") == "required"
    assert policy.default_state("ATS-EPI-001", "SPECIFY") == "advisory"
    assert policy.default_state("ATS-EPI-001", "TRANSFORM") == "required"

    winner, conflict = policy.resolve_composed(
        "ATS-EPI-001", policy.profiles, now=fixed_now, artifact_id=ARTIFACT
    )
    assert winner.state == "required", "the weakening override is refused everywhere"
    assert conflict is None
    # ASSESS and TRANSFORM both refuse; SPECIFY's default already equals the
    # attempted state, so there is nothing there to refuse.
    assert [d.profile for d in winner.ignored] == ["ASSESS", "TRANSFORM"]
    assert {d.directive for d in winner.ignored} == {"rule_override"}


def test_resolve_all_covers_every_registered_rule(ctx, load_policy, fixed_now) -> None:
    """Spec 6.1: every rule resolves to exactly one state per evaluation."""
    policy = snapshot(ctx, load_policy("assess"))
    states, conflicts = policy.resolve_all(["ASSESS"], now=fixed_now, artifact_id=ARTIFACT)
    assert set(states) == set(ctx.registry.ids())
    assert conflicts == []
    for rule_id, state in states.items():
        assert state.state in STATE_ORDER
        assert state.state == ctx.registry.get(rule_id).default_states.get("ASSESS", "disabled")


def test_transform_policy_activates_the_unwaivable_preservation_rules(
    ctx, load_policy, fixed_now
) -> None:
    """Spec 6.4: ATS-PRES-001 and ATS-PRES-002 are unwaivable under TRANSFORM."""
    assess = snapshot(ctx, load_policy("assess"))
    transform = snapshot(ctx, load_policy("assess_transform"))
    for rule_id in ("ATS-PRES-001", "ATS-PRES-002"):
        assert ctx.registry.get(rule_id).waivable is False
        assess_state, _ = assess.resolve_composed(rule_id, assess.profiles, now=fixed_now)
        transform_state, _ = transform.resolve_composed(
            rule_id, transform.profiles, now=fixed_now
        )
        assert assess_state.state == "disabled"
        assert assess_state.runs is False
        assert transform_state.state == "required"
        assert transform_state.runs is True


# -- currentness ------------------------------------------------------------


def test_require_current_binds_the_exact_snapshot_hash(ctx, load_policy) -> None:
    """Spec 6.6 and 14.3: the declared address must be the canonical one."""
    policy = snapshot(ctx, load_policy("assess"))
    assert policy.require_current(spec_version=ctx.spec_version) == policy.declared_sha256
    assert policy.computed_sha256() == policy.declared_sha256


def test_require_current_fails_closed_on_a_hash_mismatch(ctx, load_policy) -> None:
    """Spec 14.3: two snapshots with one id and different hashes are distinct versions."""
    document = {**load_policy("assess"), "finding_budget": {"guardrail": "none", "coach": 1}}
    policy = snapshot(ctx, document)
    with pytest.raises(StalePolicyError, match="snapshot_sha256"):
        policy.require_current(spec_version=ctx.spec_version)


def test_require_current_fails_closed_on_a_spec_version_mismatch(ctx, load_policy) -> None:
    """Spec 14.3 and 19.1: a snapshot targets one specification version."""
    from ats.canonical import seal

    document = seal({**load_policy("assess"), "spec_version": "1.0.0-draft.0"})
    policy = snapshot(ctx, document)
    assert policy.computed_sha256() == policy.declared_sha256, "the mismatch is the version only"
    with pytest.raises(StalePolicyError, match="spec_version"):
        policy.require_current(spec_version=ctx.spec_version)


def test_context_policy_refuses_a_stale_snapshot(ctx, load_policy) -> None:
    """Spec 14.3: currentness is established before any rule runs."""
    document = {**load_policy("assess"), "snapshot_sha256": "0" * 64}
    with pytest.raises(StalePolicyError):
        ctx.policy(document)


def test_from_document_refuses_a_foreign_schema_version(ctx, load_policy) -> None:
    """Spec 19.4: an unknown major schema version MUST be rejected."""
    document = {**load_policy("assess"), "schema_version": "ats.policy_snapshot.v2"}
    with pytest.raises(UsageError, match="ats.policy_snapshot.v1"):
        snapshot(ctx, document)


def test_unsupported_profiles_are_reported_not_coerced(ctx, load_policy) -> None:
    """Spec 9.5: a reserved profile is preserved and named, never mapped onto a stable one."""
    assert snapshot(ctx, load_policy("composed")).unsupported_profiles() == ()
    document = {**load_policy("assess"), "profiles": ["ASSESS", "EXPLAIN"]}
    assert snapshot(ctx, document).unsupported_profiles() == ("EXPLAIN",)


def test_parse_timestamp_requires_an_offset() -> None:
    """Spec 6.3 compares expiry against an evaluation instant, so naive time is refused."""
    assert parse_timestamp("2026-08-03T00:00:00Z") == _dt.datetime(2026, 8, 3, tzinfo=_dt.UTC)
    assert parse_timestamp("2026-08-03T02:00:00+02:00") == _dt.datetime(
        2026, 8, 3, tzinfo=_dt.UTC
    )
    with pytest.raises(UsageError, match="no timezone offset"):
        parse_timestamp("2026-08-03T00:00:00")
    with pytest.raises(UsageError, match="invalid RFC 3339"):
        parse_timestamp("the third of August")

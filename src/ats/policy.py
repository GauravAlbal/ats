"""Policy resolution.

Pure functions over an ``ats.policy_snapshot.v1`` document and the normative
rule registry. Resolution has no I/O, no clock reads except the explicitly
passed evaluation time, and no heuristics: spec Section 6.5 forbids selecting a
profile conflict winner by probability, so a conflict is returned as a typed
:class:`~ats.errors.PolicyConflict` instead.

Lattice (spec Section 6.2)::

    disabled < shadow < advisory < required

A more specialized policy MAY strengthen a rule. It MUST NOT weaken one without
an exact ``TextPolicyExceptionV1`` whose scope covers the object being judged
and whose expiry has not passed (spec Section 6.3).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field, replace
from typing import Any, Final, Iterable, Mapping

from .canonical import content_hash
from .errors import PolicyConflict, PolicyResolutionError, StalePolicyError, UsageError

#: Ordered rule-state lattice (spec Section 6.2).
STATE_ORDER: Final[tuple[str, ...]] = ("disabled", "shadow", "advisory", "required")
STATE_RANK: Final[dict[str, int]] = {s: i for i, s in enumerate(STATE_ORDER)}

#: Profiles this edition fully specifies (spec Section 3.2 and 1.2).
STABLE_PROFILES: Final[frozenset[str]] = frozenset({"ASSESS", "SPECIFY", "TRANSFORM"})

#: Policy layers, least to most specialized (spec Section 6.1). Recorded on every
#: resolution so a receipt can show which layer set a state.
POLICY_LAYERS: Final[tuple[str, ...]] = (
    "standard_default",
    "profile_default",
    "organization_policy",
    "project_policy",
    "artifact_policy",
    "scoped_exception",
)


def stronger(a: str, b: str) -> str:
    """Return the stricter of two lattice states."""
    return a if STATE_RANK[a] >= STATE_RANK[b] else b


@dataclass(frozen=True, slots=True)
class ExceptionScope:
    """The exact scope of a policy exception (spec Section 6.3)."""

    artifact_id: str | None = None
    path: str | None = None
    section_id: str | None = None
    claim_id: str | None = None
    locator: str | None = None
    description: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ExceptionScope:
        return cls(**{k: data.get(k) for k in cls.__slots__})

    def covers(
        self,
        *,
        artifact_id: str | None = None,
        section_id: str | None = None,
        claim_id: str | None = None,
        path: str | None = None,
    ) -> bool:
        """True when every declared dimension of this scope matches the target.

        A dimension the exception does not declare is not a wildcard over a
        dimension it does declare: an exception scoped to ``claim_id`` never
        applies to a different claim. An exception that declares only
        ``description`` covers nothing mechanically and is reported as such by
        :meth:`PolicySnapshot.exception_diagnostics`.
        """
        checks = (
            (self.artifact_id, artifact_id),
            (self.section_id, section_id),
            (self.claim_id, claim_id),
            (self.path, path),
        )
        declared = [(want, got) for want, got in checks if want is not None]
        if not declared:
            return False
        return all(got is not None and want == got for want, got in declared)


@dataclass(frozen=True, slots=True)
class PolicyException:
    exception_id: str
    rule_id: str
    from_state: str
    to_state: str
    scope: ExceptionScope
    rationale: str
    authorized_by: str
    created_at: str
    expires_at: str | None
    non_expiring_justification: str | None
    sha256: str
    raw: Mapping[str, Any]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PolicyException:
        return cls(
            exception_id=data["exception_id"],
            rule_id=data["rule_id"],
            from_state=data["from_state"],
            to_state=data["to_state"],
            scope=ExceptionScope.from_dict(data["scope"]),
            rationale=data["rationale"],
            authorized_by=data["authorized_by"],
            created_at=data["created_at"],
            expires_at=data.get("expires_at"),
            non_expiring_justification=data.get("non_expiring_justification"),
            sha256=data["sha256"],
            raw=data,
        )

    def expired_at(self, now: _dt.datetime) -> bool:
        """True when the exception has an expiry that has passed (spec 6.3)."""
        if self.expires_at is None:
            return False
        return parse_timestamp(self.expires_at) <= now

    def hash_matches(self) -> bool:
        return content_hash(dict(self.raw), exclude={"sha256"}) == self.sha256


@dataclass(frozen=True, slots=True)
class IgnoredDirective:
    """A policy directive that was refused, retained for the resolution trace.

    Spec Section 6.2 forbids weakening a rule through a bare override. Dropping
    the directive silently would hide an attempted policy change from the
    receipt, so every refusal is recorded here and surfaced by
    :meth:`PolicySnapshot.ignored_directives`.
    """

    rule_id: str
    profile: str
    directive: str
    attempted_state: str
    effective_state: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "profile": self.profile,
            "directive": self.directive,
            "attempted_state": self.attempted_state,
            "effective_state": self.effective_state,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class RuleState:
    """The resolved state of one rule for one profile, with provenance."""

    rule_id: str
    profile: str
    state: str
    layer: str
    default_state: str
    exception_id: str | None = None
    ignored: tuple[IgnoredDirective, ...] = ()

    @property
    def runs(self) -> bool:
        return self.state != "disabled"

    @property
    def blocks_conformance(self) -> bool:
        return self.state == "required"

    @property
    def surfaces_findings(self) -> bool:
        return self.state in ("advisory", "required")


@dataclass(frozen=True, slots=True)
class ExceptionDiagnostic:
    exception_id: str
    rule_id: str
    status: str  # active | expired | hash_mismatch | unscoped | weakening_without_authority
    detail: str


@dataclass(slots=True)
class PolicySnapshot:
    """A validated ``ats.policy_snapshot.v1`` with resolution helpers."""

    raw: Mapping[str, Any]
    rules: Mapping[str, Mapping[str, Any]]
    exceptions: tuple[PolicyException, ...] = field(default_factory=tuple)

    @classmethod
    def from_document(
        cls, document: Mapping[str, Any], rules: Mapping[str, Mapping[str, Any]]
    ) -> PolicySnapshot:
        if document.get("schema_version") != "ats.policy_snapshot.v1":
            raise UsageError(
                f"expected ats.policy_snapshot.v1, got {document.get('schema_version')!r}"
            )
        exceptions = tuple(PolicyException.from_dict(e) for e in document.get("exceptions", []))
        return cls(raw=document, rules=rules, exceptions=exceptions)

    # -- identity ----------------------------------------------------------

    @property
    def snapshot_id(self) -> str:
        return self.raw["snapshot_id"]

    @property
    def declared_sha256(self) -> str:
        return self.raw["snapshot_sha256"]

    @property
    def spec_version(self) -> str:
        return self.raw["spec_version"]

    @property
    def profiles(self) -> tuple[str, ...]:
        return tuple(self.raw["profiles"])

    @property
    def fallback_policy(self) -> str:
        return self.raw.get("fallback_policy", "fail_closed")

    @property
    def finding_budget(self) -> Mapping[str, Any]:
        return self.raw["finding_budget"]

    def computed_sha256(self) -> str:
        return content_hash(dict(self.raw), exclude={"snapshot_sha256"})

    def require_current(self, *, spec_version: str) -> str:
        """Spec Section 14.3 / 6.6: bind the exact snapshot hash before evaluation."""
        computed = self.computed_sha256()
        if computed != self.declared_sha256:
            raise StalePolicyError(
                f"policy snapshot {self.snapshot_id!r} declares "
                f"snapshot_sha256={self.declared_sha256} but canonical bytes hash to {computed}; "
                "two snapshots with one id and different hashes are distinct policy versions"
            )
        if self.spec_version != spec_version:
            raise StalePolicyError(
                f"policy snapshot targets spec_version {self.spec_version!r} "
                f"but the imported package is {spec_version!r}"
            )
        return computed

    # -- rule states -------------------------------------------------------

    def default_state(self, rule_id: str, profile: str) -> str:
        rule = self.rules.get(rule_id)
        if rule is None:
            raise PolicyResolutionError(f"unknown rule id {rule_id!r}")
        defaults = rule["default_states"]
        if profile in defaults:
            return defaults[profile]
        # Extension and reserved profiles inherit nothing by similarity
        # (spec Section 9.5): the rule simply does not run.
        return "disabled"

    def resolve_rule(
        self,
        rule_id: str,
        profile: str,
        *,
        now: _dt.datetime,
        artifact_id: str | None = None,
        section_id: str | None = None,
        claim_id: str | None = None,
        path: str | None = None,
    ) -> RuleState:
        """Resolve one rule for one profile at one scope."""
        default = self.default_state(rule_id, profile)
        state = default
        layer = (
            "profile_default"
            if profile in self.rules[rule_id]["default_states"]
            else "standard_default"
        )

        ignored: list[IgnoredDirective] = []

        # A bare override may only strengthen (spec 6.2); weakening requires an
        # exact scoped exception.
        override = self.raw.get("rule_overrides", {}).get(rule_id)
        if override is not None:
            if STATE_RANK[override] > STATE_RANK[state]:
                state = override
                layer = "project_policy"
            elif STATE_RANK[override] < STATE_RANK[state]:
                ignored.append(
                    IgnoredDirective(
                        rule_id=rule_id,
                        profile=profile,
                        directive="rule_override",
                        attempted_state=override,
                        effective_state=state,
                        reason=(
                            "a more specialized policy MUST NOT weaken a rule without an exact "
                            "TextPolicyExceptionV1 (spec 6.2); the override was refused"
                        ),
                    )
                )

        applied: str | None = None
        for exc in self.exceptions:
            if exc.rule_id != rule_id:
                continue
            if not exc.hash_matches():
                ignored.append(
                    IgnoredDirective(
                        rule_id=rule_id,
                        profile=profile,
                        directive=f"exception:{exc.exception_id}",
                        attempted_state=exc.to_state,
                        effective_state=state,
                        reason="exception sha256 does not match its canonical bytes",
                    )
                )
                continue
            if exc.expired_at(now):
                ignored.append(
                    IgnoredDirective(
                        rule_id=rule_id,
                        profile=profile,
                        directive=f"exception:{exc.exception_id}",
                        attempted_state=exc.to_state,
                        effective_state=state,
                        reason=(
                            f"expired at {exc.expires_at}; an expired exception is invalid and the "
                            "original rule state is re-evaluated (spec 6.3)"
                        ),
                    )
                )
                continue
            if not exc.scope.covers(
                artifact_id=artifact_id, section_id=section_id, claim_id=claim_id, path=path
            ):
                continue
            state = exc.to_state
            layer = "scoped_exception"
            applied = exc.exception_id
        return RuleState(
            rule_id=rule_id,
            profile=profile,
            state=state,
            layer=layer,
            default_state=default,
            exception_id=applied,
            ignored=tuple(ignored),
        )

    def resolve_composed(
        self,
        rule_id: str,
        profiles: Iterable[str],
        *,
        now: _dt.datetime,
        **scope: Any,
    ) -> tuple[RuleState, PolicyConflict | None]:
        """Resolve a rule across composed section profiles (spec Section 6.5).

        Non-conflicting requirements accumulate and the stricter state wins. A
        genuine conflict — one profile weakened by an exception while another
        requires the rule — is returned as a typed conflict rather than
        silently resolved.
        """
        states = [self.resolve_rule(rule_id, p, now=now, **scope) for p in profiles]
        if not states:
            raise PolicyResolutionError(
                f"section resolves to no profile; every section MUST resolve to at least one "
                f"content profile (spec 6.5) [rule {rule_id}]"
            )
        winner = states[0]
        for candidate in states[1:]:
            if STATE_RANK[candidate.state] > STATE_RANK[winner.state]:
                winner = candidate
        # Refusals recorded under any composed profile stay attached to the
        # winning state so the receipt shows every directive that was declined.
        merged_ignored = tuple(d for s in states for d in s.ignored)
        if merged_ignored != winner.ignored:
            winner = replace(winner, ignored=merged_ignored)
        conflict: PolicyConflict | None = None
        weakened = [s for s in states if s.exception_id is not None]
        if weakened:
            strongest = max(STATE_RANK[s.state] for s in states)
            if any(STATE_RANK[w.state] < strongest for w in weakened):
                conflict = PolicyConflict(
                    rule_id=rule_id,
                    profiles=tuple(s.profile for s in states),
                    states=tuple(s.state for s in states),
                    detail=(
                        "a scoped exception weakens this rule under one profile while another "
                        "composed profile keeps it stronger; the conflict is typed, not resolved"
                    ),
                )
        return winner, conflict

    def resolve_all(
        self, profiles: Iterable[str], *, now: _dt.datetime, **scope: Any
    ) -> tuple[dict[str, RuleState], list[PolicyConflict]]:
        profiles = tuple(profiles)
        states: dict[str, RuleState] = {}
        conflicts: list[PolicyConflict] = []
        for rule_id in sorted(self.rules):
            state, conflict = self.resolve_composed(rule_id, profiles, now=now, **scope)
            states[rule_id] = state
            if conflict is not None:
                conflicts.append(conflict)
        return states, conflicts

    @staticmethod
    def ignored_directives(states: Mapping[str, RuleState]) -> list[IgnoredDirective]:
        """Every policy directive refused during a resolution, for the receipt."""
        out: list[IgnoredDirective] = []
        for rule_id in sorted(states):
            out.extend(states[rule_id].ignored)
        return out

    # -- diagnostics -------------------------------------------------------

    def exception_diagnostics(self, now: _dt.datetime) -> list[ExceptionDiagnostic]:
        out: list[ExceptionDiagnostic] = []
        for exc in self.exceptions:
            if not exc.hash_matches():
                out.append(
                    ExceptionDiagnostic(
                        exc.exception_id,
                        exc.rule_id,
                        "hash_mismatch",
                        "declared sha256 does not match the canonical bytes of the exception",
                    )
                )
                continue
            if exc.expired_at(now):
                out.append(
                    ExceptionDiagnostic(
                        exc.exception_id,
                        exc.rule_id,
                        "expired",
                        f"expired at {exc.expires_at}; the original rule state is re-evaluated",
                    )
                )
                continue
            mechanical = any(
                getattr(exc.scope, dim) is not None
                for dim in ("artifact_id", "section_id", "claim_id", "path")
            )
            if not mechanical:
                out.append(
                    ExceptionDiagnostic(
                        exc.exception_id,
                        exc.rule_id,
                        "unscoped",
                        "scope declares only a description; no mechanical dimension to match",
                    )
                )
                continue
            out.append(
                ExceptionDiagnostic(exc.exception_id, exc.rule_id, "active", "in force")
            )
        return out

    def unsupported_profiles(self) -> tuple[str, ...]:
        """Declared profiles this edition does not fully specify (spec Section 9.5)."""
        return tuple(p for p in self.profiles if p not in STABLE_PROFILES)


def parse_timestamp(value: str) -> _dt.datetime:
    """Parse an RFC 3339 timestamp into an aware UTC datetime."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = _dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise UsageError(f"invalid RFC 3339 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise UsageError(f"timestamp {value!r} has no timezone offset")
    return parsed.astimezone(_dt.UTC)


def now_utc() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.UTC)

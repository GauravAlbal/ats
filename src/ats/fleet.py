"""Fleet artifact policy resolution (draft.2 D-G).

The fleet policy is the machine-readable contract for deciding when ATS applies
to an artifact, what enforcement is required, and how failures are treated.
The checked-in default is a host-neutral public draft.2 authoring policy; a
deployment may provide an explicit policy for local fleet conventions. This
module validates ``ats.fleet_policy.v1`` documents against the repository-local
schema, binds them by content address (fail-closed: a document whose
``policy_id`` does not match its canonical bytes is an error, never a pass),
and resolves applicability for one artifact class.

Applicability is by artifact intent/policy classification, never inferred from
a filename alone: the schema records ``applicability_basis`` on every class
entry. Resolution precedence (least to most specialized):

1. ``default_exclusions`` are the floor — an excluded class is NOT applicable
   unless it is explicitly required.
2. ``text_policy.required_for`` makes a class applicable.
3. A ``repository_overrides`` entry for the resolved repository adjusts the
   required set (additions/removals), may replace ``default_exclusions`` for
   that repository, and overlays enforcement/failure policy.

Unknown classes with no rule resolve to NOT applicable; they are never
auto-required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Mapping

from .canonical import content_hash
from .errors import StalePolicyError, UsageError
from .spec_package import REPO_ROOT

#: Repository-local fleet policy schema id (ADR-0003: local extension, new $id).
FLEET_POLICY_SCHEMA_ID: Final[str] = "ats_fleet_policy_v1.schema.json"

#: Host-neutral public draft.2 policy used when no --policy is given.
DEFAULT_POLICY_PATH: Final[Path] = REPO_ROOT / "config" / "policies" / "fleet_policy.json"

#: The schema_version discriminator fleet policy documents declare.
FLEET_POLICY_SCHEMA_VERSION: Final[str] = "ats.fleet_policy.v1"

#: Which source decided a resolution; the vocabulary receipts can bind.
BASIS_TEXT_POLICY: Final[str] = "text_policy"
BASIS_REPOSITORY_OVERRIDE: Final[str] = "repository_override"
BASIS_DEFAULT_EXCLUSION: Final[str] = "default_exclusion"


@dataclass(frozen=True, slots=True)
class RepositoryOverride:
    """One per-repository adjustment to the fleet policy (draft.2 D-G)."""

    repository: str
    required_for_additions: tuple[str, ...]
    required_for_removals: tuple[str, ...]
    default_exclusions: tuple[str, ...] | None
    enforcement_overrides: Mapping[str, str]
    failure_policy: Mapping[str, str] | None
    receipt_binding: str


@dataclass(frozen=True, slots=True)
class FleetPolicy:
    """A validated and content-bound ``ats.fleet_policy.v1`` document."""

    raw: Mapping[str, Any]
    policy_id: str
    text_policy: Mapping[str, Any]
    default_exclusions: tuple[str, ...]
    repository_overrides: Mapping[str, RepositoryOverride]

    @classmethod
    def from_document(cls, document: Mapping[str, Any], schemas: Any) -> FleetPolicy:
        """Validate ``document`` against the repo SchemaSet and bind its hash.

        Fail-closed: schema violations raise
        :class:`~ats.errors.SchemaValidationError`; a ``policy_id`` that does
        not match the canonical content hash raises
        :class:`~ats.errors.StalePolicyError`.
        """
        if not isinstance(document, Mapping):
            raise UsageError("a fleet policy document is a JSON object")
        schemas.validate(document, FLEET_POLICY_SCHEMA_ID)
        computed = content_hash(dict(document), exclude={"policy_id"})
        declared = document.get("policy_id")
        if computed != declared:
            raise StalePolicyError(
                f"fleet policy declares policy_id={declared!r} but canonical bytes hash to "
                f"{computed}; a stale or unverifiable policy document is an error, not a pass"
            )
        overrides: list[RepositoryOverride] = []
        seen: set[str] = set()
        for entry in document.get("repository_overrides", []):
            repo = entry["repository"]
            if repo in seen:
                raise UsageError(
                    f"fleet policy declares more than one repository override for {repo!r}; "
                    "the resolution would be ambiguous"
                )
            seen.add(repo)
            per_repo_exclusions = entry.get("default_exclusions")
            overrides.append(
                RepositoryOverride(
                    repository=repo,
                    required_for_additions=tuple(entry.get("required_for_additions", ())),
                    required_for_removals=tuple(entry.get("required_for_removals", ())),
                    default_exclusions=(
                        tuple(per_repo_exclusions) if per_repo_exclusions is not None else None
                    ),
                    enforcement_overrides=dict(entry.get("enforcement_overrides", {})),
                    failure_policy=entry.get("failure_policy"),
                    receipt_binding=entry["receipt_binding"],
                )
            )
        return cls(
            raw=dict(document),
            policy_id=computed,
            text_policy=dict(document["text_policy"]),
            default_exclusions=tuple(document.get("default_exclusions", ())),
            repository_overrides={o.repository: o for o in overrides},
        )

    # -- identity ----------------------------------------------------------

    @property
    def spec_version(self) -> str:
        """The standard version the policy text targets (e.g. ``1.0.0-draft.2``)."""
        return self.text_policy["version"]

    @property
    def required_for(self) -> tuple[str, ...]:
        return tuple(self.text_policy["required_for"])

    @property
    def enforcement(self) -> Mapping[str, str]:
        return self.text_policy["enforcement"]

    @property
    def failure_policy(self) -> Mapping[str, str]:
        return self.text_policy["failure_policy"]

    # -- resolution --------------------------------------------------------

    def resolve(
        self, artifact_class: str, *, repository: str | None = None
    ) -> Resolution:
        """Resolve the fleet policy for one artifact class.

        The repository override (when one exists for ``repository``) is folded
        into the effective required set and exclusion list BEFORE membership is
        decided, so additions can make a class applicable, removals can take a
        base-required class out, and per-repository exclusions replace the
        fleet-level list. Enforcement overrides and a per-repository failure
        policy overlay the text policy whenever an override exists, regardless
        of who decided membership.
        """
        override = (
            self.repository_overrides.get(repository) if repository is not None else None
        )

        required: set[str] = set(self.text_policy["required_for"])
        exclusions: set[str] = set(self.default_exclusions)
        if override is not None:
            required |= set(override.required_for_additions)
            required -= set(override.required_for_removals)
            if override.default_exclusions is not None:
                exclusions = set(override.default_exclusions)

        enforcement = dict(self.text_policy["enforcement"])
        failure_policy = dict(self.text_policy["failure_policy"])
        if override is not None:
            enforcement.update(override.enforcement_overrides)
            if override.failure_policy is not None:
                failure_policy = dict(override.failure_policy)

        applicable, basis = self._decide(artifact_class, required, exclusions, override)
        return Resolution(
            applicable=applicable,
            enforcement=enforcement,
            failure_policy=failure_policy,
            basis=basis,
            policy_id=self.policy_id,
            spec_version=self.spec_version,
        )

    @staticmethod
    def _decide(
        artifact_class: str,
        required: set[str],
        exclusions: set[str],
        override: RepositoryOverride | None,
    ) -> tuple[bool, str]:
        """Membership plus the source that decided it."""
        if artifact_class in exclusions and artifact_class not in required:
            # Exclusion is the floor: not applicable unless explicitly required.
            if override is not None and artifact_class in override.required_for_removals:
                return False, BASIS_REPOSITORY_OVERRIDE
            if (
                override is not None
                and override.default_exclusions is not None
                and artifact_class in override.default_exclusions
            ):
                return False, BASIS_REPOSITORY_OVERRIDE
            return False, BASIS_DEFAULT_EXCLUSION
        if artifact_class in required:
            if override is not None and artifact_class in override.required_for_additions:
                return True, BASIS_REPOSITORY_OVERRIDE
            return True, BASIS_TEXT_POLICY
        # Unknown class with no rule: never auto-required.
        if override is not None and artifact_class in override.required_for_removals:
            return False, BASIS_REPOSITORY_OVERRIDE
        return False, BASIS_TEXT_POLICY


@dataclass(frozen=True, slots=True)
class Resolution:
    """The resolved fleet policy for one artifact class.

    ``basis`` names the source that decided applicability: ``text_policy``,
    ``repository_override``, or ``default_exclusion``. ``enforcement`` and
    ``failure_policy`` are the EFFECTIVE maps for the class (text policy
    overlaid with any repository overrides), whether or not the class is
    applicable, so a receipt can bind the exact enforcement set.
    """

    applicable: bool
    enforcement: Mapping[str, str]
    failure_policy: Mapping[str, str]
    basis: str
    policy_id: str
    spec_version: str

    def to_dict(self) -> dict[str, Any]:
        """Canonical-JSON-safe view for CLI emission and receipts."""
        return {
            "applicable": self.applicable,
            "basis": self.basis,
            "enforcement": dict(self.enforcement),
            "failure_policy": dict(self.failure_policy),
            "policy_id": self.policy_id,
            "spec_version": self.spec_version,
        }


def resolve(
    policy_document: Mapping[str, Any] | FleetPolicy,
    artifact_class: str,
    *,
    repository: str | None = None,
    schemas: Any | None = None,
) -> Resolution:
    """Resolve the fleet policy for one artifact class.

    ``policy_document`` is either a validated :class:`FleetPolicy` (resolved
    directly) or a raw ``ats.fleet_policy.v1`` document, in which case
    ``schemas`` MUST be the repo :class:`~ats.schemas.SchemaSet` used to
    validate and content-bind it.
    """
    if isinstance(policy_document, FleetPolicy):
        return policy_document.resolve(artifact_class, repository=repository)
    if schemas is None:
        raise UsageError(
            "resolve() on a raw fleet policy document requires schemas= to validate it"
        )
    return FleetPolicy.from_document(policy_document, schemas).resolve(
        artifact_class, repository=repository
    )

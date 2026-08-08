"""The resolved evaluation context.

One object carrying the imported package, its schemas, the rule registry, the
force lexicon, and this implementation's capability declaration. Every
subsystem takes a context rather than reaching for globals, so a test can point
the whole stack at a different package version without patching module state.
"""

from __future__ import annotations

import datetime as _dt
import functools
from dataclasses import dataclass
from typing import Any, Mapping

from . import IMPLEMENTATION_NAME, __version__
from .canonical import content_hash
from .capability import CapabilityDeclaration, load_capability
from .errors import UsageError
from .policy import PolicySnapshot, now_utc
from .rules.registry import ForceLexicon, RuleRegistry
from .rules.results import Detector
from .schemas import SchemaSet
from .spec_package import SpecPackage

#: Where the authority basis for a conformance-evidence detector is recorded.
AUTHORITY_BASIS_DOC = "docs/AUTHORITY_MODEL.md"


# No ``slots``: ``schema_set_sha256`` is a ``functools.cached_property``.
@dataclass
class Context:
    package: SpecPackage
    schemas: SchemaSet
    registry: RuleRegistry
    lexicon: ForceLexicon
    capability: CapabilityDeclaration
    now: _dt.datetime

    @classmethod
    def load(
        cls, spec_version: str | None = None, *, now: _dt.datetime | None = None
    ) -> Context:
        package = SpecPackage.load(spec_version)
        schemas = SchemaSet(package)
        registry = RuleRegistry(package)
        lexicon = ForceLexicon(package)
        capability = load_capability(registry, schemas, package_root=package.root)
        return cls(
            package=package,
            schemas=schemas,
            registry=registry,
            lexicon=lexicon,
            capability=capability,
            now=now or now_utc(),
        )

    # -- identity ----------------------------------------------------------

    @property
    def spec_version(self) -> str:
        return self.package.spec_version

    @property
    def implementation(self) -> dict[str, str]:
        return {
            "name": IMPLEMENTATION_NAME,
            "version": __version__,
            "rule_registry_version": self.registry.spec_version,
            "lexicon_version": self.lexicon.version,
        }

    @functools.cached_property
    def schema_set_sha256(self) -> str:
        """Content address over every schema in play, normative and local."""
        return content_hash({k: v for k, v in sorted(self.schemas.documents.items())}, exclude=set())

    def detector(
        self,
        name: str,
        *,
        detector_class: str,
        authority: str,
        basis_anchor: str | None = None,
    ) -> Detector:
        """Build a detector identity, refusing authority a class may not carry."""
        from .rules.registry import DETECTOR_CLASS_MAX_AUTHORITY

        ceiling = DETECTOR_CLASS_MAX_AUTHORITY.get(detector_class)
        if ceiling is None:
            raise UsageError(f"unknown detector class {detector_class!r}")
        if authority == "conformance_evidence" and ceiling != "conformance_evidence":
            raise UsageError(
                f"detector class {detector_class} may not carry conformance_evidence authority"
            )
        basis = None
        if authority == "conformance_evidence":
            basis = f"{AUTHORITY_BASIS_DOC}#{basis_anchor or name}"
        return Detector(
            name=name,
            version=__version__,
            detector_class=detector_class,
            authority=authority,
            authority_basis_ref=basis,
            detector_status="deterministic",
        )

    # -- policy ------------------------------------------------------------

    def policy(self, document: Mapping[str, Any]) -> PolicySnapshot:
        """Validate and bind a policy snapshot, failing closed on staleness."""
        self.schemas.validate(document, "ats_policy_snapshot_v1.schema.json")
        snapshot = PolicySnapshot.from_document(document, self.registry.raw_rules)
        snapshot.require_current(spec_version=self.spec_version)
        return snapshot

    def timestamp(self) -> str:
        return self.now.astimezone(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

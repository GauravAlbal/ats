"""Access to the imported normative package.

``spec/ATS-1/<version>/`` is immutable upstream territory. Every read goes
through this module so that no implementation convenience can rewrite a
normative object or vocabulary. Nothing here writes into the package
directory; the import receipt is deliberately written beside the manifest and
is deliberately absent from the manifest's own file list.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from .canonical import load_json
from .errors import PackageIntegrityError, UsageError
from .hashes import file_sha256

#: Repository root, resolved from this file's location.
REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SPEC_ROOT: Final[Path] = REPO_ROOT / "spec" / "ATS-1"

#: The legacy interpretation default (ADR-0020): corpus reads, the annotation
#: bench, and unlabeled historical material resolve here when no policy or
#: explicit --spec-version pins an edition. An old artifact must never acquire
#: draft.2 semantics merely because the fleet advanced.
DEFAULT_SPEC_VERSION: Final[str] = "1.0.0-draft.1"

#: The new durable authoring default (ADR-0020, F0): new ATS-authored artifacts
#: resolve here. The fleet policy document pins this edition, so a command run
#: under the fleet policy (or any policy whose declared spec_version is draft.2)
#: resolves draft.2 automatically; this constant is the documented anchor.
AUTHORING_SPEC_VERSION: Final[str] = "1.0.0-draft.2"


def declared_policy_spec_version(path: Path) -> str | None:
    """The edition a policy document pins, read directly from its bytes.

    Used by the CLI's context resolution to pick the standard edition before a
    :class:`Context` exists (the policy layer validates currentness later).
    Returns ``None`` when the file cannot be read or declares no version, so
    the caller falls back to the legacy interpretation default rather than
    inventing an edition.
    """
    try:
        document = load_json(path)
    except Exception:
        return None
    # Policy snapshots declare spec_version at the top level; the fleet policy
    # document declares the standard edition at text_policy.version.
    declared = document.get("spec_version")
    if not isinstance(declared, str) or not declared:
        text_policy = document.get("text_policy") or {}
        declared = text_policy.get("version")
    return declared if isinstance(declared, str) and declared else None
#: Import receipts live BESIDE the version directories, never inside one.
#:
#: The upstream validator (``tools/validate_package.py``) asserts that the set
#: of files under the package root equals the manifest's file list exactly. A
#: receipt written inside the package would therefore make the package's own
#: validator fail on every run after the import. Keeping receipts in a sibling
#: directory leaves the version directory byte-identical to the upstream
#: distribution, which is what "preserve the package bytes exactly" requires.
RECEIPTS_DIRNAME: Final[str] = "receipts"


@dataclass(frozen=True, slots=True)
class FileIntegrity:
    path: str
    expected_sha256: str
    actual_sha256: str | None
    expected_bytes: int
    actual_bytes: int | None

    @property
    def ok(self) -> bool:
        return (
            self.actual_sha256 == self.expected_sha256 and self.actual_bytes == self.expected_bytes
        )

    @property
    def status(self) -> str:
        if self.actual_sha256 is None:
            return "missing"
        return "match" if self.ok else "mismatch"


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    spec_version: str
    root: Path
    files: tuple[FileIntegrity, ...]
    extra_files: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return all(f.ok for f in self.files) and not self.extra_files

    def failures(self) -> tuple[FileIntegrity, ...]:
        return tuple(f for f in self.files if not f.ok)


class SpecPackage:
    """A read-only view over one imported normative package version."""

    def __init__(self, root: Path, spec_version: str) -> None:
        self.root = root
        self.spec_version = spec_version

    # -- discovery ---------------------------------------------------------

    @classmethod
    def load(cls, spec_version: str | None = None, *, root: Path | None = None) -> SpecPackage:
        base = root if root is not None else SPEC_ROOT
        version = spec_version or DEFAULT_SPEC_VERSION
        path = base / version
        if not (path / "MANIFEST.json").is_file():
            raise UsageError(
                f"no imported ATS-1 package at {path}; expected MANIFEST.json. "
                "Import the normative package before running implementation commands."
            )
        return cls(path, version)

    @classmethod
    def available_versions(cls, *, root: Path | None = None) -> tuple[str, ...]:
        base = root if root is not None else SPEC_ROOT
        if not base.is_dir():
            return ()
        return tuple(
            sorted(p.name for p in base.iterdir() if (p / "MANIFEST.json").is_file())
        )

    # -- normative documents ----------------------------------------------

    @functools.cached_property
    def manifest(self) -> dict[str, Any]:
        return load_json(self.root / "MANIFEST.json")

    @functools.cached_property
    def manifest_sha256(self) -> str:
        return file_sha256(self.root / "MANIFEST.json")

    @functools.cached_property
    def ruleset(self) -> dict[str, Any]:
        """The ruleset YAML for this edition; the filename moved at draft.2.

        draft.1 ships ``ats_rules_v1.yaml`` (schema_version ``ats.ruleset.v1``);
        draft.2 ships ``ats_rules_v2.yaml`` (schema_version ``ats.ruleset.v2``,
        36 rules). The registry never hardcodes which file an edition carries.
        """
        for name in ("ats_rules_v2.yaml", "ats_rules_v1.yaml"):
            path = self.root / "rules" / name
            if path.is_file():
                return self._load_yaml(path)
        raise UsageError(f"no ruleset found under {self.root / 'rules'}")

    @functools.cached_property
    def force_lexicon(self) -> dict[str, Any]:
        return self._load_yaml(self.root / "lexicons" / "ats_force_lexicon_v1.yaml")

    @functools.cached_property
    def schema_paths(self) -> tuple[Path, ...]:
        return tuple(sorted((self.root / "schemas").glob("*.schema.json")))

    def schema(self, schema_file: str) -> dict[str, Any]:
        path = self.root / "schemas" / schema_file
        if not path.is_file():
            raise UsageError(f"normative schema not found: {schema_file}")
        return load_json(path)

    def example(self, name: str) -> Any:
        path = self.root / "examples" / name
        if not path.is_file():
            raise UsageError(f"normative example not found: {name}")
        return load_json(path)

    @property
    def spec_document(self) -> Path:
        return self.root / "ATS-1_SPEC.md"

    @property
    def validator_script(self) -> Path:
        return self.root / "tools" / "validate_package.py"

    @property
    def receipts_dir(self) -> Path:
        return self.root.parent / RECEIPTS_DIRNAME

    @property
    def import_receipt_path(self) -> Path:
        return self.receipts_dir / f"{self.spec_version}.json"

    def import_receipt(self) -> dict[str, Any] | None:
        path = self.import_receipt_path
        return load_json(path) if path.is_file() else None

    # -- integrity ---------------------------------------------------------

    def verify(self) -> IntegrityReport:
        """Compare the on-disk package bytes against its own manifest.

        The import receipt is excluded: it is an implementation artifact placed
        beside the package and is intentionally not covered by the upstream
        manifest.
        """
        entries: list[FileIntegrity] = []
        listed: set[str] = set()
        for record in self.manifest["files"]:
            rel = record["path"]
            listed.add(rel)
            target = self.root / rel
            if target.is_file():
                entries.append(
                    FileIntegrity(
                        path=rel,
                        expected_sha256=record["sha256"],
                        actual_sha256=file_sha256(target),
                        expected_bytes=record["bytes"],
                        actual_bytes=target.stat().st_size,
                    )
                )
            else:
                entries.append(
                    FileIntegrity(
                        path=rel,
                        expected_sha256=record["sha256"],
                        actual_sha256=None,
                        expected_bytes=record["bytes"],
                        actual_bytes=None,
                    )
                )
        present = {
            str(p.relative_to(self.root))
            for p in self.root.rglob("*")
            if p.is_file()
        }
        extra = tuple(sorted(present - listed - {"MANIFEST.json"}))
        return IntegrityReport(
            spec_version=self.spec_version,
            root=self.root,
            files=tuple(entries),
            extra_files=extra,
        )

    def require_intact(self) -> IntegrityReport:
        report = self.verify()
        if not report.ok:
            broken = ", ".join(f"{f.path} ({f.status})" for f in report.failures())
            extra = ", ".join(report.extra_files)
            detail = "; ".join(part for part in (broken, f"unlisted: {extra}" if extra else "") if part)
            raise PackageIntegrityError(
                f"imported package {self.spec_version} does not match its manifest: {detail}"
            )
        return report

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise UsageError(f"normative file not found: {path}")
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise UsageError(f"{path} is not valid YAML: {exc}") from exc

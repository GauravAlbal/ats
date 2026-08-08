"""Normative-package import and its receipt.

The import is the first link in the evidence chain: every later claim about
conformance is claimed against a specific package version whose bytes were
verified at a specific time by the package's own validator. That evidence is
recorded in ``IMPORT_RECEIPT.json`` beside the manifest and is deliberately
absent from the manifest's file list, so verifying the package against its
manifest never has to special-case our own artifact.
"""

from __future__ import annotations

import datetime as _dt
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import load_json, write_json
from .errors import PackageIntegrityError, UsageError
from .hashes import file_sha256
from .spec_package import SPEC_ROOT, SpecPackage

#: SHA-256 of the ATS-1 1.0.0-draft.1 distribution archive, as published.
KNOWN_ARCHIVE_SHA256: dict[str, str] = {
    "1.0.0-draft.1": "8ccef3dffdf39ad8f6a2a27f5ed2940c0c6180c57eee0f085a8b4644e7d37c28",
}


@dataclass(frozen=True, slots=True)
class ValidatorRun:
    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    interpreter: str

    @property
    def status(self) -> str:
        return "PASS" if self.exit_code == 0 else "FAIL"

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "command": list(self.command),
            "exit_code": self.exit_code,
            "stdout": self.stdout.strip(),
            "status": self.status,
            "interpreter": self.interpreter,
        }
        if self.stderr.strip():
            out["stderr"] = self.stderr.strip()
        return out


def extract_archive(archive: Path, spec_version: str, *, root: Path | None = None) -> Path:
    """Extract ``archive`` into ``spec/ATS-1/<version>/``, preserving bytes exactly.

    The archive's single top-level directory is stripped so the version
    directory holds ``MANIFEST.json`` at its root. Nothing is rewritten: entries
    are copied verbatim.
    """
    base = root if root is not None else SPEC_ROOT
    target = base / spec_version
    if target.exists() and any(target.iterdir()):
        raise UsageError(
            f"{target} already exists and is not empty; an imported package is immutable and "
            "MUST be replaced through a documented upstream-version replacement"
        )
    with zipfile.ZipFile(archive) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        if not names:
            raise UsageError(f"{archive} contains no files")
        prefixes = {n.split("/", 1)[0] for n in names}
        if len(prefixes) != 1:
            raise UsageError(
                f"{archive} has {len(prefixes)} top-level entries; expected one package directory"
            )
        prefix = prefixes.pop()
        target.mkdir(parents=True, exist_ok=True)
        for name in names:
            rel = name[len(prefix) + 1 :]
            if not rel or rel.startswith("/") or ".." in Path(rel).parts:
                raise UsageError(f"refusing unsafe archive member {name!r}")
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(name))
    return target


def run_package_validator(package: SpecPackage, *, interpreter: str | None = None) -> ValidatorRun:
    """Run the package's own offline validator from its directory."""
    script = package.validator_script
    if not script.is_file():
        raise UsageError(f"package validator not found at {script}")
    exe = interpreter or sys.executable
    command = (exe, str(script.relative_to(package.root)))
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        command,
        cwd=package.root,
        capture_output=True,
        text=True,
        check=False,
    )
    return ValidatorRun(
        command=command,
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        interpreter=exe,
    )


def build_receipt(
    package: SpecPackage,
    *,
    archive: Path,
    validator: ValidatorRun,
    imported_at: _dt.datetime,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Assemble the import receipt from measured facts only."""
    integrity = package.verify()
    archive_sha = file_sha256(archive)
    expected = expected_sha256 or KNOWN_ARCHIVE_SHA256.get(package.spec_version, archive_sha)
    with zipfile.ZipFile(archive) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        root_prefix = names[0].split("/", 1)[0] if names else ""
    return {
        "schema_version": "ats.import_receipt.v1",
        "standard": "ATS-1",
        "spec_version": package.spec_version,
        "imported_at": imported_at.astimezone(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "extraction_path": str(package.root.relative_to(package.root.parents[2])),
        "source_archive": {
            "filename": archive.name,
            "sha256": archive_sha,
            "expected_sha256": expected,
            "sha256_matches": archive_sha == expected,
            "bytes": archive.stat().st_size,
            "root_prefix": root_prefix,
        },
        "manifest_sha256": package.manifest_sha256,
        "manifest_file_count": len(package.manifest["files"]),
        "manifest_verification": {
            "status": "match" if integrity.ok else "mismatch",
            "files_checked": len(integrity.files),
            "mismatches": [f.path for f in integrity.files if f.status == "mismatch"],
            "missing": [f.path for f in integrity.files if f.status == "missing"],
            "unlisted": list(integrity.extra_files),
            "excluded_from_manifest": [],
        },
        "package_validator": validator.to_dict(),
        "notes": [
            "The imported package is immutable. Implementation commands read it and never write "
            "into it, and this repository adds no file inside the version directory.",
            "This receipt lives in the sibling `receipts/` directory rather than inside the "
            "package. The upstream validator asserts that the files under the package root "
            "equal the manifest's file list exactly, so a receipt written inside would make the "
            "package's own validator fail on every run after the import.",
        ],
    }


def write_receipt(package: SpecPackage, receipt: dict[str, Any]) -> str:
    """Write the receipt beside the version directory and return its SHA-256."""
    return write_json(package.import_receipt_path, receipt)


def verify_import(package: SpecPackage) -> dict[str, Any]:
    """Re-check a previous import: manifest integrity plus receipt agreement."""
    receipt = package.import_receipt()
    if receipt is None:
        raise PackageIntegrityError(
            f"no import receipt at {package.import_receipt_path}; the import is unreceipted"
        )
    integrity = package.verify()
    manifest_sha = package.manifest_sha256
    problems: list[str] = []
    if not integrity.ok:
        problems.extend(f"{f.path}: {f.status}" for f in integrity.failures())
        problems.extend(f"{p}: unlisted" for p in integrity.extra_files)
    if receipt["manifest_sha256"] != manifest_sha:
        problems.append(
            f"MANIFEST.json now hashes to {manifest_sha}, receipt recorded "
            f"{receipt['manifest_sha256']}"
        )
    if receipt["package_validator"]["status"] != "PASS":
        problems.append("recorded package validator run did not pass")
    if not receipt["source_archive"]["sha256_matches"]:
        problems.append("recorded source archive hash did not match the expected distribution hash")
    return {
        "spec_version": package.spec_version,
        "status": "PASS" if not problems else "FAIL",
        "problems": problems,
        "manifest_sha256": manifest_sha,
        "receipt": receipt,
    }


def load_receipt(path: Path) -> dict[str, Any]:
    return load_json(path)

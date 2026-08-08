#!/usr/bin/env python3
"""Whole-repository coherence gate.

Checks the invariants that no single test owns because they span directories:
the imported package is intact and receipted, every generated artifact is
current, the capability declaration describes the code, every repo-local schema
is valid and namespaced, the public skill-pack provenance is reproducible, the
runtime/build tree has no private dependency, and every declared deliverable
exists.

Run it before committing::

    PYTHONPATH=src python tools/validate_repo.py
"""

from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ats.context import Context  # noqa: E402
from ats.errors import AtsError  # noqa: E402
from ats.schemas import NORMATIVE_SCHEMA_IDS, SCHEMA_FOR_VERSION  # noqa: E402
from ats.spec_import import verify_import  # noqa: E402

GENERATORS = (
    "tools/generate_capability.py",
    "tools/generate_ir_fixtures.py",
    "tools/generate_policies.py",
    "tools/generate_output_bundle.py",
    "tools/generate_corpus_fixtures.py",
)

# Pilot-specific evidence generators were intentionally removed with the
# publication-denied corpus. Only the synthetic fixture generator remains in
# the generated-artifact check.

# No externally-bound or locally-bound corpus generators remain after the
# publication-denied pilot was removed. Public fixture generation is fully
# repository-local and is checked above.

LICENSE_PATHS = (
    "LICENSE.md",
    "LICENSES/Apache-2.0.txt",
    "LICENSES/CC-BY-4.0.txt",
    "THIRD_PARTY_NOTICES.md",
    "spec/ATS-1/LICENSE.md",
)

#: Deliverables the v0 milestone names by path.
REQUIRED_PATHS = (
    "README.md",
    "LICENSE.md",
    "LICENSES/Apache-2.0.txt",
    "LICENSES/CC-BY-4.0.txt",
    "THIRD_PARTY_NOTICES.md",
    "spec/ATS-1/LICENSE.md",
    "pyproject.toml",
    "spec/ATS-1/1.0.0-draft.1/MANIFEST.json",
    "spec/ATS-1/receipts/1.0.0-draft.1.json",
    "capability/ats_rule_capability_v1.json",
    "skills/ats-ir-author/SKILL.md",
    "skills/ats-assess-output/SKILL.md",
    "skills/ats-specify-output/SKILL.md",
    "protocols/ATS_CORPUS_PROTOCOL_V0.md",
    "protocols/ATS_ANNOTATION_GUIDE_V0.md",
    "protocols/ATS_SPLIT_POLICY_V0.md",
    "corpus/operators/ats_mutation_operators_v1.yaml",
    "corpus/README.md",
    "docs/NORTH_STAR.md",
    "docs/ARCHITECTURE.md",
    "docs/AUTHORITY_MODEL.md",
    "docs/SKILL_CONTRACTS.md",
    "docs/CORPUS_DATA_MODEL.md",
    "tools/validate_repo.py",
    # Public corpus deliverables. The denied pilot evidence is intentionally
    # absent; the boundary check below rejects its return rather than requiring
    # historical reports.
    "corpus/seeds/seed_examples.jsonl",
    "fixtures/corpus/examples.jsonl",
    "fixtures/corpus/context_bundles.jsonl",
    "fixtures/corpus/judgments.jsonl",
    "fixtures/corpus/adjudications.jsonl",
    "fixtures/corpus/split_policy.json",
    "fixtures/corpus/split_policy_random.json",
    "fixtures/repositories/sample-repo/COMMITS.json",
    "fixtures/repositories/sample-repo/content/.ats/corpus.json",
    "fixtures/repositories/sample-repo/content/docs/assessment.md",
    "fixtures/repositories/sample-repo/content/docs/requirements.md",
    "fixtures/repositories/sample-repo/content/src/main.py",
)

#: Anchors `capability/ats_rule_capability_v1.json` points into.
REQUIRED_AUTHORITY_ANCHORS = (
    "ats-ir-structural",
    "ats-ir-rule",
    "ats-output-structural",
    "ats-output-rule",
)
#: Files whose execution or packaging can make the public clone depend on
#: private infrastructure. Conceptual references in docs and tests are
#: intentionally outside this gate; they are reviewed by the disclosure gate.
PUBLIC_AUDIT_PATHS = (
    "config",
    "src",
    "tools",
    "pyproject.toml",
    "uv.lock",
    ".github",
    "dist/skill-pack",
)

#: Build these tokens from parts so this checker does not report its own
#: vocabulary as a violation while scanning tools/.
_PRIVATE_TOKENS = (
    "ats-" + "internal",
    "ats_" + "internal",
)
_PRIVATE_IMPORT_MODULES = ("arq", "tribunal", "vx", "moat", "sear")
_PRIVATE_IMPORT_RE = re.compile(
    r"(?m)^\s*(?:from|import)\s+(?:" + "|".join(_PRIVATE_IMPORT_MODULES) + r")(?:\.|\s|$)"
)
_PRIVATE_CHECKOUT_RE = re.compile(r"/(?:Users|home|private)/[A-Za-z0-9._-]+(?:/[^\s'\"`)>]+)+")
_PRIVATE_CONFIG_RE = re.compile(
    r"\b(?:PRIVATE|INTERNAL)_(?:ARQ|FLEET|CORPUS|INTEGRATION)_"
    r"(?:CONFIG|ROOT|PATH|FIXTURES?)\b",
    re.IGNORECASE,
)
_PRIVATE_BUILD_DEP_RE = re.compile(
    r"""(?im)(?:^\s*name\s*=\s*["']|["'])(?:arq|tribunal|vx|moat|sear)(?:["'<>=!~])"""
)
_PRIVATE_FLEET_TOKEN_RE = re.compile(
    r"\b(?:arq|tribunal|moat|vx|sear)\b",
    re.IGNORECASE,
)
# Public-distributable source classes covered by the disclosure boundary. The
# roots are intentionally explicit: this is not a scan of the checkout, and
# private operator state under the excluded pearls directory is outside the
# public export.
PUBLIC_DISCLOSURE_ROOTS = (
    "src",
    "tools",
    "docs",
    "config",
    "schemas",
    "tests",
    "skills",
    "spec",
    "fixtures",
    "corpus",
    "capability",
    "protocols",
    ".github",
    "dist",
)
PUBLIC_DISCLOSURE_EXTENSIONS = frozenset(
    {
        ".c",
        ".cfg",
        ".conf",
        ".css",
        ".csv",
        ".go",
        ".html",
        ".ini",
        ".java",
        ".js",
        ".json",
        ".jsonl",
        ".lock",
        ".md",
        ".markdown",
        ".py",
        ".pyi",
        ".rb",
        ".rst",
        ".rs",
        ".sh",
        ".sql",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
)
PUBLIC_DISCLOSURE_ROOT_FILES = frozenset(
    {
        ".gitignore",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "LICENSE.md",
        "PRODUCT.md",
        "README.md",
        "SECURITY.md",
        "THIRD_PARTY_NOTICES.md",
        "pyproject.toml",
        "uv.lock",
    }
)

PUBLIC_DISCLOSURE_FILENAMES = frozenset({"Dockerfile", "Makefile"})
PUBLIC_DISCLOSURE_EXCLUDED_PARTS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pearls",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "_build",
        "build",
        "cache",
        "scratch",
        "temp",
        "tmp",
        "venv",
    }
)
_DISCLOSURE_SEPARATOR = r"[/\\]"
_DISCLOSURE_HOST_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9])[/\\](?:users|home|private)[/\\][A-Za-z0-9._-]+",
    re.IGNORECASE,
)
_DISCLOSURE_REPOSITORY_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    + re.escape("ats-" + "internal")
    + r"(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_DISCLOSURE_PILOT_RE = re.compile(
    r"(?<![A-Za-z0-9])corpus"
    + _DISCLOSURE_SEPARATOR
    + r"pilot-0(?=$|[/\\\s'\"`<>)\],.;:!?])",
    re.IGNORECASE,
)
_DISCLOSURE_AUTHORITY_RE = re.compile(
    r"(?<![A-Za-z0-9])corpus"
    + _DISCLOSURE_SEPARATOR
    + r"authority"
    + _DISCLOSURE_SEPARATOR
    + r"private-sample(?=$|[/\\\s'\"`<>)\],.;:!?])",
    re.IGNORECASE,
)
_DISCLOSURE_LOCAL_PASTE_RE = re.compile(
    re.escape("local://" + "paste-"),
    re.IGNORECASE,
)

_DISCLOSURE_PEARLS_RE = re.compile(
    r"(?<![A-Za-z0-9])\." + "pearls" + _DISCLOSURE_SEPARATOR,
    re.IGNORECASE,
)
_DISCLOSURE_EMAIL_RE = re.compile(
    re.escape("galbal" + "@") + re.escape("comcast") + r"\.net",
    re.IGNORECASE,
)
_DISCLOSURE_AUTHORITY_CITATION_RE = re.compile(
    r"\b(?:directive\s+§\s*\w+|program\s+directive|operator\s+directive)\b",
    re.IGNORECASE,
)





def _public_audit_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for relative in PUBLIC_AUDIT_PATHS:
        path = repo_root / relative
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(p for p in sorted(path.rglob("*")) if p.is_file())
    return files

def _public_disclosure_files(repo_root: Path) -> list[Path]:
    """Return deterministic files in the explicitly public source classes."""

    def eligible(path: Path) -> bool:
        relative = path.relative_to(repo_root)
        if any(part.lower() in PUBLIC_DISCLOSURE_EXCLUDED_PARTS for part in relative.parts):
            return False
        return path.name in PUBLIC_DISCLOSURE_FILENAMES or path.suffix.lower() in PUBLIC_DISCLOSURE_EXTENSIONS

    candidates: list[Path] = []
    for path in sorted(repo_root.iterdir(), key=lambda item: item.name):
        if path.is_file() and (path.name in PUBLIC_DISCLOSURE_ROOT_FILES or eligible(path)):
            candidates.append(path)
    for relative in PUBLIC_DISCLOSURE_ROOTS:
        root = repo_root / relative
        if root.is_file():
            if eligible(root):
                candidates.append(root)
        elif root.is_dir():
            candidates.extend(path for path in root.rglob("*") if path.is_file() and eligible(path))
    return sorted(set(candidates), key=lambda path: path.relative_to(repo_root).as_posix())


def _reachable_git_metadata(repo_root: Path) -> tuple[list[tuple[str, str]], str | None]:
    """Return commit and annotated-tag metadata reachable from public refs."""

    if not (repo_root / ".git").exists():
        return [], None

    commands = (
        (
            "commit",
            [
                "git",
                "log",
                "--branches",
                "--tags",
                "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B%x1e",
            ],
        ),
        (
            "tag",
            [
                "git",
                "for-each-ref",
                "--format=%(refname)%00%(taggername)%00%(taggeremail)%00%(contents)%1e",
                "refs/tags",
            ],
        ),
    )
    records: list[tuple[str, str]] = []
    for kind, command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as exc:
            return [], f"cannot inspect reachable Git {kind} metadata: {exc}"
        if completed.returncode != 0:
            detail = completed.stderr.strip() or f"exit {completed.returncode}"
            return [], f"cannot inspect reachable Git {kind} metadata: {detail}"
        for raw_record in completed.stdout.split("\x1e"):
            record = raw_record.strip()
            if not record:
                continue
            identity, _, _ = record.partition("\x00")
            records.append((f"reachable Git {kind} {identity}", record))
    return records, None


def check_public_disclosure_surface(repo_root: Path = REPO_ROOT) -> Result:
    """Reject concrete private residues from public files and reachable history."""

    detectors = (
        (_DISCLOSURE_HOST_PATH_RE, "absolute host path"),
        (_DISCLOSURE_REPOSITORY_RE, "private repository identifier"),
        (_DISCLOSURE_PILOT_RE, "denied pilot corpus path"),
        (_DISCLOSURE_AUTHORITY_RE, "denied authority corpus path"),
        (_DISCLOSURE_PEARLS_RE, "private operator state path"),
        (_DISCLOSURE_EMAIL_RE, "operator credential/email residue"),
        (_DISCLOSURE_LOCAL_PASTE_RE, "unavailable private authority citation"),
        (_DISCLOSURE_AUTHORITY_CITATION_RE, "unavailable private authority citation"),
    )
    hits: list[str] = []
    audited = _public_disclosure_files(repo_root)
    for path in audited:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(repo_root).as_posix()
        for detector, reason in detectors:
            detector_text = text
            if relative == ".gitignore" and reason == "private operator state path":
                exclusion = "." + "pearls" + "/"
                detector_text = "\n".join(
                    "" if line == exclusion else line for line in text.splitlines()
                )
            if detector.search(detector_text):
                hits.append(f"{relative}: disclosure residue ({reason})")

    metadata_records, metadata_error = _reachable_git_metadata(repo_root)
    if metadata_error:
        hits.append(metadata_error)
    for identity, text in metadata_records:
        for detector, reason in detectors:
            if detector.search(text):
                hits.append(f"{identity}: disclosure residue ({reason})")

    return Result(
        "public disclosure surface",
        not hits,
        (
            f"{len(audited)} public source file(s) and "
            f"{len(metadata_records)} reachable Git metadata record(s) "
            "contain no concrete private residue"
        )
        if not hits
        else "; ".join(hits[:8]),
    )



def check_public_dependencies(repo_root: Path = REPO_ROOT) -> Result:
    """Reject runtime/build references to private systems or local checkouts.

    This is deliberately narrower than a disclosure scan: useful historical
    prose may mention a fleet system, while executable source, build metadata,
    CI, and distributed files must remain usable in a public clone.
    """
    hits: list[str] = []
    audited = _public_audit_files(repo_root)
    for path in audited:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(repo_root).as_posix()
        lowered = text.lower()
        for token in _PRIVATE_TOKENS:
            if token in lowered:
                hits.append(f"{relative}: private repository token {token!r}")
        for match in _PRIVATE_IMPORT_RE.finditer(text):
            hits.append(f"{relative}: private module import {match.group(0).strip()!r}")
        if path.name in {"pyproject.toml", "uv.lock"}:
            for match in _PRIVATE_BUILD_DEP_RE.finditer(text):
                hits.append(f"{relative}: private build dependency {match.group(0).strip()!r}")

        for match in _PRIVATE_CHECKOUT_RE.finditer(text):
            hits.append(f"{relative}: private/developer checkout path {match.group(0)!r}")
        for match in _PRIVATE_CONFIG_RE.finditer(text):
            hits.append(f"{relative}: private configuration identifier {match.group(0)!r}")
        if relative == "config" or relative.startswith("config/"):
            for match in _PRIVATE_FLEET_TOKEN_RE.finditer(text):
                hits.append(f"{relative}: private fleet token {match.group(0)!r}")
    return Result(
        "public dependency audit",
        not hits,
        f"{len(audited)} runtime/build/distribution file(s) contain no private dependency"
        if not hits
        else "; ".join(hits[:8]),
    )



@dataclass
class Result:
    name: str
    ok: bool
    detail: str

    def render(self) -> str:
        return f"[{'ok  ' if self.ok else 'FAIL'}] {self.name}: {self.detail}"


def check_required_paths() -> Result:
    missing = [p for p in REQUIRED_PATHS if not (REPO_ROOT / p).exists()]
    return Result(
        "deliverables",
        not missing,
        f"all {len(REQUIRED_PATHS)} declared paths exist"
        if not missing
        else f"missing: {', '.join(missing)}",
    )

def check_public_corpus_boundary(repo_root: Path = REPO_ROOT) -> Result:
    """Reject withheld authority records and raw/private corpus payloads."""
    problems: list[str] = []
    corpus_root = repo_root / "corpus"
    for relative in ("raw", "private", "withheld"):
        path = corpus_root / relative
        if path.exists():
            problems.append(f"{path.relative_to(repo_root)} must be absent from the public tree")

    authority = corpus_root / "authority"
    if authority.is_dir():
        for path in sorted(authority.glob("*.json")):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                problems.append(f"{path.relative_to(repo_root)} is not valid authority JSON")
                continue
            if document.get("publication") == "deny" or document.get("classification") == "private":
                problems.append(
                    f"{path.relative_to(repo_root)} is a publication-denied authority record"
                )

    public_roots = (
        corpus_root,
        repo_root / "fixtures" / "corpus",
        repo_root / "fixtures" / "repositories" / "sample-repo",
    )
    forbidden = re.compile(
        r"(?:<private-origin>|\"publication\"\s*:\s*\"deny\"|"
        r"\"classification\"\s*:\s*\"private\"|"
        r"\"use_authority\"\s*:\s*\"(?:internal_only|internal_training_permitted|prohibited)\"|"
        r"\"handling_policy\"\s*:\s*\"(?:internal|confidential|restricted)\")"
    )
    for root in public_roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if forbidden.search(text):
                problems.append(f"{path.relative_to(repo_root)} contains denied corpus metadata")

    return Result(
        "public corpus boundary",
        not problems,
        "no denied authority records, private metadata, or withheld evidence is present"
        if not problems
        else "; ".join(problems[:8]),
    )

def check_license_deliverables(repo_root: Path = REPO_ROOT) -> Result:
    """Require the split license map, legal texts, and package grant."""
    missing = [relative for relative in LICENSE_PATHS if not (repo_root / relative).is_file()]
    problems = [f"missing {relative}" for relative in missing]
    obsolete = repo_root / "LICENSE"
    if obsolete.exists():
        problems.append("obsolete root LICENSE is present")

    expected_hashes = {
        "LICENSES/Apache-2.0.txt": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
        "LICENSES/CC-BY-4.0.txt": "9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411",
    }
    for relative, expected in expected_hashes.items():
        path = repo_root / relative
        if path.is_file():
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                problems.append(f"{relative} is not the canonical legal text")

    text_checks = {
        "LICENSE.md": (
            "Apache-2.0",
            "CC-BY-4.0",
            "spec/ATS-1/",
            "THIRD_PARTY_NOTICES.md",
        ),
        "THIRD_PARTY_NOTICES.md": (
            "uv.lock",
            "upstream terms",
            "does not relicense",
        ),
        "spec/ATS-1/LICENSE.md": (
            "Gaurav Albal",
            "rightsholder",
            "draft.1",
            "draft.2",
            "CC-BY-4.0",
            "Unspecified",
            "Apache-2.0",
        ),
    }
    for relative, required in text_checks.items():
        path = repo_root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for phrase in required:
            if phrase.lower() not in lowered:
                problems.append(f"{relative} omits required licensing boundary {phrase!r}")
        if "by-nc" in lowered:
            problems.append(f"{relative} contains a disallowed noncommercial license claim")
        if relative != "THIRD_PARTY_NOTICES.md" and "mit license" in lowered:
            problems.append(f"{relative} contains an obsolete project license claim")

    return Result(
        "split licensing deliverables",
        not problems,
        "scope map, canonical legal texts, third-party notice, and ATS-1 adjacent grant are present"
        if not problems
        else "; ".join(problems),
    )


def check_package(ctx: Context) -> Result:
    report = ctx.package.verify()
    if not report.ok:
        detail = "; ".join(f"{f.path}: {f.status}" for f in report.failures())
        if report.extra_files:
            detail += f"; unlisted: {', '.join(report.extra_files)}"
        return Result("imported package", False, detail)
    verification = verify_import(ctx.package)
    return Result(
        "imported package",
        verification["status"] == "PASS",
        f"{len(report.files)} file(s) match MANIFEST.json; import receipt "
        f"{verification['status']}" + (f" — {verification['problems']}" if verification["problems"] else ""),
    )


def check_capability(ctx: Context) -> Result:
    problems = ctx.capability.coherence_errors()
    declared = len(ctx.capability.rules)
    return Result(
        "capability declaration",
        not problems,
        f"{declared} rule(s) declared coherently" if not problems else "; ".join(problems[:4]),
    )


def check_schemas(ctx: Context) -> Result:
    problems = [v.message for v in ctx.schemas.check_own_schemas()]
    local_dir = REPO_ROOT / "schemas"
    for path in sorted(local_dir.glob("*.schema.json")):
        schema_id = json.loads(path.read_text(encoding="utf-8"))["$id"]
        if schema_id in NORMATIVE_SCHEMA_IDS:
            problems.append(f"{path.name} shadows normative schema id {schema_id}")
    unregistered = sorted(
        json.loads(p.read_text(encoding="utf-8"))["$id"]
        for p in local_dir.glob("*.schema.json")
        if json.loads(p.read_text(encoding="utf-8"))["$id"] not in SCHEMA_FOR_VERSION.values()
    )
    if unregistered:
        problems.append(f"local schemas not registered in SCHEMA_FOR_VERSION: {unregistered}")
    return Result(
        "schemas",
        not problems,
        f"{len(ctx.schemas.documents)} schema(s) valid and namespaced"
        if not problems
        else "; ".join(problems[:4]),
    )


def check_detectors(ctx: Context) -> Result:
    from ats.rules.deterministic import load_detectors

    detectors = load_detectors()
    # The detector pool is shared across editions; draft.2 adds six rules the
    # draft.1 default registry does not carry. Validate the pool against the
    # union of every imported edition's registry, so a detector is never
    # orphaned and a rule is never without one.
    known = set(ctx.registry.ids())
    for version in ctx.package.available_versions():
        if version == ctx.spec_version:
            continue
        try:
            other = Context.load(spec_version=version)
        except Exception:
            continue  # an edition that cannot load is reported elsewhere
        known |= set(other.registry.ids())
    missing = sorted(known - set(detectors))
    extra = sorted(set(detectors) - known)
    problems = []
    if missing:
        problems.append(f"no detector for {', '.join(missing)}")
    if extra:
        problems.append(f"detector for unknown rule {', '.join(extra)}")
    return Result(
        "detectors",
        not problems,
        f"{len(detectors)} detector(s) cover every registry rule across editions"
        if not problems
        else "; ".join(problems),
    )


def check_generated_artifacts() -> Result:
    stale: list[str] = []
    for script in GENERATORS:
        result = subprocess.run(
            [sys.executable, script, "--check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
        )
        if result.returncode != 0:
            stale.append(f"{script}: {result.stderr.strip() or result.stdout.strip()}")
    return Result(
        "generated artifacts",
        not stale,
            f"{len(GENERATORS)} generator(s) report current; all surviving "
            "generators are locally checkable and included in this check"
        if not stale
        else "; ".join(stale),
    )


def check_authority_anchors() -> Result:
    path = REPO_ROOT / "docs" / "AUTHORITY_MODEL.md"
    if not path.is_file():
        return Result("authority anchors", False, "docs/AUTHORITY_MODEL.md is missing")
    text = path.read_text(encoding="utf-8")
    slugs = set()
    for line in text.splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip().lower()
            slug = "".join(c if c.isalnum() or c in " -" else "" for c in heading)
            slugs.add(slug.replace(" ", "-"))
    missing = [a for a in REQUIRED_AUTHORITY_ANCHORS if a not in slugs]
    return Result(
        "authority anchors",
        not missing,
        "every authority_basis_ref anchor resolves"
        if not missing
        else f"missing anchors: {', '.join(missing)}",
    )


def check_no_placeholders() -> Result:
    """A hollow-implementation scan (constitution #23)."""
    markers = ("TODO:", "FIXME", "raise NotImplementedError", "pass  # stub", "XXX")
    hits: list[str] = []
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for marker in markers:
                if marker in line:
                    hits.append(f"{path.relative_to(REPO_ROOT)}:{number}: {marker}")
    return Result(
        "hollow-implementation scan",
        not hits,
        "no placeholder markers in src/" if not hits else "; ".join(hits[:6]),
    )

def check_skill_pack(repo_root: Path = REPO_ROOT) -> Result:
    """Run the canonical public-pack validator, including provenance/regen checks."""
    from ats.skill_pack import verify_pack

    pack = repo_root / "dist" / "skill-pack"
    findings = verify_pack(pack, repo_root)
    if findings:
        detail = "; ".join(f"{finding.code}: {finding.message}" for finding in findings[:6])
        return Result("public skill pack", False, detail)
    return Result(
        "public skill pack",
        True,
        "manifest, standard identity, source commit, tree hash, hosts, and zero-diff regeneration match",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-generators", action="store_true")
    args = parser.parse_args()

    try:
        ctx = Context.load()
    except AtsError as exc:
        print(f"[FAIL] context: {exc}", file=sys.stderr)
        return 1

    results = [
        check_required_paths(),
        check_public_corpus_boundary(),
        check_license_deliverables(),
        check_package(ctx),
        check_schemas(ctx),
        check_capability(ctx),
        check_detectors(ctx),
        check_authority_anchors(),
        check_no_placeholders(),
        check_public_dependencies(),
        check_public_disclosure_surface(),
        check_skill_pack(),
    ]
    if not args.skip_generators:
        results.append(check_generated_artifacts())

    for result in results:
        print(result.render())
    failed = [r for r in results if not r.ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

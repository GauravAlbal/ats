"""Skill-pack packaging and validation tests.

Covers: deterministic generation (two runs, zero diff); clean regeneration
against the committed ``dist/skill-pack``; manifest schema validity and
SCHEMA_FOR_VERSION registration; per-host file existence and SHA-256 match;
byte parity with the canonical public skills; no local absolute paths; no
fleet-tool-only dependency in the generic pack; the ten mini-constitution laws in
every skill; recipe references and absence of unavailable internal-skill
absolute path, removed required skill, bad plugin name, missing plugin $schema,
missing/tampered generated-host license).
Nothing here reads a wall clock or git: regeneration tests pin the manifest's
own ``generated_at`` / ``source_commit`` (or fixed literals), so they are
deterministic across machines and commits.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from ats import SKILL_PACK_VERSION, __version__
from ats.schemas import SCHEMA_FOR_VERSION
from ats.skill_pack import (
    CANONICAL_RECIPES_PATH,
    HOST_IDENTITIES,
    HOST_RECIPE_DIRECTORIES,
    HOST_NOTICE_SOURCES,
    MANIFEST_SCHEMA_ID,
    MANIFEST_SCHEMA_VERSION,
    MINI_CONSTITUTION,
    PLUGIN_LICENSE,
    PLUGIN_NAME,
    PLUGIN_SCHEMA_URL,
    REQUIRED_SKILLS,
    STANDARD_VERSIONS_SUPPORTED,
    canonical_source_files,
    file_sha256,
    generate_pack,
    tree_hash,
    validate_manifest_schema,
    verify_pack,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_DIR = REPO_ROOT / "dist" / "skill-pack"

#: Fixed literals for the determinism test — independent of the committed
#: manifest's provenance.
FIXED_NOW = "2026-01-02T03:04:05+00:00"
FIXED_COMMIT = "0" * 40


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _manifest() -> dict:
    return json.loads((PACK_DIR / "skill-pack-manifest.json").read_text(encoding="utf-8"))


def _copy_pack(tmp_path: Path) -> Path:
    """Generate a throwaway pack for corruption tests."""
    out = tmp_path / "skill-pack"
    generate_pack(REPO_ROOT, out, now=FIXED_NOW, source_commit=FIXED_COMMIT)
    return out


def _forbid_symlink_content_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text

    def read_bytes(path: Path) -> bytes:
        assert not path.is_symlink(), f"verifier dereferenced symlink bytes: {path}"
        return original_read_bytes(path)

    def read_text(path: Path, *args, **kwargs) -> str:
        assert not path.is_symlink(), f"verifier dereferenced symlink text: {path}"
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(Path, "read_text", read_text)


def _diff(left: Path, right: Path) -> tuple[list[str], list[str]]:
    """(only-in-one relative paths, byte-differing relative paths)."""

    def index(root: Path) -> dict[str, bytes]:
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    a, b = index(left), index(right)
    only = sorted(set(a) ^ set(b))
    changed = [rel for rel in sorted(set(a) & set(b)) if a[rel] != b[rel]]
    return only, changed


def _all_pack_files() -> list[Path]:
    manifest = _manifest()
    paths = [PACK_DIR / entry["path"] for host in manifest["hosts"] for entry in host["files"]]
    return [p for p in paths if p.is_file()]


# -- generation ----------------------------------------------------------------


def test_regeneration_is_deterministic(tmp_path: Path) -> None:
    first = generate_pack(REPO_ROOT, tmp_path / "a", now=FIXED_NOW, source_commit=FIXED_COMMIT)
    second = generate_pack(REPO_ROOT, tmp_path / "b", now=FIXED_NOW, source_commit=FIXED_COMMIT)
    only, changed = _diff(tmp_path / "a", tmp_path / "b")
    assert only == [] and changed == []
    assert first == second



def test_generation_schema_failure_preserves_existing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "skill-pack"
    destination.mkdir()
    sentinel = destination / "sentinel.txt"
    sentinel.write_text("old pack", encoding="utf-8")
    monkeypatch.setattr(
        "ats.skill_pack.validate_manifest_schema",
        lambda manifest, repo_root: ["forced schema failure"],
    )

    with pytest.raises(ValueError, match="generated manifest fails"):
        generate_pack(REPO_ROOT, destination, now=FIXED_NOW, source_commit=FIXED_COMMIT)

    assert sentinel.read_text(encoding="utf-8") == "old pack"
    assert sorted(path.name for path in destination.iterdir()) == ["sentinel.txt"]


def test_generation_rejects_duplicate_recipe_basenames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "skill-pack"
    destination.mkdir()
    sentinel = destination / "sentinel.txt"
    sentinel.write_text("old pack", encoding="utf-8")
    monkeypatch.setattr(
        "ats.skill_pack._canonical_recipe_paths",
        lambda repo_root: [CANONICAL_RECIPES_PATH, "skills/public/recipes/ARTIFACT_RECIPES.md"],
    )

    with pytest.raises(ValueError, match="unique basenames"):
        generate_pack(REPO_ROOT, destination, now=FIXED_NOW, source_commit=FIXED_COMMIT)

    assert sentinel.read_text(encoding="utf-8") == "old pack"


def test_generation_rejects_date_only_timestamp(tmp_path: Path) -> None:
    destination = tmp_path / "skill-pack"

    with pytest.raises(ValueError, match="strict RFC 3339 date-time"):
        generate_pack(REPO_ROOT, destination, now="2026-01-02", source_commit=FIXED_COMMIT)

    assert not destination.exists()

def test_clean_regeneration_matches_the_committed_pack(tmp_path: Path) -> None:
    """Regenerating at the manifest's own provenance reproduces dist/ byte-for-byte."""
    manifest = _manifest()
    regenerated = generate_pack(
        REPO_ROOT, tmp_path / "skill-pack", now=manifest["generated_at"], source_commit=manifest["source_commit"]
    )
    only, changed = _diff(PACK_DIR, tmp_path / "skill-pack")
    assert only == [] and changed == []
    assert regenerated == manifest


# -- manifest ------------------------------------------------------------------


def test_manifest_schema_rejects_date_only_generated_at() -> None:
    manifest = _manifest()
    manifest["generated_at"] = "2026-01-02"

    violations = validate_manifest_schema(manifest, REPO_ROOT)

    assert any("generated_at" in violation for violation in violations)


def test_manifest_is_schema_valid_and_registered(tmp_path: Path) -> None:
    manifest = generate_pack(REPO_ROOT, tmp_path / "skill-pack", now=FIXED_NOW, source_commit=FIXED_COMMIT)
    assert validate_manifest_schema(manifest, REPO_ROOT) == []
    assert SCHEMA_FOR_VERSION[MANIFEST_SCHEMA_VERSION] == MANIFEST_SCHEMA_ID
    assert (REPO_ROOT / "schemas" / MANIFEST_SCHEMA_ID).is_file()


def test_manifest_identity_fields() -> None:
    manifest = _manifest()
    assert manifest["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert manifest["skill_pack_version"] == SKILL_PACK_VERSION == "0.1.4"
    assert manifest["implementation_version"] == __version__
    assert manifest["standard_versions_supported"] == STANDARD_VERSIONS_SUPPORTED
    assert manifest["standard_versions_supported"]["new_authoring"] == "1.0.0-draft.3"
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["canonical_source_sha256"])
    assert manifest["source_commit"]
    assert manifest["packager_version"]


def test_canonical_tree_hash_matches_the_manifest() -> None:
    manifest = _manifest()
    assert manifest["canonical_source_sha256"] == tree_hash(canonical_source_files(REPO_ROOT))
    assert {s["path"] for s in manifest["skills"]} == {
        f"skills/public/{name}/SKILL.md" for name in REQUIRED_SKILLS
    }


def test_required_skills_present_everywhere() -> None:
    manifest = _manifest()
    names = {entry["name"] for entry in manifest["skills"]}
    assert set(REQUIRED_SKILLS) <= names
    for name in REQUIRED_SKILLS:
        assert (REPO_ROOT / "skills" / "public" / name / "SKILL.md").is_file()
        assert (PACK_DIR / "generic" / name / "SKILL.md").is_file()
        assert (PACK_DIR / "agent-plugins" / "skills" / name / "SKILL.md").is_file()


def test_per_host_files_exist_and_match_the_manifest() -> None:
    manifest = _manifest()
    identities = [host["identity"] for host in manifest["hosts"]]
    assert identities == list(HOST_IDENTITIES)
    for host in manifest["hosts"]:
        for entry in host["files"]:
            path = PACK_DIR / entry["path"]
            assert path.is_file(), f"{host['identity']}: {entry['path']} missing"
            assert file_sha256(path) == entry["sha256"], f"sha256 mismatch: {entry['path']}"


def test_host_skill_files_are_byte_identical_to_canonical() -> None:
    for name in REQUIRED_SKILLS:
        canonical = (REPO_ROOT / "skills" / "public" / name / "SKILL.md").read_bytes()
        for host in ("generic", "claude", "codex"):
            assert (PACK_DIR / host / name / "SKILL.md").read_bytes() == canonical
        assert (PACK_DIR / "agent-plugins" / "skills" / name / "SKILL.md").read_bytes() == canonical
def test_each_host_carries_the_complete_split_notice_set() -> None:
    for identity in HOST_IDENTITIES:
        for destination, source in HOST_NOTICE_SOURCES:
            host_notice = PACK_DIR / identity / destination
            root_notice = REPO_ROOT / source
            assert host_notice.is_file(), f"{identity}: {destination} missing"
            assert host_notice.read_bytes() == root_notice.read_bytes()




# -- distributed content checks -------------------------------------------------


def test_no_local_absolute_paths_in_any_distributed_file() -> None:
    repo_root_str = str(REPO_ROOT.resolve())
    for path in _all_pack_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for prefix in ("/" + "Users/", "/" + "tmp", "/" + "private/", "/" + "home/"):
            assert prefix not in text, f"{path.relative_to(PACK_DIR)} contains {prefix!r}"
        assert repo_root_str not in text, f"{path.relative_to(PACK_DIR)} contains the repo root path"


def test_no_fleet_dependency_in_generic_pack() -> None:
    fleet_name = "a" + "rq"
    for path in (PACK_DIR / "generic").rglob("*"):
        if not path.is_file():
            continue
        text = re.sub(
            rf"{fleet_name}\s+text\s+standard",
            "",
            path.read_text(encoding="utf-8"),
            flags=re.IGNORECASE,
        )
        text = re.sub(rf"{fleet_name}\s+text", "", text, flags=re.IGNORECASE)
        assert not re.search(rf"\b{fleet_name}\b", text, re.IGNORECASE), (
            f"{path.name} mentions a fleet dependency"
        )


@pytest.mark.parametrize(
    "identifier",
    ("ats-" + "internal", "A" + "rq", "S" + "ear", "Trib" + "unal", "V" + "X", "M" + "oat"),
)
def test_private_fleet_identifiers_are_rejected_case_insensitively(identifier: str) -> None:
    from ats.skill_pack import _private_fleet_findings

    findings = _private_fleet_findings(f"uses {identifier.swapcase()} here", "generic/test.md")
    assert any(finding.code == "PRIVATE-FLEET-DEP" for finding in findings), findings


def test_private_fleet_identifier_check_uses_word_boundaries() -> None:
    from ats.skill_pack import _private_fleet_findings

    safe = (
        "search " + "s" + "earing " + "tribu" + "nals "
        + "v" + "x" + "path " + "m" + "oatland "
        + "x" + "ats-" + "internalized"
    )
    assert _private_fleet_findings(safe, "generic/test.md") == []


def test_mini_constitution_laws_present_in_every_skill() -> None:
    for name in REQUIRED_SKILLS:
        text = _normalize((PACK_DIR / "generic" / name / "SKILL.md").read_text(encoding="utf-8"))
        missing = [law for law in MINI_CONSTITUTION if law not in text]
        assert missing == [], f"{name}: missing laws {missing}"


def test_recipe_references_resolve() -> None:
    assert (REPO_ROOT / CANONICAL_RECIPES_PATH).is_file()
    assert (REPO_ROOT / "skills" / "public" / "recipes").is_dir()
    for path in _all_pack_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for ref in re.findall(r"skills/public/recipes/[\w.\-]+", text):
            assert (REPO_ROOT / ref).is_file(), f"{path.name}: {ref} does not resolve"


def test_public_skill_bodies_have_no_unavailable_internal_dependencies() -> None:
    """Every installed public body must run without repository-only helpers."""
    for path in _all_pack_files():
        if path.name != "SKILL.md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for helper in ("ats-ir-author", "ats-specify-output", "ats-assess-output"):
            assert helper not in text, f"{path.relative_to(PACK_DIR)} invokes unavailable {helper}"


# -- agent-plugins host ---------------------------------------------------------


def test_agent_plugins_manifest_fields() -> None:
    plugin = json.loads((PACK_DIR / "agent-plugins" / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["$schema"] == PLUGIN_SCHEMA_URL
    assert plugin["name"] == PLUGIN_NAME == "ats-skill-pack"
    assert re.fullmatch(r"[a-z0-9](?:[a-z0-9.\-]*[a-z0-9])?", plugin["name"])
    assert "--" not in plugin["name"] and ".." not in plugin["name"]
    assert plugin["version"] == SKILL_PACK_VERSION
    assert isinstance(plugin["description"], str) and plugin["description"]
    assert plugin["license"] == PLUGIN_LICENSE == "Apache-2.0 AND CC-BY-4.0"
    assert isinstance(plugin["keywords"], list) and all(isinstance(k, str) for k in plugin["keywords"])


def test_validator_rejects_plugin_license_without_recipe_terms(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    plugin_path = pack / "agent-plugins" / "plugin.json"
    plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
    plugin["license"] = "Apache-2.0"
    plugin_path.write_text(json.dumps(plugin), encoding="utf-8")
    findings = verify_pack(pack, REPO_ROOT)
    assert any(finding.code == "AGENT-PLUGINS-LICENSE" for finding in findings), findings

def test_agent_plugins_skills_layout() -> None:
    skills_dir = PACK_DIR / "agent-plugins" / "skills"
    assert {p.name for p in skills_dir.iterdir()} == set(REQUIRED_SKILLS)
    for name in REQUIRED_SKILLS:
        canonical = (REPO_ROOT / "skills" / "public" / name / "SKILL.md").read_bytes()
        assert (skills_dir / name / "SKILL.md").read_bytes() == canonical
    for path in (PACK_DIR / "agent-plugins").rglob("*"):
        assert not path.is_symlink()


# -- validator ------------------------------------------------------------------


def test_validator_passes_on_the_generated_pack() -> None:
    assert verify_pack(PACK_DIR, REPO_ROOT) == []


def test_validator_fails_on_a_mutated_skill_file(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    with (pack / "generic" / "ats" / "SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write("\n<!-- tampered -->\n")
    findings = verify_pack(pack, REPO_ROOT)
    codes = {f.code for f in findings}
    assert codes & {"HOST-FILE-HASH", "HOST-REGEN-DRIFT"}, findings


@pytest.mark.parametrize("notice", tuple(destination for destination, _ in HOST_NOTICE_SOURCES))
@pytest.mark.parametrize("mutation", ("missing", "tampered"))
def test_validator_fails_on_a_missing_or_tampered_host_notice(
    tmp_path: Path, notice: str, mutation: str
) -> None:
    pack = _copy_pack(tmp_path)
    path = pack / "generic" / notice
    if mutation == "missing":
        path.unlink()
    else:
        path.write_bytes(path.read_bytes() + b"\n# tampered\n")
    findings = verify_pack(pack, REPO_ROOT)
    codes = {finding.code for finding in findings}
    expected = (
        {"HOST-NOTICE-MISSING", "HOST-FILE-MISSING"}
        if mutation == "missing"
        else {"HOST-NOTICE-PARITY", "HOST-FILE-HASH"}
    )
    assert codes & expected, findings

@pytest.mark.parametrize("host,recipe_dir", tuple(HOST_RECIPE_DIRECTORIES.items()))
def test_validator_fails_on_a_missing_host_recipe(
    tmp_path: Path, host: str, recipe_dir: str
) -> None:
    pack = _copy_pack(tmp_path)
    manifest = json.loads((pack / "skill-pack-manifest.json").read_text(encoding="utf-8"))
    recipe = Path(manifest["recipes"][0]).name
    (pack / host / recipe_dir / recipe).unlink()
    findings = verify_pack(pack, REPO_ROOT)
    assert any(finding.code == "RECIPE-STANDALONE" for finding in findings), findings


@pytest.mark.parametrize("host,recipe_dir", tuple(HOST_RECIPE_DIRECTORIES.items()))
def test_validator_fails_when_host_readme_omits_recipe_layout(
    tmp_path: Path, host: str, recipe_dir: str
) -> None:
    pack = _copy_pack(tmp_path)
    readme = pack / host / "README.md"
    original = readme.read_text(encoding="utf-8")
    marker = f"`{recipe_dir}/`"
    assert marker in original
    readme.write_text(
        original.replace(marker, "`missing-layout/`"),
        encoding="utf-8",
    )
    findings = verify_pack(pack, REPO_ROOT)
    assert any(finding.code == "RECIPE-STANDALONE" for finding in findings), findings


def test_validator_rejects_recipe_symlink_that_escapes_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = _copy_pack(tmp_path)
    recipe = pack / "generic" / "recipes" / "ARTIFACT_RECIPES.md"
    outside = tmp_path / "outside-recipe.md"
    outside.write_bytes(recipe.read_bytes())
    recipe.unlink()
    recipe.symlink_to(outside)
    _forbid_symlink_content_reads(monkeypatch)

    findings = verify_pack(pack, REPO_ROOT)
    codes = {finding.code for finding in findings}
    assert {"RECIPE-STANDALONE", "HOST-SYMLINK"} <= codes, findings


def test_validator_rejects_ordinary_host_file_symlink_that_escapes_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = _copy_pack(tmp_path)
    skill = pack / "generic" / "ats" / "SKILL.md"
    outside = tmp_path / "outside-skill.md"
    outside.write_bytes(skill.read_bytes())
    skill.unlink()
    skill.symlink_to(outside)
    _forbid_symlink_content_reads(monkeypatch)

    findings = verify_pack(pack, REPO_ROOT)
    codes = {finding.code for finding in findings}
    assert "HOST-SYMLINK" in codes, findings


@pytest.mark.parametrize("absolute", (False, True), ids=("parent-traversal", "absolute"))
def test_validator_returns_finding_for_out_of_pack_manifest_path(
    tmp_path: Path, absolute: bool
) -> None:
    pack = _copy_pack(tmp_path)
    outside = tmp_path / "outside-host-file.md"
    outside.write_text("outside\n", encoding="utf-8")
    manifest_path = pack / "skill-pack-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["hosts"][0]["files"][0]["path"] = (
        str(outside) if absolute else "../outside-host-file.md"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    findings = verify_pack(pack, REPO_ROOT)
    assert any(finding.code == "HOST-PATH-ESCAPE" for finding in findings), findings



def test_validator_rejects_symlinked_manifest_without_reading_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = _copy_pack(tmp_path)
    manifest = pack / "skill-pack-manifest.json"
    outside = tmp_path / "outside-manifest.json"
    outside.write_bytes(manifest.read_bytes())
    manifest.unlink()
    manifest.symlink_to(outside)
    _forbid_symlink_content_reads(monkeypatch)

    findings = verify_pack(pack, REPO_ROOT)
    assert [finding.code for finding in findings] == ["MANIFEST-SYMLINK"], findings


def test_validator_rejects_unmanifested_top_level_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = _copy_pack(tmp_path)
    outside = tmp_path / "outside-directory"
    outside.mkdir()
    (outside / "payload.md").write_text("outside\n", encoding="utf-8")
    (pack / "unmanifested").symlink_to(outside, target_is_directory=True)
    _forbid_symlink_content_reads(monkeypatch)

    findings = verify_pack(pack, REPO_ROOT)
    assert any(finding.code == "PACK-SYMLINK" for finding in findings), findings

@pytest.mark.parametrize(
    "relative",
    ("generic/recipes/ARTIFACT_RECIPES.md", "generic/ats/SKILL.md"),
    ids=("recipe", "ordinary-host-file"),
)
def test_validator_returns_findings_for_cyclic_host_symlink(
    tmp_path: Path, relative: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = _copy_pack(tmp_path)
    path = pack / relative
    path.unlink()
    path.symlink_to(path.name)
    _forbid_symlink_content_reads(monkeypatch)

    findings = verify_pack(pack, REPO_ROOT)
    codes = {finding.code for finding in findings}
    assert "HOST-SYMLINK" in codes, findings
    if relative.endswith("ARTIFACT_RECIPES.md"):
        assert "RECIPE-STANDALONE" in codes, findings


def test_validator_fails_on_a_flipped_law_phrase(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    path = pack / "generic" / "ats" / "SKILL.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("Do not invent authority", "Invent authority freely"),
        encoding="utf-8",
    )
    findings = verify_pack(pack, REPO_ROOT)
    assert any(f.code == "LAWS-MISSING" for f in findings), findings


def test_validator_fails_on_an_injected_absolute_path(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    path = pack / "generic" / "ats" / "SKILL.md"
    injected_path = "/" + "Users/" + "galbal/" + "private/" + "notes.md"
    path.write_text(path.read_text(encoding="utf-8") + f"\n{injected_path}\n", encoding="utf-8")
    findings = verify_pack(pack, REPO_ROOT)
    assert any(f.code == "ABS-PATH" for f in findings), findings


def test_validator_fails_on_a_removed_required_skill(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    (pack / "generic" / "ats-spec" / "SKILL.md").unlink()
    findings = verify_pack(pack, REPO_ROOT)
    codes = {f.code for f in findings}
    assert codes & {"SKILLS-PACK", "HOST-FILE-MISSING"}, findings


def test_validator_fails_on_a_bad_plugin_name(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    path = pack / "agent-plugins" / "plugin.json"
    plugin = json.loads(path.read_text(encoding="utf-8"))
    plugin["name"] = "Bad-Name"
    path.write_text(json.dumps(plugin, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    findings = verify_pack(pack, REPO_ROOT)
    assert any(f.code == "AGENT-PLUGINS-NAME" for f in findings), findings


def test_validator_fails_on_a_missing_plugin_schema(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    path = pack / "agent-plugins" / "plugin.json"
    plugin = json.loads(path.read_text(encoding="utf-8"))
    del plugin["$schema"]
    path.write_text(json.dumps(plugin, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    findings = verify_pack(pack, REPO_ROOT)
    assert any(f.code == "AGENT-PLUGINS-SCHEMA" for f in findings), findings


def test_validator_fails_on_a_stale_draft1_new_authoring_default(tmp_path: Path) -> None:
    pack = _copy_pack(tmp_path)
    path = pack / "generic" / "ats" / "SKILL.md"
    text = path.read_text(encoding="utf-8").replace(
        "New durable authoring** resolves ATS-1 `1.0.0-draft.3`",
        "New durable authoring** resolves ATS-1 `1.0.0-draft.1`",
    )
    assert text != path.read_text(encoding="utf-8"), "mutation did not apply"
    path.write_text(text, encoding="utf-8")
    findings = verify_pack(pack, REPO_ROOT)
    assert any(f.code == "DRAFT1-DEFAULT" for f in findings), findings


# -- CLI -------------------------------------------------------------------------


def test_cli_skills_verify_passes_on_the_committed_pack(run_tool) -> None:
    result = run_tool("-m", "ats.cli", "skills", "verify", "--pack", "dist/skill-pack")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"
    assert payload["findings"] == []


def test_escalation_check_flags_unbounded_human_escalation() -> None:
    """Review F4: 'never' inside 'whenever' must not qualify an unguarded
    escalation sentence. Word-bounded matching keeps the §40 gate honest."""
    from ats.skill_pack import _escalation_findings

    adversarial = "Escalate to the human operator whenever REVIEW_REQUIRED appears."
    assert _escalation_findings(adversarial, "x.md") != []
    qualified = "Ask a human only when an unresolved semantic distinction blocks the requested action."
    assert _escalation_findings(qualified, "x.md") == []


def test_validator_fails_on_a_manifest_pinned_to_a_non_reproducing_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An existing commit that lacks the canonical source must fail provenance.

    The test creates an unreachable empty-tree commit in a temporary object
    directory. It therefore works in a history-free one-commit checkout without
    modifying the repository's refs or object store.
    """
    from ats.skill_pack import generate_pack, verify_pack

    objects = tmp_path / "git-objects"
    objects.mkdir()
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(objects))
    monkeypatch.setenv(
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        str(REPO_ROOT / ".git" / "objects"),
    )
    monkeypatch.setenv("GIT_AUTHOR_NAME", "ATS test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "ats-test@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "ATS test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "ats-test@example.invalid")

    empty_tree = subprocess.check_output(
        ["git", "mktree"],
        cwd=REPO_ROOT,
        input="",
        text=True,
    ).strip()
    stale_commit = subprocess.check_output(
        ["git", "commit-tree", empty_tree, "-m", "non-reproducing source"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()

    out = tmp_path / "stale-pack"
    generate_pack(
        REPO_ROOT,
        out,
        now="2026-08-07T00:00:00Z",
        source_commit=stale_commit,
    )

    findings = verify_pack(out, REPO_ROOT)
    assert "SOURCE-COMMIT" in {finding.code for finding in findings}


def test_two_default_guard_follows_current_new_authoring_edition() -> None:
    from ats.skill_pack import _stale_draft1_findings

    assert STANDARD_VERSIONS_SUPPORTED == {
        "new_authoring": "1.0.0-draft.3",
        "legacy_interpretation": "1.0.0-draft.1",
    }
    legitimate = (
        "New durable authoring resolves ATS-1 1.0.0-draft.3; "
        "legacy material stays ATS-1 1.0.0-draft.1."
    )
    stale = "New durable authoring uses ATS-1 1.0.0-draft.1."
    contradictory = (
        "New durable authoring uses ATS-1 1.0.0-draft.1; "
        "1.0.0-draft.3 is unsupported."
    )
    assert _stale_draft1_findings(legitimate, "legitimate.md") == []
    findings = _stale_draft1_findings(stale, "stale.md")
    assert [finding.code for finding in findings] == ["DRAFT1-DEFAULT"]
    contradictory_findings = _stale_draft1_findings(contradictory, "contradictory.md")
    assert [finding.code for finding in contradictory_findings] == ["DRAFT1-DEFAULT"]

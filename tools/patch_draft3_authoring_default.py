#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ats.canonical import content_hash  # noqa: E402

D2 = "1.0.0-draft.2"
D3 = "1.0.0-draft.3"


def replace_one(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}: {count}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def replace_all(path: Path, old: str, new: str, *, minimum: int = 1) -> int:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count < minimum:
        raise SystemExit(f"expected >= {minimum} matches in {path}: {count}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")
    return count


def main() -> int:
    # Two-default law: historical interpretation stays draft.1; only new authoring advances.
    spec_pkg = ROOT / "src/ats/spec_package.py"
    replace_one(spec_pkg, 'AUTHORING_SPEC_VERSION: Final[str] = "1.0.0-draft.2"', 'AUTHORING_SPEC_VERSION: Final[str] = "1.0.0-draft.3"')
    text = spec_pkg.read_text(encoding="utf-8")
    text = text.replace("An old artifact must never acquire\n#: draft.2 semantics merely because the fleet advanced.", "An old artifact must never acquire\n#: newer-edition semantics merely because the fleet advanced.")
    text = text.replace("policy whose declared spec_version is draft.2)\n#: resolves draft.2 automatically", "policy whose declared spec_version is draft.3)\n#: resolves draft.3 automatically")
    spec_pkg.write_text(text, encoding="utf-8")

    cli = ROOT / "src/ats/cli.py"
    text = cli.read_text(encoding="utf-8")
    text = text.replace("authoring under the fleet policy resolves draft.2 automatically;", "authoring under the fleet policy resolves draft.3 automatically;")
    cli.write_text(text, encoding="utf-8")

    fleet = ROOT / "src/ats/fleet.py"
    text = fleet.read_text(encoding="utf-8")
    text = text.replace("The checked-in default is a host-neutral public draft.2 authoring policy;", "The checked-in default is a host-neutral public draft.3 authoring policy;")
    text = text.replace("#: Host-neutral public draft.2 policy used when no --policy is given.", "#: Host-neutral public draft.3 policy used when no --policy is given.")
    fleet.write_text(text, encoding="utf-8")

    # Content-addressed fleet policy.
    policy_path = ROOT / "config/policies/fleet_policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy["text_policy"]["version"] != D2:
        raise SystemExit(f"unexpected fleet policy version: {policy['text_policy']['version']}")
    policy["text_policy"]["version"] = D3
    policy["policy_id"] = content_hash(policy, exclude={"policy_id"})
    policy_path.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Public runtime documentation: available editions and new-authoring default.
    readme = ROOT / "README.md"
    replace_one(readme, "ATS-1 `1.0.0-draft.2`, the result stays readable as prose", "ATS-1 `1.0.0-draft.3`, the result stays readable as prose")
    replace_one(readme, "`ats spec status` should list both `1.0.0-draft.1` and\n`1.0.0-draft.2`.", "`ats spec status` should list `1.0.0-draft.1`, `1.0.0-draft.2`, and\n`1.0.0-draft.3`.")

    # Public skill pack canonical source. Replace only the current-default language;
    # historical interpretation remains draft.1. The four skills are version-policy surfaces.
    public_skills = [
        ROOT / "skills/public/ats/SKILL.md",
        ROOT / "skills/public/ats-spec/SKILL.md",
        ROOT / "skills/public/ats-assess/SKILL.md",
        ROOT / "skills/public/ats-review/SKILL.md",
    ]
    for path in public_skills:
        replace_all(path, "draft.2", "draft.3", minimum=1)

    # D-G needs to survive into the authoring skill, not merely change an edition label.
    spec_skill = ROOT / "skills/public/ats-spec/SKILL.md"
    replace_one(
        spec_skill,
        "- acceptance criteria — falsifiable evidence obligations;",
        "- acceptance criteria — canonical falsifiable behavioral propositions; tests, probes, proofs, and receipts are evidence used to adjudicate them, not the criteria themselves;",
    )
    replace_one(
        spec_skill,
        "The requirement declares the desired invariant; the acceptance converts it into a\nfalsifiable evidence obligation. Do not \"fix\" the overlap by deleting either side.",
        "The requirement declares the desired invariant; the acceptance states the canonical\nfalsifiable behavioral proposition. Tests, probes, proofs, or receipts are subordinate\nevidence used to adjudicate that proposition. Do not \"fix\" the overlap by deleting either side.\n\nFor each normative REQ/AC pair, ask one adversarial question: **could a materially broken\nimplementation satisfy this AC as written?** If yes, strengthen the AC or decompose the REQ.\nThe AC must not compensate by adding an independent obligation, widening scope, or strengthening\ndeontic force; normative behavior belongs in the REQ.",
    )

    front = ROOT / "skills/public/ats/SKILL.md"
    replace_one(
        front,
        "9. Acceptance evidence is not the same discourse role as the requirement it verifies.",
        "9. Acceptance criteria state falsifiable behavior; tests, probes, proofs, and receipts are evidence used to adjudicate them, not substitutes for the criterion.",
    )

    # Version-law regression tests.
    tests = ROOT / "tests/unit/test_cli_spec_defaults.py"
    text = tests.read_text(encoding="utf-8")
    text = text.replace("pins — draft.2 for the fleet policy", "pins — draft.3 for the fleet policy")
    text = text.replace("test_the_authoring_default_is_draft2", "test_the_authoring_default_is_draft3")
    text = text.replace('assert AUTHORING_SPEC_VERSION == "1.0.0-draft.2"', 'assert AUTHORING_SPEC_VERSION == "1.0.0-draft.3"')
    text = text.replace("test_the_fleet_policy_pins_draft2_for_new_authoring", "test_the_fleet_policy_pins_draft3_for_new_authoring")
    old = '''    ctx = _context(_args(policy="config/policies/fleet_policy.json"))\n    assert ctx.spec_version == "1.0.0-draft.2"\n    assert len(ctx.registry.ids()) == 36'''
    new = '''    ctx = _context(_args(policy="config/policies/fleet_policy.json"))\n    assert ctx.spec_version == "1.0.0-draft.3"\n    assert len(ctx.registry.ids()) == 37\n    assert "ATS-REQ-004" in ctx.registry.ids()'''
    if text.count(old) != 1:
        raise SystemExit(f"fleet policy test anchor count: {text.count(old)}")
    text = text.replace(old, new, 1)
    tests.write_text(text, encoding="utf-8")

    # The canonical public skill bytes change, so this is the next skill-pack candidate.
    init = ROOT / "src/ats/__init__.py"
    replace_one(init, 'SKILL_PACK_VERSION = "0.1.3"', 'SKILL_PACK_VERSION = "0.1.4"')

    changelog = ROOT / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    marker = "## [Unreleased]\n"
    addition = """## [Unreleased]\n\n### Changed — draft.3 authoring cutover candidate\n\n- New durable authoring and the checked-in fleet policy now resolve ATS-1 `1.0.0-draft.3`; legacy unlabeled interpretation remains draft.1 and explicit version pins still win.\n- Public authoring/review skills carry the draft.3 version law and D-G behavioral acceptance-criterion boundary.\n- Canonical public skill bytes changed, so the generated skill-pack candidate advances to `0.1.4`; the published release remains `0.1.3` until separately tagged/released.\n"""
    if addition not in text:
        if text.count(marker) != 1:
            raise SystemExit(f"changelog unreleased anchor count: {text.count(marker)}")
        changelog.write_text(text.replace(marker, addition, 1), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

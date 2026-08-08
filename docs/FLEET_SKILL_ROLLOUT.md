# ATS Skill Pack — Fleet Rollout and Vendor Contract

This document is the vendor contract for fleet repositories consuming the ATS
public skill pack. It answers the ten fleet questions concretely: what is
vendored, what is generated, how versions and policy are pinned, how upgrades
and drift are handled, how ATS is removed, how legacy draft.1 material is
treated, and what an agent actually invokes.

Related documents:

- `docs/SKILL_PACK_NORTH_STAR.md` — the program's north star (one canonical
  surface, OSS + fleet).
- `docs/SKILL_PACKAGING.md` — canonical source, host generation, manifest,
  verification, and the upgrade mechanism the fleet re-vendors from.
- `docs/OSS_SKILL_PACK.md` — install/use/upgrade for a standalone user.
- `docs/decisions/ADR-0020` (two-default version law) and
  `docs/decisions/ADR-0023` (public skill-pack architecture).

## 1. What the fleet vendors, and what it does not

**Every fleet repository vendors the same OSS surface.** There is one canonical
`ats-spec`, `ats-assess`, `ats-review` — and the fleet consumes the generated
pack, not a fork and not a private dialect. The ATS repository does not mutate
fleet repositories; its responsibility is a deterministic, documented vendoring
surface. Vendoring is a copy step in each fleet repo, performed against the
committed pack baseline.

Two vendoring forms are supported, both byte-identical in skill content:

- **`dist/skill-pack/generic/`** — the canonical plain-markdown form. Skills
  keep their YAML frontmatter (`name`, `description`) and their full bodies;
  the shared recipes live in `recipes/`. This is the default fleet form: it
  works in any host that reads markdown skills and it is the form the verifier
  treats as canonical (`generic/<name>/SKILL.md` must be byte-identical to
  `skills/public/<name>/SKILL.md`).
- **`dist/skill-pack/agent-plugins/`** — a portable Agent Plugins root
  (`plugin.json` + `skills/<name>/SKILL.md`, agent-plugins.org schema 1.0.0)
  for clients that discover Agent Plugins natively.

Either way the fleet vendors the **exact OSS surface**: the same skill
identity, the same ten-law mini-constitution, the same recipes, the same
version behavior, the same invocation semantics. The only difference between
host forms is layout/transport, never content.

What is vendored (per fleet repo):

```text
<fleet-repo>/
├── .ats-skill-pack/                 # vendored pack (any name; see §3 for the pin)
│   ├── generic/…                    # or agent-plugins/…
│   └── skill-pack-manifest.json     # the pin record (see §2, §3)
└── <repo guidance file>             # AGENTS.md / CONTRIBUTING.md / policy ref (§5)
```

What is **not** vendored:

- The internal compiler skills (`ats-ir-author`, `ats-specify-output`,
  `ats-assess-output`) remain repository-only development artifacts. The four
  public skills are self-contained and do not invoke or require them.
- The `ats` CLI or its runtime. The skills invoke `ats …` commands when a
  fleet repo has the CLI installed; the pack itself carries no code.
- The packager (`tools/generate_skill_pack.py`) or the canonical source tree.
  Those stay in the ATS repository; fleet repos consume generated output.

## 2. Generated vs. canonical — what to never hand-edit

The canonical source of the pack lives in the ATS repository:

```text
skills/public/ats/SKILL.md
skills/public/ats-spec/SKILL.md
skills/public/ats-assess/SKILL.md
skills/public/ats-review/SKILL.md
skills/public/recipes/               # architecture, diagnostic, implementation_program,
                                     # postmortem, rfc_technical_proposal
docs/ARTIFACT_RECIPES.md             # canonical recipes document
```

Everything under `dist/skill-pack/` — all four host forms plus
`skill-pack-manifest.json` — is **generated** by `tools/generate_skill_pack.py`
from that canonical source. Consequences for the fleet:

- Vendored skill files are copies of generated output. Never edit them in the
  fleet repo by hand; an edit there is drift, detected by the verifier, and is
  lost on the next re-vendor.
- The ATS repository commits the generated baseline (`dist/skill-pack/`), so
  fleet repos pin to an ATS source commit or release and copy from it.

## 3. How the ATS version is pinned

The pack carries **three version strings, never collapsed** (§38); the
manifest is the pin record:

| String | Manifest field | Current value | Means |
|---|---|---|---|
| ATS-1 standard | `standard_versions_supported` | `new_authoring: 1.0.0-draft.2` / `legacy_interpretation: 1.0.0-draft.1` | normative edition(s) the skills resolve |
| ATS implementation | `implementation_version` | `0.5.0` | the runtime/CLI the skills invoke |
| ATS skill pack | `skill_pack_version` | `0.1.2` candidate | the public skill surface + packaging |

A fleet repo pins by vendoring `skill-pack-manifest.json` alongside the host
form and recording, in its vendor note or commit message:

```text
ATS skill pack 0.1.2 · implementation 0.5.0 · ATS-1 1.0.0-draft.2 (new) / 1.0.0-draft.1 (legacy)
source_commit:       <canonical source commit used before generation>
canonical_source_sha256: <generated from that source>
```

Release `0.1.1` remains published from the history-free public repository under
the signed annotated tag `v0.1.1-skill-pack`. Candidate `0.1.2` repairs
standalone recipe lookup and will receive a new tag only after its own gates
pass; vendoring instructions never create or move release tags.

`source_commit` and `canonical_source_sha256` are the reproducibility anchors:
the same source commit regenerates the identical pack (deterministic packager,
SKILL_PACKAGING §2), and the tree hash detects any canonical-source change
without trusting copy history. Pin both, and the standard edition is pinned
too: the manifest's `standard_versions_supported` is a hard check in
`ats skills verify` (finding code `STANDARD-VERSIONS`), so a vendored pack that
stops resolving draft.2 for new authoring fails verification, never silently
downgrades.

## 4. How policy is resolved

New durable authoring resolves **ATS-1 `1.0.0-draft.2`** under the binding
policy (ADR-0020 two-default law). The fleet policy document lives in the ATS
repository at `config/policies/fleet_policy.json` (`ats.fleet_policy.v1`):

- `text_policy.version = "1.0.0-draft.2"` — the edition new authoring resolves.
- `text_policy.required_for` — the artifact classes ATS applies to:
  architecture, technical_proposal, rfc, implementation_spec,
  capability_program, implementation_plan, postmortem, diagnostic,
  forensic_analysis, technical_assessment, acceptance_record,
  change_control_record.
- `default_exclusions` — scratch_notes, exploratory_chat, brainstorming,
  blog_posts, marketing_copy, README_marketing, ordinary_issue_comments,
  casual_explanation, social_copy: ATS does **not** apply mechanically to these.
- `repository_overrides` — an optional per-repo adjustment mechanism in the
  policy schema (added `required_for` classes, removals, enforcement changes;
  the parser defaults it to empty). The **public default policy is
  host-neutral**: `config/policies/fleet_policy.json` ships with **no
  repository overrides at all** — no private fleet special-casing is encoded
  in the public runtime. A private fleet repo that wants repository-specific
  adjustments supplies its own policy document explicitly (see below).

Resolution is explicit and per artifact class. In a fleet environment the
front-door skill runs:

```bash
ats policy resolve <artifact-class>          # e.g. implementation_spec
ats policy resolve <artifact-class> --repo <repo>   # applies overrides when the policy document has them
ats policy resolve <artifact-class> --policy <custom-policy.json>   # private fleet policy
```

The output is JSON (`{"applicable": true, "spec_version": "1.0.0-draft.2",
"enforcement": …, "failure_policy": …, "policy_id": …, "basis": "text_policy"}`).
The `--repo` flag is a mechanism note: it applies `repository_overrides` only
when the resolved policy document actually contains the key; the shipped
default contains none. A private fleet repo that wants repository-specific
behavior resolves against its own policy document (`--policy`) rather than the
public default. A class outside `required_for` is out of scope: the skill says
so and does not half-apply ATS. Explicit `--spec-version` always wins; a
draft.2 artifact under a draft.1 policy is a refusal, never a silent
downgrade.

## 5. Repository guidance the fleet adds

Each fleet repo adds the canonical fleet guidance block where its agents read
instructions (AGENTS.md or equivalent) plus a pointer to the vendored skills.
The block is copied verbatim:

```markdown
Use ATS for new architecture, specification, technical proposal, implementation-program, diagnostic, postmortem, and technical-assessment artifacts. New durable authoring uses ATS-1 1.0.0-draft.2 under fleet policy. Do not apply ATS mechanically to scratch notes, exploratory discussion, marketing prose, or casual explanations.
```

Repo guidance must not contradict the vendored skills: no private ATS dialect,
no second set of "ATS rules" in the repo, no instruction that changes the
version behavior (e.g. telling agents to author new material under draft.1).
The skill is the contract; the repo guidance names *when* ATS applies, it does
not redefine *what* ATS is.

## 6. The ten answers (§50)

### 6.1 What files are vendored

The chosen host form — `dist/skill-pack/generic/**` (four skill directories,
each with `SKILL.md`, plus `recipes/` with `ARTIFACT_RECIPES.md` and the five
recipe summaries, plus `README.md`) or the `agent-plugins/` form
(`plugin.json`, `skills/ats|ats-spec|ats-assess|ats-review/SKILL.md`,
`README.md`) — together with `skill-pack-manifest.json` as the pin record.

### 6.2 Which files are generated

All of them. Every file under `dist/skill-pack/` is produced deterministically
by `tools/generate_skill_pack.py` from `skills/public/**` plus
`docs/ARTIFACT_RECIPES.md`. Fleet repos copy generated output; they never
generate it themselves and never hand-edit it. The canonical source lives only
in the ATS repository.

### 6.3 How the ATS version is pinned

By vendoring the manifest and recording its identity fields — `skill_pack_version`
(`0.1.2` candidate), `implementation_version` (`0.5.0`), `standard_versions_supported`
(`1.0.0-draft.2` new authoring / `1.0.0-draft.1` legacy), plus
`source_commit` and `canonical_source_sha256` (§3). `ats skills verify`
enforces the version fields, so a stale or downgraded pack fails loudly.

### 6.4 How policy is resolved

Per artifact class, via `ats policy resolve <artifact-class> [--repo <repo>]`
against the fleet policy (`config/policies/fleet_policy.json`), which pins
draft.2 for new durable authoring (ADR-0020). The public default is
host-neutral (no repository overrides); private fleet repos may resolve
against their own policy document with `--policy`. Explicit `--spec-version`
wins; no silent downgrade of draft.2 artifacts (§4).

### 6.5 What repository guidance is added

The canonical fleet guidance block (§5) in the repo's agent-facing guidance
file, plus a pointer to the vendored skill directory. Nothing that redefines
the skills' contracts.

### 6.6 How upgrades are performed

Re-vendor from a new ATS pack baseline:

1. Regenerate/verify the pack in the ATS repository (SKILL_PACKAGING §6–§8):
   `ats skills verify --pack dist/skill-pack` must PASS.
2. Copy the new `generic/` (or `agent-plugins/`) host form and the new
   `skill-pack-manifest.json` into the fleet repo, replacing the old vendored
   tree.
3. Update the vendor note with the new `skill_pack_version`,
   `source_commit`, and `canonical_source_sha256`.
4. Re-run the fleet-side drift check (§6.7) and land the vendored copy as a
   normal change.

There is no copy-paste archaeology: the pack is a pure function of its
canonical source, so an upgrade is a byte-exact replace, and any residue from
the previous version is removed by replacing the whole vendored directory.

### 6.7 How drift is detected

Two layers:

- **In the ATS repository / on release:** `ats skills verify --pack dist/skill-pack`
  recomputes the canonical tree hash, re-checks every host file's SHA-256
  against the manifest, and regenerates the pack in a temp dir and diffs trees.
  Any drift is a typed finding (`TREE-HASH`, `HOST-FILE-HASH`, `HOST-PARITY`,
  `HOST-REGEN-DRIFT`, …) and a non-zero exit.
- **In a fleet repo:** compare the vendored files against the manifest's
  per-file SHA-256s (`hosts[].files[].sha256`) and the manifest's
  `canonical_source_sha256` against the tree hash recorded at pin time.
  A mismatch means someone edited a vendored file, the pack was swapped
  without updating the pin, or the canonical source changed — treat it as
  drift, not as a local improvement.

Run the fleet-side comparison in CI: fail the change that introduces drift.

### 6.8 How ATS is removed/disabled

Delete the vendored skill directory and the policy reference:

1. Remove the vendored pack directory (e.g. `.ats-skill-pack/`) from the fleet
   repo.
2. Remove the fleet guidance block (§5) from the repo's guidance file.
3. Drop any CI check that referenced the pack or ran `ats skills verify`.
4. Leave no residue: no dangling pointers to the vendored paths, no stale
   guidance telling agents to "use ATS", no half-vendored skill directories.

There is no deactivation flag and no partial state; a fleet repo either
vendors the pack with its pin or it does not. The ATS repository needs no
changes for a fleet repo to exit — the ATS repo never mutated fleet repos in
the first place (§21).

### 6.9 How old draft.1 artifacts are handled

Legacy/historical material stays **`1.0.0-draft.1`** (legacy interpretation),
the default for corpus reads and unlabeled historical material (ADR-0020).
Draft.1 artifacts are never silently migrated to draft.2 and never
re-interpreted under draft.2 semantics; receipts keep their bound
`spec_version` identity forever. Migration is explicit only: a user requests
conversion, and the result is a new draft.2 artifact checked under draft.2.
A draft.2 artifact under a draft.1 policy is refused, never downgraded. The
skills encode this: legacy input routes `1.0.0-draft.1 (historical material;
no explicit migration)` and reports the edition honestly.

### 6.10 What an agent actually types/invokes

One skill name: **`ats`** — the front door. An agent in a fleet repo invokes it
by name in its host (Claude Code skill `ats`, Codex guidance under the `ats`
heading, Agent Plugin skill `ats`, or plain markdown), and the front door
routes: new authoring → transformation → review, ASSESS/SPECIFY/composition,
the artifact recipe, and the standard version. The deterministic machinery the
skill runs before reporting success:

```bash
ats policy resolve <artifact-class>      # applicability + edition (fleet)
ats ir lint <artifact>.ir.json --policy <policy>
ats output lint <artifact>.md --trace <artifact>.trace.json --ir <artifact>.ir.json --policy <policy>
ats output verify-receipt <artifact>.receipt.json
```

The CLI is the authority for conformance; the skill is not. Agents do not need
ATS internals (TextIR, basis records, lint reports) in ordinary prose — those
stay available as machine records.

## 7. Tribunal: the future native producer

Tribunal remains outside this public vendoring contract. The fleet consumes
the same ATS artifacts and does not maintain a private dialect.

- Tribunal consumes the **same** ATS artifacts — the same skill pack, the same
  standard editions, the same receipts — with **no forked dialect** (law 12).
  When Tribunal becomes the authoring surface, it vendors/pins the ATS package
  version and authoring skills like any other fleet repo.
- The ATS repository does not own or mutate Tribunal/vx in this program; the
  vendoring contract is identical to arq/sear/vx/moat/tribunal today.

## 8. Vendoring mechanics, restated

```text
ATS repository (owns canonical source + packager)
  skills/public/** + docs/ARTIFACT_RECIPES.md
        │  tools/generate_skill_pack.py   (deterministic, pinned now + commit)
        ▼
  dist/skill-pack/  (generic | claude | codex | agent-plugins + manifest)
        │  ats skills verify  → PASS, zero diff (baseline regenerated at a verified public source commit)
        ▼
fleet repositories
  vendor generic/ (or agent-plugins/) + manifest; record pin; add §5 guidance
  drift check in CI: per-file SHA-256 vs manifest
```

The ATS repository's contract is deterministic + documented vendoring (§21):
it never pushes into fleet repos. Fleet repos contract is byte-exact vendoring
of the same surface, with a pin and a drift check. Neither side forks.

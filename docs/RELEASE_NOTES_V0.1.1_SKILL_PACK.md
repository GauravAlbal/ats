# ATS Skill Pack 0.1.1

**Status:** released as SSH-signed annotated tag `v0.1.1-skill-pack`.

These notes describe the public `0.1.1` skill-pack release. The exact tagged
candidate passed hosted `public-gate` run
[`31270694983`](https://github.com/GauravAlbal/ats/actions/runs/31270694983)
and the fresh-clone full gate before the tag was created.

## Purpose

ATS-1 is a technical discourse standard for AI-generated and AI-consumed
engineering artifacts. It keeps distinctions such as observation versus
inference, normative force, scope, evidence, authority, uncertainty, and
stable semantic coordinates recoverable in ordinary prose.

The skill pack is the practical interface to ATS-1. It provides local,
deterministic guidance and checks; it is not a hosted service or a promise of
universal semantic acceptance.

## User-visible changes

The release provides four public skills:

- `ats` — choose an ATS mode and route a request;
- `ats-spec` — author implementation-relevant specifications and proposals;
- `ats-assess` — produce bounded technical assessments and diagnostics; and
- `ats-review` — review an artifact for semantic preservation and typed
  findings.

It also provides recipes and deterministic host forms for:

- `generic/` — host-neutral Markdown skills;
- `claude/` — Claude Code skills and references;
- `codex/` — Markdown skills with placement guidance; and
- `agent-plugins/` — an Agent Plugins root using schema `1.0.0`.

The local CLI reports typed findings and receipts, validates ATS artifacts and
policies, and verifies that a generated skill pack matches its canonical
source.

## Version law

The three version identities are independent:

| Identity | Version | Meaning |
| --- | --- | --- |
| ATS-1 standard | `1.0.0-draft.2` / `1.0.0-draft.1` | Draft.2 is the edition for new durable authoring; draft.1 is the interpretation for historical unlabeled material. |
| ATS implementation | `0.5.0` | The local Python runtime and CLI. |
| ATS skill pack | `0.1.1` | The four skills, recipes, generated host forms, and manifest. |

Draft.2 is not a final standard. Historical unlabeled material remains
draft.1 unless it is explicitly migrated. The runtime and skills do not
silently downgrade draft.2 or add draft.2 semantics to draft.1 material.

## Install, host, and verify

From a checkout, use Python 3.12 or newer:

```bash
git clone https://github.com/gauravalbal/ats.git
cd ats
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --editable .
```

Validate the standard package and generated pack with the installed CLI:

```bash
ats spec validate
ats skills verify --pack dist/skill-pack
ats spec status
```

Choose one generated host form under `dist/skill-pack/`. For a host-neutral
installation, the documented copy is:

```bash
PACK=dist/skill-pack/generic
DEST="$PWD/.ats-skills"
mkdir -p "$DEST"
cp -R "$PACK/ats" "$PACK/ats-spec" "$PACK/ats-assess" "$PACK/ats-review" "$DEST/"
cp -R "$PACK/recipes" "$DEST/"
```

For Claude, Codex, or Agent Plugins, copy the same four skill folders and
recipes from the corresponding generated host directory, following that
form's README and the host's skill-directory rules.

To regenerate the pack from canonical source and then verify it:

```bash
python tools/generate_skill_pack.py
ats spec validate
ats skills verify --pack dist/skill-pack
```

Verification checks the manifest, supported standard versions, required
skills, canonical tree hash, per-file hashes, host parity, references, and
deterministic regeneration. A clean result is evidence only for those
declared checks, not universal correctness.

## Licensing boundary

- **Apache-2.0:** software, public skills, packaging machinery, schemas, and
  other software or machine-readable assets in the software scope.
- **CC-BY-4.0:** ATS-1 normative material and repository-authored
documentation and recipes.

Generated host forms have a mixed scope map: host machinery, skill copies,
plugin metadata, and manifests follow the software scope, while copied
normative, reference, and host documentation follows the documentation scope.
Use the applicable notices with each host form when redistributing it.

## Provenance and regeneration

Canonical public skill source and the artifact recipes are the inputs to
`tools/generate_skill_pack.py`. The generator produces all four host forms and
`skill-pack-manifest.json`; generated files are not hand-maintained.

The manifest records the pack version, supported ATS-1 editions,
implementation version, source provenance, canonical tree hash, and per-file
SHA-256 digests. Regenerate from one canonical source state, then run
`ats skills verify`; hand-editing generated output or mixing generations should
fail verification.

The public repository uses a history-free lineage: P0 contains canonical
source, P1 adds only regenerated `dist/skill-pack/` output, and the signed
annotated release tag points to P1.

## Compatibility and upgrades

Use a generated host form as a matched tree: do not edit individual generated
skill files. When upgrading, regenerate and verify the new pack, then replace
the prior host form and manifest together. Keep the standard edition attached
to each artifact: new durable authoring uses draft.2, while historical
unlabeled interpretation remains draft.1.

The build backend is pinned to Hatchling `1.31.0`. The pack requires no hosted
service, account, or host-specific API; host placement remains the
responsibility of the consuming agent environment.

## Release state

Release `0.1.1` is published from the verified public source state under
`v0.1.1-skill-pack`. The release assets include source and standalone
skill-pack archives plus SHA-256 checksums.

Verify the SSH signature with the repository-bound signer record:

```bash
git -c gpg.ssh.allowedSignersFile=.github/allowed_signers \
  tag -v v0.1.1-skill-pack
```

GitHub currently reports `unknown_key` for provider-side attribution because
the SSH key is not registered with the account as a signing key. The committed
allowed-signers record, not the provider badge, is this release's public trust
anchor.

See `docs/OSS_SKILL_PACK.md`, `docs/SKILL_PACKAGING.md`, and `docs/STABILITY.md`
for the standalone walkthrough, regeneration contract, and version rules.

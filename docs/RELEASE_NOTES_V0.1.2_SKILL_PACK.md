# ATS Skill Pack 0.1.2

**Status:** release candidate. A distinct SSH-signed annotated tag
`v0.1.2-skill-pack` is created only after the exact generated candidate passes
hosted CI and the fresh-clone publication gate.

## Why this patch exists

Release `0.1.1` packaged the canonical recipes in every host, but its public
skills named only repository-source paths such as `docs/ARTIFACT_RECIPES.md`
and `skills/public/recipes/`. Generated hosts place those same canonical bytes
under host-local directories instead:

- generic and Codex: `recipes/`;
- Claude and Agent Plugins: `references/`.

The `0.1.1` verifier checked the source-tree paths against the repository root.
That allowed repository files to mask a broken standalone lookup. The skill
procedures themselves remained usable and the recipe bytes were present, but a
recipe-guided invocation could follow a path that did not exist in an extracted
standalone host. This is a release defect, not a standard change.

## Correction

`0.1.2` makes the boundary explicit and mechanically checked:

1. Canonical public skills identify source-tree paths as provenance and name
   both generated host-local layouts.
2. Recipe summaries carry the same source-versus-installed distinction.
3. Generation still copies from one canonical recipe source; generated prose is
   never hand-maintained.
4. `ats skills verify` resolves every manifest-declared recipe basename inside
   every generated host using its declared layout, rejects missing or
   out-of-pack targets, and rejects symlinks anywhere in a generated host.
5. An isolated-pack capstone copies the pack into an empty temporary directory
   and proves repository-only files cannot satisfy standalone references.

Host mapping:

| Host | Installed recipe directory |
|---|---|
| `generic` | `recipes/` |
| `codex` | `recipes/` |
| `claude` | `references/` |
| `agent-plugins` | `references/` |

## Version identity

The three version domains remain separate:

| Domain | Version | Meaning |
|---|---|---|
| ATS-1 standard | `1.0.0-draft.2` new authoring / `1.0.0-draft.1` legacy interpretation | Normative artifact semantics |
| ATS implementation | `0.5.0` | Runtime and CLI |
| ATS skill pack | `0.1.2` | Skills, recipes, generated hosts, and manifest |

The patch does not alter ATS-1 normative text, the implementation version, or
the two-default law. New durable authoring remains draft.2; historical unlabeled
material remains draft.1 unless explicitly migrated.

## Upgrade

Replace the entire previous generated host form with the matching `0.1.2` host
form and retain its manifest. Do not copy individual changed files across
versions. From a matching source checkout, run:

```bash
ats skills verify --repo . --pack dist/skill-pack
```

For the standalone release archive, verify the archive against the release's
`SHA256SUMS`; full canonical-parity verification additionally requires the
matching source checkout. The archive contains all four host forms. Use the
containing host README to select placement and the correct recipe directory.

## `0.1.1` preservation

The published `v0.1.1-skill-pack` tag, its source archive, standalone archive,
and `SHA256SUMS` remain historical release evidence and are not rewritten.
Verify its SSH signature independently with:

```bash
git -c gpg.ssh.allowedSignersFile=.github/allowed_signers \
  tag -v v0.1.1-skill-pack
```

GitHub reports `unknown_key` for provider-side attribution because the SSH key
is not registered with the account as a signing key. The repository-bound
`.github/allowed_signers` file is the public trust anchor; the project does not
claim a provider-verified badge.

## Candidate gate

Before `v0.1.2-skill-pack` is created, the exact generated candidate must pass:

- repository validation;
- the complete test suite and standalone isolated-pack capstone;
- CLI smoke checks;
- both ATS-1 normative package validators;
- `ats skills verify` and fixed-provenance zero-diff regeneration;
- hosted `public-gate`; and
- a fresh-clone repetition of the full publication gate.

After those checks, the release will carry a new source archive, standalone
skill-pack archive, and `SHA256SUMS`. The tag will point to the generated-pack
commit. GitHub ruleset `Immutable release tags` permits its initial creation
and blocks later updates or deletion for `refs/tags/v*`.

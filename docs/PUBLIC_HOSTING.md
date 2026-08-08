# Public hosting

This document records the hosting contract for the public ATS repository at
[`gauravalbal/ats`](https://github.com/gauravalbal/ats).

## Publication status

The selected licensing split is recorded in
[`PUBLICATION_LICENSING.md`](PUBLICATION_LICENSING.md): Apache-2.0 covers the
implementation, public skills, repository-local schemas and machine-readable
assets, tools, tests, and generated assets; CC-BY-4.0 covers ATS-1 normative
text/package material and repository-authored documentation. Skill-pack version
`0.1.2` is the current release under the SSH-signed annotated tag
`v0.1.2-skill-pack`; release `0.1.1` remains available as the previous release.

## Current release facts

These facts are recorded from the repository and hosting provider:

- The default branch is `master`.
- The Python implementation version is `0.5.0` (`pyproject.toml`).
- The current public skill-pack release is `0.1.2`; its generated manifest
  records canonical source commit and tree hash.
- Canonical source is committed before generated `dist/skill-pack/` output.
- New durable authoring uses ATS-1 `1.0.0-draft.2`; historical unlabeled material remains ATS-1 `1.0.0-draft.1` unless explicitly migrated.
- The public workflow at `.github/workflows/public-ci.yml` is named `Public
  publication gate`; its job and required status-check context are
  `public-gate`.
- Hosted runs use Python `3.12`, isolated runner directories, public editable
  installation, repository validation, skill-pack verification, CLI smoke
  checks, focused provenance/regeneration/private-dependency tests, and the
  public capstone.
- The generated pack's integrity contract is
  `ats skills verify --pack dist/skill-pack`.


## Hosting posture

### Default branch

`master` is the hosted repository's default branch. If the name changes, update
the hosting configuration and links in one deliberate change; do not maintain
two competing default branches.

### Branch protection and CI

The default branch is protected with these provider-side controls:

- successful `public-gate` status is required against the current branch;
- linear history and resolved review conversations are required;
- force pushes and branch deletion are disabled; and
- external contributions arrive through pull requests. The repository owner
  retains the provider's administrative bypass for release and hosting
  maintenance; no fixed approval count is asserted here.

The public workflow defines these verification steps:

```bash
python tools/validate_repo.py
python -m ats.cli skills verify --pack dist/skill-pack
python tools/smoke_cli.py
python -m pytest -q tests/unit/test_skill_pack.py tests/unit/test_publication_gate.py
python -m pytest -q tests/capstone/test_oss_skill_pack.py
```

The required provider status is the observed `public-gate` job from the
`Public publication gate` workflow. The active `master` workflow pins GitHub
Actions to full commit SHAs, synchronizes dependencies from committed `uv.lock`,
and uses isolated runner directories. It remains independent of sibling
checkouts, private credentials, operator home directories, and private services.

### Issues and pull requests

Public issues and pull requests are enabled. The templates in `.github/` are
intentionally small:

- `ISSUE_TEMPLATE/bug_report.md` requests a reproducible report, versions, host
  form, and privacy-safe evidence;
- `ISSUE_TEMPLATE/feature_request.md` asks for the user problem and semantic
  boundary; and
- `pull_request_template.md` asks contributors to record behavior, checks,
  version-law impact, and disclosure/provenance review.

Do not put credentials, private corpus, private infrastructure details, or
sensitive artifacts in a public issue or pull request. Security reports use the
private route in `SECURITY.md`, not a public issue.

### Security reporting and release identity

GitHub private vulnerability reporting is enabled at
<https://github.com/GauravAlbal/ats/security/advisories/new>. Secret scanning,
push protection, and Dependabot security updates are enabled. `SECURITY.md`
defines report scope and safe submission guidance; public issues are not a
vulnerability-reporting route.

The standard, implementation, and skill pack remain separate release
identities:

- ATS-1 standard: `1.0.0-draft.2` for new authoring and
  `1.0.0-draft.1` for legacy interpretation;
- implementation: `0.5.0`; and
- skill pack: current release `0.1.2` is `v0.1.2-skill-pack`; previous release
  `0.1.1` remains available as `v0.1.1-skill-pack`.

The release tag targets the generated-pack commit. The release carries a source
archive, a standalone `dist/skill-pack/` archive, and `SHA256SUMS`. The pack
manifest retains its canonical source commit, tree hash, per-file hashes, and
supported-standard declarations.

### Repository description and topics

The repository description is:

> ATS-1 technical writing standard and public skill pack for
> implementation-bearing AI handoffs

The configured topics are:

- `ats`
- `technical-writing`
- `technical-documentation`
- `ai-agents`
- `semantic-preservation`
- `python`

Topics are discoverability metadata, not compatibility claims. They do not
imply a hosted service, private integration, or support guarantee.

## `0.1.2` publication completion record

The `v0.1.2-skill-pack` cutover completed in this order:

1. P0 `b22d168013b5d287eaced9fb502f84ab6bce6b61` committed the canonical
   portable host-recipe mapping, verifier hardening, and release documentation.
2. P1 `5329397b1ce5725616e9e6261fe29307967434b2` changed only generated
   `dist/skill-pack/` files. Its manifest binds P0 and canonical source hash
   `32e91bf969f8a401fcdb18679e542e7a79de842850374a81c173f33f91d65d47`.
3. The exact P1 candidate passed pull-request `public-gate` run
   [`31275270984`](https://github.com/GauravAlbal/ats/actions/runs/31275270984)
   and master-push run
   [`31275426278`](https://github.com/GauravAlbal/ats/actions/runs/31275426278).
4. Before tagging, a fresh clone at P1 passed `uv sync --frozen`, the complete
   test suite, repository and CLI validation, both normative package
   validators, `ats skills verify`, and the isolated standalone-pack capstone.
5. Independent code and security reviews found no remaining BLOCK or
   REVIEW_REQUIRED issue on exact P1.
6. The SSH-signed annotated tag was created at P1. The GitHub release carries a
   source archive, standalone pack archive, and `SHA256SUMS`; downloaded asset
   checksums and standalone verification passed. The `v0.1.1-skill-pack` tag
   was not moved.

## Previous publication completion record (`0.1.1`)

The corrected `v0.1.1-skill-pack` cutover completed in this order:

1. P0 `a6bea8d2fe2f0d686821142f030596e99024476a` created the history-free
   source root with public author/committer metadata and the repository-bound
   `.github/allowed_signers` trust record.
2. P1 `41fce2b24b812ab7614bf06b51fddf75464237fa` added only the 66 generated
   `dist/skill-pack/` files. Its manifest binds P0 and canonical source hash
   `eafb79e32131321f8e23d6b54ffdbb3d9e05d9a708f91d361c4ba957cb4a2524`.
3. The exact P1 candidate passed hosted `public-gate` run
   [`31270694983`](https://github.com/GauravAlbal/ats/actions/runs/31270694983).
4. Before tagging, a fresh clone at P1 passed `uv sync --frozen`, the complete
   `python -m pytest -q` suite, `tools/validate_repo.py`, `tools/smoke_cli.py`,
   both normative package validators, and `ats skills verify`.
5. The SSH-signed annotated tag was then created at P1 and the source archive,
   standalone pack archive, and `SHA256SUMS` were published.

The public signer binding is `.github/allowed_signers`:

```bash
git -c gpg.ssh.allowedSignersFile=.github/allowed_signers \
  tag -v v0.1.2-skill-pack
```

That command reports a good ED25519 signature for
`157336828+GauravAlbal@users.noreply.github.com`. GitHub currently reports
`unknown_key` for provider-side attribution because this SSH key is not
registered with the account as a signing key; the release does not claim a
provider-verified badge.

Project policy and GitHub ruleset `Immutable release tags` (ID `20590138`)
protect `refs/tags/v*` from updates and deletion. The ruleset does not restrict
initial tag creation. Post-release hosting controls or documentation changes do
not move release tags. Branch protection requires the observed `public-gate`
context,
linear history, and resolved conversations; force pushes and branch deletion
are disabled. Private vulnerability reporting, secret scanning, push
protection, Dependabot security updates, and GitHub CodeQL default scanning for
Python and Actions are enabled. The initial CodeQL run
[`31271232453`](https://github.com/GauravAlbal/ats/actions/runs/31271232453)
completed successfully.

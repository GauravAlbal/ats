# Public hosting

This document records the hosting contract for the public ATS repository at
[`gauravalbal/ats`](https://github.com/gauravalbal/ats).

## Publication status

The selected licensing split is recorded in
[`PUBLICATION_LICENSING.md`](PUBLICATION_LICENSING.md): Apache-2.0 covers the
implementation, public skills, repository-local schemas and machine-readable
assets, tools, tests, and generated assets; CC-BY-4.0 covers ATS-1 normative
text/package material and repository-authored documentation. Skill-pack version
`0.1.1` is the release candidate; the gate below MUST pass before the signed
annotated tag `v0.1.1-skill-pack` is created.

## Candidate facts

These facts are recorded from the repository rather than inferred from a
hosting provider:

- The default branch is `master`.
- The Python implementation version is `0.5.0` (`pyproject.toml`).
- The public skill-pack version is `0.1.1`; its generated manifest MUST record
  the canonical source commit and tree hash.
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
- skill pack: `0.1.1`, released as `v0.1.1-skill-pack`.

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

## Release gate

The `v0.1.1-skill-pack` tag and release MUST follow, not precede, all of these
checks:

- reachable history begins at a history-free P0 source root whose public Git
  metadata passes the disclosure scan;
- P1 adds only the generated `dist/skill-pack/` tree, whose manifest binds P0;
- the exact P1 candidate passes hosted `public-gate`;
- a fresh clone at P1 passes `uv sync --frozen`, the complete
  `python -m pytest -q` suite, `tools/validate_repo.py`, `tools/smoke_cli.py`,
  both normative package validators, and `ats skills verify`;
- private vulnerability reporting and the documented contribution surfaces are
  enabled; and
- only then is a signed annotated tag created and the source, standalone pack,
  and `SHA256SUMS` release assets published.

The public signer binding is `.github/allowed_signers`. Consumers can verify the
release independently of provider badges:

```bash
git -c gpg.ssh.allowedSignersFile=.github/allowed_signers \
  tag -v v0.1.1-skill-pack
```

The release tag is immutable after publication. Post-release hosting controls
or documentation changes belong in a child commit and do not move the tag.

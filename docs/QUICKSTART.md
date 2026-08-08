# ATS quickstart

This path uses only a clean clone, Python 3.12 or newer, and the files in this
repository. It does not require a private repository, hosted service,
credential, sibling checkout, or developer-specific environment variable.
This checkout carries the current `0.1.2` skill-pack release under
`v0.1.2-skill-pack`; release `0.1.1` remains available as the previous release.
Canonical source comes first: update the public skills and recipes, then
generate and verify the host forms; do not hand-edit `dist/skill-pack/`.

## 1. Clone and install

Clone the canonical public repository:

```bash
git clone https://github.com/gauravalbal/ats.git
cd ats
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --editable .
```

The editable install provides the `ats` command from this checkout. If your
Python 3.12 executable has another name, use that executable to create the
virtual environment.

## 2. Verify the checkout

Run the package and generated-pack checks before using a skill:

```bash
ats spec validate
ats skills verify --pack dist/skill-pack
```

Both checks are local and deterministic for the checkout's inputs. Inspect the
three identities and available standard editions with:

```bash
ats spec status
ats --spec-version 1.0.0-draft.2 capability show
```

New durable authoring uses `ATS-1 1.0.0-draft.2`; unlabeled historical,
corpus, and annotation-bench material remains `ATS-1 1.0.0-draft.1`. See
[`STABILITY.md`](STABILITY.md) for the two-default law and artifact binding.

## 3. Install the four public skills

Choose the host form that matches your agent. The repository ships `generic/`,
`claude/`, `codex/`, and `agent-plugins/` under `dist/skill-pack/`; each form
contains placement guidance in its README. The generic form is plain Markdown
and is a useful host-neutral starting point.

The following command copies all four generic skills and their recipes into a
local directory you choose to expose to your agent:

```bash
PACK=dist/skill-pack/generic
DEST="$PWD/.ats-skills"
mkdir -p "$DEST"
cp -R "$PACK/ats" "$PACK/ats-spec" "$PACK/ats-assess" "$PACK/ats-review" "$DEST/"
cp -R "$PACK/recipes" "$DEST/"
```

For a host with a prescribed skill directory, copy the same four skill folders
(and the recipes) from the matching generated host form into that directory.
The pack does not assume a host-specific API.

## 4. Use each skill

These are prompts to your agent, not shell commands. The first prompt is the
usual entry point; the others address a skill directly:

```text
Use ATS to write this implementation specification.
Use ats-spec for this implementation specification.
Use ats-assess for this diagnostic and separate observations from inferences.
Use ats-review to review this technical proposal without inventing missing facts.
```

The result is a human-readable technical artifact. You do not need to construct
TextIR or receipt objects to use the public skill surface.

## 5. Keep the result verifiable

For a generated pack or a later change, rerun:

```bash
ats spec validate
ats skills verify --pack dist/skill-pack
```

A clean result means the checks that ran found no issue within their declared
capability. It is not a universal claim that an artifact is complete or
correct. Read [`EVIDENCE.md`](EVIDENCE.md) for the boundary between mechanical
checks, case-study observations, and unsupported broad claims.

## Next steps

- [`../README.md`](../README.md) — purpose, applicability, and navigation;
- [`OSS_SKILL_PACK.md`](OSS_SKILL_PACK.md) — standalone skill-pack details;
- [`SKILL_CONTRACTS.md`](SKILL_CONTRACTS.md) — inputs, outputs, and refusal
  behavior;
- [`ARTIFACT_RECIPES.md`](ARTIFACT_RECIPES.md) — artifact shapes;
- [`STABILITY.md`](STABILITY.md) — standard, implementation, and pack versions;
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — contribution boundaries.

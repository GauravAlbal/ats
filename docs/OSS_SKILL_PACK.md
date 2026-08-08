# ATS Skill Pack — Install and Use

## What ATS is

ATS-1 is a technical writing standard for AI-generated and AI-consumed
engineering artifacts. It is designed to preserve implementation-relevant
meaning across machine handoffs while keeping the result inspectable as prose.

When an artifact moves between systems — author to planner, deliberation to
implementation, analysis to decision — the distinctions that change
interpretation must survive: whether a claim was observed or inferred, whether
a requirement is MUST or SHOULD, whether a number is a bound or a guess, which
source an assertion came from. Ordinary readability systems make prose shorter
and smoother. ATS-1 governs the recovery cost of *meaning*: a transformation
must not delete a distinction that could change interpretation or action. The
standard's implementation is deterministic — validation, linting, and receipts
run locally and produce the same answer every time.

This skill pack is the easy way to use ATS-1. It is four skills — `ats`,
`ats-spec`, `ats-assess`, `ats-review` — plus artifact recipes, packaged for a
coding agent. It is an interface to ATS, not a second specification: the same
standard, the same runtime, the same checks.

## Use ATS for / Do not use ATS for

Use ATS for durable technical artifacts whose operative meaning must survive a
machine handoff while remaining human-inspectable:

- architecture
- RFCs and technical proposals
- implementation specifications
- diagnostics and forensic analysis
- postmortems
- technical assessments
- acceptance and change-control artifacts

Do not use ATS for:

- every chat message
- marketing copy
- casual prose
- anything whose distinctions do not materially change interpretation or action

If you are not sure whether ATS applies, the `ats` skill decides that before it
does anything else.

## 30-second install and first use

The pack ships inside the ATS repository, generated from canonical skill
source, under `dist/skill-pack/`. It has four host forms:

| Form | What it is |
|---|---|
| `generic/` | Plain Markdown: skill identity, governing laws, recipes — no host syntax. **The reference form.** |
| `claude/` | Packaging shaped for Claude's skill convention. |
| `codex/` | Packaging shaped for Codex's convention. |
| `agent-plugins/` | A portable Agent Plugins root (agent-plugins.org, schema 1.0.0): `plugin.json` + `skills/` as Agent Skills + `references/` recipes. |

All four forms are **generated from the canonical source** (`skills/public/**`
plus `docs/ARTIFACT_RECIPES.md`), never hand-maintained, so they carry the
same content and the same laws. Pick the form matching your agent and preserve
that host's relative layout: copy the four skill folders plus its `recipes/`
or `references/` directory as described by the host README. From a source
checkout, verify the generated pack before installation:

```bash
ats skills verify --pack dist/skill-pack
```

Then ask your agent, in plain words:

```text
Use ATS for this architecture proposal.
```

That is the whole interface. The `ats` skill determines the mode (here: new
authoring), resolves the standard version (new durable authoring resolves to
draft.2), selects the authoring path, runs the deterministic checks before
reporting success, and returns a human-readable artifact. You do not need to
know what TextIR, basis records, or receipt schemas are to get the artifact —
that machinery stays in the background. If a material semantic distinction is
unresolved, the skill tells you instead of inventing an answer; it asks you
only when that unresolved meaning blocks the requested action.

## What you installed (version identity)

Three version strings stay distinct, on purpose:

| String | Value | What it means to you |
|---|---|---|
| ATS-1 standard | `1.0.0-draft.2` (new authoring) / `1.0.0-draft.1` (legacy interpretation) | The normative edition your artifacts are judged against. New durable authoring uses draft.2; historical material stays draft.1 unless you explicitly migrate it. |
| ATS implementation | `0.5.0` | The runtime behind the skills: validation, linting, receipts, policy resolution. |
| ATS skill pack | `0.1.2` | The released skills, recipes, and packaging with portable host-local recipe lookup. |

The pack declares which standard editions it supports; it is not the standard
itself. If the standard moves, the pack follows by regeneration — it never
pretends to be the new standard, and a pack update never pretends to be a
standard change.
Release `0.1.2` is published under the signed annotated tag
`v0.1.2-skill-pack`; release `0.1.1` remains available as the previous release.
Canonical source comes first: generated forms are never hand-maintained, and
the public manifest binds them to the source commit used for generation.

## Upgrading

Upgrading is regenerate, verify, re-vendor:

```bash
python tools/generate_skill_pack.py
ats skills verify --pack dist/skill-pack
```

Then replace the entire previous host form with the regenerated one. Do not
hand-port individual files between versions.

The manifest (`skill-pack-manifest.json`) records the pack version, the
supported standard editions, per-file checksums, and provenance (source commit
and packager version), so drift between your installed copy and the canonical
source is detectable rather than silent. Because every host form is generated
from one source, upgrading never means hand-porting edits between forms.


## The mini-constitution

The ten laws every ATS skill carries:

1. **Preserve meaning before improving surface form.**
2. **Do not invent authority.**
3. **Separate observation, inference, judgment, recommendation, and requirement when the distinction matters.**
4. **Preserve exact normative force.**
5. **Unknown is a valid state.**
6. **Remove surface material before removing material relations.**
7. **Stable semantic coordinates survive transformation.**
8. **Prefer local semantic closure for units expected to survive extraction.**
9. **Acceptance evidence is not the same discourse role as the requirement it verifies.**
10. **Ask only when unresolved meaning blocks the requested action.**

These laws are what make ATS different from a style guide: they govern what
happens to meaning during authoring, transformation, and review — not just how
the prose reads.

## ATS and STE

STE (ASD-STE100) and ATS do different jobs:

- **STE controls the language.**
- **ATS controls the semantic handoff.**

STE makes technical prose simpler and more controlled for human readers. ATS
preserves the distinctions a technical artifact needs to survive machine
handoffs — force, scope, authority, evidence, uncertainty — while remaining
inspectable as prose. They are complementary, not competitors, and this project
makes no "ATS beats STE" claim. The repository's ATS/STE evidence packet exists
as case-study / empirical evidence from a specific observed experiment; it is
evidence, not normative authority, and its claims are bounded to what was
observed.

## Independence

The pack needs nothing beyond itself and the ATS runtime. **No Arq, Tribunal,
VX, Moat, or Sear is required** to install it, invoke it, or produce an ATS
artifact. There is no account, no fleet, no hosted service, and no
out-of-band dependency.

Advanced users can go further: `ats planning project` projects an accepted ATS
specification into planning input, which Arq can consume as tasks with source
lineage preserved. That is an optional extension of the same surface — it
changes nothing about generic use.

## How ATS differs from an ordinary style guide

A style guide tells you how the writing should look. ATS-1 is a discourse
standard for what the writing must preserve: it separates observation from
inference from judgment from recommendation, keeps MUST/SHOULD exact, refuses
to strengthen causal claims, records unknown as unknown, and checks
deterministically that a transformation did not silently change meaning. The
skills route your request to the right kind of artifact — spec, assessment, or
review — and keep the machinery out of the way.

## Further reading

- [`SKILL_PACK_NORTH_STAR.md`](SKILL_PACK_NORTH_STAR.md) — the program's north star: one canonical surface, authority precedence, non-goals
- [`NORTH_STAR.md`](NORTH_STAR.md) — what ATS itself exists to do
- [`ARTIFACT_RECIPES.md`](ARTIFACT_RECIPES.md) — shapes for architecture, RFC, implementation program, diagnostic, postmortem
- [`SKILL_PACKAGING.md`](SKILL_PACKAGING.md) — how the pack is generated, versioned, and verified
- [`FLEET_SKILL_ROLLOUT.md`](FLEET_SKILL_ROLLOUT.md) — how the Arq fleet consumes the same surface
- [`decisions/ADR-0023-public-skill-pack-architecture.md`](decisions/ADR-0023-public-skill-pack-architecture.md) — the architecture decision behind the pack

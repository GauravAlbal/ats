# ATS Skill Pack — North Star

This document is the program's north star: what the public ATS skill pack is,
which laws govern it, why the version and authority models are shaped the way
they are, and what the program is explicitly not. The governing architecture
decision is [`ADR-0023`](decisions/ADR-0023-public-skill-pack-architecture.md);
section references below resolve to that ADR, `SKILL_CONTRACTS.md`, or ATS-1.

## The program

ATS is implemented standard infrastructure: a normative package
(`spec/ATS-1/1.0.0-draft.2`), a deterministic runtime (TextIR validation, IR
lint, output lint, receipts, policy resolution, planning projection), and
compiler-grade internal skills that speak TextIR, basis records, and lint
reports. An ordinary coding-agent user cannot adopt ATS from that surface
without learning the implementation.

This program is the bridge between those two states:

```text
ATS as implemented standard infrastructure
        ↓
one canonical public skill surface, packaged
        ↓
ATS as something an ordinary coding agent user can install and use
```

The program succeeds when: there is one canonical public ATS skill surface an
ordinary coding-agent user can install independently; the Arq fleet consumes
that same surface; new durable artifacts are authored under ATS-1 draft.2 with
semantic integrity checks; historical draft.1 material remains safely pinned;
and accepted ATS specifications flow into downstream planning without losing
their source semantics.

## One canonical public surface

Four operator-facing skills are authored once in this repository and consumed
by both OSS users and fleet consumers (governing public contract):

- **`ats`** — the front door. Determines mode (new authoring / transformation /
  review), determines artifact intent, resolves whether ATS is appropriate,
  selects the ASSESS / SPECIFY / composition path, resolves the standard
  version, invokes deterministic validation, and surfaces REVIEW_REQUIRED
  honestly.
- **`ats-spec`** — durable artifacts from which implementation work can be
  decomposed without reconstructing undeclared semantic state. The strongest
  initial adoption surface.
- **`ats-assess`** — reasoning artifacts: diagnosis, forensic investigation,
  postmortem, design assessment, technical recommendation — with epistemic and
  evidential distinctions preserved.
- **`ats-review`** — adds value to arbitrary existing technical prose without
  requiring conversion. Review first; rewrite only on request.

Canonical source is `skills/public/**` (the four SKILL.md files plus the
recipe references). Host representations — generic, Claude, Codex, and the
portable Agent Plugins form — are mechanically generated adapters of that
source, never hand-maintained copies.
The fleet vendors the OSS surface rather than maintaining a private dialect
(governing law 13); there is no fork, in fact or in effect.

The internal compiler skills (`ats-ir-author`, `ats-assess-output`,
`ats-specify-output`) remain repository-only development artifacts. They are
not packaged, and the four public skills are self-contained: no public skill
invokes or requires them.

```text
                    ATS repository
                         │
              canonical public skills (skills/public/**)
                         │
             ┌───────────┴───────────┐
             │                       │
          OSS users              Arq fleet
             │                       │
             └───────────┬───────────┘
                         │
                  ATS runtime/CLI
                         │
                 TextIR + lint
                         │
                  render + receipt
                         │
                 planning projection (advanced)
```

The skill pack is an **interface to ATS, not a second specification**
(governing law 2). It routes intent to the ATS machinery — version resolution,
authoring, deterministic validation, receipts — and it carries the
mini-constitution below. It does not restate, extend, or override ATS-1
semantics; where the pack and the standard could disagree, the standard wins
(see authority precedence). Users of the pack consume the same semantics, the
same checks, and the same receipts as the fleet.

## The bridge

The pack is what the ordinary user sees. What the ordinary user must never
need to learn:

- TextIR internals and basis records;
- renderer internals;
- rule registries;
- receipt schemas;
- planning-projection machinery.

Those remain implementation infrastructure. The desired experience is a
sentence, not a curriculum:

```text
"Use ATS for this architecture proposal."
"Write this implementation spec in ATS."
"Review this RFC under ATS."
"Convert these investigation notes into an ATS assessment."
```

The front-door skill resolves everything else: mode, artifact intent, standard
version, authoring path, deterministic checks, honest review escalation, and a
human-readable artifact — with IR/trace/receipt surfaces kept available but
out of ordinary user prose.

Generic ATS operation depends on nothing beyond the pack and the ATS runtime:
no external integration is required. Planning projection and downstream
consumption are advanced, optional capabilities for users who want them, never
prerequisites.

Delivery surface (generated): `dist/skill-pack/` with `generic/`, `claude/`,
and `codex/` host forms plus a manifest (`skill-pack-manifest.json`) carrying
pack version, standard compatibility, per-file checksums, and provenance. The
deterministic packager is `tools/generate_skill_pack.py`; the validator
surface is `ats skills verify`. Exact command details belong to the packaging
slice (see [`SKILL_PACKAGING.md`](SKILL_PACKAGING.md)); nothing in this
program hand-maintains per-host skill copies.

## The two-default version law

ATS has two intentionally different defaults, and the public skills must never
collapse them into one global default (ADR-0020).

- **New durable authoring → `1.0.0-draft.2`**, via `AUTHORING_SPEC_VERSION`;
  the fleet policy pins `text_policy.version = 1.0.0-draft.2`.
- **Legacy interpretation → `1.0.0-draft.1`**, via `DEFAULT_SPEC_VERSION`;
  unlabeled historical material with no policy is interpreted under draft.1.

Hard compatibility laws, preserved exactly:

```text
draft.1 artifact + draft.1 policy              → draft.1
unlabeled legacy material + no policy          → draft.1
new durable authoring under fleet policy       → draft.2
draft.2 artifact + draft.1 policy              → refusal
```

A draft.2 artifact must never silently downgrade. A draft.1 artifact must
never silently acquire draft.2 semantics. The skills resolve the standard
version explicitly; an explicit `--spec-version` wins, and no default collapse
is permitted. This law is load-bearing for every public skill: it is what
keeps new authoring current while keeping historical material honest.

## The mini-constitution

The ten laws the public skills carry are the canonical skill constitution. Every
public skill must be consistent with them, and every generated host package must
preserve them:

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

The semantic content of these laws is fixed by draft.2; the skills reference
them rather than restating the full 36-rule registry. Their public contract is
`SKILL_CONTRACTS.md`.

## Three version strings, never collapsed

| String | Value | What it names |
|---|---|---|
| ATS-1 standard | `1.0.0-draft.2` (new authoring) / `1.0.0-draft.1` (legacy interpretation) | The normative edition an artifact is judged against. |
| ATS implementation | `0.5.0` | The runtime/CLI that validates, lints, renders, and receipts. |
| ATS skill pack | `0.1.2` candidate | The public skill surface and its packaging. |

The three answer different questions and change on different cadences: the
standard moves when the normative text moves, the implementation moves when
runtime behavior moves, the pack moves when the surface or packaging moves.
Collapsing them into one string would make a pack update pretend to be a
standard change, and a standard update pretend to be a pack change. Instead,
the pack **declares compatibility** with the standard editions it supports,
including older editions it can safely review or transform, rather than being
pinned to one. The pack version is a dedicated constant
(`SKILL_PACK_VERSION`) stamped in the pack manifest and in every generated
host package, so an installed pack's identity is always verifiable.
Release `0.1.1` remains published under `v0.1.1-skill-pack`. Candidate `0.1.2`
repairs portable recipe lookup and receives a distinct signed tag only after
its gates pass. Canonical source comes first: complete the public skills and
recipes, generate the host forms, and verify their manifest.

## Authority precedence

Where the layers can disagree, precedence is fixed by the public contract:

```text
ATS-1 normative package
        >
public skill contract
        >
artifact recipe
        >
host packaging adapter
```

Internal implementation skills execute the public contract; they do not
override ATS normative semantics. If a host adapter cannot express a required
public-skill behavior, package validation fails rather than the skill being
silently weakened. The standard is the ceiling and the floor; everything in
the pack is a route to it.

## What this program is not

- **Not a new normative profile set.** Artifact recipes are authoring guidance,
  not normative profiles; nothing here extends ATS-1's profile surface without
  evidence.
- **Not a quality score.** No artifact receives a score. Review findings are
  BLOCK / REVIEW_REQUIRED / ADVISORY, and style findings are never blocking.
- **Not a web app and not hosted ATS.** The pack is local files plus a local
  runtime; there is no service.
- **Not a mass conversion of historical documents.** Historical material stays
  draft.1 unless migration is explicit; no fleet document is bulk-converted.
- **Not a style bureaucracy.** ATS-1 is not a universal writing style, ATS does
  not apply to all prose, and the pack does not make style advisory.

The release retains these additional non-goals: no
redesign of ATS-1, no large new rule family, no completion of the annotation
bench, no semantic-model training, no public-skill dependency on Arq or
Tribunal, no deep integration into the transitional Python Tribunal seam, no
duplicated canonical skills per host, no manual TextIR authoring by users, no
routine human review for successful authoring, and no equating ATS requirement
IDs with VX task IDs.

## How the program proves itself

- **OSS fresh-install capstone:** a clean environment installs the pack and
  produces a draft.2 architecture/spec artifact with deterministic checks and a
  receipt — no private fleet dependency, no local absolute path, no manual
  TextIR authoring, no unnecessary human question.
- **Fleet planning capstone:** an accepted `ats-spec` artifact projects into
  planning with source coordinates preserved, task IDs distinct from ATS IDs,
  and one requirement allowed to map to multiple tasks.
- **Review capstone:** pre-ATS prose with a tempting semantic ambiguity yields
  a review finding, optional safe conversion, and no invented authority.
- **Independent adversarial review** before release examines version,
  packaging, fleet, and UX risks with a reviewer who is not the author.

## Where the program ends

Success is not "more prompt templates". Success is: ATS now has one canonical
public skill surface that an ordinary coding-agent user can install
independently, and the Arq fleet consumes that same surface. New durable
artifacts are authored under ATS-1 draft.2 with semantic integrity checks;
historical draft.1 material remains safely pinned; and accepted ATS
specifications flow into downstream planning without losing their source
semantics.

The later Tribunal milestone strengthens this architecture by replacing
skill-mediated semantic compilation at the primary production boundary with
native structured ATS production. Tribunal does not receive a forked dialect
and does not own ATS semantics (governing law 12) — and it does not replace
the public skill pack.

## Related documents

- [`OSS_SKILL_PACK.md`](OSS_SKILL_PACK.md) — install/use/upgrade for a standalone user
- [`SKILL_PACKAGING.md`](SKILL_PACKAGING.md) — canonical source to host generation, versioning, drift detection
- [`FLEET_SKILL_ROLLOUT.md`](FLEET_SKILL_ROLLOUT.md) — vendor path for the Arq constellation
- [`ARTIFACT_RECIPES.md`](ARTIFACT_RECIPES.md) — the recipe set the skills reference
- [`NORTH_STAR.md`](NORTH_STAR.md) — what ATS itself exists to do
- [`decisions/ADR-0023-public-skill-pack-architecture.md`](decisions/ADR-0023-public-skill-pack-architecture.md) — this program's architecture decision
- [`decisions/ADR-0020-draft1-draft2-coexistence.md`](decisions/ADR-0020-draft1-draft2-coexistence.md) — the two-default version law

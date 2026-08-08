# ATS-1 — Arq Text Standard

**ATS-1 is a technical writing standard for AI-generated and AI-consumed
engineering artifacts.** It is for documents whose meaning must survive a
handoff between people, agents, and tools while remaining inspectable as prose.

Technical writing can stay readable while losing distinctions that change an
implementation: authority, normative force, conditions, exceptions, lifecycle
state, uncertainty, evidence requirements, or system boundaries. ATS makes those
distinctions explicit and keeps them checkable.

## Start here

### Use ATS when the artifact has a job to survive

Use ATS for:

- architecture and RFCs;
- technical proposals and implementation specifications;
- implementation programs and acceptance/change-control records;
- diagnostics, postmortems, and technical assessments.

Usually do not use ATS for:

- casual chat, brainstorming, or scratch notes;
- marketing or ordinary social writing;
- every paragraph of a README;
- any short-lived prose whose distinctions do not change interpretation or
  action.

ATS is a standard and a local tool surface, not a hosted service or a claim
that one writing style is universally best.

### A 30-second path

1. Install the repository and its local CLI (the prerequisite is Python 3.12
   or newer):

   ```bash
   python3.12 -m venv .venv
   . .venv/bin/activate
   python -m pip install --editable .
   ```

2. Install one generated host form of the four public skills
   (`ats`, `ats-spec`, `ats-assess`, `ats-review`) using the host's normal
   skill-directory mechanism. The generated forms are under
   `dist/skill-pack/{generic,claude,codex,agent-plugins}/`; each form includes
   placement guidance.

3. Ask the agent:

   ```text
   Use ATS to write this implementation specification.
   ```

The `ats` front door chooses the artifact path. You can also address a skill
directly: `ats-spec` builds durable specifications, `ats-assess` creates
reasoning artifacts, and `ats-review` reviews existing technical prose. The
skills return a human-readable artifact; TextIR and other intermediate records
stay behind this surface.

### One compact lifecycle example

These states are not interchangeable:

```text
accepted → routed → disclosed → consumed
```

`accepted` means an artifact entered the relevant flow; `routed` means a
destination was selected; `disclosed` means the information was made
available at the required boundary; `consumed` means a downstream actor used
it. Collapsing those states into “handled” can leave different
implementations possible. ATS preserves the distinction when it matters.

## What ATS is (and is not)

ATS-1 governs semantic handoff, not just surface style. It preserves exact
force (`MUST` versus `SHOULD`), authority, scope, evidence status, uncertainty,
conditions, exceptions, and stable coordinates. It reports an unavailable
decision as `UNAVAILABLE` rather than treating the absence of a finding as
proof.

ATS is independent of any particular fleet or agent host. A public clone can
install the local implementation and inspect or verify the generated skill
pack without a private account or external service. Integrations that consume
planning projections are optional; they are not prerequisites for authoring or
checking an artifact.

## ATS and STE

ASD-STE100 Simplified Technical English and ATS address related but different
jobs:

- **STE controls the language.**
- **ATS controls the semantic handoff.**

STE emphasizes controlled technical communication and clear language. ATS
emphasizes preserving implementation-relevant meaning across complex,
machine-consumed engineering artifacts. They can be complementary. ATS does
not claim ASD endorsement, formal STE compatibility, or universal superiority
over STE.

ATS draws on controlled-language discipline, requirements engineering, and
state/provenance practices, adapting them to machine-consumed technical
handoffs rather than presenting every underlying idea as a clean-room
invention. The repository's lineage and prior-art summary explains these
influences and their explicit boundaries:
[`docs/LINEAGE_AND_PRIOR_ART.md`](docs/LINEAGE_AND_PRIOR_ART.md). That document
is informative; the normative source is the ATS-1 package.

## Standard and version identity

Three identities are intentionally separate:

| Domain | Current identity | Meaning |
|---|---|---|
| ATS-1 standard | `1.0.0-draft.2` for new durable authoring | Normative edition governing the artifact |
| ATS implementation | `0.5.0` | Local runtime that validates, lints, and creates receipts |
| ATS skill pack | `0.1.2` candidate | Portable recipe lookup repair for the released skill surface |

Historical, corpus, and other unlabeled material remains interpreted as
`ATS-1 1.0.0-draft.1` unless explicitly migrated. New durable authoring
defaults to draft.2. Draft.1 is immutable; neither edition is silently
reinterpreted, downgraded, or upgraded. See
[`docs/STABILITY.md`](docs/STABILITY.md) and the
[`draft.1 → draft.2 migration record`](docs/ATS_1_DRAFT_2_MIGRATION.md).
The public skill-pack candidate is `0.1.2` (`SKILL_PACK_VERSION`). Release
`0.1.1` remains available under `v0.1.1-skill-pack` while the candidate passes
its publication gates. Canonical source comes first: update `skills/public/**`
and the canonical recipes, then generate and verify `dist/skill-pack/`;
generated host forms are never hand-maintained. The canonical repository is
[`gauravalbal/ats`](https://github.com/gauravalbal/ats).
The portable-reference defect and correction are documented in the
[`0.1.2` release notes](docs/RELEASE_NOTES_V0.1.2_SKILL_PACK.md).

## Deterministic checks

After installation, these checks run locally:

```bash
# Verify the imported normative package and its validator.
ats spec validate

# Verify every generated skill-pack host form against canonical source.
ats skills verify --pack dist/skill-pack

# Inspect available standard editions and implementation identity.
ats spec status

# Inspect draft.2 capabilities explicitly.
ats --spec-version 1.0.0-draft.2 capability show
```

The pack manifest binds host files to the canonical source tree, source
commit, standard versions, implementation version, and per-file SHA-256
digests. A mismatch is a typed finding, not a silently accepted install.

## Public planning boundary

An ATS requirement is not a task:

```text
ATS requirement ≠ task
```

A generic planner may map one requirement to several tasks, or several
requirements to one task, while preserving the ATS source coordinates. This
planning projection is public and useful to third-party planner authors. Any
workflow-specific consumer is an optional integration and does not define ATS
meaning.

## Documentation authority and navigation

When documents disagree, use this order:

1. the [ATS-1 normative package](spec/ATS-1/);
2. [normative migration and change records](docs/ATS_1_DRAFT_2_MIGRATION.md);
3. [public skill contracts](docs/SKILL_CONTRACTS.md);
4. [artifact recipes](docs/ARTIFACT_RECIPES.md);
5. this README and [`docs/QUICKSTART.md`](docs/QUICKSTART.md);
6. [case studies and lineage notes](docs/LINEAGE_AND_PRIOR_ART.md).

The shortest public path is **README → QUICKSTART → skills → standard →
rules/schemas → advanced integration**. README guidance and case studies do
not override normative behavior.

## Advanced surface

Contributors and integrators can inspect the intermediate TextIR representation,
rules, schemas, receipts, and planning projection. Those details are useful
when authoring tools or validating a pipeline, but they are not required for a
first artifact. Start with the public skill contracts and recipes:

- [`docs/OSS_SKILL_PACK.md`](docs/OSS_SKILL_PACK.md) — standalone skill-pack
  installation and use;
- [`docs/SKILL_CONTRACTS.md`](docs/SKILL_CONTRACTS.md) — inputs, outputs,
  refusal behavior, and authority boundaries;
- [`docs/ARTIFACT_RECIPES.md`](docs/ARTIFACT_RECIPES.md) — architecture, RFC,
  implementation, diagnostic, and postmortem shapes;
- [`docs/AUTHORITY_MODEL.md`](docs/AUTHORITY_MODEL.md) — detector limits and
  conformance authority;
- [`docs/PLANNING_PROJECTION.md`](docs/PLANNING_PROJECTION.md) — the public
  projection contract;
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — implementation module map
  and deterministic pipeline;
- [`docs/ATS_1_DRAFT_2_MIGRATION.md`](docs/ATS_1_DRAFT_2_MIGRATION.md) —
  protected edition boundaries.
- [`docs/PUBLICATION_LICENSING.md`](docs/PUBLICATION_LICENSING.md) — licensing
  and redistribution scope.

The implementation can expose a finding or ambiguity in the normative package;
it does not silently redefine the standard. Claims about what is established,
observed, or unsupported are recorded in
[`docs/EVIDENCE.md`](docs/EVIDENCE.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the lightweight contribution
contract. Changes to rule meaning, force semantics, schemas, profiles, or
normative examples require an explicit proposal; an ordinary cleanup must not
change ATS meaning accidentally.

## License

ATS-1 is dual-licensed by scope. [`LICENSE.md`](LICENSE.md) is the authoritative
scope map; the complete legal texts are in [`LICENSES/`](LICENSES/):

- **Apache-2.0** — implementation and runtime source (`src/`), repository
tooling (`tools/`), repository-local schemas and machine-readable assets
(`schemas/`, `capability/`, `config/`, `fixtures/`, generated assets), the
public skills (`skills/`), generated host packs (`dist/skill-pack/`), and
tests (`tests/`).
- **CC-BY-4.0** — the ATS-1 normative package under `spec/ATS-1/` (see
[`spec/ATS-1/LICENSE.md`](spec/ATS-1/LICENSE.md)) and repository-authored
prose under `docs/`, this README, and related documentation.

The historical MIT notice is retired and does not apply to this split.
Separately identified third-party material remains under its upstream terms
([`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)).

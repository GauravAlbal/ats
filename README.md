# ATS-1 — Applied Technical Semantics

**Write technical specs designed so the next agent doesn't have to reinterpret them.**

ATS-1 is a standard designed to make implementation-relevant technical meaning
explicit enough to survive handoffs between people, agents, and tools.

Think of ATS as **the anti-telephone-game standard for technical work**. Its
design target is preserving implementation-relevant semantic distinctions
through summarization, retrieval, decomposition, and the next handoff:

```text
you mean X
    ↓
spec → planner → summary
    ↓
task shard → coding agent
    ↓
reviewer

...somewhere along the way,
X quietly becomes X′
```

ATS exists to resist that drift. Its target is **loss-resistant technical
artifacts**: specifications, architectures, diagnostics, postmortems, and other
durable documents whose important distinctions remain recoverable at the next
handoff.
The target is simple: **same spec, same system**. Different implementations are
fine; different interpretations of the contract are not.

A first request is ordinary language:

```text
Use ATS to write the implementation specification for this change.
```

The `ats` front door chooses the right public skill. New durable authoring uses
ATS-1 `1.0.0-draft.3`, the result stays readable as prose, and the local runtime
performs deterministic checks. [Install ATS](#install) or
[jump straight to the four skills](#the-four-skills).

## Readable is not always implementable

A polished technical document can still permit materially different
implementations.

Consider this sentence:

> Once a message is handled, notify downstream consumers and mark it done.

It is easy to read. It is also missing the distinctions an implementer needs:

- Does “handled” mean `accepted`, `routed`, `disclosed`, or `consumed`?
- Is notification required, recommended, or merely allowed?
- Which consumers are in scope, and when must they be registered?
- What survives a crash?
- What evidence proves completion?

Those questions are not editorial trivia. Different answers produce different
systems.

ATS is designed for that failure mode. It treats technical writing as a
**technical-state preservation** problem: the artifact must preserve the
operative distinctions required to understand, verify, continue, decompose, or
act on the work.

> **Remove words before removing relations.**

Concise prose is welcome. Semantic collapse is not.

## A concrete example

Suppose the source system has this lifecycle:

```text
accepted → routed → disclosed → consumed
```

A summary such as “accepted messages cannot be lost” sounds reasonable but
collapses four states into one slogan. Recovery, disclosure, retries,
notification, and consumption may each depend on a different transition.

An ATS-shaped requirement keeps those relations available:

```text
REQ-NOTIFY-01
When a message enters DISCLOSED, the routing service MUST append one
notification for every downstream consumer registered before that transition.

FAILURE BEHAVIOR
If the service restarts after DISCLOSED but before all notifications are
appended, it MUST resume from the recorded disclosure receipt without emitting
a duplicate notification.

AC-NOTIFY-01
Given two consumers registered before DISCLOSED, the receipt records two
consumer-specific notification IDs.
```

The example does not tell the implementation team which database or queue to
use. It preserves the state, actor, force, condition, recovery obligation, and
acceptance evidence that constrain a correct design.

The same issue appears in cancellation language:

```text
A cancellation requested before admission prevents admission.
A cancellation requested after admission does not erase the accepted record.
```

Compressing both into “cancellation stops the job” would be shorter and wrong.

## What ATS protects

ATS protects distinctions that change the operative model:

- **state and lifecycle** — `accepted` is not `consumed`;
- **authority** — observed, inferred, recommended, authorized, and required are
  not interchangeable;
- **normative force** — `MUST`, `SHOULD`, and `MAY` remain different;
- **uncertainty** — unknown, unavailable, estimated, and established remain
  distinct;
- **scope** — conditions, exceptions, actors, objects, and system boundaries
  stay attached to the claims they qualify;
- **provenance** — material assertions remain traceable to their source;
- **relations** — dependencies, alternatives, causality, temporal order, and
  evidence links survive transformation;
- **coordinates** — requirements, decisions, acceptance criteria, protocols,
  and work items retain stable identities;
- **completion evidence** — a requirement does not masquerade as proof that the
  requirement was satisfied.

ATS keeps five kinds of force separate where they matter: likelihood,
assessment confidence, evidential force, causal force, and deontic force. “The
retry probably caused the duplicate” is not the same claim as “the evidence
supports a retry cause,” and neither statement means “the service MUST change.”

It also keeps discourse roles distinct. An observation can support an
inference; an inference can motivate a recommendation; a recommendation can be
accepted as a requirement. ATS does not silently collapse those steps.

## What the name means

**Applied Technical Semantics** means semantics applied to practical technical
work.

- **Applied** does not mean ATS automatically applies to every technical
  paragraph. Applicability depends on whether the artifact must preserve
  operative meaning across a durable handoff.
- **Technical semantics** means the state, authority, force, uncertainty, scope,
  evidence, conditions, relations, coordinates, and acceptance obligations
  that govern later action.

A well-formed ATS artifact is not automatically true, authorized, accepted for
execution, or formally complete. ATS makes claims and obligations explicit; it
does not supply the evidence, authority, or judgment the source lacks.

## When to use ATS

Use ATS for durable artifacts whose semantic distinctions affect later action:

- architecture and RFCs;
- technical proposals and implementation specifications;
- protocols and implementation programs;
- diagnostics, assessments, and postmortems;
- migrations and change-control records;
- acceptance contracts and evidence-bearing completion records.

Usually do not use ATS for:

- casual chat or brainstorming;
- scratch notes and transient working memory;
- marketing copy or ordinary social prose;
- every paragraph of a README;
- any text whose distinctions have no downstream operational consequence.

The threshold is not “is this Markdown?” It is:

> **Will another actor need to recover this artifact’s operative meaning later?**

## The four skills

Start with `ats` unless you already know the job.

| Skill | Job |
|---|---|
| **`ats`** | Front door. Decides whether ATS applies and routes authoring, transformation, assessment, or review. |
| **`ats-spec`** | Writes durable, buildable specifications, protocols, acceptance contracts, migrations, and implementation programs. |
| **`ats-assess`** | Writes diagnostics, postmortems, comparisons, and recommendations while preserving evidence, inference, judgment, and uncertainty. |
| **`ats-review`** | Reviews existing technical prose for semantic risk without forcing conversion or rewriting by default. |

Example requests:

```text
Use ATS to write the implementation specification for this change.
Use ats-assess to diagnose this failure without turning inferences into facts.
Use ats-review to find where this RFC invents authority or weakens requirements.
```

## Install

You need two pieces:

1. the **public skill pack**, which tells your agent how to author and review ATS
   artifacts; and
2. the **`ats` runtime**, which validates the standard packages and performs the
   deterministic checks.

Prerequisites: [Git](https://git-scm.com/) and
[`uv`](https://docs.astral.sh/uv/getting-started/installation/). `uv` can supply
Python 3.12 when needed.

### 1. Check out the released source

```bash
mkdir -p "$HOME/.local/share"
git clone --depth 2 --branch v0.1.2-skill-pack \
  https://github.com/GauravAlbal/ats.git \
  "$HOME/.local/share/ats"
```

The release contains the four skills and their shared artifact recipes. Copy a
complete generated host form; do not copy only the four `SKILL.md` files and
leave their shared references behind.

<details open>
<summary><strong>Claude Code</strong></summary>

```bash
mkdir -p "$HOME/.claude/skills"
cp -R "$HOME/.local/share/ats/dist/skill-pack/claude/"{ats,ats-spec,ats-assess,ats-review,references} \
  "$HOME/.claude/skills/"
```

</details>

<details>
<summary><strong>Codex</strong></summary>

Codex loads user-level skills from
[`~/.agents/skills`](https://developers.openai.com/codex/skills/#where-to-save-skills).
Use the generic host form so the recipes remain beside the skills.

```bash
mkdir -p "$HOME/.agents/skills"
cp -R "$HOME/.local/share/ats/dist/skill-pack/generic/"{ats,ats-spec,ats-assess,ats-review,recipes} \
  "$HOME/.agents/skills/"
```

</details>

<details>
<summary><strong>Other skill hosts</strong></summary>

Copy the complete generic host form into the host’s skill root:

```bash
cp -R "$HOME/.local/share/ats/dist/skill-pack/generic/"{ats,ats-spec,ats-assess,ats-review,recipes} \
  /path/to/your/skill-root/
```

If the client supports the
[Agent Plugins specification](https://agent-plugins.org/), import
`$HOME/.local/share/ats/dist/skill-pack/agent-plugins/` instead.

</details>

### 2. Install the deterministic runtime

Keep the checkout. The runtime reads the versioned ATS-1 packages from it.

```bash
uv tool install --python 3.12 --editable "$HOME/.local/share/ats"
uv tool update-shell
export PATH="$HOME/.local/bin:$PATH"
ats spec status
```

`ats spec status` should list `1.0.0-draft.1`, `1.0.0-draft.2`, and
`1.0.0-draft.3`. Restart an already-running agent once so it discovers the new
skills.

### 3. Ask for the artifact

```text
Use ATS to write the implementation specification for this change.
```

That is enough to begin. You do not need to learn a schema or manually author
TextIR first.

## How ATS works

The ordinary artifact remains prose. The machine representation exists to
support the prose, not replace it.

For ATS-authored work, the skills make the operative model explicit and use the
local runtime to check it:

```text
author intent or source material
        ↓
meaning ledger (TextIR)
        ↓
deterministic validation and lint
        ↓
readable Markdown + trace
        ↓
candidate receipt or explicit unresolved state
```

The meaning ledger records claims, roles, force, scope, basis, relations, and
stable coordinates. Rendering produces normal Markdown. A trace maps rendered
blocks back to the ledger, and receipts bind the evaluated artifact to its
standard edition and policy.

TextIR is an implementation and control surface. Most users should never write
it by hand.

### Explicit unknowns are valid

ATS does not reward fake completeness. `UNAVAILABLE`, insufficient evidence,
and unresolved authority are valid outcomes when the source does not establish
an answer. The artifact can still be complete as a record of what is known and
what remains open.

### Each unit carries enough local meaning

A requirement that only makes sense after rereading six distant paragraphs is
fragile under extraction. ATS calls the alternative **local semantic closure**:
an extractable unit should be understandable from the unit plus its explicitly
declared dependencies.

That permits useful repetition. Repeating an actor, condition, or requirement
identity can reduce reconstruction cost without turning the document into
verbose boilerplate.

### Coordinates survive transformation

Identifiers such as `REQ-*`, `DEC-*`, and `AC-*` are stable join keys when
other systems refer to the artifact. They let planning, implementation, review,
and acceptance reconnect to the same source obligations after prose is
reorganized.

A coordinate preserves requirement identity; it does not force a one-to-one
task mapping. One requirement can produce many tasks, and one task can satisfy
parts of many requirements, while source coordinates remain attached.

### Checks make bounded claims

Deterministic checks can establish properties such as schema validity,
reference resolution, coordinate preservation, basis preservation, and receipt
integrity for the supplied inputs. They do not prove that every source claim is
true, that the artifact is complete for every use, or that every conforming
implementation will be identical.

## Optional planning integration

ATS owns semantic representation and conformance evidence. It does not own the
workflow engine.

`ats planning project` can produce a sealed planning projection with source
coordinates and policy provenance. Arq, VX, or another planner may consume that
projection, but none is required to use ATS. A planner may map requirements to
tasks without rewriting the source semantics or treating requirement identity
as task identity.

ATS works without Arq, Tribunal, VX, Moat, Sear, a hosted service, or a private
fleet.

## Relation to Simplified Technical English

[ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/) and ATS
address different layers:

- **STE controls the language.** It reduces vocabulary and grammatical
  ambiguity.
- **ATS controls the semantic handoff.** It preserves implementation-relevant
  relations, force, authority, uncertainty, scope, evidence, and coordinates.

They can be used together. ATS makes no ASD endorsement, formal STE
compatibility claim, or universal superiority claim. The repository’s observed
comparison is a bounded case study, not a general benchmark.

## Prior art and the integration ATS adds

ATS draws from mature disciplines rather than claiming to invent technical
clarity:

- controlled languages such as ASD-STE100;
- requirements engineering and RFC normative language;
- architecture decision records and traceability practice;
- FMEA, hazard analysis, diagnostics, and postmortems;
- structured data, provenance, and content-addressed receipts;
- literate programming and human-inspectable technical artifacts.

ATS integrates these ideas around one workload: AI-authored, AI-consumed,
implementation-bearing technical artifacts that must remain inspectable by
humans. Its contribution is the combined preservation contract and the
mechanical path from readable prose to explicit semantics, deterministic
checks, stable coordinates, and evidence-bearing handoff.

See [Lineage and prior art](docs/LINEAGE_AND_PRIOR_ART.md) for source-specific
adoption, adaptation, rejection, and provenance boundaries.

## Evidence and claim boundaries

ATS is designed to reduce semantic loss during technical handoffs. The public
repository mechanically verifies bounded properties of its packages, schemas,
checks, projections, and generated skill pack.

It does not currently establish that ATS always improves coding-agent
performance, universally beats another writing system, reduces defects by a
fixed percentage, or guarantees semantic equivalence. See
[Evidence and claim boundaries](docs/EVIDENCE.md).

## Versions

ATS keeps separate things separately versioned:

| Domain | Current identity | Meaning |
|---|---|---|
| ATS-1 standard | `1.0.0-draft.2` for new durable authoring | Normative edition governing newly authored artifacts |
| Legacy interpretation | `1.0.0-draft.1` | Default interpretation for unlabeled historical and corpus material |
| ATS runtime | `0.5.0` | Local validation, lint, policy, receipt, and projection implementation |
| ATS skill pack | `0.1.2` | Released four-skill surface, recipes, and host packaging |

Historical and corpus material does not silently acquire draft.2 semantics.
Migration is explicit. The sealed draft.1 and draft.2 package bytes retain the
historical expansion **Arq Text Standard**; current public product language uses
**Applied Technical Semantics**. That naming migration changes no normative
meaning, package identity, schema ID, CLI name, or release tag.

See [Stability](docs/STABILITY.md) and the
[draft.1 → draft.2 migration record](docs/ATS_1_DRAFT_2_MIGRATION.md).

## Deterministic commands

```bash
# Inspect the implementation and available standard editions.
ats spec status

# Validate both imported/sealed ATS-1 packages.
ats spec validate

# Verify generated host forms against canonical skill source.
cd "$HOME/.local/share/ats"
ats skills verify --repo . --pack dist/skill-pack
```

The skill-pack manifest binds every generated file to canonical source,
standard compatibility, implementation and pack versions, release commit, and
SHA-256 digest. A mismatch becomes a typed finding rather than a silently
accepted install.

## Go deeper

- [Quickstart](docs/QUICKSTART.md) — source checkout and first use.
- [Artifact recipes](docs/ARTIFACT_RECIPES.md) — architecture, RFC,
  implementation, diagnostic, and postmortem shapes.
- [Skill contracts](docs/SKILL_CONTRACTS.md) — inputs, outputs, refusals, and
  authority limits.
- [ATS north star](docs/NORTH_STAR.md) — mission, non-goals, and semantic
  recovery cost.
- [Architecture](docs/ARCHITECTURE.md) — runtime and deterministic pipeline.
- [Authority model](docs/AUTHORITY_MODEL.md) — what checks may establish and
  who may accept it.
- [Standalone skill-pack guide](docs/OSS_SKILL_PACK.md) — packaging, upgrading,
  and provenance.
- [ATS-1 standard packages](spec/ATS-1/) — normative source.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md). A documentation cleanup must not change
ATS meaning accidentally; changes to normative force, rule meaning, schemas,
profiles, or examples require the repository’s explicit proposal path.

ATS uses a scope-based license split:

- **Apache-2.0** — implementation, tooling, schemas, skills, generated packs,
  tests, and machine-readable assets;
- **CC-BY-4.0** — ATS-1 normative packages and repository-authored
  documentation.

[`LICENSE.md`](LICENSE.md) is the authoritative scope map. Complete texts are
under [`LICENSES/`](LICENSES/); separately identified material remains under
its upstream terms in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Choose the next action

- **Writing a new buildable artifact?** Start with `ats-spec`.
- **Reasoning under uncertainty?** Start with `ats-assess`.
- **Reviewing an existing document?** Start with `ats-review`.
- **Not sure whether ATS applies?** Start with `ats`.
- **Ready to install?** Go to [Install](#install).

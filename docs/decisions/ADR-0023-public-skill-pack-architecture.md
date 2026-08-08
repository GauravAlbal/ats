# ADR-0023: One canonical public skill surface, packaged for independent adoption

**Status:** Accepted
**Date:** 2026-08-07

## Context

`v0.5.0-fleet` shipped ATS as implemented standard infrastructure. The three
skills that exist — `ats-ir-author`, `ats-assess-output`, `ats-specify-output`
— are compiler primitives: they speak TextIR, basis records, and lint reports.
An ordinary coding-agent user cannot adopt ATS from them without learning the
implementation surface.

The program goal is the bridge from *implemented standard infrastructure* to
*something an ordinary coding-agent user can install and use* — independently
of Arq, Tribunal, VX, or Moat. Two failure modes are available from the first
step: a private fleet skill set that diverges from the public one (a fork in
all but name), and hand-maintained per-host skill copies that drift.

## Decision

There is **one canonical public ATS skill surface** — four operator-facing
skills (`ats`, `ats-spec`, `ats-assess`, `ats-review`) — authored once in this
repository, consumed by both OSS users and the Arq fleet, and mechanically
packaged into host representations. Internal compiler skills remain internal
primitives with independently testable contracts.

**Layout** (conceptual split; internal paths stay put per existing convention):

```text
skills/
├── public/
│   ├── ats/            front door: routing, policy/version resolution
│   ├── ats-spec/       durable buildable artifacts (implementation recoverability)
│   ├── ats-assess/     reasoning artifacts (epistemic/evidential distinctions)
│   └── ats-review/     review-first, rewrite-only-on-request
└── (internal, unchanged)
    ├── ats-ir-author/
    ├── ats-assess-output/
    └── ats-specify-output/
```

**Three version strings, never collapsed** (ADR-0020 version law):

| String | Value | Means |
|---|---|---|
| ATS-1 standard | `1.0.0-draft.2` (new authoring) / `1.0.0-draft.1` (legacy interpretation) | normative edition |
| ATS implementation | `0.5.0` | the runtime/CLI |
| ATS skill pack | `0.1.1` | the public skill surface + packaging |

The two-default version law (ADR-0020) is load-bearing for the skills: new
durable authoring resolves draft.2 via the binding policy; legacy material
stays draft.1 unless migration is explicit. Public skills must never collapse
the two defaults or let a draft.2 artifact silently downgrade.
Release `0.1.1` is published under the signed annotated tag
`v0.1.1-skill-pack`. Canonical source precedes deterministic generation and
verification.

**Authority precedence** (public skill contract): ATS-1 normative package >
public skill contract > artifact recipe > host packaging adapter. A host adapter
that cannot express a required behavior fails package validation rather than
silently weakening the skill.

**Packaging** (public pack contract): canonical Markdown → deterministic packager
→ generic / Claude / Codex representations, with parity tests and drift
detection. The generated pack declares standard compatibility, pack version, and
provenance; a validator refuses stale, forked, path-leaking, or Arq-dependent
packages.

## Consequences

- The fleet vendors the exact OSS surface; no private dialect is maintained.
- Users get the front-door experience: "Use ATS for this architecture
  proposal" — no TextIR literacy required. IR/trace/receipt surfaces stay
  available but out of ordinary user prose.
- Tribunal remains the future native structured producer (after TE parity); it
  does not receive a forked dialect and does not own ATS semantics.
- Cost: the pack adds a generated-artifact surface that must stay
  deterministic; the validator is the guard, and regeneration must be a
  no-diff operation.

## Alternatives considered

**Ship only a generic skill and let each host adapt by hand.** Rejected:
hand-maintained per-host copies drift, and the fleet would be tempted to fork.

**Extend the internal skills outward instead of adding a public layer.**
Rejected: internal skills are compiler contracts (IR/basis/lint vocabulary);
exposing them directly forces users to learn implementation infrastructure.

**One merged "megaskill".** Rejected: `ats-spec`, `ats-assess`, and
`ats-review` have different discourse obligations and different adoption angles;
the front door routes to them by task, keeping each contract small and JIT-loadable.

**Make the pack depend on Arq/Tribunal for the normal path.** Rejected: OSS
independence is a completion requirement; Arq/Tribunal are optional advanced
consumers, not prerequisites.

## References

- Public pack contracts under `skills/public/`; `tools/package_skill_pack.py`;
  `dist/skill-pack/skill-pack-manifest.json`; ADR-0010 (operational pivot),
  ADR-0020 (version law)
- `skills/ats-ir-author/SKILL.md` (internal contract format)

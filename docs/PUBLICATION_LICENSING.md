# Publication licensing

**Scope:** the public ATS repository and published `0.1.1` and `0.1.2`
skill-pack releases. This document records licensing boundaries and release
evidence; it is not a separate license grant or legal opinion.

## Current status

The repository has a resolved split-license map and both complete legal texts.
The generated skill-pack tree is built from the canonical public source, binds
its source commit and per-file hashes, and includes the complete notice set in
every host form. Repository, package, pack, and fresh-clone publication checks
have passed.

The public source is self-contained with respect to its authored source
classes. Runtime and development dependencies are installed from public package
sources under their upstream terms; they are not relicensed here.

## Scope map

| Source class | Current paths | License and notice |
|---|---|---|
| Implementation and tests | `src/`, `tools/`, `tests/` | Apache-2.0; use the complete text in [`LICENSES/Apache-2.0.txt`](../LICENSES/Apache-2.0.txt). |
| Machine-readable implementation assets | `schemas/`, `capability/`, `config/`, `fixtures/`, and generated implementation assets outside the mixed host tree | Apache-2.0 unless a path carries a separate notice. |
| Public skills | `skills/public/` | Apache-2.0. |
| Generated host packs | `dist/skill-pack/` | Mixed: host machinery, skill copies, plugin metadata, and manifests are Apache-2.0; copied recipe/reference documents and host documentation are CC-BY-4.0. The complete per-host notice set governs redistribution. |
| Public synthetic data inputs | `corpus/seeds/`, `corpus/operators/` | Apache-2.0 as repository-authored machine-readable assets. |
| ATS-1 normative packages | `spec/ATS-1/1.0.0-draft.1/` and `spec/ATS-1/1.0.0-draft.2/` | CC-BY-4.0 under [`spec/ATS-1/LICENSE.md`](../spec/ATS-1/LICENSE.md). The adjacent notice applies to package text and package material. |
| Repository-authored prose | `docs/`, `README.md`, `CHANGELOG.md`, `protocols/`, and other authored prose files | CC-BY-4.0 unless a file carries a more specific notice. |
| Separately identified third-party material | Any path with an upstream notice | The upstream license governs; see [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md). |

The root [`LICENSE.md`](../LICENSE.md) is the path-scoped map. It does not
replace either complete legal text. `LICENSES/Apache-2.0.txt` and
`LICENSES/CC-BY-4.0.txt` are the canonical Apache-2.0 and CC-BY-4.0 texts.

## ATS-1 package grant and byte boundary

`spec/ATS-1/LICENSE.md` identifies Gaurav Albal as creator, rightsholder, and
publisher of the ATS-1 material and grants the package text and package
material under CC-BY-4.0. Attribution should identify Gaurav Albal, link the
applicable package when available, identify CC-BY-4.0, and indicate
modifications.

The adjacent grant covers both current package editions without changing
`spec/ATS-1/1.0.0-draft.1/`. The draft.1 package remains byte-preserved,
including its internal package metadata. The package's included implementation
tools remain under the Apache-2.0 implementation scope; this does not change
the CC-BY-4.0 terms for normative text and package documentation.

## Dependency notices

`THIRD_PARTY_NOTICES.md` records seven direct runtime, development, and build
requirements declared by `pyproject.toml`, with locked versions/specifiers and
representative artifact hashes where available, SPDX terms, upstream locations,
and relevant copyright information. The notice explicitly states that ATS does
not relicense these dependencies; the pinned Hatchling build requirement is
documented separately because it is not in `uv.lock`.
`pyproject.toml` points its package license metadata to `LICENSE.md`, the
path-scoped map, rather than asserting Apache-2.0 for the whole repository.
The implementation and skills package scope is therefore machine-visible while
the ATS-1 and documentation CC-BY-4.0 boundary remains explicit.

The repository does not vendor dependency source. If a future wheel,
image, or other distribution bundles dependency material, that distribution
must include the applicable upstream license and copyright/NOTICE text. The
current source notice intentionally does not assert a complete inventory of
transitive packages because they are not bundled authored assets.

## Generated host notice contract

`src/ats/skill_pack.py` defines one manifest-bound notice set for every host:

- `LICENSE` — the complete Apache-2.0 text;
- `LICENSES/Apache-2.0.txt` — the complete Apache-2.0 text;
- `LICENSES/CC-BY-4.0.txt` — the complete CC-BY-4.0 text;
- `LICENSE.md` — the path-scoped split map; and
- `THIRD_PARTY_NOTICES.md` — direct dependency terms and boundaries.

The source generator copies the canonical notice inputs byte-for-byte and
records each generated path and SHA-256 in the host manifest. Its verifier
checks presence, byte parity, and manifest hashes. Plugin metadata is generated
with Apache-2.0 for the implementation/skills portion; copied recipe and
documentation files retain the CC-BY-4.0 class.

For release `0.1.1`, the history-free source root precedes the generated-pack
commit. `dist/skill-pack/` was regenerated from that source commit and both
manifest verification and fixed-provenance zero-diff regeneration passed.

## Cutover evidence

Release `0.1.1` satisfied these licensing and packaging checks:

1. the repository validator and both normative package validators passed;
2. the generated skill pack was regenerated from the public source root and
   its manifest-bound notice set verified with zero findings;
3. regeneration with the manifest's fixed provenance was a byte-for-byte no-op;
4. the source and generated trees contain only the scoped authored classes,
   complete notices, and ordinary build metadata; and
5. a fresh clone installed the locked public dependencies and reproduced the
   repository, package, pack, CLI, and test checks.

Future tags, releases, or license-boundary changes remain explicit operator
actions. This record does not pre-authorize them.

## Evidence index

- [`LICENSE.md`](../LICENSE.md) — root scope map.
- [`LICENSES/Apache-2.0.txt`](../LICENSES/Apache-2.0.txt) — complete Apache-2.0 text.
- [`LICENSES/CC-BY-4.0.txt`](../LICENSES/CC-BY-4.0.txt) — complete CC-BY-4.0 text.
- [`spec/ATS-1/LICENSE.md`](../spec/ATS-1/LICENSE.md) — adjacent ATS-1 grant.
- [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) — direct dependency notices.
- [`pyproject.toml`](../pyproject.toml) — package metadata and dependency declarations.
- [`src/ats/skill_pack.py`](../src/ats/skill_pack.py) — generated-host notice and verifier logic.

# ATS licensing map

Copyright © 2026 Gaurav Albal.

This file is a scope map. The complete legal texts are in
[`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt) and
[`LICENSES/CC-BY-4.0.txt`](LICENSES/CC-BY-4.0.txt). Unless a file carries a
separate notice, the following paths are covered as follows:

- **Apache-2.0:** implementation and runtime source under `src/`; repository
  tooling under `tools/`; package/build metadata under `pyproject.toml` and
  `uv.lock`; automation configuration under `.github/workflows/`;
  repository-local schemas and machine-readable assets under `schemas/`,
  `capability/`, `config/`, public synthetic corpus seeds/operators, and
  `fixtures/`; tests under `tests/`; public skill bodies under `skills/`; and
  generated host machinery, skill copies, plugin metadata, and manifests under
  `dist/skill-pack/`.
- **CC-BY-4.0:** ATS-1 normative text and package material under
  `spec/ATS-1/`, subject to its adjacent package notice and the complete
  [`CC-BY-4.0`](LICENSES/CC-BY-4.0.txt) terms; project documentation under
  `docs/`, `README.md`, `CHANGELOG.md`, and other repository-authored
  prose files; and authored recipe/reference documentation under
  `docs/ARTIFACT_RECIPES.md` and `skills/public/recipes/`, including generated
  copies of those documents.
- **Mixed generated hosts:** each `dist/skill-pack/` host contains the
  Apache-2.0 implementation/skills/metadata class and CC-BY-4.0
  recipe/documentation class. The complete per-host notice set defined by
  `src/ats/skill_pack.py` governs redistribution; the host root does not
  receive one blanket license.
- **Third-party material:** any separately identified third-party material
  remains under its upstream license and is not relicensed by this map. See
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). No vendored third-party
  source is included in this repository.

The implementation license does not relicense runtime or development
dependencies installed from public package indexes. Those dependencies remain
under their own upstream terms. The split is also reflected in package and
host notices; a generated host is self-contained only when its complete
manifest-bound notice set is present.

The historical `LICENSE` filename is intentionally retired. The explicit
path-scoped grants above control distribution.

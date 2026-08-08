# Third-party notices

Copyright © 2026 Gaurav Albal for ATS-authored material.

No third-party source code is vendored in this repository. ATS installs the
following direct runtime, development, and build dependencies from the public
Python package index; it does not redistribute or relicense them. This project
does not relicense those dependencies. Each dependency remains under its
upstream terms. The versions, specifiers, SPDX terms, upstream repositories,
and one representative artifact hash are recorded from `uv.lock` where
available and the upstream release records:

| Package | Locked version / specifier | SPDX | Upstream / copyright | Representative `uv.lock` artifact SHA-256 |
|---|---|---|---|---|
| `jsonschema` | 4.26.0 (`>=4.18,<5`) | MIT | [python-jsonschema/jsonschema](https://github.com/python-jsonschema/jsonschema); © 2013 Julian Berman | `d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce` |
| `PyYAML` | 6.0.3 (`>=6,<7`) | MIT | [yaml/pyyaml](https://github.com/yaml/pyyaml); © 2017–2021 Ingy döt Net and © 2006–2016 Kirill Simonov | `fc09d0aa354569bc501d4e787133afc08552722d3ab34836a80547331bb5d4a0` |
| `referencing` | 0.37.0 (`>=0.30`) | MIT | [python-jsonschema/referencing](https://github.com/python-jsonschema/referencing); © 2022 Julian Berman | `381329a9f99628c9069361716891d34ad94af76e461dcb0335825aecc7692231` |
| `markdown-it-py` | 4.2.0 (`>=3,<5`) | MIT | [executablebooks/markdown-it-py](https://github.com/executablebooks/markdown-it-py); © 2020 ExecutableBookProject | `9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a` |
| `rfc8785` | 0.1.4 (`>=0.1.4,<0.2`) | Apache-2.0 | [trailofbits/rfc8785.py](https://github.com/trailofbits/rfc8785.py); upstream Apache-2.0 text carries no separate copyright header or `NOTICE` file | `520d690b448ecf0703691c76e1a34a24ddcd4fc5bc41d589cb7c58ec651bcd48` |
| `pytest` (development only) | 9.1.1 (`>=8`) | MIT | [pytest-dev/pytest](https://github.com/pytest-dev/pytest); © 2004 Holger Krekel and others | `37a86b45efb9a47a61a36449063e8e18d0cab3161329fc099eb21783169c4f0c` |
| `hatchling` (build backend) | 1.31.0 (pinned in `pyproject.toml`; not present in `uv.lock`) | MIT | [pypa/hatch](https://github.com/pypa/hatch); © 2021-present Ofek Lev <oss@ofek.dev> | no lock hash (build requirement is outside `uv.lock`) |

The hashes identify representative wheels from the locked artifact set; all
platform-specific hashes remain in `uv.lock`. This notice records seven direct
dependency records declared by the project: five runtime dependencies, the
development dependency `pytest`, and the pinned build backend `hatchling`.
`hatchling` is intentionally absent from `uv.lock` because it is a PEP 517
build-system requirement. Transitive packages in the lock are not separately
asserted here because ATS does not vendor or redistribute dependency source.
If ATS later bundles or vendors dependencies into a wheel, image, or binary,
the applicable upstream license and copyright texts must accompany that
distribution (and any upstream `NOTICE` must be retained).

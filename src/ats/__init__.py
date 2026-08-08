"""ATS-1 reference implementation (deterministic v0).

The normative package under ``spec/ATS-1/<version>/`` is the source of truth for
every schema, rule, and vocabulary this package evaluates. Code here validates,
resolves, and reports; it never redefines a normative object.
"""

from __future__ import annotations

__all__ = ["__version__", "SKILL_PACK_VERSION", "IMPLEMENTATION_NAME"]

__version__ = "0.5.0"
IMPLEMENTATION_NAME = "ats"

#: Version of the public skill surface and its packaging.
#: Independent of the implementation version above and of the ATS-1 standard
#: edition (draft.2 new authoring / draft.1 legacy interpretation).
SKILL_PACK_VERSION = "0.1.1"

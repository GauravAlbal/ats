"""Planning projection (draft.2 D-H).

The projection turns an accepted, lint-clean ATS TextIR artifact into the
deterministic planning-input surface a downstream planner consumes. It is a
pure function of (validated IR, resolved policy, artifact hash): it preserves
every stable semantic coordinate and IR source pointer, binds the artifact and
policy hashes, validates against ``ats_planning_projection_v1.schema.json``, and
seals itself by content hash. It never derives tasks; task shape is the
planner's judgment and is outside this projection.
"""

from __future__ import annotations

from .project import project_from_ir

__all__ = ["project_from_ir"]

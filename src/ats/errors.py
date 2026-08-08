"""Typed error hierarchy.

ATS-1 requires typed insufficiency over an unsupported pass (spec Section 20.6).
Every failure path in this implementation raises one of these types; no code path
degrades to a bare ``Exception`` or to a silently weaker result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AtsError(Exception):
    """Base class for every ATS implementation error."""

    #: Stable machine-readable code surfaced in CLI output and receipts.
    code = "ats_error"
    #: Process exit code used when this error reaches the CLI boundary.
    exit_code = 1

    def payload(self) -> dict[str, Any]:
        return {"error": self.code, "message": str(self)}


class UsageError(AtsError):
    """The caller supplied arguments or files that cannot be interpreted."""

    code = "usage_error"
    exit_code = 2


class UnsupportedCapabilityError(AtsError):
    """A requested capability is declared unsupported by this implementation.

    Spec Section 5.5 and Section 14.12: an unsupported capability MUST be
    reported, never emulated by a weaker component holding the same claim.
    """

    code = "unsupported_capability"
    exit_code = 3

    def __init__(self, capability: str, reason: str, *, declared_at: str | None = None) -> None:
        super().__init__(f"{capability}: {reason}")
        self.capability = capability
        self.reason = reason
        self.declared_at = declared_at

    def payload(self) -> dict[str, Any]:
        data = {
            "error": self.code,
            "capability": self.capability,
            "reason": self.reason,
            "status": "UNAVAILABLE",
        }
        if self.declared_at:
            data["declared_at"] = self.declared_at
        return data


class RequiredCheckUnavailableError(AtsError):
    """A required check could not execute (spec Section 5.4: UNAVAILABLE, not PASS)."""

    code = "required_check_unavailable"
    exit_code = 4


@dataclass(frozen=True, slots=True)
class SchemaViolation:
    """One JSON Schema validation error, located by JSON Pointer."""

    pointer: str
    message: str
    schema_id: str
    validator: str


class SchemaValidationError(AtsError):
    """An object failed validation against its normative JSON Schema."""

    code = "schema_validation_failed"
    exit_code = 1

    def __init__(self, schema_id: str, violations: list[SchemaViolation]) -> None:
        rendered = "\n".join(f"  {v.pointer or '/'}: {v.message}" for v in violations)
        super().__init__(f"{schema_id} validation failed:\n{rendered}")
        self.schema_id = schema_id
        self.violations = violations

    def payload(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "schema_id": self.schema_id,
            "violations": [
                {"pointer": v.pointer, "message": v.message, "validator": v.validator}
                for v in self.violations
            ],
        }


class PackageIntegrityError(AtsError):
    """The imported normative package does not match its manifest."""

    code = "package_integrity_failed"


@dataclass(frozen=True, slots=True)
class PolicyConflict:
    """A typed policy conflict (spec Section 6.5: no heuristic winner selection)."""

    rule_id: str
    profiles: tuple[str, ...]
    states: tuple[str, ...]
    detail: str


class PolicyResolutionError(AtsError):
    """Policy resolution failed or produced a typed conflict."""

    code = "policy_resolution_failed"

    def __init__(self, message: str, conflicts: list[PolicyConflict] | None = None) -> None:
        super().__init__(message)
        self.conflicts = conflicts or []

    def payload(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": str(self),
            "conflicts": [
                {
                    "rule_id": c.rule_id,
                    "profiles": list(c.profiles),
                    "states": list(c.states),
                    "detail": c.detail,
                }
                for c in self.conflicts
            ],
        }


class StalePolicyError(AtsError):
    """Policy currentness could not be established (spec Section 14.3)."""

    code = "stale_policy"
    exit_code = 4


class ParseError(AtsError):
    """A parser failed and identified the affected region (spec Section 14.4)."""

    code = "parse_failed"

    def __init__(self, message: str, *, locator: str | None = None, line: int | None = None) -> None:
        super().__init__(message)
        self.locator = locator
        self.line = line

    def payload(self) -> dict[str, Any]:
        data = {"error": self.code, "message": str(self)}
        if self.locator is not None:
            data["locator"] = self.locator
        if self.line is not None:
            data["line"] = self.line
        return data


class ReferenceError_(AtsError):
    """An internal reference in an ATS object does not resolve."""

    code = "dangling_reference"


@dataclass(slots=True)
class ErrorBundle:
    """Accumulates errors when a command must report every failure, not just the first."""

    errors: list[AtsError] = field(default_factory=list)

    def add(self, error: AtsError) -> None:
        self.errors.append(error)

    def __bool__(self) -> bool:
        return bool(self.errors)

    def payload(self) -> list[dict[str, Any]]:
        return [e.payload() for e in self.errors]

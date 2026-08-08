"""Capability declaration.

Spec Sections 5.5 and 16.1 require a machine-readable declaration of what this
implementation actually does, including the detector class and declared
authority per rule and an authority-basis receipt for every detector that
contributes conformance evidence.

The per-rule detail lives in ``capability/ats_rule_capability_v1.json``, which
is authored alongside the detectors and validated against
``ats_rule_capability_v1.schema.json``. This module reads that file, checks it
covers every rule in the registry, and projects it into the normative
``ats.capability.v1`` shape. Two representations, one source: the projection is
derived, never separately maintained.

A loaded spec package MAY publish its own capability file at
``capability/ats_rule_capability_v1.json`` inside its version directory (the
draft.2 package does); when it does, that declaration is authoritative for the
package. Otherwise the repo-root declaration is used, which is the draft.1
default.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Mapping

from . import IMPLEMENTATION_NAME, __version__
from .canonical import load_json
from .errors import UnsupportedCapabilityError, UsageError
from .rules.registry import DETECTOR_CLASS_MAX_AUTHORITY, RuleRegistry
from .schemas import SchemaSet
from .spec_package import REPO_ROOT

CAPABILITY_ROOT: Final[Path] = REPO_ROOT / "capability"
RULE_CAPABILITY_FILE: Final[Path] = CAPABILITY_ROOT / "ats_rule_capability_v1.json"

#: Markup formats this implementation parses (spec Section 16.3).
SUPPORTED_FORMATS: Final[tuple[str, ...]] = ("text/markdown", "application/json")
SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = ("en",)

#: Preservation methods implemented. TRANSFORM preservation requires a source
#: IR and an output IR; the v0 output linter compares a single IR against its
#: rendering, which is declared-representation evidence, not a source-to-output
#: preservation proof.
PRESERVATION_METHODS: Final[tuple[str, ...]] = (
    "p0_exact_declared_rendering",
    "p1_declared_representation",
)

KNOWN_LIMITATIONS: Final[tuple[str, ...]] = (
    "No D2 rule router, D3 semantic critic, or learned detector of any kind is implemented; "
    "rules that require semantic judgement report REVIEW_REQUIRED or UNAVAILABLE.",
    "TRANSFORM preservation (ATS-PRES-001, ATS-PRES-002) requires a source IR, an output IR, "
    "a retention contract, and authorizations; the v0 commands accept none of those inputs, "
    "so both rules report UNAVAILABLE whenever the resolved state is not disabled.",
    "forecast_calibration is always INSUFFICIENT_EVIDENCE: no resolved-forecast cohort, scoring "
    "rule, or reliability analysis is implemented (spec Section 15.5).",
    "semantic_review never reports PASS: this implementation holds no authority to disposition a "
    "finding, and Section 15.3 requires dispositions by an authorized human or a promoted detector.",
    "Rules whose required inputs include source_text, syntax, or document_ast cannot be decided "
    "from a TextIR document alone and report UNAVAILABLE with the missing input named.",
    "Markdown parsing covers CommonMark as implemented by markdown-it-py; unsupported constructs "
    "are reported rather than silently skipped.",
)


@dataclass(frozen=True, slots=True)
class RuleCapability:
    """One rule's declared implementation status."""

    rule_id: str
    implemented: bool
    surfaces: tuple[str, ...]
    detector_class: str
    detector_name: str | None
    decision_power: str
    produces_conformance_evidence: bool
    authority: str
    authority_basis_ref: str | None
    required_inputs: tuple[str, ...]
    available_inputs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    blocking_inputs: tuple[str, ...]
    input_substitutions: tuple[Mapping[str, Any], ...]
    unavailable_conditions: tuple[str, ...]
    known_limits: tuple[str, ...]
    subchecks: tuple[Mapping[str, Any], ...]
    raw: Mapping[str, Any]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RuleCapability:
        return cls(
            rule_id=data["rule_id"],
            implemented=bool(data["implemented"]),
            surfaces=tuple(data.get("surfaces", ())),
            detector_class=data["detector_class"],
            detector_name=data.get("detector_name"),
            decision_power=data["decision_power"],
            produces_conformance_evidence=bool(data["produces_conformance_evidence"]),
            authority=data.get("authority", "none"),
            authority_basis_ref=data.get("authority_basis_ref"),
            required_inputs=tuple(data["required_inputs"]),
            available_inputs=tuple(data["available_inputs"]),
            missing_inputs=tuple(data.get("missing_inputs", ())),
            blocking_inputs=tuple(data.get("blocking_inputs", ())),
            input_substitutions=tuple(data.get("input_substitutions", ())),
            unavailable_conditions=tuple(data["unavailable_conditions"]),
            known_limits=tuple(data["known_limits"]),
            subchecks=tuple(data.get("subchecks", ())),
            raw=data,
        )

    def missing_for(self, surface: str) -> tuple[str, ...]:
        """Required inputs this surface cannot supply at all."""
        if surface not in self.surfaces:
            return self.required_inputs
        return self.blocking_inputs


class CapabilityDeclaration:
    """Loaded per-rule capability plus the normative projection."""

    def __init__(self, registry: RuleRegistry, path: Path | None = None) -> None:
        self.registry = registry
        self.path = path if path is not None else RULE_CAPABILITY_FILE

    @functools.cached_property
    def document(self) -> Mapping[str, Any]:
        if not self.path.is_file():
            raise UsageError(
                f"capability declaration not found at {self.path}; "
                "an implementation MUST publish one (spec 5.5)"
            )
        return load_json(self.path)

    @functools.cached_property
    def rules(self) -> dict[str, RuleCapability]:
        out: dict[str, RuleCapability] = {}
        for record in self.document["rules"]:
            cap = RuleCapability.from_dict(record)
            if cap.rule_id in out:
                raise UsageError(f"duplicate capability entry for {cap.rule_id}")
            out[cap.rule_id] = cap
        return out

    def for_rule(self, rule_id: str) -> RuleCapability:
        try:
            return self.rules[rule_id]
        except KeyError:
            raise UnsupportedCapabilityError(
                f"rule:{rule_id}",
                "no capability declared for this rule; unsupported rules MUST be reported "
                "as UNAVAILABLE when required by the active policy (spec 5.5)",
            ) from None

    # -- coherence ---------------------------------------------------------

    def coherence_errors(self) -> list[str]:
        """Every way the declaration could lie about what the code does.

        Checked at import time by the CLI and asserted by the test suite, so a
        detector cannot quietly gain or lose capability without the declaration
        moving with it.
        """
        problems: list[str] = []
        declared = set(self.rules)
        registered = set(self.registry.ids())
        for missing in sorted(registered - declared):
            problems.append(f"{missing}: rule in the registry has no capability declaration")
        for extra in sorted(declared - registered):
            problems.append(f"{extra}: capability declared for a rule not in the registry")
        for rule_id in sorted(declared & registered):
            cap = self.rules[rule_id]
            rule = self.registry.get(rule_id)
            if tuple(cap.required_inputs) != tuple(rule.required_inputs):
                problems.append(
                    f"{rule_id}: declared required_inputs {list(cap.required_inputs)} "
                    f"differ from the registry's {list(rule.required_inputs)}"
                )
            if cap.detector_class != "none" and cap.detector_class not in rule.detector_classes:
                problems.append(
                    f"{rule_id}: detector_class {cap.detector_class} is not among the "
                    f"registry's detector_classes {list(rule.detector_classes)}"
                )
            if cap.detector_class != "none":
                ceiling = DETECTOR_CLASS_MAX_AUTHORITY[cap.detector_class]
                if cap.authority == "conformance_evidence" and ceiling != "conformance_evidence":
                    problems.append(
                        f"{rule_id}: class {cap.detector_class} may not carry "
                        "conformance_evidence authority"
                    )
            # `produces_conformance_evidence` describes what a RAISED finding
            # establishes. It is orthogonal to decision power, which describes
            # what the ABSENCE of a finding establishes (spec Section 12.3).
            if cap.produces_conformance_evidence and cap.authority != "conformance_evidence":
                problems.append(
                    f"{rule_id}: claims conformance evidence but declares authority "
                    f"{cap.authority!r}"
                )
            if cap.produces_conformance_evidence and not cap.authority_basis_ref:
                problems.append(f"{rule_id}: conformance evidence declared without authority_basis_ref")
            if cap.decision_power == "decides" and cap.authority != "conformance_evidence":
                problems.append(
                    f"{rule_id}: declares a complete decision procedure while its authority is "
                    f"{cap.authority!r}; such a detector can never report PASS, so declaring "
                    "'decides' overstates it"
                )
            unsupplied = set(cap.required_inputs) - set(cap.available_inputs)
            if set(cap.missing_inputs) != unsupplied:
                problems.append(
                    f"{rule_id}: missing_inputs {sorted(cap.missing_inputs)} does not equal "
                    f"required_inputs minus available_inputs {sorted(unsupplied)}"
                )
            substituted = {s["input"] for s in cap.input_substitutions}
            if not substituted <= unsupplied:
                problems.append(
                    f"{rule_id}: substitutions declared for inputs that are not missing: "
                    f"{sorted(substituted - unsupplied)}"
                )
            if set(cap.blocking_inputs) != unsupplied - substituted:
                problems.append(
                    f"{rule_id}: blocking_inputs {sorted(cap.blocking_inputs)} does not equal "
                    f"missing_inputs minus substituted inputs "
                    f"{sorted(unsupplied - substituted)}"
                )
            if cap.implemented and cap.blocking_inputs:
                problems.append(
                    f"{rule_id}: declared implemented while {sorted(cap.blocking_inputs)} are "
                    "unavailable; such a detector can only ever return UNAVAILABLE, so it must "
                    "declare itself undecidable or declare a substitution"
                )
            if cap.decision_power == "undecidable" and not cap.blocking_inputs:
                problems.append(
                    f"{rule_id}: declared undecidable but names no blocking input; an "
                    "undecidable rule must say what it lacks"
                )
            if not cap.implemented and cap.surfaces:
                problems.append(f"{rule_id}: unimplemented rule declares surfaces {list(cap.surfaces)}")
        return problems

    def require_coherent(self) -> None:
        problems = self.coherence_errors()
        if problems:
            raise UsageError(
                "capability declaration is incoherent with the rule registry:\n  "
                + "\n  ".join(problems)
            )

    # -- normative projection ---------------------------------------------

    def to_normative(self, *, spec_version: str, schema_versions: list[str]) -> dict[str, Any]:
        """Project into an ``ats.capability.v1`` document."""
        rules: list[dict[str, Any]] = []
        for rule_id in self.registry.ids():
            cap = self.rules[rule_id]
            rule = self.registry.get(rule_id)
            classes = [cap.detector_class] if cap.detector_class != "none" else []
            entry: dict[str, Any] = {
                "rule_id": rule_id,
                "detector_classes": classes,
                "autofix": rule.autofix if cap.implemented else "none",
                "authority_by_class": (
                    {cap.detector_class: cap.authority}
                    if classes and cap.authority != "none"
                    else {"D0": "candidate_only"}
                ),
            }
            if cap.authority_basis_ref and classes:
                entry["authority_basis_refs"] = {cap.detector_class: cap.authority_basis_ref}
            rules.append(entry)
        return {
            "schema_version": "ats.capability.v1",
            "implementation_name": IMPLEMENTATION_NAME,
            "implementation_version": __version__,
            "ats_versions": [spec_version],
            "schema_versions": sorted(schema_versions),
            "profiles": ["ASSESS", "SPECIFY", "TRANSFORM"],
            "rules": rules,
            "languages": list(SUPPORTED_LANGUAGES),
            "formats": list(SUPPORTED_FORMATS),
            "autofix_classes": [],
            "preservation_methods": list(PRESERVATION_METHODS),
            "deterministic_replay": True,
            "known_limitations": list(KNOWN_LIMITATIONS),
        }


def load_capability(
    registry: RuleRegistry,
    schemas: SchemaSet,
    package_root: Path | None = None,
) -> CapabilityDeclaration:
    """Load and validate the per-rule capability declaration.

    Resolution order: when ``package_root`` names a loaded spec package whose
    version directory contains ``capability/ats_rule_capability_v1.json``, that
    package-relative file is authoritative; otherwise the repo-root capability
    file is used. The draft.1 default keeps the repo-root file.
    """
    path = RULE_CAPABILITY_FILE
    if package_root is not None:
        package_file = package_root / "capability" / RULE_CAPABILITY_FILE.name
        if package_file.is_file():
            path = package_file
    declaration = CapabilityDeclaration(registry, path=path)
    schemas.validate(declaration.document, "ats_rule_capability_v1.schema.json")
    declaration.require_coherent()
    return declaration

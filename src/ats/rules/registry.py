"""The normative rule registry, as a typed read-only view.

``rules/ats_rules_v1.yaml`` is authoritative. This module indexes it; it never
restates a rule's normative statement, severity, or default states in Python.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any, Final, Mapping

from ..errors import UsageError
from ..spec_package import SpecPackage

#: Detector classes and what authority they may carry (spec Sections 12.3, 16.5,
#: and the ``detector`` definition in ats_common_v1.schema.json).
DETECTOR_CLASS_MAX_AUTHORITY: Final[dict[str, str]] = {
    "D0": "conformance_evidence",
    "D1": "conformance_evidence",
    "D2": "candidate_only",
    "D3": "proposal_only",
    "D4": "conformance_evidence",
}


@dataclass(frozen=True, slots=True)
class Rule:
    """One ``ats.rule.v1`` record."""

    rule_id: str
    rule_version: str
    title: str
    category: str
    normative_statement: str
    rationale: str
    default_states: Mapping[str, str]
    severity: str
    detector_classes: tuple[str, ...]
    required_inputs: tuple[str, ...]
    protected_impact: tuple[str, ...]
    autofix: str
    waivable: bool
    exceptions: tuple[str, ...]
    fixture_requirements: tuple[str, ...]
    raw: Mapping[str, Any]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Rule:
        return cls(
            rule_id=data["rule_id"],
            rule_version=data["rule_version"],
            title=data["title"],
            category=data["category"],
            normative_statement=data["normative_statement"],
            rationale=data["rationale"],
            default_states=dict(data["default_states"]),
            severity=data["severity"],
            detector_classes=tuple(data["detector_classes"]),
            required_inputs=tuple(data["required_inputs"]),
            protected_impact=tuple(data["protected_impact"]),
            autofix=data["autofix"],
            waivable=bool(data["waivable"]),
            exceptions=tuple(data.get("exceptions", ())),
            fixture_requirements=tuple(data["fixture_requirements"]),
            raw=data,
        )


class RuleRegistry:
    """Indexed access to the 30-rule v0 registry."""

    def __init__(self, package: SpecPackage) -> None:
        self.package = package

    @functools.cached_property
    def document(self) -> Mapping[str, Any]:
        return self.package.ruleset

    @functools.cached_property
    def rules(self) -> dict[str, Rule]:
        out: dict[str, Rule] = {}
        for record in self.document["rules"]:
            rule = Rule.from_dict(record)
            if rule.rule_id in out:
                raise UsageError(f"duplicate rule id in registry: {rule.rule_id}")
            out[rule.rule_id] = rule
        return out

    @functools.cached_property
    def raw_rules(self) -> dict[str, Mapping[str, Any]]:
        """Raw rule records, for :class:`~ats.policy.PolicySnapshot`."""
        return {r.rule_id: r.raw for r in self.rules.values()}

    @property
    def spec_version(self) -> str:
        return self.document["spec_version"]

    def __iter__(self):
        return iter(self.rules.values())

    def __len__(self) -> int:
        return len(self.rules)

    def __contains__(self, rule_id: object) -> bool:
        return rule_id in self.rules

    def get(self, rule_id: str) -> Rule:
        try:
            return self.rules[rule_id]
        except KeyError:
            raise UsageError(
                f"unknown rule id {rule_id!r}; rule identifiers are immutable and "
                "a retired identifier MUST NOT be reused (spec 18.1)"
            ) from None

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.rules))

    def by_category(self, category: str) -> tuple[Rule, ...]:
        return tuple(r for r in self.rules.values() if r.category == category)


class ForceLexicon:
    """Typed access to the calibrated force lexicon.

    Every vocabulary this implementation matches against comes from here or
    from an enumerated list in the specification. No detector invents a term
    list of its own.
    """

    def __init__(self, package: SpecPackage) -> None:
        self.package = package

    @functools.cached_property
    def document(self) -> Mapping[str, Any]:
        return self.package.force_lexicon

    @property
    def version(self) -> str:
        return self.document["spec_version"]

    @functools.cached_property
    def wep_terms(self) -> dict[str, Mapping[str, Any]]:
        return {t["id"]: t for t in self.document["likelihood"]["terms"]}

    @functools.cached_property
    def wep_phrases(self) -> dict[str, str]:
        """Canonical phrase -> term id."""
        return {t["phrase"]: t["id"] for t in self.document["likelihood"]["terms"]}

    @functools.cached_property
    def wep_aliases(self) -> dict[str, str]:
        """Noncanonical input alias -> canonical term id (spec Section 8.3)."""
        out: dict[str, str] = {}
        for term in self.document["likelihood"]["terms"]:
            for alias in term.get("input_aliases", ()):
                out[alias] = term["id"]
        return out

    @property
    def non_probability_terms(self) -> tuple[str, ...]:
        return tuple(self.document["likelihood"]["non_probability_terms"])

    @property
    def first_use_must_show_range(self) -> bool:
        return bool(self.document["likelihood"]["first_material_use_must_show_range"])

    @property
    def confidence_levels(self) -> tuple[str, ...]:
        return tuple(t["id"] for t in self.document["assessment_confidence"]["terms"])

    @property
    def basis_dimensions(self) -> Mapping[str, list[str]]:
        return self.document["assessment_confidence"]["basis_dimensions"]

    @property
    def evidential_terms(self) -> tuple[str, ...]:
        return tuple(t["id"] for t in self.document["evidential_force"]["terms"])

    @property
    def causal_terms(self) -> tuple[str, ...]:
        return tuple(t["id"] for t in self.document["causal_force"]["terms"])

    @property
    def causal_untyped_candidates(self) -> tuple[str, ...]:
        return tuple(self.document["causal_force"].get("untyped_candidates", ()))

    @functools.cached_property
    def deontic_surfaces(self) -> dict[str, str]:
        """Deontic id -> the exact surface form that must appear in text."""
        out: dict[str, str] = {}
        for term in self.document["deontic_force"]["terms"]:
            out[term["id"]] = term.get("surface", term["id"])
        return out

    @property
    def deontic_noncanonical(self) -> tuple[str, ...]:
        return tuple(self.document["deontic_force"].get("noncanonical", ()))

    @property
    def collision_rules(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.document.get("collision_rules", ()))

    def interval_for(self, term_id: str) -> tuple[float, float, bool]:
        """``(lower, upper, upper_inclusive)`` for a canonical WEP term."""
        term = self.wep_terms.get(term_id)
        if term is None:
            raise UsageError(f"{term_id!r} is not a canonical ATS-1 WEP term")
        return float(term["lower"]), float(term["upper"]), bool(term["upper_inclusive"])

    def display_range(self, term_id: str) -> str:
        term = self.wep_terms.get(term_id)
        if term is None:
            raise UsageError(f"{term_id!r} is not a canonical ATS-1 WEP term")
        return str(term["display_range"])

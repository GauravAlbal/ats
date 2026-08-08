"""Typed, indexed views over a schema-valid ``ats.text_ir.v1`` document.

These are *views*, not a second schema. Every accessor reads the validated
document; nothing here declares which fields exist or are required — that lives
in the imported JSON Schema and would drift if restated (constitution #5).

The views exist so detectors address claims, evidence, and relations by
identity and position rather than by re-walking nested dictionaries, and so
every finding can name a deterministic JSON Pointer into the source document.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Sequence

from ..canonical import canonical_bytes, sha256_hex
from ..context import Context
from ..errors import UsageError
from ..policy import PolicySnapshot, RuleState
from ..rules.results import Detector, Finding

#: Kinds of identified object inside a TextIR section.
OBJECT_KINDS = ("claim", "evidence", "relation", "update_indicator")


def pointer(*parts: Any) -> str:
    """Build a JSON Pointer from path segments (RFC 6901 escaping)."""
    out = []
    for part in parts:
        text = str(part).replace("~", "~0").replace("/", "~1")
        out.append(text)
    return "/" + "/".join(out)


def json_pointer_span(ptr: str) -> dict[str, str]:
    """A ``span`` object addressing a location inside the IR document."""
    return {"kind": "json_pointer", "locator": ptr}


@dataclass(frozen=True, slots=True)
class ClaimView:
    section_id: str
    section_index: int
    index: int
    data: Mapping[str, Any]

    @property
    def claim_id(self) -> str:
        return self.data["claim_id"]

    @property
    def role(self) -> str:
        return self.data["role"]

    @property
    def proposition(self) -> str:
        return self.data["proposition"]

    @property
    def material(self) -> bool:
        return bool(self.data["material"])

    @property
    def polarity(self) -> str:
        return self.data["polarity"]

    @property
    def status(self) -> str:
        return self.data["status"]

    @property
    def force(self) -> Mapping[str, Any]:
        return self.data.get("force", {})

    @property
    def likelihood(self) -> Mapping[str, Any] | None:
        return self.force.get("likelihood")

    @property
    def assessment_confidence(self) -> Mapping[str, Any] | None:
        return self.force.get("assessment_confidence")

    @property
    def deontic(self) -> str | None:
        return self.force.get("deontic")

    @property
    def quantifier(self) -> Mapping[str, Any] | None:
        return self.data.get("quantifier")

    @property
    def scope(self) -> Mapping[str, Any]:
        return self.data.get("scope", {})

    @property
    def requirement(self) -> Mapping[str, Any] | None:
        return self.data.get("requirement")

    @property
    def forecast(self) -> Mapping[str, Any] | None:
        return self.data.get("forecast")

    @property
    def interpretations(self) -> Sequence[str]:
        return self.data.get("interpretations", ())

    def refs(self, name: str) -> Sequence[str]:
        return self.data.get(name, ())

    @property
    def pointer(self) -> str:
        return pointer("sections", self.section_index, "claims", self.index)

    def field_pointer(self, *parts: Any) -> str:
        return self.pointer + pointer(*parts)

    def span(self) -> dict[str, Any]:
        """Prefer the claim's declared source span; fall back to its pointer."""
        declared = self.data.get("span")
        if declared:
            return dict(declared)
        return json_pointer_span(self.pointer)


@dataclass(frozen=True, slots=True)
class EvidenceView:
    section_id: str
    section_index: int
    index: int
    data: Mapping[str, Any]

    @property
    def evidence_id(self) -> str:
        return self.data["evidence_id"]

    @property
    def proposition(self) -> str:
        return self.data["proposition"]

    @property
    def source(self) -> Mapping[str, Any]:
        return self.data["source"]

    @property
    def availability(self) -> str:
        return self.data["availability"]

    @property
    def pointer(self) -> str:
        return pointer("sections", self.section_index, "evidence", self.index)

    def span(self) -> dict[str, Any]:
        declared = self.data.get("span")
        if declared:
            return dict(declared)
        return json_pointer_span(self.pointer)


@dataclass(frozen=True, slots=True)
class RelationView:
    section_id: str
    section_index: int
    index: int
    data: Mapping[str, Any]

    @property
    def relation_id(self) -> str:
        return self.data["relation_id"]

    @property
    def source_id(self) -> str:
        return self.data["source_id"]

    @property
    def target_id(self) -> str:
        return self.data["target_id"]

    @property
    def type(self) -> str:
        return self.data["type"]

    @property
    def material(self) -> bool:
        return bool(self.data["material"])

    @property
    def basis_refs(self) -> Sequence[str]:
        return self.data.get("basis_refs", ())

    @property
    def notes(self) -> str | None:
        """Free-text note on the relation.

        Optional in ``ats_common_v1#/$defs/relation``. For an ``updates`` or
        ``reverses`` relation it is one of the two ways the artifact can record
        what changed (spec Section 7.14), the other being ``basis_refs``.
        """
        return self.data.get("notes")

    @property
    def scope(self) -> Mapping[str, Any]:
        return self.data.get("scope", {})

    @property
    def pointer(self) -> str:
        return pointer("sections", self.section_index, "relations", self.index)

    def span(self) -> dict[str, Any]:
        return json_pointer_span(self.pointer)


@dataclass(frozen=True, slots=True)
class IndicatorView:
    section_id: str
    section_index: int
    index: int
    data: Mapping[str, Any]

    @property
    def indicator_id(self) -> str:
        return self.data["indicator_id"]

    @property
    def text(self) -> str:
        return self.data["text"]

    @property
    def target_claim_refs(self) -> Sequence[str]:
        return self.data["target_claim_refs"]

    @property
    def effect(self) -> str | None:
        return self.data.get("effect")

    @property
    def pointer(self) -> str:
        return pointer("sections", self.section_index, "update_indicators", self.index)

    def span(self) -> dict[str, Any]:
        return json_pointer_span(self.pointer)


@dataclass(frozen=True, slots=True)
class SectionView:
    index: int
    data: Mapping[str, Any]
    claims: tuple[ClaimView, ...]
    evidence: tuple[EvidenceView, ...]
    relations: tuple[RelationView, ...]
    update_indicators: tuple[IndicatorView, ...]

    @property
    def section_id(self) -> str:
        return self.data["section_id"]

    @property
    def heading(self) -> str | None:
        return self.data.get("heading")

    @property
    def profiles(self) -> tuple[str, ...]:
        return tuple(self.data["profiles"])

    @property
    def pointer(self) -> str:
        return pointer("sections", self.index)

    def span(self) -> dict[str, Any]:
        declared = self.data.get("span")
        if declared:
            return dict(declared)
        return json_pointer_span(self.pointer)

    def material_claims(self) -> tuple[ClaimView, ...]:
        return tuple(c for c in self.claims if c.material)

    def claims_with_role(self, *roles: str) -> tuple[ClaimView, ...]:
        return tuple(c for c in self.claims if c.role in roles)


# No ``slots``: this view caches derived indexes with ``functools.cached_property``.
@dataclass
class IrDocument:
    """An indexed view over one validated TextIR document."""

    raw: Mapping[str, Any]
    sections: tuple[SectionView, ...]

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> IrDocument:
        if document.get("schema_version") != "ats.text_ir.v1":
            raise UsageError(
                f"expected ats.text_ir.v1, got {document.get('schema_version')!r}"
            )
        sections: list[SectionView] = []
        for si, sec in enumerate(document["sections"]):
            sid = sec["section_id"]
            sections.append(
                SectionView(
                    index=si,
                    data=sec,
                    claims=tuple(
                        ClaimView(sid, si, i, c) for i, c in enumerate(sec.get("claims", ()))
                    ),
                    evidence=tuple(
                        EvidenceView(sid, si, i, e) for i, e in enumerate(sec.get("evidence", ()))
                    ),
                    relations=tuple(
                        RelationView(sid, si, i, r) for i, r in enumerate(sec.get("relations", ()))
                    ),
                    update_indicators=tuple(
                        IndicatorView(sid, si, i, u)
                        for i, u in enumerate(sec.get("update_indicators", ()))
                    ),
                )
            )
        return cls(raw=document, sections=tuple(sections))

    # -- identity ----------------------------------------------------------

    @property
    def artifact_id(self) -> str:
        return self.raw["artifact_id"]

    @property
    def policy_snapshot_id(self) -> str:
        return self.raw["policy_snapshot_id"]

    @property
    def audience(self) -> Mapping[str, Any]:
        return self.raw["audience"]

    @property
    def source(self) -> Mapping[str, Any]:
        return self.raw["source"]

    @property
    def extraction_status(self) -> str:
        return self.raw["extraction_status"]

    @property
    def extraction_issues(self) -> Sequence[Mapping[str, Any]]:
        return self.raw.get("extraction_issues", ())

    @property
    def glossary(self) -> Sequence[Mapping[str, Any]]:
        return self.raw.get("glossary", ())

    @property
    def stable_coordinates(self) -> tuple[Mapping[str, Any], ...]:
        """Document-declared stable semantic coordinates (draft.2 D-C, spec 7.17).

        Each entry is ``{kind, id, source_pointer}`` with ``kind`` one of the
        eight protected coordinate kinds from spec Section 4.23.
        """
        return tuple(self.raw.get("stable_coordinates", ()))

    @property
    def basis_policy(self) -> Mapping[str, Any] | None:
        """Document-level basis policy, when declared (draft.2 D-F, spec 7.5)."""
        return self.raw.get("basis_policy")

    @functools.cached_property
    def ir_sha256(self) -> str:
        """Content address over the JCS-canonical bytes of the whole document."""
        return sha256_hex(canonical_bytes(self.raw))

    @functools.cached_property
    def profiles(self) -> tuple[str, ...]:
        seen: list[str] = []
        for section in self.sections:
            for profile in section.profiles:
                if profile not in seen:
                    seen.append(profile)
        return tuple(seen)

    # -- indexes -----------------------------------------------------------

    @functools.cached_property
    def claims(self) -> dict[str, ClaimView]:
        return {c.claim_id: c for s in self.sections for c in s.claims}

    @functools.cached_property
    def evidence(self) -> dict[str, EvidenceView]:
        return {e.evidence_id: e for s in self.sections for e in s.evidence}

    @functools.cached_property
    def relations(self) -> dict[str, RelationView]:
        return {r.relation_id: r for s in self.sections for r in s.relations}

    @functools.cached_property
    def indicators(self) -> dict[str, IndicatorView]:
        return {u.indicator_id: u for s in self.sections for u in s.update_indicators}

    @functools.cached_property
    def glossary_by_concept(self) -> dict[str, Mapping[str, Any]]:
        return {g["concept_id"]: g for g in self.glossary}

    @functools.cached_property
    def object_ids(self) -> dict[str, str]:
        """Every identified object -> its kind. Duplicates are a linter finding,
        not an exception, so the last writer wins here and
        :meth:`duplicate_ids` reports the collision."""
        out: dict[str, str] = {}
        for section in self.sections:
            for c in section.claims:
                out[c.claim_id] = "claim"
            for e in section.evidence:
                out[e.evidence_id] = "evidence"
            for r in section.relations:
                out[r.relation_id] = "relation"
            for u in section.update_indicators:
                out[u.indicator_id] = "update_indicator"
        return out

    def duplicate_ids(self) -> list[tuple[str, list[str]]]:
        """Identifiers used more than once, with the pointers that use them.

        Three id spaces are tracked separately because a claim id, its
        requirement id, and a declared coordinate for it routinely coincide
        (spec 7.17); those coincidences are references to one object, not
        collisions. The spaces are:

        * object ids (claims, evidence, relations, update indicators, sections);
        * declared stable-coordinate ids (same id twice in the block, any kind);
        * protected-coordinate uses (``requirement_id`` / ``decision_id`` /
          ``acceptance_criterion_id``), which must be unique across sections.
        """
        seen: dict[str, list[str]] = {}
        for section in self.sections:
            seen.setdefault(section.section_id, []).append(section.pointer)
            for c in section.claims:
                seen.setdefault(c.claim_id, []).append(c.pointer)
            for e in section.evidence:
                seen.setdefault(e.evidence_id, []).append(e.pointer)
            for r in section.relations:
                seen.setdefault(r.relation_id, []).append(r.pointer)
            for u in section.update_indicators:
                seen.setdefault(u.indicator_id, []).append(u.pointer)
        duplicates = [(k, v) for k, v in sorted(seen.items()) if len(v) > 1]

        declared_coordinates: dict[str, list[str]] = {}
        for i, entry in enumerate(self.stable_coordinates):
            cid = entry.get("id")
            if cid is None:
                continue
            declared_coordinates.setdefault(cid, []).append(
                pointer("stable_coordinates", i, "id")
            )
        duplicates += [
            (k, v) for k, v in sorted(declared_coordinates.items()) if len(v) > 1
        ]

        uses: dict[str, list[str]] = {}
        for claim in self.all_claims():
            requirement = claim.requirement
            if requirement is not None:
                rid = requirement.get("requirement_id")
                if rid:
                    uses.setdefault(rid, []).append(
                        claim.field_pointer("requirement", "requirement_id")
                    )
                ac_id = requirement.get("acceptance_criterion_id")
                if ac_id:
                    uses.setdefault(ac_id, []).append(
                        claim.field_pointer("requirement", "acceptance_criterion_id")
                    )
            decision_id = claim.data.get("decision_id")
            if decision_id:
                uses.setdefault(decision_id, []).append(
                    claim.field_pointer("decision_id")
                )
        duplicates += [(k, v) for k, v in sorted(uses.items()) if len(v) > 1]
        return sorted(duplicates)

    def relations_targeting(self, object_id: str) -> tuple[RelationView, ...]:
        return tuple(r for r in self.relations.values() if r.target_id == object_id)

    def relations_from(self, object_id: str) -> tuple[RelationView, ...]:
        return tuple(r for r in self.relations.values() if r.source_id == object_id)

    def indicators_targeting(self, claim_id: str) -> tuple[IndicatorView, ...]:
        return tuple(u for u in self.indicators.values() if claim_id in u.target_claim_refs)

    def all_claims(self) -> Iterator[ClaimView]:
        for section in self.sections:
            yield from section.claims

    def material_claims(self) -> Iterator[ClaimView]:
        for claim in self.all_claims():
            if claim.material:
                yield claim

    def section_for(self, section_id: str) -> SectionView:
        for section in self.sections:
            if section.section_id == section_id:
                return section
        raise UsageError(f"no section {section_id!r}")


@dataclass(slots=True)
class IrEvaluation:
    """Everything a detector needs, plus deterministic finding identity."""

    ctx: Context
    ir: IrDocument
    policy: PolicySnapshot
    states: Mapping[str, RuleState]
    _counters: dict[str, int] = field(default_factory=dict)

    @property
    def artifact_id(self) -> str:
        return self.ir.artifact_id

    @property
    def profiles(self) -> tuple[str, ...]:
        return self.ir.profiles

    def state_for(self, rule_id: str) -> RuleState:
        try:
            return self.states[rule_id]
        except KeyError:
            raise UsageError(f"no resolved state for rule {rule_id!r}") from None

    def finding_id(self, rule_id: str, issue_code: str) -> str:
        """Deterministic finding identity.

        Spec Section 16.2 requires identical results for identical canonical
        inputs, so identity is a function of the artifact, rule, issue code, and
        the ordinal of this issue within the run, never of a clock or a UUID.
        """
        key = f"{rule_id}:{issue_code}"
        ordinal = self._counters.get(key, 0)
        self._counters[key] = ordinal + 1
        return f"{self.ir.artifact_id}:{rule_id}:{issue_code}:{ordinal:03d}"

    def finding(
        self,
        *,
        rule_id: str,
        issue_code: str,
        summary: str,
        spans: Sequence[Mapping[str, Any]],
        detector: Detector,
        profile: str | None = None,
        evidence_spans: Sequence[Mapping[str, Any]] = (),
        interpretations: Sequence[Mapping[str, Any]] = (),
        applicability: str = "applies",
        abstention_reason: str | None = None,
        severity: str | None = None,
        protected_impact: Sequence[str] | None = None,
    ) -> Finding:
        """Build a finding bound to the rule registry's own severity and impact."""
        rule = self.ctx.registry.get(rule_id)
        state = self.state_for(rule_id)
        return Finding(
            finding_id=self.finding_id(rule_id, issue_code),
            artifact_id=self.ir.artifact_id,
            policy_snapshot_id=self.policy.snapshot_id,
            rule_id=rule_id,
            rule_version=rule.rule_version,
            profile=profile or state.profile,
            spans=tuple(dict(s) for s in spans),
            issue_code=issue_code,
            summary=summary,
            severity=severity or rule.severity,
            detector=detector,
            applicability=applicability,
            protected_impact=tuple(protected_impact or rule.protected_impact),
            evidence_spans=tuple(dict(s) for s in evidence_spans),
            interpretations=tuple(dict(i) for i in interpretations),
            abstention_reason=abstention_reason,
        )

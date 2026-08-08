"""Synthetic mutation of TextIR documents, one semantic feature at a time.

Spec Section 17.5: a synthetic mutation SHOULD change one semantic feature at a
time and MUST be tagged, and it MUST NOT be counted as independent real-world
evidence of rule prevalence or user value. This module enforces all three:

* every applier performs exactly one edit against one JSON Pointer, and the
  pointer, the old value, and the new value are recorded;
* the mutant is emitted as a ``TextExampleV1`` with ``synthetic: true`` and
  ``provenance: synthetic_mutation``, which :mod:`ats.corpus.records` refuses to
  contradict;
* the source example is preserved verbatim in the result, and the mutant
  inherits its ``split_group`` so the pair can never be separated by a split
  (spec Section 17.7).

An operator declared ``supported: false`` in
``corpus/operators/ats_mutation_operators_v1.yaml`` raises
:class:`~ats.errors.UnsupportedCapabilityError`. It is never approximated: spec
Section 5.5 requires an unsupported capability to be reported, not emulated by
a weaker component holding the same claim.
"""

from __future__ import annotations

import copy
import functools
from pathlib import Path
from typing import Any, Callable, Final, Mapping, Sequence

import yaml

from ..canonical import content_hash
from ..errors import UnsupportedCapabilityError, UsageError
from ..spec_package import REPO_ROOT
from . import records as rec

#: The operator registry this repository ships.
OPERATOR_REGISTRY_PATH: Final[Path] = (
    REPO_ROOT / "corpus" / "operators" / "ats_mutation_operators_v1.yaml"
)

#: Relation types whose direction is asserted, and which therefore change
#: meaning when reversed. Taken from the relation enum in ats_common_v1;
#: consistent_with, alternative_to, and contrasts_with are symmetric and absent.
DIRECTIONAL_RELATIONS: Final[tuple[str, ...]] = (
    "supports",
    "strongly_supports",
    "contradicts",
    "qualifies",
    "depends_on",
    "condition_for",
    "exception_to",
    "derived_from",
    "associated_with",
    "predicts",
    "contributes_to",
    "causes",
    "necessary_for",
    "sufficient_for",
    "updates",
    "reverses",
)

#: Relation types that declare a live alternative or a contrary reading
#: (spec Sections 9.2.7, 9.2.8).
CONTRARY_RELATIONS: Final[tuple[str, ...]] = ("contradicts", "alternative_to", "contrasts_with")

#: Quantifier kinds whose number carries a unit (spec Section 10.9).
UNIT_BEARING_QUANTIFIERS: Final[tuple[str, ...]] = (
    "exact_count",
    "minimum",
    "maximum",
    "range",
    "proportion",
)

#: The deontic exchange cycle. Every step stays inside the closed vocabulary of
#: ``deontic_force.terms`` and, for requirement-role claims, inside
#: ``requirement_slots.deontic``, which has no CAN.
DEONTIC_CYCLE: Final[dict[str, str]] = {
    "MUST": "SHOULD",
    "SHOULD": "MAY",
    "MAY": "MUST",
    "MUST_NOT": "SHOULD_NOT",
    "SHOULD_NOT": "MUST_NOT",
    "CAN": "MAY",
    "CANNOT": "MUST_NOT",
}

#: Deontic values a requirement slot may hold.
REQUIREMENT_DEONTICS: Final[frozenset[str]] = frozenset(
    {"MUST", "MUST_NOT", "SHOULD", "SHOULD_NOT", "MAY"}
)


class Mutation:
    """One applied edit, in the shape the transformation record needs."""

    __slots__ = ("pointer", "old_value", "new_value", "detail")

    def __init__(self, pointer: str, old_value: Any, new_value: Any, detail: str) -> None:
        self.pointer = pointer
        self.old_value = old_value
        self.new_value = new_value
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_pointer": self.pointer,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "detail": self.detail,
        }


#: An applier mutates a deep copy of the IR in place and returns the edit.
Applier = Callable[[dict[str, Any], Any], Mutation]

APPLIERS: dict[str, Applier] = {}


def applier(operator_id: str) -> Callable[[Applier], Applier]:
    def register(fn: Applier) -> Applier:
        APPLIERS[operator_id] = fn
        return fn

    return register


def _unmet(operator_id: str, precondition: str) -> UsageError:
    return UsageError(
        f"{operator_id} cannot be applied: {precondition}. A mutation whose precondition is "
        "unmet is refused rather than approximated (spec 17.5)."
    )


def _sections(ir: dict[str, Any]):
    return enumerate(ir["sections"])


# -- appliers ---------------------------------------------------------------


@applier("ATS-MUT-QUAL-DELETE")
def _qual_delete(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            condition = (claim.get("scope") or {}).get("condition")
            if claim.get("material") and condition:
                del claim["scope"]["condition"]
                return Mutation(
                    f"/sections/{si}/claims/{ci}/scope/condition",
                    condition,
                    None,
                    "the qualifying condition was deleted from the claim's scope",
                )
    raise _unmet("ATS-MUT-QUAL-DELETE", "no material claim declares a scope condition")


@applier("ATS-MUT-WEP-BAND-SHIFT")
def _wep_band_shift(ir: dict[str, Any], lexicon: Any) -> Mutation:
    order = list(lexicon.wep_terms)
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            likelihood = (claim.get("force") or {}).get("likelihood") or {}
            term = likelihood.get("term")
            if not claim.get("material") or likelihood.get("kind") != "wep" or term not in order:
                continue
            index = order.index(term)
            adjacent = order[index + 1] if index + 1 < len(order) else order[index - 1]
            likelihood["term"] = adjacent
            return Mutation(
                f"/sections/{si}/claims/{ci}/force/likelihood/term",
                term,
                adjacent,
                f"the band moved to the adjacent lexicon term while lower={likelihood['lower']} "
                f"and upper={likelihood['upper']} stayed at the source band",
            )
    raise _unmet("ATS-MUT-WEP-BAND-SHIFT", "no material claim carries a canonical WEP likelihood")


@applier("ATS-MUT-WEP-RANGE-STRIP")
def _wep_range_strip(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            likelihood = (claim.get("force") or {}).get("likelihood") or {}
            if likelihood.get("kind") != "wep" or not likelihood.get("range_shown_inline"):
                continue
            display = likelihood.pop("display", None)
            likelihood["range_shown_inline"] = False
            return Mutation(
                f"/sections/{si}/claims/{ci}/force/likelihood/range_shown_inline",
                True,
                False,
                f"the inline display {display!r} was removed while the band was preserved",
            )
    raise _unmet("ATS-MUT-WEP-RANGE-STRIP", "no claim shows a WEP range inline")


@applier("ATS-MUT-LIKELIHOOD-CONFIDENCE-SWAP")
def _likelihood_confidence_swap(ir: dict[str, Any], lexicon: Any) -> Mutation:
    levels = set(lexicon.confidence_levels)
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            force = claim.get("force") or {}
            likelihood = force.get("likelihood")
            confidence = force.get("assessment_confidence")
            if not likelihood or not confidence:
                continue
            level = confidence["level"]
            if level not in levels:
                continue
            old = likelihood.get("display")
            likelihood["display"] = f"{level} confidence"
            return Mutation(
                f"/sections/{si}/claims/{ci}/force/likelihood/display",
                old,
                likelihood["display"],
                "the assessment-confidence level now stands where the probability band was "
                "displayed, conflating two different quantities",
            )
    raise _unmet(
        "ATS-MUT-LIKELIHOOD-CONFIDENCE-SWAP",
        "no claim carries both a likelihood and an assessment confidence",
    )


@applier("ATS-MUT-DEONTIC-EXCHANGE")
def _deontic_exchange(ir: dict[str, Any], lexicon: Any) -> Mutation:
    surfaces = lexicon.deontic_surfaces
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            force = claim.get("force") or {}
            current = force.get("deontic")
            if not claim.get("material") or current not in DEONTIC_CYCLE:
                continue
            replacement = DEONTIC_CYCLE[current]
            requirement = claim.get("requirement")
            if requirement is not None and replacement not in REQUIREMENT_DEONTICS:
                continue
            force["deontic"] = replacement
            if requirement is not None:
                requirement["deontic"] = replacement
            old_surface = surfaces.get(current, current)
            new_surface = surfaces.get(replacement, replacement)
            claim["proposition"] = claim["proposition"].replace(old_surface, new_surface)
            return Mutation(
                f"/sections/{si}/claims/{ci}/force/deontic",
                current,
                replacement,
                f"the obligation force moved from {old_surface} to {new_surface} in the force "
                "field, the requirement slot, and the proposition surface",
            )
    raise _unmet(
        "ATS-MUT-DEONTIC-EXCHANGE", "no material claim carries an exchangeable deontic force"
    )


@applier("ATS-MUT-ACTOR-REMOVE")
def _actor_remove(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    from ..rules.deterministic.requirements import CONCEALING_ACTORS

    concealed = "the system"
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            requirement = claim.get("requirement")
            if not claim.get("material") or not requirement:
                continue
            actor = requirement["actor"]
            if actor.strip().lower() in CONCEALING_ACTORS:
                continue
            requirement["actor"] = concealed
            claim["proposition"] = claim["proposition"].replace(f"the {actor}", concealed)
            return Mutation(
                f"/sections/{si}/claims/{ci}/requirement/actor",
                actor,
                concealed,
                "the responsible actor was replaced with the concealing form the specification "
                "itself names nonconforming",
            )
    raise _unmet("ATS-MUT-ACTOR-REMOVE", "no material requirement names an explicit actor")


@applier("ATS-MUT-OBLIGATION-MERGE")
def _obligation_merge(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        claims = section.get("claims", [])
        indexes = [
            i
            for i, c in enumerate(claims)
            if c.get("material") and c.get("role") == "requirement" and c.get("requirement")
        ]
        if len(indexes) < 2:
            continue
        first, second = indexes[0], indexes[1]
        keeper, absorbed = claims[first], claims[second]
        old_action = keeper["requirement"]["action"]
        merged = f"{old_action} and {absorbed['requirement']['action']}"
        keeper["requirement"]["action"] = merged
        keeper["proposition"] = (
            f"{keeper['proposition'].rstrip('.')} and "
            f"{absorbed['requirement']['action']} {absorbed['requirement']['object']}."
        )
        del claims[second]
        return Mutation(
            f"/sections/{si}/claims/{first}/requirement/action",
            old_action,
            merged,
            f"requirement {absorbed['requirement']['requirement_id']} was absorbed into "
            f"{keeper['requirement']['requirement_id']} without an indivisible-actions "
            "justification",
        )
    raise _unmet("ATS-MUT-OBLIGATION-MERGE", "no section holds two material requirement claims")


@applier("ATS-MUT-UNIT-STRIP")
def _unit_strip(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    """Delete the unit from a material number.

    The denominator of a ``proportion`` is left in place: the TextIR schema
    requires it, so removing it would produce a document that is not a valid
    quantifier at all rather than a valid document with a lost distinction. A
    mutation that breaks the schema tests the validator, not the rule.
    """
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            quantifier = claim.get("quantifier") or {}
            if (
                not claim.get("material")
                or quantifier.get("kind") not in UNIT_BEARING_QUANTIFIERS
                or "unit" not in quantifier
            ):
                continue
            unit = quantifier.pop("unit")
            return Mutation(
                f"/sections/{si}/claims/{ci}/quantifier/unit",
                unit,
                None,
                f"the unit {unit!r} was removed from a material {quantifier['kind']} quantifier, "
                "leaving the number without its dimension or count basis",
            )
    raise _unmet("ATS-MUT-UNIT-STRIP", "no material quantifier declares a unit")


@applier("ATS-MUT-THRESHOLD-BOUNDARY-SHIFT")
def _threshold_boundary_shift(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            requirement = claim.get("requirement")
            quantifier = claim.get("quantifier") or {}
            if (
                not claim.get("material")
                or not requirement
                or quantifier.get("kind") not in ("minimum", "maximum", "range")
                or not requirement.get("constraints")
            ):
                continue
            constraints = requirement.pop("constraints")
            return Mutation(
                f"/sections/{si}/claims/{ci}/requirement/constraints",
                constraints,
                None,
                "the boundary's comparator and inclusivity declaration was removed while the "
                "numeral was left in place",
            )
    raise _unmet(
        "ATS-MUT-THRESHOLD-BOUNDARY-SHIFT",
        "no material requirement declares boundary constraints on a threshold quantifier",
    )


@applier("ATS-MUT-NEGATION-FLIP")
def _negation_flip(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            if not claim.get("material"):
                continue
            old = claim["polarity"]
            claim["polarity"] = "negative" if old == "positive" else "positive"
            return Mutation(
                f"/sections/{si}/claims/{ci}/polarity",
                old,
                claim["polarity"],
                "the claim's polarity was inverted; the proposition text is deliberately "
                "untouched, so the pair is an IR preservation pair and not natural prose",
            )
    raise _unmet("ATS-MUT-NEGATION-FLIP", "the document holds no material claim")


@applier("ATS-MUT-QUANTIFIER-WIDEN")
def _quantifier_widen(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            quantifier = claim.get("quantifier") or {}
            if not claim.get("material") or quantifier.get("kind") != "some":
                continue
            quantifier["kind"] = "all"
            return Mutation(
                f"/sections/{si}/claims/{ci}/quantifier/kind",
                "some",
                "all",
                "the claim's population was widened from some to all",
            )
    raise _unmet("ATS-MUT-QUANTIFIER-WIDEN", "no material claim carries a quantifier of kind some")


@applier("ATS-MUT-RELATION-REVERSE")
def _relation_reverse(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        for ri, relation in enumerate(section.get("relations", ())):
            if not relation.get("material") or relation["type"] not in DIRECTIONAL_RELATIONS:
                continue
            source, target = relation["source_id"], relation["target_id"]
            relation["source_id"], relation["target_id"] = target, source
            return Mutation(
                f"/sections/{si}/relations/{ri}",
                {"source_id": source, "target_id": target},
                {"source_id": target, "target_id": source},
                f"the direction of the {relation['type']} relation was inverted",
            )
    raise _unmet("ATS-MUT-RELATION-REVERSE", "no material directional relation exists")


@applier("ATS-MUT-CAUSAL-UPGRADE")
def _causal_upgrade(ir: dict[str, Any], lexicon: Any) -> Mutation:
    if "causes" not in lexicon.causal_terms:
        raise UsageError("the lexicon declares no 'causes' term")
    for si, section in _sections(ir):
        for ri, relation in enumerate(section.get("relations", ())):
            if not relation.get("material") or relation["type"] != "associated_with":
                continue
            relation["type"] = "causes"
            return Mutation(
                f"/sections/{si}/relations/{ri}/type",
                "associated_with",
                "causes",
                "an association was restated as causation without adding a causal basis",
            )
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            force = claim.get("force") or {}
            if force.get("causal") != "associated_with":
                continue
            force["causal"] = "causes"
            return Mutation(
                f"/sections/{si}/claims/{ci}/force/causal",
                "associated_with",
                "causes",
                "an association was restated as causation without adding a causal basis",
            )
    raise _unmet("ATS-MUT-CAUSAL-UPGRADE", "no material association is declared")


@applier("ATS-MUT-EXCEPTION-DELETE")
def _exception_delete(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            requirement = claim.get("requirement")
            if not requirement or requirement.get("deontic") not in ("SHOULD", "SHOULD_NOT"):
                continue
            exceptions = requirement.get("exceptions")
            if not exceptions:
                continue
            requirement["exceptions"] = []
            return Mutation(
                f"/sections/{si}/claims/{ci}/requirement/exceptions",
                exceptions,
                [],
                "the recommendation's declared exceptions were removed, leaving no stated "
                "condition under which an override is valid",
            )
    raise _unmet(
        "ATS-MUT-EXCEPTION-DELETE", "no SHOULD or SHOULD NOT requirement enumerates an exception"
    )


@applier("ATS-MUT-CONTRARY-EVIDENCE-DELETE")
def _contrary_evidence_delete(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        claims = {c["claim_id"]: c for c in section.get("claims", ())}
        for ri, relation in enumerate(section.get("relations", ())):
            if not relation.get("material") or relation["type"] not in CONTRARY_RELATIONS:
                continue
            target = claims.get(relation["target_id"])
            if target is None or target.get("role") not in ("judgment", "forecast"):
                continue
            removed = dict(relation)
            del section["relations"][ri]
            return Mutation(
                f"/sections/{si}/relations/{ri}",
                removed,
                None,
                f"the {removed['type']} link between {removed['source_id']} and "
                f"{removed['target_id']} was removed while the alternative claim itself "
                "was preserved",
            )
    raise _unmet(
        "ATS-MUT-CONTRARY-EVIDENCE-DELETE",
        "no material contrary or alternative relation targets a judgment or forecast",
    )


@applier("ATS-MUT-ASSUMPTION-TO-OBSERVATION")
def _assumption_to_observation(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            if claim.get("role") != "assumption" or not claim.get("material"):
                continue
            if not (claim.get("force") or {}).get("assessment_confidence"):
                continue
            claim["role"] = "observation"
            return Mutation(
                f"/sections/{si}/claims/{ci}/role",
                "assumption",
                "observation",
                "an assumption was relabelled as an observation, collapsing the evidence chain "
                "the profile requires to stay differentiated",
            )
    raise _unmet(
        "ATS-MUT-ASSUMPTION-TO-OBSERVATION",
        "no material assumption carries an assessment confidence",
    )


@applier("ATS-MUT-SOURCE-ATTRIBUTION-STRIP")
def _source_attribution_strip(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        for ei, evidence in enumerate(section.get("evidence", ())):
            source = evidence.get("source") or {}
            if source.get("availability") != "present" or "locator" not in source:
                continue
            old = dict(source)
            source["availability"] = "not_searched"
            source["search_scope"] = "the corpus mutation removed the attribution"
            for field in ("locator", "content_sha256", "revision", "observed_at"):
                source.pop(field, None)
            return Mutation(
                f"/sections/{si}/evidence/{ei}/source",
                old,
                dict(source),
                "the evidence lost its source locator and its availability was downgraded to "
                "not_searched",
            )
    raise _unmet(
        "ATS-MUT-SOURCE-ATTRIBUTION-STRIP",
        "no evidence object declares a present source with a locator",
    )


@applier("ATS-MUT-UPDATE-INDICATOR-DELETE")
def _update_indicator_delete(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        roles = {
            c["claim_id"]: c.get("role") for c in section.get("claims", ()) if c.get("material")
        }
        for ui, indicator in enumerate(section.get("update_indicators", ())):
            if not any(
                roles.get(ref) in ("judgment", "forecast")
                for ref in indicator.get("target_claim_refs", ())
            ):
                continue
            removed = dict(indicator)
            del section["update_indicators"][ui]
            return Mutation(
                f"/sections/{si}/update_indicators/{ui}",
                removed,
                None,
                f"the update indicator for {', '.join(removed['target_claim_refs'])} was "
                "removed, leaving the judgment with no stated condition that would change it",
            )
    raise _unmet(
        "ATS-MUT-UPDATE-INDICATOR-DELETE",
        "no update indicator targets a material judgment or forecast",
    )


@applier("ATS-MUT-EVIDENTIAL-STRENGTHEN")
def _evidential_strengthen(ir: dict[str, Any], lexicon: Any) -> Mutation:
    order = list(lexicon.evidential_terms)
    for si, section in _sections(ir):
        for ci, claim in enumerate(section.get("claims", ())):
            force = claim.get("force") or {}
            current = force.get("evidential")
            if current not in order or order.index(current) + 1 >= len(order):
                continue
            stronger = order[order.index(current) + 1]
            force["evidential"] = stronger
            return Mutation(
                f"/sections/{si}/claims/{ci}/force/evidential",
                current,
                stronger,
                f"the evidential expression moved from {current} to {stronger} while the "
                "described basis was unchanged",
            )
    raise _unmet(
        "ATS-MUT-EVIDENTIAL-STRENGTHEN",
        "no claim carries an evidential force below the strongest lexicon term",
    )


@applier("ATS-MUT-RESTATEMENT-INSERT")
def _restatement_insert(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        claims = section.get("claims", [])
        source = next((c for c in claims if c.get("material")), None)
        if source is None:
            continue
        restated = {
            "claim_id": f"{source['claim_id']}-restated",
            "role": "inference",
            "proposition": source["proposition"],
            "material": False,
            "polarity": source["polarity"],
            "status": "asserted",
        }
        claims.append(restated)
        return Mutation(
            f"/sections/{si}/claims/{len(claims) - 1}",
            None,
            restated,
            f"a verbatim copy of {source['claim_id']}'s proposition was inserted, adding no "
            "information and performing no declared function",
        )
    raise _unmet("ATS-MUT-RESTATEMENT-INSERT", "no section holds a material claim to restate")


@applier("ATS-MUT-JUDGMENT-BURY")
def _judgment_bury(ir: dict[str, Any], _lexicon: Any) -> Mutation:
    for si, section in _sections(ir):
        claims = section.get("claims", [])
        material = [i for i, c in enumerate(claims) if c.get("material")]
        if len(claims) < 2 or not material:
            continue
        first = material[0]
        if claims[first].get("role") not in ("judgment", "requirement", "forecast"):
            continue
        moved = claims.pop(first)
        claims.append(moved)
        return Mutation(
            f"/sections/{si}/claims",
            {"position": first, "claim_id": moved["claim_id"]},
            {"position": len(claims) - 1, "claim_id": moved["claim_id"]},
            f"the leading {moved['role']} {moved['claim_id']} was moved behind the background "
            "claims of its section; no claim content changed",
        )
    raise _unmet(
        "ATS-MUT-JUDGMENT-BURY",
        "no section leads with a material judgment, forecast, or requirement beside other claims",
    )


# -- registry ---------------------------------------------------------------


@functools.lru_cache(maxsize=4)
def _load_registry_document(path: str) -> dict[str, Any]:
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise UsageError(f"{path} does not contain a mutation operator registry")
    return document


def load_operators(ctx: Any, path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the mutation operator registry.

    Every operator declared ``supported: true`` must have an applier, and every
    applier must have a declaration. A registry entry with no implementation
    would be a promise this module cannot keep; an implementation with no
    declaration would be an undocumented mutation appearing in the corpus.
    """
    document = _load_registry_document(str(path or OPERATOR_REGISTRY_PATH))
    ctx.schemas.validate(document, "ats_mutation_operator_v1.schema.json")
    by_id: dict[str, Any] = {}
    for declaration in document["operators"]:
        operator_id = declaration["operator_id"]
        if operator_id in by_id:
            raise UsageError(f"duplicate operator id in the registry: {operator_id}")
        by_id[operator_id] = declaration
        for rule_id in declaration["target_rule_ids"]:
            ctx.registry.get(rule_id)

    declared_supported = {k for k, v in by_id.items() if v["supported"]}
    implemented = set(APPLIERS)
    if declared_supported - implemented:
        raise UsageError(
            "operators declared supported with no applier: "
            f"{sorted(declared_supported - implemented)}"
        )
    if implemented - declared_supported:
        raise UsageError(
            f"appliers with no supported declaration: {sorted(implemented - declared_supported)}"
        )
    return {"document": document, "operators": by_id}


def operator(ctx: Any, operator_id: str, path: str | Path | None = None) -> dict[str, Any]:
    """One operator declaration, by id."""
    operators = load_operators(ctx, path)["operators"]
    try:
        return operators[operator_id]
    except KeyError:
        raise UsageError(
            f"unknown mutation operator {operator_id!r}; known operators: "
            f"{', '.join(sorted(operators))}"
        ) from None


# -- application ------------------------------------------------------------


def source_ir(example: Mapping[str, Any]) -> dict[str, Any]:
    """The TextIR document an example carries in its extension namespace."""
    ir = (example.get("extensions") or {}).get(rec.EXT_TEXT_IR)
    if not isinstance(ir, dict):
        raise UsageError(
            f"example {example.get('example_id')} carries no TextIR under "
            f"extensions.{rec.EXT_TEXT_IR}; a mutation operator edits the meaning ledger, not "
            "the rendered sentence"
        )
    return ir


def mutant_text(mutated: Mapping[str, Any], mutation: Mutation) -> str | None:
    """The proposition the mutation landed on, when it landed on one.

    A mutation that edits a claim's proposition yields readable example text. A
    mutation that only edits a structural field — a polarity flag, a relation
    direction — does not, so it returns ``None`` and the example keeps its
    source text and stays honestly labelled as an IR pair.
    """
    parts = mutation.pointer.strip("/").split("/")
    if len(parts) < 4 or parts[0] != "sections" or parts[2] != "claims":
        return None
    try:
        claim = mutated["sections"][int(parts[1])]["claims"][int(parts[3])]
    except (IndexError, ValueError, KeyError, TypeError):
        return None
    proposition = claim.get("proposition")
    return str(proposition) if proposition else None


def apply_operator(
    ctx: Any,
    example: Mapping[str, Any],
    operator_id: str,
    *,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Apply one mutation operator to one corpus example.

    Returns ``{"operator_id", "source_example", "mutant", "transformation",
    "expected_impact"}``. The source example is preserved verbatim, the mutant
    inherits its ``split_group``, and both the source and output IR are hashed
    so the transformation can be replayed and checked.

    Raises :class:`~ats.errors.UnsupportedCapabilityError` when the operator is
    declared ``supported: false``, and :class:`~ats.errors.UsageError` when a
    precondition is unmet.
    """
    declaration = operator(ctx, operator_id, registry_path)
    if not declaration["supported"]:
        raise UnsupportedCapabilityError(
            f"mutation operator {operator_id}",
            " ".join(declaration["unsupported_reason"].split()),
            declared_at=str(registry_path or OPERATOR_REGISTRY_PATH),
        )

    ctx.schemas.validate_document(dict(example))
    original = source_ir(example)
    ctx.schemas.validate_document(original)

    mutated = copy.deepcopy(original)
    mutation = APPLIERS[operator_id](mutated, ctx.lexicon)
    ctx.schemas.validate_document(mutated)

    source_hash = content_hash(dict(original), exclude=set())
    output_hash = content_hash(mutated, exclude=set())
    if source_hash == output_hash:
        raise UsageError(
            f"{operator_id} produced an identical document; a mutation that changes nothing "
            "cannot be a labelled example"
        )

    extensions = {
        k: v
        for k, v in (example.get("extensions") or {}).items()
        if k not in (rec.EXT_TEXT_IR, rec.EXT_RECORD_SHA256)
    }
    extensions[rec.EXT_TEXT_IR] = mutated
    extensions[rec.EXT_SOURCE_EXAMPLE_ID] = example["example_id"]
    extensions[rec.EXT_MUTATION_FAMILY] = operator_id

    mutant = rec.text_example(
        text=mutant_text(mutated, mutation) or example["text"],
        context=example.get("context"),
        source_artifact=example.get("source_artifact"),
        source_span=example.get("source_span"),
        repository_group=example.get("repository_group"),
        domain=example.get("domain"),
        profile=example["profile"],
        rule_id=declaration["target_rule_ids"][0],
        label=declaration["expected_label"],
        rationale=(
            f"{declaration['title']}: {mutation.detail}. Synthetic mutation under "
            f"{operator_id}; it is tagged synthetic and MUST NOT be counted as independent "
            "real-world evidence of rule prevalence or user value (spec 17.5)."
        ),
        protected_impact=declaration["expected_protected_impact"],
        provenance="synthetic_mutation",
        use_authority=example.get("use_authority"),
        synthetic=True,
        mutation_operator=operator_id,
        # Spec 17.7: a mutation stays in the same split group as its source.
        split_group=example["split_group"],
        extensions=extensions,
    )
    ctx.schemas.validate_document(mutant)

    rules = [ctx.registry.get(r) for r in declaration["target_rule_ids"]]
    return {
        "operator_id": operator_id,
        "source_example": dict(example),
        "mutant": mutant,
        "split_group": mutant["split_group"],
        "transformation": {
            "kind": declaration["transformation"]["kind"],
            "description": " ".join(declaration["transformation"]["description"].split()),
            "source_sha256": source_hash,
            "output_sha256": output_hash,
            **mutation.to_dict(),
        },
        "expected_impact": {
            "target_rule_ids": list(declaration["target_rule_ids"]),
            "expected_label": declaration["expected_label"],
            "expected_protected_impact": list(declaration["expected_protected_impact"]),
            "expected_delta_classes": list(declaration.get("expected_delta_classes", ())),
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "rule_version": rule.rule_version,
                    "severity": rule.severity,
                    "normative_statement": rule.normative_statement,
                }
                for rule in rules
            ],
            "synthetic_evidence_note": (
                "A synthetic mutation demonstrates that the rule can be violated in this way. "
                "It is not evidence that the violation occurs in real repositories (spec 17.5)."
            ),
        },
    }


def apply_all(
    ctx: Any,
    example: Mapping[str, Any],
    *,
    registry_path: str | Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Apply every supported operator whose preconditions the example meets.

    Returns ``(applied, refused)``. A refusal names the operator and the reason,
    so an empty mutation set is never mistaken for an example that nothing
    applies to.
    """
    applied: list[dict[str, Any]] = []
    refused: list[dict[str, str]] = []
    for operator_id, declaration in sorted(
        load_operators(ctx, registry_path)["operators"].items()
    ):
        if not declaration["supported"]:
            refused.append(
                {
                    "operator_id": operator_id,
                    "reason": "unsupported",
                    "detail": " ".join(declaration["unsupported_reason"].split()),
                }
            )
            continue
        try:
            applied.append(apply_operator(ctx, example, operator_id, registry_path=registry_path))
        except UsageError as exc:
            refused.append(
                {"operator_id": operator_id, "reason": "precondition_unmet", "detail": str(exc)}
            )
    return applied, refused


def paired_examples(result: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    """The source and mutant of one applied mutation, as a split-inseparable pair."""
    return (result["source_example"], result["mutant"])

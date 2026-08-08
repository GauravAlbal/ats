"""Terminology rules: ATS-TERM-001, ATS-TERM-002, ATS-TERM-003."""

from __future__ import annotations

import re
from typing import Any

from ...ir.model import IrEvaluation
from ...rules.results import DecisionPower, Detector, Finding
from ._support import (
    Collector,
    DetectorSpec,
    SubcheckSpec,
    contains_phrase,
    detector,
    undecidable,
)

# -- ATS-TERM-001 -----------------------------------------------------------

TERM001_ALIAS = SubcheckSpec(
    subcheck_id="deprecated-alias-in-material-claim",
    decides=False,
    spec_ref="ATS-1 10.2, 10.3",
    vocabulary_source="the artifact's own glossary `deprecated_aliases`",
    description=(
        "A material claim uses a term the artifact's glossary lists as a deprecated alias "
        "of a declared canonical term."
    ),
)
TERM001_DUPLICATE = SubcheckSpec(
    subcheck_id="two-entries-one-canonical-term",
    decides=False,
    spec_ref="ATS-1 10.2",
    vocabulary_source="the artifact's own glossary",
    description="Two glossary concepts declare the same canonical term within one scope.",
)


@detector(
    DetectorSpec(
        rule_id="ATS-TERM-001",
        detector_class="D1",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(TERM001_ALIAS, TERM001_DUPLICATE),
        unavailable_conditions=(
            "The artifact declares no glossary, so no canonical term is available to compare against.",
        ),
        known_limits=(
            "Only synonym drift the glossary already names is detectable. Two undeclared terms for "
            "one concept require semantic judgement and are never reported here.",
            "Absence of a declared alias is reported as REVIEW_REQUIRED, never as conformance.",
        ),
    )
)
def term_001(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Within one scope, a concept MUST use one canonical term."""
    c = Collector(ev, det, "ATS-TERM-001")

    by_canonical: dict[tuple[str, str], list[str]] = {}
    for entry in ev.ir.glossary:
        key = (entry["canonical_term"].casefold(), entry.get("scope", ""))
        by_canonical.setdefault(key, []).append(entry["concept_id"])
    for (term, scope), concept_ids in sorted(by_canonical.items()):
        c.saw(TERM001_DUPLICATE.subcheck_id)
        if len(concept_ids) > 1:
            c.flag(
                TERM001_DUPLICATE.subcheck_id,
                issue_code="canonical-term-collision",
                summary=(
                    f"Glossary concepts {', '.join(sorted(concept_ids))} all declare the canonical "
                    f"term {term!r} in scope {scope!r}; one term cannot denote several concepts "
                    "within one scope."
                ),
                spans=[{"kind": "json_pointer", "locator": "/glossary"}],
            )

    aliases: list[tuple[str, str, str]] = []
    for entry in ev.ir.glossary:
        for alias in entry.get("deprecated_aliases", ()):
            aliases.append((alias, entry["canonical_term"], entry["concept_id"]))

    for claim in ev.ir.material_claims():
        c.saw(TERM001_ALIAS.subcheck_id)
        for alias, canonical, concept_id in aliases:
            if contains_phrase(claim.proposition, alias):
                c.flag(
                    TERM001_ALIAS.subcheck_id,
                    issue_code="deprecated-alias-used",
                    summary=(
                        f"Claim {claim.claim_id} uses {alias!r}, which glossary concept "
                        f"{concept_id!r} lists as a deprecated alias of the canonical term "
                        f"{canonical!r}. A reader must reconstruct whether the two labels denote "
                        "the same object."
                    ),
                    spans=[claim.span()],
                    evidence_spans=[{"kind": "json_pointer", "locator": "/glossary"}],
                )
    return c.result((TERM001_ALIAS, TERM001_DUPLICATE))


# -- ATS-TERM-002 -----------------------------------------------------------

undecidable(
    DetectorSpec(
        rule_id="ATS-TERM-002",
        detector_class="none",
        power=DecisionPower.UNDECIDABLE,
        subchecks=(
            SubcheckSpec(
                subcheck_id="substitution-changes-meaning",
                decides=False,
                spec_ref="ATS-1 10.4",
                description=(
                    "Deciding whether a domain term was replaced requires the source text the "
                    "output was derived from."
                ),
            ),
        ),
        unavailable_conditions=(
            "`ats ir lint` receives one TextIR document and no source text, so there is nothing to "
            "compare the current wording against.",
        ),
        known_limits=(
            "This rule is decidable only on a transformation surface holding both source and "
            "output. The v0 commands never construct that pair.",
        ),
    )
)


# -- ATS-TERM-003 -----------------------------------------------------------

TERM003 = SubcheckSpec(
    subcheck_id="acronym-unexpanded-at-first-material-use",
    decides=False,
    spec_ref="ATS-1 10.5",
    vocabulary_source=(
        "acronym shape `[A-Z][A-Z0-9]{1,}` plus the artifact's glossary `approved_abbreviations` "
        "and `audience.assumed_glossary_refs`"
    ),
    description=(
        "An acronym's first material use is neither expanded in place as `Expansion (ACR)` nor "
        "permitted by the glossary or audience policy."
    ),
)

#: An acronym as ATS-1 Section 10.5 means it: two or more capitals or digits,
#: starting with a capital. No word list is involved.
_ACRONYM = re.compile(r"(?<![\w-])([A-Z][A-Z0-9]{1,})(?![\w-])")


@detector(
    DetectorSpec(
        rule_id="ATS-TERM-003",
        detector_class="D1",
        power=DecisionPower.DETECTS_VIOLATIONS,
        subchecks=(TERM003,),
        unavailable_conditions=(
            "The artifact declares no audience expertise, so audience policy cannot be consulted.",
        ),
        known_limits=(
            "Expansion is recognised only in the canonical `Expansion (ACR)` form. An expansion "
            "carried in prose elsewhere in the document is not detected, so a clean run is "
            "REVIEW_REQUIRED rather than PASS.",
            "Uppercase deontic surfaces (MUST, MAY, CAN) and canonical protected labels (P0, P1, "
            "P2) are excluded because ATS-1 defines them; they are not audience acronyms.",
        ),
    )
)
def term_003(ev: IrEvaluation, det: Detector) -> tuple[list[Finding], list[dict[str, Any]]]:
    """An acronym MUST be expanded on first material use unless policy permits it."""
    c = Collector(ev, det, "ATS-TERM-003")

    permitted: set[str] = set()
    for entry in ev.ir.glossary:
        permitted.update(entry.get("approved_abbreviations", ()))
        permitted.add(entry["canonical_term"])
    # ATS-1's own closed vocabularies are not audience acronyms.
    permitted.update(ev.ctx.lexicon.deontic_surfaces.values())
    permitted.update(ev.ctx.lexicon.deontic_noncanonical)
    permitted.update({"P0", "P1", "P2"})
    # The deontic negative marker appears inside canonical surfaces such as
    # ``MUST NOT``; the standalone word ``NOT`` is closed vocabulary, not an
    # unexpanded audience acronym (regression: false hard block).
    permitted.add("NOT")

    seen: set[str] = set()
    for claim in ev.ir.material_claims():
        text = claim.proposition
        c.saw(TERM003.subcheck_id)
        for match in _ACRONYM.finditer(text):
            acronym = match.group(1)
            if acronym in permitted or acronym in seen:
                continue
            seen.add(acronym)
            expansion = re.search(
                r"[A-Za-z][\w\s/-]{2,}\s\(" + re.escape(acronym) + r"\)", text
            )
            if expansion is not None:
                continue
            c.flag(
                TERM003.subcheck_id,
                issue_code="acronym-not-expanded",
                summary=(
                    f"Claim {claim.claim_id} is the first material use of {acronym!r}. It is not "
                    f"expanded in place as `Expansion ({acronym})`, no glossary entry lists it "
                    "under approved_abbreviations, and the audience policy does not permit it."
                ),
                spans=[claim.span()],
            )
    return c.result((TERM003,))

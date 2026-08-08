"""Reference and scope rules: ATS-REF-001, ATS-SCOPE-001.

Both rules name ``syntax`` among their required inputs. The TextIR carries
propositions as opaque strings, not parse trees, so neither antecedent
resolution nor scope-operator nesting can be decided here. Reporting these as
PASS because no violation was found would be exactly the failure Section 16.5
forbids, so both report UNAVAILABLE with the missing input named.
"""

from __future__ import annotations

from ...rules.results import DecisionPower
from ._support import DetectorSpec, SubcheckSpec, undecidable

undecidable(
    DetectorSpec(
        rule_id="ATS-REF-001",
        detector_class="none",
        power=DecisionPower.UNDECIDABLE,
        subchecks=(
            SubcheckSpec(
                subcheck_id="single-plausible-antecedent",
                decides=False,
                spec_ref="ATS-1 10.6",
                description=(
                    "Counting the plausible antecedents of a pronoun, demonstrative, or elliptical "
                    "reference requires a syntactic analysis of the sentence."
                ),
            ),
        ),
        unavailable_conditions=(
            "The TextIR represents propositions as strings; no syntactic analysis is available, so "
            "antecedent candidates cannot be enumerated.",
        ),
        known_limits=(
            "A referential-ambiguity detector belongs on a surface that parses prose. Nothing in "
            "the IR distinguishes an unambiguous pronoun from an ambiguous one.",
        ),
    )
)

undecidable(
    DetectorSpec(
        rule_id="ATS-SCOPE-001",
        detector_class="none",
        power=DecisionPower.UNDECIDABLE,
        subchecks=(
            SubcheckSpec(
                subcheck_id="one-action-relevant-interpretation",
                decides=False,
                spec_ref="ATS-1 7.6, 10.6",
                description=(
                    "Deciding whether quantifier, negation, condition, and exclusion scope admit "
                    "exactly one action-relevant reading requires syntactic nesting."
                ),
            ),
        ),
        unavailable_conditions=(
            "Scope ambiguity is a property of how operators nest in the sentence. The TextIR "
            "records the scope an author declared, not the scope the prose admits, so the two "
            "cannot be compared without `syntax`.",
        ),
        known_limits=(
            "The IR-level scope obligations that ARE decidable are checked as structural checks "
            "IR-POLARITY-QUANTIFIER and IR-QUANT-UNITS, not folded into this rule's result.",
        ),
    )
)

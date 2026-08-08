"""The eight deterministic surface checks over rendered Markdown.

Every vocabulary these checks match against comes from the force lexicon, from
a list enumerated verbatim in ``ATS-1_SPEC.md``, or from the artifact's own
glossary. Section 5.6 exempts marked quotation, code, log, schema, and
counterexample regions, and every skip is counted rather than silent.
"""

from __future__ import annotations

import copy

import pytest

from ats.ir.model import IrDocument
from ats.output.parse import parse_markdown
from ats.output.render_checks import (
    EMPTY_INTENSIFIERS,
    EXEMPT_CONTENT_CLASSES,
    IDENTIFIER_FIELD_MARKERS,
    VAGUE_EVALUATIVE,
    VAGUE_TIMING,
    run_surface_checks,
)
from ats.output.trace import build_trace, load_trace

RENDERER = {"name": "test-renderer", "version": "0"}


@pytest.fixture(scope="module")
def surface(ctx, load_ir, load_policy):
    """Render one marked block and run the surface checks over it."""
    policy = ctx.policy(load_policy("assess"))

    def _surface(body: str, meta: dict, *, ir_document=None, heading="# Assessment"):
        document = ir_document if ir_document is not None else load_ir("assess_conforming")
        ir = IrDocument.from_document(document)
        text = f"{heading}\n\n<!-- ats:block b1 -->\n{body}\n"
        parsed = parse_markdown(text)
        trace = build_trace(
            ctx,
            ir=ir,
            parsed=parsed,
            output_bytes=text.encode("utf-8"),
            policy_snapshot_id=policy.snapshot_id,
            policy_sha256=policy.declared_sha256,
            block_metadata={"b1": {"section_id": "assessment", **meta}},
            renderer=RENDERER,
        )
        return run_surface_checks(ctx, ir, parsed, load_trace(ctx, trace))

    return _surface


def codes(report, check_id):
    return sorted(issue.issue_code for issue in report.for_check(check_id))


# -- OUT-UNITS --------------------------------------------------------------


def test_a_bare_p0_number_is_flagged(surface) -> None:
    """Spec 10.9: a material number must carry its unit or dimension."""
    report = surface(
        "The budget is 500.",
        {
            "display_role": "key_judgment",
            "material": True,
            "p0_fields": [
                {
                    "field_ref": "c1.quantifier.value",
                    "ir_pointer": "/sections/0/claims/0/proposition",
                    "rendered": "500",
                }
            ],
        },
    )
    assert codes(report, "OUT-UNITS") == ["p0-number-without-unit"]


@pytest.mark.parametrize(
    "rendered",
    ["REQ-POLICY-017", "REQ-VER-001", "24-hour", "v2", "1.0.0-draft.1"],
)
def test_identifiers_and_compound_modifiers_are_not_bare_numbers(
    surface, rendered
) -> None:
    """Spec 17.6 names identifier-shaped numbers as a required hard-negative class.

    Section 10.9 attaches its obligation to a material *quantity*. Digits that
    belong to an identifier or to a compound modifier name no quantity of their
    own, so flagging them would be exactly the false positive the standard warns
    a detector against.
    """
    report = surface(
        f"The requirement {rendered} applies.",
        {
            "display_role": "key_judgment",
            "material": True,
            "p0_fields": [
                {
                    "field_ref": "c1.proposition",
                    "ir_pointer": "/sections/0/claims/0/proposition",
                    "rendered": rendered,
                }
            ],
        },
    )
    assert codes(report, "OUT-UNITS") == []


@pytest.mark.parametrize("marker", ["requirement_id", "forecast_id", "version", "sha256"])
def test_an_identifier_class_p0_field_is_skipped_by_field_name(surface, marker) -> None:
    """Spec 11.3.1 protects identifiers exactly; Section 10.9 does not apply to them."""
    assert marker in IDENTIFIER_FIELD_MARKERS
    report = surface(
        "The requirement 017 applies.",
        {
            "display_role": "key_judgment",
            "material": True,
            "p0_fields": [
                {
                    "field_ref": f"c1.requirement.{marker}",
                    "ir_pointer": "/sections/0/claims/0/proposition",
                    "rendered": "017",
                }
            ],
        },
    )
    assert codes(report, "OUT-UNITS") == []


@pytest.mark.parametrize("rendered", ["55–80%", "55-80%", "500 milliseconds", "12 releases"])
def test_a_quantity_with_a_unit_or_percent_is_accepted(surface, rendered) -> None:
    """Spec 10.9: a percent sign or a named unit supplies the dimension."""
    report = surface(
        f"The measured value is {rendered}.",
        {
            "display_role": "key_judgment",
            "material": True,
            "p0_fields": [
                {
                    "field_ref": "c1.quantifier.value",
                    "ir_pointer": "/sections/0/claims/0/proposition",
                    "rendered": rendered,
                }
            ],
        },
    )
    assert codes(report, "OUT-UNITS") == []


# -- OUT-WEP-CANONICAL / OUT-WEP-INLINE-RANGE -------------------------------


def test_a_noncanonical_synonym_in_prose_is_flagged(ctx, surface) -> None:
    """Spec 8.3: output uses the canonical phrase, never an input alias."""
    assert ctx.lexicon.wep_aliases["probable"] == "likely"
    report = surface(
        "A migration is probable to reduce invalid-state defects.",
        {"display_role": "key_judgment", "material": True, "claim_ids": ["c1"]},
    )
    assert codes(report, "OUT-WEP-CANONICAL") == ["noncanonical-wep-phrase"]
    detail = report.for_check("OUT-WEP-CANONICAL")[0].detail
    assert "'likely'" in detail


def test_a_first_material_wep_use_without_its_range_is_flagged(ctx, surface) -> None:
    """Spec 8.4: the first material use in a section shows the numeric range."""
    assert ctx.lexicon.display_range("likely") == "55–80%"
    report = surface(
        "A migration is likely to reduce invalid-state defects.",
        {"display_role": "key_judgment", "material": True, "claim_ids": ["c1"]},
    )
    assert codes(report, "OUT-WEP-INLINE-RANGE") == ["first-use-range-absent"]


@pytest.mark.parametrize("dash", ["55–80%", "55-80%"])
def test_an_inline_range_satisfies_first_use_whichever_dash_is_used(
    surface, dash
) -> None:
    """Spec 8.4 governs the numbers shown, not the typography of the dash."""
    report = surface(
        f"A migration is likely ({dash}) to reduce invalid-state defects.",
        {"display_role": "key_judgment", "material": True, "claim_ids": ["c1"]},
    )
    assert codes(report, "OUT-WEP-INLINE-RANGE") == []


# -- OUT-DEONTIC-KEYWORDS ---------------------------------------------------


def test_a_noncanonical_modal_in_output_is_flagged(ctx, surface, load_ir) -> None:
    """Spec 8.16: SHALL is outside the closed deontic vocabulary."""
    assert "SHALL" in ctx.lexicon.deontic_noncanonical
    report = surface(
        "The verifier SHALL reject the receipt.",
        {"display_role": "requirement", "material": True},
        ir_document=load_ir("specify_conforming"),
    )
    assert "noncanonical-modal-rendered" in codes(report, "OUT-DEONTIC-KEYWORDS")


def test_a_rendered_requirement_without_an_uppercase_keyword_is_flagged(
    surface, load_ir
) -> None:
    """Spec 1.3: the deontic keywords are normative only in uppercase."""
    report = surface(
        "The verifier rejects the receipt before the acceptance transition.",
        {
            "display_role": "requirement",
            "material": True,
            "requirement_ids": ["REQ-POLICY-017"],
        },
        ir_document=load_ir("specify_conforming"),
    )
    assert codes(report, "OUT-DEONTIC-KEYWORDS") == [
        "requirement-without-uppercase-deontic"
    ]


def test_an_uppercase_keyword_satisfies_the_requirement_block(
    surface, load_ir
) -> None:
    """Spec 1.3 and 8.16: the uppercase surface carries the obligation."""
    report = surface(
        "The verifier MUST reject the receipt before the acceptance transition.",
        {
            "display_role": "requirement",
            "material": True,
            "requirement_ids": ["REQ-POLICY-017"],
        },
        ir_document=load_ir("specify_conforming"),
    )
    assert codes(report, "OUT-DEONTIC-KEYWORDS") == []


# -- OUT-ACRONYMS -----------------------------------------------------------


def test_an_unexpanded_acronym_in_output_is_flagged(surface) -> None:
    """Spec 10.5: the first rendered use must be expanded or permitted."""
    report = surface(
        "The migration keeps the FFI boundary unchanged.",
        {"display_role": "boundary", "material": True},
    )
    assert codes(report, "OUT-ACRONYMS") == ["acronym-not-expanded-in-output"]


def test_an_expanded_acronym_is_accepted(surface) -> None:
    """Spec 10.5: `Expansion (ACR)` is the canonical in-place form."""
    report = surface(
        "The migration keeps the foreign function interface (FFI) boundary unchanged.",
        {"display_role": "boundary", "material": True},
    )
    assert codes(report, "OUT-ACRONYMS") == []


def test_an_approved_abbreviation_is_accepted(surface, load_ir) -> None:
    """Spec 10.5: the artifact's glossary may permit the abbreviation."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["glossary"][0]["approved_abbreviations"] = ["FFI"]
    report = surface(
        "The migration keeps the FFI boundary unchanged.",
        {"display_role": "boundary", "material": True},
        ir_document=document,
    )
    assert codes(report, "OUT-ACRONYMS") == []


# -- OUT-RELATIVE-TIME ------------------------------------------------------


def test_an_unanchored_relative_expression_in_output_is_flagged(surface) -> None:
    """Spec 10.11: the rendered claim must resolve to an absolute anchor."""
    report = surface(
        "The prototype lands soon.",
        {"display_role": "update_indicator", "material": True},
    )
    assert codes(report, "OUT-RELATIVE-TIME") == ["unanchored-relative-time-rendered"]


def test_a_relative_expression_is_anchored_by_the_claim_it_realizes(surface) -> None:
    """Spec 10.11: the anchor may come from the claim's own scope."""
    report = surface(
        "The prototype lands soon.",
        {"display_role": "key_judgment", "material": True, "claim_ids": ["c1"]},
    )
    assert codes(report, "OUT-RELATIVE-TIME") == []


# -- OUT-TERMINOLOGY --------------------------------------------------------


def test_a_deprecated_alias_in_output_is_flagged(surface, load_ir) -> None:
    """Spec 10.2: one canonical term per concept within a scope."""
    document = copy.deepcopy(load_ir("assess_conforming"))
    document["glossary"][0]["deprecated_aliases"] = ["acceptance core"]
    report = surface(
        "The acceptance core stays unchanged.",
        {"display_role": "boundary", "material": False},
        ir_document=document,
    )
    assert "deprecated-alias-rendered" in codes(report, "OUT-TERMINOLOGY")


@pytest.mark.parametrize("word", EMPTY_INTENSIFIERS)
def test_every_empty_intensifier_section_10_20_names_is_flagged(surface, word) -> None:
    """Spec 10.20 enumerates these markers verbatim."""
    report = surface(
        f"The migration is {word} scoped to the kernel.",
        {"display_role": "boundary", "material": False},
    )
    assert "empty-intensifier" in codes(report, "OUT-TERMINOLOGY")


@pytest.mark.parametrize("word", VAGUE_EVALUATIVE)
def test_a_vague_evaluative_term_in_a_material_block_is_flagged(surface, word) -> None:
    """Spec 10.21: a vague evaluative term needs a comparison or threshold."""
    report = surface(
        f"The improvement is {word} for the acceptance kernel.",
        {"display_role": "key_judgment", "material": True},
    )
    assert "vague-evaluative-term" in codes(report, "OUT-TERMINOLOGY")


def test_a_vague_evaluative_term_in_an_immaterial_block_is_not_flagged(
    surface,
) -> None:
    """Spec 10.21 attaches to material content; Section 4.5 makes materiality declared."""
    report = surface(
        "The improvement is significant for the acceptance kernel.",
        {"display_role": "question", "material": False},
    )
    assert "vague-evaluative-term" not in codes(report, "OUT-TERMINOLOGY")


@pytest.mark.parametrize("word", VAGUE_TIMING)
def test_a_vague_timing_term_in_a_requirement_block_is_flagged(
    surface, load_ir, word
) -> None:
    """Spec 9.3.7: such terms are nonconforming when timing is material."""
    report = surface(
        f"The verifier MUST reject the receipt {word}.",
        {
            "display_role": "requirement",
            "material": True,
            "requirement_ids": ["REQ-POLICY-017"],
        },
        ir_document=load_ir("specify_conforming"),
    )
    assert "vague-timing-term" in codes(report, "OUT-TERMINOLOGY")


# -- OUT-HEADINGS-LISTS -----------------------------------------------------


def test_a_skipped_heading_level_is_flagged(surface) -> None:
    """Spec 10.17: a skipped level makes the document outline unrecoverable."""
    report = surface(
        "Prose.",
        {"display_role": "question", "material": False},
        heading="# Top\n\n### Skipped",
    )
    assert "heading-level-skipped" in codes(report, "OUT-HEADINGS-LISTS")


def test_a_one_item_bullet_list_is_flagged(surface) -> None:
    """Spec 10.18: a one-item list implies coordinate items that do not exist."""
    report = surface(
        "- the only item",
        {"display_role": "supporting_evidence", "material": True},
    )
    assert "single-item-list" in codes(report, "OUT-HEADINGS-LISTS")


def test_a_two_item_list_is_accepted(surface) -> None:
    """Spec 10.18: coordinate items are what a list represents."""
    report = surface(
        "- first item\n- second item",
        {"display_role": "supporting_evidence", "material": True},
    )
    assert codes(report, "OUT-HEADINGS-LISTS") == []


# -- Section 5.6 exemptions -------------------------------------------------


@pytest.mark.parametrize("content_class", sorted(EXEMPT_CONTENT_CLASSES))
def test_a_marked_exempt_region_is_skipped_and_counted(surface, content_class) -> None:
    """Spec 5.6: quoted and code content is exempt, but never silently."""
    report = surface(
        "A migration is probable to reduce invalid-state defects.",
        {
            "display_role": "supporting_evidence",
            "material": False,
            "content_class": content_class,
        },
    )
    assert report.for_check("OUT-WEP-CANONICAL") == []
    assert report.skipped["OUT-WEP-CANONICAL"] == ["b1"]
    assert report.inspected.get("OUT-WEP-CANONICAL", 0) == 0


def test_a_fenced_block_is_exempt_by_construction(surface) -> None:
    """Spec 5.6: code is exempt even when the trace does not mark its class."""
    report = surface(
        "```text\nA migration is probable.\n```",
        {"display_role": "supporting_evidence", "material": False},
    )
    assert report.for_check("OUT-WEP-CANONICAL") == []
    assert report.skipped["OUT-WEP-CANONICAL"] == ["b1"]


def test_prose_is_inspected_and_counted(surface) -> None:
    """Spec 5.6: an unmarked prose block is inspected, not exempt."""
    report = surface(
        "A migration is likely (55–80%) to reduce invalid-state defects.",
        {"display_role": "key_judgment", "material": True, "claim_ids": ["c1"]},
    )
    assert report.inspected["OUT-WEP-CANONICAL"] == 1
    assert "OUT-WEP-CANONICAL" not in report.skipped
    assert report.issues == []


def test_surface_issues_serialize_with_their_check_and_location(surface) -> None:
    """Spec 13.1 and 16.8: an issue names its check, its block, and its line."""
    report = surface(
        "A migration is probable to reduce defects.",
        {"display_role": "key_judgment", "material": True},
    )
    issue = report.for_check("OUT-WEP-CANONICAL")[0]
    payload = issue.to_dict()
    assert payload["check_id"] == "OUT-WEP-CANONICAL"
    assert payload["block_id"] == "b1"
    assert payload["line"] >= 1
    assert payload["issue_code"] == "noncanonical-wep-phrase"
    assert payload["detail"].strip()

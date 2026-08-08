"""Deterministic surface checks over rendered Markdown.

Every vocabulary comes from the force lexicon, a list enumerated verbatim in
``ATS-1_SPEC.md``, or the artifact's own glossary. Section 5.6 exempts quoted
source text, code, logs, schemas, and deliberate counterexamples from surface
rules — but only when the enclosing artifact marks the region's content class,
which the trace does. Every skip is counted and reported so the exemption is
never silent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from ..context import Context
from ..ir.model import IrDocument
from ..rules.deterministic._support import contains_exact, contains_phrase
from ..rules.deterministic.terminology import _ACRONYM
from ..rules.deterministic.time_rules import ANCHOR_FIELDS, RELATIVE_TIME_TERMS
from .parse import MarkdownBlock, ParsedDocument
from .trace import OutputTrace, TraceBlock

#: Content classes Section 5.6 exempts from surface rules when marked.
EXEMPT_CONTENT_CLASSES = frozenset({"quotation", "code", "log", "schema", "counterexample"})

#: Block kinds that are code or quotation by construction, exempt for the same
#: reason even when the trace does not mark them.
EXEMPT_BLOCK_KINDS = frozenset({"fence", "code_block", "blockquote"})

#: Empty intensifiers and attitude markers enumerated verbatim in Section 10.20.
EMPTY_INTENSIFIERS = ("clearly", "obviously", "simply", "just", "very", "really", "quite")

#: Vague evaluative terms enumerated verbatim in Section 10.21.
VAGUE_EVALUATIVE = (
    "significant",
    "large",
    "small",
    "meaningful",
    "material",
    "robust",
    "fast",
    "safe",
    "reliable",
)

#: Timing terms Section 9.3.7 names nonconforming when timing is material.
VAGUE_TIMING = ("promptly", "soon", "regularly", "eventually")

#: A standalone quantity: digits that are not part of a larger alphanumeric or
#: hyphenated token. The trailing lookahead rejects ``REQ-POLICY-017`` and
#: ``24-hour``, where the digits belong to an identifier or a compound
#: modifier rather than naming a quantity of their own.
#:
#: Spec Section 17.6 names "material numbers that are identifiers rather than
#: quantities" as a required hard-negative class, so treating them as bare
#: numbers would be exactly the false positive the standard warns about.
_NUMBER = re.compile(
    r"(?<![\w.-])(\d+(?:[.,]\d+)?)"          # the leading value
    r"(?:\s*[-\u2013\u2014]\s*\d+(?:[.,]\d+)?)?"  # an optional range upper bound
    r"(\s*)([%A-Za-z/\u00b5\u00b0]+)?"       # an optional unit
    # Reject a trailing dot only when a digit follows it, so a dotted
    # identifier ("1.0.0-draft.1") is not read as a quantity while a quantity
    # ending a sentence ("The latency is 1.5.") still matches.
    r"(?![\w-]|\.\d)"
)

#: P0 field classes that hold an identifier, a version, or a revision rather
#: than a quantity. Section 11.3.1 protects these exactly, but Section 10.9's
#: unit obligation applies to material numbers, not to names that contain
#: digits.
IDENTIFIER_FIELD_MARKERS = (
    "requirement_id",
    "forecast_id",
    "claim_id",
    "evidence_id",
    "relation_id",
    "indicator_id",
    "artifact_id",
    "section_id",
    "concept_id",
    "source_id",
    "exception_id",
    "snapshot_id",
    "version",
    "revision",
    "sha256",
    "locator",
)


def _is_identifier_field(p0: Mapping[str, Any]) -> bool:
    haystack = f"{p0.get('field_ref', '')} {p0.get('ir_pointer', '')}".casefold()
    return any(marker in haystack for marker in IDENTIFIER_FIELD_MARKERS)


@dataclass(slots=True)
class SurfaceIssue:
    check_id: str
    block_id: str
    line: int
    issue_code: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "block_id": self.block_id,
            "line": self.line,
            "issue_code": self.issue_code,
            "detail": self.detail,
        }


@dataclass(slots=True)
class SurfaceReport:
    issues: list[SurfaceIssue] = field(default_factory=list)
    skipped: dict[str, list[str]] = field(default_factory=dict)
    inspected: dict[str, int] = field(default_factory=dict)

    def flag(self, check_id: str, block_id: str, line: int, code: str, detail: str) -> None:
        self.issues.append(SurfaceIssue(check_id, block_id, line, code, detail))

    def saw(self, check_id: str) -> None:
        self.inspected[check_id] = self.inspected.get(check_id, 0) + 1

    def skip(self, check_id: str, block_id: str) -> None:
        self.skipped.setdefault(check_id, []).append(block_id)

    def for_check(self, check_id: str) -> list[SurfaceIssue]:
        return [i for i in self.issues if i.check_id == check_id]


@dataclass(frozen=True, slots=True)
class Pair:
    """A rendered block paired with its trace record."""

    block: MarkdownBlock
    trace: TraceBlock

    @property
    def exempt(self) -> bool:
        return (
            self.trace.content_class in EXEMPT_CONTENT_CLASSES
            or self.block.kind in EXEMPT_BLOCK_KINDS
        )

    @property
    def block_id(self) -> str:
        return self.trace.block_id

    @property
    def text(self) -> str:
        return self.block.text

    @property
    def line(self) -> int:
        return self.block.start_line


def pair_blocks(parsed: ParsedDocument, trace: OutputTrace) -> list[Pair]:
    pairs: list[Pair] = []
    for tb in trace.blocks:
        block = parsed.block_by_marker(tb.block_id)
        if block is not None:
            pairs.append(Pair(block, tb))
    return pairs


def run_surface_checks(
    ctx: Context, ir: IrDocument, parsed: ParsedDocument, trace: OutputTrace
) -> SurfaceReport:
    """All eight deterministic surface checks, in one pass over the pairs."""
    report = SurfaceReport()
    pairs = pair_blocks(parsed, trace)
    lex = ctx.lexicon

    _wep_canonical(report, pairs, lex)
    _wep_inline_range(report, pairs, ir, lex)
    _deontic_keywords(report, pairs, lex)
    _acronyms(report, pairs, ir, lex)
    _units(report, pairs)
    _relative_time(report, pairs, ir)
    _terminology(report, pairs, ir)
    _headings_lists(report, parsed, trace)
    return report


def _prose_pairs(report: SurfaceReport, check_id: str, pairs: Sequence[Pair]) -> Iterable[Pair]:
    for pair in pairs:
        if pair.exempt:
            report.skip(check_id, pair.block_id)
            continue
        report.saw(check_id)
        yield pair


def _wep_canonical(report: SurfaceReport, pairs: Sequence[Pair], lex) -> None:
    """OUT-WEP-CANONICAL: only canonical WEP phrases appear in prose (Section 8.3)."""
    for pair in _prose_pairs(report, "OUT-WEP-CANONICAL", pairs):
        for alias, canonical in sorted(lex.wep_aliases.items()):
            if contains_phrase(pair.text, alias):
                phrase = lex.wep_terms[canonical]["phrase"]
                report.flag(
                    "OUT-WEP-CANONICAL",
                    pair.block_id,
                    pair.line,
                    "noncanonical-wep-phrase",
                    f"block renders the noncanonical synonym {alias!r}; the canonical ATS-1 "
                    f"phrase for that band is {phrase!r}",
                )


def _wep_inline_range(report: SurfaceReport, pairs: Sequence[Pair], ir: IrDocument, lex) -> None:
    """OUT-WEP-INLINE-RANGE: first material WEP use per section shows its range (Section 8.4)."""
    if not lex.first_use_must_show_range:
        return
    seen_sections: set[str] = set()
    for pair in _prose_pairs(report, "OUT-WEP-INLINE-RANGE", pairs):
        for term_id, term in lex.wep_terms.items():
            if not contains_phrase(pair.text, term["phrase"]):
                continue
            section = pair.trace.section_id
            if section in seen_sections:
                continue
            seen_sections.add(section)
            expected = str(term["display_range"])
            haystack = pair.text.replace("\u2013", "-")
            if expected.replace("\u2013", "-") in haystack:
                continue
            report.flag(
                "OUT-WEP-INLINE-RANGE",
                pair.block_id,
                pair.line,
                "first-use-range-absent",
                f"the first material use of {term['phrase']!r} in section {section!r} does not "
                f"show its numeric range {expected!r} inline",
            )


def _deontic_keywords(report: SurfaceReport, pairs: Sequence[Pair], lex) -> None:
    """OUT-DEONTIC-KEYWORDS: closed uppercase vocabulary only (Sections 8.16, 8.17)."""
    for pair in _prose_pairs(report, "OUT-DEONTIC-KEYWORDS", pairs):
        for modal in lex.deontic_noncanonical:
            if contains_exact(pair.text, modal):
                report.flag(
                    "OUT-DEONTIC-KEYWORDS",
                    pair.block_id,
                    pair.line,
                    "noncanonical-modal-rendered",
                    f"block renders {modal!r}, which the lexicon marks noncanonical",
                )
        for requirement_id in pair.trace.data.get("requirement_ids", ()):
            if not any(
                contains_exact(pair.text, surface)
                for surface in lex.deontic_surfaces.values()
                if surface.isupper()
            ):
                report.flag(
                    "OUT-DEONTIC-KEYWORDS",
                    pair.block_id,
                    pair.line,
                    "requirement-without-uppercase-deontic",
                    f"block declares requirement {requirement_id!r} but renders no uppercase "
                    "ATS-1 deontic keyword, so the obligation strength is not normative "
                    "(spec 1.3)",
                )


def _acronyms(report: SurfaceReport, pairs: Sequence[Pair], ir: IrDocument, lex) -> None:
    """OUT-ACRONYMS: first material use expanded or permitted (Section 10.5)."""
    permitted: set[str] = set()
    for entry in ir.glossary:
        permitted.update(entry.get("approved_abbreviations", ()))
    permitted.update(s for s in lex.deontic_surfaces.values() if s.isupper())
    permitted.update(lex.deontic_noncanonical)
    permitted.update({"P0", "P1", "P2"})
    seen: set[str] = set()
    for pair in _prose_pairs(report, "OUT-ACRONYMS", pairs):
        for match in _ACRONYM.finditer(pair.text):
            acronym = match.group(1)
            if acronym in permitted or acronym in seen:
                continue
            seen.add(acronym)
            if re.search(r"[A-Za-z][\w\s/-]{2,}\s\(" + re.escape(acronym) + r"\)", pair.text):
                continue
            report.flag(
                "OUT-ACRONYMS",
                pair.block_id,
                pair.line,
                "acronym-not-expanded-in-output",
                f"first rendered use of {acronym!r} is neither expanded in place nor listed in "
                "the artifact's approved abbreviations",
            )


def _units(report: SurfaceReport, pairs: Sequence[Pair]) -> None:
    """OUT-UNITS: numbers the trace declares as P0 render with a unit (Sections 10.9, 9.3.8)."""
    for pair in _prose_pairs(report, "OUT-UNITS", pairs):
        for p0 in pair.trace.p0_fields:
            if _is_identifier_field(p0):
                continue
            rendered = str(p0.get("rendered", ""))
            match = _NUMBER.search(rendered)
            if match is None:
                continue
            unit = match.group(3)
            if unit:
                continue
            report.flag(
                "OUT-UNITS",
                pair.block_id,
                pair.line,
                "p0-number-without-unit",
                f"P0 field {p0.get('field_ref')!r} renders as {rendered!r} with no unit, "
                "dimension, or percent sign",
            )


def _relative_time(report: SurfaceReport, pairs: Sequence[Pair], ir: IrDocument) -> None:
    """OUT-RELATIVE-TIME: relative expressions are anchored (Section 10.11)."""
    for pair in _prose_pairs(report, "OUT-RELATIVE-TIME", pairs):
        hits = [t for t in RELATIVE_TIME_TERMS if contains_phrase(pair.text, t)]
        if not hits:
            continue
        anchored = False
        for claim_id in pair.trace.data.get("claim_ids", ()):
            claim = ir.claims.get(claim_id)
            if claim and any(str(claim.scope.get(f, "")).strip() for f in ANCHOR_FIELDS):
                anchored = True
                break
        if anchored:
            continue
        report.flag(
            "OUT-RELATIVE-TIME",
            pair.block_id,
            pair.line,
            "unanchored-relative-time-rendered",
            f"block renders {', '.join(repr(h) for h in hits)} and no claim it realizes declares "
            "a time horizon, version, evidence window, or environment to anchor it",
        )


def _terminology(report: SurfaceReport, pairs: Sequence[Pair], ir: IrDocument) -> None:
    """OUT-TERMINOLOGY: deprecated aliases and empty intensifiers (Sections 10.2, 10.20, 10.21)."""
    aliases = [
        (alias, entry["canonical_term"])
        for entry in ir.glossary
        for alias in entry.get("deprecated_aliases", ())
    ]
    for pair in _prose_pairs(report, "OUT-TERMINOLOGY", pairs):
        for alias, canonical in aliases:
            if contains_phrase(pair.text, alias):
                report.flag(
                    "OUT-TERMINOLOGY",
                    pair.block_id,
                    pair.line,
                    "deprecated-alias-rendered",
                    f"block renders {alias!r}, a deprecated alias of {canonical!r}",
                )
        for word in EMPTY_INTENSIFIERS:
            if contains_phrase(pair.text, word):
                report.flag(
                    "OUT-TERMINOLOGY",
                    pair.block_id,
                    pair.line,
                    "empty-intensifier",
                    f"block renders {word!r}, which Section 10.20 says SHOULD be removed when it "
                    "adds no calibrated meaning",
                )
        if pair.trace.material:
            for word in VAGUE_EVALUATIVE:
                if contains_phrase(pair.text, word):
                    report.flag(
                        "OUT-TERMINOLOGY",
                        pair.block_id,
                        pair.line,
                        "vague-evaluative-term",
                        f"material block renders {word!r} without an identified comparison, "
                        "threshold, or acceptance criterion (spec 10.21)",
                    )
        for word in VAGUE_TIMING:
            if contains_phrase(pair.text, word) and pair.trace.data.get("requirement_ids"):
                report.flag(
                    "OUT-TERMINOLOGY",
                    pair.block_id,
                    pair.line,
                    "vague-timing-term",
                    f"a requirement block renders {word!r}; Section 9.3.7 makes such terms "
                    "nonconforming when timing is material and no policy defines them",
                )


def _headings_lists(report: SurfaceReport, parsed: ParsedDocument, trace: OutputTrace) -> None:
    """OUT-HEADINGS-LISTS: heading nesting and list mechanics (Sections 10.17, 10.18)."""
    from .parse import headings

    check = "OUT-HEADINGS-LISTS"
    previous = 0
    for level, text, line in headings(parsed):
        report.saw(check)
        if previous and level > previous + 1:
            report.flag(
                check,
                "",
                line,
                "heading-level-skipped",
                f"heading {text!r} is level {level} directly under a level {previous} heading; "
                "the skipped level makes the document outline unrecoverable",
            )
        if not text.strip():
            report.flag(check, "", line, "empty-heading", "heading has no text")
        previous = level

    for block in parsed.blocks:
        if block.kind not in ("bullet_list", "ordered_list"):
            continue
        report.saw(check)
        items = [ln for ln in block.text.split("\n") if ln.strip().startswith(("-", "*", "+"))]
        if block.kind == "bullet_list" and len(items) == 1:
            report.flag(
                check,
                block.marker_id or "",
                block.start_line,
                "single-item-list",
                "a one-item list implies coordinate items that do not exist (spec 10.18)",
            )

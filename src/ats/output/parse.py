"""Markdown parsing and block modelling.

Spec Section 14.4: a parser MUST preserve enough source mapping to localize
findings and patches, a parser failure MUST identify the affected region, and a
failure MUST NOT cause the implementation to silently run token-only rules and
report full conformance.

Parsing goes through ``markdown-it-py`` (CommonMark) rather than regular
expressions. Regexes are used only to recognise the ATS block marker, which is
a fixed HTML comment this implementation emits itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Final, Iterator, Sequence

from markdown_it import MarkdownIt
from markdown_it.token import Token

from ..errors import ParseError

#: The marker scheme declared in ``ats_output_trace_v1.schema.json``.
MARKER_OPEN = re.compile(r"^<!--\s*ats:block\s+([a-z0-9][a-z0-9-]{0,127})\s*-->$")
MARKER_CLOSE = re.compile(r"^<!--\s*/ats:block\s+([a-z0-9][a-z0-9-]{0,127})\s*-->$")

#: Parser identity recorded on every report, so a parser change invalidates a
#: prior receipt's replay claim (spec Section 15.8).
PARSER_NAME: Final[str] = "markdown-it-py/commonmark"


def parser_version() -> str:
    from markdown_it import __version__ as mdit_version

    return f"{PARSER_NAME}@{mdit_version}"


#: Block-level constructs this implementation evaluates. Anything else is
#: reported as unsupported rather than silently skipped (spec Section 16.3).
SUPPORTED_BLOCK_TYPES: Final[frozenset[str]] = frozenset(
    {
        "heading",
        "paragraph",
        "bullet_list",
        "ordered_list",
        "list_item",
        "table",
        "fence",
        "code_block",
        "blockquote",
        "hr",
        "html_block",
    }
)

#: Constructs Section 16.3 requires an implementation to test parsing against.
REQUIRED_CONSTRUCTS: Final[tuple[str, ...]] = (
    "heading",
    "bullet_list",
    "ordered_list",
    "table",
    "fence",
    "blockquote",
    "code_inline",
    "link",
    "footnote",
    "html_block",
)


@dataclass(frozen=True, slots=True)
class MarkdownBlock:
    """One top-level block of the document, with its source line range."""

    index: int
    kind: str
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive
    text: str
    marker_id: str | None = None
    marker_line: int | None = None

    @property
    def text_bytes(self) -> bytes:
        return self.text.encode("utf-8")


@dataclass(frozen=True, slots=True)
class UnsupportedConstruct:
    construct: str
    line: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"construct": self.construct, "line": self.line, "detail": self.detail}


@dataclass(slots=True)
class ParsedDocument:
    text: str
    lines: list[str]
    blocks: list[MarkdownBlock] = field(default_factory=list)
    unsupported: list[UnsupportedConstruct] = field(default_factory=list)
    constructs_seen: set[str] = field(default_factory=set)

    def block_by_marker(self, marker_id: str) -> MarkdownBlock | None:
        for block in self.blocks:
            if block.marker_id == marker_id:
                return block
        return None

    def markers_in_order(self) -> list[str]:
        return [b.marker_id for b in self.blocks if b.marker_id]

    def duplicate_markers(self) -> list[str]:
        seen: dict[str, int] = {}
        for marker in self.markers_in_order():
            seen[marker] = seen.get(marker, 0) + 1
        return sorted(m for m, n in seen.items() if n > 1)


def _build_parser() -> MarkdownIt:
    md = MarkdownIt("commonmark")
    md.enable("table")
    md.enable("strikethrough")
    return md


def parse_markdown(text: str, *, locator: str = "<document>") -> ParsedDocument:
    """Parse ``text`` into an ATS block model.

    Raises :class:`~ats.errors.ParseError` naming the affected region when the
    parser cannot produce a usable token stream.
    """
    md = _build_parser()
    try:
        tokens: list[Token] = md.parse(text)
    except Exception as exc:  # pragma: no cover - markdown-it is total on str
        raise ParseError(f"markdown parsing failed: {exc}", locator=locator) from exc

    lines = text.split("\n")
    parsed = ParsedDocument(text=text, lines=lines)

    # Marker lines are html_block tokens. Collect them first so a marker can be
    # attached to the block that follows it.
    pending_marker: tuple[str, int] | None = None
    index = 0
    depth = 0

    for token in tokens:
        if token.nesting == 1:
            depth += 1
        elif token.nesting == -1:
            depth -= 1
            continue
        if token.type.endswith("_close"):
            continue
        if token.type == "inline" or token.map is None:
            # Inline tokens are children of a block; their constructs are
            # recorded, but they never become ATS blocks in their own right.
            _record_inline_constructs(token, parsed)
            continue

        start, end = token.map[0] + 1, token.map[1]
        kind = token.type.removesuffix("_open")
        parsed.constructs_seen.add(kind)

        if kind == "html_block":
            raw = token.content.strip()
            opened = MARKER_OPEN.match(raw)
            if opened:
                pending_marker = (opened.group(1), start)
                continue
            if MARKER_CLOSE.match(raw):
                continue
            parsed.unsupported.append(
                UnsupportedConstruct(
                    "html_block",
                    start,
                    "raw HTML that is not an ATS block marker is not evaluated by the surface "
                    "checks; its content is neither parsed nor exempted (spec 16.3)",
                )
            )

        # Only top-level constructs become ATS blocks. Anything nested — a
        # sublist, a table or fence inside a list item, a paragraph inside a
        # block quote — stays inside its parent's text, so a block's hash
        # covers the whole construct and `index` partitions the document
        # instead of overlapping it.
        if depth > 1:
            continue
        if kind not in SUPPORTED_BLOCK_TYPES:
            parsed.unsupported.append(
                UnsupportedConstruct(
                    kind, start, f"block construct {kind!r} is parsed but not evaluated"
                )
            )
            continue
        if kind == "list_item":
            # Unreachable while list items are always nested, but kept so a
            # future parser change cannot silently promote one.
            continue

        body = "\n".join(lines[start - 1 : end]).rstrip("\n")
        marker_id = marker_line = None
        if pending_marker is not None:
            marker_id, marker_line = pending_marker
            pending_marker = None
        parsed.blocks.append(
            MarkdownBlock(
                index=index,
                kind=kind,
                start_line=start,
                end_line=end,
                text=body,
                marker_id=marker_id,
                marker_line=marker_line,
            )
        )
        index += 1

        for child in token.children or ():
            _record_inline_constructs(child, parsed)

    if pending_marker is not None:
        marker, line = pending_marker
        raise ParseError(
            f"block marker {marker!r} is not followed by any block content",
            locator=locator,
            line=line,
        )
    return parsed


def _record_inline_constructs(token: Token, parsed: ParsedDocument) -> None:
    if token.type in ("code_inline", "link_open", "footnote_ref", "image", "html_inline"):
        parsed.constructs_seen.add(token.type.removesuffix("_open"))
    for child in token.children or ():
        _record_inline_constructs(child, parsed)


def iter_marked_blocks(parsed: ParsedDocument) -> Iterator[MarkdownBlock]:
    for block in parsed.blocks:
        if block.marker_id:
            yield block


def strip_markers(text: str) -> str:
    """Remove marker lines, leaving the document as an ordinary reader sees it."""
    return "\n".join(
        line
        for line in text.split("\n")
        if not MARKER_OPEN.match(line.strip()) and not MARKER_CLOSE.match(line.strip())
    )


def headings(parsed: ParsedDocument) -> list[tuple[int, str, int]]:
    """``(level, text, line)`` for every heading, in document order."""
    out: list[tuple[int, str, int]] = []
    for block in parsed.blocks:
        if block.kind != "heading":
            continue
        stripped = block.text.lstrip()
        level = len(stripped) - len(stripped.lstrip("#"))
        out.append((level, stripped.lstrip("#").strip(), block.start_line))
    return out


def missing_required_constructs(parsed: ParsedDocument) -> Sequence[str]:
    """Constructs Section 16.3 names that this document does not exercise."""
    return tuple(c for c in REQUIRED_CONSTRUCTS if c not in parsed.constructs_seen)

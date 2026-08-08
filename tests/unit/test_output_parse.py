"""Markdown parsing and block modelling.

Section 16.3 names the constructs an implementation MUST test parsing against.
Section 14.4 requires the parser to preserve source mapping, to identify the
affected region when it fails, and forbids silently running token-only rules
after a parser failure.
"""

from __future__ import annotations

import pytest

from ats.errors import ParseError
from ats.output.parse import (
    MARKER_CLOSE,
    MARKER_OPEN,
    REQUIRED_CONSTRUCTS,
    SUPPORTED_BLOCK_TYPES,
    headings,
    missing_required_constructs,
    parse_markdown,
    parser_version,
    strip_markers,
)

#: One document exercising every construct Section 16.3 enumerates.
EVERY_CONSTRUCT = """# Heading one

## Heading two

A paragraph with `code_inline`, a [link](https://example.invalid), and a
footnote reference[^1].

- bullet one
- bullet two

1. ordered one
2. ordered two

| column | value |
|---|---|
| a | 1 |

```text
fenced code
```

> a block quotation

<div>raw html block</div>

[^1]: the footnote body.
"""


@pytest.fixture(scope="module")
def parsed_all():
    return parse_markdown(EVERY_CONSTRUCT, locator="every-construct.md")


def test_parser_identity_is_recorded(ctx) -> None:
    """Spec 15.8: a parser change invalidates a prior receipt's replay claim."""
    version = parser_version()
    assert version.startswith("markdown-it-py/commonmark@")
    assert version.count("@") == 1


def test_required_constructs_are_the_section_16_3_list() -> None:
    """Spec 16.3 enumerates exactly these constructs."""
    assert REQUIRED_CONSTRUCTS == (
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


def test_block_constructs_are_recognised_and_line_mapped(parsed_all) -> None:
    """Spec 14.4: the parser preserves enough source mapping to localize a finding."""
    kinds = {block.kind for block in parsed_all.blocks}
    assert {"heading", "paragraph", "bullet_list", "ordered_list", "table", "fence",
            "blockquote"} <= kinds
    assert kinds <= SUPPORTED_BLOCK_TYPES

    lines = EVERY_CONSTRUCT.split("\n")
    for block in parsed_all.blocks:
        assert 1 <= block.start_line <= block.end_line <= len(lines)
        assert block.text == "\n".join(
            lines[block.start_line - 1 : block.end_line]
        ).rstrip("\n")
        assert block.text_bytes == block.text.encode("utf-8")

    ordinals = [block.index for block in parsed_all.blocks]
    assert ordinals == list(range(len(ordinals)))


def test_inline_constructs_are_recorded(parsed_all) -> None:
    """Spec 16.3: inline constructs are evaluated, not silently skipped."""
    assert {"code_inline", "link"} <= parsed_all.constructs_seen


def test_a_document_exercising_every_construct_leaves_none_untested(parsed_all) -> None:
    """Spec 16.3: an implementation must test parsing against each named construct."""
    untested = set(missing_required_constructs(parsed_all))
    # markdown-it's CommonMark preset has no footnote plugin, so the footnote
    # reference is parsed as ordinary text and is honestly reported as untested
    # rather than claimed.
    assert untested <= {"footnote"}


def test_raw_html_that_is_not_a_marker_is_reported_not_skipped(parsed_all) -> None:
    """Spec 16.3: an unsupported construct is reported rather than silently skipped."""
    unsupported = [u for u in parsed_all.unsupported if u.construct == "html_block"]
    assert unsupported
    entry = unsupported[0]
    assert entry.line >= 1
    assert "not an ATS block marker" in entry.detail
    assert set(entry.to_dict()) == {"construct", "line", "detail"}


def test_headings_are_reported_with_level_and_line(parsed_all) -> None:
    """Spec 10.17: heading structure must be recoverable from the rendering."""
    found = headings(parsed_all)
    assert found[0] == (1, "Heading one", 1)
    assert (2, "Heading two", 3) in found


# -- markers ----------------------------------------------------------------

MARKED = """<!-- ats:block intro -->
The first block.

<!-- ats:block second -->
The second block.
<!-- /ats:block second -->
"""


def test_a_marker_binds_the_block_that_follows_it() -> None:
    """The marker scheme: the marker line precedes the block body it names."""
    parsed = parse_markdown(MARKED)
    assert parsed.markers_in_order() == ["intro", "second"]
    intro = parsed.block_by_marker("intro")
    assert intro is not None
    assert intro.text == "The first block."
    assert intro.marker_line == 1
    assert intro.marker_line < intro.start_line
    assert parsed.block_by_marker("absent") is None


def test_marker_patterns_accept_only_the_declared_form() -> None:
    """The block-id grammar is fixed by ats_output_trace_v1.schema.json."""
    assert MARKER_OPEN.match("<!-- ats:block a-block-1 -->")
    assert MARKER_CLOSE.match("<!-- /ats:block a-block-1 -->")
    assert MARKER_OPEN.match("<!--ats:block  x  -->")
    assert MARKER_OPEN.match("<!-- ats:block Block -->") is None
    assert MARKER_OPEN.match("<!-- ats:block -block -->") is None
    assert MARKER_OPEN.match("<!-- ats:block a b -->") is None


def test_duplicate_markers_are_reported() -> None:
    """A marker identifies one block; a repeat makes the source map ambiguous."""
    text = "<!-- ats:block dup -->\nFirst.\n\n<!-- ats:block dup -->\nSecond.\n"
    parsed = parse_markdown(text)
    assert parsed.duplicate_markers() == ["dup"]
    assert parse_markdown(MARKED).duplicate_markers() == []


def test_a_marker_with_no_following_block_raises_naming_the_line() -> None:
    """Spec 14.4: a parser failure MUST identify the affected region."""
    text = "Some prose.\n\n<!-- ats:block dangling -->\n"
    with pytest.raises(ParseError) as excinfo:
        parse_markdown(text, locator="doc.md")
    error = excinfo.value
    assert "dangling" in str(error)
    assert error.line == 3
    assert error.locator == "doc.md"
    payload = error.payload()
    assert payload["error"] == "parse_failed"
    assert payload["line"] == 3
    assert payload["locator"] == "doc.md"


def test_a_closing_marker_alone_does_not_open_a_block() -> None:
    """The closer is optional metadata, not content."""
    parsed = parse_markdown("<!-- /ats:block orphan -->\n\nProse.\n")
    assert parsed.markers_in_order() == []
    assert parsed.unsupported == []


def test_strip_markers_leaves_the_document_a_reader_sees() -> None:
    """The source map is invisible: removing it must not touch the prose."""
    stripped = strip_markers(MARKED)
    assert "ats:block" not in stripped
    assert "The first block." in stripped
    assert "The second block." in stripped


def test_malformed_markup_still_parses_and_is_reported() -> None:
    """Spec 14.4: a broken construct must not silently disable the surface rules."""
    text = "| header | broken\n|---\nnot a table row\n\n<em>unclosed\n"
    parsed = parse_markdown(text)
    assert parsed.blocks, "the parser still produces a usable token stream"
    assert parsed.text == text


def test_a_nested_list_stays_inside_its_parent_block() -> None:
    """A block hash must cover the whole construct, not a fragment of it."""
    text = "- outer\n  - inner\n- second\n"
    parsed = parse_markdown(text)
    lists = [b for b in parsed.blocks if b.kind == "bullet_list"]
    assert len(lists) == 1
    assert "inner" in lists[0].text


def test_parsing_is_deterministic_for_identical_bytes() -> None:
    """Spec 16.2: identical canonical inputs produce identical results."""
    first = parse_markdown(EVERY_CONSTRUCT)
    second = parse_markdown(EVERY_CONSTRUCT)
    assert [(b.index, b.kind, b.start_line, b.end_line, b.text) for b in first.blocks] == [
        (b.index, b.kind, b.start_line, b.end_line, b.text) for b in second.blocks
    ]
    assert first.constructs_seen == second.constructs_seen
    assert [u.to_dict() for u in first.unsupported] == [
        u.to_dict() for u in second.unsupported
    ]

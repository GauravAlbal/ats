"""Source hashing and text normalization.

Spec Section 14.2: the implementation MUST bind the exact input bytes to a
content hash before evaluation, and when preprocessing changes the text it MUST
preserve both original and normalized hashes plus a deterministic mapping.

Appendix C: a text normalization step MUST produce and retain a separate
normalized hash rather than replacing the source hash.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .canonical import sha256_hex
from .errors import UsageError

#: Version of the normalization procedure. Any change to :func:`normalize_text`
#: MUST bump this, because normalized hashes recorded under the old procedure
#: are no longer reproducible.
NORMALIZATION_VERSION = "ats-normalize-v1"


@dataclass(frozen=True, slots=True)
class SourceBinding:
    """The content-addressed binding of one source artifact."""

    content_sha256: str
    normalized_sha256: str
    byte_length: int
    normalized_length: int
    normalization_version: str
    #: Monotone map from normalized character offset to source character offset.
    #: Index ``i`` holds the source offset of normalized character ``i``; the
    #: final entry is the source length, so a half-open normalized span maps to
    #: a half-open source span.
    #:
    #: ``None`` when the binding was built without it. The map costs one entry
    #: per character, so it is not built for callers that only need hashes.
    offset_map: tuple[int, ...] | None

    def to_source_span(self, start: int, end: int) -> tuple[int, int]:
        """Map a half-open normalized span back onto source character offsets."""
        if self.offset_map is None:
            raise UsageError(
                "this binding carries no offset map; rebuild it with "
                "bind_text(..., offsets=True) to map normalized spans onto source"
            )
        if not 0 <= start <= end < len(self.offset_map):
            raise UsageError(f"normalized span [{start},{end}) is outside the mapped range")
        return self.offset_map[start], self.offset_map[end]


#: Per-character NFC results, memoized. The composition of a single character
#: is a pure function of that character, and a corpus reuses the same few
#: thousand of them, so the cache is bounded by the alphabet in use.
_NFC_CHAR: dict[str, str] = {}


def normalize_text(text: str) -> tuple[str, tuple[int, ...]]:
    """Normalize ``text`` and return ``(normalized, offset_map)``.

    The procedure is deliberately minimal and reversible in position:

    * Unicode NFC composition applied per character, so offsets stay alignable;
    * CRLF and CR line endings collapsed to LF;
    * trailing horizontal whitespace removed from each line.

    Nothing else is removed. Normalization exists to make hashing stable across
    line-ending and composition differences, not to rewrite the artifact.
    """
    normalized, offsets = _normalize(text, offsets=True)
    assert offsets is not None
    return normalized, offsets


def _normalize(text: str, *, offsets: bool) -> tuple[str, tuple[int, ...] | None]:
    """Shared normalization core; builds the offset map only when asked.

    Work proceeds a line at a time rather than a character at a time. Interior
    spaces and tabs survive verbatim, so only the trailing run has to be found,
    and NFC is the identity on ASCII, so an all-ASCII line is already its own
    normalization and can be copied whole. A per-character loop produced the
    same string, but it dominated the cost of hashing a corpus.
    """
    out: list[str] = []
    pos_map: list[int] | None = [] if offsets else None
    i = 0
    n = len(text)
    while i < n:
        end = i
        while end < n and text[end] not in "\r\n":
            end += 1
        # Trailing horizontal whitespace is dropped, including at end of text
        # where no line terminator follows.
        content_end = end
        while content_end > i and text[content_end - 1] in " \t":
            content_end -= 1

        segment = text[i:content_end]
        if segment.isascii():
            out.append(segment)
            if pos_map is not None:
                pos_map.extend(range(i, content_end))
        else:
            for source_index in range(i, content_end):
                char = text[source_index]
                if char.isascii():
                    out.append(char)
                    if pos_map is not None:
                        pos_map.append(source_index)
                    continue
                composed = _NFC_CHAR.get(char)
                if composed is None:
                    # Per character, never over the whole string: composing
                    # across a character boundary would merge two source
                    # positions into one and break the offset map.
                    composed = _NFC_CHAR[char] = unicodedata.normalize("NFC", char)
                out.append(composed)
                if pos_map is not None:
                    pos_map.extend([source_index] * len(composed))

        if end < n:
            out.append("\n")
            if pos_map is not None:
                pos_map.append(end)
            i = end + 2 if text[end] == "\r" and end + 1 < n and text[end + 1] == "\n" else end + 1
        else:
            i = end

    if pos_map is None:
        return "".join(out), None
    pos_map.append(n)
    return "".join(out), tuple(pos_map)


def bind_text(
    text: str, *, raw: bytes | None = None, offsets: bool = False
) -> SourceBinding:
    """Bind ``text`` to its content and normalized hashes.

    ``offsets`` builds the normalized-to-source map as well. It costs one
    entry per character and only :meth:`SourceBinding.to_source_span` reads it,
    so it is off unless a caller asks to map spans back onto the source.
    """
    data = raw if raw is not None else text.encode("utf-8")
    normalized, offset_map = _normalize(text, offsets=offsets)
    return SourceBinding(
        content_sha256=sha256_hex(data),
        normalized_sha256=sha256_hex(normalized.encode("utf-8")),
        byte_length=len(data),
        normalized_length=len(normalized),
        normalization_version=NORMALIZATION_VERSION,
        offset_map=offset_map,
    )


def bind_file(path: str | Path) -> SourceBinding:
    """Bind a file's exact bytes, decoding as UTF-8 for normalization."""
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise UsageError(f"cannot read {p}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UsageError(f"{p} is not valid UTF-8: {exc}") from exc
    return bind_text(text, raw=raw)


def file_sha256(path: str | Path) -> str:
    """SHA-256 over a file's exact bytes."""
    p = Path(path)
    h = __import__("hashlib").sha256()
    try:
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
    except OSError as exc:
        raise UsageError(f"cannot read {p}: {exc}") from exc
    return h.hexdigest()

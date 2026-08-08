"""Context bundles: everything an annotator needs to adjudicate one span.

Spec Section 17.4 says an isolated sentence SHOULD NOT be labeled when the rule
depends on document context that was discarded. A bundle therefore carries the
complete containing block, the heading path, the neighbouring blocks, local
definitions, glossary entries, a profile hypothesis with its basis, policy
context, the diff that produced the span, the review comment on it, and any
later edit — each with an explicit ``availability`` state, and the whole bundle
with a ``context_completeness`` verdict so a truncated bundle announces itself
instead of looking complete.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

from ..canonical import content_hash
from ..errors import ParseError, UsageError
from ..output.parse import headings as _md_headings
from ..output.parse import parse_markdown
from . import inventory as inv
from . import records as rec

#: markdown-it block kind -> the ``containing_block.kind`` enum in
#: ``ats_context_bundle_v1.schema.json``. A construct with no representation is
#: refused rather than mislabelled.
BLOCK_KINDS: Final[dict[str, str]] = {
    "heading": "heading",
    "paragraph": "paragraph",
    "bullet_list": "list",
    "ordered_list": "list",
    "list_item": "list_item",
    "table": "table",
    "fence": "code_block",
    "code_block": "code_block",
    "blockquote": "block_quote",
}

#: An availability answer for a dimension nobody looked for, because the caller
#: supplied no repository to look in.
NOT_SEARCHED_NO_REPO: Final[str] = "no repository path was supplied, so git was not searched"


@dataclass(frozen=True, slots=True)
class Block:
    """One block of a source document, in both line and character coordinates."""

    kind: str
    start_line: int
    end_line: int
    start: int
    end: int
    text: str


def _line_offsets(text: str) -> list[int]:
    offsets = [0]
    for line in text.split("\n")[:-1]:
        offsets.append(offsets[-1] + len(line) + 1)
    return offsets


def document_blocks(text: str, *, media_type: str) -> list[Block]:
    """The block model of a source document.

    Markdown is parsed with the same CommonMark parser the output linter uses,
    so a corpus bundle and a lint report agree about what a block is. Plain text
    has no block grammar, so its blocks are blank-line-separated paragraphs.
    """
    offsets = _line_offsets(text)
    total = len(text)

    def bounds(start_line: int, end_line: int) -> tuple[int, int]:
        start = offsets[start_line - 1] if start_line - 1 < len(offsets) else total
        end = offsets[end_line] if end_line < len(offsets) else total
        return start, end

    if media_type == "text/markdown":
        try:
            parsed = parse_markdown(text)
        except ParseError as exc:
            raise UsageError(f"source document cannot be parsed: {exc}") from exc
        out: list[Block] = []
        for block in parsed.blocks:
            kind = BLOCK_KINDS.get(block.kind)
            if kind is None:
                continue
            start, end = bounds(block.start_line, block.end_line)
            out.append(Block(kind, block.start_line, block.end_line, start, end, block.text))
        return out

    blocks: list[Block] = []
    line_no = 1
    buffer: list[str] = []
    buffer_start = 1
    for line in text.split("\n"):
        if line.strip():
            if not buffer:
                buffer_start = line_no
            buffer.append(line)
        elif buffer:
            start, end = bounds(buffer_start, line_no - 1)
            blocks.append(
                Block("paragraph", buffer_start, line_no - 1, start, end, "\n".join(buffer))
            )
            buffer = []
        line_no += 1
    if buffer:
        start, end = bounds(buffer_start, line_no - 1)
        blocks.append(
            Block("paragraph", buffer_start, line_no - 1, start, end, "\n".join(buffer))
        )
    return blocks


def heading_path_at(text: str, line: int) -> list[str]:
    """The heading stack in effect at ``line`` (1-based)."""
    try:
        parsed = parse_markdown(text)
    except ParseError:
        return []
    stack: list[tuple[int, str]] = []
    for level, title, heading_line in _md_headings(parsed):
        if heading_line > line:
            break
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
    return [title for _level, title in stack]


def local_definitions(text: str) -> list[dict[str, str]]:
    """Definitions the document explicitly declares.

    Only ``<!-- ats:define <term> -->`` markers are collected, in the same
    comment-marker family as the block markers the output linter reads.
    Inferring a definition from ordinary prose would fabricate declared glossary
    content, which spec Section 10.3 treats as an authored artifact.
    """
    lines = text.split("\n")
    out: list[dict[str, str]] = []
    for index, line in enumerate(lines):
        match = inv.DEFINE_MARKER.match(line.strip())
        if not match:
            continue
        body: list[str] = []
        for following in lines[index + 1 :]:
            if not following.strip():
                if body:
                    break
                continue
            body.append(following.strip())
        if not body:
            continue
        out.append(
            {
                "term": match.group(1),
                "definition": " ".join(body),
                "locator": f"line:{index + 2}",
            }
        )
    return out


def _optional_text(
    availability: str, *, text: str | None = None, locator: str | None = None
) -> dict[str, Any]:
    value: dict[str, Any] = {"availability": availability}
    if text is not None:
        value["text"] = text
    if locator is not None:
        value["locator"] = locator
    return value


def _profile_hypothesis(
    artifact: Mapping[str, Any], heading_path: Sequence[str], *, hint: str | None
) -> dict[str, Any]:
    """Which profile governs the span, and on what basis.

    The field is required, so a hypothesis is always produced; the ``basis`` is
    what makes it honest. ``unknown`` means the document supplied no evidence,
    and :func:`build_context_bundle` degrades ``context_completeness``
    accordingly rather than letting a guess read as a determination.
    """
    declared = list(artifact.get("profile_hypotheses") or ())
    if hint:
        return {
            "profile": hint,
            "basis": "annotator_supplied",
            "alternatives": [p for p in declared if p != hint] or None,
        }

    for profile in declared:
        if any(re.search(rf"\b{profile}\b", segment, re.IGNORECASE) for segment in heading_path):
            return {
                "profile": profile,
                "basis": "heading_path",
                "alternatives": [p for p in declared if p != profile] or None,
            }
    if declared:
        evidence = (artifact.get("extensions") or {}).get(f"{rec.EXT_PREFIX}git", {})
        bases = {e.get("basis") for e in evidence.get("profile_evidence", ())}
        basis = "declared_front_matter" if "declared_front_matter" in bases else "path_convention"
        return {
            "profile": declared[0],
            "basis": basis,
            "alternatives": declared[1:] or None,
        }
    return {
        "profile": inv.STABLE_PROFILES[0],
        "basis": "unknown",
        "alternatives": list(inv.STABLE_PROFILES[1:]),
    }


def _git_context(
    repo_path: str | Path | None, artifact: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """``(diff, later_edit, reversal)`` for the artifact's pinned revision."""
    if repo_path is None:
        return (
            _optional_text("not_searched", locator=NOT_SEARCHED_NO_REPO),
            _optional_text("not_searched", locator=NOT_SEARCHED_NO_REPO),
            None,
        )
    repo = Path(repo_path)
    revision = artifact["revision"]
    path = artifact["path"]
    try:
        diff_text = inv.commit_diff(repo, revision, path)
    except inv.GitUnavailable as exc:
        diff = _optional_text("unavailable", locator=str(exc))
    else:
        diff = (
            _optional_text("present", text=diff_text, locator=f"git:{revision}")
            if diff_text.strip()
            else _optional_text("not_found", locator=f"git:{revision}")
        )

    git_extension = (artifact.get("extensions") or {}).get(f"{rec.EXT_PREFIX}git", {})
    later_shas = list((git_extension.get("later_edits") or {}).get("commits", ()))
    if not later_shas:
        later = _optional_text(
            "not_found",
            locator=f"no commit after {revision[:12]} touches {path}",
        )
        return diff, later, None

    next_sha = later_shas[-1]
    try:
        later_diff = inv.commit_diff(repo, next_sha, path)
    except inv.GitUnavailable as exc:
        return diff, _optional_text("unavailable", locator=str(exc)), None
    later = _optional_text("present", text=later_diff, locator=f"git:{next_sha}")

    reversal = None
    for sha in later_shas:
        try:
            commits = inv.path_history(repo, sha, path)
        except inv.GitUnavailable:
            break
        if commits and inv._REVERT_LINE.search(commits[0].message):
            reversal = _optional_text(
                "present", text=commits[0].message, locator=f"git:{commits[0].sha}"
            )
            break
    return diff, later, reversal


def _review_comment(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """The review commentary the inventory already collected, as optional text."""
    evidence = artifact.get("acceptance_evidence") or {"availability": "not_searched"}
    availability = evidence.get("availability", "not_searched")
    if availability != "present":
        return _optional_text(availability, locator=evidence.get("notes"))
    return _optional_text(
        "present",
        text=evidence.get("notes") or "",
        locator=evidence.get("locator"),
    )


def _policy_context(policy_document: Mapping[str, Any] | None) -> dict[str, Any]:
    """The policy snapshot in force, or an explicit statement that none was supplied."""
    if policy_document is None:
        return {"availability": "not_searched"}
    snapshot_id = policy_document.get("policy_snapshot_id")
    context: dict[str, Any] = {
        "availability": "present",
        "policy_sha256": policy_document.get("snapshot_sha256")
        or content_hash(dict(policy_document)),
    }
    if snapshot_id:
        context["policy_snapshot_id"] = str(snapshot_id)
    return context


def _completeness(
    *,
    profile_basis: str,
    preceding: Mapping[str, Any],
    following: Mapping[str, Any],
    diff: Mapping[str, Any],
    review_comment: Mapping[str, Any],
    later_edit: Mapping[str, Any],
    policy_context: Mapping[str, Any],
) -> str:
    """Rate how much of the required context is actually present.

    ``complete`` requires every dimension to have been searched successfully and
    the profile to rest on evidence in the document. ``not_found`` after a real
    search still counts as searched: a document genuinely without a later edit
    is not missing context. ``not_searched``, ``unavailable``, ``withheld``, and
    an unknown profile basis all degrade the verdict, because an annotator who
    cannot see those dimensions is being asked to label from a fragment.
    """
    searched = ("present", "not_found", "not_applicable")
    dimensions = (preceding, following, diff, review_comment, later_edit, policy_context)
    unsearched = [d for d in dimensions if d.get("availability") not in searched]
    if profile_basis == "unknown":
        return "insufficient" if unsearched else "partial"
    if not unsearched:
        return "complete"
    return "partial" if len(unsearched) < len(dimensions) else "insufficient"


def build_context_bundle(
    ctx: Any,
    *,
    artifact: Mapping[str, Any],
    text: str,
    span: Mapping[str, Any],
    repo_path: str | Path | None = None,
    policy_document: Mapping[str, Any] | None = None,
    glossary_entries: Sequence[Mapping[str, Any]] = (),
    profile_hint: str | None = None,
) -> dict[str, Any]:
    """Build a content-addressed ``ContextBundleV1`` for one candidate span.

    ``span`` is a character span into ``text``. The bundle is validated against
    its schema before it is returned, so a caller never receives a bundle that
    cannot be stored.
    """
    if span.get("kind") != "character":
        raise UsageError(
            f"a context bundle is built from a character span, got kind={span.get('kind')!r}"
        )
    start, end = int(span["start"]), int(span["end"])
    if not 0 <= start < end <= len(text):
        raise UsageError(f"span [{start},{end}) is outside the {len(text)}-character document")

    span_text = text[start:end]
    blocks = document_blocks(text, media_type=artifact.get("media_type", "text/markdown"))
    containing = next((b for b in blocks if b.start <= start and end <= b.end), None)
    if containing is None:
        raise UsageError(
            f"span [{start},{end}) does not fall inside a single block; a corpus example MUST "
            "carry its complete containing block (spec 17.4)"
        )

    index = blocks.index(containing)
    preceding = (
        _optional_text(
            "present",
            text=blocks[index - 1].text,
            locator=f"line:{blocks[index - 1].start_line}",
        )
        if index > 0
        else _optional_text("not_found", locator="the span is in the first block of the document")
    )
    following = (
        _optional_text(
            "present",
            text=blocks[index + 1].text,
            locator=f"line:{blocks[index + 1].start_line}",
        )
        if index + 1 < len(blocks)
        else _optional_text("not_found", locator="the span is in the last block of the document")
    )

    heading_path = (
        heading_path_at(text, containing.start_line)
        if artifact.get("media_type") == "text/markdown"
        else []
    )
    hypothesis = _profile_hypothesis(artifact, heading_path, hint=profile_hint)
    hypothesis = {k: v for k, v in hypothesis.items() if v is not None}
    diff, later_edit, reversal = _git_context(repo_path, artifact)
    review_comment = _review_comment(artifact)
    policy_context = _policy_context(policy_document)

    bundle = rec.context_bundle(
        source_artifact_id=artifact["artifact_id"],
        source_revision=artifact["revision"],
        source_span={
            "kind": "character",
            "start": start,
            "end": end,
            "source_sha256": artifact["content_sha256"],
        },
        span_text=span_text,
        containing_block={
            "kind": containing.kind,
            "text": containing.text,
            "span": {"kind": "character", "start": containing.start, "end": containing.end},
        },
        heading_path=heading_path,
        preceding_context=preceding,
        following_context=following,
        local_definitions=local_definitions(text),
        glossary_entries=[dict(g) for g in glossary_entries],
        profile_hypothesis=hypothesis,
        policy_context=policy_context,
        diff=diff,
        review_comment=review_comment,
        later_edit=later_edit,
        reversal=reversal,
        context_completeness=_completeness(
            profile_basis=hypothesis["basis"],
            preceding=preceding,
            following=following,
            diff=diff,
            review_comment=review_comment,
            later_edit=later_edit,
            policy_context=policy_context,
        ),
    )
    ctx.schemas.validate_document(bundle)
    return bundle

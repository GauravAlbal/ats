"""Local Git inventory of corpus source documents.

Spec Section 16.9 requires an implementation to declare whether source text
leaves the local environment. This module answers *never*: it shells out to
``git`` with an explicit argv, and the subcommand of every invocation is checked
against :data:`READ_ONLY_GIT_SUBCOMMANDS` before the process is spawned. There
is no fetch, clone, remote, push, or submodule path here, and a caller cannot
smuggle one in.

Spec Section 17.4 lists what mining MUST preserve: complete local context,
heading and profile context, glossary and policy context, source revision,
author or model provenance, subsequent edits, review comments, acceptance
outcomes, and downstream defects or reversals. Every one of those dimensions is
either populated or carries an explicit ``availability`` state from
``ats_common_v1#/$defs/availability``. A dimension is never silently absent, and
``accepted``, ``rejected``, ``superseded``, and ``reverted`` are kept as distinct
review states rather than collapsed into "it was merged, so it is fine".
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

from ..canonical import sha256_hex
from ..errors import ParseError, UsageError
from ..hashes import bind_text
from ..output.parse import parse_markdown
from . import authorship as auth
from . import records as rec
from .authority import (
    AuthorityDeclaration,
    coarse_recognised,
    intersect_coarse,
    require_provenance,
)

#: Git subcommands this module may run. Every one is a local read; none of them
#: can contact a network peer. An invocation outside this set is refused before
#: the process is created.
READ_ONLY_GIT_SUBCOMMANDS: Final[frozenset[str]] = frozenset(
    {"rev-parse", "ls-tree", "log", "cat-file", "show", "notes", "config", "status"}
)

#: Environment forced on every ``git`` invocation. Terminal prompting and
#: system/global configuration are disabled so the inventory of a repository
#: does not depend on who is running it.
GIT_ENV: Final[dict[str, str]] = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": "/bin/false",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_OPTIONAL_LOCKS": "0",
    # Every path this module passes to git is a literal path read out of the
    # repository, never a pattern: include and exclude globs are applied in
    # Python. Without this, a document named ``*.md``, ``[draft].md``, or
    # anything starting with ``!`` or ``:`` would be read as a pathspec
    # pattern and silently match the wrong files, or none.
    "GIT_LITERAL_PATHSPECS": "1",
    "LC_ALL": "C",
    "TZ": "UTC",
}

#: File extension -> media type. Markdown and plain text are inspected;
#: anything else is skipped with a named reason rather than guessed at.
INSPECTED_MEDIA_TYPES: Final[dict[str, str]] = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".text": "text/plain",
}

#: Inspection order: Markdown first, then plain text (spec Section 17.4 mining
#: begins with the documents that carry heading and profile context).
MEDIA_TYPE_ORDER: Final[tuple[str, ...]] = ("text/markdown", "text/plain")

#: Profile identifiers, from the normative ``profile`` enum. Profile-section
#: identification matches these names; it never invents a heading vocabulary.
STABLE_PROFILES: Final[tuple[str, ...]] = ("ASSESS", "SPECIFY", "TRANSFORM")

#: An explicit in-document profile declaration, in the same comment-marker
#: family as the ``<!-- ats:block ... -->`` scheme the output linter uses.
PROFILE_MARKER = re.compile(r"^<!--\s*ats:profile\s+([A-Za-z0-9-]+)\s*-->$")

#: An explicit in-document definition, for the same reason: a definition is
#: collected where the document declares one. Inferring a definition from
#: ordinary prose would fabricate declared glossary content.
DEFINE_MARKER = re.compile(r"^<!--\s*ats:define\s+(.+?)\s*-->$")

#: Commit trailers this module reads. Each is an explicit declaration by the
#: committer; nothing is inferred from the fact that a commit exists.
TRAILER_REVIEW_STATE: Final[str] = "ATS-Review-State"
TRAILER_REVIEWED_BY: Final[str] = "Reviewed-by"
TRAILER_REVIEW_COMMENT: Final[str] = "ATS-Review-Comment"
TRAILER_MODEL: Final[str] = "ATS-Model"
TRAILER_USE_AUTHORITY: Final[str] = "ATS-Use-Authority"

#: Review states the schema distinguishes. ``unknown`` is the honest default:
#: spec Section 17.4 refuses to read acceptance out of the mere existence of a
#: commit.
DECLARABLE_REVIEW_STATES: Final[frozenset[str]] = frozenset(
    {"accepted", "rejected", "superseded", "draft"}
)

#: Repository-level declaration file. Use authority and handling policy are
#: obligations under spec Section 17.13 and cannot be derived from file
#: contents, so they are read from a declaration or reported as unknown.
DECLARATION_PATH: Final[str] = ".ats/corpus.json"

#: Word-shingle width, and the shingle-set overlap at which two documents are
#: treated as near duplicates. Both are fixed constants so a cluster assignment
#: is reproducible across runs and across machines.
SHINGLE_WIDTH: Final[int] = 5
NEAR_DUPLICATE_THRESHOLD: Final[float] = 0.8

#: Identifier for the clustering *procedure*, beside its parameters. Width and
#: threshold are inputs; how shingles are formed and how a cluster
#: representative is chosen are not, and either can move a document's cluster
#: assignment without moving a number. The procedure therefore carries its own
#: version, for the same reason :data:`ats.hashes.NORMALIZATION_VERSION` does:
#: when it changes, previously recorded cluster identifiers stop being
#: reproducible and a census that compares across the change is comparing two
#: different measurements.
NEAR_DUPLICATE_VERSION: Final[str] = "ats-near-duplicate-v1"

_WORD = re.compile(r"[0-9a-z]+")
_REVERT_LINE = re.compile(r"^This reverts commit ([0-9a-f]{7,40})", re.MULTILINE)


class GitUnavailable(RuntimeError):
    """``git`` could not answer for this directory; every git dimension is unsearched."""


# -- git plumbing -----------------------------------------------------------


def _git(
    repo: Path, *argv: str, binary: bool = False, stdin: bytes | None = None
) -> str | bytes:
    """Run one read-only ``git`` subcommand inside ``repo``.

    Raises :class:`UsageError` when a caller asks for a subcommand outside
    :data:`READ_ONLY_GIT_SUBCOMMANDS`, and :class:`GitUnavailable` when git is
    absent or the command fails.
    """
    if not argv:
        raise UsageError("no git subcommand given")
    if argv[0] not in READ_ONLY_GIT_SUBCOMMANDS:
        raise UsageError(
            f"git {argv[0]!r} is not a permitted corpus subcommand; corpus mining is "
            f"local and read-only (spec 16.9). Permitted: "
            f"{', '.join(sorted(READ_ONLY_GIT_SUBCOMMANDS))}"
        )
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *argv],
            capture_output=True,
            check=False,
            env=GIT_ENV,
            input=stdin,
        )
    except (OSError, ValueError) as exc:
        raise GitUnavailable(f"git could not be executed: {exc}") from exc
    if proc.returncode != 0:
        raise GitUnavailable(
            f"git {' '.join(argv)} failed ({proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")


def head_revision(repo: Path) -> str:
    """The exact revision the inventory is pinned to."""
    return str(_git(repo, "rev-parse", "HEAD")).strip()


def origin_url(repo: Path) -> str | None:
    """The ``origin`` remote URL, or ``None`` when the repository has none.

    ``None`` is an answer, not a failure: a repository can be identity-bearing
    with no remote at all, which is why :func:`root_commit` sits beside this.
    A declaration that names only a directory name is ambiguous the moment two
    checkouts share it (spec Section 17.13 binds a declaration to a
    repository, not to a path on one machine).
    """
    try:
        out = str(_git(repo, "config", "--get", "remote.origin.url")).strip()
    except GitUnavailable:
        # `git config --get` exits non-zero for an unset key. That is the key
        # being absent, which is exactly what `None` reports here.
        return None
    return out or None


def root_commit(repo: Path) -> str:
    """The repository's first commit.

    Identity that survives renaming the directory, moving it, changing the
    remote, and having no remote: two checkouts are the same repository
    exactly when they share a root commit.

    A repository grafted from several histories has several roots and
    therefore no single root identity. That is refused rather than resolved by
    picking one, because picking one would manufacture an identity the
    repository does not have.
    """
    roots = str(_git(repo, "log", "--max-parents=0", "--format=%H", "HEAD")).split()
    if not roots:
        raise GitUnavailable(f"{repo} has no commits, so it has no root-commit identity")
    if len(roots) > 1:
        raise UsageError(
            f"{repo} has {len(roots)} root commits ({', '.join(sorted(roots))}); a grafted "
            "history has no single root-commit identity, so this repository must be "
            "identified some other way"
        )
    return roots[0]


def author_identities(repo: Path) -> list[str]:
    """Every distinct author and committer identity in the repository history.

    The evidence behind an ownership claim. "The principal owns this
    repository" is checkable only against who has actually written in it, and
    a repository whose history carries an identity the declaring principal
    does not account for is one the principal cannot speak for alone.
    """
    out = str(_git(repo, "log", "--format=%ae%n%ce", "HEAD"))
    return sorted({line.strip() for line in out.splitlines() if line.strip()})


def tracked_paths(repo: Path, revision: str) -> list[str]:
    """Repository-relative paths present in ``revision``, in sorted order."""
    out = str(_git(repo, "ls-tree", "-r", "--name-only", "-z", revision))
    return sorted(p for p in out.split("\0") if p)


def blob_bytes(repo: Path, revision: str, path: str) -> bytes:
    """The exact bytes of ``path`` at ``revision``.

    Read from the object store, not the worktree: a dirty worktree would
    otherwise be hashed under a revision that does not describe it.
    """
    result = _git(repo, "cat-file", "blob", f"{revision}:{path}", binary=True)
    assert isinstance(result, bytes)
    return result


def blob_batch(repo: Path, revision: str, paths: Sequence[str]) -> dict[str, bytes]:
    """The exact bytes of many paths at ``revision``, in one ``git`` invocation.

    Equivalent to calling :func:`blob_bytes` per path, but a corpus inventory
    reads every tracked document, and one process per document dominated the
    runtime. ``cat-file --batch`` answers the whole set from a single object
    store traversal.

    A path missing at ``revision`` is absent from the result rather than
    raising, so the caller can record a per-path skip reason as before.
    """
    # A newline inside a path would be read as a second request. Such paths are
    # legal in Git, so they are answered individually rather than corrupting
    # every later record in the stream.
    batched = [p for p in paths if "\n" not in p]
    out: dict[str, bytes] = {}
    for path in paths:
        if "\n" in path:
            try:
                out[path] = blob_bytes(repo, revision, path)
            except GitUnavailable:
                pass
    if not batched:
        return out

    request = "".join(f"{revision}:{p}\n" for p in batched).encode("utf-8")
    stream = _git(repo, "cat-file", "--batch", binary=True, stdin=request)
    assert isinstance(stream, bytes)

    pos = 0
    for path in batched:
        newline = stream.find(b"\n", pos)
        if newline == -1:
            break
        header = stream[pos:newline].decode("utf-8", "replace")
        pos = newline + 1
        fields = header.rsplit(" ", 2)
        if len(fields) != 3 or not fields[2].isdigit():
            # "<request> missing" -- no object, and no payload follows.
            continue
        size = int(fields[2])
        out[path] = stream[pos : pos + size]
        pos += size + 1  # git terminates each payload with a newline
    return out


@dataclass(frozen=True, slots=True)
class Commit:
    sha: str
    author: str
    author_email: str
    authored_at: str
    committer: str
    subject: str
    body: str

    @property
    def message(self) -> str:
        return f"{self.subject}\n\n{self.body}".strip()


_LOG_FORMAT = "%H%x1f%an%x1f%ae%x1f%aI%x1f%cn%x1f%s%x1f%b%x1e"


def _parse_log(out: str) -> list[Commit]:
    commits: list[Commit] = []
    for chunk in out.split("\x1e"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        parts = chunk.split("\x1f")
        if len(parts) < 7:
            continue
        commits.append(
            Commit(
                sha=parts[0],
                author=parts[1],
                author_email=parts[2],
                authored_at=parts[3],
                committer=parts[4],
                subject=parts[5],
                body=parts[6],
            )
        )
    return commits


def path_history(repo: Path, revision: str, path: str) -> list[Commit]:
    """Commits touching ``path`` up to ``revision``, newest first."""
    out = str(_git(repo, "log", f"--format={_LOG_FORMAT}", revision, "--", path))
    return _parse_log(out)


def commits_after(repo: Path, revision: str, since: str, path: str) -> list[Commit]:
    """Commits touching ``path`` between ``since`` (exclusive) and ``revision``."""
    out = str(
        _git(repo, "log", f"--format={_LOG_FORMAT}", f"{since}..{revision}", "--", path)
    )
    return _parse_log(out)


#: Same fields as :data:`_LOG_FORMAT`, but bracketed by ``\x1e`` on both sides
#: and tagged, so a whole-repository ``--name-only`` walk can tell a commit
#: header apart from the list of paths that follows it.
_WALK_FORMAT = "%x1eC%x1f" + _LOG_FORMAT


def history_index(
    repo: Path, revision: str, paths: Sequence[str] | None = None
) -> dict[str, list[Commit]]:
    """Map every path to the commits touching it, newest first, in one walk.

    :func:`path_history` answers for a single path and costs one ``git``
    process. An inventory needs the answer for every tracked document, and
    those spawns dominated the runtime; one ``--name-only`` walk answers the
    whole repository instead.

    The walk is not unconditionally equal to :func:`path_history`, and the
    difference is not cosmetic. ``git log -- <path>`` applies *history
    simplification*: it reports the commits needed to explain the file's
    current content, and prunes a side-branch commit whose change a later
    merge made redundant. A walk has no pathspec to simplify against and
    reports every commit that changed the file. Measured across fourteen
    repositories, the two disagreed for 26 of 1572 documents.

    Rather than pick a semantics silently, this reconciles to the per-path
    answer, which is what every stored record was built from. The reconciliation
    is exact and cheap because of where simplification can bite: a commit with
    one parent changed the file exactly when it is not TREESAME to that parent,
    so along the first-parent chain the walk and the per-path query cannot
    differ. Only a path touched by a commit off that chain can diverge, and
    only those paths are re-read individually.

    ``-z`` is required, not cosmetic. Without it Git renders a path containing
    a tab, a quote, or any non-ASCII byte in its quoted form
    (``"na\\303\\257ve.md"``), which matches nothing in
    :func:`tracked_paths` and would drop those documents from the corpus as
    though no commit had ever touched them.

    ``paths`` restricts the walk to a pathspec. The whole-repository walk emits
    every commit message and every changed path in the repository, most of
    which an inventory of Markdown documents discards; naming the paths keeps
    the output proportional to what is actually being read. The pathspec is
    dropped when it would approach the command-line length limit, which only
    costs time, never correctness.
    """
    argv = [
        "log",
        f"--format={_WALK_FORMAT}",
        "--name-only",
        "-z",
        # Rename detection changes which names a commit reports. A commit that
        # renames A to B is reported by --name-only as touching B alone, so A
        # vanishes from the walk -- while ``git log -- A`` still reports that
        # commit, because pathspec matching happens before renames are paired
        # and sees the deletion. Detection is therefore off: the walk must list
        # the same raw names a pathspec matches, or the rename disappears from
        # the provenance of the document that was renamed away.
        "--no-renames",
        revision,
    ]
    if paths:
        pathspec = list(paths)
        if sum(len(p) + 1 for p in pathspec) < 100_000:
            argv += ["--", *pathspec]
    out = str(_git(repo, *argv))
    index: dict[str, list[Commit]] = {}
    pending: Commit | None = None
    for chunk in out.split("\x1e"):
        if chunk.startswith("C\x1f"):
            parsed = _parse_log(chunk[2:] + "\x1e")
            pending = parsed[0] if parsed else None
            continue
        if pending is None:
            continue
        # Under ``-z`` a commit's names arrive as ``\0\n<name>\0<name>\0``:
        # the NUL terminates the (empty) format record and the newline that
        # follows separates the header from the list. That newline therefore
        # sits on the first name, not at the start of the chunk. Exactly one
        # leading newline is removed from the first entry and nothing else is
        # trimmed, because a path may legitimately begin or end with a space.
        first = True
        for path in chunk.split("\0"):
            if not path:
                continue
            if first:
                first = False
                if path.startswith("\n"):
                    path = path[1:]
                if not path:
                    continue
            index.setdefault(path, []).append(pending)

    mainline = first_parent_commits(repo, revision)
    suspect = merge_resolved_paths(repo, revision, paths)
    # The walk already parsed every commit it saw. Reconciling only needs to
    # learn which of them history simplification keeps, so the per-path query
    # asks for shas alone and the objects are reused. Re-reading the author,
    # date, and message per path is the expensive half and buys nothing.
    parsed = {c.sha: c for commits in index.values() for c in commits}
    for path in list(index):
        if path in suspect or not all(c.sha in mainline for c in index[path]):
            index[path] = _resolve_path_history(repo, revision, path, parsed)
    # A path can be resolved entirely inside a merge and appear nowhere in the
    # walk, because Git lists no files for a merge commit unless asked. Without
    # this, such a document would be dropped as though nothing had ever touched
    # it.
    for path in suspect:
        if path not in index:
            recovered = _resolve_path_history(repo, revision, path, parsed)
            if recovered:
                index[path] = recovered
    return index


def _resolve_path_history(
    repo: Path, revision: str, path: str, parsed: Mapping[str, Commit]
) -> list[Commit]:
    """The per-path history, reusing commits the walk already parsed.

    Falls back to a full read when the simplified history names a commit the
    walk never saw, which happens for a path resolved inside a merge.
    """
    shas = str(_git(repo, "log", "--format=%H", revision, "--", path)).split()
    if all(sha in parsed for sha in shas):
        return [parsed[sha] for sha in shas]
    return path_history(repo, revision, path)


def first_parent_commits(repo: Path, revision: str) -> frozenset[str]:
    """Shas on the first-parent chain from ``revision``.

    A commit on this chain has its diff taken against the same parent that
    history simplification would compare it to, which is what makes the walk
    and the per-path query agree there.
    """
    out = str(_git(repo, "log", "--format=%H", "--first-parent", revision))
    return frozenset(out.split())


def merge_resolved_paths(
    repo: Path, revision: str, paths: Sequence[str] | None = None
) -> frozenset[str]:
    """Paths a first-parent merge changed relative to the branch it merged into.

    A merge may edit a file itself, by resolving a conflict or by an outright
    change made during the merge. ``git log`` lists no files for a merge, so
    such an edit is invisible to the walk while ``git log -- <path>`` reports
    it. These paths are therefore resolved individually.

    Restricted to ``paths`` when given, but the filtering happens here rather
    than in Git. A pathspec makes Git test every commit in the walk against it,
    which on a large repository costs far more than reading the handful of file
    lists that merges actually produce: on one repository here, 6.1s against
    0.16s for the same answer.

    One walk, not one process per merge. ``--first-parent`` makes Git diff a
    merge against the branch it merged into, which is exactly the comparison
    that reveals a resolution, so the whole set comes back from a single
    invocation.
    """
    out = str(
        _git(
            repo,
            "log",
            "--merges",
            "--first-parent",
            f"--format={_WALK_FORMAT}",
            "--name-only",
            "-z",
            "--no-renames",
            revision,
        )
    )
    keep = set(paths) if paths else None
    found: set[str] = set()
    seen_header = False
    for chunk in out.split("\x1e"):
        if chunk.startswith("C\x1f"):
            seen_header = True
            continue
        if not seen_header:
            continue
        for path in chunk.split("\0"):
            # Exactly one separator newline, as in the walk parser: a path may
            # legitimately begin with whitespace.
            if path.startswith("\n"):
                path = path[1:]
            if path and (keep is None or path in keep):
                found.add(path)
    return frozenset(found)


def commit_diff(repo: Path, sha: str, path: str) -> str:
    """The unified diff a single commit applied to one path."""
    return str(_git(repo, "show", "--format=", "--unified=3", sha, "--", path))


def notes_ref_exists(repo: Path) -> bool:
    """Whether this repository carries any git notes at all."""
    try:
        return bool(str(_git(repo, "notes", "list")).strip())
    except GitUnavailable:
        return False


def commit_note(repo: Path, sha: str) -> str | None:
    """The git note attached to ``sha``, or ``None`` when it carries none."""
    try:
        return str(_git(repo, "notes", "show", sha)).strip() or None
    except GitUnavailable:
        return None


def trailers(message: str) -> dict[str, list[str]]:
    """``Key: value`` trailers from a commit message, keyed case-insensitively."""
    out: dict[str, list[str]] = {}
    for line in message.splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z0-9-]*):\s+(.+?)\s*$", line)
        if match:
            out.setdefault(match.group(1).lower(), []).append(match.group(2))
    return out


# -- deterministic clustering ----------------------------------------------


def shingles(text: str, *, width: int = SHINGLE_WIDTH) -> frozenset[str]:
    """The set of ``width``-word shingle digests of ``text``.

    Words are lowercased and reduced to alphanumeric runs, so line wrapping and
    punctuation do not change the set. Hashing keeps the set small and makes
    comparison independent of document length.
    """
    words = _WORD.findall(text.lower())
    if not words:
        return frozenset()
    if len(words) <= width:
        grams = [" ".join(words)]
    else:
        grams = [" ".join(words[i : i + width]) for i in range(len(words) - width + 1)]
    return frozenset(hashlib.sha256(g.encode("utf-8")).hexdigest() for g in grams)


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    """Shingle-set overlap. Two empty documents are identical, not undefined."""
    if not left and not right:
        return 1.0
    union = len(left | right)
    return len(left & right) / union if union else 0.0


def near_duplicate_clusters(
    documents: Mapping[str, str], *, threshold: float = NEAR_DUPLICATE_THRESHOLD
) -> dict[str, str]:
    """Assign each document a near-duplicate cluster identifier.

    Documents whose shingle sets overlap by at least ``threshold`` are joined
    transitively, and the cluster takes the identifier of its lexicographically
    smallest member key, so the assignment is a pure function of the document
    set. A document that resembles nothing else forms a cluster of one, which
    is a real answer rather than a missing field.

    A single-value sketch is deliberately not used: near-duplicates that differ
    in a handful of shingles produce different sketches, so equality on a
    sketch would silently miss exactly the copies spec Section 17.7 asks to
    group.

    The result is the same set of clusters an all-pairs comparison produces.
    Only the pairs actually examined differ: for a positive threshold, two
    documents can only reach it by sharing at least one shingle, so an
    inverted index over shingles reaches every qualifying pair and skips the
    rest. That is an exact prune, not a sampled approximation, which matters
    because the cluster identifier is part of a content-addressed record.
    """
    keys = sorted(documents)
    sets = {k: shingles(documents[k]) for k in keys}
    parent = {k: k for k in keys}

    def find(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def join(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    if threshold <= 0.0:
        # Every pair qualifies, including documents sharing no shingle, so the
        # index would not reach them. Degenerate, but it must not silently
        # produce a different answer than the definition.
        for i, left in enumerate(keys):
            for right in keys[i + 1 :]:
                join(left, right)
        return {
            k: "nearduplicate-" + sha256_hex(find(k).encode("utf-8"))[:32] for k in keys
        }

    # Two documents with no words at all are identical to each other and to
    # nothing else; they share no shingle, so the index cannot pair them.
    # ``jaccard`` scores that pair exactly 1.0, so a threshold above 1.0
    # separates them and the join must not happen.
    if threshold <= 1.0:
        empty = [k for k in keys if not sets[k]]
        for other in empty[1:]:
            join(empty[0], other)

    index: dict[str, list[str]] = {}
    for key in keys:
        for shingle in sets[key]:
            index.setdefault(shingle, []).append(key)

    for key in keys:
        own = sets[key]
        if not own:
            continue
        overlap: dict[str, int] = {}
        for shingle in own:
            for other in index[shingle]:
                if other > key:
                    overlap[other] = overlap.get(other, 0) + 1
        size = len(own)
        for other, shared in overlap.items():
            union = size + len(sets[other]) - shared
            if union and shared / union >= threshold:
                join(key, other)

    return {
        k: "nearduplicate-" + sha256_hex(find(k).encode("utf-8"))[:32] for k in keys
    }


def template_skeleton(heading_paths: Sequence[Sequence[str]]) -> str | None:
    """A deterministic identifier for a document's section skeleton.

    Two documents copied from the same template carry the same section headings
    even when their prose differs, which is the ``template`` leakage dimension
    spec Section 17.7 names. The document title is excluded: a title names the
    individual document, while the sections below it are what a template
    supplies. A document with no section headings has no skeleton to identify,
    so the field is absent rather than a hash of nothing.
    """
    sections = [p[-1].strip().lower() for p in heading_paths if len(p) > 1]
    if not sections:
        return None
    return "template-" + sha256_hex("\n".join(sections).encode("utf-8"))[:32]


# -- document structure -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class DocumentStructure:
    """What inspecting a document's text yields, independent of git."""

    heading_paths: tuple[tuple[str, ...], ...]
    profile_hypotheses: tuple[str, ...]
    profile_evidence: tuple[dict[str, str], ...]
    parse_error: str | None


def _heading_paths(text: str) -> tuple[tuple[tuple[str, ...], ...], str | None]:
    from ..output.parse import headings as _headings

    try:
        parsed = parse_markdown(text)
    except ParseError as exc:
        return (), str(exc)
    stack: list[tuple[int, str]] = []
    paths: list[tuple[str, ...]] = []
    for level, title, _line in _headings(parsed):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        paths.append(tuple(t for _lvl, t in stack))
    return tuple(paths), None


def inspect_document(text: str, *, media_type: str) -> DocumentStructure:
    """Collect heading paths and profile hypotheses from a document's text.

    A profile hypothesis is raised only by an explicit ``<!-- ats:profile X -->``
    declaration or by a heading that names one of the profile identifiers the
    normative ``profile`` enum defines. Nothing else counts: a heading
    vocabulary invented here would create profile labels the standard does not
    recognise.
    """
    paths: tuple[tuple[str, ...], ...] = ()
    parse_error: str | None = None
    if media_type == "text/markdown":
        paths, parse_error = _heading_paths(text)

    hypotheses: list[str] = []
    evidence: list[dict[str, str]] = []
    for line in text.splitlines():
        match = PROFILE_MARKER.match(line.strip())
        if match and match.group(1).upper() in STABLE_PROFILES:
            profile = match.group(1).upper()
            if profile not in hypotheses:
                hypotheses.append(profile)
                evidence.append({"profile": profile, "basis": "declared_front_matter"})
    for path in paths:
        for profile in STABLE_PROFILES:
            if profile in hypotheses:
                continue
            if any(re.search(rf"\b{profile}\b", segment, re.IGNORECASE) for segment in path):
                hypotheses.append(profile)
                evidence.append(
                    {"profile": profile, "basis": "heading_path", "heading": "/".join(path)}
                )
    return DocumentStructure(
        heading_paths=paths,
        profile_hypotheses=tuple(hypotheses),
        profile_evidence=tuple(evidence),
        parse_error=parse_error,
    )


# -- declaration ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Declaration:
    """A repository's declared corpus handling, per spec Section 17.13."""

    repository_group: str
    use_authority: str
    handling_policy: str
    domain: str | None
    declared: bool

    @classmethod
    def load(cls, repo: Path) -> Declaration:
        default_group = repo.name or str(repo)
        path = repo / DECLARATION_PATH
        if not path.is_file():
            return cls(
                repository_group=default_group,
                use_authority="unknown",
                handling_policy="internal",
                domain=None,
                declared=False,
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise UsageError(f"{path} is not readable JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise UsageError(f"{path} must contain a JSON object")
        return cls(
            repository_group=str(data.get("repository_group") or default_group),
            use_authority=str(data.get("use_authority") or "unknown"),
            handling_policy=str(data.get("handling_policy") or "internal"),
            domain=str(data["domain"]) if data.get("domain") else None,
            declared=True,
        )


# -- inventory --------------------------------------------------------------


def _matches(path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _review_state(commit: Commit, note: str | None) -> tuple[str, str]:
    """Resolve the review state of a document, and say why.

    Only three things move the state off ``unknown``: an explicit
    ``ATS-Review-State`` trailer, the same declaration inside a git note, and
    git's own ``This reverts commit`` line. Being committed on the default
    branch is not evidence of acceptance (spec Section 17.4).
    """
    if _REVERT_LINE.search(commit.message):
        return "reverted", "the commit message carries git's own revert marker"
    declared = trailers(commit.message).get(TRAILER_REVIEW_STATE.lower())
    if declared and declared[0].lower() in DECLARABLE_REVIEW_STATES:
        return declared[0].lower(), f"declared by the {TRAILER_REVIEW_STATE} commit trailer"
    if note:
        note_declared = trailers(note).get(TRAILER_REVIEW_STATE.lower())
        if note_declared and note_declared[0].lower() in DECLARABLE_REVIEW_STATES:
            return note_declared[0].lower(), f"declared by {TRAILER_REVIEW_STATE} in a git note"
    return (
        "unknown",
        "no review state is declared; a merged commit is not evidence of acceptance (spec 17.4)",
    )


def _acceptance_evidence(
    commit: Commit, note: str | None, *, notes_searched: bool
) -> dict[str, Any]:
    """Locally available review commentary, with an explicit availability state."""
    message_trailers = trailers(commit.message)
    reviewers = list(message_trailers.get(TRAILER_REVIEWED_BY.lower(), ()))
    comments = list(message_trailers.get(TRAILER_REVIEW_COMMENT.lower(), ()))
    if note:
        note_trailers = trailers(note)
        reviewers += note_trailers.get(TRAILER_REVIEWED_BY.lower(), [])
        comments += note_trailers.get(TRAILER_REVIEW_COMMENT.lower(), [])
        if not note_trailers:
            comments.append(note)

    searched = f"commit trailers of {commit.sha[:12]}" + (
        " and its git note" if notes_searched else "; this repository carries no notes ref"
    )
    if not reviewers and not comments:
        return {
            "availability": "not_found" if notes_searched else "not_searched",
            "notes": f"searched {searched}",
        }
    evidence: dict[str, Any] = {
        "availability": "present",
        "locator": f"git:{commit.sha}",
        "notes": "; ".join(comments) if comments else f"searched {searched}",
    }
    if reviewers:
        evidence["reviewers"] = reviewers
    return evidence


def _model_provenance(commit: Commit, note: str | None) -> dict[str, Any]:
    """Model authorship, only where a commit declares it (spec Section 17.4)."""
    declared = trailers(commit.message).get(TRAILER_MODEL.lower(), [])
    if note:
        declared += trailers(note).get(TRAILER_MODEL.lower(), [])
    if not declared:
        return {
            "availability": "not_found",
            "evidence": f"no {TRAILER_MODEL} trailer on {commit.sha[:12]} or its note",
        }
    name, _, version = declared[0].partition("@")
    return {
        "availability": "present",
        "model": {"name": name.strip() or declared[0], "version": version.strip() or "unknown"},
        "evidence": f"declared by the {TRAILER_MODEL} trailer on {commit.sha[:12]}",
    }


#: Where an inventory records the authority declaration it was built under.
AUTHORITY_DECLARATION: Final[str] = "authority_declaration"


def authority_declaration_binding(authority: AuthorityDeclaration) -> dict[str, Any]:
    """Which authority declaration answered for an inventory, and its bytes.

    The digest is not recoverable from the artifacts, which is why it is
    recorded here. A declaration's resolved permissions are written into every
    artifact record and therefore into its content address, so editing an
    overlay re-addresses every document the overlay covers without changing one
    byte of source text. Anything cached against those addresses -- a mining
    result above all -- is invalidated by that edit, and this is the only field
    that lets it notice.

    ``availability`` uses the same vocabulary as every other typed absence in
    this data model, for the same reason. "No declaration covers this
    repository" and "this inventory predates the field" must stay different
    answers: the first carries a ``not_found`` block, the second carries no
    block at all, and a bare ``None`` in one field could not tell them apart
    (ADR-0002).
    """
    if authority.source_sha256 is None:
        return {
            "availability": "not_found",
            "location": None,
            "sha256": None,
            "detail": (
                f"no per-use authority declaration answered for {authority.repository}, so "
                "there are no declaration bytes to hash"
            ),
        }
    return {
        "availability": "present",
        "location": authority.declaration_location,
        "sha256": authority.source_sha256,
    }



def build_inventory(
    ctx: Any,
    repo_path: str | Path,
    *,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    authority_overlay: str | Path | None = None,
) -> dict[str, Any]:
    """Inventory the Markdown and plain-text documents of a local Git repository.

    Returns ``{"repository", "revision", "declaration_present",
    "authority_declaration", "artifacts", "skipped"}``. Each artifact is a
    content-addressed ``SourceArtifactV1`` pinned to the commit that last
    touched it, and every dimension spec Section 17.4 names is either present or
    carries an explicit availability state.

    ``authority_overlay`` points at operator-authored authority declarations for
    repositories that have not yet been onboarded. A repository's own
    ``.ats/corpus.json`` always wins over the overlay, and each artifact records
    which of the two answered, so overlay-authorised material never becomes
    indistinguishable from material authorised at source.

    ``authority_declaration`` records the digest of whichever of the two
    answered. It is the input that is otherwise invisible: the declaration's
    resolved permissions go into each artifact record and so into its content
    address, which means an overlay edit re-addresses this whole inventory
    without touching a document. See :func:`authority_declaration_binding`.
    """
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        raise UsageError(f"{repo} is not a directory")

    declaration = Declaration.load(repo)
    authority = AuthorityDeclaration.load(
        repo, overlay_dir=Path(authority_overlay) if authority_overlay else None
    )
    skipped: list[dict[str, str]] = []

    try:
        revision = head_revision(repo)
        paths = tracked_paths(repo, revision)
    except GitUnavailable as exc:
        raise UsageError(
            f"{repo} is not a readable Git repository ({exc}); corpus mining pins every "
            "example to an exact revision, so an unpinned directory is refused (spec 17.4)"
        ) from exc

    notes_searched = notes_ref_exists(repo)

    candidates: list[tuple[int, str, str]] = []
    for path in paths:
        suffix = Path(path).suffix.lower()
        media_type = INSPECTED_MEDIA_TYPES.get(suffix)
        if media_type is None:
            skipped.append(
                {
                    "path": path,
                    "reason": "unsupported_media_type",
                    "detail": f"{suffix or 'no extension'} is not inspected; this implementation "
                    "reads Markdown and plain text",
                }
            )
            continue
        if include and not _matches(path, include):
            skipped.append(
                {"path": path, "reason": "not_included", "detail": "no include glob matched"}
            )
            continue
        if exclude and _matches(path, exclude):
            skipped.append(
                {"path": path, "reason": "excluded", "detail": "an exclude glob matched"}
            )
            continue
        candidates.append((MEDIA_TYPE_ORDER.index(media_type), path, media_type))

    # First pass: read every inspected document and its git dimensions.
    # Near-duplicate clustering compares documents against each other, so it
    # cannot run until the whole set is known.
    #
    # Both git reads are answered for the whole repository at once. Asking per
    # document cost one process per document per dimension, which dominated
    # every other cost in the inventory by an order of magnitude.
    ordered = sorted(candidates)
    blobs = blob_batch(repo, revision, [path for _o, path, _m in ordered])
    histories = history_index(repo, revision, [path for _o, path, _m in ordered])

    inspected: list[dict[str, Any]] = []
    for _order, path, media_type in ordered:
        raw = blobs.get(path)
        if raw is None:
            skipped.append(
                {
                    "path": path,
                    "reason": "unreadable_blob",
                    "detail": f"no blob for {path} at {revision[:12]}",
                }
            )
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            skipped.append({"path": path, "reason": "not_utf8", "detail": str(exc)})
            continue
        history = histories.get(path, [])
        if not history:
            skipped.append(
                {"path": path, "reason": "no_history", "detail": "no commit touches this path"}
            )
            continue
        inspected.append(
            {
                "path": path,
                "media_type": media_type,
                "text": text,
                "binding": bind_text(text, raw=raw),
                "structure": inspect_document(text, media_type=media_type),
                "history": history,
            }
        )

    clusters = near_duplicate_clusters({d["path"]: d["text"] for d in inspected})

    # Second pass: emit one content-addressed record per inspected document.
    # `now` is the ingest clock, resolved once: every artifact in one run is
    # ingested at the same instant, and a declaration's review date is checked
    # against that instant rather than against a clock that moves mid-run.
    now = ctx.timestamp()
    artifacts: list[dict[str, Any]] = []
    for doc in inspected:
        path = doc["path"]
        structure: DocumentStructure = doc["structure"]
        history: list[Commit] = doc["history"]
        last = history[0]
        note = commit_note(repo, last.sha) if notes_searched else None
        state, state_reason = _review_state(last, note)
        # Commits touching this path between the artifact's revision and the
        # pinned revision. ``last`` is by construction the newest commit
        # touching the path at or before ``revision``, so this set is always
        # empty and the field can only ever report ``not_found``; it is
        # derived from the walk rather than re-queried, and recorded as a
        # draft observation rather than quietly dropped.
        later: list[Commit] = []

        git_extension: dict[str, Any] = {
            "history": {
                "availability": "present",
                "commit_count": len(history),
                "commits": [
                    {"sha": c.sha, "authored_at": c.authored_at, "subject": c.subject}
                    for c in history
                ],
            },
            # The before/after pair for the pinned revision: the commit that
            # produced this content and the one it replaced.
            "previous_edit": (
                {"availability": "present", "sha": history[1].sha, "subject": history[1].subject}
                if len(history) > 1
                else {
                    "availability": "not_found",
                    "detail": f"{last.sha[:12]} introduced this path; there is no earlier edit",
                }
            ),
            "later_edits": (
                {"availability": "present", "commits": [c.sha for c in later]}
                if later
                else {
                    "availability": "not_found",
                    "detail": f"{last.sha[:12]} is the last commit touching this path at "
                    f"{revision[:12]}",
                }
            ),
            "review_state_basis": state_reason,
            "profile_evidence": [dict(e) for e in structure.profile_evidence],
            "notes_ref_present": notes_searched,
        }
        if structure.parse_error:
            git_extension["parse_error"] = structure.parse_error

        # Per-use authority, resolved for this exact path. The artifact schema
        # carries a single coarse value, so the full resolution is recorded
        # beside it: the coarse projection cannot express "annotating is
        # authorised but training is not", which is precisely the state every
        # pilot repository is in.
        # The declaration's review date is checked against the ingest clock, so
        # a lapsed declaration caps at `unknown` here rather than continuing to
        # grant indefinitely.
        resolutions = authority.resolve_all(path, now=now)
        # Provenance travels with the permission, always. An overlay and a
        # repository's own declaration can resolve identically and are not the
        # same thing, so `require_provenance` refuses a block that dropped the
        # marker rather than letting an overlay read as repository-owned.
        #
        # This block is part of the artifact's content address: `artifact_id`
        # is the SHA-256 of the whole record with only the identifier omitted,
        # extensions included. So re-issuing a declaration re-addresses every
        # document it covers even though the bytes on disk did not move, and
        # anything cached against an `artifact_id` -- a mining result, most of
        # all -- is silently orphaned by an overlay edit. Neither the inventory
        # nor a mining result records which declaration it was built under, so
        # neither can detect the mismatch on its own; the consumer has to.
        # Deliberate, and stated here because it is not obvious: the resolved
        # authority is part of what a corpus record *is*, so a record produced
        # under a different authority is a different record.
        authority_block: dict[str, Any] = {
            **authority.provenance(now),
            "declared_by": authority.authority,
            "effective_from_revision": authority.effective_from_revision or None,
            "uses": {use: r.value for use, r in resolutions.items()},
            "permitted": sorted(use for use, r in resolutions.items() if r.permitted),
            "blocked_basis": {
                use: list(r.basis) for use, r in resolutions.items() if not r.permitted
            },
        }
        require_provenance(authority_block, where=f"the inventory of {repo.name}:{path}")
        git_extension["authority"] = authority_block

        use_authority = (
            authority.coarse_use_authority(path, now=now)
            if authority.declared
            else declaration.use_authority
        )
        if not coarse_recognised(use_authority):
            # A declaration nobody can read is not a permission. It is recorded
            # verbatim beside the resolution so the mistake stays visible, and
            # resolves to `unknown` rather than being guessed at or passed
            # through into an artifact record.
            authority_block["coarse_declared"] = {
                "declared": use_authority,
                "recognised": False,
            }
            use_authority = "unknown"
        # A commit trailer can restrict a document further than its repository
        # does, and it is intersected rather than substituted so it can never
        # widen what the repository declared. Substitution was the bug: it let
        # a trailer turn a `prohibited` -- a refusal somebody made -- back into
        # a permission, and it let a committer out-declare the repository owner
        # from inside a commit message.
        declared_authority = trailers(last.message).get(TRAILER_USE_AUTHORITY.lower())
        if declared_authority:
            claimed = declared_authority[0]
            recognised = coarse_recognised(claimed)
            # An unreadable trailer is not a permission and not a refusal. It
            # caps at `unknown` and says so, rather than being dropped (which
            # would ignore a declaration somebody made) or ranked (which would
            # guess what they meant).
            applied = claimed if recognised else "unknown"
            use_authority = intersect_coarse(use_authority, applied)
            authority_block["trailer"] = {
                "declared": claimed,
                "recognised": recognised,
                "applied": applied,
            }

        artifacts.append(
            rec.source_artifact(
                # The repository *name*, not its absolute path: a corpus record
                # is content-addressed, and an absolute path would make the
                # same document hash differently on another machine.
                repository=repo.name,
                repository_group=declaration.repository_group,
                path=path,
                revision=last.sha,
                content_sha256=doc["binding"].content_sha256,
                normalized_sha256=doc["binding"].normalized_sha256,
                bytes_=doc["binding"].byte_length,
                media_type=doc["media_type"],
                review_state=state,
                use_authority=use_authority,
                handling_policy=(
                    authority.coarse_handling_policy()
                    if authority.declared
                    else declaration.handling_policy
                ),
                ingested_at=ctx.timestamp(),
                author_provenance={
                    "availability": "present",
                    "author": f"{last.author} <{last.author_email}>",
                    "authored_at": last.authored_at,
                    "committer": last.committer,
                },
                # Authorship is read, never inferred: the recorded value uses
                # the human/model/mixed/unknown vocabulary and carries the list
                # of evidence sources that were searched (spec Section 17.4).
                model_provenance=auth.historical_model_provenance(
                    _model_provenance(last, note),
                    locator=f"git:{last.sha}",
                    document_text=doc["text"],
                    authority=authority,
                ),
                acceptance_evidence=_acceptance_evidence(
                    last, note, notes_searched=notes_searched
                ),
                template_family=template_skeleton(structure.heading_paths),
                near_duplicate_cluster=clusters[path],
                domain=declaration.domain,
                profile_hypotheses=structure.profile_hypotheses or None,
                heading_paths=structure.heading_paths or None,
                extensions={f"{rec.EXT_PREFIX}git": git_extension},
            )
        )

    for artifact in artifacts:
        ctx.schemas.validate_document(artifact)

    return {
        "repository": str(repo),
        "revision": revision,
        "declaration_present": declaration.declared,
        AUTHORITY_DECLARATION: authority_declaration_binding(authority),
        "artifacts": artifacts,
        "skipped": skipped,
    }


def artifact_text(repo_path: str | Path, artifact: Mapping[str, Any]) -> str:
    """Re-read an artifact's exact text at its pinned revision."""
    repo = Path(repo_path).resolve()
    raw = blob_bytes(repo, artifact["revision"], artifact["path"])
    text = raw.decode("utf-8")
    if sha256_hex(raw) != artifact["content_sha256"]:
        raise UsageError(
            f"{artifact['path']} at {artifact['revision'][:12]} no longer matches the recorded "
            "content hash; the artifact record and the repository disagree"
        )
    return text

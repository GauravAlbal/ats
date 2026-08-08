"""Reproducibility receipt for one corpus census run.

A census reports statistics over documents that a miner selected, read,
normalized, and clustered. When a statistic moves between two runs, either the
corpus moved or the miner did — and the statistics themselves cannot tell those
apart. Spec Section 15.8 makes the same point about a rendered receipt: a
parser change invalidates a prior replay claim, so the parser identity has to
ride along. The census needs the same treatment at corpus scale.

This module emits ``ats.census_receipt.v1``, which binds both sides of the
comparison:

*the corpus side*
    every inventoried repository at its exact pinned revision, the include and
    exclude globs it was read under, the digest of the authority declaration in
    force for it, and the sorted list of every source-artifact identifier the
    run produced with one digest over that list;

*the miner side*
    the ``ats`` revision that ran, whether its worktree was dirty at emission,
    the schema set in play, :data:`ats.hashes.NORMALIZATION_VERSION`, and the
    clustering procedure with its parameters.

Two properties are deliberate.

**A dirty worktree is recorded, not hidden.** Uncommitted changes mean the code
that produced the census is not the code its revision names, so the run cannot
be replayed from the revision alone. Emitting ``clean`` because nobody looked,
or omitting the field, would convert an unreproducible run into an apparently
reproducible one.

**Wall clock is an input, not a measurement taken here.** Elapsed time belongs
to the inventory invocation; timing the emitter would report the cost of
reading JSON. Callers pass :class:`RepositoryRun` records, and a repository
with no measurement reports one as unavailable rather than zero.

The receipt is content-addressed through :func:`ats.canonical.seal`, so
``receipt_sha256`` is a pure function of what the receipt says: two emissions
over unchanged inputs carry the same address, and any change to what was bound
moves it. That address, not a file path, is what a later comparison cites.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

from ..canonical import canonical_bytes, seal, sha256_hex
from ..errors import UsageError
from ..hashes import NORMALIZATION_VERSION
from ..spec_package import REPO_ROOT
from . import inventory as inv
from .authority import REPOSITORY_DECLARATION, AuthorityDeclaration, require_provenance
from .records import EXT_PREFIX

SCHEMA_VERSION: Final[str] = "ats.census_receipt.v1"

#: File names the census run writes and this module reads or writes.
CENSUS_FILENAME: Final[str] = "census.json"
RECEIPT_FILENAME: Final[str] = "census_receipt.json"
RAW_DIRNAME: Final[str] = "raw"

#: Where operator-authored authority declarations live for repositories that
#: have not yet been onboarded. A repository's own declaration always wins, so
#: this is only consulted when the repository is silent.
DEFAULT_AUTHORITY_OVERLAY: Final[Path] = REPO_ROOT / "corpus" / "authority"

#: Where :func:`ats.corpus.inventory.build_inventory` records the authority it
#: resolved for an artifact.
_GIT_EXTENSION: Final[str] = f"{EXT_PREFIX}git"


def raw_inventory_name(repository: str, family: str) -> str:
    """The cached-inventory filename for one inventory.

    Repository and family together, because one repository may be inventoried
    more than once when a subtree is probed separately. Including both in the
    filename avoids collisions between independent inventory inputs.
    """
    return f"{repository}-{family}.json"


def _relative_to_repo_root(path: Path) -> str:
    """``path`` as this repository sees it, or as an absolute path if it is outside.

    A receipt is committed, so a path inside the checkout is recorded relative
    to it: an absolute path would bake one machine's layout into a record that
    two machines are supposed to be able to produce identically.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


@dataclass(frozen=True, slots=True)
class RepositoryRun:
    """What one inventory invocation was told to do, and how long it took.

    ``elapsed_seconds`` is ``None`` when the run did not measure it — a census
    recomputed from cached inventories, for instance, where the only thing
    timed would be a JSON read.
    """

    inventory: str
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    elapsed_seconds: float | None


# -- inputs -----------------------------------------------------------------


def _require(source: Mapping[str, Any], key: str, what: str) -> Any:
    """Read a key the census is required to carry.

    A missing key means the census writer and this reader have diverged. That
    raises rather than defaulting, because a receipt built from a substituted
    value would bind a run that never happened.
    """
    if key not in source:
        raise UsageError(
            f"{what} carries no {key!r}; the census writer and the receipt reader "
            "have diverged, and a receipt MUST NOT substitute a value for one it "
            "could not read"
        )
    return source[key]


def _read_census(census_dir: Path) -> tuple[dict[str, Any], str]:
    """The census document and the SHA-256 of its exact bytes."""
    path = census_dir / CENSUS_FILENAME
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise UsageError(f"cannot read the census at {path}: {exc}") from exc
    try:
        census = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UsageError(f"{path} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(census, dict):
        raise UsageError(f"{path} is not a census object")
    return census, sha256_hex(raw)


def _read_raw_inventories(raw_dir: Path) -> dict[str, tuple[dict[str, Any], str]]:
    """Every cached inventory under ``raw_dir``, keyed by filename.

    Returns ``{name: (inventory, sha256-of-exact-bytes)}``. The digest binds a
    committed receipt to inventories that may remain local and gitignored,
    because they can carry source path listings and other non-public metadata
    (spec Section 16.9).
    """
    if not raw_dir.is_dir():
        return {}
    out: dict[str, tuple[dict[str, Any], str]] = {}
    for path in sorted(raw_dir.glob("*.json")):
        try:
            raw = path.read_bytes()
            document = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UsageError(f"cannot read the cached inventory {path}: {exc}") from exc
        if not isinstance(document, dict):
            raise UsageError(f"{path} is not an inventory object")
        out[path.name] = (document, sha256_hex(raw))
    return out


# -- the implementation side ------------------------------------------------


def _worktree_state(repo: Path) -> dict[str, Any]:
    """Whether ``repo`` carried uncommitted or untracked changes.

    ``git status --porcelain`` is read through
    :func:`ats.corpus.inventory._git` so this module inherits the one hardened
    git entry point in the package: an allowlist of read-only subcommands, no
    terminal prompting, and no system or global configuration. A second
    subprocess convention here could drift from those guarantees.

    Untracked files count as dirty. Some of them cannot affect a census, but
    deciding which would mean inspecting them; counting them errs toward
    reporting less reproducibility rather than more.
    """
    try:
        porcelain = str(inv._git(repo, "status", "--porcelain"))
    except (inv.GitUnavailable, UsageError) as exc:
        return {
            "state": "unknown",
            "changed_paths": [],
            "detail": f"git could not report the worktree state of {repo.name}: {exc}",
        }
    # A porcelain line is two status characters, a space, then the path. A
    # rename keeps git's own ``old -> new`` form rather than being reduced to
    # one side of it.
    changed = sorted({line[3:].strip() for line in porcelain.splitlines() if line.strip()})
    if not changed:
        return {
            "state": "clean",
            "changed_paths": [],
            "detail": "no uncommitted or untracked changes; the revision names the code that ran",
        }
    return {
        "state": "dirty",
        "changed_paths": changed,
        "detail": (
            f"{len(changed)} uncommitted or untracked path(s); the census was produced by "
            "code the recorded revision does not name, so the run cannot be replayed from "
            "the revision alone"
        ),
    }


def implementation_worktree_state(repo: str | Path = REPO_ROOT) -> dict[str, Any]:
    """The implementation's cleanliness, for a caller to sample before a run.

    Exposed because the state has to be read before the run writes anything;
    see :func:`build_census_receipt`.
    """
    return _worktree_state(Path(repo))


def _implementation(
    ctx: Any, repo: Path, *, worktree: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """The miner's identity: revision, cleanliness, and the fixed procedures.

    ``worktree`` lets a caller supply the state observed *before* the run
    started. A census writes ``census.json`` and the raw inventories before the
    receipt is built, so a state sampled at emission always reports dirty --
    the run having dirtied the tree with its own output. The question this
    field answers is whether the code that produced the census was a committed
    revision, and that is only observable before the outputs land.
    """
    identity = ctx.implementation
    try:
        revision: dict[str, Any] = {"availability": "present", "sha": inv.head_revision(repo)}
    except (inv.GitUnavailable, UsageError) as exc:
        revision = {
            "availability": "unavailable",
            "detail": f"git could not resolve HEAD for {repo}: {exc}",
        }
    return {
        "name": identity["name"],
        "version": identity["version"],
        "revision": revision,
        "worktree": dict(worktree) if worktree is not None else _worktree_state(repo),
        "normalization_version": NORMALIZATION_VERSION,
        "schema_set_sha256": ctx.schema_set_sha256,
        "clustering": {
            "near_duplicate_version": inv.NEAR_DUPLICATE_VERSION,
            "shingle_width": inv.SHINGLE_WIDTH,
            "near_duplicate_threshold": inv.NEAR_DUPLICATE_THRESHOLD,
        },
    }


# -- the corpus side --------------------------------------------------------


def _recorded_authority_location(inventory: Mapping[str, Any]) -> str | None | bool:
    """Which declaration the cached inventory recorded resolving.

    Returns the recorded location, ``None`` when the inventory recorded that
    nothing was declared, or ``False`` when it recorded no authority at all —
    an inventory built before authority was resolved per artifact has nothing
    to agree or disagree with, which is a third state and not a null one.
    """
    artifacts = inventory.get("artifacts") or []
    locations: set[str | None] = set()
    for artifact in artifacts:
        extension = (artifact.get("extensions") or {}).get(_GIT_EXTENSION) or {}
        authority = extension.get("authority")
        if not isinstance(authority, Mapping):
            continue
        locations.add(authority.get("declaration_location"))
    if not locations:
        return False
    if len(locations) > 1:
        raise UsageError(
            f"cached inventory records {sorted(str(x) for x in locations)} as the authority "
            "declaration location for one repository; a repository resolves exactly one "
            "declaration, so this inventory is internally inconsistent"
        )
    return locations.pop()


def _authority_declaration(
    repo: Path | None,
    *,
    overlay_dir: Path,
    recorded: str | None | bool,
    inventory_name: str,
    now: str,
) -> dict[str, Any]:
    """The digest of the authority declaration in force for one repository.

    The declaration is resolved through :meth:`AuthorityDeclaration.load`, so
    the file hashed here is the file the loader would use — the repository's own
    declaration when it ships one, the operator overlay otherwise. A repository
    nobody has declared anything about gets ``sha256: null`` under
    ``not_found``; there is no placeholder digest, because a digest that stood
    in for an absent declaration would make an unauthorised repository
    indistinguishable from a declared one.

    ``recorded`` is what the run itself resolved. When it disagrees with what is
    in force now, the digest is still reported — it is a real digest of real
    bytes — and ``inventory_agreement`` says it does not bind the run.
    """
    # A missing repository path implies a missing cached inventory, which is the
    # same condition that leaves ``recorded`` unset, so both arrive as
    # ``unrecorded`` rather than as a comparison nobody made.
    agreement = "unrecorded" if recorded is False else None

    if repo is None:
        return {
            "availability": "unavailable",
            "location": None,
            "sha256": None,
            "inventory_agreement": agreement or "unrecorded",
            "detail": (
                f"no cached inventory {inventory_name!r}, so the repository path is unknown "
                "and the declaration bytes could not be read"
            ),
        }

    try:
        declaration = AuthorityDeclaration.load(repo, overlay_dir=overlay_dir)
    except UsageError as exc:
        return {
            "availability": "unavailable",
            "location": None,
            "sha256": None,
            "inventory_agreement": agreement or "unrecorded",
            "detail": f"the authority declaration for {repo.name} could not be resolved: {exc}",
        }

    if agreement is None:
        agreement = "agrees" if recorded == declaration.declaration_location else "diverged"

    if not declaration.declared:
        return {
            "availability": "not_found",
            "location": None,
            "sha256": None,
            "inventory_agreement": agreement,
            "provenance": declaration.provenance(now),
            "detail": (
                f"{repo.name} declares no per-use authority and no operator overlay covers "
                f"it; every use is unknown, so there are no declaration bytes to hash"
            ),
        }

    location = declaration.declaration_location
    if location == "repository":
        source = repo / REPOSITORY_DECLARATION
        recorded_source = REPOSITORY_DECLARATION
    else:
        source = overlay_dir / f"{repo.name}.json"
        # Repository-relative where the overlay lives inside this checkout: an
        # absolute path would record one machine's layout in a committed receipt.
        recorded_source = _relative_to_repo_root(source)
    try:
        digest = sha256_hex(source.read_bytes())
    except OSError as exc:
        return {
            "availability": "unavailable",
            "location": location,
            "sha256": None,
            "inventory_agreement": agreement,
            "detail": f"the declaration at {source} resolved but could not be read: {exc}",
        }

    entry: dict[str, Any] = {
        "availability": "present",
        "location": location,
        "source": recorded_source,
        "sha256": digest,
        "declared_by": declaration.authority,
        "inventory_agreement": agreement,
        # A digest binds the bytes; it says nothing about whose declaration
        # they are or how long it lasts. An overlay hashed into a receipt
        # without its provenance is indistinguishable from a repository's own
        # declaration hashed into the same field, so the marker travels here.
        "provenance": declaration.provenance(now),
    }
    require_provenance(
        entry["provenance"], where=f"the census receipt entry for {repo.name}"
    )
    if declaration.effective_from_revision:
        entry["effective_from_revision"] = declaration.effective_from_revision
    if agreement == "diverged":
        entry["detail"] = (
            f"the run resolved {recorded!r} as the declaration location and "
            f"{location!r} is in force now; this digest is of the declaration in force "
            "at emission and does not bind the run's authority basis"
        )
    return entry


def _selection(run: RepositoryRun | None, inventory_name: str) -> dict[str, Any]:
    if run is None:
        return {
            "availability": "unavailable",
            "detail": (
                f"the caller supplied no run configuration for {inventory_name!r}; the "
                "include and exclude globs a cached inventory was read under are not "
                "recorded in the inventory itself"
            ),
        }
    return {
        "availability": "present",
        "include": list(run.include),
        "exclude": list(run.exclude),
    }


def _elapsed(run: RepositoryRun | None, inventory_name: str) -> dict[str, Any]:
    if run is None:
        return {
            "availability": "unavailable",
            "detail": f"the caller supplied no run configuration for {inventory_name!r}",
        }
    if run.elapsed_seconds is None:
        return {
            "availability": "not_searched",
            "detail": (
                "this inventory was not timed; a census recomputed from a cached "
                "inventory would time a JSON read rather than the mining run"
            ),
        }
    return {"availability": "present", "seconds": round(float(run.elapsed_seconds), 3)}


def _repository_entry(
    entry: Mapping[str, Any],
    *,
    role: str,
    raw: Mapping[str, tuple[dict[str, Any], str]],
    runs: Mapping[str, RepositoryRun],
    overlay_dir: Path,
    now: str,
) -> dict[str, Any]:
    """One census entry, bound to the inventory and configuration behind it."""
    what = "a census repository entry"
    repository = str(_require(entry, "repository", what))
    family = str(_require(entry, "family", what))
    name = raw_inventory_name(repository, family)
    cached = raw.get(name)

    if cached is None:
        raw_block: dict[str, Any] = {
            "name": name,
            "availability": "not_found",
            "sha256": None,
            "detail": (
                f"no cached inventory {name!r}; raw inventories stay local and gitignored, "
                "so a receipt emitted away from the run that produced them cannot bind one"
            ),
        }
        repo_path: Path | None = None
        recorded: str | None | bool = False
    else:
        inventory, digest = cached
        raw_block = {
            "name": name,
            "availability": "present",
            "sha256": digest,
            "artifacts": len(inventory.get("artifacts") or []),
        }
        repo_path = Path(str(_require(inventory, "repository", f"the cached inventory {name}")))
        recorded = _recorded_authority_location(inventory)

    run = runs.get(name)
    return {
        "repository": repository,
        "family": family,
        "role": role,
        "revision": str(_require(entry, "revision", what)),
        "documents": int(_require(entry, "documents", what)),
        "raw_inventory": raw_block,
        "selection": _selection(run, name),
        "authority_declaration": _authority_declaration(
            repo_path,
            overlay_dir=overlay_dir,
            recorded=recorded,
            inventory_name=name,
            now=now,
        ),
        "elapsed": _elapsed(run, name),
    }


def _artifact_identity(
    entries: Sequence[Mapping[str, Any]], raw: Mapping[str, tuple[dict[str, Any], str]]
) -> dict[str, Any]:
    """Every source-artifact identifier the run produced, sorted, with a digest.

    A partial list is refused. Dropping the artifacts of one unreadable
    inventory would look exactly like a corpus that shrank, which is the
    difference this receipt exists to make visible.
    """
    missing = [
        entry["raw_inventory"]["name"]
        for entry in entries
        if entry["raw_inventory"]["availability"] != "present"
    ]
    if missing:
        return {
            "availability": "unavailable",
            "detail": (
                f"{len(missing)} of {len(entries)} cached inventories could not be read "
                f"({', '.join(missing)}); a partial identifier list would be "
                "indistinguishable from a smaller corpus"
            ),
        }
    ids: list[str] = []
    for entry in entries:
        inventory, _digest = raw[entry["raw_inventory"]["name"]]
        for artifact in inventory.get("artifacts") or []:
            identifier = artifact.get("artifact_id")
            if not isinstance(identifier, str) or not identifier:
                raise UsageError(
                    f"an artifact in {entry['raw_inventory']['name']} carries no artifact_id; "
                    "a census receipt cannot bind an unaddressed record"
                )
            ids.append(identifier)
    ids.sort()
    return {
        "availability": "present",
        "count": len(ids),
        "digest": sha256_hex(canonical_bytes(ids)),
        "artifact_ids": ids,
    }


def _total_elapsed(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    measured = [
        e["elapsed"]["seconds"] for e in entries if e["elapsed"]["availability"] == "present"
    ]
    block: dict[str, Any] = {
        "availability": "present" if len(measured) == len(entries) else "unavailable",
        "measured_repositories": len(measured),
        "total_repositories": len(entries),
    }
    if len(measured) == len(entries) and entries:
        block["total_seconds"] = round(sum(measured), 3)
        return block
    block["availability"] = "unavailable"
    block["detail"] = (
        f"{len(measured)} of {len(entries)} inventories reported wall-clock time; a total "
        "over the measured subset would understate the run while looking like a measurement"
    )
    return block


def _gate(census: Mapping[str, Any]) -> dict[str, Any]:
    """The input census gate, copied without recomputation.

    ``lines`` is dropped because it is a rendering of the same four checks;
    nothing else is transformed. Re-deriving a verdict here would create a
    second answer that can disagree with the document being bound.
    """
    gate = _require(census, "gate", "the census")
    if not isinstance(gate, Mapping):
        raise UsageError("the census gate is not an object")
    return {
        "checks": [dict(check) for check in _require(gate, "checks", "the census gate")],
        "passed": _require(gate, "passed", "the census gate"),
        "total": _require(gate, "total", "the census gate"),
        "clear_to_label": _require(gate, "clear_to_label", "the census gate"),
    }


# -- emission ---------------------------------------------------------------


def build_census_receipt(
    ctx: Any,
    census_dir: str | Path,
    *,
    runs: Sequence[RepositoryRun] = (),
    implementation_repo: str | Path = REPO_ROOT,
    authority_overlay: str | Path = DEFAULT_AUTHORITY_OVERLAY,
    worktree: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the receipt for the census under ``census_dir``.

    Reads ``census.json`` and the cached inventories under ``raw/``. ``runs``
    carries the include and exclude globs each inventory was given and how long
    it took, keyed by :func:`raw_inventory_name`; an inventory with no entry
    reports both as unavailable rather than as an empty selection.

    ``worktree`` supplies the implementation's cleanliness as observed before
    the census ran. Sampling it here instead would always report dirty, because
    the census has already written its own output by the time the receipt is
    built.

    The returned document is sealed and then validated against
    ``ats_census_receipt_v1.schema.json``, so a caller never receives a receipt
    that is unaddressed or would fail to load.
    """
    census_dir = Path(census_dir)
    census, census_sha256 = _read_census(census_dir)
    raw = _read_raw_inventories(census_dir / RAW_DIRNAME)
    overlay_dir = Path(authority_overlay)
    by_name = {run.inventory: run for run in runs}

    # A probe reads a repository at a revision exactly as a census entry does,
    # so both are bound; the role keeps them distinguishable, because a probe is
    # deliberately outside the corpus statistics.
    sections = (("census", "repositories"), ("template_probe", "template_collapse_probes"))
    entries = [
        _repository_entry(
            entry, role=role, raw=raw, runs=by_name, overlay_dir=overlay_dir, now=ctx.timestamp()
        )
        for role, key in sections
        for entry in _require(census, key, "the census")
    ]

    census_implementation = census.get("implementation")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": ctx.timestamp(),
        "stage": str(_require(census, "stage", "the census")),
        "spec_version": ctx.spec_version,
        "census": {
            "path": _relative_to_repo_root(census_dir / CENSUS_FILENAME),
            "sha256": census_sha256,
            "schema_version": str(_require(census, "schema_version", "the census")),
            "generated_at": str(_require(census, "generated_at", "the census")),
            "spec_version": str(_require(census, "spec_version", "the census")),
            **(
                {"implementation": {k: str(v) for k, v in census_implementation.items()}}
                if isinstance(census_implementation, Mapping)
                else {}
            ),
        },
        "implementation": _implementation(
            ctx, Path(implementation_repo), worktree=worktree
        ),
        "repositories": entries,
        "artifact_identity": _artifact_identity(entries, raw),
        "corpus_statistics": dict(_require(census, "totals", "the census")),
        "stage_1_gate": _gate(census),
        "elapsed": _total_elapsed(entries),
    }
    sealed = seal(receipt)
    ctx.schemas.validate_document(sealed)
    return sealed


def receipt_bytes(receipt: Mapping[str, Any]) -> bytes:
    """The exact bytes of an emitted receipt.

    Keys are sorted and the indentation is fixed, so two emissions over
    unchanged inputs are byte-identical regardless of the order this module
    happened to build the document in.
    """
    text = json.dumps(dict(receipt), indent=2, ensure_ascii=False, sort_keys=True)
    return text.encode("utf-8") + b"\n"


def write_census_receipt(census_dir: str | Path, receipt: Mapping[str, Any]) -> Path:
    """Write the receipt beside its census; returns the path written.

    The receipt's identity is its own ``receipt_sha256``, so the caller has it
    already and this function does not hand back a second digest that could
    disagree with it.
    """
    path = Path(census_dir) / RECEIPT_FILENAME
    path.write_bytes(receipt_bytes(receipt))
    return path

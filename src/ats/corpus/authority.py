"""Per-use corpus authority, resolved by intersection.

Having a repository on disk is not permission to mine it, and permission to
mine it is not permission to train on it. The uses here are kept apart because
they are not substitutes for each other, and because the consequences of each
differ (spec Sections 16.9 and 17.13).

Four rules govern resolution, and every one of them exists to stop a
permission appearing that nobody granted:

* **Most restrictive wins.** Every applicable declaration is intersected. No
  input can widen what another input allows.
* **Unknown stays unknown.** The absence of a declaration never inherits
  ``allow`` from a sibling use, from the repository root, or from a default.
* **Only an owner can grant.** Any basis other than an owner declaration is
  capped: it can restrict a use, never open one.
* **Provenance is not permission.** An operator overlay and a repository's own
  declaration can resolve to identical values. They are not the same thing:
  one is what an owner says about its own material and the other is what an
  operator wrote about it while onboarding is unfinished, and only the second
  is temporary by construction. Every report of an authority therefore carries
  :data:`PROVENANCE_KEYS`, and :func:`require_provenance` refuses one that
  does not.

A declaration binds nine things (:data:`REQUIRED_BINDINGS`). None of them has a
default, because every one of them is a fact about the world that cannot be
recovered from the others: who issued it, why they may, which repository, at
which revision, for which uses, over which paths, when, until when, and what
replaced it.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

from ..canonical import sha256_hex
from ..errors import UsageError

SCHEMA_ID: Final[str] = "ats_corpus_authority_v1.schema.json"
SCHEMA_VERSION: Final[str] = "ats.corpus_authority.v1"

#: Where a repository declares its own authority. This is the destination
#: state: the owner declares in place, and the declaration travels with the
#: repository.
REPOSITORY_DECLARATION: Final[str] = ".ats/corpus.json"

#: The uses a declaration must answer. Every one is separately consequential,
#: so a declaration that omits one leaves it unknown rather than implied.
USES: Final[tuple[str, ...]] = (
    "inventory",
    "candidate_mining",
    "human_annotation",
    "deterministic_mutation",
    "evaluation",
    "model_training",
    "model_distillation",
    "external_model_submission",
    "publication",
    "cross_repository_derivatives",
)

#: Permissiveness order, least permissive first. ``deny`` sits below
#: ``unknown`` deliberately: both block, but a refusal is a decision somebody
#: made and absence is not, so intersecting them keeps the refusal.
_RANK: Final[dict[str, int]] = {
    "deny": 0,
    "unknown": 1,
    "defer": 2,
    "allow_private": 3,
    "allow": 4,
}

#: Values under which work may proceed. ``defer`` is excluded: it is an
#: explicit refusal to decide, and an undecided use is not an authorised one.
_PERMITTED: Final[frozenset[str]] = frozenset({"allow", "allow_private"})

#: Bases that may only restrict. An owner declaration is the sole basis that
#: can grant, so a consumer cannot authorise itself by writing a manifest.
_GRANTING_AUTHORITIES: Final[frozenset[str]] = frozenset({"owner_declared"})

#: Bases a declaration may claim. The kind is machine-readable because it
#: gates granting; the statement beside it in the declaration is the part a
#: person has to be able to check.
_BASIS_KINDS: Final[frozenset[str]] = frozenset(
    {"owner_declared", "operator_pilot_overlay", "inherited", "unknown"}
)

#: Where a declaration may have been found. These are the only two provenances
#: this build can observe, and they are not interchangeable: see
#: :meth:`AuthorityDeclaration.provenance`.
_LOCATIONS: Final[frozenset[str]] = frozenset({"repository", "pilot_overlay"})

#: A principal is an identity, not a seat. "the owner", "operator", "admin",
#: and "the team" all name a role: a role cannot be asked to revisit its own
#: declaration, cannot withdraw it, and outlives whoever occupied it. Requiring
#: a scheme-qualified identifier makes the difference mechanical rather than a
#: matter of taste -- ``https://github.com/<account>`` and ``mailto:<address>``
#: pass, ``owner`` does not.
_PRINCIPAL_ID: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9+.\-]*:\S")

#: What a principal is. A service account can hold an identity but cannot
#: exercise the judgment a review date asks for, so the two are recorded
#: apart rather than flattened into "somebody".
_PRINCIPAL_KINDS: Final[frozenset[str]] = frozenset({"person", "organisation", "service"})

#: Coarse projection order for ``ats_source_artifact_v1``'s single
#: ``use_authority`` field, least permissive first. It mirrors :data:`_RANK`
#: for the same reason: ``prohibited`` is a refusal somebody made and
#: ``unknown`` is the absence of one, so a projection that ranked them
#: together -- or let one overwrite the other -- would erase the distinction
#: the rest of this module exists to keep.
COARSE_RANK: Final[dict[str, int]] = {
    "prohibited": 0,
    "unknown": 1,
    "internal_only": 2,
    "internal_training_permitted": 3,
    "external_training_permitted": 4,
}


@dataclass(frozen=True, slots=True)
class Binding:
    """One leaf a declaration must bind, and why its absence is not survivable.

    ``nullable`` marks a binding whose *answer* may be null but whose *key* may
    not be missing. ``superseded_by: null`` says "nothing has replaced this";
    an absent ``superseded_by`` says nothing at all, and the difference is the
    whole point of recording it.
    """

    #: The concept from the declaration contract. Several leaves may share one.
    name: str
    #: Where the leaf lives in the declaration document.
    path: tuple[str, ...]
    #: What goes wrong when it is missing. This is the error text a person
    #: reads, so it says the consequence rather than restating the field name.
    why: str
    nullable: bool = False

    @property
    def pointer(self) -> str:
        return ".".join(self.path)


#: The nine concepts every declaration binds, expanded to the leaves that carry
#: them. Nothing here has a default. A declaration that omits one is refused
#: rather than completed, because each of these is a fact about the world --
#: not a preference -- and inventing it would be the exact failure this corpus
#: is built to avoid.
REQUIRED_BINDINGS: Final[tuple[Binding, ...]] = (
    Binding(
        "principal",
        ("principal", "id"),
        "an unsigned declaration cannot be questioned, revisited, or withdrawn by anybody",
    ),
    Binding(
        "principal",
        ("principal", "kind"),
        "a service account holds an identity but cannot exercise the judgment a review "
        "date asks for, so which kind of principal signed has to be stated",
    ),
    Binding(
        "authority_basis",
        ("authority_basis", "kind"),
        "possession of a copy is not standing to license it (spec Section 17.13)",
    ),
    Binding(
        "authority_basis",
        ("authority_basis", "statement"),
        "the basis kind names the shape of the claim; only the statement says why this "
        "principal may speak for this repository, and an unstated why cannot be checked",
    ),
    Binding(
        "repository_identity",
        ("repository", "name"),
        "a declaration has to say what it is about",
    ),
    Binding(
        "repository_identity",
        ("repository", "origin"),
        "a directory name is ambiguous the moment two checkouts share it; the origin "
        "remote disambiguates, and an explicit null says the repository has none",
        nullable=True,
    ),
    Binding(
        "repository_identity",
        ("repository", "root_commit"),
        "the only identity that survives renaming, moving, and losing the remote",
    ),
    Binding(
        "effective_revision",
        ("repository", "effective_from_revision"),
        "a declaration says nothing about revisions it was not made about",
    ),
    Binding(
        "permitted_uses",
        ("uses",),
        "the uses are not substitutes for each other, so one answer cannot cover them",
    ),
    Binding(
        "content_scope",
        ("content",),
        "an unscoped declaration silently covers whatever happens to be in the tree, "
        "including material the principal did not write",
    ),
    Binding(
        "issued_at",
        ("issued_at",),
        "a declaration with no date cannot be ordered against the events it governs",
    ),
    Binding(
        "review_after",
        ("review_after",),
        "a declaration that never expires quietly becomes permanent governance nobody "
        "re-consented to",
    ),
    Binding(
        "superseded_by",
        ("superseded_by",),
        "an explicit null says nothing has replaced this; an absent key says nobody "
        "checked, and the two must not read alike",
        nullable=True,
    ),
)

#: The nine concepts, in declaration order, deduplicated.
BINDING_NAMES: Final[tuple[str, ...]] = tuple(
    dict.fromkeys(binding.name for binding in REQUIRED_BINDINGS)
)

#: Every key :meth:`AuthorityDeclaration.provenance` emits. A report carries
#: all of them beside an authority or it is not reporting that authority
#: honestly -- see :func:`require_provenance`.
PROVENANCE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "declaration_location",
        "repository_owned",
        "principal",
        "authority_basis",
        "issued_at",
        "review_after",
        "review_status",
        "superseded_by",
    }
)


def require_provenance(block: Mapping[str, Any], *, where: str) -> None:
    """Refuse an authority report block that has lost its provenance.

    An overlay and a repository-owned declaration can resolve to identical
    permissions, and a report that prints only the permission invites the
    reader to treat them as the same thing. They are not: the overlay is an
    operator's account of somebody else's material, written because onboarding
    is unfinished, and it expires. Every report site calls this on the block it
    built, so a future hand-rolled dict that forgets the marker fails loudly
    instead of quietly promoting an overlay to repository-owned authority.
    """
    missing = sorted(PROVENANCE_KEYS - set(block))
    if missing:
        raise UsageError(
            f"the authority block in {where} omits {', '.join(missing)}; an authority "
            "cannot be reported without saying where it was declared, who declared it, "
            "and when it must be revisited, because an overlay reported without those "
            "reads exactly like a repository's own declaration"
        )


def intersect(*values: str) -> str:
    """The most restrictive of ``values``.

    With no values this is ``unknown``: nothing was declared, so nothing is
    permitted, and saying ``deny`` would claim a refusal nobody made.
    """
    resolved = "unknown"
    best = _RANK["allow"] + 1
    for value in values:
        if value not in _RANK:
            raise UsageError(
                f"{value!r} is not an authority value; expected one of "
                f"{', '.join(sorted(_RANK))}"
            )
        rank = _RANK[value]
        if rank < best:
            best, resolved = rank, value
    return resolved


def permits(value: str) -> bool:
    """Whether work may proceed under ``value``."""
    return value in _PERMITTED


def coarse_recognised(value: str) -> bool:
    """Whether ``value`` is a coarse ``use_authority`` this build understands."""
    return value in COARSE_RANK


def intersect_coarse(*values: str) -> str:
    """The most restrictive coarse ``use_authority``.

    The same intersection as :func:`intersect`, over the artifact schema's
    five-value vocabulary. It exists so that a second declaration of the coarse
    value -- a commit trailer, say -- restricts like every other input instead
    of replacing what the repository declared. Replacement is the one operation
    that can turn ``prohibited`` back into a permission, and it is precisely
    what a lower-authority input must not be able to do.

    With no values this is ``unknown``, for the reason :func:`intersect` gives.
    An unrecognised value raises: a caller reading an arbitrary string out of a
    commit message has to decide what an unreadable declaration means, and this
    function will not decide it for them by ranking it.
    """
    resolved = "unknown"
    best = COARSE_RANK["external_training_permitted"] + 1
    for value in values:
        if value not in COARSE_RANK:
            raise UsageError(
                f"{value!r} is not a coarse use_authority; expected one of "
                f"{', '.join(sorted(COARSE_RANK))}"
            )
        rank = COARSE_RANK[value]
        if rank < best:
            best, resolved = rank, value
    return resolved


@dataclass(frozen=True, slots=True)
class Resolution:
    """One use resolved for one path, with everything that constrained it."""

    use: str
    value: str
    permitted: bool
    #: Every input that contributed, in the order applied. A resolution that
    #: blocks is only actionable if it says which input blocked it.
    basis: tuple[str, ...]
    #: Where the declaration behind this resolution was found, or ``None`` when
    #: there was none. A resolution is the finest grain authority is reported
    #: at -- profile hypotheses carry one verbatim -- so the provenance travels
    #: here too, rather than only on the whole-declaration report.
    declaration_location: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "use": self.use,
            "value": self.value,
            "permitted": self.permitted,
            "basis": list(self.basis),
            "declaration_location": self.declaration_location,
        }


@dataclass(frozen=True, slots=True)
class AuthorityDeclaration:
    """A resolved authority declaration for one repository."""

    repository: str
    #: The basis *kind*. Named ``authority`` for the field it has always been;
    #: the prose justification beside it is :attr:`authority_basis_statement`.
    authority: str
    effective_from_revision: str
    declaration_location: str | None
    uses: Mapping[str, str]
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    path_overrides: tuple[Mapping[str, Any], ...]
    classification: str
    export_raw_text: bool
    handling: Mapping[str, Any]
    authorship: str
    model_authorship_inference: str
    declared: bool
    #: Scheme-qualified identity of whoever issued this. Empty only when
    #: nothing was declared at all.
    principal: str = ""
    principal_kind: str = "unknown"
    authority_basis_statement: str = ""
    #: The ``origin`` remote, or ``None`` when the repository has none. The
    #: two are different answers and are not collapsed.
    origin: str | None = None
    root_commit: str = ""
    issued_at: str = ""
    #: The date this declaration must be revisited. An overlay is temporary by
    #: construction; past this date :meth:`resolve` caps it at ``unknown``
    #: whenever it is given a clock to check against.
    review_after: str = ""
    superseded_by: str | None = None
    notes: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)
    #: Digest of the exact bytes the declaration was read from, when it was
    #: read from a file. This is the value anything downstream keys staleness
    #: on, so it is recorded by the one method that reads the file rather than
    #: recomputed by each consumer: a second hash is a second answer, and the
    #: whole use of the value is that a difference means the declaration moved.
    #: ``None`` on :meth:`undeclared`, where there were no bytes to hash.
    source_sha256: str | None = None

    # -- construction -------------------------------------------------------

    @classmethod
    def undeclared(cls, repository: str) -> AuthorityDeclaration:
        """The state of a repository nobody has declared anything about.

        Every use is unknown. This is not a permissive default with gaps; it
        is the honest description of having been told nothing.
        """
        return cls(
            repository=repository,
            authority="unknown",
            effective_from_revision="",
            declaration_location=None,
            uses={use: "unknown" for use in USES},
            include=(),
            exclude=(),
            path_overrides=(),
            classification="restricted",
            export_raw_text=False,
            handling={"classification": "restricted", "export_raw_text": False},
            authorship="unknown_unless_explicit",
            model_authorship_inference="prohibited",
            declared=False,
        )

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        repository: str,
        location: str,
        source_sha256: str | None = None,
    ) -> AuthorityDeclaration:
        """Read a declaration, refusing anything it did not actually bind.

        Every one of :data:`REQUIRED_BINDINGS` is checked before a field is
        read, and a missing one raises naming the concept, the leaf, and the
        consequence. Nothing is filled in: a declaration that omits a binding
        is not a declaration with a gap, it is somebody's unfinished work, and
        completing it here would put a permission in front of a reader that no
        principal ever issued.
        """
        if data.get("schema_version") != SCHEMA_VERSION:
            raise UsageError(
                f"authority declaration for {repository} has schema_version "
                f"{data.get('schema_version')!r}, expected {SCHEMA_VERSION!r}"
            )
        if location not in _LOCATIONS:
            raise UsageError(
                f"{location!r} is not a declaration location; expected one of "
                f"{', '.join(sorted(_LOCATIONS))}"
            )
        _require_bindings(data, repository=repository)

        block = data["repository"]
        principal = data["principal"]
        basis = data["authority_basis"]

        # Where the declaration was actually found, not where it claims to
        # live. Provenance is an observation; a file sitting in an overlay does
        # not get to describe itself as declared in place, and one that tries
        # is refused rather than quietly corrected -- a corrected file would
        # keep shipping the false claim to anyone reading the bytes directly.
        claimed = block.get("declaration_location")
        if claimed != location:
            raise UsageError(
                f"authority declaration for {repository} describes itself as {claimed!r} "
                f"but was read from {location!r}; a declaration cannot state a provenance "
                "other than the one it was found at, because an overlay presented as "
                "repository-owned authority is exactly the confusion this field prevents"
            )

        principal_id = str(principal["id"])
        if not _PRINCIPAL_ID.match(principal_id):
            raise UsageError(
                f"authority declaration for {repository} names the principal "
                f"{principal_id!r}, which is a role rather than an identity; a role cannot "
                "be asked to revisit its own declaration, so a principal must be a "
                "scheme-qualified identity such as 'https://github.com/<account>' or "
                "'mailto:<address>'"
            )
        principal_kind = str(principal["kind"])
        if principal_kind not in _PRINCIPAL_KINDS:
            raise UsageError(
                f"authority declaration for {repository} gives the principal kind "
                f"{principal_kind!r}; expected one of {', '.join(sorted(_PRINCIPAL_KINDS))}"
            )
        basis_kind = str(basis["kind"])
        if basis_kind not in _BASIS_KINDS:
            raise UsageError(
                f"authority declaration for {repository} claims the authority basis "
                f"{basis_kind!r}; expected one of {', '.join(sorted(_BASIS_KINDS))}"
            )

        declared_uses = data["uses"]
        if not isinstance(declared_uses, Mapping):
            raise UsageError(f"authority declaration for {repository} has no uses block")
        # An omitted use is unknown, never inherited from its neighbours.
        uses = {use: str(declared_uses.get(use, "unknown")) for use in USES}
        for use, value in uses.items():
            if value not in _RANK:
                raise UsageError(
                    f"authority declaration for {repository} gives use {use!r} the value "
                    f"{value!r}; expected one of {', '.join(sorted(_RANK))}"
                )
        content = data["content"] or {}
        handling = dict(data.get("handling") or {})
        provenance = data.get("provenance") or {}
        issued_at = str(data["issued_at"])
        review_after = str(data["review_after"])
        # Both dates are parsed here rather than at first use, so a declaration
        # whose review date cannot be read is refused by the loader instead of
        # silently never coming due.
        if _parse_timestamp(review_after, repository, "review_after") <= _parse_timestamp(
            issued_at, repository, "issued_at"
        ):
            raise UsageError(
                f"authority declaration for {repository} sets review_after "
                f"{review_after!r} at or before issued_at {issued_at!r}; a declaration "
                "that is due for review before it was issued has no live interval at all"
            )
        superseded_by = data["superseded_by"]
        origin = block["origin"]
        return cls(
            repository=str(block["name"]),
            authority=basis_kind,
            effective_from_revision=str(block["effective_from_revision"]),
            declaration_location=location,
            uses=uses,
            include=tuple(content.get("include") or ()),
            exclude=tuple(content.get("exclude") or ()),
            path_overrides=tuple(data.get("path_overrides") or ()),
            classification=str(handling.get("classification") or "restricted"),
            export_raw_text=bool(handling.get("export_raw_text", False)),
            handling=handling,
            authorship=str(provenance.get("authorship") or "unknown_unless_explicit"),
            model_authorship_inference=str(
                provenance.get("model_authorship_inference") or "prohibited"
            ),
            declared=True,
            principal=principal_id,
            principal_kind=principal_kind,
            authority_basis_statement=str(basis["statement"]),
            origin=str(origin) if origin is not None else None,
            root_commit=str(block["root_commit"]),
            issued_at=issued_at,
            review_after=review_after,
            superseded_by=str(superseded_by) if superseded_by is not None else None,
            notes=str(data["notes"]) if data.get("notes") else None,
            raw=dict(data),
            source_sha256=source_sha256,
        )

    @classmethod
    def from_file(
        cls, source: str | Path, *, repository: str, location: str
    ) -> AuthorityDeclaration:
        """Read a declaration from disk, recording the digest of the bytes read.

        The bytes are read once and both parsed and hashed, so the permissions
        a caller acts on and the digest it records cannot describe two
        different revisions of the file.

        Every consumer that needs to know *which* declaration answered goes
        through here. That matters more than it looks: a declaration's bytes
        sit inside every ``artifact_id`` built under it (see
        ``ats.corpus.inventory.build_inventory``), so this digest is how a
        later reader detects that an overlay edit re-addressed a repository's
        documents. A digest computed a second way somewhere else is a second
        answer to that question.
        """
        path = Path(source)
        raw = _read_bytes(path)
        return cls.from_dict(
            _decode_json(raw, path),
            repository=repository,
            location=location,
            source_sha256=sha256_hex(raw),
        )

    @classmethod
    def load(
        cls, repo: Path, *, overlay_dir: Path | None = None
    ) -> AuthorityDeclaration:
        """Resolve the authority for ``repo``.

        The repository's own declaration is preferred over an operator overlay,
        always. An overlay exists only so a pilot can proceed before every
        repository has been onboarded; it must never mask what a repository
        says about itself.

        ``.ats/corpus.json`` predates per-use authority: the original form
        declares a repository group and a single handling policy and has no
        ``schema_version``. That file is still honoured for what it does say
        (see :class:`ats.corpus.inventory.Declaration`), but it cannot express
        per-use authority, so authority stays undeclared rather than being
        invented from it. A file that *does* carry a ``schema_version`` and
        carries the wrong one is a version mismatch and raises, because that is
        a declaration someone wrote and got wrong.
        """
        repo = Path(repo)
        local = repo / REPOSITORY_DECLARATION
        if local.is_file():
            # Peeked at before loading: a file with no ``schema_version`` is
            # not a declaration this class can read at all, and there is no
            # declaration whose bytes would be worth recording.
            if "schema_version" not in _read_json(local):
                return cls.undeclared(repo.name)
            return cls.from_file(local, repository=repo.name, location="repository")
        if overlay_dir is not None:
            overlay = Path(overlay_dir) / f"{repo.name}.json"
            if overlay.is_file():
                return cls.from_file(
                    overlay, repository=repo.name, location="pilot_overlay"
                )
        return cls.undeclared(repo.name)

    # -- resolution ---------------------------------------------------------

    def resolve(
        self,
        use: str,
        path: str | None = None,
        *,
        vendored: bool = False,
        exclusions: Sequence[str] = (),
        destination: str | None = None,
        now: str | None = None,
    ) -> Resolution:
        """Resolve one ``use`` for one ``path``, intersecting every constraint.

        ``vendored`` marks third-party content. The repository owner is not its
        author and cannot grant authority over it, so it caps at ``unknown``
        rather than ``deny``: this is missing authority, not a refusal.

        ``exclusions`` are operator-level path exclusions, and ``destination``
        names where a result would go, so that a use permitted locally is still
        blocked when the destination is not.

        ``now`` is the clock to check ``review_after`` against. Supplying it
        caps a lapsed declaration at ``unknown``; omitting it leaves the
        declaration's age unexamined, which :meth:`provenance` reports as
        ``review_status: unchecked`` rather than as a clean bill of health.
        """
        if use not in USES:
            raise UsageError(f"{use!r} is not a corpus use; expected one of {', '.join(USES)}")

        values: list[str] = []
        basis: list[str] = []

        if not self.declared:
            return Resolution(use, "unknown", False, ("no-declaration",), None)

        declared = self.uses[use]
        values.append(declared)
        # The location, not the literal word "repository". The old token read
        # ``repository:owner_declared:allow`` for an overlay too, which is the
        # one string in this module that could tell a reader an operator
        # overlay was the repository's own declaration.
        basis.append(f"{self.declaration_location}:{self.authority}:{declared}")

        if now is not None and self.review_status(now) == "overdue":
            # A declaration past its review date has not been refused; it has
            # lapsed. Nobody said no, so this caps at ``unknown`` rather than
            # ``deny`` -- and it caps rather than being ignored, because a
            # declaration that keeps granting after the date it was supposed to
            # be revisited is permanent governance nobody re-consented to.
            values.append("unknown")
            basis.append(f"review-overdue:{self.review_after}")

        # Only an owner can open a use. Any other basis is capped at the point
        # where it stops being a grant and becomes an assertion about someone
        # else's material.
        if self.authority not in _GRANTING_AUTHORITIES and permits(declared):
            values.append("allow_private")
            basis.append(f"non-owner-authority-capped:{self.authority}")

        if path is not None:
            if self.include and not _matches(path, self.include):
                values.append("unknown")
                basis.append("outside-declared-include")
            if self.exclude and _matches(path, self.exclude):
                values.append("unknown")
                basis.append("excluded-by-declaration")
            for override in self.path_overrides:
                pattern = str(override.get("pattern", ""))
                if pattern and fnmatch.fnmatch(path, pattern):
                    override_uses = override.get("uses") or {}
                    if use in override_uses:
                        value = str(override_uses[use])
                        values.append(value)
                        basis.append(f"path-override:{pattern}:{value}")
            if exclusions and _matches(path, exclusions):
                values.append("unknown")
                basis.append("operator-exclusion")

        if vendored:
            values.append("unknown")
            basis.append("vendored-content")

        if destination is not None and destination != "local":
            # Leaving the local environment is its own use. A locally granted
            # use does not carry authority to send the text anywhere.
            external = self.uses.get("external_model_submission", "unknown")
            values.append(external)
            basis.append(f"destination:{destination}:external_model_submission:{external}")

        resolved = intersect(*values)
        return Resolution(
            use, resolved, permits(resolved), tuple(basis), self.declaration_location
        )

    def resolve_all(self, path: str | None = None, **kwargs: Any) -> dict[str, Resolution]:
        """Every use resolved for one path."""
        return {use: self.resolve(use, path, **kwargs) for use in USES}

    # -- provenance ---------------------------------------------------------

    def review_status(self, now: str | None = None) -> str:
        """``current``, ``overdue``, ``unchecked``, or ``not_applicable``.

        ``unchecked`` is a real answer and not a synonym for ``current``: a
        caller with no clock has not established that this declaration is
        still live, and saying it is would be the plausible-default failure
        this module exists to prevent (ADR-0002).
        """
        if not self.declared:
            return "not_applicable"
        if now is None:
            return "unchecked"
        due = _parse_timestamp(self.review_after, self.repository, "review_after")
        return "overdue" if _parse_timestamp(now, self.repository, "now") > due else "current"

    def provenance(self, now: str | None = None) -> dict[str, Any]:
        """The marker every report of this authority carries.

        Two declarations can permit exactly the same work and still be
        different objects. A repository-owned declaration is what an owner says
        about its own material, travels with the repository, and is as durable
        as the repository. An operator overlay is what somebody wrote about
        that material from outside while onboarding is unfinished, lives in
        this checkout, and expires. ``repository_owned`` is derived from where
        the file was *found*, never from what its basis claims, so an overlay
        whose basis is ``owner_declared`` still reports ``false``.

        A declared authority with no recorded location cannot be reported at
        all. Rendering it would leave a reader with a permission and no way to
        tell which of the two kinds granted it, and the safe-looking reading --
        that it came from the repository -- is the wrong one.
        """
        if self.declared and self.declaration_location is None:
            raise UsageError(
                f"the authority for {self.repository} is declared but records no "
                "declaration location, so it cannot be reported: a reader would have no "
                "way to tell an operator overlay from the repository's own declaration"
            )
        return {
            "declaration_location": self.declaration_location,
            "repository_owned": self.declaration_location == "repository",
            "principal": self.principal or None,
            "authority_basis": self.authority,
            "issued_at": self.issued_at or None,
            "review_after": self.review_after or None,
            "review_status": self.review_status(now),
            "superseded_by": self.superseded_by,
        }

    # -- projection ---------------------------------------------------------

    def coarse_use_authority(self, path: str | None = None, **kwargs: Any) -> str:
        """Project onto ``ats_source_artifact_v1``'s single ``use_authority``.

        The artifact schema predates per-use authority and carries one value.
        The projection is lossy by construction, so the full resolution is
        recorded beside it rather than replaced by it.
        """
        if not self.declared:
            return "unknown"
        inventory = self.resolve("inventory", path, **kwargs)
        if not inventory.permitted:
            return "prohibited" if inventory.value == "deny" else "unknown"
        training = self.resolve("model_training", path, **kwargs)
        if not training.permitted:
            return "internal_only"
        external = self.resolve("external_model_submission", path, **kwargs)
        return "external_training_permitted" if external.permitted else "internal_training_permitted"

    def coarse_handling_policy(self) -> str:
        """Project onto ``ats_source_artifact_v1``'s ``handling_policy``."""
        mapping = {
            "public": "public",
            "internal": "internal",
            "private": "confidential",
            "restricted": "restricted",
        }
        return mapping.get(self.classification, "restricted")

    def permits_model_authorship_inference(self) -> bool:
        """Whether authorship may be guessed. It may not, by default."""
        return self.model_authorship_inference == "permitted"


def _leaf(data: Mapping[str, Any], path: Sequence[str]) -> tuple[bool, Any]:
    """``(present, value)`` for a dotted leaf. Presence is a key test.

    A key holding ``null`` is present. That is the whole reason this returns a
    pair instead of a value: ``superseded_by: null`` is an answer and a missing
    ``superseded_by`` is not, and a truthiness test would read them alike.
    """
    node: Any = data
    for key in path:
        if not isinstance(node, Mapping) or key not in node:
            return False, None
        node = node[key]
    return True, node


def _require_bindings(data: Mapping[str, Any], *, repository: str) -> None:
    """Refuse a declaration that omits any of :data:`REQUIRED_BINDINGS`.

    The error names the concept, the leaf, and the consequence, because
    "invalid declaration" tells the person holding it nothing about what they
    have to go and find out.
    """
    for binding in REQUIRED_BINDINGS:
        present, value = _leaf(data, binding.path)
        if not present:
            raise UsageError(
                f"authority declaration for {repository} omits the required binding "
                f"{binding.name!r} at {binding.pointer!r}: {binding.why}"
            )
        if value is None and not binding.nullable:
            raise UsageError(
                f"authority declaration for {repository} leaves the required binding "
                f"{binding.name!r} at {binding.pointer!r} null: {binding.why}"
            )
        if isinstance(value, str) and not value.strip():
            raise UsageError(
                f"authority declaration for {repository} leaves the required binding "
                f"{binding.name!r} at {binding.pointer!r} blank: {binding.why}"
            )
        if binding.path == ("content",) and not value:
            raise UsageError(
                f"authority declaration for {repository} declares an empty content scope: "
                f"{binding.why}"
            )


def _parse_timestamp(value: str, repository: str, field_name: str) -> dt.datetime:
    """An RFC 3339 timestamp, refused rather than guessed at when unreadable.

    A ``review_after`` nobody can parse never comes due, which is the same
    outcome as having no review date at all.
    """
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise UsageError(
            f"authority declaration for {repository} gives {field_name} {value!r}, which is "
            f"not an RFC 3339 timestamp: {exc}"
        ) from exc
    # A naive timestamp is an hour-scale ambiguity in a governance date. It is
    # read as UTC and said so, rather than taking the reader's local zone.
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.UTC)


def _matches(path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _read_json(path: Path) -> Mapping[str, Any]:
    return _decode_json(_read_bytes(path), path)


def _read_bytes(path: Path) -> bytes:
    """The exact bytes of a declaration file.

    Bytes rather than text: the digest recorded beside a parsed declaration has
    to address what is on disk, and decoding then re-encoding would hash a
    normalisation of the file instead of the file itself, so an operator
    checking the value with ``sha256sum`` would get a different answer.
    """
    try:
        return path.read_bytes()
    except OSError as exc:
        raise UsageError(f"{path} is not readable JSON: {exc}") from exc


def _decode_json(raw: bytes, path: Path) -> Mapping[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UsageError(f"{path} is not readable JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise UsageError(f"{path} must contain a JSON object")
    return data

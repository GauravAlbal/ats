"""Deterministic, leakage-grouped corpus splits.

Spec Section 17.7 requires training, development, and evaluation splits to
prevent leakage by grouping on source document, repository or project, author,
source-model family, template, mutation operator, domain, and near-duplicate
cluster, and states plainly that **a random sentence split is nonconforming for
semantic-detector evaluation**.

The implementation deliberately treats exact-content and near-duplicate
relationships as closure edges. Repository and author remain constraints rather
than closure keys: grouping on either alone can put identical bytes on both
sides of a split or collapse a corpus into one group.

So a split is built in two stages, under a strict priority order.

**Stage one — closure.** A group is the connected component (transitive
closure) over every leakage *edge*: the relations that mean two examples carry
the same text, or that one was derived from the other. Those are
:data:`CLOSURE_DIMENSIONS` — lineage, exact content, and near duplication. A
group is atomic: nothing below may divide it. Closure is transitive by
construction, so A near-duplicate B and B template-copied from C puts A, B, and
C in one group even though A and C share no value.

**Stage two — constrained placement.** ``repository``, ``template``, ``author``,
``domain``, ``source_model_family``, and ``mutation_family`` are
:data:`CONSTRAINT_DIMENSIONS`. They never split a group; they only constrain
*where* whole groups are placed, by co-placing the groups that share a value
into one placement block. A constraint is enforced only when a partition
declares it in ``disjoint_on``, and only when enforcing it still leaves as many
placement blocks as there are partitions to fill.

**The priority order** is :data:`CLOSURE_TIERS` then :data:`CONSTRAINT_TIERS`,
highest first: lineage integrity, exact-content integrity, near-duplicate
integrity, project disjointness, template disjointness, author disjointness,
domain balance, and last the residual disjointness dimensions ATS-1 names but
this order does not rank. A higher-priority group is never broken to improve a
lower-priority distribution target. When a lower-priority target cannot be met
without breaking a higher-priority group, the target is reported ``UNMET`` in
``leakage_checks`` — naming the groups that block it — rather than met by
breaking the group or by silently rebalancing.

**Assignment is a pure function of ``(seed, block key)``.** No RNG object is
constructed and no state is carried between groups, so inserting an example
never reshuffles the rest.

**An example with no grouping key is not assigned.** It goes to
``unassignable`` naming the dimensions it lacks. Assigning it anyway would be
the random sentence split under another name.
"""

from __future__ import annotations

import hashlib
from typing import Any, Final, Mapping, Sequence

from ..canonical import content_hash, sha256_hex
from ..errors import UsageError
from . import records as rec

#: The fourteen leakage dimensions, in the order the schema's enum declares
#: them. The canonical group key joins values in exactly this order.
DIMENSIONS: Final[tuple[str, ...]] = (
    "source_document",
    "repository",
    "author",
    "source_model_family",
    "template",
    "mutation_family",
    "source_mutation_pair",
    "domain",
    "copied_text_cluster",
    "near_duplicate_cluster",
    "common_ancestor_document",
    "content_hash",
    "normalized_content_hash",
    "explicit_derivation",
)

#: Extension keys the splitter reads that no record constructor sets yet. They
#: are defined here, beside their only consumer, rather than in
#: :mod:`ats.corpus.records`; a producer of these facts should import them from
#: this module so there is one spelling.
EXT_CONTENT_SHA256: Final[str] = f"{rec.EXT_PREFIX}source-content-sha256"
EXT_NORMALIZED_SHA256: Final[str] = f"{rec.EXT_PREFIX}source-normalized-sha256"
EXT_DERIVED_FROM: Final[str] = f"{rec.EXT_PREFIX}derived-from"

#: ``(priority, tier, dimensions)`` for the closure edges, highest priority
#: first. A shared value on one of these means two examples carry the same text
#: or one descends from the other, so they MUST land in one group.
CLOSURE_TIERS: Final[tuple[tuple[int, str, tuple[str, ...]], ...]] = (
    (
        1,
        "lineage_integrity",
        ("source_mutation_pair", "explicit_derivation", "common_ancestor_document"),
    ),
    # A normalized-hash match is byte identity modulo line endings, NFC
    # composition, and trailing whitespace (``ats.hashes.normalize_text``). That
    # is still identity rather than similarity, which is why it ranks with exact
    # content and not with near duplicates.
    (2, "exact_content_integrity", ("source_document", "content_hash", "normalized_content_hash")),
    (3, "near_duplicate_integrity", ("near_duplicate_cluster", "copied_text_cluster")),
)

#: ``(priority, tier, dimensions)`` for the placement constraints, highest
#: priority first. A constraint co-places whole groups; it never divides one.
#: ``domain`` is a *balance* target rather than a disjointness one — a domain
#: confined to one partition is the opposite of what a balanced split wants —
#: and is reported through ``policy.balance_on``.
CONSTRAINT_TIERS: Final[tuple[tuple[int, str, tuple[str, ...]], ...]] = (
    (4, "project_disjointness", ("repository",)),
    (5, "template_disjointness", ("template",)),
    (6, "author_disjointness", ("author",)),
    (7, "domain_balance", ("domain",)),
    # ATS-1 Section 17.7 names source-model family and mutation operator as
    # leakage dimensions but this repository's priority order does not rank
    # them, so they sit below everything it does rank: they can constrain a
    # placement, never displace a ranked target.
    (8, "residual_disjointness", ("source_model_family", "mutation_family")),
)

_TIERS: Final[tuple[tuple[int, str, tuple[str, ...]], ...]] = CLOSURE_TIERS + CONSTRAINT_TIERS

#: dimension -> its priority. Indexing is deliberate: a dimension added to
#: :data:`DIMENSIONS` without a tier has no defined behaviour, and failing at
#: import is better than guessing one.
PRIORITY: Final[dict[str, int]] = {d: p for p, _, dims in _TIERS for d in dims}

#: dimension -> the name of the tier it belongs to.
TIER: Final[dict[str, str]] = {d: name for _, name, dims in _TIERS for d in dims}

#: The closure edges, in :data:`DIMENSIONS` order. Two examples sharing a value
#: here are transitively joined into one group.
CLOSURE_DIMENSIONS: Final[tuple[str, ...]] = tuple(d for d in DIMENSIONS if PRIORITY[d] <= 3)

#: these would collapse a corpus that is single-repository, single-domain, or
#: heavily attributed to a small author set into one group, which makes every
#: split impossible rather than safe.
CONSTRAINT_DIMENSIONS: Final[tuple[str, ...]] = tuple(d for d in DIMENSIONS if PRIORITY[d] > 3)

#: Dimensions checked for leakage whatever a partition declares. A closure
#: dimension spanning two partitions means the closure itself was broken, which
#: is not something a policy may authorise.
ALWAYS_CHECKED: Final[tuple[str, ...]] = CLOSURE_DIMENSIONS

#: How far a value's observed share of a partition may sit from that partition's
#: ``target_fraction`` before a declared balance target is reported unmet. This
#: is repository policy, not an ATS-1 threshold; a policy MAY override it with
#: ``policy.balance_tolerance``.
BALANCE_TOLERANCE: Final[float] = 0.10

#: Dimensions an example must carry to be assignable, when the policy names
#: none. A hand-authored fixture legitimately has no source document, so
#: requiring one by default would send an entire seed corpus to ``unassignable``.
#: For a mined corpus, declare ``source_document`` as well.
DEFAULT_GROUPING_DIMENSIONS: Final[tuple[str, ...]] = ("repository", "source_mutation_pair")


def _present(provenance: Any, field: str) -> Any:
    """A provenance field, only when the block declares ``availability: present``.

    Spec Section 17.4 keeps ``not_found`` distinct from a value. Reading a field
    out of a block that declares anything other than ``present`` would be
    passing by absence (ADR-0002).
    """
    if not isinstance(provenance, Mapping) or provenance.get("availability") != "present":
        return None
    return provenance.get(field)


def dimension_values(
    example: Mapping[str, Any], *, artifact: Mapping[str, Any] | None = None
) -> dict[str, str]:
    """The leakage-dimension values an example carries.

    ``artifact`` is the ``SourceArtifactV1`` the example was mined from, when
    the caller has it. The example's own fields win; the artifact supplies what
    the example does not carry itself. That is how ``content_hash`` and
    ``normalized_content_hash`` become available at all: both are required
    fields of ``SourceArtifactV1`` and neither is stored on a ``TextExampleV1``.

    A dimension the example does not carry is absent from the result rather than
    present with an empty value, so a missing key is visibly missing.
    """
    extensions = example.get("extensions") or {}
    provenance: Mapping[str, Any] = artifact or {}
    model = _present(provenance.get("model_provenance"), "model")
    values: dict[str, Any] = {
        "source_document": example.get("source_artifact"),
        "repository": example.get("repository_group") or provenance.get("repository_group"),
        "author": extensions.get(rec.EXT_AUTHOR)
        or _present(provenance.get("author_provenance"), "author"),
        # The family is the model name: a point release does not change the
        # stylistic signature this dimension exists to keep out of evaluation.
        "source_model_family": extensions.get(rec.EXT_SOURCE_MODEL_FAMILY)
        or (model.get("name") if isinstance(model, Mapping) else None),
        "template": extensions.get(rec.EXT_TEMPLATE_FAMILY) or provenance.get("template_family"),
        # A synthetic example belongs to its operator's family; a natural one
        # belongs to no mutation family, which is itself a fact worth recording.
        "mutation_family": example.get("mutation_operator")
        or ("natural" if not example.get("synthetic") else None),
        # Source and mutant share this value, which is what keeps a mutation in
        # its source's group (spec 17.7). A chain of mutations shares no single
        # value, so :func:`lineage_targets` follows the pointers as well.
        "source_mutation_pair": extensions.get(rec.EXT_SOURCE_EXAMPLE_ID)
        or example.get("example_id"),
        "domain": example.get("domain") or provenance.get("domain"),
        "copied_text_cluster": extensions.get(rec.EXT_COPIED_TEXT_CLUSTER),
        "near_duplicate_cluster": extensions.get(rec.EXT_NEAR_DUPLICATE_CLUSTER)
        or provenance.get("near_duplicate_cluster"),
        "common_ancestor_document": extensions.get(rec.EXT_COMMON_ANCESTOR),
        # Byte identity of the source document, comparable across repositories.
        # Repository grouping alone cannot stand in for content identity.
        "content_hash": extensions.get(EXT_CONTENT_SHA256) or provenance.get("content_sha256"),
        "normalized_content_hash": extensions.get(EXT_NORMALIZED_SHA256)
        or provenance.get("normalized_sha256"),
        # Absent unless declared. Unlike source_mutation_pair there is no
        # implicit self-derivation, so the dimension can honestly report
        # UNAVAILABLE for a corpus that records no derivations.
        "explicit_derivation": extensions.get(EXT_DERIVED_FROM),
    }
    return {k: str(v) for k, v in values.items() if v}


def lineage_targets(example: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """``(dimension, target example id)`` for each lineage pointer an example declares.

    A shared value joins siblings — two mutants of one source, or two examples
    derived from one document — but a *chain* shares no value: a mutant of a
    mutant points at its parent while the parent points at the original. Lineage
    integrity is priority 1, so the pointers are followed as directed edges too.
    """
    extensions = example.get("extensions") or {}
    own = example.get("example_id")
    declared = (
        ("source_mutation_pair", extensions.get(rec.EXT_SOURCE_EXAMPLE_ID)),
        ("explicit_derivation", extensions.get(EXT_DERIVED_FROM)),
    )
    return tuple(
        (dimension, str(target))
        for dimension, target in declared
        if target and str(target) != str(own)
    )


def canonical_group_key(component: Mapping[str, set[str]]) -> str:
    """A stable identifier for one connected component of examples.

    The component's values are joined in the fixed dimension order, with ``|``
    inside a value percent-escaped so the join is unambiguous, and the result is
    hashed because the raw join has no bound.
    """
    parts: list[str] = []
    for dimension in DIMENSIONS:
        values = sorted(component.get(dimension, ()))
        parts.append(",".join(v.replace("|", "%7C") for v in values))
    return "group-" + sha256_hex("|".join(parts).encode("utf-8"))[:32]


def assign(seed: str, group_key: str, partitions: Sequence[Mapping[str, Any]]) -> str:
    """Assign a group to a partition as a pure function of ``(seed, group_key)``.

    ``u = sha256(seed || 0x00 || group_key)[:8]`` read big-endian and divided by
    ``2**64`` gives a value in ``[0, 1)``; the group falls into the first
    partition whose cumulative target fraction exceeds it. There is no RNG state
    and no dependence on iteration order. Co-placed groups pass the key of their
    placement block rather than their own, which is what makes a constraint hold
    without any group being divided.
    """
    if not group_key:
        raise UsageError(
            "cannot assign an example with no grouping key; a random sentence split is "
            "nonconforming for semantic-detector evaluation (spec 17.7)"
        )
    if not partitions:
        raise UsageError("a split policy must declare at least one partition")
    digest = hashlib.sha256(seed.encode("utf-8") + b"\x00" + group_key.encode("utf-8")).digest()
    u = int.from_bytes(digest[:8], "big") / 2**64
    cumulative = 0.0
    for partition in partitions:
        cumulative += float(partition["target_fraction"])
        if u < cumulative:
            return str(partition["name"])
    # The last partition absorbs any remainder left by fractions that do not
    # sum to exactly one.
    return str(partitions[-1]["name"])


def _root(parent: dict[str, str], node: str) -> str:
    """Find with path halving."""
    while parent[node] != node:
        parent[node] = parent[parent[node]]
        node = parent[node]
    return node


def _merge(parent: dict[str, str], members: Sequence[str]) -> None:
    """Union every member into one set, rooted at the lowest id so unions are order-free."""
    for other in members[1:]:
        a, b = _root(parent, members[0]), _root(parent, other)
        if a != b:
            parent[max(a, b)] = min(a, b)


def _sets(parent: dict[str, str]) -> dict[str, list[str]]:
    """root -> its members, both in sorted order."""
    out: dict[str, list[str]] = {}
    for node in sorted(parent):
        out.setdefault(_root(parent, node), []).append(node)
    return out


def _components(
    values: Mapping[str, Mapping[str, str]],
    dimensions: Sequence[str],
    lineage: Mapping[str, Sequence[tuple[str, str]]],
) -> dict[str, str]:
    """Connected components over the closure edges; example id -> root id.

    Two kinds of edge: a shared value on a closure dimension, and a declared
    lineage pointer from one example to another example in the same corpus. A
    pointer to an example this split does not contain is skipped — there is
    nothing here for it to leak against.
    """
    parent = {example_id: example_id for example_id in values}

    by_value: dict[tuple[str, str], list[str]] = {}
    for example_id in sorted(values):
        for dimension in dimensions:
            value = values[example_id].get(dimension)
            if value:
                by_value.setdefault((dimension, value), []).append(example_id)
    for members in by_value.values():
        _merge(parent, members)

    for example_id in sorted(values):
        for _, target in lineage.get(example_id, ()):
            if target in parent:
                _merge(parent, [example_id, target])
    return {example_id: _root(parent, example_id) for example_id in sorted(values)}


def _binding_dimensions(
    members: Sequence[str],
    values: Mapping[str, Mapping[str, str]],
    lineage: Mapping[str, Sequence[tuple[str, str]]],
) -> tuple[str, ...]:
    """The closure dimensions that actually hold a component together.

    Recorded per group so a lower-priority target reported ``UNMET`` can name
    both the group that blocks it and the priority that protects the group.
    """
    if len(members) < 2:
        return ()
    inside = set(members)
    bound: list[str] = []
    for dimension in CLOSURE_DIMENSIONS:
        counts: dict[str, int] = {}
        for member in members:
            value = values[member].get(dimension)
            if value:
                counts[value] = counts.get(value, 0) + 1
        shared = any(count > 1 for count in counts.values())
        pointed = any(
            pointer == dimension and target in inside
            for member in members
            for pointer, target in lineage.get(member, ())
        )
        if shared or pointed:
            bound.append(dimension)
    return tuple(bound)


def _blocking_priority(group: Mapping[str, Any]) -> dict[str, Any] | None:
    """How a group identifies itself when it blocks a lower-priority target."""
    priority = group.get("closure_priority")
    if priority is None:
        return None
    dimension = next(d for d in group["closure_dimensions"] if PRIORITY[d] == priority)
    return {"dimension": dimension, "priority": priority, "group_key": group["group_key"]}


def _highest(blocking: Sequence[Mapping[str, Any]]) -> str:
    """``<priority> (<tier>)`` for the strongest entry in a ``blocked_by`` list.

    A report that names only a number leaves the reader to look up what the
    number protects, and the tier name is the part that says why the group holds.
    """
    strongest = min(blocking, key=lambda b: b["priority"])
    return f"{strongest['priority']} ({TIER[strongest['dimension']]})"


def _placement_blocks(
    groups: Sequence[Mapping[str, Any]],
    values: Mapping[str, Mapping[str, str]],
    partitions: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Co-place groups so every declared constraint value lands in one partition.

    A constraint never divides a group — that is the whole priority order — so
    the only way to satisfy one is to place the groups that share a value
    together. Constraints are applied in ascending priority, so a lower-priority
    target can never displace a higher-priority one, and a constraint that
    cannot be satisfied is refused whole rather than partially applied.

    "Cannot be satisfied" is decided on one criterion: co-placement must leave
    at least as many placement blocks as there are partitions with a nonzero
    ``target_fraction``. Below that the split has collapsed into fewer sides
    than the policy declared, which is worse than an unmet target honestly
    reported.

    Returns ``(block key of each group key, decisions)``.
    """
    declared = {
        d
        for partition in partitions
        for d in partition.get("disjoint_on", ())
        if d in CONSTRAINT_DIMENSIONS
    }
    viable = sum(1 for partition in partitions if float(partition["target_fraction"]) > 0)
    parent = {group["group_key"]: group["group_key"] for group in groups}
    decisions: list[dict[str, Any]] = []

    for dimension in CONSTRAINT_DIMENSIONS:
        if dimension not in declared:
            continue
        by_value: dict[str, list[str]] = {}
        spanning: list[dict[str, Any]] = []
        for group in groups:
            carried = sorted(
                {
                    values[example_id][dimension]
                    for example_id in group["example_ids"]
                    if dimension in values[example_id]
                }
            )
            for value in carried:
                by_value.setdefault(value, []).append(group["group_key"])
            if len(carried) > 1:
                blocking = _blocking_priority(group)
                if blocking:
                    spanning.append(blocking)

        trial = dict(parent)
        for members in by_value.values():
            _merge(trial, members)
        blocks = len(_sets(trial))
        if blocks >= viable:
            parent = trial
            decisions.append(
                {
                    "dimension": dimension,
                    "priority": PRIORITY[dimension],
                    "status": "ENFORCED",
                    "detail": f"every value of this dimension is co-placed, leaving {blocks} "
                    f"placement block(s) for {viable} partition(s)",
                }
            )
            continue
        detail = (
            f"confining every value of this dimension to one partition leaves {blocks} placement "
            f"block(s) for {viable} partition(s) with a nonzero target_fraction, so the split "
            "would collapse; the constraint is not enforced"
        )
        if spanning:
            detail += (
                f", and {len(spanning)} group(s) formed at priority "
                f"{_highest(spanning)} span more than one value of it and MUST "
                "NOT be broken to satisfy it"
            )
        decisions.append(
            {
                "dimension": dimension,
                "priority": PRIORITY[dimension],
                "status": "UNMET",
                "detail": detail,
                "blocked_by": sorted(spanning, key=lambda b: (b["priority"], b["group_key"])),
            }
        )

    block_of = {key: min(members) for members in _sets(parent).values() for key in members}
    return block_of, decisions


def _leakage_checks(
    groups: Sequence[Mapping[str, Any]],
    values: Mapping[str, Mapping[str, str]],
    partitions: Sequence[Mapping[str, Any]],
    decisions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """One check per dimension, evaluated against what the partitions require.

    A closure dimension is checked whatever a partition declares: a value of one
    spanning two partitions means the closure itself was broken. A constraint
    dimension no partition declares in ``disjoint_on`` is ``NOT_APPLICABLE``
    with the reason stated — never ``PASS``, which would claim a guarantee
    nobody asked for and nobody verified. A dimension some assigned example does
    not carry is ``UNAVAILABLE`` even when the examples that do carry it are
    confined, because the check could not be completed over the corpus.

    A declared constraint the placement had to refuse reports ``UNMET``, naming
    the higher-priority groups that made it unsatisfiable, rather than ``FAIL``:
    nothing leaked, a target was not met.
    """
    declared: set[str] = set(ALWAYS_CHECKED)
    for partition in partitions:
        declared.update(partition.get("disjoint_on", ()))
    refused = {d["dimension"]: d for d in decisions if d["status"] == "UNMET"}

    partition_of = {
        example_id: group["partition"]
        for group in groups
        for example_id in group["example_ids"]
    }
    assigned = [example_id for example_id in sorted(values) if example_id in partition_of]

    checks: list[dict[str, Any]] = []
    for dimension in DIMENSIONS:
        seen: dict[str, set[str]] = {}
        without = 0
        for example_id in assigned:
            value = values[example_id].get(dimension)
            if value:
                seen.setdefault(value, set()).add(partition_of[example_id])
            else:
                without += 1
        base = {
            "dimension": dimension,
            "kind": "closure" if dimension in CLOSURE_DIMENSIONS else "disjointness",
            "priority": PRIORITY[dimension],
        }
        if not seen:
            checks.append(
                {
                    **base,
                    "status": "UNAVAILABLE",
                    "detail": "no assigned example carries this dimension, so disjointness "
                    "cannot be established either way",
                }
            )
            continue
        if dimension not in declared:
            checks.append(
                {
                    **base,
                    "status": "NOT_APPLICABLE",
                    "detail": "no partition declares this dimension in disjoint_on, so the "
                    "split makes no disjointness claim about it",
                }
            )
            continue
        if without:
            checks.append(
                {
                    **base,
                    "status": "UNAVAILABLE",
                    "detail": f"{without} of {len(assigned)} assigned example(s) carry no value "
                    "for this dimension, so the check could not be completed over the corpus",
                }
            )
            continue
        offending = sorted(v for v, parts in seen.items() if len(parts) > 1)
        decision = refused.get(dimension)
        check: dict[str, Any]
        if offending and decision:
            check = {
                **base,
                "status": "UNMET",
                "detail": decision["detail"],
                "offending_groups": offending,
            }
            if decision.get("blocked_by"):
                check["blocked_by"] = list(decision["blocked_by"])
        elif offending:
            check = {
                **base,
                "status": "FAIL",
                "detail": f"{len(offending)} value(s) of this dimension appear in more than one "
                "partition",
                "offending_groups": offending,
            }
        elif decision:
            check = {
                **base,
                "status": "PASS",
                "detail": f"each of the {len(seen)} value(s) of this dimension is confined to one "
                f"partition, although co-placement was refused as unsatisfiable: "
                f"{decision['detail']}",
            }
        else:
            check = {
                **base,
                "status": "PASS",
                "detail": f"each of the {len(seen)} value(s) of this dimension is confined to one "
                "partition",
            }
        checks.append(check)
    return checks


def _balance_checks(
    groups: Sequence[Mapping[str, Any]],
    values: Mapping[str, Mapping[str, str]],
    partitions: Sequence[Mapping[str, Any]],
    balance_on: Sequence[str],
    tolerance: float,
) -> list[dict[str, Any]]:
    """One check per declared balance target.

    A balance target asks that every value of a dimension appear in each
    partition in proportion to that partition's ``target_fraction``. It is the
    lowest-priority thing this generator knows about, and the generator never
    moves a group to reach it: moving a group to improve a distribution is
    exactly the pressure that breaks the closure groups above it. So the target
    is measured, and when a group's own size makes it unreachable the check is
    ``UNMET`` with that group named.

    A dimension not named in ``policy.balance_on`` produces no entry at all. An
    undeclared target is not a target, and reporting one either way would invent
    a claim.
    """
    if not balance_on:
        return []
    partition_of = {
        example_id: group["partition"]
        for group in groups
        for example_id in group["example_ids"]
    }
    fractions = {str(p["name"]): float(p["target_fraction"]) for p in partitions}
    assigned = [example_id for example_id in sorted(values) if example_id in partition_of]

    checks: list[dict[str, Any]] = []
    for dimension in balance_on:
        base = {"dimension": dimension, "kind": "balance", "priority": PRIORITY[dimension]}
        population: dict[str, list[str]] = {}
        without = 0
        for example_id in assigned:
            value = values[example_id].get(dimension)
            if value:
                population.setdefault(value, []).append(example_id)
            else:
                without += 1
        if not population:
            checks.append(
                {
                    **base,
                    "status": "UNAVAILABLE",
                    "detail": "no assigned example carries this dimension, so its distribution "
                    "across the partitions cannot be measured",
                }
            )
            continue
        if without:
            checks.append(
                {
                    **base,
                    "status": "UNAVAILABLE",
                    "detail": f"{without} of {len(assigned)} assigned example(s) carry no value "
                    "for this dimension, so a distribution over them would be measured against "
                    "an incomplete population",
                }
            )
            continue

        misses: list[tuple[float, str, str, float, float]] = []
        worst: tuple[float, str, str, float, float] | None = None
        blocked: dict[str, dict[str, Any]] = {}
        for value, example_ids in sorted(population.items()):
            total = len(example_ids)
            held = set(example_ids)
            for name, target in fractions.items():
                observed = sum(1 for i in example_ids if partition_of[i] == name) / total
                deviation = abs(observed - target)
                entry = (deviation, value, name, observed, target)
                if worst is None or deviation > worst[0]:
                    worst = entry
                if deviation > tolerance:
                    misses.append(entry)
            # A group holding more of this value than its own partition's target
            # admits cannot be placed anywhere that satisfies the target, and it
            # is atomic, so the target is unreachable without breaking it.
            for group in groups:
                share = sum(1 for i in group["example_ids"] if i in held) / total
                if share <= fractions.get(group["partition"], 0.0) + tolerance:
                    continue
                blocking = _blocking_priority(group)
                if blocking:
                    blocked[blocking["group_key"]] = blocking

        # population is non-empty and a policy declares at least one partition,
        # so the loop above always ran.
        assert worst is not None
        shape = (
            f"worst deviation is {worst[0]:.4f}: value {worst[1]!r} holds {worst[3]:.4f} of its "
            f"{len(population[worst[1]])} example(s) in partition {worst[2]!r} against a target "
            f"of {worst[4]:.4f}"
        )
        if not misses:
            checks.append(
                {
                    **base,
                    "status": "PASS",
                    "detail": f"every value of this dimension sits within {tolerance:.4f} of each "
                    f"partition's target_fraction; {shape}",
                }
            )
            continue
        if blocked:
            ordered = sorted(blocked.values(), key=lambda b: (b["priority"], b["group_key"]))
            checks.append(
                {
                    **base,
                    "status": "UNMET",
                    "detail": f"{len(misses)} (value, partition) pair(s) deviate from "
                    f"target_fraction by more than {tolerance:.4f}; {shape}. "
                    f"{len(ordered)} group(s) formed at priority "
                    f"{_highest(ordered)} hold more of a value than any "
                    "partition's target admits and MUST NOT be broken to improve the "
                    "distribution, so this target is not reachable for this corpus",
                    "blocked_by": ordered,
                }
            )
            continue
        checks.append(
            {
                **base,
                "status": "FAIL",
                "detail": f"{len(misses)} (value, partition) pair(s) deviate from target_fraction "
                f"by more than {tolerance:.4f}; {shape}. No group's integrity accounts for the "
                "deviation, so it is a property of the placement rather than of the closure",
            }
        )
    return checks


def generate_split(
    ctx: Any,
    examples: Sequence[Mapping[str, Any]],
    split_policy: Mapping[str, Any],
    *,
    artifacts: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Generate a content-addressed ``CorpusSplitV1``.

    ``split_policy`` carries ``policy_id``, ``seed``, and ``partitions``, may
    carry ``balance_on`` and ``balance_tolerance``, and may carry
    ``grouping_dimensions``; the schema's ``policy`` object accepts the first
    five, so ``grouping_dimensions`` is recorded at the top level of the split
    record where the schema declares it.

    ``artifacts`` are the ``SourceArtifactV1`` records the examples were mined
    from. They are optional because a hand-authored corpus has none, but without
    them ``content_hash`` and ``normalized_content_hash`` are unavailable for
    every example that does not carry them as extensions — and those are the two
    dimensions that catch a document byte-identical across two repositories.
    They are part of ``corpus_sha256`` because they change the outcome.

    Raises :class:`~ats.errors.UsageError` when the policy declares no grouping
    dimensions at all: that request is a random split, which spec Section 17.7
    declares nonconforming.
    """
    keys = ("policy_id", "seed", "partitions", "balance_on", "balance_tolerance")
    policy = {k: split_policy[k] for k in keys if k in split_policy}
    missing = {"policy_id", "seed", "partitions"} - set(policy)
    if missing:
        raise UsageError(f"split policy is missing {sorted(missing)}")
    partitions = list(policy["partitions"])
    if not partitions:
        raise UsageError("a split policy must declare at least one partition")

    # An absent key takes the default; an explicitly empty list is a request for
    # a random split, which is a different thing and is refused below.
    declared = split_policy.get("grouping_dimensions")
    grouping = tuple(DEFAULT_GROUPING_DIMENSIONS if declared is None else declared)
    if not grouping:
        raise UsageError(
            "a split policy with no grouping dimensions is a random sentence split, which is "
            "nonconforming for semantic-detector evaluation (spec 17.7)"
        )
    unknown = [d for d in grouping if d not in DIMENSIONS]
    if unknown:
        raise UsageError(f"unknown grouping dimensions: {unknown}")

    balance_on = tuple(policy.get("balance_on") or ())
    unknown = [d for d in balance_on if d not in DIMENSIONS]
    if unknown:
        raise UsageError(f"unknown balance dimensions: {unknown}")
    tolerance = float(policy.get("balance_tolerance", BALANCE_TOLERANCE))
    if not 0.0 <= tolerance <= 1.0:
        raise UsageError(f"balance_tolerance must be a fraction in [0, 1]; got {tolerance}")

    if not examples:
        raise UsageError("a split needs at least one example")

    index = {a["artifact_id"]: a for a in artifacts if a.get("artifact_id")}
    values: dict[str, dict[str, str]] = {}
    lineage: dict[str, tuple[tuple[str, str], ...]] = {}
    unassignable: list[dict[str, Any]] = []
    for example in examples:
        example_id = example["example_id"]
        dims = dimension_values(example, artifact=index.get(example.get("source_artifact") or ""))
        absent = [d for d in grouping if d not in dims]
        if absent:
            unassignable.append({"example_id": example_id, "missing_dimensions": absent})
            continue
        values[example_id] = dims
        lineage[example_id] = lineage_targets(example)

    if not values:
        raise UsageError(
            f"no example carries every required grouping dimension {list(grouping)}; assigning "
            "them anyway would be the random sentence split spec 17.7 forbids"
        )

    roots = _components(values, CLOSURE_DIMENSIONS, lineage)
    members: dict[str, list[str]] = {}
    for example_id, root in roots.items():
        members.setdefault(root, []).append(example_id)

    groups: list[dict[str, Any]] = []
    for root in sorted(members):
        example_ids = sorted(members[root])
        component: dict[str, set[str]] = {}
        for example_id in example_ids:
            for dimension, value in values[example_id].items():
                component.setdefault(dimension, set()).add(value)
        bound = _binding_dimensions(example_ids, values, lineage)
        group: dict[str, Any] = {
            "group_key": canonical_group_key(component),
            "partition": "",
            "example_ids": example_ids,
            "dimension_values": {
                dimension: ",".join(sorted(component[dimension]))
                for dimension in DIMENSIONS
                if dimension in component
            },
            "closure_dimensions": list(bound),
        }
        if bound:
            group["closure_priority"] = min(PRIORITY[d] for d in bound)
        groups.append(group)

    block_of, decisions = _placement_blocks(groups, values, partitions)
    seed = str(policy["seed"])
    assignments: dict[str, str] = {}
    for group in groups:
        block = block_of[group["group_key"]]
        group["partition"] = assign(seed, block, partitions)
        if block != group["group_key"]:
            group["placement_block"] = block
        for example_id in group["example_ids"]:
            assignments[example_id] = group["partition"]

    recorded_policy: dict[str, Any] = {
        "policy_id": str(policy["policy_id"]),
        "seed": seed,
        "partitions": [dict(p) for p in partitions],
    }
    if balance_on:
        recorded_policy["balance_on"] = list(balance_on)
        recorded_policy["balance_tolerance"] = tolerance

    split = rec.address(
        {
            "schema_version": "ats.corpus_split.v1",
            "policy": recorded_policy,
            "generated_at": ctx.timestamp(),
            "corpus_sha256": content_hash(
                {
                    "examples": [dict(e) for e in examples],
                    "artifacts": [dict(a) for a in artifacts],
                },
                exclude=set(),
            ),
            "grouping_dimensions": list(grouping),
            "groups": groups,
            "assignments": assignments,
            "leakage_checks": _leakage_checks(groups, values, partitions, decisions)
            + _balance_checks(groups, values, partitions, balance_on, tolerance),
            **({"unassignable": unassignable} if unassignable else {}),
        }
    )
    ctx.schemas.validate_document(split)
    return split


def pair_is_grouped(split: Mapping[str, Any], source_id: str, mutant_id: str) -> bool:
    """Whether a source example and one of its mutations share a partition."""
    assignments = split["assignments"]
    if source_id not in assignments or mutant_id not in assignments:
        return False
    return assignments[source_id] == assignments[mutant_id]

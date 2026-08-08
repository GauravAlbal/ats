"""Deterministic planning projection from a validated TextIR document.

Obligation (delta D-H): produce the ``AtsPlanningProjectionV1`` surface — a
pure function of ``(validated IR, resolved policy, artifact_sha256)`` — that
preserves the artifact's stable semantic coordinates, carries an IR JSON
Pointer on every projected unit, binds the artifact and policy hashes, and is
validated against the projection schema and sealed by content hash before it
is returned.

Fail-closed rules:

- An IR that fails the ``ats_text_ir_v1`` schema is refused
  (:class:`~ats.errors.SchemaValidationError`), exactly as ``ats ir lint``
  refuses it — never partially projected.
- A policy snapshot that is not current (hash mismatch or wrong spec version)
  is refused (:class:`~ats.errors.StalePolicyError`), matching Section 14.3.
- An IR whose declared ``policy_snapshot_id`` differs from the bound policy
  snapshot is refused (:class:`~ats.errors.UsageError`) — projecting an
  artifact under a different policy than it was authored against would
  mislabel the projection.
- The projection never invents a value. A missing IR value stays missing; a
  unit whose required projection field has no IR source (e.g. an acceptance
  criterion with no stated text, an update indicator with no declared
  effect) is omitted rather than fabricated.

Derivation rules implemented here (documented in docs/PLANNING_PROJECTION.md):

- ``proof_obligations``: every pair ``(requirement R, claim C)`` where ``C``
  has role ``observation`` or ``judgment`` and ``C.claim_id`` appears in
  ``R``'s ``source_refs``. Deterministic id: ``obligation_id =
  R.requirement_id + ':' + C.claim_id``.
- ``dependencies``: every relation whose type is one of
  ``depends_on`` / ``condition_for`` / ``necessary_for`` / ``sufficient_for``
  with both endpoints resolvable to requirement claims. The relation's
  ``dependency_target`` ref, when declared, selects the target requirement;
  otherwise the relation ``target_id`` is resolved. ``kind`` preserves the
  relation type verbatim.
- ``non_goals``: claims with role ``boundary`` and polarity ``negative`` —
  explicit exclusion declarations ("does not apply to X"). ``boundaries``:
  role ``boundary`` with polarity ``positive``. ``exceptions``: role
  ``exception``.
- ``acceptance_criteria``: the union of every ``acceptance_criterion_id``
  referenced by a requirement slot. The criterion text is the proposition of
  the claim whose ``claim_id`` equals the criterion id (the defining claim);
  falling back to the first slot's free-text ``acceptance_criterion`` when no
  claim defines it. ``requirement_ids`` back-references every requirement
  slot that cites the criterion, in document order.
- ``update_indicators``: one record per IR update indicator; ``claim_id`` is
  its first target claim ref, ``kind`` is its declared ``effect``.
- ``authority``: one record per distinct ``source_authority`` declared by a
  requirement slot, in first-seen document order; ``source_id`` is the
  ``requirement_id`` of the first slot declaring it. ``precedence`` is never
  emitted — the IR declares no precedence, and inventing an authority
  hierarchy is the silent-promotion failure ATS-BASIS-002 blocks.
- ``profile``: the union of the IR's section profiles, sorted, joined by
  ``'+'`` (e.g. ``SPECIFY+TRANSFORM``).
"""

from __future__ import annotations

from typing import Any, Mapping

from ..canonical import seal
from ..context import Context
from ..errors import UsageError
from ..ir.model import IrDocument
from ..ir.validate import require_valid_ir

PROJECTION_SCHEMA_ID = "ats_planning_projection_v1.schema.json"
PROJECTION_SCHEMA_VERSION = "ats.planning_projection.v1"

#: Relation types that express a requirement-level dependency (spec Section
#: 7.x relations plus the D-B protected acceptance/ordering relations).
DEPENDENCY_KINDS: tuple[str, ...] = (
    "depends_on",
    "condition_for",
    "necessary_for",
    "sufficient_for",
)

#: Claim roles that carry a verification/evidence obligation when a
#: requirement references them.
PROOF_ROLES: tuple[str, ...] = ("observation", "judgment")


def project_from_ir(
    ctx: Context,
    ir_document: Mapping[str, Any],
    policy_document: Mapping[str, Any],
    *,
    artifact_sha256: str,
) -> dict[str, Any]:
    """Project one validated TextIR document into sealed planning input.

    The projection is deterministic: it is a pure function of the validated IR,
    the resolved policy snapshot, and the caller-supplied artifact hash. It
    validates the IR with the same machinery ``ats ir lint`` uses, binds the
    policy snapshot's currentness, builds the projection material, validates
    it against the projection schema, and seals it (``projection_id`` is the
    content hash of everything else).
    """
    ir = require_valid_ir(ctx, ir_document)
    policy = ctx.policy(policy_document)
    if ir.policy_snapshot_id != policy.snapshot_id:
        raise UsageError(
            f"IR declares policy_snapshot_id {ir.policy_snapshot_id!r} but the bound "
            f"policy snapshot is {policy.snapshot_id!r}; an artifact projected under a "
            "different policy than it was authored against would mislabel the projection"
        )

    projection: dict[str, Any] = {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "artifact_id": ir.artifact_id,
        "artifact_sha256": artifact_sha256,
        "ir_sha256": ir.ir_sha256,
        "policy_snapshot_id": policy.snapshot_id,
        "policy_snapshot_sha256": policy.computed_sha256(),
        "spec_version": ctx.spec_version,
        "profile": _profile(ir, policy),
        "stable_coordinates": _stable_coordinates(ir),
        "requirements": _requirements(ir),
        "decisions": _decisions(ir),
        "acceptance_criteria": _acceptance_criteria(ir),
        "proof_obligations": _proof_obligations(ir),
        "dependencies": _dependencies(ir),
        "non_goals": _non_goals(ir),
        "boundaries": _boundaries(ir),
        "exceptions": _exceptions(ir),
        "update_indicators": _update_indicators(ir),
        "authority": _authority(ir),
    }
    sealed = seal(projection)
    ctx.schemas.validate(sealed, PROJECTION_SCHEMA_ID)
    return sealed


def _profile(ir: IrDocument, policy: Any) -> str:
    """The projection's profile: union of section profiles, sorted, joined by '+'.

    Falls back to the policy's declared profiles when the IR declares none
    (mirrors ``lint_ir``'s ``ir.profiles or policy.profiles``).
    """
    profiles = ir.profiles or policy.profiles
    return "+".join(sorted(set(profiles)))


def _stable_coordinates(ir: IrDocument) -> list[dict[str, Any]]:
    """Copy the document-level ``stable_coordinates`` block verbatim."""
    return [dict(entry) for entry in ir.raw.get("stable_coordinates", ())]


def _requirements(ir: IrDocument) -> list[dict[str, Any]]:
    """Project every requirement slot, in document order, with its IR pointer."""
    out: list[dict[str, Any]] = []
    for claim in ir.all_claims():
        slot = claim.requirement
        if slot is None:
            continue
        entry: dict[str, Any] = {
            "requirement_id": slot["requirement_id"],
            "actor": slot["actor"],
            "deontic": slot["deontic"],
            "action": slot["action"],
            "object": slot["object"],
            "source_pointer": claim.pointer,
            "authority": slot["source_authority"],
        }
        for name in ("scope", "trigger", "condition", "acceptance_criterion_id"):
            value = slot.get(name)
            if value is not None:
                entry[name] = value
        out.append(entry)
    return out


def _decisions(ir: IrDocument) -> list[dict[str, Any]]:
    """Project every claim carrying a ``decision_id`` (draft.2), in document order."""
    out: list[dict[str, Any]] = []
    for claim in ir.all_claims():
        decision_id = claim.data.get("decision_id")
        if decision_id is None:
            continue
        out.append(
            {
                "decision_id": decision_id,
                "proposition": claim.proposition,
                "status": claim.status,
                "source_pointer": claim.pointer,
            }
        )
    return out


def _acceptance_criteria(ir: IrDocument) -> list[dict[str, Any]]:
    """Project every referenced acceptance criterion with its defining text.

    The criterion text is the proposition of the claim whose ``claim_id``
    equals the criterion id; when no claim defines it, the first requirement
    slot's free-text ``acceptance_criterion`` is used. A criterion with no
    stated text anywhere is omitted (the projection never invents one).
    """
    refs: dict[str, list[str]] = {}
    free_text: dict[str, str] = {}
    for claim in ir.all_claims():
        slot = claim.requirement
        if slot is None:
            continue
        ac_id = slot.get("acceptance_criterion_id")
        if ac_id is None:
            continue
        refs.setdefault(ac_id, []).append(slot["requirement_id"])
        if ac_id not in free_text and slot.get("acceptance_criterion"):
            free_text[ac_id] = slot["acceptance_criterion"]

    out: list[dict[str, Any]] = []
    for ac_id, requirement_ids in refs.items():
        defining = ir.claims.get(ac_id)
        criterion = defining.proposition if defining is not None else free_text.get(ac_id)
        if criterion is None:
            continue
        out.append(
            {
                "acceptance_criterion_id": ac_id,
                "criterion": criterion,
                "requirement_ids": list(dict.fromkeys(requirement_ids)),
            }
        )
    return out


def _proof_obligations(ir: IrDocument) -> list[dict[str, Any]]:
    """Project every (requirement, observation/judgment) grounding pair.

    A requirement's ``source_refs`` name the claims its obligation rests on;
    when such a claim has role ``observation`` or ``judgment`` the pair is a
    proof obligation. ``obligation_id`` is the documented deterministic rule
    ``requirement_id + ':' + claim_id``.
    """
    out: list[dict[str, Any]] = []
    for claim in ir.all_claims():
        if claim.role != "requirement":
            continue
        requirement_id = claim.requirement["requirement_id"]
        for ref in claim.refs("source_refs"):
            grounded = ir.claims.get(ref)
            if grounded is None or grounded.role not in PROOF_ROLES:
                continue
            out.append(
                {
                    "obligation_id": f"{requirement_id}:{grounded.claim_id}",
                    "claim_id": grounded.claim_id,
                    "requirement_id": requirement_id,
                }
            )
    return out


def _dependencies(ir: IrDocument) -> list[dict[str, Any]]:
    """Project requirement-level dependency relations.

    Only relations whose type expresses a dependency AND whose endpoints
    resolve to requirement claims are projected (both projection fields are
    requirement ids). The relation's declared ``dependency_target``, when
    present, selects the target requirement; otherwise the relation's
    ``target_id`` is resolved through the claims index.
    """
    out: list[dict[str, Any]] = []
    for relation in ir.relations.values():
        if relation.type not in DEPENDENCY_KINDS:
            continue
        source = ir.claims.get(relation.source_id)
        if source is None or source.role != "requirement":
            continue
        target_id = relation.data.get("dependency_target") or relation.target_id
        target = ir.claims.get(target_id)
        if target is None or target.role != "requirement":
            continue
        out.append(
            {
                "from_requirement_id": source.requirement["requirement_id"],
                "to_requirement_id": target.requirement["requirement_id"],
                "kind": relation.type,
            }
        )
    return out


def _non_goals(ir: IrDocument) -> list[dict[str, Any]]:
    """Explicit exclusion declarations: boundary claims with negative polarity."""
    out: list[dict[str, Any]] = []
    for claim in ir.all_claims():
        if claim.role == "boundary" and claim.polarity == "negative":
            out.append({"statement": claim.proposition, "source_pointer": claim.pointer})
    return out


def _boundaries(ir: IrDocument) -> list[dict[str, Any]]:
    """Scope limits: boundary claims with positive polarity."""
    out: list[dict[str, Any]] = []
    for claim in ir.all_claims():
        if claim.role == "boundary" and claim.polarity == "positive":
            out.append({"statement": claim.proposition, "source_pointer": claim.pointer})
    return out


def _exceptions(ir: IrDocument) -> list[dict[str, Any]]:
    """Exception claims, verbatim with their IR pointers."""
    out: list[dict[str, Any]] = []
    for claim in ir.all_claims():
        if claim.role == "exception":
            out.append({"statement": claim.proposition, "source_pointer": claim.pointer})
    return out


def _update_indicators(ir: IrDocument) -> list[dict[str, Any]]:
    """Project update/reversal indicators.

    ``claim_id`` is the indicator's first target claim ref; ``kind`` is its
    declared ``effect``. An indicator without a declared effect is omitted —
    the projection cannot invent the kind the schema requires. ``status`` is
    carried only when the IR declares it.
    """
    out: list[dict[str, Any]] = []
    for section in ir.sections:
        for indicator in section.update_indicators:
            effect = indicator.effect
            if effect is None:
                continue
            entry: dict[str, Any] = {
                "indicator_id": indicator.indicator_id,
                "claim_id": indicator.target_claim_refs[0],
                "kind": effect,
                "source_pointer": indicator.pointer,
            }
            status = indicator.data.get("status")
            if status is not None:
                entry["status"] = status
            out.append(entry)
    return out


def _authority(ir: IrDocument) -> list[dict[str, Any]]:
    """Distinct ``source_authority`` declarations, first-seen document order.

    ``source_id`` is the ``requirement_id`` of the first requirement slot that
    declares the authority (the machine-stable coordinate binding it to the
    document). ``precedence`` is never emitted: the IR declares none, and
    inventing an authority hierarchy is a silent semantic strengthening.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for claim in ir.all_claims():
        slot = claim.requirement
        if slot is None:
            continue
        authority = slot["source_authority"]
        if authority in seen:
            continue
        seen.add(authority)
        out.append({"source_id": slot["requirement_id"], "authority": authority})
    return out

"""Operator adjudication and the gold records it authors.

The queue and record builders operate on caller-supplied annotation material.
They refuse a third model vote as authority: a human adjudicator must own the
normative decision, while the record retains the independent judgments and
their disagreement.

Three disciplines are enforced structurally rather than by convention:

**Two passes, in order.** The operator first judges from the source alone --
rule, profile, context bundle, candidate basis -- with both annotator judgments,
their rationales, and any revision-derived material withheld. Only after that
source-only judgment is recorded may the disagreement be shown. A changed
decision after seeing the arguments is evidence about the arguments, so both
passes are preserved and neither overwrites the other.

**Disposition and diagnosis are separate fields.** What the text is
(``source_disposition``) and why the instruments diverged on it
(``system_diagnosis``) answer different questions, and collapsing them turns
every disagreement into a rule defect or every operator decision into proof the
rule was adequate. The record also asks the question that keeps "the
adjudicator picked X" from standing in for "the standard is clear": could a
competent reader applying the published text reasonably reach the rejected
interpretation?

**Agreement is audited, not trusted.** The queue carries a control sample of
apparent agreements, because two LLM passes agreeing is not evidence that
either interpreted the rule correctly -- they can be wrong together in the same
way, and no agreement statistic detects that.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

from ..canonical import content_hash, seal
from ..errors import UsageError

SCHEMA_VERSION_QUEUE: Final[str] = "ats.adjudication_queue.v1"
SCHEMA_VERSION_RECORD: Final[str] = "ats.operator_adjudication.v1"
QUEUE_ID_PREFIX: Final[str] = "ats-adjqueue-sha256"
UNIT_ID_PREFIX: Final[str] = "ats-adjunit-sha256"

#: What the source text is, decided by the operator. ``ambiguous_by_design`` is
#: a statement about the prose, not about the instrument; ``excluded`` removes
#: the unit from gold with a reason rather than by deletion.
SOURCE_DISPOSITIONS: Final[tuple[str, ...]] = (
    "conforming",
    "violation",
    "near_miss",
    "hard_negative",
    "exception",
    "ambiguous_by_design",
    "insufficient_context",
    "excluded",
)

#: Profile-reconnaissance units are classified, not conformance-labelled. The
#: vocabulary is the reconnaissance study's own, so operator gold and the two
#: instrument passes answer the same question.
PROFILE_DISPOSITIONS: Final[tuple[str, ...]] = (
    "SPECIFY",
    "ASSESS",
    "mixed",
    "reserved_profile",
    "not_applicable",
    "insufficient_context",
)

#: Why the independent judgments diverged. More than one may apply; exactly one
#: must be marked primary. ``no_system_defect`` exists so ordinary annotator
#: error is a recordable outcome rather than a silence.
SYSTEM_DIAGNOSES: Final[tuple[str, ...]] = (
    "annotator_error",
    "annotation_guide_defect",
    "context_bundle_defect",
    "candidate_mining_defect",
    "profile_boundary_defect",
    "rule_wording_defect",
    "rule_boundary_defect",
    "schema_defect",
    "multiple_valid_interpretations",
    "source_ambiguity",
    "no_system_defect",
)

#: Does ATS-1 draft.1 determine one result from the available context?
DETERMINACY: Final[tuple[str, ...]] = (
    "yes",
    "no_multiple_permitted_readings",
    "no_missing_context",
    "no_missing_policy_input",
)

#: The minimum missing object behind an ``insufficient_context`` adjudication.
#: A taxonomy rather than free text, so a downstream context builder can learn
#: what to fetch -- and what it should refuse as a typed unavailable rather
#: than solve by shipping whole documents.
MISSING_CONTEXT_OBJECTS: Final[tuple[str, ...]] = (
    "preceding_sentence",
    "following_sentence",
    "full_paragraph",
    "enclosing_list",
    "heading_path",
    "definition",
    "referenced_section",
    "table_or_schema",
    "source_attribution",
    "policy_snapshot",
    "repository_convention",
    "revision_context",
    "external_artifact",
)

#: Whether each missing-context object can be fetched mechanically by the
#: context builder: a demonstrated need for a deterministically collectable
#: object is a builder change, a demonstrated need for anything else is a
#: typed unavailable. Shipping whole documents to every annotator is not a
#: substitute for naming the missing object.
#: Three values distinguish deterministic retrieval from conditional retrieval
#: and from objects that require human or external-system escalation:
#:
#: ``deterministic``
#:     A pure function of the repository at the pinned revision.
#: ``conditional``
#:     Deterministic when the source declares it; its absence is a typed
#:     unavailable, never a search.
#: ``not_deterministic``
#:     No artifact exists to fetch; only an escalation to a human or an
#:     external system could supply it.
MISSING_CONTEXT_COLLECTABILITY: Final[dict[str, dict[str, str]]] = {
    "preceding_sentence": {
        "collectability": "deterministic",
        "note": "text adjacency within the same document",
    },
    "following_sentence": {
        "collectability": "deterministic",
        "note": "text adjacency within the same document",
    },
    "full_paragraph": {
        "collectability": "deterministic",
        "note": "block structure the parser already computes",
    },
    "enclosing_list": {
        "collectability": "deterministic",
        "note": "block structure the parser already computes",
    },
    "heading_path": {
        "collectability": "deterministic",
        "note": "already carried by every bundle; a need here is a builder bug",
    },
    "definition": {
        "collectability": "conditional",
        "note": (
            "deterministic for in-document definitions and glossary entries, which "
            "the miner already collects; a repository-wide definition search is "
            "retrieval and is out of scope for a deterministic builder"
        ),
    },
    "referenced_section": {
        "collectability": "conditional",
        "note": (
            "deterministic when the reference is an explicit link or anchor; prose "
            "references ('as discussed elsewhere') name nothing fetchable"
        ),
    },
    "table_or_schema": {
        "collectability": "conditional",
        "note": "deterministic when adjacent or explicitly referenced by path",
    },
    "source_attribution": {
        "collectability": "conditional",
        "note": (
            "deterministic when front matter or a trailer declares it; absence is "
            "the common case and stays a typed unavailable"
        ),
    },
    "policy_snapshot": {
        "collectability": "conditional",
        "note": (
            "deterministic when a snapshot is declared in scope; the bundle's "
            "policy_context field already carries the declared case"
        ),
    },
    "repository_convention": {
        "collectability": "not_deterministic",
        "note": "an unwritten convention has no artifact to fetch",
    },
    "revision_context": {
        "collectability": "deterministic",
        "note": "Git history at the pinned revision is mechanical",
    },
    "external_artifact": {
        "collectability": "not_deterministic",
        "note": "outside the repository; always a typed unavailable",
    },
}

#: Naturally occurring requirement forms, recorded on profile units so the
#: SPECIFY miss can be localised to the shapes the miner does not read. This
#: taxonomy is input to caller-directed mining changes; the profile is not to
#: be broadened to fit the miner.
REQUIREMENT_FORMS: Final[tuple[str, ...]] = (
    "canonical_modal_requirement",
    "declarative_invariant",
    "acceptance_criterion",
    "prohibition",
    "permission",
    "capability_boundary",
    "conditional_obligation",
    "table_encoded_requirement",
    "schema_encoded_constraint",
    "distributed_requirement_block",
)

#: The distinct questions ATS-NUM-002 currently collapses. Each NUM-002 unit
#: asks all six, so the adjudicated examples can reveal the actual boundary
#: before anyone amends the rule.
NUM002_QUESTIONS: Final[tuple[str, ...]] = (
    "boundary_required",
    "inclusivity_material",
    "boundary_recoverable_from_operator",
    "boundary_defined_elsewhere_in_scope",
    "text_is_requirement_observation_or_explanation",
    "uncertainty_creates_implementation_divergence",
)

#: Why a unit is in the queue. A unit may carry several; none is decorative.
SCOPE_REASONS: Final[tuple[str, ...]] = (
    "applicable_by_at_least_one_pass",
    "probe_applicability_disagreement",
    "specify_verdict_evidence",
    "context_sufficiency_disagreement",
    "cited_as_observation_evidence",
    "control_apparent_agreement",
)

#: Fields the source-only pass must never see. Annotator conclusions would let
#: the operator choose the more persuasive explanation instead of judging the
#: source; revision-derived material (the diff, the later edit, the review
#: comment) is subsequent history, and the milestone requires the source-only
#: decision to be recorded before any of it is shown.
WITHHELD_IN_SOURCE_ONLY: Final[tuple[str, ...]] = (
    "judgments",
    "recon_classifications",
    "diff",
    "later_edit",
    "review_comment",
)

#: The payload keys a pass-A surface may not carry, each named with the
#: contract entry it enforces. :data:`WITHHELD_IN_SOURCE_ONLY` is the
#: documented contract and is embedded in the sealed queue, so it names
#: concepts; this is the same contract in the keys the payload builders
#: actually emit. Profile conclusions live under ``classifications``, and the
#: selector's fired signals are withheld for the reason the conclusions are:
#: they are the argument for selecting the bundle, not the source.
_WITHHELD_PAYLOAD_KEYS: Final[Mapping[str, str]] = {
    "judgments": "judgments",
    "classifications": "recon_classifications",
    "diff": "diff",
    "later_edit": "later_edit",
    "review_comment": "review_comment",
    "signals_fired": "the selector's own selection argument",
}

STAGES: Final[tuple[str, ...]] = ("source_only", "disagreement_review")

_CONTROL_TARGET: Final[int] = 16


# --------------------------------------------------------------------------
# Queue selection
# --------------------------------------------------------------------------


def _unit_states(
    judgments: Mapping[str, Sequence[Mapping[str, Any]]],
    declines: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[tuple[str, str], dict[str, dict[str, Any]]]:
    """Per (bundle, rule) unit: what each pass did, with its full row."""
    units: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for role, rows in judgments.items():
        for row in rows:
            key = (str(row["example_id"]), str(row["rule_id"]))
            units.setdefault(key, {})[role] = {"kind": "judged", "row": dict(row)}
    for role, rows in declines.items():
        for row in rows:
            key = (str(row["example_id"]), str(row["rule_id"]))
            if role in units.get(key, {}):
                raise UsageError(
                    f"{role} both judged and declined {key}; the pass files are "
                    "inconsistent and neither answer can be preferred"
                )
            units.setdefault(key, {})[role] = {"kind": "declined", "row": dict(row)}
    return units


def _applicability_of(entry: Mapping[str, Any]) -> str:
    if entry["kind"] == "judged":
        return str(entry["row"]["extensions"]["x-ats-repo-applicability"])
    return str(entry["row"]["applicability"])


def select_scope(
    round_record: Mapping[str, Any],
    units: Mapping[tuple[str, str], Mapping[str, Mapping[str, Any]]],
    recon: Mapping[str, Any],
    *,
    seed: int,
    control_target: int = _CONTROL_TARGET,
) -> tuple[dict[tuple[str, str], list[str]], list[str], list[str]]:
    """Which units are adjudicated, and why each one is.

    Returns ``(conformance_scope, profile_disagreed, profile_controls)`` where
    the first maps (bundle_id, rule_id) to its scope reasons and the last two
    list recon bundle ids. Selection is deterministic in the seed and the
    committed artifacts; nothing here samples from anything mutable.
    """
    probe_units: set[tuple[str, str]] = set()
    for pick in round_record.get("selection", ()):
        if pick.get("stratum") == "zero_candidate_rule_probe":
            for rule_id in pick.get("rule_ids", ()):
                probe_units.add((str(pick["bundle_id"]), str(rule_id)))

    scope: dict[tuple[str, str], list[str]] = {}

    def add(key: tuple[str, str], reason: str) -> None:
        if reason not in SCOPE_REASONS:
            raise UsageError(f"unknown scope reason {reason!r}")
        scope.setdefault(key, [])
        if reason not in scope[key]:
            scope[key].append(reason)

    for key, by_role in units.items():
        kinds = {role: entry["kind"] for role, entry in by_role.items()}
        if "judged" in kinds.values():
            add(key, "applicable_by_at_least_one_pass")
        answers = {_applicability_of(entry) for entry in by_role.values()}
        if key in probe_units and len(answers) > 1:
            add(key, "probe_applicability_disagreement")
        if key in probe_units:
            # Every probe unit is cited by the zero-candidate disposition
            # ledger: the both-declined probes are the naturally_rare and
            # requires_unavailable_context evidence, which is exactly the
            # evidence a control-minded adjudication must not exempt.
            add(key, "cited_as_observation_evidence")
        if all(entry["kind"] == "judged" for entry in by_role.values()) and len(by_role) == 2:
            suff = {
                str(entry["row"]["extensions"]["x-ats-repo-context-sufficiency"])
                for entry in by_role.values()
            }
            if len(suff) > 1:
                add(key, "context_sufficiency_disagreement")

    # The control sample: apparent agreements not otherwise in scope. Both
    # populations of agreement are represented -- pairs that agreed on a label,
    # and pairs that agreed the rule did not apply -- because each can be wrong
    # together in its own way.
    rng = random.Random(seed)
    label_agreed = sorted(
        key
        for key, by_role in units.items()
        if len(by_role) == 2
        and all(entry["kind"] == "judged" for entry in by_role.values())
        and len({str(entry["row"]["label"]) for entry in by_role.values()}) == 1
    )
    for key in label_agreed:
        add(key, "control_apparent_agreement")
    declined_agreed = sorted(
        key
        for key, by_role in units.items()
        if key not in scope
        and len(by_role) == 2
        and all(entry["kind"] == "declined" for entry in by_role.values())
        and len({_applicability_of(entry) for entry in by_role.values()}) == 1
    )
    take = max(0, control_target - len(label_agreed))
    for key in rng.sample(declined_agreed, min(take, len(declined_agreed))):
        add(key, "control_apparent_agreement")

    # Profile units: every reconnaissance bundle the two passes disagreed on,
    # plus a seeded audit sample of the agreed-SPECIFY bundles the verdict
    # rests on. Agreement carrying a verdict is precisely the agreement that
    # needs auditing.
    by_bundle: dict[str, dict[str, str]] = {}
    for row in recon.get("classifications", ()):
        by_bundle.setdefault(str(row["bundle_id"]), {})[str(row["annotator_id"])] = str(
            row["classification"]
        )
    disagreed = sorted(
        bundle for bundle, votes in by_bundle.items() if len(set(votes.values())) > 1
    )
    agreed_specify = sorted(
        bundle
        for bundle, votes in by_bundle.items()
        if set(votes.values()) == {"SPECIFY"}
    )
    controls = sorted(rng.sample(agreed_specify, min(8, len(agreed_specify))))
    return scope, disagreed, controls


# --------------------------------------------------------------------------
# Queue building
# --------------------------------------------------------------------------


def _judgment_summary(entry: Mapping[str, Any]) -> dict[str, Any]:
    """What the committed queue says a pass did: kind and vocabulary, no prose."""
    if entry["kind"] == "judged":
        row = entry["row"]
        return {
            "kind": "judged",
            "label": row["label"],
            "applicability": row["extensions"]["x-ats-repo-applicability"],
            "context_sufficiency": row["extensions"]["x-ats-repo-context-sufficiency"],
            "annotation_confidence": row["annotation_confidence"],
        }
    return {"kind": "declined", "applicability": entry["row"]["applicability"]}


def build_queue(
    ctx: Any,
    *,
    round_record: Mapping[str, Any],
    units: Mapping[tuple[str, str], Mapping[str, Mapping[str, Any]]],
    recon: Mapping[str, Any],
    bundles: Mapping[str, Mapping[str, Any]],
    recon_bundles: Mapping[str, Mapping[str, Any]],
    frame: Mapping[str, Any],
    seed: int,
    control_target: int = _CONTROL_TARGET,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """The sealed queue record and its caller-controlled payloads.

    The committed record carries identities, scope reasons, and judgment
    summaries, plus a content hash of each payload. Verbatim source text,
    rationales, and evidence remain caller-controlled and are exported only
    when their authority permits it.
    """
    scope, recon_disagreed, recon_controls = select_scope(
        round_record, units, recon, seed=seed, control_target=control_target
    )
    selection_by_bundle = {
        str(row["bundle_id"]): row for row in round_record.get("selection", ())
    }
    authority_by_repo = {
        str(row["repository"]): row
        for row in frame.get("authority", {}).get("authorised_repositories", ())
    }
    rules = ctx.registry.raw_rules

    queue_units: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {}

    for (bundle_id, rule_id), reasons in sorted(scope.items()):
        pick = selection_by_bundle.get(bundle_id)
        if pick is None:
            raise UsageError(f"{bundle_id} is not in the round's selection")
        bundle = bundles.get(bundle_id)
        if bundle is None:
            raise UsageError(f"no bundle payload for {bundle_id}; re-run the frame tooling")
        rule = rules.get(rule_id)
        if rule is None:
            raise UsageError(f"{rule_id} is not in the rule registry")
        by_role = units[(bundle_id, rule_id)]
        authority = authority_by_repo.get(str(pick.get("repository", "")), {})

        payload = _conformance_payload(rule_id, rule, pick, bundle, authority, by_role)
        body = {
            "kind": "conformance",
            "bundle_id": bundle_id,
            "rule_id": rule_id,
            "repository": pick.get("repository"),
            "stratum": pick.get("stratum"),
            "split_group": pick.get("split_group"),
            "source_artifact_id": pick.get("source_artifact_id"),
            "scope_reasons": sorted(reasons),
            "control": "control_apparent_agreement" in reasons,
            "priority_blocks": _priority_blocks("conformance", rule_id),
            "judgments": {
                role: _judgment_summary(entry) for role, entry in sorted(by_role.items())
            },
            "payload_sha256": content_hash(payload, exclude=set()),
        }
        body["unit_id"] = f"{UNIT_ID_PREFIX}:{content_hash(body, exclude=set())}"
        queue_units.append(body)
        payloads[body["unit_id"]] = payload

    recon_votes: dict[str, dict[str, dict[str, Any]]] = {}
    for row in recon.get("classifications", ()):
        recon_votes.setdefault(str(row["bundle_id"]), {})[str(row["annotator_id"])] = dict(row)
    recon_selection = {
        str(row["bundle_id"]): row for row in recon.get("selection", ())
    }
    for bundle_id in sorted(set(recon_disagreed) | set(recon_controls)):
        reasons = ["specify_verdict_evidence"]
        control = bundle_id in recon_controls and bundle_id not in recon_disagreed
        if control:
            reasons.append("control_apparent_agreement")
        sel = recon_selection.get(bundle_id, {})
        votes = recon_votes.get(bundle_id, {})
        bundle = recon_bundles.get(bundle_id)
        if bundle is None:
            raise UsageError(
                f"no reconnaissance bundle payload for {bundle_id}; the recon raw "
                "tree is incomplete"
            )
        payload = _profile_payload(sel, votes, bundle)
        body = {
            "kind": "profile",
            "bundle_id": bundle_id,
            "rule_id": None,
            "repository": sel.get("repository"),
            "stratum": "profile_reconnaissance",
            "split_group": sel.get("split_group"),
            "source_artifact_id": sel.get("source_artifact_id"),
            "scope_reasons": sorted(reasons),
            "control": control,
            "priority_blocks": _priority_blocks("profile", None),
            "judgments": {
                annotator: {"kind": "classified", "classification": row["classification"]}
                for annotator, row in sorted(votes.items())
            },
            "payload_sha256": content_hash(payload, exclude=set()),
        }
        body["unit_id"] = f"{UNIT_ID_PREFIX}:{content_hash(body, exclude=set())}"
        queue_units.append(body)
        payloads[body["unit_id"]] = payload

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION_QUEUE,
        "generated_at": ctx.timestamp(),
        "round": {
            "round_id": str(round_record["round_id"]),
            "record_sha256": str(round_record["record_sha256"]),
        },
        "reconnaissance": {
            "report_id": str(recon["report_id"]),
            "report_sha256": str(recon["report_sha256"]),
        },
        "frame": {
            "frame_id": str(frame["frame_id"]),
            "record_sha256": str(frame["record_sha256"]),
        },
        "policy": {"seed": seed, "control_target": control_target},
        "blinding": {
            "withheld_in_source_only": list(WITHHELD_IN_SOURCE_ONLY),
            "rationale": (
                "The operator judges the source before seeing what either instrument "
                "concluded, so the gold is a reading of the text rather than a choice "
                "between two explanations. Revision-derived material is subsequent "
                "history and is withheld for the same reason."
            ),
        },
        "adjudicator_contract": {
            "kind": "human",
            "statement": (
                "Gold is operator-authored. A third model pass would measure another "
                "correlated interpretation of the rubric, not the standard; records "
                "whose adjudicator is not a human identity are refused."
            ),
        },
        "scope_summary": _scope_summary(queue_units),
        "units": queue_units,
    }
    record["queue_id"] = f"{QUEUE_ID_PREFIX}:{content_hash(record, exclude=set())}"
    sealed = seal(record)
    ctx.schemas.validate_document(sealed)
    return sealed, payloads


def _priority_blocks(kind: str, rule_id: str | None) -> list[str]:
    blocks: list[str] = []
    if kind == "conformance" and rule_id == "ATS-NUM-002":
        blocks.append("ats_num_002")
    if kind == "profile":
        blocks.append("specify_form")
    return blocks


def _scope_summary(queue_units: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = {reason: 0 for reason in SCOPE_REASONS}
    for unit in queue_units:
        for reason in unit["scope_reasons"]:
            counts[reason] += 1
    return {
        "units": len(queue_units),
        "conformance_units": sum(1 for u in queue_units if u["kind"] == "conformance"),
        "profile_units": sum(1 for u in queue_units if u["kind"] == "profile"),
        "control_units": sum(1 for u in queue_units if u["control"]),
        "by_reason": counts,
    }


def _conformance_payload(
    rule_id: str,
    rule: Mapping[str, Any],
    pick: Mapping[str, Any],
    bundle: Mapping[str, Any],
    authority: Mapping[str, Any],
    by_role: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Everything the operator may see for one conformance unit, staged.

    ``source_only`` is the pass-A surface. ``disagreement_review`` holds what
    pass B adds; nothing in it is reachable through the pass-A view.
    """
    return {
        "source_only": {
            "rule": {
                "rule_id": rule_id,
                "rule_version": rule.get("rule_version"),
                "title": rule.get("title"),
                "category": rule.get("category"),
                "normative_statement": rule.get("normative_statement"),
                "rationale": rule.get("rationale"),
                "default_states": rule.get("default_states"),
            },
            "profile": {
                "declared_default": "ASSESS",
                "definition_reference": (
                    "spec/ATS-1/1.0.0-draft.1/ATS-1_SPEC.md Section 9.2 (ASSESS) / 9.3 "
                    "(SPECIFY); when no profile is declared, the ASSESS default applies"
                ),
            },
            "candidate": {
                "stratum": pick.get("stratum"),
                "candidate_source": _candidate_source_of(pick, bundle),
                "split_group": pick.get("split_group"),
            },
            "source": {
                "source_artifact_id": bundle.get("source_artifact_id"),
                "source_revision": bundle.get("source_revision"),
                "repository": pick.get("repository"),
                "authority": {
                    "repository_owned": authority.get("repository_owned"),
                    "declaration_location": authority.get("declaration_location"),
                    "principal": authority.get("principal"),
                },
            },
            "bundle": {
                key: bundle.get(key)
                for key in (
                    "span_text",
                    "heading_path",
                    "containing_block",
                    "preceding_context",
                    "following_context",
                    "local_definitions",
                    "glossary_entries",
                    "context_completeness",
                    "policy_context",
                )
            },
        },
        "disagreement_review": {
            "judgments": {role: entry["row"] for role, entry in sorted(by_role.items())},
            "revision_material": {
                key: bundle.get(key) for key in ("diff", "later_edit", "review_comment")
            },
        },
    }


def _candidate_source_of(pick: Mapping[str, Any], bundle: Mapping[str, Any]) -> Any:
    # The round selection row is the authority for why this bundle was drawn;
    # the frame's candidate_source is not embedded in the round row, so the
    # bundle's profile_hypothesis basis stands in when the pick carries none.
    return pick.get("candidate_source") or (bundle.get("profile_hypothesis") or {}).get(
        "basis"
    )


def _profile_payload(
    sel: Mapping[str, Any],
    votes: Mapping[str, Mapping[str, Any]],
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    """One reconnaissance unit's staged surfaces.

    The selector's fired signals are withheld from the source-only pass for the
    same reason the reconnaissance withheld them from its classifiers: they say
    "this looked requirement-shaped because X", which is the selection argument,
    not the source. They surface in the disagreement review beside the two
    classifications.
    """
    return {
        "source_only": {
            "task": (
                "Classify this bundle's profile: which reader job does the text "
                "serve? The vocabulary is the reconnaissance study's own."
            ),
            "vocabulary": list(PROFILE_DISPOSITIONS),
            "bundle": {
                key: bundle.get(key)
                for key in (
                    "span_text",
                    "heading_path",
                    "containing_block",
                    "preceding_context",
                    "following_context",
                    "local_definitions",
                    "glossary_entries",
                    "context_completeness",
                    "policy_context",
                )
            },
            "source": {
                "source_artifact_id": sel.get("source_artifact_id"),
                "source_revision": bundle.get("source_revision"),
                "repository": sel.get("repository"),
                "document_family": sel.get("document_family"),
            },
        },
        "disagreement_review": {
            "classifications": {a: dict(row) for a, row in sorted(votes.items())},
            "selector": {
                "signals_fired": sel.get("signals_fired"),
                "signal_count": sel.get("signal_count"),
            },
            "revision_material": {
                key: bundle.get(key) for key in ("diff", "later_edit", "review_comment")
            },
        },
    }


# --------------------------------------------------------------------------
# Operator records
# --------------------------------------------------------------------------


def validate_record(
    row: Mapping[str, Any],
    unit: Mapping[str, Any],
    *,
    prior_stages: Mapping[str, Mapping[str, Any]] | Iterable[str] = (),
) -> None:
    """Refuse a malformed or out-of-order operator record.

    The checks here are the protocol: human adjudicator, source-only before
    disagreement review, closed vocabularies, and the conditional obligations
    (a missing-context taxonomy behind every insufficient_context, exactly one
    primary diagnosis, the competent-reader answer wherever the instruments
    disagreed, the NUM-002 block on its units, the requirement-form taxonomy on
    profile units).

    ``prior_stages`` may be the stage names already recorded for this unit or,
    as :func:`load_gold` passes, the recorded rows keyed by stage. Given the
    rows, the review's ``decision_changed`` is checked against what the pass-A
    row actually says rather than taken on the record's word.
    """
    stage = row.get("stage")
    if stage not in STAGES:
        raise UsageError(f"unknown stage {stage!r}; expected one of {STAGES}")

    adjudicator = row.get("adjudicator") or {}
    if adjudicator.get("kind") != "human":
        raise UsageError(
            "gold is operator-authored: the adjudicator must be a human identity, "
            f"got kind={adjudicator.get('kind')!r}. A third model pass would measure "
            "another correlated interpretation of the rubric, not the standard."
        )
    identity = str(adjudicator.get("id", "")).strip()
    if not identity:
        raise UsageError("the adjudicator carries no id; authority must be attributable")
    # The kind field alone is cheap to assert -- the CLI fills it in on the
    # caller's behalf -- so the identity itself must carry the claim. Requiring
    # the operator namespace keeps an instrument identity from being recorded
    # as the authority by a tool that meant well.
    if not identity.startswith("operator:") or not identity.split(":", 1)[1].strip():
        raise UsageError(
            f"adjudicator id {identity!r} is not an operator identity; gold records "
            "name their human authority as operator:<name>, so that an instrument id "
            "passed through a well-meaning tool cannot become the adjudicator"
        )

    vocabulary = (
        SOURCE_DISPOSITIONS if unit["kind"] == "conformance" else PROFILE_DISPOSITIONS
    )
    prior = set(prior_stages)

    if stage == "source_only":
        if "source_only" in prior:
            raise UsageError(
                f"{unit['unit_id']} already carries a source-only judgment; it is "
                "immutable. A revised view belongs in the disagreement review, where "
                "the change itself is evidence."
            )
        _require_vocab(row, "disposition", vocabulary)
        _require_vocab(row, "determinacy", DETERMINACY)
        _require_rationale(row)
        _require_missing_context(row, row.get("disposition"))
        return

    require_review_unlocked(unit, prior)
    if "disagreement_review" in prior:
        raise UsageError(
            f"{unit['unit_id']} already carries a disagreement review; it is immutable"
        )
    _require_vocab(row, "final_disposition", vocabulary)
    _require_rationale(row)
    _require_missing_context(row, row.get("final_disposition"))
    if isinstance(prior_stages, Mapping):
        _require_computed_decision_changed(row, prior_stages["source_only"])

    diagnoses = row.get("system_diagnosis")
    if not isinstance(diagnoses, Sequence) or not diagnoses:
        raise UsageError(
            "the disagreement review must diagnose the system, even when the diagnosis "
            "is no_system_defect; an empty diagnosis is a silence, not an answer"
        )
    primaries = 0
    for entry in diagnoses:
        code = entry.get("code") if isinstance(entry, Mapping) else None
        if code not in SYSTEM_DIAGNOSES:
            raise UsageError(f"unknown system diagnosis {code!r}")
        primaries += 1 if entry.get("primary") else 0
    if primaries != 1:
        raise UsageError(
            f"exactly one system diagnosis must be primary; got {primaries}. Multiple "
            "may apply, but a record with no primary cannot be counted, and one with "
            "several counts twice."
        )

    if unit_disagreed(unit) and not isinstance(
        row.get("competent_reader_could_reach_rejected"), bool
    ):
        raise UsageError(
            "this unit's instruments disagreed: the review must answer whether a "
            "competent reader applying the published ATS-1 text could reasonably "
            "reach the rejected interpretation. Without that answer, 'the adjudicator "
            "selected a label' would stand in for 'the standard is clear'."
        )

    if "ats_num_002" in unit.get("priority_blocks", ()):
        block = row.get("ats_num_002")
        if not isinstance(block, Mapping) or set(block) != set(NUM002_QUESTIONS):
            raise UsageError(
                "ATS-NUM-002 units must answer all six collapsed questions "
                f"({', '.join(NUM002_QUESTIONS)}); the rule is not to be amended until "
                "the adjudicated examples reveal the actual boundary"
            )
    if "specify_form" in unit.get("priority_blocks", ()):
        forms = row.get("requirement_forms")
        if forms is None or not isinstance(forms, Sequence):
            raise UsageError(
                "profile units must record the requirement forms observed (empty list "
                "when none apply); the taxonomy supports caller-directed mining changes"
            )
        for form in forms:
            if form not in REQUIREMENT_FORMS:
                raise UsageError(f"unknown requirement form {form!r}")


def _require_vocab(row: Mapping[str, Any], field: str, allowed: Sequence[str]) -> None:
    value = row.get(field)
    if value not in allowed:
        raise UsageError(f"{field} must be one of {tuple(allowed)}; got {value!r}")


def _require_rationale(row: Mapping[str, Any]) -> None:
    if not str(row.get("rationale", "")).strip():
        raise UsageError("a judgment without a rationale is a vote, not an adjudication")


def _require_missing_context(row: Mapping[str, Any], disposition: Any) -> None:
    missing = row.get("missing_context")
    if disposition == "insufficient_context":
        if not isinstance(missing, Sequence) or not missing:
            raise UsageError(
                "insufficient_context requires the minimum missing object(s) from the "
                "taxonomy; without them the context builder cannot learn what to fetch"
            )
        for item in missing:
            if item not in MISSING_CONTEXT_OBJECTS:
                raise UsageError(f"unknown missing-context object {item!r}")
    elif missing:
        raise UsageError(
            "missing_context is only meaningful on an insufficient_context disposition"
        )


def decision_changed(source_only: Mapping[str, Any], final_disposition: Any) -> bool:
    """Whether the disagreement review moved off the source-only judgment.

    Derived from the recorded pass-A row rather than asked of the operator.
    Whether the arguments changed the adjudicator's mind is a property of the
    supplied records, not a self-reported flag.
    """
    return str(source_only.get("disposition")) != str(final_disposition)


def _require_computed_decision_changed(
    row: Mapping[str, Any], source_only: Mapping[str, Any]
) -> None:
    expected = decision_changed(source_only, row.get("final_disposition"))
    declared = row.get("decision_changed")
    if declared is not expected:
        raise UsageError(
            "decision_changed is computed from the recorded source-only row, never "
            f"declared: pass A recorded {source_only.get('disposition')!r}, this "
            f"review records {row.get('final_disposition')!r}, so decision_changed is "
            f"{expected}; the row declares {declared!r}"
        )


def require_review_unlocked(
    unit: Mapping[str, Any],
    prior_stages: Mapping[str, Mapping[str, Any]] | Iterable[str] = (),
) -> None:
    """Refuse the disagreement review until the source-only judgment exists.

    Both the recorder and the viewer call this. Showing the two judgments is
    itself the disclosure the protocol orders, so the command that displays
    them must refuse on the same grounds, and in the same words, as the record
    it precedes.
    """
    if "source_only" in set(prior_stages):
        return
    raise UsageError(
        f"{unit['unit_id']} has no recorded source-only judgment; the disagreement "
        "review is refused until it exists, because seeing the arguments first "
        "would let the operator choose the more persuasive explanation instead of "
        "judging the source"
    )


def assert_source_only_blinded(surface: Any, unit_id: str) -> None:
    """Refuse to display a pass-A surface that carries withheld material.

    :func:`build_queue` stages the two surfaces, so this holds as long as the
    payloads file is the one the committed queue sealed. Checking again at the
    point of display makes a regenerated or hand-edited payload fail closed
    instead of leaking an annotator's conclusion into the source-only pass.

    Only mapping keys are examined. Prose that happens to quote one of the
    withheld words is source text, and refusing it would blind the operator to
    the thing being adjudicated.
    """
    if isinstance(surface, Mapping):
        for key, value in surface.items():
            reason = _WITHHELD_PAYLOAD_KEYS.get(key)
            if reason is not None:
                raise UsageError(
                    f"{unit_id}: the source-only surface carries {key!r} ({reason}), "
                    "which the queue withholds from pass A. The payloads file is not "
                    "the one the queue sealed; regenerate it before adjudicating."
                )
            assert_source_only_blinded(value, unit_id)
    elif isinstance(surface, Sequence) and not isinstance(surface, (str, bytes)):
        for item in surface:
            assert_source_only_blinded(item, unit_id)


def seal_record(ctx: Any, row: Mapping[str, Any]) -> dict[str, Any]:
    """Seal one operator record and validate it against the schema."""
    body = dict(row)
    body["schema_version"] = SCHEMA_VERSION_RECORD
    body.pop("record_sha256", None)
    sealed = seal(body)
    ctx.schemas.validate_document(sealed)
    return sealed


def unit_disagreed(unit: Mapping[str, Any]) -> bool:
    """Whether the two supplied instruments disagreed on this unit, at any level.

    Public because callers need one deterministic disagreement predicate rather
    than reimplementing the comparison.
    """
    votes = unit.get("judgments", {})
    if unit["kind"] == "profile":
        return len({v.get("classification") for v in votes.values()}) > 1
    kinds = {v.get("kind") for v in votes.values()}
    if kinds == {"judged"}:
        return len({v.get("label") for v in votes.values()}) > 1
    if kinds == {"declined"}:
        return len({v.get("applicability") for v in votes.values()}) > 1
    return True  # one judged, one declined


def load_gold(
    path: str | Path,
    queue: Mapping[str, Any],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Read the append-only gold file, enforcing order and immutability.

    Returns ``{unit_id: {stage: row}}``. Every row is re-validated against its
    unit on load, so a hand-edited file fails here rather than flowing into
    scoring.
    """
    units_by_id = {u["unit_id"]: u for u in queue.get("units", ())}
    out: dict[str, dict[str, dict[str, Any]]] = {}
    source = Path(path)
    if not source.is_file():
        return out
    for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        unit = units_by_id.get(row.get("unit_id"))
        if unit is None:
            raise UsageError(
                f"line {line_no}: {row.get('unit_id')!r} is not in the queue; a gold "
                "record for a unit nobody selected has no provenance"
            )
        validate_record(row, unit, prior_stages=out.get(row["unit_id"], {}))
        out.setdefault(row["unit_id"], {})[row["stage"]] = row
    return out


def gold_disposition(stages: Mapping[str, Mapping[str, Any]]) -> str | None:
    """The authority-bearing disposition for one unit, when it exists.

    The disagreement review's ``final_disposition`` is gold; a unit with only a
    source-only judgment is in progress, not provisional gold, because the
    protocol's second stage exists precisely to let the arguments change it.
    """
    review = stages.get("disagreement_review")
    if review is None:
        return None
    return str(review["final_disposition"])

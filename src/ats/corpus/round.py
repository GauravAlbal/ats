"""Select and freeze one round of independent blind annotation.

A round draws from a frozen sampling frame and never writes back to it. The
frame is content-addressed, and an agreement figure is only meaningful against
the exact set it was measured over; a frame that gained selections, or had its
double-annotation flags re-assigned, after judgments existed would no longer be
that set. So the round carries its own selection and binds the frame it drew
from by hash (spec Sections 17.7, 17.9).

Two rules shape everything here:

* **One selection per leakage component.** The frame already admits one bundle
  per component; the round preserves that when it subsets, so two judgments
  never land on two views of the same material.
* **Both passes complete before adjudication.** Adjudicating as judgments
  arrive lets an early disagreement steer the later ones, and the disagreement
  rate is the measurement. :func:`freeze_pass` records a pass by the content
  hash of its judgments, and :func:`adjudication_ready` refuses until every
  pass is frozen.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

from ..canonical import canonical_bytes, content_hash, seal, sha256_hex
from ..errors import UsageError

SCHEMA_ID: Final[str] = "ats_annotation_round_v1.schema.json"
SCHEMA_VERSION: Final[str] = "ats.annotation_round.v1"
ID_PREFIX: Final[str] = "ats-round-sha256"

#: The default allocation over the frame's sampling mechanisms. Callers may
#: provide different targets; these values are deterministic defaults for
#: exercising each mechanism without mixing their shortfalls.
STAGE_2A_TARGETS: Final[tuple[tuple[str, int], ...]] = (
    ("natural_rule_candidate", 50),
    ("surface_cue_hard_negative", 25),
    ("zero_candidate_rule_probe", 20),
    ("revision_derived_candidate", 15),
    ("low_signal_random_control", 10),
)

#: What an annotator may not see before submitting. Each of these says why a
#: bundle was sampled, which is useful context afterwards and an anchor
#: beforehand: an annotator told a span is a "hard negative" has been handed
#: the answer to the question being asked.
WITHHELD_UNTIL_SUBMISSION: Final[tuple[str, ...]] = (
    "stratum",
    "candidate_source",
    "candidate_rule_ids",
    "near_duplicate_cluster",
    "template_family",
    "split_group",
)

BLINDING_RATIONALE: Final[str] = (
    "A miner prediction is not a gold label, and the mechanism that surfaced a "
    "span implies one. Withholding it until submission keeps the judgment a "
    "judgment about the text; releasing it afterwards lets an annotator see "
    "what they were shown and why."
)

ADJUDICATION_GATE: Final[str] = (
    "every pass frozen; adjudicating before both passes complete lets an early "
    "disagreement steer the judgments that follow it"
)

#: A judgment names one rule. Where a bundle carries no candidate rule -- a
#: control, or a probe whose rule produced no candidate -- the round still has
#: to say what is being judged, and this is the rule of last resort: whether
#: the span keeps one meaning within its scope.
FALLBACK_RULE: Final[str] = "ATS-SCOPE-001"

#: How a zero-candidate probe names the rule it was drawn to test. The frame
#: writes it into ``candidate_source`` because the pick has no candidate to
#: carry a rule id on.
PROBE_SOURCE_PREFIX: Final[str] = "zero_candidate_probe:"


@dataclass(frozen=True, slots=True)
class Annotator:
    """One annotator, and what kind of thing it is.

    ``kind`` is not decoration. Two LLM passes measure whether the rubric and
    the context bundles produce a stable judgment; two humans measure whether
    people agree. Reporting one as the other claims evidence never collected.
    """

    annotator_id: str
    kind: str
    model: str | None = None
    prompt_id: str | None = None
    prompt_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"annotator_id": self.annotator_id, "kind": self.kind}
        for key in ("model", "prompt_id", "prompt_sha256"):
            value = getattr(self, key)
            if value:
                out[key] = value
        return out


def _rules_for(selection: Mapping[str, Any]) -> list[str]:
    """Which rules this bundle is judged against.

    A zero-candidate probe carries no ``candidate_rule_ids`` by construction --
    the point of the stratum is that the miner produced no candidate for the
    rule -- but the rule it probes is named in ``candidate_source`` as
    ``zero_candidate_probe:<rule_id>:<signal>``. Reading it from there is what
    makes the stratum measure anything: without it every probe falls through to
    :data:`FALLBACK_RULE` and twenty bundles drawn to test fifteen specific
    rules are all annotated against one unrelated rule instead, producing a
    round that looks complete and answers nothing.
    """
    rules = [str(r) for r in (selection.get("candidate_rule_ids") or [])]
    if rules:
        return rules
    source = str(selection.get("candidate_source") or "")
    if source.startswith(PROBE_SOURCE_PREFIX):
        parts = source.split(":")
        if len(parts) >= 2 and parts[1]:
            return [parts[1]]
    return [FALLBACK_RULE]


def select_round(
    frame: Mapping[str, Any],
    *,
    seed: int,
    targets: Sequence[tuple[str, int]] = STAGE_2A_TARGETS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Choose the round's bundles from ``frame``, and report each stratum.

    Selection is deterministic in ``seed`` and the frame's content, and takes
    at most one bundle per leakage component. A stratum that cannot be filled
    reports how far it got and why, rather than borrowing from another: the
    strata are different sampling mechanisms, and a shortfall in one is not
    repairable with material from another.
    """
    by_stratum: dict[str, list[Mapping[str, Any]]] = {}
    for row in frame.get("selection", ()):
        by_stratum.setdefault(str(row["stratum"]), []).append(row)

    chosen: list[dict[str, Any]] = []
    report: list[dict[str, Any]] = []
    used_groups: set[str] = set()

    for stratum, target in targets:
        pool = by_stratum.get(stratum, [])
        # A fixed shuffle: the order is a pure function of the seed, the
        # stratum, and each bundle's own identity, so adding a stratum cannot
        # reorder another one.
        ordered = sorted(
            pool,
            key=lambda row: hashlib.sha256(
                f"{seed}\x1f{stratum}\x1f{row['bundle_id']}".encode("utf-8")
            ).hexdigest(),
        )
        picked: list[Mapping[str, Any]] = []
        for row in ordered:
            if len(picked) >= target:
                break
            group = str(row["split_group"])
            if group in used_groups:
                continue
            used_groups.add(group)
            picked.append(row)

        entry: dict[str, Any] = {
            "stratum": stratum,
            "target": target,
            "selected": len(picked),
            "pool": len(pool),
        }
        if len(picked) < target:
            entry["shortfall_reason"] = (
                f"selected {len(picked)} of {target}: the frame offers {len(pool)} "
                f"bundle(s) in this stratum and every remaining one belongs to a "
                f"leakage component already represented in this round"
            )
        report.append(entry)

        for row in picked:
            chosen.append(
                {
                    "bundle_id": str(row["bundle_id"]),
                    "source_artifact_id": str(row["source_artifact_id"]),
                    "repository": str(row["repository"]),
                    "stratum": stratum,
                    "split_group": str(row["split_group"]),
                    "rule_ids": _rules_for(row),
                }
            )

    chosen.sort(key=lambda row: row["bundle_id"])
    return chosen, report


def build_round(
    ctx: Any,
    frame: Mapping[str, Any],
    annotators: Sequence[Annotator],
    *,
    seed: int,
    targets: Sequence[tuple[str, int]] = STAGE_2A_TARGETS,
    passes: Sequence[Mapping[str, Any]] = (),
    supersedes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the round record over a frozen ``frame``.

    ``supersedes`` names an earlier round this one replaces. It is placed in the
    body before sealing, so a correction is part of what the round's content
    address covers; a pointer bolted on after sealing would leave the record
    claiming a hash it no longer has.
    """
    if len(annotators) < 2:
        raise UsageError(
            "a double-annotation round needs at least two annotators; one judgment is "
            "not an agreement measurement (spec 17.9)"
        )
    if not frame.get("record_sha256"):
        raise UsageError(
            "the frame carries no record_sha256; a round must bind what it drew from"
        )

    selection, strata = select_round(frame, seed=seed, targets=targets)
    target_size = sum(target for _stratum, target in targets)

    record = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": ctx.timestamp(),
        "frame": {
            "frame_id": str(frame["frame_id"]),
            "record_sha256": str(frame["record_sha256"]),
            "selection_count": len(frame.get("selection", ())),
            # The frame carries its own double_annotated flag from an earlier
            # allocation. This round's strata supersede it, and saying so keeps
            # two different answers to "which bundles get two judgments" from
            # both looking authoritative.
            "supersedes_frame_flag": True,
        },
        "policy": {
            "seed": seed,
            "target_size": target_size,
            "judgments_per_example": len(annotators),
            "adjudication_opens_after": ADJUDICATION_GATE,
        },
        "annotators": [a.to_dict() for a in annotators],
        "strata": strata,
        "selection": selection,
        "blinding": {
            "withheld_until_submission": list(WITHHELD_UNTIL_SUBMISSION),
            "rationale": BLINDING_RATIONALE,
        },
        "passes": list(passes)
        or [
            {"annotator_id": a.annotator_id, "state": "open", "judgment_count": 0}
            for a in annotators
        ],
    }
    if supersedes is not None:
        record["supersedes"] = dict(supersedes)
    # Same two-step address the frame uses: the id is a digest over the body,
    # then the record is sealed so record_sha256 covers the id too.
    record["round_id"] = f"{ID_PREFIX}:{content_hash(record, exclude=set())}"
    sealed = seal(record)
    ctx.schemas.validate_document(sealed)
    return sealed


def blind_item(
    selection: Mapping[str, Any], bundle: Mapping[str, Any], rule_id: str
) -> dict[str, Any]:
    """What an annotator sees for one rule on one bundle, and nothing else.

    Built by naming what is included rather than by deleting what is not: a
    denylist silently leaks any field added later, and the fields kept out are
    exactly the ones that would give away the answer.
    """
    if rule_id not in selection["rule_ids"]:
        raise UsageError(
            f"{rule_id} is not a rule this round judges for {selection['bundle_id']}"
        )
    return {
        "bundle_id": selection["bundle_id"],
        "rule_id": rule_id,
        "span_text": bundle["span_text"],
        "heading_path": bundle.get("heading_path", []),
        "containing_block": bundle.get("containing_block"),
        "preceding_context": bundle.get("preceding_context"),
        "following_context": bundle.get("following_context"),
        "local_definitions": bundle.get("local_definitions", []),
        "glossary_entries": bundle.get("glossary_entries", []),
        "context_completeness": bundle.get("context_completeness"),
    }


def freeze_pass(
    annotator_id: str,
    judgments_path: str | Path,
    *,
    declines_path: str | Path | None = None,
    relative_to: str | Path | None = None,
) -> dict[str, Any]:
    """Record a pass as frozen, bound to the exact bytes it produced.

    A pass answers every item it was given, but AG-19 step 2 splits those
    answers in two: a conformance judgment when the rule applies, and a decline
    when it does not. Both are recorded here. Freezing on judgments alone would
    make a pass that declined more items look like a pass that answered fewer,
    which is the difference between a scope finding and a missing answer.

    An absent decline sidecar is ``unavailable``, never zero: a file that was
    never written is not a pass that declined nothing.
    """
    path = Path(judgments_path)
    if not path.is_file():
        return {
            "annotator_id": annotator_id,
            "state": "unavailable",
            "judgment_count": 0,
            "detail": f"no judgments at {path}",
        }
    raw = path.read_bytes()
    count = _line_count(raw)
    record: dict[str, Any] = {
        "annotator_id": annotator_id,
        "state": "frozen",
        "judgment_count": count,
        "path": _display_path(path, relative_to),
        "judgments_sha256": hashlib.sha256(raw).hexdigest(),
    }
    declines = Path(declines_path) if declines_path is not None else None
    if declines is None:
        return record
    if not declines.is_file():
        record["state"] = "unavailable"
        record["detail"] = (
            f"no decline sidecar at {declines}; an absent sidecar cannot be read as a "
            "pass that declined nothing"
        )
        return record
    decline_bytes = declines.read_bytes()
    record["decline_count"] = _line_count(decline_bytes)
    record["declines_path"] = _display_path(declines, relative_to)
    record["declines_sha256"] = hashlib.sha256(decline_bytes).hexdigest()
    record["universe"] = count + record["decline_count"]
    return record


def _line_count(raw: bytes) -> int:
    return sum(1 for line in raw.decode("utf-8").splitlines() if line.strip())


def _display_path(path: Path, relative_to: str | Path | None) -> str:
    """A repo-relative path, so a frozen pass is not bound to one checkout."""
    if relative_to is None:
        return str(path)
    try:
        return str(path.resolve().relative_to(Path(relative_to).resolve()))
    except ValueError:
        return str(path)


def adjudication_ready(round_record: Mapping[str, Any]) -> tuple[bool, str]:
    """Whether adjudication may begin, and why not when it may not.

    The gate is that every pass answered the same items, not that every pass
    produced the same number of judgments. Two passes may legitimately disagree
    about how many rules applied at all -- that disagreement is one of the
    measurements the round exists to make -- so the comparison is over each
    pass's universe of answers, judgments plus declines.
    """
    passes = list(round_record.get("passes", ()))
    if not passes:
        return False, "the round records no passes"
    unfrozen = [p["annotator_id"] for p in passes if p.get("state") != "frozen"]
    if unfrozen:
        return False, f"{', '.join(unfrozen)} not frozen; {ADJUDICATION_GATE}"
    universes = {
        p["annotator_id"]: p.get("universe", p.get("judgment_count", 0)) for p in passes
    }
    if len(set(universes.values())) != 1:
        return False, (
            f"passes answered different item sets ({universes}); an unanswered item is "
            f"not a disagreement and must not be counted as one"
        )
    judgments = {p["annotator_id"]: p.get("judgment_count", 0) for p in passes}
    return True, (
        f"{len(passes)} pass(es) frozen over {next(iter(universes.values()))} item(s) "
        f"each; judgments {judgments}"
    )


def load_bundles(path: str | Path) -> dict[str, dict[str, Any]]:
    """Read the local bundle store, keyed by bundle id."""
    source = Path(path)
    if not source.is_file():
        raise UsageError(
            f"no bundles at {source}; annotation reads the bundles the frame built, and "
            f"they are written locally because they carry verbatim source text"
        )
    out: dict[str, dict[str, Any]] = {}
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip():
            bundle = json.loads(line)
            out[bundle["bundle_id"]] = bundle
    return out


def round_digest(record: Mapping[str, Any]) -> str:
    """A stable digest over the round's selection, for cross-checking a report."""
    return sha256_hex(canonical_bytes([row["bundle_id"] for row in record["selection"]]))


def iter_items(
    record: Mapping[str, Any], bundles: Mapping[str, Mapping[str, Any]]
) -> Iterable[dict[str, Any]]:
    """Every blind item in the round, in a deterministic order."""
    for selection in record["selection"]:
        bundle = bundles.get(selection["bundle_id"])
        if bundle is None:
            raise UsageError(
                f"no bundle for {selection['bundle_id']}; a judgment without its context "
                f"bundle would be a judgment about an isolated span (spec 17.4)"
            )
        for rule_id in selection["rule_ids"]:
            yield blind_item(selection, bundle, rule_id)

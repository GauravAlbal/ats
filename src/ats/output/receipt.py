"""Candidate receipts and receipt verification.

Section 14.11 assigns final authority for semantic acceptance to an authorized
human or an explicitly governed external acceptance system, and Section 13.7
forbids a component from becoming the authoritative adjudicator for its own
finding. Accordingly :func:`build_candidate_receipt` requires the adjudicator
identity to be supplied by the caller: nothing in this package can name itself.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..canonical import seal, verify_seal
from ..context import Context
from ..errors import UsageError
from ..ir.model import IrDocument
from ..policy import PolicySnapshot

RECEIPT_SCHEMA_ID = "ats_acceptance_receipt_v1.schema.json"

#: Identities this implementation refuses to accept as an adjudicator, because
#: they name the producing component rather than an external authority.
SELF_IDENTITIES = frozenset({"ats", "ats-ir-linter", "ats-output-linter", "self", ""})


def build_candidate_receipt(
    ctx: Context,
    *,
    ir: IrDocument,
    policy: PolicySnapshot,
    output_sha256: str | None,
    lint_report: Mapping[str, Any],
    adjudicator: str,
    finding_refs: Sequence[str] = (),
    adjudication_refs: Sequence[str] = (),
    supersedes: Sequence[str] = (),
) -> dict[str, Any]:
    """Assemble a candidate ``ats.acceptance_receipt.v1``.

    "Candidate" is load-bearing: the receipt records what the deterministic
    stack established and who the external adjudicator is. It does not assert
    that acceptance happened.
    """
    if adjudicator.strip().casefold() in SELF_IDENTITIES:
        raise UsageError(
            f"adjudicator {adjudicator!r} names this implementation; Section 13.7 forbids a "
            "component from adjudicating its own findings, so the acceptance authority must be "
            "supplied externally"
        )

    summary = lint_report.get("summary", {})
    by_status = summary.get("by_status", {})
    deterministic = {
        "required_passed": int(by_status.get("PASS", 0)),
        "required_failed": int(summary.get("required_failed", 0)),
        "required_unavailable": int(summary.get("required_unavailable", 0)),
        "advisory_findings": int(summary.get("advisory_findings", 0)),
    }
    review_required = int(by_status.get("REVIEW_REQUIRED", 0))
    semantic = {
        "proposed": review_required,
        "accepted": 0,
        "rejected": 0,
        "waived": 0,
        "unresolved": review_required,
        "abstained": int(by_status.get("UNAVAILABLE", 0)),
    }

    receipt: dict[str, Any] = {
        "schema_version": "ats.acceptance_receipt.v1",
        "receipt_id": f"candidate:{ir.artifact_id}:{ir.ir_sha256[:16]}",
        "standard": "ATS-1",
        "spec_version": ctx.spec_version,
        "source_sha256": ir.source["content_sha256"],
        "policy_snapshot_id": policy.snapshot_id,
        "policy_snapshot_sha256": policy.declared_sha256,
        "implementation": {
            "name": ctx.implementation["name"],
            "version": ctx.implementation["version"],
            "rule_registry_version": ctx.implementation["rule_registry_version"],
            "lexicon_version": ctx.implementation["lexicon_version"],
        },
        "profiles": list(ir.profiles),
        "deterministic_summary": deterministic,
        "semantic_summary": semantic,
        "conformance": dict(lint_report["conformance"]),
        "adjudicator": adjudicator,
        "created_at": ctx.timestamp(),
    }
    if output_sha256:
        receipt["output_sha256"] = output_sha256
    if "parser_version" in lint_report.get("implementation", {}):
        receipt["implementation"]["parser_version"] = lint_report["implementation"][
            "parser_version"
        ]
    if finding_refs:
        receipt["finding_refs"] = list(finding_refs)
    if adjudication_refs:
        receipt["adjudication_refs"] = list(adjudication_refs)
    if supersedes:
        receipt["supersedes"] = list(supersedes)

    sealed = seal(receipt)
    ctx.schemas.validate(sealed, RECEIPT_SCHEMA_ID)
    return sealed


def verify_receipt(
    ctx: Context,
    receipt_document: Mapping[str, Any],
    *,
    ir_document: Mapping[str, Any] | None = None,
    output_sha256: str | None = None,
    policy: PolicySnapshot | None = None,
    policy_document: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Re-check a receipt against the artifacts it binds (spec Section 16.12)."""
    problems: list[str] = []
    unreplayable: list[str] = []

    violations = ctx.schemas.violations(receipt_document, RECEIPT_SCHEMA_ID)
    if violations:
        return {
            "status": "FAIL",
            "receipt_id": str(receipt_document.get("receipt_id", "")),
            "detail": "; ".join(f"{v.pointer or '/'}: {v.message}" for v in violations[:6]),
        }

    ok, declared, recomputed = verify_seal(dict(receipt_document))
    if not ok:
        problems.append(
            f"receipt_sha256 {declared} does not match its canonical bytes ({recomputed})"
        )

    if receipt_document.get("spec_version") != ctx.spec_version:
        problems.append(
            f"receipt targets spec {receipt_document.get('spec_version')!r}, the imported "
            f"package is {ctx.spec_version!r}"
        )

    if policy is None and policy_document is not None:
        policy = ctx.policy(policy_document)
    if policy is not None:
        if receipt_document.get("policy_snapshot_sha256") != policy.declared_sha256:
            problems.append(
                "the receipt binds a policy hash that differs from the current resolved policy "
                "snapshot; Section 15.8 makes the claim stale and it MUST be re-evaluated"
            )
        if receipt_document.get("policy_snapshot_id") != policy.snapshot_id:
            problems.append(
                f"receipt binds policy id {receipt_document.get('policy_snapshot_id')!r}, "
                f"current snapshot is {policy.snapshot_id!r}"
            )

    if ir_document is not None:
        source = ir_document.get("source", {}).get("content_sha256")
        if receipt_document.get("source_sha256") != source:
            problems.append(
                f"receipt binds source {receipt_document.get('source_sha256')}, the IR declares "
                f"{source}"
            )
    if output_sha256 is not None and receipt_document.get("output_sha256") not in (
        None,
        output_sha256,
    ):
        problems.append(
            f"receipt binds output {receipt_document.get('output_sha256')}, the document hashes "
            f"to {output_sha256}"
        )

    conformance = receipt_document.get("conformance", {})
    if conformance.get("semantic_review") == "PASS":
        unreplayable.append(
            "semantic_review is recorded as PASS; this implementation cannot reproduce a semantic "
            "disposition, so that dimension is historical evidence only (spec 16.12)"
        )
    if conformance.get("preservation") == "PASS":
        unreplayable.append(
            "preservation is recorded as PASS; no source-to-output comparison is reproducible "
            "from the supplied artifacts"
        )

    adjudicator = str(receipt_document.get("adjudicator", "")).strip().casefold()
    if adjudicator in SELF_IDENTITIES:
        problems.append(
            f"adjudicator {receipt_document.get('adjudicator')!r} names the producing "
            "implementation; acceptance authority must be external (spec 13.7, 14.11)"
        )

    if problems:
        status = "FAIL"
        detail = "; ".join(problems)
    elif unreplayable:
        status = "UNAVAILABLE"
        detail = "; ".join(unreplayable)
    else:
        status = "PASS"
        detail = (
            f"receipt {recomputed[:16]}… reproduces its content address and binds the supplied "
            "source, policy, and output hashes"
        )
    return {
        "status": status,
        "receipt_id": str(receipt_document.get("receipt_id", "")),
        "declared_sha256": declared,
        "recomputed_sha256": recomputed,
        "detail": detail,
        "unreplayable": unreplayable,
    }

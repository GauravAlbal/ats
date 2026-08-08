"""``ats output lint`` — the deterministic output-bundle linter.

What this can prove: the declared objects were mapped, the bytes are the bytes
the trace describes, the declared P0 values render exactly, and the declared P1
relations are present. What it cannot prove is that a mapped block *realizes*
the object it points at. That gap is reported as REVIEW_REQUIRED and stated in
the conformance rationale rather than papered over.

Draft.2 adds two structural checks: OUT-COORD-PRESERVED (stable semantic
coordinates survive into the rendering, spec 7.17/11.3.1) and
OUT-BASIS-NOT-STRENGTHENED (a rendered value never exceeds the force its
declared source basis allows, spec 7.19). Both join the mechanical dimension
only when the IR declares the surfaces they protect: :data:`MECHANICAL_CHECKS`
stays a static frozenset for draft.1 parity, and the two new checks gate through
their ``required`` flag, which is True exactly when the relevant block is
present (see :data:`GATED_MECHANICAL_CHECKS`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..canonical import seal, verify_seal
from ..context import Context
from ..errors import ParseError, UsageError
from ..hashes import bind_file
from ..ir.model import IrDocument
from ..ir.validate import require_valid_ir
from ..policy import PolicySnapshot
from ..rules.deterministic._support import contains_exact, contains_phrase
from ..rules.results import CheckResult, Status
from .parse import (
    MARKER_CLOSE,
    MARKER_OPEN,
    ParsedDocument,
    missing_required_constructs,
    parse_markdown,
    parser_version,
)
from .render_checks import SurfaceReport, run_surface_checks
from .trace import OutputTrace, block_text_sha256, ir_value_at, load_trace

REPORT_SCHEMA_ID = "ats_output_lint_report_v1.schema.json"

#: The surface checks, mapped to the spec sections that ground them.
SURFACE_CHECK_SPECS: dict[str, tuple[str, str]] = {
    "OUT-WEP-CANONICAL": ("Canonical WEP phrases only", "ATS-1 8.3"),
    "OUT-WEP-INLINE-RANGE": ("First material WEP use shows its range", "ATS-1 8.4"),
    "OUT-DEONTIC-KEYWORDS": ("Deontic keywords are canonical and uppercase", "ATS-1 8.16, 1.3"),
    "OUT-ACRONYMS": ("Acronyms are expanded or permitted", "ATS-1 10.5"),
    "OUT-UNITS": ("Rendered P0 numbers carry units", "ATS-1 10.9, 9.3.8"),
    "OUT-RELATIVE-TIME": ("Relative time is anchored", "ATS-1 10.11"),
    "OUT-TERMINOLOGY": ("Terminology, intensifier, and timing constraints", "ATS-1 10.2, 10.20, 10.21, 9.3.7"),
    "OUT-HEADINGS-LISTS": ("Heading and list mechanics", "ATS-1 10.17, 10.18"),
}

#: Checks that constitute mechanical conformance for the output surface.
MECHANICAL_CHECKS = frozenset(
    {
        "OUT-BYTES",
        "OUT-MARKDOWN-PARSE",
        "OUT-MARKERS",
        "OUT-TRACE-SCHEMA",
        "OUT-BLOCK-HASHES",
        "OUT-IR-REFS",
        "OUT-UNKNOWN-REFS",
        "OUT-BLOCK-ORDER",
        "OUT-P0-EXACT",
        "OUT-POLICY-EXCEPTIONS",
    }
)

#: Draft.2 structural checks that join the mechanical dimension only when the
#: IR declares the surfaces they protect. ``MECHANICAL_CHECKS`` is a static
#: frozenset (draft.1 parity), so these checks gate through ``required``: the
#: check sets ``required=True`` exactly when the IR declares a
#: ``stable_coordinates`` block (OUT-COORD-PRESERVED) or any ``semantic_basis``
#: declaration (OUT-BASIS-NOT-STRENGTHENED), and ``_compute_conformance``
#: admits them to the mechanical dimension only then.
GATED_MECHANICAL_CHECKS = frozenset(
    {"OUT-COORD-PRESERVED", "OUT-BASIS-NOT-STRENGTHENED"}
)


def lint_output(
    ctx: Context,
    *,
    output_path: str | Path,
    trace_document: Mapping[str, Any],
    ir_document: Mapping[str, Any],
    policy_document: Mapping[str, Any],
    receipt_document: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Lint a rendered bundle and return a sealed report."""
    path = Path(output_path)
    binding = bind_file(path)
    raw = path.read_bytes()
    text = raw.decode("utf-8")

    ir = require_valid_ir(ctx, ir_document)
    policy = ctx.policy(policy_document)
    trace = load_trace(ctx, trace_document)

    checks: list[CheckResult] = []
    parse_failed = False
    try:
        parsed = parse_markdown(text, locator=str(path))
        checks.append(
            CheckResult(
                "OUT-MARKDOWN-PARSE",
                "The document parses with a real Markdown parser",
                Status.PASS,
                f"{len(parsed.blocks)} top-level block(s) parsed by {parser_version()}",
                "ATS-1 14.4, 16.3",
            )
        )
    except ParseError as exc:
        parse_failed = True
        parsed = ParsedDocument(text=text, lines=text.split("\n"))
        checks.append(
            CheckResult(
                "OUT-MARKDOWN-PARSE",
                "The document parses with a real Markdown parser",
                Status.FAIL,
                f"{exc} (line {exc.line})" if exc.line else str(exc),
                "ATS-1 14.4, 16.3",
            )
        )

    checks.insert(0, _out_bytes(binding, trace, ir))
    checks.append(_out_constructs(parsed))
    checks.append(_out_markers(parsed, trace, parse_failed))
    checks.append(_out_trace_schema(trace, ir, policy))
    checks.append(_out_block_hashes(parsed, trace))
    checks.append(_out_ir_refs(ir, trace))
    coverage, coverage_check = _out_material_coverage(ir, trace)
    checks.append(coverage_check)
    checks.append(_out_unknown_refs(ir, trace, coverage))
    checks.append(_out_block_order(parsed, trace))
    checks.append(_out_profile_sections(ir, trace, parsed))

    surface = run_surface_checks(ctx, ir, parsed, trace) if not parse_failed else SurfaceReport()
    for check_id, (title, spec_ref) in SURFACE_CHECK_SPECS.items():
        checks.append(_surface_check(check_id, title, spec_ref, surface, parse_failed))

    p0_results, p0_check = _out_p0_exact(ir, trace, parsed)
    checks.append(p0_check)
    p1_results, p1_check = _out_p1_declared(ir, trace)
    checks.append(p1_check)
    checks.append(_out_coord_preserved(ir, trace, parsed))
    checks.append(_out_basis_not_strengthened(ctx, ir, trace, parsed, policy))
    checks.append(_out_policy_exceptions(ctx, policy, trace))
    dispositions, disposition_check = _out_finding_dispositions(receipt_document)
    checks.append(disposition_check)

    conformance, rationale = _compute_conformance(checks, ir, policy, coverage)
    checks.append(_out_conformance_vector(conformance))
    receipt_check, receipt_detail = _out_receipt(ctx, receipt_document, binding, ir, policy)
    checks.append(receipt_check)

    return _build_report(
        ctx,
        ir=ir,
        policy=policy,
        trace=trace,
        binding=binding,
        checks=checks,
        surface=surface,
        parsed=parsed,
        coverage=coverage,
        p0_results=p0_results,
        p1_results=p1_results,
        dispositions=dispositions,
        receipt_detail=receipt_detail,
        conformance=conformance,
        rationale=rationale,
    )


# -- individual checks ------------------------------------------------------


def _out_bytes(binding, trace: OutputTrace, ir: IrDocument) -> CheckResult:
    problems: list[str] = []
    if binding.content_sha256 != trace.output_sha256:
        problems.append(
            f"the document hashes to {binding.content_sha256}, the trace declares "
            f"{trace.output_sha256}"
        )
    if ir.ir_sha256 != trace.ir_sha256:
        problems.append(
            f"the IR canonicalizes to {ir.ir_sha256}, the trace declares {trace.ir_sha256}"
        )
    if trace.artifact_id != ir.artifact_id:
        problems.append(
            f"the trace binds artifact {trace.artifact_id!r}, the IR is {ir.artifact_id!r}"
        )
    return CheckResult(
        "OUT-BYTES",
        "Output and IR hashes match the trace",
        Status.FAIL if problems else Status.PASS,
        "; ".join(problems) if problems else
        f"{binding.byte_length} byte(s) hash to {binding.content_sha256}",
        "ATS-1 14.2, 14.13, Appendix C",
    )


def _out_constructs(parsed: ParsedDocument) -> CheckResult:
    if parsed.unsupported:
        return CheckResult(
            "OUT-CONSTRUCTS",
            "Unsupported Markdown constructs are identified",
            Status.REVIEW_REQUIRED,
            "; ".join(f"line {u.line}: {u.construct} — {u.detail}" for u in parsed.unsupported[:6]),
            "ATS-1 16.3",
        )
    untested = missing_required_constructs(parsed)
    return CheckResult(
        "OUT-CONSTRUCTS",
        "Unsupported Markdown constructs are identified",
        Status.PASS,
        f"every construct present is evaluated; {len(untested)} of the constructs Section 16.3 "
        f"names are absent from this document ({', '.join(untested) or 'none'})",
        "ATS-1 16.3",
    )


def _out_markers(parsed: ParsedDocument, trace: OutputTrace, parse_failed: bool) -> CheckResult:
    if parse_failed:
        return CheckResult(
            "OUT-MARKERS",
            "Source-map markers are intact and unique",
            Status.UNAVAILABLE,
            "the document did not parse, so markers could not be located",
            "ATS-1 14.4",
        )
    problems: list[str] = []
    duplicates = parsed.duplicate_markers()
    if duplicates:
        problems.append(f"duplicate markers: {', '.join(duplicates)}")
    rendered = set(parsed.markers_in_order())
    declared = {b.block_id for b in trace.blocks}
    missing = sorted(declared - rendered)
    extra = sorted(rendered - declared)
    if missing:
        problems.append(f"declared in the trace but absent from the document: {', '.join(missing)}")
    if extra:
        problems.append(f"present in the document but absent from the trace: {', '.join(extra)}")
    for line_no, line in enumerate(parsed.lines, start=1):
        stripped = line.strip()
        if stripped.startswith("<!--") and "ats:block" in stripped:
            if not (MARKER_OPEN.match(stripped) or MARKER_CLOSE.match(stripped)):
                problems.append(f"line {line_no}: malformed ATS marker {stripped!r}")
    return CheckResult(
        "OUT-MARKERS",
        "Source-map markers are intact and unique",
        Status.FAIL if problems else Status.PASS,
        "; ".join(problems) if problems else f"{len(rendered)} marker(s) match the trace exactly",
        "ATS-1 14.4",
    )


def _out_trace_schema(trace: OutputTrace, ir: IrDocument, policy: PolicySnapshot) -> CheckResult:
    problems: list[str] = []
    if trace.policy_snapshot_id != policy.snapshot_id:
        problems.append(
            f"trace binds policy {trace.policy_snapshot_id!r}, the supplied snapshot is "
            f"{policy.snapshot_id!r}"
        )
    if trace.policy_sha256 != policy.declared_sha256:
        problems.append(
            f"trace binds policy hash {trace.policy_sha256}, the snapshot declares "
            f"{policy.declared_sha256}"
        )
    ok, declared, recomputed = verify_seal(dict(trace.raw))
    if not ok:
        problems.append(f"trace_sha256 {declared} does not match its canonical bytes ({recomputed})")
    if set(trace.profiles) - set(ir.profiles):
        problems.append(
            f"trace declares profiles {sorted(set(trace.profiles) - set(ir.profiles))} the IR "
            "does not carry"
        )
    return CheckResult(
        "OUT-TRACE-SCHEMA",
        "The trace validates and binds the same policy and IR",
        Status.FAIL if problems else Status.PASS,
        "; ".join(problems) if problems else
        f"trace {recomputed[:16]}… binds policy {policy.snapshot_id!r} and {len(trace.blocks)} block(s)",
        "ATS-1 6.6, 14.13",
    )


def _out_block_hashes(parsed: ParsedDocument, trace: OutputTrace) -> CheckResult:
    problems: list[str] = []
    for tb in trace.blocks:
        block = parsed.block_by_marker(tb.block_id)
        if block is None:
            continue
        actual = block_text_sha256(block)
        if actual != tb.text_sha256:
            problems.append(
                f"{tb.block_id}: body hashes to {actual[:16]}…, trace declares "
                f"{tb.text_sha256[:16]}…"
            )
    return CheckResult(
        "OUT-BLOCK-HASHES",
        "Each block's declared hash matches its rendered bytes",
        Status.FAIL if problems else Status.PASS,
        "; ".join(problems[:6]) if problems else
        f"{len(trace.blocks)} block hash(es) reproduce from the document bytes",
        "ATS-1 14.2, 16.2",
    )


def _out_ir_refs(ir: IrDocument, trace: OutputTrace) -> CheckResult:
    kinds = ir.object_ids
    requirement_ids = {
        c.requirement["requirement_id"] for c in ir.all_claims() if c.requirement
    }
    forecast_ids = {c.forecast["forecast_id"] for c in ir.all_claims() if c.forecast}
    coordinate_ids = {entry["id"] for entry in ir.stable_coordinates}
    problems: list[str] = []
    for tb in trace.blocks:
        for field, kind, object_id in tb.references():
            if kind == "coordinate":
                if object_id not in coordinate_ids:
                    problems.append(
                        f"{tb.block_id}.{field}: {object_id!r} is not a declared stable "
                        "coordinate"
                    )
                continue
            if kind == "requirement":
                if object_id not in requirement_ids:
                    problems.append(f"{tb.block_id}.{field}: {object_id!r} is not a requirement id")
                continue
            if kind == "forecast":
                if object_id not in forecast_ids:
                    problems.append(f"{tb.block_id}.{field}: {object_id!r} is not a forecast id")
                continue
            actual = kinds.get(object_id)
            if actual is None:
                problems.append(f"{tb.block_id}.{field}: {object_id!r} is not an object in the IR")
            elif actual != kind:
                problems.append(
                    f"{tb.block_id}.{field}: {object_id!r} is a {actual}, not a {kind}"
                )
    return CheckResult(
        "OUT-IR-REFS",
        "Every block reference resolves to an IR object of the right kind",
        Status.FAIL if problems else Status.PASS,
        "; ".join(problems[:6]) if problems else
        f"{len(trace.declared_object_ids())} referenced object(s) resolve",
        "ATS-1 14.4",
    )


def _material_object_ids(ir: IrDocument) -> set[str]:
    out: set[str] = set()
    for claim in ir.all_claims():
        if claim.material:
            out.add(claim.claim_id)
            if claim.requirement:
                out.add(claim.requirement["requirement_id"])
            if claim.forecast:
                out.add(claim.forecast["forecast_id"])
    for relation in ir.relations.values():
        if relation.material:
            out.add(relation.relation_id)
    for evidence in ir.evidence.values():
        out.add(evidence.evidence_id)
    return out


def _out_material_coverage(ir: IrDocument, trace: OutputTrace) -> tuple[dict[str, Any], CheckResult]:
    material = _material_object_ids(ir)
    declared = trace.declared_object_ids()
    authorized = {u["object_id"] for u in trace.unmapped}
    unmapped = sorted(material - declared - authorized)
    coverage = {
        "blocks_declared": len(trace.blocks),
        "material_ir_objects": len(material),
        "material_ir_objects_mapped": len(material & declared),
        "unmapped_material_ir_objects": unmapped,
        "authorized_omissions": sorted(authorized & material),
    }
    if unmapped:
        return coverage, CheckResult(
            "OUT-MATERIAL-COVERAGE",
            "Every material IR object is mapped or authorized as omitted",
            Status.FAIL,
            f"{len(unmapped)} material object(s) appear in no block and carry no authorized "
            f"omission: {', '.join(unmapped[:8])}",
            "ATS-1 11.7, 11.8",
        )
    for entry in trace.unmapped:
        if entry["reason"] != "not_material" and not entry.get("authorization_ref"):
            return coverage, CheckResult(
                "OUT-MATERIAL-COVERAGE",
                "Every material IR object is mapped or authorized as omitted",
                Status.FAIL,
                f"omission of {entry['object_id']!r} claims reason {entry['reason']!r} with no "
                "authorization reference (spec 11.4)",
                "ATS-1 11.4, 11.7, 11.8",
            )
    return coverage, CheckResult(
        "OUT-MATERIAL-COVERAGE",
        "Every material IR object is mapped or authorized as omitted",
        Status.PASS,
        f"{len(material & declared)} of {len(material)} material object(s) are mapped; "
        f"{len(authorized & material)} carry an authorized omission",
        "ATS-1 11.7, 11.8",
    )


def _out_unknown_refs(ir: IrDocument, trace: OutputTrace, coverage: dict[str, Any]) -> CheckResult:
    known = set(ir.object_ids)
    known |= {c.requirement["requirement_id"] for c in ir.all_claims() if c.requirement}
    known |= {c.forecast["forecast_id"] for c in ir.all_claims() if c.forecast}
    known |= {entry["id"] for entry in ir.stable_coordinates}
    unknown = sorted(trace.declared_object_ids() - known)
    coverage["unknown_ir_references"] = unknown
    return CheckResult(
        "OUT-UNKNOWN-REFS",
        "No block references an object absent from the IR",
        Status.FAIL if unknown else Status.PASS,
        f"unknown references: {', '.join(unknown[:8])}" if unknown else
        "every referenced identifier exists in the IR",
        "ATS-1 11.7",
    )


def _out_block_order(parsed: ParsedDocument, trace: OutputTrace) -> CheckResult:
    problems: list[str] = []
    ordinals = [b.ordinal for b in trace.blocks]
    if ordinals != sorted(ordinals):
        problems.append("trace ordinals are not in ascending order")
    if ordinals and ordinals != list(range(len(ordinals))):
        problems.append(f"trace ordinals are not dense: {ordinals}")
    rendered = parsed.markers_in_order()
    declared = [b.block_id for b in sorted(trace.blocks, key=lambda b: b.ordinal)]
    if rendered and declared and rendered != declared:
        problems.append(
            f"document order {rendered[:5]} does not match trace order {declared[:5]}"
        )
    return CheckResult(
        "OUT-BLOCK-ORDER",
        "Block ordering is dense, ascending, and matches the document",
        Status.FAIL if problems else Status.PASS,
        "; ".join(problems) if problems else f"{len(ordinals)} block(s) in stable document order",
        "ATS-1 14.4, 16.2",
    )


#: Display roles that satisfy each profile's structural obligations.
PROFILE_REQUIRED_ROLES: dict[str, tuple[str, ...]] = {
    # Section 9.2.12 canonical ASSESS rendering.
    "ASSESS": (
        "question",
        "key_judgment",
        "confidence",
        "supporting_evidence",
        "contrary_evidence",
        "assumption",
        "boundary",
        "update_indicator",
        "recommendation",
    ),
    # Section 9.3.5 canonical statement order plus 9.3.9 and 9.3.15.
    "SPECIFY": ("requirement", "acceptance_criterion", "authority"),
}


def _out_profile_sections(
    ir: IrDocument, trace: OutputTrace, parsed: ParsedDocument
) -> CheckResult:
    roles = {b.display_role for b in trace.blocks}
    missing: list[str] = []
    evaluated: list[str] = []
    for profile in trace.profiles:
        required = PROFILE_REQUIRED_ROLES.get(profile)
        if required is None:
            continue
        evaluated.append(profile)
        missing.extend(f"{profile}:{r}" for r in required if r not in roles)
    if not evaluated:
        return CheckResult(
            "OUT-PROFILE-SECTIONS",
            "Profile-required sections are rendered",
            Status.UNAVAILABLE,
            f"no profile among {list(trace.profiles)} has declared structural obligations here "
            "(spec 9.5)",
            "ATS-1 9.2.12, 9.3.5",
        )
    return CheckResult(
        "OUT-PROFILE-SECTIONS",
        "Profile-required sections are rendered",
        Status.FAIL if missing else Status.PASS,
        f"missing display roles: {', '.join(missing)}" if missing else
        f"{', '.join(evaluated)} structural obligations are satisfied by {len(roles)} display role(s)",
        "ATS-1 9.2.12, 9.3.5",
    )


def _surface_check(
    check_id: str, title: str, spec_ref: str, surface: SurfaceReport, parse_failed: bool
) -> CheckResult:
    if parse_failed:
        return CheckResult(
            check_id, title, Status.UNAVAILABLE, "the document did not parse", spec_ref
        )
    issues = surface.for_check(check_id)
    inspected = surface.inspected.get(check_id, 0)
    skipped = surface.skipped.get(check_id, [])
    suffix = (
        f"; {len(skipped)} block(s) exempt as marked quoted or code content: "
        f"{', '.join(skipped[:5])} (spec 5.6)"
        if skipped
        else ""
    )
    if issues:
        return CheckResult(
            check_id,
            title,
            Status.FAIL,
            "; ".join(f"{i.block_id or f'line {i.line}'}: {i.detail}" for i in issues[:6]) + suffix,
            spec_ref,
        )
    if inspected == 0:
        return CheckResult(
            check_id, title, Status.NOT_APPLICABLE, f"no block to inspect{suffix}", spec_ref
        )
    return CheckResult(
        check_id, title, Status.PASS, f"{inspected} block(s) inspected{suffix}", spec_ref
    )


def _out_p0_exact(
    ir: IrDocument, trace: OutputTrace, parsed: ParsedDocument
) -> tuple[list[dict[str, Any]], CheckResult]:
    results: list[dict[str, Any]] = []
    for tb in trace.blocks:
        block = parsed.block_by_marker(tb.block_id)
        for p0 in tb.p0_fields:
            entry: dict[str, Any] = {
                "field_ref": p0["field_ref"],
                "block_id": tb.block_id,
                "rendered_value": str(p0.get("rendered", "")),
            }
            try:
                source = ir_value_at(ir, p0["ir_pointer"])
            except UsageError as exc:
                entry["status"] = "unavailable"
                entry["detail"] = str(exc)
                results.append(entry)
                continue
            entry["source_value"] = _as_text(source)
            rendered = str(p0.get("rendered", ""))
            if entry["source_value"] != rendered:
                entry["status"] = "changed_unauthorized"
                entry["detail"] = (
                    f"the IR value at {p0['ir_pointer']} is {entry['source_value']!r} but the "
                    f"block declares it rendered as {rendered!r}"
                )
            elif block is None:
                entry["status"] = "unavailable"
                entry["detail"] = "the declaring block is absent from the document"
            elif rendered not in block.text:
                entry["status"] = "changed_unauthorized"
                entry["detail"] = (
                    f"the block does not contain the exact P0 value {rendered!r} it declares"
                )
            else:
                entry["status"] = "preserved"
            results.append(entry)
    bad = [r for r in results if r["status"] == "changed_unauthorized"]
    unavailable = [r for r in results if r["status"] == "unavailable"]
    if bad:
        status, detail = Status.FAIL, "; ".join(r["detail"] for r in bad[:6])
    elif unavailable:
        status, detail = Status.UNAVAILABLE, "; ".join(r["detail"] for r in unavailable[:6])
    elif not results:
        status, detail = (
            Status.REVIEW_REQUIRED,
            "no block declares a P0 field, so exact rendering of protected values is undeclared "
            "rather than verified (spec 11.3.1)",
        )
    else:
        status, detail = Status.PASS, f"{len(results)} declared P0 value(s) render exactly"
    return results, CheckResult(
        "OUT-P0-EXACT",
        "Declared P0 values render exactly",
        status,
        detail,
        "ATS-1 11.3.1, 11.6",
    )


def _as_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _out_p1_declared(ir: IrDocument, trace: OutputTrace) -> tuple[list[dict[str, Any]], CheckResult]:
    declared: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for tb in trace.blocks:
        for rel in tb.p1_relations:
            declared.setdefault(rel["relation_id"], []).append((tb.block_id, rel))
    results: list[dict[str, Any]] = []
    for relation in sorted(ir.relations.values(), key=lambda r: r.relation_id):
        if not relation.material:
            continue
        entries = declared.get(relation.relation_id, [])
        if not entries:
            results.append(
                {
                    "relation_id": relation.relation_id,
                    "status": "missing",
                    "detail": (
                        f"material relation {relation.type!r} from {relation.source_id!r} to "
                        f"{relation.target_id!r} is declared by no rendered block"
                    ),
                }
            )
            continue
        mismatched = [
            block_id
            for block_id, rel in entries
            if rel["type"] != relation.type
        ]
        if mismatched:
            results.append(
                {
                    "relation_id": relation.relation_id,
                    "status": "direction_changed",
                    "block_ids": mismatched,
                    "detail": (
                        f"block(s) {', '.join(mismatched)} declare a type other than the IR's "
                        f"{relation.type!r}"
                    ),
                }
            )
            continue
        results.append(
            {
                "relation_id": relation.relation_id,
                "status": "declared",
                "block_ids": [block_id for block_id, _ in entries],
            }
        )
    bad = [r for r in results if r["status"] in ("missing", "direction_changed")]
    if bad:
        status, detail = Status.FAIL, "; ".join(r["detail"] for r in bad[:6])
    elif not results:
        status, detail = Status.NOT_APPLICABLE, "the IR declares no material relation"
    else:
        status, detail = (
            Status.REVIEW_REQUIRED,
            f"{len(results)} material relation(s) are declared by a rendered block. Declaration "
            "establishes that the block claims the relation, not that the prose realizes it with "
            "the same force and direction; that remains a semantic judgement (spec 11.3.2).",
        )
    return results, CheckResult(
        "OUT-P1-DECLARED",
        "Material P1 relations are declared by a rendered block",
        status,
        detail,
        "ATS-1 11.3.2",
    )


def _out_coord_preserved(
    ir: IrDocument, trace: OutputTrace, parsed: ParsedDocument
) -> CheckResult:
    """Draft.2 D-C: every declared stable coordinate survives into the rendering.

    Spec 7.17 makes stable semantic coordinates P0 (11.3.1): each id declared in
    the IR's ``stable_coordinates`` block must be referenced by at least one
    output block (via any reference field, including the trace's ``coordinates``
    field) and that block's body text must contain the exact id string. A
    coordinate referenced but rendered with a different string is altered; a
    coordinate referenced by no block is dropped. With no block declared the
    check is NOT_APPLICABLE and non-required.
    """
    coordinates = list(ir.stable_coordinates)
    if not coordinates:
        return CheckResult(
            "OUT-COORD-PRESERVED",
            "Stable semantic coordinates survive into the rendering",
            Status.NOT_APPLICABLE,
            "the IR declares no stable_coordinates block, so there is no coordinate to "
            "preserve (draft.2 D-C, spec 7.17)",
            "ATS-1 4.23, 7.17, 11.3.1",
            required=False,
        )
    referenced: dict[str, list[TraceBlock]] = {}
    for tb in trace.blocks:
        for _, _, object_id in tb.references():
            referenced.setdefault(object_id, []).append(tb)
    problems: list[str] = []
    unavailable: list[str] = []
    for entry in coordinates:
        cid = entry["id"]
        blocks = referenced.get(cid)
        if not blocks:
            problems.append(
                f"stable coordinate {cid!r} (kind {entry['kind']!r}) is declared in the IR "
                "but appears in no output block's references (dropped)"
            )
            continue
        for tb in blocks:
            block = parsed.block_by_marker(tb.block_id)
            if block is None:
                unavailable.append(
                    f"coordinate {cid!r}: declaring block {tb.block_id} is absent from the "
                    "document, so its rendering is unverifiable"
                )
            elif cid not in block.text:
                problems.append(
                    f"coordinate {cid!r}: block {tb.block_id} references it but its body "
                    "text does not contain the exact id string (altered or dropped from "
                    "the visible text)"
                )
    if problems:
        status, detail = Status.FAIL, "; ".join(problems[:6])
    elif unavailable:
        status, detail = Status.UNAVAILABLE, "; ".join(unavailable[:6])
    else:
        status, detail = Status.PASS, (
            f"{len(coordinates)} declared stable coordinate(s) are referenced by a rendered "
            "block whose body text carries the exact id string"
        )
    return CheckResult(
        "OUT-COORD-PRESERVED",
        "Stable semantic coordinates survive into the rendering",
        status,
        detail,
        "ATS-1 4.23, 7.17, 11.3.1",
    )


#: The deontic upgrades the strengthening check may decide exactly (draft.2
#: directive Section 35.4): the rendered text shows the stronger canonical
#: surface and not the claim's own. Surface forms equal the canonical ids for
#: these three values.
DEONTIC_UPGRADES: dict[str, str] = {"SHOULD": "MUST", "MAY": "MUST"}

#: Deontic surfaces, in strictly increasing obligation strength, used only to
#: recognise *unsupported-but-suspicious* strengthening (MAY\u2192SHOULD and the
#: like). MUST NOT / SHOULD NOT sit on the prohibition axis and CAN / CANNOT /
#: REQUIRED_BY on other axes; none participates in the ordering.
DEONTIC_ORDER: dict[str, int] = {"MAY": 0, "SHOULD": 1, "MUST": 2}

#: Canonical uppercase surfaces that render a value as settled. REQUIRED_BY
#: carries a ``<source>`` placeholder, so it never matches prose literally.
SETTLED_SURFACES: tuple[str, ...] = ("MUST", "MUST NOT", "SHOULD", "SHOULD NOT", "MAY")

#: A rendered numeric probability range, e.g. ``55\u201380%`` (hyphen, en dash,
#: or em dash). Single probabilities are not bands and are never compared.
_RANGE = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*[\u2013\u2014-]\s*(\d+(?:\.\d+)?)\s*%"
)


def _claim_carried_surfaces(claim, lex) -> tuple[set[str], set[str]]:
    """Deontic surfaces and WEP phrases the claim itself legitimately carries.

    A surface the IR records on the claim (its force fields) or that appears in
    the claim's own proposition is not a rendering-side strengthening when the
    block repeats it, so it never triggers a comparison.
    """
    deontic: set[str] = set()
    deontic_id = claim.deontic
    requirement = claim.requirement
    if deontic_id is None and requirement is not None:
        deontic_id = requirement.get("deontic")
    if deontic_id:
        surface = lex.deontic_surfaces.get(deontic_id)
        if surface and surface.isupper():
            deontic.add(surface)
    wep: set[str] = set()
    likelihood = claim.likelihood or {}
    if likelihood.get("kind") == "wep" and likelihood.get("term"):
        term = lex.wep_terms.get(likelihood["term"])
        if term is not None:
            wep.add(term["phrase"])
            display = term.get("display_range")
            if display:
                wep.add(str(display))
    proposition = claim.proposition
    for surface in lex.deontic_surfaces.values():
        if surface.isupper() and contains_exact(proposition, surface):
            deontic.add(surface)
    for phrase in lex.wep_phrases:
        if contains_phrase(proposition, phrase):
            wep.add(phrase)
    return deontic, wep


def _basis_strengthening(claim, basis: str, text: str, lex) -> tuple[list[str], list[str]]:
    """Exact supported strengthening cases, then unsupported-but-suspicious ones.

    Returns ``(decided_failures, review_required)`` for one claim/block pair.
    The exact cases (SHOULD\u2192MUST, MAY\u2192MUST, WEP band mutation,
    unknown\u2192known) are decided; everything else this check can see but cannot
    decide exactly on a material INFERRED/UNAVAILABLE claim is REVIEW_REQUIRED.
    """
    failed: list[str] = []
    review: list[str] = []
    carried_deontic, carried_wep = _claim_carried_surfaces(claim, lex)
    deontic_in_text = {
        s for s in lex.deontic_surfaces.values() if s.isupper() and contains_exact(text, s)
    }
    wep_in_text = {p for p in lex.wep_phrases if contains_phrase(text, p)}

    # 1. SHOULD\u2192MUST / MAY\u2192MUST (exact, any basis value).
    deontic_id = claim.deontic
    requirement = claim.requirement
    if deontic_id is None and requirement is not None:
        deontic_id = requirement.get("deontic")
    upgrade = DEONTIC_UPGRADES.get(deontic_id or "")
    if upgrade is not None and contains_exact(text, upgrade) and not contains_exact(
        text, deontic_id
    ):
        failed.append(
            f"claim {claim.claim_id!r} declares deontic {deontic_id!r} but the block renders "
            f"{upgrade!r} without {deontic_id!r}, strengthening the obligation"
        )

    # 2. WEP band mutation (exact): a canonical band different from the claim's,
    #    or a numeric probability range with different bounds.
    likelihood = claim.likelihood or {}
    if likelihood.get("kind") == "wep" and likelihood.get("term"):
        term = lex.wep_terms.get(likelihood["term"])
        if term is not None:
            own_phrase = term["phrase"]
            lower, upper, _ = lex.interval_for(likelihood["term"])
            band = (round(lower * 100), round(upper * 100))
            own_display = str(term.get("display_range", ""))
            for phrase in sorted(wep_in_text - carried_wep):
                if phrase != own_phrase:
                    other = lex.wep_phrases.get(phrase)
                    suffix = (
                        f" ({lex.display_range(other)})" if other else ""
                    )
                    failed.append(
                        f"claim {claim.claim_id!r} declares band {own_phrase!r} "
                        f"({lex.display_range(likelihood['term'])}); the block renders "
                        f"{phrase!r}{suffix} instead"
                    )
            ranges = [
                (round(float(a) * 1), round(float(b) * 1))
                for a, b in _RANGE.findall(text)
            ]
            if band not in ranges and ranges:
                failed.append(
                    f"claim {claim.claim_id!r} declares band {own_phrase!r} "
                    f"({own_display}); the block renders probability range(s) "
                    f"{', '.join(f'{a}-{b}%' for a, b in ranges)} with different bounds"
                )

    # 3. unknown\u2192known (exact): basis UNAVAILABLE rendered with any settled
    #    normative surface the claim does not itself carry. Capability surfaces
    #    (CAN/CANNOT) are not settlement markers, so they never fire this case.
    if basis == "UNAVAILABLE":
        for surface in sorted((deontic_in_text - carried_deontic) & set(SETTLED_SURFACES)):
            failed.append(
                f"claim {claim.claim_id!r} has basis UNAVAILABLE, so its value cannot be "
                f"established; the block renders it as settled with {surface!r}"
            )
        if not likelihood.get("term"):
            for phrase in sorted(wep_in_text - carried_wep):
                failed.append(
                    f"claim {claim.claim_id!r} has basis UNAVAILABLE, so its value cannot be "
                    f"established; the block renders it as settled with band {phrase!r}"
                )

    # 4. Unsupported-but-suspicious strengthening on a material INFERRED/
    #    UNAVAILABLE claim: a stronger deontic surface, or a band where the IR
    #    records none, that no exact case decided.
    if claim.material and basis in ("INFERRED", "UNAVAILABLE"):
        own_strength = DEONTIC_ORDER.get(
            next(iter(carried_deontic & set(DEONTIC_ORDER)), "")
        )
        for surface in sorted(deontic_in_text - carried_deontic):
            strength = DEONTIC_ORDER.get(surface)
            if strength is not None and (own_strength is None or strength > own_strength):
                review.append(
                    f"claim {claim.claim_id!r} has basis {basis!r} but the block renders "
                    f"{surface!r}, which is not among the exactly-decidable upgrades "
                    "(SHOULD/MAY\u2192MUST)"
                )
        if not likelihood.get("term") and not (wep_in_text - carried_wep) and _RANGE.search(
            text
        ):
            review.append(
                f"claim {claim.claim_id!r} has basis {basis!r} and the IR records no "
                "likelihood band, but the block renders a numeric probability range"
            )
    return failed, review


def _out_basis_not_strengthened(
    ctx: Context,
    ir: IrDocument,
    trace: OutputTrace,
    parsed: ParsedDocument,
    policy: PolicySnapshot,
) -> CheckResult:
    """Draft.2 D-F: a rendered value never exceeds its declared basis's force.

    Implements only the mechanically exact supported cases (draft.2 directive
    Section 35.4), reusing the deontic and WEP vocabularies of the surface
    checks: SHOULD\u2192MUST, MAY\u2192MUST, WEP band mutation (a band shown with
    bounds different from the IR's), and unknown\u2192known (a claim whose basis is
    UNAVAILABLE rendered with a force surface the IR does not itself carry). A
    material claim whose basis is INFERRED/UNAVAILABLE and whose block carries a
    strengthening this check cannot decide exactly is REVIEW_REQUIRED, never
    PASS (ADR-0002). TRANSFORM-only; no basis declarations is NOT_APPLICABLE.
    """
    if "TRANSFORM" not in policy.profiles:
        return CheckResult(
            "OUT-BASIS-NOT-STRENGTHENED",
            "Rendered semantic force does not exceed the declared basis",
            Status.NOT_APPLICABLE,
            "TRANSFORM is not among the active profiles, so this rendering is not evaluated "
            "as a source-to-output transformation (spec 15.4)",
            "ATS-1 4.25, 7.19, 15.4",
            required=False,
        )

    lex = ctx.lexicon
    basis_values: dict[str, str] = {}
    for claim in ir.all_claims():
        basis = claim.data.get("semantic_basis")
        requirement = claim.requirement
        if basis is None and not (requirement and requirement.get("semantic_basis")):
            continue
        value = (basis or {}).get("basis")
        if value is None and requirement:
            value = requirement.get("semantic_basis", {}).get("basis")
        basis_values[claim.claim_id] = value or ""
    if not basis_values:
        return CheckResult(
            "OUT-BASIS-NOT-STRENGTHENED",
            "Rendered semantic force does not exceed the declared basis",
            Status.NOT_APPLICABLE,
            "the IR declares no semantic_basis, so no basis constraint exists to enforce "
            "(draft.2 D-F, spec 7.5)",
            "ATS-1 4.25, 7.19",
            required=False,
        )

    block_by_claim: dict[str, list[TraceBlock]] = {}
    block_by_requirement: dict[str, list[TraceBlock]] = {}
    for tb in trace.blocks:
        for oid in tb.data.get("claim_ids", ()):
            block_by_claim.setdefault(oid, []).append(tb)
        for oid in tb.data.get("requirement_ids", ()):
            block_by_requirement.setdefault(oid, []).append(tb)

    failed: list[str] = []
    review: list[str] = []
    inspected = 0
    for claim in ir.all_claims():
        basis = basis_values.get(claim.claim_id)
        if basis is None:
            continue
        blocks = list(block_by_claim.get(claim.claim_id, ()))
        requirement = claim.requirement
        if requirement is not None:
            blocks += block_by_requirement.get(requirement.get("requirement_id", ""), ())
        if not blocks:
            continue
        inspected += 1
        for tb in blocks:
            block = parsed.block_by_marker(tb.block_id)
            if block is None:
                continue
            problems, reviews = _basis_strengthening(claim, basis, block.text, lex)
            failed.extend(f"{tb.block_id}: {d}" for d in problems)
            review.extend(f"{tb.block_id}: {d}" for d in reviews)

    if failed:
        status, detail = Status.FAIL, "; ".join(failed[:6])
    elif review:
        status, detail = Status.REVIEW_REQUIRED, (
            "; ".join(review[:6])
            + ". These strengthenings are not among the mechanically exact supported cases, "
            "so they are surfaced for review rather than decided (ADR-0002, spec 7.19)."
        )
    else:
        status, detail = Status.PASS, (
            f"{inspected} claim(s) with a declared basis render no supported strengthening "
            "on any block that references them"
        )
    return CheckResult(
        "OUT-BASIS-NOT-STRENGTHENED",
        "Rendered semantic force does not exceed the declared basis",
        status,
        detail,
        "ATS-1 4.25, 7.19, 11.3.1",
    )


def _out_policy_exceptions(ctx: Context, policy: PolicySnapshot, trace: OutputTrace) -> CheckResult:
    diagnostics = policy.exception_diagnostics(ctx.now)
    bad = [d for d in diagnostics if d.status != "active"]
    if bad:
        return CheckResult(
            "OUT-POLICY-EXCEPTIONS",
            "No unrecorded or invalid policy exception is in play",
            Status.FAIL,
            "; ".join(f"{d.exception_id}: {d.status} — {d.detail}" for d in bad[:6]),
            "ATS-1 6.3",
        )
    unauthorized = [
        u
        for u in trace.unmapped
        if u["reason"] == "policy_exception"
        and u.get("authorization_ref") not in {e.exception_id for e in policy.exceptions}
    ]
    if unauthorized:
        return CheckResult(
            "OUT-POLICY-EXCEPTIONS",
            "No unrecorded or invalid policy exception is in play",
            Status.FAIL,
            "; ".join(
                f"{u['object_id']}: cites exception {u.get('authorization_ref')!r} that the "
                "policy snapshot does not contain"
                for u in unauthorized[:6]
            ),
            "ATS-1 6.3",
        )
    return CheckResult(
        "OUT-POLICY-EXCEPTIONS",
        "No unrecorded or invalid policy exception is in play",
        Status.PASS,
        f"{len(diagnostics)} exception(s) in the snapshot are active and correctly scoped",
        "ATS-1 6.3",
    )


def _out_finding_dispositions(
    receipt: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], CheckResult]:
    if receipt is None:
        return (
            {"surfaced": 0, "dispositioned": 0, "undispositioned": []},
            CheckResult(
                "OUT-FINDING-DISPOSITIONS",
                "Every surfaced finding carries a disposition",
                Status.UNAVAILABLE,
                "no receipt was supplied, so no disposition record exists to check (spec 15.3)",
                "ATS-1 13.6, 15.3",
            ),
        )
    summary = receipt.get("semantic_summary", {})
    proposed = int(summary.get("proposed", 0))
    settled = sum(
        int(summary.get(k, 0)) for k in ("accepted", "rejected", "waived", "abstained")
    )
    unresolved = int(summary.get("unresolved", 0))
    dispositions = {
        "surfaced": proposed,
        "dispositioned": settled,
        "undispositioned": (
            [f"{unresolved} unresolved finding(s) recorded in the receipt"] if unresolved else []
        ),
    }
    if unresolved:
        status, detail = (
            Status.FAIL,
            f"{unresolved} surfaced finding(s) remain undispositioned; Section 15.3 forbids "
            "semantic-review conformance while any surfaced finding is undispositioned",
        )
    elif proposed and settled < proposed:
        status, detail = (
            Status.FAIL,
            f"{proposed} finding(s) proposed but only {settled} dispositioned",
        )
    else:
        status, detail = (
            Status.PASS,
            f"{settled} of {proposed} surfaced finding(s) carry a disposition",
        )
    return dispositions, CheckResult(
        "OUT-FINDING-DISPOSITIONS",
        "Every surfaced finding carries a disposition",
        status,
        detail,
        "ATS-1 13.6, 15.3",
    )


def _out_conformance_vector(conformance: Mapping[str, str]) -> CheckResult:
    rendered = ", ".join(f"{k}={v}" for k, v in conformance.items())
    return CheckResult(
        "OUT-CONFORMANCE-VECTOR",
        "The conformance vector is computed per dimension without aggregation",
        Status.PASS,
        f"{rendered}; no dimension is averaged into another (spec 5.2, 15.6)",
        "ATS-1 5.2, 15.6, 15.7",
    )


def _out_receipt(
    ctx: Context,
    receipt: Mapping[str, Any] | None,
    binding,
    ir: IrDocument,
    policy: PolicySnapshot,
) -> tuple[CheckResult, dict[str, Any]]:
    if receipt is None:
        return (
            CheckResult(
                "OUT-RECEIPT",
                "The candidate receipt is well formed and binds this bundle",
                Status.NOT_APPLICABLE,
                "no receipt was supplied to this run",
                "ATS-1 14.13, 16.12",
            ),
            {"status": "NOT_APPLICABLE"},
        )
    from .receipt import verify_receipt

    verification = verify_receipt(
        ctx, receipt, ir_document=ir.raw, output_sha256=binding.content_sha256, policy=policy
    )
    status = Status[verification["status"]] if verification["status"] in Status.__members__ else Status.FAIL
    return (
        CheckResult(
            "OUT-RECEIPT",
            "The candidate receipt is well formed and binds this bundle",
            status,
            verification.get("detail", ""),
            "ATS-1 14.13, 16.12",
        ),
        verification,
    )


# -- conformance ------------------------------------------------------------


def _compute_conformance(
    checks: Sequence[CheckResult],
    ir: IrDocument,
    policy: PolicySnapshot,
    coverage: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    by_id = {c.check_id: c for c in checks}

    # Draft.2 gated checks (OUT-COORD-PRESERVED, OUT-BASIS-NOT-STRENGTHENED)
    # join the mechanical dimension only when the IR declares the surfaces they
    # protect; the checks set ``required`` accordingly (see
    # GATED_MECHANICAL_CHECKS).
    active_gated = {
        c.check_id for c in checks if c.check_id in GATED_MECHANICAL_CHECKS and c.required
    }
    mech_scope = MECHANICAL_CHECKS | active_gated
    mech_failed = [
        c for c in checks if c.check_id in mech_scope and c.status is Status.FAIL
    ]
    mech_unavailable = [
        c for c in checks if c.check_id in mech_scope and c.status is Status.UNAVAILABLE
    ]
    surface_failed = [
        c for c in checks if c.check_id in SURFACE_CHECK_SPECS and c.status is Status.FAIL
    ]
    if mech_failed or surface_failed:
        mechanical = "FAIL"
        mech_why = "required deterministic checks failed: " + ", ".join(
            c.check_id for c in mech_failed + surface_failed
        )
    elif mech_unavailable:
        mechanical = "UNAVAILABLE"
        mech_why = (
            "a required deterministic check could not execute, which is UNAVAILABLE and not PASS "
            "(spec 5.4): " + ", ".join(c.check_id for c in mech_unavailable)
        )
    else:
        mechanical = "PASS"
        mech_why = (
            "output bytes, markers, block hashes, references, ordering, declared P0 values, "
            "every applicable surface rule, and the draft.2 coordinate/basis checks the IR "
            "declares ("
            + (", ".join(sorted(active_gated)) if active_gated else "none gated")
            + ") executed and passed"
        )

    profile_check = by_id["OUT-PROFILE-SECTIONS"]
    coverage_check = by_id["OUT-MATERIAL-COVERAGE"]
    if profile_check.status is Status.FAIL or coverage_check.status is Status.FAIL:
        profile = "FAIL"
        prof_why = f"{profile_check.detail}; {coverage_check.detail}"
    elif profile_check.status is Status.UNAVAILABLE:
        profile = "UNAVAILABLE"
        prof_why = profile_check.detail
    else:
        profile = "PASS"
        prof_why = (
            f"{profile_check.detail}; {coverage_check.detail}. Structural obligations are "
            "satisfied at the rendering level; the IR linter owns semantic slot completeness."
        )

    semantic = "UNAVAILABLE"
    semantic_why = (
        "Mapping a block to an IR object establishes that the renderer declared the object, not "
        "that the prose realizes it with the same meaning and force. Section 15.3 requires every "
        "surfaced finding to be dispositioned by an authorized human or a promoted detector, and "
        "Section 14.11 assigns final semantic acceptance to an external authority. This "
        "implementation holds neither, so semantic_review is never PASS here."
    )

    transform_active = "TRANSFORM" in policy.profiles
    if not transform_active:
        preservation = "NOT_APPLICABLE"
        pres_why = (
            "TRANSFORM is not among the active profiles, so this rendering is not evaluated as a "
            "source-to-output transformation (spec 15.4)"
        )
    else:
        preservation = "UNAVAILABLE"
        pres_why = (
            "TRANSFORM is active but no source IR, retention contract, or authorization set was "
            "supplied. ATS-PRES-001 and ATS-PRES-002 are unwaivable (spec 6.4), so preservation "
            "MUST NOT be reported as PASS while they cannot be evaluated. The declared-P0 and "
            "declared-P1 checks in this report are evidence about one rendering, not a "
            "transformation proof."
        )

    forecasts = [c for c in ir.all_claims() if c.role == "forecast"]
    forecast_why = (
        f"{len(forecasts)} forecast claim(s) rendered. Section 15.5 requires a declared cohort, "
        "resolved outcomes, a scoring rule, reliability analysis, uncertainty estimates, and a "
        "pre-declared evidence threshold; none is implemented."
    )

    return (
        {
            "mechanical": mechanical,
            "profile": profile,
            "semantic_review": semantic,
            "preservation": preservation,
            "forecast_calibration": "INSUFFICIENT_EVIDENCE",
        },
        {
            "mechanical": mech_why,
            "profile": prof_why,
            "semantic_review": semantic_why,
            "preservation": pres_why,
            "forecast_calibration": forecast_why,
        },
    )


def _build_report(
    ctx: Context,
    *,
    ir: IrDocument,
    policy: PolicySnapshot,
    trace: OutputTrace,
    binding,
    checks: Sequence[CheckResult],
    surface: SurfaceReport,
    parsed: ParsedDocument,
    coverage: dict[str, Any],
    p0_results: list[dict[str, Any]],
    p1_results: list[dict[str, Any]],
    dispositions: dict[str, Any],
    receipt_detail: dict[str, Any],
    conformance: dict[str, str],
    rationale: dict[str, str],
) -> dict[str, Any]:
    from ..rules.results import RESULT_STATUSES

    by_status = dict.fromkeys(RESULT_STATUSES, 0)
    for check in checks:
        by_status[str(check.status)] += 1

    coverage["blocks_found"] = len(list(parsed.markers_in_order()))
    coverage.setdefault("unknown_ir_references", [])

    report: dict[str, Any] = {
        "schema_version": "ats.output_lint_report.v1",
        "report_id": f"outlint:{ir.artifact_id}:{binding.content_sha256[:16]}",
        "artifact_id": ir.artifact_id,
        "output_sha256": binding.content_sha256,
        "trace_sha256": trace.raw["trace_sha256"],
        "ir_sha256": ir.ir_sha256,
        "policy_snapshot_id": policy.snapshot_id,
        "policy_sha256": policy.declared_sha256,
        "spec_version": ctx.spec_version,
        "profiles": list(trace.profiles),
        "implementation": {**ctx.implementation, "parser_version": parser_version()},
        "checks": [c.to_dict() for c in checks],
        "rule_results": [],
        "findings": [],
        "block_coverage": coverage,
        "p0_checks": p0_results,
        "p1_checks": p1_results,
        "finding_dispositions": dispositions,
        "summary": {
            "checks_total": len(checks),
            "by_status": by_status,
            "required_failed": sum(
                1 for c in checks if c.required and c.status is Status.FAIL
            ),
            "required_unavailable": sum(
                1 for c in checks if c.required and c.status is Status.UNAVAILABLE
            ),
        },
        "conformance": conformance,
        "conformance_rationale": rationale,
        "created_at": ctx.timestamp(),
    }
    if parsed.unsupported:
        report["unsupported_constructs"] = [u.to_dict() for u in parsed.unsupported]
    if receipt_detail.get("status") != "NOT_APPLICABLE":
        report["receipt_verification"] = {
            k: v
            for k, v in receipt_detail.items()
            if k in ("status", "receipt_id", "declared_sha256", "recomputed_sha256", "detail")
        }
    sealed = seal(report)
    ctx.schemas.validate(sealed, REPORT_SCHEMA_ID)
    return sealed

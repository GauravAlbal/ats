"""The ``ats`` command line.

Exit codes are part of the contract (spec Section 16.11 requires stable
machine-readable output and exit semantics):

===  =========================================================================
0    the command completed and nothing blocks the claim it makes
1    findings, or a conformance dimension is FAIL
2    usage or input error
3    a requested capability is declared unsupported
4    a required check could not execute (UNAVAILABLE)
===  =========================================================================

Every command prints canonical JSON on stdout unless ``--format text`` is
given. A command that is only a scaffold fails with a typed
unsupported-capability result; none pretends to complete work.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import __version__
from .canonical import canonical_text, load_json
from .context import Context
from .errors import (
    AtsError,
    RequiredCheckUnavailableError,
    UnsupportedCapabilityError,
    UsageError,
)

#: Dimensions whose UNAVAILABLE status reflects something that went wrong in
#: THIS run rather than a capability this build never claimed.
#:
#: ``semantic_review`` and ``forecast_calibration`` are structurally
#: unavailable in v0 — the capability declaration says so, and no input could
#: change it. Letting them drive the exit code would make every run exit 4 and
#: destroy the signal. They stay UNAVAILABLE in the vector, where a consumer
#: reads them, and are excluded from the exit code only.
RUN_DEPENDENT_DIMENSIONS = ("mechanical", "profile", "preservation")


def _emit(payload: Any, *, fmt: str, stream=None) -> None:
    stream = stream or sys.stdout
    if fmt == "json":
        print(canonical_text(payload), file=stream)
    else:
        print(_render_text(payload), file=stream)


def _render_text(payload: Any) -> str:
    """A compact human rendering that never hides the vector (spec 5.3)."""
    if not isinstance(payload, Mapping):
        return json.dumps(payload, indent=2, ensure_ascii=False)
    lines: list[str] = []
    if "spec_version" in payload and "profiles" in payload:
        lines.append(f"ATS-1 {payload['spec_version']} / {', '.join(payload['profiles'])}")
    conformance = payload.get("conformance")
    if isinstance(conformance, Mapping):
        labels = {
            "mechanical": "Mechanical",
            "profile": "Profile",
            "semantic_review": "Semantic review",
            "preservation": "Preservation",
            "forecast_calibration": "Forecast calibration",
        }
        for key, label in labels.items():
            lines.append(f"{label}: {conformance.get(key, '?')}")
        rationale = payload.get("conformance_rationale", {})
        for key, label in labels.items():
            why = rationale.get(key)
            if why:
                lines.append(f"  {label.lower()}: {why}")
    if "report_sha256" in payload:
        lines.append(f"Report: ats-sha256:{payload['report_sha256']}")
    summary = payload.get("summary")
    if isinstance(summary, Mapping):
        lines.append("Summary: " + json.dumps(summary, sort_keys=True))
    for check in payload.get("structural_checks", []) or payload.get("checks", []):
        if check.get("status") != "PASS":
            lines.append(f"  [{check['status']}] {check['check_id']}: {check.get('detail', '')}")
    for result in payload.get("rule_results", []):
        if result.get("status") in ("FAIL", "REVIEW_REQUIRED", "UNAVAILABLE"):
            lines.append(
                f"  [{result['status']}] {result['rule_id']} ({result['effective_state']}): "
                f"{result.get('reason', '')}"
            )
    if not lines:
        return json.dumps(payload, indent=2, ensure_ascii=False)
    return "\n".join(lines)


def _exit_for(conformance: Mapping[str, str]) -> int:
    """Map a conformance vector onto an exit code.

    Any FAIL, in any dimension, is an exit 1: the artifact has a problem.
    UNAVAILABLE counts only in the dimensions this build can actually move
    (see :data:`RUN_DEPENDENT_DIMENSIONS`).
    """
    if any(v == "FAIL" for v in conformance.values()):
        return 1
    if any(conformance.get(d) == "UNAVAILABLE" for d in RUN_DEPENDENT_DIMENSIONS):
        return 4
    return 0


def _context(args: argparse.Namespace) -> Context:
    now = None
    if getattr(args, "now", None):
        from .policy import parse_timestamp

        now = parse_timestamp(args.now)
    spec_version = getattr(args, "spec_version", None)
    if spec_version is None:
        # Two-default policy (ADR-0020, F0): the policy document pins the
        # standard edition the artifact was authored under. New durable
        # authoring under the fleet policy resolves draft.2 automatically;
        # commands with no policy and no explicit --spec-version keep the
        # legacy interpretation default (draft.1) for unlabeled material.
        policy_path = getattr(args, "policy", None)
        if policy_path:
            spec_version = declared_policy_spec_version(Path(policy_path))
    return Context.load(spec_version, now=now)


from .spec_package import declared_policy_spec_version

# -- spec -------------------------------------------------------------------


def cmd_spec_validate(args: argparse.Namespace) -> int:
    from .spec_import import run_package_validator, verify_import

    ctx = _context(args)
    report = ctx.package.verify()
    validator = run_package_validator(ctx.package)
    payload = {
        "spec_version": ctx.spec_version,
        "manifest": {
            "status": "match" if report.ok else "mismatch",
            "files_checked": len(report.files),
            "mismatches": [f.path for f in report.failures()],
            "unlisted": list(report.extra_files),
        },
        "package_validator": validator.to_dict(),
        "import_receipt": verify_import(ctx.package) if ctx.package.import_receipt() else None,
    }
    _emit(payload, fmt=args.format)
    ok = report.ok and validator.exit_code == 0
    if payload["import_receipt"] is not None:
        ok = ok and payload["import_receipt"]["status"] == "PASS"
    return 0 if ok else 1


def cmd_spec_status(args: argparse.Namespace) -> int:
    from .spec_package import SpecPackage

    ctx = _context(args)
    receipt = ctx.package.import_receipt()
    payload = {
        "spec_version": ctx.spec_version,
        "available_versions": list(SpecPackage.available_versions()),
        "extraction_path": str(ctx.package.root),
        "manifest_sha256": ctx.package.manifest_sha256,
        "rules": len(ctx.registry),
        "schemas": len(ctx.schemas.documents),
        "lexicon_version": ctx.lexicon.version,
        "implementation": ctx.implementation,
        "imported_at": receipt["imported_at"] if receipt else None,
        "source_archive_sha256": receipt["source_archive"]["sha256"] if receipt else None,
    }
    _emit(payload, fmt=args.format)
    return 0


def cmd_spec_import(args: argparse.Namespace) -> int:
    from .spec_import import build_receipt, extract_archive, run_package_validator, write_receipt
    from .spec_package import SpecPackage

    archive = Path(args.archive)
    if not archive.is_file():
        raise UsageError(f"archive not found: {archive}")
    extract_archive(archive, args.version)
    package = SpecPackage.load(args.version)
    validator = run_package_validator(package)
    receipt = build_receipt(
        package,
        archive=archive,
        validator=validator,
        imported_at=_dt.datetime.now(tz=_dt.UTC),
        expected_sha256=args.expect_sha256,
    )
    Context.load(args.version).schemas.validate_document(receipt)
    digest = write_receipt(package, receipt)
    _emit({"receipt_sha256": digest, "receipt": receipt}, fmt=args.format)
    ok = receipt["manifest_verification"]["status"] == "match"
    ok = ok and receipt["package_validator"]["status"] == "PASS"
    ok = ok and receipt["source_archive"]["sha256_matches"]
    return 0 if ok else 1


# -- ir ---------------------------------------------------------------------


def cmd_ir_validate(args: argparse.Namespace) -> int:
    from .ir.validate import IR_SCHEMA_ID, validate_ir

    ctx = _context(args)
    document = load_json(args.path)
    violations = validate_ir(ctx, document)
    _emit(
        {
            "path": str(args.path),
            "schema_id": IR_SCHEMA_ID,
            "valid": not violations,
            "violations": [
                {"pointer": v.pointer, "message": v.message, "validator": v.validator}
                for v in violations
            ],
        },
        fmt=args.format,
    )
    return 0 if not violations else 1


def cmd_ir_lint(args: argparse.Namespace) -> int:
    from .ir.lint import lint_ir

    ctx = _context(args)
    report = lint_ir(
        ctx,
        load_json(args.path),
        load_json(args.policy),
        source_path=args.source,
    )
    _emit(report, fmt=args.format)
    if args.out:
        Path(args.out).write_text(canonical_text(report) + "\n", encoding="utf-8")
    return _exit_for(report["conformance"])


def cmd_ir_canonicalize(args: argparse.Namespace) -> int:
    from .canonical import canonical_bytes, sha256_hex

    document = load_json(args.path)
    data = canonical_bytes(document)
    if args.out:
        Path(args.out).write_bytes(data)
        _emit(
            {"path": str(args.out), "bytes": len(data), "sha256": sha256_hex(data)},
            fmt=args.format,
        )
    else:
        sys.stdout.write(data.decode("utf-8") + "\n")
    return 0


def cmd_ir_explain(args: argparse.Namespace) -> int:
    """Spec Section 12.10: an implementation MUST be able to explain a rule."""
    ctx = _context(args)
    target = args.finding_or_rule
    rule_id = target
    finding: Mapping[str, Any] | None = None

    if ":" in target and not target.startswith("ATS-"):
        parts = target.split(":")
        candidates = [p for p in parts if p.startswith("ATS-")]
        if candidates:
            rule_id = candidates[0]
    if args.report:
        report = load_json(args.report)
        for candidate in report.get("findings", []):
            if candidate["finding_id"] == target:
                finding = candidate
                rule_id = candidate["rule_id"]
                break

    rule = ctx.registry.get(rule_id)
    capability = ctx.capability.for_rule(rule_id)
    payload: dict[str, Any] = {
        "rule_id": rule.rule_id,
        "rule_version": rule.rule_version,
        "title": rule.title,
        "normative_statement": rule.normative_statement,
        "rationale": rule.rationale,
        "default_states": dict(rule.default_states),
        "severity": rule.severity,
        "protected_impact": list(rule.protected_impact),
        "autofix": rule.autofix,
        "waivable": rule.waivable,
        "exception_conditions": list(rule.exceptions)
        or [
            "The registry records no rule-specific exception. A scoped "
            "TextPolicyExceptionV1 remains the only way to change this rule's state "
            "(spec 6.3), and ATS-PRES-001 and ATS-PRES-002 are unwaivable (spec 6.4).",
        ],
        "detector": {
            "implemented": capability.implemented,
            "detector_class": capability.detector_class,
            "decision_power": capability.decision_power,
            "authority": capability.authority,
            "produces_conformance_evidence": capability.produces_conformance_evidence,
            "subchecks": [dict(s) for s in capability.subchecks],
            "unavailable_conditions": list(capability.unavailable_conditions),
            "known_limits": list(capability.known_limits),
        },
        "conforming_repair_examples": _repair_examples(rule.rule_id),
    }
    if finding is not None:
        payload["finding"] = {
            "finding_id": finding["finding_id"],
            "issue_code": finding["issue_code"],
            "why_it_applies": finding["summary"],
            "spans": finding["spans"],
            "evidence_spans": finding.get("evidence_spans", []),
            "interpretations": finding.get("interpretations", []),
            "protected_impact": finding["protected_impact"],
            "state": finding["state"],
        }
    elif args.report:
        raise UsageError(f"no finding {target!r} in {args.report}")
    _emit(payload, fmt=args.format)
    return 0


#: Conforming repairs quoted from the specification's own worked examples, so a
#: repair suggestion never invents a pattern the standard does not show.
_REPAIRS: dict[str, tuple[str, ...]] = {
    "ATS-REQ-001": (
        "Spec 9.3.4 conforming form: 'The verifier MUST reject the receipt before the "
        "acceptance transition.' — replace the pronoun with the responsible component.",
    ),
    "ATS-REQ-002": (
        "Spec 9.3.3 conforming decomposition: 'REQ-VER-001: The verifier MUST reject a receipt "
        "whose policy hash is stale.' and 'REQ-VER-002: After rejecting a stale receipt, the "
        "verifier MUST record an audit event.'",
    ),
    "ATS-EPI-002": (
        "Spec 8.4 and 21.1 conforming form: 'A Rust migration is likely (55–80%) to reduce "
        "invalid-state defects.' — show the display range at first material use.",
    ),
    "ATS-EPI-007": (
        "Spec 21.1 conforming form: replace 'might improve' with a canonical band, for example "
        "'likely (55–80%)', or state a justified numeric probability.",
    ),
    "ATS-EPI-004": (
        "Spec 21.1 conforming form: state likelihood and confidence as separate labelled "
        "statements — 'Key judgment: … likely (55–80%) …' and 'Confidence: Moderate. <basis>'.",
    ),
    "ATS-NUM-002": (
        "Spec 9.3.8 conforming form: 'complete policy revalidation in less than 500 ms at the "
        "99th percentile over a rolling 24-hour window.'",
    ),
    "ATS-TIME-002": (
        "Spec 10.11: replace the relative expression with a date, event, version, or policy "
        "snapshot, or declare the anchor in the claim's scope.",
    ),
}


def _repair_examples(rule_id: str) -> list[str]:
    return list(
        _REPAIRS.get(
            rule_id,
            (
                "The specification records no worked repair for this rule. Section 11.13 "
                "requires the smallest change that resolves the accepted finding while "
                "preserving unaffected meaning, and Section 11.12 forbids the repair system "
                "from accepting its own patch.",
            ),
        )
    )


# -- output -----------------------------------------------------------------


def cmd_output_lint(args: argparse.Namespace) -> int:
    from .output.lint import lint_output

    ctx = _context(args)
    report = lint_output(
        ctx,
        output_path=args.document,
        trace_document=load_json(args.trace),
        ir_document=load_json(args.ir),
        policy_document=load_json(args.policy),
        receipt_document=load_json(args.receipt) if args.receipt else None,
    )
    _emit(report, fmt=args.format)
    if args.out:
        Path(args.out).write_text(canonical_text(report) + "\n", encoding="utf-8")
    return _exit_for(report["conformance"])


def cmd_output_verify_receipt(args: argparse.Namespace) -> int:
    from .hashes import file_sha256
    from .output.receipt import verify_receipt

    ctx = _context(args)
    result = verify_receipt(
        ctx,
        load_json(args.receipt),
        ir_document=load_json(args.ir) if args.ir else None,
        output_sha256=file_sha256(args.document) if args.document else None,
        policy_document=load_json(args.policy) if args.policy else None,
    )
    _emit(result, fmt=args.format)
    return {"PASS": 0, "FAIL": 1, "UNAVAILABLE": 4}.get(result["status"], 1)


# -- rules and capability ---------------------------------------------------


def cmd_rules_list(args: argparse.Namespace) -> int:
    ctx = _context(args)
    rules = []
    for rule_id in ctx.registry.ids():
        rule = ctx.registry.get(rule_id)
        capability = ctx.capability.for_rule(rule_id)
        rules.append(
            {
                "rule_id": rule.rule_id,
                "title": rule.title,
                "category": rule.category,
                "severity": rule.severity,
                "default_states": dict(rule.default_states),
                "detector_classes": list(rule.detector_classes),
                "protected_impact": list(rule.protected_impact),
                "implemented": capability.implemented,
                "decision_power": capability.decision_power,
            }
        )
    _emit({"spec_version": ctx.spec_version, "count": len(rules), "rules": rules}, fmt=args.format)
    return 0


def cmd_rules_explain(args: argparse.Namespace) -> int:
    args.finding_or_rule = args.rule_id
    args.report = None
    return cmd_ir_explain(args)


def cmd_capability_show(args: argparse.Namespace) -> int:
    ctx = _context(args)
    payload = {
        "normative": ctx.capability.to_normative(
            spec_version=ctx.spec_version,
            schema_versions=sorted(ctx.schemas.documents),
        ),
        "per_rule": ctx.capability.document,
        "coherence_errors": ctx.capability.coherence_errors(),
    }
    _emit(payload, fmt=args.format)
    return 0 if not payload["coherence_errors"] else 1


# -- corpus -----------------------------------------------------------------


def _corpus(module: str, attribute: str) -> Callable[..., Any]:
    """Import a corpus entry point, or report it as an unsupported capability."""
    try:
        imported = __import__(f"ats.corpus.{module}", fromlist=[attribute])
        return getattr(imported, attribute)
    except (ImportError, AttributeError) as exc:
        raise UnsupportedCapabilityError(
            f"corpus:{module}.{attribute}",
            f"this build does not provide the corpus {module} capability ({exc})",
            declared_at="capability/ats_rule_capability_v1.json",
        ) from exc


def _load_records(path: str) -> list[Any]:
    """Load corpus records from ``.jsonl`` (one per line) or ``.json``.

    Corpus stores are append-only JSONL, so the CLI must read that shape
    natively rather than pushing the caller through a conversion step.
    """
    p = Path(path)
    if not p.is_file():
        raise UsageError(f"cannot read {p}: no such file")
    if p.suffix == ".jsonl":
        records: list[Any] = []
        for number, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise UsageError(f"{p}:{number} is not valid JSON: {exc}") from exc
        return records
    loaded = load_json(p)
    return loaded if isinstance(loaded, list) else [loaded]


def _select_record(records: list[Any], record_id: str | None, id_field: str) -> Any:
    """Pick one record, requiring an explicit id when the file holds several."""
    if record_id is not None:
        for record in records:
            if isinstance(record, Mapping) and record.get(id_field) == record_id:
                return record
        raise UsageError(f"no record with {id_field}={record_id!r} in the supplied file")
    if len(records) == 1:
        return records[0]
    raise UsageError(
        f"the file holds {len(records)} records; pass --example-id to choose one"
    )


def cmd_corpus_inventory(args: argparse.Namespace) -> int:
    ctx = _context(args)
    result = _corpus("inventory", "build_inventory")(
        ctx, args.repo, include=tuple(args.include or ()), exclude=tuple(args.exclude or ())
    )
    _emit(result, fmt=args.format)
    if args.out:
        Path(args.out).write_text(canonical_text(result) + "\n", encoding="utf-8")
    return 0


def cmd_corpus_mine(args: argparse.Namespace) -> int:
    ctx = _context(args)
    result = _corpus("mine", "mine_candidates")(ctx, load_json(args.inventory))
    _emit(result, fmt=args.format)
    return 0


def cmd_corpus_validate(args: argparse.Namespace) -> int:
    ctx = _context(args)
    result = _corpus("records", "validate_records")(ctx, args.path)
    _emit(result, fmt=args.format)
    return 0 if not result.get("problems") else 1


def cmd_corpus_mutate(args: argparse.Namespace) -> int:
    ctx = _context(args)
    example = _select_record(_load_records(args.path), args.example_id, "example_id")
    result = _corpus("mutate", "apply_operator")(ctx, example, args.operator)
    _emit(result, fmt=args.format)
    return 0


def cmd_corpus_split(args: argparse.Namespace) -> int:
    ctx = _context(args)
    result = _corpus("split", "generate_split")(
        ctx, _load_records(args.path), load_json(args.policy)
    )
    _emit(result, fmt=args.format)
    failed = [c for c in result.get("leakage_checks", []) if c.get("status") == "FAIL"]
    return 1 if failed else 0


def cmd_corpus_annotate(args: argparse.Namespace) -> int:
    ctx = _context(args)
    kwargs: dict[str, Any] = {}
    if args.bundles:
        kwargs["bundles"] = args.bundles
    if args.existing_judgments:
        kwargs["existing_judgments"] = _load_records(args.existing_judgments)
    if args.minimum_completeness:
        kwargs["minimum_completeness"] = args.minimum_completeness
    result = _corpus("annotate", "build_queue")(
        ctx, _load_records(args.queue), args.annotator, **kwargs
    )
    _emit(result, fmt=args.format)
    return 0


def cmd_corpus_adjudicate(args: argparse.Namespace) -> int:
    ctx = _context(args)
    result = _corpus("adjudicate", "adjudicate_file")(ctx, args.judgments, args.adjudicator)
    _emit({"adjudications": result}, fmt=args.format)
    return 0


def cmd_corpus_stats(args: argparse.Namespace) -> int:
    ctx = _context(args)
    result = _corpus("stats", "corpus_stats")(ctx, args.path)
    _emit(result, fmt=args.format)
    return 0


# -- fleet policy ---------------------------------------------------------


def cmd_policy_resolve(args: argparse.Namespace) -> int:
    """Resolve the fleet policy for one artifact class (draft.2 D-G)."""
    from .fleet import DEFAULT_POLICY_PATH, resolve

    ctx = _context(args)
    path = Path(args.policy) if args.policy else DEFAULT_POLICY_PATH
    if not path.is_file():
        raise UsageError(f"fleet policy document not found: {path}")
    document = load_json(path)
    resolution = resolve(
        document, args.artifact_class, repository=args.repo, schemas=ctx.schemas
    )
    payload = {
        "artifact_class": args.artifact_class,
        "repository": args.repo,
        **resolution.to_dict(),
    }
    _emit(payload, fmt=args.format)
    return 0


# -- planning --------------------------------------------------------------


#: The exact shape of a SHA-256 content address (mirrors the schema pattern).
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def cmd_planning_project(args: argparse.Namespace) -> int:
    """Project a validated TextIR into sealed planning input (draft.2 D-H)."""
    from .planning.project import project_from_ir

    ctx = _context(args)
    if not _SHA256_RE.fullmatch(args.artifact_sha256):
        raise UsageError(
            f"--artifact-sha256 must be a 64-hex SHA-256, got {args.artifact_sha256!r}"
        )
    projection = project_from_ir(
        ctx,
        load_json(args.path),
        load_json(args.policy),
        artifact_sha256=args.artifact_sha256,
    )
    _emit(projection, fmt=args.format)
    if args.out:
        Path(args.out).write_text(canonical_text(projection) + "\n", encoding="utf-8")
    return 0


# -- skills -----------------------------------------------------------------


def cmd_skills_verify(args: argparse.Namespace) -> int:
    """Verify a generated public skill pack against its canonical source (§40)."""
    from .skill_pack import find_repo_root, verify_pack

    repo_root = Path(args.repo).resolve() if args.repo else find_repo_root(Path.cwd())
    findings = verify_pack(Path(args.pack), repo_root)
    payload = {
        "status": "PASS" if not findings else "FAIL",
        "findings": [finding.to_dict() for finding in findings],
        "pack": str(Path(args.pack).resolve()),
        "repo": str(repo_root),
    }
    _emit(payload, fmt=args.format)
    return 0 if not findings else 1


# -- parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    from .fleet import DEFAULT_POLICY_PATH

    parser = argparse.ArgumentParser(
        prog="ats",
        description="ATS-1 (Arq Text Standard) reference implementation, deterministic v0.",
    )
    parser.add_argument("--version", action="version", version=f"ats {__version__}")
    parser.add_argument(
        "--format", choices=("json", "text"), default="json", help="output format"
    )
    parser.add_argument(
        "--spec-version", default=None, help="imported package version to evaluate against"
    )
    parser.add_argument(
        "--now",
        default=None,
        help="RFC 3339 evaluation time; pin it for reproducible receipts",
    )
    sub = parser.add_subparsers(dest="group", required=True)

    spec = sub.add_parser("spec", help="normative package operations").add_subparsers(
        dest="command", required=True
    )
    spec.add_parser("validate", help="verify package bytes and run its own validator").set_defaults(
        func=cmd_spec_validate
    )
    spec.add_parser("status", help="show the imported package and implementation identity").set_defaults(
        func=cmd_spec_status
    )
    imp = spec.add_parser("import", help="extract and receipt a normative package archive")
    imp.add_argument("archive")
    imp.add_argument("--version", required=True, help="spec version directory to create")
    imp.add_argument("--expect-sha256", default=None, help="expected archive SHA-256")
    imp.set_defaults(func=cmd_spec_import)

    ir = sub.add_parser("ir", help="TextIR operations").add_subparsers(
        dest="command", required=True
    )
    p = ir.add_parser("validate", help="validate a TextIR against the normative schema")
    p.add_argument("path")
    p.set_defaults(func=cmd_ir_validate)

    p = ir.add_parser("lint", help="run every structural check and rule detector")
    p.add_argument("path")
    p.add_argument("--policy", required=True, help="policy snapshot to bind")
    p.add_argument("--source", default=None, help="source file, to verify the declared hashes")
    p.add_argument("--out", default=None, help="write the sealed report here")
    p.set_defaults(func=cmd_ir_lint)

    p = ir.add_parser("canonicalize", help="emit RFC 8785 canonical bytes")
    p.add_argument("path")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_ir_canonicalize)

    p = ir.add_parser("explain-finding", help="explain a finding or a rule (spec 12.10)")
    p.add_argument("finding_or_rule")
    p.add_argument("--report", default=None, help="lint report containing the finding")
    p.set_defaults(func=cmd_ir_explain)

    output = sub.add_parser("output", help="rendered-output operations").add_subparsers(
        dest="command", required=True
    )
    p = output.add_parser("lint", help="lint a rendered document against its trace and IR")
    p.add_argument("document")
    p.add_argument("--trace", required=True)
    p.add_argument("--ir", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--receipt", default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_output_lint)

    p = output.add_parser("verify-receipt", help="re-check a receipt against its artifacts")
    p.add_argument("receipt")
    p.add_argument("--ir", default=None)
    p.add_argument("--document", default=None)
    p.add_argument("--policy", default=None)
    p.set_defaults(func=cmd_output_verify_receipt)

    corpus = sub.add_parser("corpus", help="corpus operations").add_subparsers(
        dest="command", required=True
    )
    p = corpus.add_parser("inventory", help="inventory a local repository")
    p.add_argument("--repo", required=True)
    p.add_argument("--include", action="append")
    p.add_argument("--exclude", action="append")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_corpus_inventory)

    p = corpus.add_parser("mine", help="extract candidates from an inventory")
    p.add_argument("--inventory", required=True)
    p.set_defaults(func=cmd_corpus_mine)

    p = corpus.add_parser("validate", help="validate corpus records against their schemas")
    p.add_argument("path")
    p.set_defaults(func=cmd_corpus_validate)

    p = corpus.add_parser("mutate", help="apply one deterministic mutation operator")
    p.add_argument("path", help="a TextExample, or a JSONL store plus --example-id")
    p.add_argument("--operator", required=True)
    p.add_argument("--example-id", default=None, dest="example_id")
    p.set_defaults(func=cmd_corpus_mutate)

    p = corpus.add_parser("split", help="generate a leakage-grouped split")
    p.add_argument("path")
    p.add_argument("--policy", required=True, dest="policy", help="split policy document")
    p.set_defaults(func=cmd_corpus_split)

    p = corpus.add_parser("annotate", help="build a blind annotation queue")
    p.add_argument("queue")
    p.add_argument("--annotator", required=True)
    p.add_argument(
        "--bundles",
        default=None,
        help=(
            "context bundles for the queued examples. Spec 17.4 forbids labelling an isolated "
            "span, so without these every item is withheld and reported under 'withheld'."
        ),
    )
    p.add_argument("--existing-judgments", default=None, dest="existing_judgments")
    p.add_argument(
        "--minimum-completeness",
        choices=("partial", "complete"),
        default=None,
        dest="minimum_completeness",
    )
    p.set_defaults(func=cmd_corpus_annotate)

    p = corpus.add_parser("adjudicate", help="resolve independent judgments")
    p.add_argument("judgments")
    p.add_argument("--adjudicator", required=True)
    p.set_defaults(func=cmd_corpus_adjudicate)

    p = corpus.add_parser("stats", help="corpus coverage and agreement statistics")
    p.add_argument("path")
    p.set_defaults(func=cmd_corpus_stats)

    rules = sub.add_parser("rules", help="rule registry operations").add_subparsers(
        dest="command", required=True
    )
    rules.add_parser("list", help="list every rule and its implementation status").set_defaults(
        func=cmd_rules_list
    )
    p = rules.add_parser("explain", help="explain one rule (spec 12.10)")
    p.add_argument("rule_id")
    p.set_defaults(func=cmd_rules_explain)

    capability = sub.add_parser("capability", help="capability declaration").add_subparsers(
        dest="command", required=True
    )
    capability.add_parser("show", help="print the capability declaration").set_defaults(
        func=cmd_capability_show
    )

    policy = sub.add_parser("policy", help="fleet artifact policy operations").add_subparsers(
        dest="command", required=True
    )
    p = policy.add_parser("resolve", help="resolve the fleet policy for one artifact class")
    p.add_argument("artifact_class", help="artifact class to resolve (e.g. implementation_spec)")
    p.add_argument(
        "--policy",
        default=None,
        help=f"fleet policy document (default: {DEFAULT_POLICY_PATH})",
    )
    p.add_argument(
        "--repo",
        default=None,
        help="repository name whose override applies (e.g. arq)",
    )
    p.set_defaults(func=cmd_policy_resolve)

    planning = sub.add_parser("planning", help="planning-input projection operations").add_subparsers(
        dest="command", required=True
    )
    p = planning.add_parser("project", help="project a validated TextIR into sealed planning input")
    p.add_argument("path")
    p.add_argument("--policy", required=True, help="policy snapshot to bind")
    p.add_argument("--artifact-sha256", required=True, help="source artifact SHA-256 to bind")
    p.add_argument("--out", default=None, help="write the sealed projection here")
    p.set_defaults(func=cmd_planning_project)

    skills = sub.add_parser("skills", help="public skill-pack operations").add_subparsers(
        dest="command", required=True
    )
    p = skills.add_parser("verify", help="verify a generated skill pack against its canonical source")
    p.add_argument("--pack", default="dist/skill-pack", help="pack directory (default: dist/skill-pack)")
    p.add_argument(
        "--repo",
        default=None,
        help="canonical source repo root (default: discovered upward from cwd)",
    )
    p.set_defaults(func=cmd_skills_verify)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except UnsupportedCapabilityError as exc:
        _emit(exc.payload(), fmt=getattr(args, "format", "json"), stream=sys.stderr)
        return exc.exit_code
    except RequiredCheckUnavailableError as exc:
        _emit(exc.payload(), fmt=getattr(args, "format", "json"), stream=sys.stderr)
        return exc.exit_code
    except AtsError as exc:
        _emit(exc.payload(), fmt=getattr(args, "format", "json"), stream=sys.stderr)
        return exc.exit_code
    except BrokenPipeError:  # pragma: no cover - piping into head and similar
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

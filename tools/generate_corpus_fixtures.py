#!/usr/bin/env python3
"""Materialize the corpus fixtures: a real Git sample repository and the seed corpus.

``fixtures/repositories/sample-repo/`` holds the *content* of the sample
repository plus ``COMMITS.json``, the plan that replays it. The ``.git``
directory is not checked in: an embedded repository inside this repository would
become a gitlink and the documents would stop being visible to the parent. The
setup helper here runs a real ``git init`` and real commits into a destination
directory, so ``ats.corpus.inventory`` is exercised against genuine git output
rather than a mock.

Run directly to (re)write the fixture content:

    PYTHONPATH=src .venv/bin/python tools/generate_corpus_fixtures.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_REPO_FIXTURE = REPO_ROOT / "fixtures" / "repositories" / "sample-repo"

#: Fixed identity and timestamps: replaying the plan twice MUST produce the same
#: commit graph, so nothing may depend on who runs it or when.
GIT_IDENTITY = (
    "-c",
    "user.name=ATS Fixture",
    "-c",
    "user.email=fixture@ats.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "core.autocrlf=false",
    "-c",
    "init.defaultBranch=main",
)

GIT_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": "/bin/false",
    "GIT_CONFIG_NOSYSTEM": "1",
    "LC_ALL": "C",
    "TZ": "UTC",
}


ASSESSMENT_V1 = """# Rust kernel assessment

<!-- ats:profile ASSESS -->

## ASSESS: acceptance-kernel language

A Rust migration is likely (55-80%) to reduce invalid-state defects in the
acceptance kernel after the transition model stabilizes. Confidence is moderate
because the evidence is mixed and partially indirect.

## Evidence

Current acceptance failures cluster around illegal intermediate states. It is
possible that a smaller typed Python kernel would close the same gap.

## Boundaries

The assessment does not apply to the policy-fluid orchestration plane.
"""

ASSESSMENT_V2 = ASSESSMENT_V1 + """
## Update indicators

If two consecutive releases show no invalid-state defects, the judgment is
currently expected to weaken. This is clearly a significant change in the
evidence base.
"""

REQUIREMENTS = """# Acceptance policy requirements

<!-- ats:profile SPECIFY -->

## SPECIFY: stale-policy rejection

REQ-POLICY-017: When the executor presents an acceptance receipt whose
policy_sha256 differs from the current resolved policy snapshot, the verifier
MUST reject the receipt before the acceptance transition.

## SPECIFY: retention

The verifier SHOULD retain both policy hashes. An operator MAY export them.
The exporter SHALL NOT redact the source revision.

## Acceptance criteria

A stale-policy fixture returns refused_stale_policy and records both hashes.
"""

REQUIREMENTS_COPY = """# Retention policy requirements

<!-- ats:profile SPECIFY -->

## SPECIFY: stale-policy rejection

REQ-RETAIN-004: When the executor presents an acceptance receipt whose
policy_sha256 differs from the current resolved policy snapshot, the verifier
MUST reject the receipt before the acceptance transition.

## SPECIFY: retention

The verifier SHOULD retain both policy hashes. An operator MAY export them.
The exporter SHALL NOT redact the source revision.

## Acceptance criteria

A stale-policy fixture returns refused_stale_policy and records both hashes.
"""

NOTES_TXT = """Operator notes

The migration decision is not settled. Recently the team recorded that the
kernel is robust under the current load, which is a very large claim without a
threshold.
"""

READ_ME = """# sample-repo fixture

Content for the corpus inventory fixture repository. `COMMITS.json` replays it
into a real Git repository; see `tools/generate_corpus_fixtures.py`.
"""

DECLARATION = {
    "repository_group": "ats-sample",
    "use_authority": "external_training_permitted",
    "handling_policy": "public",
    "domain": "acceptance-kernel",
}

#: The commit plan. Each entry writes files, then commits with a fixed date and
#: an explicit message; trailers are the only way review state and model
#: provenance enter the inventory.
COMMIT_PLAN: list[dict[str, Any]] = [
    {
        "date": "2026-01-05T09:00:00+00:00",
        "message": "Add the acceptance-kernel assessment and policy requirements\n",
        "files": {
            ".ats/corpus.json": json.dumps(DECLARATION, indent=2, sort_keys=True) + "\n",
            "docs/assessment.md": ASSESSMENT_V1,
            "docs/requirements.md": REQUIREMENTS,
            "src/main.py": "def main() -> None:\n    print('not an inspected media type')\n",
        },
    },
    {
        "date": "2026-01-06T09:00:00+00:00",
        "message": (
            "Record update indicators for the kernel assessment\n"
            "\n"
            "ATS-Model: fixture-writer@1.0.0\n"
        ),
        "files": {
            "docs/assessment.md": ASSESSMENT_V2,
            "docs/notes.txt": NOTES_TXT,
        },
    },
    {
        "date": "2026-01-07T09:00:00+00:00",
        "message": (
            "Copy the requirement template for the retention policy\n"
            "\n"
            "ATS-Review-State: accepted\n"
            "Reviewed-by: Reviewer One <one@ats.invalid>\n"
            "ATS-Review-Comment: The copied template keeps the stale-policy obligation intact.\n"
        ),
        "files": {"docs/requirements-copy.md": REQUIREMENTS_COPY},
        "note": (
            "ATS-Review-State: accepted\n"
            "Reviewed-by: Reviewer Two <two@ats.invalid>\n"
            "ATS-Review-Comment: Second reviewer confirmed the obligation text.\n"
        ),
    },
]


def _git(repo: Path, *argv: str, date: str | None = None) -> str:
    env = dict(GIT_ENV)
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    proc = subprocess.run(
        ["git", "-C", str(repo), *GIT_IDENTITY, *argv],
        capture_output=True,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(argv)} failed: {proc.stderr.decode('utf-8', 'replace')}"
        )
    return proc.stdout.decode("utf-8", "replace")


def build_sample_repo(
    dest: str | Path, *, include_review_evidence: bool = True
) -> Path:
    """Create a real Git repository at ``dest`` by replaying :data:`COMMIT_PLAN`.

    ``include_review_evidence=False`` keeps the same public content while
    omitting review-state trailers and notes, for callers that explicitly model
    a repository with no adjudication evidence.

    Returns the repository path. Idempotent for a given destination: the same
    plan, identity, dates, and evidence setting produce the same commit shas
    every run.
    """
    repo = Path(dest)
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet")
    for step in COMMIT_PLAN:
        for relative, content in step["files"].items():
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        message = step["message"]
        note = step.get("note")
        if not include_review_evidence:
            message = "\n".join(
                line
                for line in message.splitlines()
                if not line.startswith(
                    ("ATS-Review-State:", "Reviewed-by:", "ATS-Review-Comment:")
                )
            ).strip() + "\n"
            note = None
        _git(repo, "add", "--all")
        _git(repo, "commit", "--quiet", "-m", message, date=step["date"])
        if note:
            head = _git(repo, "rev-parse", "HEAD").strip()
            _git(repo, "notes", "add", "-m", note, head, date=step["date"])
    return repo


def write_fixture_content() -> None:
    """Write the sample repository's file content and commit plan into fixtures/."""
    SAMPLE_REPO_FIXTURE.mkdir(parents=True, exist_ok=True)
    (SAMPLE_REPO_FIXTURE / "README.md").write_text(READ_ME, encoding="utf-8")
    (SAMPLE_REPO_FIXTURE / "COMMITS.json").write_text(
        json.dumps(COMMIT_PLAN, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    content_root = SAMPLE_REPO_FIXTURE / "content"
    for step in COMMIT_PLAN:
        for relative, content in step["files"].items():
            target = content_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")


# -- curated seed examples ---------------------------------------------------
#
# Hand-authored by a person, one per label the vocabulary defines that mining
# cannot produce on its own. These are CURATED: editing them is an editorial
# act, and regenerating the repository never overwrites their text.
SEED_EXAMPLES: list[dict[str, Any]] = [
    {
        "text": "The verifier MUST reject a receipt whose policy_sha256 differs from the "
        "resolved snapshot.",
        "profile": "SPECIFY",
        "rule_id": "ATS-DEON-001",
        "label": "conforming",
        "rationale": "The obligation uses the canonical MUST surface and names its actor.",
        "protected_impact": ["P0"],
    },
    {
        "text": "The exporter SHALL NOT redact the source revision.",
        "profile": "SPECIFY",
        "rule_id": "ATS-DEON-001",
        "label": "violation",
        "rationale": "SHALL NOT is listed as a noncanonical deontic surface in the force "
        "lexicon; Section 8.17 makes it nonconforming when the intended force is material.",
        "protected_impact": ["P0"],
    },
    {
        "text": "An operator MAY export both policy hashes.",
        "profile": "SPECIFY",
        "rule_id": "ATS-DEON-002",
        "label": "hard_negative",
        "rationale": "The permission surface is present without a likelihood or a forecast "
        "role, so the Section 8.17 collision does not arise. The cue is there; the violation "
        "is not.",
        "protected_impact": ["P0"],
    },
    {
        "text": "The specification says the exporter \u201cshould normally\u201d redact, which "
        "this document does not adopt.",
        "profile": "SPECIFY",
        "rule_id": "ATS-DEON-003",
        "label": "hard_negative",
        "rationale": "Section 17.6 names a \u2018should\u2019 used in a non-normative discussion "
        "of another document as a hard negative: the surface cue appears with no obligation "
        "of this artifact's own.",
        "protected_impact": ["P2"],
    },
    {
        "text": "Within the quoted upstream advisory, the vendor writes that the patch is "
        "\u201chighly probable\u201d to land this quarter.",
        "profile": "ASSESS",
        "rule_id": "ATS-EPI-003",
        "label": "exception",
        "rationale": "Section 5.6 exempts quoted source material from surface rules when the "
        "region's content class is marked, so the noncanonical synonym is quoted rather than "
        "emitted by this artifact.",
        "protected_impact": ["P2"],
    },
    {
        "text": "The system may reject stale receipts.",
        "profile": "SPECIFY",
        "rule_id": "ATS-DEON-002",
        "label": "ambiguous",
        "rationale": "Lowercase \u2018may\u2019 admits permission, capability, and probability "
        "readings, and the requirement force is unresolved. Section 8.17 names this collision.",
        "protected_impact": ["P0"],
    },
    {
        "text": "Latency improved.",
        "profile": "ASSESS",
        "rule_id": "ATS-NUM-001",
        "label": "insufficient_context",
        "rationale": "Whether the number is material, and therefore whether Section 10.9 "
        "requires a unit, cannot be decided without the containing block and its heading.",
        "protected_impact": ["P0"],
    },
    {
        "text": "Arq does not merely verify that code ran; it builds an acceptance case linking "
        "the requested change to implementation, falsifiable evidence, unresolved findings, and "
        "human adjudication.",
        "profile": "ASSESS",
        "rule_id": "ATS-DISC-002",
        "label": "hard_negative",
        "rationale": "Section 17.6 names a long but coherent sentence as a hard negative. The "
        "sentence performs one conceptual move and preserves the contrast relation.",
        "protected_impact": ["P1", "P2"],
    },
]

#: Labels a person assigned to specific mined spans of the sample repository.
#: Keyed by (path, signal_id, matched phrase). Mining produces the candidate;
#: only a person produces the label (spec Section 17.4).
CURATED_LABELS: dict[tuple[str, str, str], dict[str, Any]] = {
    ("docs/requirements.md", "deontic-surface", "MUST"): {
        "rule_id": "ATS-DEON-001",
        "label": "conforming",
        "rationale": "REQ-POLICY-017 states its obligation with the canonical MUST surface.",
        "protected_impact": ["P0"],
    },
    ("docs/requirements.md", "deontic-noncanonical", "SHALL"): {
        "rule_id": "ATS-DEON-001",
        "label": "violation",
        "rationale": "SHALL NOT is a noncanonical deontic surface (Section 8.17).",
        "protected_impact": ["P0"],
    },
    ("docs/requirements-copy.md", "deontic-noncanonical", "SHALL"): {
        "rule_id": "ATS-DEON-001",
        "label": "violation",
        "rationale": "The copied template carries the same noncanonical SHALL NOT surface.",
        "protected_impact": ["P0"],
    },
    ("docs/assessment.md", "wep-canonical-phrase", "likely"): {
        "rule_id": "ATS-EPI-002",
        "label": "conforming",
        "rationale": "The first material use shows the inline range, as Section 8.4 requires.",
        "protected_impact": ["P0"],
    },
    ("docs/assessment.md", "non-probability-term", "possible"): {
        "rule_id": "ATS-EPI-007",
        "label": "violation",
        "rationale": "Section 8.7 states that \u2018possible\u2019 is not an ATS-1 likelihood "
        "band, and the sentence carries no calibrated likelihood.",
        "protected_impact": ["P0"],
    },
    ("docs/assessment.md", "relative-time-expression", "currently"): {
        "rule_id": "ATS-TIME-002",
        "label": "violation",
        "rationale": "The relative expression resolves to no date, event, version, or policy "
        "snapshot (Section 10.11).",
        "protected_impact": ["P0"],
    },
    ("docs/assessment.md", "empty-intensifier", "clearly"): {
        "rule_id": "ATS-DISC-003",
        "label": "near_miss",
        "rationale": "Section 10.20 says the intensifier SHOULD be removed when it adds no "
        "calibrated meaning; here it precedes a claim that is separately quantified, so the "
        "case sits at the rule boundary.",
        "protected_impact": ["P2"],
    },
    ("docs/assessment.md", "vague-evaluative-term", "significant"): {
        "rule_id": "ATS-SCOPE-001",
        "label": "violation",
        "rationale": "Section 10.21 requires a material use of \u2018significant\u2019 to name "
        "its comparison, threshold, or acceptance criterion; none is stated.",
        "protected_impact": ["P1"],
    },
    ("docs/notes.txt", "vague-evaluative-term", "robust"): {
        "rule_id": "ATS-SCOPE-001",
        "label": "near_miss",
        "rationale": "\u2018Robust under the current load\u2019 names a condition but no "
        "threshold, so the case sits at the boundary of Section 10.21.",
        "protected_impact": ["P1"],
    },
    ("docs/notes.txt", "relative-time-expression", "Recently"): {
        "rule_id": "ATS-TIME-002",
        "label": "violation",
        "rationale": "The note anchors \u2018recently\u2019 to nothing (Section 10.11).",
        "protected_impact": ["P0"],
    },
}

#: How the two fixture annotators answer. ``agree`` reproduces the curated
#: label; the others produce the disagreement shapes the adjudicator must
#: handle without forcing a majority.
ANNOTATOR_PLAN: dict[str, str] = {
    "ATS-EPI-007": "standard_ambiguity",
    "ATS-SCOPE-001": "insufficient_context",
    "ATS-DISC-003": "true_disagreement",
}


def _seed_examples(ctx: Any) -> list[dict[str, Any]]:
    from ats.corpus import records as rec

    out = []
    for seed in SEED_EXAMPLES:
        out.append(
            rec.text_example(
                text=seed["text"],
                profile=seed["profile"],
                rule_id=seed["rule_id"],
                label=seed["label"],
                rationale=seed["rationale"],
                protected_impact=seed["protected_impact"],
                provenance="human_authored_fixture",
                synthetic=False,
                split_group="ats-seed-curated",
                repository_group="ats-seed",
                domain="acceptance-kernel",
                use_authority="ATS repository fixture",
                adjudicators=["human:fixture-author"],
            )
        )
    for record in out:
        ctx.schemas.validate_document(record)
    return out


def _natural_examples(ctx: Any, repo: Path) -> tuple[list[dict], dict[str, dict]]:
    """Curated labels applied to real mined spans of the sample repository."""
    from ats.corpus import context as ctxmod
    from ats.corpus import inventory as inv
    from ats.corpus import mine
    from ats.corpus import records as rec

    inventory = inv.build_inventory(ctx, repo)
    artifacts = {a["artifact_id"]: a for a in inventory["artifacts"]}
    mined = mine.mine_candidates(ctx, inventory)

    texts = {a["artifact_id"]: inv.artifact_text(repo, a) for a in inventory["artifacts"]}
    examples: list[dict] = []
    bundles: dict[str, dict] = {}
    for candidate in mined["candidates"]:
        key = (candidate["path"], candidate["signal"]["signal_id"], candidate["matched_phrase"])
        curated = CURATED_LABELS.get(key)
        if curated is None:
            continue
        artifact = artifacts[candidate["artifact_id"]]
        bundle = ctxmod.build_context_bundle(
            ctx,
            artifact=artifact,
            text=texts[candidate["artifact_id"]],
            span=candidate["span"],
            repo_path=repo,
            profile_hint=(candidate["profile_hypotheses"] or [None])[0],
        )
        example = rec.text_example(
            text=bundle["span_text"],
            context=bundle["containing_block"]["text"],
            source_artifact=artifact["artifact_id"],
            source_span=candidate["span"],
            repository_group=artifact["repository_group"],
            domain=artifact.get("domain"),
            profile=bundle["profile_hypothesis"]["profile"],
            rule_id=curated["rule_id"],
            label=curated["label"],
            rationale=curated["rationale"],
            protected_impact=curated["protected_impact"],
            provenance="human_authored_fixture",
            use_authority=artifact["use_authority"],
            synthetic=False,
            split_group=f"{artifact['repository_group']}:{artifact['path']}",
            adjudicators=["human:fixture-author"],
            extensions={
                rec.EXT_CONTEXT_BUNDLE_ID: bundle["bundle_id"],
                rec.EXT_TEMPLATE_FAMILY: artifact.get("template_family"),
                rec.EXT_NEAR_DUPLICATE_CLUSTER: artifact.get("near_duplicate_cluster"),
                rec.EXT_SOURCE_REVISION: artifact["revision"],
                rec.EXT_AUTHOR: (artifact.get("author_provenance") or {}).get("author"),
            },
        )
        ctx.schemas.validate_document(example)
        examples.append(example)
        bundles[example["example_id"]] = bundle
    return examples, bundles


def _mutation_pairs(ctx: Any) -> tuple[list[dict], list[dict], dict[str, dict]]:
    """Every supported operator applied to the two hand-authored IR sources.

    Returns ``(examples, index, pair_files)``: the source and mutant example
    records, a summary index, and one full source/mutant pair per operator to be
    written as its own fixture file.
    """
    from ats.corpus import mutate
    from ats.corpus import records as rec

    sources = {
        "assess": ("ASSESS", "ATS-EPI-001"),
        "specify": ("SPECIFY", "ATS-REQ-001"),
    }
    index: list[dict] = []
    examples: list[dict] = []
    pair_files: dict[str, dict] = {}
    for name, (profile, rule_id) in sources.items():
        ir = json.loads(
            (REPO_ROOT / "fixtures" / "mutations" / "sources" / f"{name}_mutation_source.json")
            .read_text(encoding="utf-8")
        )
        source = rec.text_example(
            text=ir["sections"][0]["claims"][0]["proposition"],
            profile=profile,
            rule_id=rule_id,
            label="conforming",
            rationale="Hand-authored mutation source carrying every slot the operators need.",
            protected_impact=["P0"],
            provenance="human_authored_fixture",
            synthetic=False,
            split_group=f"mutation-source-{name}",
            repository_group="ats-seed",
            domain="acceptance-kernel",
            use_authority="ATS repository fixture",
            extensions={rec.EXT_TEXT_IR: ir},
        )
        ctx.schemas.validate_document(source)
        examples.append(source)
        applied, refused = mutate.apply_all(ctx, source)
        for result in applied:
            examples.append(result["mutant"])
            index.append(
                {
                    "operator_id": result["operator_id"],
                    "source": name,
                    "source_example_id": source["example_id"],
                    "mutant_example_id": result["mutant"]["example_id"],
                    "split_group": result["split_group"],
                    "pair_file": f"fixtures/mutations/pairs/{result['operator_id']}.json",
                }
            )
            pair_files[f"{result['operator_id']}.json"] = {
                "operator_id": result["operator_id"],
                "source_example": result["source_example"],
                "mutant": result["mutant"],
                "transformation": result["transformation"],
                "expected_impact": result["expected_impact"],
                "split_group": result["split_group"],
            }
        index.append({"source": name, "refused": refused})
    return examples, index, pair_files


def _judgments(ctx: Any, examples: list[dict], bundles: dict[str, dict]) -> list[dict]:
    """Two independent annotators over every example that has a context bundle."""
    from ats.corpus import annotate

    judgments: list[dict] = []
    for annotator in ("human:annotator-a", "human:annotator-b"):
        queue = annotate.build_queue(
            ctx,
            examples,
            annotator,
            bundles=bundles,
            existing_judgments=judgments,
        )
        for item in queue["items"]:
            example = next(e for e in examples if e["example_id"] == item["example_id"])
            plan = ANNOTATOR_PLAN.get(item["rule_id"], "agree")
            label = example["label"]
            ambiguity = "none"
            requested: list[str] = []
            rationale = example["rationale"]
            if annotator.endswith("-b") and plan == "standard_ambiguity":
                label = "ambiguous"
                ambiguity = "standard_ambiguity"
                rationale = (
                    "The rule text does not say whether a non-probability term used inside a "
                    "hedge counts as a likelihood claim, so the standard itself is unclear here."
                )
            elif annotator.endswith("-b") and plan == "insufficient_context":
                label = "insufficient_context"
                requested = ["the acceptance criterion the comparison is measured against"]
                rationale = (
                    "Whether the evaluative term is material depends on an acceptance "
                    "criterion that is not visible in this bundle."
                )
            elif annotator.endswith("-b") and plan == "true_disagreement":
                label = "conforming"
                rationale = (
                    "The intensifier precedes a separately quantified claim, so it adds no "
                    "uncalibrated meaning and the advisory rule is satisfied."
                )
            spans = [example["source_span"]] if label == "violation" and example.get("source_span") else []
            judgments.append(
                annotate.submit_judgment(
                    ctx,
                    item=item,
                    annotator_id=annotator,
                    label=label,
                    rationale=rationale,
                    evidence_spans=spans,
                    protected_impact=example["protected_impact"],
                    annotation_confidence="moderate",
                    requested_additional_context=requested,
                    ambiguity_category=ambiguity,
                )
            )
    return judgments


def generate_corpus_fixtures(ctx: Any, repo: Path) -> dict[str, int]:
    """Regenerate corpus/seeds/ and fixtures/{corpus,mutations}/ from the sample repo."""
    from ats.canonical import canonical_bytes
    from ats.corpus import adjudicate

    def write_jsonl(path: Path, records: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(canonical_bytes(r).decode("utf-8") + "\n" for r in records),
            encoding="utf-8",
        )

    seeds = _seed_examples(ctx)
    write_jsonl(REPO_ROOT / "corpus" / "seeds" / "seed_examples.jsonl", seeds)

    natural, bundles = _natural_examples(ctx, repo)
    mutation_examples, pair_index, pair_files = _mutation_pairs(ctx)
    write_jsonl(REPO_ROOT / "fixtures" / "corpus" / "examples.jsonl", natural + mutation_examples)
    write_jsonl(
        REPO_ROOT / "fixtures" / "corpus" / "context_bundles.jsonl",
        [bundles[k] for k in sorted(bundles)],
    )
    pairs_dir = REPO_ROOT / "fixtures" / "mutations" / "pairs"
    pairs_dir.mkdir(parents=True, exist_ok=True)
    for stale in pairs_dir.glob("*.json"):
        stale.unlink()
    for filename, pair in sorted(pair_files.items()):
        (pairs_dir / filename).write_text(
            json.dumps(pair, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    (REPO_ROOT / "fixtures" / "mutations" / "INDEX.json").write_text(
        json.dumps(pair_index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    judgments = _judgments(ctx, natural, bundles)
    write_jsonl(REPO_ROOT / "fixtures" / "corpus" / "judgments.jsonl", judgments)

    adjudications, deferred = adjudicate.adjudicate_judgments(
        ctx, judgments, "human:adjudicator"
    )
    write_jsonl(REPO_ROOT / "fixtures" / "corpus" / "adjudications.jsonl", adjudications)

    return {
        "seeds": len(seeds),
        "natural_examples": len(natural),
        "mutation_examples": len(mutation_examples),
        "context_bundles": len(bundles),
        "judgments": len(judgments),
        "mutation_pairs": len(pair_files),
        "deferred": len(deferred),
    }


def main() -> int:
    import datetime as dt
    import tempfile

    from ats.context import Context

    write_fixture_content()
    ctx = Context.load(now=dt.datetime(2026, 2, 1, tzinfo=dt.UTC))
    with tempfile.TemporaryDirectory() as tmp:
        repo = build_sample_repo(Path(tmp) / "sample-repo")
        counts = generate_corpus_fixtures(ctx, repo)
    print(f"wrote {SAMPLE_REPO_FIXTURE.relative_to(REPO_ROOT)}")
    for key, value in counts.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

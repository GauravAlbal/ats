"""The SPECIFY profile-reconnaissance study: what it reads, what it hides, what it refuses.

Defends the properties a diagnostic run beside a governed annotation round is
worthless without:

* only an authorised repository contributes a bundle, and an undeclared one
  contributes nothing even when its full inventory is supplied (Sections 16.9,
  17.13);
* the selector's fired signals never reach the classifier, because they are the
  study's own prediction about the text (Sections 13.2, 16.5, 17.8);
* a signal ATS-1 enumerates no vocabulary for carries no word list, so a count
  can never be raised by an invented term (ADR-0006);
* the draw is a pure function of the corpus and the seed, one bundle per
  leakage component, with no repository past its cap (Section 17.7);
* every one of the four explanations is reachable, and several supported at
  once is ``undecided`` rather than a pick (ADR-0002);
* the report says, in its own text, that both annotators are LLM passes.

Two suites: a synthetic corpus exercises the draw and report end to end at a
scale a test can fill. No checked-in private snapshot is part of the public
test surface.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ats.canonical import verify_seal
from ats.context import Context
from ats.corpus import frame as fr
from ats.corpus import inventory as inv
from ats.corpus import recon
from ats.corpus.context import Block
from ats.corpus.round import Annotator
from ats.errors import UsageError

NOW = dt.datetime(2026, 8, 3, tzinfo=dt.UTC)


AUTHORISED = ("alpha", "bravo", "charlie", "delta", "echo")
UNDECLARED = "zulu"

#: Small enough that a fixture can fill it, large enough that the repository cap
#: (30% of the target) binds at 3 and a five-repository round-robin has to
#: spread.
SMALL_TARGET = 10


def _git(repo: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2026-01-02T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-01-02T00:00:00+00:00",
        "PATH": "/usr/bin:/bin",
        "HOME": str(repo),
    }
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True
    ).stdout


#: Byte-identical in two repositories, so the leakage closure has a
#: cross-repository content match to join.
SHARED = (
    "# Shared obligation\n\n"
    "When a receipt arrives, the verifier MUST reject a receipt whose policy hash is "
    "stale, and it MUST record at least one audit event before acceptance.\n"
)


def _documents(name: str) -> dict[str, str]:
    """One repository's documents, one per behaviour this suite exercises."""
    return {
        f"docs/{name}-requirements.md": (
            f"# {name} requirements\n\n"
            "When a submission arrives, the scheduler MUST verify its receipt against the "
            "resolved policy snapshot before admission.\n\n"
            "While the snapshot is stale, the verifier MUST NOT admit the submission, and "
            "the operator MAY override the refusal only when an exception is recorded.\n\n"
            "The exporter SHOULD retry the upload at most three times after a transport "
            "failure, and the acceptance criterion is a receipt whose hash resolves.\n"
        ),
        f"docs/{name}-obligations.md": (
            f"# {name} obligations\n\n"
            "The runtime carries these obligations:\n\n"
            "- The worker MUST record the batch identifier before it acknowledges a batch.\n"
            "- The worker MUST NOT acknowledge a batch it has not recorded.\n"
            "- The supervisor SHOULD restart a worker that has not reported in at least "
            "sixty seconds.\n"
        ),
        f"docs/{name}-assessment.md": (
            f"# {name} assessment\n\n"
            "Judgment: the stale-policy path is likely to admit an invalid receipt under a "
            "narrow race, and the assessment confidence is moderate because the evidence is "
            "a single reproduction.\n\n"
            "Contrary evidence: the admission log shows no such admission in ninety days, "
            "which is consistent with the race being rare rather than absent.\n"
        ),
        f"docs/{name}-quoted.md": (
            f"# {name} quoted\n\n"
            "The prior specification contained this text, reproduced here without "
            "endorsement:\n\n"
            "```text\n"
            "When a receipt arrives, the verifier MUST reject it if the policy hash is "
            "stale, and the operator MAY NOT override the refusal at any time.\n"
            "```\n\n"
            "That block is quoted, not asserted.\n"
        ),
        f"docs/{name}-plain.md": (
            f"# {name} pipeline\n\n"
            "The pipeline writes each record to disk. A reader opens the file and iterates "
            "the rows in the order they were written. Nothing in this document states a "
            "requirement or an estimate.\n"
        ),
        f"notes/{name}-shared.md": SHARED,
    }


def _overlay(repository: str, revision: str) -> dict[str, Any]:
    """An owner declaration permitting annotation and mining, deferring training."""
    return {
        "schema_version": "ats.corpus_authority.v1",
        "principal": {"id": "https://example.invalid/fixture-owner", "kind": "person"},
        "authority_basis": {
            "kind": "owner_declared",
            "statement": "The principal authored every commit in this synthetic fixture.",
        },
        "repository": {
            "name": repository,
            "origin": None,
            "root_commit": "f" * 64,
            "effective_from_revision": revision,
            "declaration_location": "pilot_overlay",
        },
        "uses": {
            "inventory": "allow",
            "candidate_mining": "allow",
            "human_annotation": "allow",
            "deterministic_mutation": "allow",
            "evaluation": "allow",
            "model_training": "defer",
            "model_distillation": "defer",
            "external_model_submission": "deny",
            "publication": "deny",
            "cross_repository_derivatives": "allow_private",
        },
        "content": {"exclude": ["generated/*"]},
        "issued_at": "2026-01-01T00:00:00+00:00",
        "review_after": "2027-01-01T00:00:00+00:00",
        "superseded_by": None,
        "handling": {
            "classification": "private",
            "store_source_text": True,
            "store_context_bundles": True,
            "store_derived_features": True,
            "retain_deleted_revisions": True,
            "export_raw_text": False,
        },
        "provenance": {
            "authorship": "unknown_unless_explicit",
            "model_authorship_inference": "prohibited",
        },
        "notes": "Synthetic fixture repository.",
    }


@pytest.fixture(scope="module")
def now_ctx() -> Context:
    return Context.load(now=NOW)


@pytest.fixture(scope="module")
def corpus(now_ctx: Context, tmp_path_factory) -> dict[str, Any]:
    """Six synthetic repositories, five of them declared, inventoried.

    No mining result is built, and that is not an omission: the study reads the
    inventories and the source text directly. A fixture that supplied candidates
    would let a regression route the selector through the miner without any test
    noticing.
    """
    root = tmp_path_factory.mktemp("recon-corpus")
    overlay_dir = root / "authority"
    overlay_dir.mkdir()

    for name in (*AUTHORISED, UNDECLARED):
        repo = root / name
        repo.mkdir()
        _git(repo, "init", "--quiet")
        for relative, content in _documents(name).items():
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        _git(repo, "add", "--all")
        _git(repo, "commit", "--quiet", "-m", "fixture")
        revision = _git(repo, "rev-parse", "HEAD").strip()
        if name in AUTHORISED:
            (overlay_dir / f"{name}.json").write_text(
                json.dumps(_overlay(name, revision), indent=2) + "\n", encoding="utf-8"
            )

    rows: list[dict[str, Any]] = []
    for name in (*AUTHORISED, UNDECLARED):
        inventory = inv.build_inventory(now_ctx, root / name, authority_overlay=overlay_dir)
        rows.append(
            {
                "repository": name,
                "family": f"{name}-family",
                "domain": "synthetic" if name in AUTHORISED[:3] else "synthetic-other",
                "revision": inventory["revision"],
                "inventory": inventory,
            }
        )
    return {"root": root, "overlay": overlay_dir, "rows": rows}


@pytest.fixture(scope="module")
def drawn(corpus: dict[str, Any], now_ctx: Context) -> dict[str, Any]:
    return recon.draw_recon_bundles(
        now_ctx,
        repositories=corpus["rows"],
        seed=7,
        target_bundles=SMALL_TARGET,
        authority_overlay=corpus["overlay"],
    )




# -- signals -----------------------------------------------------------------


def test_every_signal_names_a_vocabulary_source_it_can_be_audited_against(
    now_ctx: Context,
) -> None:
    """ADR-0006: a matched term must trace to a lexicon key, a spec list, or a schema enum."""
    signals = recon.build_recon_signals(now_ctx)
    assert len(signals) == 7
    assert len({s.signal_id for s in signals}) == 7
    for signal in signals:
        assert signal.origin in {
            "lexicon",
            "spec_enumeration",
            "normative_schema_enum",
            "detector_vocabulary",
            "no_declared_vocabulary",
        }
        assert signal.spec_ref.startswith(("ATS-1", "ADR-")) or "ADR-0006" in signal.spec_ref
        assert signal.vocabulary_source.strip()
        # The load-bearing invariant: no phrases under the label that says there
        # is no list, and no phrase-detecting signal with an empty list.
        assert (signal.origin == "no_declared_vocabulary") == (not signal.phrases)
        assert (signal.detection == "structural") == (not signal.phrases)


def test_a_signal_declaring_no_vocabulary_may_not_carry_one() -> None:
    """The refusal is enforced at construction, not left to review."""
    with pytest.raises(UsageError, match="ADR-0006"):
        recon.ReconSignal(
            signal_id="explicit-actor",
            description="an invented actor list",
            spec_ref="ATS-1 9.3.4",
            vocabulary_source="no_declared_vocabulary",
            origin="no_declared_vocabulary",
            detection="structural",
            phrases=("the verifier", "the operator"),
        )


def test_the_condition_signal_matches_only_openers_the_spec_enumerates(
    now_ctx: Context,
) -> None:
    """"unless" reads like a condition and ATS-1 does not enumerate it.

    Matching it would cite Section 9.3.5 for a word Section 9.3.5 does not
    contain, which is the exact failure ADR-0006 names.
    """
    matchers = recon.compile_matchers(recon.build_recon_signals(now_ctx))
    pattern = matchers.by_signal["condition-or-trigger"]
    assert pattern.search("When the receipt arrives the verifier acts")
    assert pattern.search("While the snapshot is stale the verifier waits")
    for absent in recon.CONDITION_TRIGGER_UNMATCHED:
        assert not pattern.search(f"The verifier admits it {absent} the hash is stale"), absent


def test_a_concealed_actor_is_not_an_explicit_actor(now_ctx: Context) -> None:
    """Section 9.3.4's own nonconforming example must not raise the actor signal."""
    matchers = recon.compile_matchers(recon.build_recon_signals(now_ctx))
    block = Block("paragraph", 1, 1, 0, 80, "x")
    concealed = "It MUST be rejected before acceptance."
    named = "The verifier MUST reject the receipt before the acceptance transition."
    assert "explicit-actor" not in recon.fired_signals(
        matchers, sentence=concealed, block=block, block_text=concealed
    )
    assert "explicit-actor" in recon.fired_signals(
        matchers, sentence=named, block=block, block_text=named
    )


def test_a_deontic_inside_a_fenced_block_raises_no_candidate(
    drawn: dict[str, Any], corpus: dict[str, Any], now_ctx: Context
) -> None:
    """Section 5.6 exempts quoted source text: a keyword in an example is a quotation.

    The quoted document's only requirement-dense sentence is inside a fence and
    carries five signals, so it would sort to the very front of the draw if the
    exemption were dropped. Its two prose sentences carry at most one signal and
    are below the admission floor, so the document contributes nothing at all.
    """
    paths = {
        str(artifact["artifact_id"]): str(artifact["path"])
        for artifact in drawn["artifacts"].values()
    }
    quoted_ids = {
        artifact_id for artifact_id, path in paths.items() if path.endswith("-quoted.md")
    }
    assert len(quoted_ids) == len(AUTHORISED), "the fixture must supply the quoted documents"
    assert not [c for c in drawn["candidates"] if c.artifact_id in quoted_ids]

    # And the fenced sentence really would have fired, so the assertion above is
    # about the exemption rather than about a document with nothing in it.
    matchers = recon.compile_matchers(recon.build_recon_signals(now_ctx))
    fenced = (
        "When a receipt arrives, the verifier MUST reject it if the policy hash is stale, "
        "and the operator MAY NOT override the refusal at any time."
    )
    block = Block("paragraph", 1, 1, 0, len(fenced), fenced)
    assert (
        len(recon.fired_signals(matchers, sentence=fenced, block=block, block_text=fenced))
        >= recon.MIN_SIGNALS_TO_ADMIT
    )


# -- authority ---------------------------------------------------------------


def test_an_unauthorised_repository_contributes_zero_bundles(
    corpus: dict[str, Any], now_ctx: Context, drawn: dict[str, Any]
) -> None:
    """The undeclared repository's full inventory is supplied and still contributes nothing.

    Supplying it is the point: an exclusion that only holds because the loader
    happened not to read the repository is not an authority decision. Its
    documents are requirement-dense, so a selector that ignored authority would
    draw from it immediately.
    """
    assert any(row["repository"] == UNDECLARED for row in corpus["rows"])
    assert any(row["inventory"]["artifacts"] for row in corpus["rows"]
               if row["repository"] == UNDECLARED)

    repositories = {row["repository"] for row in drawn["selection"]}
    assert UNDECLARED not in repositories
    assert repositories <= set(AUTHORISED)

    excluded = {row["repository"] for row in drawn["authority"]["excluded"]}
    assert UNDECLARED in excluded
    reason = next(
        row["reason"] for row in drawn["authority"]["excluded"] if row["repository"] == UNDECLARED
    )
    assert "human_annotation" in reason or "candidate_mining" in reason

    # And no artifact of the undeclared repository entered the pool at all, so
    # the exclusion happens before any source text is read.
    assert all(
        str(artifact["repository"]) != UNDECLARED for artifact in drawn["artifacts"].values()
    )


def test_a_path_the_declaration_excludes_is_dropped_per_document(
    corpus: dict[str, Any], now_ctx: Context
) -> None:
    """Authority resolves per path, not only per repository."""
    root: Path = corpus["root"]
    repo = root / AUTHORISED[0]
    generated = repo / "generated" / "report.md"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text(
        "# generated\n\nThe exporter MUST emit at least one receipt when a batch closes.\n",
        encoding="utf-8",
    )
    _git(repo, "add", "--all")
    _git(repo, "commit", "--quiet", "-m", "generated")

    inventory = inv.build_inventory(now_ctx, repo, authority_overlay=corpus["overlay"])
    rows = [
        {**row, "inventory": inventory} if row["repository"] == AUTHORISED[0] else row
        for row in corpus["rows"]
    ]
    drawn = recon.draw_recon_bundles(
        now_ctx,
        repositories=rows,
        seed=7,
        target_bundles=SMALL_TARGET,
        authority_overlay=corpus["overlay"],
    )
    dropped = {row["path"] for row in drawn["index"]["dropped"]}
    assert "generated/report.md" in dropped
    assert all(
        not str(artifact["path"]).startswith("generated/")
        for artifact in drawn["artifacts"].values()
    )


# -- the draw ----------------------------------------------------------------


def test_the_draw_takes_one_bundle_per_leakage_component(drawn: dict[str, Any]) -> None:
    """Two members of one component cannot be separated later if only one is ever taken."""
    groups = [row["split_group"] for row in drawn["selection"]]
    assert len(groups) == len(set(groups))
    assert drawn["draw"]["components_consumed"] == len(drawn["selection"])
    # The shared document is byte-identical across five repositories, so the
    # closure has something to join and the constraint is not vacuous.
    assert len({row["source_artifact_id"] for row in drawn["selection"]}) == len(groups)


def test_no_repository_may_exceed_its_declared_share(drawn: dict[str, Any]) -> None:
    """The cap is policy, declared, and enforced during the draw."""
    cap = drawn["draw"]["repository_cap"]
    assert cap == max(1, round(SMALL_TARGET * fr.MAX_REPOSITORY_SHARE + 0.4999))
    counts: dict[str, int] = {}
    for row in drawn["selection"]:
        counts[row["repository"]] = counts.get(row["repository"], 0) + 1
    assert counts, "the draw selected nothing, so the cap assertion would be vacuous"
    assert max(counts.values()) <= cap
    assert len(counts) >= 4, "a round-robin over five repositories should spread"


def test_the_same_seed_reproduces_the_draw_and_another_seed_does_not(
    corpus: dict[str, Any], now_ctx: Context, drawn: dict[str, Any]
) -> None:
    """Section 16.2: identical canonical inputs, identical result."""
    again = recon.draw_recon_bundles(
        now_ctx,
        repositories=corpus["rows"],
        seed=7,
        target_bundles=SMALL_TARGET,
        authority_overlay=corpus["overlay"],
    )
    assert again["selection"] == drawn["selection"]
    other = recon.draw_recon_bundles(
        now_ctx,
        repositories=corpus["rows"],
        seed=99,
        target_bundles=SMALL_TARGET,
        authority_overlay=corpus["overlay"],
    )
    assert {row["bundle_id"] for row in other["selection"]} != {
        row["bundle_id"] for row in drawn["selection"]
    }


def test_every_selected_bundle_carries_its_signal_provenance(drawn: dict[str, Any]) -> None:
    known = {s.signal_id for s in drawn["index"]["signals"]}
    assert drawn["selection"], "an empty draw would make this vacuous"
    for row in drawn["selection"]:
        assert row["signals_fired"], row["bundle_id"]
        assert set(row["signals_fired"]) <= known
        assert row["signal_count"] == len(row["signals_fired"])
        assert row["signal_count"] >= recon.MIN_SIGNALS_TO_ADMIT


# -- blinding ----------------------------------------------------------------


def test_the_selectors_fired_signals_never_reach_the_classifier(
    drawn: dict[str, Any], corpus: dict[str, Any], now_ctx: Context
) -> None:
    """A field the projection does not name cannot travel, even if somebody adds it.

    The bundle is polluted with the study's own prediction -- the fired signals
    and an explicit expected profile -- and the projection is asserted to carry
    neither. An allow-list is what makes that hold for a key nobody has invented
    yet, which is why the assertion is on the key set and not on a denylist.
    """
    bundles: list[dict[str, Any]] = []
    recon.draw_recon_bundles(
        now_ctx,
        repositories=corpus["rows"],
        seed=7,
        target_bundles=SMALL_TARGET,
        authority_overlay=corpus["overlay"],
        bundle_sink=bundles,
    )
    assert bundles

    signals_by_bundle = {
        row["bundle_id"]: row["signals_fired"] for row in drawn["selection"]
    }
    for bundle in bundles:
        polluted = {
            **bundle,
            "signals_fired": signals_by_bundle[bundle["bundle_id"]],
            "signal_count": len(signals_by_bundle[bundle["bundle_id"]]),
            "selector_prediction": "SPECIFY",
            "stratum": "requirement_shaped",
        }
        item = recon.blind_recon_item(polluted)
        assert set(item) == set(recon.CLASSIFIER_VISIBLE_FIELDS)
        blob = json.dumps(item)
        assert "selector_prediction" not in blob
        assert "signals_fired" not in blob
        assert "requirement_shaped" not in blob
        for signal_id in signals_by_bundle[bundle["bundle_id"]]:
            assert signal_id not in blob, signal_id


def test_the_withheld_set_is_derived_from_the_schemas_not_enumerated(
    now_ctx: Context,
) -> None:
    """A property added to either schema is withheld until somebody admits it."""
    withheld = recon.withheld_from_classifier(now_ctx)
    assert "signals_fired" in withheld
    assert "signal_count" in withheld
    assert "split_group" in withheld
    assert "repository" in withheld
    assert "profile_hypothesis" in withheld
    assert set(withheld).isdisjoint(recon.CLASSIFIER_VISIBLE_FIELDS)


# -- judgments ---------------------------------------------------------------


def _write_judgments(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )
    return path


def test_a_classification_outside_the_vocabulary_is_refused_not_repaired(
    tmp_path: Path,
) -> None:
    """Repairing an illegal label into the nearest legal one invents an opinion."""
    path = _write_judgments(
        tmp_path / "pass.jsonl",
        [
            {"bundle_id": "b1", "answer": {"classification": "SPECIFY", "rationale": "ok"}},
            {"bundle_id": "b2", "answer": {"classification": "specify", "rationale": "case"}},
            {"bundle_id": "b3", "answer": {"classification": "PROBABLY_SPECIFY"}},
            {"bundle_id": "b4", "answer": None},
            {"bundle_id": "b1", "answer": {"classification": "ASSESS"}},
        ],
    )
    rows, refused = load = recon.load_classifications(path, "llm-recon-a")
    assert [row["classification"] for row in rows] == ["SPECIFY"]
    assert refused == 4, load
    assert rows[0]["rationale"] == "ok"


def test_a_judgment_for_a_bundle_this_study_did_not_draw_is_refused(tmp_path: Path) -> None:
    path = _write_judgments(
        tmp_path / "pass.jsonl",
        [
            {"bundle_id": "b1", "answer": {"classification": "SPECIFY"}},
            {"bundle_id": "elsewhere", "answer": {"classification": "ASSESS"}},
        ],
    )
    rows, refused = recon.load_classifications(path, "llm-recon-a", bundle_ids={"b1"})
    assert [row["bundle_id"] for row in rows] == ["b1"]
    assert refused == 1


# -- agreement ---------------------------------------------------------------


def _judgment(bundle_id: str, annotator: str, label: str, **extra: Any) -> dict[str, Any]:
    return {
        "bundle_id": bundle_id,
        "annotator_id": annotator,
        "classification": label,
        "rationale": f"{annotator} says {label}",
        "persuasive_signals": [],
        "requested_additional_context": [],
        "evidence_offsets": [],
        **extra,
    }


def test_agreement_is_reported_per_class_with_every_disagreement_preserved() -> None:
    """A pooled figure would hide the class the study turns on."""
    rows = [
        _judgment("b1", "a", "SPECIFY"),
        _judgment("b1", "b", "SPECIFY"),
        _judgment("b2", "a", "SPECIFY"),
        _judgment("b2", "b", "mixed"),
        _judgment("b3", "a", "ASSESS"),
        _judgment("b3", "b", "ASSESS"),
        _judgment("b4", "a", "insufficient_context"),
        _judgment("b4", "b", "SPECIFY"),
    ]
    result = recon.agreement_between(rows, ["a", "b"], {"b2": ["normative-modality"]})
    assert result["compared"] == 4
    assert result["agreed"] == 2
    assert result["observed_agreement"] == 0.5
    by_class = {row["classification"]: row for row in result["per_class"]}
    # a: b1,b2,  b: b1,b4  ->  both {b1} = 1, either {b1,b2,b4} = 3
    assert by_class["SPECIFY"]["both"] == 1
    assert by_class["SPECIFY"]["either"] == 3
    assert by_class["SPECIFY"]["agreement"] == pytest.approx(1 / 3)
    assert by_class["reserved_profile"]["agreement"] is None, "zero over zero is not agreement"
    assert [d["bundle_id"] for d in result["disagreements"]] == ["b2", "b4"]
    assert result["disagreements"][0]["signals_fired"] == ["normative-modality"]
    assert {label["classification"] for label in result["disagreements"][0]["labels"]} == {
        "SPECIFY",
        "mixed",
    }
    assert "not human inter-rater reliability" in result["caveat"].lower() or (
        "NOT human inter-rater reliability" in result["caveat"]
    )


def test_a_judgment_from_an_unregistered_pass_is_refused() -> None:
    rows = [_judgment("b1", "a", "SPECIFY"), _judgment("b1", "c", "SPECIFY")]
    with pytest.raises(UsageError, match="unregistered annotator"):
        recon.agreement_between(rows, ["a", "b"], {})


# -- verdict -----------------------------------------------------------------


def _counts(**overrides: int) -> dict[str, int]:
    """A baseline where nothing is supported, so each test moves exactly one thing."""
    base = {
        "target": 40,
        "selected": 40,
        "admissible_spans": 5000,
        "admissible_documents": 700,
        "compared": 40,
        "strongly_shaped_selected": 20,
        "strongly_shaped_compared": 20,
        "corpus_declared_specify": 0,
        "specify_both": 6,
        "specify_either": 8,
        "specify_both_strong": 4,
        "mixed_both": 0,
        "mixed_either": 0,
        "mixed_both_strong": 0,
        "reserved_both": 0,
        "reserved_either": 0,
        "reserved_both_strong": 0,
        "assess_both": 20,
        "not_applicable_both": 6,
        "insufficient_both": 2,
        "insufficient_either": 4,
        "specify_with_context_request": 1,
    }
    base.update(overrides)
    return base


def _supported(counts: dict[str, int]) -> set[str]:
    return {
        str(c["explanation_id"])
        for c in recon.evaluate_explanations(counts)
        if c["supported"]
    }


def test_the_baseline_supports_nothing_so_each_case_moves_one_thing() -> None:
    assert _supported(_counts()) == set()
    explanation, statement, resolve = recon.decide(recon.evaluate_explanations(_counts()))
    assert explanation == "undecided"
    assert statement == recon.UNDECIDED_NOTHING_SUPPORTED
    assert resolve


def test_each_of_the_four_explanations_is_reachable() -> None:
    """A study that cannot return three of its four answers has not tested them."""
    absence = _counts(specify_both=1, mixed_both=0, specify_either=2)
    assert "true_corpus_absence" in _supported(absence)

    thin_yield = _counts(selected=20)
    assert "true_corpus_absence" in _supported(thin_yield)

    mining = _counts(specify_both=20, specify_either=24, specify_with_context_request=2)
    assert _supported(mining) == {"candidate_mining_deficiency"}

    context = _counts(specify_either=10, specify_both=6, specify_with_context_request=9)
    assert "context_bundle_deficiency" in _supported(context)

    insufficient = _counts(insufficient_both=12, insufficient_either=16)
    assert "context_bundle_deficiency" in _supported(insufficient)

    boundary = _counts(
        specify_both=6,
        specify_both_strong=2,
        mixed_both=8,
        mixed_both_strong=8,
        reserved_both_strong=2,
    )
    assert "profile_boundary_defect" in _supported(boundary)


def test_exactly_one_supported_criterion_is_a_verdict() -> None:
    counts = _counts(specify_both=20, specify_either=24, specify_with_context_request=2)
    explanation, statement, resolve = recon.decide(recon.evaluate_explanations(counts))
    assert explanation == "candidate_mining_deficiency"
    assert statement == dict(recon.EXPLANATIONS)["candidate_mining_deficiency"]
    # Every rival is named with the experiment that would overturn the verdict.
    assert len(resolve) == 3
    for other in recon.EXPLANATION_IDS:
        if other == explanation:
            continue
        assert any(other in line for line in resolve), other


def test_several_supported_criteria_are_undecided_with_a_separating_experiment() -> None:
    """Picking one of two readings the counts do not separate is the failure to avoid."""
    counts = _counts(
        specify_both=20,
        specify_either=24,
        specify_with_context_request=22,
    )
    supported = _supported(counts)
    assert supported == {"candidate_mining_deficiency", "context_bundle_deficiency"}
    explanation, statement, resolve = recon.decide(recon.evaluate_explanations(counts))
    assert explanation == "undecided"
    assert "does not separate them" in statement
    assert resolve == [
        recon.SEPARATORS[("candidate_mining_deficiency", "context_bundle_deficiency")]
    ]


def test_every_pair_of_explanations_has_a_declared_separator() -> None:
    """An undecided verdict that names no experiment is a shrug."""
    for i, first in enumerate(recon.EXPLANATION_IDS):
        for second in recon.EXPLANATION_IDS[i + 1 :]:
            key = (first, second) if (first, second) in recon.SEPARATORS else (second, first)
            assert key in recon.SEPARATORS, (first, second)


# -- the report --------------------------------------------------------------


@pytest.fixture(scope="module")
def synthetic_report(
    corpus: dict[str, Any], now_ctx: Context, drawn: dict[str, Any], tmp_path_factory
) -> dict[str, Any]:
    out = tmp_path_factory.mktemp("recon-report")
    bundle_ids = [row["bundle_id"] for row in drawn["selection"]]
    labels_a = ["SPECIFY"] * (len(bundle_ids) - 2) + ["ASSESS", "insufficient_context"]
    labels_b = ["SPECIFY"] * (len(bundle_ids) - 2) + ["ASSESS", "SPECIFY"]
    for name, labels in (("a", labels_a), ("b", labels_b)):
        _write_judgments(
            out / f"pass_{name}.jsonl",
            [
                {
                    "bundle_id": bundle_id,
                    "answer": {
                        "classification": label,
                        "rationale": f"pass {name}",
                        "persuasive_signals": ["a deontic with a named actor"],
                        "requested_additional_context": [],
                        "evidence_offsets": [[0, 4]],
                    },
                }
                for bundle_id, label in zip(bundle_ids, labels, strict=True)
            ],
        )
    return recon.build_profile_reconnaissance(
        now_ctx,
        repositories=corpus["rows"],
        seed=7,
        target_bundles=SMALL_TARGET,
        authority_overlay=corpus["overlay"],
        annotators=[
            Annotator("llm-recon-a", "llm", model="default", prompt_id="p", prompt_sha256="0" * 64),
            Annotator("llm-recon-b", "llm", model="slow", prompt_id="p", prompt_sha256="0" * 64),
        ],
        judgment_paths={
            "llm-recon-a": out / "pass_a.jsonl",
            "llm-recon-b": out / "pass_b.jsonl",
        },
    )


def test_the_report_validates_and_its_seal_verifies(
    synthetic_report: dict[str, Any], now_ctx: Context
) -> None:
    assert now_ctx.schemas.validate_document(synthetic_report) == recon.SCHEMA_ID
    ok, declared, recomputed = verify_seal(synthetic_report)
    assert ok, f"{declared} != {recomputed}"
    assert synthetic_report["report_id"].startswith(recon.ID_PREFIX)


def test_the_report_freezes_both_passes_before_it_reports_agreement(
    synthetic_report: dict[str, Any]
) -> None:
    """A pass not bound to the bytes of its judgments could be revised after the fact."""
    passes = {row["annotator_id"]: row for row in synthetic_report["passes"]}
    assert set(passes) == {"llm-recon-a", "llm-recon-b"}
    for row in passes.values():
        assert row["state"] == "frozen"
        assert len(row["judgments_sha256"]) == 64
        assert row["judgment_count"] == len(synthetic_report["selection"])


def test_the_report_states_that_both_annotators_are_llm_passes(
    synthetic_report: dict[str, Any]
) -> None:
    """Section 17.9: two model passes are not two people."""
    assert {a["kind"] for a in synthetic_report["annotators"]} == {"llm"}
    assert len(synthetic_report["annotators"]) == 2
    for text in (
        synthetic_report["study"]["instrument"],
        synthetic_report["agreement"]["caveat"],
    ):
        assert "LLM" in text
        assert "NOT human inter-rater reliability" in text


def test_the_report_declares_all_four_explanations_and_its_thresholds(
    synthetic_report: dict[str, Any]
) -> None:
    """Thresholds declared in the artifact are thresholds a reader can dispute."""
    declared = [e["explanation_id"] for e in synthetic_report["study"]["explanations"]]
    assert declared == list(recon.EXPLANATION_IDS)
    thresholds = synthetic_report["policy"]["decision_thresholds"]
    assert thresholds["material_share"] == recon.MATERIAL_SHARE
    assert thresholds["negligible_share"] == recon.NEGLIGIBLE_SHARE
    assert thresholds["predominance_share"] == recon.PREDOMINANCE_SHARE
    criteria = {c["explanation_id"] for c in synthetic_report["verdict"]["criteria"]}
    assert criteria == set(recon.EXPLANATION_IDS)


def test_the_report_records_the_blinding_it_performed(
    synthetic_report: dict[str, Any]
) -> None:
    blinding = synthetic_report["blinding"]
    assert blinding["visible_to_classifier"] == list(recon.CLASSIFIER_VISIBLE_FIELDS)
    assert "signals_fired" in blinding["withheld_from_classifier"]
    assert set(blinding["withheld_from_classifier"]).isdisjoint(
        blinding["visible_to_classifier"]
    )


# -- the closed verdict vocabulary -------------------------------------------


def _with_verdict(report: dict[str, Any], explanation: str) -> dict[str, Any]:
    return {**report, "verdict": {**report["verdict"], "explanation": explanation}}


@pytest.mark.parametrize("explanation", [*recon.EXPLANATION_IDS, "undecided"])
def test_every_value_in_the_vocabulary_is_admissible(
    synthetic_report: dict[str, Any], now_ctx: Context, explanation: str
) -> None:
    """All five outcomes validate, ``undecided`` included."""
    assert now_ctx.schemas.validate_document(_with_verdict(synthetic_report, explanation)) == (
        recon.SCHEMA_ID
    )


@pytest.mark.parametrize(
    "explanation",
    [
        "miner_is_fine",
        "TRUE_CORPUS_ABSENCE",
        "candidate_mining_deficiency ",
        "inconclusive",
        "",
    ],
)
def test_a_verdict_outside_the_vocabulary_is_refused(
    synthetic_report: dict[str, Any], now_ctx: Context, explanation: str
) -> None:
    """The enum is the vocabulary; near-miss spellings are refused."""
    with pytest.raises(Exception):
        now_ctx.schemas.validate_document(_with_verdict(synthetic_report, explanation))


def test_the_decision_rule_can_return_nothing_but_the_vocabulary() -> None:
    """Every reachable combination of supported criteria, not a sampled few.

    ``decide`` reads only which criteria are supported, so the sixteen subsets
    of four booleans are the whole input space of the decision. Enumerating it
    is what makes "cannot return a value outside the vocabulary" a proof rather
    than an assertion about the cases somebody thought of.
    """
    vocabulary = {*recon.EXPLANATION_IDS, "undecided"}
    seen: set[str] = set()
    for mask in range(1 << len(recon.EXPLANATION_IDS)):
        criteria = [
            {
                "explanation_id": eid,
                "supported": bool(mask & (1 << i)),
                "test": "t",
                "observed": "o",
            }
            for i, eid in enumerate(recon.EXPLANATION_IDS)
        ]
        explanation, statement, resolve = recon.decide(criteria)
        assert explanation in vocabulary, explanation
        assert statement.strip()
        assert resolve, explanation
        seen.add(explanation)
        supported = [c["explanation_id"] for c in criteria if c["supported"]]
        assert explanation == (supported[0] if len(supported) == 1 else "undecided")
    assert seen == vocabulary, "an outcome no combination reaches is an outcome nobody tested"


# -- the narrative -----------------------------------------------------------


@pytest.fixture(scope="module")
def shipped(synthetic_report: dict[str, Any]) -> dict[str, Any]:
    """Compatibility name for reusable rendering tests over synthetic output."""
    return synthetic_report
@pytest.fixture(scope="module")
def narrative(shipped: dict[str, Any]) -> str:
    return recon.render_report_markdown(shipped)


def test_every_figure_in_the_narrative_moves_when_the_report_does(
    shipped: dict[str, Any], narrative: str
) -> None:
    """A number transcribed by hand would survive a change to its source."""
    agreement = shipped["agreement"]
    compared = agreement["compared"]
    assert f"{agreement['agreed']}/{compared}" in narrative

    moved = {
        **shipped,
        "agreement": {**agreement, "agreed": agreement["agreed"] - 7},
        "corpus": {**shipped["corpus"], "authorised_documents": 11},
    }
    rendered = recon.render_report_markdown(moved)
    assert f"{agreement['agreed'] - 7}/{compared}" in rendered
    assert f"{agreement['agreed']}/{compared}" not in rendered
    assert "authorised corpus of 11 documents" in rendered
    assert f"corpus of {shipped['corpus']['authorised_documents']} documents" not in rendered


def test_the_narrative_states_the_blinding_and_can_state_its_failure(
    shipped: dict[str, Any], narrative: str
) -> None:
    """A document that could only report success would be reporting nothing."""
    holds, statement = recon.blinding_holds(shipped)
    assert holds
    assert statement in narrative
    assert "signals_fired" in shipped["blinding"]["withheld_from_classifier"]

    leaked = {
        **shipped,
        "blinding": {
            **shipped["blinding"],
            "visible_to_classifier": [
                *shipped["blinding"]["visible_to_classifier"],
                "signals_fired",
            ],
            "withheld_from_classifier": [
                f for f in shipped["blinding"]["withheld_from_classifier"]
                if f != "signals_fired"
            ],
        },
    }
    holds, statement = recon.blinding_holds(leaked)
    assert not holds
    assert "does not hold" in statement
    assert statement in recon.render_report_markdown(leaked)

    silent = {
        **shipped,
        "blinding": {
            **shipped["blinding"],
            "withheld_from_classifier": [
                f
                for f in shipped["blinding"]["withheld_from_classifier"]
                if f not in ("signals_fired", "signal_count")
            ],
        },
    }
    holds, statement = recon.blinding_holds(silent)
    assert not holds, "a field in neither set is unaccounted for, not withheld"
    assert "cannot be confirmed" in statement


def test_the_narrative_argues_against_every_rejected_alternative(
    shipped: dict[str, Any], narrative: str
) -> None:
    """A verdict without its rejected alternatives is an assertion."""
    chosen = shipped["verdict"]["explanation"]
    assert chosen != "undecided", "this test reads the decided branch"
    body = narrative.split("### Why not each of the others", 1)[1]
    for criterion in shipped["verdict"]["criteria"]:
        other = criterion["explanation_id"]
        if other == chosen:
            continue
        assert f"**Not `{other}`.**" in body, other
        assert criterion["test"] in body, other
        assert criterion["observed"] in body, other
    assert "**Not `undecided`.**" in body


def test_an_undecided_narrative_says_what_it_could_not_conclude(
    shipped: dict[str, Any]
) -> None:
    """``undecided`` has to render as a result, not as a missing section."""
    criteria = shipped["verdict"]["criteria"]
    for supported, heading in (
        ([False] * len(criteria), "### Why no explanation at all"),
        ([True] * len(criteria), "### Why no single explanation"),
    ):
        forced = [
            {**c, "supported": flag} for c, flag in zip(criteria, supported, strict=True)
        ]
        explanation, statement, resolve = recon.decide(forced)
        assert explanation == "undecided"
        rendered = recon.render_report_markdown(
            {
                **shipped,
                "verdict": {
                    **shipped["verdict"],
                    "explanation": explanation,
                    "statement": statement,
                    "criteria": forced,
                    "what_would_resolve": resolve,
                },
            }
        )
        assert heading in rendered
        assert "**Not `undecided`.**" not in rendered
        for line in resolve:
            assert line in rendered


def test_the_narrative_never_reports_a_share_of_nothing(shipped: dict[str, Any]) -> None:
    """ADR-0002 in the prose layer: an empty denominator is not zero percent."""
    empty = {
        **shipped,
        "verdict": {
            **shipped["verdict"],
            "counts": {
                **shipped["verdict"]["counts"],
                "specify_either": 0,
                "specify_with_context_request": 0,
            },
        },
    }
    rendered = recon.render_report_markdown(empty)
    assert "0/0 (no denominator)" in rendered
    assert "0/0 (0.0%)" not in rendered
    assert "No pass called any bundle SPECIFY" in rendered


def test_the_narrative_reports_the_context_requests_and_refuses_to_settle_on_them(
    shipped: dict[str, Any], narrative: str
) -> None:
    """The most interesting ratio in the study, with what it does not license."""
    counts = shipped["verdict"]["counts"]
    linked = counts["specify_with_context_request"]
    specify_either = counts["specify_either"]
    assert f"{linked}/{specify_either}" in narrative
    assert f"n = {specify_either}" in narrative
    assert "context_bundle_deficiency" in narrative
    assert "cannot settle the question against `candidate_mining_deficiency`" in narrative


def test_the_narrative_states_its_small_n_and_what_that_costs(
    shipped: dict[str, Any], narrative: str
) -> None:
    """Forty bundles and two model passes, said in the document rather than inferred."""
    counts = shipped["verdict"]["counts"]
    limits = narrative.split("## Limits", 1)[1]
    assert f"n = {counts['selected']} bundles" in limits
    assert "instrument reproducibility rather than inter-rater reliability" in limits
    needed = -(-int(recon.MATERIAL_SHARE * 100) * counts["compared"] // 100)
    assert f"reach {needed} bundles" in limits
    assert "does not license a change to the miner" in limits


def test_the_narrative_separates_completeness_from_a_missing_enclosing_section(
    shipped: dict[str, Any], narrative: str
) -> None:
    """`insufficient` on every bundle is not evidence the surrounding prose was dropped."""
    availability = shipped["bundle_context"]["dimension_availability"]
    assert set(availability["preceding_context"]) == {"present"}
    assert set(availability["review_comment"]) == {"not_searched"}
    assert "is not a claim that the enclosing prose was withheld" in narrative
    for dimension in recon.CONTEXT_DIMENSIONS:
        assert f"| `{dimension}` |" in narrative

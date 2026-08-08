"""Profile hypotheses: what the corpus layer may record and what it refuses.

These tests defend staying inside evidence: section scope rather than document
scope, declared vocabularies rather than filenames, several candidates rather
than one, and REVIEW_REQUIRED rather than a decision.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
from pathlib import Path

import pytest

from ats.canonical import canonical_bytes
from ats.context import Context
from ats.corpus import inventory as inv
from ats.corpus import profile as pf
from ats.corpus import records as rec
from ats.errors import SchemaValidationError

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)

ARTIFACT = "ats-artifact-sha256:" + "a" * 64
REVISION = "0" * 40

#: A section whose only cues are ASSESS cues. Used with a SPECIFY-suggesting
#: filename, so that "no SPECIFY" is a statement about the generator rather than
#: about an empty document.
ASSESS_BODY = """# Migration outlook

Judgment: moving the acceptance kernel to Rust is likely to reduce
invalid-state defects. The benchmark suggests the effect is real.
"""

MIXED_BODY = """## Receipt verification

Judgment: stale receipts are likely to reach the verifier under load.
The verifier MUST reject a receipt whose policy hash is stale.
"""

#: Deliberately arranged so that discovery order and the declared order
#: disagree on all three axes: three candidate profiles, two deontic surfaces
#: whose document order (MUST then MAY) is reverse alphabetical, and ASSESS
#: evidence whose matcher order (role, heading, likelihood, evidential) differs
#: from its sorted order.
ORDERING_BODY = """## Boundaries on receipt handling

<!-- ats:profile X-ARQ-EXPLAIN -->

Judgment: stale receipts are very likely to reach the verifier. The replay
evidence suggests the race is real.
The verifier MUST reject a stale receipt.
The operator MAY override the refusal once.
"""


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


def hypotheses(ctx: Context, text: str, *, path: str = "docs/note.md") -> list[dict]:
    records, _examined = pf.document_hypotheses(
        ctx, text, source_artifact_id=ARTIFACT, path=path, revision=REVISION
    )
    return records


def profiles_of(records: list[dict]) -> set[str]:
    return {c["profile"] for r in records for c in r["candidate_profiles"]}


# -- schema ------------------------------------------------------------------


def test_a_generated_record_validates_against_its_schema(ctx: Context) -> None:
    """The record type is registered and the generator emits a conforming instance."""
    records = hypotheses(ctx, MIXED_BODY)
    assert records
    for record in records:
        assert ctx.schemas.validate_document(record) == "ats_profile_hypothesis_v1.schema.json"
        assert rec.verify_record(record)[0]


def test_a_resolved_decision_must_name_who_resolved_it(ctx: Context) -> None:
    """Spec 13.7: a profile selection with no decider is self-adjudication."""
    record = dict(hypotheses(ctx, MIXED_BODY)[0])
    record["decision"] = {"state": "RESOLVED", "resolved_profile": "SPECIFY"}
    with pytest.raises(SchemaValidationError):
        ctx.schemas.validate_document(record)


def test_review_required_may_not_carry_a_profile(ctx: Context) -> None:
    """An unresolved record that names a resolved profile is resolved in all but name."""
    record = dict(hypotheses(ctx, MIXED_BODY)[0])
    record["decision"] = {"state": "REVIEW_REQUIRED", "resolved_profile": "SPECIFY"}
    with pytest.raises(SchemaValidationError):
        ctx.schemas.validate_document(record)


def test_a_candidate_with_no_basis_is_refused(ctx: Context) -> None:
    """A profile named with no evidence behind it is a guess wearing a record."""
    record = dict(hypotheses(ctx, MIXED_BODY)[0])
    record["candidate_profiles"] = [
        {
            "profile": "SPECIFY",
            "basis": [],
            "status": "hypothesis",
            "conformance_claim_permitted": True,
        }
    ]
    with pytest.raises(SchemaValidationError):
        ctx.schemas.validate_document(record)


# -- what may not be inferred -------------------------------------------------


def test_a_filename_never_drives_a_profile(ctx: Context) -> None:
    """Spec 3.2: a profile is the reader job the prose does, not what the file is called."""
    records = hypotheses(ctx, ASSESS_BODY, path="docs/SPECIFICATION.md")
    assert records, "the document has ASSESS evidence, so it must produce a record"
    assert profiles_of(records) == {"ASSESS"}


def test_no_basis_is_ever_drawn_from_outside_the_prose(ctx: Context) -> None:
    """Every admissible evidence kind reads the scope's own text."""
    outside = {"filename", "path", "repository", "directory", "sibling_document"}
    kinds = {
        b["kind"]
        for r in hypotheses(ctx, MIXED_BODY, path="specs/SPECIFICATION.md")
        for c in r["candidate_profiles"]
        for b in c["basis"]
    }
    assert kinds
    assert not kinds & outside


def test_a_scope_with_no_evidence_yields_no_record(ctx: Context) -> None:
    """Spec 5.4: silence is not a profile, and it is not "no profile" either."""
    text = "## Storage layout\n\nDocuments are stored one per blob under the pinned revision.\n"
    records, examined = pf.document_hypotheses(
        ctx, text, source_artifact_id=ARTIFACT, path="docs/note.md", revision=REVISION
    )
    assert examined == 1
    assert records == []


def test_a_generated_decision_is_always_review_required(ctx: Context) -> None:
    """Spec 13.7, 14.11: the generator may not adjudicate its own output."""
    for record in hypotheses(ctx, MIXED_BODY):
        assert record["decision"] == {"state": "REVIEW_REQUIRED"}


def test_the_constructor_offers_no_way_to_resolve_a_record(ctx: Context) -> None:
    """The refusal is structural: there is no decision parameter to pass."""
    import inspect

    assert "decision" not in inspect.signature(pf.profile_hypothesis).parameters


def test_every_record_restates_the_refusals(ctx: Context) -> None:
    """A reviewer reading one record sees every inference the generator declined."""
    for record in hypotheses(ctx, MIXED_BODY):
        declared = {r["refusal_id"] for r in record["generator"]["refusals"]}
        assert declared == set(pf.REFUSAL_IDS)


# -- conformance claims -------------------------------------------------------


def test_only_a_core_profile_may_carry_a_conformance_claim(ctx: Context) -> None:
    """Spec 3.3: a reserved profile may be experimented with, never claimed as core."""
    for core in pf.core_profiles(ctx):
        assert pf.may_carry_conformance_claim(ctx, core)
    for namespaced in ("X-ARQ-EXPLAIN", "X-ARQ-EXPLAIN-1", "ATS-X-VENDOR-DECIDE"):
        assert pf.is_extension_profile(ctx, namespaced)
        assert not pf.may_carry_conformance_claim(ctx, namespaced)


def test_a_bare_reserved_profile_is_not_recordable(ctx: Context) -> None:
    """Spec 3.3 requires the namespace, so `EXPLAIN` is neither core nor an extension."""
    assert not pf.may_carry_conformance_claim(ctx, "EXPLAIN")
    assert not pf.is_extension_profile(ctx, "EXPLAIN")
    assert not pf.is_recordable_profile(ctx, "EXPLAIN")


def test_a_namespaced_profile_is_recorded_without_a_conformance_claim(ctx: Context) -> None:
    """Spec 9.5: preserve the identifier, report it as unsupported, never map it to ASSESS."""
    text = "## Explanation\n\n<!-- ats:profile X-ARQ-EXPLAIN -->\n\nThe kernel loads a policy.\n"
    records = hypotheses(ctx, text)
    candidates = [c for r in records for c in r["candidate_profiles"]]
    assert [c["profile"] for c in candidates] == ["X-ARQ-EXPLAIN"]
    assert candidates[0]["conformance_claim_permitted"] is False
    assert ctx.schemas.validate_document(records[0])


def test_an_unnamespaced_reserved_marker_raises_no_candidate(ctx: Context) -> None:
    """A declaration the standard forbids is not made admissible by being declared."""
    text = "## Explanation\n\n<!-- ats:profile EXPLAIN -->\n\nThe kernel loads a policy.\n"
    assert hypotheses(ctx, text) == []


# -- mixed artifacts ----------------------------------------------------------


def test_a_mixed_section_keeps_every_candidate(ctx: Context) -> None:
    """Spec 9.4 composes profiles; collapsing to one would delete the composition."""
    records = hypotheses(ctx, MIXED_BODY)
    assert len(records) == 1
    candidates = records[0]["candidate_profiles"]
    assert [c["profile"] for c in candidates] == ["ASSESS", "SPECIFY"]
    assert {c["status"] for c in candidates} == {"hypothesis"}


def test_a_document_is_split_into_sections_not_judged_whole(ctx: Context) -> None:
    """Spec 9.4: two sections of different character get two records, not one verdict."""
    text = ASSESS_BODY + "\n" + MIXED_BODY.replace(
        "Judgment: stale receipts are likely to reach the verifier under load.\n", ""
    )
    records = hypotheses(ctx, text)
    assert len(records) == 2
    assert [r["scope"]["heading_path"] for r in records] == [
        ["Migration outlook"],
        ["Migration outlook", "Receipt verification"],
    ]
    assert [[c["profile"] for c in r["candidate_profiles"]] for r in records] == [
        ["ASSESS"],
        ["SPECIFY"],
    ]


# -- evidence discipline ------------------------------------------------------


def test_a_deontic_keyword_inside_a_code_block_is_not_evidence(ctx: Context) -> None:
    """Spec 5.6 exempts code and quoted material, so a keyword there is a quotation."""
    text = "## Notes\n\n```text\nThe verifier MUST reject a stale receipt.\n```\n"
    assert hypotheses(ctx, text) == []


def test_deontic_surfaces_are_matched_case_sensitively(ctx: Context) -> None:
    """Spec 1.3: the keywords are normative only in uppercase."""
    text = "## Notes\n\nThe verifier must reject a stale receipt.\n"
    assert hypotheses(ctx, text) == []
    assert profiles_of(hypotheses(ctx, text.replace("must", "MUST"))) == {"SPECIFY"}


def test_one_requirement_slot_label_is_not_a_requirement_object(ctx: Context) -> None:
    """Spec 9.3.2 describes an object with several slots; one label is a paragraph heading."""
    one = "## Notes\n\nActor: the verifier.\n"
    two = one + "\nTrigger: a receipt arrives.\n"
    assert hypotheses(ctx, one) == []
    assert profiles_of(hypotheses(ctx, two)) == {"SPECIFY"}


def test_a_heading_term_both_profiles_name_is_evidence_for_neither(ctx: Context) -> None:
    """Sections 9.2.2 and 9.3.2 both name `scope`, so a Scope heading discriminates nothing."""
    assert "scope" not in pf.heading_vocabulary(ctx)
    assert hypotheses(ctx, "## Scope\n\nThis applies to the acceptance kernel.\n") == []


def test_role_mappings_stay_current_with_the_normative_enum(ctx: Context) -> None:
    """A stale mapping would silently stop producing evidence rather than failing."""
    pf.check_vocabulary_currency(ctx)
    assert set(pf.ROLE_PROFILE) <= set(pf.claim_roles(ctx))


def test_every_basis_names_a_declared_vocabulary(ctx: Context) -> None:
    """A term outside the declared sources is not evidence (North Star: no invented vocabulary)."""
    for record in hypotheses(ctx, MIXED_BODY):
        assert set(record["generator"]["evidence_sources"]) == set(pf.EVIDENCE_SOURCES)
        for candidate in record["candidate_profiles"]:
            for basis in candidate["basis"]:
                assert basis["vocabulary_source"]
                assert basis["spec_ref"].startswith("ATS-1 ")


# -- generation over a repository ---------------------------------------------

_GIT_IDENTITY = (
    "-c",
    "user.name=ATS Fixture",
    "-c",
    "user.email=fixture@ats.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "init.defaultBranch=main",
)
_GIT_ENV = {
    "PATH": os.environ.get("PATH", ""),
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_CONFIG_NOSYSTEM": "1",
    "LC_ALL": "C",
    "TZ": "UTC",
    "GIT_AUTHOR_DATE": "2026-01-05T09:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-05T09:00:00+00:00",
}

AUTHORISED_DECLARATION = """{
  "schema_version": "ats.corpus_authority.v1",
  "principal": { "id": "https://example.invalid/fixture-owner", "kind": "person" },
  "authority_basis": {
    "kind": "owner_declared",
    "statement": "The principal authored every commit in this synthetic fixture."
  },
  "repository": {
    "name": "profile-fixture",
    "origin": null,
    "root_commit": "0000000000000000000000000000000000000000000000000000000000000000",
    "effective_from_revision": "0000000000000000000000000000000000000000",
    "declaration_location": "repository"
  },
  "uses": {
    "inventory": "allow",
    "candidate_mining": "allow",
    "human_annotation": "allow",
    "deterministic_mutation": "defer",
    "evaluation": "allow",
    "model_training": "defer",
    "model_distillation": "defer",
    "external_model_submission": "deny",
    "publication": "deny",
    "cross_repository_derivatives": "defer"
  },
  "content": { "include": ["*"] },
  "issued_at": "2026-01-01T00:00:00+00:00",
  "review_after": "2027-01-01T00:00:00+00:00",
  "superseded_by": null,
  "handling": { "classification": "private", "export_raw_text": false },
  "provenance": {
    "authorship": "unknown_unless_explicit",
    "model_authorship_inference": "prohibited"
  }
}
"""


def _build_repo(dest: Path, *, declared: bool) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    files = {"docs/SPECIFICATION.md": ASSESS_BODY, "docs/verification.md": MIXED_BODY}
    if declared:
        files[".ats/corpus.json"] = AUTHORISED_DECLARATION
    for relative, content in files.items():
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    subprocess.run(
        ["git", *_GIT_IDENTITY, "init", "--quiet"], cwd=dest, env=_GIT_ENV, check=True
    )
    subprocess.run(["git", *_GIT_IDENTITY, "add", "--all"], cwd=dest, env=_GIT_ENV, check=True)
    subprocess.run(
        ["git", *_GIT_IDENTITY, "commit", "--quiet", "-m", "seed"],
        cwd=dest,
        env=_GIT_ENV,
        check=True,
    )
    return dest


@pytest.fixture(scope="module")
def authorised_repo(tmp_path_factory) -> Path:
    return _build_repo(tmp_path_factory.mktemp("git") / "profile-fixture", declared=True)


@pytest.fixture(scope="module")
def generated(ctx: Context, authorised_repo: Path) -> dict:
    inventory = inv.build_inventory(ctx, authorised_repo)
    return pf.build_profile_hypotheses(ctx, inventory, repo_path=str(authorised_repo))


def test_generation_over_a_repository_is_section_scoped_and_unresolved(
    ctx: Context, generated: dict
) -> None:
    """The acceptance shape: real repository in, reviewable section hypotheses out."""
    assert generated["skipped"] == []
    assert generated["hypotheses"]
    assert generated["scopes_examined"] >= generated["scopes_with_evidence"]
    for record in generated["hypotheses"]:
        assert ctx.schemas.validate_document(record)
        assert record["decision"]["state"] == "REVIEW_REQUIRED"
        assert record["scope"]["heading_path"]
        assert record["scope"]["start_line"] <= record["scope"]["end_line"]
        assert record["authority"]["use"] == "candidate_mining"
        assert record["authority"]["permitted"] is True


def test_a_specify_named_file_produces_no_specify_hypothesis(generated: dict) -> None:
    """The filename refusal, on a real file actually named SPECIFICATION.md."""
    named = [r for r in generated["hypotheses"] if r["path"] == "docs/SPECIFICATION.md"]
    assert named, "the file has ASSESS evidence, so it must produce a record"
    assert {c["profile"] for r in named for c in r["candidate_profiles"]} == {"ASSESS"}


def test_generation_is_deterministic(ctx: Context, authorised_repo: Path, generated: dict) -> None:
    """Spec 16.2: identical canonical inputs produce identical bytes, ids included."""
    inventory = inv.build_inventory(ctx, authorised_repo)
    again = pf.build_profile_hypotheses(ctx, inventory, repo_path=str(authorised_repo))
    assert canonical_bytes(again["hypotheses"]) == canonical_bytes(generated["hypotheses"])
    assert [r["hypothesis_id"] for r in again["hypotheses"]] == [
        r["hypothesis_id"] for r in generated["hypotheses"]
    ]


def test_output_order_is_a_function_of_the_evidence(ctx: Context) -> None:
    """A record's bytes are its identity, so nothing may be emitted in discovery order.

    Comparing two runs in one process cannot see this: a discovery-order bug is
    perfectly reproducible within a process and only diverges once a dict, a
    parser, or a filesystem walk changes. The ordering *rule* is what has to
    hold, so it is asserted directly.
    """
    record = hypotheses(ctx, ORDERING_BODY)[0]
    profiles = [c["profile"] for c in record["candidate_profiles"]]
    assert profiles == ["ASSESS", "SPECIFY", "X-ARQ-EXPLAIN"] == sorted(profiles)
    for candidate in record["candidate_profiles"]:
        keys = [(b["kind"], b["detail"], b["first_line"]) for b in candidate["basis"]]
        assert keys == sorted(keys)
    assess = next(c for c in record["candidate_profiles"] if c["profile"] == "ASSESS")
    assert [b["kind"] for b in assess["basis"]] == [
        "claim_role_label",
        "evidential_force_term",
        "heading_role_term",
        "likelihood_term",
    ]
    specify = next(c for c in record["candidate_profiles"] if c["profile"] == "SPECIFY")
    assert [b["detail"] for b in specify["basis"]] == ["MAY", "MUST"]


def test_an_undeclared_repository_is_skipped_not_mined(ctx: Context, tmp_path: Path) -> None:
    """Local availability of source text is not authority to derive from it (16.9, 17.13)."""
    repo = _build_repo(tmp_path / "undeclared", declared=False)
    inventory = inv.build_inventory(ctx, repo)
    out = pf.build_profile_hypotheses(
        ctx, inventory, repo_path=str(repo), authority_overlay=None
    )
    assert out["hypotheses"] == []
    assert out["skipped"]
    assert {s["reason"] for s in out["skipped"]} == {"authority"}
    assert all("no-declaration" in s["basis"] for s in out["skipped"])

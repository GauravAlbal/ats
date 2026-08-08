"""Authorship is declared, never inferred.

Defends spec Section 17.4 (mining preserves what the source recorded and infers
nothing else) and ADR-0002 (a check that cannot answer reports its
unavailability rather than a plausible default). These tests ensure silence
can never be read as "written by a human".
"""

from __future__ import annotations

import datetime as dt
import sys

import pytest

from ats.context import Context
from ats.corpus import authorship as auth
from ats.corpus import inventory as inv
from ats.corpus.authority import AuthorityDeclaration
from ats.errors import UsageError
from ats.spec_package import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
from generate_corpus_fixtures import _git as write_git  # noqa: E402
from generate_corpus_fixtures import build_sample_repo  # noqa: E402

NOW = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)

#: Every evidence source the reader must report on, found or not.
SEARCH_LABELS = (
    "commit trailers",
    "artifact receipts",
    "agent run manifests",
    "execution traces",
    "document text",
)

#: Prose a stylometric guess would call model-written: hedged openers, tidy
#: parallel bullets, and the tell-tale connective vocabulary.
MODEL_SHAPED_PROSE = """# Migration considerations

It's important to note that this document delves into the key considerations
surrounding the migration. Let's explore the landscape together.

- **Robustness**: the kernel is robust under the current load.
- **Scalability**: the design scales seamlessly across the fleet.
- **Maintainability**: the abstractions remain clean and idiomatic.

In conclusion, it is worth noting that the migration represents a significant
step forward in our journey toward operational excellence.
"""

#: The same phrasing again, so phrase reuse across documents is available as a
#: signal to anything tempted to read one.
REUSED_PROSE = """# Retention considerations

It's important to note that this document delves into the key considerations
surrounding the migration. Let's explore the landscape together.

The kernel is robust under the current load.
"""

AGENT_CONFIG = """# CLAUDE.md

Instructions for the coding agent that works in this repository. Always run the
test suite before committing.
"""


@pytest.fixture(scope="module")
def ctx() -> Context:
    return Context.load(now=NOW)


@pytest.fixture(scope="module")
def signals_repo(tmp_path_factory):
    """A real repository carrying every prohibited inference signal at once.

    One commit, authored at 03:00 by an agent-shaped identity, adding a large
    body of model-shaped prose plus a repeated passage, into a repository whose
    root holds a ``CLAUDE.md``. Nothing here declares authorship, so the honest
    answer for every document is ``unknown``.
    """
    repo = tmp_path_factory.mktemp("git") / "signals-repo"
    repo.mkdir(parents=True)
    write_git(repo, "init", "--quiet")
    (repo / "CLAUDE.md").write_text(AGENT_CONFIG, encoding="utf-8")
    docs = repo / "docs"
    docs.mkdir()
    (docs / "migration.md").write_text(MODEL_SHAPED_PROSE, encoding="utf-8")
    (docs / "retention.md").write_text(REUSED_PROSE, encoding="utf-8")
    # A deliberately large single commit, so commit size is on the table.
    (docs / "bulk.md").write_text(
        "# Bulk\n\n" + "".join(f"Paragraph {i} of the bulk import.\n\n" for i in range(400)),
        encoding="utf-8",
    )
    write_git(repo, "add", "--all")
    write_git(
        repo,
        "commit",
        "--quiet",
        "-m",
        "Import the migration notes\n",
        "--author=Claude Code <noreply@anthropic.invalid>",
        date="2026-01-08T03:00:00+00:00",
    )
    return repo


@pytest.fixture(scope="module")
def signals_inventory(ctx: Context, signals_repo):
    return inv.build_inventory(ctx, signals_repo)


@pytest.fixture(scope="module")
def declared_repo(tmp_path_factory):
    """The sample fixture repository, whose second commit declares ``ATS-Model``."""
    return build_sample_repo(tmp_path_factory.mktemp("git") / "sample-repo")


@pytest.fixture(scope="module")
def declared_inventory(ctx: Context, declared_repo):
    return inv.build_inventory(ctx, declared_repo)


def _by_path(inventory) -> dict[str, dict]:
    return {a["path"]: a for a in inventory["artifacts"]}


def _authorship(inventory, path: str) -> dict:
    return _by_path(inventory)[path]["model_provenance"]["authorship"]


# -- the default ------------------------------------------------------------


def test_unknown_is_the_default_with_nothing_supplied() -> None:
    """Absence of evidence is unknown authorship, not human authorship."""
    reading = auth.read_authorship(locator="git:deadbeef")
    assert reading.value == "unknown"
    assert reading.evidence == ()
    assert not reading.declared


def test_a_value_off_unknown_cannot_be_constructed_without_evidence() -> None:
    """The invariant is structural: an unevidenced label must not be representable."""
    for value in ("human", "model", "mixed"):
        with pytest.raises(UsageError, match="no evidence"):
            auth.Authorship(
                value=value,
                perspective=auth.RETROSPECTIVE,
                evidence=(),
                searched=("nothing",),
                inference_policy=auth.INFERENCE_PROHIBITED,
            )


def test_a_reading_must_say_what_it_searched() -> None:
    """A bare result cannot distinguish 'searched and not found' from 'never looked'."""
    with pytest.raises(UsageError, match="what it looked at"):
        auth.Authorship(
            value="unknown",
            perspective=auth.RETROSPECTIVE,
            evidence=(),
            searched=(),
            inference_policy=auth.INFERENCE_PROHIBITED,
        )


def test_unknown_carries_the_list_of_sources_searched() -> None:
    """ADR-0002: an unavailable answer names what was consulted, never a bare null."""
    reading = auth.read_authorship(locator="git:deadbeef", document_text="# Plain\n")
    joined = "\n".join(reading.searched)
    for label in SEARCH_LABELS:
        assert label in joined, label
    for signal in auth.PROHIBITED_SIGNALS:
        assert signal in joined, signal


def test_uncited_evidence_is_refused() -> None:
    """A declaration nobody can check is an assertion, not evidence."""
    with pytest.raises(UsageError, match="no locator"):
        auth.AuthorshipEvidence(
            kind="commit_trailer", value="model", locator="", detail="trust me"
        )


# -- over real repositories -------------------------------------------------


def test_every_document_in_a_repository_without_declarations_is_unknown(
    signals_inventory,
) -> None:
    """Spec 17.4: the corpus never claims authorship the repository did not record."""
    assert len(signals_inventory["artifacts"]) == 4
    for artifact in signals_inventory["artifacts"]:
        record = artifact["model_provenance"]["authorship"]
        assert record["value"] == "unknown", artifact["path"]
        assert record["evidence"] == [], artifact["path"]
        joined = "\n".join(record["searched"])
        for label in SEARCH_LABELS:
            assert label in joined, (artifact["path"], label)


@pytest.mark.parametrize("signal", auth.PROHIBITED_SIGNALS)
def test_a_prohibited_signal_does_not_move_the_value(signals_inventory, signal: str) -> None:
    """Each named signal is present in the fixture repository and moves nothing.

    ``prose_style`` and ``phrase_reuse`` are in ``docs/migration.md`` and
    ``docs/retention.md``, ``commit_size`` in ``docs/bulk.md``,
    ``author_identity`` and ``commit_timestamp`` on the single commit, and
    ``repository_agent_configuration`` is ``CLAUDE.md`` at the repository root.
    """
    assert signal not in auth.EVIDENCE_KINDS
    values = {a["model_provenance"]["authorship"]["value"] for a in signals_inventory["artifacts"]}
    assert values == {"unknown"}
    # The signal is genuinely present, so the test is not passing vacuously.
    git = _by_path(signals_inventory)["docs/bulk.md"]["extensions"]["x-ats-repo-git"]
    assert git["history"]["commits"][0]["authored_at"].startswith("2026-01-08T03:00")


def test_an_agent_config_file_is_just_another_unknown_document(signals_inventory) -> None:
    """A CLAUDE.md says an agent works here; it says nothing about who wrote a document."""
    assert "CLAUDE.md" in _by_path(signals_inventory)
    assert _authorship(signals_inventory, "CLAUDE.md")["value"] == "unknown"
    assert _authorship(signals_inventory, "docs/migration.md")["value"] == "unknown"


def test_an_ats_model_trailer_resolves_model_and_cites_itself(declared_inventory) -> None:
    """The one thing that does move the value: a commit deliberately recording generation."""
    record = _authorship(declared_inventory, "docs/assessment.md")
    assert record["value"] == "model"
    assert record["perspective"] == auth.RETROSPECTIVE
    [evidence] = record["evidence"]
    assert evidence["kind"] == "commit_trailer"
    assert evidence["model"] == {"name": "fixture-writer", "version": "1.0.0"}
    assert evidence["locator"].startswith("git:")
    assert inv.TRAILER_MODEL in evidence["detail"]
    # The older shape is preserved beside the reading, not replaced by it.
    assert _by_path(declared_inventory)["docs/assessment.md"]["model_provenance"][
        "availability"
    ] == "present"


def test_a_sibling_document_in_the_same_repository_stays_unknown(declared_inventory) -> None:
    """A declaration is about the commit that carries it, never about the repository."""
    assert _authorship(declared_inventory, "docs/requirements.md")["value"] == "unknown"


# -- in-document declarations ----------------------------------------------


@pytest.mark.parametrize("declared", ["human", "model", "mixed"])
def test_front_matter_declares_authorship(declared: str) -> None:
    """Structured authorship front matter is an explicit declaration and is honoured."""
    text = f"---\nats-authorship: {declared}\nats-model: fixture@2.0.0\n---\n\n# Title\n"
    reading = auth.read_authorship(locator="git:abc", document_text=text)
    assert reading.value == declared
    [evidence] = reading.evidence
    assert evidence.kind == "document_front_matter"
    assert evidence.model == {"name": "fixture", "version": "2.0.0"}


def test_an_unterminated_fence_is_not_front_matter() -> None:
    """Otherwise the first horizontal rule in a document turns prose into declarations."""
    text = "---\nats-authorship: model\n\n# Title\n\nBody without a closing fence.\n"
    assert auth.front_matter(text) == {}
    assert auth.read_authorship(locator="git:abc", document_text=text).value == "unknown"


def test_a_front_matter_value_outside_the_vocabulary_stays_unknown() -> None:
    """``ats-authorship: ai`` is not one of the four values and declares nothing."""
    text = "---\nats-authorship: ai\n---\n\n# Title\n"
    reading = auth.read_authorship(locator="git:abc", document_text=text)
    assert reading.value == "unknown"
    assert any("not an assertable value" in note for note in reading.searched)


def test_the_marker_form_matches_the_repositorys_other_in_document_declarations() -> None:
    """``<!-- ats:authorship ... -->`` sits in the same family as ats:profile."""
    text = "# Title\n\n<!-- ats:authorship model fixture@3.1.0 -->\n\nBody.\n"
    reading = auth.read_authorship(locator="git:abc", document_text=text)
    assert reading.value == "model"
    assert reading.evidence[0].model == {"name": "fixture", "version": "3.1.0"}


# -- receipts, manifests, and traces ---------------------------------------


@pytest.mark.parametrize(
    "kwarg,kind",
    [
        ("receipts", "artifact_receipt"),
        ("run_manifests", "agent_run_manifest"),
        ("execution_traces", "execution_trace"),
    ],
)
def test_each_declaring_source_resolves_and_is_cited(kwarg: str, kind: str) -> None:
    """All five evidence kinds are equally admissible; each records where to check it."""
    record = {"authorship": "model", "locator": f"{kind}:1", "model": "fixture@1.2.3"}
    reading = auth.read_authorship(locator="git:abc", **{kwarg: [record]})
    assert reading.value == "model"
    [evidence] = reading.evidence
    assert evidence.kind == kind
    assert evidence.locator == f"{kind}:1"
    assert evidence.model == {"name": "fixture", "version": "1.2.3"}


def test_a_declaration_without_a_locator_is_refused() -> None:
    """An uncitable declaration must fail loudly rather than move the value quietly."""
    with pytest.raises(UsageError, match="locator"):
        auth.read_authorship(locator="git:abc", receipts=[{"authorship": "model"}])


def test_a_declaration_outside_the_vocabulary_is_refused() -> None:
    """A producer writing 'ai' gets an error, not an unknown that looks like absence."""
    with pytest.raises(UsageError, match="expected one of"):
        auth.read_authorship(
            locator="git:abc", receipts=[{"authorship": "ai", "locator": "receipt:1"}]
        )


def test_a_source_declaring_unknown_contributes_no_evidence() -> None:
    """Declaring 'unknown' is declining to declare, and is recorded as such."""
    reading = auth.read_authorship(
        locator="git:abc", receipts=[{"authorship": "unknown", "locator": "receipt:1"}]
    )
    assert reading.value == "unknown"
    assert reading.evidence == ()
    assert any("1 searched, none declares" in note for note in reading.searched)


def test_human_and_model_declarations_combine_to_mixed() -> None:
    """Two truthful declarations about a co-authored document are 'mixed', not either one."""
    reading = auth.read_authorship(
        locator="git:abc",
        receipts=[{"authorship": "human", "locator": "receipt:1"}],
        execution_traces=[{"authorship": "model", "locator": "trace:1"}],
    )
    assert reading.value == "mixed"
    assert {e.value for e in reading.evidence} == {"human", "model"}


def test_combine_never_invents_a_value() -> None:
    assert auth.combine([]) == "unknown"
    assert auth.combine(["unknown", "unknown"]) == "unknown"
    assert auth.combine(["human"]) == "human"
    assert auth.combine(["model", "model"]) == "model"
    assert auth.combine(["mixed"]) == "mixed"


# -- authority ---------------------------------------------------------------


class _PermissiveAuthority:
    """A declaration that permits inference. This implementation still will not."""

    def permits_model_authorship_inference(self) -> bool:
        return True


def test_permitted_inference_is_recorded_and_still_not_performed() -> None:
    """Saying so beats silently doing nothing: the reader read the declaration and declined."""
    reading = auth.read_authorship(
        locator="git:abc",
        document_text=MODEL_SHAPED_PROSE,
        authority=_PermissiveAuthority(),
    )
    assert reading.inference_policy == auth.INFERENCE_PERMITTED_UNUSED
    assert reading.value == "unknown"


def test_an_undeclared_repository_records_inference_as_prohibited() -> None:
    """The default from ``AuthorityDeclaration.undeclared`` is 'prohibited', per its own field."""
    declaration = AuthorityDeclaration.undeclared("nobody")
    assert declaration.permits_model_authorship_inference() is False
    reading = auth.read_authorship(locator="git:abc", authority=declaration)
    assert reading.inference_policy == auth.INFERENCE_PROHIBITED


def test_the_inventory_records_the_inference_policy(signals_inventory) -> None:
    for artifact in signals_inventory["artifacts"]:
        assert (
            artifact["model_provenance"]["authorship"]["inference_policy"]
            == auth.INFERENCE_PROHIBITED
        )


# -- prospective: the seven-field binding ------------------------------------


def _binding(**overrides) -> auth.ProspectiveBinding:
    """A complete binding, so a test can vary exactly one field."""
    fields = {
        "producing_skill": "ats-output-authoring",
        "model": {"name": "fixture-writer", "version": "1.0.0"},
        "prompt_identity": "prompt:sha256:2b1f",
        "source_ir": "ir:sha256:9ac4",
        "human_edits": auth.BINDING_NO_HUMAN_EDITS,
        "adjudicator": auth.BINDING_PENDING_ADJUDICATION,
        "acceptance_receipt": auth.BINDING_PENDING_ACCEPTANCE,
    }
    fields.update(overrides)
    return auth.ProspectiveBinding(**fields)


def test_the_binding_carries_all_seven_fields() -> None:
    """Each one determines how the text came to say what it says; none survives it."""
    record = _binding().as_record()
    assert list(record) == list(auth.PROSPECTIVE_BINDING_FIELDS)
    assert record["model"] == {"name": "fixture-writer", "version": "1.0.0"}


@pytest.mark.parametrize(
    "field",
    [f for f in auth.PROSPECTIVE_BINDING_FIELDS if f != "model"],
)
def test_no_binding_field_may_be_left_empty(field: str) -> None:
    """An omitted field cannot say whether there was nothing or nobody recorded it."""
    with pytest.raises(UsageError, match=field):
        _binding(**{field: ""})


def test_a_producer_that_cannot_name_itself_is_refused() -> None:
    """Something produced the artifact; 'not_applicable' for the skill is a defect."""
    with pytest.raises(UsageError, match="producing_skill"):
        _binding(producing_skill=auth.BINDING_NOT_APPLICABLE)


def test_a_bound_model_must_carry_a_version() -> None:
    with pytest.raises(UsageError, match="name and version"):
        _binding(model={"name": "fixture-writer", "version": ""})


def test_a_model_outside_the_two_permitted_shapes_is_refused() -> None:
    with pytest.raises(UsageError, match="not_applicable"):
        _binding(model="unknown")


def test_a_bound_model_implies_a_bound_prompt() -> None:
    """A model that ran ran on an instruction, and the instruction is unrecoverable."""
    with pytest.raises(UsageError, match="prompt_identity"):
        _binding(prompt_identity=auth.BINDING_NOT_APPLICABLE)


def test_a_deterministic_skill_may_declare_no_model_and_no_prompt() -> None:
    """'Where applicable' has to be reachable, or the token is decoration."""
    binding = _binding(
        model=auth.BINDING_NOT_APPLICABLE,
        prompt_identity=auth.BINDING_NOT_APPLICABLE,
        human_edits="wrote the section by hand",
    )
    assert binding.as_record()["model"] == auth.BINDING_NOT_APPLICABLE
    assert auth.system_authorship(binding=binding, run_locator="run:42").value == "human"


def test_a_receipt_with_no_adjudicator_is_refused() -> None:
    """A receipt nobody signed is not an acceptance (spec 14.11)."""
    with pytest.raises(UsageError, match="nobody signed"):
        _binding(acceptance_receipt="arq://receipt/aa11")


def test_the_producer_cannot_name_itself_as_adjudicator() -> None:
    """Spec 13.7: a component must not become the authority for its own output."""
    with pytest.raises(UsageError, match="must be external"):
        _binding(adjudicator="ats", acceptance_receipt="arq://receipt/aa11")


def test_pending_adjudication_and_pending_acceptance_are_distinct_from_absence() -> None:
    """'Not ruled on yet' is a state a producer asserts, not a field it omits."""
    binding = _binding()
    assert not binding.adjudicated and not binding.accepted
    assert binding.as_record()["adjudicator"] == auth.BINDING_PENDING_ADJUDICATION
    assert binding.as_record()["acceptance_receipt"] == auth.BINDING_PENDING_ACCEPTANCE


# -- prospective: the reading -------------------------------------------------


def test_system_authorship_declares_the_model_and_the_run() -> None:
    """An artifact this system produces knows its own authorship; it does not search."""
    reading = auth.system_authorship(binding=_binding(), run_locator="run:42")
    assert reading.value == "model"
    assert reading.perspective == auth.PROSPECTIVE
    assert reading.inference_policy == auth.INFERENCE_NOT_APPLICABLE
    [evidence] = reading.evidence
    assert evidence.kind == "execution_trace"
    assert evidence.locator == "run:42"
    assert "ats-output-authoring" in evidence.detail


def test_a_human_contribution_makes_the_artifact_mixed() -> None:
    """Model-drafted, human-edited is neither 'model' nor 'human'."""
    reading = auth.system_authorship(
        binding=_binding(human_edits="rewrote the acceptance criteria by hand"),
        run_locator="run:42",
    )
    assert reading.value == "mixed"
    assert "rewrote the acceptance criteria" in reading.evidence[0].detail


def test_a_producer_declaration_must_identify_its_run() -> None:
    """A declaration that cannot be checked is not worth more than unknown."""
    with pytest.raises(UsageError, match="run locator"):
        auth.system_authorship(binding=_binding(), run_locator="")


def test_a_binding_naming_neither_a_model_nor_a_human_is_a_defect() -> None:
    """Nothing authored the artifact; that is a bug in the producer, not an unknown."""
    with pytest.raises(UsageError, match="producer defect"):
        auth.system_authorship(
            binding=_binding(
                model=auth.BINDING_NOT_APPLICABLE,
                prompt_identity=auth.BINDING_NOT_APPLICABLE,
            ),
            run_locator="run:42",
        )


def test_a_prospective_reading_cannot_exist_without_a_binding() -> None:
    """The seven fields are mandatory for a producer, enforced where it is constructed."""
    with pytest.raises(UsageError, match="carries no binding"):
        auth.Authorship(
            value="model",
            perspective=auth.PROSPECTIVE,
            evidence=(
                auth.AuthorshipEvidence(
                    kind="execution_trace", value="model", locator="run:1", detail="x"
                ),
            ),
            searched=("not searched",),
            inference_policy=auth.INFERENCE_NOT_APPLICABLE,
        )


def test_the_binding_cannot_be_attached_to_a_retrospective_reading() -> None:
    """The whole separation in one assertion: the policy cannot be projected backwards."""
    with pytest.raises(UsageError, match="prospective binding"):
        auth.Authorship(
            value="unknown",
            perspective=auth.RETROSPECTIVE,
            evidence=(),
            searched=("nothing declared",),
            inference_policy=auth.INFERENCE_PROHIBITED,
            binding=_binding(),
        )


def test_a_retrospective_read_never_produces_a_binding(signals_inventory) -> None:
    """Over a real repository, and over the reader's own output: no binding anywhere."""
    historical = auth.read_authorship(locator="git:abc")
    assert historical.binding is None
    with pytest.raises(UsageError, match="no producer binding"):
        historical.producer_binding
    for artifact in signals_inventory["artifacts"]:
        record = artifact["model_provenance"]["authorship"]
        assert record["perspective"] == auth.RETROSPECTIVE
        assert auth.BINDING_KEY not in record


def test_the_prospective_policy_cannot_be_written_onto_a_historical_reading() -> None:
    """The two directions share a shape, so the confusion has to be caught, not documented."""
    historical = auth.read_authorship(locator="git:abc")
    with pytest.raises(UsageError, match="retrospective"):
        auth.system_model_provenance(historical)
    with pytest.raises(UsageError, match="retrospective"):
        auth.prospective_declaration(historical)


def test_a_producer_declaration_carries_the_whole_binding() -> None:
    """One record holds the seven fields; the artifact cites it rather than copying it."""
    produced = auth.system_authorship(
        binding=_binding(
            adjudicator="Reviewer One <one@ats.invalid>",
            acceptance_receipt="arq://receipt/aa11",
        ),
        run_locator="run:42",
    )
    declaration = auth.prospective_declaration(produced)
    binding = declaration[auth.BINDING_KEY]
    assert list(binding) == list(auth.PROSPECTIVE_BINDING_FIELDS)
    assert binding["acceptance_receipt"] == "arq://receipt/aa11"
    # And the artifact's own provenance object does not duplicate it.
    assert auth.BINDING_KEY not in produced.as_record()


def test_a_producer_declaration_reads_back_as_ordinary_evidence() -> None:
    """The forward half feeds the backward half through a written record, not a default."""
    produced = auth.system_authorship(binding=_binding(), run_locator="run:42")
    declaration = auth.prospective_declaration(produced)
    reading = auth.read_authorship(locator="git:abc", execution_traces=[declaration])
    assert reading.value == "model"
    assert reading.perspective == auth.RETROSPECTIVE
    assert reading.binding is None, "reading a declaration is not producing an artifact"
    assert reading.evidence[0].locator == "run:42"
    # And a document the run never touched still reads unknown.
    assert auth.read_authorship(locator="git:def").value == "unknown"


def test_system_model_provenance_is_a_valid_provenance_object(ctx: Context) -> None:
    """The prospective record uses the same field shape the artifact schema already has."""
    record = auth.system_model_provenance(
        auth.system_authorship(binding=_binding(), run_locator="run:42")
    )
    assert record["availability"] == "present"
    assert record["model"] == {"name": "fixture-writer", "version": "1.0.0"}
    schema = ctx.schemas.schema("ats_source_artifact_v1.schema.json")
    properties = schema["properties"]["model_provenance"]["properties"]
    assert set(record) <= set(properties)
    assert set(record["authorship"]) <= set(properties["authorship"]["properties"])
    assert set(properties["authorship"]["properties"]["value"]["enum"]) == set(
        auth.AUTHORSHIP_VALUES
    )

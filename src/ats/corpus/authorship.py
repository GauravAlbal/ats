"""Authorship of a corpus document: declared, never inferred.

The implementation never infers authorship from corpus-wide silence. A missing
declaration is a statement about what the supplied repository recorded, not
about who wrote the prose. Treating silence as human authorship would
manufacture a label nobody asserted — exactly the "pass by absence" that
ADR-0002 forbids and spec Section 17.4 refuses.

So authorship here has four values — ``human``, ``model``, ``mixed``,
``unknown`` — and ``unknown`` is both the default and the only value reachable
without explicit evidence. A non-``unknown`` value requires a declaration from
one of :data:`EVIDENCE_KINDS`, and the declaration is recorded beside the value
so a reader can check it. :class:`Authorship` enforces that structurally: a
non-``unknown`` value with no evidence cannot be constructed at all.

The signals in :data:`PROHIBITED_SIGNALS` are the ones a plausible
implementation would reach for — the prose reads like a model, the commit is
suspiciously large, the author is known to use an agent, the timestamp is
3 a.m., the phrasing recurs elsewhere, the repository has a ``CLAUDE.md``.
None of them are read here. They are named so the prohibition is testable
rather than merely intended.

Two directions in time are kept apart, and the separation is the point:

``read_authorship``
    **Retrospective.** What a document that already exists declares about
    itself. It searches, and reports what it searched even when it finds
    nothing.
``system_authorship``
    **Prospective.** What an artifact *this* system produces declares at the
    moment of production, when the producer knows the answer and no search is
    involved. It requires a :class:`ProspectiveBinding`: the producing skill,
    the model and version where a model applies, the prompt or instruction
    identity, the source IR, the human edits, the adjudicator, and the
    acceptance receipt. Seven fields, none optional and none defaultable — a
    producer that cannot say which prompt it ran has not recorded provenance.

The prospective policy must never be projected backwards. A model wrote the
artifacts this system emits from now on; that says nothing about the documents
in the repository before it. The separation is structural rather than merely
documented: :class:`Authorship` refuses a binding on a retrospective reading and
refuses a prospective reading without one, so the seven-field policy has no path
by which it reaches a historical document. :func:`system_model_provenance` and
:func:`prospective_declaration` refuse a retrospective reading for the same
reason, and :func:`read_authorship` never constructs a binding at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence

from ..errors import UsageError
from ..output.receipt import SELF_IDENTITIES

#: The authorship vocabulary. ``mixed`` is a distinct state, not a hedge: it
#: means both human and model authorship were declared for the same document,
#: which is materially different from either alone (spec Section 17.4 keeps
#: provenance distinctions that can change interpretation).
AUTHORSHIP_VALUES: Final[tuple[str, ...]] = ("human", "model", "mixed", "unknown")

#: The default, and the only value reachable without explicit evidence.
UNDETERMINED: Final[str] = "unknown"

#: Values a declaration may assert. ``unknown`` is absent deliberately: a
#: source declaring ``unknown`` has declared nothing, and is recorded as
#: searched-and-undetermined rather than as evidence.
DECLARABLE_VALUES: Final[frozenset[str]] = frozenset({"human", "model", "mixed"})

#: The evidence kinds that may move authorship off ``unknown``. Each is a
#: deliberate record made by somebody with knowledge of how the text was
#: produced; none of them can be reconstructed from the text itself.
EVIDENCE_KINDS: Final[tuple[str, ...]] = (
    "commit_trailer",
    "artifact_receipt",
    "agent_run_manifest",
    "document_front_matter",
    "execution_trace",
)

#: Signals that MUST NOT move authorship off ``unknown``, named so the
#: prohibition can be tested rather than assumed. Every one of them correlates
#: with model authorship in somebody's experience and establishes it in nobody's.
PROHIBITED_SIGNALS: Final[tuple[str, ...]] = (
    "prose_style",
    "commit_size",
    "author_identity",
    "commit_timestamp",
    "phrase_reuse",
    "repository_agent_configuration",
)

#: Time directions. A reading carries which one produced it so the prospective
#: policy cannot be written onto a document that predates it.
RETROSPECTIVE: Final[str] = "retrospective"
PROSPECTIVE: Final[str] = "prospective"

#: Inference policy, recorded on every reading. The middle value exists because
#: a declaration *may* permit inference (``model_authorship_inference:
#: permitted``) and this implementation still does not perform it — saying so is
#: honest; silently doing nothing looks like the declaration was never read.
INFERENCE_PROHIBITED: Final[str] = "prohibited_by_this_implementation"
INFERENCE_PERMITTED_UNUSED: Final[str] = "permitted_by_declaration_but_not_performed"
INFERENCE_NOT_APPLICABLE: Final[str] = "not_applicable_producer_declares_its_own_output"

#: In-document declaration, in the ``<!-- ats:... -->`` marker family the rest
#: of this repository already uses for in-document ATS declarations
#: (``ats:profile``, ``ats:define``, ``ats:block``).
AUTHORSHIP_MARKER: Final[re.Pattern[str]] = re.compile(
    r"^<!--\s*ats:authorship\s+([A-Za-z]+)(?:\s+([^>]*?))?\s*-->$", re.MULTILINE
)

#: Front-matter keys. Only these exact keys are read, and the block is parsed as
#: flat ``key: value`` lines rather than as YAML: a corpus reader that evaluates
#: arbitrary document content is a liability, and nothing in the declaration
#: needs more than a scalar.
FRONT_MATTER_FENCE: Final[str] = "---"
FRONT_MATTER_AUTHORSHIP_KEY: Final[str] = "ats-authorship"
FRONT_MATTER_MODEL_KEY: Final[str] = "ats-model"

#: The key an artifact receipt, agent-run manifest, or execution trace must
#: carry for this module to read authorship out of it, and the citation it must
#: carry alongside. A record without a locator is an assertion, not evidence.
DECLARATION_KEY: Final[str] = "authorship"
LOCATOR_KEY: Final[str] = "locator"

#: The forward-looking policy for artifacts this system authors, stated once so
#: it is quotable and so its scope is unmistakable.
PROSPECTIVE_POLICY: Final[str] = (
    "an artifact this system produces declares its own authorship at production "
    "time, citing the run that produced it; the declaration governs artifacts "
    "produced after it and is never applied to documents that predate it"
)

#: The seven bindings a producer must record at the moment it authors an
#: artifact. They are what "how did this text come to say what it says?"
#: decomposes into, and not one of them survives the artifact: the prompt is
#: gone, the IR is a separate document, a human's edit is indistinguishable from
#: the model's sentence once both are prose, and the adjudicator was never
#: written down. Recording them costs the producer nothing and is the only
#: moment at which they are free.
PROSPECTIVE_BINDING_FIELDS: Final[tuple[str, ...]] = (
    "producing_skill",
    "model",
    "prompt_identity",
    "source_ir",
    "human_edits",
    "adjudicator",
    "acceptance_receipt",
)

#: Explicit tokens for the binding fields that legitimately have no value yet or
#: no value at all. They exist so "no model was involved" and "nobody recorded
#: the model" stay different answers: ADR-0002 forbids writing the second as the
#: first, and an omitted field cannot tell them apart.
BINDING_NOT_APPLICABLE: Final[str] = "not_applicable"
BINDING_NO_HUMAN_EDITS: Final[str] = "none"
BINDING_PENDING_ADJUDICATION: Final[str] = "not_yet_adjudicated"
BINDING_PENDING_ACCEPTANCE: Final[str] = "not_yet_accepted"

#: The key the binding travels under, both inside a provenance record and inside
#: the declaration a later reader cites.
BINDING_KEY: Final[str] = "prospective_binding"


def _model_artifact(spec: str) -> dict[str, str] | None:
    """Parse a ``name@version`` model reference from a declaration.

    ``version`` falls back to ``unknown`` rather than to a guess: the normative
    ``model_artifact`` definition requires the field, and inventing a version
    would misreport which model produced the text.
    """
    text = spec.strip()
    if not text:
        return None
    name, _, version = text.partition("@")
    return {"name": name.strip() or text, "version": version.strip() or "unknown"}


@dataclass(frozen=True, slots=True)
class AuthorshipEvidence:
    """One declaration that authorship was recorded, and where to check it."""

    kind: str
    value: str
    locator: str
    detail: str
    model: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if self.kind not in EVIDENCE_KINDS:
            raise UsageError(
                f"{self.kind!r} is not an authorship evidence kind; expected one of "
                f"{', '.join(EVIDENCE_KINDS)}"
            )
        if self.value not in DECLARABLE_VALUES:
            raise UsageError(
                f"authorship evidence declares {self.value!r}; a declaration must assert one of "
                f"{', '.join(sorted(DECLARABLE_VALUES))}"
            )
        if not self.locator:
            raise UsageError(
                "authorship evidence carries no locator; an uncitable claim is not evidence "
                "and cannot move authorship off unknown"
            )

    def as_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "kind": self.kind,
            "value": self.value,
            "locator": self.locator,
            "detail": self.detail,
        }
        if self.model:
            record["model"] = dict(self.model)
        return record


@dataclass(frozen=True, slots=True)
class ProspectiveBinding:
    """The seven things a producer binds to an artifact at the moment it authors it.

    Every field is required. Where a field genuinely has no value the producer
    writes the token that says so — :data:`BINDING_NOT_APPLICABLE` for a skill
    that ran no model or projected no IR, :data:`BINDING_NO_HUMAN_EDITS` for an
    artifact no person touched, :data:`BINDING_PENDING_ADJUDICATION` and
    :data:`BINDING_PENDING_ACCEPTANCE` while the acceptance authority has not yet
    ruled. An omitted field would collapse "there was no model" into "nobody
    recorded the model", which is the pass-by-absence ADR-0002 forbids.

    Two cross-field rules are enforced because either violation would leave a
    record that reads as complete and is not: a bound model implies a bound
    prompt, since a model that ran ran on an instruction; and a named acceptance
    receipt implies a named adjudicator, since a receipt nobody signed is not an
    acceptance (spec Section 14.11). A named adjudicator that is this
    implementation is refused outright under Section 13.7.
    """

    producing_skill: str
    model: Mapping[str, str] | str
    prompt_identity: str
    source_ir: str
    human_edits: str
    adjudicator: str
    acceptance_receipt: str

    def __post_init__(self) -> None:
        for name in PROSPECTIVE_BINDING_FIELDS:
            if name == "model":
                continue
            if not str(getattr(self, name) or "").strip():
                raise UsageError(
                    f"the prospective binding leaves {name!r} empty; each of "
                    f"{', '.join(PROSPECTIVE_BINDING_FIELDS)} must be stated, and a field the "
                    "producer cannot answer is stated as an explicit token, never omitted"
                )
        if self.producing_skill.strip() == BINDING_NOT_APPLICABLE:
            raise UsageError(
                "the prospective binding declares producing_skill not_applicable; something "
                "produced the artifact, and a producer that cannot name itself has a defect"
            )
        if isinstance(self.model, Mapping):
            if not str(self.model.get("name") or "").strip() or not str(
                self.model.get("version") or ""
            ).strip():
                raise UsageError(
                    "a bound model must carry both name and version; a version-less model "
                    "reference cannot say which model produced the text"
                )
            if self.prompt_identity.strip() == BINDING_NOT_APPLICABLE:
                raise UsageError(
                    "the prospective binding names a model and declares prompt_identity "
                    "not_applicable; a model that ran ran on an instruction, and the "
                    "instruction is the part nobody can reconstruct later"
                )
        elif self.model != BINDING_NOT_APPLICABLE:
            raise UsageError(
                f"model must be a name/version mapping or {BINDING_NOT_APPLICABLE!r}; got "
                f"{self.model!r}"
            )
        if self.adjudicated and self.adjudicator.strip().casefold() in SELF_IDENTITIES:
            raise UsageError(
                f"the prospective binding names {self.adjudicator!r} as adjudicator, which is "
                "this implementation; acceptance authority must be external (spec 13.7, 14.11)"
            )
        if self.accepted and not self.adjudicated:
            raise UsageError(
                f"the prospective binding names acceptance receipt "
                f"{self.acceptance_receipt!r} with adjudicator "
                f"{BINDING_PENDING_ADJUDICATION!r}; a receipt nobody signed is not an acceptance"
            )

    @property
    def adjudicated(self) -> bool:
        """Whether an adjudicator has been named, as opposed to still pending."""
        return self.adjudicator.strip() != BINDING_PENDING_ADJUDICATION

    @property
    def accepted(self) -> bool:
        """Whether an acceptance receipt has been named, as opposed to still pending."""
        return self.acceptance_receipt.strip() != BINDING_PENDING_ACCEPTANCE

    def as_record(self) -> dict[str, Any]:
        """All seven fields, always, in the declared order."""
        return {
            "producing_skill": self.producing_skill,
            "model": dict(self.model) if isinstance(self.model, Mapping) else self.model,
            "prompt_identity": self.prompt_identity,
            "source_ir": self.source_ir,
            "human_edits": self.human_edits,
            "adjudicator": self.adjudicator,
            "acceptance_receipt": self.acceptance_receipt,
        }


@dataclass(frozen=True, slots=True)
class Authorship:
    """An authorship reading: the value, its evidence, and what was searched.

    The invariants are enforced in ``__post_init__`` rather than documented,
    because "inference must be impossible to reach by accident" is only true if
    the accident raises.
    """

    value: str
    perspective: str
    evidence: tuple[AuthorshipEvidence, ...]
    searched: tuple[str, ...]
    inference_policy: str
    binding: ProspectiveBinding | None = None

    def __post_init__(self) -> None:
        if self.value not in AUTHORSHIP_VALUES:
            raise UsageError(
                f"{self.value!r} is not an authorship value; expected one of "
                f"{', '.join(AUTHORSHIP_VALUES)}"
            )
        if self.perspective not in (RETROSPECTIVE, PROSPECTIVE):
            raise UsageError(
                f"{self.perspective!r} is not an authorship perspective; expected "
                f"{RETROSPECTIVE!r} or {PROSPECTIVE!r}"
            )
        if self.value != UNDETERMINED and not self.evidence:
            raise UsageError(
                f"authorship {self.value!r} was asserted with no evidence; only {UNDETERMINED!r} "
                "is reachable without an explicit declaration"
            )
        if not self.searched:
            raise UsageError(
                "an authorship reading must record what it looked at; a bare result gives a "
                "reader no way to tell 'searched and not found' from 'never searched'"
            )
        # The two halves of the time separation, enforced rather than described.
        # A binding is a statement about how a producer made something; a
        # document that already existed was not made that way, and a producer
        # that declares its own authorship has no excuse for withholding it.
        if self.binding is not None and self.perspective != PROSPECTIVE:
            raise UsageError(
                f"a {self.perspective} reading carries a prospective binding; {PROSPECTIVE_POLICY}"
            )
        if self.perspective == PROSPECTIVE and self.binding is None:
            raise UsageError(
                "a prospective reading carries no binding; a producer declaring its own "
                f"authorship must bind {', '.join(PROSPECTIVE_BINDING_FIELDS)}, none of which "
                "is recoverable from the artifact afterwards"
            )

    @property
    def declared(self) -> bool:
        """Whether any source declared authorship for this document."""
        return bool(self.evidence)

    @property
    def producer_binding(self) -> ProspectiveBinding:
        """The seven-field binding, for a reading a producer made.

        Raises for a retrospective reading rather than returning ``None``: asking
        a historical document how it was produced is the mistake this module
        exists to prevent, and a null would let a caller answer it with a shrug.
        """
        if self.binding is None:
            raise UsageError(
                f"a {self.perspective} reading has no producer binding; {PROSPECTIVE_POLICY}"
            )
        return self.binding

    def as_record(self) -> dict[str, Any]:
        """The serialisable form carried on ``model_provenance.authorship``.

        The binding is deliberately not copied in here. It is the content of the
        declaration that ``evidence[].locator`` already points at, and copying it
        would create a second place the same seven facts can be wrong — the
        failure :func:`trailer_evidence` avoids by reading one record rather than
        re-parsing the commit. A consumer wanting the prompt or the adjudicator
        follows the locator to :func:`prospective_declaration`'s output, which is
        where the producer wrote them.
        """
        return {
            "value": self.value,
            "perspective": self.perspective,
            "inference_policy": self.inference_policy,
            "searched": list(self.searched),
            "evidence": [e.as_record() for e in self.evidence],
        }


def combine(values: Sequence[str]) -> str:
    """Fold declared values into one.

    Both ``human`` and ``model`` declared for the same document is ``mixed``:
    that is what two truthful declarations about a co-authored document look
    like, and collapsing it to either one would delete a distinction the
    consumer of the corpus needs. Nothing declared is ``unknown``.
    """
    declared = {v for v in values if v in DECLARABLE_VALUES}
    if not declared:
        return UNDETERMINED
    if declared == {"human"}:
        return "human"
    if declared == {"model"}:
        return "model"
    return "mixed"


# -- retrospective: what an existing document declares about itself ----------


def front_matter(text: str) -> dict[str, str]:
    """The fenced ``key: value`` block at the very top of a document, if any.

    An unterminated fence is not front matter. Reading one would let the first
    ``---`` in a document turn the rest of the prose into declarations.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != FRONT_MATTER_FENCE:
        return {}
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == FRONT_MATTER_FENCE:
            return out
        key, sep, value = line.partition(":")
        if sep:
            out[key.strip().lower()] = value.strip()
    return {}


def document_evidence(text: str, *, locator: str) -> tuple[AuthorshipEvidence | None, str]:
    """Structured authorship declared inside the document.

    Returns the evidence and a note describing the search, so a document that
    declares nothing still says what was looked for.
    """
    matter = front_matter(text)
    declared = matter.get(FRONT_MATTER_AUTHORSHIP_KEY, "").strip().lower()
    model = _model_artifact(matter.get(FRONT_MATTER_MODEL_KEY, ""))
    source = f"the {FRONT_MATTER_AUTHORSHIP_KEY} front-matter key"

    if declared not in DECLARABLE_VALUES:
        marker = AUTHORSHIP_MARKER.search(text)
        if marker:
            declared = marker.group(1).strip().lower()
            model = _model_artifact(marker.group(2) or "")
            source = "the ats:authorship marker"

    if declared in DECLARABLE_VALUES:
        return (
            AuthorshipEvidence(
                kind="document_front_matter",
                value=declared,
                locator=locator,
                detail=f"declared {declared} by {source} of {locator}",
                model=model,
            ),
            f"document text of {locator}: {source} declares {declared}",
        )
    found = f"found {declared!r}, which is not an assertable value" if declared else "none found"
    return (
        None,
        f"document text of {locator}: searched the {FRONT_MATTER_AUTHORSHIP_KEY} front-matter "
        f"key and the ats:authorship marker; {found}",
    )


def trailer_evidence(
    provenance: Mapping[str, Any], *, locator: str
) -> tuple[AuthorshipEvidence | None, str]:
    """Authorship from a commit trailer that deliberately records generation.

    Reads the ``model_provenance`` object the inventory already builds from the
    ``ATS-Model`` trailer, rather than re-parsing the commit: one reader of the
    trailer, one place it can be wrong.
    """
    availability = str(provenance.get("availability", "not_searched"))
    if availability != "present":
        return (None, f"commit trailers of {locator}: model provenance is {availability}")
    model = provenance.get("model")
    detail = str(provenance.get("evidence") or f"declared by a commit trailer on {locator}")
    return (
        AuthorshipEvidence(
            kind="commit_trailer",
            value="model",
            locator=locator,
            detail=detail,
            model=dict(model) if isinstance(model, Mapping) else None,
        ),
        f"commit trailers of {locator}: a model-generation trailer is present",
    )


def _declared_model(record: Mapping[str, Any]) -> dict[str, str] | None:
    raw = record.get("model")
    if isinstance(raw, str):
        return _model_artifact(raw)
    if isinstance(raw, Mapping):
        return {str(k): str(v) for k, v in raw.items()}
    return None


def declared_evidence(
    records: Sequence[Mapping[str, Any]], *, kind: str, label: str
) -> tuple[list[AuthorshipEvidence], str]:
    """Authorship declared by receipts, run manifests, or execution traces.

    Each record must carry an explicit ``authorship`` value and a ``locator``.
    A record carrying neither is not a declaration, and the search note says so.
    A record declaring a value this vocabulary does not have raises: a producer
    writing ``authorship: ai`` deserves an error rather than an ``unknown`` that
    is indistinguishable from an honest absence.
    """
    if kind not in EVIDENCE_KINDS:
        raise UsageError(f"{kind!r} is not an authorship evidence kind")
    found: list[AuthorshipEvidence] = []
    for index, record in enumerate(records):
        raw = record.get(DECLARATION_KEY)
        if raw is None:
            continue
        value = str(raw).strip().lower()
        if value == UNDETERMINED:
            continue
        if value not in DECLARABLE_VALUES:
            raise UsageError(
                f"{label} record {index} declares {DECLARATION_KEY}={raw!r}; expected one of "
                f"{', '.join(sorted(DECLARABLE_VALUES))} or {UNDETERMINED!r}"
            )
        locator = str(record.get(LOCATOR_KEY) or "")
        if not locator:
            raise UsageError(
                f"{label} record {index} declares {DECLARATION_KEY}={value!r} with no "
                f"{LOCATOR_KEY!r}; an uncitable declaration cannot move authorship off unknown"
            )
        found.append(
            AuthorshipEvidence(
                kind=kind,
                value=value,
                locator=locator,
                detail=str(record.get("detail") or f"declared {value} by {label} at {locator}"),
                model=_declared_model(record),
            )
        )
    if not records:
        return found, f"{label}: none supplied"
    if not found:
        return found, f"{label}: {len(records)} searched, none declares {DECLARATION_KEY}"
    return found, f"{label}: {len(found)} of {len(records)} declare {DECLARATION_KEY}"


def _inference_policy(authority: Any | None) -> str:
    """What the declaration permits, and what this implementation does anyway."""
    permits = getattr(authority, "permits_model_authorship_inference", None)
    if permits is not None and permits():
        return INFERENCE_PERMITTED_UNUSED
    return INFERENCE_PROHIBITED


def read_authorship(
    *,
    locator: str,
    model_provenance: Mapping[str, Any] | None = None,
    document_text: str | None = None,
    receipts: Sequence[Mapping[str, Any]] = (),
    run_manifests: Sequence[Mapping[str, Any]] = (),
    execution_traces: Sequence[Mapping[str, Any]] = (),
    authority: Any | None = None,
) -> Authorship:
    """Read the authorship a document already declares. Nothing is inferred.

    Every one of the five evidence kinds is searched and reported, whether or
    not it answers, so ``unknown`` arrives with the list of places that were
    looked at instead of a bare null. ``authority`` is consulted only to record
    whether inference *would* have been permitted (spec Section 17.13 puts that
    decision with the repository owner); this implementation does not infer
    under either answer, and says which case it is in.
    """
    evidence: list[AuthorshipEvidence] = []
    searched: list[str] = []

    trailer, note = trailer_evidence(
        model_provenance if model_provenance is not None else {"availability": "not_searched"},
        locator=locator,
    )
    searched.append(note)
    if trailer:
        evidence.append(trailer)

    for records, kind, label in (
        (receipts, "artifact_receipt", "artifact receipts"),
        (run_manifests, "agent_run_manifest", "agent run manifests"),
        (execution_traces, "execution_trace", "execution traces"),
    ):
        found, note = declared_evidence(records, kind=kind, label=label)
        searched.append(note)
        evidence.extend(found)

    if document_text is None:
        searched.append(f"document text of {locator}: not supplied to this reader")
    else:
        document, note = document_evidence(document_text, locator=locator)
        searched.append(note)
        if document:
            evidence.append(document)

    searched.append("not read, by policy: " + ", ".join(PROHIBITED_SIGNALS))

    return Authorship(
        value=combine([e.value for e in evidence]),
        perspective=RETROSPECTIVE,
        evidence=tuple(evidence),
        searched=tuple(searched),
        inference_policy=_inference_policy(authority),
    )


def historical_model_provenance(
    provenance: Mapping[str, Any],
    *,
    locator: str,
    document_text: str | None = None,
    receipts: Sequence[Mapping[str, Any]] = (),
    run_manifests: Sequence[Mapping[str, Any]] = (),
    execution_traces: Sequence[Mapping[str, Any]] = (),
    authority: Any | None = None,
) -> dict[str, Any]:
    """A ``model_provenance`` object carrying a retrospective authorship reading.

    The existing ``availability``/``model``/``evidence`` fields are preserved
    verbatim; the reading is added beside them, so a consumer that only knows
    the older shape still gets the same answer it got before.
    """
    record = dict(provenance)
    record["authorship"] = read_authorship(
        locator=locator,
        model_provenance=provenance,
        document_text=document_text,
        receipts=receipts,
        run_manifests=run_manifests,
        execution_traces=execution_traces,
        authority=authority,
    ).as_record()
    return record


# -- prospective: what this system declares about what it produces -----------


def system_authorship(*, binding: ProspectiveBinding, run_locator: str) -> Authorship:
    """Authorship for an artifact this system authors, declared at production.

    This is the forward-looking half of the policy and is deliberately not a
    reader: it does not search, because the producer knows. The value falls out
    of the binding rather than being passed in alongside it, so the label and the
    declaration cannot disagree — a model and human edits is ``mixed``, a model
    alone is ``model``, and a deterministic skill whose content a person supplied
    is ``human``.

    It cannot emit ``unknown``: a producer that does not know what produced its
    own output has a defect rather than an unknown. A binding naming neither a
    model nor a human raises for the same reason — an artifact nothing authored
    is a bug in the producer, not an absence of evidence.
    """
    if not run_locator:
        raise UsageError(
            "system authorship requires a run locator; the declaration is only evidence if "
            "the run that produced the artifact can be found"
        )
    model = binding.model if isinstance(binding.model, Mapping) else None
    edited = binding.human_edits.strip() != BINDING_NO_HUMAN_EDITS
    if model is None and not edited:
        raise UsageError(
            f"the binding declares model {BINDING_NOT_APPLICABLE!r} and human_edits "
            f"{BINDING_NO_HUMAN_EDITS!r}; nothing authored the artifact, which is a producer "
            "defect rather than unknown authorship"
        )
    value = "mixed" if model is not None and edited else ("model" if model is not None else "human")
    detail = f"produced by {binding.producing_skill}"
    if model is not None:
        detail += f" using {model['name']}@{model['version']}"
    detail += f" in run {run_locator}"
    if edited:
        detail += f"; human contribution: {binding.human_edits}"
    return Authorship(
        value=value,
        perspective=PROSPECTIVE,
        evidence=(
            AuthorshipEvidence(
                kind="execution_trace",
                value=value,
                locator=run_locator,
                detail=detail,
                model=dict(model) if model is not None else None,
            ),
        ),
        searched=(f"not searched; {PROSPECTIVE_POLICY}",),
        inference_policy=INFERENCE_NOT_APPLICABLE,
        binding=binding,
    )


def system_model_provenance(authorship: Authorship) -> dict[str, Any]:
    """A ``model_provenance`` object for an artifact this system authored.

    Refuses a retrospective reading. Both directions produce the same shape,
    which is exactly why the confusion is worth catching: writing the
    prospective policy onto a document this system did not produce would label
    the historical corpus by assertion. The seven-field binding rides along
    inside ``authorship`` rather than in a field of its own, so a consumer
    reading the provenance object gets the authorship and its basis together or
    gets neither.
    """
    if authorship.perspective != PROSPECTIVE:
        raise UsageError(
            f"system_model_provenance was given a {authorship.perspective} reading; "
            f"{PROSPECTIVE_POLICY}"
        )
    evidence = authorship.evidence[0]
    record: dict[str, Any] = {
        "availability": "present",
        "evidence": evidence.detail,
        "authorship": authorship.as_record(),
    }
    if evidence.model:
        record["model"] = dict(evidence.model)
    return record


def prospective_declaration(authorship: Authorship) -> dict[str, Any]:
    """The record a producer writes so a later reader can cite it as evidence.

    This closes the loop between the two directions without merging them: the
    prospective helper emits a declaration, and :func:`read_authorship` reads it
    back as ordinary ``execution_trace`` evidence for the artifact it names. The
    reading is still evidence-bound — the declaration had to be written — and it
    comes back ``retrospective``, carrying no binding, because the reader found a
    record rather than produced an artifact.

    The full binding travels in the declaration under :data:`BINDING_KEY`.
    :func:`declared_evidence` does not read it, and must not: authorship is
    established by the declared value, and a consumer wanting the prompt or the
    adjudicator goes to the declaration the locator points at.
    """
    if authorship.perspective != PROSPECTIVE:
        raise UsageError(
            f"a {authorship.perspective} reading is not a producer declaration; "
            f"{PROSPECTIVE_POLICY}"
        )
    evidence = authorship.evidence[0]
    # This is the one record the seven fields are written into. The artifact's
    # provenance object cites the locator instead of copying them, so there is
    # exactly one place they can be wrong.
    record: dict[str, Any] = {
        DECLARATION_KEY: authorship.value,
        LOCATOR_KEY: evidence.locator,
        "detail": evidence.detail,
        BINDING_KEY: authorship.producer_binding.as_record(),
    }
    if evidence.model:
        record["model"] = dict(evidence.model)
    return record

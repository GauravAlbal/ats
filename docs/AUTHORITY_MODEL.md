# Authority model

This document is load-bearing machinery, not commentary.
`capability/ats_rule_capability_v1.json` carries an `authority_basis_ref` into it for every
detector that claims conformance evidence, ATS-1 §16.1 requires an implementation to publish
an authority-basis receipt for exactly those detectors, and `tools/validate_repo.py`
fails the repository if the four anchors below stop resolving.

The question this document answers is not "did the check pass?" It is: **what is a given
result entitled to establish, and who may accept it?** §12.3 states the separation the rest
of this document elaborates — rule state declares what the artifact must satisfy; detector
authority declares what a particular result can establish. They are orthogonal.

## Naming and identity authority

The current public identity is **ATS-1 — Applied Technical Semantics**, and the
current public expansion is **Applied Technical Semantics**. Released draft.1
and draft.2 package bytes preserve the historical expansion; **ATS-1** and all
machine identifiers remain unchanged. This rename has no normative semantic
effect. On conflict, normative packages outrank current descriptive prose.

---

## Operational classes: what blocks, what reviews, what advises

Draft.2 adds a second, orthogonal axis on top of detector authority: every rule and every
check carries an **operational class** (`ats_rules_v2.yaml` `operational_class`;
`ats.ruleset.v2`). The class is the *only* input a build policy uses to decide whether a finding
blocks. Detector authority says what a result *may establish*; the operational class says what
may *gate a build*.

| Class | Meaning | What it blocks | Draft.2 members |
|---|---|---|---|
| `BLOCK` | Deterministic integrity failure: mechanically established, high-value semantic-integrity violation (D1 `DECIDES` or a structural check) | Build/acceptance, always. Unwaivable, `autofix: forbidden` | `ATS-COORD-001`, `ATS-COORD-002`, `ATS-BASIS-002`, `ATS-PRES-003`; the structural checks (`IR-ID-UNIQUE`, `IR-REFS`, `IR-BASIS-SCHEMA` when `basis_policy.declared`, `OUT-COORD-PRESERVED`, `OUT-BASIS-NOT-STRENGTHENED`) |
| `REVIEW_REQUIRED` | Material ambiguity or a semantic proposal that cannot be decided mechanically (D1 `DETECTS_VIOLATIONS` / D3) | Nothing automatically. Requires an authorized adjudicator; waivable with record | `ATS-BASIS-001`, `ATS-CLOSE-001`; `failure_policy.inferred_material_semantics: review_required` |
| `ADVISORY` | Style: ergonomic findings — complexity, repetition, density, terminology, positioning | Nothing, ever. A note, never an exit-status change | `ATS-DISC-003` (amended, draft.2) and the style surfaces of the carried rules |

Two invariants follow, and both are enforced in CI policy rather than prose: the
enforcement surface MUST NOT fail builds on style taste (`ADVISORY` is a note),
and it SHOULD fail builds on deterministic semantic-integrity violations
(`BLOCK` fails acceptance; `REVIEW_REQUIRED` fails nothing — it records an open
question an authorized adjudicator settles before acceptance when the enforcement
set makes review required). The default enforcement set (`ats.fleet_policy.v1`)
makes the deterministic surface required and `semantic_review` advisory
(D-G, `ats/fleet.py`).

The classes and the §12.3 detector authorities compose, they do not conflict: a
`BLOCK` rule is `BLOCK` because its detector `DECIDES` with `conformance_evidence`
authority; a `REVIEW_REQUIRED` rule is review-class because its detector can only recognise
violations or propose findings. The one place authority alone decides the outcome is
`decide()` (below) — a detector can never emit `PASS` from absence regardless of its class.

## Detector families

Four families of deterministic procedure run in this build. Each anchor below is the
`authority_basis_ref` target for its family.

### ats-ir-structural

**The 27 structural checks over a TextIR document and its resolved policy** (26 draft.1
checks plus draft.2's `IR-BASIS-SCHEMA`; `IR-ID-UNIQUE` and `IR-REFS` are extended in
place to cover the new coordinate ids rather than gaining new check ids).
Implemented in `src/ats/ir/checks.py` (`run_structural_checks`) plus
`src/ats/ir/profile.py` (`evaluate_profiles`, which produces `IR-PROFILE-SLOTS`). Emits
`ats.rules.results.CheckResult`, not a rule result: these operate *in addition to* the
thirty rules in draft.1 (thirty-six in draft.2, §12.7.5), so they carry their own
identifiers rather than being smuggled into a rule's result.

*What it decides.* Whether the supplied objects hang together: the document validates against
`ats_text_ir_v1.schema.json`; the policy snapshot's declared `snapshot_sha256` equals the
SHA-256 of its canonical bytes with only that field omitted; the declared source and
normalized hashes reproduce from actual bytes when a source file is supplied; every
identifier is used once — now including every declared stable coordinate and every
`requirement_id`/`decision_id`/`acceptance_criterion_id` (draft.2 D-C); every claim,
evidence, relation, and indicator reference resolves to an object of the permitted kind and
role, now including `dependency_target` and `acceptance_criterion_id` references; each
section resolves to at least one content profile; each profile's required semantic slots are
present or typed absent; each material claim's role-forbidden force fields are absent; each
declared WEP term exists in `lexicons/ats_force_lexicon_v1.yaml` with the exact lexicon
interval; each declared deontic surface is a lexicon surface; every policy exception is
hash-consistent, in scope, and unexpired; the basis-policy presence obligation holds when
`basis_policy.declared` is true (`IR-BASIS-SCHEMA`, draft.2 D-F); and the document
JCS-round-trips to a stable content address.

*Why a deterministic procedure over these inputs is conformance evidence under §16.5.*
§16.5 restricts `proposal_only` to D3 *semantic-detector* output and reserves
`conformance_evidence` for, among others, "a formally verified predicate." Every predicate in
this family is exactly that: a total function of the validated document, the imported
schemas, the imported lexicon, and the resolved policy snapshot — all four of which are
content-addressed and replayable. No natural-language interpretation enters. "This
identifier appears twice" and "this declared hash does not equal the recomputed hash" are
decidable, and their negations are equally decidable, which is what distinguishes a decision
procedure from a violation recogniser. §15.1 names precisely this family — deterministic
checks executed, glossary and policy references resolved, deterministic replay succeeds — as
the content of `mechanical: PASS`, and `ats.ir.lint.MECHANICAL_CHECKS` enumerates the 15
members that gate that dimension.

*What it explicitly does NOT establish.* That the IR is a *faithful* representation of any
source. A document can satisfy all 27 checks and still misrepresent its source: the checks
read the meaning ledger, not the prose it came from. §14.5 is explicit that an extracted
ledger is evidence, not automatically authoritative meaning. Nor do these checks establish
that the artifact's claims are true, that its materiality marks are correct (§7.15 gives that
authority to authors and upstream systems), or that a slot filled with a typed absence value
was the *right* answer rather than a convenient one.

*When it abstains.* `IR-SOURCE-HASH` reports `UNAVAILABLE` when no source file is supplied,
because a well-formed hash is not a binding to bytes. `IR-PROFILE-SLOTS` reports
`UNAVAILABLE` for a section whose profile is outside `ASSESS`/`SPECIFY`, because §9.5 gives
reserved profiles no inherited semantics and coercing them would invent an obligation.
Checks whose subject is absent report `NOT_APPLICABLE` with the reason stated —
`IR-REQUIREMENT-SLOTS` on an artifact with no requirement, `IR-POLICY-EXCEPTIONS` on a
snapshot with no exception. None of them reports `PASS` because nothing was inspected.

### ats-ir-rule

**The 36 rule detectors over TextIR in draft.2** (30 carried rules plus the six draft.2
rules — `ATS-COORD-001`, `ATS-COORD-002`, `ATS-BASIS-001`, `ATS-BASIS-002`, `ATS-PRES-003`,
`ATS-CLOSE-001`; the draft.1 edition runs 30). Implemented in `src/ats/rules/deterministic/`,
each declared once as a `DetectorSpec` in `_support.py` and executed through
`run_detector`. This is the only family that carries an emitted `authority_basis_ref`: every
`conformance_evidence` entry in the capability declaration (repo-root draft.1 file, or the
draft.2 package's own `capability/` file, resolved package-relative first) points at
`docs/AUTHORITY_MODEL.md#ats-ir-rule`, written there by `tools/generate_capability.py` and
constructed at runtime by `Context.detector(..., basis_anchor="ats-ir-rule")`.

*What it decides.* Per rule, a named set of subchecks over the structured slots of the
meaning ledger, each citing the spec section it defends and naming its vocabulary source.
`ATS-EPI-001` decides that a `wep` likelihood's `lower`/`upper` equal the lexicon interval
for its term. `ATS-DEON-001` decides that a `requirement` claim declares a deontic force and
that the force's uppercase lexicon surface appears verbatim in its proposition.
`ATS-NUM-001` decides that a material quantifier of a unit-bearing kind carries a unit or
declares the unit unknown. `ATS-REQ-003` decides that a `MUST`/`MUST_NOT` requirement carries
an acceptance criterion that is not one of the vacuous forms §9.3.9 names. The full per-rule
inventory — detector class, decision power, authority, subchecks, vocabulary sources,
unavailable conditions, and known limits — is in the capability declaration and is generated
from these same specs.

The six draft.2 rules add two new authority shapes to the family:

| Rule | Class | Power | Authority | What it may establish |
|---|---|---|---|---|
| `ATS-COORD-001` (coordinates) | D1 | `decides` | `conformance_evidence` | Every declared stable coordinate resolves to a real IR id, and every `requirement_id`/`decision_id`/`acceptance_criterion_id` the IR uses is declared when the document declares the block. Exact set checks: `PASS`/`FAIL` both decidable (D-C, §4.23/§7.17). |
| `ATS-COORD-002` (coordinates) | D1 | `decides` | `conformance_evidence` | No duplicate coordinates anywhere in the IR; `dependency_target` and `acceptance_criterion_id` references resolve. Exact reference checks (D-C). |
| `ATS-BASIS-001` (basis) | D3 | `detects_violations` | `proposal_only` | A material claim/requirement without a declared `semantic_basis` is surfaced for review. It can never `PASS` — a clean run reports `REVIEW_REQUIRED` (D-F, §4.25/§7.19; enum validity is schema-enforced, so presence is all this detector checks). |
| `ATS-BASIS-002` (basis) | D1 | `decides` | `conformance_evidence` | For a TRANSFORM, a claim whose `semantic_basis` is `EXPLICIT` while the source basis for the same value is `INFERRED`/`UNAVAILABLE` is a decided `FAIL`. When the comparison is not possible it reports `REVIEW_REQUIRED` — never `PASS` by absence (D-F, §7.19). |
| `ATS-PRES-003` (preservation) | D1 | `decides` | `conformance_evidence` | Every protected relation declared in the source meaning ledger is realized in the output trace's `p1_relations`. With a trace supplied: `PASS`/`FAIL`; without one: `UNAVAILABLE`, never `PASS` (D-B, §11.3.2). |
| `ATS-CLOSE-001` (closure) | D1 | `detects_violations` | `conformance_evidence` | For SPECIFY, missing actor/modality/action/object slots and unresolved `acceptance_criterion_id`/`dependency_target` refs are decided `FAIL`s; a clean run is `REVIEW_REQUIRED` because slot presence is mechanical but semantic closure is not claimed (D-D, §4.24/§7.18). |

The table shows the composition rule in action: `BLOCK`-class rules (`COORD-001/002`,
`BASIS-002`, `PRES-003`) are exactly the D1 `DECIDES` rules; `REVIEW_REQUIRED`-class rules
(`BASIS-001`, `CLOSE-001`) are the `DETECTS_VIOLATIONS` rules. `CLOSE-001` carries
`conformance_evidence` authority (its class ceiling is D1) yet still reports
`REVIEW_REQUIRED` on clean, because its declared power is violation-recognition, not
decision — authority and power are both declared, never chosen by the detector body.

*Why a deterministic procedure over these inputs is conformance evidence under §16.5.*
§16.5's restriction is on *learned* semantic output. These detectors read typed slots, not
prose semantics: `claim.likelihood.kind`, `requirement.deontic`, `quantifier.unit`,
`relation.basis_refs`. Where a detector must touch prose, it matches only against a closed
vocabulary that comes from the force lexicon, a list enumerated verbatim in the spec, or the
artifact's own declared glossary — never an invented keyword list (ADR-0006), and the source
is recorded per subcheck as `vocabulary_source`. That makes each subcheck a total function of
content-addressed inputs, replayable to the same result, which is what §12.3's
"`conformance_evidence` can contribute directly to a conformance decision" requires of a
D0/D1 detector after deterministic fixture and parser validation. Twelve such rules
  contribute to `mechanical` on the ASSESS conforming fixture (draft.1 counts; under draft.2
the six new rules default to `advisory` under ASSESS, so the contributing set is
unchanged on that fixture).

*What it explicitly does NOT establish.* That the artifact says something true, useful, or
well-calibrated. Structural conformance of a force field is not correctness of the judgment
it qualifies. Each rule's `known_limits` in the capability declaration names the residual
gap concretely — for example, `ATS-DEON-001` records that §1.3 makes deontic keywords
normative only in uppercase, so a lowercase `must` in ordinary prose is correctly not
flagged, and whether it smuggles normative force is a semantic question this family cannot
reach. A `PASS` here is a claim about the ledger's structure, nothing more.

*When it abstains.* Three distinct ways, and the distinction matters:

- **Undecidable from this surface.** Seven rules (`ATS-TERM-002`, `ATS-REF-001`,
  `ATS-SCOPE-001`, `ATS-DISC-002`, `ATS-DISC-003`, `ATS-PRES-001`, `ATS-PRES-002`) declare
  `decision_power: undecidable` because their `required_inputs` include something a TextIR
  document does not carry — `source_text`, `syntax`, `document_ast`, `document_context`, or
  the source/output IR pair with its retention contract and authorizations. `run_detector`
  short-circuits to `UNAVAILABLE` with the blocking inputs named. `capability.py` enforces
  the converse too: a rule declared `undecidable` that names no blocking input is a coherence
  error, because an undecidable rule must say what it lacks.
- **Disabled by policy.** `effective_state == "disabled"` yields `NOT_APPLICABLE` with the
  resolved profile, default state, and policy layer recorded.
- **Recognised nothing.** A detector declaring `DETECTS_VIOLATIONS` that finds no violation
  yields `REVIEW_REQUIRED`, never `PASS`. See the two gates below.

### ats-output-structural

**The 19 non-surface checks over a rendered bundle** (17 draft.1 checks plus draft.2's
`OUT-COORD-PRESERVED` and `OUT-BASIS-NOT-STRENGTHENED`). Implemented in
`src/ats/output/lint.py`: `OUT-BYTES`, `OUT-MARKDOWN-PARSE`, `OUT-CONSTRUCTS`, `OUT-MARKERS`,
`OUT-TRACE-SCHEMA`, `OUT-BLOCK-HASHES`, `OUT-IR-REFS`, `OUT-MATERIAL-COVERAGE`,
`OUT-UNKNOWN-REFS`, `OUT-BLOCK-ORDER`, `OUT-PROFILE-SECTIONS`, `OUT-P0-EXACT`,
`OUT-P1-DECLARED`, `OUT-POLICY-EXCEPTIONS`, `OUT-FINDING-DISPOSITIONS`,
`OUT-CONFORMANCE-VECTOR`, `OUT-RECEIPT`, `OUT-COORD-PRESERVED`, `OUT-BASIS-NOT-STRENGTHENED`.

*What it decides.* That the bundle is internally consistent and traceable: the document's
bytes hash to the value the trace declares; the IR canonicalizes to the value the trace
declares; the trace binds the same artifact, policy id, and policy hash as the supplied
snapshot and reproduces its own `trace_sha256`; every declared block marker appears exactly
once in the document and every rendered marker appears in the trace; each block body's
SHA-256 (marker excluded, one trailing newline stripped) matches its declared
`text_sha256`; every block reference resolves to an IR object of the right kind; every
material IR object is mapped by a block or carries an authorized omission; block ordinals are
dense, ascending, and match document order; every declared P0 value equals the IR value at
its JSON Pointer *and* appears verbatim in the declaring block; every IR-declared stable
coordinate appears in at least one output block's references *and* verbatim in the block
text, with `FAIL` on drop or alteration (`OUT-COORD-PRESERVED`, draft.2 D-C); a TRANSFORM
rendering never presents an `INFERRED`/`UNAVAILABLE`-basis value with a strengthening marker
on the mechanically exact supported axes — `SHOULD`→`MUST`, `MAY`→`MUST`, unknown→known,
WEP band mutation, explicit probability-band change (`OUT-BASIS-NOT-STRENGTHENED`, draft.2
D-F; it implements only the exact supported cases and says so — no general semantic-force
understanding is claimed); and the receipt, when supplied, reproduces its content address
and binds the supplied source, policy, and output hashes.

*Why a deterministic procedure over these inputs is conformance evidence under §16.5.* These
are byte- and pointer-level identities over four content-addressed artifacts: the exact
output bytes, the sealed trace, the validated IR, and the sealed policy snapshot. §14.13
requires a receipt to bind source and output hashes, policy hash, and parser identity, and
§16.12 requires a verification command to validate hashes and schemas and re-run
deterministic rules. That is what this family is. A P0 mismatch is not an opinion about
faithfulness; it is `entry["source_value"] != rendered`. The parser is named and versioned on
every report (`markdown-it-py/commonmark@<version>`), so §15.8's staleness rule can fire when
it changes.

*What it explicitly does NOT establish.* That a mapped block *realizes* the object it points
at. Mapping is a declaration by the renderer, not a proof. This is stated in the module
docstring and enforced in the results: `OUT-P1-DECLARED` reports `REVIEW_REQUIRED` — never
`PASS` — even when every material relation is declared by a block, because "declaration
establishes that the block claims the relation, not that the prose realizes it with the same
force and direction." `OUT-P0-EXACT` likewise reports `REVIEW_REQUIRED` when *no* block
declares a P0 field, because exact rendering of protected values is then undeclared rather
than verified. Nothing in this family is a preservation proof either: it compares one IR
against one rendering, not a source artifact against a derived one (§11.11, ADR-0005).

*When it abstains.* `OUT-MARKERS` reports `UNAVAILABLE` when the document did not parse,
because markers could not be located. `OUT-PROFILE-SECTIONS` reports `UNAVAILABLE` when no
declared profile has structural obligations here (§9.5). `OUT-FINDING-DISPOSITIONS` reports
`UNAVAILABLE` when no receipt is supplied, because no disposition record exists to check
(§15.3). `OUT-COORD-PRESERVED` reports `NOT_APPLICABLE` when the IR declares no
`stable_coordinates` block, and `OUT-BASIS-NOT-STRENGTHENED` reports `NOT_APPLICABLE` when
TRANSFORM is not among the active profiles or the IR declares no `semantic_basis` — both
are *gated* checks: they join the mechanical dimension (`GATED_MECHANICAL_CHECKS`) only
when the IR declares the surface they protect, via their `required` flag, so draft.1
bundles validate unchanged under draft.2. `OUT-RECEIPT` reports `NOT_APPLICABLE` when no
receipt was supplied to the run, and `UNAVAILABLE` when a supplied receipt records a
`semantic_review: PASS` or `preservation: PASS` this implementation cannot reproduce —
§16.12 permits such a result to remain valid as historical evidence, but requires the
report to state that replay is unavailable.

### ats-output-rule

**The 8 deterministic surface checks over rendered prose.** Implemented in
`src/ats/output/render_checks.py`, surfaced as `OUT-WEP-CANONICAL`, `OUT-WEP-INLINE-RANGE`,
`OUT-DEONTIC-KEYWORDS`, `OUT-ACRONYMS`, `OUT-UNITS`, `OUT-RELATIVE-TIME`, `OUT-TERMINOLOGY`,
and `OUT-HEADINGS-LISTS`. These re-express rule obligations against the *rendered* text,
where the IR-rule family can only see what the ledger declares.

*What it decides.* That the prose a reader actually sees obeys the closed vocabularies: only
canonical WEP phrases appear (§8.3); the first material WEP use in a section shows its
display range inline (§8.4); deontic keywords are canonical and uppercase (§8.16, §1.3);
acronyms are expanded on first material use or permitted by the artifact's glossary (§10.5);
numbers the trace declares as P0 render with a unit (§10.9, §9.3.8); relative-time
expressions are anchored (§10.11); deprecated glossary aliases, the empty intensifiers
enumerated verbatim in §10.20, the vague evaluative terms enumerated verbatim in §10.21, and
the vague timing terms named in §9.3.7 are absent from material prose; and heading nesting
and list mechanics hold (§10.17, §10.18).

*Why a deterministic procedure over these inputs is conformance evidence under §16.5.* Every
vocabulary this family matches against is closed and externally sourced — the force lexicon,
a list the spec enumerates verbatim, or the artifact's declared glossary — so the match is
mechanical, not interpretive. The alternative the spec forbids is precisely what this family
avoids: §14.4 says a parser failure MUST NOT cause the implementation to silently run
token-only rules and report full conformance, and `lint_output` honours that by marking every
surface check `UNAVAILABLE` when `parse_markdown` raises. Section 5.6 exemptions are applied
mechanically from declared content classes (`quotation`, `code`, `log`, `schema`,
`counterexample`) and from block kinds that are code or quotation by construction, with the
exempted block ids listed in the check detail so an exemption is visible rather than silent.

*What it explicitly does NOT establish.* That the prose means what the IR means. A document
can use every canonical phrase correctly and still say the wrong thing. In particular this
family cannot decide §10.4 (a precise term replaced by a broader one), §10.6 (one plausible
antecedent), or §10.16 as applied to rendered order with the interpretive qualifier §10.16
itself carries — those need the source text, a syntax tree, or a semantic judgment.

*When it abstains.* `NOT_APPLICABLE` when a check inspected zero blocks, `UNAVAILABLE` when
the document did not parse. Neither is reported as `PASS`.

---

## The D0–D4 ladder and the authority ceiling

§12.3 defines five detector classes and the authority each may typically carry.
`src/ats/rules/registry.py` encodes the ceiling as data:

```python
DETECTOR_CLASS_MAX_AUTHORITY: Final[dict[str, str]] = {
    "D0": "conformance_evidence",
    "D1": "conformance_evidence",
    "D2": "candidate_only",
    "D3": "proposal_only",
    "D4": "conformance_evidence",
}
```

| Class | Mechanism (§12.3) | Ceiling here | Implemented in v0 |
|---|---|---|---|
| `D0` | Token, lexicon, pattern, and exact-value checks | `conformance_evidence` | Yes — 11 rules |
| `D1` | Syntax tree, document AST, glossary, and structural checks | `conformance_evidence` | Yes — 14 rules (9 draft.1 + `ATS-COORD-001`, `ATS-COORD-002`, `ATS-BASIS-002`, `ATS-PRES-003`, `ATS-CLOSE-001`) |
| `D2` | Static retrieval of candidate rules and analogous adjudications | `candidate_only` | **No.** No rule router exists; declared in `KNOWN_LIMITATIONS`. |
| `D3` | Rule-conditioned semantic critic | `proposal_only` | Four rules report D3 — see below. `ATS-BASIS-001` is a genuine D3 detector; no learned critic exists. |
| `D4` | Cross-text preservation, contradiction, and repair verification | `conformance_evidence` *only after independent preservation validation* | **No.** Preservation remains unavailable (ADR-0005). Draft.2's `ATS-PRES-003` is a D1 trace-exactness rule, not a D4 semantic-preservation critic. |

The ceiling is not advisory. `Context.detector()` raises `UsageError` when asked to build a
detector claiming `conformance_evidence` for a class whose ceiling forbids it, and
`CapabilityDeclaration.coherence_errors()` reports the same condition against the checked-in
declaration. `load_capability` calls `require_coherent()` at load time, so an incoherent
declaration is a hard failure of `Context.load()`, not a lint warning.

### Why D3 output is proposal-only in this draft

§14.8: "A D3 critic is proposal-only in core ATS-1 draft policy. Its finding can be accepted,
rejected, or used to request more evidence, but the critic MUST NOT directly set a
conformance dimension to `PASS` or `FAIL`." §16.5 makes the consequence explicit — D3 output
is `proposal_only` *regardless of the active rule state*, so a required rule can remain a
normative artifact obligation while its detector lacks authority to decide conformance.

Four rules in this build report D3 with `proposal_only` authority. Three of them —
`ATS-EPI-006`, `ATS-EVID-002`, `ATS-EVID-003` — are the draft.1 trio, none of which is a
learned critic: they report D3 because their registry records list only `D3` and `D4` as
their detector classes, leaving a deterministic structural detector with no class of its own
to claim. Claiming an undeclared class would be the dishonest option; reporting D3 and
accepting its ceiling is the conservative one. See
[`PACKAGE_OBSERVATIONS.md`](PACKAGE_OBSERVATIONS.md) observation (a) and ADR-0008. The
practical effect is visible in a real run: on the ASSESS conforming fixture, `ATS-EVID-003`
(state `required`) reports `REVIEW_REQUIRED`, not `PASS`.

The fourth, draft.2's `ATS-BASIS-001`, *is* a genuine D3 detector — a rule-conditioned
semantic critic that checks whether material values declare a source basis. Its D3 class
and `detects_violations` power are exactly matched to its ceiling: a finding surfaces for
review, a clean run reports `REVIEW_REQUIRED`, and it can never decide conformance (§14.8,
§16.5).

---

## The basis/strengthening prohibition (ATS-BASIS-002)

Draft.2's narrowest new authority boundary is the semantic-strengthening prohibition
(§4.25, §7.19, ADR-0012):

> A transformation MUST NOT silently convert `INFERRED` or `UNAVAILABLE` source material
> into an explicit source-authoritative semantic fact.

The material axes are enumerated, not vibed: authority; authority precedence; deontic
force; acceptance/settlement state; likelihood; confidence; quantifier; polarity; causal
force; normative dependency; exception removal; source attribution.

The compiler's permitted moves are likewise enumerated, and the prohibition is on the one
move not in the list:

| Permitted | Forbidden |
|---|---|
| preserve the value as `INFERRED` | silently promote `INFERRED`/`UNAVAILABLE` to `EXPLICIT` |
| represent it as unresolved (typed `UNAVAILABLE`) | pretend the source declared it |
| omit it when nonessential | |
| propose a candidate interpretation | |
| ask for adjudication when action requires resolution | |

This is enforced at two authority levels. **`ATS-BASIS-002`** (D1, `decides`,
`conformance_evidence`, operational class `BLOCK`) compares the rendered claim's declared
basis against the source side's recorded basis — carried through `source_refs` plus a basis
map in `extensions` — and `FAIL`s on promotion for a TRANSFORM. When the comparison is not
possible, it reports `REVIEW_REQUIRED`, never `PASS` by absence. **`ATS-BASIS-001`** (D3,
`detects_violations`, `proposal_only`, operational class `REVIEW_REQUIRED`) surfaces
material values that declare no basis at all; it can propose, never decide. The
`OUT-BASIS-NOT-STRENGTHENED` output check adds the rendering-side half: no block presents
a basis-`INFERRED`/`UNAVAILABLE` IR value with a strengthening marker on the mechanically
exact axes. A detector may *never* promote inferred material — the prohibition binds the
implementation as tightly as it binds the authoring skill, and the never-PASS-by-absence
gate (§16.5, ADR-0002) guarantees that a missing comparison is a review, not a clean.

---

## Two orthogonal gates in `decide()`

`ats.rules.results.decide()` is the only constructor detectors use for a `RuleResult`, and it
**derives** the status — the caller never supplies one. Two independent gates apply, matching
§12.3's statement that rule state and detector authority are orthogonal:

> **Decision power gates `PASS`.** Only a complete decision procedure may conclude
> conformance from the absence of a finding (§5.4, §16.5).
>
> **Detector authority gates `FAIL`.** `candidate_only` output can route work but cannot
> establish applicability; `proposal_only` output can create a finding for adjudication but
> cannot independently establish `PASS` or `FAIL` (§12.3).

The derivation, in order:

| Condition | Status | Why |
|---|---|---|
| `effective_state == "disabled"` | `NOT_APPLICABLE` | The rule does not run (§6.2). |
| any `missing_inputs` | `UNAVAILABLE` | A required check that cannot execute is `UNAVAILABLE`, not `PASS` (§5.4). |
| `decision_power is UNDECIDABLE` | `UNAVAILABLE` | No decision procedure is implemented for this rule. |
| findings **and** `authority == conformance_evidence` | `FAIL` | A decided failure. |
| findings **and** lower authority | `REVIEW_REQUIRED` | Findings are attached and surfaced for adjudication; §12.3 forbids them independently establishing `FAIL`. |
| no findings, `DECIDES`, `conformance_evidence` | `PASS` | The only path to `PASS`. |
| no findings, `DECIDES`, lower authority | `REVIEW_REQUIRED` | A complete procedure ran and found nothing, but the detector may not contribute a conformance decision. |
| no findings, `DETECTS_VIOLATIONS` | `REVIEW_REQUIRED` | Absence of a deterministic violation does not establish conformance (§16.5). |

### Why this is structural, not conventional

A convention would be a rule in a style guide: "detectors should not return `PASS` when they
only recognise violations." Four things make it a structure instead:

1. **`RuleResult.status` is not a parameter.** `decide()` computes it. A detector body cannot
   pass `Status.PASS`; there is no argument for it.
2. **Detector bodies do not build results at all.** A body has the type
   `Callable[[IrEvaluation, Detector], tuple[list[Finding], list[dict]]]` — findings and
   subcheck records. `run_detector` applies the policy state, the missing-input rules, and
   `decide()`. The result type is not reachable from a body.
3. **Authority is derived from the declared class, not chosen.** `DetectorSpec.authority` is
   `DETECTOR_CLASS_MAX_AUTHORITY[self.detector_class]`, and `Context.detector()` re-checks it
   against the same table when constructing the identity. A detector cannot award itself an
   authority its class does not permit.
4. **The declaration cannot drift from the code.** `capability/ats_rule_capability_v1.json`
   is generated from the same `DetectorSpec`s by `tools/generate_capability.py`, and
   `CapabilityDeclaration.coherence_errors()` cross-checks the result against the imported
   registry — including the rule that a `decides` declaration whose authority is not
   `conformance_evidence` "can never report PASS, so declaring 'decides' overstates it."

This is constitution #9 and #10 applied to conformance: the LLM-free layer does the scoring,
and the gates are per-dimension floors, never a compensating composite. It is also an
imperfect application of #3 — Python cannot make the illegal call uncallable, so the
invariant lives at the narrowest runtime chokepoint available rather than in the type system.
That gap is named rather than papered over.

---

## `DecisionPower` and `input_substitutions`

### `DecisionPower`

Declared per detector in its `DetectorSpec`, mirrored into the capability document, and
consumed by `decide()`:

| Value | Meaning | May return |
|---|---|---|
| `decides` | A complete decision procedure for the rule over the objects supplied | `PASS`, `FAIL`, `NOT_APPLICABLE` |
| `detects_violations` | Recognises a defined subset of violations | `FAIL`, `REVIEW_REQUIRED`, `NOT_APPLICABLE` — **never `PASS`** |
| `undecidable` | Cannot decide the rule from the available inputs at all | `UNAVAILABLE` with the missing inputs named |

The corresponding subcheck records carry `decides: true|false`, and
`_support.subcheck()` maps an inspected-but-clean `decides: false` subcheck to
`REVIEW_REQUIRED` rather than `PASS`, so the honesty rule holds at subcheck granularity too,
not only at rule granularity.

`to_conformance_status()` maps `REVIEW_REQUIRED` onto the normative `UNAVAILABLE`, because
the check ran but this implementation cannot supply conformance evidence for it — which is
exactly what §5.4 calls unavailable.

### `input_substitutions`

A rule's `required_inputs` come from the normative registry. When the TextIR surface cannot
supply one, the honest default is `UNAVAILABLE`. But some required inputs are named for a
*surface* rather than for the *information* the obligation needs, and silently assuming the
information is present would be exactly the "silent fallback" §14.12 forbids.

The `input_substitutions` mechanism makes such an assumption explicit and reviewable. Each
entry declares the missing `input`, what it is `substituted_by`, the `spec_ref` that
authorizes the substitution, and a `justification` that also states what the substitution
does **not** cover. Three are declared today:

| Rule | Missing input | Substituted by | Spec basis |
|---|---|---|---|
| `ATS-EPI-002` | `document_ast` | TextIR section and claim ordering | §7.3 |
| `ATS-DISC-001` | `document_ast` | TextIR section and claim ordering | §7.3 |
| `ATS-REQ-002` | `syntax` | the requirement object's structured action slot | §9.3.2, §9.3.3 |

`CapabilityDeclaration.coherence_errors()` enforces the arithmetic so a substitution cannot
be used to hide a real gap:

- `missing_inputs` MUST equal `required_inputs − available_inputs`;
- a substitution MAY only be declared for an input that is actually missing;
- `blocking_inputs` MUST equal `missing_inputs − substituted inputs`;
- a rule declared `implemented` MUST have no blocking inputs — otherwise it could only ever
  return `UNAVAILABLE`, so it must declare itself undecidable or declare a substitution.

At runtime, `DetectorSpec.blocking_inputs()` computes the same difference, and `run_detector`
short-circuits to `UNAVAILABLE` on any blocking input. A substitution therefore changes what
the detector is *allowed to attempt*; it never changes what a clean result means.

---

## Why this implementation never reports `semantic_review: PASS`

`semantic_review` is a hardcoded `"UNAVAILABLE"` in `ats.ir.lint.compute_conformance` and in
`ats.output.lint._compute_conformance`, with a rationale string naming the reason. This is
not a temporary gap awaiting a feature; it follows from three requirements that this build
structurally cannot meet.

§15.3 lists what `semantic_review: PASS` requires. Three of its clauses are decisive:

1. *"every surfaced advisory or required finding was dispositioned."* Disposition is an act
   of authority, not a computation. This package emits findings in state `proposed` and has
   no path to any other state.
2. *"every required semantic predicate was evaluated by an authorized human, authoritative
   structured source, or detector operating as validated `conformance_evidence`."* No
   detector here has been promoted under §18, and no human is in the loop of a linter run.
3. *"The absence of D3 findings is insufficient by itself because D3 output is proposal-only
   in this draft."*

§14.11 closes the remaining door: core ATS-1 assigns final authority for semantic acceptance
to an authorized human or an explicitly governed external acceptance system.

The honest consequence is that a clean run's vector is *not* all-`PASS`, and this is correct
rather than a defect. §20.6 states it plainly: `UNAVAILABLE` and `INSUFFICIENT_EVIDENCE` are
valid outcomes. The reported rationale says so in full, so a reader of the report never has
to infer it. See ADR-0005.

`forecast_calibration` is `INSUFFICIENT_EVIDENCE` for the parallel reason: §15.5 requires a
declared cohort, resolved outcomes, a scoring rule, reliability analysis, uncertainty
estimates, no outcome leakage, and a pre-declared minimum evidence threshold. None is
implemented, and the rationale reports the forecast and resolved-forecast counts it did
observe so the gap is quantified rather than asserted.

---

## Who may adjudicate

§14.11 and §13.7 place acceptance authority outside the producing component. §13.7 is the
sharper of the two: a model MAY propose an adjudication rationale, but it MUST NOT become the
authoritative adjudicator for its own finding unless a separate policy explicitly delegates
that authority *and* an independent verifier checks the result — and core ATS-1 policy
SHOULD NOT delegate it. §14.10 adds the structural form of the same idea: the component that
generates a semantic repair MUST NOT be the sole component that verifies preservation.

`src/ats/output/receipt.py` enforces this at the only point where an adjudicator identity
enters the system:

```python
SELF_IDENTITIES = frozenset({"ats", "ats-ir-linter", "ats-output-linter", "self", ""})
```

`build_candidate_receipt` raises `UsageError` when the supplied `adjudicator`, casefolded and
stripped, is in that set. `verify_receipt` applies the same test to a receipt it is checking,
so a receipt that named itself is a `FAIL` on re-verification, not merely a refusal to create
one. The word *candidate* in `build_candidate_receipt` is load-bearing: the receipt records
what the deterministic stack established and who the external adjudicator is; it does not
assert that acceptance happened.

This is constitution #14 (independence is structural, not prompted) and #27 (trust receipts,
not self-reports) in their strictest form — the producing component cannot name itself as the
party that certifies its output, and the check is a set membership rather than a policy
someone must remember.

---

## What promotion would require

No detector in this build may be promoted by editing a declaration. §16.5 states the rule
directly: a policy MUST NOT grant a learned detector `conformance_evidence` authority unless
it has passed the promotion requirements in §18, and a capability declaration and receipt
MUST bind the authority basis.

§18.1 fixes the lifecycle: `draft → shadow → advisory → required`. A rule state MAY also move
to `deprecated` and then `retired`, and a retired identifier MUST NOT be reused —
`RuleRegistry.get()` cites §18.1 when refusing an unknown rule id for exactly this reason.

§18.2 requires evidence for rule-definition stability; positive, violation, exception, and
hard-negative coverage; parser and source-mapping reliability; detector calibration;
conceptual-gate performance; out-of-domain behavior; abstention behavior; reviewer burden;
actionability; repair safety when autofix exists; downstream value; and independent
validation.

§18.3 (advisory) requires stable wording, consistent reviewer adjudication, first-finding
utility above a preregistered threshold, acceptable false-positive burden, and a detector
that abstains rather than guessing outside its competence.

§18.4 (required) additionally requires that the operating threshold and calibration are
frozen; project-disjoint and domain-disjoint evaluation passes; hard-negative precision
passes; known failure modes are documented; required-context absence produces `UNAVAILABLE`
or abstention; an override and exception path exists; an independent acceptance authority
approves promotion; and a rollback policy exists.

§18.5 forbids promotion by aggregate score alone: a high aggregate MUST NOT compensate for
catastrophic errors on polarity changes, deontic-force changes, causal overclaim,
source-attribution loss, probability-band changes, or omitted exceptions. §18.6 requires a
promotion receipt binding rule and detector versions, preregistered gates, evaluation corpus
hashes, split policy, metrics, failure cases, the reviewer decision, the effective policy
date, and the rollback trigger.

Two of those gates are the reason this repository builds a corpus at all before it builds any
learned component: project-disjoint and domain-disjoint evaluation (§18.4) and conceptual-gate
performance (§18.2, §17.8) are unobtainable without the leakage-controlled splits described in
[`CORPUS_DATA_MODEL.md`](CORPUS_DATA_MODEL.md). §12.9 adds the corresponding rule-level bar: a
rule MUST NOT be promoted to `required` based only on synthetic violations or examples that
repeat the rule's wording.

---

## The unwaivable-preservation rule

§6.4 is the one place where the standard removes policy's discretion entirely:

> An implementation MUST NOT report `preservation: PASS` when either `ATS-PRES-001` or
> `ATS-PRES-002` is disabled, unavailable, failed, or waived for a material retained claim.
> A policy MAY allow the transformation to proceed, but the result is not ATS-1
> preservation-conformant.

Both rules carry `waivable: false` in the imported registry, and both are declared
`undecidable` here: `ats ir lint` evaluates one artifact, while preservation compares a source
artifact against an output artifact under a retention contract with authorizations, and no v0
command constructs that pair.

Draft.2 widens the unwaivable set from two rules to five. The integrity rules
`ATS-COORD-001`, `ATS-COORD-002`, `ATS-BASIS-002`, and `ATS-PRES-003` all carry
`waivable: false` and `autofix: forbidden` — they are the `BLOCK` operational class, and no
policy may waive a coordinate drop, a basis promotion, or a protected-relation loss.
`ATS-BASIS-001` and `ATS-CLOSE-001` are `waivable: true`: they are review-class rules whose
findings an authorized adjudicator may waive with a recorded rationale. The output-side
gated checks (`OUT-COORD-PRESERVED`, `OUT-BASIS-NOT-STRENGTHENED`) are structural
`BLOCK`s whenever they are active — an IR that declares coordinates or basis has no
non-blocking rendering path that drops them.

The consequence is computed, not asserted. `ats.ir.lint.compute_conformance` reports
`preservation: NOT_APPLICABLE` when both rules resolve to `disabled` (no TRANSFORM profile is
active, so the artifact is not a transformation output, §15.4), and `UNAVAILABLE` otherwise,
with the rationale naming §6.4 and the four missing inputs. `ats.output.lint` reaches the same
two outcomes from `"TRANSFORM" in policy.profiles`. There is no third branch.

It is worth being explicit about what the output linter's P0 and P1 checks are *not*. They
compare one IR against one rendering of it. §11.11 defines `preservation: PASS` over a
source-to-output transformation. `ats.capability.PRESERVATION_METHODS` therefore declares only
`p0_exact_declared_rendering` and `p1_declared_representation` — declared-representation
evidence about a single rendering, which is not a preservation proof and is not offered as
one.

---

## The planning and acceptance boundary (draft.2 D-I)

Draft.2 settles who may author, who may decide, and who may accept. The split is ownership of
*semantic compilation and conformance evidence* versus ownership of *workflow and acceptance*.
This repository implements only the ATS-owned side of that contract; downstream workflow
internals are not authored here.

| Party | Owns | Does NOT own |
|---|---|---|
| **ATS** (this repo) | Representation — the `ats.text_ir.v1` meaning ledger, its schemas, deterministic IR/output lint, receipts, and the planning projection; conformance evidence — what the deterministic stack can establish | Workflow, execution, adoption policy, acceptance. No module here is a workflow engine or an execution authority (§13.7). |
| **Downstream planner** | Planning sufficiency — whether an ATS artifact is sufficiently specified to plan from | Re-authoring — it verifies the receipt and consumes the projection; it does not re-implement IR checks, detectors, or schemas |
| **Authorized decider** | Final acceptance and any governing adoption decision | ATS semantics and the deterministic evidence record |

The chain makes three decisions explicit and distinct:

> **ATS-valid ≠ sufficiently specified for planning ≠ accepted.**

A deterministic green run establishes the first. Whether the artifact names the actors,
conditions, acceptance criteria, and dependencies a planner needs is a sufficiency decision
the downstream planner makes from the projection — it may reject a valid artifact as
insufficient. Whether the artifact is accepted is an acceptance decision held by an
authorized human or an explicitly governed external acceptance system (§14.11), never by
the producing component (`SELF_IDENTITIES`, above).

Stable semantic coordinates originate at the durable-artifact boundary and carry downstream
unchanged (`source_requirements=[REQ-...]` at task generation,
`evidence_for=[REQ-...]` at acceptance). ATS ambiguity escalates in ladder order before any
human: deterministically recover → record the judgment (`AUTHOR_JUDGMENT`) or stay
`UNAVAILABLE` → continue → only product-authority distinctions reach the human
(`ADR-0016`). The thin interface is a durable document plus IR, trace, receipt, and
planning projection; this repo ships the ATS side only. The projection contract is in
[`PLANNING_PROJECTION.md`](PLANNING_PROJECTION.md).

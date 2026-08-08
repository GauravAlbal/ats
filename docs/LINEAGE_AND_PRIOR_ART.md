# ATS-1 — Applied Technical Semantics: Lineage and Prior Art

**Status: informative, not normative.** This document explains where ATS-1's
design ideas come from. It does not define, extend, or modify ATS-1. The
normative source of truth is the ATS-1 standard package
(`spec/ATS-1/`), which governs whenever this document conflicts with it.

It answers one question:

> What existing disciplines did ATS learn from, what did ATS retain from
> each, what did ATS deliberately not inherit, and what new integration
> problem is ATS attempting to solve?

ATS is not presented as a clean-room invention of every underlying idea. It
combines established ideas from several previously separate traditions around
a different target workload:

```text
AI-authored
→ AI-consumed
→ implementation-bearing
→ human-inspectable
technical artifacts
```

## Naming migration

The current public expansion is **Applied Technical Semantics**. Earlier
sealed editions preserve **Arq Text Standard** as their historical expansion;
this record retains that name as history rather than current public identity.
The migration changes naming only and does not alter ATS-1 normative meaning,
version identities, or released package bytes.

---

## 1. Lineage doctrine

Every prior-art family below is analyzed in the same shape:

```text
SOURCE / TRADITION
    ↓
problem it was designed to solve
    ↓
useful mechanism
    ↓
ATS adoption or adaptation
    ↓
boundary / rejected inheritance
```

The important question is not merely "did ATS look at X?" It is: **which ATS
design decision descends from X, and why was X alone insufficient for ATS's
target job?**

Each entry carries an honesty classification:

- **directly adopted** — ATS takes the mechanism substantially as-is;
- **adapted** — ATS takes the mechanism and changes it materially;
- **conceptually influenced** — ATS shares the idea but the mechanism is its
  own;
- **independently convergent** — similar outcome, no established evidence of
  descent;
- **rejected** — considered and deliberately not inherited.

Where repository research notes do not establish the provenance of a feature,
this document says `provenance = UNAVAILABLE` rather than reconstructing
historical descent from resemblance.

---

## 2. ASD-STE100 — controlled technical language

**Problem:** ASD-STE100 (Simplified Technical English) targets technical
communication where vocabulary and grammatical control reduce ambiguity and
reading burden, especially in procedural and maintenance-oriented
documentation.

**Useful mechanism:** stable terminology; restricted ambiguity; controlled
vocabulary; direct grammatical constructions; procedural clarity; reduced
local parsing burden.

**ATS adoption:** ATS inherits the conviction that *language itself can be
engineered*: one stable term for one technical concept where practical,
avoidance of unnecessary lexical variation, explicit actors, direct
statements, controlled ambiguity, mechanically detectable surface rules, and
profile-sensitive writing constraints. STE is the most direct historical
inspiration for treating technical prose as something that can have an
explicit standard rather than relying only on taste. *Classification:
conceptually influenced and partially adapted (terminology control,
surface rules).*

**Boundary / rejected inheritance:** ATS does **not** adopt linguistic
simplicity as the global optimization target. Reducing local sentence
complexity can increase global reconstruction cost when technical meaning
resides in relations, state distinctions, authority, exceptions, evidential
status, dependencies, acceptance conditions, and uncertainty. ATS's governing
principle is:

> **Remove words before removing relations.**

ATS therefore permits domain terminology, locally repeated actors, repeated
requirement context, explicit state machines, and acceptance criteria that
intentionally restate requirement semantics when those forms improve semantic
recovery or downstream extraction.

**Why STE alone was insufficient:** for ATS's target workload, a document can
become easier to read while becoming less determinate to implement. The
observed Sear transformation is a case study, not universal proof, but
illustrates the failure class: `accepted → routed → disclosed → consumed` can
be compressed into "accepted mail cannot be silently dropped" while losing
distinctions that govern recovery and semantic consumption. ATS treats
**implementation-relevant semantic preservation** as non-compensable by
surface readability.

---

## 3. SEC / NASA / engineering style-guide tradition

**Problem:** institutional engineering and regulatory style guides make
technical prose direct, consistent, reviewable, concise, structurally
predictable, and resistant to common writing defects.

**ATS adoption:** conventional technical-writing mechanics — load-bearing
statements early, explicit subjects, stable terms, avoidance of decorative
prose, short paths from assertion to evidence, operationally meaningful
wording. *Classification: adapted (baseline prose discipline).*

**Boundary:** ATS does not treat conventional editorial quality as
conformance by itself. A grammatically excellent paragraph can still be
defective if it obscures epistemic status, normative force, authority, scope,
dependency, or evidence obligation. ATS separates **surface realization**
from **semantic integrity**.

---

## 4. INCOSE and requirements-engineering guidance

**Problem:** requirements engineering makes requirements singular,
attributable, testable, bounded, implementation-relevant, and verifiable.

**ATS adoption:** this lineage is central to the `SPECIFY` profile: explicit
requirement identity, explicit actor, controlled deontic force, conditions
and triggers, quantitative boundaries, verification/acceptance obligations,
stable requirement coordinates, and the preserved distinction between
*requirement* and *acceptance criterion* even when they intentionally overlap.
*Classification: adapted and extended.*

**Boundary:** ATS is not only a requirements language. It must coexist with
observations, assumptions, inference, uncertainty, alternatives, judgments,
recommendations, postmortem evidence, and causal assessments. ATS embeds
requirements discipline inside a broader discourse system rather than forcing
all technical reasoning into requirement statements.

---

## 5. EARS, FRETish, FRET — structured requirement patterns

**Problem:** structured requirement languages reduce ambiguity by giving
recurring logical forms explicit syntax (for example, the EARS event-driven
form `WHEN <trigger> THE <system> SHALL <response>`, and the combined form
`WHILE <state> WHEN <trigger> THE <system> SHALL <response>`). FRET
additionally explores machine-interpretable requirement semantics and
alternative interpretations.

**ATS adoption:** explicit conditions and triggers, scoped obligations,
separation of temporal/conditional relations from surface prose, and the idea
that ambiguous statements can produce **candidate interpretations** rather
than being silently normalized — which directly informs ATS's
`REVIEW_REQUIRED` state and the prohibition on turning an inferred
interpretation into source authority. *Classification: conceptually
influenced, adapted.*

**Boundary:** ATS does not require all prose to fit one formal requirement
template. Rationale, evidence, competing hypotheses, uncertainty, and
architecture explanation need expressive prose; ATS protects the semantic
relations while allowing varied surface realization.

---

## 6. RFC 2119 / RFC 8174 — standards deontics

**Problem:** Internet standards need a small stable vocabulary for requirement
strength (MUST / MUST NOT / SHOULD / SHOULD NOT / MAY), with RFC 8174
clarifying normative interpretation of capitalization.

**ATS adoption:** a constrained deontic vocabulary (`MUST`, `MUST NOT`,
`SHOULD`, `SHOULD NOT`, `MAY`, plus `CAN`/`CANNOT` for capability rather than
permission), with exact deontic force treated as **protected semantics** —
`SHOULD → MUST` is a semantic mutation, not a stylistic rewrite.
*Classification: directly adopted in substance, adapted into a larger force
system.*

**Boundary:** ATS applies deontic control beyond standards documents and
integrates it with epistemic force, evidence, causal claims, authority, and
provenance. A requirement-strength vocabulary alone does not tell the reader
whether the proposition is an observation, inference, judgment, or design
decision.

---

## 7. ISO-style verbal forms and requirements modality

**Problem:** standards bodies distinguish requirement, recommendation,
permission, and possibility/capability through controlled verbal forms.

**ATS adoption:** the fundamental separation is preserved: `MUST` does not
mean "likely"; `MAY` permission does not mean `CAN` capability — a
non-compensatory force model. *Classification: adapted.*

**Boundary:** ATS extends the concept from deontic form into a larger set of
independent force axes.

---

## 8. ICD 203 — words of estimative probability

**Problem:** intelligence analysis needs calibrated uncertainty language that
prevents vague probabilistic prose from concealing materially different
assessments.

**ATS adoption:** a calibrated estimative-probability vocabulary derived from
this tradition (approximately: Almost no chance 1–5%, Very unlikely 5–20%,
Unlikely 20–45%, Roughly even chance 45–55%, Likely 55–80%, Very likely
80–95%, Almost certain 95–99%). The inherited doctrine is that **probability
language should map to an explicit quantitative interpretation**.
*Classification: adapted (label set and bands).*

**Boundary:** ATS applies the calibrated vocabulary to general technical
assessments and separates it from confidence and evidential force.

---

## 9. UK PHIA / professional intelligence-analysis conventions

**Problem:** professional analytic standards distinguish likelihood,
confidence, assumptions, evidential limitations, and alternative
explanations.

**ATS adoption:** the principle that *event likelihood ≠ assessment
confidence* — an analyst can legitimately state LIKELY with LOW confidence or
ROUGHLY EVEN CHANCE with HIGH confidence — and that confidence basis should
be inspectable (directness, source independence, coverage, recency,
consistency, contrary evidence, assumption sensitivity, volatility).
*Classification: adapted.*

**Boundary:** ATS generalizes the discipline beyond intelligence products to
architecture, diagnostics, postmortems, and technical decision-making.

---

## 10. IPCC calibrated uncertainty language

**Problem:** scientific assessment needs disciplined communication of
uncertain claims across large evidence bases.

**ATS adoption:** explicit probability language, separation of assessment
confidence from likelihood, attention to evidence quality, avoidance of vague
qualifiers when a calibrated expression is warranted. *Classification:
conceptually influenced.*

**Boundary:** ATS does not adopt the IPCC framework wholesale; its domains
require additional distinctions around implementation authority,
requirements, acceptance, machine transformation, and provenance.

---

## 11. Attempto Controlled English

**Problem:** Attempto explores natural-language subsets that map to formal
semantic representations; ordinary-looking prose can have constrained
semantics suitable for machine processing.

**ATS adoption:** the idea that human-readable language and
machine-recoverable structure need not be opposing goals — the basis of the
ATS prose ↔ TextIR relationship and deterministic checks over parts of prose
semantics. *Classification: conceptually influenced.*

**Boundary:** ATS does not attempt to make all technical prose equivalent to
formal logic. Engineering artifacts contain uncertain judgments, incomplete
evidence, recommendations, defeasible reasoning, and open questions; ATS uses
typed discourse rather than complete logical formalization.

---

## 12. SBVR — business-rule semantic typing

**Problem:** SBVR-style systems make business vocabulary, rules, obligations,
and permissions explicit and machine-interpretable.

**ATS adoption:** typed concepts, modality, stable vocabulary, separation of
fact from obligation, preserved relational semantics. *Classification:
conceptually influenced.*

**Boundary:** ATS targets broader technical discourse and lighter-weight
human inspection rather than formal enterprise-rule modeling.

---

## 13. DITA — topic-oriented documentation

**Problem:** DITA treats documentation as reusable typed information units
rather than monolithic documents.

**ATS adoption:** modularity, extraction, reusable semantic units, explicit
information role — related to the ATS concept of **local semantic closure**:
a requirement or assessment unit should survive retrieval or decomposition
with limited undeclared global context. *Classification: conceptually
influenced.*

**Boundary:** ATS does not require DITA XML or its information architecture;
the modularity principle is applied at the semantic/prose layer.

---

## 14. Diátaxis — documentation-type separation

**Problem:** different documentation jobs should not be collapsed into one
generic writing style (tutorial, how-to, explanation, reference).

**ATS adoption:** the idea that **writing rules depend on discourse purpose**
motivated ATS profiles — the stable `ASSESS` and `SPECIFY` profiles rather
than one universal ATS style, with artifact recipes composing them.
*Classification: adapted (the idea), independently convergent in mechanism.*

**Boundary:** ATS profiles are defined around semantic function in
implementation-bearing technical artifacts, not general documentation
pedagogy.

---

## 15. IARPA REASON / CREATE / ACE — structured analytic reasoning

**Problem:** research programs investigate more reliable reasoning through
structured argument, evidence tracking, alternative hypotheses, forecasting,
critique, and reasoning support.

**ATS adoption:** treating technical documents as **inspectable reasoning
artifacts** — explicitly separate evidence from judgment, preserve contrary
evidence, expose assumptions, keep alternative hypotheses visible when
unresolved, calibrate forecast language, permit critique of reasoning
structure. *Classification: conceptually influenced.*

**Boundary:** ATS is not a reasoning engine or adjudicator; it *represents*
reasoning state. The system MUST NOT claim that an ATS-conforming argument is
therefore correct.

---

## 16. FRETish and ARTEMIS — distinct ambiguity-analysis lineages

**FRET/FRETish problem:** FRET is a NASA Ames requirements-elicitation tool
whose FRETish language maps constrained prose to formal semantics and can
surface alternative interpretations.

**ARTEMIS problem:** ARTEMIS is a distinct 2026 generate-and-validate
framework that uses FRETish as an intermediate representation and
distinguishing traces to expose semantic alternatives. The public repository
record does not establish direct ATS-to-ARTEMIS descent; for that specific
feature mapping, `provenance = UNAVAILABLE`.

**ATS adoption:** when multiple interpretations are plausible, ATS prefers
`candidate A, candidate B → REVIEW_REQUIRED` over `model selects one → PASS` —
supporting the laws *Never PASS by absence* and *Do not promote inferred
semantic structure into source authority without authorization*.
*Classification: conceptually influenced by the broader ambiguity-surfacing
tradition; no direct ARTEMIS adoption is claimed.*

**Boundary:** ATS implements neither FRET nor ARTEMIS. It retains ordinary
prose and incomplete/uncertain artifacts rather than requiring full
formalization before use.

---

## 17. Vale and programmable prose linting

**Problem:** editorial and technical-writing rules can be expressed as
executable checks rather than informal reviewer taste.

**ATS adoption:** the infrastructure pattern `named rule → detector →
evidence → finding`, extended with stronger authority semantics: ATS
distinguishes *a detector can observe something* from *a detector has
authority to establish conformance*. *Classification: adapted (pattern),
independently convergent (authority model).*

**Boundary:** ATS does not assume every semantic rule can be reliably linted
from lexical patterns; detector authority classes and explicit
unavailable/review states exist because semantic absence does not prove
compliance.

---

## 18. Requirements verification and model-based tooling

**Problem:** tools and research distinguish requirement statement →
formal/structured interpretation → verification obligation.

**ATS adoption:** the principle that *a requirement is incomplete
operationally if nobody can say what evidence would establish it* — informing
acceptance criteria and proof-obligation treatment. *Classification: adapted.*

**Boundary:** ATS does not require every requirement to compile to a formal
verification system.

---

## 19. Semantic-preservation research

**Problem:** research shows that transformations can preserve surface fluency
while altering semantics; text-transformation quality cannot be established
from readability or grammatical quality alone.

**ATS adoption:** ATS therefore explicitly protects `P0` (exact/protected
semantic values), `P1` (protected relations), and `P2` (surface realization),
with the governing transformation rule:

```text
optimize P2
preserve P0
preserve P1
```

*Classification: conceptually influenced; `provenance = UNAVAILABLE` for
specific paper-to-feature mappings unless repository research records them.*

**Boundary:** no single research paper is claimed to prove the complete ATS
model.

---

## 20. The ATS synthesis

| Prior-art family               | Primary contribution to ATS                       |
| ------------------------------ | ------------------------------------------------- |
| ASD-STE100                     | controlled terminology and surface discipline     |
| Engineering style guides       | direct, inspectable technical prose               |
| INCOSE requirements            | atomic/verifiable requirements                    |
| EARS/FRETish                   | explicit trigger/condition/response structure     |
| RFC 2119/8174                  | controlled deontic force                          |
| ISO verbal forms               | permission vs capability vs obligation            |
| ICD 203                        | calibrated likelihood vocabulary                  |
| PHIA/IPCC                      | confidence and uncertainty discipline             |
| Attempto/SBVR                  | machine-recoverable semantic typing               |
| DITA                           | extractable information units                     |
| Diátaxis                       | discourse purpose matters                         |
| IARPA reasoning programs       | evidence/assumption/judgment separation           |
| FRET/FRETish                   | structured semantics and candidate interpretations |
| ARTEMIS                        | distinguishing-trace validation; direct ATS descent not established |
| Vale                           | rules can be executable                           |
| semantic-preservation research | fluent transformation can still alter meaning     |

> ATS does not claim novelty for each mechanism individually. Its design
> contribution is integrating these traditions around AI-native technical
> state transfer, where prose is authored and consumed by reasoning systems
> but must remain reviewable and authorizable by humans.

---

## 21. The problem ATS integrates around

Existing traditions generally optimize one or several of: human readability,
procedural safety, formal interpretability, requirements precision, analytic
calibration, documentation modularity, style consistency.

ATS's target adds another requirement:

> The artifact must survive machine transformation, retrieval,
> decomposition, and continuation without requiring the next reasoning system
> to reconstruct material semantic state from implication.

This produces ATS-specific design priorities: stable semantic coordinates;
local semantic closure; source-basis provenance; protected relational
meaning; semantic-strengthening detection; acceptance-evidence linkage; typed
insufficiency; transformation receipts; planning projection.

---

## 22. Explicit non-claim

ATS-1 is **not** presented as a replacement for every standard in this
lineage:

- use ASD-STE100 when its procedural-language constraints are appropriate;
- use formal requirements tools when formal verification is the target;
- use Diátaxis for general documentation architecture;
- use RFC/ISO semantics within standards work;
- use calibrated analytic conventions where their domain-specific framework
  governs.

ATS is designed for a particular overlap: complex technical reasoning +
implementation-bearing prose + AI authorship/consumption + human review.

---

## 23. Intellectual honesty

Each lineage entry above states whether the inheritance is **directly
adopted, adapted, conceptually influenced, independently convergent, or
rejected**. Where repository research notes do not establish whether an ATS
feature came from a particular source, provenance is recorded as
`UNAVAILABLE` or as related prior art. No historical design provenance is
reconstructed merely because two systems look similar.

---

## 24. Reference quality

Primary sources are preferred for every named external standard/framework.
For publication, each reference should record the official title and the
version consulted, and should distinguish current from historically consulted
versions. This document names the canonical sources; the publication audit
verifies URLs, versions, and licensing/access status before release. No source
text is copied; everything here is paraphrase or short necessary quotation.

---

## 25. Licensing classification of lineage content

For publication and third-party provenance (PUB-03 input), every lineage
source is classified as one of:

| Classification | Applies to ATS content |
| --- | --- |
| concept only | most entries above (idea-level inheritance) |
| paraphrased doctrine | the deontic vocabulary, calibrated probability bands, discourse-role separation |
| terminology | `MUST`/`SHOULD`/`MAY` force vocabulary; probability labels |
| short quotation | the governing principles quoted in this document (each is ATS's own formulation, not copied source text) |
| adapted structure | requirement patterns, profile separation, lint-rule pattern |
| copied text/code | **none — nothing in this repository copies normative or prose text from any lineage source** |

Any future change that would classify content as *copied text/code* or
*adapted proprietary normative language* requires explicit redistribution
review before landing.

---

## 26. Contributor value — why this matters

The lineage is a **design rationale map**. A proposal to "remove repeated
actors because it reads awkwardly" should be seen against the intentional
trade of some surface elegance for local semantic closure, extraction, task
sharding, and reduced reconstruction. A proposal to change probability
terminology should trigger awareness of the calibrated-estimates lineage
rather than being treated as wordsmithing.

---

## 27. Acceptance checklist

- [x] This document exists and is explicitly informative / non-normative
- [x] All materially consulted standards/frameworks are represented
- [x] Each entry states the original problem
- [x] Each entry states what ATS retained
- [x] Each entry states what ATS rejected or changed
- [x] The ATS synthesis is explicit (§20)
- [x] ATS novelty claims are bounded (§20, §22)
- [x] Primary references preferred (§24)
- [x] Third-party/licensing classifications feed PUB-03 (§25)
- [x] No unsupported historical provenance is invented (§23)
- [x] No proprietary normative text is copied (§25)

---

## 28. Public-facing summary (README form)

> ATS-1 draws on controlled technical English, requirements engineering,
> standards deontics, calibrated analytic language, structured requirements,
> and machine-checkable prose.
>
> It combines those traditions around a different target: technical artifacts
> that must survive AI-to-AI handoff and still be inspectable by a human.
>
> See `docs/LINEAGE_AND_PRIOR_ART.md`.

---

## 29. Governing lineage statement

> ATS-1 is not an attempt to replace decades of technical-writing,
> requirements, and analytic-language work. It is an attempt to compose the
> strongest ideas from those traditions around a newer boundary condition:
> the next competent reader may be a reasoning system that must recover
> enough of the operative model to continue the work correctly.

---

## References (primary sources)

Verified against official/canonical sources at publication preparation time.
Current-version status is noted; ATS's design consultation predates some of
these versions, and the historical provenance of individual features is
recorded as `provenance = UNAVAILABLE` where the repository's research notes
do not establish it.

| Standard / framework | Canonical source | Version / status consulted at publication prep |
| --- | --- | --- |
| ASD-STE100 Simplified Technical English | [ASD STEMG](https://www.asd-ste100.org/); [Issue 9](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf) | Issue 9, 2025-01-15 (current); exact historically consulted edition is `UNAVAILABLE` |
| SEC / NASA engineering style guides | [SEC Plain English Handbook](https://www.sec.gov/files/handbook.htm); [NASA STI writing resources](https://sti.nasa.gov/writing-resources-and-style-guides/) | SEC handbook 1998; NASA current resource index |
| INCOSE requirements guidance | [Guide to Writing Requirements v4](https://www.incose.org/docs/default-source/working-groups/requirements-wg/gtwr/incose_rwg_gtwr_v4_040423_final_drafts.pdf); [SE Handbook](https://www.incose.org/resources-publications/technical-publications/se-handbook/) | GtWR v4, 2023-07-01; SE Handbook v5 |
| EARS | Mavin, Wilkinson, Harwood, Novak, ["Easy Approach to Requirements Syntax"](https://doi.org/10.1109/RE.2009.9), IEEE RE'09, pp. 317-322 | 2009 |
| FRET / FRETish | NASA Ames, [FRET repository](https://github.com/NASA-SW-VnV/fret), ["Formal Requirements Elicitation with FRET"](https://ntrs.nasa.gov/citations/20200001989) | Apache-2.0 tool; REFSQ paper 2020 |
| ARTEMIS | Mendoza, Mavridou, Katis, Trippel, ["Automating Requirements Formalization"](https://doi.org/10.1145/3744916.3787815), ICSE '26 | 2026; feature-level ATS descent `UNAVAILABLE` |
| RFC 2119 / RFC 8174 | [BCP 14](https://www.rfc-editor.org/info/bcp14/) | RFC 2119 (1997), RFC 8174 (2017) |
| ISO verbal forms / requirements modality | [ISO/IEC Directives, Part 2](https://www.iso.org/sites/directives/current/part2/index.xhtml) | 9th edition, 2021; Amendment 1, 2026 |
| ICD 203 Analytic Standards | [ODNI ICD 203](https://www.odni.gov/files/documents/ICD/ICD-203.pdf) | signed 2015-01-02; technical amendments 2022-01-21 and 2023-06-12 |
| UK Professional Head of Intelligence Analysis (PHIA) | [Explaining Uncertainty in UK Intelligence Assessment](https://www.gov.uk/government/publications/explaining-uncertainty-in-uk-intelligence-assessment/explaining-uncertainty-in-uk-intelligence-assessment) | 2025-03-24; OGL v3.0 |
| IPCC uncertainty language | [AR6 WGI Chapter 1, Box 1.1](https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-1/); [AR5 uncertainty guidance](https://www.ipcc.ch/publication/ipcc-cross-working-group-meeting-on-consistent-treatment-of-uncertainties/) | AR6 assessment cycle; AR7 underway |
| Attempto Controlled English | [Attempto ACE 6.7](https://attempto.ifi.uzh.ch/site/docs/ace_nutshell.html) | academic project, ACE 6.7 |
| SBVR | [OMG SBVR 1.5](https://www.omg.org/spec/SBVR/1.5/) | formal specification, 2019-12 |
| DITA | [OASIS DITA v1.3](https://www.oasis-open.org/standard/ditav1-3/) | OASIS Standard 2015; Errata 02, 2018 |
| Diátaxis | [diataxis.fr](https://diataxis.fr/) (Daniele Procida) | current; no version scheme |
| IARPA REASON / CREATE / ACE | [REASON](https://www.iarpa.gov/research-programs/reason); [CREATE](https://www.iarpa.gov/research-programs/create); [ACE](https://www.iarpa.gov/index.php/research-programs/ace) | official program records; REASON outcome record remains partial |
| Vale prose linter | [vale.sh](https://vale.sh/); [vale-cli/vale](https://github.com/vale-cli/vale) | MIT; v3.15.2 at verification |
| Semantic-preservation research | [Alva-Manchego, Scarton, Specia survey](https://aclanthology.org/2020.cl-1.4/) and peer-reviewed text-transformation literature | no single paper claimed as the complete ATS model; feature-level provenance `UNAVAILABLE` |

**Licensing posture for this document:** all lineage content is concept-level
or paraphrased doctrine; ATS's own terminology and quoted governing principles
are original formulations. Nothing in this document or the ATS repository
copies normative or prose text from any lineage source (§25).

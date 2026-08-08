# ADR-0006: A detector's term list must come from the lexicon, an enumerated spec list, or the artifact's own glossary

**Status:** Accepted
**Date:** 2026-08-02

## Context

Most ATS-1 surface rules are about words. `ATS-EPI-003` is about noncanonical WEP synonyms.
`ATS-EPI-007` is about "possible," "plausible," "might," and "could." `ATS-TIME-002` is about
relative-time expressions. `ATS-DEON-001` is about deontic keywords. §10.20 is about empty
intensifiers, §10.21 about vague evaluative terms.

The natural way to implement any of them is a Python list of strings. That list is where an
implementation stops being a conformance checker and starts being a house style guide.

Concretely: §10.20 enumerates "clearly," "obviously," "simply," "just," "very," "really," and
"quite." An implementer who adds "actually," "basically," and "essentially" has written a
better style rule and a worse ATS-1 detector — because a finding now cites §10.20 for a term
§10.20 does not name, and no author can predict what the linter will flag by reading the
standard. §12.10 forbids a finding that cannot be explained by returning the normative
statement and why it applies to the span; a finding grounded in an invented term list cannot
satisfy that. §16.8 forbids generating a plausible but unsupported explanation merely because
the detector classified the span.

The same failure has a subtler form: a *reasonable-looking* regex. `\b(may|might|could)\b`
looks like it implements §8.17, but the lexicon is the thing that says which surfaces carry
which force, and §19.3 makes changing a deontic definition a breaking change for artifacts
that use the affected field. A hardcoded regex silently pins a lexicon version.

## Decision

A detector may match text only against a vocabulary drawn from one of exactly three sources:

1. **`lexicons/ats_force_lexicon_v1.yaml`**, read through `ats.rules.registry.ForceLexicon` —
   `wep_terms`, `wep_phrases`, `wep_aliases`, `non_probability_terms`, `confidence_levels`,
   `basis_dimensions`, `evidential_terms`, `causal_terms`, `causal_untyped_candidates`,
   `deontic_surfaces`, `deontic_noncanonical`, `collision_rules`, `interval_for()`,
   `display_range()`.
2. **A list enumerated verbatim in `ATS-1_SPEC.md`**, transcribed with the section number
   recorded — e.g. `EMPTY_INTENSIFIERS` (§10.20), `VAGUE_EVALUATIVE` (§10.21), `VAGUE_TIMING`
   (§9.3.7) in `src/ats/output/render_checks.py`, and the relative-time expressions §10.11
   enumerates.
3. **Declared content in the artifact itself** — the IR's glossary `deprecated_aliases`,
   `canonical_term`, `approved_abbreviations`, and `audience.assumed_glossary_refs`; or an
   enum declared in a normative schema, such as the relation types in
   `ats_common_v1#/$defs/relation` or the slots in `#/$defs/requirement_slots`.

**Every subcheck records its source.** `SubcheckSpec.vocabulary_source` is a required field of
the declaration, emitted into `capability/ats_rule_capability_v1.json` for all 30 rules. The
27 distinct values in the current declaration are auditable in one place; a reviewer can read
them without opening a detector. Examples:

```text
lexicons/ats_force_lexicon_v1.yaml deontic_force.terms[].surface
lexicons/ats_force_lexicon_v1.yaml likelihood.terms[].input_aliases
the relative expressions enumerated verbatim in ATS-1 10.11
the concealing actor forms quoted from ATS-1 9.3.4 and 21.4
the coordination marker in the nonconforming example at ATS-1 9.3.3
the artifact's own glossary `deprecated_aliases`
relation types enumerated in ats_common_v1#/$defs/relation
none
```

`"none"` appears on the seven undecidable rules' subchecks — a detector that matches nothing
declares nothing.

**The shared helpers carry no terms.** `contains_phrase`, `find_phrases`, and `contains_exact`
in `_support.py` handle only word-boundary matching; the module comment states that they
"never carry a term list of their own." `contains_exact` is case-sensitive specifically
because §1.3 makes the deontic keywords normative only in uppercase, so a lowercase `must` in
ordinary prose must not be flagged.

## Consequences

- **Every finding is explainable.** §12.10 is satisfiable because the term that triggered the
  finding traces to a named lexicon key or a quoted spec section, both of which a reader can
  look up.
- **A lexicon version bump moves the detectors.** Adding a WEP term or changing an interval
  changes behaviour without a code edit, which is what §19.3 implies when it makes such changes
  breaking for affected artifacts. `ForceLexicon.version` rides on every report as
  `implementation.lexicon_version`.
- **Coverage gaps become visible instead of being papered over.** `ATS-TERM-003` recognises an
  expansion only in the canonical `Expansion (ACR)` form; rather than inventing patterns for
  the other ways an author might expand an acronym, the detector declares
  `detects_violations` and records the limit. The gap is in the report, not hidden in a regex.
- **Cost: less catches.** A style-guide list would flag more real problems in real documents.
  That is a genuine loss, and it is the correct trade: a linter whose vocabulary nobody can
  audit is a linter whose findings nobody can contest, and §12.4 makes a `critical` finding
  something that changes action, acceptance, or authority.
- **Terms transcribed from the spec can go stale.** `EMPTY_INTENSIFIERS` and its siblings are
  copies. If §10.20 changes in a future draft, they must be re-transcribed — the mitigation is
  that each list names its section and the package is version-pinned (ADR-0001), so a version
  bump is a review point.

## Alternatives considered

**Curate a "quality lexicon" of additional terms, marked non-normative.** Rejected. In a
report the distinction collapses: a reader sees a finding citing `ATS-TERM-001` and a span.
If the project wants additional terms, the correct vehicle is a §19.5 extension rule under a
namespaced identifier, with its own rule record and its own detector — not extra entries
inside an ATS-1 rule.

**Derive term lists by parsing the spec Markdown at load time.** Considered seriously; it
would remove the transcription-staleness cost. Rejected because the enumerations are embedded
in prose sentences with varying punctuation and quoting, so the parser would itself be a
heuristic — trading an auditable copy with a section citation for an unauditable extraction.
The copy is wrong loudly; a parser would be wrong quietly.

**Use an embedding model or WordNet to catch synonyms of the enumerated terms.** Rejected. It
is a learned semantic component, which the milestone lists as a non-goal, and §16.5 would cap
its output at `proposal_only` anyway. It would also make a D0 check nondeterministic, breaking
§16.2.

**Skip `vocabulary_source` and document sources in comments.** Rejected. A comment is not
machine-readable and is not in the published capability declaration, so a consumer of the
declaration could not tell whether a detector's vocabulary is normative. §5.5 and §16.1 make
the capability document the place an implementation states what it actually does.

## References

- ATS-1 §8.2–§8.3 (likelihood vocabulary; canonical output rule), §8.16–§8.17 (deontic
  vocabulary and collisions), §10.5 (acronyms), §10.11 (relative time), §10.20 (empty
  intensifiers), §10.21 (vague evaluative terms), §12.10 (rule explanation), §16.2
  (determinism), §16.8 (explanation fidelity), §19.3 (lexicon versioning), §19.5 (extensions)
- Constitution #2 (evidence has authority; prose has license), #17 (soft shaping, hard
  provenance — a matched term must carry where it came from), #5 (single source of truth)
- `src/ats/rules/registry.py::ForceLexicon`,
  `src/ats/rules/deterministic/_support.py::SubcheckSpec`,
  `src/ats/output/render_checks.py`, `capability/ats_rule_capability_v1.json`

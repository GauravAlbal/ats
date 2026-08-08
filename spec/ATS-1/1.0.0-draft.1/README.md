# ATS-1 specification package

This directory contains the repo-ready normative package for **ATS-1: Arq Text Standard**, version `1.0.0-draft.1`.

## Contents

- `ATS-1_SPEC.md` — 17,000+ word normative specification.
- `rules/ats_rules_v1.yaml` — the 30-rule v0 registry.
- `lexicons/ats_force_lexicon_v1.yaml` — canonical probability, confidence, evidence, causal, and deontic vocabularies.
- `schemas/*.schema.json` — JSON Schema Draft 2020-12 definitions for every normative package object, including policy exceptions and the package manifest.
- `examples/*` — worked TextIR, policy, finding, retention, preservation, receipt, capability, and corpus examples.
- `tools/validate_package.py` — offline structural and cross-object coherence validator.
- `requirements-validation.txt` — reference validator dependencies.
- `MANIFEST.json` — SHA-256 hashes for the package.

## Stable scope

This draft fully specifies `ASSESS`, `SPECIFY`, and cross-cutting `TRANSFORM`. Other profile names are reserved but not core-conformant.

## Validate

From this directory:

```bash
python -m pip install -r requirements-validation.txt
python tools/validate_package.py
```

The validator checks:

- every JSON schema is itself valid;
- the YAML rule registry conforms to its schema and contains exactly 30 unique rules;
- the force lexicon conforms to its schema and has contiguous, non-overlapping canonical WEP intervals;
- all JSON and JSONL examples conform to their schemas and preserve internal references;
- example policy, policy-exception, and receipt hashes match RFC 8785 for the validator's explicitly supported integral JSON subset;
- rule identifiers and normative statements agree between the prose specification and registry;
- detector class and authority declarations agree; and
- `MANIFEST.json` matches the current package bytes.

## Status

Working Draft. Open ratification questions are listed in Appendix E of the specification.

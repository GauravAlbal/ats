# ADR-0001: The imported normative package is immutable and receipted

**Status:** Accepted
**Date:** 2026-08-02

## Context

ATS-1 1.0.0-draft.1 arrives as a distribution archive containing the 3,438-line normative
specification, the 30-rule registry, the calibrated force lexicon, 14 JSON Schemas, worked
examples, and the package's own offline validator. Every conformance claim this repository
ever makes is a claim *against a specific version of that package*.

Two failure modes are available from the first commit. The first is drift: a schema is
tweaked to make a fixture pass, a lexicon interval is nudged, a rule's `default_states` is
softened — and from then on the implementation is conformant to a private fork nobody can
name. The second is unreceipted provenance: the bytes are pristine but nothing records which
archive they came from, whether its hash matched the published one, or whether the package's
own validator ever passed.

§1.2 defines the normative package as a unit. §19.1 requires every downstream artifact to
bind the exact draft version, because draft revisions may make breaking changes. §15.8 makes
a conformance claim stale when the rule registry or the lexicon changes. None of that is
enforceable if the package can be edited in place.

## Decision

`spec/ATS-1/<version>/` is immutable upstream territory and is read only through
`ats.spec_package.SpecPackage`. Nothing in `src/` writes into it.

The import is receipted. `ats.spec_import` extracts the archive verbatim (stripping only the
single top-level directory, refusing any member with an absolute or `..` path), runs the
package's own `tools/validate_package.py` from the package directory with a fixed argv and no
shell, and writes `IMPORT_RECEIPT.json` recording: the source archive filename, its SHA-256,
the expected SHA-256 (`KNOWN_ARCHIVE_SHA256["1.0.0-draft.1"] =
8ccef3df…37c28`) and whether they matched; the manifest SHA-256 and file count; the
per-file manifest verification result including mismatches, missing files, and unlisted
files; the validator's exit code, status, stdout, and interpreter; the import timestamp; and
the exact extraction path.

The receipt is written **beside** the manifest and is deliberately absent from the manifest's
own file list. `SpecPackage.verify()` excludes `IMPORT_RECEIPT.json` by name when computing
unlisted files, so verifying the package against its manifest stays a pure upstream check
with no special-casing of our own artifact.

`extract_archive` refuses to write into a non-empty version directory: *"an imported package
is immutable and MUST be replaced through a documented upstream-version replacement."*
`verify_import` re-checks a previous import — manifest integrity, receipt agreement on the
manifest hash, a recorded validator `PASS`, and a recorded archive-hash match — and returns a
typed problem list.

## Consequences

- A schema, rule, or lexicon change is impossible to make silently. `tests/unit/test_package.py`
  verifies the package byte-for-byte against `MANIFEST.json`, so any edit breaks the build.
- Every report carries `spec_version` and `implementation.rule_registry_version` /
  `lexicon_version` from the package itself, so a reader can tell which package a verdict was
  computed against. `Context.schema_set_sha256` content-addresses the whole schema set on top
  of that.
- An upstream version bump is a visible, receipted operation into a new directory rather than
  an in-place edit. `SpecPackage.available_versions()` and `Context.load(spec_version=...)`
  make running against two versions a parameter, not a branch.
- Defects in the package cannot be "fixed" locally. They are recorded in
  [`../PACKAGE_OBSERVATIONS.md`](../PACKAGE_OBSERVATIONS.md) with the conservative choice the
  implementation made instead. Observation D — the examples' unresolvable source locators —
  is exactly the case that would have been tempting to patch away.
- Cost: the two shipped TextIR examples cannot be fully checked, because their declared source
  files are not in the package and we may not add them. `IR-SOURCE-HASH` reports `UNAVAILABLE`
  for them. That is the correct outcome and it is the price of the rule.

## Alternatives considered

**Vendor the package and allow annotated local patches.** Rejected. A patch file is still a
fork; the moment a patch exists, "conformant to ATS-1 1.0.0-draft.1" becomes false and no
receipt can say what it is actually conformant to.

**Fetch the package at runtime from a registry.** Rejected. It introduces a network dependency
into validation and tests, which the milestone forbids, and makes a run's meaning depend on
when it happened.

**Restate the schemas as Python dataclasses/pydantic models and treat those as authoritative.**
Rejected. That is a second definition of every normative object, and it will drift — see
ADR-0003 and constitution #5. The typed views in `ats.ir.model` are explicitly *views* over a
validated document; their module docstring says so.

**Skip the import receipt and rely on the manifest alone.** Rejected. The manifest proves the
bytes are self-consistent; it does not prove they came from the published archive or that the
package's own validator ever passed. Those are the two facts a downstream reader most needs
and cannot recover later.

## References

- ATS-1 §1.2 (normative package), §19.1 (bind the exact draft version), §15.8 (rule-registry
  and lexicon changes make a claim stale), Appendix C (canonical serialization and hashes)
- Constitution #2 (evidence has authority; prose has license — the receipt is the artifact,
  the claim is a projection over it)
- Constitution #27 (trust receipts, not self-reports — the validator's exit code, not our
  assertion that the package is fine)
- `src/ats/spec_package.py`, `src/ats/spec_import.py`, `tests/unit/test_package.py`

# ADR-0004: RFC 8785 canonicalization is delegated to the `rfc8785` library

**Status:** Accepted
**Date:** 2026-08-02

## Context

Appendix C requires content-addressed ATS-1 objects to omit the object's own hash field,
serialize the remainder with RFC 8785 JCS, hash the canonical bytes with SHA-256, and encode
the digest as lowercase hex. §6.6 makes `snapshot_sha256` the normative content address of a
policy snapshot and states that two snapshots with one `snapshot_id` and different hashes are
distinct policy versions. §16.2 requires deterministic components to produce identical results
for identical canonical inputs.

Everything downstream rides on that canonicalization being *exactly* RFC 8785. A policy hash
that differs by one byte makes `StalePolicyError` fire on a valid snapshot, or — worse —
makes two genuinely different snapshots hash the same if the difference falls in a region the
serializer normalizes away.

The tempting shortcut is `json.dumps(obj, sort_keys=True, separators=(",", ":"),
ensure_ascii=False)`. It is one line, it looks canonical, and it is wrong. RFC 8785 requires:

- object keys sorted by **UTF-16 code unit** sequence, which differs from Python's
  code-point ordering whenever an astral-plane key meets a BMP key above the surrogate range;
- numbers serialized by the **ECMAScript `Number::toString`** algorithm — shortest
  round-tripping representation, `-0` written as `0`, integral floats without a trailing
  `.0`, and a specific exponent spelling;
- rejection of `NaN` and `Infinity`;
- specific string escaping and UTF-8 encoding rules.

Measured against `rfc8785` on this interpreter, `json.dumps` diverges on all three counts:

| Value | `json.dumps` | RFC 8785 |
|---|---|---|
| `1.0` | `1.0` | `1` |
| `-0.0` | `-0.0` | `0` |
| `1e-7` | `1e-07` | `1e-7` |
| `{"\ufffd": 1, "\U00010000": 2}` with `sort_keys=True` | `"\ufffd"` first | `"\U00010000"` first |

The number divergences are invisible until a document contains a float, which for ATS-1 means
any WEP interval bound, any `target_fraction` in a split policy, and any numeric quantifier.

## Decision

Delegate. `ats.canonical.canonical_bytes` calls `rfc8785.dumps(value)` and translates
`rfc8785.CanonicalizationError`, `ValueError`, and `TypeError` into
`UsageError("value is not JCS-serializable: …")`. The module docstring records the reasoning:

> Canonicalization is delegated to `rfc8785` rather than re-implemented here. A hand-rolled
> JCS would duplicate a normative encoding, and RFC 8785's ES6 number formatting is exactly
> the part that silently diverges.

Everything that needs canonical bytes goes through that one function: `sha256_hex` over its
output, `content_hash(obj, exclude=…)`, `seal`, `verify_seal`, `write_json`,
`Context.schema_set_sha256`, `IR-CANONICAL`, and the trace's `canonical_ir_sha256`. There is
no second serialization path.

`content_hash` derives the excluded field from `schema_version` through `SELF_HASH_FIELDS`
when `exclude` is not given, so Appendix C step 1 is applied by table lookup rather than by
each call site remembering which field to drop. `seal` raises `UsageError` when the object's
schema declares no self-hash field, because sealing an object with nowhere to record its
address would silently produce an unaddressed artifact.

## Consequences

- Number formatting is correct by construction, including the cases nobody writes a test for.
- `rfc8785` becomes a load-bearing dependency. It is pure Python, has no transitive
  dependencies, and implements one frozen RFC — a small and stable surface. If it were
  abandoned, the fallback is vendoring it, not rewriting it.
- `canonical_bytes` returns `bytes`, not `str`, which keeps the hash input unambiguous. The
  one place text is wanted, `canonical_text`, decodes explicitly.
- Non-serializable values fail as a typed `UsageError` at the canonicalization boundary rather
  than as a `TypeError` from deep inside the JSON encoder.
- Cost: an extra dependency for something that "looks like one line." That framing is the
  trap; the one line is a different algorithm wearing the same shape.

## Alternatives considered

**`json.dumps(..., sort_keys=True, separators=(",", ":"))`.** Rejected. Wrong key ordering
above the BMP and wrong number formatting for floats. It would work on the current fixtures
and break on a WEP interval bound expressed as `0.55` versus `0.5500000000000001`, or on a
`target_fraction` of `1.0`.

**Hand-roll JCS.** Rejected on two grounds. First, correctness: the ES6 `Number::toString`
shortest-round-trip algorithm is the hard part, and getting it wrong produces hashes that are
stable within this implementation and wrong against everyone else's — the worst possible
failure mode for a content address that is supposed to be interoperable. Second, constitution
#5: a hand-rolled JCS is a second definition of a normative encoding, exactly the drift this
repository refuses elsewhere for schemas and vocabularies.

**Canonicalize only at emission and compare parsed objects internally.** Rejected. Equality of
parsed dicts is not equality of canonical bytes — `1` and `1.0` compare equal in Python and
serialize differently — so a "same object" check would disagree with the hash.

**Use a general canonical-JSON library that supports several profiles.** Rejected. ATS-1 names
RFC 8785 specifically; a configurable library adds a way to be configured wrong.

## References

- ATS-1 Appendix C (canonical serialization and hashes), §6.6 (content-addressed policy),
  §16.2 (determinism), §16.12 (reproducible receipts)
- RFC 8785, JSON Canonicalization Scheme
- Constitution #5 (single source of truth; one canonical encoding, one chokepoint conversion),
  #1 (design so that being wrong produces observable consequences — a divergent hash is
  observable, a divergent-but-self-consistent hash is not)
- `src/ats/canonical.py`

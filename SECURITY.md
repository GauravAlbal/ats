# Security policy

## Scope

This policy covers the public ATS repository, including the executable
implementation, CLI, archive/package handling, schemas and validators, public
skill-pack generation and verification, fixtures, and provenance/receipt
checks.

Please do not put sensitive details in a public issue, pull request, discussion,
or commit. In particular, do not publish credentials, tokens, private corpus
contents, or a working exploit while asking where to report it.

## Private reporting channel

Report vulnerabilities through GitHub's private vulnerability-reporting form:

<https://github.com/GauravAlbal/ats/security/advisories/new>

The repository owner enabled this provider-managed channel for confidential
reports. Do not use a public issue, pull request, discussion, or commit for
vulnerability details. If the form is unavailable to you, a public issue may
request that maintainers provide a secure contact route, but it must contain no
vulnerability details or other sensitive information and is not itself a
vulnerability-reporting route.

Include:

- the affected version, commit, or package edition;
- a concise impact statement and reproducible steps;
- the smallest safe proof of concept (redacted where possible);
- relevant platform, dependency, and configuration details; and
- whether the report is known to be exploited or publicly disclosed.

Please allow maintainers reasonable time to validate, develop a fix, and
coordinate disclosure. No response or remediation time guarantee is made by this
policy.

## What to report

Report privately if you find any of the following, or another defect that could
harm users or defeat an integrity boundary:

- **Secret exposure:** committed or emitted credentials, tokens, private paths,
  private corpus data, or logs that disclose sensitive material.
- **Unsafe file handling:** path traversal, symlink or archive extraction issues,
  unsafe temporary-file behavior, unintended file writes, command injection, or
  processing of attacker-controlled paths/content.
- **Malicious package or skill behavior:** a skill pack, package, generated
  artifact, or verification step that executes unintended code, changes files
  unexpectedly, hides behavior, or smuggles in an undeclared dependency.
- **Validator vulnerabilities:** a crash, denial of service, unsafe parser,
  acceptance bypass, or false pass that could cause a user to trust an invalid
  artifact.
- **Provenance verification bypasses:** a way to defeat hashes, manifests,
  import receipts, package identity checks, receipt verification, or other
  provenance/integrity claims.
- **Other security-sensitive defects:** anything that enables unauthorized code
  execution, data disclosure, integrity loss, or a meaningful bypass of a
  documented safety boundary.

## Do not disclose secrets while reporting

If a secret may have been exposed, revoke or rotate it first when possible and
report only redacted evidence. Do not attach private corpus records or a full
production dump. A maintainer may request a minimal reproduction through the
private vulnerability report.

## Public fixes

Security fixes should preserve the relevant ATS edition and claim boundary. Do
not turn a security fix into an unannounced normative change: if rule meaning,
force semantics, schema semantics, profile semantics, protected meaning, or a
normative example must change, follow the explicit proposal process in
[`CONTRIBUTING.md`](CONTRIBUTING.md). Coordinate release and disclosure details
through the private vulnerability report rather than revealing an exploitable
path in the first public patch description.

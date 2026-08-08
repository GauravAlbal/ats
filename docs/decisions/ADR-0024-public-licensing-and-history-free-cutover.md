# ADR-0024: Split public licensing and history-free cutover

**Status:** Accepted
**Date:** 2026-08-08

## Context

ATS was developed in a private repository whose reachable history contains
local paths, private corpus authority records, and derived pilot evidence that
is not authorized for public distribution. Rewriting that history in place
would weaken the private audit trail and make omission harder to verify.

The repository also needs an explicit licensing boundary. The prior root MIT
notice deliberately did not license `spec/ATS-1/`; package prose still carried
historical "license unspecified" metadata. On 2026-08-08, Gaurav Albal recorded
that he created and owns the ATS material distributed by this project, may act
as its publisher/licensor, and selected the following terms. This resolves the
rightsholder question for the author-created ATS-1 draft.1 and draft.2 material.
It does not grant rights in third-party material.

## Decision

### Licensing

The public repository uses a path-scoped split:

- implementation code, public skills, schemas, tooling, tests, synthetic
  machine-readable fixtures, and generated skill-pack artifacts are licensed
  under Apache License 2.0;
- ATS-1 normative text, protocols, and project documentation are licensed under
  Creative Commons Attribution 4.0 International (CC BY 4.0);
- third-party dependencies and referenced material retain their own terms and
  are not relicensed by ATS.

`LICENSE.md` is the human-readable scope map. Exact license texts live under
`LICENSES/`. `THIRD_PARTY_NOTICES.md` records dependency boundaries and
upstream terms. The authoritative ATS-1 grant is adjacent to the versioned
packages at `spec/ATS-1/LICENSE.md` so the immutable draft.1 package bytes and
closed manifest remain unchanged. That adjacent rightsholder grant supersedes
the packages' historical "unspecified" distribution metadata without rewriting
the sealed package content.

Generated host packs must carry the applicable notices as manifest-bound files.
A missing, stale, or modified notice is a pack-verification failure.

### Disclosure and history

The public Git repository begins from a new, no-parent root commit exported from
a disclosure-sealed private snapshot. The private repository and its history
remain intact; none of its old commits or tags are copied into the public
lineage. Public provenance records bind the public root commit and tree to the
generated skill-pack commit and manifest. The private seal identifier remains
in the private audit record, not in the public tree.

The public export omits:

- every corpus authority record whose policy says `publication: deny`;
- dependent private pilot reports and metadata derived from those inputs;
- private paths, credentials, caches, local environments, and private fleet
  dependencies;
- any empirical claim whose public evidence was removed.

No synthetic record may impersonate an omitted private source. Public evidence
and claims shrink together. Independently redistributable synthetic fixtures
and generic corpus machinery may remain.

Arq, Tribunal, VX, Moat, and Sear may be mentioned only as contextual or future
integrations. The public implementation and skills must remain independently
installable and usable without them.

The historical private `v0.1.0-skill-pack` tag remains immutable and ineligible
for public release. A public `v0.1.1-skill-pack` tag may be created only after a
history-free candidate passes a fresh-clone capstone and hosted CI. Repository
creation, visibility, branch protection, a tested security channel, tagging,
and release publication remain operator actions.

## Consequences

- Public redistribution terms are locally resolvable by path and no longer
  depend on an unstated package default.
- Draft.1 integrity is preserved: its package bytes and import receipt do not
  change merely to add licensing metadata.
- Generated skill packs become independently redistributable and tamper-evident
  with respect to their complete notice set.
- The public repository does not publish the private pilot as if it were public
  evidence. Historical research claims that depended on it are omitted.
- The first public history intentionally does not represent the first day ATS
  existed. Public provenance says so rather than fabricating continuity.
- The public source commit precedes generated artifacts. The pack manifest binds
  to that source commit; a later public provenance receipt may name both without
  introducing a self-referential commit hash.

## Alternatives considered

**Rewrite and publish the private history.** Rejected. It destroys useful audit
provenance, carries unnecessary disclosure risk, and is not required for an
honest public release.

**Keep MIT for code and leave ATS-1 terms unspecified.** Rejected. It does not
implement the rightsholder's selected terms and leaves normative redistribution
ambiguous.

**Apply one license to the entire tree.** Rejected. Software/skill reuse and
normative-document reuse have different audiences; a path-scoped split is more
accurate and avoids relicensing third-party dependencies by proximity.

**Publish denied authority records under redacted names.** Rejected. Renaming
would not create redistribution authority and would falsify provenance.

**Rebuild pilot evidence with fabricated or relabeled inputs.** Rejected. Public
metrics may be smaller or unavailable; they may not be manufactured to preserve
an old gate result.

## References

- `LICENSE.md`, `LICENSES/Apache-2.0.txt`, `LICENSES/CC-BY-4.0.txt`,
  `spec/ATS-1/LICENSE.md`, `THIRD_PARTY_NOTICES.md`
- ADR-0001 (imported package immutable and receipted)
- ADR-0020 (draft.1/draft.2 coexistence)
- ADR-0023 (canonical public skill-pack architecture)
- `docs/PUBLICATION_LICENSING.md`
- `docs/PUBLICATION_DISCLOSURE_AUDIT.md`

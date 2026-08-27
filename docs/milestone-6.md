# Milestone 6: metadata-path hardening

Status: planned; begins after the bounded convergence and custody-transition work below

Predecessor: [`milestone-5.md`](milestone-5.md)

Normative source-adapter contract: [`source-adapters.md`](source-adapters.md)

Current human-policy queue: [`human-review-decisions.md`](human-review-decisions.md)

## Before Milestone 6

Upstream repinning, the compatibility fixes caused by that repinning, aligned Orinoco Lite releases, and the approved repository-custody move are ordinary maintenance prerequisites rather than a separate milestone.
They may proceed now without an exhaustive milestone specification.

The implementing pull requests must:

1. compare every component used by the retained static, service, runtime, editor, query, enrichment, snapshot, or consumer paths with its authoritative upstream head;
2. merge the focused compatibility corrections needed to make those current components pass together;
3. record accepted commits through the existing gitlinks, direct pins, locks, releases, and pull-request summaries;
4. pass the combined recorded static, service, snapshot, release, and consumer checks; and
5. transfer only the repositories and GitHub App in an exact scope approved by John after active pull requests have merged.

This work does not add a tracked upstream inventory or a second acceptance authority.
Exact coordinates and evidence belong in the implementing pull requests, commits, locks, and releases.
The real CON site, its remotes, its deployment, and its production domain remain read-only and outside the transfer.

## Outcome

Milestone 6 begins from the reviewed current stack produced by the prerequisite work above.
It aligns open-reference behavior, makes compatibility tests explicit and dependable, and proves that the two human-facing metadata paths work from current state.

The milestone will:

- preserve well-formed unresolved Things references by default while reporting references and graph edges that cannot be materialized locally;
- remove environment-dependent compatibility tests and unexpected CI skips;
- make the GitHub proposal route discoverable from the SHACL Vue editing experience and exercise one real proposal;
- regenerate and complete a current Zotero proposal rather than repair the obsolete Milestone 5 proposal;
- and publish any follow-up immutable engine, runtime, and template release required by those Milestone 6 changes.

The exact upstream commits and release coordinates belong in the implementing pull requests, gitlinks, locks, and releases.
Milestone 6 does not add a tracked compatibility ledger or a file that attempts to describe mutable upstream head state.

## Accepted planning decisions

### M6-D001 — Use upstream-compatible open references

Canonical Things may contain a well-formed reference to a Thing that is not in the local repository.
Validation preserves that reference and does not contact the network or create a local identity record merely to satisfy closure.

Projection resolves a target when a matching local Thing exists.
The local graph contains only edges whose selected source and target nodes can be materialized.
Missing targets and omitted graph edges are counted in stable diagnostics rather than silently discarded.

Malformed values, schema failures, changed RDF semantics, duplicate PIDs, and features that explicitly require a locally dereferenceable record still fail.
A site may choose stricter local-reference validation as site policy, but strict closure is not the default engine definition of valid upstream-compatible metadata.

This supersedes Milestone 5's field-specific `Identifier.creator` exception and general local-closure default.
It retains the reviewed semantic rule that an identifier venue must not be substituted for its creator.

### M6-D002 — Update upstream deliberately before the milestone

The pre-Milestone 6 upstream update compares authoritative heads when the work begins, tests the candidate commits together, and records the accepted result through ordinary gitlinks, direct dependency pins, generated locks, and the pull-request summary.
No scheduled updater, tracked head inventory, or automatic pin advance is introduced.

Every local compatibility layer affected by the update must either:

- remain with focused parity evidence and a current reason;
- shrink because upstream now supplies part of its behavior; or
- be removed after the upstream implementation passes the same contract.

### M6-D003 — Exercise current Zotero and SHACL flows

Milestone 5 closes on its implemented and focused acceptance evidence.
Its closed Zotero pull request is historical proposal evidence, not a current review entry point.
Milestone 6 creates a fresh proposal from the current default branch and current read-only Zotero coordinate, completes review and finalization, and reruns the identical source to obtain an empty proposal.

Milestone 6 also exercises the first live SHACL Vue GitHub proposal and trusted replacement.
These operational proofs do not reopen the accepted Milestone 5 adapter, provenance, or stateless-service architecture.

### M6-D004 — Move repository custody before the milestone and after active work is merged

Creating the organization, transferring repositories or the GitHub App, and changing application installation or deployment configuration are external operations.
They occur only after the current implementation and documentation pull requests have merged and the exact transfer scope is approved.

The personal demonstration downstream remains under `leej3`.
The real CON site and its remotes remain read-only and outside this transfer unless separately authorized.

The approved scope is the three core repositories, the GitHub App, and the nine mirrors still used by the retained static, service, runtime, editor, query, enrichment, snapshot, or consumer paths: `congo`, `dump-things-pyclient`, `dump-things-service`, `pool.psychoinformatics.de-ui`, `query-things`, `shacl-vue`, `things-enrichment-tools`, `things-schemas`, and `www-from-model`.
Unused historical mirrors, including `dump-things-service-mirror`, remain with their existing owners.
The repository and GitHub App ownership transfers completed on 2026-08-26.
The App installation is limited to `ORINOCO-Lite/test-orinoco-downstream-website`; authenticated discovery and the exact-head SHACL editor passed without creating a review comment, branch, or pull request.
The custody audit also replaced the accidental query-things and things-enrichment-tools merge tips with the already accepted linear heads by exact lease, and fast-forwarded the Things Schemas mirror default ref to its accepted pin.
The Congo mirror retains its upstream `stable` history plus two owned commits; its local Dependabot policy disables independent version-update pull requests, and the nine superseded bot pull requests were closed.
The central backend then advanced from [engineering pull request 50](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/50) at `b992e9788ee66572ca613cfa230cb2ecda40667e` with runtime `v0.2.0rc6`; its [final deployment evidence](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/50#issuecomment-5433725958) records the provider configuration, immutable deployment, authenticated read-only proof, and retained rollback.

## Workstream 1: reference and projection alignment

Replace the special `Identifier.creator` filtering path with the general policy in M6-D001.
Configuration and diagnostics must distinguish:

- a preserved canonical reference whose target is absent locally;
- a graph edge omitted because its target is not a selected local node;
- a relationship context that legitimately has no optional object; and
- malformed or schema-invalid metadata.

Update query and projection parity against the new query-things pin, including nested reference traversal, unresolved scalar preservation, multivalued relationships, route generation, and graph selection.
Site policy may still require particular records for a page, label, role display, or other feature that actually dereferences them.

The default configuration supplied by the next template release must preserve missing references and omit nonmaterialized graph edges with diagnostics.
Existing strict sites receive an explicit, tested migration path and may retain strict site policy.

## Workstream 2: dependable compatibility tests

The normal package test command must not discover a consumer from an arbitrary sibling directory.
Unit tests use repository-owned fixtures.
Full-consumer and upstream compatibility tests receive explicit repository and commit coordinates from their task or workflow.

A required compatibility job must initialize only the fixtures it declares and must fail when one is missing, at the wrong commit, or unexpectedly skipped.
It covers the schema/RDF round trips, upstream enrichment behavior, released editor overlay, schema localization, open-reference projection, and one exact full-consumer projection.

Caching may reduce network transfer, especially for repositories in one organization, but it is never authority.
Cache keys include the runner platform and required commit IDs; every job verifies the checked-out commits and succeeds from an empty cache.

## Workstream 3: SHACL Vue proposal entry

The credential-free downstream editor retains its normal **Download review bundle** behavior.
The separate central wrapper remains the GitHub-authenticated proposal surface and already requests GitHub sign-in when needed.

The site must make that distinction visible before a curator performs edits.
The chosen record action opens the wrapper with the repository and, where applicable, exact pull-request head and selected record.
The wrapper owns the editing session from its beginning; Milestone 6 does not add cross-origin bundle storage or an OAuth recovery store to transfer a completed static-editor session.

Acceptance exercises one public-data edit through sign-in, bundle generation, the temporary handoff, trusted canonical replacement, validation, and a final branch with no handoff bundle.
Automation still does not approve or merge the proposal.

## Workstream 4: current Zotero operation

The obsolete demonstration pull request 7 was closed without merge as superseded rather than rebasing its source- and base-bound proposal.
Acquire current Zotero data read-only, record its exact library/content coordinate, and generate a new proposal from the current demonstration default branch.

Human review may use the existing bulk initializer, but every candidate still receives an explicit disposition before finalization.
The accepted result must validate on both supported platforms.
An identical rerun must create no branch or pull request, and a focused test must continue to prove that a later material source change reopens review.

## Non-goals

Milestone 6 does not:

- modify, transfer, deploy, or graduate the real CON site;
- write to Zotero, the German public pool, or another external metadata source;
- add a persistent metadata, bundle, candidate, decision, or credential store;
- add an automatic upstream updater or tracked compatibility inventory;
- broaden the security model beyond the existing public-data, untrusted pull-request code, and credential boundaries;
- invent metadata to make an open reference local;
- require every repository to disable squash or rebase merges; or
- track whether an unrelated downstream has adopted a release.

Source-adapter pull requests still state and check their merge-commit requirement.
GitHub does not provide a path-conditional repository merge-method setting, so Milestone 6 does not impose a repository-wide restriction merely to protect metadata pull requests.

## Acceptance

Milestone 6 is complete when:

1. `pixi run test` is independent of sibling repositories and required hosted compatibility CI has no unexpected fixture skips;
2. well-formed unresolved references survive validation and projection by default, omitted graph edges are reported, and strict site policy remains available;
3. one current SHACL Vue edit completes the GitHub handoff and trusted replacement path; and
4. one current Zotero proposal is reviewed and finalized, and its identical rerun reports an empty proposal.

Acceptance records representative commands, releases, pull requests, and runs.
It does not duplicate commit ancestry already enforced by Git and the workflow or reproduce every transient artifact coordinate.

## Open questions

### M6-Q001 — Which edit action is primary?

Should a record show two explicit actions—**Edit or download** and **Propose through GitHub**—or should **Edit** open the authenticated GitHub wrapper by default with download retained there?

The recommended default is two clearly named actions.
It preserves the credential-free editor while making the proposal path visible before editing.

### Resolved Pre-M6-Q001 — What moves to the new organization?

Should the new organization receive only the core product repositories, integration-test repository, and GitHub App, or also every actively used upstream mirror currently under `leej3`?
May top-level gitlinks with no retained build, test, release, or preservation role be removed instead of transferred?

The accepted scope is the core product, integration fixture, GitHub App, and actively used mirrors.
Keep the personal demo, CON-owned source and real-site repositories, and unrelated historical mirrors where they are; remove unused gitlinks only in a reviewed parent-repository change.

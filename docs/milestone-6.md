# Milestone 6: upstream convergence and maintenance hardening

Status: planned; two bounded human choices remain open

Predecessor: [`milestone-5.md`](milestone-5.md)

Normative source-adapter contract: [`source-adapters.md`](source-adapters.md)

Current human-policy queue: [`human-review-decisions.md`](human-review-decisions.md)

## Outcome

Milestone 6 brings the engineering stack to a newly reviewed set of current upstream commits, removes avoidable local divergence, makes compatibility tests explicit and dependable, and proves that the two human-facing metadata paths work from current state.

The milestone will:

- advance the upstream components used by supported engineering, release, and compatibility workflows;
- fix regressions caused by those advances and contribute generally useful corrections upstream where practical;
- preserve well-formed unresolved Things references by default while reporting references and graph edges that cannot be materialized locally;
- remove environment-dependent compatibility tests and unexpected CI skips;
- make the GitHub proposal route discoverable from the SHACL Vue editing experience and exercise one real proposal;
- regenerate and complete a current Zotero proposal rather than repair the obsolete Milestone 5 proposal;
- publish aligned immutable engine, runtime, and template releases; and
- prepare a reviewed move of the appropriate repositories and GitHub App into an `orinoco-lite` organization after open pull requests have merged.

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

### M6-D002 — Update upstream deliberately without an inventory

An upstream update compares authoritative heads when the work begins, tests the candidate commits together, and records the accepted result through ordinary gitlinks, direct dependency pins, generated locks, and the pull-request summary.
No scheduled updater, tracked head inventory, or automatic pin advance is introduced.

Every local compatibility layer affected by the update must either:

- remain with focused parity evidence and a current reason;
- shrink because upstream now supplies part of its behavior; or
- be removed after the upstream implementation passes the same contract.

### M6-D003 — Exercise current Zotero and SHACL flows

Milestone 5 closes on its implemented and focused acceptance evidence.
Its old Zotero pull request is historical proposal evidence, not a current review entry point.
Milestone 6 creates a fresh proposal from the current default branch and current read-only Zotero coordinate, completes review and finalization, and reruns the identical source to obtain an empty proposal.

Milestone 6 also exercises the first live SHACL Vue GitHub proposal and trusted replacement.
These operational proofs do not reopen the accepted Milestone 5 adapter, provenance, or stateless-service architecture.

### M6-D004 — Move repository custody after active work is merged

Creating the organization, transferring repositories or the GitHub App, and changing application installation or deployment configuration are external operations.
They occur only after the current implementation and documentation pull requests have merged and the exact transfer scope is approved.

The personal demonstration downstream remains under `leej3`.
The real CON site and its remotes remain read-only and outside this milestone unless separately authorized.

## Workstream 1: upstream update

Start from the authoritative remote for each component used by the recorded static site, full service stack, runtime release, editor release, query parity, or enrichment parity.
Advance candidates in isolated component worktrees, then record parent gitlinks only after the combined stack passes.

The update must cover at least the components actually exercised by those paths, including the website and Congo theme, query-things, Dump Things client and service, Things Schema, enrichment tools, pool UI, and SHACL Vue.
A gitlink that supports no retained build, test, release, or preservation purpose should not be perpetually updated merely because it is present; its removal is part of the open scope question below.

Run the static reproduction, service-backed checks, exact snapshot conversion, ordinary Orinoco composition, editor/runtime assembly, and source-adapter parity tests.
A changed upstream semantic result must be explained and reviewed; it must not be normalized away only to retain an old fixture.

The current 609-line generated-site project-path adapter in [`adapt_upstream_pages.py`](../tools/adapt_upstream_pages.py) remains isolated engineering glue.
It currently repairs root-absolute HTML, graph, manifest, and editor links in generated upstream output and then audits for remaining path escapes.
Prefer upstream Hugo `relURL` or permalink handling, an explicit base-aware graph-data URL, and base-aware graph node routes.
Remove each local rewrite after its released upstream successor passes the same idempotence and browser tests; retain the audit as long as it finds meaningful regressions.

## Workstream 2: reference and projection alignment

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

## Workstream 3: dependable compatibility tests

The normal package test command must not discover a consumer from an arbitrary sibling directory.
Unit tests use repository-owned fixtures.
Full-consumer and upstream compatibility tests receive explicit repository and commit coordinates from their task or workflow.

A required compatibility job must initialize only the fixtures it declares and must fail when one is missing, at the wrong commit, or unexpectedly skipped.
It covers the schema/RDF round trips, upstream enrichment behavior, released editor overlay, schema localization, open-reference projection, and one exact full-consumer projection.

Caching may reduce network transfer, especially for repositories in one organization, but it is never authority.
Cache keys include the runner platform and required commit IDs; every job verifies the checked-out commits and succeeds from an empty cache.

## Workstream 4: SHACL Vue proposal entry

The credential-free downstream editor retains its normal **Download review bundle** behavior.
The separate central wrapper remains the GitHub-authenticated proposal surface and already requests GitHub sign-in when needed.

The site must make that distinction visible before a curator performs edits.
The chosen record action opens the wrapper with the repository and, where applicable, exact pull-request head and selected record.
The wrapper owns the editing session from its beginning; Milestone 6 does not add cross-origin bundle storage or an OAuth recovery store to transfer a completed static-editor session.

Acceptance exercises one public-data edit through sign-in, bundle generation, the temporary handoff, trusted canonical replacement, validation, and a final branch with no handoff bundle.
Automation still does not approve or merge the proposal.

## Workstream 5: current Zotero operation

Close the obsolete demonstration pull request 7 as superseded rather than rebasing its source- and base-bound proposal.
Acquire current Zotero data read-only, record its exact library/content coordinate, and generate a new proposal from the current demonstration default branch.

Human review may use the existing bulk initializer, but every candidate still receives an explicit disposition before finalization.
The accepted result must validate on both supported platforms.
An identical rerun must create no branch or pull request, and a focused test must continue to prove that a later material source change reopens review.

## Workstream 6: release and organization transition

Publish a new engine/runtime release only after the upstream, projection, and compatibility changes pass reproducible release assembly.
Align the template to that immutable release and prove a fresh generated consumer.
This repository records that release proof; it does not maintain ongoing adoption status for independent downstreams.

After active pull requests merge and the scope question is answered, John creates the `orinoco-lite` organization and grants the required ownership.
The reviewed transfer then updates repository remotes, `.gitmodules`, direct package URLs, generated locks, reusable-workflow coordinates, GitHub App ownership and installation, and deployment configuration.
Redirects are migration aids, not the permanent release contract.

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

1. the deliberately selected upstream pins and direct dependencies pass all retained static, service, snapshot, release, query, and enrichment checks;
2. every resulting material upstream difference is fixed, accepted explicitly, or deferred outside the supported paths with a clear issue;
3. `pixi run test` is independent of sibling repositories and required hosted compatibility CI has no unexpected fixture skips;
4. well-formed unresolved references survive validation and projection by default, omitted graph edges are reported, and strict site policy remains available;
5. one current SHACL Vue edit completes the GitHub handoff and trusted replacement path;
6. one current Zotero proposal is reviewed and finalized, and its identical rerun reports an empty proposal;
7. new immutable engine/runtime and template releases pass clean generated-consumer acceptance on macOS ARM64 and Linux x86-64; and
8. the approved organization transfer is complete, or is recorded as a named external follow-up if organization creation is unavailable.

Acceptance records representative commands, releases, pull requests, and runs.
It does not duplicate commit ancestry already enforced by Git and the workflow or reproduce every transient artifact coordinate.

## Open questions

### M6-Q001 — Which edit action is primary?

Should a record show two explicit actions—**Edit or download** and **Propose through GitHub**—or should **Edit** open the authenticated GitHub wrapper by default with download retained there?

The recommended default is two clearly named actions.
It preserves the credential-free editor while making the proposal path visible before editing.

### M6-Q002 — What moves to the new organization?

Should the new organization receive only the core product repositories, integration-test repository, and GitHub App, or also every actively used upstream mirror currently under `leej3`?
May top-level gitlinks with no retained build, test, release, or preservation role be removed instead of transferred?

The recommended scope is the core product, integration fixture, GitHub App, and actively used mirrors.
Keep the personal demo, CON-owned source and real-site repositories, and unrelated historical mirrors where they are; remove unused gitlinks only in a reviewed parent-repository change.

# Milestone 6: metadata-path hardening

Status: active; bounded convergence, aligned releases, and custody transition complete

Predecessor: [`milestone-5.md`](milestone-5.md)

Normative source-adapter contract: [`source-adapters.md`](source-adapters.md)

Current human-policy queue: [`human-review-decisions.md`](human-review-decisions.md)

## Completed prerequisite batch

Upstream repinning, the compatibility fixes caused by that repinning, aligned Orinoco Lite releases, and the approved repository-custody move are ordinary maintenance prerequisites rather than a separate milestone.
That bounded batch is complete.

The implementing pull requests were required to:

1. compare every component used by the retained static, service, runtime, editor, query, enrichment, snapshot, or consumer paths with its authoritative upstream head;
2. merge the focused compatibility corrections needed to make those current components pass together;
3. record accepted commits through the existing gitlinks, direct pins, locks, releases, and pull-request summaries;
4. pass the combined recorded static, service, snapshot, release, and consumer checks; and
5. transfer only the repositories and GitHub App in an exact scope approved by John after active pull requests have merged.

This work does not add a tracked upstream inventory or a second acceptance authority.
Exact coordinates and evidence belong in the implementing pull requests, commits, locks, and releases.
The real CON site, its remotes, its deployment, and its production domain remain read-only and outside the transfer.

## Current mechanical coordinates

| Surface | Current evidence |
| --- | --- |
| Static editor and receiver | [Engineering pull request 52](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/52) merged as `e9ce410f711495070126beb80ec2a89f0225bb9c`. The receiver-only service is at [`https://orinoco-curation-review.pages.dev/`](https://orinoco-curation-review.pages.dev/) with immutable deployment `55ce9125-ea66-4f43-a28b-a0c51734125c` at [`https://55ce9125.orinoco-curation-review.pages.dev/`](https://55ce9125.orinoco-curation-review.pages.dev/). Deployment `9d2909c1-d75b-4de7-ba32-ae37f2d44dc4` remains the retained rollback at [`https://9d2909c1.orinoco-curation-review.pages.dev/`](https://9d2909c1.orinoco-curation-review.pages.dev/). Authenticated browser verification against the final fixture deployment showed both static-editor actions and a receiver waiting for the unchanged bundle, with no duplicate editor. |
| Engine and runtime | [Engineering pull request 53](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/53) merged as `b7201b2e3fefe3e30f9145b597aba9e0c64bccb7`; [`v0.2.0rc8`](https://github.com/ORINOCO-Lite/orinoco-lite-dev/releases/tag/v0.2.0rc8) is the immutable release, and [hosted run 33043289218](https://github.com/ORINOCO-Lite/orinoco-lite-dev/actions/runs/33043289218) passed. |
| Template | [Template pull request 26](https://github.com/ORINOCO-Lite/orinoco-lite-template/pull/26) merged as `88645022f7845ce2c99dd97015ed5538a5defe22`; [`v0.2.0rc12`](https://github.com/ORINOCO-Lite/orinoco-lite-template/releases/tag/v0.2.0rc12) published generated template commit `f855a8ed2442b399f0ae00ff684b16834d779026`, and [hosted run 33044087381](https://github.com/ORINOCO-Lite/orinoco-lite-template/actions/runs/33044087381) passed. |
| Released snapshot adoption | [Engineering pull request 54](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/54) merged as `c21b2cdaa85ed81ced65ed60ce842a87b4cc8ed7`, and [hosted run 33045450687](https://github.com/ORINOCO-Lite/orinoco-lite-dev/actions/runs/33045450687) passed. [Pull request 55](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/55) then merged as `3d539514a9c126a6efb9e6dfae0200569335ebc6`; [hosted run 33047175981](https://github.com/ORINOCO-Lite/orinoco-lite-dev/actions/runs/33047175981) passed after advancing only the exact accepted-consumer coordinate to the final fixture while leaving the adapted upstream gitlinks unchanged. |
| Integration fixture | [Fixture pull request 43](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/pull/43) merged rc12/rc8 as `b405b8853541baa19922dee474870a3b5dab9cd1`. [Validation run 33046225114](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/actions/runs/33046225114) and [Pages run 33046225159](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/actions/runs/33046225159) passed. The publication chain is source `b405b8853541baa19922dee474870a3b5dab9cd1`, projection `3882cd1afea82787a931b66403e71ec8d399e300`, and site `e307bf5a2a5dfff3b5ed681980ceedbf991ea301`; deployment `6117786815` is current. Rollback evidence remains source `4108568df2adc52d619d365e5dc735b30b7730b9`, projection `d265a65dfa7aade20a668f3ded4551585eebefdf`, site `aaf400ec362c9def44f368cc95321ec452ba682e`, and deployment `6117152594`. |
| Personal demonstration | [Demo pull request 25](https://github.com/leej3/orinoco-lite-demo/pull/25) merged rc12/rc8 as `5f53d60d52b815ed2548e8055296d79f11bd4925` while retaining `leej3` custody. [Validation run 33046291553](https://github.com/leej3/orinoco-lite-demo/actions/runs/33046291553) and [Pages run 33046291533](https://github.com/leej3/orinoco-lite-demo/actions/runs/33046291533) passed. The publication chain is source `5f53d60d52b815ed2548e8055296d79f11bd4925`, projection `85da033b60287de69dd722509325844311346aa3`, and site `ab2c4b857159eddfac9e4820164ada35349a8ca6`; deployment `6117800895` is current. Rollback evidence remains source `d1e49f2e940119736d9f3e5f7b007674f7ce017c`, projection `173e258ead8e4578b37a5ce26bd1a804e6df7aba`, site `8a4af9ab88ec5b3a17117e4949105e86a2ae5ba5`, and deployment `6112517513`. |
| Current Zotero input | [Demo pull request 23](https://github.com/leej3/orinoco-lite-demo/pull/23) merged the read-only public-library evidence at version `668` with normalized payload SHA-256 `23aa443a248e9e1dfc73003cde76f3a93c533bf9e57cc5674539b80da52f17b8`. Deterministic planning reports 126 modification candidates; their human dispositions, finalization, and identical no-op rerun remain open. |
| Retired engineering Pages | The unsupported Milestone 3 engineering Pages site was disabled and the repository homepage cleared on 2026-08-27. Its obsolete `codex/milestone-3` deployment policy, retired manual Pages workflow, and orphaned engineering Pages builder were removed from current configuration, while branch `codex/milestone-3`, deployment `5862443246`, and earlier workflow and builder copies remain preserved as historical evidence. Fixture and demo Pages remain the supported live surfaces. |

These coordinates establish the mechanical release boundary but do not complete Milestone 6.
The live SHACL Vue proposal and current Zotero review and no-op proof remain acceptance work below.

## Outcome

Milestone 6 proceeds from the reviewed current stack produced by the completed prerequisite work above.
It aligns open-reference behavior, makes compatibility tests explicit and dependable, and proves that the two human-facing metadata paths work from current state.

The active milestone will:

- preserve well-formed unresolved Things references by default while reporting references and graph edges that cannot be materialized locally;
- remove environment-dependent compatibility tests and unexpected CI skips;
- add **Propose via GitHub** to the downstream static SHACL Vue editing experience and exercise one real proposal;
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
These operational proofs do not reopen the accepted Milestone 5 adapter, provenance, fixed-path handoff, trusted-replacement, or stateless-service boundaries.
M6-D005 separately corrects only the editor-hosting and browser-session portion of the earlier SHACL presentation design.

### M6-D004 — Move repository custody before the milestone and after active work is merged

Creating the organization, transferring repositories or the GitHub App, and changing application installation or deployment configuration are external operations.
They occur only after the current implementation and documentation pull requests have merged and the exact transfer scope is approved.

The personal demonstration downstream remains under `leej3`.
The real CON site and its remotes remain read-only and outside this transfer unless separately authorized.

The approved scope is the three core repositories, the GitHub App, and the nine mirrors still used by the retained static, service, runtime, editor, query, enrichment, snapshot, or consumer paths: `congo`, `dump-things-pyclient`, `dump-things-service`, `pool.psychoinformatics.de-ui`, `query-things`, `shacl-vue`, `things-enrichment-tools`, `things-schemas`, and `www-from-model`.
Unused historical mirrors, including `dump-things-service-mirror`, remain with their existing owners.
The repository and GitHub App ownership transfers completed on 2026-08-26.
The App installation is limited to `ORINOCO-Lite/test-orinoco-downstream-website`; authenticated discovery and the exact-head SHACL editor passed without creating a review comment, branch, or pull request.
That installation scope does not presently include the personal demonstration targeted by the current Zotero operation; Open M6-Q002 records the authority choice that must be made before hosted Zotero review can complete.
The custody audit also replaced the accidental query-things and things-enrichment-tools merge tips with the already accepted linear heads by exact lease, and fast-forwarded the Things Schemas mirror default ref to its accepted pin.
The Congo mirror retains its upstream `stable` history plus two owned commits; its local Dependabot policy disables independent version-update pull requests, and the nine superseded bot pull requests were closed.
The central backend then advanced from [engineering pull request 50](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/50) at `b992e9788ee66572ca613cfa230cb2ecda40667e` with runtime `v0.2.0rc6`; its [final deployment evidence](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/50#issuecomment-5433725958) records that historical provider configuration, immutable deployment, authenticated read-only proof, and retained rollback.
The receiver-only current boundary and deployment supersede that presentation surface and are recorded in the mechanical coordinates above.

### M6-D005 — Keep SHACL Vue in the downstream static site

The downstream static site is the only SHACL Vue editor for that downstream.
Its editing session exposes two explicit actions for the same unchanged version 2 bundle: credential-free **Download bundle** and **Propose via GitHub**.
The latter opens a configurable stateless GitHub service for sign-in, public-data confirmation, and bundle receipt; that service does not assemble, embed, or host another editor.

The live browser handoff validates the configured service origin, the exact static-site origin, both window identities, and a cryptographically random one-time nonce while keeping the bundle out of URLs, OAuth state, cross-origin storage, and durable service state.
If OAuth or browser policy breaks the live window relationship, the curator may download the same bundle and select it on the lightweight receiver page.
The static site never receives a GitHub token, and the receiver applies the same repository, source-commit, exact-head, format, size, authorization, and acknowledgment checks to either transport.

This resolves M6-Q001 in favor of two actions in one static editor rather than two editor destinations.
It supersedes only the central editor-input artifact and the central-wrapper-owned editor assembly and session portions of HR-213 and M5-D014.
It retains the immutable released editor and schema, exact source binding, unchanged bundle, fixed-path temporary Git handoff, trusted Python conversion and replacement, and stateless GitHub App boundary accepted in Milestone 5.

## Workstream 1: reference and projection alignment

Replace the special `Identifier.creator` filtering path with the general policy in M6-D001.
Configuration and diagnostics must distinguish:

- a preserved canonical reference whose target is absent locally;
- a graph edge omitted because its target is not a selected local node;
- a relationship context that legitimately has no optional object; and
- malformed or schema-invalid metadata.

Update query and projection parity against the new query-things pin, including nested reference traversal, unresolved scalar preservation, multivalued relationships, route generation, and graph selection.
Site policy may still require particular records for a page, label, role display, or other feature that actually dereferences them.

The engine and the default configuration supplied by the next template release must preserve missing references and omit nonmaterialized graph edges with diagnostics.
Omitting `graph.missing_external_targets` selects `drop`; existing strict sites retain `graph.missing_external_targets: reject` through an explicit, tested migration path.

## Workstream 2: dependable compatibility tests

The normal package test command must not discover a consumer from an arbitrary sibling directory.
Unit tests use repository-owned fixtures.
Full-consumer and upstream compatibility tests receive explicit repository and commit coordinates from their task or workflow.

A required compatibility job must initialize only the fixtures it declares and must fail when one is missing, at the wrong commit, or unexpectedly skipped.
It covers the schema/RDF round trips, upstream enrichment behavior, released editor overlay, schema localization, open-reference projection, and one exact full-consumer projection.

Caching may reduce network transfer, especially for repositories in one organization, but it is never authority.
Cache keys include the runner platform and required commit IDs; every job verifies the checked-out commits and succeeds from an empty cache.

## Workstream 3: SHACL Vue proposal entry

The downstream static editor retains its normal **Download bundle** behavior and adds an explicit **Propose via GitHub** action for the same editor result.
The site must make both actions visible in the editing session and bind them to the repository and exact source commit represented by the generated editor input.

The proposal action opens the configured central service only for GitHub sign-in, confirmation, and bundle receipt.
The service must not assemble or host SHACL Vue or own another editing session.
A live transfer validates the expected service origin, static-site origin, both windows, and a one-time nonce; selecting a previously downloaded unchanged bundle on the receiver page is the fallback when OAuth or browser policy prevents that transfer.
Neither path adds cross-origin bundle storage or an OAuth recovery store.

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
2. well-formed unresolved references survive validation and projection by default, an omitted graph-target policy drops and reports nonmaterialized edges, and explicit `reject` remains strict;
3. the deployed downstream static editor exposes both actions, the central service exposes no duplicate editor, and one current SHACL Vue edit completes the GitHub handoff and trusted replacement path; and
4. one current Zotero proposal is reviewed and finalized, and its identical rerun reports an empty proposal.

Acceptance records representative commands, releases, pull requests, and runs.
It does not duplicate commit ancestry already enforced by Git and the workflow or reproduce every transient artifact coordinate.

## Open questions

### Open M6-Q002 — Where may the App review the current Zotero proposal?

The current Zotero operation is bound to the personal `leej3/orinoco-lite-demo` downstream, while the transferred GitHub App installation is deliberately limited to the organization fixture.
Hosted review therefore requires one explicit authority decision: install the App on the personal demonstration as well, or revise the reviewed proposal target and its source/base bindings.
Do not install the App, retarget the proposal, or broaden repository authority without John's explicit decision.

## Resolved questions

### Resolved M6-Q001 — Which edit action is primary?

Should a record show two explicit actions—**Edit or download** and **Propose through GitHub**—or should **Edit** open the authenticated GitHub wrapper by default with download retained there?

The accepted result is one downstream static editor with two clearly named actions: **Download bundle** and **Propose via GitHub**.
The central service is only the authenticated receiver and GitHub transport; it does not host an alternative editor.
M6-D005 records the complete boundary.

### Resolved Pre-M6-Q001 — What moves to the new organization?

Should the new organization receive only the core product repositories, integration-test repository, and GitHub App, or also every actively used upstream mirror currently under `leej3`?
May top-level gitlinks with no retained build, test, release, or preservation role be removed instead of transferred?

The accepted scope is the core product, integration fixture, GitHub App, and actively used mirrors.
Keep the personal demo, CON-owned source and real-site repositories, and unrelated historical mirrors where they are; remove unused gitlinks only in a reviewed parent-repository change.

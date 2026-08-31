# Milestone 6: metadata-path hardening

Status: accepted on 2026-08-28; discoverable, live-proven SHACL proposal flow deferred

Predecessor: [`milestone-5.md`](milestone-5.md)

Normative source-adapter contract: [`source-adapters.md`](../contract/source-adapters.md)

Current human-policy queue: [`open-decisions.md`](../open-decisions.md)

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
| Backend-only curation service | [Engineering pull request 62](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/62) merged as `0cba471d72c8df6822b7f13a8a5ff9155c01522b` and moved every editing, review, warning, and confirmation surface downstream. [Pull request 63](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/63) merged as `93c45630ea4cf62b4b4ab6bcad4096f60982e748` and made the retired root fail closed explicitly. That source is deployed at the canonical [`https://orinoco-curation-review.pages.dev/`](https://orinoco-curation-review.pages.dev/) origin as immutable deployment `8d448e3d-97e2-4054-b29d-b9ed88321b8b` at [`https://8d448e3d.orinoco-curation-review.pages.dev/`](https://8d448e3d.orinoco-curation-review.pages.dev/). It contains no static presentation assets; the root and retired presentation routes return `404` or compatibility `410`, while only the backend API and minimal popup transport remain. The earlier receiver deployment `55ce9125-ea66-4f43-a28b-a0c51734125c` remains available as rollback evidence. |
| Engine and runtime | [Engineering pull request 65](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/65) merged the post-rc10 release coordinate as `fad9c2f6f1bc5203739faed5f17dca5d93344403`. Immutable prerelease [`v0.2.0rc11`](https://github.com/ORINOCO-Lite/orinoco-lite-dev/releases/tag/v0.2.0rc11) points to that commit, and [release run 33110460193](https://github.com/ORINOCO-Lite/orinoco-lite-dev/actions/runs/33110460193) passed. This publishes the later source state; it does not replace the independently reviewed downstream engine and runtime locks, which remain on [`v0.2.0rc10`](https://github.com/ORINOCO-Lite/orinoco-lite-dev/releases/tag/v0.2.0rc10) at `0cba471d72c8df6822b7f13a8a5ff9155c01522b`. |
| Template | [Template pull request 28](https://github.com/ORINOCO-Lite/orinoco-lite-template/pull/28) merged as source `02f5667586b5140c9bad0adab147414d210476bb`, and [hosted run 33101551153](https://github.com/ORINOCO-Lite/orinoco-lite-template/actions/runs/33101551153) passed. Immutable prerelease [`v0.2.0rc13`](https://github.com/ORINOCO-Lite/orinoco-lite-template/releases/tag/v0.2.0rc13) published generated template commit `8a047c39859239c885aacc5e92989cf752fb8de0`. Its generated downstream lock selects engine and runtime `v0.2.0rc10` and reusable workflow `0cba471d72c8df6822b7f13a8a5ff9155c01522b`; rc11 remains the separate later engineering source release. |
| Released snapshot adoption | [Engineering pull request 54](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/54) merged as `c21b2cdaa85ed81ced65ed60ce842a87b4cc8ed7`, and [hosted run 33045450687](https://github.com/ORINOCO-Lite/orinoco-lite-dev/actions/runs/33045450687) passed. [Pull request 55](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/55) then merged as `3d539514a9c126a6efb9e6dfae0200569335ebc6`; [hosted run 33047175981](https://github.com/ORINOCO-Lite/orinoco-lite-dev/actions/runs/33047175981) passed after advancing only the exact accepted-consumer coordinate. [Pull request 66](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/66) finally advanced all three independently enforced accepted-consumer coordinates from fixture `7f57c82468b7483bd6926435034a71013cbc9c89` to current source `96a87e38f149badf76d98ee9dc5fe2e4fd3b9c07` and merged as `be797c0da6c6cc13eea6a3c028f444c0808beb7b`. [Pull-request run 33114074038](https://github.com/ORINOCO-Lite/orinoco-lite-dev/actions/runs/33114074038) and [post-merge run 33114421829](https://github.com/ORINOCO-Lite/orinoco-lite-dev/actions/runs/33114421829) passed on macOS and Linux; every adapted upstream gitlink and all other pins remain unchanged. |
| Integration fixture framework | [Fixture pull request 45](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/pull/45) merged the rc13 framework update as `ee81198a92dbfc1fc88dae7043d2dc2d92a48206`, retaining the adapted upstream pins while selecting engine and runtime rc10 and reusable workflow `0cba471d72c8df6822b7f13a8a5ff9155c01522b`. [Pull request 46](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/pull/46) merged the fixture-specific downstream review-link correction as `84c5a351ab69e56751a00224897870c588afbe18`; [validation run 33107025008](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/actions/runs/33107025008) and [Pages run 33107024951](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/actions/runs/33107024951) passed. Documentation [pull request 47](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/pull/47) then merged as `d59844b890e043954b6fb139f9e26eb53b1709e1`. |
| Integration fixture current evidence | [Fixture pull request 48](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/pull/48) merged the current Zotero evidence at version `668` and normalized payload SHA-256 `23aa443a248e9e1dfc73003cde76f3a93c533bf9e57cc5674539b80da52f17b8` as source `96a87e38f149badf76d98ee9dc5fe2e4fd3b9c07`, tree `5cd83a3b6d298824462b9bb6264fd0e39fea1674`. [Pages run 33112748154](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/actions/runs/33112748154) passed. [Validation run 33112748222](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/actions/runs/33112748222) passed on the failed-job retry. The first Linux attempt had already passed every non-browser test and build before one Chromium project-path graph-route check reached its one-off 90-second timeout; the Linux retry and original macOS job passed. The publication chain is source `96a87e38f149badf76d98ee9dc5fe2e4fd3b9c07`, projection `8d0a29a2e7a005579b2a715d6d87b586de49c868`, and site `fc23f9bc871881abed1739956586cc7f99c7bbe0`; deployment `6130395402` is current. The deployed root, `/edit/`, `/review/`, and both generated configurations return successfully and bind the fixture repository to the central backend. Deterministic planning still produces 126 modification candidates. The six retired Zotero identifiers were removed from current canonical records and proposal facts; they were fields within those records, not six candidate records, so all 126 candidate dispositions remain unresolved. |
| Personal demonstration | Demo [framework pull request 28](https://github.com/leej3/orinoco-lite-demo/pull/28) merged the rc13 framework as `40f190a4922ae6b4bfe7c7fda7952883792c2ad0` after [pull request 29](https://github.com/leej3/orinoco-lite-demo/pull/29) added the downstream review-link correction at `9f5c324018a3a782a9f11d011bc09f83706a1ae3`. Later trusted-runtime corrections culminated in [pull request 31](https://github.com/leej3/orinoco-lite-demo/pull/31) at `68cae51cb721468b16c572dec2a07c7827787653`. Current source `bb4f833b5d57b9c3205f8cd15a13689dce301a5b` passed [Pages run 33168061909](https://github.com/leej3/orinoco-lite-demo/actions/runs/33168061909) and [validation run 33168061947](https://github.com/leej3/orinoco-lite-demo/actions/runs/33168061947) on Linux and on the failed-job macOS retry. The first macOS attempt passed all non-browser checks before one Chromium editor test reached its one-off 90-second timeout; attempt 2 passed the complete consumer facade. The current publication chain is source `bb4f833b5d57b9c3205f8cd15a13689dce301a5b`, projection `7b22a55c40ac9f6b20dfa2c540150c68ba596451`, and site `067c7e5526bd5555d4d127d64c2861d5b9c580ed`; deployment `6140515970` is current. |
| Current demonstration Zotero acceptance | [Demo pull request 23](https://github.com/leej3/orinoco-lite-demo/pull/23) merged the read-only public-library evidence at version `668` with normalized payload SHA-256 `23aa443a248e9e1dfc73003cde76f3a93c533bf9e57cc5674539b80da52f17b8`. [Proposal run 33058621923](https://github.com/leej3/orinoco-lite-demo/actions/runs/33058621923) opened [demo pull request 27](https://github.com/leej3/orinoco-lite-demo/pull/27) from exact base `c6ec36cdc2ecc0c7fd1a229975ded4a31f642099` at proposal `3fb2d7b7a61ca218dfe1dd11855820309ad88290` with 126 modification candidates. Compatibility commit `2146a46bd598d152c4e40ac750c4023abf780f84` removed six retired Zotero identifiers from those candidate records without removing candidates. [Finalization run 33166927923](https://github.com/leej3/orinoco-lite-demo/actions/runs/33166927923) applied the complete reviewed decision state as human-attributed commit `0f1a99f0bce5e2e19a270e863aaa1f94d38df5d6`; pull request 27 then merged with merge commit `bb4f833b5d57b9c3205f8cd15a13689dce301a5b`. The identical version-668 [rerun 33179419893](https://github.com/leej3/orinoco-lite-demo/actions/runs/33179419893) reported that the exact active candidate plan was empty and created no branch or pull request. |
| Current SHACL acceptance status | The deployed downstream `/edit/` route keeps the editor on the downstream origin and provides credential-free **Download review bundle**. After a user edits and saves a record, an unlabeled changed-record icon opens a submission drawer containing guarded **Propose via GitHub**. The control is therefore present but not a discoverable primary action. Recorded [run 33058692028](https://github.com/leej3/orinoco-lite-demo/actions/runs/33058692028) and [run 33071388848](https://github.com/leej3/orinoco-lite-demo/actions/runs/33071388848) resolved and validated canonical proposal heads, but neither executed temporary-bundle extraction, attributed canonical commit creation, or exact-head lease replacement. Improving the control's discoverability and completing one live trusted-replacement proof are deferred by M6-D008. The backend-only service retains no presentation surface. |
| GitHub App installation scope | Organization installation `156883473` is limited to `ORINOCO-Lite/test-orinoco-downstream-website`. Personal installation `156987346` is limited to `leej3/orinoco-lite-demo`. Both exact selected-repository scopes were verified on 2026-08-27; neither installation grants the App access to other repositories in its account. |
| Retired engineering Pages | The unsupported Milestone 3 engineering Pages site was disabled and the repository homepage cleared on 2026-08-27. Its obsolete `codex/milestone-3` deployment policy, retired manual Pages workflow, and orphaned engineering Pages builder were removed from current configuration, while branch `codex/milestone-3`, deployment `5862443246`, and earlier workflow and builder copies remain preserved as historical evidence. Fixture and demo Pages remain the supported live surfaces. |
| Remaining capability issues | [Issue 32](https://github.com/ORINOCO-Lite/orinoco-lite-dev/issues/32) remains open because deterministic YAML sharding requires a reviewed storage and migration policy. [Issue 34](https://github.com/ORINOCO-Lite/orinoco-lite-dev/issues/34) and its open [engineering pull request 64](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/64) retain multi-namespace routing for human semantic review. Engineering `main` records the accepted adapted tips plus later custody and compatibility commits. Pull request 64 is based on that accepted pin state and preserves every pin; it does not replace adapted tips with older raw upstream heads. |

These coordinates establish the mechanical release boundary and completed Zotero acceptance path.
Together with the explicit SHACL proposal-flow exception in M6-D008, they complete Milestone 6.

## Outcome

Milestone 6 proceeded from the reviewed current stack produced by the completed prerequisite work above.
It aligns open-reference behavior, makes compatibility tests explicit and dependable, proves the current Zotero path, and records the deployed SHACL boundary plus its deferred direct-GitHub gaps.

The milestone:

- preserved well-formed unresolved Things references by default while reporting references and graph edges that cannot be materialized locally;
- removed environment-dependent compatibility tests and unexpected CI skips;
- added guarded **Propose via GitHub** to the downstream static SHACL Vue editing experience, while deferring its discoverability correction and one live trusted-replacement proof;
- regenerated and completed a current Zotero proposal rather than repairing the obsolete Milestone 5 proposal;
- and published the follow-up immutable engine, runtime, and template releases required by those Milestone 6 changes.

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

Milestone 6 originally required the first live SHACL Vue GitHub proposal and trusted replacement.
M6-D008 accepts the implemented boundary while deferring that operational proof and the discoverability correction to later work.
These operational proofs do not reopen the accepted Milestone 5 adapter, provenance, fixed-path handoff, trusted-replacement, or stateless-service boundaries.
M6-D005 separately corrects only the editor-hosting and browser-session portion of the earlier SHACL presentation design.

### M6-D008 — Close with the SHACL proposal flow deferred

Milestone 6 accepts the deployed downstream editor and backend-only service boundary without claiming that the direct-GitHub SHACL proposal experience is complete.
The guarded **Propose via GitHub** control exists only inside the changed-record submission drawer reached through an unlabeled top-bar icon after an edit is saved.
That placement is not a discoverable primary action, and no current run proves the complete temporary-bundle extraction and trusted-replacement path.

Making the action readily discoverable and recording one live end-to-end proposal and trusted replacement are deferred to a later milestone.
**Download review bundle** remains the accepted credential-free path.
This exception closed Milestone 6 without changing the then-implemented downstream-origin, backend-only-service, repository-scope, or Git-history requirements.

### M6-D009 — Complete the SHACL proposal control without acknowledgment gates

The changed-record header uses a submit icon and opens the existing drawer containing **Download review bundle** and **Propose via GitHub**.
On a shared `github.io` origin, `/edit/` shows the concise origin warning, information text, and custom-domain remediation link without requiring a checkbox.
It also removes the separate public-data bundle acknowledgment.

The GitHub transport opens as a compact popup, tells the curator that it closes automatically, and remains open through authorization and the proposal result.
Repository, source, exact-head, collaborator, fixed-path, and trusted-replacement checks remain unchanged.
This decision completes M6-D008's deferred SHACL user-flow correction.
The current shared-origin policy is warning-only for both `/edit/` and `/review/`.

### M6-D010 — Make the SHACL proposal one click and keep automation messages automated

The **Propose via GitHub** control is the final authorizing click for one proposal.
Its drawer shows the repository and selected records before that click; the authenticated popup submits automatically and does not ask for a second confirmation.

The service opens a new draft without placing explanatory text under the curator's identity.
After verifying the handoff, trusted workflow code posts the concise `github-actions[bot]` status defined by the SHACL profile.
Trusted editor application also preserves the original order of any RDF multivalue whose members are unchanged, so an unrelated scalar edit does not rewrite the rest of a YAML record.
This decision completes M6-D009's submission interaction without changing the source-adapter `/review/` flow.

### M6-D004 — Move repository custody before the milestone and after active work is merged

Creating the organization, transferring repositories or the GitHub App, and changing application installation or deployment configuration are external operations.
They occur only after the current implementation and documentation pull requests have merged and the exact transfer scope is approved.

The personal demonstration downstream remains under `leej3`.
The real CON site and its remotes remain read-only and outside this transfer unless separately authorized.

The approved scope is the three core repositories, the GitHub App, and the nine mirrors still used by the retained static, service, runtime, editor, query, enrichment, snapshot, or consumer paths: `congo`, `dump-things-pyclient`, `dump-things-service`, `pool.psychoinformatics.de-ui`, `query-things`, `shacl-vue`, `things-enrichment-tools`, `things-schemas`, and `www-from-model`.
Unused historical mirrors, including `dump-things-service-mirror`, remain with their existing owners.
The repository and GitHub App ownership transfers completed on 2026-08-26.
The organization installation `156883473` is limited to `ORINOCO-Lite/test-orinoco-downstream-website`; authenticated exact-proposal loading and the exact-head SHACL editor passed without creating a review comment, branch, or pull request.
The separate personal installation `156987346` is limited to `leej3/orinoco-lite-demo`.
Those exact selected-repository scopes were verified on 2026-08-27 and resolve M6-Q002 without granting the App account-wide access.
The custody audit also replaced the accidental query-things and things-enrichment-tools merge tips with the already accepted linear heads by exact lease, and fast-forwarded the Things Schemas mirror default ref to its accepted pin.
The Congo mirror retains its upstream `stable` history plus two owned commits; its local Dependabot policy disables independent version-update pull requests, and the nine superseded bot pull requests were closed.
The central backend then advanced from [engineering pull request 50](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/50) at `b992e9788ee66572ca613cfa230cb2ecda40667e` with runtime `v0.2.0rc6`; its [final deployment evidence](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/50#issuecomment-5433725958) records that historical provider configuration, immutable deployment, authenticated read-only proof, and retained rollback.
The receiver-only current boundary and deployment supersede that presentation surface and are recorded in the mechanical coordinates above.

### M6-D005 — Keep SHACL Vue in the downstream static site

The downstream static site is the only SHACL Vue editor for that downstream.
Its editing session exposes two explicit actions for the same unchanged version 2 bundle: credential-free **Download bundle** and **Propose via GitHub**.
The latter opens a stateless GitHub service popup only for backend sign-in and verified GitHub transport; the downstream owns proposal confirmation and bundle memory or file reselection.
The released central service is the default, with one optional self-host override, and the service does not assemble, embed, or host another editor.

The live browser handoff validates the configured service origin, the exact static-site origin, both window identities, and a cryptographically random one-time nonce while keeping the bundle out of URLs, OAuth state, cross-origin storage, and durable service state.
If OAuth or browser policy breaks the live window relationship, the curator may download the same bundle, select it again on downstream `/edit/`, and begin a fresh popup session.
The static site never receives a GitHub token, and the service applies the same repository, source-commit, exact-head, format, size, and authorization checks to either editor-memory or reselected-file transport.

This resolves M6-Q001 in favor of two actions in one static editor rather than two editor destinations.
It supersedes only the central editor-input artifact and the central-wrapper-owned editor assembly and session portions of HR-213 and M5-D014.
It retains the immutable released editor and schema, exact source binding, unchanged bundle, fixed-path temporary Git handoff, trusted Python conversion and replacement, and stateless GitHub App boundary accepted in Milestone 5.

### M6-D006 — Keep source-adapter review in the downstream static site

The downstream's deployed `/review/` route is the only source-adapter decision interface for that site.
The generated static route contains the released, content-neutral review shell plus a build-derived repository and the effective default or override service origin.
The workflow links directly to that route with the repository, pull-request number, and exact Actions artifact ID.

The central service exposes no second decision-review page.
Its minimal generated popup transport performs GitHub authorization and verified reads, binds a short-lived session grant to the exact operation, repository, pull request, artifact, downstream origin, and one-time nonce, and verifies the downstream coordinates from `orinoco.yaml` at the proposal's metadata base before releasing proposal data.
The transport sends data only after an exact ready/request handshake.
The downstream shows the authenticated reviewer the complete repository, commit, path, and disposition summary and instructs the popup to post only after an explicit confirmation there.

Browser messaging can authenticate an origin but not a path.
A GitHub Pages project site therefore shares its browser trust boundary with other pages on that account's Pages hostname.
Exact build-derived repository binding and one-shot window and nonce checks remain mandatory.
A shared `github.io` deployment also explains the origin-wide boundary.
Both `/review/` and `/edit/` present that explanation as a warning without gating submission.
A custom or otherwise unique origin receives the normal flow.

M6-D007 supersedes M6-D006's originally accepted central confirmation while preserving its proposal, candidate, decision-cache, provenance, artifact, and finalization authority.
It also leaves M6-D005's distinct `/edit/` SHACL Vue route unchanged.

### M6-D007 — Keep presentation downstream and make the service backend-only

The current authentication contract is in [`curation-service-authentication-options.md`](../contract/curation-service-authentication-options.md).

The downstream's deployed `/edit/` and `/review/` routes own every user-facing editing, review, warning, and confirmation surface.
The main browser remains on that downstream origin throughout GitHub authorization and submission.
The central Orinoco Lite service supplies the default stateless GitHub App authorization and verified transport; `site.curation_service` is only an optional override for an independently hosted compatible service.
Repository identity is derived from the trusted downstream build or its general project identity and is verified independently by the service.
It is not another curation-specific setting.

The service has no landing page, editor, review application, upload page, or final-confirmation page and deploys no static presentation assets.
It may return only the minimal generated, restrictive-CSP OAuth callback and popup transport document required to retain host-only session cookies and complete an exact opener, origin, operation, repository, and nonce-bound channel.
Neither a GitHub token nor CSRF material crosses that channel.
Root and retired presentation routes fail closed with `404` or `410`.

Browser messaging authenticates an origin rather than a path.
A downstream on a shared `github.io` origin must therefore explain that another compromised page on the same origin could impersonate the intended `/edit/` or `/review/` path.
Both routes present that explanation as a warning without gating submission.
Neither presentation is treated as an authorization or security proof.
A custom or otherwise unique downstream origin receives the normal low-friction flow.
**Download bundle** remains enabled and credential-free in both cases.

The template and backend-deployment skill guide maintainers through adding and verifying a custom domain while preserving the shared-`github.io` fallback.
The service still revalidates curator access, App installation, repository, pull request, commits, paths, artifact or unchanged bundle, and exact head immediately before a write.
This decision supersedes M6-D005 and M6-D006 only where they required a central receiver, upload fallback, presentation, confirmation, independently configured repository coordinate, or central landing surface.
Their downstream-interface, exact-source, statelessness, GitHub-authority, fixed-path handoff, and trusted-replacement boundaries remain in force.

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

The proposal action opens the configured service only as a backend OAuth and GitHub-transport popup.
The service must not assemble or host SHACL Vue, receive a browser-selected fallback file, own another editing session, or render confirmation UI.
A live transfer validates the expected service origin, static-site origin, both windows, repository, operation, and a one-time nonce.
If OAuth or browser policy prevents that transfer, **Download bundle** preserves the unchanged credential-free result; the user may reselect it on the downstream `/edit/` route before retrying.
Neither path adds cross-origin bundle storage or an OAuth recovery store.

Acceptance exercises one public-data edit through sign-in, bundle generation, the temporary handoff, trusted canonical replacement, validation, and a final branch with no handoff bundle.
Automation still does not approve or merge the proposal.

## Workstream 4: current Zotero operation

The obsolete demonstration pull request 7 was closed without merge as superseded rather than rebasing its source- and base-bound proposal.
Acquire current Zotero data read-only, record its exact library/content coordinate, and generate a new proposal from the current demonstration default branch.

The proposal link must open the demonstration site's deployed `/review/` route as specified by M6-D006.
The central deployment is backend-only authentication and verified GitHub transport and is not a review, confirmation, upload, or landing destination.

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
3. the deployed downstream static editor keeps its main page on the downstream origin, provides credential-free bundle download, and keeps guarded direct-GitHub submission in the editing session while the central service exposes no static presentation surface; the discoverability correction and live trusted-replacement proof are accepted as the explicit M6-D008 deferral;
4. one current Zotero proposal is reviewed and finalized, and its identical rerun reports an empty proposal.

For the direct GitHub paths, the implemented contract retains the normal flow on a custom or otherwise unique origin and an explanation on a shared `github.io` origin.
Neither `/review/` nor `/edit/` gates submission on the shared-origin warning.
Live end-to-end proof of the direct-GitHub SHACL path is part of the M6-D008 deferral.
**Download bundle** remains usable there without GitHub authentication.

Acceptance records representative commands, releases, pull requests, and runs.
It does not duplicate commit ancestry already enforced by Git and the workflow or reproduce every transient artifact coordinate.

### Current acceptance record

1. Accepted: [engineering pull request 42](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/42) removed sibling-worktree discovery and made compatibility inputs hermetic; the current accepted-consumer [post-merge run 33114421829](https://github.com/ORINOCO-Lite/orinoco-lite-dev/actions/runs/33114421829) passed on macOS and Linux without unexpected skips.
2. Accepted: immutable engine/runtime release [`v0.2.0rc8`](https://github.com/ORINOCO-Lite/orinoco-lite-dev/releases/tag/v0.2.0rc8) records the general open-reference default and strict opt-in behavior; [release run 33043289218](https://github.com/ORINOCO-Lite/orinoco-lite-dev/actions/runs/33043289218) passed.
3. Accepted with deferral: the downstream and backend-only presentation boundaries are deployed and tested.
The guarded proposal control exists in the changed-record drawer but is not readily discoverable, and no recorded current run executed the temporary-bundle extraction, human-attributed canonical commit, and exact-head trusted replacement steps.
M6-D008 defers those two gaps without claiming they are complete.
4. Accepted: demo pull request 27 records the completed version-668 review and merge, and identical [rerun 33179419893](https://github.com/leej3/orinoco-lite-demo/actions/runs/33179419893) reported an empty active plan without creating a branch or pull request.

## Resolved questions

### Resolved M6-Q001 — Which edit action is primary?

Should a record show two explicit actions—**Edit or download** and **Propose through GitHub**—or should **Edit** open the authenticated GitHub wrapper by default with download retained there?

The accepted result is one downstream static editor with two clearly named actions: **Download bundle** and **Propose via GitHub**.
The central service is only backend authorization and GitHub transport; it does not host an alternative editor, receiver, upload fallback, or confirmation page.
M6-D005 records the retained editor boundary, and M6-D007 records the superseding browser and service boundary.

### Resolved M6-Q002 — What personal installation scope is accepted?

Limit the personal GitHub App installation to `leej3/orinoco-lite-demo` and accept that repository-only scope for the current Zotero operation.
Keep the separate organization installation limited to `ORINOCO-Lite/test-orinoco-downstream-website`.
Installation IDs `156987346` and `156883473`, respectively, were verified with those exact selected-repository scopes on 2026-08-27.

### Resolved Pre-M6-Q001 — What moves to the new organization?

Should the new organization receive only the core product repositories, integration-test repository, and GitHub App, or also every actively used upstream mirror currently under `leej3`?
May top-level gitlinks with no retained build, test, release, or preservation role be removed instead of transferred?

The accepted scope is the core product, integration fixture, GitHub App, and actively used mirrors.
Keep the personal demo, CON-owned source and real-site repositories, and unrelated historical mirrors where they are; remove unused gitlinks only in a reviewed parent-repository change.

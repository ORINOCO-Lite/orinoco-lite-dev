# Milestone 4 acceptance record

Status: Milestone 4 accepted; production graduation remains separate

The engine and runtime are published, the template has been exercised through subsequent immutable maintenance releases, and the complete accepted Milestone 3 site and test contract are present in the public test consumer.
Replacement pull request 2 was reviewed and merged after correcting the three basic local-use defects found in superseded pull request 1.
Pull request 3 then exercised a normal framework maintenance update, and pull request 4 applied a site-owned presentation change.
Project Pages now serves the reviewed default branch at the public project path.

The Milestone 4 distribution architecture, licensing matrix, and legacy-preview disposition were accepted in the [contemporaneous decision record](https://github.com/ORINOCO-Lite/orinoco-lite-dev/blob/c1f367d7e8f5fa4c5beb8b0a160c563c91a84524/docs/human-review-decisions.md).
This acceptance remains distinct from approval of the content or a future production cutover.
Updates still must not merge automatically.

This record distinguishes immutable release evidence from exploratory runs that failed closed.
A discovery failure is not acceptance evidence.

## Fixed source coordinates

| Source | Commit |
| --- | --- |
| Parent inventory baseline | `0df9ed8c9b32fb72f78d1c6aba101d03e563a1c7` |
| Accepted Milestone 3 site | `26907c487efaa2c31bba9d02398aa201ab6f774b` |
| Reviewed upstream website | `a9ac9d5abc3898fd13d9b8392008f0c323c8dcd8` |
| Accepted parent clean migration | `f54cf5fdb2b5ae4bf03fe6939246316fd9ec818d` |
| Accepted site clean migration | `a122e506de9e4a13473edbe8d74a950d74032a16` |
| Accepted parent Milestone 2 | `7ce44a28c13954e514c8b7e9ab6f1eaade77d891` |
| Accepted site Milestone 2 | `d60f274b4bf8af3e513d83d1727cfe3e6c9bb8af` |
| Milestone 4 engine/runtime source | `1e1001ead15f5a96ef56bc2e18be92070922244f` |
| Milestone 4 template baseline source | `76a11c5a2c3792d8e5a0d6ebe65c7f20c824bb96` |
| Current template maintenance source | `28aecf3c850fbd0e17ba0a6f0bcce721bd25ba88` |
| Reviewed consumer compatibility update | `652c7702d9b62126013f003cc4742969d5400347` |
| Current reviewed consumer default branch | `63ce7761adcfe596ff18b8ae3f2be6e585abc999` |

Git history identifies the commit containing this open-review ledger; the source-coordinate table intentionally avoids a self-reference.

## Engine and runtime release

The immutable [`v0.1.10` release][engine-release] has GitHub release ID `370001522`.
Annotated tag object `3343df643107b165b6036e67189f010f83859386` peels to source commit `1e1001ead15f5a96ef56bc2e18be92070922244f` with source tree `218d8950e6f5504ca3f667dfef9a0b1db1b030bf`.

| Artifact | SHA-256 |
| --- | --- |
| `orinoco_lite-0.1.10-py3-none-any.whl` | `1034ae0de2d160a382eca08f5008de7f90b5aa01a864169358f8f73de7e74705` |
| `orinoco_lite-0.1.10.tar.gz` | `8557f2bc0229e721700e6e70f35b2160fa7c18bc9445272dd3a47667a92b3059` |
| `orinoco-runtime-0.1.10.tar.gz` | `24416557d2791b2c4959c0a2532abbf523669d466721f009cf92d0ce6b7abbcd` |
| archived `runtime-manifest.json` | `592a186e08ea472ca569cd4700aca444ecf82ce6bae286920505484fe83800af` |
| `orinoco-provenance-bundle.jsonl` | `8c1fb617a804e47d29f52bf6266bbd22805f92169f771f52c67bdeeaf60b34ff` |
| `SHA256SUMS` | `f1d2214accd89c6ccf77b7421c6c6c46c71ddc2dfa9efe66150bb32f31a36c00` |

Release workflow [run `31712939175`][engine-run] and job `94490313872` succeeded.
Its provenance attestation binds the checksum subjects to `refs/tags/v0.1.10`, source commit `1e1001ead15f5a96ef56bc2e18be92070922244f`, and that workflow run.
The packaged engine suite passed 44/44 tests.
Two independent runtime assemblies produced the same 754-resource archive, every declared payload and internal checksum verified, and the runtime exposes the seven declared commands.

Engine/runtime `v0.1.8` and `v0.1.9` remain immutable but are superseded discovery evidence.
They established page-to-editor binding, canonical-PID accessibility, and the full hosted compatibility path.
Local use of the `v0.1.9` consumer then exposed the recursion-boundary and build-origin defects addressed in `v0.1.10`.

The reusable workflow and action pin is source commit `1e1001ead15f5a96ef56bc2e18be92070922244f` for the reviewed template update line.

### Recursive schema diagnosis

The pinned stack is LinkML `1.11.1`, LinkML Runtime `1.11.1`, Pydantic `2.13.4`, Dump Things `6.3.6`, and Python `3.12.13`.
The source schema has 82 classes, 98 inheritance edges, no inheritance cycle, and maximum inheritance depth 5.
Its recursion is intentional: the inlined `Thing.relations` range can refer to `Thing` or any of its 48 descendants.

The unmodified LinkML `PydanticGenerator` reproduces the failure at Python's default recursion limit without Dump Things patches.
Generation and Python compilation succeed; executing the generated module fails in Pydantic core schema construction at `Thing.model_rebuild()`.
LinkML represents the recursive range as a repeatedly expanded union rather than a named recursive type.
Dump Things does not cause the defect: it catches the failure and raises the process-wide limit from 1,000 to 2,000.
Orinoco's earlier direct converter construction exposed that behavior.

Engine `v0.1.10` therefore serializes converter construction with a lock, temporarily applies the already-proven limit of 2,000 only while constructing the paired converters, and restores the caller's exact prior limit on success or failure.
A caller limit already above 2,000 is preserved.
Full-schema tests start at 1,000, validate all 199 records and the JSON/RDF round trips, emit no recursion warning, and confirm exact restoration.
This is a scoped integration workaround; the durable upstream correction is for LinkML's Pydantic generator to emit a named recursive alias, which was separately reproduced successfully.

## Template release

Template `v0.1.3` is immutable but superseded evidence.
It proved the safe three-way updater and legacy-consumer bootstrap before the packaged Hugo revision incompatibility was discovered:

- repository: [`con/orinoco-lite-template`][template-repository];
- release ID: `369592522`;
- annotated tag object: `0801afa99d263eccc34278a8af1ca81b57927c9c`;
- source commit: `946733a8b1dc98b6e53c1d14f2b85d3507babc58`;
- generated `github-template` commit: `1b729ca894aa2768a5e615d0d011151731bbf24e`;
- rendered tree: `3e8b64c9b4f2c32b69656b279e0e04d3d3841181`;
- source checks: 23 of 23 passed;
- rendered-template checks: 12 of 12 passed; and
- source CI: Linux passed, while the queued macOS job was cancelled after the release was superseded.

Template `v0.1.4`, `v0.1.5`, and `v0.1.6` are also immutable, superseded discovery evidence.
They established the complete compatibility update path, then exposed hosted dependency ordering, Chromium graph teardown, and macOS 14 Playwright/WebKit protocol behavior addressed in `v0.1.7`.

The superseded `v0.1.6` release has ID `369629347`, source commit `63f62716dcf4065ab8a309e2b0ddb62da2d12d56`, annotated tag object `32b5a0065d45643e94bb1f1e098047b710efe725`, publication commit `633f355900a587a9e65ba3c9ea87c7fdc96217da`, and rendered tree `8505a0866c25ff2005faebb684077883e1ba55ad`.
Its source CI run `31660181699` passed on Linux and macOS, and updater run `31660256727` produced consumer head `a8fdce6e713c220e2f3ad7381bb5286d79cb059a`.
Independent consumer validation subsequently exposed the macOS mismatch, so none of those coordinates is terminal acceptance evidence.

Template `v0.1.7` is immutable but superseded discovery evidence.
It retained the default-branch-only Pages correction and its ownership-safe macOS 14 browser overlay.
Its terminal hosted compatibility evidence was:

| Superseded template `v0.1.7` coordinate | Exact value |
| --- | --- |
| Annotated tag object | `c0c6c8e3f539828027eb6d92ee26eb76dbc9955c` |
| Source commit | `9ae15a1deaf044c6a08c3fe9c8a07724ff0dc467` |
| Source-tree SHA | `89dbdb19b58d16f82da0b0dd30df3c729333f1b1` |
| Generated `github-template` commit | `8a0b11f953009a7f5cb4e5d499320ee3cfa82393` |
| Rendered/publication-tree SHA | `8a8bc1660897c7d2346e463e0704230a078784f9` |
| Source CI | run `31662096753`: Linux and macOS 14 passed |

Template [`v0.1.8`][template-v018-release] is the immutable distribution baseline that introduced the final engine/runtime `v0.1.10` compatibility contract.
It has GitHub release ID `370011385`:

| Baseline template `v0.1.8` coordinate | Exact value |
| --- | --- |
| Annotated tag object | `052dc4335f8848f52c5f663330100d78125b0761` |
| Source commit | `76a11c5a2c3792d8e5a0d6ebe65c7f20c824bb96` |
| Source-tree SHA | `c73b45972c96ad6069d505eaaeb813b12d9ab6ea` |
| Generated `github-template` commit | `3af523ed5c2372e8df1296144b0897a497a0b598` |
| Rendered/publication-tree SHA | `58636171863224c2b832847fe8399f7b82872401` |
| Source CI | [run `31714605299`][template-v018-run]: Linux job `94495988212` and macOS 14 job `94495988130` passed |

The generated publication tree exactly equals the source `github-template` subtree.
Template `v0.1.8` targets engine and runtime `v0.1.10`, retains the Pages and macOS compatibility corrections, and changes local `build` and `build-repeat` to the host-neutral root base `/`.
A template-owned verifier rejects any baked loopback origin, serves the complete output on a random loopback port, and checks the entry point and every same-origin root reference through both `127.0.0.1` and `localhost`.
The Pages workflow still supplies the explicit project-path base and remains default-branch-only.

Local source checks passed 24/24 and rendered-template checks passed 25/25.
A disposable update rehearsal preserved all 1,101 protected paths, passed 68 consumer tests, produced equal 561-file builds, checked 62 same-origin references through each loopback hostname, and passed Chromium 2/2 and WebKit 2/2.
Subsequent immutable template maintenance releases exercised the real updater path.
The current release is [`v0.1.11`][template-release], release ID `370066378`.
Annotated tag object `deacdf9f0edc8c6219ab8541b4bbb185ddf052e4` peels to source commit `28aecf3c850fbd0e17ba0a6f0bcce721bd25ba88`; its `github-template` subtree and the publication branch have the identical tree `d17f6e34011b73be505c18dc8c7fb6fb337234a1`.
Source CI [run `31722216813`][template-run] passed on Linux job `94521713149` and macOS 14 job `94521713044`.

The tag/default-answer/changelog identity inconsistency discovered during this documentation review is an implementation follow-up, not a new architecture decision.
New-site creation should use the next internally aligned release; the existing consumer's reviewed pin remains explicit and auditable.

## Public test consumer

The public [`con/test-orinoco-downstream-website`][consumer-repository] repository uses one ordinary Git worktree.
Its recorded default-branch coordinates are:

| Event | Commit |
| --- | --- |
| Complete accepted-content seed | `a667f8ab24ed50255dcb0bf8dd82ca3360f02271` |
| Hosted Pixi syntax correction | `7067e687afa37d0432f025822d084f6006245c01` |
| Active projection release ledger | `7df4f6add97a756fd2794a2737bc28f932edc444` |
| Reviewed `v0.1.3` updater bootstrap | `a369cdeafe59c23e599ed4c2cb85d7ab5ebed08d` |
| Offline acceptance seam | `6fb267e24efc8a6759b783c23b1f0fa4e3da8194` |
| Final updater and Pages bootstrap | `d437ae085573737155740853134ab37a03476d4e` |
| Reviewed compatibility merge | `3ad859aebaa1653f16b21a6e3555462b369e9de1` |
| Reviewed template-maintenance merge | `db6c19262e93b8ddd8848a82e327cfb1037374e4` |
| Current site-presentation merge | `63ce7761adcfe596ff18b8ae3f2be6e585abc999` |

On replacement pull-request head `652c7702d9b62126013f003cc4742969d5400347`, `orinoco-site-bundle.json` records 1,092 files and 21,745,331 bytes and has SHA-256 `c77fc77a1ae416112d7ccf88c4296cdf7046d722868d248cb9824e3dfb5a12cf`.
It classifies 867 initialized site-owned paths, 205 generated paths, and 20 consumer-test paths.
Every one of its 1,092 path, size, digest, and ownership entries matches the tracked source snapshot.
The active 400-line `generated/projection/SHA256SUMS` has SHA-256 `2c80062a38d4201ef97e1a34333477ef4c280af84ca5259fcf92108c619aff00`.
It covers 210 projection inputs, 187 projection outputs, and two release pins; the reviewed root `.gitattributes` control sidecar is preserved outside the deterministic projection inventory.

Current `main` includes a two-phase offline acceptance seam.
Its preparation phase performs a frozen install, verifies the runtime and all declared assets, builds the complete site, and prepares a backend-free editor review bundle.
Its network-denied phase uses the operating system's network isolation to validate metadata, verify and regenerate the projection, compare two complete builds, exercise the editor bundle, and confirm the tracked snapshot remains unchanged.
The full local consumer suite passed 54/54 tests, including the offline seam; inventory, ownership, and protected-content diff checks also passed.

The earlier automated update run succeeded and stopped at the required human-review boundary, but local use exposed the three defects documented in this record.
Pull request 1 was closed without merge and is superseded discovery evidence.
Replacement pull request 2 contained its reviewed update, the materialized presentation payloads, and the `v0.1.8`/`v0.1.10` update:

| Consumer publication coordinate | Exact value or result |
| --- | --- |
| Superseded update workflow | [run `31662120512`][superseded-update-run]: passed and opened pull request 1 |
| Replacement update pull request | [`con/test-orinoco-downstream-website#2`][consumer-update-pr] |
| Update branch and commit | `automation/orinoco-framework-update` at `652c7702d9b62126013f003cc4742969d5400347` |
| Independent pull-request validation | [run `31715026535`][final-validate-run]: Linux job `94497450004` and macOS 14 job `94497449873` passed |
| Human review and merge commit | John recorded `LGTM!`; merge commit `3ad859aebaa1653f16b21a6e3555462b369e9de1` |
| Template maintenance pull request | [`#3`][consumer-template-pr], validation [run `31722702460`][template-update-validate-run], merge `db6c19262e93b8ddd8848a82e327cfb1037374e4` |
| Site presentation pull request | [`#4`][consumer-presentation-pr], merge `63ce7761adcfe596ff18b8ae3f2be6e585abc999` |
| Default-branch Pages | [run `31725057404`][current-pages-run] passed build and deploy |
| Published project Pages | <https://con.github.io/test-orinoco-downstream-website/> returned the reviewed project-path site |

The replacement pull request was attributed as an AI-generated draft, carried the `dependencies` and `orinoco-update` labels, and had no automatic approval or merge path.
Its finalized update ledger is `ready-for-review`: validation passed, conflicts, migrations, and `site_owned.changed` are all empty, and all 1,101 protected hashes remain equal to the post-materialization baseline.
The ledger has SHA-256 `ecf28964ef1c4214f10813fbcb52803aaa5b7ae68b077f3716980dc0de7db070` and binds template `v0.1.8`, engine/runtime `v0.1.10`, and reusable-workflow source `1e1001ead15f5a96ef56bc2e18be92070922244f`.
Both hosted platforms completed the compatibility pull-request validation successfully before its merge.

The complete local suite on exact head `652c7702d9b62126013f003cc4742969d5400347` passed all 68 Python tests, verified all 71 declared assets, the 186 canonical and 13 reference records, the 199-record/185-page projection, the 186-node/467-edge graph, and all 754 runtime resources.
Two root-relative local builds each contained 561 files and had tree SHA-256 `50d8719ea08627e76c568e54edae5b04c6d6c55fcc6206bd0c5f81ac13b5eeba`.
Every one of the 62 same-origin references resolved through both loopback hostnames, and no `127.0.0.1`, `localhost`, or `::1` origin was baked into the output.
The separate explicit Pages-project-path build passed Chromium 2/2 and WebKit 2/2.

Hosted Linux job `94497450004` independently passed the same 68 tests and semantic, projection, asset, and 754-resource runtime contracts without a `RecursionError` or recursion warning.
Its two root-relative 561-file builds were identical at tree SHA-256 `b19a4fe06ad46ef1aab9db8b264dd9a4ac62d8ba430031a46b7564e9ee62836e`; the dual-host verifier checked 62 references for each hostname, and Chromium 2/2 and WebKit 2/2 passed.

### Ordinary presentation payloads

The flattened presentation framework formerly contained 13 unresolved git-annex pointer blobs, including the main compiled stylesheet.
Exact size-and-MD5 keys were matched to the same paths at pinned hydrated mirror commit `6c8b9a5b7260dc20dfe1453dd863b353e8f90f06`, then committed as ordinary Git bytes.
A downstream build or preview no longer needs DataLad or git-annex.

`generated/manifests/framework-import.json` has SHA-256 `17cc75a3e542ad00531ab47c01d3b41ecf361e02b9a58f2ebe5d3cf66b3904d7`.
It records 72 files and 1,378,923 bytes: 59 byte-identical Git blobs and 13 verified annex-payload materializations.
Each materialized entry binds the accepted source blob and pointer digest, annex key, expected payload size and MD5, ordinary-Git target SHA-256, and hydrated mirror coordinate.
Source and build tests reject pointer-form content and verify that the emitted compiled stylesheet is a real payload.
The full-fidelity manifest has SHA-256 `e5ea9b72ba338158a0158973b198c2c27b48f03af633d0e3006cf648e255a393`; the bound site-import ledger has SHA-256 `3d60139295ccf578f74600b8949c2496f1759a8c0822d6d07bd44251816cf9d9`.

## Full-fidelity parity

The complete content is present; no representative subset was selected.
The consumer bundle and local contract checks on replacement head `652c7702d9b62126013f003cc4742969d5400347` recorded the following parity evidence:

| Contract | Recorded result |
| --- | --- |
| Canonical metadata | 186 records: 33 people, 24 projects including the home record, 126 publications, one instrument, one organization, and one topic |
| Reference closure | 13 records |
| Editorial sources | 10 declared sources and routes |
| Content assets | 71 declarations totaling 57,407,085 bytes: 55 Git payloads and 16 digest-addressed hydrated payloads |
| Presentation framework | 72 ordinary-Git files; 59 source blobs plus 13 verified former-annex payload materializations |
| Provenance | 7 ledgers with extraction coordinates |
| Projection | 199 records and 185 rendered pages |
| Graph | 186 nodes and 467 native edges |
| Static editor | all 186 canonical records with backend-free review-bundle export |
| German isolation | no German route or graph node |
| Downstream topology | no `.gitmodules`, gitlinks, or component checkout |

The local final update hydrated all 16 digest-addressed content assets and verified all 71 declarations, the 186-record canonical set and 13-record reference closure, the 199-record/185-page projection, the 186-node/467-edge graph, all 754 runtime resources, and all 13 ordinary presentation payloads before the replacement review pull request was opened.

## Test traceability

The machine-readable consumer ledger `tests/traceability.json` has SHA-256 `7a6f6c160daa846a04ca082559e2277c024aadf727da33776d23a13fc6a54da6`.
It maps every required source assertion with no unmapped entry:

| Source contract | Mapping result |
| --- | --- |
| Parent Python | 106 methods |
| Playwright | 5 definitions and 9 configured executions |
| Zotero Python | 42 methods: 23 consumer-port successors and 19 engine-retained assertions |
| SHACL Vue editor | 8 definitions |
| Unmapped | 0 |

The terminal `v0.1.8` update reports no update conflicts or migrations and preserves all 1,101 protected site-owned hashes.
Independent Linux and macOS 14 validation is tracked on the exact pull-request head and recorded only after both jobs reach a terminal state.

## Failed-closed discovery runs

These runs explain subsequent fixes.
They did not create an acceptable update and must not be cited as passing acceptance gates.

| Run | Result | Consequence |
| --- | --- | --- |
| [`31650656485`][update-v012-run] | The `v0.1.2` updater produced four rejection files and created no pull request. | Replaced by the three-way updater and legacy bootstrap in template `v0.1.3`. |
| [`31652296155`][pages-v012-run] | Default-branch Pages failed closed on the undeclared `.dumpthings` control input. | Carried into the full-consumer compatibility release. |
| [`31652296538`][validate-v012-run] | Linux validation failed on the same strict input boundary; queued macOS work was cancelled. | Avoided spending runner time after the decisive failure. |
| [`31653114295`][update-v013-run] | Content, assets, projection, graph, runtime, and update transformation passed; strict Hugo verification rejected the packaged revision label and no pull request was created. | Drove compatibility work incorporated in engine/runtime `v0.1.9` and later templates. |
| [`31658793271`][update-v015-run], attempts 1 and 2 | Both attempts failed closed and created no pull request. After hosted dependencies were corrected, Chromium reached the graph test but hung during teardown because of package-install sequencing. | Drove the terminal dependency ordering and browser teardown correction in template `v0.1.6`. |
| [`31660582152`][validate-v016-run] | Linux passed, but macOS 14 exposed a Playwright/WebKit protocol mismatch on the exact `v0.1.6` consumer update. | Superseded that update and drove the ownership-safe macOS 14 browser-compatibility overlay in template `v0.1.7`. |
| Pull request 1 at `8fa32f078f95d736154883cb5deadfe213cbad10` | Hosted Linux and macOS validation passed, but local use exposed a recursive Pydantic model-generation failure, baked `127.0.0.1` origins, and 13 unresolved presentation pointers. | Closed without merge; superseded by engine/runtime `v0.1.10`, template `v0.1.8`, and pull request 2. |

## Repository and Pages settings

The template repository is public, uses generated branch `github-template` as its default, is enabled as a GitHub template, and has immutable releases.
Both `github-template` and source branch `main` disallow force pushes and deletion and require linear history.
Template `main` additionally requires one approving review, approval of the most recent push, dismissal of stale reviews, and resolution of review conversations; administrator enforcement is disabled.
The authorized administrator bypass was used only for the terminal template maintenance pushes after protection was installed.

The consumer repository is public with `main` as its default branch.
Default Actions workflow permissions remain `read`.
GitHub's combined “create and approve pull requests” repository switch is enabled (`can_approve_pull_request_reviews=true`) so `GITHUB_TOKEN` can create the review pull request.
The update job grants only its explicit required write permissions, and the automation contains no approval or merge step.
Consumer `main` requires one approving review, approval of the most recent push, dismissal of stale reviews, resolution of review conversations, and linear history; it disallows force pushes and deletion, with administrator enforcement disabled.

Consumer Pages is configured for workflow deployment at <https://con.github.io/test-orinoco-downstream-website/> with HTTPS enabled.
It has no `CNAME`, custom domain, or production-domain configuration.
The Pages workflow builds and deploys only reviewed default-branch code.
The current reviewed default branch produced the successful Pages deployment recorded above; no pull-request branch deployed.
Labels `dependencies` and `orinoco-update` are available for update review.

## User-level and engineering scenarios

Existing contracts and terminal local rehearsals cover content-neutral template creation, complete site import, protected-content preservation, validation, projection, build, browser behavior, backend-free editor export and application, and deterministic update rollback.

The earlier two-phase offline acceptance passed on superseded pull-request commit `8fa32f078f95d736154883cb5deadfe213cbad10` under the `macos-sandbox` network boundary.
It checked 1,126 tracked files and 71 assets, exercised the full semantic and projection contracts, produced two equal 561-file builds with tree `94bf42410f4c6868403bf270cf32721f5f7ffb7a64c54c13358e1f19cdb8bdba`, dry-ran the editor bundle, and left the tracked snapshot unchanged.

The final two-phase offline acceptance passed on exact replacement head `652c7702d9b62126013f003cc4742969d5400347` under the same `macos-sandbox` network boundary.
It checked 1,128 tracked files and all 71 assets, verified runtime `v0.1.10` and its 754 resources, validated the 186 canonical and 13 reference records, updated and verified the 199-record/185-page projection and 186-node/467-edge graph, and dry-ran the editor bundle.
Its two root-relative 561-file builds had deterministic tree SHA-256 `7ada89fdae086f2fbac1b5337acc4643f341778bdf3434f56e8b752dafdfb137`, and the tracked snapshot remained unchanged.

That final proof supersedes the earlier offline build evidence.
Together with the final local suite, it passed with Python's default recursion limit restored, ordinary framework payloads, host-neutral `/` output through both loopback hostnames, and the separately parameterized Pages project path.

A separate actual user-interface bundle was exported and applied with `orinoco editor apply --write`, after which the projection was updated and verified, metadata was validated, and the site was built twice with identical tree prefix `aa5f9bd5`.
Exact binary rollback passed.
An ordinary framework revert at local commit `ceae6b46` in a disposable clone restored parent tree `2beee32de5a4842955f624023f7054ca981e1a82` exactly.

The terminal fresh-clone scenario, human review boundary, framework-maintenance update, default-branch Pages deployment, and public project-path result have now all been exercised in the test consumer.
They prove the distribution mechanism; they do not substitute for the separate production-graduation decisions.

The engineering workspace continues to retain the accepted upstream review, comparison, package, runtime, and release path.
Those operations remain outside the consumer interface.
Git history supplies the terminal engineering documentation coordinate.
The open boundary is now the comprehensive human decision about engineering merge, governance, licensing, content semantics, and any future production graduation.

Opening the draft engineering pull request triggered legacy Milestone 3 preview run `31663064883` before the Milestone 4 exclusion was present.
That hosted workflow completed a read-only recursive checkout and checkpoint verification of the pinned site repository before it was cancelled.
It made no repository, ref, setting, Pages, or deployment change, and its deploy job did not run.
The Milestone 4 branch now skips that legacy pull-request workflow so a later review synchronization cannot repeat the checkout.

## Real-site no-touch invariant

The final recorded no-touch check for `centerforopenneuroscience.org` is:

- `HEAD`: `734b6997df1b6ff0b3a3fab0db4dc3e7bc34abb7`;
- worktree status: clean; and
- sorted ref-name/object-ID SHA-256: `18c2ead30630aa13c97c3be8ac9a8345b9ba8b94f240f4bd0adcf3007418f0ff`.

No Milestone 4 operation wrote a file, ref, setting, workflow, deployment, Pages source, default branch, DNS record, or custom domain in the real-site repository.
Do not replace the sorted-ref digest above with a digest computed from a differently formatted ref listing.

## Remaining production-graduation review

The test-consumer publication gates and all P0 decisions are complete.
Engineering pull request 5 is accepted for merge, the project license matrix is recorded, and the legacy preview is retained only as frozen evidence with an explicit opt-in engineering-preview path.

The current [`open decisions`](../open-decisions.md) remain required before production graduation.
They do not reopen the accepted single-repository distribution mechanism or authorize a real-site operation.

[engine-release]: https://github.com/con/orinoco-lite-dev/releases/tag/v0.1.10

[engine-run]: https://github.com/con/orinoco-lite-dev/actions/runs/31712939175

[template-repository]: https://github.com/con/orinoco-lite-template

[template-release]: https://github.com/con/orinoco-lite-template/releases/tag/v0.1.11

[template-v018-release]: https://github.com/con/orinoco-lite-template/releases/tag/v0.1.8

[template-v018-run]: https://github.com/con/orinoco-lite-template/actions/runs/31714605299

[template-run]: https://github.com/con/orinoco-lite-template/actions/runs/31722216813

[consumer-repository]: https://github.com/con/test-orinoco-downstream-website

[consumer-update-pr]: https://github.com/con/test-orinoco-downstream-website/pull/2

[consumer-template-pr]: https://github.com/con/test-orinoco-downstream-website/pull/3

[consumer-presentation-pr]: https://github.com/con/test-orinoco-downstream-website/pull/4

[superseded-update-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31662120512

[final-validate-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31715026535

[template-update-validate-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31722702460

[current-pages-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31725057404

[update-v012-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31650656485

[pages-v012-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31652296155

[validate-v012-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31652296538

[update-v013-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31653114295

[update-v015-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31658793271

[validate-v016-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31660582152

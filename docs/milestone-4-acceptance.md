# Milestone 4 acceptance record

Status: not accepted; human merge and default-branch publication are pending

The engine, runtime, and final template are published, and the complete accepted Milestone 3 site and test contract are present in the public test consumer.
The automated update pull request is ready for review.
Acceptance still awaits its human review and merge, successful validation and Pages deployment from the updated default branch, and verification of the published project-path site.
The update must not merge automatically.

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
| Milestone 4 engine/runtime source | `0a0b0891e4e7ae3648d4e9d7d6e7e988194600aa` |
| Milestone 4 template source | `9ae15a1deaf044c6a08c3fe9c8a07724ff0dc467` |
| Consumer update | `8fa32f078f95d736154883cb5deadfe213cbad10` |

Git history identifies the commit containing this pending-acceptance ledger; the source-coordinate table intentionally avoids a self-reference.

## Engine and runtime release

The immutable [`v0.1.9` release][engine-release] has GitHub release ID `369612145`.
Annotated tag object `6485f57c5b5fcf0471acc37e524857c0fe55ae8a` peels to source commit `0a0b0891e4e7ae3648d4e9d7d6e7e988194600aa`.

| Artifact | SHA-256 |
| --- | --- |
| `orinoco_lite-0.1.9-py3-none-any.whl` | `c247cb8f63891724d63e86486941d4958517d96e44f01e72999b84c86b6359de` |
| `orinoco_lite-0.1.9.tar.gz` | `04d50642057ed5200b509ff624a215612d4b5ab44e628d90882e3749723045e2` |
| `orinoco-runtime-0.1.9.tar.gz` | `7850eb9af3205034fcb97c5034ec0a3811df7d174332c7563d011bb0b5bcbba0` |
| archived `runtime-manifest.json` | `afef6b7d5a61131cbdb6db6a136e6f381bdf8eb9caf1a641a35df3ef94da07bc` |
| `orinoco-provenance-bundle.jsonl` | `8058b8f5869b9db417eba3686b6773461efccc24b345448c1e43e4a605dfc65b` |
| `SHA256SUMS` | `2711ae172d1bb59505e4f6ddbc90d9dc6858a8d93ae8f50a43c5452629011bf6` |

Release workflow [run `31656953686`][engine-run] succeeded.
Its provenance attestation binds the checksum subjects to `refs/tags/v0.1.9`, source commit `0a0b0891e4e7ae3648d4e9d7d6e7e988194600aa`, and that workflow run.
The packaged engine suite passed 38/38 tests. The editor-overlay unit suite passed 3/3 tests, and the overlaid JavaScript review-bundle suite passed in both independent editor builds.
Those editor builds were byte-identical.
Two independent runtime assemblies produced the same 753-resource archive, all resources verified against its manifest, and the runtime exposes the seven declared commands.

A disposable full-consumer rehearsal used the frozen installation and passed all four configured browser executions across Chromium and WebKit.
Both the graph and static editor passed in each browser, including selection of a record by an accessibility name containing its canonical PID.

Engine/runtime `v0.1.8` remains immutable but is superseded discovery evidence.
It established page-to-editor link binding; the subsequent full-consumer browser rehearsal exposed the missing canonical-PID accessibility binding that `v0.1.9` adds through a reviewed, fail-closed source overlay.

The reusable workflow and action pin remains source commit `0a0b0891e4e7ae3648d4e9d7d6e7e988194600aa` for the final template update.

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
They established the complete compatibility update path, then exposed hosted dependency ordering, Chromium graph teardown, and macOS 14 Playwright/WebKit protocol behavior addressed by the terminal template release.

The superseded `v0.1.6` release has ID `369629347`, source commit `63f62716dcf4065ab8a309e2b0ddb62da2d12d56`, annotated tag object `32b5a0065d45643e94bb1f1e098047b710efe725`, publication commit `633f355900a587a9e65ba3c9ea87c7fdc96217da`, and rendered tree `8505a0866c25ff2005faebb684077883e1ba55ad`.
Its source CI run `31660181699` passed on Linux and macOS, and updater run `31660256727` produced consumer head `a8fdce6e713c220e2f3ad7381bb5286d79cb059a`.
Independent consumer validation subsequently exposed the macOS mismatch, so none of those coordinates is terminal acceptance evidence.

The final compatibility template is the immutable [`v0.1.7` release][template-release] with GitHub release ID `369639310`:

| Final template `v0.1.7` coordinate | Exact value |
| --- | --- |
| Annotated tag object | `c0c6c8e3f539828027eb6d92ee26eb76dbc9955c` |
| Source commit | `9ae15a1deaf044c6a08c3fe9c8a07724ff0dc467` |
| Source-tree SHA | `89dbdb19b58d16f82da0b0dd30df3c729333f1b1` |
| Generated `github-template` commit | `8a0b11f953009a7f5cb4e5d499320ee3cfa82393` |
| Rendered/publication-tree SHA | `8a8bc1660897c7d2346e463e0704230a078784f9` |
| Source CI | [run `31662096753`][template-run]: Linux and macOS 14 passed |

Template `v0.1.7` targets engine and runtime `v0.1.9`, carries the default-branch-only Pages deployment correction, and adds an ownership-safe macOS 14 browser-compatibility overlay.
Source CI job `94328813822` passed on Linux in 44 seconds, and job `94328813824` passed on macOS 14 in 55 seconds.

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
| Final updater and Pages bootstrap on current `main` | `d437ae085573737155740853134ab37a03476d4e` |

`orinoco-site-bundle.json` records 1,092 files and 20,467,655 bytes and has SHA-256 `767116bc7d7e02219677e5cbda76d7de11a9a15f1a39af665a9d93ca1d6523fe`.
The active 400-line `generated/projection/SHA256SUMS` has SHA-256 `2c80062a38d4201ef97e1a34333477ef4c280af84ca5259fcf92108c619aff00`.
It covers 210 projection inputs, 187 projection outputs, and two release pins; the reviewed root `.gitattributes` control sidecar is preserved outside the deterministic projection inventory.

Current `main` includes a two-phase offline acceptance seam.
Its preparation phase performs a frozen install, verifies the runtime and all declared assets, builds the complete site, and prepares a backend-free editor review bundle.
Its network-denied phase uses the operating system's network isolation to validate metadata, verify and regenerate the projection, compare two complete builds, exercise the editor bundle, and confirm the tracked snapshot remains unchanged.
The full local consumer suite passed 54/54 tests, including the offline seam; inventory, ownership, and protected-content diff checks also passed.

The final automated update succeeded and stopped at the required human-review boundary:

| Final consumer coordinate | Exact value or remaining gate |
| --- | --- |
| Update workflow run | [run `31662120512`][final-update-run]: passed |
| Update pull request | [`con/test-orinoco-downstream-website#1`][consumer-update-pr] |
| Update branch and commit | `automation/orinoco-framework-update` at `8fa32f078f95d736154883cb5deadfe213cbad10` |
| Independent pull-request validation | [run `31662399371`][final-validate-run]: Linux and macOS 14 passed |
| Human review and merge commit | **PENDING** |
| Default-branch validation run | **PENDING** |
| Default-branch Pages run | **PENDING** |
| Published project Pages proof | **PENDING** |

The pull request is attributed as an AI-generated draft, has no automatic approval or merge path, and requires human review.
Its generated update commit changes only 14 framework-owned paths.
The update ledger is `ready-for-review`: validation passed, update conflicts, migrations, and `site_owned.changed` are all empty, and all 1,101 protected site-owned hashes remain equal to the baseline.

Independent validation ran against exact head `8fa32f078f95d736154883cb5deadfe213cbad10`.
Linux job `94329743831` passed in 4 minutes 58 seconds, and macOS 14 job `94329743862` passed in 2 minutes 52 seconds.
Both platforms passed all 64 Python tests, hydrated all 16 digest-addressed assets, verified all 71 asset declarations, verified the 186 canonical and 13 reference records, verified all 753 runtime resources, and produced the same 561-file build tree `94bf42410f4c6868403bf270cf32721f5f7ffb7a64c54c13358e1f19cdb8bdba`.
Each platform passed Chromium 2/2 and WebKit 2/2.
Linux verified Playwright `1.62.1`; the ownership-safe macOS compatibility path replaced only ignored packages, verified Playwright `1.61.1`, and then passed both browser projects.

## Full-fidelity parity

The complete content is present; no representative subset was selected.
The consumer bundle, local contract checks, and final updater run `31662120512` recorded the following parity evidence:

| Contract | Recorded result |
| --- | --- |
| Canonical metadata | 186 records: 33 people, 24 projects including the home record, 126 publications, one instrument, one organization, and one topic |
| Reference closure | 13 records |
| Editorial sources | 10 declared sources and routes |
| Assets | 71 declarations totaling 57,407,085 bytes: 55 Git payloads and 16 digest-addressed annex payloads |
| Provenance | 7 ledgers with extraction coordinates |
| Projection | 199 records and 185 rendered pages |
| Graph | 186 nodes and 467 native edges |
| Static editor | all 186 canonical records with backend-free review-bundle export |
| German isolation | no German route or graph node |
| Downstream topology | no `.gitmodules`, gitlinks, or component checkout |

The final updater hydrated all 16 annex-backed assets and verified all 71 declarations, the 186-record canonical set and 13-record reference closure, the 199-record/185-page projection, the 186-node/467-edge graph, and all 753 runtime resources before creating the review pull request.

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

The terminal `v0.1.7` update reports no update conflicts or migrations and preserves all 1,101 protected site-owned hashes.
Independent Linux and macOS 14 validation passed on the exact pull-request commit.

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
That correction is active in the consumer bootstrap, but neither the pull-request branch nor updated default branch has produced the final Pages deployment.
Labels `dependencies` and `orinoco-update` are available for update review.

## User-level and engineering scenarios

Existing contracts and terminal local rehearsals cover content-neutral template creation, complete site import, protected-content preservation, validation, projection, build, browser behavior, backend-free editor export and application, and deterministic update rollback.

The two-phase offline acceptance passed on exact pull-request commit `8fa32f078f95d736154883cb5deadfe213cbad10` under the `macos-sandbox` network boundary.
It checked 1,126 tracked files and 71 assets, exercised the full semantic and projection contracts, produced two equal 561-file builds with tree `94bf42410f4c6868403bf270cf32721f5f7ffb7a64c54c13358e1f19cdb8bdba`, dry-ran the editor bundle, and left the tracked snapshot unchanged.

A separate actual user-interface bundle was exported and applied with `orinoco editor apply --write`, after which the projection was updated and verified, metadata was validated, and the site was built twice with identical tree prefix `aa5f9bd5`.
Exact binary rollback passed.
An ordinary framework revert at local commit `ceae6b46` in a disposable clone restored parent tree `2beee32de5a4842955f624023f7054ca981e1a82` exactly.

The terminal fresh-clone scenario still needs the pull request's human review and merge and the default-main Pages result.
A local rehearsal cannot substitute for those hosted publication boundaries.

The engineering workspace continues to retain the accepted upstream review, comparison, package, runtime, and release path.
Those operations remain outside the consumer interface.
Git history supplies the terminal engineering documentation coordinate.
Only the human publication boundary and its default-branch hosted evidence remain pending with the acceptance decision.

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

## Remaining acceptance gates

Milestone 4 remains unaccepted until all of the following are recorded:

1. have a human review and merge pull request 1 without changing site-owned content;
2. record successful validation and Pages deployment from updated `main`;
3. verify the published project-path site and editor review-bundle behavior.

[engine-release]: https://github.com/con/orinoco-lite-dev/releases/tag/v0.1.9

[engine-run]: https://github.com/con/orinoco-lite-dev/actions/runs/31656953686

[template-repository]: https://github.com/con/orinoco-lite-template

[template-release]: https://github.com/con/orinoco-lite-template/releases/tag/v0.1.7

[template-run]: https://github.com/con/orinoco-lite-template/actions/runs/31662096753

[consumer-repository]: https://github.com/con/test-orinoco-downstream-website

[consumer-update-pr]: https://github.com/con/test-orinoco-downstream-website/pull/1

[final-update-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31662120512

[final-validate-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31662399371

[update-v012-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31650656485

[pages-v012-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31652296155

[validate-v012-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31652296538

[update-v013-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31653114295

[update-v015-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31658793271

[validate-v016-run]: https://github.com/con/test-orinoco-downstream-website/actions/runs/31660582152

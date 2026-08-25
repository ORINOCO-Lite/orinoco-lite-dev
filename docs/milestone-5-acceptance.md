# Milestone 5 acceptance record

Status: active; implementation released and integrated, real proposal green, authenticated review pending

Original planning parent: `68b0ec1e0d70b9247d94091ae0754550074ae14e`

Plan: [`milestone-5.md`](milestone-5.md)

Normative contract: [`source-adapters.md`](source-adapters.md)

Decision register: [`milestone-5-decisions.md`](milestone-5-decisions.md)

This record receives exact implementation evidence.
The old prototype inventories, transaction reports, sidecars, and custom attestation results are historical exploration and do not satisfy the current contract by themselves.

## Baseline evidence

Record these coordinates when each implementation workstream begins:

| Surface | Required evidence | Status |
| --- | --- | --- |
| Specification | reviewed pull request head and merge commit establishing the normative contract and accepted M5 decisions | engineering pull request [16](https://github.com/con/orinoco-lite-dev/pull/16), head `eeb41ac1d1bf04291e5316cb1e91f457a8aadaa4`, merge `91b1658135e4a21b8d103e43c70db58cbabc58e1` |
| Engineering | exact base, released engine/runtime inputs, upstream pins, clean worktree, and baseline tests | pull requests [16](https://github.com/con/orinoco-lite-dev/pull/16), [17](https://github.com/con/orinoco-lite-dev/pull/17), and [19](https://github.com/con/orinoco-lite-dev/pull/19); release/tag `v0.2.0rc3` at merge `7e331a2c61be2a5701c95c7dc48acf61d2ee106d`; Dump Things `9f101d97c7f15d491f602db5a9c33ad9a19ad8bf`; Things Schema `cb6c791aec4c5309775437df4bd58e94e1bfcc3c`; enrichment-tools `2e6a5ddc92928a6165b81fdae24a52c447967c7d` |
| Zotero | exact library version, adapter revision, policy revision, and baseline behavior | library version `451`; snapshot blob `6d287b0f6d5edbdb36a5308b3605bb86ab3d55a7`; adapter tree `cc45d86b97ee0ad5f7c84ea60fa483e0cd88b733`; policy tree `3606bad690c41a9f120d113ca7d7e21062017ec7` |
| `dump-research-info` | exact source revision, adapter revision, policy revision, and baseline behavior | adapter tree `8598768bae80e3eff55191876d8e20c57a8a5365`; candidate builder blob `5e6eb317b41076eb6a131620534b7a743e456ccf`; adapter blob `4897dfa97128d68bcdf76881993d2c9a7b1a4afa`; external source revision remains an explicit dispatch input |
| Consumer | exact base, lock, template release, corpus counts, branch policy, and baseline CI | implementation pull request [28](https://github.com/con/test-orinoco-downstream-website/pull/28), framework pull requests [30](https://github.com/con/test-orinoco-downstream-website/pull/30) and [31](https://github.com/con/test-orinoco-downstream-website/pull/31), release-adoption pull request [33](https://github.com/con/test-orinoco-downstream-website/pull/33), and fixture-isolation pull request [34](https://github.com/con/test-orinoco-downstream-website/pull/34), head `eb6930ebbf0d73128516bd658786e92107be5f9e`, merge `3f75c7d1395f1d442ba30d15516bd9d8ce8db949`; engine/runtime `v0.2.0rc3`, template `v0.2.0rc4`; `required_linear_history=false` |
| Template | exact source release and generated-template commit if generic support changes | pull requests [12](https://github.com/con/orinoco-lite-template/pull/12), [13](https://github.com/con/orinoco-lite-template/pull/13), and [14](https://github.com/con/orinoco-lite-template/pull/14); latest head `3d59b54f75bafb47fae68c64d679e2c5a9083bb8`, merge/tag `48d14836f0ba26e61ac205e93e80cfe035000585`, immutable `v0.2.0rc4`; generated `github-template` commit `cb3790c83fc1a7a6bdf476c98522130378d61a8d`, tree `c7d545ad9293204b4a37a6479ca6efc36b1a99e9` |
| Platforms | macOS ARM64 and Linux x86-64 clean-clone commands and results | engine pull-request run [32804725258](https://github.com/con/orinoco-lite-dev/actions/runs/32804725258), template run [32793702036](https://github.com/con/orinoco-lite-template/actions/runs/32793702036), and personal-demo adoption run [32806388070](https://github.com/leej3/orinoco-lite-demo/actions/runs/32806388070) passed on macOS 14 ARM64 and Ubuntu 24.04 x86-64 |

Live-source or authoritative-head drift is advisory and must not silently replace a reviewed input.

## Shared metadata foundation

| Requirement | Evidence | Status |
| --- | --- | --- |
| Canonical ordering | Focused parity with pinned Dump Things mapping ordering and YAML serialization, including idempotence and preserved list order | merged in pull request 16; cross-platform release run `32786292302` passed |
| Corpus normalization | Separate reviewed pull request showing the one-time canonicalization-only diff | draft consumer pull request [29](https://github.com/con/test-orinoco-downstream-website/pull/29), current base `f19692f8fa2eee2202b419fe91ed7274eee70c94`, DataLad proposal `0305fe8b19536f81318de10022b9bd77ab58fd21`, merge-preserving head `0bbec9bc2871ddb60dd351e616dda62386ad970b`; current cross-platform run [32794979684](https://github.com/con/test-orinoco-downstream-website/actions/runs/32794979684/attempts/2) passed; current review and merge remain pending |
| Annotation selectors | Exact path/hash matching rejects missing or ambiguous mapping assertions; scalar targets are rejected | merged in pull request 16; release run `32786292302` passed |
| Joined validation | Stored semantic assertion objects plus annotation companions validate as one Thing with the locked schema | object, typed data, and class-range cases merged in pull request 16; release run passed |
| RDF round trip | Expanded PAV survives JSON-to-RDF-to-JSON for imported objects, string data, typed non-string data, and class-range Statements without semantic loss or topical type coercion | merged parity and round-trip tests passed in release run `32786292302` |
| Projection | Stored qualified assertions reach normal semantic projections, joined PAV reaches the machine projection, and actual public rendering behavior is explicit | engine projection tests and complete consumer build passed in runs `32786292302` and `32788660797` |
| Human-facing storage | Record YAML contains no machine-only PAV and the overlay contains no copied record or decision history | merged storage-boundary tests passed in release run `32786292302` |
| Upstream scalar updates | Missing, equal, differing, same-owner, human-owned, and differently owned values match pinned `update_data_property()` after reversible compact-PAV split/join and typed normalization; the missing-topical/equivalent-unowned case copies the topical value without new PAV | merged upstream-parity matrix passed in release run `32786292302` |

Release run `32786292302` at `8bd328b17e359bf9594e83381c3efc1c7ab0ecac` passed 155 engine tests with 11 fixture skips, all 40 engineering-contract tests, and 21 isolated service-stack tests on both supported platforms.
It covers scalar-target rejection; absent, equal, changed, same-owner, human-owned, and differently owned upstream paths; the approved missing-topical convenience copy; multivalue order; compact/expanded PAV; typed values; class-range `Statement` storage; joined RDF; projection fingerprints; and candidate/cache behavior.
At normalization commit `0305fe8b19536f81318de10022b9bd77ab58fd21`, type-sensitive comparison proved all 199 parsed values equal, all outputs canonical and idempotent, and `.dumpthings.yaml` byte-identical.
The exact diff is 199 files, 3,191 insertions, and 3,215 deletions; it removes only five identical legacy source-coordinate comments, whose prior bytes remain in Git history.
`pixi run test-all` passed locally with 129 Python tests, Chromium 2/2, WebKit 2/2, deterministic 561-file build tree `0d85b80f71a1b001316dbb099186170664231d03892bc5fc03ed6adccb764a41`, and no tracked output.
At current merge-preserving head `0bbec9bc2871ddb60dd351e616dda62386ad970b`, hosted run [32794979684](https://github.com/con/test-orinoco-downstream-website/actions/runs/32794979684/attempts/2) passed 134 site-owned Python tests, the deterministic 561-file build with tree `b3dfa91ee1ff60e2a441ab0900eda30b3283e90417ef4af3d59ed39264e796cf`, Chromium 2/2, and WebKit 2/2 on both supported platforms.
The first Linux attempt encountered a transient loose-object copy race; rerunning only the failed job passed without a source change.

## Shared review core

| Requirement | Evidence | Status |
| --- | --- | --- |
| Ephemeral candidates | Deterministic immutable add/modify/delete plans, canonical record/companion bytes, source-claim hashes independent of curated baselines, fixed PIDs/paths, no provenance-only candidates, and adapter-agent checks | merged in pull request 16; focused engine and both-adapter consumer tests passed in runs `32786292302` and `32788660797` |
| Compact decisions | Exact v1 canonical YAML, complete current-candidate decisions, authenticated GitHub review coordinates, accept/reject suppression, defer and material-change reopening, human-correction suppression, source remap, and referenced-review pruning | merged in pull request 16; focused engine and consumer tests passed |
| Git finalization | Exact base/proposal/head verification; add, modify, delete, all-rejected, accepted correction, cache-only accept, clean three-way reversal, overlap failure, hostile Git environment, and path-escape prevention | merged in pull request 16; focused temporary-repository and consumer interaction tests passed on both platforms |

The released shared core is in [`orinoco-lite==0.2.0rc3`](https://github.com/con/orinoco-lite-dev/releases/tag/v0.2.0rc3).
Pull-request run [32804725258](https://github.com/con/orinoco-lite-dev/actions/runs/32804725258) passed 217 tests on each supported platform after finalization switched temporary repository cloning to Git `--no-local`.
Release run [32805667553](https://github.com/con/orinoco-lite-dev/actions/runs/32805667553) published reproducible artifacts and attestations; a credential-free public wheel install reported `orinoco-lite 0.2.0rc3`.

## Adapter behavior matrix

Each row requires focused tests for both adapters and at least one reviewed GitHub execution across the combined evidence.

| Case | Required result | Zotero | `dump-research-info` |
| --- | --- | --- | --- |
| New claim | A friendly record entry and actual metadata diff are presented for explicit review. | focused pass; real 126-record proposal in [personal-demo pull request 7](https://github.com/leej3/orinoco-lite-demo/pull/7) | focused pass; exact real dispatch reached a source-semantic validation blocker before proposal publication |
| Accept | The reviewed proposal remains, the compact cache records acceptance, and an identical rerun is a no-op. | focused pass; live review pending | focused pass; live review pending |
| Reject | The candidate patch is reversed with three-way semantics, non-overlapping human edits survive, the compact cache records rejection, and the unchanged claim stays suppressed. | focused pass; live review pending | focused pass; live review pending |
| Defer | The candidate patch is reversed with three-way semantics, non-overlapping human edits survive, and the claim returns on the next adapter proposal. | focused pass; live review pending | focused pass; live review pending |
| Material source change | A changed metadata-affecting source claim returns for review. | focused pass; live review pending | focused pass; live review pending |
| Unused source change | A source change that cannot affect generated metadata produces no candidate or metadata diff. | focused pass | focused pass |
| Human correction | An accepted human edit is attributed, removes only untouched stale proposal PAV, deletes an emptied companion, and is not reverted by an unchanged source claim; overlap or ambiguous companion state fails. | focused pass; live review pending | focused pass; live review pending |
| Deletion | The record and matching annotation companion are visibly proposed for deletion and accept/reject behave normally. | focused pass; live review pending | focused pass; live review pending |
| All rejected | Final metadata matches the base while the compact decisions and reviewed proposal lineage survive the merge. | focused pass; live review pending | focused pass; live review pending |
| Existing PAV | A semantically identical assertion retains its current PAV and produces no provenance-only diff. | focused pass | focused pass |
| Adapter rerun | Generation cannot overwrite an explicit human disposition or unrelated human metadata. | focused pass; live rerun pending | focused pass; live rerun pending |
| Missing or malformed decision | Finalization stops with a focused diagnostic and does not infer a disposition. | focused pass | focused pass |
| Adapter overlap | Independent claims remain visible, preserve their own identities/PAV, and neither cache suppresses the other. | combined pass | combined pass |

Consumer pull request run `32788660797` used only released interfaces and passed 129 site-owned Python tests, deterministic projection/build checks, and two Chromium plus two WebKit checks on macOS ARM64 and Linux x86-64. It covers both adapters, the trusted host and workflows, idempotence, all-rejected review, material-change reopening, human correction, deletion, exact-head behavior, conflict regeneration, and non-overlapping merges in both Git-allowed orders. Framework integration run [32794385122](https://github.com/con/test-orinoco-downstream-website/actions/runs/32794385122) passed 134 site-owned Python tests, the deterministic 561-file build, Chromium 2/2, and WebKit 2/2 on both supported platforms.
Release-adoption pull request [33](https://github.com/con/test-orinoco-downstream-website/pull/33), head `9c6aeeb622de45a2ca94f827d3daa0e12e4f8629`, merged as `77aa43fe4cb140bd7a92c5218f0dbd94dd686787`; its Linux job passed all 135 site-owned Python tests and browser checks, and the code-equivalent personal-demo run [32806388070](https://github.com/leej3/orinoco-lite-demo/actions/runs/32806388070) passed the same contract on both supported platforms.
[Consumer pull request 34](https://github.com/con/test-orinoco-downstream-website/pull/34), head `eb6930ebbf0d73128516bd658786e92107be5f9e`, isolates adapter tests from assertions already materialized on a proposal head by deriving bounded fixtures that remove only the two adapters' PAV and compact caches.
It merged as `3f75c7d1395f1d442ba30d15516bd9d8ce8db949` after Linux run [32808851917](https://github.com/con/test-orinoco-downstream-website/actions/runs/32808851917) passed 136 Python tests, Chromium 2/2, WebKit 2/2, and deterministic 561-file tree `ae81a3a29a53df7c01b505b401ac787c22a3c760e4871f187bfe2f702bc6843`.
The GitHub-hosted macOS job remained unassigned with older organization jobs; a clean local macOS ARM64 `pixi run test-all` passed the same contract with tree `80f0652ad538f909ce9348eaf77b4a5fb6856e83fbda7920aa545221be0f728c`, and code-equivalent personal-demo run [32808871679](https://github.com/leej3/orinoco-lite-demo/actions/runs/32808871679) passed on GitHub-hosted macOS and Linux.
A real Zotero proposal is now open; authenticated disposition submission and finalization remain pending, and no synthetic proposal was opened.

## Live demonstration evidence

| Surface | Immutable coordinates | Result |
| --- | --- | --- |
| Personal downstream | public repository [`leej3/orinoco-lite-demo`](https://github.com/leej3/orinoco-lite-demo), fixture-isolation pull request [6](https://github.com/leej3/orinoco-lite-demo/pull/6), head `1eb6949de3c83bfa496f592c3fbbe4947f11c957`, merge `68738ed8df375fe14d87da216c6d8a7ee6d7e82c` | Run [32808871679](https://github.com/leej3/orinoco-lite-demo/actions/runs/32808871679) passed 136 Python tests, Chromium 2/2, WebKit 2/2, and deterministic 565-file tree `9f654940741afb00c30acb7c91c2b197fde837417765e21187f0d7cc07460d2a` on both supported platforms; artifact `9549239993` has digest `sha256:668a53760c9b12d1827d5b4b67401f1a6ce5304ab48fb624001d9da8725eb329`, and SHACL run [32808870008](https://github.com/leej3/orinoco-lite-demo/actions/runs/32808870008) passed. The fixture derivation preserves topical fields and unrelated provenance, and [the public site](https://leej3.github.io/orinoco-lite-demo/) remains live. |
| Zotero proposal | workflow run [32809444741](https://github.com/leej3/orinoco-lite-demo/actions/runs/32809444741), draft pull request [7](https://github.com/leej3/orinoco-lite-demo/pull/7), base `68738ed8df375fe14d87da216c6d8a7ee6d7e82c`, DataLad proposal `f087cd3884a5b54885553d0d5e89b57c21d564b3`, tree `33bb4e5bd49806ed305b94a7f0238ecb9664d4cb` | Exact source coordinate is `{"content_sha256":"sha256:5e0f5fe1d68c18214110a37c24a8e9177dc484f64a1d9d832f322b477bfef20d","group_id":6197458,"kind":"zotero-public-library","library_version":451}`. The one-parent proposal has 126 unblocked modifications and an actual 252-file metadata diff: 126 publication records plus 126 PAV-only companions, 3,624 additions, and no deletions. |
| Decision-review artifact | [artifact 9549289607](https://github.com/leej3/orinoco-lite-demo/actions/runs/32809444741/artifacts/9549289607), `orinoco-curation-review-f087cd3884a5b54885553d0d5e89b57c21d564b3`, 16,253 bytes, ZIP digest `sha256:e023c25915041c06d1a4791ebec3c62ac7fa8d0195050cbed521065979258dc9`, extracted JSON SHA-256 `e7adac240a1e259ba4c94b15be7a9686dc98f1dc51287d8b14098ebc7a22e88f`, expiry `2026-11-23T04:33:52Z` | The concise pull-request body links the [central review application](https://orinoco-curation-review.pages.dev/?repository=leej3%2Forinoco-lite-demo&pull_request=7&artifact_id=9549289607) and records source, retention, and merge-history requirements. Candidate membership and operations remain the proposal diff's authority; authenticated review is pending. |
| Exact-head SHACL input | run [32809501669](https://github.com/leej3/orinoco-lite-demo/actions/runs/32809501669), [artifact 9549337148](https://github.com/leej3/orinoco-lite-demo/actions/runs/32809501669/artifacts/9549337148), `orinoco-shacl-vue-input-f087cd3884a5b54885553d0d5e89b57c21d564b3`, 331,924 bytes, digest `sha256:85da1df4cafc0329c24a077a8bdf2038cbdb6530fd2066b6b9b41114fdb521a0`, expiry `2026-11-23T04:34:48Z` | Trusted default-branch code validated 201 records, 126 companions, and 408 annotation assertions, then posted the [attributed exact-head edit link](https://github.com/leej3/orinoco-lite-demo/pull/7#issuecomment-5405293563). No handoff commit was created. |
| Proposal-head consumer CI | run [32809500083](https://github.com/leej3/orinoco-lite-demo/actions/runs/32809500083), static-site artifact [9549410266](https://github.com/leej3/orinoco-lite-demo/actions/runs/32809500083/artifacts/9549410266), digest `sha256:d9127f4f0fd1012329b6deb57524397cc0ea7bbcfe086e272c2db45f66d848e3` | Both supported platforms passed 136 Python tests, Chromium 2/2, WebKit 2/2, 201-record/126-companion joined validation, and deterministic 565-file tree `6303496055bd682a55e3313566084673a5d474fa538fea143bc96b386fba4ceb`. A local `pixi run test-all` with the fixture fix overlaid on the superseded proposal head also passed the complete contract, with tree `84c3570e3f683f1659f76cc9c4fc975f4b411a50d666d41d2a04a84b773777a3`. |
| `dump-research-info` dispatch | run [32807071950](https://github.com/leej3/orinoco-lite-demo/actions/runs/32807071950), source commit `397b56080d14aeb94592f308b2f0bf325a298c13`, source tree `ce2435465c246a7b7da620f8fc5511cba11dd531`, directory `data/con_site` | Candidate planning was nonempty, then source validation stopped at `ror:04tfhh831: dangling about target https://centerforopenneuroscience.org/`. No proposal commit, branch, pull request, or artifact was created. Resolving the source assertion requires an explicit metadata-semantics decision; it was not silently mapped, dropped, or replaced. |

Pull request 5 is closed and retained only as the superseded run that exposed the proposal-head fixture defect; pull request 7 is the current review entry point.

## GitHub profile

Normative profile: [`github-curation-review.md`](github-curation-review.md)

| Requirement | Required evidence | Status |
| --- | --- | --- |
| Proposal | Default-branch dispatch opens one draft pull request whose first commit is an inline `datalad run --explicit` metadata proposal. | pass: run `32809444741` opened real draft pull request 7 at proposal `f087cd3884a5b54885553d0d5e89b57c21d564b3` |
| Pull-request summary | Trusted workflow provides a concise service link, source coordinate, retention notice, and merge-history requirement; detailed presentation facts remain in the ephemeral artifact. | pass in real pull request 7 |
| Review application | Deployed application shows responsive before-and-after record diffs, friendly primary identifiers, secondary source/path/hash details, mutually exclusive controls, filters, changed-only views, keyboard navigation, and completion status. | 86 application tests and production deployment pass; the real proposal route reaches GitHub authentication, with authenticated record review pending |
| Stateless service | The decision path exercises metadata read, Contents read, Actions read, and pull-requests write; the shared App's Contents write is confined to the separate explicit SHACL Vue handoff profile. OAuth state and short-lived sessions are operational state, and no proposal, decision, metadata, provenance, source, refresh token, or durable credential copy is retained. | deployment has no persistent bindings; App permissions and repository-scoped installation `156354646` pass |
| Complete decision state | Exact structured `/curation submit` binds repository, pull request, proposal commit, head, source, and the complete diff-derived candidate set; the trusted Action regenerates source IDs and claim digests and rejects missing, duplicate, unknown, or stale decisions. | focused app/Action tests pass; authenticated live submission pending |
| Human modifications | Comments and direct commits can produce attributed, validated metadata changes on the same branch. | focused tests pass; live attributed edit pending |
| SHACL Vue editing | GitHub proposal editing through SHACL Vue remains a distinct human-edit profile rather than a bundle input to this decision workflow. | exact-head input and attributed edit link pass at real pull request 7; live handoff pending |
| DataLad boundary | Programmatic metadata changes use the project Pixi/DataLad task; decision-cache-only commits use ordinary Git. | proposal/finalizer tests pass; normalization `0305fe8b19536f81318de10022b9bd77ab58fd21` and Zotero proposal `f087cd3884a5b54885553d0d5e89b57c21d564b3` supply real inline-run evidence |
| Attribution | The GitHub App posts on the user's behalf; the Action derives the reviewer from authenticated comment context, and each bot commit uses the most recent triggering human as author and automation as committer. | focused identity tests pass; live comment/commit pending |
| Trusted execution | Write credentials are not exposed to pull-request executable code or source data. | default-branch checkout and credential-isolation tests pass |
| Exact-head update | Automated writes use the observed pull-request head and fail on a concurrent change. | focused compare-and-swap and stale-head tests pass; live update pending |
| Correction | A pre-merge correction remains on the same pull request and finalization reruns against the new head. | focused interaction tests pass; live correction pending |
| Merge preservation | The default branch permits a merge commit and retains the exact proposal and human-review commit objects. | `required_linear_history=false`; real curation merge remains pending |
| Conflict handling | A conflicting proposal is regenerated from the new base; a clean non-overlapping proposal is not. | both orders and conflict regeneration pass in consumer run `32788660797` |
| Human authority | Automation never chooses a disposition, marks review ready, approves, merges, deploys, or writes to the source. | workflow permissions and negative-action tests pass |
| Public retention | The proposal discloses that rejected public metadata remains in Git history and requires acknowledgment before publication. | workflow and handoff tests pass; real pull request 7 contains the notice |
| No local requirement | An authorized reviewer completes the normal workflow through the linked web application and GitHub without a checkout. | real central application path is live; authenticated decision completion remains pending |
| Complexity boundary | No tracked inventory, review document, manifest, sidecar, reconciliation report, custom journal, or attestation graph is introduced. | merged tree and deployed bindings inspected; pass |

Application source commit `8bd328b17e359bf9594e83381c3efc1c7ab0ecac`, tree `57eab1253fcb668d7822973cf158feadfb67c1bf`, passed all 86 tests, type checking, Prettier, the Vite production build, and the Pages Functions build in run [32786292233](https://github.com/con/orinoco-lite-dev/actions/runs/32786292233).
Cloudflare deployment `cf459f0a-2ec9-40f1-9570-8f2041250d99` serves [its immutable URL](https://cf459f0a.orinoco-curation-review.pages.dev) and [the production origin](https://orinoco-curation-review.pages.dev) with HTTP 200, security headers, an anonymous stateless session response, and no KV, D1, R2, Durable Object, queue, or Worker product binding.
The deployed runtime manifest digest is `4ff3f2ff5a02d94084c262ca00ed5a8259a6ddfc420b9cfa0c4cd8cefe39bb3b`.
The public GitHub App [`orinoco-lite-curation-review`](https://github.com/apps/orinoco-lite-curation-review) (App 4704454) has metadata read, Contents write, Actions read, and pull-requests write and is installed as installation `156354646` only on `leej3/orinoco-lite-demo`.
Infrastructure pull request [Python-AI-Solutions/websites-management#13](https://github.com/Python-AI-Solutions/websites-management/pull/13), head `dd0e486caa99363ddcb266005f97c8e20494a1ec`, merge `91cbfbc65de29377d6b1679a4715a47bd24ee95c`, records OpenTofu lineage `85c4e740-c3c3-06b0-7786-0b91fa7fc457`.
A production-state repair restored public `EDITOR_RUNTIME_MANIFEST_SHA256=4ff3f2ff5a02d94084c262ca00ed5a8259a6ddfc420b9cfa0c4cd8cefe39bb3b` with a `0 add, 1 change, 0 destroy` apply, advanced serial `49` to `50`, and ended with a no-change plan; [the attributed evidence comment](https://github.com/Python-AI-Solutions/websites-management/pull/13#issuecomment-5404855515) records the final deployment state.

## GitHub SHACL Vue human-edit profile

Normative profile: [`github-shacl-vue-edit.md`](github-shacl-vue-edit.md)

| Requirement | Required evidence | Status |
| --- | --- | --- |
| Neutral editor handoff | Existing download bytes remain unchanged; the browser event exposes the exact same version 2 object and contains no GitHub or curation semantics. | engine pull request 16; object-identity and unchanged-download tests passed in release run `32786292302` |
| Exact editor state | Existing-PR editing is bound to its exact head and standalone editing to an exact default-branch commit. | app tree `57eab1253fcb668d7822973cf158feadfb67c1bf`; real pull requests 29 and 7 produced exact-head artifacts and attributed links |
| Authenticated proposal | A write/admin curator explicitly creates a same-repository draft branch or appends to an existing draft PR through the configurable service. | focused service tests and repository-scoped App Contents-write authorization pass; live handoff pending |
| Temporary handoff | One bounded bundle-only commit has one exact parent and cannot merge; the public-retention warning excludes secrets and non-public data. | app and consumer pull request 28 tests pass; live handoff pending |
| Trusted conversion | Default-branch Python applies pinned Orinoco behavior without executing PR code and permits only canonical records and mirrored annotation companions. | consumer default `77aa43fe4cb140bd7a92c5218f0dbd94dd686787`; workflow/helper tests and canonical merge-head validation passed |
| Replacement history | Exact force-with-lease replaces only the handoff commit with an attributed human metadata commit sharing its parent; every earlier commit survives and the final branch contains no bundle. | consumer pull request 28 repeated-edit and exact-lease tests pass; live handoff pending |
| Joined validation | Stored records, annotation companions, and the complete joined graph validate before the replacement ref is published. | trusted runs `32794977293` and `32809501669` validated real exact heads; live bundle replacement pending |
| Least privilege | Contents write is used only for explicit human handoff branch/commit operations; no approval, merge, deployment, disposition, cache, provenance, or source write occurs. | implementation tests and App installation `156354646` pass; live handoff pending |
| Statelessness | Neither service nor Action retains the bundle after replacement, and no database, metadata service, manifest, journal, or recovery protocol is introduced. | application/workflow inspection and deployed no-binding evidence pass; live handoff pending |

The browser-Python feasibility spike was closed without retained code: the pinned conversion stack requires unavailable native/WASM dependencies and Git/subprocess behavior, so conversion remains in trusted default-branch Python rather than a browser or TypeScript replacement.
Default-branch SHACL publication run [32789236694](https://github.com/con/test-orinoco-downstream-website/actions/runs/32789236694) produced artifact `9542562091`, name `orinoco-shacl-vue-input-14414164bcf7f901261be8ecb7364c67b42b62a6`, digest `sha256:0ea26de44d9f723882aa1db8d6a6a45c009f7e33cc955ad9ef2a1bdda8468f27`, 243,200 bytes, expiring 2026-11-22.
Default-main Pages run [32789236666](https://github.com/con/test-orinoco-downstream-website/actions/runs/32789236666) passed.
Default-main validation run [32789237197](https://github.com/con/test-orinoco-downstream-website/actions/runs/32789237197) passed on attempt 2 after a transient loose-object checkout failure on the first Linux attempt; no source change was required.
At real draft pull request 29 head `0bbec9bc2871ddb60dd351e616dda62386ad970b`, trusted run [32794977293](https://github.com/con/test-orinoco-downstream-website/actions/runs/32794977293) classified the three-commit merge history as canonical, validated 199 records and a deterministic 467-edge/186-node graph, and produced [artifact 9544519920](https://github.com/con/test-orinoco-downstream-website/actions/runs/32794977293/artifacts/9544519920), name `orinoco-shacl-vue-input-0bbec9bc2871ddb60dd351e616dda62386ad970b`, digest `sha256:3faba63410653d7295cdc4d6a5c3d784e6f41639d4a03c695bb39e78b9002518`, 243,195 bytes, expiring `2026-11-23T00:46:39Z`.
The workflow posted the [attributed exact-head service link](https://github.com/con/test-orinoco-downstream-website/pull/29#issuecomment-5403481275) and performed no handoff replacement.
The preceding failure at run `32792689668` isolated the merge-head classification defect; template pull request 14 and immutable `v0.2.0rc4` corrected it while retaining one-parent bundle heads, approved-path history checks, and rejection of unapproved merge resolutions.

## Cross-layer acceptance

Current cross-layer coordinates are:

- engineering pull requests 16, 17, and 19, release/tag `v0.2.0rc3` at `7e331a2c61be2a5701c95c7dc48acf61d2ee106d`, rollback parent `8bd328b17e359bf9594e83381c3efc1c7ab0ecac`;
- template pull requests 12 through 14 and latest release/tag `v0.2.0rc4`, source rollback parent `1c4c105a57e23a745b86cf0491177e2b788345f0`, and published-branch rollback parent `88c5f0629c31bca30001a2c8feb9a0629a83bbab`;
- consumer pull requests 28 and 30 through 34, latest merge `3f75c7d1395f1d442ba30d15516bd9d8ce8db949`, fixture-isolation head `eb6930ebbf0d73128516bd658786e92107be5f9e`, and rollback parent `77aa43fe4cb140bd7a92c5218f0dbd94dd686787`;
- personal demonstration pull request 6 and merge `68738ed8df375fe14d87da216c6d8a7ee6d7e82c`, rollback parent `9b178b49099d37e5bd10cc128962aea8b8b0d89a`;
- infrastructure pull request 13 and merge `91cbfbc65de29377d6b1679a4715a47bd24ee95c`, rollback base `0c129d26897ba9b7a07cac9fa06ca19bf70c055f`; and
- separate canonicalization pull request 29 at merge-preserving head `0bbec9bc2871ddb60dd351e616dda62386ad970b`, whose review and merge remain pending.

Published `v0.2.0rc3` release and embedded manifest SHA-256 values are: wheel `5224bf90ca441b70012f7297b21b1b8072fe612e9c8984d3682c824118037267`, source distribution `5dac72b1486ddd22b79e8f40ca4bc6220faba2b072e46223d52be24f01632ca2`, runtime `d25be7a05da33b6b91dc7b3bc1c6b83168f9c54f6bca663cb4a4902e1e7b060a`, runtime manifest `839f82029ae0b4805a6d8c53afd88eb18a53023daf13fa5fd09c217dc8f101fd`, provenance bundle `5a326f741360e229497bb4d581a5f5bda81b0d64f91f3b30373b334f57955e96`, and `SHA256SUMS` `2a12d5a20000321e7e9933c0a4333c870e09d38548f95dd3168d4d3f58bb185a`.
GitHub artifact attestations verified for the wheel, source distribution, and runtime; an unauthenticated public wheel install reported `orinoco-lite 0.2.0rc3`.

Still required are a reviewed resolution of the real `dump-research-info` source-semantic blocker and its first proposal, compact-cache examples from authenticated finalization, the same-source no-op rerun, one real SHACL handoff, and the merge commit that proves proposal and review commits survive.
The real Zotero proposal already supplies exact dispatch-time source coordinates, presentation artifacts, and green exact-head consumer validation; its OAuth sign-in, dispositions, submission, and finalization remain entirely human-owned.

## Conditional semantics

Additional W3C PROV and SSSOM are not activated.
If a later concrete lineage question or ontology-mapping set requires either, amend the normative specification first and add focused round-trip evidence here.

## Exit status

Milestone 5 implementation and distribution are complete through the development repositories, the central service is deployed, the App permission update is installed on the isolated public demo, and a real Zotero proposal is open.
Exit remains pending on review and merge of the separate corpus normalization, an authenticated human review/finalization and same-source rerun, one explicit SHACL handoff, and a reviewed resolution plus proposal for the `dump-research-info` source-semantic blocker.
No synthetic metadata proposal was created, and no curation proposal was approved or merged by automation.

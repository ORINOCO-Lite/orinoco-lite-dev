# Milestone 5 acceptance record

Status: active; implementation released and integrated, live curation evidence pending

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
| Engineering | exact base, released engine/runtime inputs, upstream pins, clean worktree, and baseline tests | pull requests [16](https://github.com/con/orinoco-lite-dev/pull/16) and [17](https://github.com/con/orinoco-lite-dev/pull/17); release/tag commit `8bd328b17e359bf9594e83381c3efc1c7ab0ecac`; Dump Things `9f101d97c7f15d491f602db5a9c33ad9a19ad8bf`; Things Schema `cb6c791aec4c5309775437df4bd58e94e1bfcc3c`; enrichment-tools `2e6a5ddc92928a6165b81fdae24a52c447967c7d` |
| Zotero | exact library version, adapter revision, policy revision, and baseline behavior | library version `451`; snapshot blob `6d287b0f6d5edbdb36a5308b3605bb86ab3d55a7`; adapter tree `cc45d86b97ee0ad5f7c84ea60fa483e0cd88b733`; policy tree `3606bad690c41a9f120d113ca7d7e21062017ec7` |
| `dump-research-info` | exact source revision, adapter revision, policy revision, and baseline behavior | adapter tree `8598768bae80e3eff55191876d8e20c57a8a5365`; candidate builder blob `5e6eb317b41076eb6a131620534b7a743e456ccf`; adapter blob `4897dfa97128d68bcdf76881993d2c9a7b1a4afa`; external source revision remains an explicit dispatch input |
| Consumer | exact base, lock, template release, corpus counts, branch policy, and baseline CI | implementation pull request [28](https://github.com/con/test-orinoco-downstream-website/pull/28), head `1616b5d909f872a379a9e915469c35f6ef973355`, merge `14414164bcf7f901261be8ecb7364c67b42b62a6`; framework pull requests [30](https://github.com/con/test-orinoco-downstream-website/pull/30) and [31](https://github.com/con/test-orinoco-downstream-website/pull/31), latest head `5eaa7c7aee127c45080006d1344ef4824fd84da0`, merge `f19692f8fa2eee2202b419fe91ed7274eee70c94`; 199 Things and no companions; engine/runtime `v0.2.0rc2`, template `v0.2.0rc4`; `required_linear_history=false` |
| Template | exact source release and generated-template commit if generic support changes | pull requests [12](https://github.com/con/orinoco-lite-template/pull/12), [13](https://github.com/con/orinoco-lite-template/pull/13), and [14](https://github.com/con/orinoco-lite-template/pull/14); latest head `3d59b54f75bafb47fae68c64d679e2c5a9083bb8`, merge/tag `48d14836f0ba26e61ac205e93e80cfe035000585`, immutable `v0.2.0rc4`; generated `github-template` commit `cb3790c83fc1a7a6bdf476c98522130378d61a8d`, tree `c7d545ad9293204b4a37a6479ca6efc36b1a99e9` |
| Platforms | macOS ARM64 and Linux x86-64 clean-clone commands and results | engineering run [32786292302](https://github.com/con/orinoco-lite-dev/actions/runs/32786292302), latest template run [32793702036](https://github.com/con/orinoco-lite-template/actions/runs/32793702036), and latest framework consumer run [32794385122](https://github.com/con/test-orinoco-downstream-website/actions/runs/32794385122) passed on macOS 14 ARM64 and Ubuntu 24.04 x86-64 |

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

The released shared core is in `orinoco-lite==0.2.0rc2`; the wheel digest is `f504d1fb9f2dfdbdd224dcbbcc663843a7ac34107c304d0eb5ed538e45a43198` and the runtime digest is `a038f3810fe5a001d1cc28a30715cc0cf95c90365d0b1e6c344271a631db8e09`.

## Adapter behavior matrix

Each row requires focused tests for both adapters and at least one reviewed GitHub execution across the combined evidence.

| Case | Required result | Zotero | `dump-research-info` |
| --- | --- | --- | --- |
| New claim | A friendly record entry and actual metadata diff are presented for explicit review. | focused pass; live review pending | focused pass; live review pending |
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

Consumer pull request run `32788660797` used only released `v0.2.0rc2` interfaces and passed 129 site-owned Python tests, deterministic projection/build checks, and two Chromium plus two WebKit checks on macOS ARM64 and Linux x86-64. It covers both adapters, the trusted host and workflows, idempotence, all-rejected review, material-change reopening, human correction, deletion, exact-head behavior, conflict regeneration, and non-overlapping merges in both Git-allowed orders. Framework integration run [32794385122](https://github.com/con/test-orinoco-downstream-website/actions/runs/32794385122) passed 134 site-owned Python tests, the deterministic 561-file build, Chromium 2/2, and WebKit 2/2 on both supported platforms with template `v0.2.0rc4` and unchanged engine/runtime `v0.2.0rc2`.
At least one real adapter proposal and authenticated review remain required; no synthetic proposal was opened.

## GitHub profile

Normative profile: [`github-curation-review.md`](github-curation-review.md)

| Requirement | Required evidence | Status |
| --- | --- | --- |
| Proposal | Default-branch dispatch opens one draft pull request whose first commit is an inline `datalad run --explicit` metadata proposal. | pending |
| Pull-request summary | Trusted workflow provides a concise service link, source coordinate, retention notice, and merge-history requirement; detailed presentation facts remain in the ephemeral artifact. | workflow tests pass; live proposal pending |
| Review application | Deployed application shows responsive before-and-after record diffs, friendly primary identifiers, secondary source/path/hash details, mutually exclusive controls, filters, changed-only views, keyboard navigation, and completion status. | 86 application tests and production deployment pass; real proposal load pending |
| Stateless service | The decision path exercises metadata read, Contents read, Actions read, and pull-requests write; the shared App's Contents write is confined to the separate explicit SHACL Vue handoff profile. OAuth state and short-lived sessions are operational state, and no proposal, decision, metadata, provenance, source, refresh token, or durable credential copy is retained. | deployment has no persistent bindings; App Contents-write update pending |
| Complete decision state | Exact structured `/curation submit` binds repository, pull request, proposal commit, head, source, and the complete diff-derived candidate set; the trusted Action regenerates source IDs and claim digests and rejects missing, duplicate, unknown, or stale decisions. | focused app/Action tests pass; authenticated live submission pending |
| Human modifications | Comments and direct commits can produce attributed, validated metadata changes on the same branch. | focused tests pass; live attributed edit pending |
| SHACL Vue editing | GitHub proposal editing through SHACL Vue remains a distinct human-edit profile rather than a bundle input to this decision workflow. | implemented and tested; live handoff pending |
| DataLad boundary | Programmatic metadata changes use the project Pixi/DataLad task; decision-cache-only commits use ordinary Git. | proposal/finalizer tests pass; normalization commit `0305fe8b19536f81318de10022b9bd77ab58fd21` supplies real inline-run evidence |
| Attribution | The GitHub App posts on the user's behalf; the Action derives the reviewer from authenticated comment context, and each bot commit uses the most recent triggering human as author and automation as committer. | focused identity tests pass; live comment/commit pending |
| Trusted execution | Write credentials are not exposed to pull-request executable code or source data. | default-branch checkout and credential-isolation tests pass |
| Exact-head update | Automated writes use the observed pull-request head and fail on a concurrent change. | focused compare-and-swap and stale-head tests pass; live update pending |
| Correction | A pre-merge correction remains on the same pull request and finalization reruns against the new head. | focused interaction tests pass; live correction pending |
| Merge preservation | The default branch permits a merge commit and retains the exact proposal and human-review commit objects. | `required_linear_history=false`; real curation merge remains pending |
| Conflict handling | A conflicting proposal is regenerated from the new base; a clean non-overlapping proposal is not. | both orders and conflict regeneration pass in consumer run `32788660797` |
| Human authority | Automation never chooses a disposition, marks review ready, approves, merges, deploys, or writes to the source. | workflow permissions and negative-action tests pass |
| Public retention | The proposal discloses that rejected public metadata remains in Git history and requires acknowledgment before publication. | workflow and handoff acknowledgment tests pass; live proposal pending |
| No local requirement | An authorized reviewer completes the normal workflow through the linked web application and GitHub without a checkout. | application path implemented; end-to-end live review pending |
| Complexity boundary | No tracked inventory, review document, manifest, sidecar, reconciliation report, custom journal, or attestation graph is introduced. | merged tree and deployed bindings inspected; pass |

Application source commit `8bd328b17e359bf9594e83381c3efc1c7ab0ecac`, tree `57eab1253fcb668d7822973cf158feadfb67c1bf`, passed all 86 tests, type checking, Prettier, the Vite production build, and the Pages Functions build in run [32786292233](https://github.com/con/orinoco-lite-dev/actions/runs/32786292233).
Cloudflare deployment `cf459f0a-2ec9-40f1-9570-8f2041250d99` serves [its immutable URL](https://cf459f0a.orinoco-curation-review.pages.dev) and [the production origin](https://orinoco-curation-review.pages.dev) with HTTP 200, security headers, an anonymous stateless session response, and no KV, D1, R2, Durable Object, queue, or Worker product binding.
The deployed runtime manifest digest is `4ff3f2ff5a02d94084c262ca00ed5a8259a6ddfc420b9cfa0c4cd8cefe39bb3`.
The public GitHub App `orinoco-lite-curation-review` (App 4704454) currently has metadata read, Contents read, Actions read, and pull-requests write; the approved Contents-write update and installation 156254062 approval remain pending interactive GitHub authorization.
Infrastructure pull request [Python-AI-Solutions/websites-management#13](https://github.com/Python-AI-Solutions/websites-management/pull/13), head `dd0e486caa99363ddcb266005f97c8e20494a1ec`, merge `91cbfbc65de29377d6b1679a4715a47bd24ee95c`, records OpenTofu lineage `85c4e740-c3c3-06b0-7786-0b91fa7fc457`, serial `48` to `49`, and a `0 add, 1 change, 0 destroy` apply followed by a no-change plan.

## GitHub SHACL Vue human-edit profile

Normative profile: [`github-shacl-vue-edit.md`](github-shacl-vue-edit.md)

| Requirement | Required evidence | Status |
| --- | --- | --- |
| Neutral editor handoff | Existing download bytes remain unchanged; the browser event exposes the exact same version 2 object and contains no GitHub or curation semantics. | engine pull request 16; object-identity and unchanged-download tests passed in release run `32786292302` |
| Exact editor state | Existing-PR editing is bound to its exact head and standalone editing to an exact default-branch commit. | app tree `57eab1253fcb668d7822973cf158feadfb67c1bf`; real pull request 29 artifact and attributed exact-head link pass |
| Authenticated proposal | A write/admin curator explicitly creates a same-repository draft branch or appends to an existing draft PR through the configurable service. | focused service tests pass; live App Contents-write authorization pending |
| Temporary handoff | One bounded bundle-only commit has one exact parent and cannot merge; the public-retention warning excludes secrets and non-public data. | app and consumer pull request 28 tests pass; live handoff pending |
| Trusted conversion | Default-branch Python applies pinned Orinoco behavior without executing PR code and permits only canonical records and mirrored annotation companions. | consumer default `f19692f8fa2eee2202b419fe91ed7274eee70c94`; workflow/helper tests and canonical merge-head validation passed |
| Replacement history | Exact force-with-lease replaces only the handoff commit with an attributed human metadata commit sharing its parent; every earlier commit survives and the final branch contains no bundle. | consumer pull request 28 repeated-edit and exact-lease tests pass; live handoff pending |
| Joined validation | Stored records, annotation companions, and the complete joined graph validate before the replacement ref is published. | trusted run `32794977293` validated the real 199-record normalization head; live bundle replacement pending |
| Least privilege | Contents write is used only for explicit human handoff branch/commit operations; no approval, merge, deployment, disposition, cache, provenance, or source write occurs. | implementation tests pass; public App Contents-write registration and installation approval pending |
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

- engineering pull requests 16 and 17, release/tag `v0.2.0rc2`, rollback parent `829ee92acbc2c872e89b4a68f7b260ac5ed990a3`;
- template pull requests 12 through 14 and latest release/tag `v0.2.0rc4`, source rollback parent `1c4c105a57e23a745b86cf0491177e2b788345f0`, and published-branch rollback parent `88c5f0629c31bca30001a2c8feb9a0629a83bbab`;
- consumer pull requests 28, 30, and 31 and latest merge `f19692f8fa2eee2202b419fe91ed7274eee70c94`, implementation rollback base `7e66d156a677435e838e9495094288d42fb26c29`;
- infrastructure pull request 13 and merge `91cbfbc65de29377d6b1679a4715a47bd24ee95c`, rollback base `0c129d26897ba9b7a07cac9fa06ca19bf70c055f`; and
- separate canonicalization pull request 29 at merge-preserving head `0bbec9bc2871ddb60dd351e616dda62386ad970b`, whose review and merge remain pending.

Published release and embedded manifest SHA-256 values are: wheel `f504d1fb9f2dfdbdd224dcbbcc663843a7ac34107c304d0eb5ed538e45a43198`, source distribution `47c831a7d9dc2c7e433cbf78459551a00280ddd01d1a6ac70a1d5dff478f23da`, runtime `a038f3810fe5a001d1cc28a30715cc0cf95c90365d0b1e6c344271a631db8e09`, runtime manifest `4ff3f2ff5a02d94084c262ca00ed5a8259a6ddfc420b9cfa0c4cd8cefe39bb3`, provenance bundle `f0d3a15bb486b8379ea2a88012cd0970c3078e15b422d25b734d77b17251a209`, and `SHA256SUMS` `e33fcb34bdcab0ae65700f8796a081572ef9ee861572b21fc84a36f9cdcba797`.
GitHub artifact attestations verified for the wheel, source distribution, and runtime; an unauthenticated public wheel install reported `orinoco-lite 0.2.0rc2`.

Still required are exact dispatch-time source coordinates and compact-cache examples for the first live proposal from each adapter, at least one real authenticated proposal/review/finalization, the same-source no-op rerun, one real SHACL handoff, and the merge commit that proves proposal and review commits survive.

## Conditional semantics

Additional W3C PROV and SSSOM are not activated.
If a later concrete lineage question or ontology-mapping set requires either, amend the normative specification first and add focused round-trip evidence here.

## Exit status

Milestone 5 implementation and distribution are complete through the development repositories, but exit remains pending on four reviewed external steps: merge the separate corpus normalization, approve canonical versioned Things for the two adapter identities, authorize the GitHub App's Contents-write permission, and exercise the central application against the resulting real proposal and one real SHACL handoff.
No synthetic metadata proposal was created, and no curation proposal was approved or merged by automation.

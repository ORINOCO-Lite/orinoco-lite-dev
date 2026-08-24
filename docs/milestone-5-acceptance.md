# Milestone 5 acceptance record

Status: active; shared metadata foundation implemented, cross-layer evidence pending

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
| Specification | reviewed pull request head and merge commit establishing the normative contract and accepted M5 decisions | `829ee92acbc2c872e89b4a68f7b260ac5ed990a3` (`main`, pull request 15); current refinement pending review |
| Engineering | exact base, released engine/runtime inputs, upstream pins, clean worktree, and baseline tests | base `829ee92acbc2c872e89b4a68f7b260ac5ed990a3`; Dump Things `9f101d97c7f15d491f602db5a9c33ad9a19ad8bf`; Things Schema `cb6c791aec4c5309775437df4bd58e94e1bfcc3c`; enrichment-tools `2e6a5ddc92928a6165b81fdae24a52c447967c7d`; local implementation heads below |
| Zotero | exact library version, adapter revision, policy revision, and baseline behavior | pending |
| `dump-research-info` | exact source revision, adapter revision, policy revision, and baseline behavior | pending |
| Consumer | exact base, lock, template release, corpus counts, branch policy, and baseline CI | reviewed base `7e66d156a677435e838e9495094288d42fb26c29`; implementation `e7aa3079b2312b27cfd9689bcd3ad16b74addf60`; immutable release pin and review pending |
| Template | exact source release and generated-template commit if generic support changes | pending |
| Platforms | macOS ARM64 and Linux x86-64 clean-clone commands and results | local macOS 26.5.2 ARM64 foundation pass; clean-clone and Linux evidence pending |

Live-source or authoritative-head drift is advisory and must not silently replace a reviewed input.

## Shared metadata foundation

| Requirement | Evidence | Status |
| --- | --- | --- |
| Canonical ordering | Focused parity with pinned Dump Things mapping ordering and YAML serialization, including idempotence and preserved list order | local pass `f413278a4ad8c6da0eb1f1d6412d42b06f5a759c`; review pending |
| Corpus normalization | Separate reviewed pull request showing the one-time canonicalization-only diff | pending |
| Annotation selectors | Exact path/hash matching rejects missing or ambiguous mapping assertions; scalar targets are rejected | local pass `91ad2b6886a610aad24a9061d3e71ea2d39db042`; review pending |
| Joined validation | Stored semantic assertion objects plus annotation companions validate as one Thing with the locked schema | local pass `91ad2b6886a610aad24a9061d3e71ea2d39db042` for object, typed data, and class-range assertions; review pending |
| RDF round trip | Expanded PAV survives JSON-to-RDF-to-JSON for imported objects, string data, typed non-string data, and class-range Statements without semantic loss or topical type coercion | local pass `91ad2b6886a610aad24a9061d3e71ea2d39db042`; review pending |
| Projection | Stored qualified assertions reach normal semantic projections, joined PAV reaches the machine projection, and actual public rendering behavior is explicit | joined machine projection and assertion fingerprints pass at `91ad2b6886a610aad24a9061d3e71ea2d39db042`; consumer rendering pending |
| Human-facing storage | Record YAML contains no machine-only PAV and the overlay contains no copied record or decision history | local pass `91ad2b6886a610aad24a9061d3e71ea2d39db042`; review pending |
| Upstream scalar updates | Missing, equal, differing, same-owner, human-owned, and differently owned values match pinned `update_data_property()` after reversible compact-PAV split/join and typed normalization; the missing-topical/equivalent-unowned case copies the topical value without new PAV | local parity pass `91ad2b6886a610aad24a9061d3e71ea2d39db042`; review pending |

Foundation verification command: `pixi run test` at `427232e0a0d9065f560227c24034e26c8b0bce8f` on macOS 26.5.2 ARM64; 153 engine tests passed with 2 fixture skips and all 40 development tests passed.
The tests cover scalar-target rejection; absent, equal, changed, same-owner, human-owned, and differently owned upstream paths; the approved missing-topical convenience copy; multivalue order; compact/expanded PAV; typed values; class-range `Statement` storage; joined RDF; projection fingerprints; and candidate/cache behavior.

## Shared review core

| Requirement | Evidence | Status |
| --- | --- | --- |
| Ephemeral candidates | Deterministic immutable add/modify/delete plans, canonical record/companion bytes, source-claim hashes independent of curated baselines, fixed PIDs/paths, no provenance-only candidates, and adapter-agent checks | local pass `8ebd7122a0167e1c300a2c1eff94dc74ec162a19`; 20 focused tests |
| Compact decisions | Exact v1 canonical YAML, complete current-candidate decisions, authenticated GitHub review coordinates, accept/reject suppression, defer and material-change reopening, human-correction suppression, source remap, and referenced-review pruning | local pass `f7b14d45f86040edbdab7b061a7b4c1ef3dbb4a3`; 21 focused tests |
| Git finalization | Exact base/proposal/head verification; add, modify, delete, all-rejected, accepted correction, cache-only accept, clean three-way reversal, overlap failure, hostile Git environment, and path-escape prevention | local pass `961f2961488cb6185fe1a5985c82be591bfab300`; 18 focused temporary-repository tests |

Shared-core verification command: `pixi run test` at `961f2961488cb6185fe1a5985c82be591bfab300` on macOS 26.5.2 ARM64; 142 engine tests passed with 2 expected fixture skips and all 40 development tests passed.
The scalar-path tests in that count remain provisional as described above; candidate, decision, and Git-finalization evidence is independent of the reopened storage choice.

## Adapter behavior matrix

Each row requires focused tests for both adapters and at least one reviewed GitHub execution across the combined evidence.

| Case | Required result | Zotero | `dump-research-info` |
| --- | --- | --- | --- |
| New claim | A friendly record entry and actual metadata diff are presented for explicit review. | local pass; review pending | local pass; review pending |
| Accept | The reviewed proposal remains, the compact cache records acceptance, and an identical rerun is a no-op. | local pass; review pending | local pass; review pending |
| Reject | The candidate patch is reversed with three-way semantics, non-overlapping human edits survive, the compact cache records rejection, and the unchanged claim stays suppressed. | local pass; review pending | local pass; review pending |
| Defer | The candidate patch is reversed with three-way semantics, non-overlapping human edits survive, and the claim returns on the next adapter proposal. | shared-core pass; adapter evidence pending | shared-core pass; adapter evidence pending |
| Material source change | A changed metadata-affecting source claim returns for review. | local pass; review pending | local pass; review pending |
| Unused source change | A source change that cannot affect generated metadata produces no candidate or metadata diff. | local pass; review pending | local pass; review pending |
| Human correction | An accepted human edit is attributed, removes only untouched stale proposal PAV, deletes an emptied companion, and is not reverted by an unchanged source claim; overlap or ambiguous companion state fails. | local pass; review pending | local pass; review pending |
| Deletion | The record and matching annotation companion are visibly proposed for deletion and accept/reject behave normally. | host-core pass; adapter evidence pending | host-core pass; adapter evidence pending |
| All rejected | Final metadata matches the base while the compact decisions and reviewed proposal lineage survive the merge. | local pass; review pending | local pass; review pending |
| Existing PAV | A semantically identical assertion retains its current PAV and produces no provenance-only diff. | local pass; review pending | local pass; review pending |
| Adapter rerun | Generation cannot overwrite an explicit human disposition or unrelated human metadata. | local pass; review pending | local pass; review pending |
| Missing or malformed decision | Finalization stops with a focused diagnostic and does not infer a disposition. | host-core pass; adapter review pending | host-core pass; adapter review pending |
| Adapter overlap | Independent claims remain visible, preserve their own identities/PAV, and neither cache suppresses the other. | local combined pass; review pending | local combined pass; review pending |

Consumer verification used engineering `427232e0a0d9065f560227c24034e26c8b0bce8f` and consumer `e7aa3079b2312b27cfd9689bcd3ad16b74addf60`: `pixi run --manifest-path ENGINEERING/pixi.toml python .orinoco-lite/tools/run_consumer_tests.py` passed all 107 site-owned tests on macOS ARM64.
That run includes both adapters, the trusted host and workflow, idempotence, all-rejected review, material-change reopening, human correction, deletion, exact-head behavior, conflict regeneration, and non-overlapping merges in both Git-allowed orders.
The immutable `0.2.0rc1` consumer pin remains pending publication.

## GitHub profile

Normative profile: [`github-curation-review.md`](github-curation-review.md)

| Requirement | Required evidence | Status |
| --- | --- | --- |
| Proposal | Default-branch dispatch opens one draft pull request whose first commit is an inline `datalad run --explicit` metadata proposal. | pending |
| Pull-request summary | Trusted workflow provides a concise service link, source coordinate, retention notice, and merge-history requirement; detailed presentation facts remain in the ephemeral artifact. | pending |
| Review application | Deployed application shows responsive before-and-after record diffs, friendly primary identifiers, secondary source/path/hash details, mutually exclusive controls, filters, changed-only views, keyboard navigation, and completion status. | pending |
| Stateless service | GitHub App uses only metadata read, contents read, Actions read, and pull-requests write access; OAuth state and short-lived sessions are operational state, and no proposal, decision, metadata, provenance, source, refresh token, or durable credential copy is retained. | pending |
| Complete decision state | Exact structured `/curation submit` binds repository, pull request, proposal commit, head, source, and the complete diff-derived candidate set; the trusted Action regenerates source IDs and claim digests and rejects missing, duplicate, unknown, or stale decisions. | pending |
| Human modifications | Comments and direct commits can produce attributed, validated metadata changes on the same branch. | pending |
| SHACL Vue editing | GitHub proposal editing through SHACL Vue is a distinct human-edit profile rather than a bundle input to this decision workflow. | deferred to a separate reviewed task |
| DataLad boundary | Programmatic metadata changes use the project Pixi/DataLad task; decision-cache-only commits use ordinary Git. | pending |
| Attribution | The GitHub App posts on the user's behalf; the Action derives the reviewer from authenticated comment context, and each bot commit uses the most recent triggering human as author and automation as committer. | pending |
| Trusted execution | Write credentials are not exposed to pull-request executable code or source data. | pending |
| Exact-head update | Automated writes use the observed pull-request head and fail on a concurrent change. | pending |
| Correction | A pre-merge correction remains on the same pull request and finalization reruns against the new head. | pending |
| Merge preservation | The default branch permits a merge commit and retains the exact proposal and human-review commit objects. | pending |
| Conflict handling | A conflicting proposal is regenerated from the new base; a clean non-overlapping proposal is not. | pending |
| Human authority | Automation never chooses a disposition, marks review ready, approves, merges, deploys, or writes to the source. | pending |
| Public retention | The proposal discloses that rejected public metadata remains in Git history and requires acknowledgment before publication. | pending |
| No local requirement | An authorized reviewer completes the normal workflow through the linked web application and GitHub without a checkout. | pending |
| Complexity boundary | No tracked inventory, review document, manifest, sidecar, reconciliation report, custom journal, or attestation graph is introduced. | pending |

Application verification at `031c70f83e534d2fb066172330ede52e4c4184fa` used Node 22.23.2 and npm 11.6.0: 45 tests, type checking, the Vite production build, and the Wrangler Functions build passed.
Cloudflare deployment `a69a83f5-4d0c-4512-a608-48836ba8f794` serves both `https://a69a83f5.orinoco-curation-review.pages.dev` and `https://orinoco-curation-review.pages.dev` with HTTP 200 and no persistent-service bindings.
The public GitHub App `orinoco-lite-curation-review` (App 4704454) is registered for metadata read, contents read, Actions read, and pull-requests write.
Installation 156254062 remains limited to `con/test-orinoco-downstream-website`; its added Actions permission awaits approval by a `con` organization owner.
Infrastructure pull request [Python-AI-Solutions/websites-management#13](https://github.com/Python-AI-Solutions/websites-management/pull/13) records deployment and no-change OpenTofu evidence at `8f0f8d2e1819ea046b5306f7a49f87ec457be640`.

## Cross-layer acceptance

Before Milestone 5 exits, record:

- reviewed engineering, consumer, and any template pull requests with exact heads and merge commits;
- released engine and runtime coordinates if shared runtime behavior changes;
- clean-clone macOS ARM64 and Linux x86-64 results through released interfaces;
- complete consumer validation, build, deterministic-output, browser, and ownership results;
- exact source coordinates and compact decision-cache examples for both adapters;
- one non-overlapping adapter merge-order exercise and one conflict/regeneration exercise;
- rollback coordinates for every changed repository; and
- any separately authorized content changes.

## Conditional semantics

Additional W3C PROV and SSSOM are not activated.
If a later concrete lineage question or ontology-mapping set requires either, amend the normative specification first and add focused round-trip evidence here.

## Exit status

Milestone 5 remains pending until every required row above has reviewed evidence or is explicitly removed through a focused specification change.

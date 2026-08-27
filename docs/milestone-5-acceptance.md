# Milestone 5 acceptance

Status: accepted on 2026-08-26

Plan: [`milestone-5.md`](milestone-5.md)

Normative contract: [`source-adapters.md`](source-adapters.md)

Decision register: [`milestone-5-decisions.md`](milestone-5-decisions.md)

## Result

Milestone 5 delivered the source-adapter and human-review architecture described by the normative contract:

- canonical human-facing Things records plus PAV-only annotation companions;
- a reversible joined schema/RDF/projection view;
- deterministic source candidates and compact current-state decisions;
- Zotero and `dump-research-info` adapters with distinct source policy and one shared review/finalization contract;
- one GitHub pull request containing the proposal, human decisions, attributed changes, and mechanical finalization;
- a stateless hosted decision interface with GitHub as the durable review authority;
- a separate SHACL Vue GitHub handoff and trusted Python replacement path; and
- immutable engine/runtime and template distribution exercised on macOS ARM64 and Linux x86-64.

Milestone 5 is accepted on implemented, focused, cross-layer, and one complete live source-adapter transition.
A fresh current Zotero transition, the first live SHACL handoff, and improved SHACL proposal discoverability are operational Milestone 6 work, not missing Milestone 5 architecture.

## Accepted coordinates

| Surface | Accepted evidence |
| --- | --- |
| Specification | [Engineering pull request 16](https://github.com/con/orinoco-lite-dev/pull/16), merged as `91b1658135e4a21b8d103e43c70db58cbabc58e1`. |
| Engine and runtime | [`orinoco-lite` `v0.2.0rc4`](https://github.com/con/orinoco-lite-dev/releases/tag/v0.2.0rc4), commit `abdf5623ce7b0b16146940ba6dafc7290124e9cc`. |
| Template | [`v0.2.0rc7`](https://github.com/con/orinoco-lite-template/releases/tag/v0.2.0rc7), source commit `f46f717fddb452440ad0ba091b1af145a2769eef`. |
| Current engineering integration | [Engineering pull request 39](https://github.com/con/orinoco-lite-dev/pull/39), merged as `6e64072ec535149cc0652da64c51b15e4d586fec`; [hosted engineering run 32998589027](https://github.com/con/orinoco-lite-dev/actions/runs/32998589027) passed. |
| Hosted review application | The stateless application and trusted functions passed the focused application suite, type checks, formatting, and production builds in [run 32962736080](https://github.com/con/orinoco-lite-dev/actions/runs/32962736080). The [current post-acceptance deployment and rollback evidence](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/50#issuecomment-5433725958) is recorded with its implementing pull request. |

These coordinates identify the released interface and final Milestone 5 integration.
Independent consumers select their own immutable release coordinates; this record does not track ongoing downstream adoption.

## Source-adapter evidence

Focused engine and integration tests cover additions, modifications, deletions, accept, reject, defer, material-change reopening, all-rejected review, human correction, exact-head failure, three-way reversal, overlap failure, compact cache pruning, provenance splitting and joining, and identical-source idempotence for both adapters.

The real `dump-research-info` path completed the whole transition:

1. [source pull request 27](https://github.com/con/dump-research-info/pull/27) corrected source semantics and merged as `d498f20b494529d8a082dd3e8221fac2e818716e`;
2. the multi-root adapter and released interface were integrated through [consumer pull requests 36](https://github.com/con/test-orinoco-downstream-website/pull/36) and [37](https://github.com/con/test-orinoco-downstream-website/pull/37);
3. [demonstration pull request 19](https://github.com/leej3/orinoco-lite-demo/pull/19) received a complete authenticated 82-record decision submission, finalized with the human reviewer as author, and merged through an ordinary merge commit as `8cb24b6c29065ed63d081d4c33a2da0d961fe484`; and
4. [same-source run 33002386512](https://github.com/leej3/orinoco-lite-demo/actions/runs/33002386512) passed its explicit empty-proposal step and skipped branch, commit, artifact, and pull-request creation.

The later adapter-provenance identity correction was reviewed in engineering pull request 39, consumer pull request 39, and [demonstration pull request 22](https://github.com/leej3/orinoco-lite-demo/pull/22).
The successful no-op run used that corrected current default-branch behavior.

Git and the trusted workflow enforce the required proposal/review/finalization history.
This acceptance record does not duplicate the complete ancestry or every transient artifact digest in prose.

## Zotero evidence and disposition

Focused tests prove Zotero acquisition, transformation, PAV ownership, candidate review, finalization, suppression, reopening, and idempotence against the shared contract.
Historical [demonstration pull request 7](https://github.com/leej3/orinoco-lite-demo/pull/7) also produced a real 126-record proposal, an exact-head review artifact, and a cross-platform-valid proposal tree from Zotero library version 451.

That pull request was closed without merge as superseded on 2026-08-26; none of its proposed metadata was accepted.
It was not rebased because the proposal is intentionally bound to its original metadata base and source coordinate.
Milestone 6 regenerates from the current default branch and current read-only Zotero coordinate, completes review and finalization, and verifies a same-source no-op.

## SHACL Vue evidence and disposition

The released editor continues to download the normal version 2 review bundle.
Focused engine, application, workflow, and consumer tests cover exact-head input, immutable released editor assets, explicit public-data acknowledgment, bounded temporary handoff, trusted canonical conversion, exact replacement, joined validation, stale-head failure, and a final branch without the bundle.

Authenticated browser evidence also verified the exact-head wrapper, normal editor controls, and guarded **Propose via GitHub** action.
A complete live write/replacement was not needed to accept the implemented profile.
The first live proposal and a visible choice between credential-free download and the authenticated wrapper are Milestone 6 acceptance items.

The downstream site's credential-free `/edit/` page and the central application's authenticated `/edit/` wrapper are intentionally different surfaces.
Being signed in does not add a GitHub button to the static page.

Those two sentences preserve the accepted Milestone 5 deployment evidence; they are not the current presentation contract.
HR-227 and M6-D005 subsequently supersede the duplicate central-editor surface.
The downstream static site is now the only SHACL Vue editor and exposes both **Download bundle** and **Propose via GitHub**; the central service is limited to a lightweight sign-in, confirmation, and bundle-receiver page before the retained fixed-path handoff and trusted replacement.

## Boundaries retained

- Source acquisition remains read-only and no workflow writes to Zotero or `dump-research-info`.
- Automation never chooses a disposition, approves, merges, deploys, or changes production content.
- The hosted application retains no metadata, candidates, decisions, bundles, source payloads, or durable credentials.
- Pull-request code is treated as data by trusted default-branch workflows.
- The real CON site, its remotes, Pages configuration, deployment, DNS, and domain were not changed.
- No persistent metadata service, candidate inventory, event ledger, transaction graph, or extra semantic overlay was introduced.

## Follow-on work

The pre-Milestone 6 boundary in [`milestone-6.md`](milestone-6.md) owns upstream repinning, resulting compatibility fixes, the aligned release, and the separately authorized organization migration.
Milestone 6 begins afterward with general upstream-compatible open references, hermetic compatibility CI, the current Zotero operation, and SHACL proposal discoverability and live use.
The corpus-normalization proposal remains site-owned content review and is not an engineering milestone or downstream-adoption gate here.

### First convergence batch

[Engineering pull request 44](https://github.com/con/orinoco-lite-dev/pull/44) records the first deliberate pre-Milestone 6 upstream update.
The accepted component reviews are [query-things pull request 1](https://github.com/leej3/query-things/pull/1), [things-enrichment-tools pull request 1](https://github.com/leej3/things-enrichment-tools/pull/1), [SHACL Vue pull request 1](https://github.com/leej3/shacl-vue/pull/1), [pool UI pull request 1](https://github.com/leej3/pool.psychoinformatics.de-ui/pull/1), [www-from-model pull request 1](https://github.com/leej3/www-from-model/pull/1), and [Congo pull request 11](https://github.com/leej3/congo/pull/11).

Repository-owned commits were rebased onto authoritative upstream heads, and the mirror default branches were advanced directly to the resulting linear histories.
The accepted parent gitlinks are query-things `2383c51a81d1f0f623231c1e52fc8ea0fa747fb1`, things-enrichment-tools `9f036a4cdfb53f87346152f9cd4620aaef38bce2`, pool UI `c353e0b631d0110d5a36a7ee3cec9cd5606720ca`, and www-from-model `aa297506916373755e05ffd33ccf78624dccd2dd`.
The nested accepted heads are SHACL Vue `2d3673e0a3bd1054f41c303bc7faa4111277c2d0` and Congo `574506bb48a48740219183177fa77edfd699f035`.
Dump Things client `1e79391195ad4412286344189dc5f81a06accb90`, Dump Things service `9f101d97c7f15d491f602db5a9c33ad9a19ad8bf`, and Things Schema `cb6c791aec4c5309775437df4bd58e94e1bfcc3c` were already at their authoritative current heads and remain unchanged.
The website's Annex metadata is pinned independently at `d18f512d1cd722a8300b656c330020739da05be6`, which makes the regenerated graph object available to a fresh clone.

Current Congo requires Hugo 0.158 or newer, so the exact engineering, trial, and release-source runtime moved together to Hugo Extended 0.161.1.
The static build produced 3,501 pages with no URL-audit violations, and the full service-backed acceptance round-tripped 5,014 records exactly through both isolated collections before proving the Dump Things, Git Annex, SHACL Vue, and site endpoints healthy.

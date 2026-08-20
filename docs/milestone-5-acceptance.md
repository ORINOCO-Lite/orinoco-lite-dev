# Milestone 5 acceptance record

Status: active; implementation evidence pending

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
| Specification | reviewed pull request head and merge commit establishing the normative contract and accepted M5 decisions | pending |
| Engineering | exact base, released engine/runtime inputs, upstream pins, clean worktree, and baseline tests | pending |
| Zotero | exact library version, adapter revision, policy revision, and baseline behavior | pending |
| `dump-research-info` | exact source revision, adapter revision, policy revision, and baseline behavior | pending |
| Consumer | exact base, lock, template release, corpus counts, branch policy, and baseline CI | pending |
| Template | exact source release and generated-template commit if generic support changes | pending |
| Platforms | macOS ARM64 and Linux x86-64 clean-clone commands and results | pending |

Live-source or authoritative-head drift is advisory and must not silently replace a reviewed input.

## Shared metadata foundation

| Requirement | Evidence | Status |
| --- | --- | --- |
| Canonical ordering | Focused parity with pinned Dump Things mapping ordering and YAML serialization, including idempotence and preserved list order | pending |
| Corpus normalization | Separate reviewed pull request showing the one-time canonicalization-only diff | pending |
| Annotation selectors | Exact path/hash matching rejects missing or ambiguous assertions | pending |
| Joined validation | Record plus annotation overlay validates as one Thing with the locked schema | pending |
| RDF round trip | Expanded PAV survives JSON-to-RDF-to-JSON without semantic loss | pending |
| Projection | Joined annotations reach the machine projection while configured public views remain unaffected | pending |
| Human-facing storage | Record YAML contains no machine-only PAV and the overlay contains no copied record or decision history | pending |

## Adapter behavior matrix

Each row requires focused tests for both adapters and at least one reviewed GitHub execution across the combined evidence.

| Case | Required result | Zotero | `dump-research-info` |
| --- | --- | --- | --- |
| New claim | A friendly record entry and actual metadata diff are presented for explicit review. | pending | pending |
| Accept | The reviewed proposal remains, the compact cache records acceptance, and an identical rerun is a no-op. | pending | pending |
| Reject | The baseline is restored, the compact cache records rejection, and the unchanged claim stays suppressed. | pending | pending |
| Defer | The baseline is restored and the claim returns on the next adapter proposal. | pending | pending |
| Material source change | A changed metadata-affecting source claim returns for review. | pending | pending |
| Unused source change | A source change that cannot affect generated metadata produces no candidate or metadata diff. | pending | pending |
| Human correction | An accepted human edit is attributed, removes replaced machine PAV, and is not reverted by an unchanged source claim. | pending | pending |
| Deletion | The record and matching annotation companion are visibly proposed for deletion and accept/reject behave normally. | pending | pending |
| All rejected | Final metadata matches the base while the compact decisions and reviewed proposal lineage survive the merge. | pending | pending |
| Existing PAV | A semantically identical assertion retains its current PAV and produces no provenance-only diff. | pending | pending |
| Adapter rerun | Generation cannot overwrite an explicit human disposition or unrelated human metadata. | pending | pending |
| Missing or malformed decision | Finalization stops with a focused diagnostic and does not infer a disposition. | pending | pending |
| Adapter overlap | Independent claims remain visible, preserve their own identities/PAV, and neither cache suppresses the other. | pending | pending |

## GitHub profile

| Requirement | Required evidence | Status |
| --- | --- | --- |
| Proposal | Default-branch dispatch opens one draft pull request whose first commit is an inline `datalad run --explicit` metadata proposal. | pending |
| Review interface | Pull-request body shows friendly per-record controls without opaque hashes as the primary identifier. | pending |
| Complete decision state | Exact `/curation submit` rejects missing, duplicate, unknown, or stale record decisions. | pending |
| Human modifications | Comments, direct commits, and a SHACL Vue bundle can produce attributed, validated metadata changes on the same branch. | pending |
| DataLad boundary | Programmatic metadata changes use the project Pixi/DataLad task; decision-cache-only commits use ordinary Git. | pending |
| Attribution | Each bot commit uses the most recent triggering human as author and automation as committer. | pending |
| Trusted execution | Write credentials are not exposed to pull-request executable code or source data. | pending |
| Exact-head update | Automated writes use the observed pull-request head and fail on a concurrent change. | pending |
| Correction | A pre-merge correction remains on the same pull request and finalization reruns against the new head. | pending |
| Merge preservation | The default branch permits a merge commit and retains the exact proposal and human-review commit objects. | pending |
| Conflict handling | A conflicting proposal is regenerated from the new base; a clean non-overlapping proposal is not. | pending |
| Human authority | Automation never chooses a disposition, marks review ready, approves, merges, deploys, or writes to the source. | pending |
| Public retention | The proposal discloses that rejected public metadata remains in Git history and requires acknowledgment before publication. | pending |
| No local requirement | An authorized reviewer completes the normal workflow entirely in GitHub. | pending |
| Complexity boundary | No tracked inventory, review document, manifest, sidecar, reconciliation report, custom journal, or attestation graph is introduced. | pending |

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

# Milestone 5 implementation report

Status: technical implementation complete; formal acceptance pending human and hosted gates

Started: 2026-08-18

Technical implementation completed: 2026-08-18

Engineering branch: `codex/milestone-5`

Consumer branch: `codex/milestone-5`

Template branch: `codex/milestone-5`

## Purpose and documentation boundary

This report records Milestone 5 implementation choices, deviations, commands, test evidence, and proposed decision outcomes while preserving the planning documents supplied by the reviewer.

The following source documents remain unchanged:

- `docs/milestone-5.md`;
- `docs/milestone-5-decisions.md`;
- `docs/milestone-5-acceptance.md`;
- `docs/source-adapters.md`; and
- `docs/human-review-decisions.md`.

The implementation interprets the request to implement Milestone 5 as authorization to activate engineering work on isolated branches.
It does not interpret that request as a human disposition for any source candidate, as acceptance of M5-Q001 through M5-Q007, or as authorization to approve, merge, deploy, or modify the read-only production-site repository.

Keeping evidence here instead of editing the original decision and acceptance registers is an explicit documentation-location deviation requested for this implementation.
Formal milestone acceptance will still require a human to review the final evidence and record the accepted outcomes in the authoritative registers, or explicitly accept this report as their replacement.

## Scope and ownership

The implementation changes:

- the test consumer for the two site-owned adapter vertical slices, durable decision state, transaction tests, and complete downstream regression; and
- this engineering repository for activation evidence and this report.

The template adds update-preservation acceptance for site-owned adapter policy and a generic test-runner isolation fix demonstrated by the complete concurrent consumer gate.
It does not receive the curation prototype or a new managed adapter surface.
`dump-research-info` remains an exact, read-only source checkout unless a source-specific defect is demonstrated.
The production `centerforopenneuroscience.org` repository and all of its local and remote state remain read-only.

## Activation baseline

### Engineering

- Integrated implementation base: `2d32c4b7f470317291b868906e461cbf8bdcedff`.
- Base tree: `b5ab5a94db96723bbaf3d064202f71ac9b2824fd`.
- Planning parent named by the original plan: `68b0ec1e0d70b9247d94091ae0754550074ae14e`.
- The planning parent was integrated through a rebased, tree-equivalent commit rather than as an ancestor of current `main`; both coordinates are retained instead of substituting one silently.
- Host: macOS 26.5.2 ARM64; Pixi 0.76.2.
- Baseline command: `pixi run test`.
- Result: 50 engine tests with 3 unavailable-fixture skips and 40 development tests passed.

### Consumer and released interface

- Planning snapshot: `1d7962720eaa3021ffe0a6cd52ac0694be47cffd`.
- Activated current default-branch base: `53a0d1be2f200f76901cc7e65b8bfb3ad72d9a3b`.
- Activated base tree: `ebc8eb10f0e98035f01154a25b674a9a4c78d6c8`.
- The intervening commit adopts template `v0.1.15`; it does not change the engine/runtime release or source-adapter implementation.
- Engine wheel: Orinoco Lite 0.1.12, SHA-256 `7bcba4c4124873d5a985233c4fef84aa3cd3902dfa401bbdfefb951785c36173`.
- Runtime archive: 0.1.12, SHA-256 `0d43cf6b3db4c324777a373c7d2178ab8dcdaf224795f19b4ce2c16e8f114a5a`.
- Runtime manifest: SHA-256 `4751bab7bfe5fa65bdc95499aff05a77b48de2f7f194270293865d6f25ab200f`.
- Reusable workflow: `fe01e297d3d22d1690bf891b40eaab36595cea9e`.
- Template source release: `v0.1.15`, source commit `bea66d916da3791fe3820498aca676c8b64a585d`, tag object `ca8c78070e7a9fed291db662c43026d2cac65ac4`.
- Published `github-template` remains `92ce600d2a0428169d94d9ad71bd438230d48558`, generated from `v0.1.14`.
- Baseline command at the activated consumer base: `pixi run test`.
- Result: all 46 site-owned Python tests passed.
- Hosted validation run `32191740068` passed at the activated base on both macOS 14 ARM64 and Linux x86-64.
- Hosted Pages run `32191739405` passed at the activated base.

### Source fixtures

- Zotero public group: `6197458`.
- Reviewed Zotero library version: `451`.
- Reviewed snapshot: 5 collections and 197 top-level items.
- Snapshot file SHA-256: `e824d6e007aeed49c36caa84d60d0458a882425b6fbdd69a18505ac8dbc6b28c`.
- Snapshot semantic-content SHA-256: `5e0f5fe1d68c18214110a37c24a8e9177dc484f64a1d9d832f322b477bfef20d`.
- `dump-research-info` revision: `062da59cb5a00ca128b3df895426a54088bfc625`.
- `dump-research-info` tree: `3d3bee9caa4520bf5615d5754f13fa0093bcb322`.
- `dump-research-info/data/con_site` tree: `fdc048901927ef731a41af0a5b37e5b1a54ec2a2`.
- Both source fixtures were clean at activation.
Normal acceptance must remain independent of live Zotero, credentials, git-annex, and a persistent service.

### Classified drift and negative evidence

- A read-only Zotero API check on 2026-08-18 reported library version `668` and 190 top-level items.
That is advisory live-source drift only.
The implementation continues to propose from the exact reviewed version `451` fixture and does not refresh or combine it with live state.
- The existing consumer proposal branch at `9cbed0b` is not an implementation base.
It contains 218 records rather than the accepted 199-record corpus, combines unresolved person, grant, and venue changes, and its two platform checks fail.
It is retained only as evidence that unconditional materialization is unsafe.
- The consumer currently permits merge commits, squash merges, and rebase merges.
Its `main` branch requires linear history, one approval, approval of the latest push, and dismissal of stale approvals.
Any accepted transaction must therefore retain its complete inventory, decisions, reconciliation report, and DataLad sidecar in the final tracked tree instead of relying on intermediate proposal commits to survive a squash or rebase.
This implementation branch retains only synthetic format and squash evidence because publication of the real artifacts remains a human privacy and retention gate.

## Design and decision ledger

The implementation will record evidence for M5-Q001 through M5-Q007 here, but will label every outcome either `proposed`, `not activated`, or `human accepted`.
Codex-authored evidence cannot turn a proposal into the last state.
Source candidate decisions likewise require explicit human input; tests may use clearly synthetic reviewer identities and rationales without asserting a real content decision.

No W3C PROV or SSSOM representation is activated at baseline.
Git/DataLad, PAV assertion annotations, and tracked human disposition state remain the minimum provenance split to test.

The implementation currently treats all candidate, decision, and command surfaces as explicitly versioned, site-owned prototypes.
Proposal paths are relative to `metadata/records/`, and reconciliation must reject absolute paths, parent traversal, stale fingerprints, incomplete transaction coverage, and ambiguous links before replacing the canonical tree.

The following outcomes are implementation proposals, not accepted decisions:

| Gate | Proposed implementation outcome |
| --- | --- |
| M5-Q001 | A deterministic, content-addressed YAML inventory transports one complete adapter proposal. Exact source and policy inputs participate in its identifier. Inventories remain noncanonical review envelopes and are not retained on the integration branch until a human accepts their public-repository privacy and retention policy. |
| M5-Q002 | A site-owned, prototype-versioned YAML ledger records immutable decision events and the exact inventory transactions that anchor them. Generation cannot write the ledger. No predecessor or compatibility promise is activated. |
| M5-Q003 | Reconciliation requires a complete active decision event for every inventory candidate, a current-baseline compare-and-swap, locked-schema staged validation, an exclusive local transaction, and rollback or explicit interrupted-run recovery before a whole-tree activation. Tracked inventory, ledger, reconciliation report, and DataLad sidecar evidence are intended to survive the consumer's squash/rebase-capable merge policy. |
| M5-Q004 | Every decision event requires reviewer identity, decision date, rationale, and nonempty evidence. The prototype validates presence and retention but deliberately does not decide who is authorized to approve. |
| M5-Q005 | Not activated. The demonstrated audit questions are answered by tracked transaction state, Git/DataLad execution evidence, and PAV assertion provenance. |
| M5-Q006 | Not activated. No genuine ontology-mapping case was found; entity linkage and rejection remain decision semantics rather than SSSOM mappings. |
| M5-Q007 | Keep the common curation semantics, tests, and command facade as a site-owned prototype. Do not release an engine API or template-managed adapter. The template receives generic proofs that normal updates preserve site-owned decision and crosswalk bytes, plus a framework-owned test-runner fix that prevents bytecode caches from entering concurrent validation inputs. |

The candidate and decision formats contain complete proposed/baseline records and human audit prose.
The underlying test corpus and frozen source fixtures are already public, but that fact does not settle future-source privacy, reviewer privacy, or long-term retention.
For that reason, real inventories and reviewer decisions are generated only as ignored local evidence during this implementation; they are not committed as durable policy before M5-Q001, M5-Q002, and M5-Q004 receive human review.

## Progress log

### 2026-08-18 — activation and baseline freeze

- Created isolated engineering and consumer worktrees from their current reviewed default branches.
- Reconciled the plan's consumer snapshot with the subsequently merged template `v0.1.15` update.
- Reproduced the engineering and consumer unit-level baselines.
- Confirmed that no original planning or acceptance document was modified.

### 2026-08-18 — source-adapter preparation

- Consumer commit `0299f71` makes literal relative `dump-research-info` checkout paths resolve from the downstream repository root.
The focused adapter suite passed all 10 tests, and a review against `../dump-research-info` at the frozen revision completed without copying the source into the consumer.
- Consumer commit `9c52e42` exposes the existing dump adapter's deterministic materialization plan separately from its legacy write step.
The same 10 focused tests pass, and the proposal layer can now reuse the transform without mutating canonical metadata.
- The frozen dump source currently produces 82 transformed records: 19 are source-only and 63 overlap existing canonical records.
These counts describe review candidates, not accepted content changes.

### 2026-08-18 — provenance and update-preservation evidence

- Consumer commit `8f4e404` adds locked Orinoco Lite 0.1.12 acceptance for expanded keyed PAV annotations.
PAV round-trips on a whole record and on `dlthings:Attribution`, `dlthings:AttributeSpecification`, `dlthings:Identifier`, and `dlthings:Generation` assertions.
Compact nested input normalizes to the expanded form and fails the native semantic fingerprint check rather than publishing changed semantics silently.
- Consumer commit `98ea669` composes the guarded reconciliation transaction, the exact locked 0.1.12 validator, JSON/RDF round-trip, and projection in one acceptance test.
A top-level imported-record PAV annotation survives the reconciled YAML and exact `records.jsonl` machine projection while the public page and graph bytes remain unchanged.
Counts remain 199 records, 185 pages, 186 graph nodes, and 467 graph edges.
- Template commits `baee9a3`, `d7edba7`, and `c4c593f` add only an updater preservation test and align its fixture with the final immutable decision-event format.
A normal framework update retains a syntactically representative prototype decision ledger and a site-owned crosswalk byte-for-byte, with no site-owned path reported as changed.
- The template does not receive the curation implementation, a managed adapter, or a new released interface.

### 2026-08-18 — two-adapter proposal evidence

- The frozen Zotero fixture deterministically produces 126 whole-publication candidates without changing canonical metadata.
Stable source identity uses `item:<key>` for one source item and a sorted `items:<keys>` identity for a merged group.
The DOI, transformed PID, path, and output remain material, so correcting a DOI reopens the same claim rather than creating a new identity.
A publication merged from multiple Zotero items retains every item key in the source material and one deterministic API query URI for assertion provenance.
- The exact clean `dump-research-info` checkout deterministically produces 82 candidates from the literal `../dump-research-info` path.
Seventy-six candidates carry one or more unresolved-relation blockers, representing eight unique unresolved target PIDs; reconciliation rejects an accept event until those blockers are resolved.
- Checkout relocation, a run-identifier change, and an unrelated source-repository commit leave dump candidate identities, fingerprints, and proposed records unchanged.
A material source-record change preserves candidate identity and changes the material fingerprint.
- The adapters propose the same six canonical publication paths.
Their candidate identities remain source-specific, both proposals remain visible, and reconciling either proposal makes the other's captured baseline stale until it is reproposed and explicitly reviewed.
- PAV uses stable source-record and software-agent URIs.
Exact snapshot digests, Git commit/tree coordinates, and provider/transformer hashes remain separate inventory inputs so execution provenance is exact without turning an unrelated commit or implementation comment into a material source change.

### 2026-08-18 — durable prototype and transaction safety

- Consumer commit `e2bc134` adds the adapter-neutral, explicitly versioned `curation-*-prototype-v1` core and behavior vectors for both adapter identifiers.
Candidate identity excludes run identifiers while the material fingerprint binds the source material, relevant policy, destination path, complete proposed record, and captured baseline.
- Durable decisions are immutable events with a stable claim-revision identity, a unique decision-event identity, explicit supersession, and exact inventory-transaction anchoring.
Only the active nonbranching chain tip can affect evaluation or reconciliation; historical events remain retained but cannot be replayed.
The model supports accept, reject, link, defer, permanent exclusion, and supersede, including material/policy return, explicit dates, resolved-policy-question context, wildcard permanent scope, and `v1 -> v2 -> v1` source reversion without deleting history.
- Consumer commits `9e9e45a` and `c8caa77` bind the dump and Zotero providers to those shared safety semantics while retaining their source-specific identity and material rules.
Consumer commit `f757602` makes transaction inventory coordinates strict full SHA-256 identities.
- Consumer commit `62295c5` adds the guarded command facade for proposal, decision rendering, reconciliation, interrupted-tree recovery, stale-lock recovery, and report-reservation recovery.
Proposal cannot write canonical metadata or the decision ledger.
Reconciliation requires complete transaction-local decisions and invokes the exact locked 0.1.12 semantic validator on the staged full corpus before activation.
- The canonical transaction uses an exclusive sibling lock, exact baseline compare-and-swap, symlink and duplicate-PID rejection, pre-validation and pre-activation tree-digest checks, staged and installed digest checks, atomic whole-tree rename, rollback authority, and explicit crash recovery.
Append-only report journals are prepared before mutation, finalized under the same lock, and recoverable only when exact canonical digests and artifact sets match.
Recovery evidence uses logical repository-relative paths rather than host paths.
- Consumer commit `a97ba32` creates and revalidates fresh ignored provider-output directories, so the documented first-run Zotero command needs no manual setup.
Consumer commits `058afa1` and `11379e4` add the prototype operator guide and make its first-run commands independent of a nonexistent future decision ledger.

### 2026-08-18 — exact local proposal evidence

The following real inventories were generated twice with explicit `--as-of 2026-08-18`, no decision ledger, and no resolved policy questions.
Both reruns reproduced the same inventory identifier and exact file SHA-256.
They were summarized and moved to Trash after the comparison rather than retained in public history before the privacy and retention gates are reviewed.
Canonical `metadata/records/` remained unchanged and the consumer worktree returned clean.

| Adapter | Candidates | Blocked | Inventory ID | File SHA-256 | Bytes |
| --- | ---: | ---: | --- | --- | ---: |
| Zotero v451 | 126 | 0 | `curation-inventory-v1:d7230a3523277dad2b975226ab091bd95c8a1d7e607fcd286ce5d1f1f272012e` | `34a5a5c8c1494d39aa7dd43561c8719862503fe81737108bef197bac8c51a461` | 467153 |
| `dump-research-info` `062da59` | 82 | 76 | `curation-inventory-v1:d2edc26f13ecd586ba18a1ff53680e6f55c1d03b75eac97989fc2e9b2e635a46` | `8c0fceecefe3544af6d3a670cd873196518800de37f4d5728df62f9c1ce2766a` | 195071 |

The Zotero set contains 120 single-item and 6 deterministic multi-item source identities.
The dump set retains 8 unique unresolved target blockers across its 76 blocked candidates.
The two proposals overlap on exactly 6 canonical paths; neither provider suppresses the other, and the captured baseline makes an out-of-order second reconciliation stale.

### 2026-08-18 — DataLad and squash-retention evidence

- Consumer commit `63c221b` adds a synthetic all-rejected transaction that runs in a nested ordinary Git repository through the project-local DataLad 1.6.2 and git-annex 10.20260420 environment.
It records one content-addressed inventory, one explicit synthetic reject event ledger, one no-change reconciliation report, and one compressed DataLad run sidecar.
- The test squashes the run branch locally, deletes the branch, expires all reflogs, prunes the original run commit, and then reparses every retained curation artifact and the sidecar.
The squash tree equals the run tree at `c19df5d2fd6b3ad34d994ce5e3ffd2c54e1f30dc`; the four retained evidence files have aggregate SHA-256 `adfcc7351b24c409109da0a7d5808bd1a298e6eeef9769d83dde80b2abcb2e27`, and the sidecar SHA-256 is `29aeb2f49bbd3490c1f4f4c1c3f3fc18dd3f6801236dce774859381a5c54b1d6`.
The canonical change count is zero.
- Consumer commit `06a3450` moves the nested test repository under ignored build scratch and asserts the ignore rule, preventing transient execution evidence from contaminating concurrent validation, build, or browser tasks.
- This proves the local Git tree semantics of the repository's enabled squash mode and that sufficient evidence can survive without the intermediate run commit.
It does not prove a server-generated GitHub squash, human final-head review, branch-protection enforcement, or a reviewed default-branch transition; those remain external acceptance gates.

### 2026-08-18 — concurrent full-gate isolation

- A clean-clone `pixi run test-all` exposed a phase-dependent source-adapter inventory even though the command exited successfully: pre-test validation saw 30 files at digest `ccd9c7f98d092e436b3b8f5ebec38aa9c1c4ba18bf17cdf232e50913b6d0d472`, while concurrent builds saw 8 additional ignored `__pycache__/*.pyc` files and digest `f1ff0f02f8dc40f7768af2b592b738a8d17349fd0eff98a4f9f1afb149ae792e`.
- Template commit `d2b11ae` makes the generic site-test runner disable bytecode for in-process imports and inherited child Python processes.
A focused template test proves both paths create no cache directory or bytecode file, and the rendered `github-template` runner remains byte-identical to the Copier source.
- Consumer commit `a82d1ae` applies the same framework-owned runner bytes on the integration branch.
This is a generic concurrent-test isolation correction, not extraction or distribution of the curation prototype.

## Acceptance coverage

`Implemented` below means that deterministic code and local test evidence exist.
It does not mean that a human made a real source disposition or accepted a Milestone 5 policy gate.

| Required case | Implemented evidence | Formal residual |
| --- | --- | --- |
| No prior decision | Both frozen providers emit deterministic visible candidates. | No reviewed transaction coordinate. |
| Accepted unchanged record | Shared-core vectors exercise positive-state suppression for both adapter identifiers. | No real-provider accepted ledger and rerun. |
| Accept disposition | Reconciliation and idempotent accepted rerun are covered. | No real content acceptance. |
| Unchanged rejection | Unchanged rejection suppression is covered for both adapter identifiers. | No human rejection. |
| Non-material source change | Shared vectors and the real dump context-only commit case keep the decision effective. | No real Zotero decision lifecycle. |
| Material source change | Shared vectors, a dump material change, and a Zotero DOI correction reopen the same stable claim. | No real changed claim reviewed again. |
| Unrelated policy change | Shared vectors keep the prior decision effective. | No real provider-policy transaction. |
| Relevant policy change | Shared vectors reopen the affected claim. | No real provider-policy transaction. |
| Run-identifier change | Run identifiers do not re-key shared claims; the dump provider also proves this directly. | No reviewed transaction; Zotero has no run-ID input. |
| Deferral | Material, policy, date, and resolved-question return conditions are covered, including event re-review. | No human deferral. |
| Permanent exclusion | Explicit bounded and wildcard scopes, material changes, policy changes, and ambiguity are covered. | No human broad-scope decision. |
| Link to existing | Valid link targets suppress duplicate creation. | No real provider linkage review. |
| Ambiguous link | Ambiguity fails closed. | Adapter-specific evidence is synthetic. |
| Supersede disposition | Active-event and replacement relationships are validated. | Adapter-specific evidence is synthetic. |
| All rejected | A synthetic decision-only transaction and DataLad squash leave canonical metadata unchanged. | No real Zotero/dump review or default-branch transition. |
| Missing disposition | Incomplete current coverage fails closed; absence is never rejection. | No real transaction. |
| Pull-request closure or abandoned proposal | Discarding a proposal without a durable event leaves the claim undecided. | No actual closed pull request. |
| Malformed decision | Strict parsing rejects malformed identities, fields, conditions, and anchors. | No reviewed adapter transaction. |
| Contradictory decisions | Branching, conflicting, ambiguous, and unbound events fail closed. | No reviewed adapter transaction. |
| Stale transaction-bound decision | Material/policy drift reopens review and a superseded inventory cannot replay an old acceptance. | No real changed-source transaction. |
| Source disappearance | Dormant historical events remain parseable and are not discarded as unused. | The retention policy remains human-unreviewed. |
| Unexpected transaction-local decision | Exact candidate coverage rejects extra active events while dormant history remains valid. | No real transaction. |
| Identical rerun | Both real inventories reproduce byte-for-byte; reconciliation vectors produce no second metadata diff. | No real reviewed reconciliation rerun. |
| Deleted cache | Decisions and canonical state are independent of provider output and cache paths. | No retained real ledger. |
| Adapter rerun | Generation cannot write or replace the append-only decision authority. | No retained real ledger. |
| Metadata boundary | Inventory and ledger fixtures remain outside `metadata/records/` and are absent from Things projection. | Public retention/publication policy remains open. |
| Framework update | Normal Copier update preserves representative site-owned policy, crosswalk, decision events, and transaction anchors byte-for-byte. | Long-term authority remains human-unreviewed. |
| Adapter overlap | Both real proposals retain all 6 overlapping paths and captured baselines make out-of-order application stale. | No reviewed resolution order or outcome. |
| One-PR transaction | Branch-local proposal, decision, reconciliation, final-state, and no-follow-up mechanics are testable through one tree. | No actual pull request, human final-head review, or merge. |
| Interrupted reconciliation | Crash windows, stale lock, staged/installed digest races, rollback failure, and explicit report/tree recovery fail closed. | No real reviewed transaction. |
| Actual merge mode | The complete synthetic evidence tree survives local squash after the run commit is pruned. | No GitHub-generated merge or default-branch transition. |
| PAV round-trip | Guarded reconcile, locked validation, JSON/RDF round-trip, `records.jsonl`, and public-output policy pass end to end. | Current-head hosted platform execution remains. |
| Decision audit fields | Reviewer identity, date, rationale, and evidence are required and retained in immutable events. | Reviewer authority and a real reviewer event remain open. |

## Formal residual gates

The implementation cannot make the following choices or external transitions on behalf of a human reviewer:

- accept M5-Q001 through M5-Q004 or M5-Q007;
- record reviewed not-activated outcomes for M5-Q005 and M5-Q006;
- approve public retention of complete inventories, reviewer identities, rationale, evidence, and dormant source history;
- decide who is authorized to review, accept broad permanent scope, or resolve source content and overlap cases;
- retain real decision ledgers or reconcile real candidate records without those dispositions;
- open, review, approve, or merge the required one-pull-request transaction;
- prove the repository's server-generated merge result and protected default-branch transition; or
- produce current-head hosted macOS 14 ARM64 and Linux x86-64 results without publishing the branches.

The original decision, acceptance, source-architecture, and human-review documents therefore remain unchanged and continue to report their formal gates as pending.
The separate report is evidence and a proposed set of outcomes; it is not a substitute for human acceptance unless a reviewer explicitly makes it one.

## Final clean-clone acceptance

All final local acceptance commands ran from ordinary, no-hardlink clones of the isolated branch heads.
Each clone ended with empty `git status --porcelain=v1` output.

| Repository | Exact tested head | Command | Result |
| --- | --- | --- | --- |
| Consumer | tested commit `31bfa7f78fcb51218695a9eaa4d7f5945f8b2625`; final message-normalized commit `a82d1ae6b194addb0fa07fcbe3d19a76844c9154`; identical tree `c6056d1d06e2bb7b40a41f8250266fb6054bbb53` | `pixi run test-all` | 131 site-owned Python tests, 2 Chromium tests, and 2 WebKit tests passed; runtime 0.1.12 verified; projection remained 199 records, 185 pages, 186 nodes, and 467 edges. |
| Engineering | `50d95510e82e55bb24daf7c02f0389cf314e80db` | `pixi run test` | 50 engine tests passed with 1 expected unavailable-fixture skip; 40 development tests passed with only Things Schema `cb6c791aec4c5309775437df4bd58e94e1bfcc3c` initialized. |
| Template | tested commit `959f2ec2887d9cb9d3212714072494445e041f49`; final message-normalized commit `d2b11ae8ae00da707da3e1bfb78d35893722429e`; identical tree `0af779bb859cebb298d0edf25cd953ec02abd323` | `pixi run check` | Rendered `github-template` current; 62 tests passed. |

The decisive consumer run started and ended with zero source-adapter bytecode files.
Pre-test validation, the normal build, repeat build, browser build, and explicit post-test validation each observed exactly 30 source-adapter files and the identical digest `ccd9c7f98d092e436b3b8f5ebec38aa9c1c4ba18bf17cdf232e50913b6d0d472`.
The two normal builds produced identical manifest SHA-256 `6cfae44cb4546c64879208c636834700bba6e1a5752913828cb1b4ce93207fa0` and a deterministic 561-file tree at `a5e1a699cb2bb86be5b9d16a8869aca03c15297a80bada4474df9d34a107bc09`.
The browser-build manifest SHA-256 was `a8a0a25cde1867500e771a78911277d1104e89bcbbce077c6cd48fe438f98df7`.

These are local macOS 26.5.2 ARM64 results.
The activated baseline's hosted macOS 14 ARM64 and Linux x86-64 runs remain valid for `53a0d1b`, but no Milestone 5 branch exists on the remotes and therefore no hosted current-head result or pull-request review coordinate exists.

## Final coordinates and rollback

| Surface | Implementation coordinate | Rollback coordinate |
| --- | --- | --- |
| Engineering evidence before this final report | commit `50d95510e82e55bb24daf7c02f0389cf314e80db`; tree `8b5d539da98efd49ee75872bc3b22cda82d0ea95` | commit `2d32c4b7f470317291b868906e461cbf8bdcedff`; tree `b5ab5a94db96723bbaf3d064202f71ac9b2824fd` |
| Consumer | commit `a82d1ae6b194addb0fa07fcbe3d19a76844c9154`; tree `c6056d1d06e2bb7b40a41f8250266fb6054bbb53` | commit `53a0d1be2f200f76901cc7e65b8bfb3ad72d9a3b`; tree `ebc8eb10f0e98035f01154a25b674a9a4c78d6c8` |
| Template | commit `d2b11ae8ae00da707da3e1bfb78d35893722429e`; tree `0af779bb859cebb298d0edf25cd953ec02abd323`; rendered tree `46fca459d86249daee2b2478f5ae7dbfd7ce7f3a` | commit `bea66d916da3791fe3820498aca676c8b64a585d`; tree `9303bab510623809f3c0957bf0a788738519731a` |
| `dump-research-info` source | unchanged detached commit `062da59cb5a00ca128b3df895426a54088bfc625`; tree `3d3bee9caa4520bf5615d5754f13fa0093bcb322` | same coordinate; no source write occurred |
| Production site | no branch, ref, file, setting, workflow, deployment, domain, or remote change | unchanged read-only repository |

The final engineering report commit is necessarily the branch head that contains this report and is supplied in the implementation handoff; a report cannot content-address its own commit without changing that commit.
Rollback requires moving only the isolated local implementation branches to the listed parents.
No remote ref, pull request, default branch, release, deployment, Zotero library, or production state was changed.

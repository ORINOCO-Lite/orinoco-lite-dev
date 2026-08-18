# Milestone 5 implementation report

Status: implementation in progress

Started: 2026-08-18

Engineering branch: `codex/milestone-5`

Consumer branch: `codex/milestone-5`

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

The implementation is expected to change:

- the test consumer for the two site-owned adapter vertical slices, durable decision state, transaction tests, and complete downstream regression; and
- this engineering repository for cross-layer fixtures, acceptance automation, and this report.

The template will change only if evidence from both adapters requires a generic framework surface.
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
Milestone 5 therefore retains the complete inventory, decisions, and reconciliation report in the final tracked tree instead of relying on intermediate proposal commits to survive a squash or rebase.

## Design and decision ledger

The implementation will record evidence for M5-Q001 through M5-Q007 here, but will label every outcome either `proposed`, `not activated`, or `human accepted`.
Codex-authored evidence cannot turn a proposal into the last state.
Source candidate decisions likewise require explicit human input; tests may use clearly synthetic reviewer identities and rationales without asserting a real content decision.

No W3C PROV or SSSOM representation is activated at baseline.
Git/DataLad, PAV assertion annotations, and tracked human disposition state remain the minimum provenance split to test.

The implementation currently treats all candidate, decision, and command surfaces as explicitly versioned, site-owned prototypes.
Proposal paths are relative to `metadata/records/`, and reconciliation must reject absolute paths, parent traversal, stale fingerprints, incomplete transaction coverage, and ambiguous links before replacing the canonical tree.

## Progress log

### 2026-08-18 — activation and baseline freeze

- Created isolated engineering and consumer worktrees from their current reviewed default branches.
- Reconciled the plan's consumer snapshot with the subsequently merged template `v0.1.15` update.
- Reproduced the engineering and consumer unit-level baselines.
- Confirmed that no original planning or acceptance document was modified.

### 2026-08-18 — source-adapter preparation

- Consumer commit `c3e689d` makes literal relative `dump-research-info` checkout paths resolve from the downstream repository root.
The focused adapter suite passed all 10 tests, and a review against `../dump-research-info` at the frozen revision completed without copying the source into the consumer.
- Consumer commit `da8568b` exposes the existing dump adapter's deterministic materialization plan separately from its legacy write step.
The same 10 focused tests pass, and the proposal layer can now reuse the transform without mutating canonical metadata.
- The frozen dump source currently produces 82 transformed records: 19 are source-only and 63 overlap existing canonical records.
These counts describe review candidates, not accepted content changes.

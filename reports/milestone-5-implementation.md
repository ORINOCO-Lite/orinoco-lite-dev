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
- Baseline command at the planning snapshot: `pixi run test`.
- Result: all 46 site-owned Python tests passed.
The current activated base is rechecked before the first consumer implementation commit.

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

## Design and decision ledger

The implementation will record evidence for M5-Q001 through M5-Q007 here, but will label every outcome either `proposed`, `not activated`, or `human accepted`.
Codex-authored evidence cannot turn a proposal into the last state.
Source candidate decisions likewise require explicit human input; tests may use clearly synthetic reviewer identities and rationales without asserting a real content decision.

No W3C PROV or SSSOM representation is activated at baseline.
Git/DataLad, PAV assertion annotations, and tracked human disposition state remain the minimum provenance split to test.

## Progress log

### 2026-08-18 — activation and baseline freeze

- Created isolated engineering and consumer worktrees from their current reviewed default branches.
- Reconciled the plan's consumer snapshot with the subsequently merged template `v0.1.15` update.
- Reproduced the engineering and consumer unit-level baselines.
- Confirmed that no original planning or acceptance document was modified.

# Source-adapter design notes

Status: non-normative notes retained from the superseded architecture exploration

The normative contract is [`docs/source-adapters.md`](../docs/source-adapters.md).
This report preserves potentially useful implementation choices without making them requirements.

## Optional operating modes

An adapter may offer `report`, `basic`, or `aggressive` modes when they help communicate review risk.
Their meaning is adapter-specific: each adapter must document its inputs, matching rules, and possible additions, replacements, field removals, or deletions.
These names are not a shared policy model or part of the common adapter contract.

## Source capture and dependencies

Redistributable source snapshots may be committed as ordinary Git files when useful, but they are not required evidence and do not use git-annex by default.
An adapter may keep an independent Pixi manifest and lock when its acquisition or transformation dependencies differ from the site runtime.

Concrete adapters remain site-owned.
A demonstrated reusable adapter could later move to a separately versioned package or template-managed support, but two examples are not enough evidence to freeze a Python ABI, plugin protocol, manifest schema, or host protocol.

## Example-specific observations

The Zotero work was explored as a possible reusable adapter with site-owned mappings and publication policy.
The `dump-research-info` work intentionally exercised ambiguous, overlapping, and CON-specific data and was not treated as a generic Git-to-Things adapter.
These observations describe the prototypes, not permanent adapter categories.

## Superseded directions

The exploration considered tracked candidate inventories, append-only decision events, reconciliation reports, custom transaction recovery, and additional dispositions such as `link`, `supersede`, permanent exclusion, and conditional deferral.
The specification deliberately replaces them with the Git diff, three dispositions, a compact current-state decision cache, ordinary Git recovery, and one annotation-overlay tree.
Git history retains the discarded exploration; implementations should not revive it without a separate reviewed need.

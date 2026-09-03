# Source adapters

This document defines the durable source-adapter contract.
The words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.

## Purpose

A source adapter turns an identified external source into a reviewable Git change to canonical Things metadata.
Acquisition is read-only.
Projection and report-only diagnostics are not source adapters.

The reviewed default branch is curated state.
A proposal branch is temporary review state.
Commits retained on the reviewed default branch record finalized changes; the project does not maintain a second history or candidate inventory.

## Repository layout

Current downstreams use:

```text
site-specific/
  metadata/
    records/
    overlays/annotations/
  curation-records/
  sources/<adapter>/
extensions/source-adapters/<adapter>/
```

- Records contain semantic assertion content.
- Annotation companions contain only machine PAV for assertions present in the corresponding record.
Joining them produces the validation and RDF view.
- `site-specific/sources/<adapter>/` contains source configuration, captured distributable input, and mapping policy.
- `site-specific/curation-records/<adapter>.yaml` contains current decisions.
- Consumer-specific executable adapters live under `extensions/`; reusable adapters belong to the engine or template.
- Credentials, restricted payloads, caches, plans, and generated review output remain untracked.

Configured record roots remain supported.
The engine derives the companion root from the configured record root.

## Adapter run

An adapter run MUST identify its implementation, source coordinate, canonical metadata base, policy, and allowed read and write roots.
Absolute developer paths, credentials, timestamps, and scratch state MUST NOT affect output.

The adapter MUST:

1. validate the declared source model;
2. map each source record to a stable source identifier and canonical PID;
3. hash only normalized source facts that can affect the proposed semantics;
4. derive an untracked deterministic candidate plan;
5. write only canonical records and matching annotation companions;
6. validate every changed record and the complete joined graph; and
7. produce the same output for the same source, base, policy, and decisions.

One shared canonicalizer recursively sorts mapping keys and preserves list order.
Untouched records are not reformatted.
Formatting, unused source fields, and PAV alone MUST NOT reopen review.

Programmatic metadata proposals and finalization changes use the project Pixi task and its DataLad recording path.
DataLad records the run and resulting commit in the downstream Git repository.
The repository MUST be configured so those paths remain ordinary Git content; source-adapter execution MUST NOT require Git Annex or annex adapter outputs.
Direct human edits are ordinary Git commits.

## Candidate decisions

Each candidate is an addition, modification, or deletion with a stable source record identifier, target PID and path, friendly label, baseline, proposal, companion changes, and semantic claim digest.
The plan is reproducible but MUST NOT be tracked.

Every candidate receives exactly one disposition:

- `accept` keeps the reviewed change and attributed human corrections;
- `reject` restores the baseline and suppresses the same unchanged claim; or
- `defer` restores the baseline and asks again on the next run.

Missing input, pull-request closure, or workflow failure is not a decision.
A material source-mapped change reopens review.
An accepted claim with unchanged source semantics is not proposed again merely because a human corrected the stored metadata.

The compact decision cache has format `orinoco-lite-curation-decisions-v1`.
It stores the adapter, authenticated review facts, and one current decision per PID: source record ID, claim digest, disposition, and review reference.
It MUST NOT contain records, diffs, plans, manifests, or an event log.
Git supplies history.

## Human edits and finalization

Humans MAY edit metadata on the proposal branch.
Those edits remain attributable ordinary commits and do not acquire machine ownership merely by sharing the branch.

Finalization MUST:

1. verify one disposition for every candidate against the original proposal;
2. retain attributed human edits;
3. keep accepted changes and restore rejected or deferred changes;
4. update only the compact decision cache as durable review state; and
5. validate records, companions, and the joined graph before committing.

Restoration uses Git three-way semantics.
A clean unrelated edit survives; an overlap stops for human resolution.
Finalization MUST fail rather than overwrite an edited companion or guess between ambiguous assertions.

Automation MUST NOT choose a disposition, approve, merge, deploy, or write back to the external source.

## Assertion ownership and PAV

Machine updates MUST preserve human- and differently owned assertions according to the pinned upstream enrichment behavior.
An unchanged assertion produces no PAV-only diff.
A changed machine assertion may be proposed, but the semantic change remains visible for acceptance.

Every machine-provided assertion object has one companion selector containing:

- an RFC 6901 path;
- the canonical assertion SHA-256 digest;
- `pav:importedBy`; and
- `pav:importedFrom`.

Selectors identify mapping assertions or members of a mapping collection; they do not use array indexes or private IDs.
Human assertions have no machine companion.
Inline machine PAV in stored records is invalid.

Qualified source claims remain semantic objects in records.
Only their PAV is split into companions.
Existing topical values are preserved when the pinned upstream helper would preserve them.
The split and join operations MUST be inverse for supported PAV and covered by upstream-parity tests.

Well-formed references to Things outside the local pool remain valid and require no network lookup.
Projection reports missing local targets and omitted graph edges.
A downstream may opt into stricter local closure.

## GitHub review profile

The supported host behavior is defined in [`github-curation-review.md`](github-curation-review.md).
It presents the proposal diff, records authenticated complete decisions, applies finalization at the current head, and validates the result.

One expiring Actions artifact MAY supply generated presentation data.
It is not metadata, a decision store, provenance authority, or recovery mechanism.
Finalized metadata and the decision cache retained on the reviewed default branch, together with the authenticated submission, form the retained review record.
The proposal branch and presentation artifact are temporary.

SHACL Vue editing follows [`github-shacl-vue-edit.md`](github-shacl-vue-edit.md).
It does not change source-adapter candidate or decision semantics.

## Guardrails

- A supported downstream is one ordinary Git repository without submodules.
- Static validation, review, build, and publication require no metadata service.
- Git commits and Git revert are the transaction and recovery mechanisms.
- Do not add candidate ledgers, duplicated diffs, exhaustive manifests, attestation graphs, or another persistent store.
- Exact-head checks protect automated writes; they are not durable project metadata.
- New semantic state requires a focused contract change, not an incidental workflow artifact.

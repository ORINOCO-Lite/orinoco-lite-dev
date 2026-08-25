# Milestone 5 completion handoff

Status: implementation released and integrated; live authenticated review pending

Milestone 5 no longer needs a separate implementation-start prompt.
The shared source-adapter runtime, both adapter profiles, annotation-overlay join, GitHub review application, and SHACL Vue human-edit handoff have been implemented, released, and integrated into the reviewed downstream.

## Authoritative records

Use these documents for current work:

1. [`source-adapters.md`](source-adapters.md) — normative adapter and curation contract;
2. [`github-curation-review.md`](github-curation-review.md) — hosted decision-review profile;
3. [`github-shacl-vue-edit.md`](github-shacl-vue-edit.md) — human-edit submission profile;
4. [`milestone-5-decisions.md`](milestone-5-decisions.md) — accepted engineering decisions;
5. [`milestone-5-acceptance.md`](milestone-5-acceptance.md) — exact releases, commits, runs, pull requests, artifacts, and remaining live evidence; and
6. [`human-review-decisions.md`](human-review-decisions.md) — accepted and deferred human policy choices.

The acceptance record, rather than this handoff, is authoritative for current coordinates and completion state.

## Delivered boundary

Milestone 5 delivered:

- a shared canonical serializer and upstream-parity behavior;
- canonical records plus PAV-only annotation companions joined before validation, RDF conversion, and projection;
- deterministic ephemeral candidate plans and compact decision caches;
- Zotero and `dump-research-info` adapters using the shared review contract;
- exact-head Git finalization that preserves proposal and review history;
- a stateless hosted GitHub decision interface for accept, reject, and defer;
- an exact-head SHACL Vue human-edit path through trusted GitHub workflows; and
- released engine/runtime and template coordinates integrated by the accepted downstream.

The implementation intentionally does not add a persistent metadata service, tracked candidate inventory, event ledger, custom transaction system, plugin ABI, automatic approval, automatic merge, production cutover, or writes to source systems.

## Remaining operational evidence

The current real Zotero proposal and its exact-head review artifacts are green.
Authenticated human disposition submission and finalization remain pending.
The real `dump-research-info` dispatch correctly stopped on an unresolved source assertion rather than inventing metadata; resolving that assertion requires an explicit semantic decision.
The separate existing-corpus normalization pull request also remains subject to human review and merge.

These are operational review gates, not missing Milestone 5 implementation.
Record new immutable evidence in [`milestone-5-acceptance.md`](milestone-5-acceptance.md) without reopening settled architecture or restoring superseded prototype machinery.

## Continuing guardrails

- Treat the merged source-adapter specification and accepted decisions as normative.
- Preserve proposal and human-review commits through merge commits.
- Keep source capture, transformation, review, and promotion distinct.
- Do not alter the real production repository or infer production cutover policy.
- Do not write to Zotero or another source system.
- Stop for human direction when ambiguity changes metadata semantics, provenance, authority, repository history, or durable state.

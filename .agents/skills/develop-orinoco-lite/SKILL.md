---
name: develop-orinoco-lite
description: Develop, diagnose, and review Orinoco Lite engine, runtime, schema integration, and source adapters against locally supported pins and current upstream implementation. Use for work in orinoco-lite-dev, adapter acquisition/import/enrichment/matching, static curation and rejection-memory design, metadata provenance with PAV or PROV, semantic mappings with SSSOM, upstream pin comparisons, parity tests, or changes that cross engine, template, and downstream ownership boundaries.
---

# Develop Orinoco Lite

Ground every design or implementation in the live repositories. Treat the
principles here as navigation and safety constraints, not as proof that a
proposed interface has already been implemented.

## Establish the active contract

1. Identify the checkout as an engineering workspace, template, downstream
   consumer, upstream component, or source-data checkout.
2. Read every applicable `AGENTS.md`, then the repository README, current
   milestone and decision documents, ownership manifest, locks, adapter README,
   schema contract, code, and tests relevant to the task.
3. Resolve the requested compatibility target before editing:

   - **supported**: the released coordinates or lock used by a consumer;
   - **engineering-compatible**: the current engineering branch and its pins;
   - **current-upstream**: a freshly verified upstream branch;
   - **proposed-upstream**: an issue, pull request, or unmerged branch.

4. Prefer the supported local pin for compatible implementation. Inspect
   current upstream when the task concerns adoption, drift, intent, or a feature
   that may have changed. Never silently substitute remote latest for a pin.
5. State which behavior is implemented, accepted by project policy, inferred,
   or merely proposed.

Read [version-and-authority.md](references/version-and-authority.md) whenever
the task compares repositories or versions. Read
[repository-boundaries.md](references/repository-boundaries.md) before a change
that crosses engineering, template, consumer, or real-site boundaries.

## Design metadata adapters as review systems

Use `source adapter` as Orinoco Lite's local umbrella for concrete scraper,
importer, and enricher workflows. Do not present it as an upstream plugin ABI
unless the inspected upstream actually defines one.

Keep these concerns distinct:

- source acquisition and reproducible snapshots;
- transformation, matching, and candidate generation;
- explicit human disposition;
- application to accepted canonical metadata;
- static projection and publication.

Separate disposable acceleration caches from durable curation state. An HTTP
cache, current-pool index, or diagnostic report must be safely evictable. A
human accept, reject, link, defer, or supersede decision must survive and guide
later runs. Never infer such a decision from silence, a missing record, a closed
pull request, a deleted inbox item, or an empty diff.

Read [adapter-static-curation.md](references/adapter-static-curation.md) in full
for adapter, matching, provenance, mapping, or decision-memory work. Verify that
the repository has adopted any described decision schema before writing against
it; otherwise frame the work as a contract proposal and preserve open human
choices.

## Preserve the static architecture

- Keep reviewed metadata as the canonical projection input.
- Do not require a continuously running metadata service for validation,
  review, build, or deployment.
- Treat Git or DataLad as execution and content-history evidence, not as a
  substitute for a human decision that leaves no metadata diff.
- Put accepted assertion provenance in the supported Things representation.
- Put adapter-specific durable curation policy in tracked, site-owned state.
- Keep credentials, caches, stores, generated reports, and build output ignored.
- Keep one canonical authority for a semantic mapping set and generate any
  alternate Things or SSSOM representation.
- Never invent identities, publication semantics, venues, topics, licensing,
  asset custody, eligibility, or publication policy.

## Implement and verify

1. Work in an isolated worktree owned by the repository being changed.
2. Change the smallest authoritative source. Regenerate staged or rendered
   copies with the repository's own commands.
3. Preserve deterministic, idempotent behavior for identical base metadata,
   source snapshot, policy, and decisions.
4. Test the exact supported pin. When adopting upstream behavior, also compare
   or parity-test the verified upstream revision and explain intentional gaps.
5. Exercise unchanged, materially changed, ambiguous, all-rejected, stale-policy,
   and cache-deletion cases when decision memory is involved.
6. Report exact revisions, commands, tests, unresolved decisions, and the owner
   of every follow-up. Do not call an experimental adapter contract stable.

For downstream execution and human review, use
`$operate-orinoco-metadata-adapters` when that skill is installed. Do not bypass
template ownership by copying framework skills directly into a generated site.

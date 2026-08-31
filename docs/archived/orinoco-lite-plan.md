# Orinoco Lite execution plan

Status: active — local full CON migration

## Outcome

The long-term Orinoco Lite outcome is a self-contained lab repository with human-editable YAML metadata, editorial content, and a deterministic static website.
Git pull requests may eventually provide the review and publication boundary without requiring a continuously running metadata service.

The accepted **clean migration** proved the upstream-compatible metadata, isolated collection, editor, static deployment, browser acceptance, and rebase strategy on a connected CON vertical slice.
Its frozen contract remains in [`docs/clean-migration.md`](clean-migration.md).

The active **full CON migration** expands that architecture into a populated CON website.
Its implementation contract is [`docs/full-con-migration.md`](full-con-migration.md).

## Repository roles

| Repository or branch | Current role |
| --- | --- |
| Parent `codex/clean-migration` | Immutable accepted coordination checkpoint |
| CON site `codex/clean-migration` | Immutable accepted two-commit site checkpoint |
| Parent `codex/full-con-migration` | Active local tooling, tests, policy, and deliberate site gitlink |
| CON site `codex/full-con-migration` | Active direct-upstream content-migration successor |
| CON site `master` and preservation refs | Legacy production history and migration evidence; unchanged |
| CON site `orinoco-lite` | Completed legacy-derived vertical slice; unchanged evidence |
| `www-from-model` `main` | Clean mirror of `upstream/main` and source of reviewed bases |
| `dump-research-info` | Structured migration evidence; never a normal build-time source |
| Orinoco submodules | Explicitly pinned schema, service, qri, UI, and graph components |

The full-migration site branch uses reviewed upstream commit `a9ac9d5abc3898fd13d9b8392008f0c323c8dcd8`.
The single upstream change after the accepted `5b401e0` base is a reviewed Forgejo CI path-to-URL correction; it does not alter presentation or generated content.

## History and authority policy

Direct upstream ancestry remains an intentional, narrow exception for the accepted clean-migration site branch and its full-migration successor.
It does not change the ancestry or production status of `master`, `legacy-site`, `orinoco-lite`, or preservation refs.

The clean-migration branches do not move.
The active site successor uses:

1. the accepted foundation replayed onto the reviewed upstream base;
2. ordinary focused commits for hand-authored profile and content batches; and
3. one terminal regenerable projection commit containing generated outputs only.

Clean-site YAML is the sole canonical metadata authority.
The legacy website and `dump-research-info` may supply evidence for a reviewed migration decision, but neither participates in a normal build.
Editorial Markdown, configuration, and declared assets in the clean-site tree are similarly authoritative for the static presentation.

## Active milestones

### 1. Generalize the vertical-slice contracts

Replace exact vertical-slice lists in projection, stack, graph, editor-link, asset, and test tooling with one executable profile manifest.
Preserve the accepted person, project, publication, instrument, organization, and homepage root as representative regression assertions.

The generalized contract must drive canonical inventory, renderable classes, routes, visibility and ordering, reference closure, native relationship integrity, assets, and acceptance expectations.
Split metadata-projection invalidation from static-site assembly invalidation so editorial-only changes do not force a metadata reprojection.

This milestone is complete only when the generalized implementation reproduces the accepted slice deterministically and passes the full unit, build, service, and Playwright suite.

### 2. Restore legacy-equivalent public coverage

Migrate the reviewed public experience in coherent batches, beginning with the legacy evidence inventory of 33 visible people and 23 featured projects.
Then restore the homepage, navigation, contact/support and other essential editorial pages, CON branding, portraits, and project imagery.

The counts are reconciliation baselines, not quotas.
Record reviewed merges, exclusions, additions, and unresolved identities.
Preserve public ordering and editorial intent where supported by evidence, while using upstream information architecture and avoiding a broad template fork or pixel-level theme rewrite.

Every batch includes provenance, native relationships, reference closure, asset status, and acceptance expectations.
Generated files remain isolated in the terminal projection commit.

## Contracts retained from clean migration

The successor keeps these proven boundaries:

- source-schema validation with exact `dlthings:*` CURIEs;
- canonical `xyzrins:.` project root and a distinct CON organization record;
- four isolated local service collections;
- `con-public` as the sole CON projection source;
- `con-protected` as the anonymous-read, token-limited local edit boundary;
- explicit-only upstream reference interfaces;
- deterministic root and project-path static builds;
- content-derived graph cache identities;
- Chromium and WebKit browser acceptance; and
- no persistent metadata service for the deployed static artifact.

Expected inventory and graph totals now derive from the reviewed profile manifest rather than fixed slice counts.
Tests must continue to detect German data leakage, stale generated products, invalid native targets, unsafe editor writes, broken assets, and process or credential residue.

## Upstream synchronization

Upstream changes are reviewed before use.
Preserve the current successor tip, inspect the candidate upstream range, remove the terminal generated commit from the replay, rebase hand-authored commits, regenerate one terminal projection commit, inspect `range-diff` and both content digests, and run complete local acceptance.
Update the parent site gitlink only after all checks pass.

Never rewrite the accepted clean-migration branches during this drill.
Prefer adapting CON profile/content to a new upstream convention over adding a compatibility layer.

## Local-only boundary

This phase may create local branches, safety refs, generated state, and local test services.
It may read remotes to review upstream or retrieve already identified public assets.

It must not push, open or update pull requests, publish Pages, change repository settings, alter DNS or production hosting, write to public metadata services, or store credentials in a repository.

## Deferred work

Do not expand the active milestones to include:

- the broader Zotero collection or bulk publication migration;
- GitHub Pages, previews, production cutover, DNS, redirects, or custom domains;
- pull-request editing, GitHub Apps, OAuth, hosted authentication, or branch protection;
- a persistent hosted metadata service;
- experimental LinkML/schema branches or full-URI type support;
- grants, CVs, annual reports, and secondary projections;
- pixel-level legacy parity or a broad upstream template fork;
- a separate metadata repository or published RDF/JSONL contract; or
- unrelated upstream contribution work.

Revisit Zotero after the people, project, editorial, and asset reconciliation is accepted.
Treat deployment and pull-request editing as later separately authorized phases.

## Handoff

Work only on the parent and site `codex/full-con-migration` branches.
Preserve all accepted and legacy refs, keep clean YAML authoritative, complete contract generalization before bulk migration, and retain a single regenerable terminal projection commit.

Run complete local acceptance and the rebase drill before changing the parent site gitlink.
Do not push or deploy.

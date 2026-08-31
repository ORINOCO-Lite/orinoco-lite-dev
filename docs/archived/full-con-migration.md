# Full CON migration implementation contract

Status: active, local-only successor phase

Reviewed upstream base: `a9ac9d5abc3898fd13d9b8392008f0c323c8dcd8`

Parent branch: `codex/full-con-migration`

Site branch: `codex/full-con-migration` in `submodules/centerforopenneuroscience.org`

Accepted clean-migration checkpoint:

- parent `f54cf5fdb2b5ae4bf03fe6939246316fd9ec818d`; and
- site `a122e506de9e4a13473edbe8d74a950d74032a16`.

## Purpose

The clean migration proved that CON metadata can use the upstream storage, projection, presentation, editor, and static-build conventions without mixing in the German snapshot or requiring a persistent metadata service.
It also proved that a small CON layer can be reviewed and replayed onto upstream.

The full migration turns that successful vertical slice into the complete CON website.
It retains the isolated profile and deterministic static deployment, generalizes the remaining slice-specific contracts, and migrates the reviewed public content in coherent batches.

This phase is not a production cutover.
All work, acceptance, and upstream synchronization remain local.

## Accepted checkpoint and successor boundary

The parent and site `codex/clean-migration` branches are accepted checkpoints.
Do not amend, rebase, delete, or move them.
They remain the compact evidence that the architecture works with six canonical records, including the ordinary `xyzrins:.` project root.

The active parent and site branches are both named `codex/full-con-migration`.
The site successor retains direct upstream ancestry as the second explicit exception to the legacy-derived branch policy.
That exception does not apply to `master`, `legacy-site`, `orinoco-lite`, or any production ref.

The successor's reviewed upstream base is `a9ac9d5abc3898fd13d9b8392008f0c323c8dcd8`.
The range after the clean migration's `5b401e0` base contains one reviewed change:

- `ci: use deposit-changes from orinoco/flow`, which changes only `.forgejo/workflows/register-depictions.yaml` from a path reference to a URL.

It does not change templates, content generation, Hugo configuration, graph rendering, assets, or the Congo theme.
The full acceptance suite is still required after replaying the CON layer.

## Site history policy

The two-commit rule belongs only to the accepted clean-migration checkpoint.
The full migration uses normal Conventional Commits so content review remains legible as the site grows.

The site history has three conceptual parts:

1. the two accepted CON foundation commits, replayed onto the reviewed upstream base;
2. focused, reviewed commits containing hand-authored profile changes and coherent content batches; and
3. one terminal `chore(projection): refresh the full CON snapshot` commit with generated projection outputs and their digests.

The terminal projection commit contains no hand-authored canonical YAML, editorial prose, migration decisions, profile contracts, or source assets.
It may be dropped before a rebase and recreated afterward, or amended after a content batch.
Generated churn must not obscure the review of hand-authored content.

Parent tooling, tests, policy, and the deliberate site gitlink use focused ordinary commits.
The parent gitlink moves only after site acceptance passes.

## Canonical content and migration evidence

Reviewed YAML under the isolated CON profile in the site repository is the sole canonical metadata source.
Editorial Markdown, profile configuration, and declared source assets in that same tree are the sole static-site inputs.

The two migration evidence sources have complementary roles:

| Evidence source | Permitted use |
| --- | --- |
| Legacy CON site history | Public roster and project selection, editorial voice, navigation intent, ordering, branding, imagery, and provenance |
| `dump-research-info` | Candidate structured fields, identity reconciliation, relationships, vocabulary requirements, and source provenance |

Neither evidence repository is a normal build-time dependency.
Import and reconciliation tools may read them explicitly while preparing a candidate batch, but the reviewed result must be copied into clean-site YAML or editorial paths before it can enter the build.

Every migrated record has a provenance entry recording its evidence paths, identity decisions, material transformations, unresolved fields, and review status.
A later change to either evidence source never changes the canonical site implicitly.

Do not copy the earlier generic relationship overlay, URL-based provisional PIDs, missing nested discriminators, vendored schema, generic projector, or custom renderer into the clean site.
Reconcile useful facts into the native upstream contract instead.

## Milestone 1: generalize the proven contracts

Before bulk content migration, replace vertical-slice constants with one executable profile manifest while preserving the accepted six-record slice as the regression fixture.

The manifest must declare or derive:

- canonical record paths and the distinguished `xyzrins:.` root;
- renderable classes, route families, page visibility, and navigation order;
- supporting reference-data closure and provenance;
- expected native relationships and allowed dangling-target policy;
- asset ownership, hydration source, availability, fallback, and destination;
- editor-link eligibility and collection boundaries; and
- graph, route, and content invariants used by build and browser acceptance.

Projection, stack preparation, graph audits, editor-link checks, asset hydration, and tests must consume that contract rather than restating exact lists for six records, four references, seven edges, five pages, or one portrait.
Yaroslav, DataLad, the publication, the instrument, the organization, and `xyzrins:.` remain representative smoke assertions rather than the complete inventory.

Split invalidation into two reviewed digests:

- a metadata-projection digest covering canonical/reference YAML, projection rules, schema and tool pins, and renderer inputs; and
- a site-assembly digest covering the committed projection, editorial content, Hugo profile, upstream templates, assets, and static adaptation.

An editorial-only change must require a new static artifact but not a metadata reprojection.
A metadata or projection-contract change must regenerate both.
Both paths fail closed on stale committed products.

## Milestone 2: restore legacy-equivalent public coverage

After the generalized six-record suite passes, migrate the legacy site's public experience in reviewable batches.
The initial evidence inventory has 33 visible people and 23 featured projects.
Treat those counts as a reconciliation baseline, not permission to manufacture records; any reviewed exclusion, addition, or merge must be recorded in provenance.

The first coverage target includes:

- the visible people roster, its public ordering, reviewed biographies, roles, links, and available portraits;
- the featured project roster, its public ordering, descriptions, links, native associations, and available artwork;
- the homepage, navigation, contact/support material, and other legacy editorial pages needed to understand the organization and move through the site; and
- CON branding and reviewed imagery with explicit provenance and fallback behavior.

`xyzrins:.` remains the canonical distinguished project root and homepage.
It is not counted as a featured research project unless a separate content review chooses to present it that way.
The CON ROR organization remains a graph record without a dedicated page until the upstream presentation defines an organization route or this phase records an explicit downstream decision.

Legacy-equivalent means equivalent public information, navigation intent, and recognizable CON identity.
It does not require pixel-level reproduction of the legacy theme.
Prefer upstream layouts and conventions, profile-local editorial content, configuration, assets, and narrowly scoped styling over a downstream template fork.

## Content-batch policy

Each content batch must be small enough to review as a semantic unit.
Suitable batches include a reconciled group of people, a connected project cluster, or one editorial section with its declared assets.

A batch is complete only when it includes:

- canonical YAML with stable CURIE/PID decisions;
- native relationship records and the required reference closure;
- editorial and asset inputs owned by that batch;
- migration provenance and explicitly deferred fields;
- validation, route, graph, link, and collection expectations; and
- a regenerated terminal projection commit after the hand-authored commit has been reviewed.

Use the pinned source Things Schema and exact `dlthings:*` CURIE designators.
Typed DOI and ISSN values remain identifiers.
Relationships use native `Association`, `Attribution`, and `Generation` records rather than generic `AttributeSpecification` bridges.

When identity, membership status, project visibility, asset licensing, or public wording is ambiguous, record the candidate and evidence in the migration ledger and continue with unambiguous records.
Do not invent public semantics merely to satisfy an expected count.
Surface the unresolved decision before publishing or treating that batch as parity-complete.

## Asset policy

Every presented asset must be an ordinary verified Git blob or a manifest entry with a retrievable read-only annex source and expected key/digest.
The manifest distinguishes available, intentionally omitted, and unavailable assets and declares the fallback for the latter two states.

Never present an annex pointer text file as an image, copy a large annex object into ordinary Git merely to simplify the migration, merge unrelated annex histories, or add a writable remote.
Preserve source path/key provenance and any known licensing or attribution information.

Missing imagery does not block migration of otherwise reviewed metadata.
It uses a deliberate neutral fallback and remains visible in the migration ledger for later custody work.

## Build, service, and deployment contracts

The proven clean-migration boundaries remain active:

- the static artifact builds only from committed clean-site inputs and the pinned local toolchain;
- `con-public` is the sole CON projection source;
- `con-protected` is the local editor boundary with anonymous curated reads and token-limited incoming writes;
- the German snapshot remains isolated in `upstream-public` and `upstream-protected`;
- unqualified commands present CON, while upstream references are explicit;
- graph resources share an audited content-derived cache identity;
- root and project-path static builds remain deterministic; and
- no metadata service is required after static generation.

As content grows, collection and graph assertions derive their expected inventory from the reviewed profile manifest.
They continue to prove exact membership, native target integrity, and the absence of German records rather than relying on hard-coded totals.

## Acceptance

Milestone 1 is accepted when the generalized contract reproduces the accepted vertical slice byte-for-byte where inputs are unchanged and all unit, projection, static, collection, and Playwright checks pass.

Each later content batch must pass:

- source-schema validation and JSON-to-RDF-to-JSON round trips for its native types;
- unknown-CURIE, full-URI designator, and dangling-target negative tests;
- deterministic projection verification and two byte-identical static builds;
- exact manifest-derived collection and graph membership checks;
- expected root and project-path routes, links, branding, and assets;
- absence of German entity routes and graph nodes from the CON artifact;
- Chromium and WebKit navigation, graph, and representative editor checks;
- the disposable authenticated-editor boundary test; and
- process, token, incoming-probe, and temporary-state cleanup.

The full legacy-coverage milestone also requires a reviewed reconciliation report for the people roster, featured projects, editorial pages, and assets.
The report explains every difference from the evidence inventory.

## Upstream synchronization

Upstream remains a reviewed input, never an automatic merge target.
For each candidate base:

1. preserve the current full-migration tip and record the candidate upstream commit;
2. review the upstream range, especially templates, projection behavior, workflows, theme and annex changes;
3. drop the terminal generated projection commit from the replay range;
4. rebase the accepted foundation and ordinary hand-authored commits onto the exact reviewed base;
5. regenerate one terminal projection commit from clean ignored state;
6. inspect `range-diff`, the two digests, and expected generated churn;
7. run complete local acceptance; and
8. update the parent gitlink deliberately only after acceptance.

Never rebase or move the accepted `codex/clean-migration` checkpoint as part of this drill.
If an upstream change requires compatibility code, first attempt to adapt the profile or content to the new convention.
Record unavoidable downstream divergence as an explicit contract decision.

## Local-only operating boundary

Remote reads may be used to review upstream and retrieve already identified public assets.
Local branches, safety refs, generated state, and test services are allowed.

This phase must not push refs, open or update pull requests, publish Pages, modify repository settings, alter DNS or production hosting, write to the public Psychoinformatics pool, or place credentials in a repository.
A successful acceptance run does not broaden this authorization.

## Explicitly deferred work

The following work remains outside the active milestones:

- importing or publishing the broader Zotero collection;
- bulk publication migration beyond records required by the reviewed legacy people/project experience;
- GitHub Pages, preview deployments, production cutover, DNS, redirects, and custom domains;
- pull-request-based editing, GitHub Apps, OAuth, hosted editor authentication, and branch-protection design;
- a persistent hosted metadata service;
- support for full-URI type designators or experimental schema/LinkML branches;
- grants, CVs, annual reports, and secondary projections;
- pixel-level legacy-theme reproduction or a broad upstream template fork;
- durable custody for every historical annex object;
- a separate metadata repository or published RDF/JSONL interface; and
- upstream contribution work unrelated to a migration blocker.

Revisit Zotero only after the legacy-equivalent people, project, editorial, and asset reconciliation is accepted.
Revisit deployment and pull-request editing as separate, explicitly authorized phases after the static content migration is stable.

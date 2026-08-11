# Orinoco Lite execution plan

Status: active — local clean-migration trial

## Outcome

The long-term Orinoco Lite outcome remains a self-contained lab repository with human-editable YAML metadata, editorial content, and a deterministic static website.
Git pull requests will eventually provide the review and publication boundary, without requiring a continuously running metadata service.

The active effort is narrower.
It layers the reviewed CON vertical slice onto a current upstream website base, proves the local service and static build paths, and establishes a small downstream commit stack that can be rebased as upstream changes.

This effort is named **clean migration**.
Its decision-complete implementation contract is [`docs/clean-migration.md`](clean-migration.md).

## Current repository roles

| Repository or branch | Current role |
| --- | --- |
| Parent `codex/clean-migration` | Local coordination, component pins, tests, and deliberate site gitlink |
| CON site `codex/clean-migration` | Direct-upstream experimental site with exactly two downstream commits |
| CON site `master` and preservation refs | Legacy production history; unchanged reference material |
| CON site `orinoco-lite` | Completed legacy-derived vertical slice; unchanged migration input |
| `www-from-model` `main` | Clean mirror of `upstream/main` and source of reviewed base commits |
| `dump-research-info` | Reviewed migration evidence; never a build-time data source |
| Orinoco submodules | Explicitly pinned schema, service, qri, UI, and graph components |

The active site branch starts directly from upstream website commit `5b401e0c478a4409442b3a8a285bd3efd5d30e05`.
This ancestry is intentional so the two downstream site commits can be replayed onto a reviewed newer upstream commit.

## Repository and branch policy

The normal Orinoco Lite policy keeps CON website history descended from legacy CON `master` and adopts upstream code selectively.
That remains the policy for `master`, `legacy-site`, `orinoco-lite`, and all future production work unless a later decision changes it.

The site branch `codex/clean-migration` is the sole exception.
It has direct `www-from-model` ancestry and must not be merged into, used to rewrite, or substituted for the preserved legacy-derived branches during this effort.

Preserve unchanged:

- legacy CON `master` and all preservation refs;
- the completed `orinoco-lite` branch and its evidence;
- `www-from-model` `main` as a clean upstream mirror; and
- all unrelated parent submodule pins.

The clean-migration site branch contains exactly two commits above its reviewed upstream base:

1. A **build-profile commit** owns the isolated CON configuration, path and projection manifests, asset manifest, account-mirror transport, and synchronization policy.
2. A **content-and-snapshot commit** owns the canonical and reference YAML, including the homepage project, editorial material, branding and assets, provenance, and committed deterministic projection.

Within the second commit, hand-authored inputs and generated outputs remain in distinct profile paths so they can be reviewed and regenerated independently.

Fixups are amended into the appropriate commit.
Do not accumulate a third site commit.
The parent coordination repository may update the site gitlink only after all local acceptance and rebase checks pass.

## Active clean-migration scope

### Data and content

Use the connected CON vertical slice already reviewed in the completed `orinoco-lite` effort:

- the Center for Open Neuroscience organization;
- one representative person;
- one project;
- one publication;
- one instrument or output needed by the connected slice;
- their native relationships and typed identifiers;
- representative reviewed media; and
- enough editorial content to assess the homepage and primary navigation.

Migration evidence may be copied deliberately from `dump-research-info` or the completed vertical slice.
The clean site tree must become the complete build input.
No normal build may join independently changing repositories or contact the German pool for CON records.

### Schema and record contract

Use the source root schema from Things Schemas commit `d26ea413` with the released LinkML, LinkML Runtime, Pydantic, and RDFLib versions pinned in the parent Pixi environment.

The native `Association`, `Attribution`, `Generation`, `DOI`, and `ISSN` designators use their exact `dlthings:*` CURIE spellings.
The verified contract, negative full-URI behavior, and excluded LinkML/schema candidates are recorded in [`docs/explaining-schema-issues.md`](explaining-schema-issues.md).

Do not validate against the completed vertical slice's vendored resolved static schema.
Do not import the LinkML discriminator trial or the later Things Schemas identity candidate.

### Isolated local collections

The local service has four named collections with no cross-profile joins:

| Collection | Contents and consumer |
| --- | --- |
| `upstream-public` | Curated German public snapshot for explicit upstream reference checks |
| `upstream-protected` | Local protected/incoming counterpart for explicit upstream editor checks |
| `con-public` | Six canonical CON records plus reference records; sole qri publication input |
| `con-protected` | CON incoming/edit boundary used by SHACL Vue |

The German snapshot is seeded only into the two `upstream-*` collections.
Canonical CON records, including the homepage project, and projection reference records are loaded only into the two `con-*` collections. qri reads `con-public`.
SHACL Vue reads and writes through `con-protected` for the default CON editing path.

The default local interfaces are the CON editor/service profile and the generated CON static site.
Upstream service, editor, snapshot, and static-site references remain available only through explicit upstream-named tasks, URLs, or arguments.
An unqualified default must never expose or project the German snapshot.

For the local editor, `con-protected` permits anonymous reads of reviewed curated CON records through a dedicated read-only identity.
Writes still require the ignored `local_editor` token and may reach only the CON `local-editor` incoming boundary.
Here, `protected` describes the incoming edit boundary rather than confidential curated content.

### Homepage project and CON organization

Following upstream, `xyzrins:.` is a canonical `xyzri:XYZProject` that provides the homepage and root for project selection.
It represents the CON website and has an explicit native association with the separate CON organization record `ror:04tfhh831`.

The homepage project may remain minimal until the vertical slice expands.
The organization remains available in the graph without a dedicated detail page, matching the current upstream presentation behavior.

### Local interfaces and deployment boundary

The supported interfaces for this effort are local:

- a one-command default CON service/editor/static stack;
- a faster static-only CON build and local server;
- explicit upstream reference build and service commands; and
- deterministic validation, projection, link, graph, and path audits;
- an explicit browser-dependency installation command; and
- a Playwright acceptance suite separate from the fast unit-test command.

No action in this effort may push a branch or tag, open a pull request, enable or publish GitHub Pages, modify DNS, change a production domain, or update the deployed CON website.
Remote reads needed to review upstream or hydrate already identified assets do not authorize remote writes.

## Acceptance criteria

The clean migration is locally accepted only when all of these are true:

- the site branch is exactly two commits above the reviewed upstream base;
- profile contracts, hand-authored inputs, and generated projection outputs remain isolated in their declared paths;
- Hugo configuration, layouts, page templates, and graph code come from the rebased clean-site ancestry, while the sibling mirror is used only for byte-identical annex/theme hydration;
- every CON record validates through the pinned live Dump Things path;
- the five native CURIE fixtures survive JSON-to-RDF-to-JSON conversion and live validation;
- invalid records and unsupported full-URI designators fail closed;
- qri reads only `con-public` and generates the expected connected pages;
- the German snapshot exists only in `upstream-public` and `upstream-protected`;
- the default editor uses `con-protected` and the default static site is CON;
- upstream references require explicit selection;
- repeated generation produces an equivalent projection and clean manifest;
- internal links, Pages-style base paths, graph nodes, and graph edges pass their audits;
- graph scripts and data use one audited content-derived cache identity so a same-origin upstream-to-CON switch cannot reuse the German graph;
- anonymous editor reads populate the concrete Yaroslav person form, while anonymous writes remain forbidden;
- a disposable browser-driven edit lands only in the CON protected incoming boundary and leaves no probe record behind;
- Chromium and Playwright WebKit pass the cache and anonymous-editor browser scenarios without leaking local credentials into test artifacts;
- no persistent metadata process is required after static generation;
- the legacy, preservation, and `orinoco-lite` refs remain unchanged; and
- no remote, Pages, DNS, domain, or production state changed.

## Upstream synchronization

Upstream changes are never merged automatically.
For each candidate base, follow the exact local rebase drill in [`docs/clean-migration.md`](clean-migration.md):

1. review the upstream range and record the proposed base;
2. replay exactly the two site commits with `rebase --onto`;
3. regenerate and amend the projection commit;
4. inspect `range-diff` for both downstream commits;
5. run the complete acceptance suite; and
6. update the parent site gitlink deliberately only after acceptance.

Do not push the rebased branch or parent gitlink during this effort.

## Explicitly deferred work

The following work is outside the active clean migration:

- full migration of all CON records and legacy editorial content;
- production cutover, DNS, custom domains, redirects, or Pages publication;
- pull-request previews, branch protection, CODEOWNERS, and deployment permissions;
- GitHub Issue Forms, a GitHub App, OAuth, or other hosted editing services;
- production SHACL Vue authentication or a persistent metadata service;
- support for full-URI type designators;
- adoption of experimental LinkML or Things Schemas candidate commits;
- detailed ROR presentation;
- complete visual redesign or pixel-level legacy parity;
- durable mirroring of every upstream annex object;
- extraction of `orinoco-lite-action` or creation of a lab template;
- a separate canonical metadata repository;
- published JSONL or RDF contracts;
- grants, CVs, annual reports, and other secondary projections;
- broad upstream refactoring or contribution work; and
- production branch ancestry, merge, or replacement decisions.

Resolve each item only when a later phase depends on it.

## Handoff

Work only on the parent and site `codex/clean-migration` branches.
Preserve the two-site-commit contract and the four-collection isolation model.
Use the source-schema CURIE path, keep default interfaces CON-focused, and make all upstream references explicit.

Complete local acceptance and the rebase drill before proposing a parent gitlink update.
Do not push or deploy.

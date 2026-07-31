# Orinoco Lite execution plan

Status: active

## Outcome

Enable a lab to create one GitHub repository, add structured research metadata
and editorial content, and deploy a static lab website through GitHub Pages.
The lab should not need to understand or operate the underlying Orinoco
services.

Canonical metadata is human-editable YAML in Git. GitHub pull requests provide
the authentication, review, and publication boundary. The same records may
later support websites, graphs, grants, CVs, annual reports, and other
projections.

## Current repository map

| Repository | Current role |
| --- | --- |
| [`con/orinoco-lite-dev`](https://github.com/con/orinoco-lite-dev) | Development workspace, architecture, component pins, and integration coordination |
| [`con/www-from-model`](https://github.com/con/www-from-model) | First downstream implementation and CON website prototype |
| [`www/www-from-model`](https://hub.psychoinformatics.de/www/www-from-model) | Upstream metadata-driven Hugo website |
| `centerforopenneuroscience.org` | Source of existing CON editorial content, assets, URLs, and presentation requirements |
| `dump-research-info` | Source of reviewed CON metadata and migration/provenance logic |
| Orinoco repositories | Upstream schemas, Dump Things, `qri`, graph, UI, and enrichment components |
| `con/orinoco-lite-action` | Future released build and deployment implementation; not yet extracted |
| `con/orinoco-lite-template` | Future minimal lab starter; not yet created |

The coordination repository currently pins 24 independently usable component
repositories under `submodules/`. Their present location does not imply that
all are runtime dependencies. Directory reorganization is not required before
the first website slice.

## Repository and branch policy

The local `submodules/www-from-model` repository has:

- `origin`: `https://github.com/con/www-from-model.git`;
- `upstream`: `https://hub.psychoinformatics.de/www/www-from-model.git`; and
- `main`: the branch reserved for mirroring `upstream/main`.

Create `con-site` from `main` for CON-specific integration. Rebase `con-site`
onto `upstream/main` while it remains a small, privately coordinated prototype.
Once others depend on the branch, avoid rewriting shared history and integrate
upstream changes by an agreed merge or refresh process.

Keep changes separated where practical:

- CON metadata, content, assets, and theme overrides belong on `con-site`.
- Generally useful fixes belong on focused topic branches and should be offered
  upstream narrowly.
- Released Orinoco Lite behavior will eventually be extracted into a separate,
  versioned action rather than maintained as permanent CON-specific patches.

The parent repository pins explicit component commits. Updating an upstream
reference must not silently change a released lab build.

## Architectural decisions

- A lab starts from a small GitHub template, not a fork of this coordination
  repository.
- The default topology is one self-contained repository containing metadata,
  website content, configuration, and deployment.
- A separate metadata repository is an optional later topology for cases with
  distinct permissions, release schedules, or independently managed consumers.
- The public site is a deterministic static projection and requires no
  continuously running metadata backend.
- Dump Things may run locally and ephemerally in CI to preserve upstream
  validation and projection behavior.
- JSONL is an internal adapter when required by `qri`, not a second canonical
  format.
- RDF is generated only when an identified consumer requires it.
- Direct Git editing and pull requests are the complete initial editing path.
- GitHub Issue Forms, SHACL-vue, a GitHub App, and an OAuth broker are possible
  later improvements, not first-milestone dependencies.
- GitHub Pages is the initial preview and deployment target.

## First milestone: CON vertical slice

### Goal

Produce a GitHub Pages preview from one small, connected set of real CON
records using as much of the upstream `www-from-model` pipeline as practical.
This milestone establishes the actual metadata, generator, theme, and workflow
boundaries before they are generalized.

### Minimum data slice

Include:

- the Center for Open Neuroscience organization;
- one person;
- one project;
- one publication or dataset;
- the relationships connecting those records;
- one or more representative depictions or assets; and
- enough editorial content to evaluate the homepage and primary navigation.

Use records that already have reviewed evidence in `dump-research-info` and
content or assets already present in `centerforopenneuroscience.org`.

### Execution sequence

1. Create `con-site` in `submodules/www-from-model` from the mirrored `main`.
2. Identify the exact metadata collection, schema release, and build entry
   points currently used by upstream `www-from-model`.
3. Select the minimum connected CON records and their source evidence.
4. Transform those records into individual upstream-compatible YAML files on
   `con-site`.
5. Copy only the corresponding editorial content and assets from
   `centerforopenneuroscience.org`.
6. Add the smallest CON theme and configuration overrides needed to evaluate
   the site.
7. Adapt the upstream build so required Dump Things behavior runs ephemerally
   during CI rather than depending on a dedicated service.
8. Use `qri` and Hugo to produce the static website.
9. Add a repository-local GitHub Actions workflow that publishes a GitHub Pages
   preview from the prototype branch.
10. Record any necessary divergence from upstream and keep reusable fixes
    isolated for possible contribution.

The production build must consume the combined candidate tree. It must not
continually join independently changing data from `dump-research-info` and
content from `centerforopenneuroscience.org`.

### Exit criteria

- One canonical metadata change deterministically changes the preview site.
- The selected records validate through the upstream Orinoco path.
- Invalid records stop publication.
- The website builds without contacting a persistent metadata service.
- The preview contains the selected organization, person, project, output,
  relationships, and representative assets.
- The build uses only files in the candidate lab repository plus pinned build
  dependencies.
- CON-specific and potentially reusable changes remain distinguishable.
- No production DNS, domain, or existing-site deployment is changed.

## Metadata and build contract

- Store approved entities as individual YAML records following the filesystem
  and schema conventions selected from upstream Orinoco.
- Use `.dumpthings.yaml` collection configuration where required by that
  upstream layout.
- Preserve source observations, retrieval details, candidates,
  reconciliation decisions, and reviewed additions separately from approved
  public records.
- Maintain stable identifiers and explicit relationships during migration.
- Pin a compatible schema and toolchain for every reproducible build.
- Run Dump Things ephemerally in CI using the upstream Orinoco validation path.
  Direct LinkML validation may provide an earlier, faster check, but it is not
  the sole publication gate unless its scope is shown to match the required
  Dump Things checks.
- Convert validated records to JSONL transiently when `qri` requires its stream
  interface.
- Generate RDF only for a named editor, graph, or interoperability consumer.
- Treat generated Hugo content, caches, JSONL, RDF, and pages as build
  artifacts rather than canonical records.
- Keep editorial Markdown, theme overrides, media, redirects, and site
  configuration with the lab website.

## Explicit first-milestone non-goals

- Full migration of all CON records.
- Production cutover or DNS changes.
- Pixel-level parity with the existing CON website.
- Extraction of `orinoco-lite-action`.
- Creation of `orinoco-lite-template` or Copier prompts.
- A separate canonical metadata repository.
- GitHub App, OAuth broker, or direct graphical writes.
- Published JSONL or RDF without an identified consumer.
- Grant, CV, annual-report, or other secondary projections.
- Reorganization or wholesale updating of every tracked submodule.
- Broad upstream refactoring.

## Later phases

### 2. Complete CON migration

- Migrate all accepted records from `dump-research-info` into canonical YAML.
- Preserve source snapshots, evidence, review decisions, merge policy, and
  identifiers.
- Compare record counts, persistent identifiers, relationships, and approved
  assets before retiring any migration path.
- Keep `dump-research-info` available as migration history until parity is
  accepted.

Exit: the candidate lab repository is the single canonical source for accepted
CON metadata and website content.

### 3. Website completion and cutover

- Complete content and presentation work based on the proven vertical slice.
- Account for existing public URLs, redirects, assets, attribution, and
  accessibility.
- Establish branch protection, reviewers, Pages ownership, and deployment
  permissions.
- Review the static preview before changing the production domain.

Exit: the candidate can replace the existing CON deployment without losing
required content, URLs, or provenance.

### 4. Reusable action and lab template

- Extract validation, projection, Hugo build, and Pages deployment from the
  working CON implementation into `con/orinoco-lite-action`.
- Expose one tagged reusable workflow with conventional paths and pinned
  dependencies.
- Obtain Pages URL and base-path information from GitHub Pages configuration
  rather than requiring users to calculate it.
- Create `con/orinoco-lite-template` with the canonical directory skeleton,
  example records, lab configuration, and a short caller workflow.
- Add Copier only if prompted initialization materially improves setup after
  the plain GitHub template works.
- Test the release in a new independent lab repository.

Exit: a lab can replace example metadata and deploy without understanding the
Orinoco toolchain.

### 5. Editing and additional projections

- Document direct file and pull-request editing first.
- Evaluate Issue Forms for bounded metadata additions.
- Configure SHACL-vue for validation and export before introducing direct
  writes.
- Consider a GitHub App and stateless OAuth broker only if the editing benefit
  justifies operating an external endpoint.
- Add RDF, grants, CVs, annual reports, and other projections only for concrete
  consumers.

Exit: additional interfaces preserve the same canonical records and Git review
boundary.

## Upstream synchronization and contribution policy

- Check upstream component heads on a deliberate schedule.
- Never auto-merge upstream updates.
- Summarize relevant component changes and test candidate pins before release.
- Ensure action tags pin reproducible dependency versions.
- Develop reusable fixes on focused branches in the relevant repository.
- Submit only narrow, generally useful changes upstream.
- Keep CON-specific policy, metadata, content, and presentation downstream.

## Deferred decisions

These do not block the first vertical slice:

- final ownership and naming of the action and template repositories;
- the public product documentation entry point;
- the exact template configuration and optional Copier questions;
- whether guided editing begins with Issue Forms or SHACL-vue export;
- whether an external OAuth broker is ever acceptable;
- criteria for splitting metadata into a separate repository;
- published RDF or JSONL contracts;
- metadata licensing, CODEOWNERS, and long-term review policy;
- production Pages, DNS, and domain ownership; and
- the final pull-request preview experience.

Resolve each decision immediately before the phase that depends on it. Do not
block the vertical slice waiting for speculative answers.

## Handoff for the next thread

Begin in `/Users/johnlee/code/CON/orinoco-lite-dev` and implement only the first
milestone above. The primary implementation repository is
`submodules/www-from-model`; create `con-site` there before making CON-specific
changes. Use `submodules/dump-research-info` and
`submodules/centerforopenneuroscience.org` only as migration inputs.

Do not begin by generalizing the action, creating more architecture documents,
or reorganizing all submodules. First prove one real record-to-website path.

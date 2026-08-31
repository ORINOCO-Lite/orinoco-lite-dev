# Clean migration implementation contract

Status: accepted local-only checkpoint; superseded for active development by [`full-con-migration.md`](full-con-migration.md)

Reviewed upstream base: `5b401e0c478a4409442b3a8a285bd3efd5d30e05`

Parent branch: `codex/clean-migration`

Site branch: `codex/clean-migration` in `submodules/centerforopenneuroscience.org`

## Purpose

The clean migration tested a deliberately different history strategy from the completed `orinoco-lite` vertical slice.
The site branch descends directly from the reviewed `www-from-model` upstream commit and carries a minimal CON layer that can be replayed onto later reviewed upstream commits.

The experiment answered four questions locally:

1. Can the real CON vertical slice validate and project through the pinned upstream stack while using the source-schema CURIE contract?
2. Can the default service/editor and static interfaces show CON data without mixing in the German snapshot?
3. Can the downstream site remain exactly two commits above upstream?
4. Can those two commits be rebased, regenerated, and reviewed without changing legacy or production state?

## Exception boundary

Direct upstream ancestry is allowed for the accepted site branch `codex/clean-migration` and its explicitly authorized `codex/full-con-migration` successor.
It is not a new repository-wide history policy.

Do not modify, rebase, force-update, merge into, or replace:

- CON `master`;
- `legacy-site` or its preservation tag;
- the completed `orinoco-lite` branch;
- the clean `www-from-model` mirror branch; or
- any production or deployment ref.

These direct-upstream branches are local integration branches.
The accepted clean-migration result informs its successor and a later production decision; it does not make that production decision itself.

## Git topology and two-commit rule

The site history has this exact shape:

```text
reviewed www-from-model base: 5b401e0
  |
  +-- build-profile commit
        |
        +-- content-and-projection snapshot commit
```

The reviewed upstream base is not counted as a downstream commit.
The branch must have exactly two commits in `5b401e0..codex/clean-migration`.

### Commit 1: build profile

The first commit establishes the downstream build and synchronization contract:

- the account-owned Congo transport URL;
- `UPSTREAM.md` and the two-commit synchronization policy;
- isolated `config/con/` Hugo configuration;
- profile, projection-path, asset-manifest, and source-schema contracts; and
- profile-local storage policy for ordinary Git and annex-backed assets.

It must not contain canonical CON records, reference records, editorial material, branding payloads, generated entity pages, generated graph data, transient service state, tokens, caches, or built Hugo output.

### Commit 2: content and projection snapshot

The second commit contains the reviewed content payload and the deterministic products declared by the first commit:

- six canonical CON records, including the homepage project, and four provenance-marked reference records;
- editorial content, branding and assets, and migration provenance;
- the deterministic dtc/qri record snapshot;
- generated metadata page bundles;
- graph data produced by the unmodified upstream graph script; and
- a digest tying the snapshot to canonical records, profile configuration, upstream templates, and tool pins.

Within this commit, canonical/editorial inputs, provenance, and generated projection outputs remain in separate declared paths.
It must not modify upstream layouts, templates, generated German content, refresh workflows, or build policy.
If generation exposes a content defect, fix the content input, regenerate, and amend this same second commit.

Do not add a third cleanup, conflict-resolution, or test-fix commit.

## Profile and projection isolation

The clean-migration profile is a named downstream build context.
It must not overwrite or reinterpret the explicit upstream reference profile.
Generated CON workspaces, service stores, qri caches, and Hugo destinations use profile-specific paths under ignored local build state.

The normal CON build consumes only:

- canonical files in the clean site tree;
- the four pinned reference records; and
- explicitly pinned local tool and schema dependencies.

It must not query the German pool, read the prepared German snapshot, or join records from another repository.

The upstream snapshot and upstream service/UI remain comparison fixtures.
They require an explicit upstream-named command, argument, collection, or URL.
They are never selected by an unqualified default.

## Four-collection service contract

The local Dump Things configuration exposes exactly these logical collection roles:

| Collection | Allowed records | Consumer |
| --- | --- | --- |
| `upstream-public` | Curated German public snapshot only | Explicit upstream reference reads |
| `upstream-protected` | Local incoming/protected German counterpart only | Explicit upstream editor reference |
| `con-public` | Six canonical CON records and required projection references only | qri and default CON reads |
| `con-protected` | CON curated/incoming editor state only | Default SHACL Vue edit boundary |

The German snapshot is seeded into `upstream-public` and `upstream-protected`, never either `con-*` collection.

Canonical CON YAML, including the homepage project, and projection references are loaded into `con-public` and `con-protected`, never either `upstream-*` collection.

qri caches and projects only `con-public` for the CON site.
The default SHACL Vue configuration reads and writes through `con-protected`.
A curated/public transition may copy an accepted CON edit from `con-protected` to `con-public`; it must never cross into the upstream pair.

Tests must inspect both collection membership and consumer configuration.
Matching record counts alone are insufficient because the two profiles contain different record sets.

### Local editor authorization decision

The word `protected` names the local incoming and editing boundary.
It does not mean that the reviewed curated CON records are confidential.
The default identity for `con-protected` is therefore a dedicated `local_con_reader` with `READ_CURATED` and no write permission.

The ignored local `local_editor` token is the only non-curator identity with `WRITE_COLLECTION` for `con-protected`.
It may write only to the `local-editor` incoming label.
Anonymous writes and writes to any other collection remain forbidden.

Static edit links contain the service URL, the generic upstream `dlthings:Thing` node shape, the exact record PID, and `edit=true`.
They never contain a token.
SHACL Vue first reads the record anonymously and then resolves its concrete `xyzri:*` type for the form.
An authenticated write uses the ignored local token through SHACL Vue's local session storage.

This is a local feedback-loop decision, not a production authentication design.
Patching upstream SHACL Vue, publishing a reusable editor credential, and production authorization remain outside this effort.

## Static graph cache identity

The upstream reference artifact and CON artifact may be served from the same loopback origin during local comparison.
They must not reuse an ambiguous `/graph.js` or `/graph.json` browser cache entry.

Each assembled artifact has one deterministic graph-bundle key.
The key is the SHA-256 digest of a canonical manifest containing the final base-path-adjusted, unversioned `graph.js` digest and the final `graph.json` digest.
The adapter adds the full bundle key to both resource URLs:

```text
graph.js?v=<bundle-sha256>
graph.json?v=<bundle-sha256>
```

Computing the key after base-path adaptation means root and project-path artifacts may have different keys.
The build audit rejects missing, unversioned, stale, or mismatched bundle references and requires adaptation to be idempotent.

Cache-control headers may improve local feedback, but they are not the correctness mechanism.
The committed static artifact must switch graphs correctly on an ordinary static host without custom response headers or modified upstream templates.

## Browser acceptance decision

Browser acceptance belongs to the parent coordination repository because it crosses the static site, Dump Things, and SHACL Vue boundaries.
It uses a root-owned, exactly pinned Playwright dependency and lockfile and does not modify either upstream JavaScript package.

The fast `pixi run test` command remains browser-free.
Browser dependencies are installed explicitly with `pixi run install-browser-tests`, and the ignored browser suite runs with `pixi run test-browser`.
The full local acceptance command includes both suites.

Chromium and Playwright WebKit cover the same-origin graph-cache transition and anonymous Yaroslav editor load.
WebKit provides useful Safari-like regression coverage but is not a claim of system Safari equivalence.
A single Chromium scenario performs an authenticated edit of a reserved, disposable person record and proves that it appears only in `con-protected/incoming/local-editor`.
It never edits Yaroslav's real incoming record.

The authenticated scenario cleans its reserved PID before and after the run.
It disables traces, screenshots, and video, reads ignored token files inside the test process, and never places credentials in URLs, logs, attachments, or assertion output.
All browser traffic remains loopback-only, fixed-port services are not reused, and the test supervisor must clean up every child process even after failure.

## Source-schema CURIE contract

The validation path uses the source root schema at:

```text
submodules/things-schemas/
  src/demo-research-information/unreleased.yaml
```

The Things Schemas commit is `d26ea4135e28c25b134c64de1cdc15d15cd2f9f0`.
The service and package pins are those recorded in [`explaining-schema-issues.md`](explaining-schema-issues.md).

Canonical and generated CON records use these exact native designators:

```text
dlthings:Association
dlthings:Attribution
dlthings:Generation
dlthings:DOI
dlthings:ISSN
```

Do not expand them to full URIs.
Do not validate with the old vendored resolved static schema.
Do not include the LinkML discriminator branch, proposed LinkML composite, or later Things Schemas class-identity candidate.

Positive tests cover JSON-to-RDF-to-JSON conversion and the live Dump Things endpoint for all five native classes.
Negative tests prove that unsupported full-URI designators fail rather than being silently normalized.

## Default and reference interfaces

The unqualified local workflow is CON-focused:

- the default build validates and projects `con-public`;
- the default full-stack server opens the CON static site and CON editor;
- the default editor points at `con-protected`; and
- the default static-only server serves the generated CON projection.

The upstream reference workflow remains available for comparison, but every entry point is explicitly labeled upstream.
This includes upstream site builds, static servers, service checks, editor configuration, collection names, and URLs.

The implementation may retain existing commands through explicit aliases while callers migrate, but it must not leave an ambiguous default that serves German content.
Documentation and startup messages must identify which profile is active.

All runtime tokens, stores, snapshots, generated workspaces, and service logs remain ignored local state.
No credentials belong in either site commit or the parent gitlink update.

## Homepage project

The clean migration follows upstream directly: `xyzrins:.` is a canonical `xyzri:XYZProject` and is the distinguished homepage and project-selection root.
This sixth canonical record represents the CON website and has an explicit native association with the canonical CON organization `ror:04tfhh831`.

The project and organization are distinct records with distinct purposes.
The homepage project may remain a small placeholder until more CON content is migrated.
The organization remains graph-only until upstream establishes an organization-page convention.

## Local-only operating boundary

This effort may read remotes to review upstream commits and retrieve already identified public assets.
It may create local branches, local safety refs, build artifacts, and service state.

It must not:

- push any parent, site, mirror, annex, or component ref;
- open or update a pull request;
- enable, configure, or publish GitHub Pages;
- change repository settings, branch protection, or Actions permissions;
- alter DNS, a custom domain, or production hosting;
- write to the public Psychoinformatics pool;
- write to a production annex or metadata service; or
- modify the deployed CON website.

No successful local test broadens this authorization.

## Initial construction sequence

1. Verify the parent is on local branch `codex/clean-migration` and record its starting status.
2. Verify the site worktree is clean and that the reviewed upstream base `5b401e0c478a4409442b3a8a285bd3efd5d30e05` is available locally.
3. Create the site `codex/clean-migration` branch directly at that base without changing legacy-derived refs.
4. Build and amend the build-profile commit until its isolated configuration, manifests, and synchronization policy are complete.
5. Add the reviewed canonical/reference records, editorial material, assets, and provenance; generate the CON projection from a clean local runtime; and create the sole content-and-snapshot commit.
6. Run the complete acceptance suite twice, including a clean regeneration comparison.
7. Inspect the two commits independently and verify each file is in the path and commit declared above.
8. Update the parent site gitlink only after every acceptance criterion passes.
9. Leave all branches and the parent gitlink local.

## Exact upstream rebase drill

Perform this drill for every proposed upstream base change.
Resolve and record the three commit IDs before running a mutating command.

### 1. Review upstream and preserve the old range

Run this drill from the parent repository.
Resolve the current two-commit range in the site and the proposed base from the clean sibling mirror:

```bash
clean_site_repo=submodules/centerforopenneuroscience.org
clean_mirror_repo=submodules/www-from-model
clean_old_base="$(git -C "$clean_site_repo" \
  rev-parse codex/clean-migration~2)"
clean_old_tip="$(git -C "$clean_site_repo" \
  rev-parse codex/clean-migration)"
clean_new_base="$(git -C "$clean_mirror_repo" rev-parse main)"
```

Before rebasing, verify and preserve the two downstream commits:

```bash
test "$(git -C "$clean_site_repo" rev-list --count \
  "$clean_old_base..$clean_old_tip")" = 2
git -C "$clean_site_repo" log --reverse --oneline \
  "$clean_old_base..$clean_old_tip"
git -C "$clean_site_repo" update-ref \
  refs/heads/codex/clean-migration-before-rebase "$clean_old_tip"
```

Review `clean_old_base..clean_new_base` in `clean_mirror_repo` before accepting `clean_new_base`.
At minimum inspect the commit log, diffstat, templates, configuration, workflow definitions, generated-content changes, theme gitlink, annex metadata, and any tool or schema references.
Record the reviewed range and relevant changes in profile provenance.

After review, make that exact mirror commit available to the site through the local sibling repository and reject a moved mirror tip:

```bash
git -C "$clean_site_repo" fetch ../www-from-model main
test "$(git -C "$clean_site_repo" rev-parse FETCH_HEAD)" = \
  "$clean_new_base"
```

The rebased site is the presentation source for configuration, layouts, page templates, and graph code.
The sibling mirror is only the hydration transport for upstream annexed assets and the initialized Congo theme.
Before regeneration, require its `assets`, `static`, and `themes/congo` Git objects to match the candidate base exactly; a mismatch means the sibling pin must be reviewed and updated before continuing.

### 2. Rebase exactly two commits

With the site worktree clean:

```bash
git -C "$clean_site_repo" rebase --onto "$clean_new_base" \
  "$clean_old_base" codex/clean-migration
test "$(git -C "$clean_site_repo" rev-list --count \
  "$clean_new_base..codex/clean-migration")" = 2
```

Resolve build-profile conflicts in the first commit and content/projection conflicts in the second.
Keep content inputs and generated output in their isolated paths.
Do not add a third commit.

### 3. Regenerate the projection

Run the profile's locked validation and generation entry point from clean ignored runtime state.
Verify that it reads `con-public`, not `upstream-public`.

Replace the tracked generated projection with the new result, review the manifest, and amend the second commit:

```bash
git -C "$clean_site_repo" commit --amend --no-edit
test "$(git -C "$clean_site_repo" rev-list --count \
  "$clean_new_base..codex/clean-migration")" = 2
```

If regeneration requires a content change, amend that input and regenerated output together into the second commit.
If it requires a build-profile or policy change, amend the first commit, rerun generation, and amend the second commit again.

### 4. Compare the downstream ranges

Use the preserved local ref to review semantic changes in both commits:

```bash
git -C "$clean_site_repo" range-diff \
  "$clean_old_base..refs/heads/codex/clean-migration-before-rebase" \
  "$clean_new_base..codex/clean-migration"
```

The range-diff must show one build-profile commit and one content-and-projection snapshot commit.
Review unexpected profile changes as contract changes and expected generated churn through the projection manifest.

### 5. Run acceptance

Run the locked unit, source-schema CURIE, live service, four-collection, projection, repeat-generation, link, graph, base-path, and local browser checks.
Confirm the default interfaces are CON and upstream references require explicit selection.

Also verify that legacy-derived refs and all remote state are unchanged.
Do not treat conflict-free rebase or a successful Hugo build as sufficient acceptance.

### 6. Update the parent gitlink deliberately

Only after acceptance, return to the parent repository and inspect the proposed site gitlink change with submodule log output.
The parent change must point to the accepted two-commit site tip and must not move another submodule.

Record the old base, new base, old tip, new tip, range-diff review, projection manifest, and acceptance result alongside the deliberate gitlink update.
Do not push either repository.

Keep the before-rebase safety ref until the range-diff and parent gitlink review are complete.
Its later local cleanup is not part of the rebase itself.

## Acceptance matrix

| Boundary | Required result |
| --- | --- |
| Site history | Exactly two downstream commits above the reviewed base |
| Path isolation | Build contract, content inputs, and generated outputs remain in their declared isolated paths |
| Presentation source | Config, layouts, templates, and graph code come from the rebased site ancestry |
| Annex transport | Sibling asset/static/theme Git objects match that ancestry exactly |
| Source schema | Pinned source YAML, never the vendored resolved schema |
| Native types | Five exact `dlthings:*` CURIE fixtures pass conversion and live validation |
| Negative types | Full-URI fixtures fail closed |
| CON data | Present only in `con-public` and `con-protected` |
| German snapshot | Present only in `upstream-public` and `upstream-protected` |
| qri | Reads only `con-public` for the CON projection |
| Editor | Default SHACL Vue boundary is `con-protected` |
| Static default | Default build/server presents CON content |
| Upstream references | Available only through explicit upstream selection |
| Projection | Repeat generation is deterministic and manifest-reviewed |
| Site integrity | Pages, links, graph, and base paths pass their audits |
| Runtime | No persistent service is needed for the static result |
| Preserved history | Legacy and `orinoco-lite` refs are unchanged |
| External state | No push, Pages, DNS, domain, or production change |

## Deferred work

Do not expand this effort to include:

- complete CON metadata or editorial migration;
- production deployment or branch replacement;
- GitHub Pages or pull-request preview workflows;
- remote editing, authentication, or authorization design;
- support for full-URI designators;
- experimental LinkML or Things Schemas candidates;
- a generalized root/profile or detailed ROR design;
- a permanent metadata service;
- durable custody for every upstream annex object;
- broad visual redesign;
- action/template extraction;
- published RDF or JSONL interfaces;
- secondary projections; or
- upstream contribution work.

The clean migration ended with a locally accepted two-commit site branch and a deliberately reviewed local parent gitlink.
Its former deferred full-content work is governed by [`full-con-migration.md`](full-con-migration.md); it remains outside this frozen checkpoint.

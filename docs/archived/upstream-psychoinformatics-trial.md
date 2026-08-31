# Upstream Psychoinformatics reproduction and Pages trial

Status: local reproduction and deployment prototype complete; no production site, DNS, or GitHub Pages setting changed

Date: 2026-08-10

Branch: `codex/upstream-psychoinformatics-trial`, created from parent `main` at `47bdf2f396e462d6622a166d2ba6c29f6a273b7c`

## Executive conclusion

The current Psychoinformatics website can be rebuilt and deployed as a static site without a running Dump Things service.
The exact current upstream commit builds deterministically with Hugo Extended 0.154.5 from its committed Markdown, graph, theme, and annexed assets.
Two builds each produced 1,973 Hugo pages and 2,058 files, and a fresh checkout from the repaired `con` mirror produced the same artifact.

That result has an important limit: it reproduces the **published projection**, not the metadata system that generated it.
Regenerating or refreshing the projection still calls the live Psychoinformatics pool and a moving, unlocked `dtc`/`qri` toolchain.
The public pool's canonical records are not present in the checked-out repositories.
Therefore:

- a frozen upstream website snapshot is deployable without Dump Things;
- a fresh metadata projection is not reproducible offline from this repository set; and
- the CON Git-native approach is still needed if the lab repository is to own canonical metadata and validate each publication from source.

A standard GitHub Pages **project** URL adds a separate presentation issue.
Hugo honors the configured base URL for ordinary site links, but upstream templates, the compiled graph renderer, `graph.json`, and the web manifest contain root-absolute paths.
At a URL such as `https://con.github.io/orinoco-lite-dev/`, the graph, some controls, and installable-app icons therefore request the domain root and fail.
The trial includes a small generated-artifact adapter that leaves upstream source untouched, fixes those paths, and rejects any remaining escape.
Browser testing confirmed the homepage graph and a representative record graph at the project path with no console errors or warnings.

The remaining external static-build dependency is Git Annex storage.
The `con/www-from-model` Git mirror is now current and carries the upstream annex metadata branch, but GitHub is not an annex object store.
A fresh GitHub-only clone could retrieve 25 annexed paths from their original web URLs but could not retrieve 14 required paths, including `graph.js`, `graph.json`, core CSS, branding, and favicons.
Adding the upstream repository as an explicit annex object remote hydrated all 39 paths.
A build can therefore run today, but a fully self-contained GitHub reproduction would need to mirror all 38 unique annex objects (55,916,505 bytes), not merely the Git refs.

## Scope and isolation

This investigation is isolated from the existing Orinoco Lite and LinkML trials:

- the parent branch starts directly from `main`;
- its worktree is `/Users/johnlee/code/CON/orinoco-upstream-trial`;
- the dirty `orinoco-lite-dev` worktree and its submodule states were not changed;
- the site submodule is pinned to current upstream `5b401e0c478a4409442b3a8a285bd3efd5d30e05`; and
- only a generated deployment artifact is adapted for a Pages project path.
No upstream website source or generated content was edited.

The phrase "German patches" is interpreted here as the LinkML patches and runtime monkeypatches carried by the upstream Psychoinformatics/Orinoco repositories.
That interpretation did not block the work; the exact patch inventory is below.

## Git and mirror state during the trial

The parent had pinned `www-from-model` at `6945272e5f3fcf353627b8e1c3e68bcaf76cc2ce`.
Current upstream is three commits later:

| Commit | Change |
| --- | --- |
| `10087fa5` | Metadata refresh touching 747 files and expanding publications from 115 to 846 records |
| `e50f88f` | A subsequent generated graph refresh |
| `5b401e0c` | Changes one Register Depictions preparation action from a deleted local path to a remote URL |

The net snapshot change is large but mostly unrelated to LinkML: publications increase by 731, graph size increases from 307 nodes/882 edges to 1,038 nodes/2,148 edges, and Hugo output increases from 491 pages/576 files to 1,973 pages/2,058 files.

The account-owned `https://github.com/leej3/www-from-model.git` mirror carries the upstream site refs and the deployment branch's nested account URL.
It was populated without rewriting the upstream history:

| Ref | Current value |
| --- | --- |
| `refs/heads/main` | `6c8b9a5b7260dc20dfe1453dd863b353e8f90f06` |
| `refs/heads/git-annex` | `010ca44f751d2ab60b9d4ad58c5931d1804e3c9e` |

The parent `.gitmodules` entry now uses the `leej3` mirror.
Local site checkouts use `origin` for that mirror and `upstream` for the Psychoinformatics source.
The Hugo theme remains the exact nested gitlink `3623fa505ee42fee899844d94a4ff7f5a1ae9096` from the upstream site.

A live comparison during the 2026-08-10 trial found 20 of 24 parent gitlinks at their then-configured remote heads.
That observation was a dated diagnostic, not a durable upstream inventory.
The repository's gitlinks and implementing update pull request are the authority for an accepted stack.
The only intentional `con` URL remaining in the parent is the migration-input `dump-research-info` repository.

## Account-owned recursive mirrors

The deployment branch now uses public `leej3` GitHub mirrors for every top-level submodule except `submodules/dump-research-info`.
That repository is intentionally left at `github.com/con/dump-research-info` because it is a CON-owned migration input.
The account mirrors preserve the pinned commits and the fetched upstream branches; existing `leej3` repositories were retained without deleting their unrelated branches.
Nested dependencies are covered as well: the pool UI points to `leej3/shacl-vue`, the website and CON site themes point to `leej3/congo`, and `tools` points to `leej3/datalad-concepts`.

The account mirror set is deliberately separate from the parent repository: `orinoco-lite-dev` remains the only repository in this workflow that is not under `leej3`.
A fresh recursive checkout therefore needed only public GitHub URLs, while `dump-research-info` remained visibly attributable to CON in the parent `.gitmodules` file.

## What is actually required

The dependency boundary differs sharply by operation:

| Operation | Required inputs | Dump Things / LinkML involvement |
| --- | --- | --- |
| Rebuild committed website | `www-from-model`, Congo, 39 annexed paths, Hugo Extended 0.154.5 | None |
| Deploy committed website | Rebuilt static artifact and a static host | None |
| Refresh pages and graph from current pool | Live `https://pool.psychoinformatics.de/api`, `dtc`, `qri`, `pool2graph.py`, Jinja templates, Annex, Forgejo actions | The remote pool service has already validated records; the refresh client itself uses no local LinkML model generation |
| Register/update depictions | Live pool, enrichment script downloaded from moving `main`, remote media URLs, Annex, deposit action | No local schema generation, but several unpinned remote services and actions |
| Recreate the pool from canonical records | Canonical source records, schema, LinkML, Dump Things service/client, storage and authorization configuration | Full stack required; the source record snapshot is missing here |
| Build Orinoco Lite from Git-owned YAML | Git records, pinned schema/toolchain, ephemeral local Dump Things, qri, templates, Hugo | Full validation/projection stack runs temporarily, then is discarded |

For the static deployment, only one parent submodule is needed: `submodules/www-from-model`, plus its nested Congo submodule.
The other Orinoco submodules are diagnostic or refresh inputs, not static runtime dependencies.

## Local reproduction

The current repeatable entry point is a locked standalone Pixi script:

```bash
pixi run serve-upstream-static
```

It serves the result at `http://127.0.0.1:8768/`.
`pixi run build-upstream-static` performs the same build without starting a server.
The script's inline environment pins Python, Hugo, and git-annex independently of the root engineering environment, then the builder:

1. checks out only the pinned upstream site and Congo theme;
2. pins annex metadata at `010ca44f...`;
3. retrieves annex content, using the upstream hub explicitly for objects that are not available from ordinary web URLs;
4. requires Hugo Extended 0.154.5;
5. builds the unchanged upstream source with the requested base URL; and
6. adapts and audits only the generated artifact when the URL has a non-root path.

The full measured result is in `provenance/upstream-psychoinformatics/baseline.yaml`.
Important values are:

| Measure | Result |
| --- | ---: |
| Committed record bundles | 15 datasets, 25 instruments, 5 objectives, 27 persons, 15 projects, 846 publications, 19 topics |
| Graph | 1,038 nodes, 2,148 edges |
| Hugo output | 1,973 pages, 2,058 files |
| Exact-build output size | 102,474,096 bytes |
| Repeatability | Two byte-identical sorted content manifests |
| Live pool requests during build | 0 |
| Dump Things processes during build | 0 |

The manifest digest records a sorted list of each relative output path and its SHA-256, then hashes that list.
It is a comparison identifier for this trial, not an upstream release checksum.

## Browser and GitHub Pages result

Three browser cases were checked:

1. An exact `hugo --minify` build inherits upstream's production `baseURL=https://www-draft.psychoinformatics.de`.
Its locally served HTML tries to load theme assets from that production host.
This is expected configuration behavior, not a missing build file.
2. A root-local build with `--baseURL http://127.0.0.1:8767/` loaded all theme and graph assets locally.
The homepage displayed seven Sigma canvases with no console error or warning.
3. A project-path build with `--baseURL http://127.0.0.1:8766/orinoco-lite-dev/` loaded normal Hugo navigation but initially requested `/graph.js` and `/explore` at the domain root.
After the artifact adapter, the homepage and a representative dataset page each displayed seven graph canvases, and all tested navigation stayed below `/orinoco-lite-dev/` with no console error or warning.

Before adaptation the project-path artifact contained:

| Root-path source | Count |
| --- | ---: |
| HTML `href`/`src` references | 974 |
| Compiled graph fetch for `/graph.json` | 1 |
| Graph node navigation URLs | 998 |
| Web-manifest icon URLs | 2 |

The adapter changed 962 generated HTML files, 974 HTML URLs, one graph fetch, 998 graph node URLs, and two web-manifest icon URLs.
A second pass made zero changes, the path-leak audit reported zero findings, and two clean build/adapt runs had the same manifest digest `a58fee0aec0d8725c72b7d26068dc340b742494c4520480f80555e1dc6246c14`.
A fresh checkout from the repaired GitHub mirror produced that same digest.

The adapter is intentionally downstream deployment glue.
A preferable general upstream change would make templates use Hugo `relURL`/`RelPermalink`, pass a base-aware graph-data URL into the renderer, and make `pool2graph.py` emit site-relative or explicitly based navigation values.
Until such a change is accepted, changing only the generated artifact avoids maintaining a fork of the upstream website source.

The repository has no GitHub Pages site configured at present: the GitHub API returns `404` for the parent, site mirror, and legacy CON site repositories.
The included manual workflow is ready for a Pages site whose source is set to GitHub Actions, but this trial deliberately did not enable Pages or publish an external preview.
This avoids claiming a shared Pages environment or changing any production domain before review.

## Local SHACL Vue and service-backed editor

The upstream edit footer originally hard-codes `https://pool.psychoinformatics.de/ui/`.
Pixi-controlled local builds set `SHACL_VUE_URL=http://127.0.0.1:3000/`; the generated-artifact adapter rewrites the 953 edit links while preserving each `sh:NodeShape`, `pid`, and `edit=true` query parameter.
The production Pages workflow leaves the upstream URL as its default, so this local stack does not alter the static deployment.

The editor was also deployed with the upstream service architecture locally during the original trial.
That capability now has a scoped locked entry point:

```bash
pixi run serve-upstream
```

It initializes the exact recorded site, theme, pool UI, SHACL Vue, Things Schema, and Dump Things gitlinks; resolves their tools in `tools/upstream_full.py` rather than the root environment; builds and checks the site and UI; seeds isolated `public` and `protected` collections; proves the editor write boundary; and serves the result at `http://127.0.0.1:8768/`.
`check-upstream` runs the same finite acceptance and stops all child processes.

Both static and full scopes also expose `*-worktree` tasks.
Recorded tasks reject modified submodules and restore the commits in the parent tree.
Worktree tasks initialize missing repositories but preserve current commits, tracked edits, and untracked files, allowing coordinated upstream changes to be tested before their gitlinks are recorded.
See [`../README.md`](../README.md) for the task matrix and update workflow.

The isolated supervisor writes generated configuration, credentials, stores, snapshots, and logs below ignored `build/upstream-stack/` state; Ctrl-C stops the complete stack.
The supervisor:

1. downloads or reuses a digest-checked public `Thing` snapshot below `build/upstream-stack`;
2. runs pinned Dump Things service commit `9f101d97c7f15d491f602db5a9c33ad9a19ad8bf` against generated configuration and the pinned source Things Schema;
3. seeds the snapshot into both local `public` and `protected` collections;
4. exposes a local git-annex repository at `http://127.0.0.1:8122/git-annex`, using the same p2p-over-HTTP path shape as the upstream uploader; and
5. builds and serves the tracked pool UI and nested SHACL Vue source at port 3000.

The measured historical snapshot contained 4,978 records.
The current task found 4,979 records on 2026-08-14.
After a full-stack preparation, `pixi run diff-upstream-pool` fetches the current public collection separately and compares it semantically with the digest-checked cache by PID.
It leaves the cache untouched, prints a bounded added/removed/changed summary with changed JSON-pointer field paths, and writes the full ignored report to `build/upstream-stack/pool/live-diff.json`.
The command succeeds when differences exist because live data drift is expected; the underlying script's explicit `--check` option is available when a strict equality gate is intended.
Uploads are keyed and stored by git-annex; they are not written to a demo-data directory.
The nested SHACL Vue checkout is pinned to `3be33196f0eb7a65817df78b88ea40ecbb5eca11`.
The deployment branch tracks its local service configuration, generated schema assets, and local git-annex target as reviewable commits.

The pool UI uses `use_service: true` and `use_token: true`, with read/write URLs pointing to the local Dump Things `public`/`protected` collections.
Its `config_default_xyzri.yaml` keeps `data_url` empty so no bundled RDF records are mistaken for the source of truth; schema, shape, and prefix assets are served from the tracked deployment checkout.
Direct local API calls use the same `/record` and `/records` route forms consumed upstream.

The original browser verification opened a generated dataset edit link, fetched the real record through local Dump Things, changed its title, and submitted it.
The protected incoming view contained the new title while protected curated and public remained at the old title, demonstrating the upstream curation boundary.
The current `check-upstream` task checks the same collection confinement at the API boundary, as well as exact seeded records, schema/UI configuration, and the generated static site.

This is a faithful local deployment of the service interactions, with three explicit scope limits: the local protected collection is seeded from the public upstream snapshot rather than private records requiring credentials; the local git-annex repository is a single-process development service, not a production Forgejo host; and a fresh checkout fetches the current public pool rather than an immutable archived snapshot.
None is hidden behind bundled demo data or a disabled backend; the limits are visible in generated runtime state and this engineering record.

## Annex boundary and GitHub-only reproducibility

The upstream source has 39 annexed worktree paths representing 38 unique keys and 55,916,505 hydrated bytes.
There is no Git LFS configuration.

A fresh clone from `leej3/www-from-model` showed two availability classes:

- 25 paths can currently be fetched through URLs registered in annex; and
- 14 paths (1,276,022 bytes) are available only from the upstream annex repository.
These include the graph bundle/data and first-party visual assets.

The exact paths and keys are recorded in `baseline.yaml`.
The Pages workflow adds the upstream repository as an object remote and pins the annex metadata commit, so it is operational without Dump Things.
It is not fully independent of Psychoinformatics infrastructure.

To make the build GitHub-only and durable, mirror **all** 38 unique object contents to an immutable GitHub-compatible store and record content hashes.
Reasonable options are a release-asset bundle, a dedicated Git LFS asset repository, or normal Git for the small first-party files plus immutable release storage for the 48 MB depiction.
Copying only the 14 hub-only objects would make today's build work but would leave the 25 URL-backed objects exposed to origin removal or content drift.

## Static snapshot quality findings

The current upstream snapshot has issues unrelated to the Pages base path:

- 26 of 998 graph navigation URLs have no generated target page: 8 organizations, 8 persons, and 10 projects.
Some graph entities are retained as relationship context even though the page-refresh queries intentionally filter which records receive pages.
One person also has an obsolete slug override (`/persons/yaroslav-halchenko`) while the generated page uses an ORCID-derived route.
- Generated HTML contains seven unique missing targets across eight link occurrences: two malformed DataLad hub paths, two root-style ORCID links, three depiction record links, and `/projects/trr379`.
- `register-depictions.yaml` is only partially repaired at current head.
Its preparation action now comes from the remote Flow repository, but its final step still references the deleted local `./.forgejo/actions/deposit-changes`.
Earlier steps can change/push Annex state before that final failure, so the workflow is not transaction-safe.

The exact missing targets are in `provenance/upstream-psychoinformatics/missing-targets.tsv`.
The Pages adapter does not hide or reinterpret these content defects; it only keeps root-local paths inside the deployment base path.

## Static deployment versus metadata refresh

The upstream deployment workflow is simple and successfully reproduced: checkout, install Git Annex, hydrate Annex, initialize Congo, install Hugo 0.154.5 Extended, and run `hugo --minify`.
It does not invoke the pool, schemas, LinkML, Dump Things, or qri.

The refresh workflow is materially different:

1. `dtc get-records` contacts `https://pool.psychoinformatics.de/api`.
2. `qri cache`, exact class filters, inlining, and Jinja rendering create the committed Markdown bundles.
3. `code/pool2graph.py` creates `static/graph.json`.
4. the workflow commits generated content and pushes annex state.

Its environment is not reproducible from the workflow definition:

- Flow is referenced as moving `@main`;
- Flow installs qri without an immutable lock;
- qri declares the Dump Things Python client from moving `@master`;
- no Python environment lock or artifact hashes are committed; and
- the full canonical pool input cannot be reconstructed from `psyinf-pool-files-public`, which contains depictions rather than records.

This explains the apparent paradox: the website is a stable static output once committed, while the process for producing a new output is neither offline nor fully pinned.

## LinkML bugs, carried patches, and content compensations

### Why the static trial bypasses the problem

The static build imports no Python packages and reads no schema.
LinkML's discriminator behavior, Things Schemas' install-time patches, and Dump Things' runtime monkeypatches therefore have no direct effect on rebuilding the committed snapshot.
This is why current upstream can deploy even while the LinkML remediation remains unresolved upstream.

Those components become relevant when records are validated, converted, loaded into generated models, selected by qri, or re-rendered.
A static success must not be treated as evidence that the metadata stack is reproducible or that discriminator behavior is correct.

### Current LinkML discriminator state

The trial identified four related upstream changes, none merged into official LinkML `main` (`c8b9bac95eb62891d8a9e5703a2ce688fdf09ce8` when checked):

| Concern | Current proposed change |
| --- | --- |
| Preserve an uncompactable URI rather than producing `"None"` | LinkML PR #3839, head `2da67e47...` |
| Dispatch a generated Python subclass from a full URI | LinkML PR #3840, head `bf9903fd...` |
| Permit equivalent CURIE/full-URI values in generated JSON Schema | LinkML PR #3843, head `a285bcfc...` |
| Cross-generator compliance coverage | Draft LinkML PR #3847, head `e0176a27...` |

These heads are independent, not one installable candidate.
The earlier local composite `793dfc12...` remains valuable evidence against LinkML 1.11.1, but a new pin should build and hash an explicit current composite rather than combine moving PR heads implicitly.

### Things Schemas file patches

Things Schemas `d26ea413...` declares only `linkml>=1.11` and an unbounded Dump Things dependency.
Hatch then mutates the installed LinkML tree using `tools/patch_linkml`; there is no lock or derived wheel.

| Patch | State | Relationship to discriminator work |
| --- | --- | --- |
| `shaclgen_annotations.diff` | Active | SHACL order/path/prefix behavior; unrelated |
| `rdflib_loader_typedesignator.diff` | Active | Populates a designator from RDF `rdf:type`; adjacent but different from generated Python dispatch/JSON Schema |
| `graphqlgen_interface_list.diff` | Active | GraphQL interface syntax; unrelated |
| `linkml_generators_common_ifabsent.diff` | Active | CURIE default generation; URI-adjacent but not discriminator lookup |
| `rdflib_loader_custom_types.diff` | Active | RDF datatype registration; unrelated |
| `linkml_runtime_utils_yamlutils.diff` | Disabled | Its inlined-object fix is already in LinkML 1.11.1 |
| `pythongen_type_reference_order.diff` | Disabled | Reference ordering was reimplemented in LinkML 1.11.1 |
| `jsonschemagen_mixins.diff` | Present but unused | Old mixin proposal; not part of the patch runner |

The five active patches applied to the earlier LinkML candidate without reject, fuzz, or overlap, and did not modify the candidate's three production files.
That only proves compatibility with the old candidate.
The exercise must be repeated against a current composite.

### Dump Things runtime monkeypatches

Dump Things `9f101d97...` imports six monkeypatches whenever its generated-model stack is loaded:

| Monkeypatch | Assessment |
| --- | --- |
| `compile.py` | Still addresses a meaningful generated module-name issue |
| `enumerations.py` | Useful against 1.11.1, but would overwrite newer LinkML main enum/MRO/`PermissibleValue` behavior |
| `ifabsent_processing.py` | Duplicates the active Things Schemas `ifabsent` patch |
| `pythongen_gen_references.py` | Replaces behavior already fixed in LinkML 1.11.1; retire or version-gate |
| `rdflib_loader.py` | Duplicates the RDF type-designator patch and replaces a whole upstream function, discarding newer namespace, `@base`, enum, and diagnostic improvements |
| `yamlutils.py` | Replaces an already-fixed, more comprehensive 1.11.1 implementation; retire or version-gate |

This is the highest-risk compatibility boundary.
A dependency resolver can select a newer LinkML version while these full-function replacements silently restore older semantics.

There are also two different effective patch stacks:

- Things Schemas development installs LinkML and applies five file patches in its Hatch environment.
- The current CON Pixi site does not install Things Schemas as a package.
It uses pristine locked LinkML 1.11.1 wheels, a vendored schema snapshot, and the six Dump Things runtime monkeypatches.

Consequently, "the Orinoco LinkML stack" is not one environment.
Schema generation and service/site validation must be recorded and tested separately.

### Schema identity correction

The Things Schemas candidate `33604b1a...` is two commits beyond upstream.
It explicitly declares `dlthings:Association`, `dlthings:Attribution`, `dlthings:Generation`, `dlthings:DOI`, and `dlthings:ISSN` in stable and unreleased modules and tests the direct and merged schemas.

This fixes an identity problem distinct from lexical normalization.
The intended stable identities are Things v2/unreleased URIs; module-derived `things-prov/...
` and `things-publications/...
` URIs remain deliberately invalid. Existing records that use the canonical `dlthings:*` CURIEs do not need a semantic migration after this correction.

### Why accepted full URIs can still disappear downstream

LinkML validity alone does not make the current pipeline representation agnostic:

- `qri list` compares top-level `schema_type` strings exactly;
- `pool2graph.py` dispatches exact `xyzri:*` strings; and
- dataset, instrument, and publication templates test exactly for `dlthings:DOI`.

qri preserves lexical input.
A full URI can therefore be valid in LinkML and Dump Things yet be omitted from a class-filtered page/graph or rendered as a missing DOI.
The earlier integration trial reproduced those failures.

The safe publication contract for the current stack is still canonical CURIEs.
A future full-URI policy needs one schema-aware normalization boundary before qri/template/graph dispatch, with adversarial tests proving that wrong or out-of-hierarchy URIs remain rejected.

### Current CON content compensation

CON Milestone 1 works around the native-container failure at a deliberately bounded boundary:

- relationships are stored as PID-valued `dlthings:AttributeSpecification` assertions rather than native Association, Attribution, or Generation containers;
- DOI/ISSN notations are generic `dlthings:Identifier` values rather than typed DOI/ISSN subclasses;
- source roles such as `marcrel:aut` and `marcrel:led` remain in structured migration provenance; and
- `scripts/project_records.py` converts a fixed predicate set into generic site edges while preserving each original source/predicate/target assertion.

This compensation retains graph and page utility, but it does not claim native qualified-edge or typed-identifier semantics.
It should remain until a pinned LinkML/schema/service/client/qri tuple passes native fixtures end to end.
Then the records can be migrated to native structures and only the compatibility normalization removed; generic route, taxonomy, backlink, and graph generation can remain.

## Recommended blend with the existing effort

This branch is a useful baseline, but it should not erase the distinction between static reproduction and canonical-data publication.

Recommended sequence:

1. Keep `5b401e0c`, its Annex manifest, Congo, Hugo, and the Pages adapter as a frozen current-upstream smoke/reference layer.
2. Retain `6945272e` as the smaller controlled discriminator comparison.
The current snapshot's 731 extra publications add test cost and review noise without adding discriminator coverage.
3. Rebase or replay the existing discriminator work onto this parent branch in separate commits only after this baseline is accepted.
Keep the LinkML composite, schema identity correction, and downstream normalization tests independent from the site snapshot/gitlink change.
4. Gate/remove obsolete Dump Things monkeypatches before testing against a new LinkML composite.
Record base wheel hashes, patch hashes, and the effective patched tree or derived wheels; a package version lock is insufficient for post-install mutation.
5. Run the five native classes through direct service post, qri cache/list and inlining, template rendering, and graph generation with both canonical CURIE and equivalent full URI fixtures.
Keep invalid modular, unknown, and wrong-hierarchy values as negative controls.
6. Keep CON's canonical YAML and ephemeral validation design.
Use the upstream committed website as a visual/projection reference, not as the source of truth for CON metadata.
7. Before a durable Pages deployment, mirror all annex content, fix or pin the refresh actions/toolchain, and decide whether to repair the 26 dead graph targets and seven missing HTML targets upstream or filter them during projection.

This gives the requested reassurance: all upstream presentation code and its current generated content can run and can be adapted to GitHub Pages without a persistent metadata service.
It also shows precisely what that success does not reproduce—the canonical pool, a locked refresh toolchain, Annex object custody, and a representation-safe LinkML-to-qri boundary.

## Deliverables

- `.github/workflows/upstream-pages-trial.yml`: historical manual, pinned Pages workflow removed from current `main` when engineering Pages retired
- `tools/build_upstream_site.sh`: local upstream checkout/hydrate/build entry point
- `tools/adapt_upstream_pages.py`: artifact-only project-path adapter and audit
- `tests/test_adapt_upstream_pages.py`: focused rewrite, validation, and idempotence tests
- `provenance/upstream-psychoinformatics/baseline.yaml`: exact commits, versions, counts, hashes, and Annex availability
- `provenance/upstream-psychoinformatics/missing-targets.tsv`: exact upstream dead-link evidence

No GitHub Pages site was enabled, no workflow was dispatched, and no production deployment or DNS record was changed.

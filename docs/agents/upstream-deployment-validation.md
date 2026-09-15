# Review upstream deployments

Maintainers and agents use this guide to assess the [thin deployment layer](../project-design.md#validate-the-deployment-layer).
Keep current differences here, disposable diagnostics untracked, and history in Git and pull requests.
Known differences are not automatically accepted deviations.

## Current comparison

The September 2026 comparison regenerated both sites from one retained 5,030-record Pool capture, not committed record pages.
The capture is `build/upstream-stack/pool/public-thing.jsonl`, SHA-256 `2b11038f95b953867356fa7bdce370a10a143d263814a835af29b69c662acd38`; this is not a claim about today's live Pool.
Package candidate `a7a9cfa` is based on merged PR 150; template candidate `3bfa867` is based on merged PR 74.
Both use gitlink-selected `www-from-model` (`a2e4534`), its declared Congo dependency, and Hugo 0.154.5.

Native generation used the selected DumpThings service, its SQLite backend, an isolated public collection, and a fresh query cache.
All 5,030 captured record dictionaries survived the native API/cache exactly, including schema types. Extra cache entries were 32 missing-record results and an equivalent URI lookup of captured `isil:DE-Juel1`, not external records. All 228 committed generated pages and the graph were removed before replaying the selected query/Jinja workflow.
No metadata reads went to the live Pool.

Lite used ordinary `dev setup`, editable package development, Copier update, `build`, and `verify-site` in a separate disposable downstream.
Its 5,030 canonical records and 787 machine-provenance companions remain distinct from generated output.
The final fixture also supplies the same 25 already-materialized page-bundle images as native, as ordinary downstream inputs—not package/template assets.
Their upstream VURL keys identify URLs rather than immutable image bytes; this establishes equal input bytes, not fresh acquisition or redistribution rights.

The final rebuild retains all 254 native HTML routes and titles; Lite adds only `/edit/` and its OIDC callback.
All 228 metadata pages match by PID, route, title, and Markdown body.
Graph node objects (1,072), counted relationship endpoints (2,288), and all 253 search entries match semantically.
Restored portraits and record logos have identical output paths and bytes.
Only the extra Lite homepage heading differs in shared main text.
Remaining media variation is four native-only branding files and four changed favicons (67 native media files, 63 Lite); there are no introduced missing local references.
This supports the core generation claim for the capture, not unconditional visual, data-normalization, or interaction parity.

## Differences and resolution

| Difference / source | Resolution |
| --- | --- |
| Member-based publication/dataset selection; five named URLs | **Fixed regression.** Match native query filters and scalar annotations passed to Jinja. Keep focused pytest coverage; never ignore missing routes. |
| Collaboration Hub URL/target and Contact footer | **Fixed regression.** Preserve captured navigation and render external URLs. Empty Outputs links are dropdown controls, not the same defect. |
| Five missing listing introductions | **Fixed setup regression.** Preserve authored section indexes, never old generated home/record pages. Check search content too. |
| Missing portraits and record logos | **Input gap, corrected in this fixture.** Metadata capture does not contain image bytes. Initially 57 native image files/renditions were absent, including visible resources. Supply matching ordinary page-bundle media through site-specific inputs. **Address soon** if snapshot-only setup must produce a visually complete replica; do not add personal media to the template or Annex to downstream builds. |
| Header/institution logos, Windows tile image, four favicon contents, copyright, extra home heading and Hub label | **Presentation choice; not accepted as replica fidelity.** Neutral defaults avoid inheriting another site's identity. Configure an explicit identity/presentation fixture when needed. The extra heading/label are not required by static curation and need separate review. |
| Editing routes/data, package/content/build footer and license notices | **Deliberate architecture; ignore for upstream-content parity.** Validate these features separately. This does not excuse missing native content or navigation. |
| Graph edge IDs/order; graph fetch cache-query suffix | **Safe narrow heuristic.** Compare full node objects and counted endpoints; ignore IDs/order only while edges contain only `id`, `source`, `target`. Strip only the known graph fetch cache query, not arbitrary URLs. |
| Graph node positions and label visibility between page loads | **Runtime layout variation.** Ignore force-layout geometry in paired screenshots only after graph data, filters and navigation agree. Do not mistake changing positions or label culling for changed metadata, or mask the entire graph without functional checks. |
| Annotation envelopes; 21 records' full-URI versus declared CURIE PAV tags | **Representation-only for this capture.** Compare joined records using schema-declared namespace equivalence. Nine person frontmatters also differ in nested annotation representation; Michael Hanke's ISIL creator is not expanded in Lite. Current identifier links/icons are unaffected. **Later** if those fields become visible or consumed. |
| Publication `fec91e0d-f22a-42c8-8170-a0dd87da53f7` loses `generated_by[0].at_time: "-"` | **Decision required; soon.** Existing conversion omits an invalid optional datetime sentinel. This is a source-value change, not formatting noise. Retain the capture and review explicit conversion policy or an upstream correction before general acceptance. |
| Nine broken HTML-link references and 790 unresolved graph paths, shared by both | **Inherited upstream behavior; visible broken links soon, graph-scope policy later.** Examples: a scheme-less `hub.datalad.org/datalad/datalad-core` link, `/orcid:0000-0003-3456-2493`, and `/depictions/logo_abcd-j`. Graph links also target filtered-out people/publications because graph records and page selectors have different scopes. Matching upstream proves inheritance, not correctness; never suppress all broken links. |
| Three native-only dataset JSON/JSON.gz payloads under `datasets/e511f0bb-9baf-4c29-88e0-079836868273/` | **Scope decision / later.** These unlinked bundle resources are not regenerated by either metadata pipeline. Supply them as site-owned resources if direct-download compatibility is required; do not copy them merely to equalize file counts. |

For each new difference record an example, source, visible impact, owner, and disposition: fixed, deliberate, narrow heuristic, later, soon, or decision required.
Hashes, successful builds, and a zero normalized diff do not replace that judgment.

## Repeat the exercise

Choose package/template candidates and one capture.
For a fresh capture use `pixi run python tools/prepare_upstream_snapshot.py --refresh`, optionally `--api URL`.
An unknown or different cached API origin requires explicit refresh; never refresh one side independently.
Acquisition alone is not a deployment test.

Create a new downstream without replacing a developer's existing checkout:

```console
pixi run orinoco-lite dev setup /path/to/new-downstream \
  --template /path/to/orinoco-lite-template --snapshot /path/to/pool.jsonl
cd /path/to/new-downstream
pixi run orinoco-lite build --base-url /
pixi run orinoco-lite verify-site build/site
pixi run orinoco-lite serve
```

Setup uses the normal Copier questionnaire and DataLad recording path, and stops before projection/building.
Use `--site-specific /path/to/input-repository` for a prepared Git repository of site inputs instead of snapshot conversion.
Place required ordinary media under `site-specific/content/<record-route>/`; never place old generated record Markdown there, because site-owned content overrides generated pages.
Use `dev enable` for an existing downstream, Copier for template changes, and `dev prepare-resources` after resource-source changes.
Editable presentation resolution uses committed objects from the local package checkout; unpublished commits do not require pushing to GitHub.

For the native reference:

1. Select the service, query client, schema and website checkouts; resolve Congo through the website's declaration.
   Required presentation assets must already be available.
   Media acquisition remains a separate operation.
2. Start `dump-things-service STORE --config CONFIG --host 127.0.0.1 --port PORT` with a fresh `public` collection, selected research-information schema, `sqlite+stl`, anonymous `READ_CURATED`, and a disposable local `CURATOR` token.
   Never seed an existing service or the public Pool.
   SQLite avoids repeated full-directory scans during reverse-link injection.
3. Using the selected client and local token, seed with `jq -c '.record' CAPTURE | dtc post-records --curated LOCAL_API public '*'`.
   Read back and check PIDs and values, not merely the count.
   Supply selected query/client sources and their declared dependencies; do not accidentally install a moving client branch.
4. Copy the selected presentation to scratch.
   Remove generated Markdown identified by `params.graphRootNodePID`/`params.generated`, plus `static/graph.json`; retain authored pages, section introductions and bundle resources.
   Use a fresh `QRI_RECORD_CACHE` and local `DUMPTHINGS_APIURL`.
   A warm cache plus live API mixes datasets.
5. Read [the selected update workflow](../../submodules/www-from-model/.forgejo/workflows/update-from-pool.yaml) and execute its graph, member-selection, seven entity and frontpage commands with pipeline failures enabled.
   Omit checkout, provisioning, deposit and Annex operations; remove only the graph step's trailing Annex-recording command.
   Do not maintain copies of its query pipelines.
   Run selected Hugo with `--minify --baseURL /` into a fresh destination, then stop the service.

Compare complete HTML route sets, including orphans; Markdown paths are not necessarily published URLs.
Compare joined record meaning, graph objects/endpoints, search entries, page text, referenced media and downloads. Inspect home and one page of each rendered class at the same viewport; exercise search, menus and graph navigation. Missing images can disappear from HTML without broken URLs, so compare expected visible resources too. Retain pytest coverage of changed/deleted record regeneration instead of a second deployment framework.

## Tools and limits

[SiteDiff](https://github.com/evolvingweb/sitediff#comparing-2-sites) is optional, not a package dependency.
Supply the union of routes explicitly and use `--cached=none`; a crawl misses orphan pages.
Check unchanged, changed and missing pages before trusting normalization.
The investigated 1.2.11 installation had MIME/doctype parsing caveats, so this run used disposable static inspection plus browser checks instead of adopting it as a gate. [BackstopJS](https://github.com/garris/BackstopJS#comparing-different-endpoints-eg-comparing-staging-and-production) supports paired visual checks if recurring review justifies its configuration.
Keep scratch checkers and detailed output untracked; no bespoke framework or new Pixi task suite is required.

Package pytest passed 325 tests; template pytest passed 22 source tests.
The final Lite build produced 846 files and passed the site check for localhost and 127.0.0.1 (60 homepage references each); that check is not an all-route/asset test. An isolated headless Chromium 151 context rendered 16 representative pages (home and seven record classes on both sites) at 1273×768, with expected images and graphs, no console/page errors, and no external requests.
Paired home/person screenshots confirmed the restored media and remaining presentation differences. Lite interaction checks passed: keyboard search for DataLad to its named project/instrument, Outputs menu to Datasets, appearance toggle/restore, graph Project filter off/on, and double-click on the rendered DataLad node to its project page.
Native search, navigation and graph double-click were also exercised in Safari before the desktop locked; the isolated Chromium checks completed without unlocking it or using a user browser profile.
These are bounded desktop-browser checks, not exhaustive responsive or cross-browser coverage.
Authenticated curation, live Pool freshness, upstream publication and media acquisition were not tested.
The local fixture has no configured GitHub repository, so review is disabled.
No repositories were merged and no hosted workflow was changed.

# Upstream comparison: current findings

## Summary

The same retained Pool capture can generate a website through native ORINOCO and through Orinoco Lite.
The earlier comparison found matching record pages, graph relationships, and search entries after the package fixes below.
It also found presentation differences, missing downloads, inherited broken links, and one source-value change that still needs a decision.
This is not evidence that Lite matches today's production or draft website.

Use the [comparison procedure](../upstream-comparison.md) to repeat the checks.
That procedure names the retained repositories, the native generation steps, the comparison tool, and its limits.
This report records findings, not another set of package pins.

## What the checks used

The native reference used the selected [`www-from-model` commit](https://github.com/ORINOCO-Lite/www-from-model/commit/a2e4534bc38a6dc0f30effed354773f1da984a18).
It follows upstream `main`, with retained changes to mobile navigation labels, publication-date handling, and a Congo branch hint.
Both builds use its declared Congo dependency and Hugo 0.154.5.
Shared source changes are therefore not independent evidence that those changes match upstream.

The native run loaded all 5,030 captured records into a temporary local Pool and used a new query cache.
It removed 228 committed generated pages and the graph before running the selected query, Jinja, and Hugo commands.
The API and cache retained the captured values.
No metadata reads used the live Pool.
The temporary Pool stopped after generation.

The repeat build uses the persistent [Psychoinformatics downstream](https://github.com/ORINOCO-Lite/psychoinformatics-downstream/tree/d5b82c583c84db65688f467689f43b7d6ad998f7).
Its recorded site-specific submodule supplies the capture, 5,030 YAML records, 787 annotation companions, authored pages, and 25 images.
Its dependency files select package `836fed5` and template `3bfa867`.
A fresh recursive clone passed frozen installation, the ordinary build, and `verify-site`, producing 846 files.
The raw capture matches the native run's input byte-for-byte.
The retained YAML also passes the capture comparison under the existing conversion rules, including the date omission described below.
The capture's original time and API origin remain unknown.
The repository creation date does not establish either fact.

Upstream deploys `main` to [the draft site](https://www-draft.psychoinformatics.de/) and `published` to [the production site](https://www.psychoinformatics.de/).
The [deployment workflow](https://hub.psychoinformatics.de/www/www-from-model/src/commit/dc2a3f2d4734cdd16b33bbcdd654687f809ef29a/.forgejo/workflows/deploy.yml#L45-L51) confirms the distinction.
The `published` workflow uses older query commands and different page-selection rules.
Neither live deployment's exact build commit was established by this comparison.

## Which tools produced the findings

**Earlier generation comparison:** A disposable Python `review.py` script compared routes, page text, graph data, media, and local link targets.
Separate checks compared generated record Markdown and search entries.
Playwright with headless Chromium checked representative pages and interactions.
SiteDiff was investigated but did not produce those results.
The scratch scripts are not a maintained package feature.

**Current tool check:** The procedure now uses [`summarized-sitediff`](https://github.com/yarikoptic/summarized-sitediff/tree/487f39bf6dd6e8b2810a23385b51ea8baa6048bf), specifically `sitediff (3).py`.
It compares all HTML files in both output directories, including pages without incoming links.
The run uses `--no-cache --strict-unicode --max-hunk-lines 10000` and writes JSON and Markdown reports.
It uses no exclusions and makes no LLM call.
An unfiltered `git diff --no-index` accompanies the report because the tool misses some changes.
The review links the generated reports separately.
The supplementary Python check still supplies graph, media, and broken-link results that this tool cannot produce.

| Tool result | Count |
| --- | --- |
| Shared HTML pages | 254 |
| Shared pages with HTML differences | 254 |
| Native-only HTML pages | 0 |
| Lite-only HTML pages | 2 |
| Grouped changes | 471 |

Every shared page changes because navigation, branding, footer, or editing markup differs.
That count is not a count of regressions.
The explanations below separate those repeated changes from missing content and metadata changes.

The tool's self-comparison found 254 identical pages.
Small test pages confirmed that it detects added and removed pages without incoming links.
Those tests also showed that it misses hexadecimal identity changes, script URLs, image URLs, and graph data.
Do not use a zero tool diff as an acceptance decision.

## Differences and proposed action

### Deliberate: editing links and build information

On 228 generated pages, Lite replaces the Pool editing link with its own `/edit/` link.
It adds the editor and its sign-in callback pages.
It also adds package and build information to the footer.
These differences follow the static editing design and can remain.
The package owns them, and authenticated editing needs separate tests.

### Deliberate: the Explore notice

The retained inputs change `/explore/` to say that this is an unofficial site built from a retained capture.
They also say that it does not refresh automatically.
Keep this notice while those statements remain true.
The site-specific repository owns it.
Its latest Explore page uses the template's graph shortcode instead of copied graph markup.

### Decision needed: site identity

Lite omits the upstream institution logos and copyright text and supplies different favicon images.
For example, the native home page links institutional logos to FZ Jülich and HHU, while Lite omits those blocks.
These are neutral template defaults, not proof of an exact visual match.
The site maintainer must choose the required identity and confirm media rights.
Do not copy institutional branding into the reusable template to hide this difference.

### Fix soon or explicitly accept: extra heading and mobile menu entry

Lite adds a `Psychoinformatics` heading on `/`.
Its mobile menu also includes `Collaboration hub`, which the native mobile menu lacks.
Neither difference is required by static editing.
The template maintainer should remove these differences or explain the intended presentation change before claiming visual agreement.

### Decision needed: Explore graph height

The new site-specific Explore page uses the template graph shortcode.
Native gives the graph a full viewport of height, while the shortcode uses 55 percent with a 320-pixel minimum.
At the checked 1273×768 viewport, that changes the graph from 768 to about 422 pixels high.
The graph still renders, filters, and navigates correctly.
The site and template maintainers should choose the intended height.
This is a layout change, not random graph positioning.

### Decision needed soon: one date value disappears

Publication `xyzrins:publications/fec91e0d-f22a-42c8-8170-a0dd87da53f7` contains `generated_by[0].at_time: "-"` in the capture.
The converter omits it because it is not a valid date value.
This changes source data, even though the optional value did not change the checked page content.
The package maintainer needs an explicit conversion decision or an upstream correction.
A successful conversion check does not approve this existing rule.

### Fix soon: broken page links inherited from upstream

Both outputs contain nine broken local HTML references.
Examples include `/depictions/logo_abcd-j` and `/orcid:0000-0003-3456-2493` from project pages.
The DataLad instrument link also lacks a URL scheme, so browsers interpret it as a local path.
The upstream or site maintainer should correct the data or link handling.
Matching upstream does not make a broken link acceptable.

### Decision needed later: graph links without pages

Both graphs contain 790 paths without a corresponding local page.
The graph includes records that the website's page-selection rules exclude.
The project must decide whether those nodes should link elsewhere, have no page link, or gain pages.
Do not suppress all missing graph targets as harmless.

### Later: annotations stored or expanded differently

Lite stores machine provenance in separate annotation companions.
The earlier check found equivalent long and short provenance annotation names in 21 records, such as `http://purl.org/pav/importedBy` and `pav:importedBy`.
Nine person pages also differ in nested metadata, including Michael Hanke's unexpanded ISIL creator reference.
The checked identifier links and icons remain unchanged.
The package maintainer should revisit these differences if a template starts to display or consume those nested values.
Ignore only established identifier equivalence, not arbitrary changes to metadata.

### Decision needed later: three dataset downloads

Native output includes `dataset.json` and two commit-named `.json.gz` files under `/datasets/e511f0bb-9baf-4c29-88e0-079836868273/`.
Lite omits them.
Neither metadata generation process recreates these retained resources, and the checked pages do not link to them.
The site maintainer should include them as site-specific files if their direct download URLs must remain available.

### Ignore by a narrow rule: generated graph variation

Edge identifiers, edge order, and the graph request's cache suffix can differ without changing graph relationships.
Compare full node objects and counted source/target pairs before ignoring these differences.
Stop applying that rule if edges gain other fields.
Graph positions and visible labels also change during the browser's force-layout calculation.
Ignore geometry only after checking the graph data, filters, and navigation.

## Fixes and remaining limits

The package fixes restore member-based publication and dataset selection, five named page URLs, external navigation, the Contact footer, and five authored section introductions.
The retained inputs now supply the missing portraits and record logos.
Those images match the native output paths and bytes, but their fresh acquisition and publication rights remain outside this check.

The earlier comparison found all 254 native routes in Lite, with two additional editor routes.
It found matching content for 228 generated record pages, 1,072 graph nodes, 2,288 relationships, and 253 search entries.
The fresh tool run and supplementary checks confirm the route and graph results.
Shared page text differs only on the home and Explore pages, apart from navigation, editing links, and footers.
The latest package checks pass 326 tests after reverting PID-derived filenames and protecting captures whose cache information is missing.
The earlier template candidate passed 22 source tests.

Fresh Playwright/Chromium checks rendered 18 pages: home, seven record classes, and Explore on both sites.
All expected images loaded, and no browser errors or external requests occurred.
Lite passed search, menus, appearance switching, graph filtering, and graph navigation.
The reviewer inspected the Explore screenshots to confirm the height difference.
These checks do not cover mobile layouts, every viewport, or other browsers.
Live-site differences, authenticated editing, upstream publication, and fresh media acquisition remain untested here.
Native regeneration still requires the documented maintainer procedure.
This PR provides tested generation fixes and a concrete comparison method, not an unattended end-to-end publication test.

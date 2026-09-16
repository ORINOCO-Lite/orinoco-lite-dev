# Psychoinformatics deployment comparison

## Result

Both generation processes use the same 5,030-record capture.
The comparison found matching record meaning, main page text, search entries, graph content, images, and downloads.
SiteDiff accounts for the known Lite adaptations.
It reports 253 matching pages and one source-formatting difference on Explore.
The Explore text and links match; no correction is needed.

| Check | Native ORINOCO | Orinoco Lite | Result |
| --- | ---: | ---: | --- |
| Shared HTML routes | 254 | 254 | All native routes retained |
| Additional HTML routes | 0 | 2 | Lite editor and sign-in callback |
| Page titles and main text | 254 pages | 254 pages | Match |
| HTML after known adaptations | 254 pages | 254 pages | 253 match; Explore differs only in paragraph line wrapping |
| Dataset structured metadata | 1 JSON-LD script | 1 JSON-LD script | Values match |
| Graph nodes / relationships | 1,072 / 2,288 | 1,072 / 2,288 | Full nodes and counted relationships match |
| Search entries | 253 | 253 | Match |
| Images / dataset downloads | 67 / 3 | 67 / 3 | Paths and bytes match |
| Captured records | 5,030 | 5,030 | Values match after equivalent annotation notation is resolved |

## Inputs and checks

Comparison date: 16 September 2026 UTC.
The original capture time is unknown.
The capture is retained in the site-specific repository so each software repin can reuse it.

- **Native:** the selected [`www-from-model` revision](https://github.com/ORINOCO-Lite/www-from-model/commit/a2e4534bc38a6dc0f30effed354773f1da984a18), regenerated through a temporary Pool, native queries, Jinja, and Hugo.
  Its generated record pages and graph were removed before generation.
- **Lite:** the [package candidate](https://github.com/ORINOCO-Lite/orinoco-lite-dev/commit/ae4601dbc519e89af98879366dfec67245a59bfd) applied to the [Psychoinformatics downstream candidate](https://github.com/ORINOCO-Lite/psychoinformatics-downstream/commit/7802e6c7b99eeb16ec34eafa402d964bd3844240).
  It uses the [restored site-specific inputs](https://github.com/ORINOCO-Lite/psychoinformatics-site-specific/commit/0fc05d2aba91924db2b9a029106d37bcdf4a8a0d).
  The downstream records the template, package lock, and input submodule.
- **Build:** `pixi run --locked orinoco-lite --root FRESH_CHECKOUT build --destination build/site --base-url /`.
  The disposable checkout has no prior generated output.
  Capture verification checks the joined YAML against the raw capture.
- **HTML:** SiteDiff with the [Unicode and doctype fix](https://github.com/evolvingweb/sitediff/pull/215) and `--cached=none`.
  The unfiltered pass covers all HTML paths from both directories.
  The default view applies the [narrow comparison rules](../../tools/site-diff/psychoinformatics.yaml) and lists the two verified editor additions separately.
  All 28 rule tests pass.
  Missing metadata, changed names, wrong editor inputs, and missing branding remain visible.
- **Data and files:** direct comparisons of graph objects, search entries, joined records, images, downloads, and script contents.
- **Browser:** 24 page/viewport samples and 14 interaction checks pass in Playwright/Chromium.
  They cover desktop and mobile pages, search, menus, appearance, graph filters, and graph navigation, with no browser errors or missing images.
  All 228 original Lite record-editor links target `/edit/`.

The [agent procedure](upstream-comparison.md) gives installation and repeat commands.
The [tool evaluation](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/154) explains the tool choice.
Upstream maps `main` to the draft deployment and `published` to production.
This comparison uses the selected revision and retained capture for both local builds.

### Read the tool output

The generated files are under `build/comparison-report/` in the comparison worktree:

- `reviewed/viewer/report/report.html`: default HTML report, with known changes listed once.
- `reviewed/report.json` and `reviewed/report.tgz`: per-page results and offline viewer archive.
- `current-raw/viewer/report/report.html`: full unfiltered report for the same builds, linked from the default view.
- Browser screenshots and data checks: alongside the HTML report.

The default view shows one changed page: Explore's paragraph line wrapping.
The unfiltered view shows changes on all 254 shared pages and two missing-native-file errors for the Lite editor additions.
Those raw counts include the repeated footer and menu changes, not 256 separate problems.
Both viewers' filters and navigation pass browser checks without network requests.
Profile-aware self-comparisons show no differences or errors: 254 native pages and 256 Lite pages.

## New differences

None requiring correction.
Explore's source newlines differ, but its paragraph text and links match after normal HTML whitespace handling.
Accept this as source formatting, not a deployment regression.

### Correction verified in this run

The focused comparison exposed missing Dataset JSON-LD on “Studyforrest: Phase 2 Data”.
Its retained `dataset.json` was in `static/`, where Hugo could publish it but could not read it as a page resource.
Moving the three original resource files into the site's `content/datasets/…/` bundle restores upstream's embedded metadata without changing their bytes or download URLs.
The package and template are unchanged.

## Accepted differences

The [standing decisions](upstream-accepted-differences.md) define the exact scope and review triggers.

| Difference | Current example | Action |
| --- | --- | --- |
| Static editing | Record pages use Lite's editor instead of the Pool editor. Two editor routes are added. | Keep as part of Lite |
| Build information | The footer adds package and source links. | Keep as part of Lite |
| Mobile navigation | The menu includes Collaboration hub. | Retain as presentation debt |
| Outputs tooltip | The desktop menu adds a tooltip that repeats its label. | Retain as presentation debt |
| Explore graph height | Lite uses 55vh with a 320px minimum instead of a full viewport. | Retain as presentation debt |
| HTML source formatting | Explore's ordinary paragraphs wrap at different source positions. Text and links match. | Ignore; no correction needed |
| Generated graph variation | Edge IDs, order, cache suffix, and force-layout positions differ while checked graph content matches. | Ignore within the documented rule |

The comparison reports differences between deployments.
Defects shared by both outputs belong to separate upstream quality work.

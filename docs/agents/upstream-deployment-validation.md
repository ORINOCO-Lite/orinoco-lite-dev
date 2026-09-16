# Psychoinformatics deployment comparison

## Result

Both generation processes use the same 5,030-record capture.
The comparison found no remaining differences in record meaning, page text, search entries, graph content, images, or downloads.
The remaining differences are the accepted Lite adaptations listed below.

| Check | Native ORINOCO | Orinoco Lite | Result |
| --- | ---: | ---: | --- |
| Shared HTML routes | 254 | 254 | All native routes retained |
| Additional HTML routes | 0 | 2 | Lite editor and sign-in callback |
| Page titles and main text | 254 pages | 254 pages | Match |
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
- **Lite:** the [package candidate](https://github.com/ORINOCO-Lite/orinoco-lite-dev/commit/ae4601dbc519e89af98879366dfec67245a59bfd) applied to the [Psychoinformatics downstream candidate](https://github.com/ORINOCO-Lite/psychoinformatics-downstream/commit/0e5e56a77a711f7bbaca7f2c7544ee6a287e67d3).
  It uses the [restored site-specific inputs](https://github.com/ORINOCO-Lite/psychoinformatics-site-specific/commit/857e9bbb378210a092e000add7cb5a093c8a29a3).
  The downstream records the template, package lock, and input submodule.
- **Build:** `pixi run --locked orinoco-lite build --no-cache --base-url /`.
  Capture verification checks the joined YAML against the raw capture.
- **HTML:** SiteDiff with the [Unicode and doctype fix](https://github.com/evolvingweb/sitediff/pull/215), `--cached=none`, no ignore rules, and all HTML paths from both directories.
- **Data and files:** direct comparisons of graph objects, search entries, joined records, images, downloads, and script contents.
- **Browser:** 24 page/viewport samples and 14 interaction checks pass in Playwright/Chromium.
  They cover desktop and mobile pages, search, menus, appearance, graph filters, and graph navigation, with no browser errors or missing images.

The [agent procedure](upstream-comparison.md) gives installation and repeat commands.
The [tool evaluation](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/154) explains the tool choice.
Upstream maps `main` to the draft deployment and `published` to production.
This comparison uses the selected revision and retained capture for both local builds.

### Read the tool output

The generated files are under `build/comparison-report/` in the comparison worktree:

- `html/report.tgz`: SiteDiff's offline HTML viewer.
- `html/report.json`: per-page results.
- `viewer/report/report.html`: extracted HTML viewer, ready to open locally.
- Browser screenshots and data checks: alongside the HTML report.

SiteDiff reports changes on all 254 shared pages because the Lite footer and navigation markup repeat across the site.
It reports the two Lite-only editor routes as missing-file errors on the native side.
These counts describe changed pages, not separate regressions.
The HTML viewer lets the reviewer inspect each change.
Its filters and navigation pass browser checks without network requests.
A native self-comparison reports 254 unchanged pages and no errors.

## New differences

None requiring a new decision in this run.

The input overlay supplies the upstream identity, authored text, and retained downloads.
It also removes the extra Lite home heading.
The converter preserves the captured `at_time: "-"` in records and RDF instead of dropping it.
Equivalent annotation names and separate YAML companions do not change record meaning.

## Accepted differences

The [standing decisions](upstream-accepted-differences.md) define the exact scope and review triggers.

| Difference | Current example | Action |
| --- | --- | --- |
| Static editing | Record pages use Lite's editor instead of the Pool editor. Two editor routes are added. | Keep as part of Lite |
| Build information | The footer adds package and source links. | Keep as part of Lite |
| Mobile navigation | The menu includes Collaboration hub. | Retain as presentation debt |
| Explore graph height | Lite uses 55vh with a 320px minimum instead of a full viewport. | Retain as presentation debt |
| Generated graph variation | Edge IDs, order, cache suffix, and force-layout positions differ while checked graph content matches. | Ignore within the documented rule |

The comparison reports differences between deployments.
Defects shared by both outputs belong to separate upstream quality work.

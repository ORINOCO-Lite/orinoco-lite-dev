# Site comparison tools for Psychoinformatics

This report helps maintainers choose tools for comparing native ORINOCO and Orinoco Lite websites.
It records an evaluation on 16 September 2026 UTC, not a new deployment contract.
Retain it while the tool choice remains under review.
After that decision, promote the short operating procedure and use Git for this evaluation's history.

## Recommendation

Use a small set of existing tools, each with a distinct job.
Do not expect one percentage or exit code to decide whether Lite follows upstream acceptably.

| Job | Recommended approach | Condition or limit |
| --- | --- | --- |
| Explain HTML changes across all pages | Evolving Web SiteDiff | Correct its demonstrated Unicode and lowercase-doctype defects before relying on its output |
| Review selected page states | BackstopJS | Stabilize graph randomness. Retain captures and interpret differences instead of requiring identical pictures |
| Check search, menus, graph actions, and errors | Existing Playwright checks | Can replace BackstopJS screenshots when one browser-test dependency is preferable |
| Find broken HTML targets | Lychee | Compare new failures separately from inherited failures. Check deployed routing separately |
| Cover assets, downloads, graph, and search data | Git directory diff plus small jq comparisons | Explain any normalization. Neither raw bytes nor sorted JSON alone establishes acceptable behavior |
| Explain repeated changes in plain English | Agent review of those reports | Cite tool findings and distinguish deliberate changes from unresolved decisions |

SiteDiff is the preferred HTML-reporting foundation, not an approved unmodified dependency.
Its defects have small demonstrated corrections, but those corrections still need upstream tests and review.
Until then, retain the unfiltered file comparison and treat SiteDiff's clean results as incomplete evidence.
Do not replace it with the summarized prototype solely because the prototype is easier to install.

BackstopJS gives the clearest ready-made visual catalogue of the tools tested.
Playwright is the lower-dependency alternative when the project keeps its existing interaction checks and accepts a test-oriented report.
Choose one as the routine visual reporter.
Running both permanently adds little value.
Keep comparison dependencies in the maintainer environment, managed through Pixi, not in released website builds.

This recommendation is based on observed coverage and report usefulness, not project age alone.
No candidate was rejected because of a failed installation.
The evaluation covers the relevant tool families and named alternatives below, not every website-testing product.

Read the [HTML trials](#html-and-content-comparison) and [visual trials](#browser-and-visual-comparison) for the main tool choice.
The [site-specific considerations](#what-makes-this-site-comparison-different) explain interpretation, and the [repeat instructions](#repeat-the-evaluation-without-adding-a-framework) include commands and the bug reproduction.

## Scope and evidence

The objective is to explain deployment differences, not to require identical files or screenshots.
A useful comparison finds missing information, broken behavior, and unintended presentation changes.
It also identifies deliberate adaptations and differences caused by the inputs or hosting.

This evaluation uses two retained outputs from the same-capture work in [PR #152](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/152).
It does not rebuild the sites, fetch the live Pool, or certify today's production deployment.
The evaluation branch starts from main after PR #153.
That branch choice does not change the older software selections in the retained outputs.

| Input | Selected source |
| --- | --- |
| Native generated site | [`www-from-model` at `a2e4534`](https://github.com/ORINOCO-Lite/www-from-model/commit/a2e4534bc38a6dc0f30effed354773f1da984a18), Hugo 0.154.5, and that revision's Congo dependency |
| Lite generated site | [Downstream at `d5b82c5`](https://github.com/ORINOCO-Lite/psychoinformatics-downstream/tree/d5b82c583c84db65688f467689f43b7d6ad998f7), package `836fed5`, template `3bfa867` |
| Retained site inputs | [Site-specific at `c15d99d`](https://github.com/ORINOCO-Lite/psychoinformatics-site-specific/tree/c15d99da3fb41f076ecd1d6738f19686a1c6240c), including the same 5,030-record capture |

The earlier native run loaded the capture into a temporary Pool and regenerated the record pages and graph.
It did not use the committed generated pages as its result.
The earlier Lite run used a fresh, frozen downstream installation and its recorded site-specific submodule.
The capture's original acquisition time and API origin remain unknown.
Neither fact can be inferred from a repository's creation date.

All new trials use the same immutable output directories.
The native site contains 254 HTML files.
Lite contains those routes plus two editor routes.
Known-change controls are small synthetic pages, each with one intentional change.
Self-comparison means comparing a site with itself to expose tool noise or configuration errors.

We distinguish three evidence levels:

- **Run:** The tool executed against these outputs or a named synthetic control.
- **Previously run:** The earlier comparison supplied the evidence.
  This evaluation did not repeat that operation.
- **Reviewed:** Official documentation or source code supplied the claim.
  No empirical result is implied.

No trial sent site content to a hosted comparison service or an external LLM.
Generated reports, screenshots, dependencies, and scratch scripts remain outside Git.
The PR contains the evaluation, not a new comparison framework or additional Pixi tasks.

## HTML and content comparison

### Evolving Web SiteDiff

The earlier decision to exclude this tool was premature.
Its original installation worked and generated reports.
The new full-site trial also succeeded.
Installation inconvenience is not a reason to reject it.

SiteDiff compares HTML and provides a report with page-level changes and colored markup differences.
Its configuration supports narrow removal or replacement rules.
An explicit path list avoids relying on a crawler to discover every page.
`--cached=none` requests fresh input rather than a retained page cache.
See the [official documentation](https://github.com/evolvingweb/sitediff#readme) and [installation instructions](https://github.com/evolvingweb/sitediff/blob/master/INSTALLATION.md).

**Run:** Ruby 3.3.6 and SiteDiff 1.2.11, with no broad ignore rules.
The local directory comparison covered the union of 256 HTML paths.
It reported 254 changed pages and two errors for the Lite-only pages absent from native output.
The native self-comparison reported 254 unchanged pages.
The full comparison took about 8.5 seconds on this machine, excluding installation and report review.
That timing is not a cross-tool benchmark.

The two errors require interpretation as additions, not automatic classification as broken pages.
A route list supplies that context.
Conversely, a fetch or parsing error must never count as an unchanged page.
The exported overview labels all 256 results as changed, including the two errors.
Read the detailed statuses rather than repeating that headline as a regression count.

SiteDiff detected all 15 intentional HTML changes in the shared synthetic control.
These included script and image URLs, alternative image text, identifiers, fragments, and an inline height change.
It compares HTML attributes that the summarized prototype does not retain.

Three real limitations need explicit handling:

- The 1.2.11 HTML parser checks for uppercase `<!DOCTYPE`.
  With lowercase `<!doctype>`, it can lose attributes on the outer `html` and `body` elements.
  A language or body-class change can therefore escape detection.
- The HTTP reader treats responses without a charset as binary.
  It still detected changes, but the report showed only MD5 values instead of readable HTML differences.
  Directory comparison avoids that HTTP-specific condition.
- The sanitizer incorrectly re-encodes UTF-8 text as binary.
  Both `Röder` and `Räder` become `Rder`, so the tool reports that changed name as unchanged.
  This affects the site's names and German text directly.

The encoding defect prevents recommending the unmodified release as the sole HTML comparator.
An isolated experimental correction made doctype matching case-insensitive and removed two incorrect binary-source encoding arguments.
The corrected copy detected the accented-name and outer-element attribute changes.
No supported sanitization configuration repairs information already lost by those earlier processing steps.
The correction belongs upstream, with regression tests, before ordinary adoption.
This PR does not install a patched tool or create a maintained fork.
Do not silently rewrite website output and call the comparison unmodified.
The [sanitizer](https://github.com/evolvingweb/sitediff/blob/b32b7926841d6b21697afd6a0b813c4b3a4fbee3/lib/sitediff/sanitize.rb) and [HTTP reader](https://github.com/evolvingweb/sitediff/blob/b32b7926841d6b21697afd6a0b813c4b3a4fbee3/lib/sitediff/uriwrapper.rb) establish the processing order.
The inspected development source labels itself 1.2.12 but contains the same sanitizer defects as the published 1.2.11 gem.

The exported report preserves markup differences.
It is not an archived visual browser comparison with all page assets captured.
SiteDiff does not execute application JavaScript or automatically compare the contents of referenced media and graph files.
Explicit non-HTML inputs sometimes produce differences, but its HTML processing is not a reliable general data comparator.

### Yarikoptic summarized-sitediff

**Run:** Unmodified [`sitediff (3).py` at `487f39b`](https://github.com/yarikoptic/summarized-sitediff/tree/487f39bf6dd6e8b2810a23385b51ea8baa6048bf).
The run used Python 3.12.13, requests 2.34.2, Beautiful Soup 4.15.0, and lxml 6.1.3.
It used `--no-cache --strict-unicode --max-hunk-lines 10000` and no LLM, exclusions, or ignore rules.

The tool reads both directory trees and includes HTML pages without incoming links.
It produced JSON and Markdown reports: 254 changed shared pages, two added pages, and 471 change groups.
Of those groups, 459 describe added or removed links.
The self-comparison reported 254 unchanged pages.

Its main advantage is grouping repeated changes across pages.
That can explain a repeated footer change once instead of presenting hundreds of unrelated page failures.
However, unique editing URLs still produce many separate link groups.
The 471 groups are neither 471 independent causes nor 471 regressions.
The compact report omits detail, so reviewers must retain the complete JSON report.

The controlled trial detected seven of 15 intentional HTML changes.
It reported the other eight changed pages as unchanged.

| Intentional change | SiteDiff 1.2.11 | summarized-sitediff |
| --- | --- | --- |
| Text, title, or description metadata | Detected | Detected |
| Stylesheet URL, ordinary link, list order, or hyphenated UUID text | Detected | Detected |
| Canonical link, script URL, or image URL | Detected | Missed |
| Image alternative text, link fragment, or element ID | Detected | Missed |
| Long lowercase hexadecimal identifier or inline layout style | Detected | Missed |
| Added or removed unlinked HTML page | Reported as a one-sided error | Reported as added or removed |

These controls used lowercase doctypes.
Separate SiteDiff controls exposed its outer-element attribute defect described above.
In a separate accented-name control, the summarized prototype detected the change that unmodified SiteDiff missed.
Neither tool automatically checked changed same-path graph, CSS, or JavaScript files through their HTML references.

The prototype replaces every lowercase hexadecimal run of at least 16 characters, even with `--strict-unicode`.
That can hide real identities, not just generated asset names.
Hyphenated UUID changes were detected in this trial, so the limitation must not be described as hiding every PID.
The source also removes scripts before collecting their URLs.
No CLI option disables the hexadecimal replacement.

The repository contains four script variants and no packaged release or license file at the examined revision.
All four variants contain the broad hexadecimal replacement.
Only `sitediff (3).py` received the full empirical trial here.
Clarify redistribution rights before vendoring code.

**Assessment:** Useful supplementary summaries, but not a sufficient primary record of differences in its current form.
Its blind spots matter directly to this site's identifiers, graph layout, and assets.
A corrected upstream version could be reconsidered using the same controls.
Avoid making two overlapping HTML engines or a locally maintained reporting application permanent requirements without a demonstrated benefit.

## Browser and visual comparison

### BackstopJS

**Run:** BackstopJS 6.3.25 with Playwright 1.62.1 and Chromium 151.0.7922.34.
Its isolated installation succeeded without changing project dependencies.
The trial covered home, Michael Hanke's page, the dataset listing, and Explore.
Each page used desktop and mobile viewports in light and dark appearance: 16 states per comparison.
The viewport sizes were 1280×800 and 390×844.
These are Chromium viewport checks, not proof of real-device or cross-browser compatibility.

BackstopJS takes reference and candidate screenshots and produces an HTML catalogue with before, after, and highlighted differences.
The report is easy to scan by page and viewport.
It shows removed branding, shifted content, and graph-size differences more directly than an HTML source report.
See the [official documentation](https://github.com/garris/BackstopJS).

The first self-comparison reported differences in 12 of 16 unchanged states.
The cause was the graph's random starting positions, not website changes.
Changing only the browser test's random-number sequence made all 16 self-comparisons report zero changed pixels.
No screenshot region was hidden.
The controlled native-versus-Lite comparison then reported differences in all 16 states.
Those are expected review items, not 16 independent regressions.
On mobile Explore, the native graph measured 342×844 pixels and Lite measured 342×464.19 pixels.
In the controlled sample, Lite's graph and filter labels overlapped substantially, while the native sample avoided that overlap.
Investigate readability before accepting the shorter graph.
Other random layouts may also overlap upstream, and this trial did not establish broken filtering controls.

Strengths:

- Ready-made visual report, viewport configuration, and separate reference/candidate URLs.
- Runs locally, without uploading the site to a service.
- Browser hooks can wait for fonts, images, and graph controls before capture.
- Reveals layout changes caused by CSS or JavaScript that static HTML comparison cannot explain.

Limits:

- No automatic complete route discovery or metadata/data comparison.
- Requires Node, a browser installation, configuration, and a small readiness hook for this site.
- Pixel differences do not identify their cause or severity.
- Tall-page offsets make large areas differ after one inserted heading.
- A blind reference update would accept both deliberate changes and regressions.
- The upstream README requests a new maintainer or owner.
  That is a stewardship risk to monitor, not a failed trial.

BackstopJS uses the MIT license.
Treat its generated report as evidence for human review, not a mandatory zero-difference gate for this deliberately different deployment.

### Playwright screenshot assertions and interaction tests

**Run:** Playwright 1.62.1 used the same 16 states and controlled random sequence.
Native compared with itself passed all 16 screenshot checks.
The native-versus-Lite run produced 16 expected screenshot failures and a usable HTML report with visual differences and traces.
The test also recorded graph bounds, viewport, appearance state, image loading, and horizontal overflow.

[Screenshot assertions](https://playwright.dev/docs/test-snapshots) fit an existing browser-test workflow.
They can share page setup with search, menu, graph-filter, and navigation tests.
[Trace Viewer](https://playwright.dev/docs/trace-viewer) helps investigate the actions and page state behind a failure.
The report starts with failed tests, so it is less immediately readable as a site-wide visual catalogue than BackstopJS.
It requires a short test file and explicit reference management rather than only a URL-pair configuration.

Playwright supports more browser engines, but only Chromium ran here.
Neither screenshot assertions nor successful navigation prove that every interactive operation works.
The project must assert those operations explicitly.
Playwright uses the Apache-2.0 license and avoids adding a second visual runner if the existing browser checks become maintained tests.
Both visual trials used the same browser engine, so their agreement is not independent cross-browser evidence.

A small [ARIA snapshot](https://playwright.dev/docs/aria-snapshots) control demonstrated complementary coverage.
A changed link destination left screenshot bytes unchanged but changed the accessibility-tree snapshot.
A panel-height change altered the screenshot but left that snapshot unchanged.
Accessible roles and names can supplement browser assertions, but they cannot represent graph data or all visual changes.

### alfredwesterveld/sidediff

**Run:** [`alfredwesterveld/sidediff` at `75e6e38`](https://github.com/alfredwesterveld/sidediff/tree/75e6e38257e9ebce40ce48b3de0638641f481150), version 0.1.0.
The upstream lock selected Playwright 1.62.1 and odiff 4.5.0 under Bun 1.4.2.
The MIT-licensed repository had four commits at inspection.
Installation succeeded on Apple Silicon.

This candidate is unusually close to the requested operation: compare two served websites and combine pixels, rendered text, and selected metadata.
Its local report offers a slider, side-by-side images, and text differences.
The three tested routes were home, Explore, and Michael Hanke's page.
All three produced readable layout/text reports, and their native self-comparison reported matches.

Important limits appeared in source inspection and controls:

- Default discovery starts from site A, samples three paths per URL shape, and caps the selection at 200 paths.
  An explicit union of routes is necessary for this site's additions and unlinked pages.
- The CLI discards input URL prefixes and uses the same path on both origins.
  It cannot directly map native `/` to Lite `/repo/`.
  Serve both builds at matching roots or change the tool.
- Capture freezes time and randomness, changes sticky positioning, and can hide banners or block hosts.
  Those are changes to the test environment, not neutral observations of every deployed behavior.
- Canonical and PID-link changes appeared in the report, but the CLI said `0 changed` and exited successfully.
  Its exit status did not include these nonvisual differences.
- Same-appearance image/script URL changes, an invisible JavaScript error, and unused changed graph data produced matches.
- Text extraction and report detail have limits, and there is no complete JSON report export.

**Assessment:** A promising combined report, but less mature and less reliable as a primary workflow today.
The observed exit-status inconsistency is a defect.
Not comparing undisplayed graph data is a scope limit.
Keep those two kinds of limitation distinct.

### Hosted visual services

**Reviewed, not run:** [Percy](https://www.browserstack.com/docs/percy/overview) and [Applitools Eyes](https://applitools.com/docs/).
They offer hosted visual review, baseline management, and browser coverage that reduce local infrastructure work.
They add an account, service dependency, commercial terms, and transfer of site content or screenshots.
Their comparison rules and rendering behavior also need the same known-change controls.

No subscription was purchased and no site content was uploaded.
For this small static site, the local tools already demonstrate useful reports.
Reconsider hosted services if shared approval workflows or broader browser coverage become a concrete requirement.
They do not remove the need to compare records, links, assets, or graph data.

## File and structured-data comparison

### Git directory diff and jq

**Run:** `git diff --no-index --no-ext-diff --no-textconv` compared both output directories.
Git 2.55.0 reported 782 changed files, 117,162 inserted lines, and 2,606 deleted lines.
The earlier complete diff was about 64 MB.
Minified HTML and generated files make that output unsuitable as the main human report.
Git marks binary files as different without explaining their visual meaning.

This is still a useful backstop.
It includes downloads, JSON, images, and same-path CSS or JavaScript that an HTML-only comparison misses.
Use a name/status summary first, then inspect the relevant files. Exit status 1 means differences, not a failed invocation. See [Git's `--no-index` documentation](https://git-scm.com/docs/git-diff).

**Run:** Small `jq` comparisons checked the graph and search data.
All 1,072 complete graph node objects matched after sorting by ID.
All 2,288 directed relationships matched after sorting their source and target pairs.
The comparison retained duplicate relationships.
Before removing edge IDs, it checked that edges contained only `id`, `source`, and `target`.
This is a narrow rule for the current graph format, not permission to discard future edge properties.

Both search indexes contain 253 entries.
After sorting by permalink, one entry differs: Explore's retained-capture notice replaces the native live-site description.
All other compared fields and entries match.
This corrects any reading of the earlier report as claiming complete equality of the fresh search indexes.

Sorting does not establish semantic equivalence on its own.
Do not sort away meaningful display order, collapse duplicate edges, remove identifiers, or normalize arbitrary metadata values.
Use [jq](https://jqlang.org/manual/) for small, explained comparisons instead of a new validation framework.

### diffoscope

**Run:** [diffoscope](https://diffoscope.org/) 329 compared the real home-page files in an isolated Python 3.9.18 environment.
Adding `defusedxml` 0.7.1 and `html2text` 2025.4.15 resolved the initial parser/helper warnings.
Installation was not a blocker.
The HTML report included source differences and a more readable text comparison.
That text also included hidden theme content, so it was not a browser-visible-text comparison.

diffoscope is useful for detailed investigation of changed archives, images, compressed downloads, JSON, and other formats.
It can explain file changes that Git merely marks as binary differences.
Many formats need additional external tools, and reports can become large.
It does not decide whether a deployment difference matters.
The trial did not run a full-directory or dataset-archive comparison.

**Assessment:** Keep as an on-demand diagnostic tool, not the routine site report.
Its broad format support is valuable when a particular download or image needs explanation.
The project uses GPL-3.0-or-later licensing.

## Link checks and other alternatives

### Lychee

**Run:** [Lychee 0.24.2](https://github.com/lycheeverse/lychee/releases/tag/lychee-v0.24.2), using the official Apple Silicon binary with its published checksum checked.
The offline run covered every HTML file, disabled the cache, and resolved root-relative links against each output directory.
It required `index.html` for directory targets.
That last setting matters: a directory existing without a served page is not a valid website destination.

Both sites had the same nine failing source/target pairs and no new failures in Lite.
The native run examined 12,610 link occurrences, and Lite examined 12,105.
Each completed in under one second on this machine.
Repeating with fragment checks found no additional failures.
Exit status 2 indicated broken links, not an installation or execution failure.

Lychee provides structured reports and can replace the earlier bespoke HTML link check.
It uses MIT or Apache-2.0 licensing and does not require a browser.
Its [documentation](https://github.com/lycheeverse/lychee) covers local and remote checks.
The offline trial did not test external availability, deployed redirects, or JavaScript-generated graph links.
External failures need separate interpretation because rate limits, authentication, or temporary outages can affect them.

### Screaming Frog SEO Spider

**Reviewed, not run:** The [crawl comparison workflow](https://www.screamingfrog.co.uk/seo-spider/tutorials/how-to-compare-crawls/) covers changed URLs, content, titles, metadata, links, and redirects.
It supports hostname/path mapping, explicit URL lists, and JavaScript rendering.
It is a credible established option for comparing hosted deployments and migration behavior.

The required comparison workflow needs a commercial license.
The [free edition's 500-URL allowance](https://www.screamingfrog.co.uk/seo-spider/pricing/) does not make this comparison feature free.
It also adds a desktop application and crawl configuration.
It does not provide graph meaning, complete asset equivalence, or authenticated curation validation.

**Assessment:** Reconsider for substantial live-site migration review.
For the current local same-capture task, the open-source tools avoid a purchase and already expose the relevant differences.
This is not a claim that the commercial tool failed a trial.

### HTML/DOM comparator libraries

**Run:** [`bem/html-differ`](https://github.com/bem/html-differ) 1.4.0 under Node 24.10.0.
It detected accented text and attribute changes, PID links, language, body classes, script source/body, image source, and canonical links.
It correctly treated doctype capitalization as equivalent.
The real home-page comparison reported 32 changed chunks, and its self-comparison was equal.

Its default whitespace normalization missed a spacing change inside `pre`.
Setting `ignoreWhitespaces: false` detected that change.
Its two-file CLI printed differences but returned status 0.
Use its comparison API rather than interpreting that CLI status as equality.
The latest published version dates to 2019, and its old dependency versions produced deprecation warnings.
It supplies a library and a two-file CLI, not route traversal and a complete site report.
It is a useful diagnostic fallback for specific HTML, but adopting it as the main tool would require maintained reporting code.

**Reviewed only:** [`dom-compare`](https://github.com/Olegas/dom-compare) compares parsed document trees and attributes.
[`htmldiff-js`](https://github.com/dfoverdx/htmldiff-js) marks insertions and deletions in HTML blocks.
Both require surrounding code for route selection, resources, and site reports.
The [W3C HTML Diff service](https://www.w3.org/2007/10/htmldiff) compares two documents rather than whole deployments and cannot reach private loopback builds.
These approaches offer little advantage over a repaired SiteDiff for this project's minimum-machinery requirement.

### Accessibility and performance audits

**Reviewed, not run:** [Lighthouse](https://github.com/GoogleChrome/lighthouse) and [axe-core](https://github.com/dequelabs/axe-core).
They answer whether a page meets particular quality checks, not whether two deployments contain equivalent content or appearance.
They can identify accessibility regressions in deliberately changed navigation that screenshots alone cannot establish.
Automated accessibility checks still need human review.
Performance comparisons require matched conditions and repeated samples, not a local-versus-production score comparison.

**Assessment:** Use them when a specific change raises a quality question.
Do not turn this site-diff task into a general audit framework or include inherited upstream defects in the Lite deviation list.
Track shared defects separately when useful.

## What makes this site comparison different

### Generation and deployment are separate comparisons

The same-capture comparison tests two generation processes.
Both must receive one retained Pool capture, compatible schema inputs, authored pages, media, and explicit software selections.
Native generation requires a temporary Pool for the selected upstream query process.
Serving or comparing its finished static output does not require a running Pool.
Authenticated editing is a different operation and remains outside this test.

The native reference here uses an Orinoco Lite mirror commit with retained patches.
When both paths share that source, agreement cannot validate those shared patches against pristine upstream.
For an upstream repin, also review the retained mirror differences.
Do not infer upstream equivalence from shared implementation alone.

The [upstream deployment workflow](https://hub.psychoinformatics.de/www/www-from-model/src/commit/dc2a3f2d4734cdd16b33bbcdd654687f809ef29a/.forgejo/workflows/deploy.yml#L45-L51) distinguishes these sites:

| Branch | Destination | Interpretation |
| --- | --- | --- |
| `main` | `www-draft.psychoinformatics.de` | Draft website |
| `published` | `www.psychoinformatics.de` | Production website |

The recorded workflow deploys built files separately from the workflow that regenerates Hugo inputs from the Pool.
A branch head, a generated-source commit, and the last successful deployment need not describe the same state.
The older `published` generation process also differs from the selected `main` process.
Do not substitute one as the reference without stating that choice.
This evaluation verified the recorded workflow in local Git, not either live deployment's current commit.

### Keep data changes separate from software changes

The downstream repository records the package, template, and site-specific submodule selections.
The site-specific repository retains the Pool capture, YAML records, annotation companions, authored pages, and media.
Use the downstream's recorded submodule commit, not the input repository's moving branch head.
These repositories already provide the necessary history.
A second pin ledger is unnecessary.

For a software comparison, keep site inputs fixed.
For a data refresh, capture once and feed both generators that capture.
Fetching the live API twice can create differences unrelated to either implementation.
Rebuilding retained YAML does not test conversion from a newly captured Pool.
When conversion changes, test that step explicitly before comparing websites.

The capture does not include image bytes, all authored pages, or hosting settings.
Missing logos, portraits, and direct downloads may therefore be input differences rather than rendering defects.
Do not infer permission to republish upstream media from its public availability.
Keep unreviewed screenshot and report uploads local until publication rights are clear.

For a later software repin, answer three questions separately:

1. What changed between the old and new native outputs with fixed inputs?
2. What changed between the old and new Lite outputs with those inputs?
3. What differences remain between the new native and new Lite outputs?

The first comparison explains upstream changes.
The second explains the downstream impact.
The third checks the thin deployment layer after the update.
A change common to both sites may be expected, while a new difference between them needs investigation.
Use existing commits and review artifacts to identify the four builds, not a second tracking system.

### A matching appearance is not sufficient

An incorrect link, changed PID, canonical URL, missing download, or omitted metadata can leave the screenshot unchanged.
An unchanged graph picture does not prove that all node labels, URLs, or relationships match.
Search is generated data plus browser behavior, not just a search-box screenshot.
Check graph data, search data, local targets, and representative interactions separately.

Earlier browser checks exercised search, menus, appearance switching, graph filtering, and graph navigation.
They did not establish successful authenticated editing, every page state, or every browser.
This evaluation does not replace the separate curation tests.

### Hosting can change a correct local build

A local root-path build does not test deployment beneath a GitHub Pages path prefix.
Check the configured publication base URL, canonical URLs, redirects, trailing slashes, case-sensitive paths, and the deployed 404 response.
Also check content types, CSP/CORS headers, compression, and cache behavior when moving hosts.
Comparing directories cannot observe those properties.
A crawler that sees a soft 404 with status 200 can mistake a missing page for a successful response.

Keep Pool/query caches, projection/build caches, comparison caches, and browser/CDN caches distinct.
Refreshing one does not refresh the others.
Use the relevant tool's explicit refresh option and record the state used.
Do not infer freshness from a successful cached build or matching screenshot.

### Normalization needs a reason

A normalization rule ignores a specified difference before comparison.
First retain an unfiltered result, then use only rules whose consequences are understood.
Avoid whole-footer, whole-navigation, all-query-string, all-hexadecimal, or whole-graph exclusions.
Those areas contain both expected changes and possible regressions.

Candidate narrow rules include graph edge ordering after a complete data check, or a known graph-request cache suffix.
An asset hash may be ignored only after checking that the associated content is equivalent.
Different host origins may be mapped for internal link comparison, while canonical and external origins remain independently checked.
Do not normalize changes to record identities, dates, meaningful query parameters, or search ordering by default.

For screenshots, match browser version, fonts, viewport, pixel ratio, locale, appearance, storage, and motion settings.
Wait for the relevant content, not just network silence.
Run a self-comparison before interpreting a new batch.
The trial's fixed random sequence affected every `Math.random()` call in the page, not only the graph.
Disclose that override and retain an ordinary browser interaction check without it.
A stable self-comparison on one machine does not guarantee stable rendering after a browser or graph-library update.
Do not increase a whole-page threshold until all deliberate changes happen to pass.
A small missing button can matter more than thousands of harmless shifted pixels.

## How the final comparison should explain differences

Each finding should identify an example page, actual change, source, owner, and proposed action.
An agent can group repeated findings, but the report must link them to tool evidence.
Do not count every affected page as an independent defect.
The following historical examples illustrate classification, not a second current deviation register.
The ongoing deployment review owns current decisions and any later fixes to these inputs.

| Finding in the retained pair | Source or uncertainty | Proposed action |
| --- | --- | --- |
| Pool editing links become Lite editing links | Deliberate package adaptation | Retain, with separate authenticated editing tests |
| Footer shows package/build information | Deliberate package adaptation | Retain, then narrowly account for changing build coordinates |
| Explore states that the site uses a retained capture | Site-specific authored content | Retain while the statement remains true. Expect the search entry to change too |
| Institutional logos and copyright differ | Site identity and media rights | Maintainer decision. Do not silently add branding to the generic template |
| Extra homepage heading or mobile menu item | Presentation adaptation, not inherently required | Fix soon or explicitly accept with a reason |
| Explore's graph height changes | Template shortcode versus native layout | Maintainer decision. Do not label it random graph noise |
| Three direct dataset downloads disappear | Retained upstream files, not regenerated records | Decide whether their direct URLs must remain available |
| One invalid date value is omitted during conversion | Existing converter behavior | Resolve soon as a data/conversion decision, not a display normalization |
| Graph edge IDs/order differ, but checked graph content matches | Generated representation | Ignore by the narrow checked rule above |

Use **Deliberate**, **Ignore by rule**, **Fix soon**, **Later**, and **Decision needed** consistently.
“Decision needed” does not mean approved.
An inherited defect can require urgent attention even when Lite introduces no new regression.
Keep inherited defects outside the Lite-specific deviation list.
For example, the earlier graph check found 790 paths without generated pages on both sides.
That needs a separate page-selection or graph-navigation decision, not 790 claimed Lite regressions.

## Repeat the evaluation without adding a framework

Use the same two output directories for each tool.
Run one unchanged control and a small set of known changes before interpreting a zero-difference result.
Include Unicode names, identifiers, HTML attributes, added routes, changed asset references, and changed asset contents in those controls.
Do not interpret the control counts as a general accuracy percentage.

The commands below assume the named versions are installed in an isolated maintainer environment.
Use Pixi for that environment in the project workflow.
The trials reused an isolated Pixi Ruby runtime, cached Python dependencies, and isolated npm/Bun installations.
Some exploratory Python helper runs used a temporary uv cache.
This report does not propose another package-management workflow or change a downstream's dependencies.

### SiteDiff report

Create `report/sitediff.yaml` with no suppression rules:

```yaml
before:
  url: /absolute/path/to/native
after:
  url: /absolute/path/to/lite
settings: {}
```

Generate the HTML file-path union for directory comparison:

```sh
{
  (cd "$NATIVE_SITE" && rg --files --hidden --no-ignore -g '*.html')
  (cd "$LITE_SITE" && rg --files --hidden --no-ignore -g '*.html')
} | sort -u | sed 's|^|/|' > report/paths.txt
sitediff diff -C report --paths-file report/paths.txt \
  --cached=none --no-verbose --report-format=json
sitediff diff -C report --paths-file report/paths.txt \
  --cached=none --no-verbose --export
```

Directory paths include `/index.html`.
HTTP paths normally use `/` and directory-style page URLs instead.
Expected differences return status 2, so do not stop other independent comparisons merely because this command returns nonzero.
`--cached=none` disables cache reads but still writes snapshots into the report directory.
Do not commit those snapshots.

The trial opened the exported report offline in Chromium with no external requests or browser errors.
Its 11 MiB archive contained the overview and 254 markup-difference pages.
The existing UI is sufficient for a lightweight HTML display.
Do not build a custom viewer.
Use separately served native and Lite sites for visual evidence, not SiteDiff's embedded side-by-side view as a screenshot baseline.
Its cached-view server can resolve assets through the after site, based on source inspection, so those views can mix versions.

### Link and file checks

Run this command once for each site, with the corresponding `SITE` and `REPORT` values:

```sh
lychee --offline --cache=false --no-progress --no-ignore \
  --index-files index.html --include-fragments --root-dir "$SITE" \
  --format json --output "$REPORT" "$SITE/**/*.html"
```

Keep all failures in the tool output, but list only newly introduced failures in the Lite deviation report.
For non-HTML coverage, first inspect filenames:

```sh
git diff --no-index --no-ext-diff --no-textconv --name-status \
  -- "$NATIVE_SITE" "$LITE_SITE"
```

Inspect graph, search, and relevant resource differences separately.
For this graph format only, the trial checked edge fields before comparing sorted nodes and counted relationships:

```sh
jq -e 'all(.edges[]; keys == ["id","source","target"])' graph.json
jq -S '{nodes:(.nodes|sort_by(.id)),
  edges:(.edges|map({source,target})|sort_by(.source,.target))}' graph.json
```

Apply the same operation to both files and compare its outputs.
Abort that normalization if the field check fails.

### Visual report settings

For BackstopJS, supply native as `referenceUrl` and Lite as `url` for each selected route.
The trial used full-document captures, `misMatchThreshold: 0`, and `requireSameDimensions: true`.
For Playwright, use `toHaveScreenshot` with `fullPage: true`, `maxDiffPixels: 0`, and `threshold: 0`.
These explicit trial settings differ from the tools' default tolerance settings.

Generate the reference from this comparison's native build, not an unexplained old golden screenshot.
Wait for fonts, image decoding, and graph readiness before capture.
Record any random-sequence override and run the self-comparison first.
Retain screenshots and reports as review output.
Do not approve Lite screenshots as the new upstream reference.
Future routine checks need only one small configuration or existing test file, not both trial runners.

### SiteDiff bug reproduction and correction

Prerequisites: Ruby 3.3.6 and SiteDiff 1.2.11, as used in the trial.
This minimal example does not need either website, a Pool service, or network access:

```ruby
require 'sitediff'

def normalized(html)
  SiteDiff::Sanitizer.prettify(SiteDiff::Sanitizer.domify(html))
end

before = '<!doctype html><html lang="en"><body><p>Röder</p></body></html>'
changes = [before.sub('Röder', 'Räder'),
           before.sub('lang="en"', 'lang="de"'),
           before.sub('<body>', '<body class="changed">')]
results = changes.map { |after| normalized(before) == normalized(after) }
abort "Defect not reproduced: #{results}" unless results == [true, true, true]
puts 'Reproduced three missed changes.'
```

Expected correct behavior: all three comparisons return `false` because each input changed.
Observed unmodified behavior: all return `true`.
The separately executed fixture also included an explicit UTF-8 charset declaration.
It produced the same result.

The experimental correction changed three lines in `lib/sitediff/sanitize.rb`:

- Match `<!DOCTYPE` case-insensitively with `/<!DOCTYPE/i`.
- Remove the explicit `'binary'` source-encoding argument from both UTF-8 conversion calls.

The corrected fixture returned `false` for all three comparisons.
The full-site comparison and unchanged controls also ran successfully with that correction.
Add upstream regression tests and review invalid/non-UTF-8 input handling before selecting a corrected commit for routine use.
An upstream report or a narrowly maintained fork is justified here.
It does not require abandoning SiteDiff.

## Evidence locations and remaining limits

The local evaluation worktree is `orinoco-lite-dev-site-diff`.
Its ignored `build/` directory contains these artifacts:

| Directory | Evidence |
| --- | --- |
| `prototype-trial/` | Full JSON/Markdown, self-check, per-change fixtures, Unicode control, graph/search comparisons |
| `sitediff-trial/` | Commands and logs, unmodified/corrected controls, full-site reports, minimal bug reproducer, exported report and UI captures |
| `visual-trial/` | Backstop/Playwright reports, screenshots, traces, page-state measurements, self-controls, configurations and hooks |
| `alternatives/` | Sidediff reports and controls, Lychee JSON, diffoscope output, html-differ controls, research notes |

Those local artifacts are not portable links in GitHub and are not release inputs.
The report records the measurements needed to review the tool choice without committing captured website content.
All temporary trial servers stopped after the checks.

This evaluation did not test current live deployments, fresh capture/media acquisition, authenticated curation, all browser engines, or every visual state. It did not adopt tools into Pixi, modify package/template code, publish captured media, or merge another repository.
The next implementation step is a corrected SiteDiff selection and a small repeatable comparison procedure in the ongoing deployment PR.
Keep tool repairs and their tests upstream where possible.

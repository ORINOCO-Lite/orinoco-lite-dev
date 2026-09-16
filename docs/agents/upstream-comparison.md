# Compare native ORINOCO with Orinoco Lite

This agent procedure supports the [deployment-layer objective](../project-design.md#validate-the-deployment-layer).
Generate two sites from one capture, then explain the differences.
Use the [current report](upstream-deployment-validation.md) for results and the [accepted differences](upstream-accepted-differences.md) for standing decisions.

## Inputs

Use the [Psychoinformatics downstream](https://github.com/ORINOCO-Lite/psychoinformatics-downstream) and its recorded [site-specific submodule](https://github.com/ORINOCO-Lite/psychoinformatics-site-specific).
Git and the dependency files identify the selected software and inputs.
The capture is `site-specific/sources/pool/public-thing.jsonl`.
Authored pages, images, identity settings, and downloads are also inputs.
A Pool capture does not contain them.
Use the same upstream content for both builds.
Keep institutional branding and downloads in this site's inputs, not the reusable template.

For a software repin, retain the capture and change the software selections.
For a data update, use one new capture for both builds.
Do not modify another developer's checkout.

Upstream's [deployment workflow](https://hub.psychoinformatics.de/www/www-from-model/src/commit/dc2a3f2d4734cdd16b33bbcdd654687f809ef29a/.forgejo/workflows/deploy.yml#L45-L51) maps `main` to [draft](https://www-draft.psychoinformatics.de/) and `published` to [production](https://www.psychoinformatics.de/).
Select the upstream revision before building.
Check this mapping when repinning.
The same-capture comparison uses local rebuilds, not the live sites.

## Capture and rebuild

To fetch Pool records, run the package command from the engineering checkout:

```console
pixi run --locked orinoco-lite dev capture build/pool/public-thing.jsonl --api https://pool.psychoinformatics.de/api
```

Add `--refresh` to fetch again.
Without it, the command checks the existing capture's origin, count, and digest before reuse.
It saves the capture time when fetching.
It does not infer a time for an old capture.
Retain the selected capture in the site-specific repository.

Use a disposable clone of the downstream commit under review:

```console
git clone --recurse-submodules https://github.com/ORINOCO-Lite/psychoinformatics-downstream.git build/psychoinformatics-check
cd build/psychoinformatics-check
git checkout --detach "$DOWNSTREAM_COMMIT"
git submodule update --init --recursive
pixi run --locked python -m orinoco_lite.upstream_orinoco_records verify \
  site-specific/sources/pool/public-thing.jsonl site-specific
pixi run --locked orinoco-lite build --no-cache --base-url /
```

`--locked` permits installation but rejects a manifest/lock mismatch.
Apply it to each Pixi invocation.
An earlier `pixi install --frozen` does not control later commands.
`--frozen` uses the existing lock without checking that it matches the manifest.
The build's `--no-cache` regenerates metadata output.
It does not fetch source data.

Test converter changes by converting the capture again in a disposable directory:

```console
pixi run --locked python -m orinoco_lite.upstream_orinoco_records project CAPTURE CONVERTED_INPUTS
```

Compare the converted records and joined annotation companions with the capture.
Use those converted inputs for the Lite build, together with the site's authored content and media.
Use the normal `dev setup` and editable-package commands for candidate development.
Check `build-pages` separately when testing a publication path prefix.

## Regenerate the native site

Use the selected `www-from-model` revision and its declared dependencies.
Follow its [Pool update workflow](../../submodules/www-from-model/.forgejo/workflows/update-from-pool.yaml), including its page-selection queries.
Do not use the committed generated pages as the reference.

1. Prepare the selected service, client, schema, query tools, website, and required media in a disposable environment.
2. Create a fresh local Pool with the selected schema and a `public` collection.
   Use the native `sqlite+stl` backend.
   Allow anonymous `READ_CURATED` and create a temporary local curator token.
3. Start the service on an unused loopback port.
   Seed only this disposable store:

   ```console
   jq -c '.record' "$CAPTURE" | DTC_TOKEN="$LOCAL_CURATOR_TOKEN" dtc post-records --curated "$LOCAL_API" public '*'
   ```

4. Read the records back.
   Check that every captured PID and value survived.
5. Copy the selected website into a scratch directory.
   Remove generated record Markdown and `static/graph.json`.
   Generated Markdown has `params.graphRootNodePID` or `params.generated` in its front matter.
   Retain authored pages, section introductions, and media.
6. Set `DUMPTHINGS_APIURL` to the local API and `QRI_RECORD_CACHE` to a new cache path.
   Run the workflow's graph, member-selection, record-page, and frontpage commands with Bash `pipefail`.
7. Build with the selected Hugo, `--minify --baseURL /`, and a fresh output directory.
8. Stop the temporary Pool.

Checkout and dependency installation are prerequisites, not generation steps to omit.
Perform them locally for the selected revisions instead of replaying the hosted runner's setup actions.
Do not run the workflow's commit/push steps: this comparison does not publish upstream changes.
The final `git annex add static` records the generated graph in Git Annex.
It does not generate graph content.
Omit that bookkeeping command in the scratch build, but keep the graph command before it unchanged.
The generated static files need no running Pool API for serving or comparison.

## Compare the outputs

Use SiteDiff for HTML and its exported HTML report for inspection.
The [tool selection](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/154) compares the available approaches.
The selected SiteDiff [fix](https://github.com/evolvingweb/sitediff/pull/215) preserves accented text and lowercase-doctype attributes.
Its commit and dependencies are locked in `tools/site-diff/Gemfile.lock`.
Do not substitute a crawler for the union of HTML paths in both build directories.

Install the comparison tool locally through Pixi:

```console
cd tools/site-diff
pixi exec --spec ruby=3.3.6 --spec libcurl --spec c-compiler --spec make -- bundle config set --local path ../../build/site-diff-gems
pixi exec --spec ruby=3.3.6 --spec libcurl --spec c-compiler --spec make -- bundle config set --local frozen true
pixi exec --spec ruby=3.3.6 --spec libcurl --spec c-compiler --spec make -- bundle install
```

Ruby's `racc` dependency needs the C compiler during installation.
These tools belong to the comparison environment, not downstream website builds.
Use absolute paths for `NATIVE_SITE`, `LITE_SITE`, and `REPORT` below.

Create an ignored report directory containing `sitediff.yaml`:

```yaml
before:
  url: /absolute/path/to/native
after:
  url: /absolute/path/to/lite
settings: {}
```

Generate the complete path list, then run SiteDiff from `tools/site-diff`:

```console
{
  (cd "$NATIVE_SITE" && rg --files --hidden --no-ignore -g '*.html')
  (cd "$LITE_SITE" && rg --files --hidden --no-ignore -g '*.html')
} | sort -u | sed 's|^|/|' > "$REPORT/paths.txt"
pixi exec --spec ruby=3.3.6 --spec libcurl --spec c-compiler --spec make -- bundle exec sitediff diff -C "$REPORT" --paths-file "$REPORT/paths.txt" --cached=none --no-verbose --report-format=json
pixi exec --spec ruby=3.3.6 --spec libcurl --spec c-compiler --spec make -- bundle exec sitediff diff -C "$REPORT" --paths-file "$REPORT/paths.txt" --cached=none --no-verbose --export
```

Exit 2 means changed or missing pages, not a failed comparison.
SiteDiff labels one-sided pages as errors.
Inspect their paths and classify them as added or removed pages.
Open the exported HTML report.
Retain the JSON result and an unfiltered file diff beside it.

```console
mkdir -p "$REPORT/viewer"
tar -xzf "$REPORT/report.tgz" -C "$REPORT/viewer"
```

Open `$REPORT/viewer/report/report.html` in a browser.

HTML comparison does not execute JavaScript or compare referenced file contents.
Also compare graph data, search entries, images, scripts, styles, and downloads.
A short disposable script is sufficient for JSON and file comparisons.
Report only differences between the two outputs.
Do not list defects shared by both.

For the current graph format, check edge fields before comparing counted relationships:

```console
jq -e 'all(.edges[]; keys == ["id","source","target"])' graph.json
jq -S '{nodes:(.nodes|sort_by(.id)), edges:(.edges|map({source,target})|sort_by(.source,.target))}' graph.json
```

Compare the normalized result from each site.
Sorting preserves duplicate relationships and all node fields.

Open both builds at the same viewport.
Check the home page, Explore, and one page from each generated record class.
Exercise search, menus, graph filters, and graph navigation.
Use a fixed random seed for graph screenshots, or apply the graph rule in the accepted-differences document.

## Write the report

Keep this shape on every run:

1. **Result:** whether new unexplained differences remain.
2. **Inputs and checks:** capture time, selected input/software commits, commands, tool report, and browser checks.
3. **New differences:** example path, native result, Lite result, cause, and proposed action.
4. **Accepted differences:** a brief list linking to the standing decisions.

Use three statuses: **accepted**, **needs investigation**, and **needs correction**.
For corrections, state **before adoption** or **later**, with the concrete impact that determines urgency.
An input mismatch means repeat the comparison with matching inputs, not accept a Lite difference.
Do not request another decision for an unchanged accepted difference.
Report metadata differences only when values or meaning change, not when YAML storage or equivalent identifier notation changes.
Keep generated reports and screenshots out of canonical site inputs.

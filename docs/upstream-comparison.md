# Compare upstream and Orinoco Lite

Maintainers use this procedure to check the [thin deployment layer](project-design.md#validate-the-deployment-layer) after a package, template, or upstream change.
The [current report](agents/upstream-deployment-validation.md) records the findings and decisions still needed.
Use the charter's terms: upstream, downstream, records, and projection.

## Choose the comparison

Two comparisons answer different questions:

- **Same-capture generation:** Give native ORINOCO and Orinoco Lite the same retained Pool capture and required site inputs.
  Compare the sites that they generate.
  This checks Orinoco Lite's implementation.
- **Live-site comparison:** Compare the downstream deployment with an upstream deployment.
  Differences can also come from capture age, deployment age, authored content, media, or the chosen upstream branch.
  Do not call those differences package regressions without checking their source.

Upstream's [deployment workflow](https://hub.psychoinformatics.de/www/www-from-model/src/commit/dc2a3f2d4734cdd16b33bbcdd654687f809ef29a/.forgejo/workflows/deploy.yml#L45-L51) selects these destinations:

| Upstream branch | Website |
| --- | --- |
| `main` | [Draft](https://www-draft.psychoinformatics.de/) |
| `published` | [Production](https://www.psychoinformatics.de/) |

The workflow triggers automatically on `main` pushes and supports manual dispatch.
Its branch head is not proof of the last successful deployment.
Record the deployed commit when available, or state that it is unknown.
Also distinguish an upstream commit from the selected Orinoco Lite mirror commit, which can include retained patches.

## Use the retained repositories

| Repository | What it records |
| --- | --- |
| [psychoinformatics-downstream](https://github.com/ORINOCO-Lite/psychoinformatics-downstream) | Package selection and lock, template selection, deployment settings, and the site-specific submodule commit |
| [psychoinformatics-site-specific](https://github.com/ORINOCO-Lite/psychoinformatics-site-specific) | Pool capture, converted YAML records and annotation companions, authored content, and ordinary media files |

Use the submodule commit recorded by the downstream, not the current input repository's `main` branch.
The raw capture is `site-specific/sources/pool/public-thing.jsonl`.
The capture does not contain image bytes, authored pages, or deployment settings.
Do not copy generated record pages into the inputs.
Check differences between the native authored pages and media and the downstream's retained inputs.
Treat those as input differences, not package regressions.

For a software repin, keep those inputs fixed and change only the candidate software selections.
For a data update, retain one new capture and use it for both generation processes.
Review converted record changes and media changes separately.
Do not maintain a second list of pins: use Git, the submodule, and the existing dependency files.

### Rebuild the recorded downstream

Use a fresh directory so the check does not change another developer's work.
Set `DOWNSTREAM_COMMIT` to the full commit under review.

```console
git clone --no-checkout https://github.com/ORINOCO-Lite/psychoinformatics-downstream.git build/psychoinformatics-check
cd build/psychoinformatics-check
git checkout --detach "$DOWNSTREAM_COMMIT"
git submodule update --init --recursive
pixi install --frozen
pixi run python -m orinoco_lite.upstream_orinoco_records verify \
  site-specific/sources/pool/public-thing.jsonl site-specific
pixi run build
pixi run orinoco-lite verify-site build/site
```

`build` uses `/` as the base URL for the local comparison.
Check `build-pages` separately when testing the configured publication URL and its path prefix.
Neither command needs a Pool API.
The capture check compares the retained YAML and annotation companions with the raw capture under the converter's current rules.
Review the reported value changes even when that check passes.
If people curated the YAML after capture, explain those changes or choose unchanged inputs for the same-capture test.

A build of retained YAML does not test capture conversion.
When the converter changes, also run `dev setup --snapshot CAPTURE` in a separate disposable downstream.
Supply the reviewed authored pages and media before comparing its output.
Use the existing downstream development commands for candidate package or template changes.
Do not update the persistent downstream or its inputs as a side effect of a comparison.

### Regenerate the native reference

The native setup remains a maintainer procedure, not a second deployment application.
Use the selected revision's own [Pool update workflow](../submodules/www-from-model/.forgejo/workflows/update-from-pool.yaml).
The procedure below describes the current `main`-derived workflow.
An older `published` revision can require different query tools and filters.

1. Prepare the selected service, client, schema, query tools, website, and its declared Congo dependency.
   Prepare required media before generation.
2. Create a disposable Pool store with a `public` collection and the selected research-information schema.
   Use the service's `sqlite+stl` backend, anonymous `READ_CURATED`, and a temporary local `CURATOR` token.
   Start it on an unused loopback port.
   Never seed the public Pool or an existing local service.
3. Seed the capture with the selected client:

   ```console
   jq -c '.record' "$CAPTURE" | DTC_TOKEN="$LOCAL_CURATOR_TOKEN" dtc post-records --curated "$LOCAL_API" public '*'
   ```

   Read the records back and compare their PIDs and values with the capture.
   Limit the temporary token to this local seeding command.
4. Copy the selected website into a scratch directory.
   Remove its generated record Markdown and `static/graph.json` before generation.
   Generated Markdown has `params.graphRootNodePID` or `params.generated` in its front matter.
   Retain authored pages, section introductions, and media.
5. Point `DUMPTHINGS_APIURL` to the local service and `QRI_RECORD_CACHE` to a new, empty cache path.
   Run the workflow's graph, member-selection, record-page, and frontpage commands with Bash `pipefail` enabled.
   Read those commands from the selected workflow rather than keeping a separate copy.
   Omit checkout, installation, and deposit steps, plus the graph step's final `git annex add static` command.
6. Run the selected Hugo with `--minify --baseURL /` into a fresh destination.
   Stop the temporary Pool service.

The Pool API supports native generation, including reverse-link queries.
It is not needed to serve or compare the resulting files.
Serving committed `www-from-model` pages does not exercise this generation process.
The old `build_upstream_site.sh` and service-preview scripts do not replace it.

For a fresh capture, use `pixi run python tools/prepare_upstream_snapshot.py --refresh --api URL` in the engineering checkout.
Without `--refresh`, an existing capture must have matching origin information and pass the cache checks.
Software selection, capture refresh, and comparison-cache refresh are separate operations.

## Produce the comparison reports

Run a comparison tool for every review, then interpret its findings.
Do not use a successful build or an agent's visual impression as the complete comparison.
Use directories for local builds so pages without incoming links remain in scope.

This recipe uses the tested [summarized-sitediff revision](https://github.com/yarikoptic/summarized-sitediff/tree/487f39bf6dd6e8b2810a23385b51ea8baa6048bf).
It is an external prototype, not a package or website dependency.
The selected `sitediff (3).py` supports directory inputs and machine-readable output.
Install `uv` separately, then run these commands from the engineering checkout.
Set `NATIVE_SITE` and `LITE_SITE` to the two generated output directories.

```console
git clone https://github.com/yarikoptic/summarized-sitediff.git build/summarized-sitediff
git -C build/summarized-sitediff checkout --detach 487f39bf6dd6e8b2810a23385b51ea8baa6048bf
mkdir -p build/site-comparison
uv run --no-project --python 3.12 'build/summarized-sitediff/sitediff (3).py' \
  "$NATIVE_SITE" "$LITE_SITE" --no-cache --strict-unicode \
  --max-hunk-lines 10000 \
  --json build/site-comparison/site-diff.json \
  --md build/site-comparison/site-diff.md
git diff --no-index --no-ext-diff --no-textconv -- "$NATIVE_SITE" "$LITE_SITE" > build/site-comparison/files.diff
```

The last command returns status 1 when files differ, which is expected.
Keep its unfiltered output alongside the grouped report.
Do not pass `--summarize`: the tool needs no LLM call to produce these reports.
The reviewing agent supplies interpretation separately.
Do not exclude navigation, footers, editing links, or branding before the first review.

The prototype does not detect every difference.
It masks hexadecimal strings of at least 16 characters, even with `--strict-unicode`.
It misses script and image URL changes and does not compare graph data or check broken links.
Use `files.diff` to inspect those omissions.
Check graph nodes and relationships, search results, media, and downloads explicitly.
Compare full node objects and counted edge endpoints only after checking that edges contain no fields beyond `id`, `source`, and `target`.

Open both sites at the same viewport.
Check the home page and one page from each generated record class.
Exercise search, menus, graph filters, and graph navigation.
A static diff does not establish working browser behavior or authenticated editing.

## Explain each difference

For each group, name an example URL, the visible or data change, its source, and who should resolve it.
Use these decisions consistently:

- **Deliberate:** Explain the project requirement that causes the difference.
- **Ignore by rule:** State the narrow rule and the checks that make it safe.
- **Fix soon:** Name the incorrect or missing behavior.
- **Later:** Explain the limited current impact and when to revisit it.
- **Decision needed:** Name the unresolved choice. Do not treat it as approval.

Keep reports, raw diffs, and screenshots as review output, not canonical site inputs.
Link them from the review and state which commands produced them.
State which checks did not run.
Use the current report for unresolved findings and Git for earlier results.

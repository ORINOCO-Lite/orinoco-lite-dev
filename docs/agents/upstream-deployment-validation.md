# Review upstream deployments

Maintainers and agents use this guide to test the [thin deployment layer](../project-design.md#validate-the-deployment-layer).
Keep current unresolved differences here, disposable output under ignored build directories, and history in Git or pull requests.
Known differences are not automatically accepted deviations.

## Exercise the ordinary downstream

Choose the package and template changes under test and one captured Pool JSONL file.
Use the selected template checkout, not a copied presentation assembled by another script:

```console
pixi run orinoco-lite dev setup /path/to/new-downstream \
  --template /path/to/orinoco-lite-template --snapshot /path/to/pool.jsonl
cd /path/to/new-downstream
pixi run orinoco-lite build --base-url /
pixi run orinoco-lite verify-site build/site
pixi run orinoco-lite serve
```

Setup converts and commits site inputs and prepares the editable package; it does not project or build.
Preserve existing downstreams.
Use their normal development connection rather than routine `--force` recreation.
Python changes take effect through the editable connection; rebuild bundled resources with `dev prepare-resources` after their sources change.
Build uses the downstream's selected toolchain and the package's normal projection, validation, and composition sequence.

For a fresh capture, the existing engineering helper accepts `pixi run python tools/prepare_upstream_snapshot.py --refresh`, optionally with `--api URL`.
It fetches once; use its `build/upstream-stack/pool/public-thing.jsonl` for both deployments.
Do not silently refresh one side, relabel a cache from another API, or change software revisions while comparing data flows.
This acquisition helper is not a deployment test.

## Native reference and comparison limits

The selected upstream `.forgejo/workflows/update-from-pool.yaml` defines the graph and query/Jinja pipelines; `.forgejo/workflows/deploy.yml` defines Hugo deployment. Run those operations against an isolated Pool loaded with the same capture, using upstream's service development procedure. Do not write into the public Pool or reuse committed generated pages or graph as the reference result. Keep acquisition/storage operations separate from rendering; Git Annex remains maintainer-only repinning tooling for Orinoco Lite.

A populated query cache alone is insufficient: native linked-record filters and injected relationships also query the API.
Pointing them at the live Pool while reading a saved cache mixes datasets.
There is currently no supported snapshot-only native runner in this repository.
Until an upstream-native isolated service or offline backend supplies that boundary, report native comparison as **not performed**, even when the downstream build and pytest pass.
Do not restore the old custom service/rendering harness to conceal this gap.

Once both builds succeed, compare their complete HTML path sets, including unlinked pages and named URLs; source Markdown paths do not necessarily equal published routes.
Compare graph node identities and relationship endpoints separately, not generated ordering or edge IDs.
At the same viewport, inspect the homepage and one page of each rendered class for text, identifiers, dates, navigation, portraits, and missing assets.
Exercise search, menus, graph links, and representative downloads; check changed and deleted records for updated pages and removal of obsolete output.
Authentication and real GitHub editing/review require their separate configured-downstream tests.
`verify-site` checks the homepage and its direct references, not every link, every asset, or browser interactions.
Record an example and explanation for each new difference, its review status, and checks not performed.
Never compare stale output after a failed build.

## Tools and review status

[SiteDiff](https://github.com/evolvingweb/sitediff#comparing-2-sites) is an optional HTML comparison tool, not a package dependency.
Use its explicit path list with the union of both outputs and `--cached=none` for a fresh comparison; a crawl alone misses orphan pages.
Check an unchanged, changed, and missing page before trusting its normalization.
For visual investigation, [BackstopJS](https://github.com/garris/BackstopJS#comparing-different-endpoints-eg-comparing-staging-and-production) supports reference and candidate URLs, but adds browser configuration and image baselines.
Prefer a small manual browser review if either tool needs substantial custom maintenance.

| Area | Current interpretation |
| --- | --- |
| Curation and build information | Intended architecture: Lite adds static editing/review with GitHub proposals and package/content/build information. These do not justify unrelated content or navigation changes. |
| Record representation | YAML and machine-provenance companions are a storage adaptation, not permission to change assertions. An earlier capture contained an invalid `generated_by.at_time: "-"` value omitted by conversion; that source-value change still needs review. |
| Page selection | Follow selected upstream filters, including publication/dataset attribution to root-project members. Auxiliary records remain available to metadata and graph operations without standalone pages. |
| Named URLs | Expanded URL annotations previously reached Jinja as mappings. Regression tests now check upstream scalar behavior and graph/page agreement; the fresh downstream emits all five named routes. Its ORINOCO project page still contains UUID links, also present in the selected upstream committed page. Review these separately rather than assuming route presence proves link correctness. |
| Identifiers, navigation, identity | The fresh downstream still emits an empty Collaboration Hub link. Earlier identifier representation differences, missing identity images/copyright, and an extra home heading remain investigation targets, not approved adaptations. |
| Media | Upstream's separate `register-depictions.yaml` acquires media. Reusing existing assets does not test that operation, changed depiction relationships, or whether snapshot setup carries all site-specific assets. |

No complete same-capture deployment comparison has been established in the new downstream-first workflow.
The local package/template candidate passed ordinary `dev setup`, `build`, and `verify-site` with the saved Pool, but did not exercise a native reference, browser interactions, media acquisition, or authenticated curation.
The disposable downstream has no configured GitHub repository, so its review interface is disabled.

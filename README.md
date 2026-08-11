# Full CON migration development workspace

This repository coordinates the local-only **full CON migration** for the Center for Open Neuroscience website.
It expands the accepted clean-migration vertical slice into a populated site while keeping canonical content isolated, deterministic, and easy to rebase onto reviewed upstream changes.

The active parent and site branches are `codex/full-con-migration`, using reviewed upstream website commit `a9ac9d5abc3898fd13d9b8392008f0c323c8dcd8`.

The parent and site `codex/clean-migration` branches remain immutable accepted checkpoints.
The successor uses focused hand-authored content commits followed by one terminal, regenerable projection commit.

Legacy CON branches, tags, and the completed `orinoco-lite` prototype remain unchanged.
Nothing in this effort is pushed or deployed.

## Start here

Read the active execution plan and implementation contract before changing the site:

- [`docs/orinoco-lite-plan.md`](docs/orinoco-lite-plan.md)
- [`docs/full-con-migration.md`](docs/full-con-migration.md)
- [`docs/clean-migration.md`](docs/clean-migration.md)
- [`docs/explaining-schema-issues.md`](docs/explaining-schema-issues.md)

Install the locked environment and fully initialize every recursive development checkout:

```console
pixi install --locked
pixi run checkout-submodules
```

The main local interfaces are:

```console
pixi run build                  # deterministic backend-free CON artifact
pixi run verify-static          # require a byte-identical repeat build
pixi run serve-static           # CON artifact only, at 127.0.0.1:8767
pixi run serve                  # full CON editor/service/static stack
pixi run verify-con-projection  # two renders, both matching the Git snapshot
pixi run update-con-assembly    # accept reviewed static-assembly inputs
pixi run verify-con-assembly    # verify the second committed digest
pixi run build-upstream         # explicit German upstream reference build
pixi run serve-upstream         # explicit upstream reference server
pixi run test                   # focused contract tests
pixi run install-browser-tests  # one-time Chromium and WebKit setup
pixi run test-browser           # managed local browser acceptance
pixi run test-all               # unit and browser acceptance
pixi run check-format           # repository formatting hooks
```

`pixi run build` verifies the committed projection digest, hydrates only the manifest-declared annex assets, and assembles the CON Hugo source in ignored build state.
`pixi run verify-static` also requires a byte-identical repeat build.
The resulting `build/con-site` directory needs no metadata backend.

Projection updates are explicit:

```console
pixi run render-con-projection  # candidate in ignored build state
pixi run update-con-projection  # replace the reviewed Git snapshot
pixi run verify-con-projection  # regenerate twice and compare with Git
pixi run update-con-assembly    # refresh only the static-input digest
pixi run verify-con-assembly    # reject stale static inputs
```

While preparing a successor before the parent gitlink moves, a developer may set `CON_SITE_ROOT` to that local site checkout for render/update work.
This is only a temporary workspace override; no absolute successor path belongs in Pixi configuration or committed manifests.
Final build and acceptance run without that override after the parent gitlink points at the reviewed successor tip, and require the site checkout to be clean with exactly one terminal projection snapshot commit.

A normal build fails closed when relevant canonical records, profile configuration, editorial content, assets, upstream presentation inputs, renderer code, Pixi pins, or component commits change without the corresponding projection or site-assembly refresh.
Metadata changes refresh both digests; editorial, styling, or asset-only changes refresh only the assembly digest.

Reviewed YAML in the clean site profile is the sole canonical metadata source.
The legacy website and `dump-research-info` are migration evidence only and do not participate in a normal build.

## Local collection boundary

The full stack uses four separate collections:

| Collection | Contents |
| --- | --- |
| `upstream-public` | Cached German public snapshot |
| `upstream-protected` | Local protected counterpart of that snapshot |
| `con-public` | Manifest-declared canonical CON and reference records |
| `con-protected` | CON editor incoming boundary |

The editor reads and writes only through `con-protected`.
The projection reads only `con-public`.
The cached German records are never seeded into either CON collection.
Tokens, stores, downloaded snapshots, hydrated annex objects, and generated sites stay under ignored `build/` state.

Curated records in `con-protected` are readable without a token so that an Edit link can populate the concrete SHACL Vue form.
The collection name describes its incoming edit boundary, not confidential curated data.
Submitting a change still requires the ignored token in `build/local-stack/editor-token`, and that token can write only to `con-protected/incoming/local-editor`.

## Browser acceptance

Browser dependencies are deliberately separate from the fast unit suite.
The first browser run needs network access to install the exactly locked Playwright package plus its Chromium and WebKit revisions:

```console
pixi run install-browser-tests
pixi run test-browser
```

The browser suite owns ports `8111`, `8122`, `3000`, and `8767` and refuses to reuse an already running stack.
Stop `pixi run serve` before starting it.
Playwright supervises the stack and verifies that all child services stop when the suite ends.

Chromium and WebKit exercise the real upstream-to-CON same-origin graph-cache transition and the Yaroslav editor link.
A separate Chromium scenario edits a disposable record through SHACL Vue, checks the CON incoming boundary, and cleans the record before and after the test.
It never modifies Yaroslav's real incoming record or records a credential in a URL, trace, screenshot, or video.

Playwright WebKit is useful Safari-like coverage, but it is not the system Safari browser.
On Linux, Playwright may report missing host browser libraries; this workspace does not install system packages or invoke `--with-deps` automatically.

## Reproducibility boundary

Pixi locks Hugo, Python, Dump Things, qri, LinkML, LinkML Runtime, Pydantic, RDFLib, Git Annex `10.20260601`, and their transitive dependencies.
Linux uses the Conda package; macOS ARM uses the pinned Python wheel in the same Pixi environment.
Asset retrieval uses read-only URLs without adding remotes or changing shared worktree configuration.

The native metadata contract is explicit `dlthings:*` CURIEs against the pinned source Things Schema.
Full-URI type designators, unknown CURIEs, dangling native targets, and generic `AttributeSpecification` relationship bridges are rejected.

## Scope boundary

This phase generalizes the proven profile and migrates the legacy-equivalent people, project, editorial, branding, and asset experience.
The broader Zotero collection is deferred.

It does not publish GitHub Pages, configure pull-request editing, change DNS, update production, or run a persistent hosted metadata service.
The documented rebase drill reviews a candidate upstream range, replays the hand-authored site commits without their terminal generated commit, regenerates the projection, inspects `range-diff`, reruns acceptance, and only then updates the parent gitlink locally.

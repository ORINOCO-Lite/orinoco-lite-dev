# Orinoco Lite engineering workspace

Orinoco Lite turns schema-backed records and editorial inputs into a static website with browser-based metadata editing and source-adapter review.
See the concise [`project design charter`](docs/project-design.md) for the durable objective, component boundaries, and data flows.

This repository contains the Python package, engineering tests and release assembly.
The package reuses an exact upstream website revision, [`orinoco-lite-template`](https://github.com/ORINOCO-Lite/orinoco-lite-template) supplies a thin adaptation and scaffold, and each deployed website is configured by one ordinary downstream repository.

## Repository roles

  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
Repository                                                                                             Role
  ------------------------------------------------------------------------------------------------------ ------------------------------------------------------------------------------
[`orinoco-lite-dev`](https://github.com/ORINOCO-Lite/orinoco-lite-dev)                                 Package development, release assembly, and engineering tests

[`www-from-model`](https://github.com/ORINOCO-Lite/www-from-model)                                     Submodule-pinned Hugo and projection source

[`orinoco-lite-template`](https://github.com/ORINOCO-Lite/orinoco-lite-template)                       Thin Orinoco adaptation, scaffold, workflows, and locks

`<github-user>/orinoco-lite-demo`                                                                      Optional user-owned site for autonomous GitHub-workflow experiments

  [`test-orinoco-downstream-website`](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website)   Human-gated reference downstream
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

The package resolves and composes the upstream website, while the template owns only the Orinoco-specific adaptation and downstream scaffold.
A downstream provides declarative `site-specific/` inputs and optional overrides, plus site-specific executable metadata adapters under `extensions/`.

The static website owns `/edit/` for SHACL Vue editing and `/review/` for source-adapter decisions.
The central curation service, or an optional replacement, provides only GitHub authentication and verified transport.

## Command environment

See [dependency management](docs/agents/dependency-management.md) for editable submodule setup and release requirements.

Use Pixi 0.76 or newer; CI always installs the latest Pixi.
Older local versions receive best-effort support without a formal version matrix.
The development `pixi.lock` is local and untracked; Pixi updates it when dependency declarations change.
Before running the commands below, enter that repository's environment:

``` console
unset PIXI_LOCKED
pixi shell
```

To leave an already installed environment and its lock unchanged, use `pixi shell --as-is` instead.
See the [Pixi shell options](https://pixi.prefix.dev/latest/reference/cli/pixi/shell/).
Run installed commands directly inside the shell; use `exit` before switching repositories and activating another environment.
For noninteractive execution, use `pixi run <command>`.
Commit dependency declarations and submodule selections, not the development lock.
Release consumer locks are generated and tested by the release workflow.

## Downstream interface

Site maintainers run these commands in their downstream's environment:

``` console
orinoco-lite validate
orinoco-lite build --base-url /
orinoco-lite serve
```

The downstream selects its Orinoco Lite package and template versions and chooses when to update either one.
`orinoco-lite template update` selects the latest tagged release (including release candidates) and applies a Copier update recorded through DataLad, using the selected template's package declaration by default.
Use `--revision main` or an exact commit to select development work.
Explicit `--package-revision` and `--package-repository` overrides are recorded separately.
The template's **Update downstream template** GitHub workflow calls this command and opens a draft pull request; see the [downstream update guide](https://github.com/ORINOCO-Lite/orinoco-lite-template/blob/main/copier-template/docs/template-updates.md).
Validation, building, previewing, deployment, bundle download, and editing do not require a continuously running metadata service.
Source-adapter tasks use DataLad to record run provenance in Git.
Distribution builds use Git Annex to retrieve required upstream assets and bundle the rendering subset.
Installed wheels build sites without an upstream checkout or upstream asset downloads; editable installs use the nested working source.
Sites can also opt into [Annex media](docs/agents/annex-media.md) for their own media.

Precise interfaces and normative engineering behavior are documented in:

- [`source adapters`](docs/agents/contract/source-adapters.md)
- [`curation review`](docs/agents/contract/github-curation-review.md)
- [`SHACL Vue editing`](docs/agents/contract/github-shacl-vue-edit.md)
- [`curation-service authentication`](docs/agents/contract/curation-service-authentication-options.md)

## Engineering workflow

In a fresh engineering checkout, initialize its recursive submodules before installing the Pixi environment:

``` console
python3 tools/setup_submodule_remotes.py
pixi run orinoco-lite dev prepare-resources
pixi run pytest
```

Package versions come from Git tags through Versioneer.
`orinoco-lite --version` reports the current commit and dirty state in an editable checkout; installed distribution metadata refreshes when the package is reinstalled.
Normal downstream installations retain the version recorded at build time.
Release tags use `v` followed by a Python package version; manually dispatched artifact builds use the selected ref's derived version.

Upstream website reproduction always uses downstream development mode with `.orinoco-lite/orinoco-lite-dev` tracked as a Git submodule.
Its nested `www-from-model` checkout supplies authored inputs and Annex media; ordinary downstreams use the bundled rendering resources without cloning upstream.
See [upstream instantiation](docs/upstream-tracking.md).

For ordinary local development in an existing downstream, `pixi run orinoco-lite dev enable` creates a local checkout at `.orinoco-lite/orinoco-lite-dev` and installs its Python dependencies editable in the downstream environment.
The checkout is locally ignored; manifest and lock changes need no commit.
See [dependency management](docs/agents/dependency-management.md) for source selection and re-running enable.

After editing bundled resource sources, run `pixi run orinoco-lite dev prepare-resources` in the engineering checkout.

The CLI owns operation sequencing: `orinoco-lite build` updates projection before validation and building.
Pixi's downstream tasks supply convenient arguments.
Use `pytest`, a test path, or pytest's selection flags to exercise code changes.
The replacement-metadata test uses `../orinoco-lite-template`, including local edits; set `ORINOCO_TEST_TEMPLATE` to select another checkout.
It skips only when neither selection is available locally; CI explicitly selects its template candidate.
This test uses the existing connected-record fixture and ordinary build CLI; upstream website fidelity is checked separately.
The original upstream application retains its own native development commands.

Project-owned agent skills are canonical, ordinary files under `.agents/skills/`.
Edit them there directly; they do not require APM or a setup hook.
Do not add a package manager, manifest, lock, bootstrap task, or agent hook while every skill is owned by this repository.
Introduce dependency management only when the project first consumes an independently maintained promoted skill; the chosen setup mechanism remains a downstream preference.

The setup command initializes missing submodules and configures the authoritative `upstream` remotes for known mirrors.
It preserves existing working checkouts and `origin` URLs; `--check` reports required setup without changing Git state.
Run it before Pixi because the editable package depends on local submodule sources.
To deliberately reset every submodule to its recorded gitlink and fetch full history, use:

``` console
python tools/checkout_submodules.py
```

Release artifacts are assembled by [`orinoco-release.yml`](.github/workflows/orinoco-release.yml) from a `v<version>` tag or an explicitly dispatched commit.
Wheels carry the gitlink-selected Python dependency revisions; source archives retain those requirements for rebuilding.
Downstreams can select a tag or exact commit with `orinoco-lite package update --revision TAG_OR_COMMIT`.
Dependency locks and release inputs contain the versions required by the build; they are not a model for site metadata or project documentation.

## Boundaries

- Original software is MIT licensed; documentation is CC BY 4.0, factual metadata is CC0 1.0, and media licensing remains item-specific.
  See [`LICENSES.md`](LICENSES.md).
- Canonical site metadata is the YAML below the configured records and annotation roots.
  Generated projection and website output are ignored.
- The German website and its declared dependency closure are resolved at their selected Git revisions rather than copied wholesale or pinned again in downstream configuration.
  Builds retrieve required Annex assets from that same checkout and copy ordinary files into the assembly.
  Editable installs use the package’s nested working checkout, including local edits; fixed installs use the package’s committed gitlink.
  Both reuse unchanged projections and Hugo resource caches; editable dependency source changes invalidate the projection cache.
- Credentials, stores, caches, browser downloads, and build output are local state.

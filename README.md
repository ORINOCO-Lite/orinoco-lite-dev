# Orinoco Lite engineering workspace

Orinoco Lite turns schema-backed records and editorial inputs into a static website with browser-based metadata editing and source-adapter review.
See the concise [`project design charter`](docs/project-design.md) for the durable objective, component boundaries, and data flows.

This repository contains the Python package, engineering tests and release assembly.
The package reuses an exact upstream website revision, [`orinoco-lite-template`](https://github.com/ORINOCO-Lite/orinoco-lite-template) supplies a thin adaptation and scaffold, and each deployed website is configured by one ordinary downstream repository.

## Repository roles

| Repository | Role |
| --- | --- |
| [`orinoco-lite-dev`](https://github.com/ORINOCO-Lite/orinoco-lite-dev) | Package development, release assembly, and engineering tests |
| [`www-from-model`](https://github.com/ORINOCO-Lite/www-from-model) | Submodule-pinned presentation and projection source |
| [`orinoco-lite-template`](https://github.com/ORINOCO-Lite/orinoco-lite-template) | Thin Orinoco adaptation, materialized assets, scaffold, workflows, and locks |
| `<github-user>/orinoco-lite-demo` | Optional user-owned site for autonomous GitHub-workflow experiments |
| [`test-orinoco-downstream-website`](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website) | Human-gated reference downstream |

The package resolves and composes the upstream website, while the template owns only the Orinoco-specific adaptation and downstream scaffold.
A downstream provides declarative `site-specific/` inputs and optional overrides, plus site-specific executable metadata adapters under `extensions/`.

The static website owns `/edit/` for SHACL Vue editing and `/review/` for source-adapter decisions.
The central curation service, or an optional replacement, provides only GitHub authentication and verified transport.

## Command environment

Use the Pixi version range declared in the repository's `pixi.toml`.
Before running the commands below, enter that repository's environment:

```console
export PIXI_LOCKED=true
pixi shell
```

`PIXI_LOCKED` prevents lock-file updates and checks that the manifest matches the lock before synchronizing the environment.
To leave an already installed environment and its lock unchanged, use `pixi shell --as-is` instead.
See the [Pixi shell options](https://pixi.prefix.dev/latest/reference/cli/pixi/shell/).
Run installed commands directly inside the shell; use `exit` before switching repositories and activating another environment.
For noninteractive execution, use `pixi run <command>`.
Commands that intentionally change dependencies use `PIXI_LOCKED=false` to allow the required lock update, as shown below.

## Downstream interface

Site maintainers run these commands in their downstream's environment:

```console
orinoco-lite validate
orinoco-lite build --base-url /
orinoco-lite serve
```

The downstream selects its Orinoco Lite package and template versions and chooses when to update either one.
Validation, building, previewing, deployment, bundle download, and editing do not require a continuously running metadata service.
Source-adapter tasks use DataLad to record run provenance in Git.
They do not require Git Annex, and ordinary website builds never invoke it.

Precise interfaces and normative engineering behavior are documented in:

- [`source adapters`](docs/agents/contract/source-adapters.md)
- [`curation review`](docs/agents/contract/github-curation-review.md)
- [`SHACL Vue editing`](docs/agents/contract/github-shacl-vue-edit.md)
- [`curation-service authentication`](docs/agents/contract/curation-service-authentication-options.md)

## Engineering workflow

In a fresh engineering checkout, activate its environment, initialize the sources used by package resources and tests, then prepare the editable package before running pytest:

```console
git submodule update --init -- \
  submodules/pool.psychoinformatics.de-ui submodules/things-schemas \
  submodules/query-things submodules/www-from-model
git -C submodules/pool.psychoinformatics.de-ui submodule update --init -- shacl-vue
orinoco-lite dev prepare-resources
pytest
```

Create an inspectable downstream populated from the upstream Pool:

```console
pixi run setup-upstream ../orinoco-lite-test-downstream
```

The [setup script](tools/setup-upstream.sh) verifies that the package candidate is fetchable, creates a non-Annex dataset, applies the selected template through `pixi exec`, and records an immutable package selection and lock.
It switches once into the downstream Pixi environment and invokes the package-owned `dev upstream populate` workflow.
Existing destinations and unpublished package candidates are refused; setup never pushes code.
The default package candidate is the engineering checkout's committed HEAD on its origin remote.
Use `--package-repository URL` and `--package-revision REV` to choose another.

`--template PATH` and `--template-ref REV` select a template commit; setup verifies it on that checkout's origin and records the remote URL, not the local checkout path.
`--snapshot PATH` saves supplied bytes as the retained input boundary instead of recording a machine-local copy command; `--site-specific PATH` installs an existing dataset as a submodule and skips imports.
New site inputs become an ordinary Git subdataset by default; `--site-layout directory` keeps them directly in the downstream repository.
Site-specific Annex support remains a separate experiment in issue #168.

In any downstream, the installed package owns the repeatable workflow:

```console
pixi run orinoco-lite dev upstream populate
pixi run orinoco-lite dev upstream populate --reuse-capture
```

The first records a fresh acquisition, JSONL-to-YAML conversion, and site import as separate DataLad runs.
The second transforms the retained capture without acquisition.
`--directory` and `--destination` select the capture and site-input directories.
Recorded acquisition and conversion commands include `--force` so reruns can replace their outputs.
Site import follows the installed package's upstream pins and retrieves the selected upstream media into `site-specific/` as ordinary files.
It synchronizes imported content, assets, and static files, deleting obsolete files like `rsync --delete`; metadata remains separate.
This preparation step always uses the pinned Git Annex package through an isolated `pixi exec` / `uvx` invocation; it prints the retrieval commands.
The generic template does not contain upstream site media, and ordinary builds do not use Annex.
Setup and population stop before projection, builds, comparisons, and deployment.

Individual commands also accept explicit paths, without recording themselves:

```console
pixi run orinoco-lite dev records get --output sourcedata/pool.jsonl --force
pixi run orinoco-lite dev records jsonl-to-yaml --source sourcedata/pool.jsonl --destination site-specific --force
pixi run orinoco-lite dev upstream import-from-www --destination site-specific
pixi run orinoco-lite dev records yaml-to-jsonl --source site-specific --output inspection/records.jsonl
pixi run orinoco-lite dev records diff sourcedata/pool.jsonl site-specific --report inspection/comparison
```

`records get --api URL` supports other compatible Dump Things servers.
Without explicit paths, individual record commands retain the `upstream-diffing/` layout.
Site import reports its upstream revision and files; `--source` and `--revision` remain available for explicit upstream experiments.
The default media source is the original upstream Annex host; `--media-remote URL` selects another source.
With an explicit `--source` checkout, its existing Annex remotes are used unless overridden.

Select a newer package with `orinoco-lite package update --revision REV`, optionally wrapped in `datalad run --explicit --output pixi.toml --output pixi.lock --`.
It resolves the remote revision to an exact commit and updates the lock without replacing the running environment.
Record transformations reject a running package that differs from the manifest’s immutable Git selection.
Inspect and record the selection, then start a fresh `pixi run datalad rerun RUN_COMMIT` to execute a recorded transformation in that environment.
Keep the capture fixed to inspect software changes, or record a fresh capture to inspect data changes.
For historical reproduction, restore the desired environment and inputs before starting Pixi; DataLad rerun does not switch a running environment, and its `--onto` option does not restore subdataset worktrees.

`dev enable [PATH]` and `dev disable` remain explicit editable-development conveniences; normal setup does not use them.
After editing bundled resource sources, run `pixi run orinoco-lite dev prepare-resources` in the engineering checkout.

The CLI owns operation sequencing: `orinoco-lite build` updates projection before validation and building.
Pixi's downstream tasks only supply convenient arguments.
Use `pytest`, a test path, or pytest's selection flags to exercise code changes.
The original upstream application retains its own native development commands.

Project-owned agent skills are canonical, ordinary files under `.agents/skills/`.
Edit them there directly; they do not require APM or a setup hook.
Do not add a package manager, manifest, lock, bootstrap task, or agent hook while every skill is owned by this repository.
Introduce dependency management only when the project first consumes an independently maintained promoted skill; the chosen setup mechanism remains a downstream preference.

Initialize the remaining engineering submodules only when broader cross-component work needs them:

```console
python tools/checkout_submodules.py
```

Release artifacts are assembled by [`orinoco-release.yml`](.github/workflows/orinoco-release.yml) from a `v<version>` tag; the workflow applies that version only to its copied package source.
Dependency locks and release inputs contain the versions required by the build; they are not a model for site metadata or project documentation.

## Boundaries

- Original software is MIT licensed; documentation is CC BY 4.0, factual metadata is CC0 1.0, and media licensing remains item-specific.
  See [`LICENSES.md`](LICENSES.md).
- Canonical site metadata is the YAML below the configured records and annotation roots.
  Generated projection and website output are ignored.
- The German website and its declared dependency closure are resolved at their selected Git revisions rather than copied wholesale or pinned again in downstream configuration.
  Maintainer repinning hydrates and verifies required Annex-backed content and may place assets required by retained functionality in a bounded licensed template overlay as ordinary files; downstreams do not hydrate them.
- Credentials, stores, caches, browser downloads, and build output are local state.

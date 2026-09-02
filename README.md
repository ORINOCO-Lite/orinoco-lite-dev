# Orinoco Lite engineering workspace

Orinoco Lite turns schema-backed records and editorial inputs into a static website with browser-based metadata editing and source-adapter review.
See the concise [`project design`](docs/project-design.md) for the durable objective, component boundaries, and data flows.

This repository contains the engine, engineering tests, release assembly, and reusable CI.
The engine reuses an exact upstream website revision, [`orinoco-lite-template`](https://github.com/ORINOCO-Lite/orinoco-lite-template) supplies a thin adaptation and scaffold, and each deployed website is configured by one ordinary downstream repository.

## Repository roles

| Repository | Role |
| --- | --- |
| [`orinoco-lite-dev`](https://github.com/ORINOCO-Lite/orinoco-lite-dev) | Engine, runtime assembly, engineering tests, and reusable CI |
| [`www-from-model`](https://github.com/ORINOCO-Lite/www-from-model) | Submodule-pinned presentation and projection source |
| [`orinoco-lite-template`](https://github.com/ORINOCO-Lite/orinoco-lite-template) | Thin Orinoco adaptation, materialized assets, scaffold, workflows, and locks |
| `<github-user>/orinoco-lite-demo` | Optional user-owned site for autonomous GitHub-workflow experiments |
| [`test-orinoco-downstream-website`](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website) | Human-gated reference downstream |

The engine resolves and composes the upstream website, while the template owns only the Orinoco-specific adaptation and downstream scaffold.
A downstream provides declarative `site-specific/` inputs and optional overrides, plus site-specific executable metadata adapters under `extensions/`.

The static website owns `/edit/` for SHACL Vue editing and `/review/` for source-adapter decisions.
The central curation service, or an optional replacement, provides only GitHub authentication and verified transport.

## Downstream interface

Site maintainers use the tasks supplied by their template version:

```console
pixi install --frozen
pixi run validate
pixi run build
pixi run serve
pixi run test-all
```

The downstream selects its template version and upgrade timing.
Validation, building, previewing, deployment, bundle download, and editing do not require a continuously running metadata service.
Source-adapter tasks use DataLad to record run provenance in Git.
They do not require Git Annex, and ordinary website builds never invoke it.

Precise interfaces and normative engineering behavior are documented in:

- [`source adapters`](docs/agents/contract/source-adapters.md)
- [`curation review`](docs/agents/contract/github-curation-review.md)
- [`SHACL Vue editing`](docs/agents/contract/github-shacl-vue-edit.md)
- [`curation-service authentication`](docs/agents/contract/curation-service-authentication-options.md)
- [`packages/orinoco-lite/README.md`](packages/orinoco-lite/README.md)

## Engineering workflow

Pixi 0.76 or newer is required:

```console
pixi install --locked
pixi run test
```

Test unreleased engine and template bytes by injecting compact downstream inputs into a fresh disposable template instance before publishing them:

```console
pixi run test-downstream-candidate -- \
  --downstream /path/to/downstream \
  --engine "$PWD" \
  --template /path/to/orinoco-lite-template
```

Either candidate may be omitted.
Quick mode validates a compact adapter sample, builds the site, and checks browser routes.
Use `--mode full` before release or adoption, and `--keep` or `--output /new/path` to inspect the staged downstream.

Project-owned agent skills are canonical, ordinary files under `.agents/skills/`.
Edit them there directly; they do not require APM or a setup hook.
Do not add a package manager, manifest, lock, bootstrap task, or agent hook while every skill is owned by this repository.
Introduce dependency management only when the project first consumes an independently maintained promoted skill; the chosen setup mechanism remains a downstream preference.

Initialize engineering submodules only when cross-component work needs them:

```console
pixi run checkout-submodules
```

Release artifacts are assembled by [`orinoco-release.yml`](.github/workflows/orinoco-release.yml).
Dependency locks and release inputs contain the versions required by the build; they are not a model for site metadata or project documentation.

## Boundaries

- Original software is MIT licensed; documentation is CC BY 4.0, factual metadata is CC0 1.0, and media licensing remains item-specific.
See [`LICENSES.md`](LICENSES.md).
- Canonical site metadata is the YAML below the configured records and annotation roots.
Generated projection and website output are ignored.
- The German website and its declared dependency closure are resolved at their selected Git revisions rather than copied wholesale or pinned again in the runtime manifest.
Maintainer repinning hydrates and verifies required Annex-backed content and may place assets required by retained functionality in a bounded licensed template overlay as ordinary files; downstreams do not hydrate them.
- Credentials, stores, caches, browser downloads, and build output are local state.

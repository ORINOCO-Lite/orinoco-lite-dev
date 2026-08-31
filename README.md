# Orinoco Lite engineering workspace

Orinoco Lite turns schema-backed records and editorial inputs into a static website with browser-based metadata editing and source-adapter review.
See the concise [`project design`](docs/project-design.md) for the intended product and division of responsibilities.

This repository contains the engine, engineering tests, release assembly, and reusable CI.
The website framework belongs to [`orinoco-lite-template`](https://github.com/ORINOCO-Lite/orinoco-lite-template), and each deployed website is configured by one ordinary downstream repository.

## Repository roles

| Repository | Role |
| --- | --- |
| [`orinoco-lite-dev`](https://github.com/ORINOCO-Lite/orinoco-lite-dev) | Engine, runtime assembly, engineering tests, and reusable CI |
| [`orinoco-lite-template`](https://github.com/ORINOCO-Lite/orinoco-lite-template) | Reusable website, downstream defaults, and update mechanism |
| `<github-user>/orinoco-lite-demo` | Optional user-owned site for autonomous GitHub-workflow experiments |
| [`test-orinoco-downstream-website`](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website) | Human-gated reference downstream |

Reusable behavior belongs in the engine or template.
A downstream should mainly provide site-specific content, configuration, and custom source-adapter code.

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
pixi run update-check
```

The template owns framework updates.
Site-owned data and extensions remain in the downstream.
Validation, building, previewing, deployment, bundle download, and editing do not require a continuously running metadata service.

Detailed engineering contracts are maintained as agent coordination material:

- [`source adapters`](docs/agents/source-adapters.md)
- [`curation review`](docs/agents/github-curation-review.md)
- [`SHACL Vue editing`](docs/agents/github-shacl-vue-edit.md)
- [`curation-service authentication`](docs/agents/curation-service-authentication-options.md)
- [`packages/orinoco-lite/README.md`](packages/orinoco-lite/README.md)

## Engineering workflow

Pixi 0.76 or newer is required:

```console
pixi install --locked
pixi run test
```

Test unreleased engine or template bytes against a disposable downstream before publishing them:

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
APM is reserved for independently maintained agent dependencies that need a manifest, exact lock, update, and deployment lifecycle.
The agent-agnostic Pixi bootstrap materializes any such pinned dependencies and verifies their deployment without changing the engine environment:

```console
pixi run -e skills agent-deps-bootstrap
pixi run -e skills agent-deps-check
```

A downstream may call the bootstrap from its preferred workspace or agent setup hook, but the checked project skills remain available before that hook runs.
The dependency check disables APM's whole-directory drift replay because native project skills intentionally share `.agents/skills/` with APM-managed dependencies; APM still verifies its manifest, lock, selected skills, deployment ownership, and recorded content hashes.

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
- Credentials, stores, caches, browser downloads, and build output are local state.

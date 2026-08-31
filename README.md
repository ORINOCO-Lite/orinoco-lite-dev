# Orinoco Lite engineering workspace

Orinoco Lite turns schema-backed records and editorial inputs into a static website with browser-based metadata editing and source-adapter review.

This repository contains the engine, engineering tests, release assembly, and reusable CI.
The supported website is produced by [`orinoco-lite-template`](https://github.com/ORINOCO-Lite/orinoco-lite-template) and is configured by one ordinary downstream repository.

## Repository roles

| Repository | Role |
| --- | --- |
| [`orinoco-lite-dev`](https://github.com/ORINOCO-Lite/orinoco-lite-dev) | Engine, runtime assembly, engineering tests, and reusable CI |
| [`orinoco-lite-template`](https://github.com/ORINOCO-Lite/orinoco-lite-template) | Reusable website, update mechanism, and downstream defaults |
| [`leej3/orinoco-lite-demo`](https://github.com/leej3/orinoco-lite-demo) | Development downstream and end-to-end test site |
| [`test-orinoco-downstream-website`](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website) | Human-reviewed downstream example |

Reusable website behavior belongs in the engine or template.
A downstream should mainly provide its site-specific content, configuration, and any custom source-adapter executable code.

The static website owns both human-facing metadata routes: `/edit/` is its SHACL Vue editor and `/review/` is its source-adapter review interface.
The central curation service, or an optional replacement, provides only GitHub authentication and verified GitHub transport.

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
Static validation, building, previewing, deployment, bundle download, and editing do not require a continuously running metadata service.

See the current product contracts for details:

- [`docs/source-adapters.md`](docs/source-adapters.md)
- [`docs/github-curation-review.md`](docs/github-curation-review.md)
- [`docs/github-shacl-vue-edit.md`](docs/github-shacl-vue-edit.md)
- [`docs/curation-service-authentication-options.md`](docs/curation-service-authentication-options.md)
- [`packages/orinoco-lite/README.md`](packages/orinoco-lite/README.md)

## Engineering workflow

Pixi 0.76 or newer is required:

```console
pixi install --locked
pixi run test
```

Exercise unreleased engine or template bytes against a disposable copy of a normal downstream before publishing them:

```console
pixi run test-downstream-candidate -- \
  --downstream /path/to/downstream \
  --engine "$PWD" \
  --template /path/to/orinoco-lite-template
```

Either candidate may be omitted.
The default quick run validates a small adapter sample, builds the site, and checks browser routes.
Use `--mode full` before release or adoption, and `--keep` or `--output /new/path` when the staged downstream needs inspection.

Submodules are engineering inputs for cross-component development.
Initialize them only when that work needs them:

```console
pixi run checkout-submodules
```

Project-owned agent skills live under `.apm/skills/` and are deployed to `.agents/skills/`.
Check them with:

```console
pixi run -e skills apm-check
```

Release artifacts are assembled by [`orinoco-release.yml`](.github/workflows/orinoco-release.yml).
Dependency locks and release inputs contain the versions required by the build; they are not a general model for site metadata or project documentation.

## Boundaries

- Original software is MIT licensed; documentation is CC BY 4.0, factual metadata is CC0 1.0, and media licensing remains item-specific.
See [`LICENSES.md`](LICENSES.md).
- Canonical site metadata is the YAML below the downstream's configured records and annotation roots.
Generated projection and website output are ignored.
- Credentials, stores, caches, browser downloads, and build output are local state, not repository content.
- The production `centerforopenneuroscience.org` repository and deployment are outside normal engineering work.

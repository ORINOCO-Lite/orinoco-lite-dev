# Orinoco Lite development

This repository is the development and integration workspace for Orinoco Lite.
It tracks upstream Orinoco components, records architectural decisions, and
coordinates development of a GitHub-native lab website workflow.

Lab websites do not build or deploy from this repository. The first
implementation is [`con/www-from-model`](https://github.com/con/www-from-model),
which preserves the history of the upstream
[`www-from-model`](https://hub.psychoinformatics.de/www/www-from-model)
repository while adapting it for CON data, theming, GitHub Actions, and GitHub
Pages.

## Start here

The canonical implementation and handoff document is
[`docs/orinoco-lite-plan.md`](docs/orinoco-lite-plan.md).

The next milestone is a small, connected CON website preview built on a
`con-site` branch of `con/www-from-model`. It will combine reviewed metadata
migrated from `dump-research-info` with selected content and assets from
`centerforopenneuroscience.org`.

```mermaid
flowchart LR
    U["Upstream Orinoco repositories"] --> D["orinoco-lite-dev"]
    W["Upstream www-from-model"] --> I["con/www-from-model con-site branch"]
    C["CON website content and assets"] --> I
    R["Reviewed CON research metadata"] --> I
    I --> A["GitHub Actions build"]
    A --> P["GitHub Pages preview"]
    I --> F["Future reusable action and lab template"]
```

## Core constraints

- Canonical metadata is stored as human-editable YAML in Git.
- Pull requests are the review and publication boundary.
- Dump Things may run ephemerally during CI, but no persistent metadata server
  is required for a deployed lab website.
- Generated pages and projections are build artifacts, not canonical records.
- CON-specific content remains downstream; narrow reusable improvements may be
  contributed upstream.


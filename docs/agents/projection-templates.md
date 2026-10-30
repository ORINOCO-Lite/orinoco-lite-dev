# Customizing the selected upstream projection

Projection executes the selected `www-from-model` workflow with `query-things`.
Omit `site-specific/projection.yaml` to follow upstream unchanged apart from Lite's environment and storage adjustments.
Use this file only for deliberate differences from named upstream steps; it does not replace the workflow.

## Inherit a project template

Put this child in `site-specific/projection-templates/local-project.md.j2`:

```jinja
{% extends "project.md.j2" %}
{% block frontmatter_params %}{{ super() }}
  localContribution: true
{% endblock %}
{% block content %}{{ super() }}

Additional editorial content.
{% endblock %}
```

Select it with `site-specific/projection.yaml`:

```yaml
version: 3
extends: upstream
adjustments:
  - step: Update projects
    old: page_templates/project.md.j2
    new: page_templates/local-project.md.j2
    reason: Add local project presentation while inheriting upstream
```

Lite copies the selected upstream templates and the downstream child templates into a temporary rendering directory.
The upstream `query-things render-record` command supplies the Jinja loader, filters, and rendering behavior.
Children must use distinct filenames: local files cannot overwrite upstream parents.
Keep entry templates at the top level of `projection-templates/` so the native loader can find the upstream parents and their dependencies.
Nested includes follow ordinary Jinja lookup relative to that entry template's directory.

`super()` retains upstream content or parameters before the local addition.
The selected project and homepage templates support adding content and frontmatter through their existing blocks.
Insertion inside a parent's content block still requires an upstream extension point; do not copy the parent merely to simulate one.
Hugo layout/configuration overrides and authored `site-specific/content/` remain separate presentation surfaces.

## Change a selection without copying its implementation

For example, append this adjustment to include projects outside the upstream root project's membership:

```yaml
  - step: Update projects
    old: query-things filter-links-pid --link part_of xyzrins:. --recursive --collection public
    new: cat
    reason: Include independent projects in this site's catalogue
```

This replaces that filter with a pass-through; upstream inlining, reverse links, and rendering remain intact.
Each adjustment names an exact workflow step and replaces exactly one occurrence of `old` with `new`.
Adjustments apply in listed order after Lite's environment/storage changes.
Unknown steps, missing fragments, or ambiguous matches fail before execution.
They never fall back to a copied policy.
Review adjustments when updating the selected upstream revision.

Inspect the same adjustments used by builds:

```sh
orinoco-lite projection blocks --site site-specific show --view all
```

`--view raw` shows the unchanged upstream text; `--json` exposes original text, adjusted text, and reasons.
The lower-level `blocks run` command still requires a prepared directory and Pool/cache environment as described in its help.
It does not prepare or copy templates.

Validation reads homepage selection from the adjusted workflow, not a separate configuration value.
Changing one homepage PID does not change other organization selectors or the upstream schema, graph URLs, and template namespace assumptions.
Those remain owned by the selected upstream source; this interface is not an automatic site/schema converter.

## Migration and execution boundary

Version 2 `projection.yaml` files, including `extends: default` from the former Python projector, are not accepted.
Remove a file only when its behavior is intentionally identical to upstream.
Otherwise retain its site-specific differences as scoped adjustments and child templates, then exercise a complete build and editor preparation.
The former `www-from-model:` Jinja namespace is replaced by native parent filenames in the prepared template directory.

Lite is a shell-block adapter, not a Forgejo runner.
It explicitly replaces the selected checkout/environment/publication actions and rejects unknown actions, step execution settings, workflow expressions, and additional environment requirements.
It supplies the temporary Pool and cache instead of the workflow's production service coordinates.
Job scheduling and the selected source's repository guard do not apply to an explicitly requested local projection.

Editable installs use the actual nested source, including edits; distributions use their bundled rendering resources.
Projection caching includes the workflow, upstream templates, scoped adjustments, and local child templates.

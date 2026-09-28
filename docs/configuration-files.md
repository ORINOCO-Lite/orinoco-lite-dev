# Downstream configuration files

This document defines configuration ownership for downstream websites.

| File | Owns |
| --- | --- |
| `pixi.toml` | All environment dependencies, package selections, and executable tasks. |
| `pixi.lock` | Generated dependency resolutions. |
| `pyproject.toml` | Tool configuration. `[tool.orinoco.site]` holds website identity, navigation, and appearance. Separate `paths`, `media`, `service`, `github`, and `operations` tables under `[tool.orinoco]` hold path overrides, Annex media opt-in, service selection, repository fallback, and permitted operations. No downstream dependency declarations or tasks belong here. |
| `.copier-answers.yml` | Template source, revision, and answers used for scaffold generation and updates. |

The downstream root's `pyproject.toml` is the sole runtime configuration authority.
Keep defaults in the package and write only necessary settings and explicit user choices.

Copier may initialize site settings; the generated configuration becomes authoritative and later updates must preserve maintained choices.
Do not ask Copier questions for permitted automation.
On App installation, explain the operations and required permissions and direct the owner to enable the desired operations in `pyproject.toml`.
The central service is the default; an independent service is selected there by URL.
The service reads automation policy from the trusted default branch and site URLs from the trusted commit used for the operation, never from untrusted request values.

Upstream-reproduction tools must accommodate this downstream interface.
They update only the site settings they import, preserving operational policy and unrelated TOML, and record the changed root manifest alongside imported content.
Preserve import and refresh behavior; upstream reproduction does not justify retaining separate configuration files or constrain the downstream design.

The package, template, service readers, and authentication contract must implement this same boundary.

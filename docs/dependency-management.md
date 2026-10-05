# Dependency management

[`pyproject.toml`](../pyproject.toml) declares Python requirements and nested editable sources through `[tool.uv.sources]`.
[`pixi.toml`](../pixi.toml) selects the package checkout, external tools, and engineering tools; `pixi.lock` retains resolved versions.
The client override is the only repeated source: it supersedes the Git URL required by `query-things`; other Python sources are inherited from package metadata.
Git submodules record source revisions, while editable installations use working-tree edits.

## Working on the project
```console
git submodule update --init --recursive
export PIXI_LOCKED=true
pixi install --locked
pixi run orinoco-lite --help
```
After changing dependencies, run `env -u PIXI_LOCKED pixi lock`, then review and commit the manifest, lock, and any submodule changes together.

## Developing in a downstream

Run `pixi run orinoco-lite dev enable` from the downstream root.
The command initializes `submodule/orinoco-lite-dev` at the selected package commit, prepares resources, and installs it and its nested Python dependencies editable in the downstream's environment.
Use `--repository` and `--revision` to select a candidate when creating the submodule; use Git inside an existing submodule to change revisions.
An existing sibling checkout is not linked or modified.
Hugo and other non-Python tools remain selected by the downstream manifest.

Commit `pixi.toml`, `pixi.lock`, `.gitmodules`, and the software gitlink before disabling.
DataLad tasks that record enable must declare these paths as outputs; older template tasks targeting `.orinoco-lite/dev` must be updated before use.
The direct CLI leaves committing to the caller.

`pixi run orinoco-lite dev disable` restores the previous package selection and client override from Git history, preserving downstream additions and the source checkout's edits.
Python code changes need no reinstall; changed dependency metadata requires a deliberate re-lock.
If a stale or unsatisfiable development lock prevents the switch from starting, use the already installed environment for this recovery command only:

```console
env -u PIXI_LOCKED pixi run --as-is orinoco-lite dev disable
```

The switch itself relaxes locking for its install without changing the caller's environment.
Normal build and validation commands continue to use locked execution.
Generated editor and schema resources still need `orinoco-lite dev prepare-resources` after their source changes.

## Releases

The exact commits and git remote are injected during [releases](../.github/workflows/orinoco-release.yml).
Downstream users need no editable installations or software submodules.

Distribution of `www-from-model` software/assets and downstream submodule setup still need work; data import is deferred.

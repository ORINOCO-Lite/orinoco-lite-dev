# Dependency management

[`pyproject.toml`](../pyproject.toml) declares Python requirements and nested editable sources through `[tool.uv.sources]`.
[`pixi.toml`](../pixi.toml) selects the package checkout, external tools, and engineering tools; `pixi.lock` retains resolved versions.
`query-things` declares a normal client dependency; the package selects its editable source, so downstreams need no client override.
Git submodules record source revisions, while editable installations use working-tree edits.

## Dependency source conflicts

When a nested package requires a dependency through a hard-coded Git URL, first fix that declaration in the package that owns it.
Declare the package name and any necessary compatibility constraint; let the consuming project's source declarations select the checkout.
For example, the `query-things` fix replaces:

```toml
"dump-things-pyclient @ git+https://hub.psychoinformatics.de/orinoco/dump-things-pyclient.git@master"
```

with `"dump-things-pyclient"` in `[project].dependencies`.
Orinoco Lite's existing `[tool.uv.sources]` then selects the editable client submodule.
No sibling source declaration in `query-things` or downstream Pixi override is needed.

Check why the original source was required before removing it; retain actual compatibility requirements.
Prefer this correction over copying overrides into each environment: uv's `override-dependencies` is scoped to the workspace root and does not propagate from an installed dependency.
If the declaring package cannot be corrected, document the reason for an environment override.

Verify with a fresh downstream environment that has no override: confirm the client installs from the intended checkout and is editable.
Refresh the lock deliberately, commit the dependency patch, and record its committed gitlink in the parent before sharing the change.

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
The command clones `submodule/orinoco-lite-dev` locally, initializes the package's nested submodules, prepares resources, and installs its Python dependencies editable in the downstream environment.
The source checkout is excluded through Git's local `info/exclude`; enable does not register a downstream submodule, stage files, or require a commit.
`pixi.toml` and `pixi.lock` remain ordinary local modifications visible in Git.
Use the direct CLI rather than older template tasks that wrap enable in `datalad run`.

Use `--repository` and `--revision` to select a candidate when creating the checkout; use Git inside an existing checkout to change revisions.
Re-running enable preserves uncommitted source edits and downstream dependencies.
Hugo and other non-Python tools remain selected by the downstream manifest.
Python code changes need no reinstall; changed dependency metadata requires a deliberate re-lock.
If a stale lock prevents Pixi from launching enable, use the installed environment:

```console
env -u PIXI_LOCKED pixi run --as-is orinoco-lite dev enable
```

Enable itself relaxes locking for its install without changing the caller's environment.
Normal build and validation commands continue to use locked execution.
Generated editor and schema resources still need `orinoco-lite dev prepare-resources` after their source changes.

## Releases

The exact commits and git remote are injected during [releases](../.github/workflows/orinoco-release.yml).
Downstream users need no editable installations or software submodules.

Distribution of `www-from-model` software/assets and downstream submodule setup still need work; data import is deferred.

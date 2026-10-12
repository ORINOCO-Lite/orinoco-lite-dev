# Dependency management

For maintainers working on package dependencies and downstream development.

## Sources and locks

[`pyproject.toml`](../../pyproject.toml) owns Python requirements and editable submodule sources.
Gitlinks select dependency revisions; editable installs use working-tree edits.
The build backend derives fixed Git requirements from committed gitlinks and writes them into release metadata, including source archives.
Downstreams need no repeated source pins or overrides.
[`pixi.toml`](../../pixi.toml) selects the package and external tools.
Keep development `pixi.lock` local and untracked.
Retain exact resolutions for failure investigation and, when offered, tested release installation artifacts; a wheel does not consume a separate Pixi lock.

Use the [upstream-convergence skill](../../.agents/skills/upstream-convergence/SKILL.md) for recursive ecosystem source selection, moving Git dependencies, compatibility exceptions, and fresh-solve validation.
The [design charter](../project-design.md#design-principles) defines the strategy.
Development constraints belong visibly in `pixi.toml`; restrictions needed by installed packages must also reach published Python metadata. uv root overrides do not propagate from installed dependencies.

## Package development

```console
git submodule update --init --recursive
unset PIXI_LOCKED
pixi install
```

Commit manifests and gitlinks, not the development lock.
Python edits take effect directly; changed dependency declarations require resolution.
After schema or browser-interface edits, run `pixi run orinoco-lite dev prepare-resources`.

## Downstream development

From the downstream root, run `pixi run orinoco-lite dev enable`.
It creates `.orinoco-lite/orinoco-lite-dev`, initializes nested dependencies, prepares resources, and installs Python dependencies editable.
The checkout is locally excluded from Git; `pixi.toml` remains visibly modified.
Re-enabling preserves source edits.
Select a new checkout with `--repository` and `--revision`; change an existing checkout with Git.

[Upstream reproduction](../upstream-tracking.md) instead tracks this checkout as a downstream submodule and imports from its nested `www-from-model`.
Commit the gitlink and editable manifest selection for recovery.
Fixed builds use bundled rendering resources.

## Fixed package selection

```console
pixi run orinoco-lite package update --revision TAG_OR_COMMIT
pixi install --locked
```

The command records a fetchable full SHA in `pixi.toml` and refreshes the local lock.
Use `--repository` for a fork; a release is not required.
If the current environment cannot launch the command, prefix it with `env -u PIXI_LOCKED pixi run --as-is` instead of `pixi run`.

The [release workflow](../../.github/workflows/orinoco-release.yml) checks reproducible artifacts, dependency commits, and clean consumer installs.
Artifact upload and publication are separate steps.

# Dependency management

[`pyproject.toml`](../pyproject.toml) declares Python requirements in `[dependency-groups].runtime` and nested editable sources through `[tool.uv.sources]`.
The build backend derives `[project].dependencies` from those requirements and the committed gitlinks; revision pins are not maintained in a second list.
[`pixi.toml`](../pixi.toml) selects the package checkout, external tools, and engineering tools; the untracked development `pixi.lock` retains locally resolved versions.
`query-things` declares a normal client dependency; the package selects its editable source, so downstreams need no client override.
Git submodules record source revisions, while editable installations use working-tree edits.

## Dependency source conflicts

When a nested package requires a dependency through a hard-coded Git URL, first fix that declaration in the package that owns it.
Declare the package name and any necessary compatibility constraint; let the consuming project's source declarations select the checkout.
For example, the `query-things` fix replaces:

``` toml
"dump-things-pyclient @ git+https://hub.psychoinformatics.de/orinoco/dump-things-pyclient.git@master"
```

with `"dump-things-pyclient"` in `[project].dependencies`.
Orinoco Lite's existing `[tool.uv.sources]` then selects the editable client submodule.
No sibling source declaration in `query-things` or downstream Pixi override is needed.

Check why the original source was required before removing it; retain actual compatibility requirements.
Prefer this correction over copying overrides into each environment: uv's `override-dependencies` is scoped to the workspace root and does not propagate from an installed dependency.
If the declaring package cannot be corrected, document the reason for an environment override.

Commit dependency fixes and update their parent gitlinks before sharing them.

## Working on the project

``` console
git submodule update --init --recursive
unset PIXI_LOCKED
pixi install
pixi run orinoco-lite --help
```

Pixi resolves changed dependency declarations automatically.
Commit the manifests and submodule selections; keep the development lock local between runs.
Development CI resolves from the declarations rather than requiring a committed lock.

## Developing in a downstream

For ordinary local development, run `pixi run orinoco-lite dev enable` from the downstream root.
The command clones `.orinoco-lite/orinoco-lite-dev` locally, initializes the package's nested submodules, prepares resources, and installs its Python dependencies editable in the downstream environment.
The source checkout is excluded through Git's local `info/exclude`; enable does not register a downstream submodule, stage files, or require a commit.
`pixi.toml` remains a local modification visible in Git.
Development locks stay local and untracked; release CI generates and tests a locked consumer environment.

Upstream website reproduction always tracks `.orinoco-lite/orinoco-lite-dev` as a downstream Git submodule and installs it editable.
The default `setup-upstream` workflow registers and selects it before import; `dev enable` alone does not register a submodule.
Commit the package gitlink and editable manifest selection so another checkout can restore the selected source and its nested dependencies.
Site-input import uses that nested `www-from-model` checkout, including authored content and Annex media.
Ordinary downstream builds use the bundled rendering subset and require no upstream checkout.
See [upstream instantiation](upstream-tracking.md) for preparation and refresh.

Use `--repository` and `--revision` to select a candidate when creating the checkout; use Git inside an existing checkout to change revisions.
Re-running enable preserves uncommitted source edits.
Python code changes need no reinstall; changed dependency declarations require a new resolution.
Run `orinoco-lite dev prepare-resources` after editing schema or browser-interface sources.

## Package commits and release artifacts

Select a release tag or a full package commit from the downstream:

``` console
pixi run orinoco-lite package update --revision TAG_OR_COMMIT
pixi install --locked
```

`--repository` selects another HTTPS or SSH repository, including a fork.
The command resolves the revision to a fetchable full SHA, updates `pixi.toml`, and refreshes `pixi.lock`; the next install or `pixi run` uses it.
A release is not required.
If the current development environment cannot launch the command, use `env -u PIXI_LOCKED pixi run --as-is orinoco-lite package update --revision TAG_OR_COMMIT`.

Wheels declare exact Git requirements for the five Python source dependencies selected by the package commit's gitlinks and `.gitmodules`.
Source archives contain those resolved requirements in standard `[project].dependencies`, so rebuilding a wheel does not require the original Git checkout.
Editable source installs continue to use local paths through `[tool.uv.sources]`.
Git installs may represent nested dependencies as subdirectories of the selected package commit; that commit's gitlinks fix their source revisions.
Registry dependencies are resolved by the downstream lock, and Hugo remains a Pixi dependency.
Downstreams need no repeated Python source pins or overrides.

The [release workflow](../.github/workflows/orinoco-release.yml) checks reproducible artifacts, installed wheel dependency commits, and a clean Git-based consumer environment.
It uploads release candidates as Actions artifacts; publication to a package index or GitHub Release is a separate step.

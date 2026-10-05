# Dependency management

[`pixi.toml`](../pixi.toml) defines the software environment: Python packages from PyPI, and Python itself and external tools from Conda.
`pyproject.toml` contains packaging metadata and build requirements, with no runtime dependency list.
Git submodules are used to track the versions of Orinoco dependencies that we may have commits rebased onto.
Development uses these for editable installs.

## Working on the project
```console
git submodule update --init --recursive
export PIXI_LOCKED=true
pixi install --locked
pixi run orinoco-lite --help
```
After changing dependencies, run `env -u PIXI_LOCKED pixi lock`, then review and commit the manifest, lock, and any submodule changes together.

## Releases

The exact commits and git remote are injected during [releases](../.github/workflows/orinoco-release.yml).
Downstream users need no editable installations or software submodules.

Distribution of `www-from-model` software/assets and downstream submodule setup still need work; data import is deferred.

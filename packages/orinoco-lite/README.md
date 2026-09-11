# Orinoco Lite package

`orinoco-lite` contains the code and resources needed to validate an Orinoco Lite site, derive its published representations, and build the static website.
Code, resources, and every internal build specification share the package's version and integrity boundary.

Site maintainers normally use the tasks supplied by their template rather than individual package entry points:

```console
pixi install --frozen
pixi run validate
pixi run build
pixi run serve
```

Each downstream owns its metadata, editorial content, site configuration, site-specific source adapters, review policy, deployment, and upgrade timing.
It independently selects exact Orinoco Lite package and template versions.

## Package selection and integrity

The environment's package manager selects and installs `orinoco-lite`.
Downstreams using Pixi declare that dependency in `pixi.toml` and resolve it in `pixi.lock`.
The `orinoco-lite` executable uses the installed package without a second version lock or development-selection variables.

The package does not publish or consume a second resource artifact.
Any resource specification or manifest needed to build or operate Orinoco Lite is internal to the package and shares its version and integrity boundary.

## Development

From the engineering repository root:

```console
pixi install --locked
PYTHONPATH=packages/orinoco-lite/src \
  python -m unittest discover -s packages/orinoco-lite/tests -v
```

The release workflow builds the wheel and source archive reproducibly, installs the wheel in a clean environment, checks the packaged resources, and runs the package tests.
The package and original Orinoco Lite software are licensed under the [MIT License](LICENSE); bundled third-party license texts and notices remain authoritative for their files.

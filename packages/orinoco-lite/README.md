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

The `package` mapping in `orinoco.lock` records the exact `orinoco-lite` distribution version, immutable wheel URL, and SHA-256 digest.
Copier records the corresponding `package_version`, `package_url`, and `package_sha256` answers.
The frozen Pixi environment installs that wheel by its recorded hash, and Orinoco Lite rejects a lock that names a different package version.

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

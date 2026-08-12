# Orinoco Lite engine

This package provides the stable, location-independent command-line boundary for an Orinoco Lite downstream website.
It discovers a site through `orinoco.yaml`, validates the single-repository content contract, verifies a digest-pinned runtime release, and invokes only commands declared by that verified release.

The engineering workspace's submodules and upstream-rebase history are not part of this interface.
A downstream site needs only its visible content, `orinoco.yaml`, `orinoco.lock`, and the `orinoco` command.

The package metadata intentionally does not declare a project-wide license.
Release archives carry a machine-readable source inventory and every available component license.
A public package-index publication must not imply a license that the project has not selected.

The runtime release surface is pinned to the selected Things Schema source profile and its complete localized import closure.
It is content-neutral, but does not claim arbitrary-schema compatibility.

The immutable wheel URL and digest in `orinoco.lock` must also match the consumer's frozen `pixi.lock`.
Pixi verifies that archive during installation; the running engine then verifies its exact installed version and every runtime archive resource.
Placeholder digests are rejected by all engine commands.

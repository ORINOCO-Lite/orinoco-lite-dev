# Runtime license inventory

Orinoco Lite does not currently declare a repository-wide license.
This directory records licenses of redistributed runtime components and is included in every runtime archive.

The deterministic release assembly copies the exact component license texts listed in `runtime-source.yaml` from their pinned source checkouts.
Presence of those component licenses does not assign a license to otherwise unlicensed Orinoco Lite code or content.

The editor dependency inventory records every installed npm package, declared license, version, and all discovered license/notice files.
The localized LinkML schema directory contains only the pinned source YAML import closure; its inventory binds every original and localized digest.
Imports are rewritten to local relative paths solely to make release validation hermetic.

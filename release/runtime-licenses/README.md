# Bundled licenses and notices

Original Orinoco Lite software is MIT licensed.
This directory records its license and the licenses of redistributed components and is bundled in every released package.

The deterministic release assembly copies the exact component license texts listed in `package-resources.yaml` from their pinned source checkouts.
Component licenses apply only to their respective components; downstream metadata, editorial content, media, and presentation retain their own declared terms.

The editor and downstream source-review dependency inventories record every installed npm package, declared license, version, and all discovered license/notice files for their respective static shells.
The localized LinkML schema directory contains only the pinned source YAML import closure.
Imports are rewritten to local relative paths solely to make release validation hermetic.

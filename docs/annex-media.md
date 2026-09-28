# Optional Annex media

A downstream can store images and other media in Git Annex under its `site-specific` submodule’s `assets/` and `static/` directories.
Records, configuration, editorial content, and source-adapter outputs must remain ordinary Git files.
Directories without a submodule do not support this option.

Set the following in `orinoco.yaml`:

```yaml
media:
  annex: true
```

Install Git Annex in the downstream’s Pixi environment and commit the manifest and lock.
For the template’s supported platforms, the engineering environment uses these dependency selections:

```console
env -u PIXI_LOCKED pixi add --platform linux-64 'git-annex==10.20260601'
env -u PIXI_LOCKED pixi add --platform osx-arm64-macos-14-0 --pypi 'git-annex==10.20260601'
```

This executable is also required when DataLad saves ordinary Git records in an Annex-enabled submodule.
It does not change where those records are stored.
Use your preferred Annex content-placement policy; DataLad’s `text2git` procedure is a useful starting point.
Ensure that saves keep records and configuration in Git, for example with these submodule `.gitattributes` rules:

```gitattributes
metadata/** annex.largefiles=nothing
*.yaml annex.largefiles=nothing
*.yml annex.largefiles=nothing
```

Orinoco does not overwrite that policy and rejects Annex-managed files outside the media directories, including unlocked files.

Configure publicly readable storage using native Git Annex remotes.
Keep their configuration in the Annex repository so new clones can discover the content.
DataLad’s `siblings configure --as-common-datasrc` can register a public Git remote as a discoverable content source.
GIN is one tested storage service, not an Orinoco dependency.
The GitHub browser curation flow still uses a GitHub metadata repository; an Annex sibling supplies its media.
Private storage and build-time credential setup are outside this feature’s scope.

`orinoco-lite build` retrieves required media, verifies it with Annex, and copies regular files into the disposable Hugo assembly.
The tracked pointers, source branch, and parent gitlink remain unchanged.
Use `orinoco-lite prepare-media` to retrieve and verify media separately without building.
Unavailable content fails with its path rather than being omitted or published as a pointer.

Validation and metadata projection inspect Annex keys without downloading media.
The isolated publication checkout uses the original checkout as its local remote, so any required content can be reused locally.
A fresh-clone test must separately demonstrate retrieval from the public storage remote; local reuse alone does not prove remote availability.

The upstream site importer and maintainer Hugo-asset preparation use the same retrieval and verification operation.
Their existing file-selection and licensing rules remain in effect.

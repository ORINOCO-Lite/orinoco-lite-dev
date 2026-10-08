# Optional Annex media

A downstream can store images and other media in Git Annex under its `site-specific` submodule’s `assets/` and `static/` directories.
Records, configuration, editorial content, and source-adapter outputs must remain ordinary Git files.
Directories without a submodule do not support this option.

Set the following in `pyproject.toml`:

```toml
[tool.orinoco.media]
annex = true
```

The package includes Git Annex for required upstream Hugo assets.
The media opt-in additionally enables retrieval for the downstream’s own media.

This executable is also required when DataLad saves ordinary Git records in an Annex-enabled submodule.
It does not change where those records are stored.
Use your preferred Annex content-placement policy; DataLad’s `text2git` procedure is a useful starting point.
Ensure that saves keep records and configuration in Git, for example with these submodule `.gitattributes` rules:

```gitattributes
metadata/** annex.largefiles=nothing
*.yaml annex.largefiles=nothing
*.yml annex.largefiles=nothing
*.toml annex.largefiles=nothing
```

Orinoco does not overwrite that policy and rejects Annex-managed files outside the media directories, including unlocked files.

Configure publicly readable storage using native Git Annex remotes.
Keep their configuration in the Annex repository so new clones can discover the content.
DataLad’s `siblings configure --as-common-datasrc` can register a public Git remote as a discoverable content source.
The GitHub browser curation flow still uses a GitHub metadata repository; an Annex sibling supplies its media.
Private storage and build-time credential setup are outside this feature’s scope.

## Public aneksajo repository

Use a public repository on [DataLad Hub](https://hub.datalad.org/) as the media sibling.
Keep the browser-curated metadata repository on GitHub.
The hub advertises Annex’s HTTPS transfer protocol; maintainer Git pushes and Annex uploads use a repository read/write token through a local Git credential helper.
Create the token under Settings → Applications → Access Tokens, with the `repository` permission set to Read and Write.
Ensure the credential helper is available to the Git executable used by Annex as well as the Git executable used for pushes.
Do not put the token in remote URLs or build environments.

Create an empty public hub repository and set `ANEKSAJO_URL` to its HTTPS clone URL.
Publish the committed input branch and Annex state, then register its public URL for other clones:

```bash
git -C site-specific remote add hub "$ANEKSAJO_URL"
git -C site-specific push hub HEAD git-annex
pixi run git -C site-specific annex copy --to hub -- assets static
pixi run datalad siblings configure -d site-specific \
  --name hub --as-common-datasrc hub-storage
git -C site-specific fetch hub git-annex
pixi run git -C site-specific annex merge
git -C site-specific push hub HEAD git-annex
git -C site-specific push origin HEAD git-annex
```

The fetch and Annex merge incorporate location records written by the hub during upload before pushing the shared Annex branch.
Commit and push the parent’s updated gitlink through the usual downstream workflow.
The `hub-storage` configuration is recorded in the `git-annex` branch and automatically enabled in new clones.
Builds retrieve public content without the maintainer’s token.
Apply the same native sibling configuration directly to an upstream Annex repository for repinning and media import.

## Cloudflare R2

R2 is an optional alternative or additional copy.
Configuring it alongside the hub does not automatically synchronize their content; copy new media to each desired remote explicitly.

Create an R2 bucket and connect a public custom domain in Cloudflare.
The managed `r2.dev` URL can be used for an initial test, but Cloudflare rate-limits it and designates it for development.
Create an R2 API token with Object Read & Write access limited to that bucket.
On the maintainer’s machine, supply its S3 credentials as `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.
Never commit credentials or provide them to website builds.

From the downstream root, initialize the native Annex S3 remote:

```bash
pixi run git -C site-specific annex initremote r2 \
  type=S3 encryption=none embedcreds=no \
  bucket="$R2_BUCKET" \
  host="$R2_ACCOUNT_ID.r2.cloudflarestorage.com" \
  region=auto protocol=https signature=v4 requeststyle=path \
  publicurl="$R2_PUBLIC_URL" autoenable=true
pixi run git -C site-specific annex copy --to r2 -- assets static
git -C site-specific push origin HEAD git-annex
```

Set `R2_PUBLIC_URL` to the bucket’s public HTTPS base URL.
The `git-annex` branch records the remote configuration and content locations; push it alongside the branch containing the media pointers.
New clones use the public URL without S3 credentials.
For upstream repinning, configure the same native remote in the selected upstream Annex repository; the shared preparation operation uses it without a provider-specific setting in Orinoco.

See [Annex’s S3 remote](https://git-annex.branchable.com/special_remotes/S3/) and [R2 public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/).

## Builds

For Netlify’s cached, disposable build checkout, prefix the build command with `git -C site-specific config core.hooksPath /dev/null &&`.
Netlify checks out cached submodules before installing Pixi; Annex’s checkout hook otherwise calls an executable that is not yet available.
Keep normal hooks enabled in development checkouts.
If an earlier Netlify build already cached the hook, clear its build cache once when applying this setting.

`orinoco-lite build` retrieves required media, verifies it with Annex, and copies regular files into the disposable Hugo assembly.
The tracked pointers, source branch, and parent gitlink remain unchanged.
Use `orinoco-lite prepare-media` to retrieve and verify media separately without building.
Unavailable content fails with its path rather than being omitted or published as a pointer.

Validation and metadata projection inspect Annex keys without downloading media.
The isolated publication checkout uses the original checkout as its local remote, so any required content can be reused locally.
A fresh-clone test must separately demonstrate retrieval from the public storage remote; local reuse alone does not prove remote availability.

The upstream site importer and maintainer Hugo-asset preparation use the same retrieval and verification operation.
Their existing file-selection and licensing rules remain in effect.

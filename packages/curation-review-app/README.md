# Curation review application

This package implements the stateless browser and authentication surface in [`docs/github-curation-review.md`](../../docs/github-curation-review.md).
It reads a workflow-generated metadata proposal and ephemeral presentation artifact from GitHub, presents one complete set of record decisions, and posts that set as the authenticated user's pull-request comment.
It also implements the thin GitHub wrapper in [`docs/github-shacl-vue-edit.md`](../../docs/github-shacl-vue-edit.md): it verifies exact-head editor input, combines that data in browser memory with a released generic editor, and creates an explicit temporary Git handoff for trusted Python replacement.
It does not run adapters, convert metadata, apply decisions, or retain metadata, bundles, artifacts, or curation state.

## Local verification

Use the locked Node and npm versions declared in `.nvmrc` and `package.json`.

```shell
npm ci --ignore-scripts
npm run check
```

`npm run dev` serves the static browser application at `http://127.0.0.1:4173`.
A complete OAuth flow uses the Pages Functions runtime:

```shell
npm run build
npm run pages:dev
```

Copy `.dev.vars.example` to the untracked `.dev.vars` file before running the Functions locally.

## GitHub App configuration

Register a GitHub App with expiring user-to-server tokens enabled.
Leave **Request user authorization (OAuth) during installation** and Device Flow disabled; the application starts its own state- and PKCE-bound browser authorization flow.
Disable callback-URL wildcard matching and webhooks, configure the exact callback URL as `PUBLIC_ORIGIN/api/auth/callback`, install it only on selected repositories, and grant these repository permissions:

- Metadata: read (the GitHub-required baseline permission)
- Actions: read
- Contents: write
- Pull requests: write

Pull requests write posts authenticated decision comments and creates an explicit standalone draft proposal.
Contents write includes the read access needed by both profiles and is used for writes only to create the exact, fixed-path SHACL Vue handoff branch and commit requested by the curator.
The source-adapter decision path never writes repository contents through the service.
The service separately requires the signed-in user to have `write` or `admin` collaborator permission.

Configure these Pages runtime values:

| Name                             | Kind     | Purpose                                |
| -------------------------------- | -------- | -------------------------------------- |
| `PUBLIC_ORIGIN`                  | variable | Exact HTTPS deployment origin          |
| `GITHUB_CLIENT_ID`               | variable | GitHub App client ID                   |
| `EDITOR_RUNTIME_MANIFEST_SHA256` | variable | SHA-256 of the staged runtime manifest |
| `GITHUB_CLIENT_SECRET`           | secret   | OAuth code exchange                    |
| `SESSION_SEAL_KEY`               | secret   | Base64url-encoded 32-byte AES-GCM key  |

Do not configure KV, D1, R2, Durable Objects, queues, or analytics-backed curation storage.
OAuth state and the short-lived GitHub access token exist only in encrypted, host-only browser cookies.
Refresh tokens are discarded.

Before deploying the SHACL Vue path, stage the generic editor shell and Things schema from one immutable Orinoco Lite runtime release.
`tools/stage-editor-runtime.mjs` verifies the release's `runtime-manifest.json` digest and every selected file before placing those static resources in the application build.
Never stage editor executable code or schema from a downstream pull request or Actions artifact.

## Cloudflare Pages

The Pages build command is `npm run build` and the output directory is `dist`.
Pages Functions are under `functions/`; `npm run pages:functions:build` verifies their Worker bundle without publishing it.
The tracked Wrangler configuration is the deployment source of truth for the public GitHub App client ID and production origin.
Cloudflare stores the client secret and session-sealing key separately as encrypted Pages secrets.

The central `https://orinoco-curation-review.pages.dev/` deployment is the default hosted option, but `PUBLIC_ORIGIN` is configurable and downstreams select their review-application origin independently.
The origin is not embedded in a submission or PR-body machine protocol.

The SHACL Vue path reuses this same application deployment.
It does not add a separate Worker, browser or hosted metadata converter, database, object store, artifact cache, or persistent service.
Its canonical wrapper route is `/edit/`.
The downstream site's own `/edit/` route remains the credential-free SHACL Vue page with its normal **Download bundle** behavior; it is not the authenticated GitHub proposal wrapper.

A canonical review link has this form:

```text
https://review.example/review/?repository=owner/repository&pull_request=42&artifact_id=123456789
```

An exact link opens that proposal directly.
A repository-only entry link such as `https://review.example/?repository=owner/repository` preserves the site identity through authentication and then lists only that repository's relevant open curation pull requests and unexpired matching artifacts.
Discovery is a live, stateless convenience; opening a choice performs the complete authoritative proposal verification again.

The link selects one artifact by immutable GitHub artifact ID.
Its required name is `orinoco-curation-review-<proposal_sha>` and its ZIP contains exactly one regular top-level `review-bundle.json` using format `orinoco-lite-curation-review-bundle-v1`.
The service permits at most 8 MiB compressed, 16 MiB uncompressed, 225 candidate records, 450 changed metadata paths, and 16 MiB of loaded Git record text per review.
These are service-resource bounds, not pull-request Markdown or native-diff limits.
The complete authenticated decision comment remains subject to GitHub's comment-size constraint.

A successful maximum-size submission makes at most 47 outbound requests: one curator check, one pull-request read, one commit-list read, one artifact metadata read, one workflow-run read, one authenticated artifact redirect, one credential-free archive download, five commit-file pages, 34 batched GraphQL record reads, and one comment write.
This remains below the Cloudflare Free limit of 50 subrequests per invocation.
Oversized artifacts, candidate sets, and proposal paths are rejected before record blobs are loaded.

The pull-request body is only an accessible fallback and review link.
The application never parses it for candidate identity, ordering, source coordinates, or completeness.
It derives candidate membership and operations from the proposal commit metadata diff, verifies initial candidate identity from base and proposal blobs, presents current-head record data, and uses the expiring bundle only for presentation facts.

## Exact-head SHACL Vue input

The source-adapter decision artifact above remains the proposal's single `orinoco-curation-review-<proposal_sha>` artifact.
It is not reused as SHACL Vue input.

For every exact pull-request or current default-branch commit exposed for editing, a trusted default-branch workflow publishes exactly one `orinoco-shacl-vue-input-<source_sha>` artifact.
Its ZIP contains exactly three ordinary data files:

- `edit/config.json`;
- `edit/records.ttl`; and
- `edit/data/record-sources.json`.

The application uses Actions read access to verify that the artifact is unexpired, belongs to the selected repository and exact commit, and came from the successful reviewed workflow.
It rejects a stale catalog or head.
The browser combines the three files only in memory with the staged immutable editor shell and schema; neither the service nor the browser converts RDF to canonical YAML.
The artifact is reproducible presentation input, not canonical metadata, a generated version 2 bundle, provenance, or durable curation state.

After the released editor emits its unchanged version 2 bundle, **Propose via GitHub** requires an explicit acknowledgment that the bundle contains only public-approved data and no secrets.
The service then creates the fixed `.orinoco-lite/shacl-vue-review-bundle.json` handoff commit at the exact head.
Trusted default-branch Python validates and replaces that one commit with the equivalent attributed canonical YAML commit; the final branch contains no bundle.
Pull-request Markdown is not parsed to locate or validate either artifact.

Provisioning the Pages project, registering the GitHub App, setting secrets, and deploying are separately reviewed external operations.
This package does not perform them.

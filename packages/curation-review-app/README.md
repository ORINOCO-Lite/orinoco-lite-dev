# Curation review application

This package implements the stateless browser and authentication surface in [`docs/github-curation-review.md`](../../docs/github-curation-review.md).
It reads a workflow-generated metadata proposal and ephemeral presentation artifact from GitHub, presents one complete set of record decisions, and posts that set as the authenticated user's pull-request comment.
It does not run adapters, apply decisions, or retain metadata or curation state.

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

Register a GitHub App with user authorization and expiring user-to-server tokens enabled.
Configure its callback URL as `PUBLIC_ORIGIN/api/auth/callback`, install it only on selected repositories, and grant these repository permissions:

- Metadata: read (the GitHub-required baseline permission)
- Contents: read
- Actions: read
- Pull requests: write

The write permission is used only to create the authenticated pull-request comment.
The service separately requires the signed-in user to have `write` or `admin` collaborator permission.

Configure these Pages runtime values:

| Name                   | Kind     | Purpose                               |
| ---------------------- | -------- | ------------------------------------- |
| `PUBLIC_ORIGIN`        | variable | Exact HTTPS deployment origin         |
| `GITHUB_CLIENT_ID`     | variable | GitHub App client ID                  |
| `GITHUB_CLIENT_SECRET` | secret   | OAuth code exchange                   |
| `SESSION_SEAL_KEY`     | secret   | Base64url-encoded 32-byte AES-GCM key |

Do not configure KV, D1, R2, Durable Objects, queues, or analytics-backed curation storage.
OAuth state and the short-lived GitHub access token exist only in encrypted, host-only browser cookies.
Refresh tokens are discarded.

## Cloudflare Pages

The Pages build command is `npm run build` and the output directory is `dist`.
Pages Functions are under `functions/`; `npm run pages:functions:build` verifies their Worker bundle without publishing it.
The tracked Wrangler configuration is the deployment source of truth for the public GitHub App client ID and production origin.
Cloudflare stores the client secret and session-sealing key separately as encrypted Pages secrets.

The central `https://orinoco-curation-review.pages.dev/` deployment is the default hosted option, but `PUBLIC_ORIGIN` is configurable and downstreams select their review-application origin independently.
The origin is not embedded in a submission or PR-body machine protocol.

A review link has this form:

```text
https://review.example/?repository=owner/repository&pull_request=42&artifact_id=123456789
```

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

Provisioning the Pages project, registering the GitHub App, setting secrets, and deploying are separately reviewed external operations.
This package does not perform them.

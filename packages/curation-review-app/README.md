# Curation review application

This package implements the stateless browser and authentication surface in [`docs/github-curation-review.md`](../../docs/github-curation-review.md).
It reads a workflow-generated metadata proposal from GitHub, presents one complete set of record decisions, and posts that set as the authenticated user's pull- request comment.
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

A review link has this form:

```text
https://review.example/?repository=owner/repository&pull_request=42
```

The bounded initial deployment accepts at most 225 candidate records, 450 proposal files (one record and at most one mirrored annotation per candidate), and 16 MiB of record text per review.
The rendered pull-request summary and complete decision comment must also fit GitHub's 65,536-character text limit; the workflow and service reject an oversized rendering before publication.
A successful maximum-size submission makes at most 32 outbound GitHub requests: one curator check, one pull-request read, one commit-list read, five commit-file pages, 23 batched GraphQL record reads, and one comment write.
This remains below the Cloudflare Free limit of 50 subrequests per invocation.
Oversized candidate sets and proposal commits are rejected before record blobs are loaded.

Provisioning the Pages project, registering the GitHub App, setting secrets, and deploying are separately reviewed external operations.
This package does not perform them.

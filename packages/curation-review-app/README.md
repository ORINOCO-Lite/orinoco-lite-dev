# Curation review application

This package implements both halves of the browser boundary in [`docs/github-curation-review.md`](../../docs/github-curation-review.md).
Its content-neutral static build is released inside the Orinoco runtime and bound into each configured downstream at `/review/`.
Its central build provides only GitHub authentication, verified proposal reads, explicit final confirmation, and authenticated comment transport.
It also implements the thin GitHub handoff in [`docs/github-shacl-vue-edit.md`](../../docs/github-shacl-vue-edit.md): it authenticates a curator, receives the unchanged bundle from the downstream static editor or a selected downloaded file, and creates an explicit temporary Git handoff for trusted Python replacement.
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

`npm run build:review` independently produces the unconfigured downstream shell in `dist-review/`.
Release assembly inventories its dependencies and places it in the runtime; the engine then supplies a strict `config.json` from the downstream's `site.repository` and `site.curation_service`.

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

The central `https://orinoco-curation-review.pages.dev/` deployment is the default authentication and GitHub-transport option, but `PUBLIC_ORIGIN` is configurable.
It is not a source-adapter review destination.

The SHACL Vue path reuses this same application deployment.
It does not add a separate Worker, browser or hosted metadata converter, database, object store, artifact cache, or persistent service.
Its canonical wrapper route is `/edit/`.
That route is only a lightweight sign-in, in-memory receiver or file upload, public-data confirmation, and GitHub proposal surface.
It does not contain, frame, assemble, or host SHACL Vue.
The downstream site's own `/edit/` route is the sole editor and offers both **Download review bundle** and **Propose via GitHub** for the same unchanged result.

A canonical source-adapter review link belongs to the deployed downstream:

```text
https://owner.example/site/review/?repository=owner/repository&pull_request=42&artifact_id=123456789
```

That route renders the complete candidate review.
It opens the central `/review-transport/` route in a separate window; OAuth uses a nested window so the transport retains the exact downstream opener.

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

Before releasing proposal data, the central service verifies the downstream repository, base URL, and service origin from `orinoco.yaml` at the proposal's metadata base.
A sealed short-lived grant and an exact ready/request handshake bind the repository, pull request, artifact, downstream origin, popup, and one-time nonce.
The downstream keeps all decisions in browser memory.
When the complete decision set returns, the central origin displays every path and disposition and requires a final user click before posting.
Tokens and CSRF material never cross the browser-message channel.

The transport sends `post-started` before its authenticated request.
A typed result marks only a definite pre-write 4xx rejection as retry-safe; the static route may then reopen the transport without discarding decisions.
Network, 5xx, malformed-success, timeout, and unknown results remain locked and tell the curator to inspect the pull request before another action.
The retired `/api/discovery` and `/api/auth/discovery-start` routes return HTTP 410 and do not authenticate or contact GitHub.

## Static-editor SHACL Vue handoff

The source-adapter decision artifact above remains the proposal's single `orinoco-curation-review-<proposal_sha>` artifact and is not SHACL Vue input.
The published downstream site already contains the released editor shell, schema, exact-source catalog, and RDF required for its `/edit/` route; no second Actions artifact or hosted editor assembly exists.

The static page opens the service route and retains the bundle in its own browser memory while OAuth completes.
After authentication, the lightweight page signals readiness to that exact opener; the static page verifies the popup and service origin before posting the repository-bound bundle once.
The receiver accepts only the opener at a credential-free HTTPS origin (or loopback HTTP for development).
If navigation severed the opener relationship, the curator can select the identical downloaded JSON bundle instead.

After the service receives the unchanged version 2 bundle, **Propose via GitHub** requires an explicit acknowledgment that it contains only public-approved data and no secrets.
The service then creates the fixed `.orinoco-lite/shacl-vue-review-bundle.json` handoff commit at the exact head.
Trusted default-branch Python validates and replaces that one commit with the equivalent attributed canonical YAML commit; the final branch contains no bundle.
Pull-request Markdown is not parsed to locate or validate either artifact.

Provisioning the Pages project, registering the GitHub App, setting secrets, and deploying are separately reviewed external operations.
This package does not perform them.

# Curation review and GitHub transport

This package implements both halves of the browser boundary in [`docs/agents/contract/github-curation-review.md`](../../docs/agents/contract/github-curation-review.md).
Its content-neutral static review shell is bundled in the `orinoco-lite` package and bound into each configured downstream at `/review/`.
Its central deployment is backend-only: API handlers authenticate with the GitHub App, verify proposals, and perform authenticated GitHub transport.
The only service-origin browser document is a generated, restrictive-CSP `/api/transport` popup that retains the host-only session cookie and exchanges nonce-bound messages with its exact downstream opener.
It contains no landing, review, editor, upload, or confirmation application.

The package also implements the thin GitHub handoff in [`docs/agents/contract/github-shacl-vue-edit.md`](../../docs/agents/contract/github-shacl-vue-edit.md).
It authenticates a curator and creates an explicit temporary Git handoff for the exact bundle confirmed in the downstream editor.
It does not run adapters, convert metadata, apply decisions, or retain metadata, bundles, artifacts, or curation state.

## Fix GitHub authorization

The static `/edit/` page uses the **Orinoco Lite GitHub App** to sign you in and create a draft pull request in the configured repository containing only the changes you selected.
It does not host the editor, store your metadata, or keep your GitHub credentials in the site.

[Install the Orinoco Lite GitHub App](https://github.com/apps/orinoco-lite-curation-review/installations/new) for the repository, approve any organization or SSO request, and retry the submission.

If a site maintainer needs a separate app, they can [create a GitHub App](https://github.com/settings/apps/new), install it only on the target repository, and configure a compatible curation service with that app.
The required callback, permissions, and service settings are described below; ordinary editors should use the shared app installation above.

## Local verification

Use the locked Node and npm versions declared in `.nvmrc` and `package.json`.

```shell
npm ci --ignore-scripts
npm run check
```

The Pages Functions development runtime serves the backend-only deployment:

```shell
npm run pages:dev
```

Copy `.dev.vars.example` to the untracked `.dev.vars` file before running the Functions locally.

`npm run build:review` independently produces the unconfigured downstream shell in `dist-review/`.
Package assembly includes the shell and its dependencies; the trusted site build supplies the repository coordinate and the effective central-default or optional override service origin in strict `config.json`.

## GitHub App configuration

Register a GitHub App with expiring user-to-server tokens enabled.
Leave **Request user authorization (OAuth) during installation** and Device Flow disabled; the application starts its own state- and PKCE-bound browser authorization flow.
Disable callback-URL wildcard matching and webhooks, configure the exact callback URL as `PUBLIC_ORIGIN/api/auth/callback`, install it only on selected repositories, and grant these repository permissions:

- Metadata: read (the GitHub-required baseline permission)
- Actions: read
- Commit statuses: read
- Contents: write
- Pull requests: write

`Pull requests: write` supports authenticated decision comments and creation of an explicit standalone draft proposal.
Contents write includes the read access needed by both profiles and supports the exact, fixed-path SHACL Vue handoff requested by the curator and verified, proposal-bound workflow materialization.
Commit-status read access verifies an exact successful Netlify deploy preview before that preview may update its own draft pull request.
The source-adapter decision path never writes repository contents through the service.
The service separately requires the signed-in user to have `write` or `admin` collaborator permission.

If the editor reports a GitHub 401, 403, or 404, confirm that the App is installed for the target repository, approve any pending organization or SSO authorization, and sign in as a collaborator with `write` or `admin` permission.

Configure these Pages runtime values:

| Name                     | Kind     | Purpose                                                            |
| ------------------------ | -------- | ------------------------------------------------------------------ |
| `PUBLIC_ORIGIN`          | variable | Exact HTTPS deployment origin                                      |
| `GITHUB_CLIENT_ID`       | variable | GitHub App client ID                                               |
| `GITHUB_CLIENT_SECRET`   | secret   | OAuth code exchange                                                |
| `SESSION_SEAL_KEY`       | secret   | Base64url-encoded 32-byte AES-GCM key                              |
| `GITHUB_APP_PRIVATE_KEY` | secret   | RSA PKCS#8 PEM; required for coordinated submodule materialization |

Do not configure KV, D1, R2, Durable Objects, queues, or analytics-backed curation storage.
OAuth state and the short-lived GitHub access token exist only in encrypted, host-only browser cookies.
Refresh tokens are discarded.

## Cloudflare Pages Functions

The Pages output directory is `service-dist/` and contains only routing configuration; it has no static presentation assets.
Its manifest sends the exact root and `/api/*` to Functions.
The root Function returns an empty, hardened, non-cacheable `404` so a superseded Pages asset cannot reappear from static hosting or cache, while every other non-API presentation path remains outside the Functions deployment.
Pages Functions are under `functions/`; `npm run pages:functions:build` verifies their Worker bundle without publishing it.
The tracked Wrangler configuration is the deployment source of truth for the public GitHub App client ID and production origin.
Cloudflare stores the client secret, session-sealing key, and optional App signing key separately as encrypted Pages secrets.

The central `https://orinoco-curation-review.pages.dev/` deployment is the default authentication and GitHub-transport option, but `PUBLIC_ORIGIN` is configurable.
It is not a source-adapter review destination.

The SHACL Vue path reuses the same backend deployment.
It does not add a separate Worker, hosted metadata converter, database, object store, artifact cache, or persistent service.
The downstream site's own `/edit/` route is the sole editor and offers both **Download bundle** and **Propose via GitHub** for the same unchanged result.
Bundle memory, downloaded-file reselection, proposal confirmation, and the shared-`github.io` warning all remain in that downstream route.

A canonical source-adapter review link belongs to the deployed downstream:

```text
https://owner.example/site/review/?repository=owner/repository&pull_request=42&artifact_id=123456789
```

That route renders the complete candidate review and final confirmation.
It opens `/api/transport` in a popup that binds the exact opener, downstream origin, repository, operation, and one-time nonce while OAuth completes.

The link selects one artifact by immutable GitHub artifact ID.
Its required name is `orinoco-curation-review-<proposal_sha>` and its ZIP contains exactly one regular top-level `review-bundle.json` using format `orinoco-lite-curation-review-bundle-v1`.
The service permits at most 8 MiB compressed, 16 MiB uncompressed, 225 candidate records, 450 changed metadata paths, and 16 MiB of loaded Git record text per review.
These are service-resource bounds, not pull-request Markdown or native-diff limits.
The complete authenticated decision comment remains subject to GitHub's comment-size constraint.

A successful maximum-size submission makes at most 48 outbound requests: one curator check, one pull-request read, one commit-list read, one artifact metadata read, one workflow-run read, one configured-site read, one authenticated artifact redirect, one credential-free archive download, five commit-file pages, 34 batched GraphQL record reads, and one comment write.
This remains below the Cloudflare Free limit of 50 subrequests per invocation.
Oversized artifacts, candidate sets, and proposal paths are rejected before record blobs are loaded.

The pull-request body is only an accessible fallback and review link.
The application never parses it for candidate identity, ordering, source coordinates, or completeness.
It derives candidate membership and operations from the proposal commit metadata diff, verifies initial candidate identity from base and proposal blobs, presents current-head record data, and uses the expiring bundle only for presentation facts.

Before releasing proposal data, the central service verifies the requested repository against the live GitHub objects and verifies the downstream base URL and effective default or override service origin from `orinoco.yaml` at the proposal's metadata base.
A sealed short-lived grant and an exact ready/request handshake bind the repository, pull request, artifact, downstream origin, popup, and one-time nonce.
The downstream keeps all decisions in browser memory.
The downstream displays every path and disposition and requires the final user click before instructing the popup to post.
Tokens and CSRF material never cross the browser-message channel.

The transport sends `post-started` before its authenticated request.
A typed result marks only a definite pre-write 4xx rejection as retry-safe; the static route may then reopen the transport without discarding decisions.
Network, 5xx, malformed-success, timeout, and unknown results remain locked and tell the curator to inspect the pull request before another action.
The retired `/api/discovery` and `/api/auth/discovery-start` routes return HTTP 410 and do not authenticate or contact GitHub.

## Static-editor SHACL Vue handoff

The source-adapter decision artifact above remains the proposal's single `orinoco-curation-review-<proposal_sha>` artifact and is not SHACL Vue input.
The published downstream site already contains the released editor shell, schema, exact-source catalog, and RDF required for its `/edit/` route; no second Actions artifact or hosted editor assembly exists.

The static page opens `/api/transport` and retains the bundle in its own browser memory while OAuth completes.
After authentication, the popup signals readiness to that exact opener; the static page verifies the popup and service origin before posting the repository-bound proposal once.
The transport accepts only an exact credential-free HTTPS opener origin (or loopback HTTP for development).
If navigation severs the opener relationship, the curator can select the identical downloaded JSON bundle again on the downstream `/edit/` route and start a fresh handoff.

The downstream submission drawer shows the repository and selected records before **Propose via GitHub**.
That click authorizes one proposal; the popup submits through the verified channel after authentication without a second confirmation.
The service then creates the fixed `.orinoco-lite/shacl-vue-review-bundle.json` handoff commit at the exact head.
Trusted default-branch Python validates and replaces that one commit with the equivalent attributed canonical YAML commit; the final branch contains no bundle.
New pull requests have no curator-attributed explanatory body; the trusted workflow posts the concise waiting status as `github-actions[bot]`.
Pull-request Markdown is not parsed to locate or validate either artifact.

Provisioning the Pages project, registering the GitHub App, setting secrets, and deploying are separately reviewed external operations.
This package does not perform them.

## Coordinated submodule materialization

Install the same curation App on the website and metadata repositories.
The curator needs write access in both; downstreams need no second App or App private key.
The service operator configures `GITHUB_APP_PRIVATE_KEY` once per hosted service, not per downstream installation.
It is an ongoing runtime signing credential, distinct from the OAuth client secret; the same App serves all its authorized installations.
A deployment that supports only ordinary-directory handoffs and source-adapter review does not need this key.

For an independent service, register your own GitHub App with the settings above, configure its client ID, client secret, session-sealing key, and exact service origin, and install that App on the selected repositories.
Set the downstream's `site.curation_service` to your service's HTTPS origin.
Do not obtain or share the central service's private key.

Reuse an existing signing key held securely by the service operator when available.
Otherwise, use **Generate a private key** in that App's GitHub settings and protect the downloaded PEM file.
A displayed fingerprint is not the private key, and a client secret cannot replace it.
Validate the file before uploading it:

```sh
openssl rsa -in /secure/path/app-private-key.pem -check -noout
```

For Cloudflare, after successful validation, convert GitHub's downloaded key to PKCS#8 and pass it directly to encrypted secret storage without printing it.
Replace `YOUR_PAGES_PROJECT` with your own service project:

```sh
openssl pkcs8 -topk8 -nocrypt -in /secure/path/app-private-key.pem |
  npx wrangler pages secret put GITHUB_APP_PRIVATE_KEY --project-name YOUR_PAGES_PROJECT
```

Deploy the service after configuring its secrets, verify authenticated operation, and remove temporary local key copies or retain them only in an approved secret store.
Never commit the key or supply it to downstream repositories.

Restrict operator access, protect the downloaded key, and revoke superseded GitHub keys after verifying a replacement.
A sign-only vault is preferable where supported; this implementation uses the hosting provider's encrypted secret binding and imports the signing key as non-extractable Web Crypto key material.
It does not copy the key to Actions or a browser.

An authenticated submission signs a one-hour authorization into the temporary website handoff.
This contains no access token or private key and disappears with that handoff.
`POST /api/shacl/workflow-access` requires a GitHub-signed OIDC identity addressed to that exact endpoint.
It checks the immutable repositories and curator, exact trusted workflow revision, active run, both current draft heads, source gitlink, and unchanged bundles.
Only the original `pull_request_target` run can obtain write access, after GitHub reports successful materialization and validation steps in that job.
The canonical follow-up may obtain read access only, using the original handoff coordinate and matching composed replacement commits.
Expired authorization requires a fresh authenticated proposal; retries cannot retarget an existing grant.

The service issues a repository-limited installation token for trusted automation, never to the browser.
Read access and write access are separate, and the workflow revokes both tokens on completion.
GitHub tokens cannot restrict paths or branches; the exact authorized workflow enforces metadata-only changes and Git leases.
The token's residual exposure is the metadata repository for its remaining lifetime (at most GitHub's one-hour expiry if cleanup cannot run).
The backend's private key has broader App-wide impact and requires operator protection and rotation.
This is an explicit automation delegation, not a fallback around failed user authentication.
See the [authentication contract](../../docs/agents/contract/curation-service-authentication-options.md#app-credentials-and-automated-completion).

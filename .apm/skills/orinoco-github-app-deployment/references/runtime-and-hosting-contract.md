# Application and hosting contract

Use this checklist to evaluate any provider.
Product names are examples of implementation environments, not requirements.

## Immutable input and build

Select and record:

- one clean reviewed application commit and tree; and
- the provider's immutable deployment identifier or image digest.

Use the Node and npm versions declared by the package.
From `packages/curation-review-app/`:

```console
npm ci --ignore-scripts
npm run check
```

`npm run check` formats, tests, type-checks, builds `dist/`, and verifies the Pages Functions bundle.
Deploy `dist/`, `functions/`, the tracked route and header files, and public configuration together from the same clean revision.
Uploading `dist/` without the Functions adapter is not a backend deployment.

Also run `npm run build:review` and verify the unconfigured `dist-review/` shell.
That shell belongs in the immutable Orinoco runtime and downstream static build; do not deploy it as a second central review page.

The service does not consume an Orinoco Lite runtime archive.
Do not stage SHACL Vue, a Things schema, downstream record input, an editor-input Actions artifact, `/editor-runtime/` assets, or a runtime-manifest digest.
The immutable editor shell and schema belong in each downstream's static site build, which is the only SHACL Vue editor.

## Required configuration

| Name | Exposure | Contract |
| --- | --- | --- |
| `PUBLIC_ORIGIN` | Public | Exact production HTTPS origin; no path, trailing slash, query, or fragment. Only loopback development may use HTTP. |
| `GITHUB_CLIENT_ID` | Public | Client ID of the configured GitHub App. |
| `GITHUB_CLIENT_SECRET` | Secret | GitHub OAuth code exchange secret. |
| `SESSION_SEAL_KEY` | Secret | Base64url encoding of exactly 32 random bytes. |

Generate `SESSION_SEAL_KEY` with a cryptographically secure random source.
Avoid commands that print it into captured logs; send it directly to the provider's secret input.
No App private key, webhook secret, installation token, runtime digest, database credential, or storage binding is required.

Each downstream that enables the SHACL proposal handoff separately declares:

- `site.repository`, the exact GitHub `owner/repository`; and
- `site.curation_service`, the credential-free HTTPS receiver origin.

Both are required for **Propose via GitHub**.
They are downstream site configuration, not service secrets, OAuth state, or a substitute for the App's selected-repository installation.
The same pair enables the downstream's static source-review shell.
Its `site.base_url` owns the canonical `review/` route, while `site.curation_service` names only this transport service.

## Provider capability gate

The deployment environment must provide all of these:

- one public HTTPS origin for the browser application and API routes;
- static asset serving plus the checked Functions or equivalent adapter;
- Fetch-compatible `Request`, `Response`, headers, streaming bodies, and URL behavior;
- Web Crypto AES-GCM, SHA-256, and secure random generation;
- preservation of multiple `Set-Cookie` headers on one response;
- outbound HTTPS to `github.com`, `api.github.com`, and GitHub's approved artifact-storage redirect hosts;
- manual redirect handling without forwarding the bearer token to artifact storage;
- atomic deployment and an immutable rollback coordinate;
- encrypted secret storage separate from build artifacts and public variables;
- log redaction and no caching of authenticated pages or API responses; and
- the request, response, CPU, memory, duration, subrequest, and payload capacity described below.

The current source uses `functions/api/**` and Pages `EventContext`.
On another provider, implement a thin hosting adapter that maps its router and static-asset behavior to those handlers while preserving Fetch and Web Crypto semantics.
Keep protocol and authorization code unchanged and exercise the adapter in the same test suite.

`npm run check` compiles and tests the checked Pages Functions bundle; it does not validate an adapter for another host.
A non-Pages adapter must add a tracked build and focused tests for route dispatch, middleware wrapping, external URL reconstruction, byte-preserved duplicate cookies, streaming and manual redirects, and static asset serving.

A reverse proxy must preserve the externally visible scheme and authority in `Request.url`.
Rewriting production requests to an internal HTTP origin breaks origin validation and secure host-only cookies unless the adapter reconstructs the exact external URL through a reviewed, trusted-proxy boundary.

## Routes and response policy

| Route | Required behavior |
| --- | --- |
| `/` | Serve a service-status and handoff landing page with no candidate-review UI. |
| `/review/`, `/review` | Redirect to `/`; the central service is not a source-review destination. |
| `/review-transport/` | Serve the exact downstream-opener-bound OAuth, verified-read, confirmation, and comment transport. |
| `/review-auth-complete/` | Serve only the lightweight OAuth-completion window. |
| `/edit/` | Serve only the lightweight sign-in, unchanged-bundle receiver or file selector, confirmation, and proposal UI. |
| `/edit` | Redirect once to the slash form. |
| `/api/*` | Route to the stateless Functions handlers. |

The service must not register `/api/shacl/editor`, serve `/editor-runtime/`, or render, frame, or assemble SHACL Vue at `/edit/`.

The exact API paths and accepted methods are:

| Accepted method and route | Source handler |
| --- | --- |
| `GET /api/auth/callback` | `functions/api/auth/callback.ts` |
| `GET /api/auth/shacl-start` | `functions/api/auth/shacl-start.ts` |
| `GET /api/auth/start` | `functions/api/auth/start.ts` |
| `POST /api/logout` | `functions/api/logout.ts` |
| `GET /api/proposal` | `functions/api/proposal.ts` |
| `GET /api/session` | `functions/api/session.ts` |
| `POST /api/shacl/propose` | `functions/api/shacl/propose.ts` |
| `POST /api/submit` | `functions/api/submit.ts` |

Keep `GET /api/discovery` and `GET /api/auth/discovery-start` registered only as compatibility tombstones.
Both must return HTTP 410 `review_discovery_retired` without creating OAuth state, reading a session, or contacting GitHub.
They must direct users to the deployed downstream `/review/` route rather than reconstructing a central discovery interface.

Wrap every dispatched handler with `functions/api/_middleware.ts`; its `context.next()` must invoke the selected handler.
Calling handlers directly loses standardized exception responses and the API security and `no-store` headers.

Register each exact path for all methods, then let the handler's `requireMethod` reject unsupported methods through the middleware.
A router that registers only the accepted method may emit its own unsecured 404 or 405 and bypass the application's standardized response contract.

Reproduce the checked static and API response headers: content security policy, `nosniff`, referrer policy, permissions policy, and the required cache policy.
Authenticated HTML and every API response are `no-store`.
Do not let a CDN cache a response containing a token-bearing or OAuth-state cookie.

The browser and API must stay same-origin.
Cookies use the `__Host-` prefix, `HttpOnly`, `Secure`, `SameSite=Lax`, and `Path=/`.
OAuth state expires after ten minutes; a session is capped at eight hours.
The callback clears the OAuth cookie and sets the session cookie in the same response, so an adapter that folds duplicate `Set-Cookie` fields is incompatible.
Test the adapter's emitted HTTP response at byte or header-list level as well as through the browser runtime; two cookies represented as one comma-joined field are not equivalent.

## Static source-review transport boundary

The downstream static `review/` route generates a fresh 256-bit nonce and opens `/review-transport/` with its exact repository, pull-request, artifact, and origin coordinates.
OAuth uses a separate window so the transport retains the downstream opener.
The sealed session grant binds all coordinates.

Before sending proposal data, the backend reads `orinoco.yaml` at the verified proposal metadata base, requires the declared repository and central service, and derives the exact downstream `site.base_url` plus `review/`.
The transport and downstream complete a typed ready/request handshake and require exact window, origin, nonce, repository, pull request, and artifact matches.
Never send a token or CSRF value through browser messaging and never use `*` as a message target.

The downstream returns one complete in-memory submission.
The central origin must display the login, repository, pull request, proposal and head commits, and every path and disposition.
Only a user click there may post the GitHub comment.
Reject duplicate, replayed, framed, timed-out, or mismatched channels.
Send `post-started` before the authenticated request and classify every result as retry-safe or potentially uncertain.
A downstream may reconnect while preserving decisions only for an explicitly retry-safe pre-write rejection.
It must keep the submission locked and tell the curator to inspect the pull request when a network, server, or malformed-success response could conceal a completed comment.
Because browser messaging authenticates an origin rather than a path, a shared Pages hostname is an origin-wide boundary; the explicit central confirmation is mandatory, and unique downstream origins remain preferable when isolation is required.

## Static-editor handoff boundary

The static site opens `/edit/` with its repository, exact editor origin, and a cryptographically random one-time nonce.
The bundle remains in the static editor's memory through OAuth.
The editor sends it only after the exact popup at `site.curation_service` signals readiness with the matching repository and nonce.
The receiver accepts it only from the exact opener at the declared HTTPS editor origin with the same repository and nonce.

The URL and OAuth state must not contain the bundle.
Neither side may use cross-origin browser storage as bundle recovery state.
If navigation or browser policy severs the opener relationship, the curator may select the identical downloaded JSON bundle on `/edit/`.
Both transports must receive the same format, size, repository, source-commit, exact-head, curator-authorization, and public-data acknowledgment checks.

## Capacity floor

Evaluate limits against the accepted maximum operation, not a trivial sample:

- at least 47 outbound subrequests for one maximum source-adapter review submission;
- an 8 MiB compressed and 16 MiB uncompressed source-adapter review artifact;
- 16 MiB of loaded Git record text;
- 225 candidates and 450 changed metadata paths;
- a SHACL proposal request body carrying a 10 MiB bundle plus its bounded JSON envelope;
- at most 50 SHACL bundle records; and
- streaming GitHub artifact responses.

There is no hosted editor-HTML or base64-inlined editor-input capacity requirement.
If a provider cannot meet these floors, choose a different plan or explicitly revise the product contract through its normal review process; do not deploy an undocumented smaller service.

## Statelessness and egress

GitHub commits, pull requests, comments, workflow runs, and expiring source-adapter Actions artifacts are the only durable authority.
OAuth state and the short-lived user token exist only in encrypted browser cookies; refresh tokens are discarded.
The received SHACL bundle exists only in browser memory and the explicit request, then temporarily in the fixed-path Git handoff until trusted replacement removes it from the branch.

Artifact download intentionally observes one GitHub redirect, verifies the destination against the approved GitHub and Azure storage-host allowlist, and then downloads without the bearer token.
A platform that automatically follows, rewrites, signs, or proxies this redirect can defeat the security boundary and must be adapted or rejected.

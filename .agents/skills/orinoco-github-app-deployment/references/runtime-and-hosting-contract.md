# Application and hosting contract

Use this checklist to evaluate any provider.
Product names are examples of implementation environments, not requirements.

## Input and build

Deploy from one clean reviewed Git revision.
Use Git and provider deployment history for recovery instead of recording a second coordinate inventory.

Use the Node and npm versions declared by the package.
From `packages/curation-review-app/`:

```console
npm ci --ignore-scripts
npm run check
```

`npm run check` formats, tests, type-checks, and verifies the checked backend and provider adapter.
Deploy its API handlers, generated protocol response, route and header policy, and public configuration together from the same clean revision.
Do not deploy `dist/`, a review shell, a landing page, or other static presentation assets with the service.

The source-review shell is bundled in the `orinoco-lite` package and included in each downstream static build.
Verify it through the release and downstream checks, not by deploying it as a second central review page.

Do not stage SHACL Vue, a Things schema, downstream record input, or an editor-input Actions artifact in the service.
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
No App private key, webhook secret, installation token, database credential, or storage binding is required.

The trusted downstream build derives the exact GitHub `owner/repository` from `GITHUB_REPOSITORY` or its equivalent general project identity and emits it into the generated `/edit/` and `/review/` configuration.
Repository identity is not a separate curation setting.

`site.curation_service` is optional.
When absent, the released integration uses the Orinoco Lite central-service origin.
When present, it is the credential-free HTTPS origin of a compatible independently hosted backend, with no path, query, fragment, or credentials.
It is not a service secret, OAuth state, or a substitute for the App's selected-repository installation.
The site's `site.base_url` owns the canonical `edit/` and `review/` routes.
The service independently verifies every browser coordinate against GitHub, the App installation, trusted repository content, and the exact operation.

## Provider capability gate

The deployment environment must provide all of these:

- one public HTTPS origin for API routes and the minimal generated OAuth callback/transport response;
- a checked Worker, Functions, or equivalent backend adapter with no static presentation deployment;
- Fetch-compatible `Request`, `Response`, headers, streaming bodies, and URL behavior;
- Web Crypto AES-GCM, SHA-256, and secure random generation;
- preservation of multiple `Set-Cookie` headers on one response;
- outbound HTTPS to `github.com`, `api.github.com`, and GitHub's approved artifact-storage redirect hosts;
- manual redirect handling without forwarding the bearer token to artifact storage;
- atomic deployment and a way to redeploy a checked Git revision or select a prior production deployment;
- encrypted secret storage separate from build artifacts and public variables;
- log redaction and no caching of authenticated pages or API responses; and
- the request, response, CPU, memory, duration, subrequest, and payload capacity described below.

The current source uses Fetch-compatible API handlers.
On another provider, implement a thin hosting adapter that maps its router to those handlers while preserving Fetch and Web Crypto semantics.
Keep protocol and authorization code unchanged and exercise the adapter in the same test suite.

`npm run check` compiles and tests the checked backend adapter; it does not validate an adapter for another host.
A different adapter must add a tracked build and focused tests for route dispatch, middleware wrapping, external URL reconstruction, byte-preserved duplicate cookies, streaming, manual redirects, and generated protocol responses.

A reverse proxy must preserve the externally visible scheme and authority in `Request.url`.
Rewriting production requests to an internal HTTP origin breaks origin validation and secure host-only cookies unless the adapter reconstructs the exact external URL through a reviewed, trusted-proxy boundary.

## Routes and response policy

| Route | Required behavior |
| --- | --- |
| `/` | Return a small `404` or `410`; do not serve a landing page. |
| `/review/`, `/review`, `/review-transport/`, `/review-auth-complete/` | Return a small `404` or compatibility `410`; do not redirect to or render a central review or confirmation surface. |
| `/edit/`, `/edit` | Return a small `404` or compatibility `410`; do not render a receiver, file selector, confirmation, or editor. |
| `/api/*` | Route to the stateless Functions handlers. |

The service must not register `/api/shacl/editor` or render, frame, or assemble SHACL Vue at `/edit/`.

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

Reproduce the checked API and generated-protocol response headers: content security policy, `nosniff`, referrer policy, permissions policy, and the required cache policy.
Generated authenticated HTML and every API response are `no-store`.
Do not let a CDN cache a response containing a token-bearing or OAuth-state cookie.
Every popup navigation and redirect in the successful OAuth chain must explicitly use `Cross-Origin-Opener-Policy: unsafe-none`; a generic `same-origin` value on even an intermediate 302 permanently severs the downstream opener in Chromium.

The browser and API must stay same-origin.
Cookies use the `__Host-` prefix, `HttpOnly`, `Secure`, `SameSite=Lax`, and `Path=/`.
OAuth state expires after ten minutes; a session grant is capped at one hour and is consumed after a successful write.
The callback clears the OAuth cookie and sets the session cookie in the same response, so an adapter that folds duplicate `Set-Cookie` fields is incompatible.
Test the adapter's emitted HTTP response at byte or header-list level as well as through the browser runtime; two cookies represented as one comma-joined field are not equivalent.

## Static source-review transport boundary

The downstream static `review/` route generates a fresh 256-bit nonce and opens the backend authorization route in a popup with its exact repository, pull-request, artifact, operation, and origin coordinates.
OAuth remains in the popup, so the main browser and all review state remain on the downstream route.
The sealed session grant binds all coordinates.

Before sending proposal data, the backend reads `orinoco.yaml` at the verified proposal metadata base, derives the trusted repository from the GitHub objects, resolves the central-service default or verifies an explicit `site.curation_service` override, and derives the exact downstream `site.base_url` plus `review/`.
The minimal generated callback/transport response and downstream complete a typed ready/request handshake and require exact opener window, origin, operation, nonce, repository, pull request, and artifact matches.
Never send a token or CSRF value through browser messaging and never use `*` as a message target.

The downstream displays the authenticated login, repository, pull request, proposal and head commits, and every path and disposition, then returns one complete in-memory submission only after the user's confirmation there.
The popup performs the authenticated request and closes; the service does not render a confirmation page.
Reject duplicate, replayed, framed, timed-out, or mismatched channels.
Send `post-started` before the authenticated request and classify every result as retry-safe or potentially uncertain.
A downstream may reconnect while preserving decisions only for an explicitly retry-safe pre-write rejection.
It must keep the submission locked and tell the curator to inspect the pull request when a network, server, or malformed-success response could conceal a completed comment.

Detect the actual downstream browser origin.
When it is on a shared `github.io` hostname, explain that the entire origin is one browser principal and link to custom-domain remediation.
A custom or otherwise unique origin receives the normal flow.

## Static-editor handoff boundary

The static site opens the backend SHACL authorization route with its repository, operation, exact editor origin, and a cryptographically random one-time nonce.
The bundle remains in the static editor's memory through OAuth.
The editor sends it only after the exact popup at the effective service origin signals readiness with the matching repository, operation, and nonce.
The backend transport accepts it only from the exact opener at the declared HTTPS editor origin with the same coordinates.
The backend independently reads `orinoco.yaml` at the trusted base commit before a SHACL write and requires its `site.base_url` editor origin and effective curation-service origin to match the sealed grant and current deployment.
Successful writes consume the relevant grant; standalone SHACL branches are deterministic for the source commit and handoff nonce so GitHub ref creation rejects a concurrent replay.

The URL and OAuth state must not contain the bundle.
Neither side may use cross-origin browser storage as bundle recovery state.
If navigation or browser policy severs the opener relationship, the curator may select the identical downloaded JSON bundle on the downstream `/edit/` route and begin a new popup session.
Both transports must receive the same format, size, repository, source-commit, exact-head, and curator-authorization checks.

On a shared `github.io` origin, keep **Download bundle** enabled without GitHub authorization and keep the warning informational rather than gating **Propose via GitHub**.
The downstream's **Propose via GitHub** click is the final authorization for that one proposal; do not add another confirmation after authentication.
When the editor is framed, refuse direct GitHub proposal at both the visible controls and the client helper while leaving **Download bundle** available.

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

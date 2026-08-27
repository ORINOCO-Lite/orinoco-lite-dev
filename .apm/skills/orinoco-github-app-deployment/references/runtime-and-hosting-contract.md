# Runtime and hosting contract

Use this checklist to evaluate any provider.
Product names are examples of implementation environments, not requirements.

## Immutable inputs and build

Select and record:

- one clean reviewed application commit and tree;
- one immutable Orinoco Lite runtime release archive and its archive digest;
- the release's exact `runtime-manifest.json` SHA-256; and
- the provider's immutable deployment identifier or image digest.

Use the Node and npm versions declared by the package.
From `packages/curation-review-app/`:

```console
npm ci --ignore-scripts
npm run check
npm run build
node tools/stage-editor-runtime.mjs \
  /path/to/verified/extracted-runtime \
  "$EDITOR_RUNTIME_MANIFEST_SHA256"
```

`npm run build` does not stage the editor.
The staging command validates the manifest digest, file digests, sizes, modes, paths, and absence of symlinks, then writes `dist/editor-runtime/<manifest-digest>/`.
Extract archives into a temporary location outside the repository and verify the release archive before staging it.
The released archive has one top-level `orinoco-runtime/` directory; pass that inner directory—the one containing `runtime-manifest.json`—to the staging command, not its extraction parent.

A concrete staging sequence is:

1. Download the archive from the exact release-asset URL into a new temporary directory.
2. Verify its bytes against the recorded archive SHA-256 before extraction.
3. Inspect the archive paths and reject absolute paths, `..` traversal, symlinks, or additional top-level roots.
4. Extract it into that temporary directory.
5. Run the staging command with `<temporary>/orinoco-runtime` and the recorded manifest SHA-256.
6. Retain the JSON staging report as evidence, then move the temporary input to trash or remove it through an explicitly validated temporary path.

Deploy code, public values, `dist/`, the Functions adapter, and the staged runtime together.
A deployment with a new digest but old runtime directory—or the reverse—must fail rather than fall back.

## Required configuration

| Name | Exposure | Contract |
| --- | --- | --- |
| `PUBLIC_ORIGIN` | Public | Exact production HTTPS origin; no path, trailing slash, query, or fragment. Only loopback development may use HTTP. |
| `GITHUB_CLIENT_ID` | Public | Client ID of the configured GitHub App. |
| `EDITOR_RUNTIME_MANIFEST_SHA256` | Public | Lowercase SHA-256 of the staged runtime manifest. |
| `GITHUB_CLIENT_SECRET` | Secret | GitHub OAuth code exchange secret. |
| `SESSION_SEAL_KEY` | Secret | Base64url encoding of exactly 32 random bytes. |

Generate `SESSION_SEAL_KEY` with a cryptographically secure random source.
Avoid commands that print it into captured logs; send it directly to the provider's secret input.
No App private key, webhook secret, installation token, database credential, or storage binding is required.

## Provider capability gate

The deployment environment must provide all of these:

- one public HTTPS origin for static pages, API routes, and staged assets;
- Fetch-compatible `Request`, `Response`, headers, streaming bodies, and URL behavior;
- Web Crypto AES-GCM, SHA-256, and secure random generation;
- preservation of multiple `Set-Cookie` headers on one response;
- outbound HTTPS to `github.com`, `api.github.com`, and GitHub's approved artifact-storage redirect hosts;
- manual redirect handling without forwarding the bearer token to artifact storage;
- an asset lookup equivalent to `ASSETS.fetch` for same-origin staged files;
- atomic deployment and an immutable rollback coordinate;
- encrypted secret storage separate from build artifacts and public variables;
- log redaction and no caching of authenticated pages or API responses; and
- the request, response, CPU, memory, duration, subrequest, and payload capacity described below.

The current source uses `functions/api/**`, Pages `EventContext`, and `env.ASSETS`.
On another provider, implement a thin hosting adapter that maps its router and static-asset API to those handlers while preserving Fetch/Web Crypto semantics. Keep protocol and authorization code unchanged. Exercise the adapter in the same test suite. Do not claim that uploading `dist/` alone deploys the application.

`npm run check` compiles and tests the checked Pages Functions bundle; it does not validate an adapter for another host.
A non-Pages adapter must add a tracked build and focused tests for route dispatch, middleware wrapping, external URL reconstruction, byte-preserved duplicate cookies, streaming/manual redirects, and the static-asset binding.

A reverse proxy must preserve the externally visible scheme and authority in `Request.url`.
Rewriting production requests to an internal HTTP origin breaks origin validation and secure host-only cookies unless the adapter reconstructs the exact external URL through a reviewed, trusted-proxy boundary.

## Routes and response policy

| Route | Required behavior |
| --- | --- |
| `/` | Serve the browser application. |
| `/review/` | Serve source-adapter review UI. |
| `/edit/` | Serve authenticated SHACL Vue wrapper. |
| `/review`, `/edit` | Redirect once to the slash form. |
| `/api/*` | Route to the stateless Functions handlers. |
| `/editor-runtime/<digest>/*` | Serve only files staged for the configured digest. |

The exact API paths and accepted methods are:

| Accepted method and route | Source handler |
| --- | --- |
| `GET /api/auth/callback` | `functions/api/auth/callback.ts` |
| `GET /api/auth/discovery-start` | `functions/api/auth/discovery-start.ts` |
| `GET /api/auth/shacl-start` | `functions/api/auth/shacl-start.ts` |
| `GET /api/auth/start` | `functions/api/auth/start.ts` |
| `GET /api/discovery` | `functions/api/discovery.ts` |
| `POST /api/logout` | `functions/api/logout.ts` |
| `GET /api/proposal` | `functions/api/proposal.ts` |
| `GET /api/session` | `functions/api/session.ts` |
| `GET /api/shacl/editor` | `functions/api/shacl/editor.ts` |
| `POST /api/shacl/propose` | `functions/api/shacl/propose.ts` |
| `POST /api/submit` | `functions/api/submit.ts` |

Wrap every dispatched handler with `functions/api/_middleware.ts`; its `context.next()` must invoke the selected handler.
Calling handlers directly loses standardized exception responses and the API security and `no-store` headers.
Preserve the editor HTML exception exactly because that response has its own stricter header construction.

Register each exact path for all methods, then let the handler's `requireMethod` reject unsupported methods through the middleware.
A router that registers only the accepted method may emit its own unsecured 404 or 405 and bypass the application's standardized response contract.

Reproduce the checked static and API response headers: content security policy, `nosniff`, referrer policy, permissions policy, and the required cache policy.
Authenticated HTML and every API response are `no-store`.
Do not let a CDN cache a response containing a token-bearing or OAuth-state cookie.

The browser and API must stay same-origin.
Cookies use the `__Host-` prefix, `HttpOnly`, `Secure`, `SameSite=Lax`, and `Path=/`.
OAuth state expires after ten minutes; a session is capped at eight hours.
The callback clears the OAuth cookie and sets the session cookie in the same response, so an adapter that folds duplicate `Set-Cookie` fields is incompatible.
Test the adapter's emitted HTTP response at byte/header-list level as well as through the browser runtime; two cookies represented as one comma-joined field are not equivalent.

## Capacity floor

Evaluate limits against the accepted maximum operation, not a trivial sample:

- at least 47 outbound subrequests for one maximum review submission;
- an 8 MiB compressed and 16 MiB uncompressed review artifact;
- 16 MiB of loaded Git record text;
- 225 candidates and 450 changed metadata paths;
- a SHACL proposal request body slightly above 10 MiB;
- streaming artifact responses; and
- enough memory and response capacity for editor HTML with base64-inlined input.
At the accepted 16 MiB input bound this can exceed 20 MiB.

The final editor-response estimate is derived from base64 expansion and should be measured on the selected adapter.
If a provider cannot meet these floors, choose a different plan or explicitly revise the product contract through its normal review process; do not deploy an undocumented smaller service.

## Statelessness and egress

GitHub commits, pull requests, comments, workflow runs, and expiring Actions artifacts are the only durable authority.
OAuth state and the short-lived user token exist only in encrypted browser cookies; refresh tokens are discarded.

Artifact download intentionally observes one GitHub redirect, verifies the destination against the approved GitHub/Azure storage-host allowlist, and then downloads without the bearer token.
A platform that automatically follows, rewrites, signs, or proxies this redirect can defeat the security boundary and must be adapted or rejected.

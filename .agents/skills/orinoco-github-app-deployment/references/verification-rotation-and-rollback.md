# Verification, rotation, and rollback

Verify in increasing order of authority.
Record response codes and immutable coordinates, but do not record cookies, OAuth codes, access tokens, client secrets, or the session-seal key.

## Deployment verification

### 1. Build and configuration

- Confirm the checkout is clean and at the reviewed application commit and tree.
- Re-run `npm ci --ignore-scripts` and `npm run check` using the declared tools.
- Confirm the deployment contains the checked Worker, Functions, or equivalent backend adapter and no static presentation application or assets.
- Confirm exactly the two public values `PUBLIC_ORIGIN` and `GITHUB_CLIENT_ID` and the two encrypted secrets `GITHUB_CLIENT_SECRET` and `SESSION_SEAL_KEY` are available.
- Confirm `EDITOR_RUNTIME_MANIFEST_SHA256`, staged editor files, editor-input artifacts, and durable storage bindings are absent.
- Confirm there is no token, cookie, or received-bundle logging.
- Confirm the deployment has an immutable identifier and a known successful production rollback target.

The backend has no runtime release or manifest coordinate.
The downstream static-site release remains responsible for its immutable editor shell, schema, and exact-source inputs.

### 2. Anonymous, non-mutating probes

- `/`, `/review`, `/review/`, `/review-transport/`, `/review-auth-complete/`, `/edit`, and `/edit/` return a small `404` or compatibility `410` and never render or redirect to a landing, review, receiver, upload, confirmation, or editor page.
- `/api/shacl/editor` is not registered and no `/editor-runtime/` tree serves an editor shell or schema.
- `/api/session` returns HTTP 200 with `authenticated: false` while anonymous.
- `/api/discovery` and `/api/auth/discovery-start` return HTTP 410 `review_discovery_retired` without a GitHub request or OAuth-state cookie.
- A callback probe with exactly `code=probe`, `state=probe`, and `iss=https://github.com/login/oauth`, but no OAuth-state cookie, returns HTTP 401 `missing_oauth_state` before any token exchange.
An `iss`-only probe is malformed and correctly returns HTTP 400 `invalid_oauth_callback`.
- Authorization starts with a 302 to GitHub containing the exact client ID, callback, state, and PKCE challenge, no OAuth scope, and `Cross-Origin-Opener-Policy: unsafe-none`.
- A successful callback uses the same opener-preserving policy and redirects to the minimal generated popup-transport protocol response, which has its restrictive CSP and no product presentation.
- Security and `no-store` response headers are present, and the callback adapter emits two distinct `Set-Cookie` fields in the actual wire or header-list representation, not one comma-joined field.

Do not add a green root page as a health probe.
Use the API and OAuth-state probes to establish backend behavior.

### 3. Authenticated read-only browser proof

Use one selected integration repository and complete a real sign-in.
Without submitting a review or proposing a handoff, verify:

- the session identifies the expected user;
- the popup retains its exact downstream opener across the outbound GitHub authorization and return redirects in a real browser;
- the downstream's deployed `/review/` route loads its build-derived repository and effective default or override service origin and opens only the exact backend popup;
- after the ready/request handshake, a source-adapter proposal renders in that downstream page after exact artifact, metadata-base configuration, and head verification;
- the downstream route shows the complete submission summary and the popup does not post without the explicit final click there;
- retry-safe pre-write failures permit a new transport handoff without losing downstream decisions, while uncertain post-started failures keep submission locked and require pull-request inspection;
- downstream `/edit/` is the only editor and file-reselection surface and contains its exact-commit shell, schema, RDF catalog, and record inputs;
- the static editor exposes both **Download bundle** and **Propose via GitHub**;
- opening **Propose via GitHub** carries only the expected operation, repository, exact static-editor origin, and one-time nonce, and the popup's readiness message is bound to the exact two windows, origins, operation, repository, and nonce;
- focused origin-policy tests classify the actual browser origin, including terminal-dot spelling, and cover both the normal custom- or unique-origin flow and the shared-`github.io` flow;
- on the exercised downstream, a shared `github.io` origin explains its origin-wide trust boundary and requires a fresh in-memory acknowledgment before either direct GitHub write action becomes usable, without writing local storage, a cookie, service state, or tracked configuration, while a custom or otherwise unique origin omits that additional warning;
- **Download bundle** remains usable on a shared origin without the origin acknowledgment, GitHub sign-in, or a reachable service, and the separate public-history acknowledgment still appears before a SHACL Git write;
- a framed editor refuses direct GitHub proposal while **Download bundle** remains usable; and
- logout clears the session.

Do not send a SHACL bundle or confirm a source-review submission during this read-only proof.
Also verify that a read-only user or uninstalled repository is rejected when such a safe fixture is available.

### 4. Explicitly authorized write proof

Only after separate authorization, use a disposable or designated integration repository to test the source-adapter comment and/or fixed-path SHACL handoff.
Record the exact test repository, static source commit, pull request, head, artifact when applicable, written refs, and cleanup.
Verify trusted replacement and absence of the temporary bundle from the final branch.
Verify that a successful write consumes its session grant, the standalone SHACL ref is deterministic for the source and nonce, and an ordinary sequential replay cannot produce another write.
Never use the real production site as a write fixture.

## Downstream custom-domain guide

Treat domain verification, repository Pages configuration, DNS changes, and HTTPS enablement as separate external mutations.
Resolve their exact target before changing them and do not use the real site unless the user explicitly includes it.

For an authorized downstream:

1. Verify the intended domain for the repository owner's GitHub account or organization before publishing it, following GitHub's [domain-verification guidance](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/verifying-your-custom-domain-for-github-pages).
2. Configure that exact domain for the downstream Pages site using GitHub's current [custom-domain procedure](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site).
Follow the current provider-displayed DNS targets; do not copy historical IP addresses from logs or documentation.
3. Wait for GitHub's domain and certificate checks, then enable and verify HTTPS using its [HTTPS guidance](https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https).
4. Confirm that the origin of `site.base_url`, the generated editor and review configuration, and the actual `window.location.origin` all identify the final HTTPS custom origin with no unexpected redirect back to `github.io`.
5. Load `/edit/` and `/review/` from the final deployment, confirm the normal low-friction flow has no shared-origin acknowledgment, and complete the read-only OAuth proof before authorizing a write proof.

If the custom domain is unavailable or not yet verified, retain the ordinary `github.io` deployment and its explicit in-memory acknowledgment gate.
Do not disable **Download bundle** while domain work is pending.

## Failure guide

| Symptom | Likely causes |
| --- | --- |
| `github_oauth_error` with the safe client-credentials message | Host and GitHub client secrets do not match, or the wrong App client ID is deployed. The raw GitHub error is intentionally not exposed. |
| `missing_oauth_state` after login | Cookie lost through origin or proxy behavior, folded `Set-Cookie`, wrong callback origin, or ten-minute expiry. |
| `invalid_oauth_callback` | Wrong callback or setup URL, stale application revision, duplicate or foreign fields, or unexpected issuer. |
| Popup never becomes ready | Popup or opener was lost, browser policy intervened, or downstream origin, service origin, operation, repository, window identity, or nonce does not match. Keep the identical downloaded bundle and reselect it on downstream `/edit/` before starting a fresh popup rather than weakening the checks. |
| Bundle is rejected | Wrong format or keys, more than 50 records, over 10 MiB, invalid record coordinates, repository mismatch, source commit mismatch, stale head, or missing public-data acknowledgment. |
| GitHub 403/404 | App not installed, permission approval pending, user lacks write or admin, or session token expired. |
| Artifact failure | Egress blocked, redirect auto-followed or rewritten, destination host rejected, or provider size limit exceeded. This applies to the source-adapter review artifact, not SHACL editor input. |
| Downstream UI works but APIs 404 | The Worker, Functions, or provider backend adapter is absent or routed incorrectly. |
| A central landing, source-review, receiver, upload, confirmation, second editor, or `/editor-runtime/` surface is available | A superseded application revision or stale static build directory was deployed. Rebuild from the reviewed backend-only revision and remove static presentation assets. |

Both the successful OAuth callback and logout emit two cookies in one response.
Exercise both paths when validating an adapter's header behavior.

## Rotation

### Client secret

1. Create a second, overlapping GitHub client secret.
2. Update the hosting secret without exposing it.
3. Deploy and complete a real OAuth flow.
4. Only after proof, delete the old GitHub secret.

Do not delete the working secret first.
After deletion, a rollback that still expects it cannot authenticate.

### Session seal key

Only one seal key is supported.
Rotation immediately invalidates every OAuth state and session cookie.
Schedule a forced sign-in, replace the secret, deploy, and repeat the OAuth proof.
Never attempt to preserve or decrypt old cookies.

### Origin

Coordinate TLS or provider routing, `PUBLIC_ORIGIN`, GitHub callbacks, the released central-service default, and only those downstreams with an explicit `site.curation_service` override.
Existing cookies are origin-bound; require a fresh sign-in.
During a migration, temporarily retain the old exact callback and add the new exact callback with wildcard matching disabled.
Deploy and verify the new origin read-only, update the released default and any explicit downstream overrides that should move, disable writes through the old origin, then remove the old callback.
Never replace the only working callback before the new flow is proven or leave both origins write-capable through an ambiguous cutover.

### GitHub App ownership or permissions

After transfer, confirm the owner, App ID, public client ID, callback, expiring token option, permissions, and selected installations.
Permission increases may remain pending until an installation owner approves them.
Repeat authenticated verification even when the client ID and secret were retained.

## Rollback and evidence

Treat these as one backend rollback unit:

- application commit and tree plus hosting adapter;
- public values;
- route and header configuration; and
- compatible secret generation.

Retain the prior immutable successful production deployment until the new deployment has passed authenticated verification.
For Cloudflare Pages or Workers, rollback only to the previously verified production deployment through the provider's rollback control or deployment API; a preview is not a valid target.
Read back the target's captured source revision, clean-trigger state, backend adapter presence, and public and secret configuration-key inventory before relying on it.

A historical rollback target may contain the superseded hosted editor and its runtime-digest variable.
That can be a valid emergency backend rollback, but record explicitly that it temporarily restores the duplicate-editor behavior and do not use its old configuration as the template for the next deployment.

Record:

- timestamp and operator or agent attribution;
- application commit, tree, and clean-state proof;
- public origin and client ID;
- App ID, owner, permissions, and selected repositories;
- each exercised downstream's build-derived repository, `site.base_url`, effective central default or explicit `site.curation_service`, exact static source commit, deployed `/edit/` and `/review/` coordinates, and origin-policy verification result;
- immutable deployment ID and URL, provider runtime class, source trigger, clean-trigger flag, backend-adapter presence, and configuration-key inventory with secret values redacted;
- build and probe results, including absence of every hosted presentation route and static asset;
- authorized write-test coordinates, if any; and
- rollback deployment ID and URL plus rotation and duplicate-editor consequences.

Do not record a runtime release, archive digest, manifest digest, or staging report as backend evidence because the transport-only service consumes none.
Keep those coordinates with the downstream static-site release evidence.

Never record secret values, OAuth codes, cookies, access or refresh tokens, or raw provider logs that contain them.
Historical deployments may be useful examples, but they are not defaults or substitutes for current evidence.

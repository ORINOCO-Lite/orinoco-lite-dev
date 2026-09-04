---
name: orinoco-github-app-deployment
description: Deploy, migrate, verify, rotate, or roll back the stateless Orinoco Lite curation-review GitHub App backend on any suitable hosting provider. Use for self-hosting the review and edit-handoff service, evaluating a provider, configuring its GitHub App and secrets, or moving an existing deployment. Do not use merely to point a downstream at the existing central service.
---

# Orinoco Github App Deployment

Deploy the stateless Orinoco Lite GitHub App authorization and verified transport backend.
Keep the hosting choice separate from the application contract and keep every human-facing interface, warning, file selector, and authorizing action in the downstream static site: source review at `/review/` and SHACL Vue at `/edit/`.

## Workflow

1. Decide whether a new deployment is necessary.
   Prefer the central service when the downstream does not require its own origin, GitHub App, or custody.
2. Resolve the exact reviewed application commit and tree.
   Refuse a mutable branch or dirty checkout as production authority.
   The backend provides authentication and verified GitHub transport; the `orinoco-lite` package supplies the static editor, schema, and review shell to downstream builds.
3. Read [runtime-and-hosting-contract.md](references/runtime-and-hosting-contract.md) and compare every required capability with the proposed provider before provisioning it.
   The checked implementation is Fetch- and Web-Crypto-shaped; a provider may need a thin, reviewed Worker or Functions adapter.
   Do not deploy a static application or presentation assets.
   If the request is only to evaluate a provider, return the completed capability matrix and unresolved gaps here; do not create an App, secrets, hosting resources, or a deployment.
4. Read [github-app-configuration.md](references/github-app-configuration.md), then create or update the GitHub App and restrict its installation to the intended repositories.
   Keep the setup URL distinct from the OAuth callback.
5. Build and check the backend and its provider adapter from the clean reviewed revision.
   Deploy only the checked API handlers, minimal generated OAuth callback/transport response, and provider routing and headers.
6. Put public values in reviewed provider configuration, tracked when the provider supports configuration-as-code.
   Put secrets only in the encrypted hosting control plane.
   Never put secret values in Git, command output, logs, evidence, or browser-visible configuration.
   Do not add durable storage.
   Keep provider-operator login separate from curator GitHub authorization as explained in the [authentication options](../../../docs/agents/contract/curation-service-authentication-options.md).
   For Cloudflare, prefer direct Cloudflare account authentication for an interactive operator and a narrowly scoped API token for CI.
   Cloudflare's GitHub social login is an optional operator choice that uses the primary GitHub email; the Orinoco GitHub App neither needs nor requests account email access.
7. Deploy atomically from the clean reviewed revision.
   Use Git and the hosting provider's deployment history for recovery; do not create a separate deployment ledger or coordinate inventory.
8. Follow [verification-rotation-and-rollback.md](references/verification-rotation-and-rollback.md): run non-mutating probes first, then a real authenticated read-only browser flow.
   Require explicit authorization before any comment, branch, commit, or pull-request write, and use only a disposable or designated integration repository for that proof.
9. Only after the deployment and App installation pass verification, set `site.curation_service` in a downstream when it should override the released central default.
   Do not add a curation-specific repository setting; verify that the trusted build derives repository identity from its general project coordinate.
10. Guide downstream maintainers through the custom-domain and shared-origin checks in [verification-rotation-and-rollback.md](references/verification-rotation-and-rollback.md).
    A custom or otherwise unique origin receives the normal flow; shared `github.io` deployments show the warning and remediation link without gating direct submission, while **Download bundle** remains credential-free.
11. Report the deployed public origin, selected GitHub App repositories, and verification outcome.
    Do not create a separate evidence manifest; Git, reviewed configuration, the provider, and GitHub remain the sources of current and historical state.

## Guardrails

- GitHub is the durable authority.
  Do not introduce a database, object store, artifact cache, queue, candidate store, decision store, metadata service, or analytics-backed curation storage.
- Preserve the exact external HTTPS service origin in every backend request.
  The minimal generated protocol response, APIs, and cookies must share that origin; product presentation remains on the downstream origin.
- Do not weaken PKCE, OAuth state, expiring-token, cookie, redirect-host, exact-head, artifact, unchanged-bundle, or handoff origin/window/nonce checks to fit a provider.
- Do not host a landing page, source-adapter decision interface, receiver, upload fallback, confirmation page, or any static presentation assets.
  Do not assemble, embed, proxy, or host SHACL Vue, its schema, or its record inputs in this service.
  The downstream static site owns both interfaces and sends only its bounded, unchanged version 2 bundle through the verified request path.
- Treat secret rotation, an origin change, a GitHub App ownership transfer, installation changes, and write-path verification as distinct external mutations.
  Resolve exact targets and obtain any required confirmation at the point of action.
- Stop when provider limits cannot satisfy the accepted maxima or its adapter cannot preserve the response, cookie, redirect, and crypto semantics.
  Report the incompatible capability instead of silently reducing the contract.

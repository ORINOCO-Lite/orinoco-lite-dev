---
name: orinoco-github-app-deployment
description: Deploy, migrate, verify, rotate, or roll back the stateless Orinoco Lite curation-review GitHub App backend on any suitable hosting provider. Use for self-hosting the review and edit-handoff service, evaluating a provider, configuring its GitHub App and secrets, moving an existing deployment, or recording deployment evidence. Do not use merely to point a downstream at the existing central service.
---

# Orinoco Github App Deployment

Deploy the lightweight SHACL bundle receiver, source-review transport, and authorization routes as one stateless, same-origin service.
Keep the hosting choice separate from the application contract and keep both human-facing interfaces in the downstream static site: source review at `/review/` and SHACL Vue at `/edit/`.

## Workflow

1. Decide whether a new deployment is necessary.
Prefer the central service when the downstream does not require its own origin, GitHub App, or custody.
2. Resolve the exact reviewed application commit and tree.
Refuse a mutable branch or dirty checkout as production authority.
The backend consumes no Orinoco Lite runtime release: do not stage an editor, schema, editor-input artifact, runtime manifest, or runtime digest.
3. Read [runtime-and-hosting-contract.md](references/runtime-and-hosting-contract.md) and compare every required capability with the proposed provider before provisioning it.
The checked implementation is Pages-Functions-shaped; another provider needs a thin, reviewed adapter.
Static `dist/` alone is not a backend deployment.
If the request is only to evaluate a provider, return the completed capability matrix and unresolved gaps here; do not create an App, secrets, hosting resources, or a deployment.
4. Read [github-app-configuration.md](references/github-app-configuration.md), then create or update the GitHub App and restrict its installation to the intended repositories.
Keep the setup URL distinct from the OAuth callback.
5. Build and check the service browser application, downstream review shell, and Functions from the clean reviewed revision.
Deploy `dist/` and the Functions adapter together; static `dist/` alone is not a backend deployment.
6. Put public values in reviewed provider configuration, tracked when the provider supports configuration-as-code.
Put secrets only in the encrypted hosting control plane.
Never put secret values in Git, command output, logs, evidence, or browser-visible configuration.
Do not add durable storage.
7. Deploy atomically from the clean reviewed revision.
Record an immutable deployment identifier and a previously working rollback coordinate.
8. Follow [verification-rotation-and-rollback.md](references/verification-rotation-and-rollback.md): run non-mutating probes first, then a real authenticated read-only browser flow.
Require explicit authorization before any comment, branch, commit, or pull-request write, and use only a disposable or designated integration repository for that proof.
9. Only after the deployment and App installation pass verification, configure each downstream's exact `site.repository` and credential-free `site.curation_service` origin.
10. Record evidence without secrets: application commit/tree and clean state, public origin and client ID, App ID/owner and permission set, selected repositories, deployment ID, probe results, configuration-key inventory with secret values redacted, and rollback coordinate.

## Guardrails

- GitHub is the durable authority.
Do not introduce a database, object store, artifact cache, queue, candidate store, decision store, metadata service, or analytics-backed curation storage.
- Preserve the exact external HTTPS origin in every request.
Browser pages, APIs, and cookies must share that origin.
- Do not weaken PKCE, OAuth state, expiring-token, cookie, redirect-host, exact-head, artifact, unchanged-bundle, or handoff origin/window/nonce checks to fit a provider.
- Do not host the source-adapter decision interface or assemble, embed, proxy, or host SHACL Vue, its schema, or its record inputs in this service.
The downstream static site owns both interfaces; the SHACL receiver accepts only its bounded, unchanged version 2 bundle.
- Treat secret rotation, an origin change, a GitHub App ownership transfer, installation changes, and write-path verification as distinct external mutations.
Resolve exact targets and obtain any required confirmation at the point of action.
- Stop when provider limits cannot satisfy the accepted maxima or its adapter cannot preserve the response, cookie, redirect, and crypto semantics.
Report the incompatible capability instead of silently reducing the contract.

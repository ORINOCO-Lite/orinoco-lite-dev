# Milestone 3 GitHub Pages preview

Status: implementation complete; draft human review open

Target repository: `con/orinoco-lite-dev`

Target project URL: `https://con.github.io/orinoco-lite-dev/`

## Outcome

Milestone 3 publishes the accepted CON static artifact as a GitHub Pages project site.
The deployment remains backend-free: the public website and the optional editor are ordinary files, no Dump Things process runs after the build, and no browser receives a service credential or GitHub token.

This document is a new successor contract.
It does not rewrite the accepted Milestone 1 or Milestone 2 records.
The user's Milestone 3 authorization supersedes their former local-only boundary only for the parent branch, reachable submodule pins, a draft parent pull request, and the Pages preview.
It does not authorize DNS, a custom domain, production cutover, hosted write credentials, or pull requests in component repositories.

## Artifact contract

`pixi run build-pages` builds the CON profile, not the German upstream snapshot.
It uses the exact locked Pixi environment and recursive gitlinks, hydrates only manifest-declared assets through credential-free read-only HTTPS sources, and emits:

```text
build/pages-preview/orinoco-lite-dev/
  .nojekyll
  index.html
  graph.js
  graph.json
  edit/
    index.html
    config.json
    editor-contract.json
    record-sources.json
  publication.json
  ...
```

The Hugo base URL and graph, navigation, asset, and edit links all use `/orinoco-lite-dev/`.
The generated site points edit links at `/orinoco-lite-dev/edit/`; loopback URLs and the German editor URL are rejected from the uploaded artifact.

`pixi run verify-pages` compiles the pinned SHACL Vue editor twice independently, requires those bundles to be byte-identical, then creates the complete Pages artifact twice and requires byte-identical file manifests.
`pixi run audit-pages` checks an existing artifact without rebuilding it.
`pixi run serve-pages` provides a local project-path preview at `http://127.0.0.1:8766/orinoco-lite-dev/`; that local origin is never embedded in the public files.

## Static editing handoff

The Pages builder requires a deterministic editor produced at `build/pages-editor`.
The bundle must contain `index.html`, `config.json`, and an `editor-contract.json` with these claims:

```json
{
  "authentication": "none",
  "backend": "none",
  "mode": "patch-download",
  "version": 1
}
```

The parent copies the bundle under `edit/` and supplies `record-sources.json`.
The editor's `config.json` must also set `use_service` and `use_token` to `false`, `review_bundle_mode` to `patch-download`, and `review_bundle_catalog` to the relative `record-sources.json` path.
That catalog contains the exact public canonical YAML, its site-repository-relative path and digest, and the immutable site commit.
It is enough for a browser-only editor to generate a reviewable patch without an API call.
It intentionally excludes service endpoints, access tokens, automatic pushes, and automatic pull-request creation.

A downloaded patch changes paths in the `centerforopenneuroscience.org` repository because that repository currently owns canonical YAML.
The parent repository contains only its gitlink.
A future one-click contribution flow therefore needs an explicit decision about the public contribution target and the subsequent parent-gitlink update.
The current milestone does not disguise that two-repository review boundary.

## Actions security boundary

`.github/workflows/con-pages-preview.yml` has separate build and deployment jobs:

| Event | Build and upload artifact | Deploy shared Pages site |
| --- | --- | --- |
| Pull request to `main` | Yes | No |
| Push to `codex/milestone-3` | Yes | Yes, for the initial human-review preview |
| Push to `main` | Yes | Yes |
| Manual dispatch | Yes | Only when the `deploy` input is selected |

The workflow gives pull-request code only `contents: read`.
The deployment job is structurally excluded from pull-request events and alone receives short-lived `pages: write` and OIDC permissions.
Checkout does not preserve credentials.
Every action is pinned to a full commit ID, Pixi itself is pinned to `0.73.0`, and the repository lock is mandatory.

The Pages environment is a single shared preview, not a separate URL for each pull request.
Deployments are serialized and a newer deployment cancels an older one.
The temporary `codex/milestone-3` push trigger makes the draft pull request reviewable before merge; remove that trigger after deciding that `main` is the only publication branch.

## Reachability and publication sequence

GitHub Actions can check out only commits reachable from the configured public submodule URLs.
Publishing the parent branch therefore has this order:

1. Run complete local Milestone 3 acceptance and freeze the site gitlink.
2. Push the exact site and any changed nested component commits to their configured read-only checkout repositories.
No component pull request is required by this milestone.
3. Confirm a disposable HTTPS recursive checkout resolves every gitlink.
4. Configure `con/orinoco-lite-dev` Pages to use GitHub Actions.
5. Push `codex/milestone-3` in `con/orinoco-lite-dev` and open one draft pull request to `main`.
6. Let that branch push publish the shared preview and record its workflow run and deployed URL in the Milestone 3 acceptance report.

Pages is configured for GitHub Actions and the public preview is available at `https://con.github.io/orinoco-lite-dev/`.
The `github-pages` environment admits `main` and the temporary `codex/milestone-3` review branch.
The temporary branch policy and workflow trigger are review scaffolding, not a production branch policy.

## Acceptance

Publication is acceptable when all of the following hold:

- the recursive HTTPS clone resolves the exact parent, site, theme, schema, projection, graph, editor, and asset pins;
- `test-pages` passes and two Pages builds are byte-identical;
- the artifact contains no symlinks, Git state, credentials, local URLs, German editor URL, or persistent-service dependency;
- homepage, people, projects, publications, graph resources, branding, and representative assets work under `/orinoco-lite-dev/`;
- the editor loads its static shapes and source record through the project path and downloads a patch that applies cleanly at the pinned site commit;
- pull-request execution cannot enter the deployment job;
- one branch deployment succeeds and its public result receives a human content review; and
- no listener, incoming edit, temporary annex remote, or token remains after local and browser acceptance.

## Human decisions and clarifications

These decisions are deliberately surfaced rather than hidden in deployment code:

1. **Patch contribution repository.** Choose whether downloaded patches and eventual component pull requests target `con/centerforopenneuroscience.org` or the account mirror used to make the direct-upstream branch reachable.
2. **Publication branch after review.** Decide whether Pages should deploy only from `main` after Milestone 3 merges.
The recommended default is yes; the milestone branch trigger is a temporary preview bootstrap.
3. **Two-repository review.** Decide whether content remains canonical in the site repository, requiring a site change followed by a parent gitlink change, or moves into the parent in a later milestone.
This milestone preserves the proven site-repository ownership.
4. **Public source catalog.** Confirm that publishing canonical YAML verbatim in the editor catalog is acceptable.
It is already public website input, but the catalog makes bulk download convenient.
5. **Environment protection.** Choose the reviewers, if any, required by the `github-pages` environment before a manual or `main` deployment proceeds.

Hosted authentication, automatic branch creation, automatic pull-request submission, custom domains, redirects, and production DNS remain deferred.

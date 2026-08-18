# Version and authority resolution

Resolve live evidence before designing against a moving ecosystem. Do not copy
the example revisions from an old report into a new conclusion.

## Classify the evidence

Use these categories explicitly:

| Category | Meaning | Normal use |
| --- | --- | --- |
| Supported | Released coordinates or a consumer lock | Ordinary downstream operation |
| Engineering-compatible | Current engineering branch and pinned components | Integration and release preparation |
| Current upstream | Freshly verified authoritative remote head | Drift analysis and potential adoption |
| Proposed upstream | Issue, pull request, topic branch, or design note | Intent and alternatives only |

A successful fetch does not make upstream behavior supported. A local
`upstream/main` is not current until its remote was refreshed. A fork's
`origin/main` is not necessarily authoritative.

## Inspect local authority first

1. Read repository instructions and current decision documents.
2. Inspect lock files, release manifests, gitlinks, submodule status, package
   metadata, and exact imports used by the code path.
3. Read the pinned implementation and tests, not only its documentation.
4. Identify whether a vendored file is source, a generated resolution, or
   historical evidence.

Useful read-only probes include:

```bash
git status --short --branch
git rev-parse HEAD
git remote -v
git ls-tree HEAD <component-path>
git -C <component-path> rev-parse HEAD
git -C <component-path> remote get-url origin
```

Use the repository's package or lock tooling to resolve non-Git dependencies.
Do not assume a directory named `submodules` is initialized or authoritative.

## Verify remote state only when relevant

Use an authoritative project remote or primary documentation. Fetch into a
non-destructive remote-tracking or temporary ref; do not move accepted refs or
update pins as a side effect of inspection.

Compare the narrow relevant range:

```bash
git ls-remote <authoritative-url> refs/heads/main
git -C <component-path> diff --stat <pin>..<verified-upstream>
git -C <component-path> log --oneline <pin>..<verified-upstream>
git -C <component-path> diff <pin>..<verified-upstream> -- <relevant-path>
```

For claims about a feature, inspect its implementation, tests, changelog,
issues, and pull requests. Label issue or pull-request behavior as proposed
until it is merged in the revision being discussed.

## Repositories commonly involved

Discover their actual remotes and pins from the workspace. Depending on the
task, inspect:

- Orinoco Lite engine and engineering integration;
- the Copier template and rendered template output;
- a downstream consumer and its `orinoco.lock` or equivalent release evidence;
- Things schemas and the exact schema source selected by the runtime;
- Things enrichment tools;
- Dump Things service and client;
- query or projection components used by the build.

Do not fetch every repository reflexively. Inspect only the layers that can
change the requested conclusion.

## Report the evidence

Include:

- repository role and checkout;
- supported or engineering revision;
- verified upstream revision and verification date, when consulted;
- relevant code or contract difference;
- status as implemented, accepted, inferred, or proposed;
- compatibility decision and any deliberately deferred adoption.

If network access or remote authority is uncertain, say so and base the work on
the local supported contract. Never describe unverified remote state as latest.

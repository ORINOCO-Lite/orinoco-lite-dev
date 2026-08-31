# Milestone 4 planning prompt: single-repository distribution

**Historical planning input.** The implemented review candidate supersedes this prompt where they differ.
In particular, M4-D001 requires the complete accepted Milestone 3 content and test snapshot rather than a representative subset.
Use [`milestone-4-decisions.md`](milestone-4-decisions.md) for accepted architecture and [`open-decisions.md`](../open-decisions.md) for the current open review queue.

Use this prompt to begin a new planning-mode task.
Do not implement the milestone until the plan and its human decisions have been reviewed.

## Context

Orinoco Lite is a CON project, and CON is also its first intended downstream user.
The goal is to sustainably maintain this variant of the Orinoco project developed by a German lab.

The useful distinction is between:

- the **Orinoco Lite engineering workspace**, where CON develops the framework, integrates `www-from-model`, manages pinned component repositories, and performs upstream rebases; and
- a **test downstream instance**, initially hosted in `test-orinoco-downstream-website`, where CON can develop and repeatedly replace the distribution workflow without disrupting the real site repository; and
- the eventual **CON website instance**, which should adopt the proven downstream experience after the test repository graduates.

The current engineering workspace is deliberately multi-repository.
It coordinates pinned schema, service, projection, editor, graph, upstream-site, migration-evidence, and CON-site repositories through Git submodules.
That topology has been effective for development and reproducibility, but it must not become the required downstream user interface.

Milestones 1–3 have established that:

- canonical CON metadata can use the upstream `www-from-model` conventions and remain isolated from the German content;
- the CON site branch can remain directly descended from and rebasable onto reviewed `www-from-model` commits;
- a now superfluous strategy of using legacy CON branches and tags that can remain permanently reachable as disconnected history in the same site repository without entering the active ancestry; we will likely adjust this organization as required by this milestone.
- canonical YAML, editorial content, configuration, assets, generated projection, and assembly inputs have explicit boundaries;
- deterministic static root and project-path builds work without a persistent metadata service;
- GitHub Pages can host the site and a credential-free static SHACL Vue editor;
- the editor can download a review bundle that is validated locally before changing canonical YAML;
- the Pixi-driven local full stack still provides isolated `con-public`, `con-protected`, `upstream-public`, and `upstream-protected` collections; and
- public Zotero API ingestion can be repeated and reconciled without making the migration repository a production runtime dependency (it seems like we should have a directory explicitly for these sorts of custom tools interfacing to an arbitrary service that can be run on CI or locally)

The accepted repository-placement decision is:

- `centerforopenneuroscience.org` owns canonical CON YAML, editorial content, assets, and the CON site overlay;
- its active branch is upstream-derived and remains rebasable onto reviewed `www-from-model` changes;
- its unrelated legacy history remains preserved by permanent branches and tags and is not merged into that active ancestry;
- `orinoco-lite-dev` is the multi-repository engineering coordinator and pins the selected site commit like its other components;
- the account mirror is transport, not a competing source of truth; and
- publishing the already-public canonical YAML in the static editor catalog is acceptable.

This is the accepted engineering and Milestone 3 deployment topology.
This cannot be the the permanent downstream distribution topology which needs to track www-for-model within orinoco-lite-dev while the templating and downstream users never see this complexity.

## Problem

A downstream adopter should not need to understand or operate:

- Git submodules;
- Git rebasing;
- disconnected histories or checkpoint refs;
- parent-versus-site gitlink updates; or
- more than one repository for an ordinary site.

The desired downstream experience is a single repository created from a GitHub template, Copier template, or similar mechanism.
The user should edit site-owned metadata, editorial content, and assets; run a small set of local commands; receive validation and preview results in GitHub; and accept framework updates through ordinary pull requests.

The first implementation consumer should be a separate repository named `test-orinoco-downstream-website`.
It provides a disposable but realistic integration target while template structure, update automation, generated pull requests, and customization rules are still changing.

The real `centerforopenneuroscience.org` repository is the intended later dog-food consumer, not the initial iteration target.
The existing upstream-derived CON branch should be treated as extraction evidence and a transitional deployment, not automatically as the permanent end-user architecture.
Do not merge experimental template iterations into the real site merely to test the distribution mechanism.
Thats what test-orinoco-downstream-website is for.


## Milestone objective

Establish a sustainable distribution boundary in `test-orinoco-downstream-website`, without exposing its user to the engineering workspace topology (orinoco-lite-dev. This will ultimately used at CON and for other downstreams.

The milestone should complete all but the last step in the following:

```te
www-from-model and component upstreams
  -> CON's Orinoco Lite engineering workspace
  -> reviewed, versioned Orinoco-Lite release and site template
  -> automated update pull request
  -> test-orinoco-downstream-website
  -> reviewed graduation to centerforopenneuroscience.org (for more persistent dog fooding)
```

The engineering workspace may remain complex.
The downstream repository should be simple.

## Desired downstream contract

Plan a repository in which site-owned inputs are directly visible and versioned, for example:

```text
content or metadata/    canonical YAML
editorial/              site-owned prose and navigation
assets/                 site-owned media or declared assets
orinoco.yaml            site profile and feature choices
pixi.toml               small local interface
pixi.lock               reproducible downstream environment, if retained
.github/workflows/      validation, preview, update, and Pages workflows
```

The exact names are not predetermined.
The plan must derive them from the current executable contracts rather than copying this sketch uncritically.

The intended user-facing commands are similarly small, such as:

```text
pixi run validate
pixi run build
pixi run serve
pixi run update-orinoco
```

Determine whether `update-orinoco` should run locally, dispatch a GitHub workflow, or merely document the automated update-PR mechanism.

## Template and update model

Evaluate a combined model rather than assuming one tool solves both creation and maintenance:

- a GitHub template repository for understandable initial creation;
- Copier, or a purpose-built equivalent, for versioned template-owned files and migrations;
- a GitHub Action or bot that runs the updater and opens an ordinary downstream pull request;
- a separately versioned Orinoco build engine or release artifact; and
- explicit ownership boundaries so updates do not overwrite downstream content or approved customization.

Do not prefer a long-lived GitHub fork merely because it provides an upstream remote.
Explain whether a fork would reintroduce upstream merge/rebase concepts that the downstream interface is intended to remove.

The update pull request should make framework changes legible.
It should show, as applicable:

- template and engine version changes;
- workflow and configuration changes;
- explicit content/schema migrations;
- regenerated artifacts, if the distribution chooses to commit them;
- validation and compatibility results; and
- a deployable preview.

No deployment should silently mutate site-owned canonical content.

## Engine and service boundary

Do not accidentally redefine Orinoco as a new simplified service product.
Orinoco already includes the full service stack.
Milestone 4 is primarily about distributing a static-site/content workflow cleanly and is termed Orinoco-Lite to distinguish itself.

The minimum downstream promise should cover:

- canonical-content validation;
- deterministic static build;
- local static preview;
- backend-free patch/download editing;
- pull-request validation and preview; and
- framework/template update pull requests.

The Pixi-driven full local stack remains important to Orinoco Lite development and advanced use.
Do not require the milestone to hide every aspect of that stack or reproduce it as a new product.
Investigate whether a single container or packaged runtime can make it available without submodules, but treat that as an option whose value, size, platform support, and maintenance cost must be justified.
Do not make a persistent container or hosted metadata service necessary for an ordinary static-site consumer.

## Packaging questions

Compare at least these implementation boundaries:

1. a Python package installed and locked through Pixi;
2. a pinned GitHub Action for hosted validation/builds;
3. an OCI container for hermetic CI and optional advanced local use;
4. a released archive containing the static editor, schemas, templates, and build support; and
5. a generated vendor directory committed into each downstream repository.

Combinations are allowed and likely.
For each, assess:

- local macOS and Linux support;
- reproducibility and integrity verification;
- release and security-update mechanics;
- repository size and binary-asset handling;
- offline behavior;
- debugging and extension experience;
- licensing and source availability;
- compatibility with Pages;
- whether users must understand the implementation topology; and
- the burden placed on CON as the sole current framework and site maintainer.

Prefer a narrow stable public interface over merely relocating all current scripts into a package or container.

## Test consumer and later dog-food proof

The milestone must first include a realistic single-repository proof in `test-orinoco-downstream-website`.
This repository is intentionally separate from `centerforopenneuroscience.org` so early template and updater iterations can be replaced, force-updated, or discarded without complicating review of the real site's upstream-derived and legacy histories.

The test repository must still exercise real contracts rather than a trivial toy fixture.
Use a representative, provenance-recorded subset or snapshot of the accepted Milestone 3 CON inputs sufficient to exercise metadata, editorial content, assets, static editing, project-path Pages, and update behavior.
Do not imply that the test repository is the production CON site or configure the CON production domain.

Plan how to derive or instantiate the test consumer from accepted Milestone 3 inputs without losing the relevant parts of:

- canonical metadata and provenance;
- editorial content and presentation decisions;
- asset manifests and verified payloads;
- Zotero ingestion evidence and update policy;
- static editor behavior;
- Pages project-path behavior;
- local public/protected full-stack capability where it remains useful; and
- legacy Git-history preservation in the engineering/site repository.

The flattened test consumer need not reproduce the legacy or upstream-derived ancestry.
Its provenance must instead identify the exact Orinoco release, template version, source site/content commit, and selected content scope used to instantiate it.

Demonstrate at least one real downstream update:

1. create `test-orinoco-downstream-website` from the proposed template or generator;
2. publish an Orinoco template or engine change;
3. have automation open an update pull request against the test consumer;
4. show an understandable diff;
5. run validation and a preview;
6. merge or simulate merging only after human review; and
7. prove that downstream-owned content and customization are preserved.

Then define, but do not perform without separate review, the graduation to `centerforopenneuroscience.org`.
Graduation should require:

- stable ownership rules for template-, engine-, generated-, and site-owned files;
- at least one successful creation and one successful automated update cycle in the test repository;
- demonstrated conflict behavior for a downstream customization;
- reproducible local and Pages builds on the supported platforms;
- a rollback path to the accepted Milestone 3 site;
- a content/provenance migration plan for the full CON site;
- preservation of the real repository's legacy refs and accepted upstream-derived history; and
- explicit human approval before changing the real site's deployment or default branch.

### Test-repository decisions to confirm before remote creation

The planning task should confirm these details before creating or configuring the test repository:

1. **Owner and visibility.** The recommended default is public `con/test-orinoco-downstream-website`, because public anonymous checkout, Pages, template creation, and update pull requests are part of the downstream acceptance contract.
If the organization namespace is unavailable or policy requires isolation, use the maintainer account only as an explicitly temporary transport and record the intended transfer.
2. **Seed content.** The recommended default is a representative public CON-derived fixture with enough people, projects, publications, editorial pages, and assets to exercise every supported path, rather than the entire catalog during early destructive iteration.
The fixture must record its source commit and selection policy.
3. **Pages identity.** The recommended default is the repository's ordinary project Pages URL with no custom domain, `CNAME`, redirect, or production branding claim beyond a visible test-site notice.
4. **History policy.** The recommended default is ordinary disposable downstream history with protected reviewed checkpoints once acceptance begins.
Do not copy the legacy CON Git ancestry or the engineering workspace's upstream-rebase history into this test consumer.
5. **Cleanup and retention.** The recommended default is to retain the repository as the permanent template/update integration fixture even after CON graduates, while allowing pre-acceptance branches and generated previews to be replaced.

Creating the GitHub repository, enabling Pages, installing an app, or granting a workflow permission is an external state change.
The implementation task must obtain or rely on explicit authorization for those actions and document the exact settings it changes.


## Customization and Copier questions

Plan explicitly for downstream divergence.
Copier or any equivalent updater must distinguish:

- files owned entirely by the template;
- files initialized by the template but thereafter owned by the site;
- structured configuration with mergeable fields;
- generated files that may be replaced;
- local extensions with stable hook or override points; and
- migrations that require a human-reviewed semantic change.

Determine:

- what answers or release metadata are recorded in the downstream repository;
- how updates detect the previous template version;
- how conflicts are surfaced without requiring users to understand rebasing;
- whether generated update PRs need a migration ledger;
- how a site can defer or skip an update safely;
- how security fixes are distinguished from optional presentation changes;
- how downstream custom layouts or schema extensions remain supportable; and
- whether the updater itself must be reproducible and pinned.

## Acceptance scenario

The decisive user-level scenario is a person unfamiliar with Git submodules and rebasing using `test-orinoco-downstream-website` as a single repository, editing a canonical record, validating and previewing it locally, publishing a Pages preview, downloading or applying a static-editor patch, and later reviewing and merging an automated Orinoco update pull request without learning the engineering workspace topology.

The test repository must pass this scenario with representative real CON-derived inputs.
Applying the same workflow to the complete real CON site is a later graduation gate, not a prerequisite for iterating on the distribution mechanism.

Also retain an engineering-level scenario in which CON can:

- review and integrate a new `www-from-model` commit;
- run the existing upstream/rebase acceptance internally;
- publish a new Orinoco release;
- generate downstream update pull requests; and
- prove that the consumer update is equivalent to the reviewed engineering result where the contracts overlap.

## Non-goals unless planning reveals a blocker

Do not make Milestone 4 implicitly include:

- production-domain cutover or DNS changes;
- hosted authentication or browser-held GitHub credentials;
- automatic merging of update pull requests;
- a persistent hosted Dump Things service;
- abstraction of every full-stack development operation;
- replacement of all Git Annex custody;
- resolution of every outstanding content decision;
- a general-purpose hosted SaaS product;
- deletion or rewriting of legacy CON history; or
- upstream contributions unrelated to extracting the distribution boundary.

## Required planning work

Begin with read-only investigation.
Do not assume that the sketch above matches the executable repository contracts.

The planning task should:

1. inventory current content, engine, generated-output, and deployment ownership;
2. trace the complete static build and editor-patch data flows;
3. identify every dependency on submodule layout and Git ancestry;
4. compare packaging and template/update alternatives;
5. define the smallest stable downstream contract;
6. propose the test-repository implementation and the later CON graduation and preservation strategy;
7. define versioning, release, compatibility, and update-PR policies;
8. specify acceptance tests for creation, update, rollback, and customization;
9. estimate migration effort and debt retirement by workstream;
10. enumerate all human decisions with recommended defaults; and
11. produce an ordered implementation plan with explicit stop/go checkpoints.

Be proactive about clarifications.
Surface choices whose answers materially alter repository ownership, release mechanics, customization guarantees, or security boundaries.
Do not ask for choices that can be answered from the existing contracts or by a safe reversible prototype.

## Requested planning deliverables

Produce:

1. a concise recommended architecture;
2. a diagram of engineering, release, template, updater, and consumer boundaries;
3. a current-to-target ownership map for files and responsibilities;
4. a comparison of GitHub template, Copier, fork, package, Action, archive, and container roles;
5. a technical-debt and extraction-risk register;
6. a phased implementation plan with independently reviewable milestones;
7. a `test-orinoco-downstream-website` implementation plan
8. a downstream update-PR contract, including customization/conflict behavior;
9. an acceptance matrix covering macOS, Linux, local static use, Pages, editor patches, and optional full-stack use;
10. a human decision register with recommended defaults; and
11. a clear statement of what remains internal Orinoco Lite engineering complexity versus the supported downstream interface.

The final plan should be detailed enough to implement in a later task without rediscovering repository roles, but it should not prematurely commit to a packaging mechanism before comparing the alternatives against the real code and build graph.

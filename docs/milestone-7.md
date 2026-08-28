# Milestone 7: sustainable downstream ownership

Status: planning; starts after Milestone 6 closes

Predecessor: [`milestone-6.md`](milestone-6.md)

Normative source-adapter contract: [`source-adapters.md`](source-adapters.md)

GitHub review profiles: [`github-curation-review.md`](github-curation-review.md) and [`github-shacl-vue-edit.md`](github-shacl-vue-edit.md)

Current human-policy queue: [`human-review-decisions.md`](human-review-decisions.md)

## Planning boundary

Milestone 7 reduces the cost and risk of changing Orinoco Lite after the Milestone 6 metadata paths have been exercised end to end.
It does not close, reinterpret, or add acceptance evidence to Milestone 6.
Its implementation begins from the exact accepted Milestone 6 release and downstream coordinates.

Small changes that do not alter metadata semantics, authority, provenance, repository ownership, or the new path contract may proceed as separate pull requests while this plan is reviewed.
In particular, user-facing bot copy and the empty `/review/` fallback can be corrected independently.
Validation-event classification, data relocation, generic-code relocation, and autonomous curation are not quick-copy changes and remain workstreams below.

## Outcome

Milestone 7 makes ordinary Orinoco Lite development a one-way promotion rather than a repeated three-repository debugging cycle.

It will:

- give every downstream one obvious root for its site-specific data;
- make a useful site render from records and structured site data without requiring downstream-authored Markdown;
- move generic presentation, projection, curation, and workflow behavior into released engine or template ownership;
- exercise a complete generated downstream locally in the engineering workspace before a change propagates;
- support an optional, developer-owned AI sandbox without making it a project coordinate or a required promotion gate;
- distribute skills for both the fast integration loop and ordinary downstream maintenance; and
- remove legacy copied framework and content after the migration is proved reversible and the maintained reference downstream adopts it.

The milestone succeeds when a generic correction is implemented and tested once at its owning layer, not copied independently into consumers and then debugged again after deployment.

## Direction established for this plan

### M7-D001 — Put site-specific data under one root

The downstream data boundary is `site-specific/`.
Canonical metadata, compact curation state, source configuration and policy, site identity, editorial data, and site-owned assets must not remain scattered among `metadata/`, `custom/`, `site/`, and `source-adapters/`.

This is an ownership and configuration migration, not merely a directory rename.
Exact record, annotation, decision-cache, editor-bundle, workflow, and allowlist paths change together through a versioned contract and a tested migration command.

### M7-D002 — Generate the normal site from structured data

The template supplies useful default pages, navigation, layouts, projection, and copy.
A downstream supplies records and a small structured site description.
Generic Markdown and templates contain no `CON` literal or other consumer identity.

Optional downstream Markdown remains available for genuinely bespoke prose or pages.
It is an extension, not a prerequisite for a useful generated site and not a second manually synchronized representation of people, projects, or other record-derived lists.

### M7-D003 — Keep the required reference downstream and optional fast path distinct

`ORINOCO-Lite/test-orinoco-downstream-website` is the required human-governed reference downstream.
It demonstrates what a normal adopter receives, including the template update path, required review, ordinary validation, and human-first curation skills.

An individual developer may also create a disposable downstream in that developer's own GitHub account and grant an agent broad authority over it.
The repository is selected by the developer; Orinoco Lite does not prescribe a shared owner, repository name, immutable repository ID, approval profile, or dedicated bot identity.
Within that explicitly granted repository scope, branch and pull-request conventions remain useful defaults for exercising the adopter experience, but they are guidance rather than gates.
The agent may choose the shortest effective path through commits, pull requests, merges, direct default-branch updates when permitted, browser flows, curation, Pages, and recovery without waiting for per-action human confirmation.

The optional sandbox is not evidence that an ordinary downstream should disable review.
The reference fixture is not the first place a generic change is debugged.
If a developer cannot or does not want to grant independent control, the hosted sandbox is omitted rather than converted into another partly gated project fixture.
The engineering dry run and the organization reference downstream then form the complete development and acceptance path.

### M7-D004 — Promote in one direction

The normal implementation sequence is:

1. establish the hermetic engineering dry run and correct generic ownership;
2. implement and test the versioned site-data and template migration there;
3. release or otherwise pin the immutable generic implementation;
4. promptly migrate the organization reference fixture through the ordinary downstream update path.

When a developer has configured an optional developer-owned sandbox, its hosted exercise can run in parallel after the immutable implementation exists or afterward as additional evidence.

A failure moves back to the owning layer.
It is not patched independently in each later consumer unless the behavior is genuinely site-specific.
The optional sandbox is useful evidence but neither a release gate nor a prerequisite for proposing the organization migration.

The dry-run harness and ownership extraction are the first blocking slice.
Once they can prove the new contract, the data and template migration proceeds as one focused batch.
Optional hosted exercise, richer `/review/` discovery, validation-event redesign, and unrelated visual polish do not delay that migration unless they expose a contract defect.

## Target ownership and layout

The provisional public shape is:

```text
site-specific/
  site.yaml
  content/
    pages/
  static/
    manifest.yaml
    files/
  curation-records/
    <adapter>.yaml
  sources/
    <adapter>/
      source.yaml
      policy/
      evidence/
  metadata/
    records/
    overlays/
      annotations/
extensions/
  source-adapters/
  site/
```

`curation-records/` contains only compact current decision caches.
Source coordinates, mapping policy, and retained source evidence belong under `sources/`.
Both are site-specific data.
Git remains the event and historical record; Milestone 7 does not introduce a second curation event store.

| Surface | Milestone 7 authority |
| --- | --- |
| `site-specific/metadata/records/**` | Human-facing canonical semantic records |
| `site-specific/metadata/overlays/annotations/**` | Machine-managed annotation companions |
| `site-specific/curation-records/**` | Compact adapter decision caches |
| `site-specific/sources/**` | Source coordinates, mappings, policy, and retained evidence |
| `site-specific/site.yaml` | Site identity, navigation, contact data, route choices, and presentation groups |
| `site-specific/content/**` | Optional site-owned prose and page data that extends generated defaults |
| `site-specific/static/**` | Site-owned files and one structured asset manifest |
| `extensions/source-adapters/**` | Truly consumer-specific adapter executable code |
| `extensions/site/**` | Optional site-specific styles, layouts, or presentation code that cannot be expressed as data |
| Engine/runtime | Generic path handling, validation, projection, curation mechanics, review application, and reusable commands |
| Template | Generic downstream configuration, workflows, layouts, generated pages, update mechanics, and ordinary maintenance skill |
| Repository root | Legal, contributor, lock, and workspace files plus a small versioned pointer to the site-data contract |

Generic Zotero behavior, curation runners, workflow logic, projection tools, index-page generation, layouts, and common configuration must not remain create-once consumer copies.
A CON-only adapter may remain an extension, but its source coordinate, policy, evidence, and decisions still belong under `site-specific/`.

The existing presentation snapshot cannot simply be copied into a distributed runtime or template until its redistribution terms are established.
The Congo theme can move with its notice; other material needs a verified license, permission, or a clean generic replacement.

## Workstream 1: engineering dry-run harness

Add one documented command that constructs an ordinary downstream in a fresh temporary directory from the candidate template and exact engine/runtime coordinates.
It must not discover a sibling checkout or depend on a developer's untracked state.
It uses the same generated repository shape, complete acceptance data, and public commands as an ordinary downstream; Milestone 7 does not introduce a smaller canary corpus or a second downstream contract for speed.

The harness exercises, as applicable:

- template render and update;
- configuration and ownership validation;
- representative source acquisition from the recorded source material within the complete acceptance dataset;
- candidate planning and curation finalization through a deterministic test oracle;
- canonical and joined metadata validation;
- projection and static build;
- `/edit/` and `/review/` route generation and focused browser checks; and
- a second identical ingestion that produces no proposal.

Network-hosted GitHub and Pages checks remain a later integration layer.
The local harness must catch path, template, workflow-rendering, content, and build errors before a release reaches any hosted downstream.

Acceptance:

1. the command succeeds from a clean clone on macOS ARM64 and Linux x86-64;
2. it identifies every immutable input and fails when an input is absent or at the wrong coordinate;
3. it creates no tracked or sibling-worktree state; and
4. generic pull requests run it before release or promotion.

Workstreams 2–4 are ownership views of one vertical implementation after this harness is available, not three release phases.
Generic-code relocation, structured rendering, and the path-contract migration proceed together so that consumers move once rather than crossing a series of temporary layouts.

## Workstream 2: extract generic presentation and curation behavior

Classify every copied downstream file as generic framework, structured site-specific data, optional extension, generated output, test fixture, legal material, or obsolete state.
Assign generic behavior to its owning release or template before cutover, then land generic-code relocation and consumer-data relocation together in the focused migration batch.

At minimum, this work covers:

- projection templates and tools;
- generated section and index pages;
- common Hugo layouts, menus, configuration, and static application shells;
- the generic Zotero adapter and curation runner;
- reusable curation workflow behavior and its tests; and
- the `/edit/` and `/review/` integration configuration.

Thin downstream workflows may call immutable reusable workflows.
Site-specific adapter coordinates and policy remain data inputs rather than copied workflow implementations.

Acceptance:

1. an ownership scan finds no byte-identical generic implementation classified as create-once site content in the generated harness consumer or organization reference, and also inspects an optional sandbox when one is exercised;
2. a generic fix has one implementation owner and one focused test location;
3. generated consumers still expose ordinary source for inspection and local builds; and
4. redistribution notices and licenses accompany every distributed framework asset.

## Workstream 3: replace consumer-specific page copies with structured rendering

Define and validate the structured `site.yaml` and asset manifest.
Generate default home, about, people, projects, publications, instruments, contact, engagement, support, and navigation surfaces from those inputs and canonical records where appropriate.

Remove manually duplicated lists.
For example, one structured presentation selection must drive a project or people view; it must not also be hand-copied into Markdown.
Site-specific headings and explanatory copy are fields or optional Markdown overrides, not literals in generic templates.
This is the presentation work required by the ownership migration, not a separate visual redesign.
Existing useful routes and content remain available unless a change is necessary to remove a duplicated or consumer-specific framework assumption.

Acceptance:

1. a new downstream with records, `site.yaml`, and assets builds a useful site without writing a Markdown page;
2. generic sources contain no `CON`, Center for Open Neuroscience, fixture repository, or optional-sandbox identity;
3. optional Markdown overrides compose with generated defaults without replacing the updateable framework; and
4. the hermetic harness varies `site.yaml` over the same complete acceptance data to exercise the generic renderer, and the organization reference uses that renderer with its complete site data.

## Workstream 4: introduce the versioned site-data contract

Add configurable record, annotation, curation, source, and asset roots.
Remove fixed old-path constants from the engine, backend allowlists, editor bundles, workflows, adapters, validation, and tests.

Ship one explicit migration command for a clean supported consumer.
It:

- verifies the exact source contract and expected ownership hashes;
- moves site data while preserving bytes and useful Git history;
- renders the new generic framework and records every intentional conflict;
- stops rather than overwriting edited site-owned content;
- updates configuration and generated workflow contracts atomically;
- validates the joined graph and built route inventory; and
- is idempotent after successful migration.

Old-layout curation pull requests must be completed or closed before cutover unless a separately reviewed compatibility design proves their exact safe finalization.
Immutable old releases remain available for rollback.
The normal runtime does not carry indefinite v2/v3 dual-path behavior.

Acceptance compares semantic graph content, record and annotation counts, decision-cache bytes, asset digests, published routes, `/edit/`, `/review/`, and clean-clone builds.
Byte-identical generated bundles are not required when they truthfully embed new repository paths.

## Workstream 5: review experience, bot copy, and validation events

The empty `/review/` route first provides a repository-bound link to open curation pull requests.
A later enhancement may populate an in-page selector asynchronously while keeping an exact proposal URL the primary deterministic entry point.
The central backend remains authentication and verified transport, not a new discovery or landing service.

Curation pull-request bodies identify the source adapter, preserve the merge-commit warning and review-artifact retention note, link to the downstream review application, and put canonical source coordinates in a closed `<details>` block.
GitHub Actions bot output does not use an AI-draft disclaimer intended for agent-authored prose.
Finalization copy reports the recorded decision commit and the actual validation state without claiming readiness before asynchronous validation has passed.

Validation redesign is coordinated across the template-owned validation workflow and its curation callers.
It must distinguish:

- a metadata proposal that needs full validation;
- an authenticated decision-cache finalization that needs trusted joined-graph validation at the exact head;
- ordinary framework or content changes;
- the explicit trusted dispatch used to avoid approval-gated bot-created pull request runs; and
- default-branch and manual runs.

A base-branch-owned classifier must never check out or execute untrusted pull request code with elevated credentials.
Event-specific concurrency must not let a later approval-gated run cancel an already running trusted dispatch.

Acceptance has no duplicate approval-gated run for the same required result, no skipped run presented as missing validation, and no weakening of exact-head or untrusted-code boundaries.

## Workstream 6: skills and explicit authority profiles

### Optional developer-account AI sandbox

Create the project-owned skill `.apm/skills/exercise-orinoco-ai-sandbox/SKILL.md` in the engineering repository.
APM owns deployment to `.agents/skills/`; skills-workshop audits, tests, remembers, and records use of the canonical skill.
The generated `.agents/` copy is never edited directly.

The skill accepts a developer-selected repository in that developer's own account.
The selection and authority grant are developer-local inputs, not a project-wide tracked coordinate or a policy that other developers must adopt.
After verifying the exact selected target and the broad grant once, the skill does not request repeated approval for ordinary state changes within that sandbox.
It may:

- choose branches, pull requests, direct updates, merges, reruns, or recovery according to the fastest useful route that the selected repository permits;
- run local checks and decide whether waiting for hosted CI is worth the delay;
- navigate the deployed `/edit/` and `/review/` browser flows;
- make the curation and editorial decisions needed to complete end-to-end testing;
- exercise Pages, repository settings, branch cleanup, and failure recovery when those operations are inside the explicit sandbox grant; and
- fix forward, revert, or repeat the run when later evidence disagrees.

Using branches, pull requests, and passing checks remains the recommended engineering practice because it exercises the normal adopter path and leaves useful evidence.
It is not an artificial human gate inside a disposable, independently authorized sandbox.

The grant does not extend to engine or template releases, the organization reference downstream, the real site, external-source writes, or another developer's repositories.
The skill cannot bypass missing credentials, two-factor authentication, or platform confirmations that technically require the account holder.

A dedicated bot or test identity is optional when it is already easy for the developer to provide; it is not a prerequisite for the sandbox.
Curation provenance distinguishes the authenticated GitHub principal from agent-mediated execution so that browser use through a developer-authorized account is not mislabeled as an unaided human decision.
The representation must accommodate a downstream's own review and attribution preferences rather than imposing the project's fixture policy on every adopter.

If these conditions do not produce a genuinely low-friction environment for a developer, that developer omits the hosted sandbox and relies on the hermetic engineering command followed by the human-gated organization fixture.

### Ordinary downstream maintenance

Add a template-owned `maintain-orinoco-site` skill and update the existing content and source-adapter skills for the new paths.
It guides an agent to:

- inspect immutable upstream, template, and runtime coordinates;
- render an update check before changing site-owned data;
- preserve site-owned bytes and surface semantic migrations for review;
- update content or adapter configuration only under the downstream's stated policy;
- validate locally and prepare a focused pull request; and
- stop before merge, publication, or unresolved semantic decisions unless the downstream explicitly grants that authority.

The template skill is copied through the normal Copier release and update mechanism.
It is a template release artifact rather than a project-owned experimental skill, so generated downstreams do not need APM merely to receive it.
If a downstream develops its own local skill, that downstream may use `.apm/skills/` and APM deployment without editing the template-owned copy.
It remains human-first and must not inherit an optional sandbox's fast-lane authority.

Acceptance includes skill validation, a skills-workshop audit/use record, exact-target tests for the sandbox skill, and a generated downstream exercise of the normal maintenance skill.
An online sandbox exercise is recorded when a developer has configured one, but the existence of a centrally maintained personal-demo repository is not a Milestone 7 requirement.

## Workstream 7: release, migrate, and remove legacy state

Promote each independently reviewed layer in the order in M7-D004.
Record exact engine/runtime and template releases, generated-template commits, migration commits, downstream heads, workflow runs, Pages deployments, rollback coordinates, and ownership classifications in a concise Milestone 7 acceptance record.

Only after the clean generated-consumer contract and organization reference adopt the new contract:

- remove obsolete `custom/**` and old metadata roots;
- remove copied generic site and curation implementation;
- remove duplicate Markdown lists, configuration, and stale paths;
- update repository skills and contributor documentation; and
- make the ownership scanner reject newly introduced site data outside `site-specific/`, except an explicit short list of legal and repository infrastructure files.

## Non-goals

Milestone 7 does not:

- close or rewrite Milestone 6 acceptance;
- modify, deploy, migrate, or graduate the real CON site;
- write to Zotero or another external source;
- treat an AI action as human review or attribute an agent decision to the authenticated developer as unaided human review;
- remove ordinary human review from the organization reference downstream;
- let optional-sandbox shortcuts weaken engine, template, schema, provenance, security, release, or organization-reference gates;
- add a persistent metadata, curation, credential, or proposal service;
- carry two writable site-data layouts indefinitely; or
- redistribute framework material without established permission.

## Milestone acceptance

Milestone 7 is complete when:

1. the hermetic engineering command validates a generated consumer end to end before downstream promotion;
2. all site-specific data is under the accepted `site-specific/` contract, optional executable overrides are isolated under `extensions/`, and generic behavior has a single engine or template owner;
3. a new downstream builds a useful site from structured data and records without required custom Markdown;
4. the one-time migration is conflict-safe, idempotent, semantically stable, and adopted by a clean generated consumer and the organization reference;
5. `/review/`, bot copy, and validation behavior meet Workstream 5 without a second frontend or redundant approval-gated run;
6. when a developer configures an optional sandbox, it records an autonomous ingestion, curation, edit, build, merge, deployment, no-op, and recovery exercise with truthful agent provenance, but its absence does not block the milestone;
7. the organization fixture completes the ordinary human-governed update and curation path using the distributed maintenance skill; and
8. ownership, release, deployment, rollback, and cross-platform evidence are recorded without duplicating Git history.

## Resolved planning decisions

The following decisions were resolved on August 28, 2026:

1. `curation-records/` has the narrow decision-cache meaning; source coordinates, mapping policy, and retained evidence belong under `sources/`.
2. The engineering dry run is the primary fast loop.
A hosted autonomous sandbox is optional, belongs to the individual developer who configures it, and is never hard-coded as an Orinoco Lite project coordinate.
3. A configured sandbox broadly authorizes repository-local engineering, editorial, curation, browser, workflow, merge, publication, and recovery choices.
Normal pull-request and check discipline is recommended evidence-producing practice, not a human permission gate.
4. No dedicated bot identity is mandatory.
The curation contract records both the actual authenticated GitHub principal and that execution was agent-mediated; a developer may substitute a dedicated bot when convenient.
5. The fast path does not use a separately maintained canary corpus.
The hermetic harness exercises the ordinary generated repository contract and complete acceptance data, while an optional hosted sandbox uses its own downstream content.
6. Development-loop organization and ownership are fixed first.
The site-data and template migration then proceeds quickly as one vertical batch; unrelated visual redesign is not a separate Milestone 7 phase.

Any destructive sandbox operation still resolves the exact repository target and a recovery route before execution, but it does not require another human approval when it is already inside the developer's broad grant.

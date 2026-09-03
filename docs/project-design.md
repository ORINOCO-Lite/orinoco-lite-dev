# Orinoco Lite project design

Orinoco Lite provides a repository template for maintaining schema-backed research information and publishing an organization's static website.
It adapts the separately maintained ORINOCO ecosystem (Organized Research Information: Ontology-mapping, Curation, Orchestration), which manages metadata records and derives consumer-specific views such as websites.
Orinoco Lite keeps the records and website on GitHub and replaces ORINOCO's server-backed metadata management with pull-request-based curation.

This document is the durable, high-level design contract shared by maintainers, developers, and AI agents.
It describes the intended architecture rather than a release inventory or progress report.
Detailed protocols, procedures, and temporary implementation plans belong in the documents linked below.

## Terminology

- *canonical* — accepted source state from which other representations are derived, not an assertion that the state is immutable;
- *contract* — behavior or a boundary that implementations must preserve, excluding incidental implementation details;
- *downstream* — a website repository created from and maintained with Orinoco Lite;
- *policy* — an explicit human or organization choice among supported behaviors, not a choice inferred from the current implementation;
- *projection* — a consumer-specific view derived by selecting, joining, or transforming canonical metadata without changing it; and
- *upstream* — the original ORINOCO ecosystem and its artifacts, including the [psychoinformatics.de](https://www.psychoinformatics.de) website.

## Objective

An Orinoco Lite deployment should help an organization:

- maintain human-readable, schema-conformant metadata under review in Git;
- prepare automated improvements from external sources for human review through pull requests;
- publish a static website based on [psychoinformatics.de](https://www.psychoinformatics.de) with GitHub Pages; and
- customize the site's content, presentation, and organization while continuing to receive Orinoco Lite updates.

The deployed site URL includes endpoints for client-side operations:

- `/edit/` for web-based metadata changes; and
- `/review/` for integrating changes from automated metadata improvements.

GitHub is the target platform for proposing, reviewing, and approving changes; static hosting serves the build output.

## System organization

The system has three layers: development sources, distributed components, and each deployed site.

### Development sources

| Part | Role | Boundary |
| --- | --- | --- |
| [`orinoco-lite-dev`](https://github.com/ORINOCO-Lite/orinoco-lite-dev/) | Develops Orinoco Lite, selects the exact presentation source, assembles releases, and maintains reusable CI | Its multi-repository engineering structure is not exposed to downstreams. |
| [`www-from-model`](https://github.com/ORINOCO-Lite/www-from-model) | Supplies the reusable website presentation, page templates, graph production, and its exact Congo selection | Its selected revision and the dependencies it declares are reused without copying German content, identity, or site-specific assets. |

### Distribution

An Orinoco Lite release is one Python package whose code and bundled resources share one version and integrity boundary.

| Part | Role | Boundary |
| --- | --- | --- |
| [`orinoco-lite`](../packages/orinoco-lite/) | Contains the code and data needed to validate metadata, derive projections, assemble the site, and add the static `/edit/` and `/review/` interfaces | It includes the pinned Things Schema, generic drivers, static interface shells, licenses, notices, and the engineering source commit that selects the presentation source. It contains no organization content or policy and no copy of the upstream website. |
| [`orinoco-lite-template`](https://github.com/ORINOCO-Lite/orinoco-lite-template/) | Supplies the downstream scaffold, thin Orinoco presentation adaptation, bounded licensed assets, workflows, helper tools, and initial locks | It is not a website copy and contains no German content or site identity. |

### Deployment

| Part | Role | Boundary |
| --- | --- | --- |
| A downstream repository, exemplified by [`test-orinoco-downstream-website`](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website) | Owns one organization's canonical site inputs, downstream-defined source adapters, review policy, deployment, and upgrade timing | It is human-gated. Generated projections, site output, and caches are build products rather than canonical input. |
| The [curation service](../packages/curation-review-app/) | Signs users in and performs verified GitHub operations for online editing and review | It is outside build and public-read paths, hosts no editor or review interface, and stores no metadata, decisions, bundles, or durable sessions. |

```mermaid
flowchart TB
  subgraph maintenance["Source selection and repinning"]
    direction LR
    engineering["orinoco-lite-dev<br/>package and service source,<br/>selected Gitlink, release assembly"]
    upstream["www-from-model<br/>presentation, page templates, graph producer"]
    dependencies["Dependencies declared and pinned<br/>by www-from-model, including Congo"]
    annex["Git Annex<br/>maintainer-only hydration and verification"]
    repin["Repin and materialize<br/>required presentation payloads"]

    engineering -->|"exact Gitlink"| upstream
    upstream -->|"declares exact pins"| dependencies
    upstream -->|"selected payloads"| repin
    annex -.->|"used only here"| repin
  end

  subgraph distribution["Distribution"]
    direction LR
    package["orinoco-lite Python package<br/>code, schema, drivers,<br/>/edit/ and /review/ shells, licenses"]
    template["orinoco-lite-template source<br/>thin adapter, licensed asset overlay,<br/>Copier scaffold, workflows, initial pins"]

    engineering -->|"publishes one package"| package
    repin -->|"ordinary licensed files"| template
    package -->|"reviewed version and integrity pin"| template
  end

  subgraph downstream["One deployed site"]
    direction LR
    repository["Downstream repository<br/>canonical metadata, content, identity,<br/>policy, adapters, exact locks"]
    cache[("Ignored exact-source cache")]
    build["Orinoco Lite build<br/>resolve, verify, join, validate, project, compose"]
    artifact["Static artifact<br/>website plus /edit/ and /review/"]
    service["Curation service<br/>sign-in and GitHub operations"]
    host["Static hosting"]

    template -->|"initial scaffold and pins; reviewed updates"| repository
    package -->|"recorded engineering commit selects<br/>exact presentation sources"| cache
    package -->|"installed and verified<br/>from the downstream lock"| build
    cache -->|"verified sources"| build
    repository -->|"site-owned inputs and policy"| build
    build -->|"static bytes"| artifact
    artifact -->|"deploy static bytes"| host
    artifact -.->|"explicit signed-in request"| service
    service -.->|"commit edit bundle or<br/>post review decisions"| repository
  end

  click engineering "https://github.com/ORINOCO-Lite/orinoco-lite-dev" "Open the engineering repository"
  click upstream "https://github.com/ORINOCO-Lite/www-from-model" "Open the presentation source"
  click dependencies "https://github.com/ORINOCO-Lite/congo" "Open the selected theme repository"
  click annex "https://git-annex.branchable.com/" "Open Git Annex"
  click repin "https://github.com/ORINOCO-Lite/orinoco-lite-dev/blob/main/tools/materialize_presentation_assets.py" "Open the repinning tool"
  click package "https://github.com/ORINOCO-Lite/orinoco-lite-dev/tree/main/packages/orinoco-lite" "Open the Orinoco Lite package"
  click template "https://github.com/ORINOCO-Lite/orinoco-lite-template/tree/main" "Open the template source"
  click repository "https://github.com/ORINOCO-Lite/test-orinoco-downstream-website" "Open the human-gated reference downstream"
```

## Downstream data boundary

Each downstream keeps its declarative site data under `site-specific/`, separate from site-specific executable adapters:

```text
site-specific/                         # Downstream-owned declarative site data
  site.yaml                            # Site identity, navigation, and presentation settings
  assets/                              # Source assets processed by Hugo during the build
  content/                             # Hand-authored editorial pages
  static/                              # Site files published verbatim
  metadata/                            # Canonical records and their annotation companions for validation and RDF view
    records/                           # Schema-compliant YAML describing organization entities
    overlays/annotations/              # Separate tree for messier record components that are part of the realized graph
  curation-records/                    # Current reviewed automated data import decisions
  sources/<adapter>/                   # Inputs, evidence, and mapping policy for metadata automation tools
  overrides/                           # Bounded replacements for framework surfaces
    config/                            # Final Hugo configuration overrides
    layouts/                           # Hugo template replacements
    static/                            # Replacements for framework static files
extensions/                            # Downstream-owned executable code for metadata management
  source-adapters/<adapter>/           # Site-specific acquisition and curation code
```

`site-specific/` is the human-curated, declarative, self-contained source for what the organization's site contains and how it appears.
It holds semantic assertions, machine-provenance companions, editorial material, identity, presentation data, assets, source evidence and policy, current curation decisions, and supported small overrides—not implementation code.

`extensions/source-adapters/` is exclusively for site-specific executable metadata acquisition and curation code.
It is not a website extension surface: adapter code, captured execution state, and dependencies are neither loaded by website composition nor copied into the generated site.
Reusable adapter primitives belong in Orinoco Lite or the template.

Orinoco Lite combines `site-specific/metadata/` with the exact Gitlink-selected `www-from-model` revision to generate the graph and Hugo pages.
It does not modify metadata during that step.
These generated files are not canonical inputs and do not enter the downstream's default branch.

## Build and deployment flow

1. The downstream lock selects exact versions of Orinoco Lite, the template, and shared workflows.
The Orinoco Lite package identifies the engineering commit whose Gitlink selects `www-from-model`; that revision selects Congo and its other dependencies.
2. Orinoco Lite converts the site's metadata into a graph and validates it against the exact Things Schema included in the package.
3. Orinoco Lite uses the selected upstream page templates and graph generator to create the site's pages and graph data.
These generated files form the **Hugo projection**: build output derived from the canonical source and selected dependency versions, rather than canonical source data.
4. Orinoco Lite combines the reusable website, the thin Orinoco adaptation, and the downstream's content and settings in a fixed order.
Site overrides apply only in the supported locations and take precedence there.
The build also adds the static `/edit/` and `/review/` interfaces and connects them to the downstream repository and exact commit being built.
5. The completed website is deployed as static files.
Once the selected dependencies have been downloaded and verified, validating, building, browsing, editing, and downloading change bundles do not require a running metadata service.

## Generated publication records

Canonical metadata, editorial content, configuration, and accepted review decisions remain on the downstream's reviewed default branch.
Generated Hugo projection and website output must not accumulate there.

The latest successful deployment retains its Hugo projection and deployed static files outside the default branch, traceable to the accepted source commit.
A longer publication history may be retained for diagnosis and recovery.
Other generated operational data is temporary and provides neither canonical metadata nor recovery authority.
This retention does not require byte-identical rebuilds or additional manifests, attestations, ledgers, or validation machinery.

## Metadata change flow

People may edit metadata through ordinary Git changes or use `/edit/` to download an edit bundle for local application.
After explicit confirmation, `/edit/` can instead ask the curation service to create or update a draft pull request.

Source adapters are downstream-defined automations that read identified external sources and prepare repeatable metadata proposals without modifying those sources.
DataLad records each adapter run and proposed Git commit; `/review/` lets a person accept, reject, or defer every proposed change.

For online editing and review, the curation service signs the user in and verifies the exact GitHub state.
It commits a confirmed edit bundle or posts confirmed review decisions to the matching pull request.
Trusted workflows validate and finalize the resulting metadata changes.
Automation must not invent metadata meaning, identity, rights, or review decisions; approve or merge changes; or write to an external source.

```mermaid
flowchart TB
  sources["External information source"] -->|"read only"| adapters["Metadata importer<br/>(source adapter)"]
  adapters -->|"repeatable proposal recorded with DataLad"| github["GitHub pull request<br/>and trusted workflow"]

  site["Published static website"] --> edit["Edit metadata<br/>/edit/"]
  site --> review["Review automated suggestions<br/>/review/"]
  edit -->|"download without signing in"| local["Review and apply locally"]
  local -->|"ordinary Git change"| github
  edit -.->|"submit edit after sign-in"| service["Curation service<br/>sign-in and exact-state checks"]
  review -.->|"submit decisions"| service
  github -.->|"verify pull request and current commit"| service
  service -.->|"commit edit bundle or post review decisions"| github

  github -->|"validated change; human merge"| canonical["Approved metadata<br/>in the downstream repository"]
  canonical -->|"validate and rebuild"| site

  click adapters "https://github.com/ORINOCO-Lite/orinoco-lite-dev/blob/main/docs/agents/contract/source-adapters.md" "Open the source-adapter contract"
  click service "https://github.com/ORINOCO-Lite/orinoco-lite-dev/tree/main/packages/curation-review-app" "Open the curation service"
  click github "https://github.com/ORINOCO-Lite/orinoco-lite-dev/tree/main/docs/agents/contract" "Open the normative contracts"
```

The precise behavior is defined by the normative contracts for [source adapters](agents/contract/source-adapters.md), [GitHub source review](agents/contract/github-curation-review.md), and [SHACL Vue editing](agents/contract/github-shacl-vue-edit.md), including the [curation-service authentication rules](agents/contract/curation-service-authentication-options.md).

## Design principles

- **Reuse rather than fork.** The selected upstream revision and its declared dependencies provide the website; Orinoco-specific changes remain small, explicit, and separately owned.
- **Separate shared behavior from site policy.** Orinoco Lite owns reusable operations and the pinned Things Schema contract.
Each downstream owns its information, presentation choices, review policy, and downstream-defined automations.
- **Publish a static product.** The website, `/edit/`, and `/review/` are static files.
The curation service is used only for signed-in GitHub operations.
- **Keep people and Git in control.** External sources are read-only, automation produces proposals, human choices are explicit, and Git supplies durable history and recovery.
- **Record each fact once.** Versions and integrity data belong in the locks, package metadata, Gitlinks, and release inputs that use them; change history belongs in Git and GitHub.
Do not add parallel ledgers or inventories merely for explanation or proof.
- **Give provenance tools distinct jobs.** Git Annex is maintainer-only tooling for selecting and materializing required presentation assets.
DataLad records downstream adapter runs in ordinary Git; released builds and adapter runs do not require Git Annex.

## Documentation and change control

This document owns the project's lasting purpose, organization, and boundaries.
Narrower or shorter-lived information belongs elsewhere:

- [`docs/agents/contract/`](agents/contract/) defines exact technical rules where metadata meaning, review behavior, or security boundaries require precision;
- [`AGENTS.md`](../AGENTS.md) gives agents current operating constraints and points them to the applicable contracts;
- project [skills](../.agents/skills/) provide step-by-step procedures for repeatable work; and
- [`docs/agents/`](agents/) holds active plans and unresolved decisions, not an alternative description of the architecture.

Plans, code, tests, releases, or downstreams may temporarily differ from this design during a reviewed change.
Treat the difference as work to resolve, not permission to preserve accidental behavior or silently change the design.
If the intended direction changes, update this document for human agreement before implementing it.

This architecture does not decide production metadata meaning, review authority, migration, hosting, cutover, accessibility, privacy, or recovery ownership.
Those choices remain in [`open-decisions.md`](agents/open-decisions.md) until people resolve them.

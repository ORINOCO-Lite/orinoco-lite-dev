# Submodule commit restructuring

Restructure the selected 27 divergence commits into 17 commits.
Keep accepted upstream bases and effective source contents unchanged.
Pool UI receives the rewritten SHACL Vue gitlink.

| Repository | Before | After |
| --- | ---: | ---: |
| Pool UI | 13 | 5 |
| SHACL Vue | 6 | 8 |
| Query Things | 1 | 1 |
| WWW from model | 7 | 3 |

Local deployment configuration remains one deployment commit: it supplies the upstream reproduction baseline used to compare against Orinoco Lite.
Keep the existing pinned build label.
The existing Starter navigation argument-order bug requires a separate correction.

Each entry gives the resulting subject, original subjects, and changes.
Git retains the full messages and diffs.

## shacl-vue

fix(form): initialize the show-all-fields ref [intent:general]

> Fix show-all-fields ref initialization

Set the Vue ref value when initializing the form field display.

===========

build(deps): refresh frontend dependencies [intent:general]

> build(deps): refresh frontend dependencies

Refresh the locked frontend dependencies and include jsdom for browser-oriented regression tests.

===========

test(markdown): cover sanitized preview rendering [intent:general]

> build(deps): refresh frontend dependencies

Extract the existing Markdown preview renderer and exercise sanitization through jsdom.

===========

fix(links): restrict external links to HTTP schemes [intent:general]

> feat(editor): add static review bundle export

Reject unsafe record-derived URL schemes and isolate opened windows with noopener and noreferrer.

===========

fix(downloads): honor selection and release URLs [intent:general]

> feat(editor): add static review bundle export

Download only selected records.
Support named, formatted JSON downloads and release JSON and Turtle object URLs after use.

===========

fix(editor): respect disabled service and tokens [intent:general]

> feat(editor): add static review bundle export
> test(editor): cover static navigation after upstream rebase
> fix(editor): pass the token reset callback in navigation order
> fix(editor): keep related-record lookups local in static mode

Keep record lookup local when service access is disabled, clear disabled tokens, and hide token settings.
Cover navigation and related-record lookup without network requests.

===========

build(app): support pinned build metadata [intent:integration]

> feat(editor): add static review bundle export

Accept the supplied build timestamp and use a pinned-source branch label for reproducible integration builds.

===========

feat(editor): export static review bundles [intent:integration]

> feat(editor): add static review bundle export

Offer credential-free review-bundle downloads tied to the static record catalog, source paths and digests, and site commit.
Keep backend submission unavailable in patch-download mode.

===========

## pool.psychoinformatics.de-ui

build(config): copy external YAML configuration [intent:general]

> Copy external YAML configuration into UI builds

Include external YAML configuration in both editor build outputs.

===========

fix(build): clear generated runtime plugins [intent:general]

> fix(build): reset runtime plugins before bundling

Remove stale generated runtime plugins before copying the selected plugin set for each build.

===========

build(site): bundle local service configuration [intent:deployment]

> Track local service deployment configuration
> Bundle the deployment schema assets
> Declare the upstream record namespace
> Use local git-annex service for deployment

Reproduce the upstream service-backed deployment locally for comparison with Orinoco Lite.
Bundle the selected schema, UI configuration and logos; configure local record and Annex services and the record namespace.

===========

build(deps): select the Orinoco Lite editor [intent:integration]

> Track local service deployment configuration
> Point nested dependencies at leej3 mirrors
> build(deps): update shacl-vue dependency
> feat(editor): pin static review bundle export
> chore(git): move SHACL Vue mirror to ORINOCO-Lite
> test(editor): pin static navigation regression coverage
> fix(editor): pin the corrected static navigation call
> fix(editor): pin static related-record service isolation

Use the organization mirror and select the complete retained editor layer with one exact dependency pin.

===========

build(app): supply pinned build metadata [intent:integration]

> feat(editor): pin static review bundle export

Supply the wrapper commit timestamp and pinned branch label to both editor variants.

===========

## query-things

build(deps): allow consumer-selected client sources [intent:general]

> remove hard-coded git source

Let consumers select the dump-things-pyclient source instead of requiring a hard-coded Git URL.

===========

## www-from-model

fix(publications): fall back to issued dates [intent:general]

> fix(publications): display retained issued dates

Use dcterms:issued when a publication-generation date is absent.

===========

fix(navigation): show mobile menu labels [intent:general]

> fix(navigation): show menu labels on mobile

Show readable mobile menu labels while retaining icon-only desktop navigation.

===========

fix(site): resolve graph assets under the base URL [intent:general]

> fix(site): resolve graph assets beneath the site base URL

Render the graph through a Hugo shortcode and resolve graph.js beneath the configured site base URL.

===========

[DROP — canceled Congo pin change]

> fix(theme): retain Congo compatibility with Hugo 0.161
> Revert "fix(theme): retain Congo compatibility with Hugo 0.161"

Remove the original change and its exact revert together; their net effect is empty.

===========

[DROP — canceled Congo branch-hint removal]

> chore(git): remove the mutable Congo branch hint
> Revert "chore(git): remove the mutable Congo branch hint"

Remove the original change and its exact revert together; their net effect is empty.

===========

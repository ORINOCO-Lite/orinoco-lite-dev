# Milestone 2 acceptance

Status: accepted local checkpoint on 2026-08-11

Milestone 2 restored the reviewed legacy-equivalent CON public experience on top of the generalized upstream-compatible profile.
The user accepted this milestone as the baseline for broader publication ingestion and deployment work.

## Accepted commits

- parent `codex/full-con-migration`: `7ce44a28c13954e514c8b7e9ab6f1eaade77d891`;
- site `codex/full-con-migration`: `d60f274b4bf8af3e513d83d1727cfe3e6c9bb8af`;
- reviewed upstream website base: `a9ac9d5abc3898fd13d9b8392008f0c323c8dcd8`; and
- accepted clean-migration checkpoints remain the commits recorded in `docs/full-con-migration.md`.

These refs are historical checkpoints.
Milestone 3 descends from them on new branches and must not rewrite them.

## Accepted coverage

The accepted site contains:

- 60 canonical records and 8 reference records;
- all 33 reviewed people in the four legacy presentation groups;
- all 23 reviewed featured projects in the six legacy categories;
- 60 graph nodes and 93 native relationship edges;
- 59 generated metadata pages;
- the homepage, About, People, Projects, Engage, Support, Contact, and Explore experience; and
- 71 declared assets with explicit ordinary-Git, annex, unavailable, and absent-in-source handling.

The organization remains graph-only because the upstream profile has no organization detail route.
The distinguished `xyzrins:.` project remains the canonical homepage root.

## Acceptance evidence

The final local acceptance run passed:

- 82 unit and contract tests;
- 7 Playwright scenarios across Chromium and WebKit;
- two byte-identical metadata projection renders;
- two byte-identical 335-file root static builds;
- the project-path static build and link audit;
- exact graph, route, collection, editor-boundary, and German-isolation checks; and
- cleanup checks for services, probes, tokens, temporary hydration remotes, and local-clone state.

## Carried review items

The following are reviewed differences rather than Milestone 2 acceptance failures:

- EMBER's Brock Wester association and OpenNeuro's Russell Poldrack association remain deferred until supporting-person visibility is decided;
- Chris Markiewicz's exact legacy portrait is unavailable;
- four projects have no source artwork and use the declared neutral fallback;
- the legacy Twitter link remains omitted pending ownership review;
- sixteen selected assets depend on declared read-only annex remotes; and
- publication breadth, static hosting, and downloadable review changes move to Milestone 3.

Human review may correct any of these matters through ordinary Milestone 3 content commits.
It does not reopen or rewrite the accepted checkpoint.

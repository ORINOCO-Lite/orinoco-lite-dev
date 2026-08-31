# Milestone 3 decision register

Status: implementation complete; draft human review open

Consolidated prioritized review queue: [`open-decisions.md`](../open-decisions.md).
This file remains the authoritative source record for Milestone 3 decision IDs and evidence.

This register distinguishes decisions already authorized by the user from questions that require human review.
Implementations must preserve unresolved source evidence and fail closed rather than invent an answer.

## Accepted decisions

| ID | Decision | Consequence |
| --- | --- | --- |
| M3-D001 | Milestone 2 is accepted at the commits recorded in `milestone-2-acceptance.md`. | Milestone 3 uses new successor branches and does not rewrite the accepted parent or site refs. |
| M3-D002 | Broader publication coverage comes from repeatable public Zotero API ingestion, not from copying the old snapshot alone. | The source snapshot records pagination, item and library versions, collection membership, and capture metadata before transformation. |
| M3-D003 | The only pull request in this milestone targets `con/orinoco-lite-dev:main`. | Required submodule commits may be pushed for gitlink availability, but no submodule PR is opened. |
| M3-D004 | The public preview is the parent repository's GitHub Pages project site. | The canonical preview base path is `/orinoco-lite-dev/`; no custom domain or production redirect is configured. |
| M3-D005 | Browser editing remains credential-free. | SHACL Vue loads public static data and downloads a review bundle; a local authenticated checkout prepares any later PR. |
| M3-D006 | Hosted authentication and direct pull-request creation remain deferred. | No OAuth, GitHub App, browser token, or persistent metadata write service is introduced. |
| M3-D007 | Production dependency advisories are resolved by updating the pinned SHACL Vue stack. | Exact dependency and lockfile changes must pass upstream and parent browser regression tests; unsupported overrides are not used, and any development-only exception is recorded separately. |
| M3-Q011 (resolved) | Downloaded editor patches target the canonical paths in `centerforopenneuroscience.org`. | The site repository owns the canonical YAML and its active branch remains a direct, rebasable descendant of `www-from-model`; the account mirror is transport, not a competing source of truth. |
| M3-Q013 (resolved) | Keep canonical content in the site repository and update its gitlink deliberately in the coordinating parent. | This is ordinary submodule coordination within the multi-repository parent, not a special two-repository architecture. Legacy CON branches and tags remain permanently reachable as disconnected history and are not merged into the upstream-derived branch. |
| M3-Q014 (resolved) | Publishing canonical YAML verbatim in the static editor catalog is acceptable. | The records are already public website inputs; the catalog intentionally makes bulk access and reuse more convenient, subject to the normal rule that private or embargoed material must never enter canonical public YAML. |

## Existing source-policy decisions retained

The Zotero importer retains the reviewed source decisions already recorded in `submodules/dump-research-info`:

- Zotero remains authoritative for the CON publication feed;
- ingestion and curation remain separate;
- creator mappings are exact and reviewed, never fuzzy at promotion time;
- all named collections except the reviewed `External` exclusion are eligible, while unfiled or unsupported items go to review; and
- Zotero writes require a separate reviewed-additions record and are not part of this milestone's ingestion path.

## Human review required

| ID | Question | Safe implementation default |
| --- | --- | --- |
| M3-Q001 | Which unresolved Zotero creator identities should become new public people records rather than remain literal source creators? | Do not create people automatically; retain the publication candidate and unresolved creator evidence. |
| M3-Q002 | Which DOI duplicates represent the same publication, alternate versions, corrections, or distinct outputs? | Merge only the transformer's reviewed exact duplicate class; report every ambiguous group. |
| M3-Q003 | Should missing or ambiguous publication venues be modeled from authoritative registry enrichment? | Retain the Zotero venue literal and queue a venue decision; do not invent ISSNs or venue identity. |
| M3-Q004 | Should items in `External`, unfiled, or unsupported Zotero categories appear publicly? | Follow the existing eligibility rule and report them without publishing them. |
| M3-Q005 | Are the two deferred project-person associations now ready for public supporting-person records? | Keep the Milestone 2 deferrals until a content owner approves visibility. |
| M3-Q006 | Is the unavailable Chris Markiewicz portrait replaceable with a newly reviewed image and license? | Keep the neutral declared fallback. |
| M3-Q007 | Is the legacy CON social-media account still owned and appropriate to publish? | Keep the Twitter link omitted. |
| M3-Q008 | Is continued read-only remote custody sufficient for the sixteen annex-backed assets? | Hydrate by exact key and digest for the preview; do not claim durable custody. |
| M3-Q009 | After review, should the preview replace the production custom-domain site? | Do not change DNS, redirects, `CNAME`, or production settings in Milestone 3. |
| M3-Q010 | Who may approve canonical publication and editorial changes after the draft PR is opened? | Require ordinary human PR review; do not encode an unapproved CODEOWNERS or branch-protection policy. |
| M3-Q012 (resolved) | Should Pages continue to deploy from `codex/milestone-3` after review? | Retain the branch and deployment history as frozen evidence, disable automatic push and pull-request deployment, and provide only an explicitly dispatched engineering preview. The supported public integration preview is the downstream consumer. |
| M3-Q015 | Should the `github-pages` environment require named deployment reviewers? | Use ordinary repository controls without inventing a reviewer policy; add environment protection only after maintainers choose the approvers. |
| M3-Q016 | May deployment configuration or schema-authored markup become writable by untrusted users in a later hosted editor? | Treat those inputs as trusted, pinned build inputs in this static preview; require an explicit sanitization boundary before making them user-controlled. |
| M3-Q017 | Is the stable documentation toolchain's four-item development-only advisory exception acceptable until VitePress publishes a supported patched line? | Keep documentation out of the deployed runtime, require a zero-finding production audit, and do not force an unsupported Vite or VitePress alpha override. |
| M3-Q018 | May the preview editor continue loading the Roboto font from Google? | Allow it in this review preview, but vendor or remove the font before claiming an offline or independently archived deployment. |

## Completion updates

The exact ingestion totals, exclusions, dependency-audit results, public review links, workflow evidence, and remaining debt are recorded in [`milestone-3-acceptance.md`](milestone-3-acceptance.md).
Questions M3-Q011, M3-Q013, and M3-Q014 are resolved above.
All other M3 questions remain open for human review; none is silently resolved by the preview implementation.
M3-Q012 is resolved by the HR-004 decision in the consolidated queue.

# Milestone 3 decision register

Status: implementation complete; draft human review open

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
| M3-Q011 | Which public site repository should receive a patch downloaded by the static editor? | Generate a repository-relative patch at the pinned site commit, but do not claim a contribution target until the CON repository or account mirror is selected. |
| M3-Q012 | Should Pages continue to deploy from `codex/milestone-3` after review? | Use that branch only to bootstrap the pre-merge preview; then remove its push trigger and deploy only from `main`. |
| M3-Q013 | Should canonical content retain the site-repository plus parent-gitlink review boundary? | Preserve the proven two-repository ownership in this milestone; consider moving content only as a separately reviewed architecture change. |
| M3-Q014 | May the Pages editor publish a bulk catalog containing the canonical YAML verbatim? | Permit it because the YAML is already public website input, but call out the increased convenience of bulk download during human review. |
| M3-Q015 | Should the `github-pages` environment require named deployment reviewers? | Use ordinary repository controls without inventing a reviewer policy; add environment protection only after maintainers choose the approvers. |
| M3-Q016 | May deployment configuration or schema-authored markup become writable by untrusted users in a later hosted editor? | Treat those inputs as trusted, pinned build inputs in this static preview; require an explicit sanitization boundary before making them user-controlled. |
| M3-Q017 | Is the stable documentation toolchain's four-item development-only advisory exception acceptable until VitePress publishes a supported patched line? | Keep documentation out of the deployed runtime, require a zero-finding production audit, and do not force an unsupported Vite or VitePress alpha override. |
| M3-Q018 | May the preview editor continue loading the Roboto font from Google? | Allow it in this review preview, but vendor or remove the font before claiming an offline or independently archived deployment. |

## Completion updates

The exact ingestion totals, exclusions, dependency-audit results, public review links, workflow evidence, and remaining debt are recorded in [`milestone-3-acceptance.md`](milestone-3-acceptance.md).
Questions M3-Q001 through M3-Q018 remain open for human review; none is silently resolved by the preview implementation.

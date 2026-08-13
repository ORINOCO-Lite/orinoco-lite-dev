# Orinoco Lite human-review decision queue

Status: open for comprehensive human review

Review snapshot: 2026-08-13

This is the single working list of unresolved **human choices** accumulated through the clean migration, full migration, complete-content migration, and single-repository distribution work.
It separates policy from facts with an objectively testable answer.
Release-coordinate repairs, documentation drift, CI results, and other engineering tasks belong in [`milestone-4-acceptance.md`](milestone-4-acceptance.md) or an implementation issue, not in this queue.

## Review rules

- Work from P0 through P2.
A recommendation is a safe default, not approval on the reviewer's behalf.
- Resolve one ID at a time.
For compound subject areas, the IDs are deliberately atomic so one answer can be accepted while another is deferred.
- Record an outcome, rationale, reviewer, date, and resulting follow-up.
Update the originating decision register in the same reviewed change.
- A resolution in this document authorizes **policy or planning only**.
It does not authorize changing the real-site repository, its refs, settings, Pages configuration, DNS, or deployment.
Read-only evidence checks remain within the existing boundary; any mutation still requires separate, explicit authorization with exact targets.

Priorities mean:

- **P0 — close the current engineering review:** answer before Milestone 4 and engineering pull request 5 can be closed.
- **P1 — before production graduation:** may remain open for the public test consumer, but must be resolved before changing or presenting the real site as production-approved.
- **P2 — strategic:** deliberate future choices that do not block the current distribution or a production graduation unless a later milestone activates them.

## Executive queue

| ID | Priority | Domain | Decision |
| --- | --- | --- | --- |
| HR-001 | P0 | Architecture | Accept, conditionally accept, or reject the Milestone 4 distribution and dispose of engineering PR 5 |
| HR-003 | P0 | Licensing | Establish rights authority and choose an interim or permanent license matrix |
| HR-004 | P0 | Hosting cleanup | Retire, archive, or retain the legacy engineering Pages preview |
| HR-101 | P1 | Graduation | Choose a history-preserving real-site migration topology |
| HR-102 | P1 | Hosting | Choose production hosting, domain cutover, and rollback |
| HR-103a | P1 | Governance | Name canonical content and presentation approvers |
| HR-103b | P1 | Governance | Name deployment approvers and production protection rules |
| HR-104a | P1 | Identity | Define when a source creator becomes a public person |
| HR-104b | P1 | Identity | Decide Brock Wester's public record and associations |
| HR-104c | P1 | Identity | Decide Russell Poldrack's public record and associations |
| HR-104d | P1 | Authorship | Decide how unresolved literal creators appear publicly |
| HR-105a | P1 | Publications | Define DOI/version identity policy |
| HR-105b | P1 | Publications | Define venue authority and publishing-activity modeling |
| HR-105c | P1 | Topics | Define tag-to-topic vocabulary and promotion policy |
| HR-106 | P1 | Publications | Confirm collection and item eligibility |
| HR-107a | P1 | Rights | Decide the Chris Markiewicz portrait replacement |
| HR-107b | P1 | Identity | Decide whether to publish the legacy social account |
| HR-108 | P1 | Assets | Choose durable custody for 16 digest-addressed content assets |
| HR-109a | P1 | Editor | Define supported review-bundle size and transaction behavior |
| HR-109b | P1 | Trust | Define whether deployment/schema inputs may become user-writable |
| HR-112 | P1 | Security policy | Set the development-toolchain advisory exception policy |
| HR-113 | P1 | Privacy | Choose the deployed site's external-resource policy |
| HR-114 | P1 | Releases | Define release stewardship, compatibility, and support lifetime |
| HR-115a | P1 | Presentation | Accept or revise production branding, information architecture, responsive design, and legacy parity |
| HR-115b | P1 | Accessibility | Define and accept the production accessibility standard |
| HR-201 | P2 | Hosted editing | Keep bundle handoff or add authenticated branch/PR creation |
| HR-202a | P2 | Packaging | Decide whether to ship an optional full-stack image |
| HR-202b | P2 | Services | Decide whether to operate a persistent public service |
| HR-203 | P2 | Generated data | Reconsider committed projections after an equivalent review model exists |
| HR-204a | P2 | Updates | Choose manual coordinates or reviewed release discovery |
| HR-204b | P2 | Automation | Choose a future update credential model |
| HR-204c | P2 | Hosting | Decide whether per-PR deployed previews are worthwhile |
| HR-205 | P2 | Support | Add platforms beyond macOS ARM64 and Linux x86-64 |
| HR-206 | P2 | Upstream | Prioritize a LinkML named-recursive-alias contribution |
| HR-210 | P2 | Test fixture | Choose the long-term role of the full-content test consumer |
| HR-211 | P2 | Presentation | Decide whether the organization record needs a page |

## P0 — close the current engineering review

### HR-001 — Accept the distribution and dispose of PR 5

**Status:** open

**Question:** Does the implemented engine/runtime/template/ordinary-consumer architecture satisfy Milestone 4, and should [`con/orinoco-lite-dev#5`](https://github.com/con/orinoco-lite-dev/pull/5) be merged, returned for named changes, or retained as an unmerged engineering branch?

**Current behavior:** Immutable engine/runtime releases, a versioned template, the complete accepted content and test snapshot in an ordinary repository, real framework-update pull requests, and public project Pages have exercised the distribution.
The real site remains outside the implementation scope.
Technical success does not approve production content or grant reuse rights.

**Options:**

1. Accept and merge after all P0 decisions have recorded outcomes.
2. Accept conditionally with named, bounded follow-ups that do not change the architecture.
3. Request specific architectural changes and identify which accepted M4 decision they supersede.
4. Preserve the branch and releases as evidence without merging PR 5.

**Recommended default:** Option 2, provided HR-003 records either an approved license matrix or an explicit interim “no reuse rights granted” posture.
Keep technical distribution acceptance separate from content and production approval.

**Evidence:** [`milestone-4.md`](milestone-4.md), [`milestone-4-acceptance.md`](milestone-4-acceptance.md), [`milestone-4-decisions.md`](milestone-4-decisions.md), the [test consumer](https://github.com/con/test-orinoco-downstream-website), and its [public Pages site](https://con.github.io/test-orinoco-downstream-website/).

**Resolution:**

- Outcome:
- Conditions or requested changes:
- Decided by / date:
- Follow-up:

### HR-003 — Establish authority and a project license matrix

**Status:** open

**Question:** Who has authority to license each surface, what upstream terms or asset-specific exceptions constrain that authority, and under what terms may people use, modify, and redistribute:

1. engine and engineering code;
2. template, updater, and generic workflows;
3. canonical metadata, editorial prose, and generated data products; and
4. images, branding, themes, and imported presentation assets?

**Current behavior:** No repository-wide license is declared.
Component license inventories do not assign rights to otherwise unlicensed Orinoco Lite code or CON content.
Public visibility is therefore evidence and evaluation access, not an implied permission to reuse.

**Options:** Adopt a code/content/assets matrix after confirming rightsholders; adopt a compatible project-wide license where authority permits; or explicitly retain no general reuse grant with item-level exceptions.
An interim answer may be the last option, but it must be stated rather than inferred.

**Recommended default:** First record rightsholder/relicensing authority and all incompatible or unknown upstream terms, then approve an explicit matrix.
Until then, do not publish to a general package index, invite third-party reuse, or describe public content as openly licensed.

**Evidence:** [`packages/orinoco-lite/README.md`](../packages/orinoco-lite/README.md), [`../release/runtime-licenses/README.md`](../release/runtime-licenses/README.md), and the [consumer framework notice](https://github.com/con/test-orinoco-downstream-website/blob/main/site/framework/README.md).

**Resolution:**

- Engine/template/content/media rightsholder(s):
- Upstream constraints and exceptions:
- Engine/engineering license:
- Template/updater license:
- Metadata/editorial license:
- Media/presentation policy:
- Interim posture, if permanent terms remain open:
- Decided by / date:

### HR-004 — Dispose of the legacy engineering Pages preview

**Status:** accepted

**Question:** After Milestone 4 review, should the historical `codex/milestone-3` engineering preview be retired, retained as frozen evidence, or kept as an actively supported review surface?

**Current behavior:** The ordinary test consumer is the supported downstream preview.
M4 prevents the legacy Pages workflow from running on PR 5, but that does not itself decide the older review surface's lifecycle.

**Decision:** Retain the branch and deployment history as immutable evidence, remove or disable automatic push and pull-request deployment triggers, and provide an explicitly dispatched engineering preview for candidate builds.
The preview is an ephemeral artifact or manually served build; it is not a downstream update, does not commit generated consumer state, and does not deploy the real site.
Point supported integration and publication review to the downstream consumer and its framework-update pull requests.
Do not delete preservation refs.

The engineering preview may use a separate, engineering-owned **production-shaped corpus**: a small frozen corpus derived from real-world content structures, bound to an exact source commit and digest, with provenance and any required rights or de-identification recorded.
It is not a content selection policy, a replacement for the complete downstream snapshot, or a dependency on the real site or current test consumer.

Engineering validation therefore has three content layers:

- a synthetic fixture for exhaustive pathological and negative cases on every pull request;
- the production-shaped corpus for messy real-world structures and representative rendering on pull requests or a scheduled engineering run; and
- the complete downstream consumer for release-candidate, update, browser, rollback, and publication-boundary evidence.

**Evidence:** M3-Q012 in [`milestone-3-decisions.md`](milestone-3-decisions.md) and M4-I010 in [`milestone-4-decisions.md`](milestone-4-decisions.md).

**Resolution:**

- Outcome: accepted with an opt-in engineering preview and a separate production-shaped corpus.
- Retained URL/ref: historical Milestone 3 branch and artifacts remain frozen evidence; the supported public integration preview remains the downstream consumer.
- Trigger cleanup, if any: disable automatic legacy preview deployment; expose only an explicit candidate-preview dispatch.
- Corpus boundary: engineering-owned, immutable, provenance-bound, and rights-reviewed; never coupled to the real site or current consumer.
- Decided by / date: John Lee / 2026-08-13

## P1 — before production graduation

### HR-101 — Choose the real-site migration topology

**Status:** open

**Question:** How should the ordinary template-derived tree enter the existing real-site repository while preserving legacy refs, accepted checkpoints, canonical source authority, and an exact rollback point?

**Current behavior:** The test consumer proves the desired end-state topology; the real site remains an untouched multi-history repository.
M4 authorizes no real-site operation.

**Recommended default:** Write a separate graduation plan naming every source and destination commit.
Existing accepted and preservation refs must never be moved, deleted, or force-updated.
An unpublished candidate branch may use a reviewed ancestry-construction technique, but publication must be additive and the exact pre-cutover rollback coordinate must be recorded first.

**Resolution:** topology; canonical branch/source; preserved refs; rollback coordinate; reviewer/date; follow-up.

### HR-102 — Choose production hosting and cutover

**Status:** open

**Question:** Which branch and workflow deploy production, when does the custom domain move, should old and new sites coexist, and what triggers rollback?

**Current behavior:** The test consumer deploys project Pages from its reviewed default branch without `CNAME`, DNS changes, redirects, or a production domain.

**Recommended default:** Use a separately addressable production candidate before any domain switch.
Require content, rights, presentation, artifact, deployment, and rollback approval before changing DNS or `CNAME`.

**Evidence:** M3-Q009 in [`milestone-3-decisions.md`](milestone-3-decisions.md) and the deferred boundary in [`milestone-4.md`](milestone-4.md).

**Resolution:** platform/workflow; branch; coexistence plan; DNS owner; rollback trigger; reviewer/date.

### HR-103a — Name content and presentation approvers

**Status:** open

**Question:** Who may approve canonical metadata, editorial prose, media, presentation overrides, and content-policy changes, and who acts as backup?

**Recommended default:** Name people who explicitly accept the responsibility, separate content approval from framework release approval, and encode the result with `CODEOWNERS` only after the ownership scopes are agreed.

**Evidence:** M3-Q010 in [`milestone-3-decisions.md`](milestone-3-decisions.md).

**Resolution:** metadata approvers; editorial/media approvers; presentation approvers; backups; enforcement; reviewer/date.

### HR-103b — Name deployment approvers and production protections

**Status:** open

**Question:** Who may approve a production Pages deployment, which checks are required, and may administrators bypass review or environment protection?

**Current behavior:** Test/template protections, including administrator enforcement being disabled, are settled in M4-I008.
They are integration-fixture controls, not a production governance decision.

**Recommended default:** Require a named deployment owner, formal approval, green supported-platform checks, conversation resolution, and a documented emergency path.
Make production bypass policy explicit rather than inheriting the test fixture's settings.

**Evidence:** M3-Q015 and M4-I008 in the two decision registers.

**Resolution:** approvers; required checks; administrator/emergency policy; environment protection; reviewer/date.

### HR-104a — Define public-person creation

**Status:** open

**Question:** When should an unresolved source creator become a canonical public person record?

**Current behavior:** No person is created through fuzzy matching; unresolved creator evidence remains source data.

**Recommended default:** Require exact evidence and human identity review.
Never create a public identity merely to make authorship counts complete.

**Evidence:** M3-Q001 in [`milestone-3-decisions.md`](milestone-3-decisions.md).

**Resolution:** eligibility/evidence rule; approver; reviewer/date.

### HR-104b — Decide Brock Wester's public identity

**Status:** open

**Question:** Should Brock Wester receive a public supporting-person record and the associated project/publication relationships?

**Current behavior:** The record and associations remain deferred.

**Recommended default:** Keep deferred until identity, desired public visibility, and associations are individually confirmed.

**Evidence:** M3-Q005 and the consumer's [`metadata/provenance/projects.yaml`](https://github.com/con/test-orinoco-downstream-website/blob/main/metadata/provenance/projects.yaml).

**Resolution:** publish/omit; approved associations; approver/date.

### HR-104c — Decide Russell Poldrack's public identity

**Status:** open

**Question:** Should Russell Poldrack receive a public supporting-person record and the associated project/publication relationships?

**Current behavior and recommendation:** Same safe boundary as HR-104b; decide independently because the evidence or desired visibility may differ.

**Evidence:** M3-Q005 and the consumer provenance cited above.

**Resolution:** publish/omit; approved associations; approver/date.

### HR-104d — Choose unresolved-author presentation

**Status:** open

**Question:** Should publications display literal source creators who are not reconciled to canonical public identities, show only reconciled people, or use another explicit representation?

**Current behavior:** Canonical relationships include only reconciled people; literal unresolved evidence is retained for review.

**Recommended default:** Preserve authorship completeness visibly without inventing identity records, provided the source strings and presentation can be clearly distinguished from curated people.

**Evidence:** M3-Q001 and the publication counts in [`milestone-3-acceptance.md`](milestone-3-acceptance.md).

**Resolution:** display rule; provenance requirements; approver/date.

### HR-105a — Define DOI and version identity

**Status:** open

**Question:** Which DOI collisions represent one work, alternate versions, corrections, or distinct outputs?

**Current behavior:** Only reviewed deterministic duplicate classes are merged; six ambiguous groups remain evidence.

**Recommended default:** Review each ambiguous group and record a reusable rule only when the cases support one.

**Evidence:** M3-Q002 and [`milestone-3-acceptance.md`](milestone-3-acceptance.md).

**Resolution:** group outcomes; reusable rule; approver/date.

### HR-105b — Define venue authority and activity modeling

**Status:** open

**Question:** When may registry enrichment establish a venue identity, and what is the canonical publishing-activity/venue model?

**Current behavior:** Source venue literals are retained without inventing ISSNs or separate venue identities.

**Recommended default:** Require an authoritative, provenance-recorded identifier before promotion; otherwise retain the literal on the publication.

**Evidence:** M3-Q003.

**Resolution:** model; authorities; enrichment rule; approver/date.

### HR-105c — Define controlled-topic promotion

**Status:** open

**Question:** Which free-form Zotero tags may become controlled public topics, and under which vocabulary and mapping process?

**Current behavior:** Only the reviewed Neuroimaging topic is public; unresolved tag observations remain provenance.

**Recommended default:** Promote only through a versioned reviewed vocabulary; never turn an arbitrary new source tag into a public topic automatically.

**Evidence:** The consumer's [`metadata/provenance/publications.yaml`](https://github.com/con/test-orinoco-downstream-website/blob/main/metadata/provenance/publications.yaml).

**Resolution:** vocabulary; mappings; unknown-tag behavior; approver/date.

### HR-106 — Confirm publication eligibility

**Status:** open

**Question:** Which Zotero collections and item forms qualify, especially `External`, unfiled, unsupported, and future unknown categories?

**Current behavior:** Reviewed named CON collections are eligible, `External` is excluded, and unfiled/unsupported items enter a review queue.

**Recommended default:** Retain that allowlist and fail unknown future labels into review until a content owner approves a versioned policy.

**Evidence:** M3-Q004.

**Resolution:** eligible/excluded categories; unknown handling; owner/date.

### HR-107a — Decide the missing portrait

**Status:** open

**Question:** Should the unavailable Chris Markiewicz portrait be replaced, and which image has confirmed identity, source, and redistribution rights?

**Current behavior:** The site uses a neutral declared fallback.

**Recommended default:** Retain the fallback until a specific licensed replacement is reviewed.

**Evidence:** M3-Q006.

**Resolution:** image/source/license or omit; approver/date.

### HR-107b — Decide the legacy social account

**Status:** open

**Question:** Is the legacy CON Twitter/X account still organization-controlled, current, and appropriate to publish?

**Current behavior:** The link is omitted.

**Recommended default:** Keep it omitted until an accountable owner confirms control and continued use.

**Evidence:** M3-Q007.

**Resolution:** publish/omit; account owner; verification date.

### HR-108 — Choose durable custody for 16 content assets

**Status:** open

**Question:** Is exact read-only hydration sufficient, or should the remaining 16 large content assets move into ordinary Git, an immutable release, or an organization-controlled object store?

**Current behavior:** They hydrate by exact size and digest and work offline after warming.
The separate 13 framework pointers are already verified ordinary Git bytes; a basic site build does not require git-annex.

**Recommended default:** Current hydration is sufficient for the test fixture.
Choose organization-controlled digest-addressed custody before claiming cold offline or long-term archival independence.

**Evidence:** M3-Q008 and M4-I002.

**Resolution:** custody model; owner; retention promise; deadline; reviewer/date.

### HR-109a — Define bundle transaction behavior

**Status:** open

**Question:** Is one record the supported production review unit, and must a multi-record application be repository-wide atomic before it is supported?

**Current behavior:** Each bundle is source-commit/path/digest bound and each write validates, but a multi-record batch is not a repository transaction.

**Recommended default:** Support one-record review normally and treat any multi-record bundle as an explicitly reviewed batch until atomic application is proven.

**Resolution:** supported size; failure/rollback rule; approver/date.

### HR-109b — Define the trusted-input boundary

**Status:** open

**Question:** May deployment configuration or schema-authored markup ever become writable by an untrusted editor?

**Current behavior:** They are trusted pinned inputs; the browser edits only public canonical records and grants no publication authority.

**Recommended default:** Keep them outside the user-writable surface unless a separate sanitization, authorization, and threat model is accepted.

**Evidence:** M3-Q016.

**Resolution:** writable surfaces; trust/sanitization rule; approver/date.

### HR-112 — Set the development-advisory exception policy

**Status:** open; current audit evidence required

**Question:** If documentation/editor development dependencies have advisories that do not enter the deployed runtime, what severity, duration, compensating controls, and removal deadline make a temporary exception acceptable?

**Current behavior:** M3 recorded a bounded four-item development-only VitePress exception and required a zero-finding production audit.
Whether the same findings still exist is an objective re-audit; the acceptable exception policy is a human decision.

**Recommended default:** Refresh the audit first.
Mark M3-Q017 superseded if the findings are gone.
Otherwise accept only a time-bounded documented exception with a named owner and a zero-finding production dependency set.

**Evidence:** M3-Q017 and the dependency evidence in [`milestone-3-acceptance.md`](milestone-3-acceptance.md).

**Resolution:** current findings; threshold; expiry; owner; reviewer/date.

### HR-113 — Choose the external-resource and privacy posture

**Status:** open

**Question:** May deployed pages contact third-party services for fonts or other presentation resources, or must a complete view be self-contained?

**Current behavior:** The main site is self-contained, but the current editor requests Google-hosted Roboto resources.
That reveals a browser request to a third party and makes the intended typography unavailable offline.

**Recommended default:** Use a local/system font stack unless the visual value justifies vendoring properly licensed files.
Do not silently retain external requests in a site whose static and warmed-cache offline behavior is otherwise an explicit property.

**Evidence:** M3-Q018 and the [public editor](https://con.github.io/test-orinoco-downstream-website/edit/).

**Resolution:** allowed origins; vendor/remove/exception; privacy notice; license source; reviewer/date.

### HR-114 — Define release stewardship and compatibility

**Status:** open

**Question:** Who may approve and publish engine/runtime/template releases; what evidence is mandatory; how long are versions and review-bundle formats supported; and how are urgent security updates distinguished from optional presentation updates?

**Current behavior:** Builds are reproducible and releases immutable, but no human stewardship, support-lifetime, deprecation, or downstream update cadence has been approved.
The concrete template identity drift is an implementation defect, not itself the policy answer.

**Recommended default:** Name at least two release roles, require the existing deterministic and cross-platform evidence, define a minimum supported predecessor for rollback, give deprecations a documented migration window, and permit expedited security proposals without automatic merge.
Keep GitHub Releases as the distribution channel until HR-003 permits broader publication.

**Evidence:** M4-I007 and the release contracts in [`milestone-4.md`](milestone-4.md) and [`packages/orinoco-lite/README.md`](../packages/orinoco-lite/README.md).

**Resolution:** approvers; required evidence; version/support lifetime; deprecation policy; security path; distribution channels; reviewer/date.

### HR-115a — Accept the production presentation

**Status:** open

**Question:** Is the current branding, navigation, information architecture, and responsive design acceptable for production, and how much visual parity with the legacy site is required?

**Current behavior:** The test consumer proves routes, assets, browser behavior, and selected accessibility contracts.
Presentation follow-ups have been reviewed separately, but no human has accepted the complete result as the production design.

**Recommended default:** Conduct a focused review at representative desktop and mobile widths across the homepage, core record types, graph, and editor.
Accept intentional modernization rather than requiring pixel parity, but record any launch-blocking design defects explicitly.

**Evidence:** The presentation deferrals in [`milestone-1-progress.md`](milestone-1-progress.md), the full consumer, and M4 acceptance browser evidence.

**Resolution:** accepted surfaces; required changes; legacy-parity expectation; approver/date.

### HR-115b — Define and accept production accessibility

**Status:** open

**Question:** Which accessibility standard and testing evidence must the production site satisfy, and does the current site meet it?

**Current behavior:** Automated browser tests cover selected roles, accessible names, keyboard-relevant controls, and content routes, but no human has accepted a production-wide conformance target or completed a focused assistive-technology review.

**Recommended default:** Adopt WCAG 2.2 AA as the review target, document any justified exceptions, and test keyboard navigation, landmarks, focus, contrast, zoom/reflow, reduced motion, alternative text, and core screen-reader paths separately from visual preference.

**Resolution:** standard; reviewed surfaces/assistive technologies; exceptions; required changes; approver/date.

## P2 — strategic decisions

These remain deferred until a later milestone activates their scope.

### HR-201 — Hosted authenticated editing

Keep credential-free bundle download and local review, or introduce a least-privilege authenticated branch/PR flow after a concrete user need and threat model exist.

### HR-202a — Optional full-stack packaging

Decide whether the optional Dump Things and SHACL Vue service stack merits a digest-pinned multi-architecture image for local/advanced deployments.

### HR-202b — Persistent service operation

Separately decide whether CON should operate any persistent public metadata or editing service.
Static build, Pages, and bundle editing need none today.

### HR-203 — Lifecycle of committed projections

Reconsider committed `generated/projection` only after another design proves equivalent stale-output rejection, reviewability, source binding, and rollback.

### HR-204a — Release discovery

Choose among manual immutable coordinates, a scheduled workflow, dependency automation, or another reviewed discovery mechanism.
Discovery must not weaken tag immutability, ownership, review, or the no-auto-merge boundary.

### HR-204b — Automation credentials

Choose a future narrowly scoped credential model only if the existing manually dispatched `GITHUB_TOKEN` update proposal is insufficient.

### HR-204c — Per-PR deployed previews

Decide whether distinct deployable PR URLs justify a new hosting and isolation model.
Default-branch-only Pages remains settled meanwhile.

### HR-205 — Additional supported platforms

Add an OS/architecture only after the complete release and consumer contract passes there continuously.
Distinguish “may work” from “supported.”

### HR-206 — Upstream recursive-alias work

Decide whether to file, fund, or contribute the proven LinkML named-recursive- alias change.
The bounded workaround remains until the objective removal test passes.

### HR-210 — Long-term test-consumer role

Decide whether the full-content public consumer remains a permanent update and compatibility fixture after real-site graduation, becomes synthetic, or is archived.
The intrusive banner question is settled by the reviewed presentation change unless explicitly reopened.

### HR-211 — Organization page

Reconsider a public organization route only when reviewed content and an information-architecture purpose exist.
The current graph-only organization record remains accepted meanwhile.

## Future candidates — not active decisions

Grants, CVs, annual reports, secondary projections, a separate metadata repository, and a formally supported RDF/JSONL interface are roadmap candidates, not one answerable decision.
Create separate IDs only when a milestone proposes a concrete scope.

## Settled constraints — do not ask again without new evidence

- The consumer contains **all** accepted Milestone 3 content and tests, not a representative subset.
- The template is content-neutral; a downstream is one ordinary Git repository without submodules or gitlinks.
- A locked engine, immutable runtime, versioned Copier source, and full-SHA reusable workflow form the release boundary.
- Generated projections remain committed initially.
- Static validate/build/preview/Pages/editor operations require no persistent service.
- Framework updates create pull requests and never auto-merge.
- Pages deploys only reviewed default-branch code, not PR code.
- Public canonical YAML may appear in the static editor catalog.
- Local output is host-neutral; Pages uses an explicit project-path base.
- The 13 inherited framework pointers are verified ordinary Git bytes.
- The source Things Schema and exact `dlthings:*` CURIE contract remain pinned.
- The LinkML recursion workaround has an objective removal test.
- Test/template branch controls, including M4-I008's administrator setting, are accepted fixture defaults unless explicitly superseded.
- Milestone 4 authorizes no real-site operation or production cutover.

## Source-ID crosswalk

This table makes completeness auditable.
“Settled” means the source register already contains the answer; it is not an omitted open choice.

| Source | Current disposition |
| --- | --- |
| M3-Q001 | HR-104a public-person rule and HR-104d unresolved-author display |
| M3-Q002 | HR-105a DOI/version identity |
| M3-Q003 | HR-105b venue/activity model |
| M3-Q004 | HR-106 collection/item eligibility |
| M3-Q005 | HR-104b Brock Wester and HR-104c Russell Poldrack |
| M3-Q006 | HR-107a portrait |
| M3-Q007 | HR-107b social account |
| M3-Q008 | HR-108 durable asset custody |
| M3-Q009 | HR-102 production hosting/cutover |
| M3-Q010 | HR-103a content approvers |
| M3-Q011 | Settled in M3; M4-D004 supersedes downstream topology; future real-site topology is HR-101 |
| M3-Q012 | HR-004 legacy engineering preview lifecycle |
| M3-Q013 | Settled historical topology; future real-site topology is HR-101 |
| M3-Q014 | Settled: public canonical YAML in the editor catalog is acceptable |
| M3-Q015 | HR-103b deployment approvers/protections |
| M3-Q016 | HR-109b trusted-input boundary |
| M3-Q017 | HR-112 development-advisory exception policy |
| M3-Q018 | HR-113 external-resource policy |

| M4 default | Current disposition |
| --- | --- |
| M4-I001 | HR-205 if additional platform support is proposed |
| M4-I002 | HR-108 for the 16 content assets; 13 framework payloads are settled |
| M4-I003 | Settled until a second consumer triggers extraction |
| M4-I004 | HR-204b if a new credential model is proposed |
| M4-I005 | HR-204c if per-PR deployments are proposed |
| M4-I006 | Settled: local and hosted updates use the same updater |
| M4-I007 | HR-114 for compatibility/deprecation; bundle v1 remains meanwhile |
| M4-I008 | Settled for test/template; production policy is HR-103b |
| M4-I009 | Objective compatibility removal gate, not a policy choice |
| M4-I010 | PR exclusion settled; broader preview lifecycle is HR-004 |
| M4-I011 | HR-206 for upstream resourcing; removal test is objective |
| M4-I012 | Settled host-neutral local and explicit Pages bases |
| M4-I013 | HR-001 engineering PR 5 disposition |

Milestone 1's native type-discriminator deferral was superseded by the accepted native relationship records and typed identifiers under the exact `dlthings:*` CURIE contract; alternative full-URI designators remain outside the supported contract rather than an open decision.
The accepted graph-only organization behavior maps to deferred HR-211, and the test fixture's long-term role maps to deferred HR-210.

## Source registers and operational evidence

Authoritative derivation remains in [`milestone-3-decisions.md`](milestone-3-decisions.md), [`milestone-3-acceptance.md`](milestone-3-acceptance.md), [`milestone-4-decisions.md`](milestone-4-decisions.md), [`milestone-4-acceptance.md`](milestone-4-acceptance.md), and [`full-con-migration.md`](full-con-migration.md).
Objective implementation follow-ups and hosted evidence belong in the acceptance record or dedicated issues so this queue stays focused on human judgment.

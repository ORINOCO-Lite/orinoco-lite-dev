# Orinoco Lite human-review decision queue

Status: Milestone 4 accepted; Milestone 5 active; production-graduation review remains open

Review snapshot: 2026-08-24

This is the single working list of unresolved **human choices** accumulated through the clean migration, full migration, complete-content migration, and single-repository distribution work.
It separates policy from facts with an objectively testable answer.
Release-coordinate repairs, documentation drift, CI results, and other engineering tasks belong in the applicable milestone acceptance record or an implementation issue, not in this queue.

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
| HR-201 | P2 | Hosted editing | Use authenticated one-pull-request source-adapter review without requiring a local checkout |
| HR-202a | P2 | Packaging | Decide whether to ship an optional full-stack image |
| HR-202b | P2 | Services | Decide whether to operate a persistent public service |
| HR-204a | P2 | Updates | Choose manual coordinates or reviewed release discovery |
| HR-204b | P2 | Automation | Choose a future update credential model |
| HR-204c | P2 | Hosting | Decide whether per-PR deployed previews are worthwhile |
| HR-205 | P2 | Support | Add platforms beyond macOS ARM64 and Linux x86-64 |
| HR-206 | P2 | Upstream | Prioritize a LinkML named-recursive-alias contribution |
| HR-207 | P2 | Source adapters | Use shared accept/reject/defer behavior with adapter-owned source semantics |
| HR-210 | P2 | Test fixture | Choose the long-term role of the full-content test consumer |
| HR-211 | P2 | Presentation | Decide whether the organization record needs a page |
| HR-213 | P2 | Hosted editing | Turn the normal SHACL Vue bundle into an attributed GitHub metadata proposal |
| HR-214 | P2 | Provenance identity | Model the two versioned source adapters using the pinned upstream pattern |

## P0 — close the current engineering review

### HR-001 — Accept the distribution and dispose of PR 5

**Status:** accepted

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

- Outcome: accept Milestone 4's distribution architecture and merge engineering pull request 5.
- Conditions or requested changes: record and implement HR-003 and HR-004; keep production content approval and real-site graduation separate.
- Decided by / date: John Lee / 2026-08-13.
- Follow-up: continue the atomic P1 review before any production graduation.

### HR-003 — Establish authority and a project license matrix

**Status:** accepted

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

- Engine/template/content/media rightsholder(s): Center for Open Neuroscience owns the original work to the extent permitted; accepted contributor rights remain respected.
- Upstream constraints and exceptions: preserve every upstream license and notice; license CON modifications only to the extent CON has authority.
- Engine/engineering license: MIT.
- Template/updater license: MIT.
- Metadata/editorial license: CC0 1.0 for factual metadata and machine-readable factual projections; CC BY 4.0 for original documentation and editorial prose.
- Media/presentation policy: item-specific licenses and provenance; no blanket grant for unverified images, portraits, logos, branding, or imported media.
- Interim posture, if permanent terms remain open: none for original code, documentation, and factual metadata; unverified media remains unlicensed until reviewed.
- Decided by / date: John Lee / 2026-08-13.

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

## Accepted strategic decisions

### HR-201 — Hosted authenticated source-adapter review

**Status:** accepted for the Milestone 5 GitHub profile

**Question:** Should normal source-adapter review require a local bundle handoff, or provide a least-privilege authenticated branch and pull-request workflow?

**Outcome:** The trusted GitHub workflow opens one draft pull request containing the actual metadata proposal, an accessible Markdown fallback, and a link to the supported decision application.
A deployed web application backed by a minimal stateless GitHub App user-authorization service provides friendly before-and-after record diffs and mutually exclusive accept, reject, or defer controls.
The workflow publishes exactly one untracked, expiring, reproducible GitHub Actions presentation bundle containing the identified source and proposal coordinates and per-record UI facts.
The application uses Actions read access to load that bundle, while deriving candidate membership and operations from the proposal commit's metadata diff.
It posts the complete head- and source-bound decision payload on the authorized collaborator's behalf and retains no second copy of metadata or curation state.
It reads the workflow-generated GitHub proposal and Actions objects and does not execute adapter or source logic.
GitHub Actions applies the human's decisions and attributed changes but never chooses a disposition, approves, merges, deploys, or writes to the external source.
The service retains only OAuth state and short-lived authentication sessions as operational state; the presentation bundle expires under ordinary GitHub artifact retention and neither is a persistent metadata or credential service.
Git commits and the authenticated submission comment remain the durable review record.
Pull-request Markdown is not a machine protocol and its native rendering limits are not curation conformance limits.
The project may publish one central application origin by default, but that origin remains configurable and the same stateless implementation may be self-hosted.

**Rationale:** The metadata diff and human decisions belong in one ordinary pull-request review, but native Markdown cannot provide dynamic mutually exclusive controls, typed complete submission, or useful compact review for a large candidate set.
The custom page and expiring bundle are only presentation and decision transport; GitHub remains authoritative for the proposal, authenticated comment, commit boundary, compact cache, and review history.
Local execution remains available for development and reproduction but is not a condition of normal curation.

**Decided and refined by/date:** John Lee, 2026-08-24.

**Follow-up:** Implement and accept the normative [`GitHub source-adapter curation profile`](github-curation-review.md) under the host-neutral [`source-adapters.md`](source-adapters.md) contract.
Treat SHACL Vue's existing download and future GitHub proposal integration as a separate human-edit profile; it is not a bundle input or contents-write requirement for this decision-review profile.

### HR-207 — Define source-adapter decision defaults

**Status:** accepted

**Question:** Should candidate identity, fingerprints, dispositions, deferral, and re-review behavior be fixed globally or owned entirely by each source adapter?

**Outcome:** Orinoco Lite supports exactly `accept`, `reject`, and `defer` for a proposed addition, modification, or deletion.
A rejection suppresses the same unchanged source-mapped claim until its normalized metadata-affecting source facts change.
A deferral returns on the next proposal.
Acceptance retains the reviewed metadata and prevents an unchanged source claim from reverting a later human correction.
Absence, pull-request closure, and workflow failure are never decisions.

Adapters configure stable source identity and the normalized source facts that can affect generated metadata.
Unused source fields and transport metadata do not enter the claim hash.
The compact current-state cache and shared behavior are defined by the normative [`source-adapters.md`](source-adapters.md) contract; source acquisition, transformation, and site policy remain adapter-owned.
There is no separate permanent-exclusion, conditional-deferral, link, or supersede disposition.
This decision does not settle identity, publication, venue, topic, or eligibility policy.

**Rationale:** Lite needs predictable safe behavior, while adapters need bounded control over what constitutes stable identity and material change for their source.

**Decided by/date:** John Lee, 2026-08-20.

**Follow-up:** Complete Zotero and `dump-research-info` conformance and the hosted review workflow under Milestone 5.

### HR-208 — Preserve source-adapter assertion types during annotation join

**Status:** accepted

**Question:** How should the annotation overlay qualify machine-provided class-range URIs and non-string data without changing their RDF meaning or coercing stored topical metadata?

**Outcome:** Follow the pinned upstream enrichment pattern for class-range URI assertions by deriving an annotated `Statement` under `characterized_by`, with the schema-induced predicate and topical URI object.
For non-string data, retain the native topical value and derive an `AttributeSpecification` whose string-valued `value` is the canonical lexical form and whose `range` is the locked LinkML datatype.
Do not add `schema_type` to the derived `Statement`, and do not coerce topical values to strings.

**Rationale:** Encoding a class-range URI as an attribute value changes an RDF resource into a literal, while putting a raw integer or boolean into `AttributeSpecification.value` violates the locked schema.
The accepted forms preserve native topical semantics and round trip through the pinned JSON/RDF converters.
This decision fixes the qualified-object shapes.
HR-212 subsequently fixed their canonical placement after the pinned update behavior exposed the representational incompatibility of scalar companion selectors.

**Decided by/date:** John Lee, 2026-08-20.

**Follow-up:** Add focused parity and locked-schema round-trip evidence to Milestone 5 acceptance.

### HR-209 — Keep review finalization compact and correction-safe

**Status:** accepted

**Question:** What exact durable cache and patch behavior preserve human corrections without reintroducing transaction artifacts or silently discarding work?

**Outcome:** Use the normative compact v1 canonical-YAML cache with PID-keyed current decisions and only their referenced authenticated GitHub-comment review blocks.
Reject and defer reverse each candidate's proposal patch using Git three-way semantics, preserve clean non-overlapping human edits, and fail on overlap.
For accepted human corrections, remove only untouched proposal-added PAV entries made stale by the correction and fail on human-edited or ambiguous companion state.
Delete empty companions, coalesce same-adapter rows into one claim per PID, and keep the candidate PID and path fixed during one review.

**Rationale:** Git already supplies patch merging, conflicts, correction, retry, and history.
These rules keep the durable cache small, avoid whole-record restoration that can discard unrelated edits, and make ambiguous ownership or identity changes visible to the reviewer.

**Decided by/date:** John Lee, 2026-08-20.

**Follow-up:** Add focused cache, correction, overlap, all-rejected, and rerun evidence to Milestone 5 acceptance.

### HR-212 — Preserve upstream qualified scalar updates

**Status:** accepted

**Question:** When a source data or class-range value differs from an already populated topical slot, should Orinoco Lite preserve the pinned enrichment helper's qualified-assertion behavior or adopt a local scalar replacement model?

**Evidence:** Pinned `update_data_property()` populates a topical slot only when it is absent.
It independently maintains machine-owned `AttributeSpecification` or `Statement` objects, preserves differently owned qualified values, and leaves an existing topical value unchanged.
The current scalar-path companion can derive only the current topical value, so it cannot represent a different machine source value.
An unannotated qualified object stored in the record and selected by the existing companion rejoins to the same RDF assertion as upstream inline PAV.

**Options:**

1. Store every qualified assertion object as canonical record content, retain only its PAV in the companion, and use an ephemeral compact-PAV view to run the pinned helper.
This preserves upstream semantics and confines local behavior to reversible PAV splitting and locked-schema typed normalization.
It also means an initial source run can add substantive qualified objects even when a topical value already matches, and public projections must tolerate those real semantic objects.
2. Derive the qualified object from a scalar companion and visibly replace conflicting topical values.
This keeps records shorter and top-level fields current, but permanently forks upstream ownership and coexistence semantics and requires a locally maintained merge algorithm.
3. Replace only a scalar inferred to be same-owner.
Upstream does not encode ownership on the topical scalar, so this requires new state or inference and is not sustainable under the accepted authority boundary.
4. Put the alternate source value in the companion.
This keeps records compact but turns the PAV companion into a second semantic metadata store and changes its schema, hashing, review, and migration contract.
5. Ignore a conflicting source scalar.
This avoids overwriting curated data but drops the upstream qualified source claim from the canonical graph and review diff.

**Outcome:** Use option 1.
Canonical records store the same topical fields and qualified `AttributeSpecification` or `Statement` objects produced by pinned upstream enrichment behavior.
The annotation companion stores only PAV removed from those objects, and joining the two trees reproduces the upstream Things assertion graph.
The join never derives qualified assertions from top-level scalar fields.
A human-reviewed edit to a top-level curated field is a separate curation action.

When a topical slot is absent but an equivalent human- or unowned qualified assertion already exists, follow upstream rather than failing closed.
The adapter proposes copying the assertion value into the topical slot without claiming ownership of the existing assertion and without adding PAV.
Human review may accept, reject, or defer that proposal.

**Decided by/date:** John Lee, 2026-08-24.

**Follow-up:** Replace the provisional scalar-selector join, add pinned-helper parity evidence, and conform both adapters before either writes existing-corpus metadata.

### HR-213 — Add the SHACL Vue GitHub human-edit path

**Status:** accepted for the Milestone 5 GitHub profile

**Question:** How should SHACL Vue propose an attributed metadata edit without embedding GitHub or source-adapter behavior in the editor or reimplementing the pinned RDF-to-Things conversion in TypeScript?

**Outcome:** Preserve SHACL Vue's normal **Download bundle** workflow and expose the exact generated version 2 bundle through a neutral browser event.
A trusted default-branch workflow first publishes one expiring, reproducible editor-input artifact for the exact pull-request or current default-branch commit being edited.
It contains only `edit/config.json`, `edit/records.ttl`, and `edit/data/record-sources.json`.
The central stateless application verifies the trusted run and exact commit, then combines those data files only in browser memory with the generic SHACL Vue shell and Things schema from an immutable, digest-verified Orinoco Lite runtime release.

A thin Orinoco wrapper adds **Propose via GitHub** and uses the authenticated curator's GitHub identity.
For an existing curation pull request it appends one bundle-only handoff commit to the exact head; for a standalone edit it creates a branch at the exact source commit, appends the handoff, and opens a draft pull request.
Before that write, the curator explicitly acknowledges that the bundle contains only public-approved data and no secrets.

Trusted default-branch Python applies the pinned Orinoco editor conversion, validates the joined graph, and replaces only the exact handoff commit with an equivalent attributed human metadata commit sharing its parent.
This preserves prior proposal and human commits while removing the bundle from the branch.
The shared GitHub App uses metadata read, Actions read, contents write, and pull requests write, with contents write confined to these explicit same-repository human proposal operations.
The service retains no bundle or metadata.

**Rationale:** The normal bundle carries RDF rather than canonical YAML and annotation companions.
Using the pinned Python conversion avoids a divergent TypeScript implementation and needs no additional deployed runtime service.
The exact-head artifact is only reproducible presentation input and is distinct from the source-adapter profile's exactly-one decision-review artifact; it is not metadata, the generated bundle, provenance, or durable curation state.
Combining trusted released editor code with exact-commit data in browser memory avoids pull-request executable code, browser-side conversion, another Worker, a database, an object store, or an artifact cache.
The temporary commit gives the trusted Action a bounded handoff while exact-head replacement keeps it out of mergeable history.
A public Git host can retain unreachable objects, so the path is limited to data already approved for public repository history.

**Decided and refined by/date:** John Lee, 2026-08-24.

**Follow-up:** Implement and accept the normative [`GitHub SHACL Vue human-edit profile`](github-shacl-vue-edit.md), including the exact-head editor-input artifact and immutable released shell, handoff replacement, App permission evidence, and standalone and existing-pull-request tests.

### HR-214 — Use upstream-style instrument identities for adapters

**Status:** accepted

**Question:** Which canonical Things should identify the Zotero and `dump-research-info` adapters in `pav:importedBy`?

**Outcome:** Store `xyzrins:source-adapters/zotero/v1` and `xyzrins:source-adapters/dump-research-info/v1` as versioned `xyzri:XYZInstrument` records.
Retain the existing protocol field names for compatibility; their use of “agent” does not require an Agent schema class.

**Rationale:** The pinned enrichment rules require a versioned pool record for every enricher, their examples and executable scrapers use instrument PIDs, and the pinned Things schema treats software as an instrument that enables an action.
`xyzri:XYZProject` instead models a collective planned activity and is not the upstream-compatible identity.

**Decided by/date:** John Lee, 2026-08-24.

**Follow-up:** Add both canonical records to the reviewed consumer, validate them with the locked schema, and record their immutable commit and hosted evidence in Milestone 5 acceptance.

### HR-215 — Separate source semantics from presentation routing

**Status:** accepted

**Question:** How should the `dump-research-info` source represent legacy CON website-routing values currently stored as semantic `about` relationships?

**Outcome:** Remove the legacy presentation-routing `about` values upstream.
Retain existing qualified `foaf:homepage` attributes and add the CON organization homepage using the same upstream `AttributeSpecification` pattern.
Do not add an adapter compatibility rule for presentation routes.

**Rationale:** Website section URLs select presentation routes; they are not Things that can satisfy the stored semantic relationships.
Correcting the upstream records preserves the established qualified homepage representation and prevents site-navigation policy from becoming canonical metadata.

**Decided by/date:** John Lee, 2026-08-25.

**Follow-up:** Review and merge [`con/dump-research-info` pull request 26](https://github.com/con/dump-research-info/pull/26), then dispatch the downstream adapter from its immutable merge coordinate.

### HR-216 — Keep external relationship identities bounded and local

**Status:** accepted for the Milestone 5 `dump-research-info` correction

**Question:** Should provider and role relationship targets be unresolved external references, complete local copies of provider records, or bounded local Things?

**Outcome:** Use bounded ordinary Things containing only the externally verified stable identity facts required by the locked schema and relationship validation.
For GitHub, ORCID, and the first-, senior-, and co-author roles, use the exact PID, schema type, and name or display label observed in the German public Things pool during the correction.
For the ISSN International Centre, which is absent from that pool, use its authoritative ROR PID and current ROR display name.
Reuse the existing `ISSN:1532-4435` JMLR venue Thing as the identifier creator instead of representing the JMLR website URL as an agent.

Do not copy the providers' annotations, descriptions, locations, or relationships, require network resolution during validation, or silently drop source fields.
These are reviewed canonical downstream records, not cached external graphs.
A later identity change is a new metadata proposal; tracking the providers' wider graphs requires a separate reviewed policy decision.

**Rationale:** A bare external link cannot satisfy the locked self-contained relationship validation.
Copying complete provider records would make their graph and metadata lifecycle a downstream maintenance responsibility.
The bounded records preserve interoperable global identifiers and the minimum human-readable identity needed for review without inventing a synchronization authority.

**Decided by/date:** John Lee, 2026-08-25.

**Follow-up:** Complete and review [`con/dump-research-info` pull request 26](https://github.com/con/dump-research-info/pull/26), then exercise the real downstream proposal from its immutable source coordinate.

## P2 — strategic decisions

These remain deferred until a later milestone activates their scope.

### HR-202a — Optional full-stack packaging

Decide whether the optional Dump Things and SHACL Vue service stack merits a digest-pinned multi-architecture image for local/advanced deployments.

### HR-202b — Persistent service operation

Separately decide whether CON should operate any persistent public metadata or editing service.
Static build, Pages, and bundle editing need none today.

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
- Projection output is ignored and regenerated during validation/build; metadata review uses source-only diffs.
- Static validate/build/preview/Pages/editor operations require no persistent service.
- Framework updates create pull requests and never auto-merge.
- Pages deploys only reviewed default-branch code, not PR code.
- Public canonical YAML may appear in the static editor catalog.
- Local output is host-neutral; Pages uses an explicit project-path base.
- The 13 inherited framework pointers are verified ordinary Git bytes.
- The source Things Schema and exact `dlthings:*` CURIE contract remain pinned.
- The LinkML recursion workaround has an objective removal test.
- Test/template branch controls remain accepted fixture defaults except that M5-D003 supersedes the consumer's linear-history requirement for conforming source-adapter review; merge commits must be permitted.
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
| M4-I008 | M5-D003 supersedes consumer linear history for source-adapter review; other test/template controls remain settled; production policy is HR-103b |
| M4-I009 | Objective compatibility removal gate, not a policy choice |
| M4-I010 | PR exclusion settled; broader preview lifecycle is HR-004 |
| M4-I011 | HR-206 for upstream resourcing; removal test is objective |
| M4-I012 | Settled host-neutral local and explicit Pages bases |
| M4-I013 | HR-001 engineering PR 5 disposition |
| M4-I014 | Settled generated-projection boundary |
| M4-I015 | HR-207 and the normative source-adapter specification supersede the exploratory disposition and representation details |

Milestone 1's native type-discriminator deferral was superseded by the accepted native relationship records and typed identifiers under the exact `dlthings:*` CURIE contract; alternative full-URI designators remain outside the supported contract rather than an open decision.
The accepted graph-only organization behavior maps to deferred HR-211, and the test fixture's long-term role maps to deferred HR-210.

## Source registers and operational evidence

Authoritative derivation remains in [`milestone-3-decisions.md`](milestone-3-decisions.md), [`milestone-3-acceptance.md`](milestone-3-acceptance.md), [`milestone-4-decisions.md`](milestone-4-decisions.md), [`milestone-4-acceptance.md`](milestone-4-acceptance.md), [`milestone-5-decisions.md`](milestone-5-decisions.md), [`milestone-5-acceptance.md`](milestone-5-acceptance.md), and [`full-con-migration.md`](full-con-migration.md).
Objective implementation follow-ups and hosted evidence belong in the acceptance record or dedicated issues so this queue stays focused on human judgment.

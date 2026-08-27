# Orinoco Lite human-review decision queue

Status: Milestone 5 accepted; pre-Milestone 6 convergence is active and the GitHub App custody transfer remains

Review snapshot: 2026-08-26

This file is the current human-decision entry point.
It keeps the bounded outcomes that opened the pre-Milestone 6 convergence work beside the unresolved choices that still require human judgment.
Accepted Milestone 5 outcomes are in [`milestone-5-decisions.md`](milestone-5-decisions.md), and the detailed decision history through that milestone is archived in [`human-review-decisions-through-m5.md`](archived/human-review-decisions-through-m5.md).
Release coordinates, CI results, documentation repairs, and other mechanical work do not belong in this queue.

## Review rules

- Resolve one ID at a time with an outcome, short rationale, reviewer, and date.
- Update the applicable milestone decision or specification in the same reviewed change.
- A policy decision does not by itself authorize a real-site, deployment, repository-transfer, or other external mutation.
- Questions activated by the pre-Milestone 6 convergence work or Milestone 6 planning are kept in [`milestone-6.md`](milestone-6.md) until answered.

## Resolved for current planning

| ID | Outcome | Source decision | Reviewer | Date |
| --- | --- | --- | --- | --- |
| HR-221 | Preserve well-formed unresolved Things references by default and report locally unmaterialized references and graph edges. Treat stricter closure as optional site policy rather than general upstream validity. | M6-D001 | John Lee | 2026-08-26 |
| HR-222 | Update upstream deliberately when requested. Record accepted commits in Git, locks, and the implementing pull request; do not maintain a tracked compatibility inventory or advance pins automatically. | M6-D002 | John Lee | 2026-08-26 |
| HR-223 | Accept Milestone 5 on its implemented and focused evidence. Use a fresh current Zotero transition and the first live SHACL handoff as Milestone 6 operational proof instead of repairing stale proposal history. | M6-D003 | John Lee | 2026-08-26 |
| HR-224 | Wait for active pull requests to merge before moving repositories or the GitHub App. Keep the personal demonstration downstream under `leej3`; resolve the remaining transfer scope through Pre-M6-Q001. | M6-D004 | John Lee | 2026-08-26 |
| HR-225 | Treat deliberate upstream repinning, resulting compatibility fixes, aligned releases, and the approved custody transfer as a bounded maintenance batch before Milestone 6. Start it without a separate exhaustive milestone specification and keep exact evidence in the implementing pull requests, commits, locks, and releases. | Before Milestone 6 | John Lee | 2026-08-26 |
| HR-226 | Transfer the core product repositories, integration fixture, GitHub App, and all actively used mirrors to `ORINOCO-Lite`. Keep the personal demonstration downstream, real CON site, unused historical mirrors, and CON-owned source repositories outside the move. Broader ecosystem visibility may be reconsidered later. | M6-D004 | John Lee | 2026-08-26 |
| HR-227 | Keep the downstream static site as the only SHACL Vue editor and expose both **Download bundle** and **Propose via GitHub** from that editing session. Use the central stateless service only for OAuth, confirmation, unchanged-bundle receipt, and the existing fixed-path Git handoff; it may provide a lightweight upload fallback but must not assemble or host another editor. | M6-D005 | John Lee | 2026-08-26 |

## Before production graduation

These choices do not block the public engineering fixtures.
They must be resolved before changing or presenting the real CON site as production-ready.

| ID | Domain | Open decision |
| --- | --- | --- |
| HR-101 | Migration | Choose a history-preserving real-site migration topology. |
| HR-102 | Hosting | Choose production hosting, domain cutover, rollback, and recovery ownership. |
| HR-103a | Governance | Name canonical content and presentation approvers. |
| HR-103b | Governance | Name deployment approvers and production protection rules. |
| HR-104a | Identity | Define when a source creator becomes a public person. |
| HR-104b | Identity | Decide Brock Wester's public record and associations. |
| HR-104c | Identity | Decide Russell Poldrack's public record and associations. |
| HR-104d | Authorship | Decide how unresolved literal creators appear publicly. |
| HR-105a | Publications | Define DOI and publication-version identity. |
| HR-105b | Publications | Define venue authority and publishing-activity modeling. |
| HR-105c | Topics | Define tag-to-topic vocabulary and promotion policy. |
| HR-106 | Publications | Confirm collection and item eligibility. |
| HR-107a | Rights | Decide the Chris Markiewicz portrait replacement. |
| HR-107b | Identity | Decide whether to publish the legacy social account. |
| HR-108 | Assets | Choose durable custody for the 16 content assets. |
| HR-109a | Editor | Define production review-bundle size and transaction behavior. |
| HR-109b | Trust | Decide whether deployment or schema inputs may become user-writable. |
| HR-112 | Security policy | Set the development-toolchain advisory exception policy using a current audit. |
| HR-113 | Privacy | Choose the deployed site's external-resource policy. |
| HR-114 | Releases | Define release stewardship, compatibility, and support lifetime. |
| HR-115a | Presentation | Accept or revise production branding, information architecture, responsive design, and legacy parity. |
| HR-115b | Accessibility | Define and accept the production accessibility standard. |

## Strategic choices

These remain dormant until a milestone proposes concrete work that needs them.

| ID | Domain | Open decision |
| --- | --- | --- |
| HR-202a | Packaging | Decide whether to ship an optional full-stack image. |
| HR-202b | Services | Decide whether to operate a persistent public metadata service. |
| HR-204a | Updates | Choose manual coordinates or reviewed release discovery. |
| HR-204b | Automation | Choose a future update credential model if the current token is insufficient. |
| HR-204c | Hosting | Decide whether per-pull-request deployed previews justify their isolation cost. |
| HR-205 | Support | Add platforms beyond macOS ARM64 and Linux x86-64 only with continuous full-contract evidence. |
| HR-206 | Upstream | Decide whether to file, fund, or contribute the LinkML named-recursive-alias correction. |
| HR-210 | Test fixture | Choose the test consumer's long-term role after real-site graduation. |
| HR-211 | Presentation | Reconsider an organization page when reviewed content and an information-architecture purpose exist. |

## Settled boundaries

- A downstream is one ordinary Git repository without submodules or gitlinks.
- Reviewed records and annotation companions are canonical semantic input; generated projections are disposable.
- Static validation, build, preview, Pages, and bundle editing require no continuously running metadata service.
- Framework updates create pull requests and never approve or merge themselves.
- The source Things Schema and exact `dlthings:*` CURIE contract remain pinned.
- Milestone 5 source-adapter review uses GitHub, merge commits, and human decisions; it does not write to an external source.
- No Milestone 5 or 6 decision authorizes changing the real site, its remotes, deployment, DNS, or production domain.

## Source records

Detailed derivation remains in the archived [`human-review-decisions-through-m5.md`](archived/human-review-decisions-through-m5.md), [`milestone-3-decisions.md`](milestone-3-decisions.md), [`milestone-4-decisions.md`](milestone-4-decisions.md), and [`milestone-5-decisions.md`](milestone-5-decisions.md).
Exact implementation evidence remains in the corresponding acceptance records.

# Milestone 4 decision register

Status: Milestone 4 accepted; production-graduation decisions remain open

Consolidated prioritized review queue: [`open-decisions.md`](../open-decisions.md).
This file remains the authoritative record of accepted Milestone 4 decisions and implementation defaults.

## Accepted decisions

| ID | Decision | Consequence |
| --- | --- | --- |
| M4-D001 | The test consumer uses the complete accepted Milestone 3 CON profile, not a subset. | All 199 Things share one `metadata/records/` input tree; every record, editorial source, declared asset, and supported source-adapter input is mapped and parity-checked. |
| M4-D002 | Preserve the complete behavioral test contract through a traceability ledger. | Topology-specific tests move to engineering or receive released-interface successors; no assertion is silently deleted. |
| M4-D003 | The generic template is content-neutral. | Creation combines a generic versioned template with a complete site-owned import bundle. Other adopters do not inherit CON content. |
| M4-D004 | The supported downstream topology is one ordinary Git repository with no submodules or gitlinks. | Upstream rebases and component coordination remain engineering concerns. |
| M4-D005 | Use a locked Python engine plus immutable runtime archive as the primary distribution. | The same implementation drives local Pixi commands and hosted validation. |
| M4-D006 | Use one Copier source and mechanically generate the GitHub template snapshot. | Creation and update templates cannot drift independently. |
| M4-D007 | Keep the committed projection during the initial distribution. | This preserved the Milestone 3 review proof; the later downstream-interface cull superseded the storage choice with M4-I014. |
| M4-D008 | The full service stack is optional advanced functionality. | Static validation, build, preview, Pages, and patch editing do not require a container or persistent service. |
| M4-D009 | The test repository is public under `con` and uses ordinary project Pages. | Anonymous checkout, template/update review, and public Pages are exercised without a production domain. |
| M4-D010 | Framework update pull requests never merge automatically. | Human review remains the release-to-site publication boundary. |
| M4-D011 | The real site repository is read-only throughout Milestone 4. | No file, ref, setting, workflow, deployment, or remote write occurs in `centerforopenneuroscience.org`. |
| M4-D012 | Original Orinoco Lite software and template code use MIT; factual metadata uses CC0 1.0; original documentation and editorial prose use CC BY 4.0; media remains item-specific. | Preserve all upstream notices and do not infer rights for unverified assets, logos, or branding. |
| M4-D013 | The legacy Milestone 3 engineering Pages preview is retired as an automatic deployment and retained as frozen evidence. | Candidate engineering previews are explicit opt-in artifacts; the complete downstream consumer remains the supported integration and publication surface. |

## Implementation defaults

| ID | Default | Revisit condition |
| --- | --- | --- |
| M4-I001 | Initial supported platforms are macOS 14 ARM64 and Linux x86-64. | Add a platform only after complete release and consumer acceptance runs there. |
| M4-I002 | Retain exact digest-based read-only hydration for the 16 content assets. Materialize the 13 inherited presentation-framework annex pointers as verified ordinary Git payloads in the distributed consumer. | Replace the 16 content-asset hydration contracts only after an immutable asset-custody release proves byte parity; never make a downstream build depend on git-annex merely to obtain the presentation framework. |
| M4-I003 | Put concrete downstream adapters under site-owned `source-adapters/`; configuration contract 2 exposes only `paths.source_adapters`, with no compatibility alias. Zotero is the only current generic template candidate, while `dump-research-info` remains a CON-specific experiment. | Extract only behavior demonstrated across adapters, prefer upstream helpers, and keep source policy site-owned. |
| M4-I004 | Keep default workflow permissions read-only. Enable GitHub's combined “create and approve pull requests” repository switch (`can_approve_pull_request_reviews=true`) so `GITHUB_TOKEN` can create a review PR; grant writes only to the update job, and never approve or merge in automation. | Consider a narrowly scoped GitHub App only if unattended validation becomes a reviewed requirement. |
| M4-I005 | Pull requests run validation, while the Pages workflow builds and deploys only the reviewed default branch. The default-branch-only correction shipped in template `v0.1.8`, remains present in current maintenance releases, and has deployed the reviewed consumer default branch successfully. | Change only after a separately reviewed per-PR preview design. |
| M4-I006 | The update command runs the same pinned updater locally and in automation. | A remote-only updater is not a supported public interface. |
| M4-I007 | Editor review bundles use a new single-consumer binding. Static page links carry the record PID into the editor, and record-selection controls expose that PID in their accessible names, while Milestone 3 bundle v1 remains a rollback fixture. | Remove v1 support only after real-site graduation is separately accepted. |
| M4-I008 | Protect generated template branch `github-template`, template source branch `main`, and consumer `main` against force pushes and deletion and require linear history. The two `main` branches additionally require one approval, latest-push approval, stale-review dismissal, and conversation resolution, with administrator enforcement disabled. | Retain these controls. The authorized administrator bypass used for terminal template maintenance does not authorize bypassing human review of the consumer update. |
| M4-I009 | Keep the macOS 14 Playwright/WebKit compatibility overlay introduced in template `v0.1.7` framework-owned and update-safe. | Remove it only after the released browser/runtime combination passes the complete consumer contract without the overlay. |
| M4-I010 | Skip the legacy Milestone 3 Pages-preview workflow on the Milestone 4 engineering pull request. | Retain the exclusion so review synchronizations cannot recursively check out the real-site repository. |
| M4-I011 | Treat the LinkML/Pydantic recursion failure as an upstream generator-representation defect, not a schema inheritance cycle or a Dump Things patch defect. Serialize Orinoco converter construction, temporarily use recursion limit 2,000 only within that boundary, and restore the caller's exact value on success or failure. | Remove the workaround after the pinned LinkML generator emits a proven named recursive alias and the full 199-record JSON/RDF contract passes at Python's default limit without it. |
| M4-I012 | Local `build` and `build-repeat` produce root-relative output with base `/`; the verifier serves and traverses that output through both `127.0.0.1` and `localhost`. Pages and explicit browser scenarios continue to supply their project-path base separately. | Add another mount mode only with deterministic output and navigation/asset verification; never bake a development hostname into portable output. |
| M4-I013 | Pull request 1 is closed, unmerged discovery evidence. Replacement pull request 2 was reviewed and merged, subsequent template maintenance was exercised through pull request 3, and site-owned presentation follow-up was merged through pull request 4. | Preserve these review boundaries as evidence. The open engineering and production decisions are tracked in the consolidated human-review queue. |
| M4-I014 | Generate projection output during validation and build, keep it ignored on the reviewed default branch, and review source metadata rather than committed derivatives. After a successful Pages deployment, retain the exact projection and website on the generated `latest-hugo-projection` and `gh-pages` commit chain. | The generated refs provide inspectable debugging evidence for the latest deployment without making derivatives part of a metadata pull request or a second source authority. |
| M4-I015 | Orinoco Lite supplies safe source-candidate decision defaults: rejection suppresses the same materially unchanged claim; relevant material or policy changes reopen review; deferral has an explicit return condition; and permanent exclusion requires explicit human scope. Adapters may configure source-specific identity components, material fingerprint fields, deferral conditions, and additional re-review triggers. | Freeze a common representation only after at least two adapters demonstrate it. Adapter configuration must remain deterministic and versioned, preserve explicit human dispositions, and never weaken the re-review or human-review boundaries. |

## Carried Milestone 3 decisions

Distribution does not resolve publication identities, duplicate semantics, venues, topics, hidden-person visibility, missing artwork, social-media ownership, annex custody, production cutover, Pages reviewers, external fonts, or the bounded development-only editor advisory.
Preserve every open entry from [`milestone-3-decisions.md`](milestone-3-decisions.md) as source provenance and fail closed where it already fails closed.

## Decisions prohibited in this milestone

The following require a later explicit authorization and are not questions for the Milestone 4 implementation to infer:

- changing the real site's default branch or active ancestry;
- updating its Pages source, deployment workflow, repository settings, or production domain;
- pushing a template-derived branch to it;
- deleting, rewriting, or moving its legacy, clean-migration, full-migration, or Milestone 3 refs; and
- accepting the redistributed CON content as production-approved merely because its distribution tests pass.

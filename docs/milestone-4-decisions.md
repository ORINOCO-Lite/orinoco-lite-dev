# Milestone 4 decision register

Status: active implementation

## Accepted decisions

| ID | Decision | Consequence |
| --- | --- | --- |
| M4-D001 | The test consumer uses the complete accepted Milestone 3 CON profile, not a subset. | Every canonical/reference record, editorial source, declared asset, provenance ledger, generated projection, and supported integration input is mapped and parity-checked. |
| M4-D002 | Preserve the complete behavioral test contract through a traceability ledger. | Topology-specific tests move to engineering or receive released-interface successors; no assertion is silently deleted. |
| M4-D003 | The generic template is content-neutral. | Creation combines a generic versioned template with a complete site-owned import bundle. Other adopters do not inherit CON content. |
| M4-D004 | The supported downstream topology is one ordinary Git repository with no submodules or gitlinks. | Upstream rebases and component coordination remain engineering concerns. |
| M4-D005 | Use a locked Python engine plus immutable runtime archive as the primary distribution. | The same implementation drives local Pixi commands and hosted validation. |
| M4-D006 | Use one Copier source and mechanically generate the GitHub template snapshot. | Creation and update templates cannot drift independently. |
| M4-D007 | Keep the committed projection during the initial distribution. | Update review, stale-product rejection, and rollback retain the Milestone 3 behavior. |
| M4-D008 | The full service stack is optional advanced functionality. | Static validation, build, preview, Pages, and patch editing do not require a container or persistent service. |
| M4-D009 | The test repository is public under `con` and uses ordinary project Pages. | Anonymous checkout, template/update review, and public Pages are exercised without a production domain. |
| M4-D010 | Framework update pull requests never merge automatically. | Human review remains the release-to-site publication boundary. |
| M4-D011 | The real site repository is read-only throughout Milestone 4. | No file, ref, setting, workflow, deployment, or remote write occurs in `centerforopenneuroscience.org`. |

## Implementation defaults

| ID | Default | Revisit condition |
| --- | --- | --- |
| M4-I001 | Initial supported platforms are macOS 14 ARM64 and Linux x86-64. | Add a platform only after complete release and consumer acceptance runs there. |
| M4-I002 | Retain exact digest-based read-only hydration for the 16 annex-backed assets. | Replace only after an immutable asset-custody release proves byte parity. |
| M4-I003 | Put CON-specific Zotero source, policy, provenance, and helpers under `integrations/zotero`. | Extract generic logic into the engine when a second consumer proves the interface. |
| M4-I004 | Use repository `GITHUB_TOKEN` with least privilege and explicit workflow approval for update PRs. | Consider a narrowly scoped GitHub App only if unattended validation becomes a reviewed requirement. |
| M4-I005 | Pull requests build and upload a preview artifact; only the reviewed default branch deploys shared Pages. | Change only after a separately reviewed per-PR preview design. |
| M4-I006 | The update command runs the same pinned updater locally and in automation. | A remote-only updater is not a supported public interface. |
| M4-I007 | Editor review bundles use a new single-consumer binding while Milestone 3 bundle v1 remains a rollback fixture. | Remove v1 support only after real-site graduation is separately accepted. |

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

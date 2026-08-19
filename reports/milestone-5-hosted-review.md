# Milestone 5 hosted-review follow-up

Status: implementation submitted; hosted review not yet activated

Started: 2026-08-19

## Purpose and documentation boundary

This report records the scope and design changes required to make source curation review available entirely through GitHub.
It supplements `milestone-5-implementation.md` without modifying the original Milestone 5 plan, decision register, acceptance record, source-adapter architecture, or human-review register.

The initial implementation supplied deterministic proposal, durable decision, and guarded reconciliation primitives, but its operator interface remained a local command line and ledger-editing workflow.
The reviewed direction on 2026-08-19 requires one pull request to contain the complete human review and reconciliation lifecycle, with no mandatory downstream checkout.
A GitHub Actions bot is acceptable, but it must not infer decisions, approve, merge, or deploy.

This direction expands the implementation surface.
It does not itself choose a content disposition, approve public retention for every future source, or replace the remaining human and hosted acceptance gates in the original plan.

## Ownership change

The site-owned test consumer retains:

- adapter-specific proposal and reconciliation behavior;
- the prototype review manifest, rendered candidate cards, decision-comment grammar, GitHub authority checks, and immutable event compilation;
- canonical metadata, policy, and transaction evidence; and
- behavior and security regressions for the hosted-review facade.

The consumer also owns the pinned GitHub Actions workflow.
This preserves the earlier M5-Q007 boundary: a fresh template output contains no adapter or hosted review backend, so advertising the workflow there would expose an interface that always fails.
The template instead receives only ownership and update evidence proving that a site's curation workflow and DataLad sidecars survive a normal Copier update.
It does not receive adapter semantics, a review facade, an engine API, or a continuously running service.

The existing template contract broadly classifies `.github/workflows/**` as a template-owned, three-way-update surface.
The consumer-specific workflow is not rendered by the current template, and a regression proves that this extra file survives the current update cycle byte-for-byte.
This is not a permanent site-owned namespace exception: if a future template introduces the same path, Copier must expose that collision for explicit review rather than silently choosing either version.

## One-pull-request interface

The hosted transaction has four visible stages:

1. A reviewer starts **Curate source metadata** through `workflow_dispatch`, supplying the adapter, exact evaluation date, immutable source coordinate, and an explicit acknowledgment that complete review data will be public in the pull request and Git history.
2. Trusted default-branch code creates one draft bot pull request with an exact inventory, manifest, complete candidate cards, batches of at most 20 copyable YAML decision items, and retained proposal execution evidence.
3. Write-authorized reviewers post strict `/curation submit` comments.
GitHub, rather than editable YAML, supplies reviewer identity, timestamp, and the immutable comment coordinate.
Corrections append superseding decision events before finalization; neither comment edits nor deletes rewrite accepted history.
4. An exact `/curation finalize` command requires complete current coverage, reproduces the proposal from trusted source pins, reconciles once through the locked runtime, validates a trusted replay, pushes the final change to the same draft branch, and explicitly dispatches read-only validation.

Normal branch protection remains the approval boundary.
Every bot push changes the reviewed head and therefore requires a fresh human approval.
The bot never marks the pull request ready, approves it, merges it, deploys it, or writes to a source system.

A zero-candidate proposal completes in the Actions summary without opening an empty pull request.
Finalization is terminal in prototype v1.
A post-finalize change requires closing the unmerged pull request and starting a new transaction because a later non-accepting event cannot safely undo already reconciled canonical bytes by itself.

## Public-data and reviewer boundary

The real `dump-research-info` proposal contains complete baseline and proposed records, including already-public personal contact fields.
Hosted review makes those values, reviewer identities, rationales, and evidence references durable in a public pull request and Git history.
The workflow therefore fails unless the initiating user selects a transaction-specific acknowledgment.
It records the immutable GitHub actor, time, workflow run, source pins, and proposal coordinate rather than treating the acknowledgment as a universal retention policy.

The implementation intentionally keeps the full review surface.
Redacting candidate data would prevent a reviewer from evaluating whole-record replacement and downstream-only field loss.
A future accepted policy may define a narrower transport, but the prototype neither silently publishes without acknowledgment nor silently hides material fields from review.

## Trust and mutation boundary

The privileged comment handler is an `issue_comment: created` workflow loaded from the default branch.
It does not use `pull_request_target`.
It checks the same-repository bot branch, draft state, base branch and commit, workflow run, reviewer identity and collaborator permission, proposal source pins, manifest, changed paths and modes, and exact head SHA before mutation.

The pull-request checkout is data-only.
Provider reproduction and reconciliation use trusted default-branch implementation files and the pinned runtime.
Any unexpected executable, workflow, symlink, gitlink, canonical path, report, or sidecar fails closed.
Source proposals are regenerated from the recorded exact source and byte-compared before a decision or finalization is accepted.

The bot records externally verifiable GitHub attestations for the original proposal and each accepted decision-branch transition.
Those receipts bind the trusted workflow run and attempt, pull request, parent and target commits, source/bundle identity, and exact decision-ledger digest.
A collaborator can push to the bot branch, but an unattested or rolled-back head cannot become decision authority.
The marker is posted before the exact compare-and-swap push, and validation requires one unique installed chain from the proposal to the current head.
Every successful transition remains on that chain.
A failed or cancelled transition is ignored when it did not install; it participates only when it is the unique exact transition needed to reach the current head with the matching ledger.
This preserves recovery when a runner fails after a successful push without allowing a failed compare-and-swap or rollback to become authority.

Comment runs are serialized per pull request with current GitHub queueing and do not cancel pending submissions.
Mutating pushes use an exact `--force-with-lease` expectation for compare-and-swap behavior.
Write credentials are never persisted into the untrusted checkout or exposed to pull-request code.
GitHub mutations occur only after the trusted guards, and the branch push is separately bound to the exact reviewed head.
The final bot push explicitly dispatches the existing read-only validation workflow because `GITHUB_TOKEN` pushes do not create ordinary pull-request events.

## Evidence log

The submitted consumer change is [test-orinoco-downstream-website PR 19](https://github.com/con/test-orinoco-downstream-website/pull/19).
Its exact base is `e669446e4f86b8986d6e1172c0b2ea8a535957ce`, and its submitted head is `ab413b82f101aaa24b4a5d6529b2d9f72fc29106` with tree `84126bd89af4808a4384db267ad147c8e5a9a7f5`.
The branch contains three separate commits for decision-history correction, the hosted-review facade, and the one-pull-request workflow and guide.

The submitted preservation change is [orinoco-lite-template PR 11](https://github.com/con/orinoco-lite-template/pull/11).
Its exact base is `4bb3dc8564a12d52a97633f43e9c786bf8aad2a9`, and its submitted head is `1ebb0fb47e226ac710ee4d360be8c0fc0d68d762` with tree `35654c1a49c97a96e9056f370f253ee880750b6f`.

The frozen hosted-review helper, helper tests, workflow, and workflow tests have SHA-256 digests `107612e3c81526663aa35e19126a587765447f4b17631768756019efd9171507`, `f8f5e238a7f2a7551858cd77f73a62a431a02c1153cdd47bb6dbbbd5099a124d`, `e33d852d7a846a76c5df4e759e03eafbf6701a7424c02bdf0402c3b3f57b25f0`, and `dc942ed1ca99369512ce0e8f28dd5a9206803eac7eeac02a3a1fb725e1be9b13`, respectively.

Local consumer verification passed ownership classification and 159 tests, with one expected locked-runtime acceptance skipped in the metadata-only environment.
This includes 22 hosted-facade tests and eight workflow contract tests.
Black, Ruff, and diff checks passed.
Local template verification passed render-current validation and 63 tests.
An independent final review reported no remaining P1 or P2 correctness or security findings.

A proposal-only trial against exact `dump-research-info` commit `062da59cb5a00ca128b3df895426a54088bfc625` and evaluation date `2026-08-19` produced 82 candidates, of which 76 were blocked.
Its inventory identity was `curation-inventory-v1:08d76ba43066d03b8e7a427526c7bfe9334ca5db84f10b8e2faf7e7153cfeaea`; the 195,071-byte YAML had SHA-256 `4b3251951ee68cd1e692b673bd915ce493b445014f50df6275b69e7799496e70`.
Canonical metadata remained byte-unchanged.
The real inventory was not committed or pushed because no transaction-specific public-data acknowledgment had yet been made.

Hosted workflow runs, human dispositions, the final reconciliation coordinate, and default-branch evidence remain pending.
These submitted coordinates do not claim activation or acceptance of the hosted workflow.

## Residual gates

Before the first real curation transaction can be treated as accepted evidence:

- the template and consumer workflow changes must receive ordinary pull-request review and merge;
- the public-data acknowledgment must be made for that exact source proposal;
- every candidate must receive an explicit authorized disposition;
- the reconciled final head must pass the existing hosted validation matrix and receive a human approval after the bot's final push; and
- the resulting default-branch transition and retained inventory, decision, report, and DataLad evidence must be inspected.

No step in this follow-up authorizes a production-site change or changes the read-only status of `centerforopenneuroscience.org`.

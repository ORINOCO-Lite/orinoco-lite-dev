# Submodule divergence

[The CSV](submodule-divergence.csv) records every direct and nested submodule selected by this package.
Gitlinks select the commits; Git history supplies descriptions, merge-bases, distances, and local commit subjects.
The CSV is generated output and can be recreated from nothing.
The setup hook initializes missing submodules and configures confirmed fork upstreams, including nested forks such as `shacl-vue`.
For maintained forks, `upstream` always identifies the original German Hub repository, including when the fork lives in another GitHub namespace.
Use `orinoco-lite` for an additional remote pointing at the ORINOCO-Lite copy; `origin` can remain your own fork.
Direct upstream dependencies such as Congo use `origin`.
Fork comparisons follow the authoritative remote's default branch.
Direct dependencies retain the selected parent's `.gitmodules` branch when declared, such as Congo's `stable`; otherwise they follow the remote default.
Selected commits always come from gitlinks, never from a branch tip.

`local_commit_subjects` contains exact subjects in oldest-first topological order, separated by newlines inside a quoted CSV field.
It includes merge and revert commits; a subject list does not imply that every patch remains effective.
`comparison_url` links the mirror branch comparison against the authoritative default branch, without requiring a hosting API.
It is a comparison link, not confirmation that a pull request exists.
No AI summary or inferred submission decision is generated.

## Commit titles

Every selected commit absent from the observed upstream history (`upstream_commit..selected_commit`) must use:

```text
<type>(<scope>): <purpose> [intent:<value>]
```

Scope is optional; the Conventional Commit breaking-change marker `!` is allowed.
Types are `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, and `revert`.
The intent describes whom the change is intended to serve:

| Intent | Meaning |
| --- | --- |
| `general` | Improvement intended for the original project |
| `integration` | Orinoco integration or adaptation |
| `deployment` | A particular site's or environment's requirements |
| `undecided` | Maintainer intent has not been settled |

For example: `fix(graph): resolve assets beneath the site URL [intent:general]`.
Submission, review, and acceptance are changing facts recorded in PRs, not commit-title categories.
Explain a temporary workaround's purpose in its title; temporary lifetime does not determine intent.
Split mixed-purpose changes where practical, or use `undecided` pending review.
A revert also needs a prescribed title describing its purpose and intent.

The check covers **all existing and future local divergence commits**, including merges and reverts, without a legacy exemption.
Original upstream commits are outside this range and are not subject to Orinoco's title policy.
Nonconforming titles fail validation.
Rewording published history and advancing its parent pins is a separate reviewed operation.

## Updating locally

Run both commands through Pixi, which supplies Python and Git 2.48 or newer.
Stage intended parent gitlink changes before running them.

```console
pixi run python tools/setup_submodule_remotes.py
pixi run submodule-divergence
```

Setup initializes missing checkouts and repairs remote configuration; it does not move initialized checkouts.
It reports unknown Orinoco Lite forks for explicit upstream configuration.
Initialization requires the containing checkout's index and working `.gitmodules` to agree with the selected dependency declaration.
Normal report generation fetches up to eight repositories concurrently and replaces the generated CSV atomically after all observations succeed.
Git discovers remote default branches during the same fetch.
Neither command stages files, advances selected pins, rebases commits, or changes remote repository settings.
Review and stage the CSV after generation.

Both commands return 1 after repairs and 0 on an unchanged, valid rerun.
The report also returns 1 for any invalid local commit title, even when the CSV is current.
Operational errors return 2.
Additional upstream commits are information, not title violations or a reason to repin automatically.
Generation writes the CSV only after every row succeeds.

Use `--no-fetch` on the report to use locally available upstream refs.
It reminds you that remote changes may be missing; refresh without that option before reviewing an update.
Missing refs or incomplete history require a fetch-enabled run.
Use `--check` on either command to report needed repairs without changing files or Git state; report checks imply `--no-fetch`.

The pre-commit hooks run setup followed by fetch-enabled report generation through Pixi on every invocation.
Commits therefore require access to the dependency remotes; network failures stop the hook.
The report uses staged parent gitlinks and recursively reads the selected child commits, regardless of checkout `HEAD`.
It compares generated output to the working CSV; pre-commit's normal stash/restore behavior supplies staged file contents during commits and protects unstaged changes.
After a repair, review and stage the CSV before retrying the commit.
Running the script directly a second time succeeds when the working CSV is current and all titles conform.
Existing nonconforming titles continue to fail; they require deliberate review and rewording.
Forks that do not use this maintenance policy can opt out through pre-commit's standard `SKIP=submodule-upstream-remotes,submodule-divergence` setting.
The daily publication job runs only in `ORINOCO-Lite/orinoco-lite-dev`.

## Daily CI

[Submodule divergence](../../.github/workflows/submodule-divergence.yml) runs daily at 07:23 UTC and can be dispatched manually on the default branch.
It fetches current upstream heads, regenerates the CSV, and opens a draft PR only when the CSV changes.
There is no observation timestamp to cause daily no-op changes.
The PR title and commit subject are `docs: refresh submodule divergence snapshot`.
These parent-repository snapshot commits follow ordinary Conventional Commits; the intent suffix applies to the dependency divergence ranges above.

Only one automated snapshot PR is open at a time.
While it awaits review, daily runs leave its branch and prose unchanged and link it in the Actions summary.
After it is merged or closed, a later run can propose another snapshot.
The workflow does not update dependency pins, advance mirror branches, merge PRs, or reword commits.
It explicitly dispatches validation for its new branch because PR creation with `GITHUB_TOKEN` does not trigger ordinary PR workflows.
Enable Actions to create pull requests in repository settings; the workflow uses the job token and needs no new secret.

PR validation fetches upstream refs, then checks the CSV without applying repairs and validates every local commit title.
A newly observed upstream advance can make a previously generated CSV stale.
A correct snapshot can still fail validation if selected local titles do not conform.
To make this a merge gate, require the workflow's `check` job in the repository's branch rules.

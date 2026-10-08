# Submodule divergence

[The CSV](submodule-divergence.csv) records every direct and nested submodule selected by this package.
Gitlinks select the commits; Git history supplies descriptions, merge-bases, distances, and local commit subjects.
The CSV owns only the original `upstream_url` and `upstream_ref` selections that are not declared by the fork gitlinks.
Set those two fields when adding a submodule, then regenerate the other fields.
Remove obsolete rows by regenerating after removing a gitlink.

`local_commit_subjects` contains exact subjects in oldest-first topological order, separated by newlines inside a quoted CSV field.
It includes merge and revert commits; a subject list does not imply that every patch remains effective.
`comparison_pr` links the matching open mirror comparison when available.
No AI summary or inferred submission decision is generated.

## Commit titles

Every commit in `merge_base..selected_commit` must use:

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
Existing nonconforming titles currently fail deliberately; this change does not rewrite them.
Rewording published history and advancing its parent pins is a separate reviewed operation.

## Updating locally

Initialize submodules with `git submodule update --init --recursive`.
The script uses Python 3 and Git; `--fetch` also uses authenticated `gh` to find comparison PRs.

```console
# Observe current upstream heads and complete histories.
python tools/submodule_divergence.py --fetch

# After staging a parent gitlink change, regenerate against those staged pins.
python tools/submodule_divergence.py --staged
git add docs/agents/submodule-divergence.csv

# Check the exact contents that will be committed, without network access.
python tools/submodule_divergence.py --staged --check
```

The pre-commit hook runs that last command when a gitlink, `.gitmodules`, the CSV, or its generator is staged.
It compares the staged CSV to staged parent gitlinks and recursively reads the selected child commits, regardless of checkout `HEAD` or unstaged edits.
An updated but unstaged CSV cannot satisfy the check.
Unrelated commits do not require initialized submodules.

Without `--staged`, generation and checks use committed parent gitlinks and the working CSV.
`--prepare --check` fetches complete histories and the **recorded** upstream commits, without advancing the snapshot; CI uses this for reproducible PR checks.
Checks return 1 for a stale CSV or invalid titles, and 2 for an operational error.
Generation writes only after every row succeeds; a failed fetch leaves the CSV unchanged.

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

PR validation recomputes the CSV and checks every local commit title.
A correct snapshot can therefore have a failing check until legacy titles are deliberately reworded.
To make this a merge gate, require the workflow's `check` job in the repository's branch rules.

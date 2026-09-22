---
name: commit-provenance
description: Resolve the exact active Codex Desktop and agent-runtime versions, model identifier, and reasoning effort for commit provenance. Use immediately before every Codex-authored git commit or whenever a commit trailer requires model, tool, or reasoning-effort attribution.
---

# Commit Provenance

Run `scripts/resolve.sh` immediately before creating the commit.
Do not reuse a previous result after a model or effort switch.

The script resolves the current task from `CODEX_THREAD_ID`, then reads the latest `turn_context` in that task's local session transcript.
If no transcript exists (as observed for side conversations), it reads the local `logs_2.sqlite` database in read-only mode using the bundled Python 3 helper.
The fallback requires matching thread and turn metadata from the last five minutes, selects the newest matching record, and reports its turn ID on stderr.
It never borrows a parent thread's settings.
Missing, stale, or unrecognized metadata causes failure; do not substitute saved defaults.
Runtime logs are an internal format: revalidate this fallback after format changes.
Treat the resolved per-turn evidence as authoritative for model and reasoning effort.
Never infer either from prose or use `config.toml` as the current-turn value.

## Commit trailer

Use the script's two output trailers unchanged:

```text
Co-Authored-By: Codex Desktop <desktop-version> (runtime codex-cli <runtime-version>) / <model> <codex@openai.com>
Codex-Reasoning-Effort: <effort>
```

If the script cannot identify every required value, stop and ask the user; do not create the commit with guessed provenance.
Preserve any stricter repository commit-message requirements.

## GitHub write transport

Use this provenance procedure together with the user-level Git transport instruction.
For GitHub Git writes—publishing a branch, pushing a commit, or updating a ref—use the configured SSH credential and an SSH remote such as `git@github.com:OWNER/REPO.git` whenever available.

Before a write:

1. Inspect the fetch and push URLs with `git remote -v` or `git remote get-url --push <remote>`.
2. If the push URL is HTTPS, use the equivalent SSH URL explicitly or configure a local SSH push URL when that is appropriate for the repository.
3. Do not retry an HTTPS write after an authentication or scope failure merely because the commit itself is valid.
4. If SSH authentication is unavailable, stop and report the write blocker; do not silently fall back to a credential known to lack write scope.

This transport rule does not authorize pushing, opening a pull request, or changing a remote when the user did not request that operation.
It prevents a requested GitHub write from wasting retries against the wrong credential.

#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'commit-provenance: %s\n' "$1" >&2
  exit 1
}

thread_id="${CODEX_THREAD_ID:-}"
[ -n "$thread_id" ] || fail 'CODEX_THREAD_ID is unavailable'

codex_root="${CODEX_HOME:-$HOME/.codex}"
session_file=$(find "$codex_root/sessions" -type f \
  -name "*-${thread_id}.jsonl" -print -quit 2>/dev/null)
[ -n "$session_file" ] || fail "no local session transcript for $thread_id"

turn_context=$(jq -sc '[.[] | select(.type == "turn_context")][-1].payload' \
  "$session_file")
model=$(jq -r '.model // empty' <<<"$turn_context")
effort=$(jq -r '.reasoning_effort // .effort // empty' <<<"$turn_context")
[ -n "$model" ] || fail 'latest turn context does not contain a model'
[ -n "$effort" ] || fail 'latest turn context does not contain reasoning effort'

app_path='/Applications/ChatGPT.app'
desktop_version=$(defaults read "$app_path/Contents/Info" \
  CFBundleShortVersionString 2>/dev/null || true)
runtime_version=$("$app_path/Contents/Resources/codex" --version 2>/dev/null \
  | awk 'NR == 1 { print $2 }')
[ -n "$desktop_version" ] || fail 'cannot identify Codex Desktop version'
[ -n "$runtime_version" ] || fail 'cannot identify bundled Codex runtime version'

printf 'Co-Authored-By: Codex Desktop %s (runtime codex-cli %s) / %s <codex@openai.com>\n' \
  "$desktop_version" "$runtime_version" "$model"
printf 'Codex-Reasoning-Effort: %s\n' "$effort"

#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
stack_dir="$root_dir/build/upstream-stack"

if [[ ! -f "$stack_dir/dumpthings.yaml" || ! -f "$stack_dir/admin-token" ]]; then
  echo "Run the serve-upstream launcher first." >&2
  exit 1
fi

export DTS_ADMIN_TOKEN="$(<"$stack_dir/admin-token")"
exec dump-things-service "$stack_dir/store" \
  --config "$stack_dir/dumpthings.yaml" \
  --host 127.0.0.1 \
  --port 8111 \
  --origins http://127.0.0.1:3000 \
  --log-level INFO

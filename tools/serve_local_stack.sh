#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
stack_dir="$root_dir/build/local-stack"
log_dir="$stack_dir/logs"
mkdir -p "$log_dir"

pids=()
names=()

cleanup() {
  trap - EXIT INT TERM
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  for pid in "${pids[@]:-}"; do
    wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

start_background() {
  local name="$1"
  shift
  echo "Starting $name (log: $log_dir/$name.log)"
  "$@" >"$log_dir/$name.log" 2>&1 &
  pids+=("$!")
  names+=("$name")
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local attempts=0
  while (( attempts < 120 )); do
    if python3 - "$url" <<'PY'
import sys
from urllib.request import urlopen

try:
    with urlopen(sys.argv[1], timeout=2):
        pass
except Exception:
    raise SystemExit(1)
PY
    then
      echo "$name is ready: $url"
      return 0
    fi
    ((attempts += 1))
    sleep 1
  done
  echo "$name did not become ready: $url" >&2
  return 1
}

start_background dump-things "$root_dir/tools/serve_local_dumpthings.sh"
wait_for_url "Dump Things" "http://127.0.0.1:8111/server"

python3 "$root_dir/tools/seed_local_pool.py"

start_background git-annex python3 "$root_dir/tools/serve_local_gitannex.py"
start_background shacl-vue python3 -m http.server 3000 --directory "$root_dir/submodules/pool.psychoinformatics.de-ui/dist/ui"
wait_for_url "SHACL Vue" "http://127.0.0.1:3000/config.yaml"
python3 "$root_dir/tools/check_local_stack.py"

start_background hugo-site python3 -m http.server 8767 --directory "$root_dir/build/upstream-local"
wait_for_url "Hugo site" "http://127.0.0.1:8767/"
echo "Local deployment is ready at http://127.0.0.1:8767/"
echo "Press Ctrl-C to stop all local services."

while :; do
  for index in "${!pids[@]}"; do
    if ! kill -0 "${pids[$index]}" 2>/dev/null; then
      echo "${names[$index]} exited unexpectedly; see $log_dir/${names[$index]}.log" >&2
      exit 1
    fi
  done
  sleep 1
done

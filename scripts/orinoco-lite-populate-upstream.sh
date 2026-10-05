#!/usr/bin/env bash
# Package-owned workflow. Caller has already selected the downstream environment.
set -euo pipefail

directory=sourcedata
destination=site-specific
api=https://pool.psychoinformatics.de/api
site_layout=submodule
supplied_dump=
site_specific=
reuse_dump=false
records_only=false
www_revision=
upstream_submodule=sourcedata/www-from-model
while [[ $# -gt 0 ]]; do
  case "$1" in
    --directory) directory=$2; shift 2 ;;
    --destination) destination=$2; shift 2 ;;
    --api) api=$2; shift 2 ;;
    --site-layout) site_layout=$2; shift 2 ;;
    --dump) supplied_dump=$2; shift 2 ;;
    --site-specific) site_specific=$2; shift 2 ;;
    --records-only) records_only=true; shift ;;
    --www-revision) www_revision=$2; shift 2 ;;
    --reuse-dump) reuse_dump=true; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
if $records_only && { ! $reuse_dump || [[ -n $www_revision || -n $site_specific || -n $supplied_dump ]]; }; then
  echo "--records-only requires --reuse-dump and cannot select site inputs." >&2; exit 2
fi
if ! python - <<'PYTHON'
from pathlib import Path
import sys
import tomllib

try:
    manifest = tomllib.loads(Path("pixi.toml").read_text())
    dependency = manifest.get("pypi-dependencies", {}).get("orinoco-lite")
    is_self = (isinstance(dependency, dict) and "path" in dependency
               and Path(dependency["path"]).resolve() == Path.cwd())
    sys.exit(0 if dependency is not None and not is_self else 1)
except (OSError, ValueError, TypeError):
    sys.exit(1)
PYTHON
then
  echo 'Populate requires an Orinoco Lite downstream. To create one from the engineering checkout, run `pixi run setup-upstream`.' >&2
  exit 2
fi
dump_path=$directory/downloaded/records.jsonl
git ls-files --error-unmatch -- pixi.toml >/dev/null 2>&1 &&
  git diff --quiet HEAD -- pixi.toml || {
  echo 'Record the package selection before populating the downstream.' >&2; exit 2;
}
[[ -z $supplied_dump || -f $supplied_dump ]] || { echo "Missing dump: $supplied_dump" >&2; exit 2; }
if $reuse_dump; then
  [[ -f $dump_path ]] || { echo "Missing retained dump: $dump_path" >&2; exit 2; }
  if ! git ls-files --error-unmatch -- "$dump_path" >/dev/null 2>&1 ||
      [[ -n $(git status --porcelain -- "$dump_path") ]]; then
    printf 'Save the retained dump before reusing it:\n  datalad save -m "chore: retain records dump" -- %q\n' "$dump_path" >&2
    exit 2
  fi
fi
set -x
if [[ -n $site_specific ]]; then
  datalad run -m "chore: install site-specific subdataset" -- \
    datalad install --dataset . --source "$site_specific" "$destination"
  exit
fi
if [[ ! -e $destination && $site_layout == submodule ]]; then
  datalad create --no-annex --dataset . "$destination"
fi
if [[ -n $supplied_dump ]]; then
  mkdir -p "$directory/downloaded"
  # Supplied bytes establish the replay boundary; the external path is not a
  # recoverable source for a recorded copy command.
  if [[ ! "$supplied_dump" -ef "$dump_path" ]]; then cp "$supplied_dump" "$dump_path"; fi
  saved_dump=("$dump_path")
  if [[ -f $supplied_dump.manifest.json ]]; then
    if [[ ! "$supplied_dump.manifest.json" -ef "$dump_path.manifest.json" ]]; then
      cp "$supplied_dump.manifest.json" "$dump_path.manifest.json"
    fi
    saved_dump+=("$dump_path.manifest.json")
  else
    if git ls-files --error-unmatch -- "$dump_path.manifest.json" >/dev/null 2>&1; then
      saved_dump+=("$dump_path.manifest.json")
    fi
    rm -f -- "$dump_path.manifest.json"
  fi
  datalad save -m "chore: retain supplied records dump

Retain supplied bytes as inputs for subsequent recorded transformations.
The original acquisition was not executed by this workflow." -- "${saved_dump[@]}"

elif ! $reuse_dump; then
  datalad run --explicit -m "chore: download records dump" \
    --input pixi.toml \
    --output "$dump_path" --output "$dump_path.manifest.json" -- \
    orinoco-lite dev records get --output "$dump_path" --api "$api" --force
fi

datalad run --explicit -m "chore: convert records dump" \
  --input pixi.toml --input "$dump_path" \
  --output "$destination/metadata" -- \
  orinoco-lite dev records jsonl-to-yaml \
    --source "$dump_path" --destination "$destination" --force

if $records_only; then exit 0; fi
checkout_args=(orinoco-lite dev upstream checkout)
if [[ -n $www_revision ]]; then checkout_args+=(--revision "$www_revision"); fi
"${checkout_args[@]}"
# Save the selection of existing upstream history, then record its transformation.
datalad save -m "chore: select upstream website submodule" -- .gitmodules "$upstream_submodule"
# The importer retrieves and verifies selected Annex media; do not get the whole site.
datalad run --explicit -m "chore: import upstream site inputs" \
  --input "$upstream_submodule" --assume-ready inputs \
  --input pixi.toml \
  --input pyproject.toml --output pyproject.toml --output "$destination/content" \
  --output "$destination/assets" --output "$destination/static" \
  --output "$destination/overrides" -- \
  orinoco-lite dev upstream import-from-www --source "$upstream_submodule" \
    --media-remote https://hub.psychoinformatics.de/www/www-from-model.git --destination "$destination" --force

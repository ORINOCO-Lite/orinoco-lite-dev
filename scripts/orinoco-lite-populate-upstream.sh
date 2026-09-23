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
while [[ $# -gt 0 ]]; do
  case "$1" in
    --directory) directory=$2; shift 2 ;;
    --destination) destination=$2; shift 2 ;;
    --api) api=$2; shift 2 ;;
    --site-layout) site_layout=$2; shift 2 ;;
    --dump) supplied_dump=$2; shift 2 ;;
    --site-specific) site_specific=$2; shift 2 ;;
    --reuse-dump) reuse_dump=true; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
dump_path=$directory/downloaded/records.jsonl
[[ -f pixi.toml && -f pixi.lock ]] || { echo 'Populate requires the downstream Pixi selection and lock.' >&2; exit 2; }
git ls-files --error-unmatch -- pixi.toml pixi.lock >/dev/null 2>&1 &&
  git diff --quiet HEAD -- pixi.toml pixi.lock || {
  echo 'Record the package selection and lock before populating the downstream.' >&2; exit 2;
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
    --input pixi.toml --input pixi.lock \
    --output "$dump_path" --output "$dump_path.manifest.json" -- \
    orinoco-lite dev records get --output "$dump_path" --api "$api" --force
fi

datalad run --explicit -m "chore: convert records dump" \
  --input pixi.toml --input pixi.lock --input "$dump_path" \
  --output "$destination/metadata" -- \
  orinoco-lite dev records jsonl-to-yaml \
    --source "$dump_path" --destination "$destination" --force

datalad run --explicit -m "chore: import upstream site inputs" \
  --input pixi.toml --input pixi.lock \
  --output "$destination/site.yaml" --output "$destination/content" \
  --output "$destination/assets" --output "$destination/static" \
  --output "$destination/overrides" -- \
  orinoco-lite dev upstream import-from-www --destination "$destination" --force

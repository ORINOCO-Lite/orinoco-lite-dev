#!/usr/bin/env bash
# Invoked by the engineering Pixi task; preparation is recorded one step at a time.
set -euo pipefail

usage() {
  cat <<'HELP'
Usage: pixi run setup-upstream [DESTINATION] [OPTIONS]

Create a downstream from a published template revision and populate it from upstream.
Stops before projection, building, comparison, or deployment.

  DESTINATION               New downstream (default: ../orinoco-lite-test-downstream)
  --template PATH           Checkout selecting the template remote (default: ../orinoco-lite-template)
  --template-ref REV        Template revision (default: HEAD)
  --snapshot PATH           Copy an existing JSONL capture instead of fetching
  --package-repository URL  Package Git remote (default: engineering origin)
  --package-revision REV    Fetchable package revision (default: engineering HEAD)
  --api URL                 Public Pool API (default: https://pool.psychoinformatics.de/api)
  --site-specific PATH      Install an existing dataset as a submodule; skip imports
  --site-layout MODE        New inputs: submodule (default) or directory
  -h, --help                Show this help

Paths are relative to the engineering directory. Existing destinations are refused.
The package commit must be remotely fetchable. No editable installation is used.
HELP
}

# Internal path calculations may be absolute; every recorded command uses relative paths.
relative_to() {
  python -c 'import os, sys; print(os.path.relpath(os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])))' "$1" "$2"
}

engineering=$PWD
destination=../orinoco-lite-test-downstream
template=../orinoco-lite-template
template_ref=HEAD
snapshot=
site_specific=
site_layout=submodule
api=https://pool.psychoinformatics.de/api
package_repository=$(git remote get-url origin)
package_revision=$(git rev-parse HEAD)
if [[ $# -gt 0 && $1 != -* ]]; then destination=$1; shift; fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --template|--template-ref|--snapshot|--api|--site-specific|--site-layout|--package-repository|--package-revision)
      if [[ $# -lt 2 ]]; then printf 'Missing value for %s\n' "$1" >&2; exit 2; fi
      case "$1" in
        --template) template=$2 ;;
        --template-ref) template_ref=$2 ;;
        --snapshot) snapshot=$2 ;;
        --api) api=$2 ;;
        --site-specific) site_specific=$2 ;;
        --site-layout) site_layout=$2 ;;
        --package-repository) package_repository=$2 ;;
        --package-revision) package_revision=$2 ;;
      esac
      shift 2 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done
[[ -f release/package-resources.yaml ]] || { echo 'Run through the engineering Pixi task.' >&2; exit 2; }
[[ ! -e $destination && ! -L $destination ]] || { echo "Destination already exists: $destination" >&2; exit 2; }
[[ -d $template ]] || { echo "Missing template: $template" >&2; exit 2; }
[[ $site_layout == submodule || $site_layout == directory ]] || { echo 'Use --site-layout submodule or directory.' >&2; exit 2; }
[[ -z $snapshot || -f $snapshot ]] || { echo "Missing snapshot: $snapshot" >&2; exit 2; }
[[ -z $site_specific || -d $site_specific ]] || { echo "Missing site-specific dataset: $site_specific" >&2; exit 2; }
[[ -z $snapshot || -z $site_specific ]] || { echo 'Choose --snapshot or --site-specific, not both.' >&2; exit 2; }

# Verify the actual remote before creating anything; never silently publish or
# substitute an editable checkout for an unavailable package candidate.
package_commit=$(orinoco-lite package update --check \
  --repository "$package_repository" --revision "$package_revision")

template_ref=$(git -C "$template" rev-parse "$template_ref^{commit}")
template_repository=$(git -C "$template" remote get-url origin)
template_ref=$(orinoco-lite package update --check \
  --repository "$template_repository" --revision "$template_ref")
if [[ -n $snapshot ]]; then snapshot_relative=$(relative_to "$snapshot" "$destination"); fi
if [[ -n $site_specific ]]; then site_relative=$(relative_to "$site_specific" "$destination"); fi
destination=$(relative_to "$destination" "$engineering")

# Show commands and arguments as they execute, including the environment boundary.
set -x
datalad create --no-annex "$destination"
cd "$destination"
pixi exec --spec datalad --spec copier -- datalad run \
  -m "chore: create downstream from template

Executed through:
pixi exec --spec datalad --spec copier -- datalad run

DataLad records the Copier command; this note records its Pixi bootstrap." -- \
  copier copy --defaults --vcs-ref "$template_ref" \
    -d include_site_specific=false "$template_repository" .

# Still in the inherited engineering environment. Lock the immutable candidate;
# the current process keeps its environment until the single switch below.
datalad run --explicit -m "chore: select Orinoco Lite package candidate" \
  --output pixi.toml --output pixi.lock -- \
  orinoco-lite package update \
    --repository "$package_repository" --revision "$package_commit"

populate=(orinoco-lite dev upstream populate --api "$api" --site-layout "$site_layout")
if [[ -n $snapshot ]]; then populate+=(--snapshot "$snapshot_relative"); fi
if [[ -n $site_specific ]]; then populate+=(--site-specific "$site_relative"); fi
# Switch once. The installed package owns the workflow, and all its commands
# inherit this downstream environment. No workflow files are copied into the site.
pixi run --manifest-path pixi.toml "${populate[@]}"
set +x
printf '\nSetup complete in %s. Build separately with pixi run build.\n' "$PWD"

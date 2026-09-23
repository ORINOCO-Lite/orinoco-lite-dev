#!/usr/bin/env bash
# Invoked by the engineering Pixi task; preparation is recorded one step at a time.
set -euo pipefail

usage() {
  cat <<'HELP'
Usage: pixi run setup-upstream [DESTINATION] [OPTIONS]

Create and populate a downstream; stop before projection and building.
Uses template origin/main and the package version and lock supplied by that template.

  DESTINATION               New directory (default: ../orinoco-lite-test-downstream)

Inputs:
  --dump PATH               Import an existing JSONL dump and upstream site files
  --site-specific PATH      Use an existing dataset as a submodule instead of importing
  --api URL                 Fetch a dump when neither input above is supplied
                            (default: https://pool.psychoinformatics.de/api)
  --site-layout MODE        Store imported inputs as submodule (default) or directory;
                            ignored with --site-specific

Version overrides (optional):
  --local-heads             Use committed template and package HEADs from local checkouts
                            (package remote: engineering origin; explicit overrides win)
  --template PATH           Checkout whose origin supplies the template
                            (default: ../orinoco-lite-template)
  --template-ref REV        Use a template revision from that checkout
  --package-repository URL  Replace the package repository, keeping its selected revision
  --package-revision REV    Replace the package revision, keeping its selected repository

  -h, --help                Show this help

Paths are relative to the engineering directory. Selected commits must be
available from their remotes; uncommitted changes are not included.

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
local_heads=false
explicit_template_ref=false
explicit_package_revision=false
dump=
site_specific=
site_layout=submodule
api=https://pool.psychoinformatics.de/api
package_repository=
package_revision=
if [[ $# -gt 0 && $1 != -* ]]; then destination=$1; shift; fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --local-heads) local_heads=true; shift ;;
    --template|--template-ref|--dump|--api|--site-specific|--site-layout|--package-repository|--package-revision)
      if [[ $# -lt 2 ]]; then printf 'Missing value for %s\n' "$1" >&2; exit 2; fi
      case "$1" in
        --template) template=$2 ;;
        --template-ref) template_ref=$2; explicit_template_ref=true ;;
        --dump) dump=$2 ;;
        --api) api=$2 ;;
        --site-specific) site_specific=$2 ;;
        --site-layout) site_layout=$2 ;;
        --package-repository) package_repository=$2 ;;
        --package-revision) package_revision=$2; explicit_package_revision=true ;;
      esac
      shift 2 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done
[[ -f release/package-resources.yaml ]] || { echo 'Run through the engineering Pixi task.' >&2; exit 2; }
[[ ! -e $destination && ! -L $destination ]] || { echo "Destination already exists: $destination" >&2; exit 2; }
[[ -d $template ]] || { echo "Missing template: $template" >&2; exit 2; }
[[ $site_layout == submodule || $site_layout == directory ]] || { echo 'Use --site-layout submodule or directory.' >&2; exit 2; }
[[ -z $dump || -f $dump ]] || { echo "Missing dump: $dump" >&2; exit 2; }
[[ -z $site_specific || -d $site_specific ]] || { echo "Missing site-specific dataset: $site_specific" >&2; exit 2; }
[[ -z $dump || -z $site_specific ]] || { echo 'Choose --dump or --site-specific, not both.' >&2; exit 2; }

template_repository=$(git -C "$template" remote get-url origin)
if $local_heads; then
  package_repository=${package_repository:-$(git remote get-url origin)}
  if ! $explicit_package_revision; then
    package_revision=$(git rev-parse HEAD)
  fi
fi
if $explicit_template_ref || $local_heads; then
  if [[ $template_ref == HEAD ]]; then
    template_branch=$(git -C "$template" symbolic-ref --quiet --short HEAD || true)
  else
    template_branch=$(git -C "$template" rev-parse --symbolic-full-name "$template_ref")
  fi
  template_selection="local $template_ref (${template_branch:-detached commit})"
  template_ref=$(git -C "$template" rev-parse "$template_ref^{commit}")
else
  template_ref=refs/heads/main
  template_selection='remote branch main'
fi

# Freeze the template selection before Copier runs. Its generated dependency
# declaration owns the package default, including when template main advances.
template_commit=$(orinoco-lite package update --check \
  --repository "$template_repository" --revision "$template_ref")
printf '\nSelected template: %s\n  Source: %s\n  Commit: %s\n' \
  "$template_repository" "$template_selection" "$template_commit"
if [[ -n $dump ]]; then dump_relative=$(relative_to "$dump" "$destination"); fi
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
  copier copy --defaults --vcs-ref "$template_commit" \
    -d include_site_specific=false "$template_repository" .

# Read the dependency produced by the selected template, not the local template
# checkout or its answers file. Preserve the bundled lock unless overridden.
package_defaults=$(python - <<'PYTHON'
import tomllib
from pathlib import Path
selection = tomllib.loads(Path("pixi.toml").read_text())["pypi-dependencies"]["orinoco-lite"]
for key in ("git", "rev"):
    value = selection[key]
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        raise SystemExit(f"Template package {key} must be a non-empty value without whitespace")
    print(value)
PYTHON
)
template_package_repository=$(printf '%s\n' "$package_defaults" | sed -n '1p')
template_package_revision=$(printf '%s\n' "$package_defaults" | sed -n '2p')
if [[ -n $package_repository || -n $package_revision ]]; then
  package_repository=${package_repository:-$template_package_repository}
  package_revision=${package_revision:-$template_package_revision}
  package_commit=$(orinoco-lite package update --check \
    --repository "$package_repository" --revision "$package_revision")
  # Still in the inherited engineering environment. Record the override before
  # switching to the downstream environment below.
  datalad run --explicit -m "chore: select Orinoco Lite package candidate" \
    --output pixi.toml --output pixi.lock -- \
    orinoco-lite package update \
      --repository "$package_repository" --revision "$package_commit"
  package_selection='development override'
else
  package_repository=$template_package_repository
  package_commit=$template_package_revision
  package_selection='selected template dependency (bundled lock retained)'
fi
printf '\nSelected package: %s\n  Source: %s\n  Revision: %s\n' \
  "$package_repository" "$package_selection" "$package_commit"

populate=(orinoco-lite dev upstream populate --api "$api" --site-layout "$site_layout")
if [[ -n $dump ]]; then populate+=(--dump "$dump_relative"); fi
if [[ -n $site_specific ]]; then populate+=(--site-specific "$site_relative"); fi
# Switch once. The installed package owns the workflow, and all its commands
# inherit this downstream environment. No workflow files are copied into the site.
pixi run --manifest-path pixi.toml "${populate[@]}"
set +x
printf '\nSetup complete in %s. Build separately with pixi run build.\n' "$PWD"

#!/usr/bin/env bash
# Invoked by the engineering Pixi task; preparation is recorded one step at a time.
set -euo pipefail

usage() {
  cat <<'HELP'
Usage: pixi run setup-upstream [DESTINATION] [OPTIONS]

Create and populate a downstream; optionally continue through a recorded build.
Uses template origin/main and the current engineering package commit.

  DESTINATION               New directory (default: ../orinoco-lite-test-downstream)

Inputs:
  --dump PATH               Import an existing JSONL dump and upstream site files
  --site-specific PATH      Use an existing dataset as a submodule instead of importing;
                            root site settings use the template defaults
  --api URL                 Fetch a dump when neither input above is supplied
                            (default: https://pool.psychoinformatics.de/api)
  --site-layout MODE        Store imported inputs as submodule (default) or directory;
                            ignored with --site-specific
  --build                   Build and retain a publication bundle after preparation;
                            does not publish or deploy

Version overrides (optional):
  --local-heads             Also use the committed local template HEAD
                            (explicit overrides win)
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
  python -c 'import os, sys; print(os.path.relpath(os.path.realpath(sys.argv[1]), os.path.realpath(sys.argv[2])))' "$1" "$2"
}

engineering=$PWD
destination=../orinoco-lite-test-downstream
template=../orinoco-lite-template
template_ref=HEAD
local_heads=false
explicit_template_ref=false
dump=
site_specific=
site_layout=submodule
api=https://pool.psychoinformatics.de/api
package_repository=
package_revision=
build=false
if [[ $# -gt 0 && $1 != -* ]]; then destination=$1; shift; fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --local-heads) local_heads=true; shift ;;
    --build) build=true; shift ;;
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
[[ -z $dump || -f $dump ]] || { echo "Missing dump: $dump" >&2; exit 2; }
[[ -z $site_specific || -d $site_specific ]] || { echo "Missing site-specific dataset: $site_specific" >&2; exit 2; }
[[ -z $dump || -z $site_specific ]] || { echo 'Choose --dump or --site-specific, not both.' >&2; exit 2; }

template_repository=$(git -C "$template" remote get-url origin)
if [[ -z $package_repository ]]; then
  package_repository=$(git remote get-url origin)
  # Public GitHub inputs must be recoverable without the maintainer's SSH setup.
  case "$package_repository" in
    git@github.com:*) package_repository="https://github.com/${package_repository#git@github.com:}" ;;
    ssh://git@github.com/*) package_repository="https://github.com/${package_repository#ssh://git@github.com/}" ;;
  esac
fi
package_revision=${package_revision:-$(git rev-parse HEAD)}
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

# Resolve both selections before creating a downstream. Unpublished package
# commits must fail here rather than leaving a partially populated dataset.
template_commit=$(orinoco-lite package update --check \
  --repository "$template_repository" --revision "$template_ref")
package_commit=$(orinoco-lite package update --check \
  --repository "$package_repository" --revision "$package_revision")
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

# Still in the inherited engineering environment. Record the exact candidate
# and update the template's lock before switching to the downstream environment.
datalad run --explicit -m "chore: select Orinoco Lite package candidate" \
  --output pixi.toml --output pixi.lock -- \
  orinoco-lite package update \
    --repository "$package_repository" --revision "$package_commit"
printf '\nSelected package: %s\n  Revision: %s\n' \
  "$package_repository" "$package_commit"

populate=(orinoco-lite dev upstream populate --api "$api" --site-layout "$site_layout")
if [[ -n $dump ]]; then populate+=(--dump "$dump_relative"); fi
if [[ -n $site_specific ]]; then populate+=(--site-specific "$site_relative"); fi
# Switch once. The installed package owns the workflow, and all its commands
# inherit this downstream environment. No workflow files are copied into the site.
pixi run --manifest-path pixi.toml "${populate[@]}"
if $build; then
  pixi run --manifest-path pixi.toml orinoco-lite build --destination build/site \
    --publication-bundle build/pages-publication.bundle
fi
set +x
if $build; then
  printf '\nSetup and build complete in %s. Publication bundle: build/pages-publication.bundle\n' "$PWD"
else
  printf '\nSetup complete in %s. Build separately with pixi run build.\n' "$PWD"
fi

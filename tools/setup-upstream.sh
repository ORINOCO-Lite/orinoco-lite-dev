#!/usr/bin/env bash
# Invoked by the engineering Pixi task; preparation is recorded one step at a time.
set -euo pipefail

usage() {
  cat <<'HELP'
Usage: pixi run setup-upstream [DESTINATION] [OPTIONS]

Create a downstream from upstream inputs.
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
  --site-specific-url URL   Register the new subdataset’s published repository; does not push
  --build                   Also build the site and publication bundle
  --development             Register the selected package as a submodule and install editable
  --force                   Replace the destination, including local changes
  --non-interactive         Skip the review pause

Version overrides (optional):
  --local-heads             Also use the committed local template HEAD
                            (explicit overrides win)
  --template PATH           Checkout whose origin supplies the template
                            (default: ../orinoco-lite-template)
  --template-ref REV        Use a template revision from that checkout
  --package-repository URL  Replace the package repository, keeping its selected revision
  --package-revision REV    Replace the package revision, keeping its selected repository

  -h, --help                Show this help

Paths are relative to the engineering directory. Publish selected commits
before setup. In an existing downstream, `pixi run orinoco-lite dev enable`
installs a locally ignored checkout at .orinoco-lite/orinoco-lite-dev editable.

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
site_specific_url=
development=false
site_layout=submodule
api=https://pool.psychoinformatics.de/api
package_repository=
package_revision=
build=false
force=false
non_interactive=false
if [[ $# -gt 0 && $1 != -* ]]; then destination=$1; shift; fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --local-heads) local_heads=true; shift ;;
    --build) build=true; shift ;;
    --development) development=true; shift ;;
    --force) force=true; shift ;;
    --non-interactive) non_interactive=true; shift ;;
    --template|--template-ref|--dump|--api|--site-specific|--site-specific-url|--site-layout|--package-repository|--package-revision)
      if [[ $# -lt 2 ]]; then printf 'Missing value for %s\n' "$1" >&2; exit 2; fi
      case "$1" in
        --template) template=$2 ;;
        --template-ref) template_ref=$2; explicit_template_ref=true ;;
        --dump) dump=$2 ;;
        --api) api=$2 ;;
        --site-specific) site_specific=$2 ;;
        --site-specific-url) site_specific_url=$2 ;;
        --site-layout) site_layout=$2 ;;
        --package-repository) package_repository=$2 ;;
        --package-revision) package_revision=$2 ;;
      esac
      shift 2 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done
[[ -f release/package-resources.yaml ]] || { echo 'Run through the engineering Pixi task.' >&2; exit 2; }
[[ -d $template ]] || { echo "Missing template: $template" >&2; exit 2; }
[[ $site_layout == submodule || $site_layout == directory ]] || { echo 'Use --site-layout submodule or directory.' >&2; exit 2; }
[[ -z $dump || -f $dump ]] || { echo "Missing dump: $dump" >&2; exit 2; }
[[ -z $site_specific || -d $site_specific ]] || { echo "Missing site-specific dataset: $site_specific" >&2; exit 2; }
[[ -z $dump || -z $site_specific ]] || { echo 'Choose --dump or --site-specific, not both.' >&2; exit 2; }

if [[ -n $site_specific_url && ( $site_layout != submodule || -n $site_specific ) ]]; then
  echo '--site-specific-url requires a newly imported submodule.' >&2; exit 2
fi

template_repository=$(git -C "$template" remote get-url origin)
case "$template_repository" in
  git@github.com:*) template_repository="https://github.com/${template_repository#git@github.com:}" ;;
  ssh://git@github.com/*) template_repository="https://github.com/${template_repository#ssh://git@github.com/}" ;;
esac
if [[ -z $package_repository ]]; then
  package_repository=$(git remote get-url origin)
  # Public GitHub inputs must be recoverable without the maintainer's SSH setup.
  case "$package_repository" in
    git@github.com:*) package_repository="https://github.com/${package_repository#git@github.com:}" ;;
    ssh://git@github.com/*) package_repository="https://github.com/${package_repository#ssh://git@github.com/}" ;;
  esac
fi
package_selection=${package_revision:-"$(git symbolic-ref --quiet --short HEAD || printf detached), engineering HEAD"}
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
printf 'Resolving package and template revisions...\n' >&2
template_commit=$(orinoco-lite package update --check \
  --repository "$template_repository" --revision "$template_ref")
package_commit=$(orinoco-lite package update --check \
  --repository "$package_repository" --revision "$package_revision")
check_destination() {
  if [[ -e $destination || -L $destination ]]; then
    if ! $force; then
      echo "Destination already exists: $destination (use --force to replace it)" >&2
      exit 2
    fi
    # Refuse paths containing this checkout or any selected local input.
    python - "$destination" "$engineering" "$HOME" "$template" "$dump" "$site_specific" <<'PY'
from pathlib import Path
import sys

target = Path(sys.argv[1])
if target.is_symlink():
    sys.exit("Refusing to replace a symlink destination")
target = target.resolve()
for value in sys.argv[2:]:
    if value and Path(value).resolve().is_relative_to(target):
        sys.exit(f"Refusing to remove destination containing a protected path: {target}")
PY
  fi
}
check_destination
python "$(dirname "${BASH_SOURCE[0]}")/setup-upstream-summary.py" \
  --package "$engineering" "$package_repository" "$package_commit" \
  --template "$template" "$template_repository" "$template_commit" \
  --package-selection "$package_selection" --template-selection "$template_selection" \
  --destination "$destination" --dump "$dump" --site-specific "$site_specific" \
  --api "$api" --site-layout "$site_layout" --build "$build" \
  --development "$development"
if ! $non_interactive; then
  if [[ ! -t 0 ]]; then
    echo 'Setup requires terminal input; pass --non-interactive for unattended execution.' >&2
    exit 2
  fi
  printf '\nPress any key to continue, or Ctrl-C to cancel: ' >&2
  if ! IFS= read -r -s -n 1; then
    printf '\nSetup cancelled; destination unchanged.\n' >&2
    exit 2
  fi
  printf '\n' >&2
fi
# Recheck after the pause in case the destination changed while waiting.
check_destination
if [[ -e $destination || -L $destination ]]; then
  # Annex object directories are read-only. Only directories need write
  # permission for deletion; do not follow Annex symlinks or chmod file bytes.
  find "$destination" -type d -exec chmod u+w {} +
  rm -rf -- "$destination"
fi
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

populate=(orinoco-lite dev upstream populate --api "$api" --site-layout "$site_layout")
if [[ -n $dump ]]; then populate+=(--dump "$dump_relative"); fi
if [[ -n $site_specific ]]; then populate+=(--site-specific "$site_relative"); fi
# Switch once. The installed package owns the workflow, and all its commands
# inherit this downstream environment. No workflow files are copied into the site.
pixi run --manifest-path pixi.toml "${populate[@]}"
if [[ -n $site_specific_url ]]; then
  pixi run datalad run --explicit --output .gitmodules \
    -m "chore: register published site-input repository" -- \
    git submodule set-url site-specific "$site_specific_url"
  pixi run datalad -C site-specific siblings configure --name origin --url "$site_specific_url"
fi
if $development; then
  checkout=.orinoco-lite/orinoco-lite-dev
  git submodule add -- "$package_repository" "$checkout"
  git -C "$checkout" checkout --quiet --detach "$package_commit"
  git -C "$checkout" submodule update --init --recursive
  datalad save -m "chore: register development package" -- .gitmodules "$checkout"
  datalad run --explicit -m "chore: enable editable Orinoco Lite" \
    --output pixi.toml -- pixi run --manifest-path pixi.toml orinoco-lite dev enable
fi
if $build; then
  pixi run --manifest-path pixi.toml orinoco-lite build --destination build/site \
    --publication-bundle build/pages-publication.bundle
fi
set +x
if $build; then
  printf '\nSetup and build complete in %s. Publication bundle: build/pages-publication.bundle\n' "$PWD"
else
  printf '\nSetup complete in %s. Build separately with pixi run build (or add --build to the task invocation next time).\n' "$PWD"
fi

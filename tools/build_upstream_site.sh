#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
site_root="$repository_root/submodules/www-from-model"
base_url=${BASE_URL:-http://127.0.0.1:1313/}
destination=${DESTINATION:-$repository_root/build/upstream-psychoinformatics}
edit_url=${SHACL_VUE_URL:-https://pool.psychoinformatics.de/ui/}
annex_commit=010ca44f751d2ab60b9d4ad58c5931d1804e3c9e
upstream_url=https://hub.psychoinformatics.de/www/www-from-model.git
annex_remote_name=clean-migration-upstream-$$
annex_remote_ref=refs/remotes/$annex_remote_name/git-annex

original_core_worktree=
had_core_worktree=false
if original_core_worktree=$(git -C "$site_root" config --get core.worktree 2>/dev/null); then
  had_core_worktree=true
fi

restore_local_state() {
  git -C "$site_root" update-ref -d "$annex_remote_ref" 2>/dev/null || true
  git -C "$site_root" config --remove-section \
    "remote.$annex_remote_name" 2>/dev/null || true
  if [[ "$had_core_worktree" == true ]]; then
    git -C "$site_root" config core.worktree "$original_core_worktree"
  else
    git -C "$site_root" config --unset-all core.worktree 2>/dev/null || true
  fi
}
trap restore_local_state EXIT

site_git() {
  git -c core.worktree="$site_root" -C "$site_root" "$@"
}

base_url=${base_url%/}/
destination=$(python3 -c \
  'import sys; from pathlib import Path; print(Path(sys.argv[1]).resolve())' \
  "$destination")
case "$destination/" in
  "$repository_root/build/"* | /tmp/* | /private/tmp/*) ;;
  *)
    echo "DESTINATION must be below $repository_root/build or a temporary directory" >&2
    exit 2
    ;;
esac
base_path=$(python3 -c \
  'import sys; from urllib.parse import urlsplit; print(urlsplit(sys.argv[1]).path or "/")' \
  "$base_url")

git -C "$repository_root" submodule sync -- submodules/www-from-model
if git -C "$site_root" rev-parse --git-dir >/dev/null 2>&1; then
  if [[ -n "$(site_git status --porcelain)" ]]; then
    echo "Refusing to update a modified www-from-model worktree" >&2
    exit 2
  fi
fi
git -C "$repository_root" submodule update --init --depth 1 -- submodules/www-from-model
site_git submodule update --init --depth 1 -- themes/congo

site_git fetch --no-write-fetch-head \
  "$upstream_url" "+$annex_commit:$annex_remote_ref"
site_git -c annex.private=true annex init
site_git \
  -c annex.private=true \
  -c remote.$annex_remote_name.url="$upstream_url" \
  -c remote.$annex_remote_name.fetch=+refs/heads/\*:refs/remotes/$annex_remote_name/\* \
  annex get --from "$annex_remote_name" .
test -z "$(site_git -c annex.private=true annex find --not --in=here)"

hugo version | grep -q 'hugo v0\.154\.5.*extended'
hugo \
  --minify \
  --cleanDestinationDir \
  --source "$site_root" \
  --destination "$destination" \
  --baseURL "$base_url"

python3 "$repository_root/tools/adapt_upstream_pages.py" \
  "$destination" \
  --base-path "$base_path" \
  --edit-url "$edit_url"
python3 "$repository_root/tools/adapt_upstream_pages.py" \
  "$destination" \
  --base-path "$base_path" \
  --edit-url "$edit_url" \
  --check-only

printf 'Built the upstream site at %s\n' "$destination"

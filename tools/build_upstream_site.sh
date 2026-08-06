#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
site_root="$repository_root/submodules/www-from-model"
base_url=${BASE_URL:-http://127.0.0.1:1313/}
destination=${DESTINATION:-$repository_root/build/upstream-psychoinformatics}
annex_commit=010ca44f751d2ab60b9d4ad58c5931d1804e3c9e
upstream_url=https://hub.psychoinformatics.de/www/www-from-model.git

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
  git -C "$site_root" config core.worktree "$site_root"
  if [[ -n "$(git -C "$site_root" status --porcelain)" ]]; then
    echo "Refusing to update a modified www-from-model worktree" >&2
    exit 2
  fi
fi
git -C "$repository_root" submodule update --init --depth 1 -- submodules/www-from-model
git -C "$site_root" config core.worktree "$site_root"
git -C "$site_root" submodule update --init --depth 1 -- themes/congo

if git -C "$site_root" remote get-url upstream >/dev/null 2>&1; then
  test "$(git -C "$site_root" remote get-url upstream)" = "$upstream_url"
else
  git -C "$site_root" remote add upstream "$upstream_url"
fi

git -C "$site_root" fetch --depth 1 \
  origin "+$annex_commit:refs/remotes/origin/git-annex"
git -C "$site_root" fetch --depth 1 \
  upstream "+$annex_commit:refs/remotes/upstream/git-annex"
git -C "$site_root" config --replace-all annex.private true
git -C "$site_root" annex init
git -C "$site_root" annex get .
test -z "$(git -C "$site_root" annex find --not --in=here)"

hugo version | grep -q 'hugo v0\.154\.5.*extended'
hugo \
  --minify \
  --cleanDestinationDir \
  --source "$site_root" \
  --destination "$destination" \
  --baseURL "$base_url"

python3 "$repository_root/tools/adapt_upstream_pages.py" \
  "$destination" \
  --base-path "$base_path"
python3 "$repository_root/tools/adapt_upstream_pages.py" \
  "$destination" \
  --base-path "$base_path" \
  --check-only

printf 'Built the upstream site at %s\n' "$destination"

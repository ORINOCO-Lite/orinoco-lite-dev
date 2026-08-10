#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
shacl_root="$repository_root/submodules/shacl-vue"
patch_file="$repository_root/patches/shacl-vue/form-editor-show-all-fields.patch"

git -C "$repository_root" submodule update --init --depth 1 -- submodules/shacl-vue

if git -C "$shacl_root" apply --check "$patch_file" >/dev/null 2>&1; then
  git -C "$shacl_root" apply "$patch_file"
elif git -C "$shacl_root" apply --reverse --check "$patch_file" >/dev/null 2>&1; then
  :
else
  echo "The pinned shacl-vue checkout cannot accept the local compatibility patch" >&2
  exit 2
fi

npm --prefix "$shacl_root" ci

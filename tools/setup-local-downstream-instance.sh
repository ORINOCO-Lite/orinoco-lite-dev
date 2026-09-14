#!/usr/bin/env bash
set -euo pipefail

# Recreate a disposable downstream using local checkouts whenever possible.
# Use --populate to clone only repositories that are missing locally.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="/tmp/orinoco-lite-test-downstream"
TEMPLATE="$ROOT/../orinoco-lite-template"
PACKAGE="$ROOT"
SITE_SPECIFIC="$ROOT/../con-site-specific"
POPULATE=false

usage() {
    cat <<'EOF'
Usage: setup-local-downstream-instance.sh [--populate]

  --populate  clone a missing repository using its configured origin URL

The sibling checkouts ../orinoco-lite-template and ../con-site-specific are
used directly. The disposable downstream is /tmp/orinoco-lite-test-downstream.
EOF
}

while (($#)); do
    case "$1" in
        --populate) POPULATE=true ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
    shift
done

repo_remote() { git -C "$1" remote get-url origin 2>/dev/null || true; }

ensure_repo() {
    local name="$1" path="$2" remote="$3"
    if [[ -d "$path/.git" || -f "$path/.git" ]]; then
        printf 'Using local %s: %s\n' "$name" "$path"
        return
    fi
    if [[ "$POPULATE" != true ]]; then
        printf 'Missing %s checkout: %s\nRun with --populate to clone it.\n' \
            "$name" "$path" >&2
        exit 1
    fi
    [[ -n "$remote" ]] || {
        printf 'Cannot populate %s: no origin URL is available.\n' "$name" >&2
        exit 1
    }
    git clone "$remote" "$path"
}

TEMPLATE_REMOTE="${TEMPLATE_REMOTE:-$(repo_remote "$TEMPLATE")}"
PACKAGE_REMOTE="${PACKAGE_REMOTE:-$(repo_remote "$PACKAGE")}"
SITE_SPECIFIC_REMOTE="${SITE_SPECIFIC_REMOTE:-$(repo_remote "$SITE_SPECIFIC")}"
ensure_repo template "$TEMPLATE" "$TEMPLATE_REMOTE"
ensure_repo package "$PACKAGE" "$PACKAGE_REMOTE"
ensure_repo site-specific "$SITE_SPECIFIC" "$SITE_SPECIFIC_REMOTE"

rm -rf -- "$WORK_DIR"

printf 'Disposable downstream: %s\n' "$WORK_DIR"

pixi exec --spec datalad --spec git -- \
    datalad create --no-annex \
    -m "chore: initialize DataLad dataset" "$WORK_DIR"
cd "$WORK_DIR"

pixi exec --spec datalad --spec copier -- \
    datalad run -m 'instantiate template' -- \
    copier copy --vcs-ref HEAD \
    -d include_site_specific=false \
    -d pr_previews=netlify \
    "$TEMPLATE" .

pixi exec --spec datalad --spec copier -- datalad run \
    -m "Add site-specific subdataset" -- \
    datalad install --dataset . --source "$SITE_SPECIFIC" site-specific

pixi exec --spec datalad --spec copier -- datalad run \
    -m 'link local package checkout' -- bash -c '
    ln -s "$1" .orinoco-lite/dev
    printf "\\n/.orinoco-lite/dev\\n" >> .gitignore
' -- "$PACKAGE"

pixi exec --spec datalad --spec copier -- datalad run \
    -m 'add editable local package dependency' -- \
    pixi add --pypi --editable \
    'orinoco-lite @ ./.orinoco-lite/dev/packages/orinoco-lite'

#!/usr/bin/env bash
set -euo pipefail

# Recreate a disposable downstream using local checkouts whenever possible.
# Use --populate to clone only repositories that are missing locally.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$ROOT/../orinoco-lite-test-downstream"
TEMPLATE="$ROOT/../orinoco-lite-template"
PACKAGE="$ROOT"
SITE_SPECIFIC="$ROOT/../con-site-specific"
POPULATE=false
FORCE=false

usage() {
    cat <<'EOF'
Usage: setup-local-downstream-instance.sh [--populate] [--force]

  --populate  clone missing repositories (default: ORINOCO-Lite on GitHub)
  --force     remove and recreate the disposable downstream

The sibling checkouts ../orinoco-lite-template and ../con-site-specific are
used directly. The disposable downstream is ../orinoco-lite-test-downstream.
Setup installs the editable package and prepares its resources, then stops.
It does not run projection or build the website.
EOF
}

while (($#)); do
    case "$1" in
        --populate) POPULATE=true ;;
        --force) FORCE=true ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
    shift
done

if [[ -e "$WORK_DIR" || -L "$WORK_DIR" ]]; then
    if [[ "$FORCE" != true ]]; then
        printf 'Destination already exists: %s\nUse --force to remove and recreate it.\n' \
            "$WORK_DIR" >&2
        exit 1
    fi
fi

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
SITE_SPECIFIC_REMOTE="${SITE_SPECIFIC_REMOTE:-$(repo_remote "$SITE_SPECIFIC")}"
ensure_repo template "$TEMPLATE" \
    "${TEMPLATE_REMOTE:-git@github.com:ORINOCO-Lite/orinoco-lite-template.git}"
ensure_repo site-specific "$SITE_SPECIFIC" \
    "${SITE_SPECIFIC_REMOTE:-git@github.com:ORINOCO-Lite/con-site-specific.git}"

if [[ "$FORCE" == true ]]; then
    rm -rf -- "$WORK_DIR"
fi

printf 'Disposable downstream: %s\n' "$WORK_DIR"

pixi exec --spec datalad --spec git -- \
    datalad create --no-annex \
    -m "chore: initialize DataLad dataset" "$WORK_DIR"
cd "$WORK_DIR"

pixi exec --spec datalad --spec copier -- \
    datalad run -m 'chore: instantiate local template' -- \
    copier copy --vcs-ref HEAD \
    -d include_site_specific=false \
    "$TEMPLATE" .

pixi exec --spec datalad --spec copier -- datalad run \
    -m 'chore: install site-specific subdataset' -- \
    datalad install --dataset . --source "$SITE_SPECIFIC" site-specific

pixi exec --spec datalad --spec copier -- datalad run \
    -m 'chore: link local package checkout' -- bash -c '
    mkdir -p .orinoco-lite
    ln -s "$1" .orinoco-lite/dev
' -- "../../$(basename "$PACKAGE")"

pixi exec --spec datalad --spec copier -- datalad run \
    -m 'chore: install editable local package' -- \
    pixi add --pypi --editable \
    'orinoco-lite @ ./.orinoco-lite/dev/packages/orinoco-lite'

pixi run --manifest-path "$ROOT/pixi.toml" orinoco-lite dev prepare-resources

printf '\nSetup complete: %s\nInspect: git log --oneline; git status\nBuild when ready: pixi run build\nServe afterward: pixi run serve\n' "$PWD"

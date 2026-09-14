#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec pixi run --manifest-path "$ROOT/pixi.toml" orinoco-lite dev setup "$@"

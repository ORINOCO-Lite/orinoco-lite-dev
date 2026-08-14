#!/usr/bin/env python3
"""Prepare the service-backed upstream pool without CON-specific inputs."""

from __future__ import annotations

import shutil
from pathlib import Path

import prepare_local_stack as shared


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "build" / "upstream-stack"
POOL_UI_SOURCE = (
    ROOT / "submodules" / "pool.psychoinformatics.de-ui" / "dist" / "ui"
)


def configure_shared_paths() -> None:
    shared.STACK = STACK
    shared.SNAPSHOT = STACK / "pool" / "public-thing.jsonl"
    shared.MANIFEST = STACK / "pool" / "manifest.json"
    shared.SERVICE_CONFIG = STACK / "dumpthings.yaml"
    shared.EDITOR_TOKEN = STACK / "editor-token"
    shared.SEED_TOKEN = STACK / "seed-token"
    shared.ADMIN_TOKEN = STACK / "admin-token"
    shared.POOL_UI = STACK / "ui"


def write_service_config(editor_token: str, seed_token: str) -> None:
    store = STACK / "store"
    for collection in ("public", "protected"):
        (store / collection / "curated").mkdir(parents=True, exist_ok=True)
        (store / collection / "incoming").mkdir(parents=True, exist_ok=True)
    config = f"""type: collections
version: 2
collections:
  public:
    default_token: local_reader
    curated: public/curated
    incoming: public/incoming
    schema: {shared.yaml_quote(str(shared.SCHEMA))}
    auth_sources:
      - type: config
  protected:
    default_token: local_reader
    curated: protected/curated
    incoming: protected/incoming
    schema: {shared.yaml_quote(str(shared.SCHEMA))}
    auth_sources:
      - type: config
tokens:
  local_reader:
    user_id: local-reader
    collections:
      public:
        mode: READ_CURATED
      protected:
        mode: READ_CURATED
  local_editor:
    user_id: local-editor
    representation: {shared.yaml_quote(editor_token)}
    collections:
      protected:
        mode: WRITE_COLLECTION
        incoming_label: local-editor
  local_seeder:
    user_id: local-seeder
    representation: {shared.yaml_quote(seed_token)}
    collections:
      public:
        mode: CURATOR
      protected:
        mode: CURATOR
"""
    shared.SERVICE_CONFIG.write_text(config, encoding="utf-8")
    shared.SERVICE_CONFIG.chmod(0o600)


def prepare_pool_ui() -> None:
    config_path = POOL_UI_SOURCE / "config.yaml"
    if not config_path.is_file():
        raise RuntimeError(f"Missing built upstream editor: {config_path}")
    if shared.POOL_UI.exists():
        shutil.rmtree(shared.POOL_UI)
    shutil.copytree(POOL_UI_SOURCE, shared.POOL_UI)
    target = shared.POOL_UI / "config.yaml"
    config = target.read_text(encoding="utf-8")
    token_info = (
        "token_info: Please contact Michael Hanke at "
        "m.hanke@fz-juelich.de for credentials."
    )
    if config.count(token_info) != 1:
        raise RuntimeError("Pinned upstream editor token contract changed")
    target.write_text(
        config.replace(
            token_info,
            "token_info: 'Paste build/upstream-stack/editor-token when prompted.'",
        ),
        encoding="utf-8",
    )


def main() -> int:
    configure_shared_paths()
    shared.write_service_config = write_service_config
    shared.prepare_pool_ui = prepare_pool_ui
    shared.remove_legacy_collection_stores = lambda: []
    result = shared.main()
    if result == 0:
        print(f"Upstream editor UI: {shared.POOL_UI}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Configure authoritative upstream remotes for installed development mirrors."""

import argparse
from pathlib import Path
import re
import subprocess

UPSTREAMS = {
    "dump-things-pyclient": "orinoco/dump-things-pyclient",
    "dump-things-service": "orinoco/dump-things-service",
    "query-things": "orinoco/query-things",
    "things-enrichment-tools": "orinoco/things-enrichment-tools",
    "things-schemas": "orinoco/things-schemas",
    "www-from-model": "www/www-from-model",
    "pool.psychoinformatics.de-ui": "www/pool.psychoinformatics.de-ui",
    "shacl-vue": "orinoco/shacl-vue",
}


def configure(root):
    from datalad.api import subdatasets

    for module in subdatasets(dataset=str(root), recursive=True, state="present",
                              result_renderer="disabled"):
        match = re.fullmatch(
            r"(?:https://github.com/|git@github.com:)[^/]+/([^/]+?)(?:\.git)?",
            module.get("gitmodule_url", ""),
        )
        upstream = UPSTREAMS.get(match[1]) if match else None
        if upstream:
            subprocess.run([
                "git", "-C", module["path"], "config", "--replace-all",
                "remote.upstream.url",
                f"https://hub.psychoinformatics.de/{upstream}.git",
            ], check=True)
        remote = "upstream" if upstream else "origin"
        subprocess.run([
            "git", "-C", module["path"], "config", "--replace-all",
            f"remote.{remote}.fetch", f"+refs/heads/*:refs/remotes/{remote}/*",
        ], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    configure(parser.parse_args().root)

#!/usr/bin/env python3
"""Serve a small local git-annex p2p-over-HTTP repository.

The endpoint shape is the one used by the upstream shacl-vue uploader:
``/<annex-uuid>/v4/put`` for uploads and ``/<annex-uuid>/key/<key>`` for
downloads.  Content is stored by git-annex itself, rather than in a separate
demo-data directory.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "build" / "upstream-stack"
ANNEX_REPOSITORY = STACK / "annex-repository"
ANNEX_UUID = os.environ.get(
    "LOCAL_ANNEX_UUID", "00000000-0000-0000-0000-000000000001"
)
HOST = os.environ.get("LOCAL_ANNEX_HOST", "127.0.0.1")
PORT = int(os.environ.get("LOCAL_ANNEX_PORT", "8122"))
EDITOR_TOKEN_PATH = STACK / "editor-token"
KEY_RE = re.compile(r"^SHA256E-s[0-9]+--[0-9a-f]+(?:\.[A-Za-z0-9._-]+)?$")


def run_annex(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ANNEX_REPOSITORY), "annex", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def ensure_repository() -> None:
    ANNEX_REPOSITORY.mkdir(parents=True, exist_ok=True)
    if not (ANNEX_REPOSITORY / ".git" / "annex").exists():
        subprocess.run(["git", "-C", str(ANNEX_REPOSITORY), "init", "-q"], check=True)
        run_annex("init", "upstream development deployment")


def content_location(key: str) -> Path | None:
    try:
        location = run_annex("contentlocation", key)
    except subprocess.CalledProcessError:
        # git-annex returns non-zero when the key is not known locally.
        return None
    if not location:
        return None
    path = ANNEX_REPOSITORY / location
    return path if path.exists() else None


class Handler(BaseHTTPRequestHandler):
    server_version = "OrinocoLocalGitAnnex/1.0"

    def _headers(self, status: HTTPStatus, length: int = 0, content_type: str = "text/plain") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:3000")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-git-annex-data-length")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS, POST")
        self.end_headers()

    def _write(self, status: HTTPStatus, body: bytes = b"") -> None:
        self._headers(status, len(body))
        if self.command != "HEAD":
            self.wfile.write(body)

    def _authorized(self) -> bool:
        expected = EDITOR_TOKEN_PATH.read_text(encoding="utf-8").strip()
        value = self.headers.get("Authorization", "")
        if not value.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(value[6:]).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        supplied, _, _ = decoded.partition(":")
        return supplied == expected

    def _key_from_path(self) -> str | None:
        prefix = f"/git-annex/{ANNEX_UUID}/key/"
        path = unquote(urlsplit(self.path).path)
        if not path.startswith(prefix):
            return None
        key = path[len(prefix) :]
        return key if KEY_RE.fullmatch(key) else None

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._write(HTTPStatus.NO_CONTENT)

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve_key(head_only=True)

    def do_GET(self) -> None:  # noqa: N802
        self._serve_key(head_only=False)

    def _serve_key(self, *, head_only: bool) -> None:
        key = self._key_from_path()
        if key is None:
            self._write(HTTPStatus.NOT_FOUND, b"Unknown git-annex key\n")
            return
        if not self._authorized():
            self._write(HTTPStatus.UNAUTHORIZED, b"A local editor token is required\n")
            return
        path = content_location(key)
        if path is None:
            self._write(HTTPStatus.NOT_FOUND, b"Key is not present\n")
            return
        data_size = path.stat().st_size
        self._headers(HTTPStatus.OK, data_size, "application/octet-stream")
        if not head_only:
            with path.open("rb") as source:
                shutil.copyfileobj(source, self.wfile)

    def do_POST(self) -> None:  # noqa: N802
        prefix = f"/git-annex/{ANNEX_UUID}/v4/put"
        if urlsplit(self.path).path != prefix:
            self._write(HTTPStatus.NOT_FOUND, b"Unknown git-annex endpoint\n")
            return
        if not self._authorized():
            self._write(HTTPStatus.UNAUTHORIZED, b"A local editor token is required\n")
            return
        key_values = parse_qs(urlsplit(self.path).query).get("key", [])
        key = key_values[0] if key_values else ""
        if not KEY_RE.fullmatch(key):
            self._write(HTTPStatus.BAD_REQUEST, b"A SHA256E git-annex key is required\n")
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            self._write(HTTPStatus.BAD_REQUEST, b"Content-Length is required\n")
            return
        existing = content_location(key)
        if existing is not None and existing.stat().st_size == length:
            self._write(HTTPStatus.OK, b"already present\n")
            return
        with tempfile.NamedTemporaryFile(
            dir=ANNEX_REPOSITORY, prefix="upload-", suffix=Path(key).suffix, delete=False
        ) as upload:
            temporary_path = Path(upload.name)
            remaining = length
            while remaining:
                chunk = self.rfile.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                upload.write(chunk)
                remaining -= len(chunk)
        if remaining:
            temporary_path.unlink(missing_ok=True)
            self._write(HTTPStatus.BAD_REQUEST, b"Upload ended before Content-Length\n")
            return
        named_path = ANNEX_REPOSITORY / ("upload-" + Path(key).name)
        temporary_path.replace(named_path)
        try:
            run_annex("add", "--backend=SHA256E", "--force", str(named_path.relative_to(ANNEX_REPOSITORY)))
            actual_key = run_annex("lookupkey", str(named_path.relative_to(ANNEX_REPOSITORY)))
            if actual_key != key:
                self._write(HTTPStatus.BAD_REQUEST, b"Content does not match the requested key\n")
                return
        finally:
            named_path.unlink(missing_ok=True)
        self._write(HTTPStatus.OK, b"stored\n")

    def log_message(self, format: str, *args: object) -> None:
        print(f"local-git-annex: {format % args}", flush=True)


def main() -> int:
    ensure_repository()
    if not EDITOR_TOKEN_PATH.exists():
        raise SystemExit("Run `pixi run serve-upstream` through its launcher.")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Local git-annex p2p service listening at http://{HOST}:{PORT}/git-annex", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

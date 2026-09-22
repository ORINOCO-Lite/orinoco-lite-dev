"""Loopback web review over validated, portable stage evidence.

The trusted application and untrusted evidence use separate origins. The HTTP
API previews decisions in memory; it never applies edits to repository files.
"""
from __future__ import annotations

from contextlib import contextmanager
import codecs
import hashlib
import html
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
from threading import Thread
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit
import webbrowser

from .errors import ConfigurationError
from .stage_reports import canonical

TEXT_LIMIT = 512 * 1024
BODY_LIMIT = 8 * 1024 * 1024
ASSETS = {"index.html": "text/html", "app.js": "text/javascript", "app.css": "text/css"}


def application_root() -> Path:
    """Use installed trusted code, never JavaScript supplied by a review bundle."""
    checkout = Path(__file__).resolve().parents[2]
    source = checkout / "packages/diff-review-application"
    if (checkout / "release/package-resources.yaml").is_file() and (source / "index.html").is_file():
        return source
    source = Path(__file__).parent / "_resources/diff-review-app"
    if not (source / "index.html").is_file():
        raise ConfigurationError("Web review assets are absent; prepare package resources or reinstall the package")
    return source


def _child(root: Path, relative: str = "") -> Path:
    if not isinstance(relative, str):
        raise ConfigurationError("Evidence path must be text")
    path = PurePosixPath(relative)
    if ("\\" in relative or "\x00" in relative
            or path.is_absolute() or any(part in {"..", ".git"} for part in path.parts)):
        raise ConfigurationError("Evidence path must remain inside its declared artifact")
    if root.is_file():
        if relative not in {"", "."}:
            raise ConfigurationError("A file artifact has no child paths")
        target = root
    else:
        target = root / relative
        if root.resolve() != target.resolve() and root.resolve() not in target.resolve().parents:
            raise ConfigurationError("Evidence path leaves its artifact")
    for candidate in (target, *target.parents):
        if candidate.is_symlink():
            raise ConfigurationError("Evidence paths cannot traverse symbolic links")
        if candidate == root:
            break
    if not target.exists() or not (target.is_file() or target.is_dir()):
        raise ConfigurationError("The requested evidence does not exist")
    return target


def _local_url(value: str, prefix: str) -> str | None:
    parsed = urlsplit(value.strip())
    if parsed.scheme or parsed.netloc:
        return value if parsed.scheme == "data" else None
    if value.startswith("/"):
        return prefix + value.lstrip("/")
    return value


def _css(text: str, prefix: str) -> str:
    # Only preview bytes are rebased. The original remains available unchanged.
    return re.sub(r"url\(\s*(['\"]?)/([^/])", lambda m: "url(" + m[1] + prefix + m[2], text)


class _PreviewHTML(HTMLParser):
    def __init__(self, prefix: str):
        super().__init__(convert_charrefs=False)
        self.prefix, self.parts = prefix, []
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "base" or (tag == "meta" and (values.get("http-equiv") or "").lower() == "refresh"):
            return
        rendered = []
        for name, value in attrs:
            # The preview rebases local styles and has an opaque sandbox
            # origin. Source integrity attributes cannot validate those
            # modified preview responses; the original download is untouched.
            if name.startswith("on") or name in {"srcdoc", "formaction", "action", "ping", "srcset", "integrity"}:
                continue
            if value is not None and name in {"href", "src", "poster", "data", "background"}:
                value = _local_url(value, self.prefix)
                if value is None:
                    continue
            if name == "style" and value is not None:
                value = _css(value, self.prefix)
            rendered.append(name if value is None else f'{name}="{html.escape(value, quote=True)}"')
        self.parts.append("<" + tag + (" " + " ".join(rendered) if rendered else "") + ">")
        self.in_style = tag == "style" or self.in_style

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag != "base":
            self.parts.append(f"</{tag}>")
        if tag == "style":
            self.in_style = False

    def handle_data(self, data):
        self.parts.append(_css(data, self.prefix) if self.in_style else data)

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def handle_decl(self, decl):
        self.parts.append(f"<!{decl}>")

    def handle_comment(self, data):
        self.parts.append(f"<!--{data}-->")


def _origin(server) -> str:
    return f"http://127.0.0.1:{server.server_port}"


class _Handler(BaseHTTPRequestHandler):
    server_version = "OrinocoReview"

    def log_message(self, *args):
        pass

    def _host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def _headers(self, status, kind, length, *, download=None):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", self.server.csp)
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin" if self.server.evidence else "same-origin")
        if self.server.evidence:
            # Sandboxed documents have opaque origins; this permits only their
            # read-only fonts and images. No API exists on the evidence origin.
            self.send_header("Access-Control-Allow-Origin", "*")
        if download:
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(download, safe=""))
        self.end_headers()

    def _bytes(self, content: bytes, kind="application/json", status=200, **kwargs):
        self._headers(status, kind, len(content), **kwargs)
        if self.command != "HEAD":
            self.wfile.write(content)

    def _json(self, data, status=200):
        self._bytes(canonical(data).encode(), "application/json; charset=utf-8", status)

    def _file(self, path: Path, kind: str, *, download=False):
        self._headers(200, kind, path.stat().st_size, download=path.name if download else None)
        if self.command != "HEAD":
            with path.open("rb") as stream:
                shutil.copyfileobj(stream, self.wfile)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self._host():
            self._json({"error": "Use the printed loopback URL"}, 403)
            return
        try:
            if self.server.evidence:
                self._evidence()
            else:
                self._application()
        except (ConfigurationError, ValueError, KeyError, TypeError) as error:
            self._json({"error": str(error)}, 400)
        except FileNotFoundError:
            self._json({"error": "Evidence not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _params(self):
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if any(len(values) != 1 for values in query.values()):
            raise ConfigurationError("Query parameters must be unique")
        return unquote(parsed.path), {key: value[0] for key, value in query.items()}

    def _artifact(self, params):
        root = self.server.model.artifact_root(params["run_id"], int(params["stage_index"]), params["role"])
        return root, _child(root, params.get("path", ""))

    def _application(self):
        path, params = self._params()
        if path in {"/", "/index.html", "/app.js", "/app.css"}:
            name = "index.html" if path == "/" else path[1:]
            self._file(self.server.application / name, ASSETS[name] + "; charset=utf-8")
        elif path == "/api/review":
            self._json({**self.server.model.overview(), "csrf_token": self.server.token})
        elif path == "/api/findings":
            self._json(self.server.model.findings(
                state=params.get("state", "new"), stage=params.get("stage", ""), q=params.get("q", ""),
                offset=int(params.get("offset", "0")), limit=int(params.get("limit", "50")),
                run_id=params.get("run_id", ""),
                stage_index=int(params["stage_index"]) if "stage_index" in params else None))
        elif path == "/api/finding":
            self._json(self.server.model.finding(params["key"]))
        elif path in {"/api/artifact", "/download", "/image"}:
            root, target = self._artifact(params)
            query = urlencode(params)
            if path == "/download":
                if not target.is_file():
                    raise ConfigurationError("Choose a file to download")
                self._file(target, "application/octet-stream", download=True)
                return
            kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            raster = kind in {"image/png", "image/jpeg", "image/gif", "image/webp", "image/avif"}
            if path == "/image":
                if not raster or not target.is_file():
                    raise ConfigurationError("Only raster images can be displayed on the review origin")
                self._file(target, kind)
                return
            if target.is_dir():
                entries = []
                for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold())):
                    if child.name == ".git":
                        continue
                    checked = _child(root, child.relative_to(root).as_posix())
                    entries.append({"name": child.name, "path": child.relative_to(root).as_posix(),
                                    "kind": "directory" if checked.is_dir() else "file",
                                    "size": checked.stat().st_size if checked.is_file() else None})
                self._json({"kind": "directory", "entries": entries, "path": params.get("path", "")})
                return
            result = {"media_type": kind, "download_url": "/download?" + query, "size": target.stat().st_size,
                      "path": params.get("path", ""), "name": target.name}
            if raster:
                result.update(kind="image", url="/image?" + query)
            else:
                with target.open("rb") as stream:
                    raw = stream.read(TEXT_LIMIT + 1)
                try:
                    decoder = codecs.getincrementaldecoder("utf-8")()
                    content = decoder.decode(raw[:TEXT_LIMIT], final=len(raw) <= TEXT_LIMIT)
                except UnicodeDecodeError:
                    content = None
                if content is None or "\x00" in content:
                    result.update(kind="binary")
                else:
                    result.update(kind="text", text=content, truncated=len(raw) > TEXT_LIMIT)
                    if target.suffix.lower() in {".html", ".htm"}:
                        mount = hashlib.sha256((params["run_id"] + "/" + params["stage_index"] + "/" + params["role"]).encode()).hexdigest()[:24]
                        self.server.preview.mounts[mount] = (params["run_id"], int(params["stage_index"]), params["role"])
                        relative = target.relative_to(root).as_posix() if root.is_dir() else ""
                        result["preview_url"] = _origin(self.server.preview) + "/" + mount + "/" + quote(relative)
            self._json(result)
        else:
            self._json({"error": "Unknown review route"}, 404)

    def _evidence(self):
        path = unquote(urlsplit(self.path).path)
        parts = path.lstrip("/").split("/", 1)
        if len(parts) != 2 or parts[0] not in self.server.mounts:
            raise ConfigurationError("Unknown evidence mount")
        root = self.server.model.artifact_root(*self.server.mounts[parts[0]])
        target = _child(root, parts[1])
        if target.is_dir():
            target = _child(root, (PurePosixPath(parts[1]) / "index.html").as_posix())
        prefix = "/" + parts[0] + "/"
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix.lower() in {".html", ".htm"}:
            parser = _PreviewHTML(prefix)
            parser.feed(target.read_text(encoding="utf-8"))
            self._bytes("".join(parser.parts).encode(), "text/html; charset=utf-8")
        elif target.suffix.lower() == ".css":
            self._bytes(_css(target.read_text(encoding="utf-8"), prefix).encode(), "text/css; charset=utf-8")
        elif kind.startswith("image/") or kind.startswith("font/") or target.suffix.lower() in {".woff", ".woff2", ".ttf"}:
            self._file(target, kind)
        else:
            self._file(target, "text/plain; charset=utf-8")

    def do_POST(self):
        if (self.server.evidence or not self._host()
                or self.headers.get("Origin") != _origin(self.server)
                or self.headers.get("X-Review-Token") != self.server.token):
            self._json({"error": "Review requests require the local application's origin and token"}, 403)
            return
        try:
            if self.headers.get_content_type() != "application/json":
                raise ConfigurationError("Review requests require application/json")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= BODY_LIMIT:
                raise ConfigurationError("Review request is empty or exceeds 8 MiB")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ConfigurationError("Review request must be a JSON object")
            path = urlsplit(self.path).path
            if path == "/api/decision":
                decision = self.server.model.decision(payload)
                self._json({"decision": decision, "decision_json": canonical(decision)})
            elif path == "/api/preview":
                preview = self.server.model.preview(payload)
                self._json({**preview, "changes_json": canonical(preview["changes"])})
            else:
                self._json({"error": "Unknown review route"}, 404)
        except (ConfigurationError, ValueError, KeyError, TypeError) as error:
            self._json({"error": str(error)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass


@contextmanager
def review_servers(model, *, port=8765, application=None):
    """Start isolated origins; useful to CLI and real browser integration tests."""
    assets = application or application_root()
    if type(port) is not int or not 0 <= port <= 65535:
        raise ConfigurationError("Review port must be between 0 and 65535")
    preview = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    except OSError as error:
        preview.server_close()
        raise ConfigurationError(f"Cannot start the local review server: {error}") from error
    server.evidence, preview.evidence = False, True
    server.application, server.model, server.preview = assets, model, preview
    preview.model = model
    server.token = secrets.token_urlsafe(32)
    preview.mounts = {}
    server.csp = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                  "connect-src 'self'; frame-src " + _origin(preview) + "; object-src 'none'; "
                  "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
    preview.csp = ("sandbox; default-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                   "font-src 'self'; script-src 'none'; connect-src 'none'; frame-src 'none'; "
                   "form-action 'none'; object-src 'none'; base-uri 'none'; frame-ancestors " + _origin(server))
    threads = [Thread(target=item.serve_forever, daemon=True) for item in (server, preview)]
    for thread in threads:
        thread.start()
    try:
        yield server
    finally:
        for item in (server, preview):
            item.shutdown()
            item.server_close()
        for thread in threads:
            thread.join()


def serve(directory: Path, *, port=8765, open_browser=False):
    from .stage_bundle import ReviewModel
    from threading import Event
    model = ReviewModel(directory)
    with review_servers(model, port=port) as server:
        url = _origin(server) + "/"
        print(f"Review: {url}", flush=True)
        print("Decision drafts are exported for CLI application; repository files are unchanged.", flush=True)
        if open_browser:
            webbrowser.open(url)
        try:
            Event().wait()
        except KeyboardInterrupt:
            print("\nReview server stopped.")

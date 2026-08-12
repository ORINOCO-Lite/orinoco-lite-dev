from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from orinoco_lite.assets import Asset, hydrate_asset_cache, verify_asset
from orinoco_lite.errors import IntegrityError


class Handler(BaseHTTPRequestHandler):
    payload = b"asset payload\n"

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format, *args):
        pass


class AssetCacheTests(unittest.TestCase):
    def test_hydration_is_digest_verified_and_cache_reusable(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                destination = Path(temporary) / "cache" / "object"
                payload = Handler.payload
                asset = Asset(
                    source="assets/files/example.txt",
                    sha256=hashlib.sha256(payload).hexdigest(),
                    size=len(payload),
                    availability="available",
                    object_url=f"http://127.0.0.1:{server.server_port}/object".replace(
                        "http://", "https://"
                    ),
                )
                # The production contract is HTTPS; use a temporary direct
                # override here to exercise download integrity without TLS.
                asset = Asset(asset.source, asset.sha256, asset.size, asset.availability,
                              f"http://127.0.0.1:{server.server_port}/object")
                hydrate_asset_cache(destination, asset)
                verify_asset(destination, asset)
                server.shutdown()
                verify_asset(destination, asset)
                destination.write_bytes(b"tampered")
                with self.assertRaisesRegex(IntegrityError, "integrity"):
                    verify_asset(destination, asset)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

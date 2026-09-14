from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

from tools import upstream_pool_diff as pool_diff


def record(pid: str, label: str, **values: object) -> dict[str, object]:
    return {
        "pid": pid,
        "schema_type": "dlthings:Thing",
        "display_label": label,
        **values,
    }


class UpstreamPoolDiffTests(unittest.TestCase):
    def test_compare_reports_pid_and_field_level_changes(self) -> None:
        cached = {
            "same": record("same", "Same", value=1),
            "gone": record("gone", "Gone"),
            "edit": record("edit", "Old", nested={"left": 1, "gone": True}),
        }
        live = {
            "same": record("same", "Same", value=1),
            "new": record("new", "New"),
            "edit": record("edit", "New", nested={"left": 2, "new": True}),
        }

        result = pool_diff.compare_records(cached, live)

        self.assertEqual(
            result["summary"],
            {"added": 1, "removed": 1, "changed": 1, "unchanged": 1, "different": True},
        )
        self.assertEqual([item["pid"] for item in result["added"]], ["new"])
        self.assertEqual([item["pid"] for item in result["removed"]], ["gone"])
        changed = result["changed"][0]
        self.assertEqual(changed["pid"], "edit")
        self.assertEqual(
            [item["path"] for item in changed["changes"]],
            ["/display_label", "/nested/gone", "/nested/left", "/nested/new"],
        )
        self.assertFalse(changed["changes"][1]["live_present"])
        self.assertFalse(changed["changes"][3]["cache_present"])

    def test_cache_and_manifest_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache.jsonl"
            payload = (
                json.dumps({"class_name": "Thing", "record": record("one", "One")}, sort_keys=True)
                + "\n"
            ).encode()
            cache.write_bytes(payload)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "record_count": 1,
                        "snapshot": str(cache.resolve()),
                        "snapshot_sha256": hashlib.sha256(payload).hexdigest(),
                    }
                ),
                encoding="utf-8",
            )

            records, digest = pool_diff.load_cache(cache)
            loaded = pool_diff.load_manifest(manifest, cache, len(records), digest)
            self.assertEqual(list(records), ["one"])
            self.assertEqual(loaded["record_count"], 1)

            manifest.write_text(
                json.dumps(
                    {
                        "record_count": 1,
                        "snapshot": str(cache.resolve()),
                        "snapshot_sha256": "0" * 64,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(pool_diff.PoolDiffError, "digest"):
                pool_diff.load_manifest(manifest, cache, len(records), digest)

    def test_live_fetch_restarts_at_a_smaller_page_size(self) -> None:
        all_records = [record(f"pid-{index}", f"Record {index}") for index in range(5)]
        requested_sizes: list[int] = []

        def fetch(url: str) -> object:
            if url.endswith("/server"):
                return {"version": "test"}
            query = parse_qs(urlparse(url).query)
            page = int(query["page"][0])
            size = int(query["size"][0])
            requested_sizes.append(size)
            if size > 2:
                raise pool_diff.PoolDiffError("HTTP Error 413")
            start = (page - 1) * size
            items = all_records[start : start + size]
            return {
                "items": items,
                "total": len(all_records),
                "pages": math.ceil(len(all_records) / size),
                "page": page,
                "size": size,
            }

        records, server = pool_diff.fetch_live(
            "https://example.test/api", fetch=fetch, workers=1
        )

        self.assertEqual(set(records), {f"pid-{index}" for index in range(5)})
        self.assertEqual(server, {"version": "test"})
        self.assertGreater(requested_sizes[0], 2)
        self.assertLessEqual(requested_sizes[-1], 2)

    def test_report_is_atomic_and_console_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = Path(temporary) / "report.json"
            report = {
                "cache": {"record_count": 1, "semantic_sha256": "a" * 64},
                "live": {"record_count": 2, "semantic_sha256": "b" * 64},
                "summary": {"added": 1, "removed": 0, "changed": 1, "unchanged": 0, "different": True},
                "added": [{"pid": "new", "display_label": "New"}],
                "removed": [],
                "changed": [
                    {
                        "pid": "edit",
                        "live_display_label": "Edit",
                        "cache_display_label": "Edit",
                        "changes": [{"path": "/value", "cache": 1, "live": 2}],
                    }
                ],
                "report_path": str(report_path),
            }
            pool_diff.write_report(report_path, report)
            self.assertEqual(json.loads(report_path.read_text()), report)
            output = io.StringIO()
            with mock.patch("sys.stdout", output):
                pool_diff.print_report(report, 1)
            self.assertIn("Diff: +1 -0 ~1 =0", output.getvalue())
            self.assertIn("... 1 more changed records", output.getvalue())

    def test_changed_values_are_readable_and_bounded(self) -> None:
        self.assertEqual(
            pool_diff.display_change(
                {"path": "/label", "cache": "Old", "live": "New"}
            ),
            '/label: "Old" -> "New"',
        )
        self.assertEqual(
            pool_diff.display_change(
                {"path": "/added", "cache_present": False, "live": 1}
            ),
            "/added: <missing> -> 1",
        )
        self.assertLessEqual(len(pool_diff.display_value("x" * 200)), 120)


if __name__ == "__main__":
    unittest.main()

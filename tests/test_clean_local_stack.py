from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name: str):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREPARE = load_tool("prepare_local_stack")
SEED = load_tool("seed_local_pool")
CHECK = load_tool("check_local_stack")


def write_manifest(path: Path, *items: str | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for item in items:
        record = (
            {
                "pid": item,
                "schema_type": "xyzri:XYZProject",
            }
            if isinstance(item, str)
            else item
        )
        class_name = record["schema_type"].rsplit(":", 1)[-1]
        lines.append(
            json.dumps(
                {"class_name": class_name, "record": record},
                sort_keys=True,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class CleanLocalStackTests(unittest.TestCase):
    def test_snapshot_restarts_with_one_page_size_and_checks_total(self) -> None:
        def page(*pids: str, total: int, pages: int) -> dict:
            return {
                "total": total,
                "pages": pages,
                "items": [
                    {
                        "pid": pid,
                        "schema_type": "xyzri:XYZProject",
                    }
                    for pid in pids
                ],
            }

        with tempfile.TemporaryDirectory() as temporary:
            snapshot = Path(temporary) / "snapshot.jsonl"
            responses = [
                (page("example:1", "example:2", total=4, pages=2), 100),
                (page("example:3", total=4, pages=2), 50),
                (page("example:1", "example:2", total=4, pages=2), 50),
                (page("example:3", "example:4", total=4, pages=2), 50),
            ]
            with (
                mock.patch.object(PREPARE, "SNAPSHOT", snapshot),
                mock.patch.object(
                    PREPARE,
                    "request_json",
                    return_value={"pid": "server"},
                ),
                mock.patch.object(
                    PREPARE,
                    "fetch_page",
                    side_effect=responses,
                ) as fetch_page,
            ):
                records, server = PREPARE.write_snapshot()
            self.assertEqual(records, 4)
            self.assertEqual(server, {"pid": "server"})
            self.assertEqual(
                [call.args for call in fetch_page.call_args_list],
                [(1, 100), (2, 100), (1, 50), (2, 50)],
            )
            self.assertEqual(len(snapshot.read_text().splitlines()), 4)

            with (
                mock.patch.object(PREPARE, "SNAPSHOT", snapshot),
                mock.patch.object(
                    PREPARE,
                    "request_json",
                    return_value={},
                ),
                mock.patch.object(
                    PREPARE,
                    "fetch_page",
                    return_value=(
                        page("example:1", total=2, pages=1),
                        100,
                    ),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "incomplete"):
                    PREPARE.write_snapshot()
            self.assertEqual(len(snapshot.read_text().splitlines()), 4)
            count, digest = PREPARE.snapshot_fingerprint(snapshot)
            self.assertEqual(count, 4)
            self.assertEqual(len(digest), 64)

    def test_prepare_isolates_collections_tokens_and_runtime_ui(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stack = root / "build" / "local-stack"
            source_ui = root / "source-ui"
            source_ui.mkdir()
            source_config = """service_base_url:
  - url: http://127.0.0.1:8111/protected/
    type: write
  - url: http://127.0.0.1:8111/public/
    type: read
token_info: Please contact Michael Hanke at m.hanke@fz-juelich.de for credentials.
use_service: true
"""
            (source_ui / "config.yaml").write_text(
                source_config,
                encoding="utf-8",
            )
            (source_ui / "config_default_xyzri.yaml").write_text(
                "data_url: ''\n",
                encoding="utf-8",
            )
            schema = root / "schema.yaml"
            schema.write_text("id: example:test\n", encoding="utf-8")
            patches = (
                mock.patch.object(PREPARE, "STACK", stack),
                mock.patch.object(
                    PREPARE,
                    "SERVICE_CONFIG",
                    stack / "dumpthings.yaml",
                ),
                mock.patch.object(PREPARE, "POOL_UI_SOURCE", source_ui),
                mock.patch.object(PREPARE, "POOL_UI", stack / "ui"),
                mock.patch.object(PREPARE, "SCHEMA", schema),
            )
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                stack.mkdir(parents=True)
                PREPARE.write_service_config("editor-secret", "seed-secret")
                for collection in PREPARE.LEGACY_COLLECTIONS:
                    legacy = stack / "store" / collection
                    legacy.mkdir()
                    (legacy / "record.json").write_text(
                        '{"pid": "example:legacy"}\n',
                        encoding="utf-8",
                    )
                removed = PREPARE.remove_legacy_collection_stores()
                persisted = stack / "store" / "__dump_things__"
                persisted.mkdir()
                (persisted / "stale-config").write_text(
                    "old two-collection config\n",
                    encoding="utf-8",
                )
                PREPARE.reset_persisted_service_config()
                PREPARE.prepare_pool_ui()

            service = (stack / "dumpthings.yaml").read_text(encoding="utf-8")
            for collection in PREPARE.COLLECTIONS:
                self.assertIn(f"  {collection}:\n", service)
                self.assertTrue((stack / "store" / collection / "curated").is_dir())
                self.assertTrue((stack / "store" / collection / "incoming").is_dir())
            self.assertEqual(service.count("default_token: local_reader"), 3)
            self.assertEqual(service.count("default_token: local_con_reader"), 1)
            self.assertNotIn("local_denied", service)
            self.assertEqual(
                {path.name for path in removed},
                set(PREPARE.LEGACY_COLLECTIONS),
            )
            for collection in PREPARE.LEGACY_COLLECTIONS:
                self.assertFalse((stack / "store" / collection).exists())
            self.assertFalse((stack / "store" / "__dump_things__").exists())
            reader = service.split("  local_reader:", 1)[1].split(
                "  local_con_reader:", 1
            )[0]
            self.assertIn("upstream-public:", reader)
            self.assertIn("upstream-protected:", reader)
            self.assertIn("con-public:", reader)
            self.assertNotIn("con-protected:", reader)
            self.assertNotIn("WRITE", reader)
            con_reader = service.split("  local_con_reader:", 1)[1].split(
                "  local_editor:", 1
            )[0]
            self.assertIn("user_id: local-con-reader", con_reader)
            self.assertIn("con-protected:", con_reader)
            self.assertIn("mode: READ_CURATED", con_reader)
            self.assertNotIn("upstream-", con_reader)
            self.assertNotIn("WRITE", con_reader)
            self.assertEqual(con_reader.count("mode:"), 1)
            editor = service.split("  local_editor:", 1)[1].split("  local_seeder:", 1)[
                0
            ]
            self.assertIn("con-protected:", editor)
            self.assertIn("mode: WRITE_COLLECTION", editor)
            self.assertIn("incoming_label: local-editor", editor)
            self.assertNotIn("upstream-", editor)
            self.assertNotIn("con-public:", editor)
            self.assertNotIn("READ_", editor)
            self.assertEqual(editor.count("mode:"), 1)
            seeder = service.split("  local_seeder:", 1)[1]
            for collection in PREPARE.COLLECTIONS:
                self.assertIn(f"      {collection}:\n", seeder)
            runtime = (stack / "ui" / "config.yaml").read_text(encoding="utf-8")
            con_url = "http://127.0.0.1:8111/con-protected/"
            self.assertEqual(runtime.count(con_url), 2)
            self.assertNotIn("127.0.0.1:8111/public/", runtime)
            self.assertNotIn("127.0.0.1:8111/protected/", runtime)
            self.assertIn("build/local-stack/editor-token", runtime)
            self.assertNotIn("Please contact Michael Hanke", runtime)
            self.assertEqual(
                (source_ui / "config.yaml").read_text(encoding="utf-8"),
                source_config,
            )

    def test_seed_manifests_target_only_their_collection_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = root / "upstream.jsonl"
            con = root / "con.jsonl"
            write_manifest(upstream, "example:upstream-1", "example:upstream-2")
            write_manifest(con, "example:con-1")
            with (
                mock.patch.object(
                    SEED,
                    "put_record",
                    return_value="created",
                ) as put_record,
                mock.patch.object(
                    SEED,
                    "prune_collection",
                    return_value=0,
                ) as prune,
            ):
                SEED.seed_manifest(
                    upstream,
                    SEED.UPSTREAM_COLLECTIONS,
                    "seed-token",
                    "upstream",
                )
                SEED.seed_manifest(
                    con,
                    SEED.CON_COLLECTIONS,
                    "seed-token",
                    "CON",
                )
            targets: dict[str, set[str]] = {}
            for call in put_record.call_args_list:
                collection, _, record, _ = call.args
                targets.setdefault(record["pid"], set()).add(collection)
            self.assertEqual(
                targets["example:upstream-1"],
                set(SEED.UPSTREAM_COLLECTIONS),
            )
            self.assertEqual(
                targets["example:upstream-2"],
                set(SEED.UPSTREAM_COLLECTIONS),
            )
            self.assertEqual(
                targets["example:con-1"],
                set(SEED.CON_COLLECTIONS),
            )
            self.assertEqual(
                [call.args[0] for call in prune.call_args_list],
                [
                    "upstream-public",
                    "upstream-protected",
                    "con-public",
                    "con-protected",
                ],
            )

    def test_manifest_rejects_duplicate_pids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "records.jsonl"
            write_manifest(manifest, "example:same", "example:same")
            with self.assertRaisesRegex(RuntimeError, "duplicate record pid"):
                SEED.load_manifest(manifest)

    def test_seed_idempotence_accepts_service_class_normalization(self) -> None:
        record = {
            "pid": "example:project",
            "schema_type": "xyzri:XYZProject",
        }
        with mock.patch.object(
            SEED,
            "call",
            return_value=(200, {"pid": "example:project"}),
        ) as call:
            result = SEED.put_record(
                "con-public",
                "XYZProject",
                record,
                "seed-token",
            )
        self.assertEqual(result, "unchanged")
        self.assertEqual(call.call_count, 1)

    def test_check_compares_all_four_curated_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = root / "upstream.jsonl"
            con = root / "con.jsonl"
            write_manifest(
                upstream,
                {
                    "pid": "example:shared",
                    "schema_type": "xyzri:XYZProject",
                    "title": "Upstream",
                },
            )
            write_manifest(
                con,
                {
                    "pid": "example:shared",
                    "schema_type": "xyzri:XYZProject",
                    "title": "CON",
                },
            )
            upstream_records = CHECK.manifest_records(upstream)
            con_records = CHECK.manifest_records(con)

            def records(collection: str, _token: str) -> dict[str, dict]:
                if collection.startswith("upstream-"):
                    return upstream_records
                return con_records

            with (
                mock.patch.object(CHECK, "UPSTREAM_SNAPSHOT", upstream),
                mock.patch.object(CHECK, "CON_RECORDS", con),
                mock.patch.object(CHECK, "curated_records", side_effect=records),
            ):
                counts = CHECK.check_seed_separation("seed-token")
            self.assertEqual(counts["upstream-public"], 1)
            self.assertEqual(counts["con-protected"], 1)

            def contaminated(
                collection: str,
                token: str,
            ) -> dict[str, dict]:
                if collection == "con-public":
                    return upstream_records
                return records(collection, token)

            with (
                mock.patch.object(CHECK, "UPSTREAM_SNAPSHOT", upstream),
                mock.patch.object(CHECK, "CON_RECORDS", con),
                mock.patch.object(
                    CHECK,
                    "curated_records",
                    side_effect=contaminated,
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "con-public.*changed",
                ):
                    CHECK.check_seed_separation("seed-token")

    def test_write_probe_is_confined_to_con_protected_incoming(self) -> None:
        calls: list[tuple[str, str, str]] = []
        written: dict | None = None

        def request(
            method: str,
            url: str,
            token: str | None,
            body=None,
            *,
            missing_ok: bool = False,
        ):
            nonlocal written
            del missing_ok
            calls.append((method, url, token or ""))
            if method == "DELETE":
                return None
            if method == "POST":
                written = body
                return body
            if written is not None and "/con-protected/incoming/local-editor/" in url:
                return written
            return None

        with (
            mock.patch.object(CHECK, "request_json", side_effect=request),
            mock.patch.object(CHECK, "expect_rejected") as rejected,
            mock.patch.object(
                CHECK,
                "manifest_envelopes",
                return_value={"xyzrins:.": {}},
            ),
            mock.patch.object(
                CHECK,
                "incoming_probe_pids",
                return_value={f"{CHECK.PROBE_PID_PREFIX}stale"},
            ),
            mock.patch.object(
                CHECK.uuid,
                "uuid4",
                return_value=mock.Mock(hex="unit-probe"),
            ),
        ):
            CHECK.prove_write_isolation("editor-token", "seed-token")
        post = next(call for call in calls if call[0] == "POST")
        self.assertEqual(post[0], "POST")
        self.assertIn("/con-protected/record/XYZProject", post[1])
        self.assertEqual(post[2], "editor-token")
        self.assertEqual(rejected.call_count, 7)
        probe = {
            "pid": ("xyzrins:projects/_clean-migration-write-probe-unit-probe"),
            "schema_type": "xyzri:XYZProject",
        }
        for collection in (
            "upstream-public",
            "upstream-protected",
            "con-public",
            "con-protected",
        ):
            url = f"http://127.0.0.1:8111/{collection}/record/XYZProject"
            rejected.assert_any_call("POST", url, None, probe)
        for collection in (
            "upstream-public",
            "upstream-protected",
            "con-public",
        ):
            rejected.assert_any_call(
                "POST",
                f"http://127.0.0.1:8111/{collection}/record/XYZProject",
                "editor-token",
                probe,
            )
        self.assertGreaterEqual(
            sum(call[0] == "DELETE" for call in calls),
            24,
        )
        self.assertTrue(
            any(call[0] == "DELETE" and "stale" in call[1] for call in calls)
        )

    def test_write_probe_namespace_cannot_collide_with_canonical_data(self) -> None:
        collision = f"{CHECK.PROBE_PID_PREFIX}canonical"
        with mock.patch.object(
            CHECK,
            "manifest_envelopes",
            return_value={collision: {}},
        ):
            with self.assertRaisesRegex(RuntimeError, "reserved acceptance PID"):
                CHECK.prove_write_isolation("editor-token", "seed-token")

    def test_stale_write_probes_are_discovered_without_human_edits(self) -> None:
        stale = f"{CHECK.PROBE_PID_PREFIX}interrupted"
        pages = (
            {
                "items": [
                    {"pid": "xyzrins:projects/human-pending-edit"},
                    {"pid": CHECK.LEGACY_PROBE_PID},
                ],
                "pages": 2,
            },
            {"items": [{"pid": stale}], "pages": 2},
        )
        with mock.patch.object(CHECK, "request_json", side_effect=pages) as request:
            self.assertEqual(
                CHECK.incoming_probe_pids("con-protected", "seed-token"),
                {CHECK.LEGACY_PROBE_PID, stale},
            )
        self.assertEqual(request.call_count, 2)

    def test_ui_links_and_supervisor_default_to_con(self) -> None:
        config = """use_service: true
use_token: true
service_base_url:
  - url: http://127.0.0.1:8111/con-protected/
    type: write
  - url: http://127.0.0.1:8111/con-protected/
    type: read
gitannex_p2phttp_url: http://127.0.0.1:8122/git-annex
"""
        external = "xyzrins:\ndlschemas_owl.ttl\ndata_url: ''\n"
        expected_pids = frozenset(
            {
                "xyzrins:.",
                CHECK.CON_PERSON_PID,
                "xyzrins:projects/datalad",
                "xyzrins:persons/new-member",
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            for index, pid in enumerate(sorted(expected_pids)):
                page = site / str(index)
                page.mkdir()
                query_pid = pid.replace(":", "%3A").replace("/", "%2F")
                (page / "index.html").write_text(
                    '<a href="http://127.0.0.1:3000/'
                    "?sh%3ANodeShape=dlthings%3AThing&amp;pid="
                    f'{query_pid}&amp;edit=true">edit</a>',
                    encoding="utf-8",
                )
            with (
                mock.patch.object(
                    CHECK,
                    "read_text",
                    side_effect=(config, external),
                ),
                mock.patch.object(CHECK, "CON_SITE", site),
            ):
                CHECK.check_editor_ui()
                self.assertEqual(
                    CHECK.check_static_edit_links(expected_pids),
                    len(expected_pids),
                )

    def test_edit_links_reject_credentials_and_unknown_records(self) -> None:
        def write_link(site: Path, query: str) -> None:
            (site / "index.html").write_text(
                f'<a href="http://127.0.0.1:3000/?{query}">edit</a>',
                encoding="utf-8",
            )

        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            credential_query = (
                "sh%3ANodeShape=dlthings%3AThing&amp;"
                "pid=xyzrins%3Apersons%2Fyaroslav-halchenko&amp;"
                "edit=true&amp;token=secret"
            )
            write_link(site, credential_query)
            with mock.patch.object(CHECK, "CON_SITE", site):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "credential-free",
                ):
                    CHECK.check_static_edit_links(frozenset({CHECK.CON_PERSON_PID}))

            unknown_query = (
                "sh%3ANodeShape=dlthings%3AThing&amp;"
                "pid=xyzrins%3Apersons%2Funknown&amp;edit=true"
            )
            write_link(site, unknown_query)
            with mock.patch.object(CHECK, "CON_SITE", site):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "rendered record set",
                ):
                    CHECK.check_static_edit_links(frozenset({CHECK.CON_PERSON_PID}))

    def test_edit_pid_closure_comes_from_records_and_render_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            records = root / "records.jsonl"
            projection = root / "projection.yaml"
            write_manifest(
                records,
                {
                    "pid": "xyzrins:.",
                    "schema_type": "xyzri:XYZProject",
                },
                {
                    "pid": "xyzrins:projects/datalad",
                    "schema_type": "xyzri:XYZProject",
                },
                {
                    "pid": CHECK.CON_PERSON_PID,
                    "schema_type": "xyzri:XYZPerson",
                },
                {
                    "pid": "xyzrins:persons/new-member",
                    "schema_type": "xyzri:XYZPerson",
                },
                {
                    "pid": "marcrel:aut",
                    "schema_type": "xyzri:XYZAgentRole",
                },
            )
            projection.write_text(
                """render:
  pages:
    xyzri:XYZProject: project.md.j2
    xyzri:XYZPerson: person.md.j2
  homepage:
    pid: xyzrins:.
""",
                encoding="utf-8",
            )
            self.assertEqual(
                CHECK.expected_edit_pids(records, projection),
                {
                    "xyzrins:.",
                    "xyzrins:projects/datalad",
                    CHECK.CON_PERSON_PID,
                    "xyzrins:persons/new-member",
                },
            )

            without_datalad = root / "without-datalad.jsonl"
            write_manifest(
                without_datalad,
                {
                    "pid": "xyzrins:.",
                    "schema_type": "xyzri:XYZProject",
                },
                {
                    "pid": CHECK.CON_PERSON_PID,
                    "schema_type": "xyzri:XYZPerson",
                },
            )
            with self.assertRaisesRegex(RuntimeError, "Representative"):
                CHECK.expected_edit_pids(without_datalad, projection)

    def test_anonymous_read_targets_curated_yaroslav_record(self) -> None:
        record = {"pid": CHECK.CON_PERSON_PID}
        with mock.patch.object(
            CHECK,
            "request_json",
            return_value=record,
        ) as request:
            CHECK.check_anonymous_con_read()
        request.assert_called_once_with(
            "GET",
            (
                "http://127.0.0.1:8111/con-protected/record?"
                "pid=xyzrins%3Apersons%2Fyaroslav-halchenko&format=json"
            ),
            None,
        )

        with mock.patch.object(CHECK, "request_json", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Anonymous"):
                CHECK.check_anonymous_con_read()

        supervisor = (ROOT / "tools" / "serve_local_stack.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('--directory "$stack_dir/ui"', supervisor)
        self.assertIn('--directory "$root_dir/build/con-site"', supervisor)
        self.assertNotIn("build/upstream-local", supervisor)
        self.assertIn("trap cleanup EXIT", supervisor)
        self.assertIn("trap 'exit 130' INT TERM", supervisor)

    def test_check_rejects_legacy_collection_stores(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stack = Path(temporary)
            with mock.patch.object(CHECK, "STACK", stack):
                CHECK.check_no_legacy_collection_stores()
                legacy = stack / "store" / "public"
                legacy.mkdir(parents=True)
                with self.assertRaisesRegex(RuntimeError, "Obsolete"):
                    CHECK.check_no_legacy_collection_stores()


if __name__ == "__main__":
    unittest.main()

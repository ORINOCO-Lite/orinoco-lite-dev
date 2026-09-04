from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml

from orinoco_lite.config import DEFAULT_PATHS, WorkspaceConfig
from orinoco_lite.errors import DriverError
from orinoco_lite.integrity import tree_sha256
from orinoco_lite.projection import (
    _is_historical_provenance,
    projection_manifest,
    render_projection,
    update_projection,
    verify_projection,
)
from orinoco_lite.release_schema import localize_schema


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SOURCE = ROOT / "submodules/things-schemas/src"
CONSUMER_ENVIRONMENT = "ORINOCO_TEST_ACCEPTED_CONSUMER"
CONSUMER_COMMIT = "96a87e38f149badf76d98ee9dc5fe2e4fd3b9c07"
TRACKED_INPUTS = (
    "metadata",
    "site/projection.yaml",
    "site/projection-templates",
    "site/projection-tools",
)


def _fixture_records(root: Path) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for path in sorted((root / "metadata/records").rglob("*.yaml")):
        relative = path.relative_to(root / "metadata/records")
        if any(part.startswith(".") for part in relative.parts):
            continue
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise AssertionError(f"fixture record is not a mapping: {relative}")
        pid = record.get("pid")
        if not isinstance(pid, str) or not pid:
            raise AssertionError(f"fixture record has no PID: {relative}")
        if pid in records:
            raise AssertionError(f"fixture contains duplicate PID: {pid}")
        records[pid] = record
    return records


def _relationship_targets(record: Mapping[str, object], field: str) -> set[str]:
    raw_values = record.get(field, [])
    values = raw_values if isinstance(raw_values, list) else [raw_values]
    targets: set[str] = set()
    for value in values:
        target = value.get("object") if isinstance(value, dict) else value
        candidates = target if isinstance(target, list) else [target]
        targets.update(item for item in candidates if isinstance(item, str))
    return targets


def _selected_by_fixture_policy(
    record: Mapping[str, object],
    policy: Mapping[str, object],
    by_pid: Mapping[str, Mapping[str, object]],
) -> bool:
    select = policy.get("select")
    if select is None:
        return True
    if not isinstance(select, dict) or len(select) != 1:
        raise AssertionError("fixture page selector has an unsupported shape")
    if "linked_from" in select:
        arguments = select["linked_from"]
        if not isinstance(arguments, dict):
            raise AssertionError("fixture linked_from selector is malformed")
        source_pid = arguments.get("pid")
        field = arguments.get("field")
        if not isinstance(source_pid, str) or not isinstance(field, str):
            raise AssertionError("fixture linked_from selector is malformed")
        source = by_pid.get(source_pid)
        if source is None:
            raise AssertionError(f"fixture selector source is missing: {source_pid}")
        return record["pid"] in _relationship_targets(source, field)
    if "links_to" not in select:
        raise AssertionError("fixture page selector uses an unsupported operator")
    arguments = select["links_to"]
    if not isinstance(arguments, dict):
        raise AssertionError("fixture links_to selector is malformed")
    target = arguments.get("pid")
    field = arguments.get("field")
    recursive = arguments.get("recursive", False)
    if (
        not isinstance(target, str)
        or not isinstance(field, str)
        or not isinstance(recursive, bool)
    ):
        raise AssertionError("fixture links_to selector is malformed")

    def links(candidate: Mapping[str, object], visited: set[str]) -> bool:
        for linked_pid in _relationship_targets(candidate, field):
            if linked_pid == target:
                return True
            linked = by_pid.get(linked_pid)
            if recursive and linked is not None and linked_pid not in visited:
                if links(linked, {*visited, linked_pid}):
                    return True
        return False

    pid = record["pid"]
    return links(record, {pid})


class AcceptedConsumerCompatibilityTests(unittest.TestCase):
    """Exercise the package against one frozen set of tracked consumer inputs."""

    @classmethod
    def setUpClass(cls) -> None:
        value = os.environ.get(CONSUMER_ENVIRONMENT)
        if not value:
            raise AssertionError(
                f"{CONSUMER_ENVIRONMENT} must name the frozen consumer checkout"
            )
        cls.accepted_consumer = Path(value).resolve()
        result = subprocess.run(
            ["git", "-C", str(cls.accepted_consumer), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise AssertionError(
                f"accepted consumer fixture is not a Git checkout: {detail}"
            )
        if result.stdout.strip() != CONSUMER_COMMIT:
            raise AssertionError(
                "accepted consumer fixture should be "
                f"{CONSUMER_COMMIT}, not {result.stdout.strip()}"
            )
        status = subprocess.run(
            [
                "git",
                "-C",
                str(cls.accepted_consumer),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if status.returncode or status.stdout:
            detail = (status.stderr or status.stdout).strip()
            raise AssertionError(f"accepted consumer fixture is modified: {detail}")
        required = [cls.accepted_consumer / item for item in TRACKED_INPUTS]
        required.append(
            SCHEMA_SOURCE / "demo-research-information/unreleased.yaml"
        )
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise AssertionError(
                "accepted compatibility inputs are missing: " + ", ".join(missing)
            )

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        temporary = Path(self.temporary.name)
        self.root = temporary / "consumer"
        self.resources_010 = temporary / "resources-0.1.0"
        self.resources_011 = temporary / "resources-0.1.1"
        self.root.mkdir()
        for relative in TRACKED_INPUTS:
            source = self.accepted_consumer / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copyfile(source, destination)
        localize_schema(
            SCHEMA_SOURCE,
            SCHEMA_SOURCE / "demo-research-information/unreleased.yaml",
            self.resources_010 / "schema",
        )
        shutil.copytree(self.resources_010 / "schema", self.resources_011 / "schema")
        self.workspace = WorkspaceConfig(
            root=self.root,
            config_path=self.root / "orinoco.yaml",
            lock_path=self.root / "orinoco.lock",
            site_name="Full fixture",
            base_url="https://example.invalid/",
            paths=DEFAULT_PATHS,
            raw={},
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _active_files(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
            and path.name not in {".gitattributes", "SHA256SUMS"}
            and not _is_historical_provenance(root, path)
        }

    def test_full_parity_stale_recovery_atomicity_and_patch_compatibility(self) -> None:
        temporary = Path(self.temporary.name)
        candidate = temporary / "candidate"
        repeated = temporary / "candidate-repeat"
        previous_limit = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(1000)
            with self.assertNoLogs("dump_things_service", level="WARNING"):
                report = render_projection(
                    self.workspace, self.resources_010, candidate
                )
                repeated_report = render_projection(
                    self.workspace, self.resources_010, repeated
                )
            self.assertEqual(sys.getrecursionlimit(), 1000)
        finally:
            sys.setrecursionlimit(previous_limit)
        self.assertEqual(repeated_report, report)
        self.assertEqual(
            self._active_files(candidate),
            self._active_files(repeated),
        )

        records = _fixture_records(self.root)
        projected_records = [
            json.loads(line)
            for line in (candidate / "records.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            if line
        ]
        projected_by_pid = {record["pid"]: record for record in projected_records}
        self.assertEqual(len(projected_records), len(projected_by_pid))
        self.assertEqual(set(projected_by_pid), set(records))
        self.assertEqual(
            {
                pid: record["schema_type"]
                for pid, record in projected_by_pid.items()
            },
            {pid: record["schema_type"] for pid, record in records.items()},
        )

        configuration = yaml.safe_load(
            (self.root / "site/projection.yaml").read_text(encoding="utf-8")
        )
        homepage_pid = configuration["homepage"]["pid"]
        page_policies = configuration["pages"]
        expected_page_pids = {homepage_pid}
        expected_page_pids.update(
            pid
            for pid, record in records.items()
            if record["schema_type"] in page_policies
            and _selected_by_fixture_policy(
                record,
                page_policies[record["schema_type"]],
                records,
            )
        )
        route_prefix = configuration["routing"]["strip_prefix"]
        expected_pages = {
            "content/_index.md": homepage_pid,
            **{
                (
                    "content/"
                    + pid.removeprefix(route_prefix).strip("/")
                    + "/_index.md"
                ): pid
                for pid in expected_page_pids - {homepage_pid}
            },
        }
        self.assertEqual(len(expected_pages), len(expected_page_pids))
        actual_page_paths = [
            path.relative_to(candidate).as_posix()
            for path in (candidate / "content").rglob("*.md")
        ]
        self.assertEqual(len(actual_page_paths), len(set(actual_page_paths)))
        self.assertEqual(set(actual_page_paths), set(expected_pages))
        for relative, pid in expected_pages.items():
            source = (candidate / relative).read_text(encoding="utf-8")
            self.assertTrue(source.startswith("---\n"), relative)
            frontmatter = yaml.safe_load(source.split("---", 2)[1])
            self.assertEqual(frontmatter["params"]["graphRootNodePID"], pid)

        graph_node_classes = set(configuration["graph"]["node_classes"])
        expected_nodes = {
            pid
            for pid, record in records.items()
            if record["schema_type"] in graph_node_classes
        }
        expected_edges = {
            (pid, target)
            for pid in expected_nodes
            for field in configuration["graph"]["relationship_fields"]
            for target in _relationship_targets(records[pid], field)
            if target in expected_nodes
        }
        graph = json.loads(
            (candidate / "static/graph.json").read_text(encoding="utf-8")
        )
        actual_nodes = [node["id"] for node in graph["nodes"]]
        actual_edges = [
            (edge["source"], edge["target"]) for edge in graph["edges"]
        ]
        self.assertEqual(len(actual_nodes), len(set(actual_nodes)))
        self.assertEqual(set(actual_nodes), expected_nodes)
        self.assertEqual(len(actual_edges), len(set(actual_edges)))
        self.assertEqual(set(actual_edges), expected_edges)

        expected_report = {
            "records": len(records),
            "pages": len(expected_pages),
            "graph_nodes": len(expected_nodes),
            "graph_edges": len(expected_edges),
        }
        self.assertEqual(
            {key: report[key] for key in expected_report},
            expected_report,
        )
        self.assertNotIn(
            "xyzri:XYZ",
            (
                ROOT / "packages/orinoco-lite/src/orinoco_lite/projection.py"
            ).read_text(encoding="utf-8"),
        )

        committed = self.root / "generated/projection"
        committed.parent.mkdir(parents=True)
        shutil.copytree(candidate, committed)

        semantic = {key: report[key] for key in report if key != "pages"}
        with patch("orinoco_lite.projection.validate_semantics", return_value=semantic):
            verified = verify_projection(self.workspace, self.resources_010)
        self.assertTrue(verified["deterministic"])
        self.assertEqual(
            projection_manifest(self.workspace, self.resources_010, committed),
            projection_manifest(self.workspace, self.resources_011, committed),
        )

        record = next(
            path
            for path in (self.root / "metadata/records").rglob("*.yaml")
            if not path.name.startswith(".")
        )
        record.write_text(
            record.read_text(encoding="utf-8") + "# stale edit\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(DriverError, "stale"):
            verify_projection(self.workspace, self.resources_010)
        with patch("orinoco_lite.projection.validate_semantics", return_value=semantic):
            update_projection(self.workspace, self.resources_010)
            verify_projection(self.workspace, self.resources_011)

        before = tree_sha256(committed)
        real_replace = os.replace
        replacements = 0

        def fail_install(source, destination):
            nonlocal replacements
            replacements += 1
            if replacements == 2:
                raise OSError("injected projection install failure")
            return real_replace(source, destination)

        with patch("orinoco_lite.projection.validate_semantics", return_value=semantic):
            with patch("orinoco_lite.projection.os.replace", side_effect=fail_install):
                with self.assertRaisesRegex(OSError, "injected"):
                    update_projection(self.workspace, self.resources_010)
        self.assertEqual(tree_sha256(committed), before)

        producer = self.root / "site/projection-tools/pool2graph.py"
        producer.write_text(
            producer.read_text(encoding="utf-8")
            + "\nprint('missing node', file=sys.stderr)\n",
            encoding="utf-8",
        )
        with patch("orinoco_lite.projection.validate_semantics", return_value=semantic):
            with self.assertRaisesRegex(DriverError, "missing node"):
                render_projection(
                    self.workspace,
                    self.resources_010,
                    temporary / "bad-graph",
                )


if __name__ == "__main__":
    unittest.main()

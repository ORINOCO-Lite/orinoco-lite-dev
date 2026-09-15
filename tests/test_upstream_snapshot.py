from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import pytest

from orinoco_lite import upstream_snapshot as snapshot


def record(
    pid: str,
    *,
    class_name: str = "XYZProject",
    **fields: object,
) -> snapshot.RecordEnvelope:
    return snapshot.RecordEnvelope(
        class_name=class_name,
        record={
            "pid": pid,
            "schema_type": f"xyzri:{class_name}",
            **fields,
        },
    )


class UpstreamSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_jsonl(
        self,
        envelopes: list[snapshot.RecordEnvelope],
        *,
        name: str = "records.jsonl",
    ) -> Path:
        path = self.root / name
        lines = [
            json.dumps(
                {"class_name": item.class_name, "record": item.record},
                allow_nan=False,
                ensure_ascii=False,
            )
            for item in envelopes
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def fixture(self) -> list[snapshot.RecordEnvelope]:
        return [
            record(
                "xyzrins:projects/alpha",
                name="Données naïves 🧠",
                active=True,
                absent=None,
                integer=1,
                decimal=1.0,
                negative_zero=-0.0,
                temporal_strings=["2026-08-25", "12:34:56", "yes", "null"],
                ordered=["second", "first", "second"],
                nested={"z": 2, "a": [{"b": 2, "a": 1}]},
            ),
            record(
                "other:projects/alpha",
                class_name="XYZDataset",
                same_final_segment=True,
            ),
        ]

    def test_jsonl_yaml_jsonl_roundtrip_is_exact_and_canonical(self) -> None:
        source = self.write_jsonl(self.fixture())
        records_root = self.root / "metadata" / "records"
        manifest_path = self.root / "snapshot-manifest.json"

        manifest = snapshot.materialize(
            source,
            records_root,
            manifest_path=manifest_path,
        )
        exported = self.root / "exported.jsonl"
        actual = snapshot.export_records(records_root, exported)

        snapshot.compare_snapshots(self.fixture(), actual)
        self.assertEqual(manifest["record_count"], 2)
        self.assertEqual(
            manifest["records_semantic_sha256"],
            snapshot.semantic_digest(actual),
        )
        self.assertEqual(json.loads(manifest_path.read_text()), manifest)
        for path in records_root.rglob("*.yaml"):
            loaded = snapshot._load_yaml_mapping(path)
            self.assertEqual(path.read_bytes(), snapshot.canonical_yaml_bytes(loaded))

    def test_materialization_is_independent_of_source_line_order(self) -> None:
        first_source = self.write_jsonl(self.fixture(), name="first.jsonl")
        second_source = self.write_jsonl(
            list(reversed(self.fixture())), name="second.jsonl"
        )
        first_tree = self.root / "first-tree"
        second_tree = self.root / "second-tree"

        snapshot.materialize(first_source, first_tree)
        snapshot.materialize(second_source, second_tree)

        self.assertEqual(
            snapshot.records_tree_digest(first_tree),
            snapshot.records_tree_digest(second_tree),
        )
        self.assertEqual(
            {
                path.relative_to(first_tree): path.read_bytes()
                for path in first_tree.rglob("*.yaml")
            },
            {
                path.relative_to(second_tree): path.read_bytes()
                for path in second_tree.rglob("*.yaml")
            },
        )

    def test_repeated_list_values_and_order_are_not_deduplicated(self) -> None:
        source = self.write_jsonl(self.fixture())
        tree = self.root / "tree"
        snapshot.materialize(source, tree)

        loaded = {item.pid: item for item in snapshot.load_records_tree(tree)}

        self.assertEqual(
            loaded["xyzrins:projects/alpha"].record["ordered"],
            ["second", "first", "second"],
        )

    def test_upstream_store_schema_type_is_rehydrated_without_mutation(self) -> None:
        source_record = record(
            "xyzrins:projects/alpha",
            name="Stored without a redundant class field",
        )
        source = self.write_jsonl([source_record])
        store = self.root / "store"
        class_dir = store / source_record.class_name
        class_dir.mkdir(parents=True)
        stored_record = dict(source_record.record)
        stored_record.pop("schema_type")
        (class_dir / "record.yaml").write_bytes(
            snapshot.canonical_yaml_bytes(stored_record)
        )
        (store / ".dumpthings.yaml").write_text("type: records\n", encoding="utf-8")
        (store / ".directory_dir_index.db").write_bytes(b"ignored index")

        result = snapshot.verify(source, store, upstream_store=True)

        self.assertEqual(result["record_count"], 1)
        self.assertNotIn(
            b"schema_type", (class_dir / "record.yaml").read_bytes()
        )

    def test_number_type_change_is_not_treated_as_equal(self) -> None:
        expected = [record("xyzrins:projects/alpha", value=1)]
        actual = [record("xyzrins:projects/alpha", value=1.0)]

        with self.assertRaisesRegex(snapshot.SnapshotError, "JSON record differs"):
            snapshot.compare_snapshots(expected, actual)

    def test_duplicate_pid_is_rejected_instead_of_deduplicated(self) -> None:
        source = self.write_jsonl(
            [
                record("xyzrins:projects/duplicate", name="first"),
                record("xyzrins:projects/duplicate", name="second"),
            ]
        )

        with self.assertRaisesRegex(snapshot.SnapshotError, "duplicate record pid"):
            snapshot.load_jsonl(source)

    def test_duplicate_yaml_mapping_key_is_rejected(self) -> None:
        tree = self.root / "tree" / "XYZProject"
        tree.mkdir(parents=True)
        (tree / "record.yaml").write_text(
            "pid: xyzrins:projects/alpha\n"
            "pid: xyzrins:projects/beta\n"
            "schema_type: xyzri:XYZProject\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(snapshot.SnapshotError, "duplicate key"):
            snapshot.load_records_tree(tree.parent)

    def test_class_and_schema_type_mismatch_is_rejected(self) -> None:
        invalid = snapshot.RecordEnvelope(
            class_name="XYZProject",
            record={
                "pid": "xyzrins:projects/alpha",
                "schema_type": "xyzri:XYZDataset",
            },
        )
        source = self.write_jsonl([invalid])

        with self.assertRaisesRegex(snapshot.SnapshotError, "does not match"):
            snapshot.load_jsonl(source)

    def test_noncanonical_yaml_is_rejected(self) -> None:
        tree = self.root / "tree" / "XYZProject"
        tree.mkdir(parents=True)
        (tree / "record.yaml").write_text(
            "schema_type: xyzri:XYZProject\npid: xyzrins:projects/alpha\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(snapshot.SnapshotError, "is not canonical"):
            snapshot.load_records_tree(tree.parent)

    def test_symlink_and_unexpected_file_are_rejected(self) -> None:
        source = self.write_jsonl([record("xyzrins:projects/alpha")])
        tree = self.root / "tree"
        snapshot.materialize(source, tree)
        (tree / "notes.txt").write_text("not metadata\n", encoding="utf-8")
        with self.assertRaisesRegex(snapshot.SnapshotError, "unexpected"):
            snapshot.load_records_tree(tree)

        (tree / "notes.txt").unlink()
        target = next(tree.rglob("*.yaml"))
        (tree / "linked.yaml").symlink_to(target)
        with self.assertRaisesRegex(snapshot.SnapshotError, "symlink"):
            snapshot.load_records_tree(tree)


@pytest.mark.parametrize(("pid", "reference"), [
    ("xyzrins:persons/michael-hanke", "persons/michael-hanke.yaml"),
    ("xyzrins:projects/87be5fa3-80fb-4221-8406-2ddd40fb1fd1",
     "projects/87be5fa3-80fb-4221-8406-2ddd40fb1fd1.yaml"),
    ("dldi:01ed46012d5a6bcb384e8a5e6b0be62824cb09a3/datalad/commit",
     "01ed46012d5a6bcb384e8a5e6b0be62824cb09a3/datalad/commit.yaml"),
    ("xyzrins:.", "_root.yaml"),
    ("ror:", "_empty.yaml"),
    ("http://edamontology.org/format_3548", "edamontology.org/format_3548.yaml"),
    ("http://www.cogpo.org/ontologies/CogPOver1.owl#COGPO_00053",
     "www.cogpo.org/ontologies/CogPOver1.owl%23COGPO_00053.yaml"),
    ("https://example.org:8443/a?b=c", "example.org%3A8443/a%3Fb%3Dc.yaml"),
    ("spdxlic:GPL-2.0+", "GPL-2.0%2B.yaml"),
    ("ex:with space/naïve%name", "with%20space/na%C3%AFve%25name.yaml"),
])
def test_readable_pid_paths_preserve_records(tmp_path, pid, reference):
    original = record(pid, related_to=["xyzrins:persons/michael-hanke"])
    tree = tmp_path / "records"
    snapshot.write_records_tree([original], tree)

    expected = Path("XYZProject") / reference
    assert snapshot.record_relative_path(original) == expected
    assert (tree / expected).read_bytes() == snapshot.canonical_yaml_bytes(original.record)
    assert snapshot.load_records_tree(tree) == [original]


def test_full_reference_keeps_distinct_records_with_the_same_basename(tmp_path):
    records = [record("dldi:first/datalad/commit", class_name="XYZFile"),
               record("dldi:second/datalad/commit", class_name="XYZFile")]
    tree = tmp_path / "records"
    snapshot.write_records_tree(records, tree)

    assert snapshot.load_records_tree(tree) == records
    assert {p.relative_to(tree).as_posix() for p in tree.rglob("*.yaml")} == {
        "XYZFile/first/datalad/commit.yaml", "XYZFile/second/datalad/commit.yaml",
    }


@pytest.mark.parametrize("pid", [
    "ex:../outside", "ex:a/../outside", "ex:a/./b", "ex:a//b",
    "ex:/absolute", "ex:a/", "ex:.hidden", "ex:a/.hidden/b",
    "ex:a\\..\\outside", "https://example.org/../outside",
])
def test_unsafe_pid_paths_leave_destination_untouched(tmp_path, pid):
    tree = tmp_path / "records"
    tree.mkdir()
    marker = tree / "preserved.txt"
    marker.write_bytes(b"existing content")

    with pytest.raises(snapshot.SnapshotError, match="unsafe record path"):
        snapshot.write_records_tree([record(pid)], tree, replace=True)

    assert list(tree.iterdir()) == [marker]
    assert marker.read_bytes() == b"existing content"


@pytest.mark.parametrize("pids", [
    ("one:projects/alpha", "two:projects/alpha"),
    ("ex:Alpha", "ex:alpha"),
    ("ex:.", "ex:_root"),
    ("ex:", "ex:_empty"),
    ("http://example.org/one", "https://example.org/one"),
    ("ex:one", "ex:one.yaml/two"),
    ("ex:ONE", "ex:one.YAML/two"),
])
def test_path_collisions_leave_destination_untouched(tmp_path, pids):
    tree = tmp_path / "records"
    tree.mkdir()
    marker = tree / "preserved.txt"
    marker.write_bytes(b"existing content")

    with pytest.raises(snapshot.SnapshotError, match="path collision"):
        snapshot.write_records_tree([record(pid) for pid in pids], tree, replace=True)

    assert list(tree.iterdir()) == [marker]
    assert marker.read_bytes() == b"existing content"


if __name__ == "__main__":
    unittest.main()

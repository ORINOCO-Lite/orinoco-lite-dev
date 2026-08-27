from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

from tools import check_upstream_orinoco as check
from tools import upstream_orinoco as fixture


class UpstreamOrinocoTests(unittest.TestCase):
    def test_projection_tracks_every_observed_top_level_class(self) -> None:
        classes = Counter(
            {
                "xyzri:XYZProject": 2,
                "xyzri:XYZPublication": 3,
                "xyzri:XYZOrganization": 1,
                "dlthings:Thing": 4,
            }
        )

        contract = fixture.projection_contract(classes)

        declared = set(contract["pages"]) | set(contract["unrendered_classes"])
        self.assertEqual(declared, set(classes) | set(fixture.PAGE_POLICIES))
        self.assertNotIn("xyzri:XYZProject", contract["unrendered_classes"])
        self.assertIn("dlthings:Thing", contract["unrendered_classes"])
        self.assertEqual(contract["editor"], {"record_scope": "editable"})
        self.assertEqual(
            contract["references"],
            {"missing_targets": "preserve"},
        )
        self.assertEqual(contract["graph"]["missing_external_targets"], "drop")

    def test_projection_targets_objects_inside_qualified_relationships(self) -> None:
        contract = fixture.projection_contract(Counter())
        policies = {
            **contract["pages"],
            "homepage": contract["homepage"],
        }
        qualified_fields = {
            "xyzri:XYZDataset": ("attributed_to", "characterized_by"),
            "xyzri:XYZProject": ("associated_with", "influenced_by"),
            "xyzri:XYZPerson": ("delegated_by",),
            "xyzri:XYZPublication": ("attributed_to",),
            "xyzri:XYZInstrument": ("attributed_to",),
            "homepage": ("associated_with", "influenced_by"),
        }

        for policy_name, fields in qualified_fields.items():
            inline = policies[policy_name]["inline"]
            for field in fields:
                with self.subTest(policy=policy_name, field=field):
                    self.assertIn(f"{field}::object", inline)
                    self.assertNotIn(field, inline)

    def test_source_copy_flattens_annex_style_links_and_ignores_nested_git(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "destination"
            object_path = root / "annex-object"
            object_path.write_bytes(b"payload")
            source.mkdir()
            (source / "asset.png").symlink_to(object_path)
            (source / "ordinary.txt").write_text("ordinary\n", encoding="utf-8")
            (source / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
            nested = source / "theme"
            nested.mkdir()
            (nested / ".git").mkdir()
            (nested / ".git" / "config").write_text("ignored\n", encoding="utf-8")
            (nested / "theme.txt").write_text("theme\n", encoding="utf-8")

            fixture.copy_regular_tree(source, destination)

            self.assertEqual((destination / "asset.png").read_bytes(), b"payload")
            self.assertFalse((destination / "asset.png").is_symlink())
            self.assertFalse((destination / ".git").exists())
            self.assertFalse((destination / "theme" / ".git").exists())
            self.assertTrue((destination / "theme" / "theme.txt").is_file())

    def test_unavailable_annex_link_fails_instead_of_copying_a_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "missing.png").symlink_to(root / "absent-object")

            with self.assertRaisesRegex(
                fixture.UpstreamOrinocoError, "git-annex can hydrate"
            ):
                fixture.copy_regular_tree(source, root / "destination")

    def test_fixture_destination_must_stay_under_ignored_build_root(self) -> None:
        with self.assertRaisesRegex(
            fixture.UpstreamOrinocoError, "must be below"
        ):
            fixture._safe_destination(fixture.ROOT / "outside-fixture")

        self.assertEqual(
            fixture._safe_destination(fixture.BUILD / "safe-fixture"),
            (fixture.BUILD / "safe-fixture").resolve(),
        )

    def test_copied_provenance_replaces_developer_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.json"
            destination = root / "portable.json"
            source.write_text(
                json.dumps({"source_jsonl": "/private/worktree/records.jsonl"}),
                encoding="utf-8",
            )

            fixture._copy_portable_json(
                source,
                destination,
                rewrites={
                    "source_jsonl": (
                        "source-adapters/upstream-snapshot/public-thing.jsonl"
                    )
                },
            )

            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8")),
                {
                    "source_jsonl": (
                        "source-adapters/upstream-snapshot/public-thing.jsonl"
                    )
                },
            )

    def test_console_comparison_bounds_large_route_inventory(self) -> None:
        report = {
            "upstream_only_routes": ["/legacy/"],
            "orinoco_only_routes": [f"/records/{index}/" for index in range(20)],
        }

        summary = check.console_summary(report)

        self.assertEqual(summary["orinoco_only_route_count"], 20)
        self.assertEqual(len(summary["orinoco_only_route_sample"]), 10)
        self.assertNotIn("orinoco_only_routes", summary)
        self.assertEqual(summary["upstream_only_routes"], ["/legacy/"])
        self.assertIn("orinoco_only_routes", report)

    def test_release_probe_uses_the_generated_repository_environment(self) -> None:
        command = check.released_engine_command("/opt/pixi")

        self.assertEqual(
            command,
            [
                "/opt/pixi",
                "run",
                "--frozen",
                "--manifest-path",
                check.FIXTURE / "pixi.toml",
                "orinoco",
                "--root",
                check.FIXTURE,
                "projection",
                "update",
            ],
        )


if __name__ == "__main__":
    unittest.main()

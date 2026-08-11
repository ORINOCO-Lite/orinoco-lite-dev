from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import con_projection as PROJECTION  # noqa: E402


class CleanProjectionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not PROJECTION.PROFILE_PATH.is_file():
            raise unittest.SkipTest("clean-migration site gitlink is not pinned")

    def source_closure(self) -> list[PROJECTION.SourceRecord]:
        canonical = PROJECTION.source_records(
            PROJECTION.PROFILE_ROOT / "metadata" / "records",
            "canonical",
        )
        references = PROJECTION.source_records(
            PROJECTION.PROFILE_ROOT / "metadata" / "reference",
            "reference",
        )
        return [*canonical, *references]

    def test_site_history_is_exactly_two_isolated_commits(self) -> None:
        profile = PROJECTION.load_yaml(PROJECTION.PROFILE_PATH)
        PROJECTION.verify_declared_pins(profile)
        base = profile["components"]["www_from_model"]["commit"]
        subjects = subprocess.run(
            [
                "git",
                "-C",
                str(PROJECTION.SITE),
                "log",
                "--reverse",
                "--format=%s",
                f"{base}..HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        self.assertEqual(
            subjects,
            [
                "build(clean-migration): add the CON site profile",
                "feat(content): add the clean CON vertical slice",
            ],
        )

    def test_native_metadata_and_committed_projection_close_exactly(self) -> None:
        records = self.source_closure()
        PROJECTION.validate_record_contract(records)
        observed = PROJECTION.native_value_fingerprint(
            [item.record for item in records]
        )
        self.assertEqual(
            {schema_type for schema_type, _ in observed},
            PROJECTION.REQUIRED_NATIVE_TYPES,
        )
        self.assertIn(
            (
                "dlthings:DOI",
                json.dumps({"notation": "10.21105/joss.03262"}),
            ),
            observed,
        )
        self.assertIn(
            (
                "dlthings:ISSN",
                json.dumps({"notation": "2475-9066"}),
            ),
            observed,
        )

        PROJECTION.verify_manifest(PROJECTION.COMMITTED)
        snapshot = [
            json.loads(line)
            for line in (PROJECTION.COMMITTED / "records.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
        report = PROJECTION.validate_projection(snapshot, PROJECTION.COMMITTED)
        self.assertEqual(report["graph_nodes"], 6)
        self.assertEqual(report["graph_edges"], 7)
        self.assertEqual(report["pages"], 5)

    def test_invalid_discriminators_bridges_and_targets_are_rejected(self) -> None:
        original = self.source_closure()

        def replace_association(
            value: object,
            replacement: str,
        ) -> bool:
            if isinstance(value, dict):
                if value.get("schema_type") == "dlthings:Association":
                    value["schema_type"] = replacement
                    return True
                return any(
                    replace_association(child, replacement)
                    for child in value.values()
                )
            if isinstance(value, list):
                return any(
                    replace_association(child, replacement) for child in value
                )
            return False

        for replacement, message in (
            (
                "https://concepts.datalad.org/s/things/v2/Association",
                "full-URI",
            ),
            ("dlthings:NotARealAssociation", "unknown CURIE"),
        ):
            records = deepcopy(original)
            self.assertTrue(
                replace_association(records[0].record, replacement)
                or any(
                    replace_association(item.record, replacement)
                    for item in records[1:]
                )
            )
            with self.assertRaisesRegex(PROJECTION.ProjectionError, message):
                PROJECTION.validate_record_contract(records)

        dangling = deepcopy(original)
        project = next(
            item
            for item in dangling
            if item.record["pid"] == "xyzrins:projects/datalad"
        )
        project.record["associated_with"][0]["object"] = "xyzrins:missing"
        with self.assertRaisesRegex(PROJECTION.ProjectionError, "dangling"):
            PROJECTION.validate_record_contract(dangling)

        bridge = deepcopy(original)
        project = next(
            item
            for item in bridge
            if item.record["pid"] == "xyzrins:projects/datalad"
        )
        project.record.setdefault("attributes", []).append(
            {
                "predicate": "dcterms:relation",
                "value": "xyzrins:missing",
                "schema_type": "dlthings:AttributeSpecification",
            }
        )
        with self.assertRaisesRegex(
            PROJECTION.ProjectionError,
            "cannot encode relationship",
        ):
            PROJECTION.validate_record_contract(bridge)

    def test_portrait_remains_an_annex_pointer_and_snapshot_has_no_assets(self) -> None:
        portrait = "profiles/con/assets/img/yaroslav-halchenko.jpg"
        entry = subprocess.run(
            [
                "git",
                "-C",
                str(PROJECTION.SITE),
                "ls-tree",
                "HEAD",
                portrait,
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertTrue(entry.startswith("120000 blob "))
        target = subprocess.run(
            [
                "git",
                "-C",
                str(PROJECTION.SITE),
                "show",
                f"HEAD:{portrait}",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertIn(
            "MD5E-s37940--90e74fa17a709006dd527c5b36e41217.jpg",
            target,
        )
        assets = [
            path
            for path in (PROJECTION.COMMITTED / "content").rglob("*")
            if path.is_file() and path.suffix.lower() not in {".md"}
        ]
        self.assertEqual(assets, [])


if __name__ == "__main__":
    unittest.main()

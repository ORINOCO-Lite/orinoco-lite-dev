from __future__ import annotations

from copy import deepcopy
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.annotations import annotation_companion, assertion_sha256
from orinoco_lite.candidates import (
    Candidate,
    CandidateOperation,
    CandidatePlan,
    friendly_record_label,
    source_claim_sha256,
)
from orinoco_lite.canonical import (
    canonical_json,
    canonical_json_bytes,
    canonical_yaml_bytes,
)
from orinoco_lite.errors import ConfigurationError


NAMESPACE = "https://source.example/records"
BASE = "0123456789abcdef0123456789abcdef01234567"
AGENT = "xyzrins:source-adapters/example/v1"


def record(pid: str, name: str, **values: object) -> dict[str, object]:
    return {
        "schema_type": "xyzri:XYZOrganization",
        "pid": pid,
        "name": name,
        "attributes": [
            {
                "predicate": "schema:name",
                "schema_type": "dlthings:AttributeSpecification",
                "value": name,
            }
        ],
        **values,
    }


def companion(
    pid: str,
    source: dict[str, object],
    *,
    imported_by: str = AGENT,
) -> dict[str, object]:
    return annotation_companion(
        pid,
        [
            {
                "path": "/attributes",
                "assertion_sha256": assertion_sha256(source["attributes"][0]),
                "pav:importedBy": imported_by,
                "pav:importedFrom": f"{NAMESPACE}/one",
            }
        ],
    )


def candidate(
    source_id: str,
    pid: str,
    path: str,
    *,
    baseline: dict[str, object] | None,
    proposed: dict[str, object] | None,
    baseline_annotations: dict[str, object] | None = None,
    proposed_annotations: dict[str, object] | None = None,
    claim: dict[str, object] | None = None,
    blockers: tuple[str, ...] = (),
    record_root: str | None = "site-specific/metadata/records",
    annotation_root: str | None = (
        "site-specific/metadata/overlays/annotations"
    ),
) -> Candidate:
    return Candidate(
        source_namespace=NAMESPACE,
        source_record_id=source_id,
        pid=pid,
        record_path=path,
        baseline_record=baseline,
        proposed_record=proposed,
        baseline_companion=baseline_annotations,
        proposed_companion=proposed_annotations,
        source_claim=claim or {"name": "source name"},
        blockers=blockers,
        record_root=record_root,
        annotation_root=annotation_root,
    )


class CanonicalJsonTests(unittest.TestCase):
    def test_sorted_unicode_compact_json_preserves_list_order(self) -> None:
        value = {"z": [2, 1], "a": "é"}

        self.assertEqual(canonical_json(value), '{"a":"é","z":[2,1]}')
        self.assertEqual(canonical_json_bytes(value), canonical_json(value).encode())

    def test_python_only_or_non_finite_values_fail_closed(self) -> None:
        for value in ({1: "not a JSON key"}, {"tuple": (1, 2)}, {"nan": math.nan}):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                canonical_json(value)


class SourceClaimTests(unittest.TestCase):
    def test_hash_uses_only_canonical_source_mapped_content(self) -> None:
        first = {
            "z": ["first", "second"],
            "a": {
                "value": "é",
                "annotations": {"pav:importedBy": "old-agent"},
            },
        }
        reordered = {
            "a": {
                "annotations": {"pav:importedBy": "new-agent"},
                "value": "é",
            },
            "z": ["first", "second"],
        }

        one = source_claim_sha256(
            first,
            pid="xyzrins:records/one",
            record_path="XYZOrganization/one.yaml",
        )
        two = source_claim_sha256(
            reordered,
            pid="xyzrins:records/one",
            record_path="XYZOrganization/one.yaml",
        )

        self.assertEqual(one, two)
        self.assertEqual(
            one,
            "sha256:8be4d66d84ee29ca86ab26e7f62bd9b4593a1ba23e89ee2227d162693aec4878",
        )

    def test_list_order_target_and_delete_action_are_material(self) -> None:
        common = {
            "pid": "xyzrins:records/one",
            "record_path": "XYZOrganization/one.yaml",
        }
        forward = source_claim_sha256({"values": [1, 2]}, **common)
        reversed_items = source_claim_sha256({"values": [2, 1]}, **common)
        moved = source_claim_sha256(
            {"values": [1, 2]},
            pid=common["pid"],
            record_path="XYZOrganization/moved.yaml",
        )
        deletion = source_claim_sha256(
            {"values": [1, 2]}, deletion=True, **common
        )

        self.assertEqual(len({forward, reversed_items, moved, deletion}), 4)

    def test_non_json_claim_fails_with_focused_error(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "deterministic JSON"):
            source_claim_sha256(
                {"bad": {1, 2}},
                pid="xyzrins:records/one",
                record_path="XYZOrganization/one.yaml",
            )
        with self.assertRaisesRegex(ConfigurationError, "must be Boolean"):
            source_claim_sha256(
                {"name": "one"},
                pid="xyzrins:records/one",
                record_path="XYZOrganization/one.yaml",
                deletion="false",
            )


class CandidateTests(unittest.TestCase):
    def test_add_modify_and_delete_are_derived_from_record_states(self) -> None:
        pid = "xyzrins:records/one"
        path = "XYZOrganization/one.yaml"
        old = record(pid, "old")
        new = record(pid, "new")

        addition = candidate("add", pid, path, baseline=None, proposed=new)
        modification = candidate("modify", pid, path, baseline=old, proposed=new)
        deletion = candidate("delete", pid, path, baseline=old, proposed=None)

        self.assertEqual(addition.operation, CandidateOperation.ADD)
        self.assertEqual(modification.operation, CandidateOperation.MODIFY)
        self.assertEqual(deletion.operation, CandidateOperation.DELETE)

    def test_add_and_modify_share_claim_identity_across_curated_baselines(self) -> None:
        pid = "xyzrins:records/one"
        path = "XYZOrganization/one.yaml"
        desired = record(pid, "source name")
        claim = {"assertions": [{"path": "/name", "value": "source name"}]}

        addition = candidate(
            "one",
            pid,
            path,
            baseline=None,
            proposed=desired,
            claim=claim,
            blockers=("diagnostic:one",),
        )
        correction = candidate(
            "one",
            pid,
            path,
            baseline=record(pid, "human correction"),
            proposed=desired,
            claim=claim,
            blockers=("diagnostic:two",),
        )
        deletion = candidate(
            "one", pid, path, baseline=record(pid, "human correction"), proposed=None
        )

        self.assertEqual(addition.claim_sha256, correction.claim_sha256)
        self.assertNotEqual(addition.claim_sha256, deletion.claim_sha256)

    def test_labels_are_friendly_and_deletion_uses_the_baseline(self) -> None:
        pid = "xyzrins:records/one"
        path = "XYZOrganization/one.yaml"
        addition = candidate(
            "one",
            pid,
            path,
            baseline=None,
            proposed=record(pid, "fallback", display_label="  Friendly\n label "),
        )
        deletion = candidate(
            "one",
            pid,
            path,
            baseline=record(pid, "Deleted label"),
            proposed=None,
        )
        pid_fallback = candidate(
            "two",
            "xyzrins:records/two",
            "XYZOrganization/two.yaml",
            baseline=None,
            proposed={
                "pid": "xyzrins:records/two",
                "schema_type": "xyzri:XYZOrganization",
            },
        )

        self.assertEqual(addition.label, "Friendly label")
        self.assertEqual(deletion.label, "Deleted label")
        self.assertEqual(pid_fallback.label, "xyzrins:records/two")
        self.assertEqual(
            friendly_record_label(
                {
                    "formatted_name": "Formatted person",
                    "short_name": "Short",
                },
                pid,
            ),
            "Formatted person",
        )
        self.assertEqual(
            friendly_record_label({"short_name": "Short"}, pid),
            "Short",
        )

    def test_inputs_and_exposed_nested_values_cannot_mutate_a_candidate(self) -> None:
        pid = "xyzrins:records/one"
        proposed = record(pid, "source name", aliases=[{"name": "first"}])
        source_claim = {"aliases": [{"name": "first"}]}
        item = candidate(
            "one",
            pid,
            "XYZOrganization/one.yaml",
            baseline=None,
            proposed=proposed,
            claim=source_claim,
        )
        digest = item.claim_sha256

        proposed["name"] = "mutated"
        source_claim["aliases"][0]["name"] = "mutated"
        exposed = item.source_claim["aliases"]
        exposed[0]["name"] = "also mutated"

        self.assertEqual(item.proposed_record["name"], "source name")
        self.assertEqual(item.source_claim["aliases"], [{"name": "first"}])
        self.assertEqual(item.claim_sha256, digest)
        with self.assertRaises(TypeError):
            item.proposed_record["name"] = "forbidden"

    def test_canonical_file_changes_include_the_mirrored_companion(self) -> None:
        pid = "xyzrins:records/one"
        old = record(pid, "old")
        new = record(pid, "new")
        item = candidate(
            "one",
            pid,
            "XYZOrganization/one.yaml",
            baseline=old,
            proposed=new,
            baseline_annotations=companion(pid, old),
            proposed_annotations=companion(pid, new),
        )

        changes = {change.path: change for change in item.file_changes()}

        self.assertEqual(
            set(changes),
            {
                "site-specific/metadata/records/XYZOrganization/one.yaml",
                "site-specific/metadata/overlays/annotations/XYZOrganization/one.yaml",
            },
        )
        self.assertEqual(
            changes[item.record_repository_path].proposed,
            canonical_yaml_bytes(new),
        )
        self.assertEqual(
            changes[item.companion_repository_path].proposed,
            canonical_yaml_bytes(companion(pid, new)),
        )

    def test_delete_serialization_uses_none_for_both_removed_files(self) -> None:
        pid = "xyzrins:records/one"
        old = record(pid, "old")
        item = candidate(
            "one",
            pid,
            "XYZOrganization/one.yaml",
            baseline=old,
            proposed=None,
            baseline_annotations=companion(pid, old),
        )

        self.assertTrue(all(change.proposed is None for change in item.file_changes()))

    def test_configured_legacy_and_custom_metadata_roots_are_preserved(self) -> None:
        pid = "xyzrins:records/one"
        cases = (
            (
                "records",
                "overlays/annotations",
            ),
            (
                "metadata/records",
                "metadata/overlays/annotations",
            ),
            (
                "custom/library/records",
                "custom/library/overlays/annotations",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for record_root, annotation_root in cases:
                environment = {
                    "ORINOCO_ROOT": os.fspath(root),
                    "ORINOCO_RECORDS_ROOT": os.fspath(root / record_root),
                }
                with self.subTest(record_root=record_root), patch.dict(
                    os.environ, environment, clear=True
                ):
                    item = candidate(
                        "one",
                        pid,
                        "XYZOrganization/one.yaml",
                        baseline=None,
                        proposed=record(pid, "One"),
                        record_root=None,
                        annotation_root=None,
                    )

                self.assertEqual(
                    item.record_repository_path,
                    f"{record_root}/XYZOrganization/one.yaml",
                )
                self.assertEqual(
                    item.companion_repository_path,
                    f"{annotation_root}/XYZOrganization/one.yaml",
                )

    def test_unconfigured_candidate_preserves_the_legacy_default(self) -> None:
        pid = "xyzrins:records/one"
        with patch.dict(os.environ, {}, clear=True):
            item = Candidate(
                source_namespace=NAMESPACE,
                source_record_id="one",
                pid=pid,
                record_path="XYZOrganization/one.yaml",
                baseline_record=None,
                proposed_record=record(pid, "One"),
                baseline_companion=None,
                proposed_companion=None,
                source_claim={"name": "One"},
            )

        self.assertEqual(
            item.record_repository_path,
            "metadata/records/XYZOrganization/one.yaml",
        )

    def test_candidate_metadata_roots_fail_closed(self) -> None:
        pid = "xyzrins:records/one"
        common = {
            "source_namespace": NAMESPACE,
            "source_record_id": "one",
            "pid": pid,
            "record_path": "XYZOrganization/one.yaml",
            "baseline_record": None,
            "proposed_record": record(pid, "One"),
            "baseline_companion": None,
            "proposed_companion": None,
            "source_claim": {"name": "One"},
        }
        for values in (
            {"record_root": "../records"},
            {"record_root": " padded/records"},
            {"record_root": "a" * 1_025},
            {
                "record_root": "metadata/records",
                "annotation_root": "other/annotations",
            },
        ):
            with self.subTest(values=values), self.assertRaises(ConfigurationError):
                Candidate(**common, **values)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = (
                {"ORINOCO_ROOT": os.fspath(root)},
                {"ORINOCO_RECORDS_ROOT": os.fspath(root / "metadata/records")},
                {
                    "ORINOCO_ROOT": os.fspath(root / "repository"),
                    "ORINOCO_RECORDS_ROOT": os.fspath(root / "outside/records"),
                },
            )
            for environment in cases:
                with self.subTest(environment=environment), patch.dict(
                    os.environ, environment, clear=True
                ), self.assertRaises(ConfigurationError):
                    Candidate(**common)

            configured = root / "repository"
            environment = {
                "ORINOCO_ROOT": os.fspath(configured),
                "ORINOCO_RECORDS_ROOT": os.fspath(
                    configured / "site-specific/metadata/records"
                ),
            }
            with patch.dict(os.environ, environment, clear=True), self.assertRaisesRegex(
                ConfigurationError, "configured workspace record root"
            ):
                Candidate(
                    **common,
                    record_root="other/records",
                    annotation_root="other/overlays/annotations",
                )

    def test_invalid_identity_record_path_and_companion_fail_closed(self) -> None:
        pid = "xyzrins:records/one"
        old = record(pid, "old")
        new = record(pid, "new")
        cases = (
            {"source_record_id": " bad "},
            {"record_path": "../one.yaml"},
            {"record_path": "XYZOrganization/.one.yaml"},
            {"record_path": "XYZOrganization/one.json"},
            {"proposed_record": record("different", "new")},
            {
                "proposed_record": {
                    "pid": pid,
                    "schema_type": "xyzri:XYZOrganization",
                    "pav:importedBy": "machine",
                }
            },
            {
                "baseline_record": None,
                "baseline_companion": companion(pid, old),
            },
        )
        base = {
            "source_namespace": NAMESPACE,
            "source_record_id": "one",
            "pid": pid,
            "record_path": "XYZOrganization/one.yaml",
            "baseline_record": old,
            "proposed_record": new,
            "baseline_companion": None,
            "proposed_companion": None,
            "source_claim": {"name": "new"},
        }
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ConfigurationError):
                Candidate(**{**base, **changes})

    def test_noop_and_provenance_only_candidates_are_rejected(self) -> None:
        pid = "xyzrins:records/one"
        current = record(pid, "current")
        common = {
            "source_namespace": NAMESPACE,
            "source_record_id": "one",
            "pid": pid,
            "record_path": "XYZOrganization/one.yaml",
            "baseline_record": current,
            "proposed_record": deepcopy(current),
            "source_claim": {"name": "current"},
        }

        with self.assertRaisesRegex(ConfigurationError, "unchanged"):
            Candidate(
                **common,
                baseline_companion=None,
                proposed_companion=None,
            )
        with self.assertRaisesRegex(ConfigurationError, "provenance-only"):
            Candidate(
                **common,
                baseline_companion=None,
                proposed_companion=companion(pid, current),
            )

    def test_companion_order_and_blocker_set_are_exact(self) -> None:
        pid = "xyzrins:records/one"
        old = record(pid, "old", display_label="Old")
        new = record(pid, "new", display_label="New")
        new["attributes"].append(
            {
                "predicate": "skos:prefLabel",
                "schema_type": "dlthings:AttributeSpecification",
                "value": new["display_label"],
            }
        )
        annotations = annotation_companion(
            pid,
            [
                {
                    "path": "/attributes",
                    "assertion_sha256": assertion_sha256(new["attributes"][0]),
                    "pav:importedBy": "xyzrins:source-adapters/example/v1",
                    "pav:importedFrom": f"{NAMESPACE}/one",
                },
                {
                    "path": "/attributes",
                    "assertion_sha256": assertion_sha256(new["attributes"][1]),
                    "pav:importedBy": "xyzrins:source-adapters/example/v1",
                    "pav:importedFrom": f"{NAMESPACE}/one",
                },
            ],
        )
        noncanonical = deepcopy(annotations)
        noncanonical["assertions"].reverse()

        with self.assertRaisesRegex(
            ConfigurationError, "deterministic assertion order"
        ):
            candidate(
                "one",
                pid,
                "XYZOrganization/one.yaml",
                baseline=old,
                proposed=new,
                proposed_annotations=noncanonical,
            )
        with self.assertRaisesRegex(ConfigurationError, "unique"):
            candidate(
                "one",
                pid,
                "XYZOrganization/one.yaml",
                baseline=old,
                proposed=new,
                blockers=("same", "same"),
            )

        stale = deepcopy(annotations)
        stale["assertions"][1]["assertion_sha256"] = assertion_sha256(
            {"value": "stale"}
        )
        with self.assertRaisesRegex(ConfigurationError, "matched zero assertions"):
            candidate(
                "one",
                pid,
                "XYZOrganization/one.yaml",
                baseline=old,
                proposed=new,
                proposed_annotations=stale,
            )


class CandidatePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        first_pid = "xyzrins:records/first"
        second_pid = "xyzrins:records/second"
        self.first = candidate(
            "first",
            first_pid,
            "XYZOrganization/first.yaml",
            baseline=None,
            proposed=record(first_pid, "First"),
        )
        second_old = record(second_pid, "old")
        second_new = record(second_pid, "new")
        self.second = candidate(
            "second",
            second_pid,
            "XYZOrganization/second.yaml",
            baseline=second_old,
            proposed=second_new,
            baseline_annotations=companion(second_pid, second_old),
            proposed_annotations=companion(second_pid, second_new),
        )

    def plan(self, candidates: tuple[Candidate, ...]) -> CandidatePlan:
        return CandidatePlan(
            adapter="example-adapter",
            adapter_version="1.0.0",
            adapter_agent_pid=AGENT,
            source_namespace=NAMESPACE,
            source_coordinate={"revision": "source-42"},
            metadata_base=BASE,
            candidates=candidates,
        )

    def test_plan_sorts_candidates_and_file_changes_deterministically(self) -> None:
        plan = self.plan((self.second, self.first))

        self.assertEqual(
            [item.source_record_id for item in plan.candidates],
            ["first", "second"],
        )
        paths = [change.path for change in plan.file_changes()]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(len(paths), 3)

    def test_plan_rejects_mixed_metadata_roots(self) -> None:
        pid = "xyzrins:records/custom"
        custom = candidate(
            "custom",
            pid,
            "XYZOrganization/custom.yaml",
            baseline=None,
            proposed=record(pid, "Custom"),
            record_root="custom/records",
            annotation_root="custom/overlays/annotations",
        )

        with self.assertRaisesRegex(ConfigurationError, "metadata root pair"):
            self.plan((self.first, custom))

    def test_source_coordinate_is_detached_and_read_only(self) -> None:
        coordinate = {"revision": "source-42", "nested": {"value": 1}}
        plan = CandidatePlan(
            adapter="example-adapter",
            adapter_version="1.0.0",
            adapter_agent_pid=AGENT,
            source_namespace=NAMESPACE,
            source_coordinate=coordinate,
            metadata_base=BASE,
            candidates=(),
        )

        coordinate["revision"] = "moved"
        nested = plan.source_coordinate["nested"]
        nested["value"] = 2

        self.assertEqual(plan.source_coordinate["revision"], "source-42")
        self.assertEqual(plan.source_coordinate["nested"], {"value": 1})
        with self.assertRaises(TypeError):
            plan.source_coordinate["revision"] = "forbidden"

    def test_duplicate_source_pid_or_path_is_rejected(self) -> None:
        duplicate_source = candidate(
            "first",
            "xyzrins:records/third",
            "XYZOrganization/third.yaml",
            baseline=None,
            proposed=record("xyzrins:records/third", "Third"),
        )
        duplicate_pid = candidate(
            "third",
            self.first.pid,
            "XYZOrganization/third.yaml",
            baseline=None,
            proposed=record(self.first.pid, "Third"),
        )
        duplicate_path = candidate(
            "third",
            "xyzrins:records/third",
            self.first.record_path,
            baseline=None,
            proposed=record("xyzrins:records/third", "Third"),
        )

        for duplicate, message in (
            (duplicate_source, "source identity"),
            (duplicate_pid, "target PID"),
            (duplicate_path, "record path"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(
                ConfigurationError, message
            ):
                self.plan((self.first, duplicate))

    def test_plan_requires_its_agent_only_for_new_or_changed_pav(self) -> None:
        pid = "xyzrins:records/other-owned"
        baseline = record(pid, "unchanged", display_label="Before")
        proposed = record(pid, "unchanged", display_label="After")
        other_agent = "xyzrins:source-adapters/other/v4"
        unchanged = candidate(
            "other-owned",
            pid,
            "XYZOrganization/other-owned.yaml",
            baseline=baseline,
            proposed=proposed,
            baseline_annotations=companion(
                pid, baseline, imported_by=other_agent
            ),
            proposed_annotations=companion(
                pid, baseline, imported_by=other_agent
            ),
        )

        self.plan((unchanged,))

        changed = candidate(
            "other-owned",
            pid,
            "XYZOrganization/other-owned.yaml",
            baseline=record(pid, "before"),
            proposed=record(pid, "after"),
            baseline_annotations=companion(
                pid, record(pid, "before"), imported_by=other_agent
            ),
            proposed_annotations=companion(
                pid, record(pid, "after"), imported_by=other_agent
            ),
        )
        with self.assertRaisesRegex(ConfigurationError, "adapter agent PID"):
            self.plan((changed,))

    def test_record_edit_cannot_hide_same_assertion_ownership_rewrite(self) -> None:
        pid = "xyzrins:records/ownership"
        baseline = record(pid, "unchanged", display_label="Before")
        proposed = record(pid, "unchanged", display_label="After")
        other_agent = "xyzrins:source-adapters/other/v4"
        rewritten = candidate(
            "ownership",
            pid,
            "XYZOrganization/ownership.yaml",
            baseline=baseline,
            proposed=proposed,
            baseline_annotations=companion(
                pid, baseline, imported_by=other_agent
            ),
            proposed_annotations=companion(pid, proposed, imported_by=AGENT),
        )

        with self.assertRaisesRegex(ConfigurationError, "rewrite provenance"):
            self.plan((rewritten,))

    def test_plan_rejects_mixed_namespaces_and_invalid_coordinates(self) -> None:
        different = Candidate(
            source_namespace="https://other.example/records",
            source_record_id="other",
            pid="xyzrins:records/other",
            record_path="XYZOrganization/other.yaml",
            baseline_record=None,
            proposed_record=record("xyzrins:records/other", "Other"),
            baseline_companion=None,
            proposed_companion=None,
            source_claim={"name": "Other"},
        )

        with self.assertRaisesRegex(ConfigurationError, "does not match"):
            self.plan((different,))
        with self.assertRaisesRegex(ConfigurationError, "must not be empty"):
            CandidatePlan(
                adapter="example-adapter",
                adapter_version="1.0.0",
                adapter_agent_pid=AGENT,
                source_namespace=NAMESPACE,
                source_coordinate={},
                metadata_base=BASE,
                candidates=(),
            )
        for bad_base in ("ABCDEF" * 6 + "ABCD", "0" * 39, "g" * 40):
            with self.subTest(bad_base=bad_base), self.assertRaisesRegex(
                ConfigurationError, "40-hex Git commit"
            ):
                CandidatePlan(
                    adapter="example-adapter",
                    adapter_version="1.0.0",
                    adapter_agent_pid=AGENT,
                    source_namespace=NAMESPACE,
                    source_coordinate={"revision": "source-42"},
                    metadata_base=bad_base,
                    candidates=(),
                )


if __name__ == "__main__":
    unittest.main()

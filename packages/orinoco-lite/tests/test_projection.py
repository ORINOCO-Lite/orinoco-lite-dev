from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from orinoco_lite.annotations import annotation_companion, assertion_sha256
from orinoco_lite.canonical import canonical_yaml
from orinoco_lite.config import DEFAULT_PATHS, WorkspaceConfig
from orinoco_lite.errors import DriverError
from orinoco_lite.integrity import tree_sha256
from orinoco_lite.projection import (
    _all_links,
    _apply_inline,
    _is_historical_provenance,
    _machine_pav_fingerprint,
    _matches_policy,
    _native_fingerprint,
    _relationship_targets,
    _route_for_pid,
    load_contract,
    projection_manifest,
    rendered_record_route,
    render_projection,
    update_projection,
    validate_semantics,
    verify_projection,
)
from orinoco_lite.schema_conversion import build_format_converters


ENGINE_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_SOURCE = ENGINE_ROOT / "submodules/things-schemas/src"


class SemanticReferencePolicyTests(unittest.TestCase):
    """Apply one general open-reference policy to every recognized link."""

    @staticmethod
    def _validate(
        record: dict[str, object],
        *,
        missing_reference_targets: str = "reject",
        to_ttl: Mock | None = None,
    ) -> dict[str, object]:
        contract = Mock(
            homepage_pid="acme:.",
            pages={"acme:Thing": Mock()},
            unrendered_classes=frozenset(),
            relationship_fields=("about",),
            graph_node_classes=frozenset({"acme:Thing"}),
            missing_reference_targets=missing_reference_targets,
            missing_graph_targets="reject",
        )
        schema_view = Mock()
        schema_view.all_classes.return_value = ["Thing", "Identifier"]
        class_uris = {
            "Thing": "acme:Thing",
            "Identifier": "dlthings:Identifier",
        }
        schema_view.get_uri.side_effect = (
            lambda name, **_kwargs: class_uris.get(name)
        )
        if to_ttl is None:
            to_ttl = Mock()
            to_ttl.convert.side_effect = lambda value, _class_name: deepcopy(value)
        to_json = Mock()
        to_json.convert.side_effect = lambda value, _class_name: deepcopy(value)
        with (
            patch("orinoco_lite.projection.load_contract", return_value=contract),
            patch(
                "orinoco_lite.projection._records",
                return_value=([record], {str(record["pid"])}),
            ),
            patch("orinoco_lite.projection.SchemaView", return_value=schema_view),
            patch(
                "orinoco_lite.projection.build_format_converters",
                return_value=(to_ttl, to_json),
            ),
        ):
            return validate_semantics(Mock(), Path("/unused-runtime"))

    def test_preserve_policy_reports_external_creator_and_keeps_scalar(
        self,
    ) -> None:
        creator = "https://identifiers.example/agency"
        record = {
            "pid": "acme:.",
            "schema_type": "acme:Thing",
            "identifiers": [
                {
                    "creator": creator,
                    "notation": "one",
                    "schema_type": "dlthings:Identifier",
                }
            ],
        }

        self.assertEqual(
            self._validate(record, missing_reference_targets="preserve"),
            {
                "records": 1,
                "graph_nodes": 1,
                "graph_edges": 0,
                "preserved_reference_targets": 1,
                "preserved_reference_unique_targets": 1,
                "preserved_references_by_field": {
                    "identifiers.creator": 1,
                },
            },
        )
        projected = deepcopy(record)
        _apply_inline(projected, "identifiers::creator", {})
        self.assertEqual(projected["identifiers"][0]["creator"], creator)

    @unittest.skipUnless(
        (SCHEMA_SOURCE / "demo-research-information/unreleased.yaml").is_file(),
        "pinned Things Schema fixture is unavailable",
    )
    def test_pinned_thing_range_round_trip_preserves_external_creator_pid(
        self,
    ) -> None:
        creator = "https://identifiers.example/agency"
        record = {
            "pid": "xyzrins:records/one",
            "schema_type": "xyzri:XYZPublication",
            "title": "A title",
            "identifiers": [
                {
                    "creator": creator,
                    "notation": "one",
                    "schema_type": "dlthings:Identifier",
                }
            ],
        }
        schema = SCHEMA_SOURCE / "demo-research-information/unreleased.yaml"
        to_rdf, to_json = build_format_converters(schema)

        restored = to_json.convert(
            to_rdf.convert(record, "XYZPublication"),
            "XYZPublication",
        )

        self.assertEqual(restored["identifiers"][0]["creator"], creator)

    def test_local_identifier_creator_is_inlined(self) -> None:
        creator = "acme:agencies/one"
        agency = {
            "pid": creator,
            "schema_type": "acme:Thing",
            "display_label": "Agency One",
        }
        record = {"identifiers": [{"creator": creator}]}

        _apply_inline(record, "identifiers::creator", {creator: agency})

        self.assertEqual(record["identifiers"][0]["creator"], agency)

    def test_external_creator_still_reaches_schema_conversion(self) -> None:
        record = {
            "pid": "acme:.",
            "schema_type": "acme:Thing",
            "identifiers": [
                {
                    "creator": "not a valid Thing PID",
                    "notation": "one",
                    "schema_type": "dlthings:Identifier",
                }
            ],
        }
        to_ttl = Mock()
        to_ttl.convert.side_effect = ValueError("invalid creator PID")

        with self.assertRaisesRegex(
            DriverError,
            "JSON/RDF/JSON schema validation failed: invalid creator PID",
        ):
            self._validate(
                record,
                missing_reference_targets="preserve",
                to_ttl=to_ttl,
            )

        to_ttl.convert.assert_called_once()

    def test_missing_graph_relationship_target_still_fails(self) -> None:
        record = {
            "pid": "acme:.",
            "schema_type": "acme:Thing",
            "about": ["https://topics.example/missing"],
        }

        with self.assertRaisesRegex(
            DriverError,
            "dangling about target https://topics.example/missing",
        ):
            self._validate(record)

    def test_other_required_local_reference_kinds_still_fail(self) -> None:
        cases = (
            (
                {
                    "about": [
                        {
                            "object": "acme:.",
                            "roles": ["acme:roles/missing"],
                        }
                    ]
                },
                "about.roles",
            ),
            ({"kind": "acme:kinds/missing"}, "kind"),
            ({"rules": ["acme:rules/missing"]}, "rules"),
        )
        for fields, label in cases:
            with self.subTest(field=label):
                record = {
                    "pid": "acme:.",
                    "schema_type": "acme:Thing",
                    **fields,
                }
                with self.assertRaisesRegex(
                    DriverError,
                    f"dangling {label} target",
                ):
                    self._validate(record)

    def test_explicit_reject_policy_includes_identifier_creators(self) -> None:
        record = {
            "pid": "acme:.",
            "about": [
                {
                    "object": "acme:topics/one",
                    "roles": ["acme:roles/one"],
                }
            ],
            "kind": "acme:kinds/one",
            "rules": ["acme:rules/one"],
            "identifiers": [{"creator": "https://identifiers.example/agency"}],
        }

        self.assertEqual(
            list(_all_links(record, ("about",))),
            [
                ("about", "acme:topics/one"),
                ("about.roles", "acme:roles/one"),
                ("kind", "acme:kinds/one"),
                ("rules", "acme:rules/one"),
                (
                    "identifiers.creator",
                    "https://identifiers.example/agency",
                ),
            ],
        )
        with self.assertRaisesRegex(
            DriverError,
            "dangling identifiers.creator target",
        ):
            self._validate(
                {
                    "pid": "acme:.",
                    "schema_type": "acme:Thing",
                    "identifiers": [
                        {"creator": "https://identifiers.example/agency"}
                    ],
                }
            )


class QueryInlineParityTests(unittest.TestCase):
    """Match the pinned query-things path walker without a live resolver."""

    def setUp(self) -> None:
        self.by_pid = {
            "acme:one": {"pid": "acme:one", "label": "One"},
            "acme:two": {"pid": "acme:two", "label": "Two"},
        }

    def test_nested_path_preserves_missing_children_and_unresolved_scalars(
        self,
    ) -> None:
        record = {
            "groups": [
                {
                    "items": [
                        {"target": "acme:one"},
                        {"label": "no target"},
                    ]
                },
                {
                    "items": {
                        "target": [
                            "acme:two",
                            "external:missing",
                            "plain text",
                        ]
                    }
                },
            ]
        }

        _apply_inline(record, "groups::items::target", self.by_pid)

        self.assertEqual(
            record["groups"][0]["items"][0]["target"],
            self.by_pid["acme:one"],
        )
        self.assertEqual(
            record["groups"][0]["items"][1],
            {"label": "no target"},
        )
        self.assertEqual(
            record["groups"][1]["items"]["target"],
            [
                self.by_pid["acme:two"],
                "external:missing",
                "plain text",
            ],
        )

    def test_multivalued_qualified_relationship_keeps_context_entries(
        self,
    ) -> None:
        record = {
            "associated_with": [
                {
                    "object": ["acme:one", "external:missing"],
                    "roles": ["external:role"],
                },
                {"roles": ["external:context-only"]},
                {"object": "acme:two"},
            ]
        }

        _apply_inline(record, "associated_with::object", self.by_pid)

        self.assertEqual(
            record["associated_with"],
            [
                {
                    "object": [self.by_pid["acme:one"], "external:missing"],
                    "roles": ["external:role"],
                },
                {"roles": ["external:context-only"]},
                {"object": self.by_pid["acme:two"]},
            ],
        )

    def test_behavior_matches_the_exact_pinned_query_things_walker(self) -> None:
        source = (
            ENGINE_ROOT
            / "submodules/query-things/query_things/inline_things.py"
        )
        if not source.is_file():
            self.skipTest("pinned query-things source fixture is unavailable")
        common = types.ModuleType("query_things.common")
        common.RecordCache = object
        common.iter_json_objects = lambda: ()
        common.make_record_resolver = lambda **_kwargs: None
        common.stdargs = {
            "--api-url": {},
            "--record-cache": {},
            "--token": {},
            "collection": {},
        }
        spec = importlib.util.spec_from_file_location(
            "orinoco_pinned_query_inline",
            source,
        )
        assert spec is not None and spec.loader is not None
        pinned = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"query_things.common": common}):
            spec.loader.exec_module(pinned)

        value = {
            "groups": [
                {
                    "items": [
                        {"target": ["acme:one", "external:missing"]},
                        {"label": "unmatched"},
                    ]
                }
            ]
        }
        expected = deepcopy(value)
        pinned.walk(
            expected,
            ("groups", "items", "target"),
            self.by_pid.get,
        )
        actual = deepcopy(value)
        _apply_inline(actual, "groups::items::target", self.by_pid)

        self.assertEqual(actual, expected)

    def test_recursive_selector_follows_qualified_pid_arrays(self) -> None:
        records = [
            {
                "pid": "acme:projects/child",
                "part_of": [{"object": ["acme:projects/mid", "external:parent"]}],
            },
            {
                "pid": "acme:projects/mid",
                "part_of": "acme:.",
            },
            {"pid": "acme:."},
        ]
        by_pid = {record["pid"]: record for record in records}
        policy = Mock(
            select={
                "links_to": {
                    "pid": "acme:.",
                    "field": "part_of",
                    "recursive": True,
                }
            }
        )

        self.assertTrue(_matches_policy(records[0], policy, by_pid))
        self.assertEqual(
            _route_for_pid(records[0]["pid"], "acme:"),
            "projects/child",
        )

    def test_shared_record_routes_reject_unrendered_and_unsafe_records(self) -> None:
        policy = Mock(select={})
        contract = Mock(
            homepage_pid="acme:site",
            route_prefix="acme:",
            pages={"acme:Project": policy},
        )
        by_pid = {
            "acme:site": {"pid": "acme:site", "schema_type": "acme:Site"},
            "acme:projects/one": {
                "pid": "acme:projects/one",
                "schema_type": "acme:Project",
            },
            "acme:unrendered": {
                "pid": "acme:unrendered",
                "schema_type": "acme:Other",
            },
        }

        self.assertEqual(rendered_record_route("acme:site", contract, by_pid), "")
        self.assertEqual(
            rendered_record_route("acme:projects/one", contract, by_pid),
            "projects/one",
        )
        with self.assertRaisesRegex(DriverError, "unrendered record"):
            rendered_record_route("acme:unrendered", contract, by_pid)
        with self.assertRaisesRegex(DriverError, "unknown PID"):
            rendered_record_route("acme:missing", contract, by_pid)

        for pid in (
            "acme:",
            "acme:/projects/one",
            "acme:projects/one/",
            "acme://projects/one//",
            "acme:.",
            "acme:../escape",
            "acme:%2e%2e/escape",
            "acme:%252e%252e/escape",
            "acme:projects\\escape",
            "acme:projects/one?view=full",
            "acme:projects/one#section",
            'acme:projects/bad\" >}}injected{{< ref \"x',
            "acme:projects/'quoted'",
            "acme:projects/control\nvalue",
            "other:one",
        ):
            unsafe = {"pid": pid, "schema_type": "acme:Project"}
            with self.subTest(pid=pid), self.assertRaises(DriverError):
                rendered_record_route(pid, contract, {pid: unsafe})


class GenericProjectionContractTests(unittest.TestCase):
    """Keep core projection mechanics hermetic and independent of CON content."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "consumer"
        self.runtime = Path(self.temporary.name) / "runtime"
        for relative in (
            "metadata/records/Person",
            "site/projection-templates",
            "site/projection-tools",
            "generated",
        ):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        (self.root / "metadata/records/Person/home.yaml").write_text(
            "pid: acme:.\nschema_type: acme:Person\ndisplay_label: Home\n",
            encoding="utf-8",
        )
        (self.root / "metadata/records/Person/one.yaml").write_text(
            "pid: acme:people/one\n"
            "schema_type: acme:Person\n"
            "display_label: One\n"
            "attributes:\n"
            "- predicate: skos:prefLabel\n"
            "  schema_type: dlthings:AttributeSpecification\n"
            "  value: One\n",
            encoding="utf-8",
        )
        (self.root / "site/projection-templates/page.md.j2").write_text(
            "---\npid: {{ pid }}\n---\n{{ display_label }}\n", encoding="utf-8"
        )
        (self.root / "site/projection-tools/graph.py").write_text(
            "import json,sys\n"
            "records=[json.loads(line) for line in sys.stdin if line.strip()]\n"
            "json.dump({'nodes':[{'id': r['pid']} for r in records], 'edges':[]},sys.stdout)\n",
            encoding="utf-8",
        )
        (self.root / "site/projection.yaml").write_text(
            "version: 2\n"
            "routing:\n  strip_prefix: 'acme:'\n"
            "homepage:\n  pid: 'acme:.'\n  template: site/projection-templates/page.md.j2\n"
            "pages:\n  'acme:Person':\n    template: site/projection-templates/page.md.j2\n"
            "    inline: [attributes::annotations::source::creator]\n"
            "unrendered_classes: []\n"
            "graph:\n  producer: site/projection-tools/graph.py\n"
            "  node_classes: ['acme:Person']\n  relationship_fields: []\n",
            encoding="utf-8",
        )
        schema = self.runtime / "schema/demo/main.yaml"
        imported = self.runtime / "schema/types/base.yaml"
        schema.parent.mkdir(parents=True)
        imported.parent.mkdir(parents=True)
        schema.write_text("id: https://example.invalid/main\nimports: [../types/base]\n", encoding="utf-8")
        imported.write_text("id: https://example.invalid/base\n", encoding="utf-8")
        sources = []
        for relative in ("demo/main.yaml", "types/base.yaml"):
            data = (self.runtime / "schema" / relative).read_bytes()
            sources.append(
                {
                    "localized_path": relative,
                    "source_path": relative,
                    "source_sha256": hashlib.sha256(data).hexdigest(),
                    "localized_sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        (self.runtime / "schema/source-inventory.json").write_text(
            json.dumps(
                {
                    "entrypoint": "demo/main.yaml",
                    "format": "orinoco-localized-linkml-source-closure",
                    "sources": sources,
                    "version": 1,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        self.workspace = WorkspaceConfig(
            root=self.root,
            config_path=self.root / "orinoco.yaml",
            lock_path=self.root / "orinoco.lock",
            site_name="Generic fixture",
            base_url="https://example.invalid/",
            paths=DEFAULT_PATHS,
            command_aliases={},
            raw={},
        )
        self.semantic = {
            "records": 2,
            "graph_nodes": 2,
            "graph_edges": 0,
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _validate_records(
        self,
        records: list[dict[str, object]],
    ) -> dict[str, object]:
        class IdentityConverter:
            @staticmethod
            def convert(value, _class_name):
                return deepcopy(value)

        schema_view = Mock()
        schema_view.all_classes.return_value = ["Person"]
        schema_view.get_uri.return_value = "acme:Person"
        with (
            patch(
                "orinoco_lite.projection._records",
                return_value=(records, {str(item["pid"]) for item in records}),
            ),
            patch("orinoco_lite.projection.SchemaView", return_value=schema_view),
            patch(
                "orinoco_lite.projection.build_format_converters",
                return_value=(IdentityConverter(), IdentityConverter()),
            ),
        ):
            return validate_semantics(self.workspace, self.runtime)

    def test_non_xyz_route_closure_pin_and_single_semantic_pass(self) -> None:
        contract = load_contract(self.workspace)
        self.assertEqual(contract.editor_record_scope, "all")
        self.assertEqual(contract.missing_reference_targets, "preserve")
        self.assertEqual(contract.missing_graph_targets, "drop")
        self.assertEqual(
            contract.pages["acme:Person"].inline,
            ("attributes::annotations::source::creator",),
        )
        with patch(
            "orinoco_lite.projection.validate_semantics", return_value=self.semantic
        ) as semantic:
            update_projection(self.workspace, self.runtime)
            semantic.reset_mock()
            report = verify_projection(self.workspace, self.runtime)
            semantic.assert_called_once()
        self.assertTrue(report["deterministic"])
        self.assertTrue(
            (
                self.root
                / "generated/projection/content/people/one/_index.md"
            ).is_file()
        )
        imported = self.runtime / "schema/types/base.yaml"
        imported.write_text(imported.read_text() + "# semantic change\n", encoding="utf-8")
        with self.assertRaisesRegex(DriverError, "stale"):
            verify_projection(self.workspace, self.runtime)

    def test_noncanonical_pid_route_fails_before_overwriting_a_page(self) -> None:
        alias = self.root / "metadata/records/Person/alias.yaml"
        alias.write_text(
            "pid: acme:people/one/\n"
            "schema_type: acme:Person\n"
            "display_label: Alias\n",
            encoding="utf-8",
        )
        output = Path(self.temporary.name) / "route-collision-projection"

        with patch(
            "orinoco_lite.projection.validate_semantics",
            return_value={**self.semantic, "records": 3},
        ), self.assertRaisesRegex(DriverError, "unsafe route"):
            render_projection(self.workspace, self.runtime, output)

        canonical = output / "content/people/one/_index.md"
        self.assertTrue(canonical.is_file())
        self.assertIn("One", canonical.read_text(encoding="utf-8"))
        self.assertNotIn("Alias", canonical.read_text(encoding="utf-8"))

    def test_joined_annotations_reach_machine_projection_only(self) -> None:
        companion = self.root / (
            "metadata/overlays/annotations/Person/one.yaml"
        )
        companion.parent.mkdir(parents=True)
        companion.write_text(
            canonical_yaml(
                annotation_companion(
                    "acme:people/one",
                    [
                        {
                            "path": "/attributes",
                            "assertion_sha256": assertion_sha256(
                                {
                                    "predicate": "skos:prefLabel",
                                    "schema_type": (
                                        "dlthings:AttributeSpecification"
                                    ),
                                    "value": "One",
                                }
                            ),
                            "pav:importedBy": "acme:source-adapters/example/v1",
                            "pav:importedFrom": "https://source.example/people/one",
                        }
                    ],
                )
            ),
            encoding="utf-8",
        )

        output = Path(self.temporary.name) / "annotated-projection"
        with patch(
            "orinoco_lite.projection.validate_semantics", return_value=self.semantic
        ):
            render_projection(self.workspace, self.runtime, output)

        public_page = output / "content/people/one/_index.md"
        self.assertEqual(
            public_page.read_text(encoding="utf-8"),
            "---\npid: acme:people/one\n---\nOne\n",
        )
        records = [
            json.loads(line)
            for line in (output / "records.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        joined = next(item for item in records if item["pid"] == "acme:people/one")
        self.assertNotIn("annotations", joined)
        self.assertEqual(
            joined["attributes"][0]["annotations"]["pav:importedBy"]
            ["annotation_value"],
            "acme:source-adapters/example/v1",
        )
        stored = (
            self.root / "metadata/records/Person/one.yaml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("pav:imported", stored)
        manifest = (output / "SHA256SUMS").read_text(encoding="utf-8")
        self.assertIn(
            "input:metadata/overlays/annotations/Person/one.yaml",
            manifest,
        )

    def test_default_open_reference_policy_reports_omissions(self) -> None:
        projection = self.root / "site/projection.yaml"
        projection.write_text(
            projection.read_text(encoding="utf-8")
            .replace(
                "homepage:\n",
                "editor:\n  record_scope: editable\nhomepage:\n",
            )
            .replace(
                "relationship_fields: []",
                "relationship_fields: [about]",
            ),
            encoding="utf-8",
        )
        records = [
            {
                "pid": "acme:.",
                "schema_type": "acme:Person",
                "display_label": "Home",
                "about": [{"roles": ["ext:role"]}],
            },
            {
                "pid": "acme:people/one",
                "schema_type": "acme:Person",
                "display_label": "One",
                "about": [
                    {
                        "object": ["ext:topic", "ext:topic-two"],
                        "roles": ["ext:qualified-role"],
                    }
                ],
                "identifiers": [{"creator": "https://registry.example/"}],
            },
        ]

        report = self._validate_records(records)

        self.assertEqual(
            report,
            {
                "records": 2,
                "graph_nodes": 2,
                "graph_edges": 0,
                "preserved_reference_targets": 5,
                "preserved_reference_unique_targets": 5,
                "preserved_references_by_field": {
                    "about": 2,
                    "about.roles": 2,
                    "identifiers.creator": 1,
                },
                "dropped_graph_edges": 2,
                "dropped_graph_edges_by_field": {"about": 2},
                "targetless_relationship_contexts": 1,
                "targetless_relationship_contexts_by_field": {"about": 1},
            },
        )
        self.assertEqual(
            load_contract(self.workspace).editor_record_scope,
            "editable",
        )
        self.assertEqual(
            load_contract(self.workspace).missing_graph_targets,
            "drop",
        )
        self.assertEqual(
            list(_relationship_targets(records[0], "about")),
            [],
        )

        graph = self.root / "site/projection-tools/graph.py"
        graph.write_text(
            graph.read_text(encoding="utf-8")
            + "print('Dropped non-materialized graph targets', file=sys.stderr)\n",
            encoding="utf-8",
        )
        output = Path(self.temporary.name) / "open-projection"
        with patch(
            "orinoco_lite.projection.validate_semantics",
            return_value=report,
        ):
            rendered = render_projection(self.workspace, self.runtime, output)
        self.assertEqual(rendered["dropped_graph_edges"], 2)
        self.assertEqual(
            json.loads((output / "static/graph.json").read_text(encoding="utf-8"))[
                "edges"
            ],
            [],
        )

    def test_explicit_graph_reject_policy_remains_strict(self) -> None:
        projection = self.root / "site/projection.yaml"
        projection.write_text(
            projection.read_text(encoding="utf-8").replace(
                "relationship_fields: []",
                "relationship_fields: [about]\n"
                "  missing_external_targets: reject",
            ),
            encoding="utf-8",
        )
        records = [
            {
                "pid": "acme:.",
                "schema_type": "acme:Person",
                "display_label": "Home",
                "about": ["ext:topic"],
            }
        ]

        with self.assertRaisesRegex(
            DriverError,
            "acme:.: graph target does not materialize: ext:topic",
        ):
            self._validate_records(records)

        self.assertEqual(
            load_contract(self.workspace).missing_graph_targets,
            "reject",
        )

    def test_machine_pav_fingerprint_binds_provenance_to_assertion(self) -> None:
        annotation = {
            "pav:importedBy": {
                "annotation_tag": "pav:importedBy",
                "annotation_value": "acme:source-adapters/example/v1",
            },
            "pav:importedFrom": {
                "annotation_tag": "pav:importedFrom",
                "annotation_value": "https://source.example/people/one",
            },
        }
        original = {
            "notation": "source-one",
            "schema_type": "dlthings:Identifier",
            "annotations": annotation,
        }
        changed_assertion = deepcopy(original)
        changed_assertion["notation"] = "source-two"
        changed_source = deepcopy(original)
        changed_source["annotations"]["pav:importedFrom"][
            "annotation_value"
        ] = "https://source.example/people/two"

        self.assertNotEqual(
            _machine_pav_fingerprint(original),
            _machine_pav_fingerprint(changed_assertion),
        )
        self.assertNotEqual(
            _machine_pav_fingerprint(original),
            _machine_pav_fingerprint(changed_source),
        )

    def test_native_fingerprint_treats_rdf_multivalues_as_unordered(self) -> None:
        first = {
            "schema_type": "dlthings:Rule",
            "attributes": [
                {
                    "schema_type": "dlthings:AttributeSpecification",
                    "predicate": "acme:first",
                    "value": "one",
                },
                {
                    "schema_type": "dlthings:AttributeSpecification",
                    "predicate": "acme:second",
                    "value": "two",
                },
            ],
        }
        second = deepcopy(first)
        second["attributes"].reverse()

        self.assertEqual(
            _native_fingerprint(first),
            _native_fingerprint(second),
        )

    def test_update_preserves_projection_control_sidecar_and_active_ledger(self) -> None:
        projection = self.root / "generated/projection"
        projection.mkdir()
        sidecar = projection / ".gitattributes"
        sidecar_bytes = b"* annex.largefiles=nothing\n"
        sidecar.write_bytes(sidecar_bytes)

        with patch("orinoco_lite.projection.validate_semantics", return_value=self.semantic):
            update_projection(self.workspace, self.runtime)
            report = verify_projection(self.workspace, self.runtime)

        self.assertEqual(sidecar.read_bytes(), sidecar_bytes)
        self.assertTrue((projection / "SHA256SUMS").is_file())
        self.assertNotIn(
            "output:.gitattributes",
            (projection / "SHA256SUMS").read_text(encoding="utf-8"),
        )
        self.assertTrue(report["deterministic"])

    def test_verify_rejects_arbitrary_undeclared_sidecar(self) -> None:
        with patch("orinoco_lite.projection.validate_semantics", return_value=self.semantic):
            update_projection(self.workspace, self.runtime)

        projection = self.root / "generated/projection"
        undeclared = projection / ".undeclared-sidecar"
        undeclared.write_text("must remain in deterministic scope\n", encoding="utf-8")
        (projection / "SHA256SUMS").write_text(
            projection_manifest(self.workspace, self.runtime, projection),
            encoding="utf-8",
        )

        with patch("orinoco_lite.projection.validate_semantics", return_value=self.semantic):
            with self.assertRaisesRegex(
                DriverError,
                r"deterministic regeneration: \.undeclared-sidecar",
            ):
                verify_projection(self.workspace, self.runtime)

    def test_provenance_named_content_remains_in_projection_scope(self) -> None:
        output = self.root / "generated/projection"
        historical = output / "provenance/source.json"
        page = output / "content/topics/provenance/_index.md"

        self.assertTrue(_is_historical_provenance(output, historical))
        self.assertFalse(_is_historical_provenance(output, page))

    def test_double_failure_preserves_recovery_backup(self) -> None:
        with patch("orinoco_lite.projection.validate_semantics", return_value=self.semantic):
            update_projection(self.workspace, self.runtime)
        real_replace = os.replace
        replacements = 0

        def fail_install_and_rollback(source, destination):
            nonlocal replacements
            replacements += 1
            if replacements in {2, 3}:
                raise OSError(f"injected replace failure {replacements}")
            return real_replace(source, destination)

        with patch("orinoco_lite.projection.validate_semantics", return_value=self.semantic):
            with patch(
                "orinoco_lite.projection.os.replace",
                side_effect=fail_install_and_rollback,
            ):
                with self.assertRaisesRegex(DriverError, "original is preserved"):
                    update_projection(self.workspace, self.runtime)
        backups = list((self.root / "generated").glob(".projection-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / "records.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()

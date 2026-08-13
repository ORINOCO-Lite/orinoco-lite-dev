from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import call, patch


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_con_site as BUILD  # noqa: E402
import con_projection as PROJECTION  # noqa: E402


class CleanProjectionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not PROJECTION.PROFILE_PATH.is_file():
            raise unittest.SkipTest("clean-migration site gitlink is not pinned")

    def projection_contract(self) -> PROJECTION.ProjectionContract:
        profile = PROJECTION.load_yaml(PROJECTION.PROFILE_PATH)
        specification = PROJECTION.load_yaml(PROJECTION.PROJECTION_SPEC_PATH)
        graph = specification["graph"]
        producer = PROJECTION.site_manifest_path(
            graph["producer"], "projection.graph.producer"
        )
        graph.setdefault(
            "node_classes",
            sorted(PROJECTION.producer_mapping(producer, "wanted_node_types")),
        )
        graph.setdefault(
            "relationship_fields",
            sorted(PROJECTION.producer_mapping(producer, "wanted_edge_types")),
        )
        return PROJECTION.load_projection_contract(profile, specification)

    def source_closure(self) -> list[PROJECTION.SourceRecord]:
        return PROJECTION.source_closure(self.projection_contract())

    def test_terminal_snapshot_owns_projection_and_assembly_outputs(self) -> None:
        self.assertTrue(
            PROJECTION.generated_snapshot_path("profiles/con/projection/records.jsonl")
        )
        self.assertTrue(
            PROJECTION.generated_snapshot_path("profiles/con/assembly/SHA256SUMS")
        )
        self.assertFalse(
            PROJECTION.generated_snapshot_path("profiles/con/presentation.yaml")
        )

    def test_successor_history_preserves_checkpoint_and_accepts_focused_commits(
        self,
    ) -> None:
        profile = PROJECTION.load_yaml(PROJECTION.PROFILE_PATH)
        PROJECTION.verify_successor_history(profile)
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
        self.assertGreaterEqual(len(subjects), 2)
        self.assertEqual(
            subjects[:2],
            list(PROJECTION.FOUNDATION_SUBJECTS),
        )
        self.assertIn(
            PROJECTION.ACCEPTED_CLEAN_MIGRATION_TIP,
            PROJECTION.checkpoint_refs().values(),
        )
        self.assertIn(
            PROJECTION.ACCEPTED_CLEAN_MIGRATION_PARENT_TIP,
            PROJECTION.checkpoint_refs(ROOT).values(),
        )

    def test_final_site_state_requires_terminal_history_and_clean_checkout(
        self,
    ) -> None:
        profile = {"profile": "fixture"}
        repository = Path("fixture-site")
        with (
            patch.object(PROJECTION, "verify_successor_history") as history,
            patch.object(PROJECTION, "require_clean_checkout") as clean,
            patch.object(PROJECTION, "require_no_ignored_files") as no_ignored,
        ):
            PROJECTION.verify_final_site_state(profile, repository)
        history.assert_called_once_with(
            profile,
            repository,
            require_terminal=True,
        )
        self.assertEqual(
            clean.call_args_list,
            [
                call(repository, "full-migration website"),
                call(PROJECTION.ROOT, "full-migration coordinator"),
            ],
        )
        self.assertEqual(
            no_ignored.call_args_list,
            [
                call(repository, "full-migration website"),
                call(
                    PROJECTION.UPSTREAM,
                    "www-from-model hydration transport",
                    ("assets", "static", "themes/congo"),
                ),
            ],
        )

    def test_terminal_history_has_distinct_preparation_and_final_modes(self) -> None:
        PROJECTION.verify_terminal_history([], 4, require_terminal=False)
        PROJECTION.verify_terminal_history([3], 4, require_terminal=True)
        with self.assertRaisesRegex(
            PROJECTION.ProjectionError,
            "exactly one terminal generated projection commit",
        ):
            PROJECTION.verify_terminal_history([], 4, require_terminal=True)
        for indexes in ([2], [2, 3]):
            with (
                self.subTest(indexes=indexes),
                self.assertRaisesRegex(
                    PROJECTION.ProjectionError,
                    "unique and terminal",
                ),
            ):
                PROJECTION.verify_terminal_history(
                    indexes,
                    4,
                    require_terminal=False,
                )

    def test_snapshot_check_enters_final_site_mode(self) -> None:
        profile = {"profile": "fixture"}
        with (
            patch.object(
                PROJECTION.sys,
                "argv",
                ["con_projection.py", "check-snapshot"],
            ),
            patch.object(PROJECTION, "load_yaml", return_value=profile),
            patch.object(
                PROJECTION,
                "verify_final_site_state",
                side_effect=PROJECTION.ProjectionError("strict marker"),
            ) as final_state,
            patch("builtins.print"),
        ):
            self.assertEqual(PROJECTION.main(), 1)
        final_state.assert_called_once_with(profile)

    def test_static_build_enters_final_site_mode(self) -> None:
        profile = {"profile": "fixture"}
        destination = Path("fixture-site")
        with (
            patch.object(BUILD, "safe_destination", return_value=destination),
            patch.object(BUILD, "load_yaml", return_value=profile),
            patch.object(
                BUILD,
                "verify_final_site_state",
                side_effect=PROJECTION.ProjectionError("strict marker"),
            ) as final_state,
        ):
            with self.assertRaisesRegex(BUILD.BuildError, "strict marker"):
                BUILD.build_site(destination, "http://127.0.0.1:8767/")
        final_state.assert_called_once_with(profile)

    def test_dirty_site_policy_rejects_upstream_owned_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "layouts").mkdir()
            (repository / "layouts" / "upstream.html").write_text(
                "upstream\n", encoding="utf-8"
            )
            subprocess.run(
                ["git", "init", "--initial-branch=main", str(repository)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "add", "."],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "-c",
                    "user.name=Projection Test",
                    "-c",
                    "user.email=projection@example.invalid",
                    "commit",
                    "-m",
                    "test: create fixture",
                ],
                check=True,
                capture_output=True,
            )
            for relative in (
                ".gitmodules",
                "config/con/hugo.yaml",
                "profiles/con/metadata/person.yaml",
            ):
                path = repository / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")
            PROJECTION.verify_site_worktree_isolation(repository)

            (repository / "layouts" / "upstream.html").write_text(
                "downstream edit\n", encoding="utf-8"
            )
            (repository / "content" / "leaked.md").parent.mkdir()
            (repository / "content" / "leaked.md").write_text(
                "leak\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(
                PROJECTION.ProjectionError,
                "dirty or untracked upstream-owned paths",
            ):
                PROJECTION.verify_site_worktree_isolation(repository)

    def test_final_input_policy_rejects_ignored_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(
                ["git", "init", "--initial-branch=main", str(repository)],
                check=True,
                capture_output=True,
            )
            (repository / ".gitignore").write_text(
                "resources/\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(repository), "add", ".gitignore"],
                check=True,
                capture_output=True,
            )
            hidden = repository / "profiles/con/metadata/resources/hidden.yaml"
            hidden.parent.mkdir(parents=True)
            hidden.write_text("schema_type: xyzri:XYZPerson\n", encoding="utf-8")
            with self.assertRaisesRegex(
                PROJECTION.ProjectionError,
                "ignored files",
            ):
                PROJECTION.require_no_ignored_files(repository, "fixture")
            PROJECTION.require_no_ignored_files(
                repository,
                "scoped fixture",
                ("assets",),
            )
            scoped = repository / "assets/resources/hidden.yaml"
            scoped.parent.mkdir(parents=True)
            scoped.write_text("hidden: true\n", encoding="utf-8")
            with self.assertRaisesRegex(
                PROJECTION.ProjectionError,
                "ignored files",
            ):
                PROJECTION.require_no_ignored_files(
                    repository,
                    "scoped fixture",
                    ("assets",),
                )

    def test_successor_history_rejects_merge_parents(self) -> None:
        base = "0" * 40
        first = "1" * 40
        merge = "2" * 40
        other = "3" * 40
        with patch.object(
            PROJECTION,
            "run",
            side_effect=[f"{base}\n", f"{first} {other}\n"],
        ):
            with self.assertRaisesRegex(
                PROJECTION.ProjectionError,
                "linear commit stack",
            ):
                PROJECTION.verify_linear_successor_history(
                    Path("fixture-site"),
                    base,
                    [first, merge],
                )

    def test_native_metadata_and_committed_projection_close_exactly(
        self,
    ) -> None:
        contract = self.projection_contract()
        records = self.source_closure()
        expectations = PROJECTION.validate_record_contract(records, contract)
        observed = PROJECTION.native_value_fingerprint(
            [item.record for item in records]
        )
        self.assertTrue(
            PROJECTION.REQUIRED_NATIVE_TYPES
            <= {schema_type for schema_type, _ in observed},
        )
        self.assertIn(
            (
                "dlthings:DOI",
                PROJECTION.normalized_payload(
                    {
                        "notation": "10.21105/joss.03262",
                        "schema_type": "dlthings:DOI",
                    }
                ),
            ),
            observed,
        )
        self.assertIn(
            (
                "dlthings:ISSN",
                PROJECTION.normalized_payload(
                    {
                        "notation": "2475-9066",
                        "schema_type": "dlthings:ISSN",
                    }
                ),
            ),
            observed,
        )

        qualified = {
            "schema_type": "dlthings:Association",
            "object": "xyzrins:persons/example",
            "roles": ["marcrel:led"],
            "statement": "qualified relationship",
        }
        changed = deepcopy(qualified)
        changed["statement"] = "changed qualifier"
        self.assertNotEqual(
            PROJECTION.native_value_fingerprint(qualified),
            PROJECTION.native_value_fingerprint(changed),
        )

        # The accepted slice remains a representative semantic smoke fixture,
        # not the production validator's complete PID/edge/page inventory.
        self.assertTrue(
            {
                "xyzrins:.",
                "ror:04tfhh831",
                "xyzrins:persons/yaroslav-halchenko",
                "xyzrins:projects/datalad",
                "xyzrins:publications/datalad-joss-2021",
                "xyzrins:instruments/datalad",
            }
            <= expectations.canonical_pids
        )
        self.assertTrue(
            {
                "marcrel:led",
                "marcrel:aut",
                "obo:IAO_0000010",
                "bibo:AcademicArticle",
            }
            <= expectations.reference_pids
        )
        self.assertIn(
            (
                "xyzrins:publications/datalad-joss-2021",
                "xyzrins:projects/datalad",
            ),
            expectations.graph_edges,
        )
        self.assertIn(
            "persons/yaroslav-halchenko",
            expectations.entity_routes,
        )

        by_pid = {item.record["pid"]: item.record for item in records}
        self.assertEqual(
            by_pid["xyzrins:projects/datalad"]["part_of"],
            ["xyzrins:."],
        )
        publication = by_pid["xyzrins:publications/datalad-joss-2021"]
        self.assertFalse(
            any(
                str(identifier.get("notation", "")).startswith("https://doi.org/")
                for identifier in publication.get("identifiers", [])
                if isinstance(identifier, dict)
            )
        )

        PROJECTION.verify_manifest(PROJECTION.COMMITTED)
        snapshot = [
            json.loads(line)
            for line in (PROJECTION.COMMITTED / "records.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
        report = PROJECTION.validate_projection(
            snapshot, PROJECTION.COMMITTED, expectations
        )
        self.assertEqual(report["graph_nodes"], len(expectations.graph_node_pids))
        self.assertEqual(report["graph_edges"], len(expectations.graph_edges))
        self.assertEqual(report["pages"], len(expectations.markdown_pages))

    def test_source_inventory_expands_pages_and_graph_without_code_edits(
        self,
    ) -> None:
        contract = self.projection_contract()
        records = deepcopy(self.source_closure())
        homepage = next(item for item in records if item.record["pid"] == "xyzrins:.")
        homepage.record["associated_with"].append(
            {
                "object": "xyzrins:persons/example-person",
                "schema_type": "dlthings:Association",
            }
        )
        records.append(
            PROJECTION.SourceRecord(
                class_name="XYZPerson",
                record={
                    "pid": "xyzrins:persons/example-person",
                    "schema_type": "xyzri:XYZPerson",
                    "given_name": "Example",
                    "family_name": "Person",
                    "display_label": "Example Person",
                },
                path=contract.canonical_root / "XYZPerson" / "example-person.yaml",
                category="canonical",
            )
        )
        expectations = PROJECTION.validate_record_contract(records, contract)
        self.assertIn(
            "persons/example-person/_index.md",
            expectations.markdown_pages,
        )
        self.assertIn(
            ("xyzrins:.", "xyzrins:persons/example-person"),
            expectations.graph_edges,
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for page in expectations.markdown_pages:
                path = output / "content" / page
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("---\n---\n", encoding="utf-8")
            graph_path = output / "static" / "graph.json"
            graph_path.parent.mkdir(parents=True)
            graph_json = json.dumps(
                {
                    "nodes": [
                        {"id": pid} for pid in sorted(expectations.graph_node_pids)
                    ],
                    "edges": [
                        {"source": source, "target": target}
                        for source, target in sorted(expectations.graph_edges)
                    ],
                }
            )
            graph_path.write_text(graph_json, encoding="utf-8")
            (output / "graph.json").write_text(graph_json, encoding="utf-8")
            report = PROJECTION.validate_projection(
                [item.record for item in records], output, expectations
            )
            altered = [deepcopy(item.record) for item in records]
            altered[0]["projection_test_qualifier"] = "changed"
            with self.assertRaisesRegex(
                PROJECTION.ProjectionError,
                "record payload differs from source inventory",
            ):
                PROJECTION.validate_projection(altered, output, expectations)
            for route in expectations.entity_routes:
                route_index = output / route / "index.html"
                route_index.parent.mkdir(parents=True, exist_ok=True)
                route_index.write_text("<!doctype html>\n", encoding="utf-8")
            BUILD.graph_contract(output, expectations)
            self.assertEqual(
                BUILD.entity_routes(output, expectations.entity_routes),
                expectations.entity_routes,
            )
        self.assertEqual(report["canonical_records"], len(expectations.canonical_pids))

    def test_invalid_discriminators_bridges_and_targets_are_rejected(
        self,
    ) -> None:
        contract = self.projection_contract()
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
                    replace_association(child, replacement) for child in value.values()
                )
            if isinstance(value, list):
                return any(replace_association(child, replacement) for child in value)
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
                PROJECTION.validate_record_contract(records, contract)

        dangling = deepcopy(original)
        project = next(
            item
            for item in dangling
            if item.record["pid"] == "xyzrins:projects/datalad"
        )
        project.record["associated_with"][0]["object"] = "xyzrins:missing"
        with self.assertRaisesRegex(PROJECTION.ProjectionError, "dangling"):
            PROJECTION.validate_record_contract(dangling, contract)

        native_reference = deepcopy(original)
        project = next(
            item
            for item in native_reference
            if item.record["pid"] == "xyzrins:projects/datalad"
        )
        project.record["part_of"] = ["marcrel:led"]
        with self.assertRaisesRegex(PROJECTION.ProjectionError, "native graph target"):
            PROJECTION.validate_record_contract(native_reference, contract)

        bridge = deepcopy(original)
        project = next(
            item for item in bridge if item.record["pid"] == "xyzrins:projects/datalad"
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
            PROJECTION.validate_record_contract(bridge, contract)

        unused_reference = deepcopy(original)
        unused_reference.append(
            PROJECTION.SourceRecord(
                class_name="XYZAgentRole",
                record={
                    "pid": "marcrel:unused",
                    "schema_type": "xyzri:XYZAgentRole",
                    "display_label": "Unused",
                },
                path=contract.reference_root / "XYZAgentRole" / "unused.yaml",
                category="reference",
            )
        )
        with self.assertRaisesRegex(
            PROJECTION.ProjectionError, "outside the canonical native-link"
        ):
            PROJECTION.validate_record_contract(unused_reference, contract)

    def test_graph_traversal_must_be_declared_and_match_producer(self) -> None:
        profile = PROJECTION.load_yaml(PROJECTION.PROFILE_PATH)
        specification = PROJECTION.load_yaml(PROJECTION.PROJECTION_SPEC_PATH)
        producer = PROJECTION.site_manifest_path(
            specification["graph"]["producer"],
            "projection.graph.producer",
        )
        specification["graph"].setdefault(
            "node_classes",
            sorted(PROJECTION.producer_mapping(producer, "wanted_node_types")),
        )
        specification["graph"].setdefault(
            "relationship_fields",
            sorted(PROJECTION.producer_mapping(producer, "wanted_edge_types")),
        )
        for field in ("node_classes", "relationship_fields"):
            missing = deepcopy(specification)
            missing["graph"].pop(field, None)
            with self.assertRaisesRegex(
                PROJECTION.ProjectionError,
                f"projection.graph.{field}",
            ):
                PROJECTION.load_projection_contract(profile, missing)

        mismatched = deepcopy(specification)
        mismatched["graph"]["node_classes"] = ["xyzri:XYZPerson"]
        mismatched["graph"]["relationship_fields"] = ["part_of"]
        with self.assertRaisesRegex(PROJECTION.ProjectionError, "pinned producer"):
            PROJECTION.load_projection_contract(profile, mismatched)

    def test_profile_paths_homepage_and_page_policy_are_executable(
        self,
    ) -> None:
        profile = PROJECTION.load_yaml(PROJECTION.PROFILE_PATH)
        specification = PROJECTION.load_yaml(PROJECTION.PROJECTION_SPEC_PATH)
        producer = PROJECTION.site_manifest_path(
            specification["graph"]["producer"],
            "projection.graph.producer",
        )
        specification["graph"].setdefault(
            "node_classes",
            sorted(PROJECTION.producer_mapping(producer, "wanted_node_types")),
        )
        specification["graph"].setdefault(
            "relationship_fields",
            sorted(PROJECTION.producer_mapping(producer, "wanted_edge_types")),
        )

        wrong_path = deepcopy(profile)
        wrong_path["paths"]["canonical_records"] = wrong_path["paths"][
            "reference_records"
        ]
        with self.assertRaisesRegex(
            PROJECTION.ProjectionError, "canonical_records paths disagree"
        ):
            PROJECTION.load_projection_contract(wrong_path, specification)

        wrong_homepage = deepcopy(profile)
        wrong_homepage["identity"]["homepage_pid"] = "xyzrins:projects/not-the-homepage"
        with self.assertRaisesRegex(
            PROJECTION.ProjectionError, "disagree on homepage PID"
        ):
            PROJECTION.load_projection_contract(wrong_homepage, specification)

        no_person_pages = deepcopy(specification)
        no_person_pages["render"]["pages"].pop("xyzri:XYZPerson")
        no_person_pages["render"]["unrendered_classes"].append("xyzri:XYZPerson")
        contract = PROJECTION.load_projection_contract(profile, no_person_pages)
        expectations = PROJECTION.validate_record_contract(
            PROJECTION.source_closure(contract), contract
        )
        self.assertNotIn("persons/yaroslav-halchenko", expectations.entity_routes)
        self.assertIn(
            "xyzrins:persons/yaroslav-halchenko",
            expectations.graph_node_pids,
        )

    def test_runtime_declarations_are_enforced_exactly(self) -> None:
        profile = PROJECTION.load_yaml(PROJECTION.PROFILE_PATH)
        specification = PROJECTION.load_yaml(PROJECTION.PROJECTION_SPEC_PATH)
        cases = (
            (
                "profile.schema.path",
                lambda candidate_profile, _: candidate_profile["schema"].__setitem__(
                    "path", "src/demo-research-information/resolved.yaml"
                ),
            ),
            (
                "profile.paths.qri_snapshot",
                lambda candidate_profile, _: candidate_profile["paths"].__setitem__(
                    "qri_snapshot", "profiles/con/projection/wrong.jsonl"
                ),
            ),
            (
                "projection.snapshot.records",
                lambda _, candidate: candidate["snapshot"].__setitem__(
                    "records", "profiles/con/projection/wrong.jsonl"
                ),
            ),
            (
                "projection.snapshot.format",
                lambda _, candidate: candidate["snapshot"].__setitem__(
                    "format", "yaml"
                ),
            ),
            (
                "projection.snapshot.sort_key",
                lambda _, candidate: candidate["snapshot"].__setitem__(
                    "sort_key", ["pid"]
                ),
            ),
            (
                "projection.render.engine",
                lambda _, candidate: candidate["render"].__setitem__(
                    "engine", "custom"
                ),
            ),
            (
                "projection.render.content_root",
                lambda _, candidate: candidate["render"].__setitem__(
                    "content_root", "profiles/con/projection/wrong-content"
                ),
            ),
            (
                "projection.graph.output",
                lambda _, candidate: candidate["graph"].__setitem__(
                    "output", "profiles/con/projection/wrong-graph.json"
                ),
            ),
            (
                "projection.digest.algorithm",
                lambda _, candidate: candidate["digest"].__setitem__(
                    "algorithm", "sha512"
                ),
            ),
            (
                "projection.digest.output",
                lambda _, candidate: candidate["digest"].__setitem__(
                    "output", "profiles/con/projection/wrong-digest"
                ),
            ),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                candidate_profile = deepcopy(profile)
                candidate_specification = deepcopy(specification)
                mutate(candidate_profile, candidate_specification)
                with self.assertRaisesRegex(
                    PROJECTION.ProjectionError,
                    label.replace(".", r"\."),
                ):
                    PROJECTION.load_projection_contract(
                        candidate_profile, candidate_specification
                    )

    def test_all_pinned_upstream_page_classes_have_executable_pipelines(
        self,
    ) -> None:
        profile = PROJECTION.load_yaml(PROJECTION.PROFILE_PATH)
        specification = PROJECTION.load_yaml(PROJECTION.PROJECTION_SPEC_PATH)
        specification["render"]["pages"].update(
            {
                "xyzri:XYZDataset": "page_templates/dataset.md.j2",
                "xyzri:XYZObjective": "page_templates/objective.md.j2",
                "xyzri:XYZTopic": "page_templates/topic.md.j2",
            }
        )
        contract = PROJECTION.load_projection_contract(profile, specification)
        pages, homepage = PROJECTION.upstream_qri_pipelines(contract)
        self.assertEqual(
            set(pages),
            {
                "xyzri:XYZDataset",
                "xyzri:XYZInstrument",
                "xyzri:XYZObjective",
                "xyzri:XYZPerson",
                "xyzri:XYZProject",
                "xyzri:XYZPublication",
                "xyzri:XYZTopic",
            },
        )
        self.assertEqual(
            pages["xyzri:XYZObjective"],
            [
                ["qri", "list", "--class", "xyzri:XYZObjective"],
                [
                    "qri",
                    "inline-records",
                    "-p",
                    "part_of",
                    "-c",
                    "con-public",
                ],
                [
                    "qri",
                    "inline-records",
                    "-p",
                    "depends_on",
                    "-c",
                    "con-public",
                ],
            ],
        )
        self.assertEqual(
            pages["xyzri:XYZTopic"][-1],
            [
                "qri",
                "inline-records",
                "-p",
                "part_of",
                "-c",
                "con-public",
            ],
        )
        self.assertIn("characterized_by", pages["xyzri:XYZDataset"][-1])
        self.assertEqual(homepage[0], ["qri", "list", "--pid", "xyzrins:."])
        self.assertTrue(all("con-public" in command for command in homepage[1:]))

    def test_projection_digest_scope_is_metadata_only(self) -> None:
        specification = PROJECTION.load_yaml(PROJECTION.PROJECTION_SPEC_PATH)
        specification["digest"]["scope"] = [
            "profiles/con/profile.yaml",
            "profiles/con/projection.yaml",
            "profiles/con/metadata",
            "upstream:page_templates",
            "upstream:code/pool2graph.py",
            "upstream:.forgejo/workflows/update-from-pool.yaml",
            (
                "parent:submodules/things-schemas/src/"
                "demo-research-information/unreleased.yaml"
            ),
            "parent:tools/con_projection.py",
            "component-commit-pins",
            "projection-runtime-pins",
        ]
        labels = {label for label, _ in PROJECTION.input_files(specification)}
        self.assertIn("parent/tools/con_projection.py", labels)
        self.assertIn("upstream/code/pool2graph.py", labels)
        self.assertIn(
            "upstream/.forgejo/workflows/update-from-pool.yaml",
            labels,
        )
        self.assertTrue(
            any(label.startswith("site/profiles/con/metadata/") for label in labels)
        )
        self.assertFalse(any("editorial" in label for label in labels))
        self.assertFalse(any("assets" in label for label in labels))
        self.assertFalse(any("build_con_site" in label for label in labels))

        runtime_pins = dict(PROJECTION.projection_runtime_pins())
        self.assertEqual(runtime_pins["linkml"], "==1.11.1")
        self.assertEqual(runtime_pins["linkml-runtime"], "==1.11.1")
        self.assertEqual(runtime_pins["pydantic"], "==2.13.4")
        self.assertEqual(runtime_pins["rdflib"], "==7.6.0")
        self.assertEqual(runtime_pins["packaging"], "==26.3")
        self.assertEqual(
            runtime_pins["local:dump-things-service"],
            "path=submodules/dump-things-service",
        )
        self.assertEqual(
            runtime_pins["override:dump-things-pyclient"],
            "path=submodules/dump-things-pyclient",
        )
        runtime_records = PROJECTION.projection_runtime_lock_records()
        runtime_labels = {label for label, _ in runtime_records}
        self.assertTrue(
            any(":pypi:pydantic-core@" in label for label in runtime_labels)
        )
        self.assertFalse(
            any(
                excluded in label
                for label in runtime_labels
                for excluded in (
                    ":conda:git-annex@",
                    ":conda:hugo@",
                    ":conda:libuv@",
                    ":conda:nodejs@",
                    ":pypi:pre-commit@",
                    ":pypi:snapper-fmt@",
                )
            )
        )
        lock_digest = PROJECTION.projection_runtime_lock_digest()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with (
                patch.object(PROJECTION, "input_files", return_value=[]),
                patch.object(PROJECTION, "projection_component_pins", return_value=[]),
                patch.object(PROJECTION, "projection_runtime_pins", return_value=[]),
            ):
                manifest = PROJECTION.projection_manifest(output)
        self.assertIn(
            f"{lock_digest}  pin:runtime-lock:projection-closure",
            manifest,
        )
        first_label, first_digest = runtime_records[0]
        self.assertIn(
            f"{first_digest}  pin:runtime-resolved:{first_label}",
            manifest,
        )

        projection_components = dict(PROJECTION.projection_component_pins())
        assembly_components = dict(PROJECTION.declared_component_pins())
        self.assertEqual(
            set(projection_components),
            {
                "dump-things-pyclient",
                "dump-things-service",
                "query-things",
                "things-schemas",
            },
        )
        self.assertIn("congo", assembly_components)
        self.assertIn("things-graph-renderer", assembly_components)
        self.assertNotIn("congo", projection_components)
        self.assertNotIn("things-graph-renderer", projection_components)

    def test_projection_local_runtime_paths_and_markers_fail_closed(self) -> None:
        config = PROJECTION.tomllib.loads(
            (ROOT / "pixi.toml").read_text(encoding="utf-8")
        )
        pins = PROJECTION.projection_local_runtime_pins(config)
        self.assertEqual(
            pins["local:query-things"],
            "path=submodules/query-things",
        )
        for mutation in ("path", "extras", "override"):
            with self.subTest(mutation=mutation):
                candidate = deepcopy(config)
                if mutation == "path":
                    candidate["pypi-dependencies"]["query-things"]["path"] = (
                        "../alternate-query-things"
                    )
                elif mutation == "extras":
                    candidate["pypi-dependencies"]["dump-things-service"]["extras"] = [
                        "unsafe"
                    ]
                else:
                    candidate["pypi-options"]["dependency-overrides"][
                        "dump-things-pyclient"
                    ]["path"] = "../alternate-client"
                with self.assertRaisesRegex(
                    PROJECTION.ProjectionError,
                    "declared exactly",
                ):
                    PROJECTION.projection_local_runtime_pins(candidate)

        environment = PROJECTION.lock_platform_environment(
            "linux-64",
            "linux-64",
            "3.12.12",
        )
        self.assertEqual(environment["platform_release"], "")
        self.assertEqual(environment["platform_version"], "")
        requirement = PROJECTION.Requirement(
            "example; platform_release == 'host-specific'"
        )
        with self.assertRaisesRegex(
            PROJECTION.ProjectionError,
            "host-specific marker",
        ):
            PROJECTION.require_deterministic_marker(requirement)

        profile = PROJECTION.load_yaml(PROJECTION.PROFILE_PATH)
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)

            def profile_bytes(candidate: dict[str, object]) -> bytes:
                path = directory_path / "profile.yaml"
                path.write_text(
                    PROJECTION.yaml.safe_dump(candidate, sort_keys=False),
                    encoding="utf-8",
                )
                return PROJECTION.projection_profile_digest_bytes(path)

            baseline_profile = profile_bytes(profile)
            irrelevant_profile = deepcopy(profile)
            irrelevant_profile["components"]["congo"]["commit"] = "0" * 40
            irrelevant_profile["components"]["graph"]["commit"] = "1" * 40
            self.assertEqual(profile_bytes(irrelevant_profile), baseline_profile)
            relevant_profile = deepcopy(profile)
            relevant_profile["identity"]["homepage_pid"] = "xyzrins:changed"
            self.assertNotEqual(profile_bytes(relevant_profile), baseline_profile)

    def test_projection_lock_closure_ignores_unrelated_runtime_changes(self) -> None:
        lock_path = ROOT / "pixi.lock"
        document = PROJECTION.yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        baseline = PROJECTION.projection_runtime_lock_digest(lock_path)

        def changed_digest(
            package_name: str | None = None,
            conda_fragment: str | None = None,
        ) -> str:
            candidate = deepcopy(document)
            matches = [
                package
                for package in candidate["packages"]
                if (package_name is not None and package.get("name") == package_name)
                or (
                    conda_fragment is not None
                    and conda_fragment in str(package.get("conda", ""))
                )
            ]
            self.assertTrue(matches)
            matches[0]["sha256"] = "0" * 64
            with tempfile.TemporaryDirectory() as directory:
                candidate_path = Path(directory) / "pixi.lock"
                candidate_path.write_text(
                    PROJECTION.yaml.safe_dump(candidate, sort_keys=False),
                    encoding="utf-8",
                )
                return PROJECTION.projection_runtime_lock_digest(candidate_path)

        for package_name, conda_fragment in (
            ("snapper-fmt", None),
            (None, "/hugo-"),
            (None, "/libuv-"),
        ):
            with self.subTest(irrelevant_package=package_name or conda_fragment):
                self.assertEqual(
                    changed_digest(package_name, conda_fragment),
                    baseline,
                )
        for package_name in ("pydantic", "markupsafe"):
            with self.subTest(relevant_package=package_name):
                self.assertNotEqual(changed_digest(package_name), baseline)

    def test_source_and_digest_symlink_escapes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = root / "records"
            class_root = records / "XYZPerson"
            class_root.mkdir(parents=True)
            outside_record = root / "outside.yaml"
            outside_record.write_text(
                "pid: xyzrins:persons/outside\nschema_type: xyzri:XYZPerson\n",
                encoding="utf-8",
            )
            (class_root / "escaped.yaml").symlink_to(outside_record)
            with self.assertRaisesRegex(
                PROJECTION.ProjectionError,
                "resolves outside",
            ):
                PROJECTION.source_records(records, "canonical")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site"
            metadata = site / "profiles" / "con" / "metadata"
            metadata.mkdir(parents=True)
            outside = root / "outside.yaml"
            outside.write_text("outside: true\n", encoding="utf-8")
            (metadata / "escaped.yaml").symlink_to(outside)
            specification = {
                "digest": {
                    "scope": [
                        "profiles/con/metadata",
                        "component-commit-pins",
                        "projection-runtime-pins",
                    ]
                }
            }
            with (
                patch.object(PROJECTION, "SITE", site.resolve()),
                self.assertRaisesRegex(
                    PROJECTION.ProjectionError,
                    "resolves outside",
                ),
            ):
                PROJECTION.input_files(specification)

    def test_portrait_remains_an_annex_pointer_and_snapshot_has_no_assets(
        self,
    ) -> None:
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

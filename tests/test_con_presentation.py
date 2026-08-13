from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_con_site as BUILD  # noqa: E402
import con_projection as PROJECTION  # noqa: E402


class CONPresentationTests(unittest.TestCase):
    def records(self) -> tuple[list[PROJECTION.SourceRecord], str]:
        contract = PROJECTION.load_projection_contract()
        return PROJECTION.source_closure(contract), contract.homepage_pid

    def test_contract_exactly_covers_people_projects_routes_and_menus(self) -> None:
        records, homepage = self.records()
        presentation = BUILD.validate_presentation_contract(records, homepage)
        self.assertEqual(len(presentation.people), 33)
        self.assertEqual(len(presentation.projects), 23)
        self.assertEqual(
            presentation.editorial_routes,
            frozenset(
                {
                    "about",
                    "contact",
                    "engage",
                    "explore",
                    "instruments",
                    "persons",
                    "projects",
                    "publications",
                    "support",
                    "whoweare",
                }
            ),
        )
        self.assertEqual(
            presentation.editorial_aliases,
            frozenset(
                {
                    "engage.html",
                    "projects.html",
                    "support.html",
                    "whoweare.html",
                }
            ),
        )
        self.assertEqual(
            BUILD.declared_taxonomy_routes(),
            frozenset(
                {
                    "datasets",
                    "instruments",
                    "objectives",
                    "persons",
                    "projects",
                    "publications",
                    "tags",
                    "topics",
                }
            ),
        )

    def test_duplicate_person_is_rejected(self) -> None:
        records, homepage = self.records()
        presentation = deepcopy(PROJECTION.load_yaml(BUILD.PRESENTATION))
        first = presentation["people"]["groups"][0]["members"][0]
        presentation["people"]["groups"][1]["members"].append(first)
        original_load = BUILD.load_yaml

        def load(path: Path):
            if path == BUILD.PRESENTATION:
                return presentation
            return original_load(path)

        with mock.patch.object(BUILD, "load_yaml", side_effect=load):
            with self.assertRaisesRegex(BUILD.BuildError, "not unique"):
                BUILD.validate_presentation_contract(records, homepage)

    def test_person_group_boundary_is_executable(self) -> None:
        records, homepage = self.records()
        presentation = deepcopy(PROJECTION.load_yaml(BUILD.PRESENTATION))
        groups = presentation["people"]["groups"]
        boundary_member = groups[0]["members"].pop()
        groups[1]["members"].insert(0, boundary_member)
        original_load = BUILD.load_yaml

        def load(path: Path):
            if path == BUILD.PRESENTATION:
                return presentation
            return original_load(path)

        with mock.patch.object(BUILD, "load_yaml", side_effect=load):
            with self.assertRaisesRegex(BUILD.BuildError, "groups/order"):
                BUILD.validate_presentation_contract(records, homepage)

    def test_project_category_heading_is_executable(self) -> None:
        records, homepage = self.records()
        presentation = deepcopy(PROJECTION.load_yaml(BUILD.PRESENTATION))
        presentation["projects"]["categories"][0]["name"] = "Core software"
        original_load = BUILD.load_yaml

        def load(path: Path):
            if path == BUILD.PRESENTATION:
                return presentation
            return original_load(path)

        with mock.patch.object(BUILD, "load_yaml", side_effect=load):
            with self.assertRaisesRegex(BUILD.BuildError, "categories/order"):
                BUILD.validate_presentation_contract(records, homepage)

    def test_markdown_order_is_executable(self) -> None:
        records, homepage = self.records()
        presentation = deepcopy(PROJECTION.load_yaml(BUILD.PRESENTATION))
        members = presentation["people"]["groups"][0]["members"]
        members[0], members[1] = members[1], members[0]
        original_load = BUILD.load_yaml

        def load(path: Path):
            if path == BUILD.PRESENTATION:
                return presentation
            return original_load(path)

        with mock.patch.object(BUILD, "load_yaml", side_effect=load):
            with self.assertRaisesRegex(BUILD.BuildError, "editorial links"):
                BUILD.validate_presentation_contract(records, homepage)

    def test_every_editorial_markdown_source_must_be_declared(self) -> None:
        records, homepage = self.records()
        presentation = deepcopy(PROJECTION.load_yaml(BUILD.PRESENTATION))
        presentation["editorial"]["routes"] = [
            route
            for route in presentation["editorial"]["routes"]
            if route["path"] != "/contact/"
        ]
        original_load = BUILD.load_yaml

        def load(path: Path):
            if path == BUILD.PRESENTATION:
                return presentation
            return original_load(path)

        with mock.patch.object(BUILD, "load_yaml", side_effect=load):
            with self.assertRaisesRegex(BUILD.BuildError, "source closure"):
                BUILD.validate_presentation_contract(records, homepage)

    def test_published_html_routes_fail_closed(self) -> None:
        entity_routes = {"persons/example"}
        editorial_routes = {"about", "persons"}
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / "index.html").write_text("home", encoding="utf-8")
            for route in entity_routes | editorial_routes:
                output = site / route / "index.html"
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(route, encoding="utf-8")

            BUILD.verify_published_route_closure(site, entity_routes, editorial_routes)

            unexpected = site / "draft" / "index.html"
            unexpected.parent.mkdir()
            unexpected.write_text("draft", encoding="utf-8")
            with self.assertRaisesRegex(BUILD.BuildError, "undeclared=.*draft"):
                BUILD.verify_published_route_closure(
                    site, entity_routes, editorial_routes
                )

            unexpected.unlink()
            alias = site / "unreviewed.html"
            alias.write_text("alias", encoding="utf-8")
            with self.assertRaisesRegex(
                BUILD.BuildError, "undeclared=.*unreviewed.html"
            ):
                BUILD.verify_published_route_closure(
                    site, entity_routes, editorial_routes
                )

            alias.unlink()
            (site / "persons" / "example" / "index.html").unlink()
            with self.assertRaisesRegex(BUILD.BuildError, "missing=.*persons/example"):
                BUILD.verify_published_route_closure(
                    site, entity_routes, editorial_routes
                )

    def test_menu_weight_drift_is_rejected(self) -> None:
        records, homepage = self.records()
        menu = BUILD.MENU_CONFIG.read_text(encoding="utf-8").replace(
            "weight = 10", "weight = 11", 1
        )
        with tempfile.TemporaryDirectory() as directory:
            menu_path = Path(directory) / "menus.en.toml"
            menu_path.write_text(menu, encoding="utf-8")
            with mock.patch.object(BUILD, "MENU_CONFIG", menu_path):
                with self.assertRaisesRegex(BUILD.BuildError, "menus|menu"):
                    BUILD.validate_presentation_contract(records, homepage)


if __name__ == "__main__":
    unittest.main()

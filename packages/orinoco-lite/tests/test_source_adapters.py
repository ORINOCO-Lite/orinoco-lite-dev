from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

import yaml

from orinoco_lite.source_adapters import curation, review
from orinoco_lite.source_adapters.zotero import candidates, metadata_adapter


class PackagedSourceAdapterTests(unittest.TestCase):
    def write_source(self, root: Path, source: dict[str, object]) -> Path:
        directory = root / "site-specific/sources" / str(source["id"])
        directory.mkdir(parents=True)
        path = directory / "source.yaml"
        path.write_text(yaml.safe_dump({"contract_version": 1, **source}))
        return path

    def test_builtin_modules_do_not_require_copied_downstream_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = {
                "id": "zotero",
                "adapter": "orinoco_lite.source_adapters.zotero.metadata_adapter",
                "candidate_provider": "orinoco_lite.source_adapters.zotero.candidates",
                "provenance_identity": "https://example.invalid/agents/zotero",
            }
            self.write_source(root, source)
            self.assertIs(metadata_adapter, review.load_adapter(root, source))
            self.assertIs(candidates, curation._load_provider(root, "zotero"))
            self.assertFalse((root / ".orinoco-lite").exists())

    def test_site_provider_loads_from_the_explicit_trusted_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = root / "extensions/source-adapters/example/candidates.py"
            provider.parent.mkdir(parents=True)
            provider.write_text('ORIGIN = "trusted checkout"\n')
            self.write_source(
                root,
                {
                    "id": "example",
                    "adapter": "extensions/source-adapters/example/adapter.py",
                    "candidate_provider": provider.relative_to(root).as_posix(),
                },
            )
            self.assertEqual(
                "trusted checkout", curation._load_provider(root, "example").ORIGIN
            )

    def test_cli_resolves_policy_relative_to_the_selected_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(
                root,
                {
                    "id": "zotero",
                    "adapter": "orinoco_lite.source_adapters.zotero.metadata_adapter",
                    "provenance_identity": "https://example.invalid/agents/zotero",
                },
            )
            output = StringIO()
            with redirect_stdout(output):
                result = review.main(
                    [
                        "--root", str(root), "resolve-provenance-identity",
                        "--adapter", "zotero",
                    ]
                )
            self.assertEqual(0, result)
            self.assertEqual(
                "https://example.invalid/agents/zotero\n", output.getvalue()
            )

    def test_source_repository_is_a_reviewed_github_coordinate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.write_source(
                root,
                {
                    "id": "example",
                    "adapter": "extensions/source-adapters/example/adapter.py",
                    "repository": "example/source-data",
                },
            )
            self.assertEqual(
                "example/source-data",
                review.resolve_source_repository("example", path.parent.parent),
            )
            source = yaml.safe_load(path.read_text())
            source["repository"] = "https://github.com/example/source-data"
            path.write_text(yaml.safe_dump(source))
            with self.assertRaises(review.MetadataReviewError):
                review.resolve_source_repository("example", path.parent.parent)

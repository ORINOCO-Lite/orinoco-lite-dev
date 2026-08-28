from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import call, patch

from orinoco_lite import cli
from orinoco_lite.errors import ConfigurationError


class TrustedBuildCoordinatesTests(unittest.TestCase):
    def test_build_parser_defaults_repository_from_github_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {"GITHUB_REPOSITORY": "ORINOCO-Lite/example-site"},
            clear=True,
        ):
            args = cli._parser().parse_args(["build"])

        self.assertEqual(args.github_repository, "ORINOCO-Lite/example-site")

    def test_build_forwards_only_the_trusted_repository_coordinate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_root = root / "build"
            workspace = SimpleNamespace(
                base_url="https://example.invalid/site/",
                root=root,
                path=lambda name: build_root if name == "build" else root / name,
            )
            runtime = root / "runtime"
            lock = object()
            args = SimpleNamespace(
                base_url=None,
                destination=None,
                github_repository="ORINOCO-Lite/example-site",
                skip_structural_validation=True,
            )

            with (
                patch.object(cli, "_resolve", return_value=(workspace, lock, runtime)),
                patch.object(cli, "invoke_driver", side_effect=(0, 0)) as invoke,
            ):
                result = cli._build(args)

            self.assertEqual(result, 0)
            self.assertEqual(
                invoke.call_args_list,
                [
                    call("validate", workspace, lock, runtime),
                    call(
                        "build",
                        workspace,
                        lock,
                        runtime,
                        values={
                            "base_url": "https://example.invalid/site/",
                            "destination": str((build_root / "site").resolve()),
                        },
                        environment={
                            "ORINOCO_GITHUB_REPOSITORY": "ORINOCO-Lite/example-site"
                        },
                    ),
                ],
            )

    def test_build_rejects_an_invalid_trusted_repository_before_drivers(self) -> None:
        workspace = SimpleNamespace()
        args = SimpleNamespace(github_repository="not-a-repository")
        with (
            patch.object(
                cli,
                "_resolve",
                return_value=(workspace, object(), Path("runtime")),
            ),
            patch.object(cli, "invoke_driver") as invoke,
            self.assertRaisesRegex(ConfigurationError, "owner/repository"),
        ):
            cli._build(args)

        invoke.assert_not_called()


class DevelopmentEngineVersionTests(unittest.TestCase):
    def test_release_execution_rejects_an_engine_version_mismatch(self) -> None:
        lock = SimpleNamespace(engine_version="0.1.0")
        with (
            patch.object(cli, "__version__", "0.2.0"),
            patch.dict("os.environ", {}, clear=True),
            self.assertRaisesRegex(ConfigurationError, "requires orinoco-lite"),
        ):
            cli._require_engine_version(lock)

    def test_explicit_local_candidate_may_differ_from_release_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "packages/orinoco-lite/src/orinoco_lite"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            lock = SimpleNamespace(engine_version="0.1.0")
            environment = {
                "ORINOCO_UNSAFE_DEVELOPMENT_RUNTIME": "1",
                "ORINOCO_CANDIDATE_ENGINE_ROOT": str(root),
            }
            with (
                patch.object(cli, "__version__", "0.2.0"),
                patch.dict("os.environ", environment, clear=True),
            ):
                cli._require_engine_version(lock)


if __name__ == "__main__":
    unittest.main()

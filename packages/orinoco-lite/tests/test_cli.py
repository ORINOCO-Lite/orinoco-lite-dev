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
            resources = root / "resources"
            args = SimpleNamespace(
                base_url=None,
                build_timestamp="2026-09-08T12:34:56Z",
                destination=None,
                github_repository="ORINOCO-Lite/example-site",
                skip_structural_validation=True,
            )

            with (
                patch.object(cli, "_resolve", return_value=(workspace, resources)),
                patch.object(cli, "invoke_driver", side_effect=(0, 0)) as invoke,
            ):
                result = cli._build(args)

            self.assertEqual(result, 0)
            self.assertEqual(
                invoke.call_args_list,
                [
                    call("validate", workspace, resources),
                    call(
                        "build",
                        workspace,
                        resources,
                        values={
                            "base_url": "https://example.invalid/site/",
                            "destination": str((build_root / "site").resolve()),
                        },
                        environment={
                            "ORINOCO_GITHUB_REPOSITORY": "ORINOCO-Lite/example-site"
                        },
                        extra_arguments=(
                            "--build-timestamp", "2026-09-08T12:34:56Z"
                        ),
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
                return_value=(workspace, Path("resources")),
            ),
            patch.object(cli, "invoke_driver") as invoke,
            self.assertRaisesRegex(ConfigurationError, "owner/repository"),
        ):
            cli._build(args)

        invoke.assert_not_called()



if __name__ == "__main__":
    unittest.main()

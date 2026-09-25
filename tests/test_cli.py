from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import call, patch

import pytest

from orinoco_lite import cli
from orinoco_lite.errors import ConfigurationError


@pytest.mark.parametrize("command", [["build"], ["projection", "update"]])
def test_no_cache_option_is_explicit_and_forwarded(command):
    args = cli._parser().parse_args([*command, "--no-cache"])
    with patch.object(cli, "invoke_driver", return_value=0) as invoke:
        cli._update_projection(args, "workspace", "resources")
    invoke.assert_called_once_with(
        "projection-update", "workspace", "resources", extra_arguments=("--no-cache",),
    )


class TrustedBuildCoordinatesTests(unittest.TestCase):
    def test_build_parser_defaults_repository_from_github_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {"GITHUB_REPOSITORY": "ORINOCO-Lite/example-site"},
            clear=True,
        ):
            args = cli._parser().parse_args(["build"])

        self.assertEqual(args.github_repository, "ORINOCO-Lite/example-site")

    def test_netlify_preview_binds_exact_pull_request(self) -> None:
        commit = "a" * 40
        with patch.dict(
            "os.environ",
            {
                "COMMIT_REF": commit,
                "CONTEXT": "deploy-preview",
                "NETLIFY": "true",
                "REPOSITORY_URL": (
                    "https://github.com/ORINOCO-Lite/example-site.git"
                ),
                "REVIEW_ID": "42",
            },
            clear=True,
        ):
            environment = cli._netlify_preview_environment()

        self.assertEqual(
            environment,
            {
                "ORINOCO_CANDIDATE_CONTENT_COMMIT": commit,
                "ORINOCO_CANDIDATE_PULL_REQUEST": "42",
                "ORINOCO_GITHUB_REPOSITORY": "ORINOCO-Lite/example-site",
                "ORINOCO_UNSAFE_DEVELOPMENT_PACKAGE": "1",
            },
        )

    def test_non_preview_netlify_build_has_no_candidate_target(self) -> None:
        with patch.dict(
            "os.environ",
            {"CONTEXT": "production", "NETLIFY": "true"},
            clear=True,
        ):
            self.assertEqual(cli._netlify_preview_environment(), {})

    def test_netlify_preview_rejects_incomplete_coordinates(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "COMMIT_REF": "main",
                "CONTEXT": "deploy-preview",
                "NETLIFY": "true",
                "REPOSITORY_URL": "https://github.com/ORINOCO-Lite/example-site",
                "REVIEW_ID": "42",
            },
            clear=True,
        ), self.assertRaisesRegex(ConfigurationError, "full Git commit"):
            cli._netlify_preview_environment()

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
            )

            with (
                patch.object(cli, "_resolve", return_value=(workspace, resources)),
                patch.object(cli, "validate_workspace"),
                patch.object(cli, "invoke_driver", side_effect=(0, 0)) as invoke,
            ):
                result = cli._build(args)

            self.assertEqual(result, 0)
            self.assertEqual(
                invoke.call_args_list,
                [
                    call("projection-update", workspace, resources),
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



def test_validate_checks_inputs_without_generating_projection():
    args = cli._parser().parse_args(["validate", "--no-cache"])
    with (
        patch.object(cli, "_workspace", return_value=SimpleNamespace(site_name="Test")),
        patch.object(cli, "validate_workspace", return_value={"records": 1}),
        patch.object(cli, "resolve_resources", return_value="resources"),
        patch.object(cli, "invoke_driver", return_value=0) as invoke,
    ):
        assert cli._validate(args) == 0
    assert invoke.call_count == 1
    assert invoke.call_args.args[0] == "validate"
    assert invoke.call_args.kwargs["extra_arguments"] == ("--no-cache",)


@pytest.mark.parametrize("status", [0, 1])
def test_build_bundle_is_optional_and_only_created_after_success(tmp_path, status):
    workspace = SimpleNamespace(root=tmp_path, base_url="/", path=lambda name: tmp_path / name)
    args = cli._parser().parse_args(["build", "--publication-bundle", "build/publication.bundle"])
    with (
        patch.object(cli, "_resolve", return_value=(workspace, "resources")),
        patch.object(cli, "validate_workspace"),
        patch.object(cli, "invoke_driver", return_value=status),
        patch("orinoco_lite.publication.require_clean_source") as clean,
        patch("orinoco_lite.publication.record_projection", return_value="projection-commit"),
        patch("orinoco_lite.publication.prepare") as prepare,
    ):
        assert cli._build(args) == status
    clean.assert_called_once_with(tmp_path)
    if status == 0:
        prepare.assert_called_once_with(tmp_path, "projection-commit", "build/site", "build/publication.bundle")
    else:
        prepare.assert_not_called()

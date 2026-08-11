from __future__ import annotations

import hashlib
import importlib.util
from io import BytesIO
import os
from pathlib import Path
from pathlib import PurePosixPath
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name: str):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ASSETS = load_tool("con_assets")


PNG = b"\x89PNG\r\n\x1a\nfull-migration-test"
JPEG = b"\xff\xd8\xff\xe0full-migration-test"


def digest(payload: bytes, algorithm: str) -> str:
    return hashlib.new(algorithm, payload).hexdigest()


def git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", repository, *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def canonical_pointer(
    site: Path,
    destination: Path,
    key: str,
    hashdir: PurePosixPath,
) -> str:
    object_path = site / ".git/annex/objects" / Path(*hashdir.parts) / key / key
    return Path(os.path.relpath(object_path, destination.parent)).as_posix()


def manifest() -> dict:
    annex_key = f"MD5E-s{len(JPEG)}--{digest(JPEG, 'md5')}.jpg"
    return {
        "fallback_policy": {
            "mode": "upstream-neutral",
            "person": "meerkat-person",
            "project": "meerkat-project",
            "render_image": True,
        },
        "omissions": {
            "xyzrins:persons/missing": {
                "kind": "portrait",
                "availability": "unavailable",
                "projection_link": None,
                "fallback": "meerkat-person",
                "source_path": "theme/static/img/team/missing.jpg",
                "annex_key": "MD5E-s12--00000000000000000000000000000000.jpg",
                "expected_size": 12,
            },
            "xyzrins:projects/plain": {
                "kind": "logo",
                "availability": "absent-in-source",
                "projection_link": None,
                "fallback": "meerkat-project",
            },
        },
        "assets": {
            "profiles/con/assets/img/brand.png": {
                "source_repository": "https://example.test/site.git",
                "source_commit": "1" * 40,
                "source_path": "theme/static/img/brand.png",
                "availability": "available",
                "storage": "git",
                "media_type": "image/png",
                "mode": "0644",
                "size": len(PNG),
                "sha256": digest(PNG, "sha256"),
                "role": "site-brand",
            },
            "profiles/con/assets/img/person.jpg": {
                "source_repository": "https://example.test/site.git",
                "source_commit": "1" * 40,
                "source_path": "theme/static/img/person.jpg",
                "availability": "available",
                "storage": "git-annex",
                "media_type": "image/jpeg",
                "mode": "0644",
                "size": len(JPEG),
                "md5": digest(JPEG, "md5"),
                "sha256": digest(JPEG, "sha256"),
                "annex_key": annex_key,
                "role": "person-portrait",
                "retrieval": {
                    "remote": "example-read-only",
                    "repository": "https://assets.example.test/dataset/.git/",
                    "object_url": (
                        "https://assets.example.test/dataset/.git/annex/"
                        f"objects/example/{annex_key}/{annex_key}"
                    ),
                    "mode": "read-only",
                },
            },
        },
        "projection_links": {
            "profiles/con/projection/content/persons/example/portrait.jpg": (
                "profiles/con/assets/img/person.jpg"
            ),
        },
        "static_links": {
            "profiles/con/static/favicon.png": ("profiles/con/assets/img/brand.png"),
        },
    }


class CONAssetTests(unittest.TestCase):
    def test_all_declared_assets_hydrate_and_materialize(self) -> None:
        declaration = manifest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site = root / "site"
            cache = root / "cache"
            site.mkdir()
            git(site, "init", "--quiet")
            brand = site / "profiles/con/assets/img/brand.png"
            portrait = site / "profiles/con/assets/img/person.jpg"
            brand.parent.mkdir(parents=True)
            brand.write_bytes(PNG)
            brand.chmod(0o644)
            key = declaration["assets"]["profiles/con/assets/img/person.jpg"][
                "annex_key"
            ]
            hashdir = PurePosixPath("ab/cd")
            portrait.symlink_to(canonical_pointer(site, portrait, key, hashdir))
            git(site, "add", "--all")
            real_os_open = os.open
            with (
                mock.patch.object(ASSETS, "SITE", site),
                mock.patch.object(ASSETS, "CACHE", cache),
                mock.patch.object(
                    ASSETS,
                    "annex_hashdir",
                    return_value=hashdir,
                ),
                mock.patch.object(
                    ASSETS,
                    "urlopen",
                    return_value=BytesIO(JPEG),
                ),
                mock.patch.object(ASSETS, "verify_annex_key") as annex_key,
                mock.patch.object(
                    ASSETS.os,
                    "open",
                    wraps=real_os_open,
                ) as secure_open,
            ):
                files = ASSETS.hydrate_manifest_assets(declaration)
                assembly = root / "assembly"
                materialized = ASSETS.materialize_all_assets(
                    assembly,
                    declaration,
                    files,
                )

            self.assertEqual(set(files), set(declaration["assets"]))
            self.assertEqual(annex_key.call_count, 1)
            temporary_flags = secure_open.call_args.args[1]
            self.assertTrue(temporary_flags & os.O_EXCL)
            self.assertTrue(temporary_flags & os.O_NOFOLLOW)
            self.assertEqual(len(materialized), 4)
            self.assertEqual(
                (
                    assembly
                    / "profiles/con/projection/content/persons/example/portrait.jpg"
                ).read_bytes(),
                JPEG,
            )
            self.assertEqual(
                (assembly / "profiles/con/static/favicon.png").read_bytes(),
                PNG,
            )
            self.assertTrue(
                all(os.stat(path).st_mode & 0o777 == 0o644 for path in materialized)
            )

    def test_manifest_rejects_unsafe_or_incomplete_asset_contracts(self) -> None:
        declaration = manifest()
        bad_mode = {
            **declaration,
            "assets": {
                **declaration["assets"],
                "profiles/con/assets/img/brand.png": {
                    **declaration["assets"]["profiles/con/assets/img/brand.png"],
                    "mode": "0664",
                },
            },
        }
        with self.assertRaisesRegex(ASSETS.AssetError, "mode"):
            ASSETS.asset_specs(bad_mode)

        traversal = {
            **declaration,
            "assets": {
                "profiles/con/assets/../../secret.png": declaration["assets"][
                    "profiles/con/assets/img/brand.png"
                ]
            },
        }
        with self.assertRaisesRegex(ASSETS.AssetError, "normalized"):
            ASSETS.asset_specs(traversal)

        writable = manifest()
        writable["assets"]["profiles/con/assets/img/person.jpg"]["retrieval"][
            "mode"
        ] = "write"
        with self.assertRaisesRegex(ASSETS.AssetError, "read-only"):
            ASSETS.asset_specs(writable)

        outside = manifest()
        outside["assets"]["profiles/con/assets/img/person.jpg"]["retrieval"][
            "object_url"
        ] = "https://elsewhere.example.test/object.jpg"
        with self.assertRaisesRegex(ASSETS.AssetError, "outside"):
            ASSETS.asset_specs(outside)

        missing_provenance = manifest()
        del missing_provenance["assets"]["profiles/con/assets/img/brand.png"][
            "source_commit"
        ]
        with self.assertRaisesRegex(ASSETS.AssetError, "source_commit"):
            ASSETS.asset_specs(missing_provenance)

        broken_fallback = manifest()
        broken_fallback["fallback_policy"]["render_image"] = False
        with self.assertRaisesRegex(ASSETS.AssetError, "fallback_policy"):
            ASSETS.asset_specs(broken_fallback)

        linked_omission = manifest()
        linked_omission["projection_links"][
            "profiles/con/projection/content/persons/missing/portrait.jpg"
        ] = "profiles/con/assets/img/person.jpg"
        with self.assertRaisesRegex(ASSETS.AssetError, "projection link"):
            ASSETS.asset_specs(linked_omission)

    def test_every_repository_and_object_url_rejects_credentials(self) -> None:
        for url in (
            "http://example.test/site.git",
            "https://user@example.test/site.git",
            "https://:secret@example.test/site.git",
            "https://user:secret@example.test/site.git",
        ):
            with self.subTest(source_repository=url):
                declaration = manifest()
                declaration["assets"]["profiles/con/assets/img/brand.png"][
                    "source_repository"
                ] = url
                with self.assertRaisesRegex(ASSETS.AssetError, "credential-free"):
                    ASSETS.asset_specs(declaration)

        for field in ("repository", "object_url"):
            with self.subTest(retrieval_field=field):
                declaration = manifest()
                declaration["assets"]["profiles/con/assets/img/person.jpg"][
                    "retrieval"
                ][field] = "https://:secret@assets.example.test/dataset/.git/"
                with self.assertRaisesRegex(ASSETS.AssetError, "credential-free"):
                    ASSETS.asset_specs(declaration)

        baseline = {
            "website": {
                "annex_metadata_commit": "a" * 40,
                "upstream_repository": "https://user:secret@example.test/site.git",
            }
        }
        with mock.patch.object(ASSETS, "load_yaml", return_value=baseline):
            with self.assertRaisesRegex(ASSETS.AssetError, "credential-free"):
                ASSETS.hydrate_upstream()

        with self.assertRaisesRegex(ASSETS.AssetError, "credential-free"):
            ASSETS.annex_from_url(
                Path("/tmp/example"),
                "unsafe",
                "https://user:secret@example.test/site.git",
                "get",
                action="Unsafe test transport",
            )

    def test_file_verification_checks_digest_mime_and_mode(self) -> None:
        declaration = manifest()
        spec = ASSETS.asset_specs(declaration)["profiles/con/assets/img/brand.png"]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "brand.png"
            path.write_bytes(PNG)
            path.chmod(0o644)
            ASSETS.verify_file(path, spec)

            path.chmod(0o600)
            with self.assertRaisesRegex(ASSETS.AssetError, "mode"):
                ASSETS.verify_file(path, spec)
            path.chmod(0o644)
            path.write_bytes(JPEG)
            with self.assertRaisesRegex(ASSETS.AssetError, "bytes|sha256"):
                ASSETS.verify_file(path, spec)

            wrong_mime = ASSETS.AssetSpec(
                **{
                    **spec.__dict__,
                    "size": len(PNG),
                    "sha256": digest(PNG, "sha256"),
                    "media_type": "image/jpeg",
                }
            )
            path.write_bytes(PNG)
            with self.assertRaisesRegex(ASSETS.AssetError, "media type"):
                ASSETS.verify_file(path, wrong_mime)

    def test_git_index_modes_and_annex_pointer_targets_are_exact(self) -> None:
        declaration = manifest()
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            site.mkdir()
            git(site, "init", "--quiet")
            brand_relative = Path("profiles/con/assets/img/brand.png")
            portrait_relative = Path("profiles/con/assets/img/person.jpg")
            brand = site / brand_relative
            portrait = site / portrait_relative
            brand.parent.mkdir(parents=True)
            brand.write_bytes(PNG)
            brand.chmod(0o644)
            key = declaration["assets"][portrait_relative.as_posix()]["annex_key"]
            hashdir = PurePosixPath("ab/cd")
            expected_pointer = canonical_pointer(site, portrait, key, hashdir)
            portrait.symlink_to(expected_pointer)
            git(site, "add", "--all")

            with (
                mock.patch.object(ASSETS, "SITE", site),
                mock.patch.object(
                    ASSETS,
                    "annex_hashdir",
                    return_value=hashdir,
                ),
            ):
                specs = ASSETS.asset_specs(declaration)
                brand_spec = specs[brand_relative.as_posix()]
                portrait_spec = specs[portrait_relative.as_posix()]
                self.assertIsNone(ASSETS.verify_git_index_contract(brand_spec))
                self.assertEqual(
                    ASSETS.verify_git_index_contract(portrait_spec),
                    expected_pointer,
                )
                ASSETS.verify_annex_pointer(portrait_spec, expected_pointer)

                git(site, "update-index", "--chmod=+x", brand_relative.as_posix())
                with self.assertRaisesRegex(ASSETS.AssetError, "100644"):
                    ASSETS.verify_git_index_contract(brand_spec)
                git(site, "update-index", "--chmod=-x", brand_relative.as_posix())

                portrait.unlink()
                portrait.symlink_to("../../../../../wrong-annex-object")
                with self.assertRaisesRegex(ASSETS.AssetError, "not canonical"):
                    ASSETS.verify_annex_pointer(portrait_spec, expected_pointer)
                git(site, "add", "--", portrait_relative.as_posix())
                with self.assertRaisesRegex(ASSETS.AssetError, "not canonical"):
                    ASSETS.verify_git_index_contract(portrait_spec)

    def test_cache_rejects_symlinks_and_downloads_exclusively(self) -> None:
        spec = ASSETS.asset_specs(manifest())["profiles/con/assets/img/person.jpg"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            outside = root / "outside"
            cache.mkdir()
            outside.mkdir()
            (cache / "profiles").symlink_to(outside, target_is_directory=True)
            with mock.patch.object(ASSETS, "CACHE", cache):
                with self.assertRaisesRegex(ASSETS.AssetError, "ancestor is a symlink"):
                    ASSETS.hydrate_annex_asset(spec)

            safe_cache = root / "safe-cache"
            destination = safe_cache.joinpath(*PurePosixPath(spec.destination).parts)
            destination.parent.mkdir(parents=True)
            outside_file = outside / "payload.jpg"
            outside_file.write_bytes(JPEG)
            destination.symlink_to(outside_file)
            with mock.patch.object(ASSETS, "CACHE", safe_cache):
                with self.assertRaisesRegex(
                    ASSETS.AssetError,
                    "cache destination is a symlink",
                ):
                    ASSETS.hydrate_annex_asset(spec)

            collision = root / "exclusive-download"
            collision.symlink_to(outside_file)
            with self.assertRaisesRegex(ASSETS.AssetError, "exclusive"):
                ASSETS.open_exclusive_download(collision)

    def test_materialization_rejects_symlinked_destination_ancestors(self) -> None:
        spec = ASSETS.asset_specs(manifest())["profiles/con/assets/img/brand.png"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            source.write_bytes(PNG)
            source.chmod(0o644)
            assembly = root / "assembly"
            outside = root / "outside"
            assembly.mkdir()
            outside.mkdir()
            (assembly / "profiles").symlink_to(
                outside,
                target_is_directory=True,
            )
            with self.assertRaisesRegex(ASSETS.AssetError, "ancestor is a symlink"):
                ASSETS.copy_materialized_file(
                    assembly,
                    spec.destination,
                    source,
                    spec,
                )
            self.assertEqual(list(outside.iterdir()), [])

    def test_materialization_replaces_only_the_declared_annex_pointer(self) -> None:
        spec = ASSETS.asset_specs(manifest())["profiles/con/assets/img/person.jpg"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assembly = root / "assembly"
            source = root / "person.jpg"
            source.write_bytes(JPEG)
            destination = assembly / spec.destination
            destination.parent.mkdir(parents=True)
            destination.symlink_to("../../canonical-annex-object")
            with mock.patch.object(
                ASSETS,
                "canonical_annex_pointer_target",
                return_value="../../canonical-annex-object",
            ):
                result = ASSETS.copy_materialized_file(
                    assembly,
                    spec.destination,
                    source,
                    spec,
                )
            self.assertEqual(result.read_bytes(), JPEG)
            self.assertFalse(result.is_symlink())

            result.unlink()
            result.symlink_to("../../different-object")
            with (
                mock.patch.object(
                    ASSETS,
                    "canonical_annex_pointer_target",
                    return_value="../../canonical-annex-object",
                ),
                self.assertRaisesRegex(ASSETS.AssetError, "canonical annex pointer"),
            ):
                ASSETS.copy_materialized_file(
                    assembly,
                    spec.destination,
                    source,
                    spec,
                )

    def test_runtime_and_annex_commands_are_pixi_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline.yaml"
            baseline.write_text(
                "toolchain:\n  git_annex: '10.20260601'\n",
                encoding="utf-8",
            )
            executable = ROOT / ".pixi/envs/default/bin/git-annex"

            def command(arguments, **kwargs):
                del kwargs
                if any("import shutil" in argument for argument in arguments):
                    output = f"{executable}\n"
                else:
                    output = "git-annex version: 10.20260601-gtest\n"
                return mock.Mock(returncode=0, stdout=output, stderr="")

            with (
                mock.patch.object(ASSETS, "BASELINE_MANIFEST", baseline),
                mock.patch.object(ASSETS, "run", side_effect=command) as run,
            ):
                ASSETS.verify_annex_runtime()
            self.assertEqual(run.call_count, 2)
            for call in run.call_args_list:
                self.assertEqual(call.args[0][:2], ["pixi", "run"])

        with mock.patch.object(
            ASSETS,
            "git",
            return_value="/tmp/example.git",
        ):
            command = ASSETS.annex_command(Path("/tmp/example"), "version")
        self.assertEqual(command[:3], ["pixi", "run", "git"])
        self.assertIn(
            f"--work-tree={Path('/tmp/example').resolve()}",
            command,
        )
        self.assertNotIn("core.worktree", " ".join(command))

    def test_annex_payload_verification_supports_md5e_and_sha256e(self) -> None:
        payloads = {
            "MD5E": JPEG,
            "SHA256E": PNG,
        }
        algorithms = {
            "MD5E": "md5",
            "SHA256E": "sha256",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for backend, payload in payloads.items():
                with self.subTest(backend=backend):
                    path = root / f"{backend.lower()}.bin"
                    path.write_bytes(payload)
                    key = (
                        f"{backend}-s{len(payload)}--"
                        f"{digest(payload, algorithms[backend])}.bin"
                    )
                    with mock.patch.object(
                        ASSETS,
                        "run",
                        return_value=mock.Mock(
                            returncode=0,
                            stdout=f"{key}\n",
                            stderr="",
                        ),
                    ):
                        ASSETS.verify_payload_against_annex_key(
                            path,
                            key,
                            label=f"{backend} payload",
                        )
                    path.write_bytes(b"x" * len(payload))
                    with self.assertRaisesRegex(ASSETS.AssetError, "digest"):
                        ASSETS.verify_payload_against_annex_key(
                            path,
                            key,
                            label=f"{backend} payload",
                        )

    def test_upstream_hydration_verifies_all_available_payloads(self) -> None:
        md5_payload = b"a"
        sha_payload = b"b"
        md5_key = f"MD5E-s1--{digest(md5_payload, 'md5')}.txt"
        sha_key = f"SHA256E-s1--{digest(sha_payload, 'sha256')}.txt"
        entries = {
            "assets/md5.txt": md5_key,
            "static/sha.txt": sha_key,
        }
        baseline = {
            "website": {
                "annex_metadata_commit": "a" * 40,
                "upstream_repository": "https://example.test/upstream.git",
            }
        }
        with (
            mock.patch.object(ASSETS, "load_yaml", return_value=baseline),
            mock.patch.object(
                ASSETS,
                "upstream_annex_entries",
                return_value=entries,
            ),
            mock.patch.object(
                ASSETS,
                "annex",
                side_effect=("", md5_key, sha_key),
            ),
            mock.patch.object(
                ASSETS,
                "annex_path_available",
                side_effect=(True, True, True, True),
            ),
            mock.patch.object(
                ASSETS,
                "verify_payload_against_annex_key",
            ) as verify_payload,
        ):
            ASSETS.hydrate_upstream()
        self.assertEqual(
            verify_payload.call_args_list,
            [
                mock.call(
                    ASSETS.UPSTREAM / "assets/md5.txt",
                    md5_key,
                    label="Upstream annex payload assets/md5.txt",
                ),
                mock.call(
                    ASSETS.UPSTREAM / "static/sha.txt",
                    sha_key,
                    label="Upstream annex payload static/sha.txt",
                ),
            ],
        )

    def test_upstream_hydration_removes_inferred_remote_metadata(self) -> None:
        baseline = {
            "website": {
                "annex_metadata_commit": "a" * 40,
                "upstream_repository": "https://example.test/upstream.git",
            }
        }
        key = "MD5E-s1--0cc175b9c0f1b6a831c399e269772661.txt"
        with (
            mock.patch.object(ASSETS, "load_yaml", return_value=baseline),
            mock.patch.object(
                ASSETS,
                "upstream_annex_entries",
                return_value={"assets/example.txt": key},
            ),
            mock.patch.object(
                ASSETS,
                "annex",
                side_effect=("", key),
            ),
            mock.patch.object(
                ASSETS,
                "annex_path_available",
                side_effect=(False, True),
            ),
            mock.patch.object(ASSETS, "temporary_remote_config", return_value=""),
            mock.patch.object(ASSETS, "git"),
            mock.patch.object(ASSETS, "annex_from_url"),
            mock.patch.object(
                ASSETS,
                "remove_temporary_remote_config",
            ) as remove,
            mock.patch.object(
                ASSETS,
                "verify_payload_against_annex_key",
            ) as verify_payload,
        ):
            ASSETS.hydrate_upstream()
        remove.assert_called_once_with(
            ASSETS.UPSTREAM,
            "full-con-migration-upstream",
        )
        verify_payload.assert_called_once_with(
            ASSETS.UPSTREAM / "assets/example.txt",
            key,
            label="Upstream annex payload assets/example.txt",
        )


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from orinoco_lite.errors import IntegrityError
from orinoco_lite.www_from_model import resolve_www_from_model


def _git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def test_fixed_install_uses_packaged_files_without_git(tmp_path):
    source = tmp_path / "resources/www-from-model"
    (source / "page_templates").mkdir(parents=True)
    (source / "themes/congo").mkdir(parents=True)
    (source / "themes/congo/theme.toml").write_text("name = 'Congo'")
    with patch("orinoco_lite.www_from_model.editable_package_checkout", return_value=None), patch(
        "subprocess.run", side_effect=AssertionError("No runtime Git operation allowed"),
    ):
        assert resolve_www_from_model(tmp_path, source.parent) == source
    assert not (tmp_path / ".orinoco-lite").exists()


def test_missing_payload_fails_without_fetching(tmp_path):
    with patch("orinoco_lite.www_from_model.editable_package_checkout", return_value=None):
        with pytest.raises(IntegrityError, match="reinstall"):
            resolve_www_from_model(tmp_path, tmp_path)


def test_editable_uses_actual_nested_working_source(tmp_path):
    source = tmp_path / "submodules/www-from-model"
    source.mkdir(parents=True)
    (source / ".git").write_text("gitdir: fixture")
    (source / "edited").write_text("uncommitted source")
    with patch("orinoco_lite.www_from_model.editable_package_checkout", return_value=tmp_path):
        assert resolve_www_from_model(tmp_path, tmp_path / "missing-resources") == source
    assert (source / "edited").read_text() == "uncommitted source"


def test_build_metadata_uses_committed_source_without_initialized_submodules(tmp_path):
    from orinoco_lite.build_resources import selected_upstream
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Fixture")
    _git(tmp_path, "config", "user.email", "fixture@example.invalid")
    (tmp_path / ".gitmodules").write_text('[submodule "website"]\npath = submodules/www-from-model\nurl = https://example.org/our-www.git\n')
    _git(tmp_path, "add", ".gitmodules")
    _git(tmp_path, "update-index", "--add", "--cacheinfo", "160000", "a" * 40, "submodules/www-from-model")
    _git(tmp_path, "commit", "-qm", "fixture")
    commit = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / ".gitmodules").write_text("uncommitted change")
    _git(tmp_path, "update-index", "--cacheinfo", "160000", "b" * 40, "submodules/www-from-model")
    assert selected_upstream(tmp_path, commit) == {"repository": "https://example.org/our-www.git", "commit": "a" * 40}


def test_distribution_requires_exact_clean_upstream_and_nested_theme(tmp_path):
    from orinoco_lite.build_resources import distribution_upstream
    from orinoco_lite.errors import DriverError

    def init(root):
        root.mkdir(parents=True, exist_ok=True)
        _git(root, 'init', '-q')
        _git(root, 'config', 'user.name', 'Fixture')
        _git(root, 'config', 'user.email', 'fixture@example.invalid')
        (root / 'file').write_text('committed')
        _git(root, 'add', '.')
        _git(root, 'commit', '-qm', 'fixture')
        return _git(root, 'rev-parse', 'HEAD')

    init(tmp_path)
    source = tmp_path / 'submodules/www-from-model'
    init(source)
    theme = source / 'themes/congo'
    theme_commit = init(theme)
    (source / '.gitmodules').write_text('[submodule "theme"]\npath = themes/congo\nurl = https://example.org/theme.git\n')
    _git(source, 'add', '.gitmodules')
    _git(source, 'update-index', '--add', '--cacheinfo', '160000', theme_commit, 'themes/congo')
    _git(source, 'commit', '-qm', 'select theme')
    _git(source, 'submodule', 'init')
    upstream_commit = _git(source, 'rev-parse', 'HEAD')
    (tmp_path / '.gitmodules').write_text('[submodule "source"]\npath = submodules/www-from-model\nurl = https://example.org/www.git\n')
    _git(tmp_path, 'add', '.gitmodules')
    _git(tmp_path, 'update-index', '--add', '--cacheinfo', '160000', upstream_commit, 'submodules/www-from-model')
    _git(tmp_path, 'commit', '-qm', 'select source')
    commit = _git(tmp_path, 'rev-parse', 'HEAD')
    _, selection = distribution_upstream(tmp_path, commit)
    assert selection['commit'] == upstream_commit
    assert selection['dependencies']['themes/congo'] == theme_commit
    (theme / 'file').write_text('dirty nested source')
    with pytest.raises(DriverError, match='working changes'):
        distribution_upstream(tmp_path, commit)
    _git(theme, 'commit', '-qam', 'different theme')
    with pytest.raises(DriverError, match='dependencies at their gitlinks'):
        distribution_upstream(tmp_path, commit)
    _git(source, 'commit', '--allow-empty', '-qm', 'different upstream')
    with pytest.raises(DriverError, match='package gitlink'):
        distribution_upstream(tmp_path, commit)

from pathlib import Path
import subprocess
import tomllib

import pytest

import _build_backend as backend


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


@pytest.fixture
def package(tmp_path, monkeypatch):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.name', 'Build fixture')
    git(tmp_path, 'config', 'user.email', 'fixture@example.invalid')
    git(tmp_path, 'commit', '--allow-empty', '-qm', 'test: dependency revision')
    dependency = git(tmp_path, 'rev-parse', 'HEAD')
    (tmp_path / '.gitmodules').write_text('[submodule "client"]\npath = submodules/client\nurl = https://example.org/client.git\n')
    (tmp_path / 'pyproject.toml').write_text('''[project]
name = "fixture"
dynamic = ["version", "dependencies"]
[dependency-groups]
runtime = ["requests>=2", "client[extra]; python_version >= '3.12'"]
[tool.uv.sources]
client = {path = "submodules/client", editable = true}
''')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'update-index', '--add', '--cacheinfo', f'160000,{dependency},submodules/client')
    git(tmp_path, 'commit', '-qm', 'test: selected dependency')
    monkeypatch.setattr(backend, '_PACKAGE', tmp_path)
    return tmp_path, dependency


def test_metadata_uses_committed_gitlink_and_url_not_index_or_worktree(package):
    root, commit = package
    git(root, 'update-index', '--cacheinfo', f'160000,{git(root, "rev-parse", "HEAD")},submodules/client')
    (root / '.gitmodules').write_text('uncommitted changes')
    assert backend.package_dependencies() == [
        'requests>=2', f'client[extra] @ git+https://example.org/client.git@{commit} ; python_version >= "3.12"',
    ]


def test_archive_metadata_is_self_contained_and_source_is_unchanged(package, monkeypatch):
    root, _ = package
    manifest = root / 'pyproject.toml'
    before = manifest.read_bytes()
    expected = backend.package_dependencies()
    archive = root / 'archive'
    archive.mkdir()
    (archive / 'pyproject.toml').hardlink_to(manifest)
    backend.archive_metadata(archive)
    doc = tomllib.loads((archive / 'pyproject.toml').read_text())
    assert doc['project']['dependencies'] == expected
    assert 'dependencies' not in doc['project']['dynamic']
    assert not doc.get('tool', {}).get('uv', {}).get('sources')
    assert manifest.read_bytes() == before
    monkeypatch.setattr(backend, '_PACKAGE', archive)
    assert backend.package_dependencies() == expected


def test_missing_gitlink_fails_instead_of_selecting_registry_version(package):
    root, _ = package
    manifest = root / 'pyproject.toml'
    manifest.write_text(manifest.read_text().replace('submodules/client', 'untracked/client'))
    with pytest.raises(RuntimeError, match='Cannot resolve committed Python source'):
        backend.package_dependencies()

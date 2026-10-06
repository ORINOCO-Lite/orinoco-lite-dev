from dataclasses import replace
from pathlib import Path
import subprocess

import pytest

from orinoco_lite.annex_media import annex_files, prepare_media, retrieve_and_verify, workspace_annex_files
from orinoco_lite.config import load_workspace
from orinoco_lite.errors import ConfigurationError, DriverError
from orinoco_lite.publication import _clone_inputs
from orinoco_lite.site import _copy_tree
from orinoco_lite.validation import validate_workspace


def git(root, *args):
    return subprocess.check_output(['git', *map(str, args)], cwd=root, text=True).strip()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    for role in ('AUTHOR', 'COMMITTER'):
        monkeypatch.setenv(f'GIT_{role}_NAME', 'Media Test')
        monkeypatch.setenv(f'GIT_{role}_EMAIL', 'media@example.invalid')
    root = tmp_path / 'website'
    root.mkdir()
    git(root, 'init', '-b', 'main')
    site = root / 'site-specific'
    site.mkdir()
    git(site, 'init', '-b', 'main')
    git(site, 'annex', 'init', 'site media')
    for path in ('metadata/records', 'content', 'assets', 'static'):
        (site / path).mkdir(parents=True)
    (root / 'extensions').mkdir()
    (root / 'pyproject.toml').write_text(
        '[tool.orinoco.media]\nannex = true\n'
        '[tool.orinoco.site.identity]\ntitle = "Media test"\n'
        'description = "Media fixture"\nbase_url = "https://example.org/"\n'
    )
    (site / 'content/example.md').write_text('Editorial content stays in Git.\n')
    (site / 'metadata/records/person.yaml').write_text('pid: ex:person\nschema_type: dlthings:Person\nname: Person\n')
    (site / 'static/image.png').write_bytes(b'fixture image bytes')
    git(site, 'annex', 'add', 'static/image.png')
    (site / '.gitattributes').write_text('metadata/** annex.largefiles=nothing\n*.yaml annex.largefiles=nothing\n*.yml annex.largefiles=nothing\n')
    git(site, 'add', 'metadata', 'content', '.gitattributes')
    git(site, 'commit', '-m', 'test: add media and Git metadata')
    (root / '.gitmodules').write_text('[submodule "site-specific"]\npath = site-specific\nurl = https://example.org/metadata.git\n')
    git(root, 'add', '.')
    git(root, 'commit', '-m', 'test: pin site inputs')
    return load_workspace(root)


def test_materializes_bytes_without_changing_inputs(workspace, tmp_path):
    root = workspace.root
    site = workspace.path('site')
    before = git(root, 'rev-parse', 'HEAD'), git(site, 'rev-parse', 'HEAD')
    media = prepare_media(workspace)
    _copy_tree(site / 'static', tmp_path / 'output', media=media)
    assert (tmp_path / 'output/image.png').read_bytes() == b'fixture image bytes'
    assert not (tmp_path / 'output/image.png').is_symlink()
    assert before == (git(root, 'rev-parse', 'HEAD'), git(site, 'rev-parse', 'HEAD'))
    assert git(root, 'status', '--porcelain') == ''


def test_validation_needs_no_payload_and_rejects_annexed_records(workspace):
    site = workspace.path('site')
    git(site, 'annex', 'drop', '--force', 'static/image.png')
    validate_workspace(workspace)
    git(site, 'rm', '--cached', 'metadata/records/person.yaml')
    git(site, 'annex', 'add', '--force-large', 'metadata/records/person.yaml')
    with pytest.raises(ConfigurationError, match='ordinary Git'):
        validate_workspace(workspace)


def test_unavailable_media_stops_materialization(workspace):
    site = workspace.path('site')
    git(site, 'annex', 'drop', '--force', 'static/image.png')
    with pytest.raises(DriverError, match='static/image.png'):
        prepare_media(workspace)


def test_arbitrary_symlink_and_directory_optin_rejected(workspace):
    (workspace.path('site') / 'static/other').symlink_to('/etc/hosts')
    with pytest.raises(ConfigurationError, match='symlinks'):
        validate_workspace(workspace)
    git(workspace.root, 'rm', '--cached', 'site-specific')
    with pytest.raises(ConfigurationError, match='submodule'):
        prepare_media(workspace)


def test_plain_sites_do_not_call_annex(workspace, monkeypatch):
    monkeypatch.setattr('orinoco_lite.annex_media._git', lambda *a: pytest.fail('Annex invoked'))
    assert prepare_media(replace(workspace, annex_media=False)) == {}


def test_publication_clone_retrieves_from_original_checkout(workspace, tmp_path):
    clone = tmp_path / 'publication'
    _clone_inputs(workspace.root, clone, git(workspace.root, 'rev-parse', 'HEAD'))
    site = clone / 'site-specific'
    assert git(site, 'remote', 'get-url', 'origin') == str(workspace.path('site'))
    # Only local files may be used in this test; no upstream retrieval is possible.
    git(site, 'config', 'protocol.http.allow', 'never')
    git(site, 'config', 'protocol.https.allow', 'never')
    paths = retrieve_and_verify(site, annex_files(site))
    assert paths[Path('static/image.png')].read_bytes() == b'fixture image bytes'
    assert git(clone, 'status', '--porcelain') == ''


def test_unlocked_media_is_verified_and_prohibited_inputs_still_rejected(workspace, tmp_path):
    site = workspace.path('site')
    git(site, 'annex', 'unlock', 'static/image.png')
    media = prepare_media(workspace)
    _copy_tree(site / 'static', tmp_path / 'output', media=media)
    assert (tmp_path / 'output/image.png').read_bytes() == b'fixture image bytes'
    git(site, 'rm', '--cached', 'content/example.md')
    git(site, 'annex', 'add', '--force-large', 'content/example.md')
    git(site, 'annex', 'unlock', 'content/example.md')
    with pytest.raises(ConfigurationError, match='content/example.md'):
        workspace_annex_files(workspace)


def test_corrupt_media_is_not_copied(workspace):
    site = workspace.path('site')
    key = git(site, 'annex', 'lookupkey', 'static/image.png')
    location = site / git(site, 'annex', 'contentlocation', key)
    location.chmod(0o600)
    location.write_bytes(b'corrupted bytes')
    with pytest.raises(DriverError, match='static/image.png'):
        prepare_media(workspace)


def test_metadata_save_keeps_yaml_in_git_without_retrieving_media(workspace):
    site = workspace.path('site')
    git(site, 'annex', 'drop', '--force', 'static/image.png')
    record = site / 'metadata/records/person.yaml'
    record.write_text(record.read_text().replace('name: Person', 'name: Updated person'))
    subprocess.run(['datalad', 'save', '-m', 'test: save Git metadata', '--', str(record)],
                   cwd=site, check=True, capture_output=True)
    assert not git(site, 'annex', 'find', '--anything', '--', 'metadata')
    assert not (site / 'static/image.png').exists()
    assert 'Updated person' in git(site, 'show', 'HEAD:metadata/records/person.yaml')


def test_shallow_clone_discovers_annex_storage(workspace, tmp_path, monkeypatch):
    source = workspace.path('site')
    clone = tmp_path / 'shallow'
    subprocess.run(['git', 'clone', '--depth', '1', source.as_uri(), str(clone)], check=True)
    assert not git(clone, 'branch', '-r', '--list', '*/git-annex')
    before = git(clone, 'rev-parse', 'HEAD')
    for role in ('AUTHOR', 'COMMITTER'):
        for field in ('NAME', 'EMAIL'):
            monkeypatch.delenv(f'GIT_{role}_{field}', raising=False)
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', '/dev/null')
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')
    files = annex_files(clone, initialize=True)
    media = retrieve_and_verify(clone, files)
    assert media[Path('static/image.png')].read_bytes() == b'fixture image bytes'
    assert git(clone, 'rev-parse', 'HEAD') == before
    assert git(clone, 'status', '--porcelain') == ''


def test_missing_submodule_repository_never_initializes_parent_annex(workspace, tmp_path):
    (workspace.path('site') / '.git').rename(tmp_path / 'child-git')
    with pytest.raises(ConfigurationError, match='initialized'):
        prepare_media(workspace)
    assert not (workspace.root / '.git/annex').exists()


@pytest.mark.parametrize("failed", [False, True])
def test_netlify_cache_checkout_without_annex(workspace, monkeypatch, tmp_path, failed):
    from orinoco_lite.annex_media import netlify_media_checkout

    site = workspace.path("site")
    monkeypatch.setenv("NETLIFY", "true")
    # This command must never be invoked during the subsequent plain checkout.
    git(site, "config", "filter.annex.process", "missing-annex-for-checkout-test")
    (site / '.gitattributes').write_text('* filter=annex\n')
    try:
        with netlify_media_checkout(workspace):
            if failed:
                raise RuntimeError("build failed")
    except RuntimeError:
        assert failed
    git(site, "checkout-index", "--all", "--force")
    assert prepare_media(workspace)[site / 'static/image.png'].read_bytes() == b'fixture image bytes'


def test_netlify_annexless_does_not_touch_git(monkeypatch):
    from types import SimpleNamespace
    from orinoco_lite import annex_media

    monkeypatch.setenv("NETLIFY", "true")
    monkeypatch.setattr(annex_media, "_git", lambda *args: pytest.fail("annexless build invoked Git cleanup"))
    with annex_media.netlify_media_checkout(SimpleNamespace(annex_media=False)):
        pass


def test_local_build_keeps_annex_filters(workspace, monkeypatch):
    from orinoco_lite.annex_media import netlify_media_checkout

    monkeypatch.delenv("NETLIFY", raising=False)
    site = workspace.path("site")
    before = git(site, 'config', '--local', '--get-regexp', r'^filter\.annex\.')
    with netlify_media_checkout(workspace):
        prepare_media(workspace)
    assert git(site, 'config', '--local', '--get-regexp', r'^filter\.annex\.') == before


def test_hugo_assets_follow_unlocked_development_edits(workspace, tmp_path):
    from orinoco_lite.annex_media import prepare_hugo_assets
    source = workspace.path("site")
    git(source, "annex", "unlock", "static/image.png")
    (source / "static/image.png").write_bytes(b"edited asset")
    mapping = prepare_hugo_assets(source, editable=True)
    _copy_tree(source / "static", tmp_path / "assembly", media=mapping)
    assert (tmp_path / "assembly/image.png").read_bytes() == b"edited asset"
    assert (source / "static/image.png").read_bytes() == b"edited asset"


def test_hugo_assets_require_available_payloads(workspace):
    from orinoco_lite.annex_media import prepare_hugo_assets
    source = workspace.path("site")
    git(source, "annex", "drop", "--force", "static/image.png")
    with pytest.raises(DriverError, match="image.png"):
        prepare_hugo_assets(source)

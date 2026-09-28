"""Downstream TOML configuration and its public validation boundaries."""
import pytest
import tomlkit

from orinoco_lite.config import (
    ConfigurationError, DEFAULT_CURATION_SERVICE, find_workspace_root,
    github_repository, load_workspace,
)

SITE = {"identity": {"title": "Test site", "description": "A fixture.",
                     "base_url": "https://example.invalid/test-site/"}}


def write(root, **settings):
    (root / "pyproject.toml").write_text(tomlkit.dumps({
        "tool": {"orinoco": {"site": SITE, **settings}, "unrelated": {"enabled": True}},
    }))


def test_defaults_and_discovery(tmp_path):
    write(tmp_path)
    nested = tmp_path / "site-specific/metadata/records"
    nested.mkdir(parents=True)
    (nested / "pyproject.toml").write_text('[project]\nname = "independent-tool"\n')
    assert find_workspace_root(nested) == tmp_path
    workspace = load_workspace(tmp_path)
    assert workspace.site_name == "Test site"
    assert workspace.base_url == SITE["identity"]["base_url"]
    assert workspace.path("records") == nested
    assert workspace.curation_service == DEFAULT_CURATION_SERVICE
    assert workspace.repository is None
    assert workspace.environment()["ORINOCO_CONFIG"] == str(tmp_path / "pyproject.toml")


@pytest.mark.parametrize("operations", [{}, {"template_updates": True}, {"template_updates": False}])
def test_operation_choices(tmp_path, operations):
    write(tmp_path, operations=operations)
    assert load_workspace(tmp_path).raw["operations"] == operations


@pytest.mark.parametrize("operations", [[], {"unknown": True}, {"template_updates": "true"}, {"template_updates": 1}])
def test_invalid_operations(tmp_path, operations):
    write(tmp_path, operations=operations)
    with pytest.raises(ConfigurationError, match="tool.orinoco.operations"):
        load_workspace(tmp_path)


@pytest.mark.parametrize("value,expected", [
    ("HTTPS://Review.Example.Test:443/", "https://review.example.test"),
    ("https://Review.Example.Test:8443/", "https://review.example.test:8443"),
    ("http://LOCALHOST:80/", "http://localhost"),
    ("https://[2001:0DB8::1]:443/", "https://[2001:db8::1]"),
])
def test_service_override(tmp_path, value, expected):
    write(tmp_path, service={"url": value}, github={"repository": "owner/site"})
    workspace = load_workspace(tmp_path)
    assert workspace.curation_service == expected
    assert workspace.repository == "owner/site"


@pytest.mark.parametrize("value", ["http://review.example/", "https://review.example/edit/",
    "https://user@review.example/", "https://review.example/?x=1", "https://review.example/#x",
    "https://127.1/", "https://0x7f000001/", "https://faß.example/"])
def test_invalid_service(tmp_path, value):
    write(tmp_path, service={"url": value})
    with pytest.raises(ConfigurationError):
        load_workspace(tmp_path)


@pytest.mark.parametrize("value", ["not-a-repository", "owner/example..site", " owner/site", "owner/site/extra"])
def test_invalid_repository(value):
    with pytest.raises(ConfigurationError, match="owner/repository"):
        github_repository(value, "GitHub repository")


@pytest.mark.parametrize("value", ["r" * 234, "review\x7fname", "review\tname", "📚" * 117])
def test_site_title_matches_browser_contract(tmp_path, value):
    write(tmp_path, site={"identity": {**SITE["identity"], "title": value}})
    with pytest.raises(ConfigurationError, match=r"identity.title"):
        load_workspace(tmp_path)


def test_title_boundary(tmp_path):
    write(tmp_path, site={"identity": {**SITE["identity"], "title": "r" * 233}})
    assert load_workspace(tmp_path).site_name == "r" * 233


@pytest.mark.parametrize("paths", [
    {"records": "../outside"}, {"records": "metadata", "editorial": "metadata"},
    {"build": "elsewhere"}, {"generated": "elsewhere"}, {"site": "elsewhere"},
    {"records": " metadata/records"}, {"records": "metadata/records "},
    {"records": "a" * 1025}, {"records": "metadata/\trecords"}, {"assets": "legacy"},
])
def test_invalid_paths(tmp_path, paths):
    write(tmp_path, paths=paths)
    with pytest.raises(ConfigurationError):
        load_workspace(tmp_path)


def test_normalized_record_root(tmp_path):
    write(tmp_path, paths={"records": "metadata/records/"})
    assert load_workspace(tmp_path).paths["records"] == "metadata/records"


@pytest.mark.parametrize("text", ["[project]\nname='unrelated'", "[tool.orinoco]\noperations=[]", "[tool.orinoco]\na=1\na=2"])
def test_invalid_manifest(tmp_path, text):
    (tmp_path / "pyproject.toml").write_text(text)
    with pytest.raises(ConfigurationError):
        load_workspace(tmp_path)

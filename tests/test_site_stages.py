"""Observable boundaries of import, comparison, assembly and rendering."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from orinoco_lite import dev_site, site
from orinoco_lite.errors import DriverError
from orinoco_lite.site_compare import check_site, compare_trees
from orinoco_lite.site_inputs import import_site_inputs


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def source(tmp_path):
    root = tmp_path / "source"
    write(root / "config/_default/languages.en.toml", 'title="Research"\n[params]\ndescription="Research site"\n')
    write(root / "config/_default/hugo.toml", 'baseURL="https://example.org"\n')
    write(root / "config/_default/params.toml", 'colorScheme="fire"\ndefaultAppearance="light"\n[header]\nlayout="hybrid"\n')
    write(root / "config/_default/menus.en.toml", '[[main]]\nname="Projects"\npageRef="projects"\n')
    write(root / "content/_index.md", "generated homepage")
    write(root / "content/projects/_index.md", "authored section body")
    write(root / "content/projects/one/_index.md", "generated entity")
    write(root / "content/projects/one/logo.svg", "page resource")
    write(root / "content/posts/news/index.md", "authored post")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    return root


def test_import_preserves_authored_sections_resources_and_existing_records(tmp_path):
    upstream = source(tmp_path)
    output = tmp_path / "site-specific"
    write(output / "metadata/records/Thing/one.yaml", "human record")
    write(output / "sources/capture.jsonl", "raw capture")
    write(output / "content/local.md", "local page")
    import_site_inputs(upstream, output)
    assert (output / "content/projects/_index.md").read_text() == "authored section body"
    assert (output / "content/projects/one/logo.svg").read_text() == "page resource"
    assert (output / "content/posts/news/index.md").read_text() == "authored post"
    assert not (output / "content/projects/one/_index.md").exists()
    assert not (output / "content/_index.md").exists()
    assert (output / "metadata/records/Thing/one.yaml").read_text() == "human record"
    assert (output / "sources/capture.jsonl").read_text() == "raw capture"
    assert (output / "content/local.md").read_text() == "local page"


def test_missing_import_resource_leaves_existing_inputs_untouched(tmp_path):
    upstream = source(tmp_path)
    (upstream / "content/projects/one/logo.svg").write_text("/annex/objects/not-present")
    output = tmp_path / "site-specific"
    write(output / "site.yaml", "original")
    with pytest.raises(DriverError, match="Annex pointer"):
        import_site_inputs(upstream, output)
    assert (output / "site.yaml").read_text() == "original"
    assert list(output.iterdir()) == [output / "site.yaml"]


def test_input_comparison_accepts_system_temporary_directory_symlink(tmp_path, monkeypatch):
    from contextlib import contextmanager

    upstream = source(tmp_path)
    output = tmp_path / "site-specific"
    import_site_inputs(upstream, output)
    real_temporary = tmp_path / "real-temporary"
    real_temporary.mkdir()
    temporary_alias = tmp_path / "temporary-alias"
    temporary_alias.symlink_to(real_temporary, target_is_directory=True)

    @contextmanager
    def temporary_directory(**kwargs):
        yield str(temporary_alias)

    monkeypatch.setattr(dev_site.tempfile, "TemporaryDirectory", temporary_directory)
    monkeypatch.setattr(dev_site, "_selection", lambda args: (tmp_path / "resources", upstream))
    args = argparse.Namespace(root=tmp_path, dev_command="inputs", inputs_command="diff",
                              inputs=Path("site-specific"), report=None, mode="isolated",
                              stage="site-input-import")
    assert dev_site.execute(args) == 0


def test_content_diff_keeps_typed_order_duplicates_null_and_raw_changes(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    write(left / "static/graph.json", '{"nodes":[true,1,1],"optional":null}')
    write(right / "static/graph.json", '{"nodes":[1,true]}')
    write(left / "content/page.md", '---\ntitle: Before\ndate: 2026-09-18\n---\nold body\n')
    write(right / "content/page.md", '---\ntitle: After\ndate: 2026-09-18\n---\nnew body\n')
    changes, names = compare_trees(left, right)
    assert ["json", "nodes"] in [item["location"] for item in changes]
    removed = next(item for item in changes if item["location"] == ["json", "optional"])
    assert removed["before_present"] and removed["before"] is None
    assert not removed["after_present"]
    assert ["frontmatter", "title"] in [item["location"] for item in changes]
    assert ["markdown"] in [item["location"] for item in changes]
    assert any(item["location"][0] == "bytes" for item in changes)
    json.dumps(changes)  # Dates must remain portable report values.


def test_html_diff_preserves_unicode_doctype_and_added_removed_routes(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    write(left / "index.html", '<!DOCTYPE html><p>café</p>')
    write(right / "index.html", '<!DOCTYPE html><p>cafe</p>')
    write(left / "gone/index.html", 'old')
    write(right / "new/index.html", 'new')
    changes, _ = compare_trees(left, right, rendered=True)
    assert any(item["location"][:2] == ["html", "events"] for item in changes)
    assert any(item["subject"] == "gone/index.html" and item["change"] == "removed" for item in changes)
    assert any(item["subject"] == "new/index.html" and item["change"] == "added" for item in changes)


def test_site_check_resolves_routes_resources_and_fragments(tmp_path):
    write(tmp_path / "index.html", '<a href="/about/#intro">ok</a><a href="/about/#gone">bad</a><img src="/logo.svg"><a href="https://external.invalid">outside</a>')
    write(tmp_path / "about/index.html", '<h1 id="intro">About</h1><a href="../missing/">bad</a>')
    write(tmp_path / "logo.svg", '<svg/>')
    findings, scope = check_site(tmp_path)
    assert len(findings) == 2
    assert {item["after"]["error"] for item in findings} == {"missing fragment", "missing local target"}
    assert scope["local_links_checked"] == 4


def test_build_consumes_supplied_tree_without_mutating_it(tmp_path, monkeypatch):
    assembly, output = tmp_path / "assembly", tmp_path / "site"
    write(assembly / "content/_index.md", "explicit content")
    workspace = SimpleNamespace(root=tmp_path)
    def run(command, *, cwd):
        source = Path(command[command.index("--source") + 1])
        assert (source / "content/_index.md").read_text() == "explicit content"
        write(source / ".hugo_build.lock", "created by Hugo")
        write(output / "index.html", "built")
        return ""
    monkeypatch.setattr(site, "_run", run)
    site.build_hugo(workspace, tmp_path, assembly, output, "/", flavor="upstream")
    assert not (assembly / ".hugo_build.lock").exists()
    assert (output / "index.html").read_text() == "built"
    with pytest.raises(DriverError, match="already exists"):
        site.build_hugo(workspace, tmp_path, assembly, output, "/", flavor="upstream")


def test_cli_comparison_exit_codes_and_portable_report(tmp_path):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=tmp_path)
    commands = parser.add_subparsers(dest="dev_command")
    dev_site.register(commands)
    write(tmp_path / "before/a.json", '{"value":true}')
    write(tmp_path / "after/a.json", '{"value":1}')
    args = parser.parse_args(["content", "diff", "before", "after", "--report", "report"])
    assert dev_site.execute(args) == 1
    assert (tmp_path / "report/report.json").is_file()
    args = parser.parse_args(["site", "diff", "missing", "after"])
    assert dev_site.execute(args) == 2


def test_diagnostic_lite_build_does_not_read_records_or_bind_apps(tmp_path, monkeypatch):
    assembly, output = tmp_path / "assembly", tmp_path / "site"
    write(assembly / "content/_index.md", "supplied content")
    workspace = SimpleNamespace(root=tmp_path)
    def run(command, *, cwd):
        assert command[0] == "hugo"
        write(output / "index.html", "rendered")
        return ""
    def unexpected(*args, **kwargs):
        raise AssertionError("Diagnostic Hugo build must not bind metadata applications")
    monkeypatch.setattr(site, "_run", run)
    monkeypatch.setattr(site, "bind_editor", unexpected)
    monkeypatch.setattr(site, "bind_review", unexpected)
    result = site.build_hugo(workspace, tmp_path / "resources", assembly, output, "/", flavor="lite")
    assert "application binding excluded" in result["scope"]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["assembly", "site"]


def test_import_preserves_source_identity_settings_without_shadowing_site_yaml(tmp_path):
    import tomllib
    upstream = source(tmp_path)
    with (upstream / "config/_default/params.toml").open("a") as stream:
        stream.write('logo="img/logo.png"\nlogoDark="img/dark.svg"\n[footer]\nshowCopyright=true\n')
    with (upstream / "config/_default/languages.en.toml").open("w") as stream:
        stream.write('title="Research"\ncopyright="Selected source copyright"\n[params]\ndescription="Research site"\n')
    write(upstream / "static/site.webmanifest", '{"name":"Selected","icons":[{"src":"/favicon.png"}]}')
    subprocess.run(["git", "-C", str(upstream), "add", "."], check=True)
    output = tmp_path / "inputs"
    write(output / "overrides/config/params.toml", '[article]\nshowDate=true\n')
    import_site_inputs(upstream, output)
    settings = tomllib.loads((output / "overrides/config/params.toml").read_text())
    assert settings == {"article": {"showDate": True}, "header": {"logo": "img/logo.png", "logoDark": "img/dark.svg"}, "footer": {"showCopyright": True}}
    language = tomllib.loads((output / "overrides/config/languages.en.toml").read_text())
    assert language == {"copyright": "Selected source copyright"}
    assert (output / "static/site.webmanifest").read_bytes() == (upstream / "static/site.webmanifest").read_bytes()


def test_partial_site_config_overrides_preserve_selected_tables_and_replace_arrays(tmp_path):
    import tomllib
    selected, overrides = tmp_path / "selected", tmp_path / "overrides"
    write(selected / "params.toml", 'colorScheme="fire"\n[header]\nlogo=""\nlayout="hybrid"\n[article]\nshowDate=false\n[custom]\nitems=["old","old"]\n')
    write(overrides / "params.toml", '[header]\nlogo="img/logo.png"\n[custom]\nitems=["new"]\n')
    site._overlay_config(overrides, selected)
    settings = tomllib.loads((selected / "params.toml").read_text())
    assert settings["header"] == {"logo": "img/logo.png", "layout": "hybrid"}
    assert settings["colorScheme"] == "fire"
    assert settings["article"] == {"showDate": False}
    assert settings["custom"]["items"] == ["new"]

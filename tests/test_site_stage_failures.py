"""Failed diagnostic outputs cannot later pass a complete comparison."""
from types import SimpleNamespace

import pytest

from orinoco_lite import cli, dev_site
from orinoco_lite.errors import ConfigurationError, DriverError
from orinoco_lite.stage_reports import operation_receipt


@pytest.mark.parametrize("failure", [DriverError("Hugo failed"), KeyboardInterrupt()])
def test_failed_hugo_output_retains_explicit_failure(tmp_path, monkeypatch, failure):
    assembly, output = tmp_path / "assembly", tmp_path / "site"
    assembly.mkdir()
    (assembly / "input.txt").write_text("input")
    monkeypatch.setattr(dev_site, "load_workspace", lambda _: SimpleNamespace(root=tmp_path))

    def fail(*args, **kwargs):
        output.mkdir()
        (output / "index.html").write_text("partial")
        raise failure

    monkeypatch.setattr(dev_site, "build_hugo", fail)
    command = ["--root", str(tmp_path), "dev", "hugo", "build", "upstream", "assembly", "site",
               "--resources", str(tmp_path / "resources"), "--base-url", "/"]
    if isinstance(failure, KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            cli.main(command)
    else:
        assert cli.main(command) == 2
    assert (output / "index.html").read_text() == "partial"
    with pytest.raises(ConfigurationError, match="did not complete"):
        operation_receipt(output)
    assert cli.main(["dev", "site", "diff", str(output), str(output)]) == 2
    assert cli.main(["dev", "site", "check", str(output)]) == 2


def test_existing_hugo_output_is_not_relabelled_as_failed(tmp_path, monkeypatch):
    output = tmp_path / "site"
    output.mkdir()
    (output / "index.html").write_text("existing")
    monkeypatch.setattr(dev_site, "load_workspace", lambda _: SimpleNamespace(root=tmp_path))
    assert cli.main(["--root", str(tmp_path), "dev", "hugo", "build", "upstream", "assembly", "site",
                     "--base-url", "/"]) == 2
    assert operation_receipt(output) is None
    assert (output / "index.html").read_text() == "existing"

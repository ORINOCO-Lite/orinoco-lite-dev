"""Exercise live checkout versions without changing the engineering repository."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import orinoco_lite


def test_checkout_version_tracks_tags_commits_and_dirty_changes(tmp_path):
    package = tmp_path / "src/orinoco_lite"
    package.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "src/orinoco_lite"
    for name in ("__init__.py", "_version.py"):
        shutil.copyfile(source / name, package / name)

    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(tmp_path), *args], text=True
        ).strip()

    def version():
        return json.loads(subprocess.check_output(
            [sys.executable, "-c", "import json; import orinoco_lite; "
             "print(json.dumps(orinoco_lite.__version__))"],
            cwd=tmp_path / "src", text=True,
        ))

    git("init")
    git("config", "user.name", "Version test")
    git("config", "user.email", "version-test@example.invalid")
    git("add", ".")
    git("commit", "-m", "initial")
    git("tag", "v1.2.3")
    assert version() == "1.2.3"

    change = tmp_path / "change.txt"
    change.write_text("first\n")
    git("add", "change.txt")
    git("commit", "-m", "next")
    current = version()
    assert current.startswith("1.2.3+1.g")
    assert git("rev-parse", "HEAD").startswith(current.split(".g")[1])
    change.write_text("second\n")
    assert version() == current + ".dirty"
    git("checkout", "--", "change.txt")
    assert version() == current


def test_cli_reports_the_package_version(capsys):
    import pytest
    from orinoco_lite.cli import _parser

    with pytest.raises(SystemExit) as result:
        _parser().parse_args(["--version"])
    assert result.value.code == 0
    assert capsys.readouterr().out == f"orinoco-lite {orinoco_lite.__version__}\n"

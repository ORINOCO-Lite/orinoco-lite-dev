"""Check setup selection and handoff without downloading or populating a site."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "tools/setup-upstream.sh"


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def repository(root, branch):
    root.mkdir()
    git(root, "init", "-q", "-b", branch)
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "--no-verify", "--allow-empty", "-qm", "test: fixture")
    git(root, "remote", "add", "origin", f"https://example.invalid/{root.name}.git")
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def setup(tmp_path):
    engineering, template = tmp_path / "engineering", tmp_path / "template"
    package_head = repository(engineering, "package-candidate")
    template_head = repository(template, "template-candidate")
    (engineering / "release").mkdir()
    (engineering / "release/package-resources.yaml").write_text("fixture\n")
    commands = tmp_path / "bin"
    commands.mkdir()
    # Replace only external operations. Real Git supplies checkout refs and
    # remote URLs; the log verifies which immutable selections reach setup.
    stub = f'''#!{sys.executable}
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["SETUP_TEST_LOG"], "a") as stream:
    stream.write(json.dumps([name, *args]) + "\\n")
if name == "orinoco-lite":
    if os.environ.get("SETUP_TEST_FAIL"):
        raise SystemExit(2)
    revision = args[args.index("--revision") + 1]
    repository = args[args.index("--repository") + 1]
    if revision == "refs/heads/main":
        revision = ("b" if "template.git" in repository else "a") * 40
    print(revision)
elif name == "pixi" and "copier" in args:
    Path("pixi.toml").write_text('[pypi-dependencies]\\n orinoco-lite = {{git = "https://example.invalid/declared-package.git", rev = "' + "d" * 40 + '"}}\\n')
    Path("pixi.lock").write_text("template lock\\n")
elif name == "datalad" and args[0] == "create":
    Path(args[-1]).mkdir()
'''
    for name in ("orinoco-lite", "datalad", "pixi"):
        executable = commands / name
        executable.write_text(stub)
        executable.chmod(0o755)
    log = tmp_path / "calls.jsonl"
    env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"], SETUP_TEST_LOG=str(log))
    destination = tmp_path / "downstream"

    def run(*args, fail=False):
        result = subprocess.run(["bash", str(SCRIPT), str(destination), "--template", str(template), *args],
                                cwd=engineering, env={**env, **({"SETUP_TEST_FAIL": "1"} if fail else {})},
                                text=True, capture_output=True)
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls
    return run, engineering, template, destination, package_head, template_head


@pytest.mark.parametrize("local", [False, True])
def test_selection_summary_and_immutable_handoff(setup, local):
    run, engineering, template, destination, package_head, template_head = setup
    result, calls = run(*(["--local-heads"] if local else []))
    assert result.returncode == 0, result.stderr
    expected_package = package_head if local else "d" * 40
    expected_template = template_head if local else "b" * 40
    assert f"Revision: {expected_package}" in result.stdout
    assert f"Commit: {expected_template}" in result.stdout
    copier = next(call for call in calls if "copier" in call and "copy" in call)
    assert copier[copier.index("--vcs-ref") + 1] == expected_template
    updates = [call for call in calls if call[:2] == ["datalad", "run"]]
    if local:
        assert updates[0][updates[0].index("--revision") + 1] == package_head
        assert "https://example.invalid/engineering.git" in updates[0]
    else:
        assert not updates
        assert (destination / "pixi.lock").read_text() == "template lock\n"
        assert "https://example.invalid/declared-package.git" in result.stdout
        # Package main is deliberately different from the template package pin.
        assert "a" * 40 not in result.stdout
    assert git(engineering, "rev-parse", "HEAD") == package_head
    assert git(template, "rev-parse", "HEAD") == template_head
    assert git(engineering, "branch", "--show-current") == "package-candidate"
    assert git(template, "branch", "--show-current") == "template-candidate"


@pytest.mark.parametrize("local", [False, True])
@pytest.mark.parametrize("option", ["--template-ref", "--package-revision", "--package-repository"])
def test_explicit_override_retains_other_defaults(setup, local, option):
    run, _, _, _, package_head, template_head = setup
    selected = {"--template-ref": template_head, "--package-revision": "c" * 40,
                "--package-repository": "https://example.invalid/fork.git"}[option]
    result, calls = run(*(["--local-heads"] if local else []), option, selected)
    assert result.returncode == 0, result.stderr
    expected_package = selected if option == "--package-revision" else package_head if local else "d" * 40
    expected_template = template_head if local or option == "--template-ref" else "b" * 40
    assert f"Revision: {expected_package}" in result.stdout
    assert f"Commit: {expected_template}" in result.stdout
    expected_repository = selected if option == "--package-repository" else (
        "https://example.invalid/engineering.git" if local else "https://example.invalid/declared-package.git")
    assert expected_repository in result.stdout


def test_explicit_selections_and_detached_template(setup):
    run, _, template, _, _, template_head = setup
    git(template, "checkout", "--quiet", "--detach")
    result, calls = run("--package-repository", "https://example.invalid/fork.git",
                        "--package-revision", "c" * 40, "--template-ref", template_head)
    assert result.returncode == 0, result.stderr
    assert "Revision: " + "c" * 40 in result.stdout
    assert "detached commit" in result.stdout
    assert "https://example.invalid/fork.git" in result.stdout


def test_unavailable_template_does_not_create_destination(setup):
    run, _, _, destination, _, _ = setup
    result, calls = run(fail=True)
    assert result.returncode == 2
    assert not destination.exists()
    assert all(call[0] == "orinoco-lite" for call in calls)

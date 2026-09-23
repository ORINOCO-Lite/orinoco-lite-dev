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


@pytest.mark.parametrize("latest", [False, True])
def test_selection_summary_and_immutable_handoff(setup, latest):
    run, engineering, template, destination, package_head, template_head = setup
    result, calls = run(*([] if latest else ["--local-heads"]))
    assert result.returncode == 0, result.stderr
    expected_package, expected_template = ("a" * 40, "b" * 40) if latest else (package_head, template_head)
    assert f"Commit: {expected_package}" in result.stdout
    assert f"Commit: {expected_template}" in result.stdout
    assert "https://example.invalid/engineering.git" in result.stdout
    assert "https://example.invalid/template.git" in result.stdout
    if latest:
        assert result.stdout.count("remote branch main") == 2
        assert all(call[-1] == "refs/heads/main" for call in calls[:2])
    else:
        assert "package-candidate" in result.stdout
        assert "template-candidate" in result.stdout
    assert calls[2][:2] == ["datalad", "create"]
    copier = next(call for call in calls if "copier" in call and "copy" in call)
    assert copier[copier.index("--vcs-ref") + 1] == expected_template
    update = next(call for call in calls if call[:2] == ["datalad", "run"])
    assert update[update.index("--revision") + 1] == expected_package
    assert git(engineering, "rev-parse", "HEAD") == package_head
    assert git(template, "rev-parse", "HEAD") == template_head
    assert git(engineering, "branch", "--show-current") == "package-candidate"
    assert git(template, "branch", "--show-current") == "template-candidate"


@pytest.mark.parametrize("local", [False, True])
@pytest.mark.parametrize("option", ["--template-ref", "--package-revision"])
def test_explicit_revision_overrides_only_its_selection(setup, local, option):
    run, _, _, _, package_head, template_head = setup
    selected = template_head if option == "--template-ref" else "c" * 40
    result, calls = run(*(["--local-heads"] if local else []), option, selected)
    assert result.returncode == 0, result.stderr
    expected_package = selected if option == "--package-revision" else package_head if local else "refs/heads/main"
    expected_template = selected if option == "--template-ref" else template_head if local else "refs/heads/main"
    assert calls[0][-1] == expected_package
    assert calls[1][-1] == expected_template


def test_explicit_selections_and_detached_template(setup):
    run, _, template, _, _, template_head = setup
    git(template, "checkout", "--quiet", "--detach")
    result, calls = run("--package-repository", "https://example.invalid/fork.git",
                        "--package-revision", "c" * 40, "--template-ref", template_head)
    assert result.returncode == 0, result.stderr
    assert "explicit revision " + "c" * 40 in result.stdout
    assert "detached commit" in result.stdout
    assert "https://example.invalid/fork.git" in calls[0]


def test_unavailable_remote_main_does_not_create_destination(setup):
    run, _, _, destination, _, _ = setup
    result, calls = run(fail=True)
    assert result.returncode == 2
    assert not destination.exists()
    assert all(call[0] == "orinoco-lite" for call in calls)

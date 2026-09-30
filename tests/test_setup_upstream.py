"""Check setup selection and handoff without downloading or populating a site."""
import fcntl
import json
import os
import pty
import re
import select
import time
import termios
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
    git(template, "branch", "main")
    git(template, "checkout", "--quiet", "main")
    git(template, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "--no-verify", "--allow-empty", "-qm", "test: remote template")
    remote_template = git(template, "rev-parse", "HEAD")
    git(template, "checkout", "--quiet", "template-candidate")
    (engineering / "submodules").mkdir()
    upstream = engineering / "submodules/www-from-model"
    upstream_head = repository(upstream, "main")
    (engineering / ".gitmodules").write_text(
        f'[submodule "submodules/www-from-model"]\n path = submodules/www-from-model\n url = {upstream}\n')
    git(engineering, "add", ".gitmodules")
    git(engineering, "update-index", "--add", "--cacheinfo", f"160000,{upstream_head},submodules/www-from-model")
    git(engineering, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "--no-verify", "-qm", "test: selected upstream")
    git(engineering, "tag", "alternate")
    git(engineering, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "--no-verify", "--allow-empty", "-qm", "test: package candidate")
    package_head = git(engineering, "rev-parse", "HEAD")
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
        revision = "{remote_template}"
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
    env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"], SETUP_TEST_LOG=str(log), COLUMNS="240")
    destination = tmp_path / "downstream"

    def run(*args, fail=False, destination_path=None, interactive=False):
        result = subprocess.run(["bash", str(SCRIPT), str(destination_path or destination), "--template", str(template), *([] if interactive else ["--non-interactive"]), *args],
                                cwd=engineering, env={**env, **({"SETUP_TEST_FAIL": "1"} if fail else {})},
                                text=True, capture_output=True)
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls
    run.env = env
    return run, engineering, template, destination, package_head, template_head


@pytest.mark.parametrize("local", [False, True])
def test_selection_summary_and_immutable_handoff(setup, local):
    run, engineering, template, destination, package_head, template_head = setup
    result, calls = run(*(["--local-heads"] if local else []))
    assert result.returncode == 0, result.stderr
    expected_package = package_head
    expected_template = template_head if local else git(template, "rev-parse", "main")
    assert f"({expected_package[:7]}" in result.stdout
    assert f"({expected_template[:7]}" in result.stdout
    copier = next(call for call in calls if "copier" in call and "copy" in call)
    assert copier[copier.index("--vcs-ref") + 1] == expected_template
    updates = [call for call in calls if call[:2] == ["datalad", "run"]]
    assert updates[0][updates[0].index("--revision") + 1] == package_head
    assert "https://example.invalid/engineering.git" in updates[0]
    assert "d" * 40 not in result.stdout
    assert git(engineering, "rev-parse", "HEAD") == package_head
    assert git(template, "rev-parse", "HEAD") == template_head
    assert git(engineering, "branch", "--show-current") == "package-candidate"
    assert git(template, "branch", "--show-current") == "template-candidate"


@pytest.mark.parametrize("local", [False, True])
@pytest.mark.parametrize("option", ["--template-ref", "--package-revision", "--package-repository"])
def test_explicit_override_retains_other_defaults(setup, local, option):
    run, engineering, template, _, package_head, template_head = setup
    selected = {"--template-ref": template_head, "--package-revision": git(engineering, "rev-parse", "alternate"),
                "--package-repository": "https://example.invalid/fork.git"}[option]
    result, calls = run(*(["--local-heads"] if local else []), option, selected)
    assert result.returncode == 0, result.stderr
    expected_package = selected if option == "--package-revision" else package_head
    expected_template = template_head if local or option == "--template-ref" else git(template, "rev-parse", "main")
    assert f"({expected_package[:7]}" in result.stdout
    assert f"({expected_template[:7]}" in result.stdout
    expected_repository = selected if option == "--package-repository" else "https://example.invalid/engineering.git"
    assert expected_repository in result.stdout


def test_explicit_selections_and_detached_template(setup):
    run, engineering, template, _, _, template_head = setup
    git(template, "checkout", "--quiet", "--detach")
    result, calls = run("--package-repository", "https://example.invalid/fork.git",
                        "--package-revision", git(engineering, "rev-parse", "alternate"), "--template-ref", template_head)
    assert result.returncode == 0, result.stderr
    assert "(" + git(engineering, "rev-parse", "alternate")[:7] in result.stdout
    assert "detached commit" in result.stdout
    assert "https://example.invalid/fork.git" in result.stdout


def test_unavailable_template_does_not_create_destination(setup):
    run, _, _, destination, _, _ = setup
    result, calls = run(fail=True)
    assert result.returncode == 2
    assert not destination.exists()
    assert all(call[0] == "orinoco-lite" for call in calls)


def test_existing_destination_requires_force(setup):
    run, _, _, destination, _, _ = setup
    destination.mkdir()
    (destination / "sentinel").write_text("keep\n")
    result, calls = run()
    assert result.returncode == 2
    assert "use --force" in result.stderr
    assert (destination / "sentinel").read_text() == "keep\n"
    assert all(call[0] == "orinoco-lite" for call in calls)


def test_force_replaces_existing_destination_after_selection(setup):
    run, _, _, destination, _, _ = setup
    destination.mkdir()
    (destination / "sentinel").write_text("replace\n")
    objects = destination / ".git/annex/objects/key"
    objects.mkdir(parents=True)
    payload = objects / "key"
    payload.write_bytes(b"annex content")
    payload.chmod(0o444)
    objects.chmod(0o555)
    result, _ = run("--force")
    assert result.returncode == 0, result.stderr
    assert not (destination / "sentinel").exists()
    assert (destination / "pixi.toml").exists()


def test_force_keeps_destination_when_selection_fails(setup):
    run, _, _, destination, _, _ = setup
    destination.mkdir()
    (destination / "sentinel").write_text("keep\n")
    result, _ = run("--force", fail=True)
    assert result.returncode != 0
    assert (destination / "sentinel").read_text() == "keep\n"


def test_force_refuses_engineering_checkout(setup):
    run, engineering, _, _, _, _ = setup
    result, _ = run("--force", destination_path=engineering)
    assert result.returncode != 0
    assert "protected path" in result.stderr
    assert (engineering / "release/package-resources.yaml").exists()


def test_optional_build_uses_existing_recorded_publication_path(setup):
    run, _, _, _, _, _ = setup
    result, calls = run("--build")
    assert result.returncode == 0, result.stderr
    populate = next(call for call in calls if "populate" in call)
    build = next(call for call in calls if "build" in call)
    assert build[-2:] == ["--publication-bundle", "build/pages-publication.bundle"]
    assert calls.index(populate) < calls.index(build)
    assert not any("publication" in call for call in calls)
    assert "Setup and build complete" in result.stdout


def test_setup_input_paths_resolve_from_physical_destination(setup, tmp_path):
    run, _, _, _, _, _ = setup
    physical = tmp_path / "deeper/physical"
    physical.mkdir(parents=True)
    alias = tmp_path / "alias"
    alias.symlink_to(physical, target_is_directory=True)
    supplied = tmp_path / "capture.jsonl"
    supplied.write_text('{}\n')
    result, calls = run("--dump", str(supplied), destination_path=alias / "site")
    assert result.returncode == 0, result.stderr
    populate = next(call for call in calls if "populate" in call)
    retained_input = populate[populate.index("--dump") + 1]
    assert (physical / "site" / retained_input).resolve() == supplied.resolve()


@pytest.mark.parametrize("remote", ["git@github.com:example/package.git", "ssh://git@github.com/example/package.git"])
def test_github_ssh_origin_uses_public_read_url(setup, remote):
    run, engineering, _, _, package_head, _ = setup
    git(engineering, "remote", "set-url", "origin", remote)
    result, calls = run("--build")
    assert result.returncode == 0, result.stderr
    update = next(call for call in calls if call[:2] == ["datalad", "run"])
    assert update[update.index("--repository") + 1] == "https://github.com/example/package.git"
    assert update[update.index("--revision") + 1] == package_head


def test_summary_includes_versions_changes_inputs_and_build_hint(setup, tmp_path):
    run, engineering, template, _, package_head, _ = setup
    (template / "untracked.txt").write_text("local edit")
    (engineering / ".gitmodules").write_text("local edit")
    dump = tmp_path / "input.jsonl"
    dump.write_text("{}")
    result, _ = run("--dump", str(dump), "--site-layout", "directory")
    assert result.returncode == 0, result.stderr
    assert "test: package candidate" in result.stdout
    assert "test: remote template" in result.stdout
    assert "• www-from-model:" in result.stdout
    assert git(engineering / "submodules/www-from-model", "rev-parse", "HEAD")[:7] in result.stdout
    assert "Warning: Engineering: M .gitmodules; untracked: release/" in result.stdout
    assert result.stdout.index("• www-from-model:") < result.stdout.index("• Inputs:") < result.stdout.index("Warning:")
    assert " M .gitmodules" in result.stdout
    assert "Warning: Template: untracked: untracked.txt" in result.stdout
    assert str(dump) in result.stdout
    assert "site layout: directory" in result.stdout
    assert "Build: skipped" in result.stdout
    assert "or add --build to the task invocation next time" in result.stdout


def test_redirected_input_requires_explicit_noninteractive_flag(setup):
    run, _, _, destination, _, _ = setup
    destination.mkdir()
    sentinel = destination / "sentinel"
    sentinel.write_text("keep")
    result, calls = run("--force", interactive=True)
    assert result.returncode == 2
    assert "--non-interactive" in result.stderr
    assert "Forced overwrite" in result.stdout
    assert sentinel.read_text() == "keep"
    assert all(call[0] == "orinoco-lite" for call in calls)


@pytest.mark.parametrize("key", [b"x", b"\x03"])
@pytest.mark.parametrize("no_color", [False, True])
def test_terminal_pause_precedes_force_replacement(setup, key, no_color):
    run, engineering, template, destination, _, _ = setup
    destination.mkdir()
    sentinel = destination / "sentinel"
    sentinel.write_text("keep")
    terminal_env = {**run.env, "TERM": "xterm-256color", "COLUMNS": "80"}
    terminal_env.pop("NO_COLOR", None)
    if no_color:
        terminal_env["NO_COLOR"] = "1"
    master, slave = pty.openpty()
    process = subprocess.Popen(
        ["bash", str(SCRIPT), str(destination), "--template", str(template), "--force"],
        cwd=engineering, env=terminal_env, stdin=slave, stdout=slave, stderr=slave,
        start_new_session=True, preexec_fn=lambda: fcntl.ioctl(0, termios.TIOCSCTTY, 0))
    os.close(slave)
    output = b""
    try:
        deadline = time.monotonic() + 15
        while b"Press any key to continue" not in output and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                output += os.read(master, 65536)
        assert b"Press any key to continue" in output, output.decode()
        assert b"www-from-model:" in output
        assert (b"\x1b[" in output) is not no_color
        plain = re.sub(r"\x1b\[[0-9;]*m", "", output.decode()).splitlines()
        assert len(plain) <= 20
        assert all(len(row) <= 80 for row in plain)
        assert b"Forced overwrite" in output
        assert sentinel.read_text() == "keep"
        assert process.poll() is None
        os.write(master, key)
        # Drain the terminal so the pipeline's trace cannot fill its output buffer.
        while process.poll() is None and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    output += os.read(master, 65536)
                except OSError:
                    break
        process.wait(timeout=5)
        if key == b"x":
            assert process.returncode == 0, output.decode()
            assert not sentinel.exists()
        else:
            assert process.returncode != 0, output.decode()
            assert sentinel.read_text() == "keep"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)


def test_summary_uses_selected_gitlink_instead_of_upstream_checkout_head(setup):
    run, engineering, _, _, _, _ = setup
    upstream = engineering / "submodules/www-from-model"
    selected = git(upstream, "rev-parse", "HEAD")
    git(upstream, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "--no-verify", "--allow-empty", "-qm", "test: unselected upstream")
    result, _ = run()
    assert result.returncode == 0, result.stderr
    assert f"({selected[:7]}" in result.stdout
    assert "test: unselected upstream" not in result.stdout


@pytest.mark.parametrize("relative_url", [False, True])
def test_summary_fetches_commit_metadata_without_modifying_checkouts(setup, tmp_path, relative_url):
    _, engineering, template, destination, package_head, template_head = setup
    if relative_url:
        modules = engineering / ".gitmodules"
        modules.write_text(modules.read_text().replace(str(engineering / "submodules/www-from-model"),
                                                       "./submodules/www-from-model"))
        git(engineering, "add", ".gitmodules")
        git(engineering, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "--no-verify", "-qm", "test: relative upstream URL")
        package_head = git(engineering, "rev-parse", "HEAD")
    missing = tmp_path / "no-checkout"
    result = subprocess.run([
        sys.executable, str(SCRIPT.with_name("setup-upstream-summary.py")),
        "--package", str(missing), str(engineering), package_head,
        "--template", str(missing), str(template), template_head,
        "--package-selection", package_head, "--template-selection", template_head,
        "--destination", str(destination), "--api", "https://example.invalid/api",
        "--site-layout", "submodule", "--build", "true"], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert ("test: relative upstream URL" if relative_url else "test: package candidate") in result.stdout
    assert "• www-from-model:" in result.stdout
    assert "Build: site + publication bundle" in result.stdout
    assert not destination.exists()
    assert not missing.exists()
    assert git(engineering, "rev-parse", "HEAD") == package_head


def test_review_stays_under_twenty_lines_with_many_local_changes(setup):
    run, engineering, template, destination, _, _ = setup
    repository(destination, "main")
    roots = [engineering, template, engineering / "submodules/www-from-model", destination]
    for root in roots:
        (root / "tracked.txt").write_text("before")
        git(root, "add", "tracked.txt")
        for number in range(30):
            directory = root / f"new-directory-{number:02d}"
            directory.mkdir()
            (directory / "file").write_text("untracked")
    result, _ = run("--force", interactive=True)
    assert result.returncode == 2
    rows = result.stdout.splitlines()
    assert len(rows) + 2 <= 20  # Include the blank line and terminal prompt.
    assert all(len(row) <= 240 for row in rows)
    assert "..." in result.stdout
    warnings = [row for row in rows if row.startswith("Warning:")]
    assert len(warnings) == 4
    assert any(row.startswith("Warning: Destination: A tracked.txt; untracked:") for row in warnings)
    assert "\x1b[" not in result.stdout
    assert "dev enable" not in result.stdout
    assert "DataLad" not in result.stdout


def test_site_specific_publication_url_is_recorded_after_population(setup):
    run, *_ = setup
    url = "https://github.com/example/site-inputs.git"
    result, calls = run("--site-specific-url", url)
    assert result.returncode == 0, result.stderr
    registration = next(c for c in calls if "set-url" in c)
    assert registration[-3:] == ["set-url", "site-specific", url]
    assert registration[:4] == ["pixi", "run", "datalad", "run"]
    assert ".gitmodules" in registration
    assert calls.index(registration) > next(i for i, c in enumerate(calls) if "populate" in c)
    assert any("siblings" in c and c[-1] == url for c in calls)


def test_site_specific_url_rejects_directory_layout_before_creation(setup):
    run, _, _, destination, *_ = setup
    result, _ = run("--site-specific-url", "https://example.invalid/inputs.git", "--site-layout", "directory")
    assert result.returncode != 0
    assert not destination.exists()

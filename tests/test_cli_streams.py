"""Exercise the public executable with real pipes and separate output streams."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

import pytest

CLI = [sys.executable, "-m", "orinoco_lite"]


def run(root, *args, input=""):
    return subprocess.run(CLI + list(args), cwd=root, input=input,
                          capture_output=True, text=True, timeout=30)


def record(label="Café", **values):
    return {"pid": "ex:item", "schema_type": "xyzri:XYZPublication",
            "display_label": label, **values}


def source(root, name="input.jsonl", **values):
    path = root / name
    path.write_text(json.dumps(record(**values)) + "\n", encoding="utf-8")
    return path


def test_stdin_import_stdout_export_and_real_pipe_diff(tmp_path):
    original = source(tmp_path)
    result = run(tmp_path, "dev", "records", "jsonl-to-yaml", "--source", "-",
                 input=original.read_text())
    assert result.returncode == 0, result.stderr
    exported = run(tmp_path, "dev", "records", "yaml-to-jsonl", "--output", "-")
    assert exported.returncode == 0, exported.stderr
    assert json.loads(exported.stdout) == record()
    assert exported.stdout.endswith("\n")
    assert not (tmp_path / "-").exists()
    assert "Wrote 1" in exported.stderr
    producer = subprocess.Popen(CLI + ["dev", "records", "yaml-to-jsonl", "--output", "-"],
                                cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        consumer = subprocess.run(CLI + ["dev", "records", "diff", "--json", "-", str(original)],
                                  cwd=tmp_path, stdin=producer.stdout, capture_output=True, timeout=30)
        producer.stdout.close()
        _, stderr = producer.communicate(timeout=30)
        assert producer.returncode == consumer.returncode == 0, (stderr, consumer.stderr)
        assert json.loads(consumer.stdout)["findings"] == []
    finally:
        if producer.poll() is None:
            producer.kill()
            producer.wait()


def test_literal_dash_and_option_like_paths(tmp_path):
    original = source(tmp_path, "-")
    source(tmp_path, "-other")
    result = run(tmp_path, "dev", "records", "diff", "--json", "--", "./-", "-other")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["findings"] == []
    assert run(tmp_path, "dev", "records", "jsonl-to-yaml", "--source", "./-").returncode == 0
    original.unlink()
    result = run(tmp_path, "dev", "records", "yaml-to-jsonl", "--output", "./-")
    assert result.returncode == 0, result.stderr
    assert json.loads(original.read_text()) == record()


@pytest.mark.parametrize("payload", ["", '{"broken":\n', json.dumps(record()) + '\ninvalid\n'])
def test_invalid_stream_does_not_replace_metadata(tmp_path, payload):
    original = source(tmp_path)
    assert run(tmp_path, "dev", "records", "jsonl-to-yaml", "--source", str(original)).returncode == 0
    before = {p.relative_to(tmp_path): p.read_bytes() for p in (tmp_path / "site-specific").rglob("*") if p.is_file()}
    result = run(tmp_path, "dev", "records", "jsonl-to-yaml", "--force", "--source", "-", input=payload)
    assert result.returncode == 2
    assert not result.stdout
    assert result.stderr and "Traceback" not in result.stderr
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in (tmp_path / "site-specific").rglob("*") if p.is_file()}


def test_diff_json_complete_values_filters_and_status(tmp_path):
    left = source(tmp_path, "before file.jsonl", label="a" * 1000, description="before")
    right = source(tmp_path, "after.jsonl", label="b" * 1000, description="after")
    args = ("dev", "records", "diff", "--json", str(left), str(right))
    result = run(tmp_path, *args, "--summary", "--limit", "0", "--field", "display_label")
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["total_findings"] == 2
    assert len(report["findings"]) == 1
    assert report["findings"][0]["after"] == "b" * 1000
    result = run(tmp_path, *args, "--field", "absent")
    assert result.returncode == 1
    assert json.loads(result.stdout)["findings"] == []
    result = run(tmp_path, "dev", "records", "diff", "-", "-")
    assert result.returncode == 2 and "Only one" in result.stderr


@pytest.mark.parametrize("size", [1, 200000])
def test_early_reader_exit_has_no_python_error(tmp_path, size):
    left = source(tmp_path, "before.jsonl", label="a" * size)
    right = source(tmp_path, "after.jsonl", label="b" * size)
    reader, writer = os.pipe()
    os.close(reader)
    try:
        result = subprocess.run(CLI + ["dev", "records", "diff", "--json", str(left), str(right)],
                                cwd=tmp_path, stdout=writer, stderr=subprocess.PIPE, timeout=30)
    finally:
        os.close(writer)
    assert result.returncode == 141
    assert b"BrokenPipe" not in result.stderr and b"Traceback" not in result.stderr


def test_interrupt_while_waiting_for_stdin(tmp_path):
    # The delayed progress message proves parsing is complete and stdin is being read.
    process = subprocess.Popen(CLI + ["dev", "records", "diff", "-", "missing.jsonl"],
                               cwd=tmp_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    try:
        import selectors
        with selectors.DefaultSelector() as selector:
            selector.register(process.stderr, selectors.EVENT_READ)
            assert selector.select(timeout=15), "no progress while waiting for input"
            assert b"Reading and comparing" in process.stderr.readline()
        process.send_signal(signal.SIGINT)
        _, stderr = process.communicate(timeout=10)
        assert process.returncode == 130
        assert b"interrupted" in stderr and b"Traceback" not in stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


@pytest.mark.parametrize("args", [("--help",), ("--version",), ("dev", "records", "diff", "--help")])
def test_help_without_workspace_or_stdin(tmp_path, args):
    result = run(tmp_path, *args)
    assert result.returncode == 0
    assert result.stdout and not result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("machine", [False, True])
def test_piped_diff_retains_report_evidence(tmp_path, machine):
    original = source(tmp_path)
    report = tmp_path / "comparison"
    args = ["dev", "records", "diff", "-", str(original), "--report", str(report)]
    if machine:
        args.append("--json")
    result = run(tmp_path, *args, input=original.read_text())
    assert result.returncode == 0, result.stderr
    if machine:
        assert json.loads(result.stdout)["findings"] == []
    else:
        assert "Before: stdin" in result.stdout
    from orinoco_lite.stage_reports import load_report
    data, _ = load_report(report)
    artifact = data["stages"][0]["artifacts"]["left"]["path"]
    assert (report / artifact).read_bytes() == original.read_bytes()
    assert "Report:" in result.stderr
    repeated = run(tmp_path, *args, input=original.read_text())
    assert repeated.returncode == 0, repeated.stderr
    if machine:
        assert json.loads(repeated.stdout)["findings"] == []
    assert "Existing report kept" in repeated.stderr

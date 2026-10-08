"""Execute selected query-things pipelines against a retained record stream.

The subprocess uses the selected upstream commands. Pool lookups use the selected service populated from retained records.
The service and client own lookup and pagination behavior.
"""

from __future__ import annotations

from contextlib import ExitStack
import socket
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

import yaml

from .errors import DriverError
from .projection import _route_for_pid
from .upstream_snapshot import load_jsonl


def run_upstream(records: Path, presentation: Path, output: Path,
                 *, python_command: list[str] | None = None, resources_root: Path | None = None) -> dict:
    from .record_stages import _check_record_input
    _check_record_input(records)
    command = [*(python_command or [sys.executable]), "-m", __name__, str(records), str(presentation), str(output)]
    if resources_root is not None:
        command.append(str(resources_root))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise DriverError(f"Selected upstream projection failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        summary = json.loads(result.stdout)
        summary["runtime_command"] = python_command or [sys.executable]
        return summary
    except ValueError as error:
        raise DriverError("Selected upstream projection emitted an invalid summary") from error


def workflow_steps(presentation: Path) -> list[dict]:
    path = presentation / ".forgejo/workflows/update-from-pool.yaml"
    try:
        steps = yaml.safe_load(path.read_text())["jobs"]["create_pages"]["steps"]
        if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
            raise ValueError("steps must be mappings")
        return steps
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as error:
        raise DriverError(f"Unsupported upstream projection workflow: {path}") from error


def homepage_pid(presentation: Path) -> str:
    """Read the singleton homepage selection from the authoritative workflow."""
    pids = []
    for step in workflow_steps(presentation):
        run = step.get("run", "").replace("\\\n", " ")
        if "render-record" not in run:
            continue
        arguments = shlex.split(run.split("|", 1)[0])
        if arguments[:3] == ["query-things", "list", "--pid"] and len(arguments) == 4:
            pids.append(arguments[3])
    if len(pids) != 1:
        raise DriverError("Upstream workflow must select exactly one homepage PID")
    return pids[0]


def render_graph(records: str, presentation: Path) -> str:
    """Use the upstream producer for graph membership and relationships."""
    result = subprocess.run([sys.executable, str(presentation / "code/pool2graph.py")],
                            input=records, capture_output=True, text=True)
    if result.returncode:
        raise DriverError(f"Upstream graph production failed: {result.stderr.strip()}")
    try:
        graph = json.loads(result.stdout)
        if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
            raise ValueError("missing node or edge arrays")
    except ValueError as error:
        raise DriverError("Upstream graph output has no node and edge arrays") from error
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result.stdout.rstrip() + "\n"


def project(records_path: Path, presentation: Path, output: Path, resources_root: Path | None = None) -> dict:
    """Run query-things commands from the selected upstream workflow."""
    from .record_stages import _check_record_input
    _check_record_input(records_path)
    try:
        from click.testing import CliRunner
        from query_things.cli import main
        from dump_things_pyclient import communicate
    except ImportError as error:
        raise DriverError(
            "The selected query-things dependencies are unavailable; reinstall "
            "orinoco-lite in the active environment."
        ) from error
    records = [item.record for item in load_jsonl(records_path)]
    steps = workflow_steps(presentation)
    root_pid = homepage_pid(presentation)
    route_prefix = root_pid.split(":", 1)[0] + ":"
    runner = CliRunner()
    output.mkdir(parents=True, exist_ok=True)
    (output / "content").mkdir(exist_ok=True)
    (output / "static").mkdir(exist_ok=True)
    commands = []
    original_cwd = Path.cwd()
    try:
        with tempfile.TemporaryDirectory(prefix="orinoco-query-") as temporary, ExitStack() as services:
            scratch = Path(temporary)
            from .upstream_service import local_service
            from .upstream_service import selected_schema
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            # The selected SQLite backend applies search patterns in storage;
            # the file backend scans all records for each incoming-link query.
            service = services.enter_context(local_service(
                scratch / "service", selected_schema(resources_root), port=port, backend="sqlite+stl"))
            with communicate.get_session() as session:
                for item in load_jsonl(records_path):
                    try:
                        communicate.curated_write_record(service.url, "public", item.class_name,
                            item.record, token=service.token, session=session)
                    except communicate.HTTPError as error:
                        raise DriverError(f"Cannot load {item.pid} into the selected service: {error.response.text}") from error
            os.chdir(scratch)
            environment = {
                "QRI_RECORD_CACHE": str(scratch / "cache.json"),
                "DUMPTHINGS_APIURL": service.url,
            }

            def invoke(arguments, stream=""):
                result = runner.invoke(main, arguments, input=stream, env=environment)
                if result.exit_code:
                    raise DriverError(
                        f"query-things {' '.join(arguments)} failed: "
                        f"{result.output.strip()} ({result.exception})"
                    )
                commands.append(["query-things", *arguments])
                return result.stdout

            raw = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
            invoke(["cache"], raw)
            render_steps = 0
            for step in steps:
                run = step.get("run", "").replace("\\\n", " ")
                if not run.lstrip().startswith("query-things "):
                    continue
                stream = ""
                for pipe in run.strip().split("|"):
                    arguments = shlex.split(pipe.strip())
                    if arguments[:2] == ["jq", "-r"]:
                        if arguments != ["jq", "-r", ".pid", ">", "localfolk.pids"]:
                            raise DriverError("Unsupported selected upstream member-list pipeline")
                        (scratch / "localfolk.pids").write_text("".join(
                            json.loads(line)["pid"] + "\n" for line in stream.splitlines() if line
                        ))
                        continue
                    if not arguments or arguments.pop(0) != "query-things":
                        raise DriverError("Unsupported operation in selected upstream projection pipeline")
                    if arguments[0] == "render-record":
                        for line in stream.splitlines():
                            if line:
                                pid = json.loads(line)["pid"]
                                if pid != root_pid:
                                    _route_for_pid(pid, route_prefix)
                        arguments[1] = str(presentation / arguments[1])
                        for index in range(2, len(arguments)):
                            value = Path(arguments[index])
                            if value.is_absolute() or ".." in value.parts or value.parts[0] != "content":
                                raise DriverError("Upstream render output must remain under content/")
                            arguments[index] = str(output / value)
                        render_steps += 1
                    stream = invoke(arguments, stream)
            if not render_steps:
                raise DriverError("Selected upstream workflow has no supported render-record operations")
            (output / "static/graph.json").write_text(render_graph(raw, presentation))
    finally:
        os.chdir(original_cwd)
    (output / "records.jsonl").write_text(raw)
    return {"records": len(records), "pages": len(list((output / "content").rglob("*.md"))),
            "operations": commands, "lookup": "temporary service populated from retained records"}


if __name__ == "__main__":
    try:
        print(json.dumps(project(*(Path(value).resolve() for value in sys.argv[1:]))))
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)

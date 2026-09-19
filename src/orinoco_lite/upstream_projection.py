"""Execute selected query-things pipelines against a retained record stream.

The subprocess uses the selected upstream commands. Only their Pool lookup
boundary is bound to the retained stream; no RDF conversion or network lookup
participates in this isolated projection comparison.
"""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

import yaml

from .errors import DriverError, IntegrityError
from .projection import _route_for_pid
from .upstream_snapshot import load_jsonl



def resolve_tools(workspace: Path, presentation: Path) -> Path:
    """Use prepared query tools only when they match the presentation owner's pins."""
    from .development import LINK
    from .presentation import _git_text, _repository_head, _selected_presentation_commit

    engineering = presentation.parent.parent
    commit = _repository_head(engineering, label="Selected engineering checkout")
    if _repository_head(presentation, label="Selected presentation checkout") != _selected_presentation_commit(engineering, commit):
        raise DriverError("Selected presentation checkout does not match its owning engineering Gitlink")
    selected = {}
    for name in ("query-things", "dump-things-pyclient"):
        path = f"submodules/{name}"
        entry = _git_text(engineering, ("ls-tree", commit, "--", path),
                          operation=f"read the selected {name} Gitlink")
        fields = entry.split()
        if len(fields) != 4 or fields[:2] != ["160000", "commit"] or fields[3] != path:
            raise DriverError(f"Selected engineering commit does not pin {path}")
        selected[name] = fields[2]
    candidates = []
    link = workspace / LINK
    if link.is_symlink():
        candidates.append(link.resolve() / "submodules")
    candidates.append(presentation.parent)
    diagnostics = []
    for candidate in dict.fromkeys(candidates):
        try:
            for name, expected in selected.items():
                checkout = candidate / name
                actual = _repository_head(checkout, label=f"Selected {name} checkout")
                if actual != expected:
                    raise DriverError(f"{name} checkout is {actual}, expected Gitlink {expected}")
                if _git_text(checkout, ("status", "--porcelain", "--untracked-files=all"),
                             operation=f"verify selected {name} sources"):
                    raise DriverError(f"Selected {name} checkout has uncommitted source changes")
            return candidate.resolve()
        except (DriverError, IntegrityError) as error:
            diagnostics.append(str(error))
    raise DriverError("Selected upstream tools are unavailable; initialize the query-things "
                      "and dump-things-pyclient submodules in the linked engineering checkout. "
                      + "; ".join(diagnostics))


def run_upstream(records: Path, presentation: Path, output: Path, tools: Path,
                 *, python_command: list[str] | None = None) -> dict:
    query = tools / "query-things"
    client = tools / "dump-things-pyclient"
    if not (query / "query_things").is_dir() or not (client / "dump_things_pyclient").is_dir():
        raise DriverError(
            f"Selected upstream query tools are missing below {tools}; initialize "
            "the query-things and dump-things-pyclient submodules."
        )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join([
        str(query), str(client), str(Path(__file__).parents[1]),
        environment.get("PYTHONPATH", ""),
    ])
    command = [*(python_command or [sys.executable]), "-m", __name__, str(records), str(presentation), str(output)]
    result = subprocess.run(command, env=environment, capture_output=True, text=True)
    if result.returncode:
        raise DriverError(f"Selected upstream projection failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        summary = json.loads(result.stdout)
        summary["runtime_command"] = python_command or [sys.executable]
        return summary
    except ValueError as error:
        raise DriverError("Selected upstream projection emitted an invalid summary") from error


def project(records_path: Path, presentation: Path, output: Path) -> dict:
    """Run query-things commands from the selected upstream workflow."""
    try:
        from click.testing import CliRunner
        from query_things.cli import main
        import query_things.common.api as api
        import query_things.filter_linked_pid as linked
        import query_things.inject_links_pid as injected
        import requests
    except ImportError as error:
        raise DriverError(
            "The selected query-things dependencies are unavailable; activate "
            "the maintainer environment (including click-option-group)."
        ) from error
    records = [item.record for item in load_jsonl(records_path)]
    by_pid = {item["pid"]: item for item in records}
    missing: set[str] = set()

    def lookup(*args, **kwargs):
        pid = kwargs.get("pid", args[2] if len(args) > 2 else None)
        if pid not in by_pid:
            missing.add(str(pid))
            return None
        return deepcopy(by_pid[pid])

    def collection(*args, **kwargs):
        class_name = args[2] if len(args) > 2 else kwargs.get("class_name", "Thing")
        return [(deepcopy(record), {}) for record in records
                if class_name == "Thing" or record["schema_type"].split(":")[-1] == class_name]

    def no_network(*args, **kwargs):
        raise DriverError("Upstream projection attempted a lookup outside the retained stream")

    api.collection_read_record_with_pid = lookup
    linked.collection_read_record_with_pid = lookup
    injected.collection_read_records_of_class = collection
    requests.sessions.Session.request = no_network
    workflow = presentation / ".forgejo/workflows/update-from-pool.yaml"
    document = yaml.safe_load(workflow.read_text())
    steps = document["jobs"]["create_pages"]["steps"]
    runner = CliRunner()
    output.mkdir(parents=True, exist_ok=True)
    (output / "content").mkdir(exist_ok=True)
    (output / "static").mkdir(exist_ok=True)
    commands = []
    original_cwd = Path.cwd()
    try:
        with tempfile.TemporaryDirectory(prefix="orinoco-query-") as temporary:
            scratch = Path(temporary)
            os.chdir(scratch)
            environment = {
                "QRI_RECORD_CACHE": str(scratch / "cache.json"),
                "DUMPTHINGS_APIURL": "http://retained-input.invalid/api",
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
                                if pid.split(":", 1)[1] != ".":
                                    _route_for_pid(pid, pid.split(":", 1)[0] + ":")
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
            graph = subprocess.run(
                [sys.executable, str(presentation / "code/pool2graph.py")],
                input=raw, capture_output=True, text=True,
            )
            if graph.returncode:
                raise DriverError(f"Upstream graph production failed: {graph.stderr.strip()}")
            value = json.loads(graph.stdout)
            if not isinstance(value, dict) or not isinstance(value.get("nodes"), list) or not isinstance(value.get("edges"), list):
                raise DriverError("Upstream graph output has no node and edge arrays")
            (output / "static/graph.json").write_text(graph.stdout.rstrip() + "\n")
    finally:
        os.chdir(original_cwd)
    (output / "records.jsonl").write_text(raw)
    return {"records": len(records), "pages": len(list((output / "content").rglob("*.md"))),
            "operations": commands, "lookup": "retained stream only",
            "unresolved_reference_pids": sorted(missing)}


if __name__ == "__main__":
    try:
        print(json.dumps(project(*(Path(value).resolve() for value in sys.argv[1:]))))
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)

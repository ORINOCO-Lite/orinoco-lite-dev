"""Execute selected query-things pipelines against a retained record stream.

The subprocess uses the selected upstream commands. Pool lookups use the selected service populated from retained records.
The service and client own lookup and pagination behavior.
"""

from __future__ import annotations

import socket
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

import yaml

from .errors import DriverError
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
    """Execute inspected upstream shell blocks against the local Pool."""
    from .record_stages import _check_record_input
    from .projection_blocks import adjust_for_lite, parse_workflow, BlockExecutionError
    from .upstream_service import local_service, selected_schema
    from dump_things_pyclient import communicate
    import shutil

    _check_record_input(records_path)
    records = load_jsonl(records_path)
    pipeline = adjust_for_lite(parse_workflow(
        presentation / '.forgejo/workflows/update-from-pool.yaml'))
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='orinoco-projection-') as temporary:
        scratch = Path(temporary)
        # Upstream interpolates PID suffixes into this literal filename.
        # Check filesystem containment without imposing URL or page-selection rules.
        content_root = (scratch / 'content').resolve()
        for item in records:
            suffix = item.pid.partition(':')[2]
            target = (scratch / f'content/{suffix}/_index.md').resolve()
            if not target.is_relative_to(content_root):
                raise DriverError(f'Record PID escapes upstream content directory: {item.pid}')
        for name in ('page_templates', 'code'):
            shutil.copytree(presentation / name, scratch / name)
        for name in ('content', 'static'):
            (scratch / name).mkdir()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        with local_service(scratch / 'service', selected_schema(resources_root),
                           port=port, backend='sqlite+stl') as service:
            with communicate.get_session() as session:
                for item in records:
                    try:
                        communicate.curated_write_record(service.url, 'public', item.class_name,
                            item.record, token=service.token, session=session)
                    except communicate.HTTPError as error:
                        raise DriverError(f'Cannot load {item.pid} into the selected service: {error.response.text}') from error
            try:
                operations = pipeline.execute(cwd=scratch, environment={
                    'DUMPTHINGS_APIURL': service.url,
                    'QRI_RECORD_CACHE': str(scratch / 'cache.json'),
                }, stdout=sys.stderr)
            except BlockExecutionError as error:
                raise DriverError(str(error)) from error
        for name in ('content', 'static'):
            shutil.copytree(scratch / name, output / name, dirs_exist_ok=True)
    raw = ''.join(json.dumps(item.record, ensure_ascii=False) + '\n' for item in records)
    (output / 'records.jsonl').write_text(raw)
    graph = json.loads((output / 'static/graph.json').read_text())
    return {'records': len(records), 'pages': len(list((output / 'content').rglob('*.md'))),
            'graph_nodes': len(graph['nodes']), 'graph_edges': len(graph['edges']),
            'operations': operations, 'lookup': 'temporary service populated from retained records'}


if __name__ == "__main__":
    try:
        print(json.dumps(project(*(Path(value).resolve() for value in sys.argv[1:]))))
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)

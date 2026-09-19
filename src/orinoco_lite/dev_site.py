"""Independent import, projection, assembly, build and comparison commands."""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import tempfile

from .config import load_workspace, _load_site_data
from .errors import DriverError, OrinocoError
from .presentation import resolve_presentation
from .projection import render_projection
from .resources import resolve_resources
from .site import assemble_hugo, build_hugo
from .site_compare import compare_trees, check_site
from .site_inputs import import_site_inputs, selected_site_files
from .upstream_projection import resolve_tools, run_upstream


def _sources(parser):
    parser.add_argument("--resources", type=Path, help="prepared package resources")
    parser.add_argument("--presentation", type=Path, help=(
        "explicit selected presentation checkout with required file bytes already prepared; "
        "recorded import through a development link requires datalad rerun --assume-ready inputs"
    ))


def _comparison(parser, stage):
    parser.add_argument("--report", type=Path)
    parser.add_argument("--mode", choices=("isolated", "complete-path"), default="isolated")
    parser.add_argument("--stage", default=stage)


def register(dev_subparsers):
    inputs = dev_subparsers.add_parser("inputs", help="import and compare selected upstream site data")
    actions = inputs.add_subparsers(dest="inputs_command", required=True)
    for action in ("import", "diff"):
        parser = actions.add_parser(action)
        parser.add_argument("inputs", type=Path)
        _sources(parser)
        if action == "import":
            parser.add_argument("--no-record", action="store_true")
        else:
            _comparison(parser, "site-input-import")
    hugo = dev_subparsers.add_parser("hugo", help="run one explicit Hugo generation boundary")
    actions = hugo.add_subparsers(dest="hugo_command", required=True)
    project = actions.add_parser("project")
    project.add_argument("flavor", choices=("upstream", "lite"))
    project.add_argument("output", type=Path)
    project.add_argument("--records", required=True, type=Path)
    project.add_argument("--upstream-tools", type=Path, help="directory containing selected query-things and dump-things-pyclient checkouts")
    _sources(project)
    assemble = actions.add_parser("assemble")
    assemble.add_argument("flavor", choices=("upstream", "lite"))
    assemble.add_argument("projection", type=Path)
    assemble.add_argument("output", type=Path)
    assemble.add_argument("--inputs", type=Path, required=True)
    _sources(assemble)
    build = actions.add_parser("build", help="render a supplied tree; ordinary build binds editor/review applications separately")
    build.add_argument("flavor", choices=("upstream", "lite"))
    build.add_argument("assembly", type=Path)
    build.add_argument("output", type=Path)
    build.add_argument("--base-url", required=True)
    build.add_argument("--resources", type=Path)
    for group, stage in (("content", "projection"), ("site", "rendering")):
        parser = dev_subparsers.add_parser(group)
        actions = parser.add_subparsers(dest=f"{group}_command", required=True)
        diff = actions.add_parser("diff")
        diff.add_argument("left", type=Path)
        diff.add_argument("right", type=Path)
        _comparison(diff, stage)
        if group == "site":
            check = actions.add_parser("check")
            check.add_argument("site", type=Path)
            _comparison(check, "site-check")
            check.add_argument("--browser", action="store_true", help="inspect selected routes with workspace Playwright and retain screenshots")
            check.add_argument("--route", action="append", default=[], help="browser route; repeat for additional routes (default /)")


def _path(args, value):
    return (Path(args.root) / value).resolve() if not value.is_absolute() else value.resolve()


def _revision(path):
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def _selection(args):
    resources = _path(args, args.resources) if args.resources else resolve_resources().root
    presentation = (_path(args, args.presentation) if args.presentation
                    else resolve_presentation(Path(args.root), resources))
    return resources, presentation


def _report(args, left, right, findings, scope, *, comparator, evidence=None):
    from .stage_reports import write_report
    print(f"{args.stage}: {len(findings)} raw differences")
    print(f"  left: {left}\n  right: {right}")
    for item in findings[:30]:
        print(f"  {item['change']}: {item['subject']} / {'/'.join(map(str, item['location']))}")
    if len(findings) > 30:
        print(f"  {len(findings) - 30} additional findings; inspect the report")
    if args.report:
        report = write_report(_path(args, args.report), stage=args.stage, left=left, right=right,
                             findings=findings, comparator=comparator, scope=scope, mode=args.mode,
                             evidence=evidence, command=getattr(args, "invocation", []))
        print(f"  report: {_path(args, args.report)}")
    return int(bool(findings))


def execute(args):
    """Return 0 for agreement/success, 1 for findings, and 2 for failure."""
    from .stage_reports import operation_receipt, write_operation
    from .upstream_snapshot import SnapshotError
    output = None
    new_output = False
    try:
        args.root = (args.root or Path.cwd()).resolve()
        group = args.dev_command
        if group == "hugo" and args.hugo_command == "project":
            from .record_stages import _check_record_input
            _check_record_input(_path(args, args.records))
        if group in {"content", "site"}:
            if group == "site" and args.site_command == "check":
                root = _path(args, args.site)
                operation_receipt(root)
                findings, checked = check_site(root)
                evidence = None
                if args.browser:
                    if not args.report:
                        raise DriverError("Browser checks require --report to retain screenshots and diagnostics")
                    from .site_browser import inspect
                    from .site_compare import finding
                    browser_output = _path(args, args.report).with_name(args.report.name + "-browser")
                    observations = inspect(root, browser_output, args.route or ["/"], Path(args.root))
                    checked["browser_routes"] = args.route or ["/"]
                    checked["subjects"].extend(args.route or ["/"])
                    checked["locations"].append(["browser"])
                    evidence = {"browser": browser_output}
                    for observed in observations:
                        if observed["errors"] or observed["status"] is None or observed["status"] >= 400:
                            findings.append(finding(observed["route"], ["browser"], None, observed))
                return _report(args, root, root, findings, {
                    "complete": True,
                    "selection": "HTML local href/src/poster targets and fragments", **checked,
                }, comparator="local-html-targets/1", evidence=evidence)
            left, right = _path(args, args.left), _path(args, args.right)
            operation_receipt(left)
            operation_receipt(right)
            findings, names = compare_trees(left, right, rendered=group == "site")
            return _report(args, left, right, findings, {
                "complete": True, "all_subjects": True, "subjects": names,
                "exclusions": [".git"],
                "selection": "all file bytes; Markdown front matter and body; ordered JSON" + ("; HTML parser events" if group == "site" else ""),
            }, comparator="site-files/1" if group == "site" else "hugo-content/1")
        if group == "inputs":
            resources, presentation = _selection(args)
            destination = _path(args, args.inputs)
            if args.inputs_command == "import":
                if not args.no_record:
                    from .recording import record, relative_path
                    root = Path(args.root).resolve()
                    command = ["dev", "inputs", "import", relative_path(root, destination), "--no-record"]
                    declared_inputs = []
                    assume_ready_inputs = False
                    for option in ("resources", "presentation"):
                        value = getattr(args, option)
                        if value is not None:
                            # Keep an explicit maintainer source through the
                            # tracked development link relative and rerunnable.
                            selected = relative_path(root, value, follow_symlinks=False)
                            command.extend([f"--{option}", selected])
                            # Declare the retained connection itself. DataLad
                            # must not retrieve from an external maintainer
                            # checkout: the importer preflights its file bytes.
                            retained = Path(selected)
                            for ancestor in reversed((retained, *retained.parents)):
                                if ancestor.parts and (root / ancestor).is_symlink():
                                    retained = ancestor
                                    assume_ready_inputs = True
                                    break
                            declared_inputs.append(retained.as_posix())
                    outputs = [destination / path for path in selected_site_files(presentation)]
                    outputs.append(destination / "site.yaml")
                    record(root, command, inputs=declared_inputs, outputs=outputs,
                           message="chore: import selected upstream site inputs",
                           assume_ready_inputs=assume_ready_inputs)
                    return 0
                result = import_site_inputs(presentation, destination)
                print(json.dumps(result, indent=2))
                return 0
            with tempfile.TemporaryDirectory(prefix="orinoco-site-inputs-") as temporary:
                expected = Path(temporary) / "expected"
                import_site_inputs(presentation, expected)
                subjects = [path.as_posix() for path in selected_site_files(presentation)] + ["site.yaml"]
                findings, names = compare_trees(expected, destination, subjects=subjects)
                return _report(args, expected, destination, findings, {
                    "complete": True, "subjects": names,
                    "exclusions": ["metadata", "sources", "unimported paths"],
                    "selection": "selected upstream authored files and mapped site settings",
                }, comparator="site-input-import/1")
        workspace = load_workspace(Path(args.root))
        output = _path(args, args.output)
        if output.exists():
            raise DriverError(f"Declared output already exists; choose a fresh path: {output}")
        new_output = True
        if args.hugo_command == "build":
            resources = _path(args, args.resources) if args.resources else resolve_resources().root
            source = _path(args, args.assembly)
            operation_receipt(source)
            result = build_hugo(workspace, resources, source, output, args.base_url,
                                flavor=args.flavor)
            inputs = {"assembly": source}
            adapter = resources / "drivers/adapt_pages.py"
            hugo = subprocess.run(["hugo", "version"], capture_output=True, text=True, check=True)
            context = {"base_url": args.base_url, "flavor": args.flavor,
                       "scope": result["scope"], "hugo_version": hugo.stdout.strip(),
                       "adapter_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest()
                           if args.flavor == "lite" and adapter.is_file() else None}
        else:
            resources, presentation = _selection(args)
            context = {"presentation_commit": _revision(presentation), "flavor": args.flavor}
            if args.hugo_command == "project":
                source = _path(args, args.records)
                if output == source or output in source.parents:
                    raise DriverError("Projection output must not contain the input stream")
                if args.flavor == "upstream":
                    tools = (_path(args, args.upstream_tools) if args.upstream_tools
                             else resolve_tools(Path(args.root), presentation))
                    from .development import LINK
                    linked = Path(args.root) / LINK
                    runtime = None
                    if linked.is_symlink() and linked.resolve() == tools.parent:
                        runtime = ["pixi", "run", "--manifest-path", str(linked.resolve() / "pixi.toml"),
                                   "--locked", "python"]
                    result = run_upstream(source, presentation, output, tools, python_command=runtime)
                    context.update({"query_things_commit": _revision(tools / "query-things"),
                                    "pyclient_commit": _revision(tools / "dump-things-pyclient"),
                                    "lookup": "retained stream only", "operations": result.get("operations"),
                                    "runtime_command": result.get("runtime_command")})
                else:
                    result = render_projection(workspace, resources, output,
                                               records_input=source, presentation_root=presentation)
                inputs = {"records": source}
            else:
                projection, site_inputs = _path(args, args.projection), _path(args, args.inputs)
                operation_receipt(projection)
                operation_receipt(site_inputs)
                data = _load_site_data(site_inputs / "site.yaml")
                workspace = replace(workspace, site_data=data, site_name=data["identity"]["title"],
                                    base_url=data["identity"]["base_url"])
                result = assemble_hugo(workspace, resources, output, projection=projection,
                                       inputs=site_inputs, presentation=presentation, flavor=args.flavor)
                inputs = {"projection": projection, "site_inputs": site_inputs}
        write_operation(output, operation=f"hugo-{args.hugo_command}-{args.flavor}",
                        inputs=inputs, context=context, command=getattr(args, "invocation", []))
        print(json.dumps(result, indent=2))
        return 0
    except BaseException as error:
        # Retain failed boundary artifacts for inspection, but never let a later
        # comparison mistake an interrupted output for a complete supplied tree.
        if new_output and output is not None and output.exists():
            try:
                write_operation(output, operation=f"hugo-{args.hugo_command}-{args.flavor}",
                                inputs={}, command=getattr(args, "invocation", []),
                                context={"status": "failed", "diagnostic": f"{type(error).__name__}: {error}"})
            except (OrinocoError, OSError, ValueError) as receipt_error:
                print(f"Could not describe failed output {output}: {receipt_error}")
        if isinstance(error, (OrinocoError, OSError, ValueError, KeyError, SnapshotError)):
            print(f"orinoco-lite dev: {error}")
            return 2
        raise

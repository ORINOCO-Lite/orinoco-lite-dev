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


def register(dev_subparsers):
    from .diagnostics import options
    inputs = dev_subparsers.add_parser("inputs", help="inspect selected upstream site inputs")
    actions = inputs.add_subparsers(dest="inputs_command", required=True)
    for action in ("import", "diff"):
        parser = actions.add_parser(action, help="copy selected site inputs into the investigation" if action == "import" else "compare the copied inputs with upstream")
        options(parser)
    hugo = dev_subparsers.add_parser("hugo", help="project records, assemble Hugo inputs, or build HTML")
    actions = hugo.add_subparsers(dest="hugo_command", required=True)
    for action in ("project", "assemble", "build"):
        parser = actions.add_parser(action, description=(
            "Run the selected upstream or Lite operation inside the investigation. "
            "Inputs come from earlier commands; existing outputs require --force. "
            "Assembly and build default to identical upstream inputs on both sides; "
            "--mode complete-path uses each side's own preceding output."))
        parser.add_argument("flavor", choices=("upstream", "lite"), help="implementation to exercise")
        options(parser)
        parser.add_argument("--mode", choices=("isolated", "complete-path"), default="isolated")
        if action == "build":
            parser.add_argument("--base-url", default="/", help="website base URL (default: /)")
    for group in ("content", "site"):
        parser = dev_subparsers.add_parser(group)
        actions = parser.add_subparsers(dest=f"{group}_command", required=True)
        diff = actions.add_parser("diff", help="compare upstream and Lite outputs")
        options(diff)
        diff.add_argument("--mode", choices=("isolated", "complete-path"), default="isolated")
        if group == "content":
            diff.add_argument("stage", nargs="?", choices=("projection", "assembly"), default="projection")
        if group == "site":
            check = actions.add_parser("check", help="check links in a built website")
            check.add_argument("flavor", nargs="?", choices=("upstream", "lite"), default="lite")
            check.add_argument("--mode", choices=("isolated", "complete-path"), default="isolated")
            options(check)
            check.add_argument("--browser", action="store_true", help="also inspect routes in a real browser and retain screenshots")
            check.add_argument("--route", action="append", default=[], help="browser route (default: /)")


def _path(args, value):
    return (Path(args.root) / value).resolve() if not value.is_absolute() else value.resolve()


def _revision(path):
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def _selection(args):
    resources = resolve_resources().root
    presentation = resolve_presentation(Path(args.root), resources)
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
        from .diagnostics import directory, record_path, require, prepare_output
        args.root = (args.root or Path.cwd()).resolve()
        root = directory(args)
        group = args.dev_command
        mode = getattr(args, "mode", "isolated")
        args.mode = mode
        args.resources = None
        if group == "inputs":
            args.inputs = root / "site-inputs"
            args.stage = "site-input-import"
            if args.inputs_command == "diff":
                require(args.inputs, "inputs import")
            else:
                prepare_output(args.inputs, args.force)
        elif group == "hugo":
            action = args.hugo_command
            if action == "project":
                args.records = record_path(root, "downloaded" if mode == "complete-path" and args.flavor == "upstream" else "yaml-jsonl")
                base = root if mode == "isolated" else root / mode
                args.output = base / args.flavor / "projection"
            elif action == "assemble":
                source_flavor = args.flavor if mode == "complete-path" else "upstream"
                base = root if mode == "isolated" else root / mode
                args.projection = require(base / source_flavor / "projection", f"hugo project {source_flavor}")
                args.inputs = require(root / "site-inputs", "inputs import")
                args.output = root / mode / args.flavor / "assembly"
            else:
                source_flavor = args.flavor if mode == "complete-path" else "upstream"
                args.assembly = require(root / mode / source_flavor / "assembly", f"hugo assemble {source_flavor} --mode {mode}")
                args.output = root / mode / args.flavor / "website"
        elif group == "site" and args.site_command == "check":
            args.site = require(root / mode / args.flavor / "website", f"hugo build {args.flavor} --mode {mode}")
            args.stage = "site-check"
        else:
            if group == "site":
                args.stage = "rendering"
            folder = {"projection": "projection", "assembly": "assembly", "rendering": "website"}[args.stage]
            base = root if args.stage == "projection" and mode == "isolated" else root / mode
            command = {"projection": "project", "assembly": "assemble", "rendering": "build"}[args.stage]
            args.left = require(base / "upstream" / folder, f"hugo {command} upstream")
            args.right = require(base / "lite" / folder, f"hugo {command} lite")
        if group != "hugo":
            report_name = args.stage if args.stage == "site-input-import" or (args.stage == "projection" and mode == "isolated") else f"{args.stage}-{mode}"
            if args.stage == "site-check":
                report_name += f"-{args.flavor}"
            args.report = root / "reports" / report_name
            if not (group == "inputs" and args.inputs_command == "import"):
                prepare_output(args.report, args.force)
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
                result = import_site_inputs(presentation, destination)
                print(json.dumps(result, indent=2))
                print(f"Site inputs: {destination}")
                return 0
            with tempfile.TemporaryDirectory(prefix="orinoco-site-inputs-") as temporary:
                expected = Path(temporary).resolve() / "expected"
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
        prepare_output(output, args.force)
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
                    tools = resolve_tools(Path(args.root), presentation)
                    result = run_upstream(source, presentation, output, tools)
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
        print(f"Output: {output}")
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

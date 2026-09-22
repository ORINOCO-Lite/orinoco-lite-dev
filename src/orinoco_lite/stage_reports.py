"""Portable evidence from explicit diagnostic operations and comparisons.

Receipts live beside generated outputs. They are evidence for opening a review,
not another source of dependency selections or a persistent execution engine.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
from pathlib import Path
import shutil
import subprocess
import uuid
from typing import Any

from .errors import ConfigurationError

VERSION = 1
RECEIPT = ".orinoco-operation.json"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":"))


def json_digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_json(path: Path) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              ValueError(f"non-finite number: {value}")))
    except (OSError, ValueError) as error:
        raise ConfigurationError(f"Cannot read JSON {path}: {error}") from error


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
                    + "\n", encoding="utf-8")


def is_receipt(path: Path) -> bool:
    return path.name == RECEIPT or path.name.endswith(".operation.json")


def artifact_digest(path: Path) -> str:
    """Hash bytes and relative names without following links outside evidence."""
    if path.is_symlink():
        raise ConfigurationError(f"Evidence must not be a symbolic link: {path}")
    if path.is_file():
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    if not path.is_dir():
        raise ConfigurationError(f"Missing evidence: {path}")
    entries = []
    for child in sorted(path.rglob("*")):
        if child.is_symlink():
            raise ConfigurationError(f"Evidence contains a symbolic link: {child}")
        if child.is_file() and not is_receipt(child):
            entries.append([child.relative_to(path).as_posix(), artifact_digest(child)])
    return json_digest(entries)


def receipt_path(path: Path) -> Path:
    return path.with_name(path.name + ".operation.json")


def operation_receipt(path: Path) -> dict | None:
    receipt = receipt_path(path)
    if not receipt.is_file():
        return None
    data = read_json(receipt)
    if not isinstance(data, dict) or data.get("schema_version") != VERSION:
        raise ConfigurationError(f"Unsupported operation receipt at {receipt}")
    if not isinstance(data.get("operation"), str) or not isinstance(data.get("inputs"), dict):
        raise ConfigurationError(f"Invalid operation receipt at {receipt}")
    if data.get("context", {}).get("status", "complete") != "complete":
        raise ConfigurationError(f"Operation did not complete: {path}; inspect its partial artifacts")
    if data.get("output_digest") != artifact_digest(path):
        return None  # Edited diagnostic input is comparable, without producer attribution.
    return data


def execution_context() -> dict:
    from . import __version__
    root = Path(__file__).resolve().parents[2]

    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    context: dict[str, Any] = {"package_version": __version__}
    schema = Path(__file__).parent / "_resources" / "schema"
    if schema.is_dir():
        context["schema_digest"] = artifact_digest(schema)
    if (root / ".git").exists():
        context.update(package_commit=git("rev-parse", "HEAD"),
                       dirty=bool(git("status", "--porcelain", "--untracked-files=no")))
        context["gitlinks"] = git("ls-tree", "HEAD", "submodules/")
    else:
        from .resources import resolve_resources, source_commit
        context["package_commit"] = source_commit(resolve_resources().root)
    return context


def write_operation(output: Path, *, operation: str, inputs: dict[str, Path],
                    command: list[str] | None = None, context: dict | None = None) -> dict:
    dependencies = {}
    for role, path in inputs.items():
        producer = operation_receipt(path)
        dependencies[role] = {"digest": artifact_digest(path),
                              "producer": json_digest(producer) if producer else None}
    data = {"schema_version": VERSION, "operation": operation,
            "context": {**execution_context(), **(context or {})},
            "command": command or [], "inputs": dependencies,
            "output_digest": artifact_digest(output)}
    write_json(receipt_path(output), data)
    return data


def _copy_artifact(source: Path, destination: Path) -> dict:
    digest = artifact_digest(source)
    producer = operation_receipt(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, ignore=lambda _, names: [
            name for name in names if is_receipt(Path(name))])
    else:
        shutil.copyfile(source, destination)
    media_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    return {"path": destination.name, "digest": digest,
            "media_type": "inode/directory" if source.is_dir() else
            media_type,
            "operation": producer}


def write_report(report_dir: Path, *, stage: str, left: Path, right: Path,
                 findings: list[dict], comparator: str, scope: dict | None = None,
                 mode: str = "isolated", status: str = "complete",
                 diagnostics: list[str] | None = None,
                 command: list[str] | None = None,
                 evidence: dict[str, Path] | None = None) -> dict:
    if mode not in {"isolated", "complete-path"} or status not in {"complete", "failed", "skipped"}:
        raise ConfigurationError("Invalid comparison mode or stage status")
    report_dir = Path(report_dir).absolute()
    if report_dir.exists() and any(report_dir.iterdir()):
        raise ConfigurationError(f"Report output is not empty: {report_dir}; choose a new directory")
    sources = {"left": left, "right": right, **(evidence or {})}
    if evidence and (set(evidence) & {"left", "right"}):
        raise ConfigurationError("Additional evidence must not replace left/right inputs")
    for source in sources.values():
        if source.resolve() == report_dir.resolve() or source.resolve() in report_dir.resolve().parents:
            raise ConfigurationError("Report output must be outside its input artifacts")
    report_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for side, source in sources.items():
        if not side or side in {".", ".."} or not all(c.isalnum() or c in "_.-" for c in side):
            raise ConfigurationError("Evidence roles must contain only letters, digits, hyphens and underscores")
        if source.exists():
            destination = report_dir / "artifacts" / (side + (source.suffix if source.is_file() else ""))
            artifacts[side] = _copy_artifact(source, destination)
            artifacts[side]["path"] = destination.relative_to(report_dir).as_posix()
        elif status == "complete":
            raise ConfigurationError(f"Completed comparison has missing {side} evidence: {source}")
    rows = []
    for index, finding in enumerate(findings, start=1):
        rows.append({**finding, "id": f"{stage}:{index}", "stage": stage,
                     "first_boundary": finding.get("first_boundary", "unestablished"),
                     "comparator": comparator, "evidence": list(artifacts)})
    entry = {"stage": stage, "mode": mode, "status": status,
             "scope": scope or {"complete": False}, "comparator": comparator,
             "artifacts": artifacts, "findings": rows,
             "diagnostics": diagnostics or [], "command": command or [], "links": []}
    report = {"schema_version": VERSION, "run_id": str(uuid.uuid4()),
              "context": execution_context(), "stages": [entry]}
    # Validate before publishing the report, including every copied artifact.
    validate_report(report, report_dir)
    write_json(report_dir / "report.json", report)
    lines = [f"# {stage}: {status}", "", f"Mode: {mode}",
             f"Comparator: {comparator}", f"Scope: {canonical(entry['scope'])}",
             f"Raw findings: {len(rows)}", ""]
    if command:
        import shlex
        lines += [f"Reproduce: `{shlex.join(command)}`", ""]
    for side, artifact in artifacts.items():
        operation = artifact.get("operation")
        lines.append(f"{side}: [{artifact['path']}]({artifact['path']})"
                     + (f" ({operation['operation']})" if operation else " (supplied input)"))
    lines += ["", *diagnostics] if diagnostics else [""]
    for row in rows:
        lines += [f"- {row['id']} {row['subject']} {canonical(row['location'])}: {row['change']}",
                  f"  before: {canonical(row.get('before')) if row.get('before_present', True) else '<missing>'}",
                  f"  after: {canonical(row.get('after')) if row.get('after_present', True) else '<missing>'}"]
    (report_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def safe_artifact(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ConfigurationError(f"Artifact path must remain inside the report: {relative!r}")
    path = root / relative
    for parent in (path, *path.parents):
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise ConfigurationError(f"Artifact path contains a symbolic link: {relative}")
    if root.resolve() not in path.resolve().parents:
        raise ConfigurationError(f"Artifact path leaves the report: {relative}")
    return path


def validate_report(report: dict, root: Path) -> None:
    if not isinstance(report, dict) or type(report.get("schema_version")) is not int or report["schema_version"] != VERSION:
        raise ConfigurationError("Unsupported report schema_version; regenerate with this CLI (version 1)")
    if not isinstance(report.get("run_id"), str) or not isinstance(report.get("context"), dict):
        raise ConfigurationError("Report requires run_id and execution context")
    if not isinstance(report.get("stages"), list) or not report["stages"]:
        raise ConfigurationError("Report requires stages")
    ids = set()
    for stage in report["stages"]:
        if not isinstance(stage, dict) or not isinstance(stage.get("stage"), str):
            raise ConfigurationError("Report stage requires a stage identifier")
        if stage.get("status") not in {"complete", "failed", "skipped"} or stage.get("mode") not in {"isolated", "complete-path"}:
            raise ConfigurationError("Report has an invalid stage status or mode")
        if not isinstance(stage.get("scope"), dict) or not isinstance(stage.get("comparator"), str):
            raise ConfigurationError("Stage requires explicit scope and comparator")
        if not isinstance(stage.get("artifacts"), dict) or not isinstance(stage.get("findings"), list):
            raise ConfigurationError("Stage requires artifacts and findings")
        if stage["status"] == "complete" and not {"left", "right"} <= stage["artifacts"].keys():
            raise ConfigurationError("Complete stage requires left and right artifacts")
        for artifact in stage["artifacts"].values():
            if not isinstance(artifact, dict) or not isinstance(artifact.get("media_type"), str):
                raise ConfigurationError("Artifact requires path, digest, and media_type")
            path = safe_artifact(root, artifact.get("path"))
            if artifact_digest(path) != artifact.get("digest"):
                raise ConfigurationError(f"Artifact digest mismatch: {path}")
            operation = artifact.get("operation")
            if operation is not None:
                if (not isinstance(operation, dict) or operation.get("schema_version") != VERSION
                        or operation.get("output_digest") != artifact["digest"]
                        or not isinstance(operation.get("operation"), str)
                        or not isinstance(operation.get("inputs"), dict)
                        or not isinstance(operation.get("context"), dict)):
                    raise ConfigurationError(f"Operation does not describe artifact: {path}")
                for dependency in operation["inputs"].values():
                    if not isinstance(dependency, dict) or not isinstance(dependency.get("digest"), str) or "producer" not in dependency:
                        raise ConfigurationError(f"Operation has an invalid input reference: {path}")
                if stage["status"] == "complete" and operation["context"].get("status", "complete") != "complete":
                    raise ConfigurationError(f"Completed comparison includes a failed operation: {path}")
        for finding in stage["findings"]:
            if not isinstance(finding, dict):
                raise ConfigurationError("Finding must be an object")
            if not isinstance(finding.get("id"), str) or finding["id"] in ids:
                raise ConfigurationError("Finding IDs must be unique within a report")
            ids.add(finding["id"])
            if not isinstance(finding.get("subject"), str) or not isinstance(finding.get("location"), list) or not isinstance(finding.get("change"), str):
                raise ConfigurationError("Finding requires subject, structured location, and change")
            if any(type(part) not in (str, int) for part in finding["location"]):
                raise ConfigurationError("Finding location components must be strings or integers")
            if finding.get("stage") != stage["stage"] or finding.get("comparator") != stage["comparator"]:
                raise ConfigurationError("Finding stage/comparator does not match its report")
            if any(key not in stage["artifacts"] for key in finding.get("evidence", [])):
                raise ConfigurationError("Finding refers to missing evidence")
        canonical(stage)


def load_report(path: Path) -> tuple[dict, Path]:
    source = path / "report.json" if path.is_dir() else path
    data = read_json(source)
    validate_report(data, source.parent)
    return data, source.parent
